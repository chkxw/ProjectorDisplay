"""
Drawing commands for projector display server.

Commands for creating and managing persistent drawing overlays.
Drawings are positioned in field coordinates (converted to world at creation).
"""

from projector_display.commands.base import register_command
from projector_display.core.draw_primitive import DrawPrimitive, DrawPrimitiveType, Drawing
from projector_display.utils.color import parse_color


def _to_world(scene, x, y, field):
    """Convert field coordinates to world coordinates (same pattern as update_position)."""
    if field != "base" and field in scene.field_calibrator.fields:
        world_pos = scene.field_calibrator.convert([x, y], field, "base")
        return float(world_pos[0]), float(world_pos[1])
    return float(x), float(y)


def _parse_color_param(color, default=(255, 255, 255, 255)):
    """Parse color parameter if provided, else return default."""
    if color is None:
        return default
    return parse_color(color)


@register_command
def draw_circle(scene, id: str, x: float, y: float, radius: float,
                color=None, field: str = "base",
                filled: bool = True, thickness: int = 0,
                z_order: int = 0) -> dict:
    """
    Draw a persistent circle overlay.

    Args:
        scene: Scene instance
        id: Unique identifier (replaces existing drawing with same id)
        x: X position in field coordinates
        y: Y position in field coordinates
        radius: Radius in meters
        color: RGBA color (default white)
        field: Coordinate field (default "base" = world coords)
        filled: Whether to fill (default True)
        thickness: Outline thickness in pixels (used when filled=False)
        z_order: Render order (lower = behind, default 0)

    Returns:
        Response with status and id
    """
    world_x, world_y = _to_world(scene, x, y, field)
    prim = DrawPrimitive(
        type=DrawPrimitiveType.CIRCLE,
        radius=radius,
        color=_parse_color_param(color),
        filled=filled,
        thickness=thickness,
    )
    drawing = Drawing(id=id, primitive=prim, world_x=world_x, world_y=world_y,
                      z_order=z_order)
    scene.add_drawing(drawing)
    result = {"status": "success", "id": id}
    if z_order != 0:
        result["z_order"] = z_order
    return result


@register_command
def draw_box(scene, id: str, x: float, y: float,
             width: float, height: float,
             color=None, field: str = "base",
             filled: bool = True, thickness: int = 0,
             angle: float = 0.0, z_order: int = 0) -> dict:
    """
    Draw a persistent box/rectangle overlay.

    Args:
        scene: Scene instance
        id: Unique identifier
        x: Center X in field coordinates
        y: Center Y in field coordinates
        width: Width in meters
        height: Height in meters
        color: RGBA color (default white)
        field: Coordinate field (default "base")
        filled: Whether to fill (default True)
        thickness: Outline thickness in pixels
        angle: Rotation angle in radians (default 0)
        z_order: Render order (lower = behind, default 0)

    Returns:
        Response with status and id
    """
    world_x, world_y = _to_world(scene, x, y, field)
    prim = DrawPrimitive(
        type=DrawPrimitiveType.BOX,
        width=width,
        height=height,
        angle=angle,
        color=_parse_color_param(color),
        filled=filled,
        thickness=thickness,
    )
    drawing = Drawing(id=id, primitive=prim, world_x=world_x, world_y=world_y,
                      z_order=z_order)
    scene.add_drawing(drawing)
    result = {"status": "success", "id": id}
    if z_order != 0:
        result["z_order"] = z_order
    return result


@register_command
def draw_line(scene, id: str, x1: float, y1: float,
              x2: float, y2: float,
              color=None, thickness: int = 2,
              field: str = "base", z_order: int = 0) -> dict:
    """
    Draw a persistent line overlay.

    Args:
        scene: Scene instance
        id: Unique identifier
        x1, y1: Start point in field coordinates
        x2, y2: End point in field coordinates
        color: RGBA color (default white)
        thickness: Line thickness in pixels (default 2)
        field: Coordinate field (default "base")
        z_order: Render order (lower = behind, default 0)

    Returns:
        Response with status and id
    """
    wx1, wy1 = _to_world(scene, x1, y1, field)
    wx2, wy2 = _to_world(scene, x2, y2, field)
    prim = DrawPrimitive(
        type=DrawPrimitiveType.LINE,
        color=_parse_color_param(color),
        thickness=thickness,
    )
    drawing = Drawing(id=id, primitive=prim,
                      world_x=wx1, world_y=wy1,
                      world_x2=wx2, world_y2=wy2,
                      z_order=z_order)
    scene.add_drawing(drawing)
    result = {"status": "success", "id": id}
    if z_order != 0:
        result["z_order"] = z_order
    return result


