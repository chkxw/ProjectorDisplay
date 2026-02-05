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
from projector_display.rendering.renderer import Renderer, PygameRenderer
from projector_display.rendering.primitives import draw_rigidbody
from projector_display.rendering.trajectory import draw_trajectory
from projector_display.core.draw_primitive import DrawPrimitiveType
from projector_display.rendering.debug_layers import GridLayer, FieldLayer
from projector_display.rendering.background import BackgroundRenderer
from projector_display.commands import get_registry
from projector_display.utils.logging import setup_logging, get_logger
from projector_display.utils.profiler import FrameProfiler
from projector_display.storage import init_storage_manager, get_storage_manager
from projector_display.mocap import MocapTracker


# Default configuration
DEFAULT_SOCKET_PORT = 9999
DEFAULT_SOCKET_HOST = "0.0.0.0"
DEFAULT_UPDATE_RATE = 30  # Hz
DEFAULT_BACKGROUND_COLOR = (0, 0, 0)  # Black


class _TimingFC:
    """Wraps FieldCalibrator to accumulate per-method transform timing."""

    __slots__ = ('_fc', 't_convert', 't_world_scale', 't_orientation',
                 'n_convert', 'n_world_scale', 'n_orientation')

    def __init__(self, fc):
        self._fc = fc
        self.t_convert = 0.0
        self.t_world_scale = 0.0
        self.t_orientation = 0.0
        self.n_convert = 0
        self.n_world_scale = 0
        self.n_orientation = 0

    @property
    def elapsed(self):
        return self.t_convert + self.t_world_scale + self.t_orientation

    def convert(self, *args, **kwargs):
        t0 = time.perf_counter()
        result = self._fc.convert(*args, **kwargs)
        self.t_convert += time.perf_counter() - t0
        self.n_convert += 1
        return result

    def world_scale(self, *args, **kwargs):
        t0 = time.perf_counter()
        result = self._fc.world_scale(*args, **kwargs)
        self.t_world_scale += time.perf_counter() - t0
        self.n_world_scale += 1
        return result

    def transform_orientation(self, *args, **kwargs):
        t0 = time.perf_counter()
        result = self._fc.transform_orientation(*args, **kwargs)
        self.t_orientation += time.perf_counter() - t0
        self.n_orientation += 1
        return result

    def __getattr__(self, name):
        return getattr(self._fc, name)


class _CalibrationDumper(yaml.SafeDumper):
    """YAML dumper that uses flow style for lists of scalars (e.g. coordinate pairs)."""
    pass


def _represent_list(dumper, data):
    flow = all(isinstance(item, (int, float)) for item in data)
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=flow)

