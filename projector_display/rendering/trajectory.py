"""
Trajectory rendering for rigid bodies.

Supports solid, dotted, and dashed line styles with gradient color support.
Based on draw_trajectory() from box_push_deploy/shared/display_toolbox.py.

ADR-8: All colors use RGBA format. Gradients support alpha fade (e.g., opaque to transparent).
"""

import math
from typing import List, Tuple, Union, Callable
from projector_display.rendering.renderer import PygameRenderer
from projector_display.core.rigidbody import TrajectoryStyle

# Type alias for RGBA color
ColorRGBA = Tuple[int, int, int, int]


def _ensure_rgba(color: Union[Tuple[int, ...], List[int]]) -> ColorRGBA:
    """Ensure color is RGBA format. Convert RGB to RGBA with alpha=255."""
    if len(color) == 3:
        return (color[0], color[1], color[2], 255)
    return (color[0], color[1], color[2], color[3])


def draw_trajectory(renderer: PygameRenderer,
                    screen_points: List[Tuple[int, int]],
                    style: TrajectoryStyle,
                    distance_to_pixels: Callable[[float], int]) -> None:
    """
    Draw trajectory on the renderer.

    Args:
        renderer: Renderer instance
        screen_points: List of points in screen coordinates
        style: Trajectory style configuration
        distance_to_pixels: Callable that converts a world distance to pixels
            (ADR-12: position-aware, bound to the rigid body's world position)
    """
    if not style.enabled or len(screen_points) < 2:
        return

    if style.style == "solid":
        _draw_solid_trajectory(renderer, screen_points, style)
    elif style.style == "dotted":
        _draw_dotted_trajectory(renderer, screen_points, style, distance_to_pixels)
    elif style.style == "dashed":
        _draw_dashed_trajectory(renderer, screen_points, style, distance_to_pixels)


def _draw_solid_trajectory(renderer: PygameRenderer,
                           screen_points: List[Tuple[int, int]],
                           style: TrajectoryStyle) -> None:
    """Draw solid line trajectory with RGBA gradient support."""
    if style.color == "gradient":
        # Draw gradient line segment by segment (ADR-8: RGBA support)
        for i in range(len(screen_points) - 1):
            t = i / max(1, len(screen_points) - 1)
            color = _interpolate_color(
                style.gradient_end,
                style.gradient_start,
                t
            )
            # Use alpha-aware drawing if alpha < 255
            if len(color) == 4 and color[3] < 255:
                renderer.draw_line_alpha(screen_points[i], screen_points[i + 1],
                                        color[:3], color[3], style.thickness)
            else:
                renderer.draw_line(screen_points[i], screen_points[i + 1],
                                   color[:3], style.thickness)
    else:
        # Single color line
        color = _ensure_rgba(style.color) if isinstance(style.color, tuple) else (100, 100, 255, 255)
        if color[3] < 255:
            # Draw segments with alpha
            for i in range(len(screen_points) - 1):
                renderer.draw_line_alpha(screen_points[i], screen_points[i + 1],
                                        color[:3], color[3], style.thickness)
        else:
            renderer.draw_lines(screen_points, color[:3], style.thickness)


def _draw_dotted_trajectory(renderer: PygameRenderer,
                            screen_points: List[Tuple[int, int]],
                            style: TrajectoryStyle,
                            distance_to_pixels: Callable[[float], int]) -> None:
    """Draw dotted trajectory with RGBA support."""
    dot_spacing_pixels = distance_to_pixels(style.dot_spacing)
    accumulated_dist = 0

    for i in range(len(screen_points) - 1):
        p1 = screen_points[i]
        p2 = screen_points[i + 1]
        segment_dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

        if segment_dist > 0:
            current_dist = accumulated_dist

            while current_dist < segment_dist:
                t = current_dist / segment_dist
                dot_x = int(p1[0] + t * (p2[0] - p1[0]))
                dot_y = int(p1[1] + t * (p2[1] - p1[1]))

                if style.color == "gradient":
                    color_t = (i + t) / max(1, len(screen_points) - 1)
                    color = _interpolate_color(
                        style.gradient_end,
                        style.gradient_start,
                        color_t
                    )
                else:
                    color = _ensure_rgba(style.color) if isinstance(style.color, tuple) else (100, 100, 255, 255)

                # Use alpha-aware drawing if needed
                if len(color) == 4 and color[3] < 255:
                    renderer.draw_circle_alpha((dot_x, dot_y), max(2, style.thickness), color[:3], color[3])
                else:
                    renderer.draw_circle((dot_x, dot_y), max(2, style.thickness), color[:3])
                current_dist += dot_spacing_pixels

            accumulated_dist = current_dist - segment_dist


