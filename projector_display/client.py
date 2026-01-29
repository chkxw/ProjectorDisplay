#!/usr/bin/env python3
"""
Display client for projector display server.

Provides a simple Python API for communicating with the display server.
Based on display_client.py from box_push_deploy/shared/.

ADR-10: Includes helper methods for image upload and field background management.
"""

import base64
import hashlib
import socket
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from projector_display.mocap import DEFAULT_NATNET_PORT

logger = logging.getLogger(__name__)


class DisplayClient:
    """
    Socket client for projector display server.

    All coordinates are in world units (meters) unless a field is specified.
    The display server handles transformation to screen pixels.

    Usage:
        # Basic usage
        client = DisplayClient("192.168.0.100")
        client.connect()
        client.update_position("robot1", 1.0, 2.0, orientation=0.5)
        client.disconnect()

        # Context manager
        with DisplayClient("192.168.0.100") as client:
            client.update_position("robot1", 1.0, 2.0)

        # With auto-reconnect (F15)
        client = DisplayClient("192.168.0.100", auto_reconnect=True)
    """

    def __init__(self, host: str, port: int = 9999, timeout: float = 5.0,
                 auto_reconnect: bool = False, max_reconnect_attempts: int = 3):
        """
        Initialize display client.

        Args:
            host: Display server IP address
            port: Display server port (default: 9999)
            timeout: Socket timeout in seconds
            auto_reconnect: F15 - Automatically reconnect on connection loss
            max_reconnect_attempts: Maximum reconnection attempts
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.socket: Optional[socket.socket] = None
        self._connected = False
        self._recv_buffer = ""  # F5: Buffer for partial message handling

    def connect(self) -> bool:
        """
        Connect to the display server.

        Returns:
            True if connection successful
        """
        # F8: Close existing socket first if any
        self._close_socket()

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self._connected = True
            self._recv_buffer = ""  # F5: Reset buffer on new connection
            logger.info(f"Connected to display server at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to display server: {e}")
            self._close_socket()  # F8: Ensure socket is closed on error
            return False

    def _close_socket(self):
        """F8: Helper to properly close socket and reset state."""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
        self._connected = False
        self._recv_buffer = ""

    def disconnect(self):
        """Disconnect from the display server."""
        self._close_socket()
        logger.info("Disconnected from display server")

    def _try_reconnect(self) -> bool:
        """F15: Attempt to reconnect to the server."""
        if not self.auto_reconnect:
            return False

        for attempt in range(self.max_reconnect_attempts):
            logger.info(f"Reconnection attempt {attempt + 1}/{self.max_reconnect_attempts}")
            if self.connect():
                return True
            import time
            time.sleep(0.5 * (attempt + 1))  # Exponential backoff

        logger.error("Failed to reconnect after maximum attempts")
        return False

    @property
    def is_connected(self) -> bool:
        """Check if connected to display server."""
        return self._connected

    def _send_command(self, cmd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send command to display server and get response.

        Args:
            cmd: Command dictionary

        Returns:
            Response dictionary or None on error
        """
        if not self._connected:
            # F15: Try to reconnect if enabled
            if self.auto_reconnect and self._try_reconnect():
                pass  # Continue with command
            else:
                logger.warning("Not connected to display server")
                return None

        try:
            cmd_str = json.dumps(cmd) + '\n'
            self.socket.send(cmd_str.encode('utf-8'))

            # F5: Buffer-based message receiving
            while "\n" not in self._recv_buffer:
                data = self.socket.recv(4096)
                if not data:
                    raise ConnectionError("Server closed connection")
                self._recv_buffer += data.decode('utf-8')

            line, self._recv_buffer = self._recv_buffer.split("\n", 1)
            return json.loads(line.strip())

        except Exception as e:
            logger.error(f"Command failed: {e}")
            self._close_socket()  # F8: Close socket on error

            # F15: Try to reconnect and retry once
            if self.auto_reconnect and self._try_reconnect():
                try:
                    cmd_str = json.dumps(cmd) + '\n'
                    self.socket.send(cmd_str.encode('utf-8'))
                    while "\n" not in self._recv_buffer:
                        data = self.socket.recv(4096)
                        if not data:
                            raise ConnectionError("Server closed connection")
                        self._recv_buffer += data.decode('utf-8')
                    line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                    return json.loads(line.strip())
                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}")
                    self._close_socket()

            return None

    # --- RigidBody Commands ---

    def create_rigidbody(self, name: str, style: dict = None,
                         trajectory: dict = None, mocap_name: str = None,
                         auto_track: bool = False) -> Optional[Dict]:
        """
        Create a new rigid body.

        Args:
            name: Unique identifier
            style: Optional style configuration
            trajectory: Optional trajectory configuration
            mocap_name: Optional MoCap system name
            auto_track: Enable auto-tracking from MoCap (requires MoCap enabled)

        Returns:
            Response dictionary
        """
        cmd = {"action": "create_rigidbody", "name": name}
        if style:
            cmd["style"] = style
        if trajectory:
            cmd["trajectory"] = trajectory
        if mocap_name:
            cmd["mocap_name"] = mocap_name
        if auto_track:
            cmd["auto_track"] = auto_track
        return self._send_command(cmd)

    def remove_rigidbody(self, name: str) -> Optional[Dict]:
        """Remove a rigid body."""
        return self._send_command({"action": "remove_rigidbody", "name": name})

    def update_position(self, name: str, x: float, y: float,
                        orientation: Optional[float] = None,
                        field: str = "base") -> Optional[Dict]:
        """
        Update rigid body position.

        Creates rigid body if it doesn't exist (with default style).

        Args:
            name: Rigid body name
            x: X position in field coordinates
            y: Y position in field coordinates
            orientation: Orientation in radians (optional)
            field: Coordinate field for interpretation (default: "base" = world)

        Returns:
            Response dictionary
        """
        cmd = {
            "action": "update_position",
            "name": name,
            "x": x,
            "y": y,
            "field": field
        }
        if orientation is not None:
            cmd["orientation"] = orientation
        return self._send_command(cmd)

    def update_style(self, name: str, **style_params) -> Optional[Dict]:
        """
        Update rigid body visualization style.

        Args:
            name: Rigid body name
            **style_params: Style parameters (shape, size, color, etc.)

        Returns:
            Response dictionary
        """
        cmd = {"action": "update_style", "name": name}
        cmd.update(style_params)
        return self._send_command(cmd)

    def update_trajectory(self, name: str, **traj_params) -> Optional[Dict]:
        """
        Update rigid body trajectory style.

        Args:
            name: Rigid body name
            **traj_params: Trajectory parameters

        Returns:
            Response dictionary
        """
        cmd = {"action": "update_trajectory", "name": name}
        cmd.update(traj_params)
        return self._send_command(cmd)

    def get_rigidbody(self, name: str) -> Optional[Dict]:
        """Get rigid body state."""
        return self._send_command({"action": "get_rigidbody", "name": name})

    def list_rigidbodies(self) -> Optional[Dict]:
        """List all rigid body names."""
        return self._send_command({"action": "list_rigidbodies"})

    # --- Field Commands ---

    def create_field(self, name: str, world_points: List[List[float]],
                     local_points: List[List[float]]) -> Optional[Dict]:
        """
        Create a new coordinate field.

        Args:
            name: Unique identifier
            world_points: 4x2 array of world coordinates [BL, BR, TR, TL]
            local_points: 4x2 array of local coordinates [BL, BR, TR, TL]

        Returns:
            Response dictionary
        """
        return self._send_command({
            "action": "create_field",
            "name": name,
            "world_points": world_points,
            "local_points": local_points
        })

    def remove_field(self, name: str) -> Optional[Dict]:
        """Remove a coordinate field."""
        return self._send_command({"action": "remove_field", "name": name})

    def list_fields(self) -> Optional[Dict]:
        """List all registered field names."""
        return self._send_command({"action": "list_fields"})

    def get_field(self, name: str) -> Optional[Dict]:
        """Get field information."""
        return self._send_command({"action": "get_field", "name": name})

    def set_calibration(self, calibration: dict) -> Optional[Dict]:
        """
        Apply new calibration at runtime.

        Validates resolution, replaces the screen field, clears all
        user-defined fields, and writes the calibration to disk.

        Args:
            calibration: Full calibration dict with resolution and screen_field

        Returns:
            Response with status and world_bounds on success
        """
        return self._send_command({
            "action": "set_calibration",
            "calibration": calibration
        })

    # --- Scene Commands ---

    def clear_scene(self) -> Optional[Dict]:
        """Clear all rigid bodies (keeps fields)."""
        return self._send_command({"action": "clear_scene"})

    def clear_all(self) -> Optional[Dict]:
        """Clear everything including fields (except screen)."""
        return self._send_command({"action": "clear_all"})

    def dump_scene(self) -> Optional[Dict]:
        """Dump scene state for serialization."""
        return self._send_command({"action": "dump_scene"})

    def get_scene(self) -> Optional[Dict]:
        """Get full scene state."""
        return self._send_command({"action": "get_scene"})

    def load_scene(self, scene_data: dict) -> Optional[Dict]:
        """Load scene from dumped data."""
        return self._send_command({"action": "load_scene", "scene_data": scene_data})

    def status(self) -> Optional[Dict]:
        """Get server status."""
        return self._send_command({"action": "status"})

    # --- Debug Commands ---

    def toggle_grid_layer(self) -> Optional[Dict]:
        """Toggle grid layer visibility."""
        return self._send_command({"action": "toggle_grid_layer"})

    def toggle_field_layer(self) -> Optional[Dict]:
        """Toggle field layer visibility."""
        return self._send_command({"action": "toggle_field_layer"})

    def set_grid_layer(self, enabled: bool) -> Optional[Dict]:
        """Set grid layer visibility."""
        return self._send_command({"action": "set_grid_layer", "enabled": enabled})

    def set_field_layer(self, enabled: bool) -> Optional[Dict]:
        """Set field layer visibility."""
        return self._send_command({"action": "set_field_layer", "enabled": enabled})

    def configure_grid_layer(self,
                             show_minor: bool = None,
                             major_color: list = None,
                             minor_color: list = None) -> Optional[Dict]:
        """
        Configure grid layer settings.

        Args:
            show_minor: Whether to show minor (0.1m) grid lines
            major_color: RGB color for major grid lines [r, g, b]
            minor_color: RGB color for minor grid lines [r, g, b]
        """
        cmd = {"action": "configure_grid_layer"}
        if show_minor is not None:
            cmd["show_minor"] = show_minor
        if major_color is not None:
            cmd["major_color"] = major_color
        if minor_color is not None:
            cmd["minor_color"] = minor_color
        return self._send_command(cmd)

    def get_grid_settings(self) -> Optional[Dict]:
        """Get current grid layer settings."""
        return self._send_command({"action": "get_grid_settings"})

    # --- Asset Commands (ADR-10) ---

    def check_image(self, name: str, file_hash: Optional[str] = None) -> Optional[Dict]:
        """
        Check if an image exists on the server.

        Args:
            name: Image filename
            file_hash: Optional SHA256 hash (first 16 chars) to verify

        Returns:
            Response with existence and hash match info
        """
        cmd = {"action": "check_image", "name": name}
        if file_hash:
            cmd["hash"] = file_hash
        return self._send_command(cmd)

    def upload_image(self, name: str, data: str) -> Optional[Dict]:
        """
        Upload base64-encoded image to the server.

        Args:
            name: Image filename
            data: Base64-encoded image data

        Returns:
            Response with upload result
        """
        return self._send_command({
            "action": "upload_image",
            "name": name,
            "data": data
        })

    def list_images(self) -> Optional[Dict]:
        """List all images in the session."""
        return self._send_command({"action": "list_images"})

    def delete_image(self, name: str) -> Optional[Dict]:
        """Delete an image from the session."""
        return self._send_command({"action": "delete_image", "name": name})

    def set_field_background_cmd(self, field: str, image: str,
                                  alpha: int = 255) -> Optional[Dict]:
        """
        Set field background (low-level command).

        Image must already be uploaded.

        Args:
            field: Field name
            image: Image filename (already uploaded)
            alpha: Opacity (0-255)

        Returns:
            Response with result
        """
        return self._send_command({
            "action": "set_field_background",
            "field": field,
            "image": image,
            "alpha": alpha
        })

    def remove_field_background(self, field: str) -> Optional[Dict]:
        """Remove background from a field."""
        return self._send_command({
            "action": "remove_field_background",
            "field": field
        })

    # --- High-Level Image Helper (ADR-10) ---

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """Compute SHA256 hash (first 16 chars) of a file."""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    @staticmethod
    def _encode_file_base64(file_path: Path) -> str:
        """Read file and encode as base64."""
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('ascii')

    def set_field_background(self, field: str, image_path: Union[str, Path],
                             alpha: int = 255) -> Optional[Dict]:
        """
        Set a field's background image with automatic upload if needed.

        This high-level helper orchestrates the 3-step flow:
        1. Compute local file hash
        2. Check if server has the image (skip upload if hash matches)
        3. Upload image if needed
        4. Set the field background

        Args:
            field: Field name to set background for
            image_path: Path to the local image file
            alpha: Opacity (0-255, default 255 = fully opaque)

        Returns:
            Response with result, or None on error
        """
        image_path = Path(image_path)

        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return {"status": "error", "message": f"File not found: {image_path}"}

        # Use just the filename for server storage
        image_name = image_path.name

        # Step 1: Compute local file hash
        local_hash = self._compute_file_hash(image_path)
        logger.debug(f"Local image hash: {local_hash}")

        # Step 2: Check if server has this image
        check_result = self.check_image(image_name, local_hash)
        if check_result is None:
            return None

        need_upload = True

        if check_result.get("exists"):
            if check_result.get("hash_match"):
                # Image exists and matches - no upload needed
                logger.info(f"Image '{image_name}' already on server (hash matches)")
                need_upload = False
            else:
                # Image exists but different content - will replace
                logger.warning(f"Image '{image_name}' exists on server but differs, will replace")
        else:
            logger.debug(f"Image '{image_name}' not found on server, uploading")

        # Step 3: Upload if needed
        if need_upload:
            image_data = self._encode_file_base64(image_path)
            upload_result = self.upload_image(image_name, image_data)

            if upload_result is None:
                return None

            if upload_result.get("status") != "success":
                logger.error(f"Failed to upload image: {upload_result.get('message')}")
                return upload_result

            logger.info(f"Uploaded image: {upload_result.get('message')}")

        # Step 4: Set the field background
        result = self.set_field_background_cmd(field, image_name, alpha)

        if result and result.get("status") == "success":
            logger.info(f"Set background for field '{field}': {image_name} (alpha={alpha})")

        return result

    # --- Scene Persistence Commands (ADR-10) ---

    def save_scene(self, name: str) -> Optional[Dict]:
        """
        Save current scene to persistent storage.

        Args:
            name: Name for the saved scene

        Returns:
            Response with save result
        """
        return self._send_command({"action": "save_scene", "name": name})

    def load_scene_from_file(self, name: str) -> Optional[Dict]:
        """
        Load scene from persistent storage.

        Args:
            name: Name of the saved scene

        Returns:
            Response with load result
        """
        return self._send_command({"action": "load_scene_from_file", "name": name})

    def list_saved_scenes(self) -> Optional[Dict]:
        """List all saved scenes."""
        return self._send_command({"action": "list_saved_scenes"})

    def delete_saved_scene(self, name: str) -> Optional[Dict]:
        """
        Delete a saved scene.

        Args:
            name: Name of the scene to delete

        Returns:
            Response with deletion result
        """
        return self._send_command({"action": "delete_saved_scene", "name": name})

    # --- MoCap Commands ---

    def set_mocap(self, ip: str, port: int = DEFAULT_NATNET_PORT,
                  enabled: bool = True) -> Optional[Dict]:
        """
        Configure MoCap server connection.

        Args:
            ip: MoCap server IP address
            port: NatNet port (default DEFAULT_NATNET_PORT)
            enabled: Enable MoCap immediately (default True)

        Returns:
            Response with configuration result
        """
        return self._send_command({
            "action": "set_mocap",
            "ip": ip,
            "port": port,
            "enabled": enabled
        })

    def enable_mocap(self) -> Optional[Dict]:
        """Enable MoCap integration (uses saved config)."""
        return self._send_command({"action": "enable_mocap"})

    def disable_mocap(self) -> Optional[Dict]:
        """Disable MoCap integration (keeps config)."""
        return self._send_command({"action": "disable_mocap"})

    def get_mocap_status(self) -> Optional[Dict]:
        """Get MoCap status information."""
        return self._send_command({"action": "get_mocap_status"})

    def get_mocap_bodies(self) -> Optional[Dict]:
        """Get list of rigid bodies available in MoCap system."""
        return self._send_command({"action": "get_mocap_bodies"})

    def set_auto_track(self, name: str, mocap_name: str = None,
                       enabled: bool = True) -> Optional[Dict]:
        """
        Configure auto-tracking for a rigidbody.

        Args:
            name: Rigidbody name
            mocap_name: Name in MoCap system (optional, updates if provided)
            enabled: Enable auto-tracking (default True)

        Returns:
            Response with result
        """
        cmd = {"action": "set_auto_track", "name": name, "enabled": enabled}
        if mocap_name is not None:
            cmd["mocap_name"] = mocap_name
        return self._send_command(cmd)

    def enable_tracking(self, name: str) -> Optional[Dict]:
        """Enable auto-tracking for a rigidbody."""
        return self._send_command({"action": "enable_tracking", "name": name})

    def disable_tracking(self, name: str) -> Optional[Dict]:
        """Disable auto-tracking for a rigidbody."""
        return self._send_command({"action": "disable_tracking", "name": name})

    # --- Drawing Commands ---

    def draw_circle(self, id: str, x: float, y: float, radius: float,
                    color=None, field: str = "base", **kwargs) -> Optional[Dict]:
        """Draw a persistent circle overlay."""
        cmd = {"action": "draw_circle", "id": id, "x": x, "y": y,
               "radius": radius, "field": field}
        if color is not None:
            cmd["color"] = color
        cmd.update(kwargs)
        return self._send_command(cmd)

    def draw_box(self, id: str, x: float, y: float,
                 width: float, height: float,
                 color=None, field: str = "base", **kwargs) -> Optional[Dict]:
        """Draw a persistent box/rectangle overlay."""
        cmd = {"action": "draw_box", "id": id, "x": x, "y": y,
               "width": width, "height": height, "field": field}
        if color is not None:
            cmd["color"] = color
        cmd.update(kwargs)
        return self._send_command(cmd)

    def draw_line(self, id: str, x1: float, y1: float,
                  x2: float, y2: float,
                  color=None, thickness: int = 2,
                  field: str = "base") -> Optional[Dict]:
        """Draw a persistent line overlay."""
        cmd = {"action": "draw_line", "id": id,
               "x1": x1, "y1": y1, "x2": x2, "y2": y2,
               "thickness": thickness, "field": field}
        if color is not None:
            cmd["color"] = color
        return self._send_command(cmd)

    def draw_arrow(self, id: str, x1: float, y1: float,
                   x2: float, y2: float,
                   color=None, thickness: int = 2,
                   field: str = "base") -> Optional[Dict]:
        """Draw a persistent arrow overlay."""
        cmd = {"action": "draw_arrow", "id": id,
               "x1": x1, "y1": y1, "x2": x2, "y2": y2,
               "thickness": thickness, "field": field}
        if color is not None:
            cmd["color"] = color
        return self._send_command(cmd)

    def draw_polygon(self, id: str, vertices: list,
                     color=None, field: str = "base", **kwargs) -> Optional[Dict]:
        """Draw a persistent polygon overlay."""
        cmd = {"action": "draw_polygon", "id": id,
               "vertices": vertices, "field": field}
        if color is not None:
            cmd["color"] = color
        cmd.update(kwargs)
        return self._send_command(cmd)

    def draw_text(self, id: str, x: float, y: float, text: str,
                  color=None, font_size: int = 24,
                  field: str = "base") -> Optional[Dict]:
        """Draw a persistent text label overlay."""
        cmd = {"action": "draw_text", "id": id, "x": x, "y": y,
               "text": text, "font_size": font_size, "field": field}
        if color is not None:
            cmd["color"] = color
        return self._send_command(cmd)

    def remove_drawing(self, id: str) -> Optional[Dict]:
        """Remove a persistent drawing by ID."""
        return self._send_command({"action": "remove_drawing", "id": id})

    def list_drawings(self) -> Optional[Dict]:
        """List all persistent drawing IDs."""
        return self._send_command({"action": "list_drawings"})

    def clear_drawings(self) -> Optional[Dict]:
        """Remove all persistent drawings."""
        return self._send_command({"action": "clear_drawings"})

    # --- Context Manager ---

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