_CalibrationDumper.add_representer(list, _represent_list)


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
        self.renderer: Optional[Renderer] = None
        self._running = threading.Event()  # F11: Use Event for thread-safe shutdown
        self._running.set()  # Start in running state

        # Server settings
        self.socket_host = DEFAULT_SOCKET_HOST
        self.socket_port = DEFAULT_SOCKET_PORT
        self.update_rate = DEFAULT_UPDATE_RATE
        self.background_color = DEFAULT_BACKGROUND_COLOR
        self.screen_index = 0
        self.renderer_backend = "gles"  # "gles" or "pygame"
        self.fullscreen = False

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
        # Attach server to scene so commands can access it (e.g. set_calibration)
        self.scene._server = self

        # Cached transform values
        self._screen_width = 0
        self._screen_height = 0
        self._world_bounds: Optional[Tuple[float, float, float, float]] = None

        # Profiler (None = disabled, set via enable_profiling())
        self._profiler: Optional[FrameProfiler] = None

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

    def enable_profiling(self, interval: float = 5.0):
        """Enable frame and command profiling with periodic log output.

        Args:
            interval: Seconds between profiling summary logs.
        """
        self._profiler = FrameProfiler(interval=interval)
        self.logger.info(f"Profiling enabled (report every {interval}s)")

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
            self.renderer_backend = display_config.get('renderer', self.renderer_backend)
            self.fullscreen = display_config.get('fullscreen', self.fullscreen)

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

    def apply_calibration(self, calib_data: dict, write_to_disk: bool = True) -> dict:
        """
        Apply new calibration at runtime.

        Validates resolution and screen_field, clears all existing fields,
        registers the new screen field, updates world bounds, and optionally
        writes the calibration to disk.

        Args:
            calib_data: Full calibration dict (resolution, screen_field)
            write_to_disk: Whether to write calibration to the YAML file

        Returns:
            Dict with world_bounds on success

        Raises:
            ValueError: On resolution mismatch or missing fields
        """
        # 1. Validate resolution
        res = calib_data.get('resolution', {})
        w, h = res.get('width'), res.get('height')
        if not w or not h:
            raise ValueError("Missing resolution.width/height")
        if w != self._screen_width or h != self._screen_height:
            raise ValueError(
                f"Resolution mismatch: got {w}x{h}, "
                f"screen is {self._screen_width}x{self._screen_height}"
            )

        # 2. Validate screen_field
        sf = calib_data.get('screen_field', {})
        world_points = sf.get('world_points')
        local_points = sf.get('local_points')
        if not world_points or not local_points:
            raise ValueError("Missing screen_field.world_points/local_points")

        # 3. Register new screen field first (replaces existing atomically,
        #    so the render thread always sees a valid "screen" field)
        fc = self.scene.field_calibrator
        fc.register_field(
            "screen",
            np.array(world_points, dtype=np.float32),
            np.array(local_points, dtype=np.float32)
        )

        # 4. Remove all non-screen fields individually (thread-safe:
        #    "screen" and its transforms remain valid throughout)
        non_screen = [name for name in fc.fields if name != "screen"]
        for name in non_screen:
            del fc.fields[name]
            fc.transform_matrix.pop(name, None)
            fc.transform_matrix["base"].pop(name, None)
            if "screen" in fc.transform_matrix:
                fc.transform_matrix["screen"].pop(name, None)

        # 5. Update world bounds
        world_pts = np.array(world_points)
        self._world_bounds = (
            float(world_pts[:, 0].min()),
            float(world_pts[:, 1].min()),
            float(world_pts[:, 0].max()),
            float(world_pts[:, 1].max())
        )

        # 6. Write to calibration file if requested
        if write_to_disk and self.calibration_path:
            with open(self.calibration_path, 'w') as f:
                yaml.dump(calib_data, f, Dumper=_CalibrationDumper, sort_keys=False)

        self.logger.info(f"Screen field registered. World bounds: {self._world_bounds}")

        return {
            "world_bounds": list(self._world_bounds),
        }

    def _apply_calibration(self) -> bool:
        """Apply loaded calibration after renderer is initialized."""
        if not hasattr(self, '_pending_calibration'):
            return False

        calib_data = self._pending_calibration
        del self._pending_calibration

        try:
            self.apply_calibration(calib_data, write_to_disk=False)
            return True
        except ValueError as e:
            self.logger.error(f"Calibration error: {e}")
            return False

    def init_display(self) -> bool:
        """
        Initialize the renderer.

        Selects renderer backend based on self.renderer_backend ('gles' or 'pygame').

        Returns:
            True if successful
        """
        try:
            if self.renderer_backend == "gles":
                from projector_display.rendering.gles_renderer import GLESRenderer
                self.logger.info("Using GLES2 renderer")
                self.renderer = GLESRenderer(fullscreen=self.fullscreen)
            else:
                self.logger.info("Using pygame software renderer")
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

            # Execute via registry (with optional profiling)
            p = self._profiler
            if p:
                t0 = time.perf_counter()

            registry = get_registry()
            result = registry.execute(action, self.scene, **params)

            if p:
                p.record_command(action, time.perf_counter() - t0)

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

    def batch_world_to_screen(self, points) -> List[Tuple[int, int]]:
        """Convert multiple world coordinate points to screen coordinates in a single batch.

        Args:
            points: Iterable of (x, y) world coordinate pairs

        Returns:
            List of (int, int) screen coordinate tuples
        """
        if "screen" not in self.scene.field_calibrator.fields:
            center = (self._screen_width // 2, self._screen_height // 2)
            return [center] * len(points)

        pts_array = [[float(p[0]), float(p[1])] for p in points]
        screen_pts = self.scene.field_calibrator.convert(pts_array, "base", "screen")
        return [(round(float(sp[0])), round(float(sp[1]))) for sp in screen_pts]

    def render_frame(self):
        """Render a single frame."""
        if not self.renderer:
            return

        p = self._profiler

        if p:
            p.begin_frame()

        # Clear screen
        self.renderer.clear(self.background_color)

        if p:
            p.mark("clear")

        # Get fields snapshot for thread-safe iteration
        fields_snapshot = self.scene.get_fields_snapshot()

        if p:
            p.mark("fields_snap")

        # Render field backgrounds (ADR-10) - before everything else
        self.background_renderer.render_field_backgrounds(
            self.renderer,
            fields_snapshot,
            self.world_to_screen
        )

        if p:
            p.mark("backgrounds")

        # Draw debug layers if enabled
        if self.scene.grid_layer_enabled and self._world_bounds:
            # Apply scene settings to grid layer
            self.grid_layer.show_minor = self.scene.grid_show_minor
            self.grid_layer.major_color = self.scene.grid_major_color
            self.grid_layer.minor_color = self.scene.grid_minor_color
            self.grid_layer.draw(self.renderer, self.world_to_screen, self._world_bounds)

        if self.scene.field_layer_enabled:
            self.field_layer.draw(self.renderer, fields_snapshot, self.world_to_screen)

        if p:
            p.mark("debug_layers")

        # F1: Get snapshot for safe iteration (lock held briefly for copy only)
        rigidbodies_snapshot = self.scene.get_rigidbodies_snapshot()
        drawings_snapshot = self.scene.get_drawings_snapshot()

        if p:
            p.mark("scene_snap")

        # ADR-12: Position-aware size conversion
        fc = self.scene.field_calibrator

        # When profiling, wrap fc to accumulate transform timing
        _tfc = None
        if p:
            _tfc = _TimingFC(fc)
            self.scene.field_calibrator = _tfc
            fc = _tfc

        # Collect all renderables for z-order sorted rendering
        renderables = []
        for rb in rigidbodies_snapshot.values():
            if rb.get_display_position() is not None:
                renderables.append((rb.z_order, rb._z_seq, 'rb', rb))
        for drawing in drawings_snapshot.values():
            renderables.append((drawing.z_order, drawing._z_seq, 'drawing', drawing))

        renderables.sort(key=lambda x: (x[0], x[1]))

        if p:
            # Profiled render loop — track per-body timing
            _t_render_start = time.perf_counter()
            _n_bodies = 0
            _n_draws = 0
            _max_body_t = 0.0
            _sum_body_t = 0.0
            for _, _, item_type, item in renderables:
                _t_item = time.perf_counter()
                if item_type == 'rb':
                    self._render_rigidbody(item, fc)
                    _n_bodies += 1
                else:
                    self._render_drawing(item)
                    _n_draws += 1
                _dt = time.perf_counter() - _t_item
                if item_type == 'rb':
                    _max_body_t = max(_max_body_t, _dt)
                    _sum_body_t += _dt
            _t_render_total = time.perf_counter() - _t_render_start

            # Restore original fc and record transform/draw split
            self.scene.field_calibrator = _tfc._fc
            _t_xform = _tfc.elapsed
            _t_draw = _t_render_total - _t_xform
            p.record("  xform", _t_xform)
            p.record("  draw", _t_draw)
            p.mark("render")

            # Log render sub-breakdown every 60 frames
            if p._frame_count % 60 == 0 and (_n_bodies + _n_draws) > 0:
                _avg_body = (_sum_body_t / _n_bodies * 1000) if _n_bodies else 0
                self.logger.info(
                    f"RENDER: {_n_bodies}rb + {_n_draws}draw in "
                    f"{_t_render_total*1000:.1f}ms "
                    f"(xform={_t_xform*1000:.1f}ms "
                    f"[convert={_tfc.t_convert*1000:.1f}ms×{_tfc.n_convert}, "
                    f"world_scale={_tfc.t_world_scale*1000:.1f}ms×{_tfc.n_world_scale}, "
                    f"orient={_tfc.t_orientation*1000:.1f}ms×{_tfc.n_orientation}], "
                    f"draw={_t_draw*1000:.1f}ms, "
                    f"avg/body={_avg_body:.1f}ms, "
                    f"max/body={_max_body_t*1000:.1f}ms)"
                )
        else:
            for _, _, item_type, item in renderables:
                if item_type == 'rb':
                    self._render_rigidbody(item, fc)
                else:
                    self._render_drawing(item)

        # Update display
        self.renderer.flip()

        if p:
            p.mark("flip")
            p.end_frame()

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
                    "base", "screen", display_pos, effective_orientation
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
                screen_traj = self.batch_world_to_screen(trajectory_points)
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
                self.renderer.draw_circle(screen_pos, screen_radius, rgb, alpha=alpha)
                self.renderer.draw_circle(screen_pos, screen_radius, (0, 0, 0),
                                          alpha=alpha, border=2)
            else:
                thickness = prim.thickness if prim.thickness > 0 else 2
                self.renderer.draw_circle(screen_pos, screen_radius, rgb,
                                          alpha=alpha, border=thickness)

        elif prim.type == DrawPrimitiveType.BOX:
            screen_pos = self.world_to_screen(drawing.world_x, drawing.world_y)
            draw_world_pos = (drawing.world_x, drawing.world_y)
            hw = fc.world_scale(draw_world_pos, prim.width * 0.5)
            hh = fc.world_scale(draw_world_pos, prim.height * 0.5)

            if prim.angle != 0.0:
                if "screen" in self.scene.field_calibrator.fields:
                    screen_angle = self.scene.field_calibrator.transform_orientation(
                        "base", "screen", draw_world_pos, prim.angle
                    )
                else:
                    screen_angle = prim.angle
                cos_a = math.cos(screen_angle)
                sin_a = math.sin(screen_angle)
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
                    self.renderer.draw_polygon(points, rgb, alpha)
                    self.renderer.draw_polygon(points, (0, 0, 0), alpha, 2)
                else:
                    self.renderer.draw_polygon(points, rgb)
                    self.renderer.draw_polygon(points, (0, 0, 0), border=2)
            else:
                thickness = prim.thickness if prim.thickness > 0 else 2
                if alpha < 255:
                    self.renderer.draw_polygon(points, rgb, alpha, thickness)
                else:
                    self.renderer.draw_polygon(points, rgb, border=thickness)

        elif prim.type in (DrawPrimitiveType.LINE, DrawPrimitiveType.ARROW):
            screen_start = self.world_to_screen(drawing.world_x, drawing.world_y)
            screen_end = self.world_to_screen(drawing.world_x2, drawing.world_y2)
            thickness = prim.thickness if prim.thickness > 0 else 2

            if prim.type == DrawPrimitiveType.LINE:
                self.renderer.draw_line(screen_start, screen_end, rgb, alpha, thickness)
            else:
                from projector_display.rendering.primitives import draw_orientation_arrow
                draw_orientation_arrow(self.renderer, screen_start, screen_end, color, thickness)

        elif prim.type == DrawPrimitiveType.POLYGON:
            if prim.vertices and len(prim.vertices) >= 3:
                # Vertices stored as absolute world coords
                points = [self.world_to_screen(vx, vy) for vx, vy in prim.vertices]
                if prim.filled:
                    if alpha < 255:
                        self.renderer.draw_polygon(points, rgb, alpha)
                        self.renderer.draw_polygon(points, (0, 0, 0), alpha, 2)
                    else:
                        self.renderer.draw_polygon(points, rgb)
                        self.renderer.draw_polygon(points, (0, 0, 0), border=2)
                else:
                    thickness = prim.thickness if prim.thickness > 0 else 2
                    if alpha < 255:
                        self.renderer.draw_polygon(points, rgb, alpha, thickness)
                    else:
                        self.renderer.draw_polygon(points, rgb, border=thickness)

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
    parser.add_argument(
        "--renderer", "-r",
        choices=["pygame", "gles"],
        default=None,
        help="Renderer backend (default: gles)"
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        default=False,
        help="Use true fullscreen instead of borderless window (higher perf, but window disappears on focus loss)"
    )
    parser.add_argument(
        "--profile",
        nargs="?",
        const=5.0,
        type=float,
        metavar="INTERVAL",
        help="Enable performance profiling (optional: report interval in seconds, default 5)"
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
    if args.renderer:
        server.renderer_backend = args.renderer
    if args.fullscreen:
        server.fullscreen = True
    if args.profile is not None:
        server.enable_profiling(interval=args.profile)

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
