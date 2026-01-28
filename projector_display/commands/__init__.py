"""
Command system for projector display server.

Commands are registered using the @register_command decorator and auto-discovered
from the core/ submodule on import.
"""

from projector_display.commands.base import (
    CommandRegistry,
    register_command,
    get_registry,
)

# Auto-import core commands to register them
from projector_display.commands import core

__all__ = [
    "CommandRegistry",
    "register_command",
    "get_registry",
]
