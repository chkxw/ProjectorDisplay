"""
RigidBody and style definitions for projector display.

RigidBody is the first-class displayable entity (supports robots, payloads, any tracked object).
Based on RobotData/RobotStyle from box_push_deploy/shared/display_toolbox.py.
"""

from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import time


class RigidBodyShape(Enum):
    """Available rigid body visualization shapes"""
    CIRCLE = "circle"
    BOX = "box"
    TRIANGLE = "triangle"
    POLYGON = "polygon"  # Custom polygon shape


class TrajectoryLineStyle(Enum):
    """Trajectory line styles"""
    SOLID = "solid"
    DOTTED = "dotted"
    DASHED = "dashed"


def _normalize_color(color: Tuple[int, ...]) -> Tuple[int, int, int, int]:
    """
    Normalize color to RGBA format with clamping (ADR-8).

    Accepts RGB (3 values) or RGBA (4 values).
    RGB is converted to RGBA with alpha=255 (fully opaque).
    """
    clamped = tuple(max(0, min(255, int(c))) for c in color)
    if len(clamped) == 3:
        return clamped + (255,)  # Add full opacity
    elif len(clamped) >= 4:
        return clamped[:4]
    else:
        # Fallback for invalid input
        return (0, 0, 0, 255)


@dataclass
class RigidBodyStyle:
    """Configuration for rigid body visualization (ADR-8: RGBA colors)"""
    shape: RigidBodyShape = RigidBodyShape.CIRCLE
    size: float = 0.1  # Size in meters
    color: Tuple[int, int, int, int] = (0, 0, 255, 255)  # RGBA (alpha in 4th component)
    label: bool = True
    label_offset: Tuple[float, float] = (0, -0.2)  # Offset in meters
    orientation_length: float = 0.15  # Length of orientation arrow in meters
    orientation_color: Tuple[int, int, int, int] = (255, 255, 255, 255)  # Arrow color RGBA
    orientation_thickness: int = 2  # Arrow thickness in pixels
    polygon_vertices: Optional[List[Tuple[float, float]]] = None  # For POLYGON shape, relative to center

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'shape': self.shape.value,
            'size': self.size,
            'color': list(self.color),  # RGBA
            'label': self.label,
            'label_offset': list(self.label_offset),
            'orientation_length': self.orientation_length,
            'orientation_color': list(self.orientation_color),  # RGBA
            'orientation_thickness': self.orientation_thickness,
            'polygon_vertices': [list(v) for v in self.polygon_vertices] if self.polygon_vertices else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RigidBodyStyle":
        """Create from dictionary. Accepts RGB or RGBA (ADR-8)."""
        shape = data.get('shape', 'circle')
        if isinstance(shape, str):
            shape = RigidBodyShape(shape)
        return cls(
            shape=shape,
            size=data.get('size', 0.1),
            color=_normalize_color(tuple(data.get('color', [0, 0, 255]))),
            label=data.get('label', True),
            label_offset=tuple(data.get('label_offset', [0, -0.2])),
            orientation_length=data.get('orientation_length', 0.15),
            orientation_color=_normalize_color(tuple(data.get('orientation_color', [255, 255, 255]))),
            orientation_thickness=data.get('orientation_thickness', 2),
            polygon_vertices=[tuple(v) for v in data['polygon_vertices']] if data.get('polygon_vertices') else None,
        )


@dataclass
class TrajectoryStyle:
    """Configuration for trajectory visualization (ADR-8: RGBA colors)"""
    enabled: bool = True
    mode: str = "time"  # "time" or "distance"
    length: float = 5.0  # Seconds or meters depending on mode
    style: str = "solid"  # "solid", "dotted", "dashed"
    thickness: int = 2  # Pixels
    color: Union[Tuple[int, int, int, int], str] = (100, 100, 255, 255)  # RGBA or "gradient"
    gradient_start: Tuple[int, int, int, int] = (0, 0, 255, 255)  # Near rigid body (RGBA)
    gradient_end: Tuple[int, int, int, int] = (0, 255, 0, 255)  # At tail (RGBA, can fade to transparent)
    dot_spacing: float = 0.05  # For dotted style, spacing in meters
    dash_length: float = 0.1  # For dashed style, dash length in meters

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'length': self.length,
            'style': self.style,
            'thickness': self.thickness,
            'color': list(self.color) if isinstance(self.color, tuple) else self.color,
            'gradient_start': list(self.gradient_start),  # RGBA
            'gradient_end': list(self.gradient_end),  # RGBA
            'dot_spacing': self.dot_spacing,
            'dash_length': self.dash_length,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrajectoryStyle":
        """Create from dictionary. Accepts RGB or RGBA (ADR-8)."""
        color = data.get('color', [100, 100, 255])
        if isinstance(color, list):
            color = _normalize_color(tuple(color))
        return cls(
            enabled=data.get('enabled', True),
            mode=data.get('mode', 'time'),
            length=data.get('length', 5.0),
            style=data.get('style', 'solid'),
            thickness=data.get('thickness', 2),
            color=color,
            gradient_start=_normalize_color(tuple(data.get('gradient_start', [0, 0, 255]))),
            gradient_end=_normalize_color(tuple(data.get('gradient_end', [0, 255, 0]))),
            dot_spacing=data.get('dot_spacing', 0.05),
            dash_length=data.get('dash_length', 0.1),
        )