@register_command
def draw_arrow(scene, id: str, x1: float, y1: float,
               x2: float, y2: float,
               color=None, thickness: int = 2,
               field: str = "base", z_order: int = 0) -> dict:
    """
    Draw a persistent arrow overlay.

    Args:
        scene: Scene instance
        id: Unique identifier
        x1, y1: Start point in field coordinates
        x2, y2: End point (arrow tip) in field coordinates
        color: RGBA color (default white)
        thickness: Arrow thickness in pixels (default 2)
        field: Coordinate field (default "base")
        z_order: Render order (lower = behind, default 0)

    Returns:
        Response with status and id
    """
    wx1, wy1 = _to_world(scene, x1, y1, field)
    wx2, wy2 = _to_world(scene, x2, y2, field)
    prim = DrawPrimitive(
        type=DrawPrimitiveType.ARROW,
        color=_parse_color_param(color),
        thickness=thickness,
    )
    drawing = Drawing(id=id, primitive=prim,
                      world_x=wx1, world_y=wy1,
                      world_x2=wx2, world_y2=wy2,
                      z_order=z_order)
    scene.add_drawing(drawing)
    result = {"status": "success", "id": id}
    if z_order != 0:
        result["z_order"] = z_order
    return result


@register_command
def draw_polygon(scene, id: str, vertices: list,
                 color=None, field: str = "base",
                 filled: bool = True, thickness: int = 0,
                 z_order: int = 0) -> dict:
    """
    Draw a persistent polygon overlay.

    Args:
        scene: Scene instance
        id: Unique identifier
        vertices: List of [x, y] points in field coordinates (min 3)
        color: RGBA color (default white)
        field: Coordinate field (default "base")
        filled: Whether to fill (default True)
        thickness: Outline thickness in pixels
        z_order: Render order (lower = behind, default 0)

    Returns:
        Response with status and id
    """
    if not vertices or len(vertices) < 3:
        return {"status": "error", "message": "Polygon requires at least 3 vertices"}

    # Convert all vertices to world coordinates
    world_verts = []
    for v in vertices:
        wx, wy = _to_world(scene, v[0], v[1], field)
        world_verts.append((wx, wy))

    # Anchor at first vertex
    anchor_x, anchor_y = world_verts[0]

    prim = DrawPrimitive(
        type=DrawPrimitiveType.POLYGON,
        vertices=world_verts,
        color=_parse_color_param(color),
        filled=filled,
        thickness=thickness,
    )
    drawing = Drawing(id=id, primitive=prim, world_x=anchor_x, world_y=anchor_y,
                      z_order=z_order)
    scene.add_drawing(drawing)
    result = {"status": "success", "id": id}
    if z_order != 0:
        result["z_order"] = z_order
    return result


@register_command
def draw_text(scene, id: str, x: float, y: float, text: str,
              color=None, font_size: int = 24,
              field: str = "base", z_order: int = 0) -> dict:
    """
    Draw a persistent text label overlay.

    Args:
        scene: Scene instance
        id: Unique identifier
        x: X position in field coordinates
        y: Y position in field coordinates
        text: Text string to display
        color: RGBA color (default white)
        font_size: Font size in pixels (default 24)
        field: Coordinate field (default "base")
        z_order: Render order (lower = behind, default 0)

    Returns:
        Response with status and id
    """
    world_x, world_y = _to_world(scene, x, y, field)
    prim = DrawPrimitive(
        type=DrawPrimitiveType.TEXT,
        text=text,
        font_size=font_size,
        color=_parse_color_param(color),
    )
    drawing = Drawing(id=id, primitive=prim, world_x=world_x, world_y=world_y,
                      z_order=z_order)
    scene.add_drawing(drawing)
    result = {"status": "success", "id": id}
    if z_order != 0:
        result["z_order"] = z_order
    return result


@register_command
def remove_drawing(scene, id: str) -> dict:
    """
    Remove a persistent drawing by ID.

    Args:
        scene: Scene instance
        id: Drawing identifier

    Returns:
        Response with status
    """
    if scene.remove_drawing(id):
        return {"status": "success", "id": id}
    return {"status": "error", "message": f"Drawing '{id}' not found"}


@register_command
def list_drawings(scene) -> dict:
    """
    List all persistent drawing IDs.

    Returns:
        Response with list of drawing IDs
    """
    return {"status": "success", "drawings": scene.list_drawings()}


@register_command
def clear_drawings(scene) -> dict:
    """
    Remove all persistent drawings.

    Returns:
        Response with status
    """
    scene.clear_drawings()
    return {"status": "success", "message": "All drawings cleared"}
