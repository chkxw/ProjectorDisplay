"""
Shape drawing primitives for rigid body visualization.

All orientation rendering goes through transform_orientation() to ensure
correct handling of coordinate transformations.

Based on draw_robot() from box_push_deploy/shared/display_toolbox.py.

ADR-8: All colors use RGBA format (4-tuple). RGB (3-tuple) is auto-converted.
"""

import math
from typing import Tuple, List, Optional, Callable, Union
from projector_display.rendering.renderer import Renderer
from projector_display.core.rigidbody import RigidBody, RigidBodyShape
from projector_display.core.draw_primitive import DrawPrimitive, DrawPrimitiveType

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


def draw_circle(renderer: Renderer,
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

    renderer.draw_circle(center, radius, rgb, alpha=alpha)
    renderer.draw_circle(center, radius, (0, 0, 0), alpha=alpha, border=2)


def draw_box(renderer: Renderer,
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
        renderer.draw_polygon(points, rgb, alpha)
        renderer.draw_polygon(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_polygon(points, rgb)
        renderer.draw_polygon(points, (0, 0, 0), border=2)


def draw_triangle(renderer: Renderer,
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
        renderer.draw_polygon(points, rgb, alpha)
        renderer.draw_polygon(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_polygon(points, rgb)
        renderer.draw_polygon(points, (0, 0, 0), border=2)


def draw_polygon(renderer: Renderer,
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
        renderer.draw_polygon(points, rgb, alpha)
        renderer.draw_polygon(points, (0, 0, 0), alpha, 2)
    else:
        renderer.draw_polygon(points, rgb)
        renderer.draw_polygon(points, (0, 0, 0), border=2)


def draw_orientation_arrow(renderer: Renderer,
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
    renderer.draw_line(start, end, rgb, width=thickness)

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


def draw_label(renderer: Renderer,
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


def draw_rigidbody(renderer: Renderer,
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

    elif style.shape == RigidBodyShape.COMPOUND:
        if style.draw_list:
            draw_compound(renderer, screen_pos, screen_size,
                          style.draw_list, screen_orientation)

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


def _draw_tracking_lost_outline(renderer: Renderer,
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
        renderer.draw_circle(center, size, TRACKING_LOST_COLOR, border=TRACKING_LOST_THICKNESS)

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
        renderer.draw_polygon(points, TRACKING_LOST_COLOR, border=TRACKING_LOST_THICKNESS)

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
        renderer.draw_polygon(points, TRACKING_LOST_COLOR, border=TRACKING_LOST_THICKNESS)

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
        renderer.draw_polygon(points, TRACKING_LOST_COLOR, border=TRACKING_LOST_THICKNESS)

    elif shape == RigidBodyShape.COMPOUND:
        # Bounding circle fallback for compound shapes
        renderer.draw_circle(center, size, TRACKING_LOST_COLOR, border=TRACKING_LOST_THICKNESS)


def _batch_key(prim: DrawPrimitive) -> tuple:
    """Create a grouping key for batching consecutive primitives."""
    color = _ensure_rgba(prim.color)
    return (prim.type, color, prim.filled, prim.thickness, prim.z_order)


def draw_compound(renderer: Renderer,
                  center: Tuple[int, int],
                  scale: int,
                  primitives: List[DrawPrimitive],
                  angle: Optional[float] = None) -> None:
    """
    Draw a compound shape from a list of DrawPrimitives.

    Groups consecutive primitives with the same type/color/style for batched
    rendering when possible (filled circles -> draw_circles_batch, lines ->
    draw_lines_batch). Non-batchable types and single-element groups
    fall through to _draw_single_primitive.

    Args:
        renderer: Renderer instance
        center: Body position in screen coordinates
        scale: Pixels per local unit (from world_scale(pos, style.size))
        primitives: List of DrawPrimitive definitions
        angle: Body orientation in screen radians
    """
    cos_a = math.cos(angle) if angle is not None else 1.0
    sin_a = math.sin(angle) if angle is not None else 0.0

    sorted_prims = sorted(primitives, key=lambda p: p.z_order)

    # Group consecutive primitives with same batch key
    i = 0
    while i < len(sorted_prims):
        prim = sorted_prims[i]
        key = _batch_key(prim)

        # Collect consecutive primitives with the same key
        group = [prim]
        j = i + 1
        while j < len(sorted_prims) and _batch_key(sorted_prims[j]) == key:
            group.append(sorted_prims[j])
            j += 1
        i = j

        ptype = key[0]
        color = key[1]
        filled = key[2]
        thickness = key[3]
        alpha = color[3]
        rgb = color[:3]

        # Batch filled circles (>1 element)
        if ptype == DrawPrimitiveType.CIRCLE and filled and len(group) > 1:
            circles = []
            for p in group:
                screen_pos = _transform_local_point(p.x, p.y, center, scale, cos_a, sin_a)
                screen_radius = max(1, int(p.radius * scale))
                circles.append((screen_pos, screen_radius))

            renderer.draw_circles_batch(circles, rgb, alpha)
            if thickness > 0:
                renderer.draw_circles_batch(circles, (0, 0, 0), alpha, border=thickness)

        # Batch lines (>1 element)
        elif ptype == DrawPrimitiveType.LINE and len(group) > 1:
            lines = []
            line_thickness = thickness if thickness > 0 else 2
            for p in group:
                s = _transform_local_point(p.x, p.y, center, scale, cos_a, sin_a)
                e = _transform_local_point(p.x2, p.y2, center, scale, cos_a, sin_a)
                lines.append((s, e))
            renderer.draw_lines_batch(lines, rgb, alpha, line_thickness)

        # Non-batchable or single-element: fall through to individual draws
        else:
            for p in group:
                _draw_single_primitive(renderer, p, center, scale, cos_a, sin_a, angle)


def _transform_local_point(lx: float, ly: float,
                           center: Tuple[int, int],
                           scale: int,
                           cos_a: float, sin_a: float) -> Tuple[int, int]:
    """Transform a body-local point to screen coordinates."""
    px = lx * scale
    py = ly * scale
    sx = center[0] + int(px * cos_a - py * sin_a)
    sy = center[1] + int(px * sin_a + py * cos_a)
    return (sx, sy)


def _draw_single_primitive(renderer: Renderer,
                           prim: DrawPrimitive,
                           center: Tuple[int, int],
                           scale: int,
                           cos_a: float, sin_a: float,
                           body_angle: Optional[float]) -> None:
    """
    Draw one primitive of a compound shape, applying body transform.

    Args:
        renderer: Renderer instance
        prim: The primitive to draw
        center: Body screen position
        scale: Pixels per local unit
        cos_a, sin_a: Precomputed body rotation
        body_angle: Body orientation in screen radians (for combining with local angles)
    """
    color = _ensure_rgba(prim.color)
    alpha = color[3]
    rgb = color[:3]

    if prim.type == DrawPrimitiveType.CIRCLE:
        screen_pos = _transform_local_point(prim.x, prim.y, center, scale, cos_a, sin_a)
        screen_radius = max(1, int(prim.radius * scale))

        if prim.filled:
            renderer.draw_circle(screen_pos, screen_radius, rgb, alpha=alpha)
            if prim.thickness > 0:
                renderer.draw_circle(screen_pos, screen_radius, (0, 0, 0),
                                     alpha=alpha, border=prim.thickness)
        else:
            thickness = prim.thickness if prim.thickness > 0 else 2
            renderer.draw_circle(screen_pos, screen_radius, rgb,
                                 alpha=alpha, border=thickness)

    elif prim.type == DrawPrimitiveType.BOX:
        screen_pos = _transform_local_point(prim.x, prim.y, center, scale, cos_a, sin_a)
        hw = max(1, int(prim.width * scale * 0.5))
        hh = max(1, int(prim.height * scale * 0.5))

        # Combine body angle with local angle
        combined_angle = (body_angle or 0.0) + prim.angle

        cos_c = math.cos(combined_angle)
        sin_c = math.sin(combined_angle)
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        points = []
        for bx, by in corners:
            rx = bx * cos_c - by * sin_c
            ry = bx * sin_c + by * cos_c
            points.append((screen_pos[0] + int(rx), screen_pos[1] + int(ry)))

        if prim.filled:
            if alpha < 255:
                renderer.draw_polygon(points, rgb, alpha)
                if prim.thickness > 0:
                    renderer.draw_polygon(points, (0, 0, 0), alpha, prim.thickness)
            else:
                renderer.draw_polygon(points, rgb)
                if prim.thickness > 0:
                    renderer.draw_polygon(points, (0, 0, 0), border=prim.thickness)
        else:
            thickness = prim.thickness if prim.thickness > 0 else 2
            if alpha < 255:
                renderer.draw_polygon(points, rgb, alpha, thickness)
            else:
                renderer.draw_polygon(points, rgb, border=thickness)

    elif prim.type in (DrawPrimitiveType.LINE, DrawPrimitiveType.ARROW):
        screen_start = _transform_local_point(prim.x, prim.y, center, scale, cos_a, sin_a)
        screen_end = _transform_local_point(prim.x2, prim.y2, center, scale, cos_a, sin_a)
        thickness = prim.thickness if prim.thickness > 0 else 2

        if prim.type == DrawPrimitiveType.LINE:
            renderer.draw_line(screen_start, screen_end, rgb, alpha, thickness)
        else:
            # ARROW: reuse draw_orientation_arrow
            draw_orientation_arrow(renderer, screen_start, screen_end, color, thickness)

    elif prim.type == DrawPrimitiveType.POLYGON:
        if not prim.vertices or len(prim.vertices) < 3:
            return
        points = [_transform_local_point(vx, vy, center, scale, cos_a, sin_a)
                  for vx, vy in prim.vertices]

        if prim.filled:
            if alpha < 255:
                renderer.draw_polygon(points, rgb, alpha)
                if prim.thickness > 0:
                    renderer.draw_polygon(points, (0, 0, 0), alpha, prim.thickness)
            else:
                renderer.draw_polygon(points, rgb)
                if prim.thickness > 0:
                    renderer.draw_polygon(points, (0, 0, 0), border=prim.thickness)
        else:
            thickness = prim.thickness if prim.thickness > 0 else 2
            if alpha < 255:
                renderer.draw_polygon(points, rgb, alpha, thickness)
            else:
                renderer.draw_polygon(points, rgb, border=thickness)

    elif prim.type == DrawPrimitiveType.TEXT:
        screen_pos = _transform_local_point(prim.x, prim.y, center, scale, cos_a, sin_a)
        renderer.draw_text(prim.text, screen_pos, rgb, prim.font_size, (0, 0, 0))