def _draw_dashed_trajectory(renderer: PygameRenderer,
                            screen_points: List[Tuple[int, int]],
                            style: TrajectoryStyle,
                            distance_to_pixels: Callable[[float], int]) -> None:
    """Draw dashed trajectory with RGBA support."""
    dash_length_pixels = distance_to_pixels(style.dash_length)
    gap_length_pixels = dash_length_pixels // 2  # Gap is half the dash length

    accumulated_dist = 0
    in_dash = True
    dash_start = screen_points[0]

    def _draw_dash_line(start, end, color):
        """Helper to draw a dash with proper alpha handling."""
        if len(color) == 4 and color[3] < 255:
            renderer.draw_line_alpha(start, end, color[:3], color[3], style.thickness)
        else:
            renderer.draw_line(start, end, color[:3], style.thickness)

    for i in range(len(screen_points) - 1):
        p1 = screen_points[i]
        p2 = screen_points[i + 1]
        segment_dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

        if segment_dist == 0:
            continue

        current_dist = 0
        remaining = segment_dist

        while remaining > 0:
            if in_dash:
                # Currently drawing a dash
                dash_remaining = dash_length_pixels - accumulated_dist

                if remaining >= dash_remaining:
                    # Finish this dash
                    t = (current_dist + dash_remaining) / segment_dist
                    dash_end = (
                        int(p1[0] + t * (p2[0] - p1[0])),
                        int(p1[1] + t * (p2[1] - p1[1]))
                    )

                    if style.color == "gradient":
                        color_t = (i + t) / max(1, len(screen_points) - 1)
                        color = _interpolate_color(
                            style.gradient_end,
                            style.gradient_start,
                            color_t
                        )
                    else:
                        color = _ensure_rgba(style.color) if isinstance(style.color, tuple) else (100, 100, 255, 255)

                    _draw_dash_line(dash_start, dash_end, color)

                    current_dist += dash_remaining
                    remaining -= dash_remaining
                    accumulated_dist = 0
                    in_dash = False
                else:
                    # Continue dash into next segment
                    accumulated_dist += remaining
                    remaining = 0
            else:
                # Currently in a gap
                gap_remaining = gap_length_pixels - accumulated_dist

                if remaining >= gap_remaining:
                    # Finish this gap
                    t = (current_dist + gap_remaining) / segment_dist
                    dash_start = (
                        int(p1[0] + t * (p2[0] - p1[0])),
                        int(p1[1] + t * (p2[1] - p1[1]))
                    )

                    current_dist += gap_remaining
                    remaining -= gap_remaining
                    accumulated_dist = 0
                    in_dash = True
                else:
                    # Continue gap into next segment
                    accumulated_dist += remaining
                    remaining = 0

    # Draw final partial dash if we're in a dash
    if in_dash and accumulated_dist > 0:
        dash_end = screen_points[-1]
        if style.color == "gradient":
            color = _ensure_rgba(style.gradient_start)
        else:
            color = _ensure_rgba(style.color) if isinstance(style.color, tuple) else (100, 100, 255, 255)
        _draw_dash_line(dash_start, dash_end, color)


def _interpolate_color(color1: ColorRGBA,
                       color2: ColorRGBA,
                       t: float) -> Tuple[int, int, int]:
    """
    Interpolate between two RGBA colors.

    Args:
        color1: Start color RGBA (at t=0)
        color2: End color RGBA (at t=1)
        t: Interpolation factor (0-1)

    Returns:
        Interpolated RGB color (alpha handled separately by renderer)

    Note: Alpha is interpolated but the return is RGB for pygame compatibility.
          For alpha-blended drawing, use draw_line_alpha in the renderer.
    """
    color1 = _ensure_rgba(color1)
    color2 = _ensure_rgba(color2)
    t = max(0, min(1, t))

    # Interpolate all 4 channels
    r = int(color1[0] + (color2[0] - color1[0]) * t)
    g = int(color1[1] + (color2[1] - color1[1]) * t)
    b = int(color1[2] + (color2[2] - color1[2]) * t)
    a = int(color1[3] + (color2[3] - color1[3]) * t)

    return (r, g, b, a)


def _interpolate_color_rgb(color1: ColorRGBA,
                           color2: ColorRGBA,
                           t: float) -> Tuple[int, int, int]:
    """
    Interpolate between two colors, returning RGB only.

    For backwards compatibility with non-alpha-aware renderer methods.
    """
    rgba = _interpolate_color(color1, color2, t)
    return rgba[:3]
