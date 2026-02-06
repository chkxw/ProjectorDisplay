"""Rendering components for projector display."""

from projector_display.rendering.renderer import Renderer, PygameRenderer

try:
    from projector_display.rendering.renderer import GLESRenderer
except (ImportError, AttributeError):
    pass
from projector_display.rendering.trajectory import draw_trajectory
from projector_display.rendering.debug_layers import GridLayer, FieldLayer
from projector_display.rendering.background import BackgroundRenderer

__all__ = [
    "Renderer",
    "PygameRenderer",
    "GLESRenderer",
    "draw_trajectory",
    "GridLayer",
    "FieldLayer",
    "BackgroundRenderer",
]
