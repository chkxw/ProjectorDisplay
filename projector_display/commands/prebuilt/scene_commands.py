"""
Scene commands for projector display server.

Commands for scene-level operations like clear, dump, and status.
ADR-10: Includes persistent scene save/load operations.
"""

import shutil
import logging
from datetime import datetime
from typing import Dict, Any

import yaml

from projector_display.commands.base import register_command
from projector_display.storage import get_storage_manager

logger = logging.getLogger(__name__)


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
    result = {
        "status": "success",
        "rigidbodies": scene.list_rigidbodies(),
        "rigidbody_count": len(scene.rigidbodies),
        "fields": scene.list_fields(),
        "field_count": len(scene.field_calibrator.fields),
        "grid_layer_enabled": scene.grid_layer_enabled,
        "field_layer_enabled": scene.field_layer_enabled,
    }

    # Add MoCap status if tracker is available
    tracker = getattr(scene, '_mocap_tracker', None)
    if tracker is not None:
        mocap_status = tracker.get_status()
        result["mocap"] = {
            "enabled": mocap_status.get("enabled", False),
            "connected": mocap_status.get("connected", False),
            "server": mocap_status.get("server"),
        }

    return result


# ============================================================================
# Persistent Storage Commands (ADR-10)
# ============================================================================

@register_command
def save_scene(scene, name: str) -> dict:
    """
    Save scene to persistent storage.

    Creates:
        ~/.local/share/projector_display/scenes/{name}/
            ├── scene.yaml
            └── images/
                └── (any background images)

    Args:
        scene: Scene instance
        name: Name for the saved scene

    Returns:
        Response with save result
    """
    storage = get_storage_manager()

    # Get scene data
    scene_data = scene.to_dict()

    # Add metadata
    scene_data['created'] = datetime.now().isoformat()

    # Create scene directory
    scene_dir = storage.get_scene_dir(name)
    scene_images_dir = storage.get_scene_images_dir(name)

    # Collect images to copy from session dir
    images_to_copy = set()
    for field_name, field_data in scene_data.get('fields', {}).items():
        background = field_data.get('background')
        if background and background.get('image'):
            images_to_copy.add(background['image'])

    # Copy images from session temp dir to persistent scene dir
    session_images_dir = storage.get_session_images_dir()
    copied_images = []
    missing_images = []

    for image_name in images_to_copy:
        src = session_images_dir / image_name
        dst = scene_images_dir / image_name
        if src.exists():
            shutil.copy2(src, dst)
            copied_images.append(image_name)
            logger.info(f"Copied image '{image_name}' to scene '{name}'")
        else:
            missing_images.append(image_name)
            logger.warning(f"Image '{image_name}' not found in session, skipping")

    # Write scene.yaml
    scene_yaml_path = storage.get_scene_yaml_path(name)
    with open(scene_yaml_path, 'w') as f:
        yaml.safe_dump(scene_data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved scene '{name}' with {len(scene_data.get('fields', {}))} fields, "
                f"{len(scene_data.get('rigidbodies', {}))} rigidbodies")

    result = {
        "status": "success",
        "message": f"Scene '{name}' saved",
        "path": str(scene_dir),
        "fields": len(scene_data.get('fields', {})),
        "rigidbodies": len(scene_data.get('rigidbodies', {})),
        "images_copied": copied_images,
    }

    if missing_images:
        result["images_missing"] = missing_images
        result["warning"] = f"Some images not found: {missing_images}"

    return result


@register_command
def load_scene_from_file(scene, name: str) -> dict:
    """
    Load scene from persistent storage.

    Loads from:
        ~/.local/share/projector_display/scenes/{name}/scene.yaml

    Also copies scene images to session temp dir for working.

    Args:
        scene: Scene instance
        name: Name of the saved scene to load

    Returns:
        Response with load result
    """
    storage = get_storage_manager()

    # Check if scene exists
    scene_yaml_path = storage.get_scene_yaml_path(name)
    if not scene_yaml_path.exists():
        return {
            "status": "error",
            "message": f"Scene '{name}' not found",
            "available_scenes": storage.list_scenes()
        }

    try:
        # Load scene.yaml
        with open(scene_yaml_path, 'r') as f:
            scene_data = yaml.safe_load(f)

        if not scene_data:
            return {
                "status": "error",
                "message": f"Scene '{name}' is empty or invalid"
            }

        # Copy images from scene dir to session temp dir
        scene_images_dir = storage.get_scene_images_dir(name)
        session_images_dir = storage.get_session_images_dir()
        copied_images = []

        if scene_images_dir.exists():
            for image_file in scene_images_dir.iterdir():
                if image_file.is_file():
                    dst = session_images_dir / image_file.name
                    shutil.copy2(image_file, dst)
                    copied_images.append(image_file.name)

        # Clear current scene (but keep screen field)
        scene.clear_all()

        # Load fields
        for field_name, field_data in scene_data.get('fields', {}).items():
            scene.create_field(
                name=field_name,
                world_points=field_data['world_points'],
                local_points=field_data['local_points'],
            )

            # Load field background if present
            background = field_data.get('background')
            if background:
                field_obj = scene.get_field(field_name)
                if field_obj:
                    field_obj.background_image = background.get('image')
                    field_obj.background_alpha = background.get('alpha', 255)

        # Load rigid bodies
        for rb_name, rb_data in scene_data.get('rigidbodies', {}).items():
            rb = scene.create_rigidbody(
                name=rb_name,
                style=rb_data.get('style'),
                trajectory=rb_data.get('trajectory'),
                mocap_name=rb_data.get('mocap_name'),
            )
            if rb_data.get('position'):
                rb.position = tuple(rb_data['position'])
            if rb_data.get('orientation') is not None:
                rb.orientation = rb_data['orientation']
                rb._last_orientation = rb_data['orientation']

        logger.info(f"Loaded scene '{name}' with {len(scene_data.get('fields', {}))} fields, "
                    f"{len(scene_data.get('rigidbodies', {}))} rigidbodies")

        return {
            "status": "success",
            "message": f"Scene '{name}' loaded",
            "fields": len(scene_data.get('fields', {})),
            "rigidbodies": len(scene_data.get('rigidbodies', {})),
            "images_copied": copied_images,
            "created": scene_data.get('created'),
        }

    except yaml.YAMLError as e:
        return {
            "status": "error",
            "message": f"Invalid scene YAML: {e}"
        }
    except Exception as e:
        logger.error(f"Failed to load scene '{name}': {e}")
        return {
            "status": "error",
            "message": f"Failed to load scene: {e}"
        }


@register_command
def list_saved_scenes(scene) -> dict:
    """
    List all saved scenes in persistent storage.

    Returns:
        Response with list of saved scene names
    """
    storage = get_storage_manager()
    scenes = storage.list_scenes()

    return {
        "status": "success",
        "scenes": scenes,
        "count": len(scenes)
    }


@register_command
def delete_saved_scene(scene, name: str) -> dict:
    """
    Delete a saved scene from persistent storage.

    Args:
        scene: Scene instance (unused)
        name: Name of the scene to delete

    Returns:
        Response with deletion result
    """
    storage = get_storage_manager()

    if not storage.scene_exists(name):
        return {
            "status": "error",
            "message": f"Scene '{name}' not found"
        }

    storage.delete_scene(name)

    return {
        "status": "success",
        "message": f"Scene '{name}' deleted"
    }
