"""Renderer protocol and implementations."""

from .base import Renderer
from .base import (
    _get_sdl_version, _get_display_position_xrandr,
    _init_display_sdl2, _init_display_sdl1,
)
from .pygame_renderer import PygameRenderer

# GLESRenderer requires OpenGL — import lazily to avoid hard dependency
try:
    from .gles_renderer import GLESRenderer
except ImportError:
    pass

__all__ = [
    "Renderer",
    "PygameRenderer",
    "GLESRenderer",
    "_get_sdl_version",
    "_get_display_position_xrandr",
    "_init_display_sdl2",
    "_init_display_sdl1",
]
