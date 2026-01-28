"""Rendering components for projector display."""

from projector_display.rendering.renderer import Renderer, PygameRenderer
from projector_display.rendering.primitives import draw_circle, draw_box, draw_triangle, draw_polygon
from projector_display.rendering.trajectory import draw_trajectory
from projector_display.rendering.debug_layers import GridLayer, FieldLayer
from projector_display.rendering.background import BackgroundRenderer

__all__ = [
    "Renderer",
    "PygameRenderer",
    "draw_circle",
    "draw_box",
    "draw_triangle",
    "draw_polygon",
    "draw_trajectory",
    "GridLayer",
    "FieldLayer",
    "BackgroundRenderer",
]
