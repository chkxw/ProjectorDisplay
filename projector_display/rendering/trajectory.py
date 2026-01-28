"""
Trajectory rendering for rigid bodies.

Supports solid, dotted, and dashed line styles with gradient color support.
Based on draw_trajectory() from box_push_deploy/shared/display_toolbox.py.
"""

import math
from typing import List, Tuple, Union, Callable
from projector_display.rendering.renderer import PygameRenderer
from projector_display.core.rigidbody import TrajectoryStyle


def draw_trajectory(renderer: PygameRenderer,
                    screen_points: List[Tuple[int, int]],
                    style: TrajectoryStyle,
                    meters_to_pixels: Callable[[float], int]) -> None:
    """
    Draw trajectory on the renderer.

    Args:
        renderer: Renderer instance
        screen_points: List of points in screen coordinates
        style: Trajectory style configuration
        meters_to_pixels: Function to convert meters to pixels
    """
    if not style.enabled or len(screen_points) < 2:
        return

    if style.style == "solid":
        _draw_solid_trajectory(renderer, screen_points, style)
    elif style.style == "dotted":
        _draw_dotted_trajectory(renderer, screen_points, style, meters_to_pixels)
    elif style.style == "dashed":
        _draw_dashed_trajectory(renderer, screen_points, style, meters_to_pixels)


def _draw_solid_trajectory(renderer: PygameRenderer,
                           screen_points: List[Tuple[int, int]],
                           style: TrajectoryStyle) -> None:
    """Draw solid line trajectory."""
    if style.color == "gradient":
        # Draw gradient line segment by segment
        for i in range(len(screen_points) - 1):
            t = i / max(1, len(screen_points) - 1)
            color = _interpolate_color(
                style.gradient_end,
                style.gradient_start,
                t
            )
            renderer.draw_line(screen_points[i], screen_points[i + 1],
                               color, style.thickness)
    else:
        # Single color line
        color = style.color if isinstance(style.color, tuple) else (100, 100, 255)
        renderer.draw_lines(screen_points, color, style.thickness)


def _draw_dotted_trajectory(renderer: PygameRenderer,
                            screen_points: List[Tuple[int, int]],
                            style: TrajectoryStyle,
                            meters_to_pixels: Callable[[float], int]) -> None:
    """Draw dotted trajectory."""
    dot_spacing_pixels = meters_to_pixels(style.dot_spacing)
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
                    color = style.color if isinstance(style.color, tuple) else (100, 100, 255)

                renderer.draw_circle((dot_x, dot_y), max(2, style.thickness), color)
                current_dist += dot_spacing_pixels

            accumulated_dist = current_dist - segment_dist


def _draw_dashed_trajectory(renderer: PygameRenderer,
                            screen_points: List[Tuple[int, int]],
                            style: TrajectoryStyle,
                            meters_to_pixels: Callable[[float], int]) -> None:
    """Draw dashed trajectory."""
    dash_length_pixels = meters_to_pixels(style.dash_length)
    gap_length_pixels = dash_length_pixels // 2  # Gap is half the dash length

    accumulated_dist = 0
    in_dash = True
    dash_start = screen_points[0]

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
                        color = style.color if isinstance(style.color, tuple) else (100, 100, 255)

                    renderer.draw_line(dash_start, dash_end, color, style.thickness)

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
            color = style.gradient_start
        else:
            color = style.color if isinstance(style.color, tuple) else (100, 100, 255)
        renderer.draw_line(dash_start, dash_end, color, style.thickness)


def _interpolate_color(color1: Tuple[int, int, int],
                       color2: Tuple[int, int, int],
                       t: float) -> Tuple[int, int, int]:
    """
    Interpolate between two colors.

    Args:
        color1: Start color (at t=0)
        color2: End color (at t=1)
        t: Interpolation factor (0-1)

    Returns:
        Interpolated RGB color
    """
    t = max(0, min(1, t))
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t),
    )
