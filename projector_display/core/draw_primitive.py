"""
Drawing primitive data types for projector display.

DrawPrimitive is the building block for:
  1. Compound rigid bodies (body-local coordinates, scaled by style.size)
  2. Direct drawings / persistent overlays (world coordinates)

All types are data-only and JSON/YAML serializable.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from projector_display.utils.color import parse_color


class DrawPrimitiveType(Enum):
    """Types of drawing primitives."""
    CIRCLE = "circle"
    BOX = "box"
    LINE = "line"
    POLYGON = "polygon"
    TEXT = "text"
    ARROW = "arrow"


@dataclass
class DrawPrimitive:
    """
    A single drawing operation, serializable as JSON/YAML.

    Coordinate semantics depend on context:
      - Compound body: (x, y) relative to body center, +x = orientation direction.
        Scaled by style.size (local units -> meters).
      - Direct drawing: coordinates are in meters (world space, converted from
        field coords at creation time). Position stored in Drawing wrapper.

    Not all fields are used by every type:
      CIRCLE: x, y (center offset), radius
      BOX:    x, y (center offset), width, height, angle (local rotation)
      LINE:   x, y (start), x2, y2 (end)
      ARROW:  x, y (start), x2, y2 (end)
      POLYGON: vertices (list of [x, y])
      TEXT:   x, y (position), text, font_size
    """
    type: DrawPrimitiveType

    # Position / offset
    x: float = 0.0
    y: float = 0.0

    # LINE/ARROW end point
    x2: float = 0.0
    y2: float = 0.0

    # CIRCLE
    radius: float = 0.05

    # BOX
    width: float = 0.1
    height: float = 0.1
    angle: float = 0.0  # Local rotation in radians

    # POLYGON
    vertices: Optional[List[Tuple[float, float]]] = None

    # TEXT
    text: str = ""
    font_size: int = 24

    # Style
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    thickness: int = 0   # 0 = filled, >0 = outline/line width in pixels
    filled: bool = True

    def to_dict(self) -> dict:
        """Serialize to dictionary. Only includes fields relevant to this type."""
        data = {
            'type': self.type.value,
            'color': list(self.color),
            'thickness': self.thickness,
            'filled': self.filled,
        }

        if self.type == DrawPrimitiveType.CIRCLE:
            data['x'] = self.x
            data['y'] = self.y
            data['radius'] = self.radius

        elif self.type == DrawPrimitiveType.BOX:
            data['x'] = self.x
            data['y'] = self.y
            data['width'] = self.width
            data['height'] = self.height
            data['angle'] = self.angle

        elif self.type in (DrawPrimitiveType.LINE, DrawPrimitiveType.ARROW):
            data['x'] = self.x
            data['y'] = self.y
            data['x2'] = self.x2
            data['y2'] = self.y2

        elif self.type == DrawPrimitiveType.POLYGON:
            data['vertices'] = [list(v) for v in self.vertices] if self.vertices else []

        elif self.type == DrawPrimitiveType.TEXT:
            data['x'] = self.x
            data['y'] = self.y
            data['text'] = self.text
            data['font_size'] = self.font_size

        return data

    @classmethod
    def from_dict(cls, data: dict) -> "DrawPrimitive":
        """Deserialize from dictionary."""
        ptype = DrawPrimitiveType(data['type'])
        return cls(
            type=ptype,
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            x2=data.get('x2', 0.0),
            y2=data.get('y2', 0.0),
            radius=data.get('radius', 0.05),
            width=data.get('width', 0.1),
            height=data.get('height', 0.1),
            angle=data.get('angle', 0.0),
            vertices=[tuple(v) for v in data['vertices']] if data.get('vertices') else None,
            text=data.get('text', ''),
            font_size=data.get('font_size', 24),
            color=parse_color(data.get('color', [255, 255, 255, 255])),
            thickness=data.get('thickness', 0),
            filled=data.get('filled', True),
        )


@dataclass
class Drawing:
    """
    A persistent screen drawing (direct drawing overlay).

    Positioned in world coordinates (converted from field coords at creation time).
    Rendered every frame until explicitly removed.
    """
    id: str
    primitive: DrawPrimitive
    world_x: float = 0.0
    world_y: float = 0.0
    # LINE/ARROW second endpoint in world coordinates
    world_x2: float = 0.0
    world_y2: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'primitive': self.primitive.to_dict(),
            'world_x': self.world_x,
            'world_y': self.world_y,
            'world_x2': self.world_x2,
            'world_y2': self.world_y2,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Drawing":
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            primitive=DrawPrimitive.from_dict(data['primitive']),
            world_x=data.get('world_x', 0.0),
            world_y=data.get('world_y', 0.0),
            world_x2=data.get('world_x2', 0.0),
            world_y2=data.get('world_y2', 0.0),
        )
