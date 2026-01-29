"""
MoCap tracker for projector display.

Manages connection to OptiTrack MoCap system and updates rigidbody positions.
MocapUtility is lazy-loaded only when tracking is enabled.
"""

import math
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from projector_display.core.scene import Scene

logger = logging.getLogger(__name__)

# Default MoCap polling rate (Hz)
DEFAULT_POLL_RATE = 30

# Default NatNet command port (OptiTrack)
DEFAULT_NATNET_PORT = 1511


@dataclass
class MocapConfig:
    """Configuration for MoCap connection."""
    ip: str = ""
    port: int = DEFAULT_NATNET_PORT
    enabled: bool = False

    def is_configured(self) -> bool:
        """Check if MoCap is configured (has IP address)."""
        return bool(self.ip)

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MocapConfig":
        return cls(
            ip=data.get("ip", ""),
            port=data.get("port", DEFAULT_NATNET_PORT),
            enabled=data.get("enabled", False),
        )


def _quaternion_to_yaw(quat: tuple) -> float:
    """
    Extract yaw (Z-axis rotation) from quaternion.

    Args:
        quat: (x, y, z, w) quaternion from OptiTrack

    Returns:
        Yaw angle in radians
    """
    x, y, z, w = quat
    # Yaw (Z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class MocapTracker:
    """
    Manages MoCap connection and rigidbody position updates.

    Lazy-loads MocapUtility only when tracking is enabled.
    Runs a background thread to poll MoCap and update rigidbody positions.
    """

    def __init__(self, scene: "Scene"):
        """
        Initialize MoCap tracker.

        Args:
            scene: Scene instance to update rigidbody positions
        """
        self._scene = scene
        self._config = MocapConfig()
        self._mocap = None  # MoCapUtility instance (lazy-loaded)
        self._mocap_available = None  # None = not checked, True/False = checked

        self._connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()  # Reentrant lock for nested calls

        self._poll_rate = DEFAULT_POLL_RATE
        self._last_error: Optional[str] = None
        self._in_error_state: bool = False  # For log rate-limiting
        self._missing_bodies: set = set()  # Track bodies not found (log once)

    def _check_mocap_available(self) -> bool:
        """Check if MocapUtility is available (installed)."""
        if self._mocap_available is not None:
            return self._mocap_available

        try:
            from external.MocapUtility import MoCapUtility
            self._mocap_available = True
            logger.debug("MocapUtility is available")
        except ImportError:
            self._mocap_available = False
            logger.warning("MocapUtility not installed - MoCap features unavailable")

        return self._mocap_available

    def is_available(self) -> bool:
        """Check if MoCap integration is available (MocapUtility installed)."""
        return self._check_mocap_available()

    def is_configured(self) -> bool:
        """Check if MoCap is configured (has server address)."""
        return self._config.is_configured()

    def is_enabled(self) -> bool:
        """Check if MoCap is enabled in config."""
        return self._config.enabled

    def is_connected(self) -> bool:
        """Check if connected to MoCap server."""
        return self._connected

    def is_running(self) -> bool:
        """Check if polling thread is running."""
        return self._running

    def get_config(self) -> MocapConfig:
        """Get current MoCap configuration."""
        return self._config

    def get_last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error

    def set_config(self, ip: str, port: int = DEFAULT_NATNET_PORT, enabled: bool = True) -> dict:
        """
        Configure MoCap connection settings.

        Args:
            ip: MoCap server IP address
            port: NatNet port (default DEFAULT_NATNET_PORT, valid range 1-65535)
            enabled: Whether to enable MoCap (default True)

        Returns:
            Result dict with status
        """
        # Validate port range
        if not (1 <= port <= 65535):
            return {
                "status": "error",
                "message": f"Invalid port {port}: must be between 1 and 65535",
                "code": "INVALID_PORT",
            }

        with self._lock:
            self._config.ip = ip
            self._config.port = port

            # If enabling, try to connect
            if enabled:
                return self.enable()
            else:
                self._config.enabled = False
                return {
                    "status": "success",
                    "message": f"MoCap configured (ip={ip}, port={port}, enabled=False)",
                    "connected": False,
                }

    def enable(self) -> dict:
        """
        Enable MoCap integration and connect to server.

        Returns:
            Result dict with status
        """
        # Check if MocapUtility is available
        if not self._check_mocap_available():
            self._last_error = "MocapUtility not installed"
            return {
                "status": "error",
                "message": "MocapUtility not installed. Install it with: pip install MocapUtility",
                "code": "MOCAP_NOT_INSTALLED",
            }

        # Check if configured
        if not self._config.is_configured():
            self._last_error = "MoCap not configured"
            return {
                "status": "error",
                "message": "MoCap not configured. Call set_mocap(ip, port) first.",
                "code": "MOCAP_NOT_CONFIGURED",
            }

        with self._lock:
            # Connect if not already connected
            if not self._connected:
                result = self._connect()
                if result["status"] != "success":
                    return result  # Don't set enabled on failure

            # Only set enabled after successful connect
            self._config.enabled = True

            # Start polling thread if not running
            if not self._running:
                self._start_polling()

            return {
                "status": "success",
                "message": f"MoCap enabled and connected to {self._config.ip}:{self._config.port}",
                "connected": True,
            }

    def disable(self) -> dict:
        """
        Disable MoCap integration (keeps config, stops polling).

        Returns:
            Result dict with status
        """
        with self._lock:
            self._config.enabled = False
            self._stop_polling()

            return {
                "status": "success",
                "message": "MoCap disabled (config preserved)",
                "connected": self._connected,
            }

    def _connect(self) -> dict:
        """
        Connect to MoCap server (internal, must hold lock).

        Returns:
            Result dict with status
        """
        try:
            from external.MocapUtility import MoCapUtility

            logger.info(f"Connecting to MoCap server at {self._config.ip}:{self._config.port}")

            self._mocap = MoCapUtility(server_address=self._config.ip)
            self._mocap.connect()

            self._connected = True
            self._last_error = None

            logger.info("MoCap connected successfully")
            return {"status": "success", "message": "Connected to MoCap server"}

        except Exception as e:
            self._last_error = str(e)
            self._connected = False
            self._mocap = None  # Clean up failed instance
            logger.error(f"Failed to connect to MoCap: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect to MoCap server: {e}",
                "code": "MOCAP_CONNECTION_FAILED",
            }

    def _disconnect(self):
        """Disconnect from MoCap server (internal)."""
        if self._mocap:
            try:
                self._mocap.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting from MoCap: {e}")
            self._mocap = None
        self._connected = False

    def _start_polling(self):
        """Start background polling thread (internal, must hold lock)."""
        if self._running:
            return

        # Prevent duplicate threads if previous one didn't stop cleanly
        if self._thread and self._thread.is_alive():
            logger.warning("Previous polling thread still running, skipping start")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"MoCap polling started at {self._poll_rate} Hz")

    def _stop_polling(self):
        """Stop background polling thread (internal, must hold lock)."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("MoCap polling stopped")

    def _poll_loop(self):
        """Background thread: poll MoCap and update rigidbody positions."""
        poll_interval = 1.0 / self._poll_rate

        while self._running:
            try:
                self._update_tracked_bodies()
                # Clear error state on success
                if self._in_error_state:
                    logger.info("MoCap poll loop recovered")
                    self._in_error_state = False
            except Exception as e:
                self._last_error = str(e)
                # First error logs as ERROR, subsequent as DEBUG
                if not self._in_error_state:
                    logger.error(f"Error in MoCap poll loop: {e}")
                    self._in_error_state = True
                else:
                    logger.debug(f"Error in MoCap poll loop (repeated): {e}")

            time.sleep(poll_interval)

    def _update_tracked_bodies(self):
        """Update positions of all auto-tracked rigidbodies."""
        if not self._connected or not self._mocap:
            return

        # Get all rigidbodies with auto_track enabled
        rigidbodies = self._scene.get_rigidbodies_snapshot()

        for rb in rigidbodies.values():
            if not rb.auto_track or not rb.mocap_name:
                continue

            try:
                # Get position from MoCap (x, y, z) -> we use (x, y)
                pos = self._mocap.get_pos(rb.mocap_name)
                if pos is None:
                    # Log once per missing body
                    if rb.mocap_name not in self._missing_bodies:
                        logger.warning(f"MoCap body '{rb.mocap_name}' not found for rigidbody '{rb.name}'")
                        self._missing_bodies.add(rb.mocap_name)
                    continue

                # Body found - clear from missing set if it was there
                if rb.mocap_name in self._missing_bodies:
                    logger.info(f"MoCap body '{rb.mocap_name}' now available")
                    self._missing_bodies.discard(rb.mocap_name)

                # Get orientation from MoCap (quaternion) -> convert to yaw
                quat = self._mocap.get_quat(rb.mocap_name)
                orientation = None
                if quat is not None:
                    orientation = _quaternion_to_yaw(quat)

                # Update rigidbody position (thread-safe via scene lock)
                self._scene.update_position(
                    rb.name,
                    x=pos[0],
                    y=pos[1],
                    orientation=orientation
                )

            except Exception as e:
                logger.debug(f"Failed to update {rb.name} from MoCap: {e}")

    def get_available_bodies(self) -> dict:
        """
        Get list of rigid bodies available in MoCap system.

        Returns:
            Result dict with list of body names
        """
        if not self._connected or not self._mocap:
            return {
                "status": "error",
                "message": "MoCap not connected",
                "code": "MOCAP_NOT_CONNECTED",
            }

        try:
            names = self._mocap.get_robot_names()
            return {
                "status": "success",
                "bodies": names,
                "count": len(names),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get MoCap bodies: {e}",
            }

    def get_status(self) -> dict:
        """
        Get comprehensive MoCap status.

        Returns:
            Status dict with config, connection, and tracking info
        """
        # Count tracked rigidbodies
        tracked_count = 0
        tracked_names = []
        rigidbodies = self._scene.get_rigidbodies_snapshot()
        for rb in rigidbodies.values():
            if rb.auto_track and rb.mocap_name:
                tracked_count += 1
                tracked_names.append(rb.name)

        return {
            "status": "success",
            "available": self.is_available(),
            "configured": self.is_configured(),
            "enabled": self.is_enabled(),
            "connected": self.is_connected(),
            "running": self.is_running(),
            "config": self._config.to_dict(),
            "last_error": self._last_error,
            "tracked_rigidbodies": tracked_names,
            "tracked_count": tracked_count,
            "poll_rate": self._poll_rate,
        }

    def shutdown(self):
        """Clean shutdown of MoCap tracker."""
        with self._lock:
            self._stop_polling()
            self._disconnect()
        logger.info("MoCap tracker shut down")
