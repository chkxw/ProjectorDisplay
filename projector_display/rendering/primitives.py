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
                   orientation_end: Optional[Tuple[int, int]],
                   label_offset_pixels: Tuple[int, int],
                   body_world_pos: Tuple[float, float],
                   body_size: float,
                   body_world_angle: float,
                   world_to_screen_batch_fn: Callable) -> None:
    """
    Draw a complete rigid body with shape, orientation arrow, and label.

    Uses the vertex-transform pipeline: compute world vertices, batch-convert
    to screen via homography, then draw screen polygons.

    Args:
        renderer: Renderer instance
        rigidbody: RigidBody to draw
        screen_pos: Position in screen coordinates (for label/tracking)
        screen_size: Size in pixels (for tracking-lost outline)
        screen_orientation: Orientation in screen coordinates (radians, for tracking-lost)
        orientation_end: End point of orientation arrow in screen coordinates
        label_offset_pixels: Label offset in pixels
        body_world_pos: World-space position (x, y)
        body_size: World-space size (meters)
        body_world_angle: World-space orientation (radians)
        world_to_screen_batch_fn: Callable that converts list of world points to screen points
    """
    style = rigidbody.style
    batch_fn = world_to_screen_batch_fn

    color = _ensure_rgba(style.color)
    alpha = color[3]
    rgb = color[:3]
    cos_b = math.cos(body_world_angle)
    sin_b = math.sin(body_world_angle)

    # Draw shape based on type (ADR-8: colors are RGBA)
    if style.shape == RigidBodyShape.CIRCLE:
        # Circle → N-gon polygon in world space
        world_verts = []
        for i in range(32):
            theta = 2.0 * math.pi * i / 32
            wx = body_world_pos[0] + body_size * math.cos(theta)
            wy = body_world_pos[1] + body_size * math.sin(theta)
            world_verts.append((wx, wy))
        screen_pts = batch_fn(world_verts)
        _draw_polygon_filled_or_outline(renderer, screen_pts, rgb, alpha, True, 0)

    elif style.shape == RigidBodyShape.BOX:
        # 4 world corners using body angle
        corners_local = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        world_verts = []
        for lx, ly in corners_local:
            sx = lx * body_size
            sy = ly * body_size
            wx = body_world_pos[0] + sx * cos_b - sy * sin_b
            wy = body_world_pos[1] + sx * sin_b + sy * cos_b
            world_verts.append((wx, wy))
        screen_pts = batch_fn(world_verts)
        _draw_polygon_filled_or_outline(renderer, screen_pts, rgb, alpha, True, 0)

    elif style.shape == RigidBodyShape.TRIANGLE:
        # 3 world vertices (pointing in orientation direction)
        tri_local = [(1.0, 0.0), (-0.5, -0.866), (-0.5, 0.866)]
        world_verts = []
        for lx, ly in tri_local:
            sx = lx * body_size
            sy = ly * body_size
            wx = body_world_pos[0] + sx * cos_b - sy * sin_b
            wy = body_world_pos[1] + sx * sin_b + sy * cos_b
            world_verts.append((wx, wy))
        screen_pts = batch_fn(world_verts)
        _draw_polygon_filled_or_outline(renderer, screen_pts, rgb, alpha, True, 0)

    elif style.shape == RigidBodyShape.POLYGON:
        if style.polygon_vertices and len(style.polygon_vertices) >= 3:
            world_verts = []
            for vx, vy in style.polygon_vertices:
                sx = vx * body_size
                sy = vy * body_size
                wx = body_world_pos[0] + sx * cos_b - sy * sin_b
                wy = body_world_pos[1] + sx * sin_b + sy * cos_b
                world_verts.append((wx, wy))
            screen_pts = batch_fn(world_verts)
            _draw_polygon_filled_or_outline(renderer, screen_pts, rgb, alpha, True, 0)

    elif style.shape == RigidBodyShape.COMPOUND:
        if style.draw_list:
            draw_compound(renderer, style.draw_list,
                          body_world_pos, body_size,
                          body_world_angle, batch_fn)

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


def _draw_polygon_filled_or_outline(renderer: Renderer,
                                     points: List[Tuple[int, int]],
                                     rgb: Tuple[int, int, int],
                                     alpha: int, filled: bool,
                                     thickness: int) -> None:
    """Draw a polygon with fill/outline handling."""
    if filled:
        if alpha < 255:
            renderer.draw_polygon(points, rgb, alpha)
            renderer.draw_polygon(points, (0, 0, 0), alpha, 2)
        else:
            renderer.draw_polygon(points, rgb)
            renderer.draw_polygon(points, (0, 0, 0), border=2)
    else:
        thickness = thickness if thickness > 0 else 2
        if alpha < 255:
            renderer.draw_polygon(points, rgb, alpha, thickness)
        else:
            renderer.draw_polygon(points, rgb, border=thickness)


