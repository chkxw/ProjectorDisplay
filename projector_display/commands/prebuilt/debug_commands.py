"""
Debug commands for projector display server.

Commands for toggling debug visualization layers.
"""

from projector_display.commands.base import register_command


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
