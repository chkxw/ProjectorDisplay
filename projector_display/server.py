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
from projector_display.core.draw_primitive import DrawPrimitiveType
from projector_display.rendering.debug_layers import GridLayer, FieldLayer
from projector_display.rendering.background import BackgroundRenderer
from projector_display.commands import get_registry
from projector_display.utils.logging import setup_logging, get_logger
from projector_display.storage import init_storage_manager, get_storage_manager
from projector_display.mocap import MocapTracker


# Default configuration
DEFAULT_SOCKET_PORT = 9999
DEFAULT_SOCKET_HOST = "0.0.0.0"
DEFAULT_UPDATE_RATE = 30  # Hz
DEFAULT_BACKGROUND_COLOR = (0, 0, 0)  # Black


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

        # Initialize storage manager for this session (ADR-10)
        self.storage = init_storage_manager()

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

        # Background renderer (ADR-10)
        self.background_renderer = BackgroundRenderer()

        # MoCap tracker (optional integration)
        self.mocap_tracker = MocapTracker(self.scene)
        # Attach tracker to scene so commands can access it
        self.scene._mocap_tracker = self.mocap_tracker

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
        """Handle shutdown signals. Second signal forces immediate exit."""
        signal_names = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT (Ctrl+C)"}
        signal_name = signal_names.get(signum, f"signal {signum}")

        if not self._running.is_set():
            # Already shutting down, force exit
            self.logger.info(f"Force exit: Received {signal_name} during shutdown")
            import os
            os._exit(1)

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

    def render_frame(self):
        """Render a single frame."""
        if not self.renderer:
            return

        # Clear screen
        self.renderer.clear(self.background_color)

        # Get fields snapshot for thread-safe iteration
        fields_snapshot = self.scene.get_fields_snapshot()

        # Render field backgrounds (ADR-10) - before everything else
        self.background_renderer.render_field_backgrounds(
            self.renderer,
            fields_snapshot,
            self.world_to_screen
        )

        # Draw debug layers if enabled
        if self.scene.grid_layer_enabled and self._world_bounds:
            # Apply scene settings to grid layer
            self.grid_layer.show_minor = self.scene.grid_show_minor
            self.grid_layer.major_color = self.scene.grid_major_color
            self.grid_layer.minor_color = self.scene.grid_minor_color
            self.grid_layer.draw(self.renderer, self.world_to_screen, self._world_bounds)

        if self.scene.field_layer_enabled:
            self.field_layer.draw(self.renderer, fields_snapshot, self.world_to_screen)

        # F1: Get snapshot for safe iteration (lock held briefly for copy only)
        rigidbodies_snapshot = self.scene.get_rigidbodies_snapshot()
        drawings_snapshot = self.scene.get_drawings_snapshot()

        # ADR-12: Position-aware size conversion
        fc = self.scene.field_calibrator

        # Collect all renderables for z-order sorted rendering
        renderables = []
        for rb in rigidbodies_snapshot.values():
            if rb.get_display_position() is not None:
                renderables.append((rb.z_order, rb._z_seq, 'rb', rb))
        for drawing in drawings_snapshot.values():
            renderables.append((drawing.z_order, drawing._z_seq, 'drawing', drawing))

        renderables.sort(key=lambda x: (x[0], x[1]))

        for _, _, item_type, item in renderables:
            if item_type == 'rb':
                self._render_rigidbody(item, fc)
            else:
                self._render_drawing(item)

        # Update display
        self.renderer.flip()

    def _render_rigidbody(self, rb, fc):
        """Render a single rigid body with trajectory, shape, orientation, and label.

        Args:
            rb: RigidBody snapshot to render
            fc: FieldCalibrator for coordinate conversion
        """
        display_pos = rb.get_display_position()
        # Convert position to screen coords
        screen_pos = self.world_to_screen(display_pos[0], display_pos[1])
        screen_size = fc.world_scale(display_pos, rb.style.size)

        # Get screen orientation
        screen_orientation = None
        orientation_end = None

        display_orient = rb.get_display_orientation()
        if display_orient is not None or rb._last_orientation != 0:
            effective_orientation = rb.get_effective_orientation()

            # Transform orientation via two-point method
            if "screen" in self.scene.field_calibrator.fields:
                screen_orientation = self.scene.field_calibrator.transform_orientation(
                    "screen", display_pos, effective_orientation
                )

                # Calculate arrow end point
                arrow_len_world = rb.style.orientation_length
                world_end = (
                    display_pos[0] + math.cos(effective_orientation) * arrow_len_world,
                    display_pos[1] + math.sin(effective_orientation) * arrow_len_world
                )
                orientation_end = self.world_to_screen(world_end[0], world_end[1])
            else:
                screen_orientation = effective_orientation

        # Get label offset in pixels (ADR-12: signed distance scaling)
        lo = rb.style.label_offset
        label_offset_pixels = (
            int(math.copysign(fc.world_scale(display_pos, abs(lo[0])), lo[0])) if lo[0] else 0,
            int(math.copysign(fc.world_scale(display_pos, abs(lo[1])), lo[1])) if lo[1] else 0,
        )

        # Draw trajectory first (behind rigid body)
        if rb.trajectory_style.enabled:
            trajectory_points = rb.get_trajectory_points()
            if len(trajectory_points) >= 2:
                screen_traj = [self.world_to_screen(p[0], p[1]) for p in trajectory_points]
                # ADR-12: Bind scale to rigid body position
                scale_at_pos = lambda d, pos=display_pos: fc.world_scale(pos, d)
                draw_trajectory(self.renderer, screen_traj, rb.trajectory_style,
                                scale_at_pos)

        # Draw the rigid body
        draw_rigidbody(self.renderer, rb, screen_pos, screen_size,
                       screen_orientation, orientation_end, label_offset_pixels)

    def _render_drawing(self, drawing):
        """Render a single persistent drawing overlay.

        Converts world coordinates to screen and dispatches to renderer
        based on primitive type.
        """
        prim = drawing.primitive
        color = prim.color
        alpha = color[3] if len(color) == 4 else 255
        rgb = color[:3]

        # ADR-12: Position-aware size conversion for drawings
        fc = self.scene.field_calibrator
        if prim.type == DrawPrimitiveType.CIRCLE:
            screen_pos = self.world_to_screen(drawing.world_x, drawing.world_y)
            draw_world_pos = (drawing.world_x, drawing.world_y)
            screen_radius = fc.world_scale(draw_world_pos, prim.radius)
            if prim.filled:
                if alpha < 255:
                    from projector_display.rendering.primitives import _circle_to_polygon
                    pts = _circle_to_polygon(screen_pos, screen_radius, 32)
                    self.renderer.draw_polygon_alpha(pts, rgb, alpha)
                    self.renderer.draw_polygon_alpha(pts, (0, 0, 0), alpha, 2)
                else:
                    self.renderer.draw_circle(screen_pos, screen_radius, rgb)
                    self.renderer.draw_circle(screen_pos, screen_radius, (0, 0, 0), 2)
            else:
                thickness = prim.thickness if prim.thickness > 0 else 2
                if alpha < 255:
                    from projector_display.rendering.primitives import _circle_to_polygon
                    pts = _circle_to_polygon(screen_pos, screen_radius, 32)
                    self.renderer.draw_polygon_alpha(pts, rgb, alpha, thickness)
                else:
                    self.renderer.draw_circle(screen_pos, screen_radius, rgb, thickness)

        elif prim.type == DrawPrimitiveType.BOX:
            screen_pos = self.world_to_screen(drawing.world_x, drawing.world_y)
            draw_world_pos = (drawing.world_x, drawing.world_y)
            hw = fc.world_scale(draw_world_pos, prim.width * 0.5)
            hh = fc.world_scale(draw_world_pos, prim.height * 0.5)

            if prim.angle != 0.0:
                cos_a = math.cos(prim.angle)
                sin_a = math.sin(prim.angle)
                corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
                points = []
                for bx, by in corners:
                    rx = bx * cos_a - by * sin_a
                    ry = bx * sin_a + by * cos_a
                    points.append((screen_pos[0] + int(rx), screen_pos[1] + int(ry)))
            else:
                points = [
                    (screen_pos[0] - hw, screen_pos[1] - hh),
                    (screen_pos[0] + hw, screen_pos[1] - hh),
                    (screen_pos[0] + hw, screen_pos[1] + hh),
                    (screen_pos[0] - hw, screen_pos[1] + hh),
                ]

            if prim.filled:
                if alpha < 255:
                    self.renderer.draw_polygon_alpha(points, rgb, alpha)
                    self.renderer.draw_polygon_alpha(points, (0, 0, 0), alpha, 2)
                else:
                    self.renderer.draw_polygon(points, rgb)
                    self.renderer.draw_polygon(points, (0, 0, 0), 2)
            else:
                thickness = prim.thickness if prim.thickness > 0 else 2
                if alpha < 255:
                    self.renderer.draw_polygon_alpha(points, rgb, alpha, thickness)
                else:
                    self.renderer.draw_polygon(points, rgb, thickness)

        elif prim.type in (DrawPrimitiveType.LINE, DrawPrimitiveType.ARROW):
            screen_start = self.world_to_screen(drawing.world_x, drawing.world_y)
            screen_end = self.world_to_screen(drawing.world_x2, drawing.world_y2)
            thickness = prim.thickness if prim.thickness > 0 else 2

            if prim.type == DrawPrimitiveType.LINE:
                if alpha < 255:
                    self.renderer.draw_line_alpha(screen_start, screen_end, rgb, alpha, thickness)
                else:
                    self.renderer.draw_line(screen_start, screen_end, rgb, thickness)
            else:
                from projector_display.rendering.primitives import draw_orientation_arrow
                draw_orientation_arrow(self.renderer, screen_start, screen_end, color, thickness)

        elif prim.type == DrawPrimitiveType.POLYGON:
            if prim.vertices and len(prim.vertices) >= 3:
                # Vertices stored as absolute world coords
                points = [self.world_to_screen(vx, vy) for vx, vy in prim.vertices]
                if prim.filled:
                    if alpha < 255:
                        self.renderer.draw_polygon_alpha(points, rgb, alpha)
                        self.renderer.draw_polygon_alpha(points, (0, 0, 0), alpha, 2)
                    else:
                        self.renderer.draw_polygon(points, rgb)
                        self.renderer.draw_polygon(points, (0, 0, 0), 2)
                else:
                    thickness = prim.thickness if prim.thickness > 0 else 2
                    if alpha < 255:
                        self.renderer.draw_polygon_alpha(points, rgb, alpha, thickness)
                    else:
                        self.renderer.draw_polygon(points, rgb, thickness)

        elif prim.type == DrawPrimitiveType.TEXT:
            screen_pos = self.world_to_screen(drawing.world_x, drawing.world_y)
            self.renderer.draw_text(prim.text, screen_pos, rgb, prim.font_size, (0, 0, 0))

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

        # ADR-10: Clean up session temp directory
        if self.storage:
            self.storage.cleanup_session()

        # Shutdown MoCap tracker
        if self.mocap_tracker:
            self.mocap_tracker.shutdown()

        self.logger.info("Shutdown complete")


def main():
    """Entry point for the display server."""
    # Get default calibration path from storage manager
    storage = get_storage_manager()
    default_calibration = storage.get_calibration_path()

    parser = argparse.ArgumentParser(
        description="Projector Display Server - Scene-based visualization for robot experiments"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to server configuration YAML"
    )
    parser.add_argument(
        "--calibration", "-C",
        default=str(default_calibration),
        help=f"Path to calibration YAML (default: {default_calibration})"
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
