"""
Prebuilt commands for projector display server.

These are researcher-friendly commands that provide intuitive access
to display functionality.
"""

# Import all command modules to trigger registration
from . import rigidbody_commands
from . import field_commands
from . import scene_commands
from . import debug_commands
from . import asset_commands
from . import mocap_commands
from . import drawing_commands

__all__ = [
    "rigidbody_commands",
    "field_commands",
    "scene_commands",
    "debug_commands",
    "asset_commands",
    "mocap_commands",
    "drawing_commands",
]
