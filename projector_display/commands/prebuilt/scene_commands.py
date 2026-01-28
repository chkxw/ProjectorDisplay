"""
Scene commands for projector display server.

Commands for scene-level operations like clear, dump, and status.
"""

import yaml
from typing import Dict, Any
from projector_display.commands.base import register_command


@register_command
def clear_scene(scene) -> dict:
    """
    Clear all rigid bodies from the scene (keeps fields).

    Returns:
        Response with status
    """
    scene.clear()
    return {"status": "success", "message": "Scene cleared (rigid bodies removed, fields kept)"}


@register_command
def clear_all(scene) -> dict:
    """
    Clear everything including fields (except screen field).

    Returns:
        Response with status
    """
    scene.clear_all()
    return {"status": "success", "message": "Scene fully cleared (screen field preserved)"}


@register_command
def dump_scene(scene) -> dict:
    """
    Dump scene state for serialization.

    Returns YAML-serializable dict that can recreate the scene.

    Returns:
        Response with scene data
    """
    return {
        "status": "success",
        "scene": scene.to_dict()
    }


@register_command
def get_scene(scene) -> dict:
    """
    Get full scene state for inspection.

    Returns:
        Response with complete scene state
    """
    scene_data = scene.to_dict()
    return {
        "status": "success",
        "scene": scene_data,
        "grid_layer_enabled": scene.grid_layer_enabled,
        "field_layer_enabled": scene.field_layer_enabled,
    }


@register_command
def load_scene(scene, scene_data: dict) -> dict:
    """
    Load scene from previously dumped data.

    This clears the current scene and loads the new one.

    Args:
        scene: Scene instance
        scene_data: Dictionary from dump_scene

    Returns:
        Response with status
    """
    # Clear current scene first
    scene.clear_all()

    # Load fields
    for name, field_data in scene_data.get('fields', {}).items():
        scene.create_field(
            name=name,
            world_points=field_data['world_points'],
            local_points=field_data['local_points'],
        )

    # Load rigid bodies
    for name, rb_data in scene_data.get('rigidbodies', {}).items():
        rb = scene.create_rigidbody(
            name=name,
            style=rb_data.get('style'),
            trajectory=rb_data.get('trajectory'),
            mocap_name=rb_data.get('mocap_name'),
        )
        if rb_data.get('position'):
            rb.position = tuple(rb_data['position'])
        if rb_data.get('orientation') is not None:
            rb.orientation = rb_data['orientation']
            rb._last_orientation = rb_data['orientation']

    return {
        "status": "success",
        "message": "Scene loaded",
        "fields": len(scene_data.get('fields', {})),
        "rigidbodies": len(scene_data.get('rigidbodies', {})),
    }


@register_command
def status(scene) -> dict:
    """
    Get display server status.

    Returns:
        Response with server status information
    """
    return {
        "status": "success",
        "rigidbodies": scene.list_rigidbodies(),
        "rigidbody_count": len(scene.rigidbodies),
        "fields": scene.list_fields(),
        "field_count": len(scene.field_calibrator.fields),
        "grid_layer_enabled": scene.grid_layer_enabled,
        "field_layer_enabled": scene.field_layer_enabled,
    }
