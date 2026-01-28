#!/usr/bin/env python3
"""
Projector Display Server - Scene-based projector display server for robot experiments.

This server provides:
1. Scene-based architecture with RigidBodies as first-class entities
2. Multiple coordinate Fields per scene
3. JSON/TCP command interface
4. YAML configuration and scene serialization

Based on toolbox_display_server.py from box_push_deploy/shared/.
"""

import os
import sys
import math
import time
import signal
import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import yaml
import numpy as np
import pygame  # F18: Move import to top

from projector_display.core.scene import Scene
from projector_display.core.field_calibrator import FieldCalibrator
from projector_display.rendering.renderer import PygameRenderer
from projector_display.rendering.primitives import draw_rigidbody
from projector_display.rendering.trajectory import draw_trajectory
from projector_display.rendering.debug_layers import GridLayer, FieldLayer
from projector_display.commands import get_registry
from projector_display.utils.logging import setup_logging, get_logger


# Default configuration
DEFAULT_SOCKET_PORT = 9999
DEFAULT_SOCKET_HOST = "0.0.0.0"
DEFAULT_UPDATE_RATE = 30  # Hz
DEFAULT_BACKGROUND_COLOR = (50, 50, 50)


class ProjectorDisplayServer:
    """
    Display server for projector-based robot experiment visualization.

    Architecture:
        Server (single instance)
        └── Scene
            ├── FieldCalibrator (with "screen" field)
            └── RigidBodies
    """

    def __init__(self, config_path: Optional[str] = None,
                 calibration_path: Optional[str] = None,
                 verbose: bool = False):
        """
        Initialize the display server.

        Args:
            config_path: Path to server configuration YAML
            calibration_path: Path to calibration YAML (required)
            verbose: Enable verbose logging
        """
        self.config_path = config_path
        self.calibration_path = calibration_path
        self.verbose = verbose
        self.config: Dict = {}

        # Core components
        self.scene = Scene()
        self.renderer: Optional[PygameRenderer] = None
        self._running = threading.Event()  # F11: Use Event for thread-safe shutdown
        self._running.set()  # Start in running state

        # Server settings
        self.socket_host = DEFAULT_SOCKET_HOST
        self.socket_port = DEFAULT_SOCKET_PORT
        self.update_rate = DEFAULT_UPDATE_RATE
        self.background_color = DEFAULT_BACKGROUND_COLOR
        self.screen_index = 0

        # Networking
        self.server_socket: Optional[socket.socket] = None
        self.socket_thread: Optional[threading.Thread] = None
        self._client_executor: Optional[ThreadPoolExecutor] = None  # F4: Use ThreadPoolExecutor

        # Debug layers
        self.grid_layer = GridLayer()
        self.field_layer = FieldLayer()

        # Cached transform values
        self._screen_width = 0
        self._screen_height = 0
        self._world_bounds: Optional[Tuple[float, float, float, float]] = None

        # Logger
        self.logger = get_logger(__name__)

        # Signal handling
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    @property
    def running(self) -> bool:
        """Check if server is running (thread-safe)."""
        return self._running.is_set()

    @running.setter
    def running(self, value: bool):
        """Set running state (thread-safe)."""
        if value:
            self._running.set()
        else:
            self._running.clear()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        signal_names = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT (Ctrl+C)"}
        signal_name = signal_names.get(signum, f"signal {signum}")
        self.logger.info(f"Shutdown initiated: Received {signal_name}")
        self._running.clear()  # Thread-safe shutdown

    def load_config(self) -> bool:
        """
        Load configuration from YAML file.

        Returns:
            True if successful
        """
        if not self.config_path:
            self.logger.info("No config file specified, using defaults")
            return True

        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                self.logger.error(f"Config file not found: {self.config_path}")
                return False

            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f) or {}

            # Parse server settings
            server_config = self.config.get('server', {})
            self.socket_host = server_config.get('socket_host', DEFAULT_SOCKET_HOST)
            self.socket_port = server_config.get('socket_port', DEFAULT_SOCKET_PORT)

            # Parse display settings
            display_config = self.config.get('display', {})
            self.update_rate = display_config.get('update_rate', DEFAULT_UPDATE_RATE)
            self.screen_index = display_config.get('screen_index', 0)

            bg = display_config.get('background_color', list(DEFAULT_BACKGROUND_COLOR))
            self.background_color = tuple(bg) if isinstance(bg, list) else bg

            self.logger.info(f"Config loaded: socket={self.socket_host}:{self.socket_port}, "
                             f"update_rate={self.update_rate}Hz")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return False

    def load_calibration(self) -> bool:
        """
        Load calibration file to set up the "screen" field.

        The calibration file is REQUIRED. Server refuses to start without it.

        Returns:
            True if successful
        """
        if not self.calibration_path:
            self.logger.error("Calibration file path is required. Use --calibration option.")
            return False

        calib_file = Path(self.calibration_path)
        if not calib_file.exists():
            self.logger.error(f"Calibration file not found: {self.calibration_path}")
            self.logger.error("Server cannot start without a valid calibration file.")
            return False

        try:
            with open(calib_file, 'r') as f:
                calib_data = yaml.safe_load(f)

            # Validate resolution matches current screen
            # (will be validated after renderer init)
            self._pending_calibration = calib_data
            self.logger.info(f"Calibration file loaded: {self.calibration_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load calibration: {e}")
            return False

    def _apply_calibration(self) -> bool:
        """Apply loaded calibration after renderer is initialized."""
        if not hasattr(self, '_pending_calibration'):
            return False

        calib_data = self._pending_calibration
        del self._pending_calibration

        # Check resolution
        stored_resolution = calib_data.get('resolution', {})
        stored_width = stored_resolution.get('width')
        stored_height = stored_resolution.get('height')

        if stored_width and stored_height:
            if stored_width != self._screen_width or stored_height != self._screen_height:
                self.logger.error(f"Calibration resolution mismatch: "
                                  f"stored={stored_width}x{stored_height}, "
                                  f"current={self._screen_width}x{self._screen_height}")
                return False

        # Get screen field data
        screen_field = calib_data.get('screen_field', {})
        world_points = screen_field.get('world_points')
        local_points = screen_field.get('local_points')

        if not world_points or not local_points:
            self.logger.error("Calibration file missing 'screen_field' with world_points and local_points")
            return False

        # Register screen field
        self.scene.field_calibrator.register_field(
            "screen",
            np.array(world_points, dtype=np.float32),
            np.array(local_points, dtype=np.float32)
        )

        # Calculate world bounds from world_points
        world_pts = np.array(world_points)
        self._world_bounds = (
            float(world_pts[:, 0].min()),
            float(world_pts[:, 1].min()),
            float(world_pts[:, 0].max()),
            float(world_pts[:, 1].max())
        )

        self.logger.info(f"Screen field registered. World bounds: {self._world_bounds}")
        return True

    def init_display(self) -> bool:
        """
        Initialize the renderer.

        Returns:
            True if successful
        """
        try:
            self.renderer = PygameRenderer()
            self.renderer.init(screen_index=self.screen_index)

            self._screen_width, self._screen_height = self.renderer.get_size()
            self.logger.info(f"Display initialized: {self._screen_width}x{self._screen_height}")

            # Now apply calibration
            if not self._apply_calibration():
                return False

            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize display: {e}")
            return False

    def start_socket_server(self):
        """Start the socket server in a separate thread."""
        # F4: Use ThreadPoolExecutor for automatic thread cleanup
        self._client_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="client")
        self.socket_thread = threading.Thread(target=self._socket_server_loop, daemon=True)
        self.socket_thread.start()
        self.logger.info(f"Socket server started on {self.socket_host}:{self.socket_port}")

    def _socket_server_loop(self):
        """Main socket server loop."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.socket_host, self.socket_port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    self.logger.info(f"Client connected from {addr}")
                    # F4: Submit to executor instead of raw threads
                    self._client_executor.submit(self._handle_client, client_socket, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Socket accept error: {e}")

        except Exception as e:
            self.logger.error(f"Socket server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def _handle_client(self, client_socket: socket.socket, addr):
        """Handle individual client connections with message buffering."""
        buffer = ""  # F5: Message buffer for partial message handling
        try:
            client_socket.settimeout(5.0)
            while self.running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break

                    # F5: Append to buffer and process complete lines
                    buffer += data.decode("utf-8")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            cmd = json.loads(line)
                            response = self._process_command(cmd)
                            response_str = json.dumps(response) + "\n"
                            client_socket.send(response_str.encode("utf-8"))
                        except json.JSONDecodeError as e:
                            response = {"status": "error", "message": f"Invalid JSON: {e}"}
                            response_str = json.dumps(response) + "\n"
                            client_socket.send(response_str.encode("utf-8"))

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Client handling error: {e}")
                    break

        finally:
            client_socket.close()
            self.logger.info(f"Client disconnected from {addr}")

    def _process_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a command and return response.

        Command format: {"action": "command_name", "param1": value1, ...}

        Never crashes on bad commands - returns error response instead.
        """
        try:
            action = cmd.get("action", cmd.get("cmd", ""))
            if not action:
                return {"status": "error", "message": "Missing 'action' field"}

            # Extract parameters (everything except action/cmd)
            params = {k: v for k, v in cmd.items() if k not in ("action", "cmd")}

            # Execute via registry
            registry = get_registry()
            result = registry.execute(action, self.scene, **params)

            if self.verbose:
                self.logger.debug(f"Command: {action}, Result: {result.get('status')}")

            return result

        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Invalid JSON: {e}"}
        except Exception as e:
            # Log but don't crash
            self.logger.error(f"Command error: {e}")
            return {"status": "error", "message": str(e)}

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        if "screen" not in self.scene.field_calibrator.fields:
            # No calibration - return center of screen
            return (self._screen_width // 2, self._screen_height // 2)

        screen_pos = self.scene.field_calibrator.convert([x, y], "base", "screen")
        # F17: Use round() instead of int() for better accuracy
        return (round(screen_pos[0]), round(screen_pos[1]))

    def meters_to_pixels(self, meters: float) -> int:
        """Convert meters to pixels (approximate, for sizing)."""
        if self._world_bounds is None:
            return round(meters * 100)  # Fallback

        world_width = self._world_bounds[2] - self._world_bounds[0]
        # F10: Explicit check for division by zero
        if world_width <= 0:
            return round(meters * 100)  # Fallback for invalid bounds

        pixels_per_meter = self._screen_width / world_width
        return max(1, round(meters * pixels_per_meter))

    def render_frame(self):
        """Render a single frame."""
        if not self.renderer:
            return

        # Clear screen
        self.renderer.clear(self.background_color)

        # Draw debug layers if enabled
        if self.scene.grid_layer_enabled and self._world_bounds:
            self.grid_layer.draw(self.renderer, self.world_to_screen, self._world_bounds)

        if self.scene.field_layer_enabled:
            self.field_layer.draw(self.renderer, self.scene.field_calibrator,
                                  self.world_to_screen)

        # F1: Get snapshot for safe iteration (lock held briefly for copy only)
        rigidbodies_snapshot = self.scene.get_rigidbodies_snapshot()

        # Draw rigid bodies
        for name, rb in rigidbodies_snapshot.items():
            if rb.position is None:
                continue

            # Convert position to screen coords
            screen_pos = self.world_to_screen(rb.position[0], rb.position[1])
            screen_size = self.meters_to_pixels(rb.style.size)

            # Get screen orientation
            screen_orientation = None
            orientation_end = None

            if rb.orientation is not None or rb._last_orientation != 0:
                effective_orientation = rb.get_effective_orientation()

                # Transform orientation via two-point method
                if "screen" in self.scene.field_calibrator.fields:
                    screen_orientation = self.scene.field_calibrator.transform_orientation(
                        "screen", rb.position, effective_orientation
                    )

                    # Calculate arrow end point
                    arrow_len_world = rb.style.orientation_length
                    world_end = (
                        rb.position[0] + math.cos(effective_orientation) * arrow_len_world,
                        rb.position[1] + math.sin(effective_orientation) * arrow_len_world
                    )
                    orientation_end = self.world_to_screen(world_end[0], world_end[1])
                else:
                    screen_orientation = effective_orientation

            # Get label offset in pixels
            label_offset_pixels = (
                self.meters_to_pixels(rb.style.label_offset[0]),
                self.meters_to_pixels(rb.style.label_offset[1])
            )

            # Draw trajectory first (behind rigid body)
            if rb.trajectory_style.enabled:
                trajectory_points = rb.get_trajectory_points()
                if len(trajectory_points) >= 2:
                    screen_traj = [self.world_to_screen(p[0], p[1]) for p in trajectory_points]
                    draw_trajectory(self.renderer, screen_traj, rb.trajectory_style,
                                    self.meters_to_pixels)

            # Draw the rigid body
            draw_rigidbody(self.renderer, rb, screen_pos, screen_size,
                           screen_orientation, orientation_end, label_offset_pixels)

        # Update display
        self.renderer.flip()

    def run(self):
        """Main server loop."""
        self.logger.info("Starting render loop...")

        try:
            while self.running:
                # Handle pygame events (F18: pygame imported at top of file)
                for event in self.renderer.get_events():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key == pygame.K_g:
                            self.scene.toggle_grid_layer()
                        elif event.key == pygame.K_f:
                            self.scene.toggle_field_layer()

                # Render
                self.render_frame()

                # Tick
                self.renderer.tick(self.update_rate)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Render loop error: {e}")
            raise
        finally:
            # F14: Ensure proper cleanup on any exception
            self.shutdown()

    def shutdown(self):
        """Clean shutdown."""
        self.logger.info("Shutting down...")
        self._running.clear()

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        # F4: Shutdown thread pool executor
        if self._client_executor:
            self._client_executor.shutdown(wait=False)

        # F14: Ensure pygame is properly quit
        if self.renderer:
            try:
                self.renderer.quit()
            except Exception:
                pass

        self.logger.info("Shutdown complete")


def main():
    """Entry point for the display server."""
    parser = argparse.ArgumentParser(
        description="Projector Display Server - Scene-based visualization for robot experiments"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to server configuration YAML"
    )
    parser.add_argument(
        "--calibration", "-C",
        required=True,
        help="Path to calibration YAML (required)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        help=f"Socket port (default: {DEFAULT_SOCKET_PORT})"
    )
    parser.add_argument(
        "--host",
        help=f"Socket host (default: {DEFAULT_SOCKET_HOST})"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)

    # Create server
    server = ProjectorDisplayServer(
        config_path=args.config,
        calibration_path=args.calibration,
        verbose=args.verbose
    )

    # Override with command line args
    if args.port:
        server.socket_port = args.port
    if args.host:
        server.socket_host = args.host

    # Load configuration
    if not server.load_config():
        sys.exit(1)

    # Load calibration
    if not server.load_calibration():
        sys.exit(1)

    # Initialize display
    if not server.init_display():
        sys.exit(1)

    # Start socket server
    server.start_socket_server()

    # Run main loop
    server.run()


if __name__ == "__main__":
    main()
