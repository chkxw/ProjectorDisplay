"""
MoCap commands for projector display server.

Commands for configuring and controlling MoCap integration.
MoCap is optional - commands return detailed errors when unavailable.
"""

import logging
from typing import Optional

from projector_display.commands.base import register_command
from projector_display.mocap import DEFAULT_NATNET_PORT

logger = logging.getLogger(__name__)


def _get_mocap_tracker(scene):
    """
    Get MocapTracker from scene's server reference.

    Returns:
        (tracker, error_response) - tracker if available, else (None, error_dict)
    """
    tracker = getattr(scene, '_mocap_tracker', None)
    if tracker is None:
        return None, {
            "status": "error",
            "message": "MoCap tracker not initialized. Server may not support MoCap.",
            "code": "MOCAP_NOT_INITIALIZED",
        }
    return tracker, None


def _require_mocap_enabled(tracker) -> Optional[dict]:
    """
    Check if MoCap is enabled and connected.

    Returns:
        Error dict if not enabled, None if OK
    """
    if not tracker.is_available():
        return {
            "status": "error",
            "message": "MocapUtility not installed. Install with: pip install MocapUtility",
            "code": "MOCAP_NOT_INSTALLED",
        }

    if not tracker.is_configured():
        return {
            "status": "error",
            "message": "MoCap not configured. Call set_mocap(ip, port) first.",
            "code": "MOCAP_NOT_CONFIGURED",
        }

    if not tracker.is_enabled():
        return {
            "status": "error",
            "message": "MoCap not enabled. Call enable_mocap() first.",
            "code": "MOCAP_NOT_ENABLED",
        }

    return None


# =============================================================================
# Global MoCap Configuration & Control
# =============================================================================

@register_command
def set_mocap(scene, ip: str, port: int = DEFAULT_NATNET_PORT, enabled: bool = True) -> dict:
    """
    Configure MoCap server connection settings.

    Args:
        scene: Scene instance
        ip: MoCap server IP address
        port: NatNet port (default DEFAULT_NATNET_PORT)
        enabled: Whether to enable MoCap immediately (default True)

    Returns:
        Response with configuration result
    """
    tracker, error = _get_mocap_tracker(scene)
    if error:
        return error

    # If enabling, check if MocapUtility is available
    if enabled and not tracker.is_available():
        return {
            "status": "error",
            "message": "Cannot enable MoCap: MocapUtility not installed. "
                       "Install with: pip install MocapUtility. "
                       "You can still configure with enabled=False.",
            "code": "MOCAP_NOT_INSTALLED",
        }

    result = tracker.set_config(ip=ip, port=port, enabled=enabled)
    logger.info(f"MoCap configured: ip={ip}, port={port}, enabled={enabled}")
    return result


@register_command
def enable_mocap(scene) -> dict:
    """
    Enable MoCap integration (uses previously configured settings).

    Returns:
        Response with enable result
    """
    tracker, error = _get_mocap_tracker(scene)
    if error:
        return error

    result = tracker.enable()
    if result["status"] == "success":
        logger.info("MoCap enabled")
    return result


@register_command
def disable_mocap(scene) -> dict:
    """
    Disable MoCap integration (keeps configuration for later re-enable).

    Returns:
        Response with disable result
    """
    tracker, error = _get_mocap_tracker(scene)
    if error:
        return error

    result = tracker.disable()
    logger.info("MoCap disabled")
    return result


@register_command
def get_mocap_status(scene) -> dict:
    """
    Get comprehensive MoCap status.

    Returns:
        Response with MoCap status information
    """
    tracker, error = _get_mocap_tracker(scene)
    if error:
        return error

    return tracker.get_status()


@register_command
def get_mocap_bodies(scene) -> dict:
    """
    Get list of rigid bodies available in the MoCap system.

    Requires MoCap to be enabled and connected.

    Returns:
        Response with list of available body names
    """
    tracker, error = _get_mocap_tracker(scene)
    if error:
        return error

    check_error = _require_mocap_enabled(tracker)
    if check_error:
        return check_error

    return tracker.get_available_bodies()


# =============================================================================
# Per-RigidBody Tracking Control
# =============================================================================

@register_command
def set_auto_track(scene, name: str, mocap_name: Optional[str] = None,
                   enabled: bool = True) -> dict:
    """
    Configure auto-tracking for a rigidbody.

    Args:
        scene: Scene instance
        name: Rigidbody name
        mocap_name: Name in MoCap system (optional, updates if provided)
        enabled: Whether to enable auto-tracking (default True)

    Returns:
        Response with result

    Note:
        - Setting mocap_name with enabled=False is always allowed (config only)
        - Setting enabled=True requires MoCap to be enabled
    """
    # Check rigidbody exists
    rb = scene.get_rigidbody(name)
    if rb is None:
        return {
            "status": "error",
            "message": f"Rigidbody '{name}' not found",
        }

    # If enabling tracking, validate MoCap is available
    if enabled:
        tracker, error = _get_mocap_tracker(scene)
        if error:
            return error

        check_error = _require_mocap_enabled(tracker)
        if check_error:
            check_error["hint"] = "You can set mocap_name with enabled=False to configure without enabling tracking."
            return check_error

        # Check rigidbody will have mocap_name (either provided or existing)
        effective_mocap_name = mocap_name if mocap_name is not None else rb.mocap_name
        if not effective_mocap_name:
            return {
                "status": "error",
                "message": f"Cannot enable tracking: Rigidbody '{name}' has no mocap_name set.",
                "hint": "Provide mocap_name parameter or set it first.",
            }

    # Apply changes atomically through Scene (thread-safe)
    scene.set_rigidbody_tracking(name, mocap_name=mocap_name, auto_track=enabled)

    # Get updated state for response
    rb = scene.get_rigidbody(name)
    action = "enabled" if enabled else "disabled"
    msg = f"Auto-tracking {action} for '{name}'"
    if mocap_name:
        msg += f" (mocap_name='{mocap_name}')"

    logger.info(msg)

    return {
        "status": "success",
        "message": msg,
        "name": name,
        "mocap_name": rb.mocap_name,
        "auto_track": rb.auto_track,
    }


@register_command
def enable_tracking(scene, name: str) -> dict:
    """
    Enable auto-tracking for a rigidbody (shorthand for set_auto_track).

    Rigidbody must already have mocap_name set.

    Args:
        scene: Scene instance
        name: Rigidbody name

    Returns:
        Response with result
    """
    return set_auto_track(scene, name=name, enabled=True)


@register_command
def disable_tracking(scene, name: str) -> dict:
    """
    Disable auto-tracking for a rigidbody (shorthand for set_auto_track).

    Args:
        scene: Scene instance
        name: Rigidbody name

    Returns:
        Response with result
    """
    return set_auto_track(scene, name=name, enabled=False)
