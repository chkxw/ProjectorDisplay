"""
MoCap integration package for projector display.

Optional integration with OptiTrack motion capture via MocapUtility.
Lazy-loads MocapUtility only when MoCap features are used.
"""

from projector_display.mocap.tracker import MocapTracker, MocapConfig

__all__ = ["MocapTracker", "MocapConfig"]
