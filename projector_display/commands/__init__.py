"""
Command system for projector display server.

Commands are registered using the @register_command decorator and auto-discovered
from the prebuilt/ submodule on import.
"""

from projector_display.commands.base import (
    CommandRegistry,
    register_command,
    get_registry,
)

# Auto-import prebuilt commands to register them
from projector_display.commands import prebuilt

__all__ = [
    "CommandRegistry",
    "register_command",
    "get_registry",
]
