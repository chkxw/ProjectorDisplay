"""
Projector Display - Scene-based projector display server for robot experiments.

This package provides a scene-based display server where:
- Scenes are created via commands (not pre-configured)
- RigidBody is the first-class displayable entity
- Multiple custom Fields (coordinate systems) per Scene
- Commands specify target coordinate field
- YAML and Commands are interconvertible
"""

from projector_display.core.field_calibrator import FieldCalibrator, Field
from projector_display.core.rigidbody import RigidBody, RigidBodyStyle, TrajectoryStyle
from projector_display.core.scene import Scene
from projector_display.client import DisplayClient

__version__ = "1.0.0"
__all__ = [
    "FieldCalibrator",
    "Field",
    "RigidBody",
    "RigidBodyStyle",
    "TrajectoryStyle",
    "Scene",
    "DisplayClient",
]
