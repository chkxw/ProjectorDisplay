"""
RigidBody commands for projector display server.

Commands for creating, updating, and managing rigid bodies in the scene.
All position commands must specify `field` parameter for coordinate interpretation.
"""

from typing import Optional, Dict, Any
from projector_display.commands.base import register_command
from projector_display.commands.prebuilt.mocap_commands import (
    _get_mocap_tracker, _require_mocap_enabled
)


@register_command
def create_rigidbody(scene, name: str, style: dict = None,
                     trajectory: dict = None, mocap_name: str = None,
                     auto_track: bool = False) -> dict:
    """
    Create a new rigid body for display.

    Args:
        scene: Scene instance
        name: Unique identifier for the rigid body
        style: Optional style configuration dict
        trajectory: Optional trajectory configuration dict
        mocap_name: Optional name in MoCap system
        auto_track: Enable auto-tracking from MoCap (default False)

    Returns:
        Response with status and created name

    Note:
        If auto_track=True, MoCap must be enabled and mocap_name must be provided.
    """
    # If auto_track requested, validate MoCap is available
    if auto_track:
        tracker, error = _get_mocap_tracker(scene)
        if error:
            return error

        check_error = _require_mocap_enabled(tracker)
        if check_error:
            check_error["hint"] = "Create with auto_track=False, or enable MoCap first."
            return check_error

        if not mocap_name:
            return {
                "status": "error",
                "message": "Cannot enable auto_track: mocap_name is required.",
            }

    rb = scene.create_rigidbody(name, style=style, trajectory=trajectory,
                                 mocap_name=mocap_name, auto_track=auto_track)

    result = {"status": "success", "name": rb.name}
    if mocap_name:
        result["mocap_name"] = mocap_name
    if auto_track:
        result["auto_track"] = True

    return result


@register_command
def remove_rigidbody(scene, name: str) -> dict:
    """
    Remove a rigid body from the scene.

    Args:
        scene: Scene instance
        name: Rigid body name to remove

    Returns:
        Response with status
    """
    if scene.remove_rigidbody(name):
        return {"status": "success", "name": name}
    else:
        return {"status": "error", "message": f"RigidBody '{name}' not found"}


@register_command
def update_position(scene, name: str, x: float, y: float,
                    orientation: float = None, field: str = "base") -> dict:
    """
    Update rigid body position.

    Creates rigid body if it doesn't exist (with default style).

    Args:
        scene: Scene instance
        name: Rigid body name
        x: X position in field coordinates
        y: Y position in field coordinates
        orientation: Orientation in radians (optional)
        field: Coordinate field for x, y interpretation (default: "base" = world coords)

    Returns:
        Response with status
    """
    # Auto-create rigid body if it doesn't exist
    if scene.get_rigidbody(name) is None:
        scene.create_rigidbody(name)

    # Convert from field coordinates to world coordinates if needed
    if field != "base" and field in scene.field_calibrator.fields:
        # F6: Save original field position BEFORE converting to world coords
        original_field_pos = (x, y)

        world_pos = scene.field_calibrator.convert([x, y], field, "base")
        x, y = float(world_pos[0]), float(world_pos[1])

        # Also convert orientation if provided
        if orientation is not None:
            # F6: Use ORIGINAL field position for orientation transform
            orientation = scene.field_calibrator.transform_orientation(
                field, original_field_pos, orientation
            )

    if scene.update_position(name, x, y, orientation):
        return {"status": "success", "name": name}
    else:
        return {"status": "error", "message": f"RigidBody '{name}' not found"}


@register_command
def update_style(scene, name: str, **style_params) -> dict:
    """
    Update rigid body visualization style.

    Args:
        scene: Scene instance
        name: Rigid body name
        **style_params: Style parameters to update:
            - shape: "circle", "box", "triangle", "polygon"
            - size: Size in meters
            - color: [R, G, B] (0-255)
            - alpha: Transparency (0-255)
            - label: bool - show label
            - label_offset: [x, y] offset in meters
            - orientation_length: Arrow length in meters
            - orientation_color: [R, G, B]
            - orientation_thickness: Pixels
            - polygon_vertices: List of [x, y] for custom polygon

    Returns:
        Response with status
    """
    if scene.update_style(name, **style_params):
        return {"status": "success", "name": name}
    else:
        return {"status": "error", "message": f"RigidBody '{name}' not found"}


@register_command
def update_trajectory(scene, name: str, **traj_params) -> dict:
    """
    Update rigid body trajectory style.

    Args:
        scene: Scene instance
        name: Rigid body name
        **traj_params: Trajectory parameters to update:
            - enabled: bool
            - mode: "time" or "distance"
            - length: Seconds or meters depending on mode
            - style: "solid", "dotted", "dashed"
            - thickness: Pixels
            - color: [R, G, B] or "gradient"
            - gradient_start: [R, G, B]
            - gradient_end: [R, G, B]
            - dot_spacing: Meters (for dotted)
            - dash_length: Meters (for dashed)

    Returns:
        Response with status
    """
    if scene.update_trajectory(name, **traj_params):
        return {"status": "success", "name": name}
    else:
        return {"status": "error", "message": f"RigidBody '{name}' not found"}


@register_command
def get_rigidbody(scene, name: str) -> dict:
    """
    Get rigid body state for inspection.

    Args:
        scene: Scene instance
        name: Rigid body name

    Returns:
        Response with rigid body data
    """
    rb = scene.get_rigidbody(name)
    if rb is None:
        return {"status": "error", "message": f"RigidBody '{name}' not found"}

    return {
        "status": "success",
        "rigidbody": rb.to_dict(include_runtime=True)
    }


@register_command
def list_rigidbodies(scene) -> dict:
    """
    List all rigid body names in the scene.

    Returns:
        Response with list of names
    """
    return {
        "status": "success",
        "rigidbodies": scene.list_rigidbodies()
    }
