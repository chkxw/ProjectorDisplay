"""Utility components for projector display."""

from projector_display.utils.logging import setup_logging, get_logger
from projector_display.utils.color import parse_color, normalize_color

__all__ = [
    "setup_logging",
    "get_logger",
    "parse_color",
    "normalize_color",
]
