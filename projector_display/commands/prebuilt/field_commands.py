"""
Field commands for projector display server.

Commands for managing coordinate fields in the scene.
Vertex order convention: [BL, BR, TR, TL] (counter-clockwise from bottom-left)

ADR-10: Includes background configuration commands for field backgrounds.
"""

import logging
from typing import List, Optional
from projector_display.commands.base import register_command
from projector_display.storage import get_storage_manager
from projector_display.utils.color import parse_color

logger = logging.getLogger(__name__)

# Reusable error messages
ERR_FIELD_NOT_FOUND = "Field '{}' not found"
ERR_SCREEN_FIELD_BACKGROUND = (
    "Cannot set background on the 'screen' field. "
    "Use display.background_color in server config instead."
)
ERR_INVALID_ALPHA = "Alpha must be 0-255, got {}"


@register_command
def create_field(scene, name: str, world_points: List[List[float]],
                 local_points: List[List[float]],
                 color=None) -> dict:
    """
    Create a new coordinate field.

    Args:
        scene: Scene instance
        name: Unique identifier for the field
        world_points: 4x2 list of points in world coordinates (meters)
                     Order: [BL, BR, TR, TL] (counter-clockwise from bottom-left)
        local_points: 4x2 list of points in local coordinates
                     Order: [BL, BR, TR, TL] (counter-clockwise from bottom-left)
        color: Optional background color (hex, RGB, or RGBA)

    Returns:
        Response with status

    Raises:
        ValueError: If points are not in counter-clockwise order
    """
    scene.create_field(name, world_points, local_points)

    if color is not None:
        try:
            rgba = parse_color(color)
        except ValueError as e:
            return {"status": "error", "message": f"Invalid color: {e}"}

        field_obj = scene.get_field(name)
        field_obj.background_color = rgba[:3]
        field_obj.background_alpha = rgba[3]

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
        return {"status": "error", "message": ERR_FIELD_NOT_FOUND.format(name)}


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
        return {"status": "error", "message": ERR_FIELD_NOT_FOUND.format(name)}

    result = {
        "status": "success",
        "field": {
            "name": field.name,
            "world_points": field.world_points.tolist(),
            "local_points": field.local_points.tolist(),
        }
    }

    # Include background info if present
    if hasattr(field, 'background_image') and field.background_image:
        result["field"]["background"] = {
            "image": field.background_image,
            "alpha": getattr(field, 'background_alpha', 255)
        }

    return result


@register_command
def set_field_background(scene, field: str, image: str, alpha: int = 255) -> dict:
    """
    Assign an uploaded image as the background for a field.

    The image must already be uploaded via upload_image command.
    This command only configures the field-to-image assignment.

    Args:
        scene: Scene instance
        field: Field name to set background for
        image: Image filename (must already be uploaded)
        alpha: Opacity (0-255, default 255 = fully opaque)

    Returns:
        Response with status
    """
    # Screen field background is not supported -- the display background color
    # is a global server setting (display.background_color in config YAML).
    if field == "screen":
        return {"status": "error", "message": ERR_SCREEN_FIELD_BACKGROUND}

    # Validate field exists
    field_obj = scene.get_field(field)
    if field_obj is None:
        return {"status": "error", "message": ERR_FIELD_NOT_FOUND.format(field)}

    # Validate image exists in session
    storage = get_storage_manager()
    images_dir = storage.get_session_images_dir()
    image_path = images_dir / image

    if not image_path.exists():
        return {
            "status": "error",
            "message": f"Image '{image}' not found. Upload it first using upload_image."
        }

    # Validate alpha
    if not 0 <= alpha <= 255:
        return {"status": "error", "message": ERR_INVALID_ALPHA.format(alpha)}

    # Set background properties on field
    field_obj.background_image = image
    field_obj.background_alpha = alpha

    logger.info(f"Set background for field '{field}': {image} (alpha={alpha})")

    return {
        "status": "success",
        "message": f"Set background '{image}' on field '{field}'",
        "field": field,
        "image": image,
        "alpha": alpha
    }


@register_command
def remove_field_background(scene, field: str) -> dict:
    """
    Clear the background (image or color) from a field.

    Args:
        scene: Scene instance
        field: Field name to remove background from

    Returns:
        Response with status
    """
    if field == "screen":
        return {"status": "error", "message": ERR_SCREEN_FIELD_BACKGROUND}

    # Validate field exists
    field_obj = scene.get_field(field)
    if field_obj is None:
        return {"status": "error", "message": ERR_FIELD_NOT_FOUND.format(field)}

    # Check if field has a background
    had_background = (
        (hasattr(field_obj, 'background_image') and field_obj.background_image) or
        (hasattr(field_obj, 'background_color') and field_obj.background_color)
    )

    # Clear background properties
    field_obj.background_image = None
    field_obj.background_color = None
    field_obj.background_alpha = 255

    if had_background:
        logger.info(f"Removed background from field '{field}'")
        return {
            "status": "success",
            "message": f"Removed background from field '{field}'"
        }
    else:
        return {
            "status": "success",
            "message": f"Field '{field}' had no background"
        }


@register_command
def set_calibration(scene, calibration: dict) -> dict:
    """
    Apply new calibration at runtime.

    Accepts the full calibration structure (resolution, screen_field),
    validates it, replaces the screen field, clears all user-defined fields,
    and writes the updated calibration to disk.

    Args:
        scene: Scene instance
        calibration: Full calibration dict with resolution and screen_field

    Returns:
        Response with status and world_bounds on success
    """
    server = getattr(scene, '_server', None)
    if server is None:
        return {"status": "error", "message": "Server reference not available"}
    try:
        info = server.apply_calibration(calibration)
        return {"status": "success", "message": "Calibration applied and saved", **info}
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@register_command
def set_field_background_color(scene, field: str, color, alpha: int = 255) -> dict:
    """
    Set a solid color background for a field.

    Args:
        scene: Scene instance
        field: Field name to set background for
        color: Color (hex string, RGB list, or RGBA list)
        alpha: Opacity (0-255, default 255 = fully opaque)

    Returns:
        Response with status
    """
    if field == "screen":
        return {"status": "error", "message": ERR_SCREEN_FIELD_BACKGROUND}

    # Validate field exists
    field_obj = scene.get_field(field)
    if field_obj is None:
        return {"status": "error", "message": ERR_FIELD_NOT_FOUND.format(field)}

    # Parse color
    try:
        rgba = parse_color(color)
        rgb = rgba[:3]
    except ValueError as e:
        return {"status": "error", "message": f"Invalid color: {e}"}

    # Validate alpha
    if not 0 <= alpha <= 255:
        return {"status": "error", "message": ERR_INVALID_ALPHA.format(alpha)}

    # Set background properties (color takes precedence over image)
    field_obj.background_color = rgb
    field_obj.background_image = None  # Clear image if any
    field_obj.background_alpha = alpha

    logger.info(f"Set background color for field '{field}': {rgb} (alpha={alpha})")

    return {
        "status": "success",
        "message": f"Set background color on field '{field}'",
        "field": field,
        "color": list(rgb),
        "alpha": alpha
    }
