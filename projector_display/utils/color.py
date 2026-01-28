"""
Color parsing and normalization utilities.

Supports multiple color formats:
- HEX: "#RRGGBB" or "#RRGGBBAA"
- RGB tuple/list: [R, G, B] with values 0-255
- RGBA tuple/list: [R, G, B, A] with values 0-255
- RGB float: [R, G, B] with values 0.0-1.0 (detected by float type)
- RGBA float: [R, G, B, A] with values 0.0-1.0

All outputs are RGBA tuples with values 0-255.
"""

import re
from typing import Tuple, Union, List, Optional

# Type aliases
Color = Tuple[int, int, int, int]  # RGBA
ColorInput = Union[str, List, Tuple]

# Regex for hex color codes
HEX_COLOR_PATTERN = re.compile(r'^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')

# Regex for comma-separated values like "50,50,50" or "(50, 50, 50)" or "[50,50,50]" or "0.5, 0.5, 0.5"
CSV_COLOR_PATTERN = re.compile(r'^[\(\[]?\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)(?:\s*,\s*([0-9.]+))?\s*[\)\]]?$')


def normalize_color(color: Tuple[Union[int, float], ...]) -> Color:
    """
    Normalize color tuple to RGBA format with clamping.

    Args:
        color: Tuple of 3 (RGB) or 4 (RGBA) numeric values.
               If all values are floats in 0.0-1.0 range, treated as float color.
               Otherwise treated as 0-255 integer color.

    Returns:
        RGBA tuple with values clamped to 0-255.

    Examples:
        >>> normalize_color((255, 0, 0))
        (255, 0, 0, 255)
        >>> normalize_color((1.0, 0.0, 0.0))
        (255, 0, 0, 255)
        >>> normalize_color((128, 64, 32, 200))
        (128, 64, 32, 200)
    """
    if len(color) < 3:
        raise ValueError(f"Color must have at least 3 components, got {len(color)}")

    # Detect float color (0.0-1.0 range)
    # A color is float if all values are floats AND all values are <= 1.0
    is_float_color = (
        all(isinstance(c, float) for c in color) and
        all(0.0 <= c <= 1.0 for c in color)
    )

    if is_float_color:
        # Convert from 0.0-1.0 to 0-255
        values = [int(round(c * 255)) for c in color]
    else:
        # Already 0-255 range, just convert to int
        values = [int(c) for c in color]

    # Clamp to 0-255
    clamped = [max(0, min(255, v)) for v in values]

    # Return RGBA (add alpha=255 if only RGB)
    if len(clamped) == 3:
        return (clamped[0], clamped[1], clamped[2], 255)
    else:
        return (clamped[0], clamped[1], clamped[2], clamped[3])


def parse_hex_color(hex_str: str) -> Optional[Color]:
    """
    Parse hex color string to RGBA tuple.

    Args:
        hex_str: Hex color like "#RRGGBB" or "#RRGGBBAA" (# optional)

    Returns:
        RGBA tuple or None if invalid format.

    Examples:
        >>> parse_hex_color("#FF0000")
        (255, 0, 0, 255)
        >>> parse_hex_color("00FF00FF")
        (0, 255, 0, 255)
        >>> parse_hex_color("#FF000080")
        (255, 0, 0, 128)
    """
    match = HEX_COLOR_PATTERN.match(hex_str.strip())
    if not match:
        return None

    hex_value = match.group(1)

    if len(hex_value) == 6:
        # RGB
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
        return (r, g, b, 255)
    else:
        # RGBA
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
        a = int(hex_value[6:8], 16)
        return (r, g, b, a)


def parse_csv_color(csv_str: str) -> Optional[Color]:
    """
    Parse comma-separated color string to RGBA tuple.

    Args:
        csv_str: Color string like "50,50,50" or "(50, 50, 50)" or "0.5,0.5,0.5"

    Returns:
        RGBA tuple or None if invalid format.
    """
    match = CSV_COLOR_PATTERN.match(csv_str.strip())
    if not match:
        return None

    try:
        values = [match.group(i) for i in range(1, 5) if match.group(i) is not None]
        # Detect if float format (contains '.')
        if any('.' in v for v in values):
            parsed = tuple(float(v) for v in values)
        else:
            parsed = tuple(int(v) for v in values)
        return normalize_color(parsed)
    except (ValueError, TypeError):
        return None


def parse_color(color: ColorInput) -> Color:
    """
    Parse color from various formats to RGBA tuple.

    Supported formats:
    - HEX string: "#RRGGBB", "#RRGGBBAA", "RRGGBB", "RRGGBBAA"
    - CSV string: "R,G,B", "(R,G,B)", "R,G,B,A", "(R, G, B, A)"
    - RGB list/tuple: [R, G, B] with 0-255 values
    - RGBA list/tuple: [R, G, B, A] with 0-255 values
    - RGB float list/tuple: [R, G, B] with 0.0-1.0 values (all must be floats)
    - RGBA float list/tuple: [R, G, B, A] with 0.0-1.0 values

    Args:
        color: Color in any supported format

    Returns:
        RGBA tuple with values 0-255

    Raises:
        ValueError: If color format is invalid or unrecognized

    Examples:
        >>> parse_color("#FF0000")
        (255, 0, 0, 255)
        >>> parse_color("50,50,50")
        (50, 50, 50, 255)
        >>> parse_color("(255, 128, 0)")
        (255, 128, 0, 255)
        >>> parse_color([255, 128, 0])
        (255, 128, 0, 255)
        >>> parse_color([1.0, 0.5, 0.0])
        (255, 128, 0, 255)
        >>> parse_color((0, 255, 0, 128))
        (0, 255, 0, 128)
    """
    # Handle string
    if isinstance(color, str):
        # Try hex first
        result = parse_hex_color(color)
        if result is not None:
            return result

        # Try CSV format
        result = parse_csv_color(color)
        if result is not None:
            return result

        raise ValueError(f"Invalid color format: {color}")

    # Handle list/tuple
    if isinstance(color, (list, tuple)):
        if len(color) < 3:
            raise ValueError(f"Color must have at least 3 components, got {len(color)}")
        return normalize_color(tuple(color))

    raise ValueError(f"Unsupported color type: {type(color).__name__}")
