"""
Shape drawing primitives for rigid body visualization.

All orientation rendering goes through transform_orientation() to ensure
correct handling of coordinate transformations.

Based on draw_robot() from box_push_deploy/shared/display_toolbox.py.

ADR-8: All colors use RGBA format (4-tuple). RGB (3-tuple) is auto-converted.
"""

import math
from typing import Tuple, List, Optional, Callable, Union
from projector_display.rendering.renderer import PygameRenderer
from projector_display.core.rigidbody import RigidBody, RigidBodyShape

# Type alias for RGBA color
ColorRGBA = Tuple[int, int, int, int]

# Tracking lost indicator settings
TRACKING_LOST_COLOR = (255, 0, 0)  # Red
TRACKING_LOST_THICKNESS = 4  # Thicker outline


def _ensure_rgba(color: Union[Tuple[int, ...], List[int]]) -> ColorRGBA:
    """Ensure color is RGBA format. Convert RGB to RGBA with alpha=255."""
    if len(color) == 3:
        return (color[0], color[1], color[2], 255)
    return (color[0], color[1], color[2], color[3])


def draw_circle(renderer: PygameRenderer,
                center: Tuple[int, int],
                radius: int,
                color: ColorRGBA) -> None:
    """
    Draw a circle shape.

    Args:
        renderer: Renderer instance
        center: Screen coordinates (x, y)
        radius: Radius in pixels
        color: RGBA color tuple
    """
    color = _ensure_rgba(color)
    alpha = color[3]
    rgb = color[:3]

    if alpha < 255:
        # Use transparency
        points = _circle_to_polygon(center, radius, 32)
        renderer.draw_polygon_alpha(points, rgb, alpha)
        renderer.draw_polygon_alpha(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_circle(center, radius, rgb)
        renderer.draw_circle(center, radius, (0, 0, 0), 2)  # Border


def draw_box(renderer: PygameRenderer,
             center: Tuple[int, int],
             size: int,
             color: ColorRGBA,
             angle: Optional[float] = None) -> None:
    """
    Draw a box/square shape, optionally rotated.

    Args:
        renderer: Renderer instance
        center: Screen coordinates (x, y)
        size: Half-size in pixels (full box is 2*size x 2*size)
        color: RGBA color tuple
        angle: Rotation angle in radians (screen coordinates). None = axis-aligned.
    """
    color = _ensure_rgba(color)
    alpha = color[3]
    rgb = color[:3]

    if angle is not None:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Box corners in local coordinates
        corners = [
            (-size, -size),
            (size, -size),
            (size, size),
            (-size, size)
        ]

        # Rotate and translate
        points = []
        for px, py in corners:
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            points.append((center[0] + int(rx), center[1] + int(ry)))
    else:
        # Axis-aligned box
        points = [
            (center[0] - size, center[1] - size),
            (center[0] + size, center[1] - size),
            (center[0] + size, center[1] + size),
            (center[0] - size, center[1] + size),
        ]

    if alpha < 255:
        renderer.draw_polygon_alpha(points, rgb, alpha)
        renderer.draw_polygon_alpha(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_polygon(points, rgb)
        renderer.draw_polygon(points, (0, 0, 0), 2)  # Border


def draw_triangle(renderer: PygameRenderer,
                  center: Tuple[int, int],
                  size: int,
                  color: ColorRGBA,
                  angle: Optional[float] = None) -> None:
    """
    Draw a triangle shape pointing in the direction of angle.

    Args:
        renderer: Renderer instance
        center: Screen coordinates (x, y)
        size: Size in pixels
        color: RGBA color tuple
        angle: Direction angle in radians (screen coordinates). None = pointing up.
    """
    color = _ensure_rgba(color)
    alpha = color[3]
    rgb = color[:3]

    if angle is not None:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Triangle points in local coordinates (pointing right when angle=0)
        points_local = [
            (size, 0),  # Tip
            (-size * 0.5, -size * 0.866),  # Back left
            (-size * 0.5, size * 0.866)   # Back right
        ]

        # Rotate and translate
        points = []
        for px, py in points_local:
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            points.append((center[0] + int(rx), center[1] + int(ry)))
    else:
        # Default upward-pointing triangle
        points = [
            (center[0], center[1] - size),
            (center[0] - int(size * 0.866), center[1] + int(size * 0.5)),
            (center[0] + int(size * 0.866), center[1] + int(size * 0.5))
        ]

    if alpha < 255:
        renderer.draw_polygon_alpha(points, rgb, alpha)
        renderer.draw_polygon_alpha(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_polygon(points, rgb)
        renderer.draw_polygon(points, (0, 0, 0), 2)  # Border


def draw_polygon(renderer: PygameRenderer,
                 center: Tuple[int, int],
                 vertices: List[Tuple[float, float]],
                 scale: float,
                 color: ColorRGBA,
                 angle: Optional[float] = None) -> None:
    """
    Draw a custom polygon shape.

    Args:
        renderer: Renderer instance
        center: Screen coordinates (x, y)
        vertices: List of (x, y) vertices relative to center (in normalized units)
        scale: Scale factor (pixels per unit)
        color: RGBA color tuple
        angle: Rotation angle in radians. None = no rotation.
    """
    color = _ensure_rgba(color)
    alpha = color[3]
    rgb = color[:3]

    if len(vertices) < 3:
        return

    if angle is not None:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        points = []
        for vx, vy in vertices:
            px = vx * scale
            py = vy * scale
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            points.append((center[0] + int(rx), center[1] + int(ry)))
    else:
        points = []
        for vx, vy in vertices:
            px = center[0] + int(vx * scale)
            py = center[1] + int(vy * scale)
            points.append((px, py))

    if alpha < 255:
        renderer.draw_polygon_alpha(points, rgb, alpha)
        renderer.draw_polygon_alpha(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_polygon(points, rgb)
        renderer.draw_polygon(points, (0, 0, 0), 2)  # Border


def draw_orientation_arrow(renderer: PygameRenderer,
                           start: Tuple[int, int],
                           end: Tuple[int, int],
                           color: ColorRGBA,
                           thickness: int = 2) -> None:
    """
    Draw an orientation arrow from start to end.

    Args:
        renderer: Renderer instance
        start: Arrow start in screen coordinates
        end: Arrow end in screen coordinates
        color: RGBA color tuple
        thickness: Line thickness in pixels
    """
    color = _ensure_rgba(color)
    rgb = color[:3]
    # Draw main line
    renderer.draw_line(start, end, rgb, thickness)

    # Calculate arrowhead
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    arrow_length = math.sqrt(dx * dx + dy * dy)

    if arrow_length < 1:
        return

    screen_angle = math.atan2(dy, dx)
    arrow_size = max(5, int(arrow_length // 4))

    arrowhead_points = [
        end,
        (end[0] - int(arrow_size * math.cos(screen_angle - 0.5)),
         end[1] - int(arrow_size * math.sin(screen_angle - 0.5))),
        (end[0] - int(arrow_size * math.cos(screen_angle + 0.5)),
         end[1] - int(arrow_size * math.sin(screen_angle + 0.5)))
    ]
    renderer.draw_polygon(arrowhead_points, rgb)


def draw_label(renderer: PygameRenderer,
               text: str,
               position: Tuple[int, int],
               offset: Tuple[int, int] = (0, 0)) -> None:
    """
    Draw a text label with background.

    Args:
        renderer: Renderer instance
        text: Label text
        position: Base position in screen coordinates
        offset: Offset from base position
    """
    label_pos = (position[0] + offset[0], position[1] + offset[1])
    renderer.draw_text(text, label_pos, (255, 255, 255), 24, (0, 0, 0))


def draw_rigidbody(renderer: PygameRenderer,
                   rigidbody: RigidBody,
                   screen_pos: Tuple[int, int],
                   screen_size: int,
                   screen_orientation: Optional[float],
                   orientation_end: Optional[Tuple[int, int]] = None,
                   label_offset_pixels: Tuple[int, int] = (0, 0)) -> None:
    """
    Draw a complete rigid body with shape, orientation arrow, and label.

    This is the single render path for all rigid bodies - ensures consistent
    handling of orientation transformation.

    Args:
        renderer: Renderer instance
        rigidbody: RigidBody to draw
        screen_pos: Position in screen coordinates
        screen_size: Size in pixels
        screen_orientation: Orientation in screen coordinates (radians)
        orientation_end: End point of orientation arrow in screen coordinates
        label_offset_pixels: Label offset in pixels
    """
    style = rigidbody.style

    # Draw shape based on type (ADR-8: colors are RGBA)
    if style.shape == RigidBodyShape.CIRCLE:
        draw_circle(renderer, screen_pos, screen_size, style.color)

    elif style.shape == RigidBodyShape.BOX:
        draw_box(renderer, screen_pos, screen_size, style.color, screen_orientation)

    elif style.shape == RigidBodyShape.TRIANGLE:
        draw_triangle(renderer, screen_pos, screen_size, style.color, screen_orientation)

    elif style.shape == RigidBodyShape.POLYGON:
        if style.polygon_vertices:
            draw_polygon(renderer, screen_pos, style.polygon_vertices,
                         screen_size, style.color, screen_orientation)

    # Draw tracking lost indicator (thick red outline)
    if rigidbody.tracking_lost:
        _draw_tracking_lost_outline(
            renderer, style.shape, screen_pos, screen_size,
            screen_orientation, style.polygon_vertices
        )

    # Draw orientation arrow if we have orientation end point
    if orientation_end is not None:
        draw_orientation_arrow(renderer, screen_pos, orientation_end,
                               style.orientation_color, style.orientation_thickness)

    # Draw label if enabled
    if style.label:
        draw_label(renderer, rigidbody.name, screen_pos, label_offset_pixels)


def _circle_to_polygon(center: Tuple[int, int], radius: int,
                       num_points: int = 32) -> List[Tuple[int, int]]:
    """Convert circle to polygon points for alpha rendering."""
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = center[0] + int(radius * math.cos(angle))
        y = center[1] + int(radius * math.sin(angle))
        points.append((x, y))
    return points


def _draw_tracking_lost_outline(renderer: PygameRenderer,
                                 shape: RigidBodyShape,
                                 center: Tuple[int, int],
                                 size: int,
                                 angle: Optional[float] = None,
                                 polygon_vertices: Optional[List[Tuple[float, float]]] = None) -> None:
    """
    Draw a thick red outline to indicate tracking lost.

    Args:
        renderer: Renderer instance
        shape: Shape type
        center: Screen coordinates (x, y)
        size: Size in pixels
        angle: Rotation angle in radians (screen coordinates)
        polygon_vertices: For POLYGON shape, list of vertices
    """
    if shape == RigidBodyShape.CIRCLE:
        renderer.draw_circle(center, size, TRACKING_LOST_COLOR, TRACKING_LOST_THICKNESS)

    elif shape == RigidBodyShape.BOX:
        if angle is not None:
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            corners = [(-size, -size), (size, -size), (size, size), (-size, size)]
            points = []
            for px, py in corners:
                rx = px * cos_a - py * sin_a
                ry = px * sin_a + py * cos_a
                points.append((center[0] + int(rx), center[1] + int(ry)))
        else:
            points = [
                (center[0] - size, center[1] - size),
                (center[0] + size, center[1] - size),
                (center[0] + size, center[1] + size),
                (center[0] - size, center[1] + size),
            ]
        renderer.draw_polygon(points, TRACKING_LOST_COLOR, TRACKING_LOST_THICKNESS)

    elif shape == RigidBodyShape.TRIANGLE:
        if angle is not None:
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            points_local = [(size, 0), (-size * 0.5, -size * 0.866), (-size * 0.5, size * 0.866)]
            points = []
            for px, py in points_local:
                rx = px * cos_a - py * sin_a
                ry = px * sin_a + py * cos_a
                points.append((center[0] + int(rx), center[1] + int(ry)))
        else:
            points = [
                (center[0], center[1] - size),
                (center[0] - int(size * 0.866), center[1] + int(size * 0.5)),
                (center[0] + int(size * 0.866), center[1] + int(size * 0.5))
            ]
        renderer.draw_polygon(points, TRACKING_LOST_COLOR, TRACKING_LOST_THICKNESS)

    elif shape == RigidBodyShape.POLYGON and polygon_vertices:
        if angle is not None:
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            points = []
            for vx, vy in polygon_vertices:
                px = vx * size
                py = vy * size
                rx = px * cos_a - py * sin_a
                ry = px * sin_a + py * cos_a
                points.append((center[0] + int(rx), center[1] + int(ry)))
        else:
            points = [(center[0] + int(vx * size), center[1] + int(vy * size))
                      for vx, vy in polygon_vertices]
        renderer.draw_polygon(points, TRACKING_LOST_COLOR, TRACKING_LOST_THICKNESS)