# F7: Default max history length (configurable)
DEFAULT_POSITION_HISTORY_MAXLEN = 10000


@dataclass
class RigidBody:
    """
    Data for a tracked rigid body.

    RigidBody is the first-class displayable entity - supports robots, payloads,
    any tracked object.
    """
    name: str
    position: Optional[Tuple[float, float]] = None  # Current position in world coords
    orientation: Optional[float] = None  # Current orientation in radians
    _last_orientation: float = field(default=0.0, repr=False)  # Internal fallback for missing orientation
    mocap_name: Optional[str] = None  # Name in MoCap system (optional)
    style: RigidBodyStyle = field(default_factory=RigidBodyStyle)
    trajectory_style: TrajectoryStyle = field(default_factory=TrajectoryStyle)
    # F7: Made configurable via set_history_maxlen() or at creation time
    position_history: deque = field(default_factory=lambda: deque(maxlen=DEFAULT_POSITION_HISTORY_MAXLEN), repr=False)
    last_update_time: float = 0

    def set_history_maxlen(self, maxlen: int):
        """Set maximum length for position history. Existing entries are preserved up to new limit."""
        old_history = list(self.position_history)
        self.position_history = deque(old_history, maxlen=maxlen)

    def update_position(self, x: float, y: float, orientation: Optional[float] = None):
        """
        Update rigid body position and orientation.

        Args:
            x: X position in world coordinates (meters)
            y: Y position in world coordinates (meters)
            orientation: Orientation in radians (optional)
        """
        self.position = (x, y)
        current_time = time.time()

        if orientation is not None:
            self.orientation = orientation
            self._last_orientation = orientation
        else:
            self.orientation = None

        # Add to position history
        self.position_history.append({
            'position': self.position,
            'orientation': self.get_effective_orientation(),
            'time': current_time,
        })

        self.last_update_time = current_time

    def get_effective_orientation(self) -> float:
        """
        Return orientation for rendering.

        If current orientation is None, uses last known orientation.
        """
        return self.orientation if self.orientation is not None else self._last_orientation

    def get_trajectory_points(self) -> List[Tuple[float, float]]:
        """
        Get trajectory points based on trajectory style settings.

        Returns:
            List of (x, y) positions for the trajectory
        """
        if not self.trajectory_style.enabled or not self.position_history:
            return []

        current_time = time.time()
        points = []

        if self.trajectory_style.mode == "time":
            # Time-based: show all positions from last N seconds
            cutoff_time = current_time - self.trajectory_style.length
            for entry in self.position_history:
                if entry['time'] >= cutoff_time:
                    points.append(entry['position'])
        else:
            # Distance-based: show trajectory of fixed length
            max_distance = self.trajectory_style.length
            total_distance = 0.0

            # Iterate backwards from most recent
            history_list = list(self.position_history)
            for i in range(len(history_list) - 1, 0, -1):
                p1 = history_list[i]['position']
                p2 = history_list[i - 1]['position']

                if not points:
                    points.append(p1)

                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                segment_dist = (dx * dx + dy * dy) ** 0.5

                if total_distance + segment_dist <= max_distance:
                    points.append(p2)
                    total_distance += segment_dist
                else:
                    # Interpolate to exact length
                    remaining = max_distance - total_distance
                    ratio = remaining / segment_dist if segment_dist > 0 else 0
                    interp_x = p1[0] + dx * ratio
                    interp_y = p1[1] + dy * ratio
                    points.append((interp_x, interp_y))
                    break

            points.reverse()

        return points

    def clear_history(self):
        """Clear position history."""
        self.position_history.clear()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'position': list(self.position) if self.position else None,
            'orientation': self.orientation,
            'mocap_name': self.mocap_name,
            'style': self.style.to_dict(),
            'trajectory': self.trajectory_style.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RigidBody":
        """Create from dictionary."""
        rb = cls(
            name=data['name'],
            mocap_name=data.get('mocap_name'),
        )
        if data.get('position'):
            rb.position = tuple(data['position'])
        if data.get('orientation') is not None:
            rb.orientation = data['orientation']
            rb._last_orientation = data['orientation']
        if data.get('style'):
            rb.style = RigidBodyStyle.from_dict(data['style'])
        if data.get('trajectory'):
            rb.trajectory_style = TrajectoryStyle.from_dict(data['trajectory'])
        return rb
