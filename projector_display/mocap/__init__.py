"""
MoCap integration package for projector display.

Optional integration with OptiTrack motion capture via MocapUtility.
Lazy-loads MocapUtility only when MoCap features are used.
"""

from projector_display.mocap.tracker import MocapTracker, MocapConfig, DEFAULT_NATNET_PORT

__all__ = ["MocapTracker", "MocapConfig", "DEFAULT_NATNET_PORT"]
