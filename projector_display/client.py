#!/usr/bin/env python3
"""
Display client for projector display server.

Provides a simple Python API for communicating with the display server.
Based on display_client.py from box_push_deploy/shared/.
"""

import socket
import json
import logging
from typing import Dict, Any, Optional, List

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
                         trajectory: dict = None, mocap_name: str = None) -> Optional[Dict]:
        """
        Create a new rigid body.

        Args:
            name: Unique identifier
            style: Optional style configuration
            trajectory: Optional trajectory configuration
            mocap_name: Optional MoCap system name

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

    # --- Context Manager ---

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
