"""Rendering components for projector display."""

from .renderer import Renderer, PygameRenderer

try:
    from .renderer import GLESRenderer
except (ImportError, AttributeError):
    pass
from .trajectory import draw_trajectory
from .debug_layers import GridLayer, FieldLayer
from .background import BackgroundRenderer

__all__ = [
    "Renderer",
    "PygameRenderer",
    "GLESRenderer",
    "draw_trajectory",
    "GridLayer",
    "FieldLayer",
    "BackgroundRenderer",
]