def _local_to_world(lx: float, ly: float,
                    body_pos: Tuple[float, float],
                    body_size: float,
                    cos_b: float, sin_b: float) -> Tuple[float, float]:
    """Transform body-local point to world coordinates."""
    sx = lx * body_size
    sy = ly * body_size
    wx = body_pos[0] + sx * cos_b - sy * sin_b
    wy = body_pos[1] + sx * sin_b + sy * cos_b
    return (wx, wy)


def draw_compound(renderer: Renderer,
                  primitives: List[DrawPrimitive],
                  body_world_pos: Tuple[float, float],
                  body_size: float,
                  body_world_angle: float,
                  world_to_screen_batch_fn: Callable,
                  circle_segments: int = 32) -> None:
    """
    Draw a compound shape using the vertex-transform pipeline.

    Each primitive's local vertices are transformed to world coordinates,
    then batch-converted to screen coordinates via homography.

    For efficiency, all world vertices across all primitives are collected
    into one list, converted in a single batch call, then distributed back.

    Args:
        renderer: Renderer instance
        primitives: List of DrawPrimitive definitions
        body_world_pos: Body position in world coordinates
        body_size: Body size in world units (local→world scale)
        body_world_angle: Body orientation in world radians
        world_to_screen_batch_fn: Batch world→screen converter
        circle_segments: Segments for circle polygon approximation
    """
    cos_b = math.cos(body_world_angle)
    sin_b = math.sin(body_world_angle)

    sorted_prims = sorted(primitives, key=lambda p: p.z_order)

    # Phase 1: Collect all world vertices and record per-primitive ranges
    all_world = []
    prim_ranges = []  # (start_idx, count, prim)

    for prim in sorted_prims:
        start = len(all_world)

        if prim.type == DrawPrimitiveType.CIRCLE:
            for i in range(circle_segments):
                theta = 2.0 * math.pi * i / circle_segments
                lx = prim.x + prim.radius * math.cos(theta)
                ly = prim.y + prim.radius * math.sin(theta)
                all_world.append(_local_to_world(lx, ly, body_world_pos,
                                                 body_size, cos_b, sin_b))

        elif prim.type == DrawPrimitiveType.BOX:
            hw, hh = prim.width / 2.0, prim.height / 2.0
            cos_p = math.cos(prim.angle)
            sin_p = math.sin(prim.angle)
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
                lx = prim.x + dx * cos_p - dy * sin_p
                ly = prim.y + dx * sin_p + dy * cos_p
                all_world.append(_local_to_world(lx, ly, body_world_pos,
                                                 body_size, cos_b, sin_b))

        elif prim.type in (DrawPrimitiveType.LINE, DrawPrimitiveType.ARROW):
            all_world.append(_local_to_world(prim.x, prim.y, body_world_pos,
                                             body_size, cos_b, sin_b))
            all_world.append(_local_to_world(prim.x2, prim.y2, body_world_pos,
                                             body_size, cos_b, sin_b))

        elif prim.type == DrawPrimitiveType.POLYGON:
            if prim.vertices and len(prim.vertices) >= 3:
                for vx, vy in prim.vertices:
                    all_world.append(_local_to_world(vx, vy, body_world_pos,
                                                     body_size, cos_b, sin_b))

        elif prim.type == DrawPrimitiveType.TEXT:
            all_world.append(_local_to_world(prim.x, prim.y, body_world_pos,
                                             body_size, cos_b, sin_b))

        count = len(all_world) - start
        if count > 0:
            prim_ranges.append((start, count, prim))

    if not all_world:
        return

    # Phase 2: Single batch world→screen conversion
    all_screen = world_to_screen_batch_fn(all_world)

    # Phase 3: Draw each primitive using its screen points
    for start, count, prim in prim_ranges:
        color = _ensure_rgba(prim.color)
        alpha = color[3]
        rgb = color[:3]
        pts = all_screen[start:start + count]

        if prim.type == DrawPrimitiveType.CIRCLE:
            _draw_polygon_filled_or_outline(renderer, pts, rgb, alpha,
                                            prim.filled, prim.thickness)

        elif prim.type == DrawPrimitiveType.BOX:
            _draw_polygon_filled_or_outline(renderer, pts, rgb, alpha,
                                            prim.filled, prim.thickness)

        elif prim.type in (DrawPrimitiveType.LINE, DrawPrimitiveType.ARROW):
            thickness = prim.thickness if prim.thickness > 0 else 2
            if prim.type == DrawPrimitiveType.LINE:
                renderer.draw_line(pts[0], pts[1], rgb, alpha, thickness)
            else:
                draw_orientation_arrow(renderer, pts[0], pts[1], color, thickness)

        elif prim.type == DrawPrimitiveType.POLYGON:
            if count >= 3:
                _draw_polygon_filled_or_outline(renderer, pts, rgb, alpha,
                                                prim.filled, prim.thickness)

        elif prim.type == DrawPrimitiveType.TEXT:
            renderer.draw_text(prim.text, pts[0], rgb, prim.font_size, (0, 0, 0))
