"""
Command registry and decorator for projector display server.

Minimal decorator pattern - decorator only handles registration, no hidden behavior.
"""

from typing import Dict, Callable, Any, Optional
import functools
import logging

logger = logging.getLogger(__name__)


class CommandRegistry:
    """
    Registry for command handlers.

    Commands are registered using the @register_command decorator.
    Each command handler receives a Scene instance and returns a response dict.
    """

    def __init__(self):
        self._commands: Dict[str, Callable] = {}

    def register(self, name: str, handler: Callable) -> None:
        """
        Register a command handler.

        Args:
            name: Command name (used as "action" in JSON commands)
            handler: Function that handles the command
        """
        if name in self._commands:
            logger.warning(f"Command '{name}' is being re-registered")
        self._commands[name] = handler
        logger.debug(f"Registered command: {name}")

    def get(self, name: str) -> Optional[Callable]:
        """Get a command handler by name."""
        return self._commands.get(name)

    def execute(self, action: str, scene: Any, **params) -> Dict[str, Any]:
        """
        Execute a command.

        Args:
            action: Command name/action
            scene: Scene instance
            **params: Command parameters

        Returns:
            Response dictionary with 'status' key
        """
        handler = self._commands.get(action)
        if handler is None:
            return {
                "status": "error",
                "message": f"Unknown command: {action}",
                "available_commands": list(self._commands.keys())
            }

        try:
            result = handler(scene, **params)
            if result is None:
                result = {"status": "success"}
            elif "status" not in result:
                result["status"] = "success"
            return result
        except TypeError as e:
            # Likely missing or wrong parameters
            return {
                "status": "error",
                "message": f"Invalid parameters for '{action}': {str(e)}"
            }
        except ValueError as e:
            # Validation error
            return {
                "status": "error",
                "message": str(e)
            }
        except Exception as e:
            # Unexpected error - let it propagate for debugging
            # Per tech-spec: unhandled exceptions should crash the server
            raise

    def list_commands(self) -> list:
        """List all registered command names."""
        return list(self._commands.keys())


# Global registry instance
_registry = CommandRegistry()


def get_registry() -> CommandRegistry:
    """Get the global command registry."""
    return _registry


def register_command(func: Callable = None, *, name: str = None) -> Callable:
    """
    Decorator to register a command handler.

    Usage:
        @register_command
        def create_rigidbody(scene, name: str, style: dict = None):
            '''Create a new rigid body for display.'''
            # Implementation
            return {"status": "success", "name": name}

        @register_command(name="custom_name")
        def my_handler(scene, ...):
            ...

    The decorator only registers the function - no hidden behavior.
    Command name defaults to the function name.
    """
    def decorator(fn: Callable) -> Callable:
        cmd_name = name if name is not None else fn.__name__
        _registry.register(cmd_name, fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        return wrapper

    if func is not None:
        # Called without parentheses: @register_command
        return decorator(func)
    else:
        # Called with parentheses: @register_command(name="...")
        return decorator
