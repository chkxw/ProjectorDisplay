"""Core components for projector display."""

from projector_display.core.field_calibrator import FieldCalibrator, Field
from projector_display.core.rigidbody import RigidBody, RigidBodyStyle, TrajectoryStyle
from projector_display.core.scene import Scene

__all__ = [
    "FieldCalibrator",
    "Field",
    "RigidBody",
    "RigidBodyStyle",
    "TrajectoryStyle",
    "Scene",
]
