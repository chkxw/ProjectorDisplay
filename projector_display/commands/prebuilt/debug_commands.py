"""
Debug commands for projector display server.

Commands for toggling debug visualization layers.
"""

from projector_display.commands.base import register_command
from projector_display.utils.color import parse_color


@register_command
def toggle_grid_layer(scene) -> dict:
    """
    Toggle grid layer visibility.

    Shows coordinate grid over display area when enabled.

    Returns:
        Response with new state
    """
    new_state = scene.toggle_grid_layer()
    return {
        "status": "success",
        "grid_layer_enabled": new_state
    }


@register_command
def toggle_field_layer(scene) -> dict:
    """
    Toggle field layer visibility.

    Shows boundaries of all registered fields with labels when enabled.

    Returns:
        Response with new state
    """
    new_state = scene.toggle_field_layer()
    return {
        "status": "success",
        "field_layer_enabled": new_state
    }


@register_command
def set_grid_layer(scene, enabled: bool) -> dict:
    """
    Set grid layer visibility explicitly.

    Args:
        scene: Scene instance
        enabled: Whether grid layer should be visible

    Returns:
        Response with new state
    """
    scene.grid_layer_enabled = enabled
    return {
        "status": "success",
        "grid_layer_enabled": scene.grid_layer_enabled
    }


@register_command
def set_field_layer(scene, enabled: bool) -> dict:
    """
    Set field layer visibility explicitly.

    Args:
        scene: Scene instance
        enabled: Whether field layer should be visible

    Returns:
        Response with new state
    """
    scene.field_layer_enabled = enabled
    return {
        "status": "success",
        "field_layer_enabled": scene.field_layer_enabled
    }


@register_command
def configure_grid_layer(scene,
                         show_minor: bool = None,
                         major_color=None,
                         minor_color=None) -> dict:
    """
    Configure grid layer settings.

    Args:
        scene: Scene instance
        show_minor: Whether to show minor (0.1m) grid lines
        major_color: Color for major grid lines (hex, RGB, RGBA, or float)
        minor_color: Color for minor grid lines (hex, RGB, RGBA, or float)

    Returns:
        Response with current settings
    """
    if show_minor is not None:
        scene.grid_show_minor = bool(show_minor)

    if major_color is not None:
        try:
            scene.grid_major_color = parse_color(major_color)[:3]  # RGB only for grid
        except ValueError:
            pass

    if minor_color is not None:
        try:
            scene.grid_minor_color = parse_color(minor_color)[:3]  # RGB only for grid
        except ValueError:
            pass

    return {
        "status": "success",
        "show_minor": scene.grid_show_minor,
        "major_color": list(scene.grid_major_color),
        "minor_color": list(scene.grid_minor_color)
    }


@register_command
def get_grid_settings(scene) -> dict:
    """
    Get current grid layer settings.

    Returns:
        Current grid configuration
    """
    return {
        "status": "success",
        "enabled": scene.grid_layer_enabled,
        "show_minor": scene.grid_show_minor,
        "major_color": list(scene.grid_major_color),
        "minor_color": list(scene.grid_minor_color)
    }
