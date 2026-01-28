"""
Prebuilt commands for projector display server.

These are researcher-friendly commands that provide intuitive access
to display functionality.
"""

# Import all command modules to trigger registration
from projector_display.commands.prebuilt import rigidbody_commands
from projector_display.commands.prebuilt import field_commands
from projector_display.commands.prebuilt import scene_commands
from projector_display.commands.prebuilt import debug_commands

__all__ = [
    "rigidbody_commands",
    "field_commands",
    "scene_commands",
    "debug_commands",
]
