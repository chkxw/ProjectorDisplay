"""
Field commands for projector display server.

Commands for managing coordinate fields in the scene.
Vertex order convention: [BL, BR, TR, TL] (counter-clockwise from bottom-left)
"""

from typing import List
from projector_display.commands.base import register_command


@register_command
def create_field(scene, name: str, world_points: List[List[float]],
                 local_points: List[List[float]]) -> dict:
    """
    Create a new coordinate field.

    Args:
        scene: Scene instance
        name: Unique identifier for the field
        world_points: 4x2 list of points in world coordinates (meters)
                     Order: [BL, BR, TR, TL] (counter-clockwise from bottom-left)
        local_points: 4x2 list of points in local coordinates
                     Order: [BL, BR, TR, TL] (counter-clockwise from bottom-left)

    Returns:
        Response with status

    Raises:
        ValueError: If points are not in counter-clockwise order
    """
    scene.create_field(name, world_points, local_points)
    return {"status": "success", "name": name}


@register_command
def remove_field(scene, name: str) -> dict:
    """
    Remove a registered field.

    Args:
        scene: Scene instance
        name: Field name to remove

    Returns:
        Response with status
    """
    if name == "screen":
        return {"status": "error", "message": "Cannot remove the 'screen' field"}

    if scene.remove_field(name):
        return {"status": "success", "name": name}
    else:
        return {"status": "error", "message": f"Field '{name}' not found"}


@register_command
def list_fields(scene) -> dict:
    """
    List all registered field names.

    Returns:
        Response with list of field names
    """
    return {
        "status": "success",
        "fields": scene.list_fields()
    }


@register_command
def get_field(scene, name: str) -> dict:
    """
    Get field information.

    Args:
        scene: Scene instance
        name: Field name

    Returns:
        Response with field data
    """
    field = scene.get_field(name)
    if field is None:
        return {"status": "error", "message": f"Field '{name}' not found"}

    return {
        "status": "success",
        "field": {
            "name": field.name,
            "world_points": field.world_points.tolist(),
            "local_points": field.local_points.tolist(),
        }
    }
