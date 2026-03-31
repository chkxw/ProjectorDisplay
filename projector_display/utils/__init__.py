"""Utility components for projector display."""

from .logging import setup_logging, get_logger
from .color import parse_color, normalize_color

__all__ = [
    "setup_logging",
    "get_logger",
    "parse_color",
    "normalize_color",
]
