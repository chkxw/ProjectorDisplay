"""
Dual-sink logging for projector display server.

Logs to both stdout/stderr AND a log file.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional


# Log file paths (in order of preference)
LOG_FILE_PATHS = [
    "/var/log/projector_display.log",
    "/tmp/projector_display.log",
]


def setup_logging(verbose: bool = False,
                  log_file: Optional[str] = None,
                  log_format: str = None) -> logging.Logger:
    """
    Setup dual-sink logging.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
        log_file: Override log file path. If None, uses default paths.
        log_format: Override log format string.

    Returns:
        Root logger
    """
    level = logging.DEBUG if verbose else logging.INFO

    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create handlers list
    handlers = []

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)

    # File handler
    file_path = log_file
    if file_path is None:
        # Try default paths
        for path in LOG_FILE_PATHS:
            try:
                # Check if we can write to this location
                test_path = Path(path)
                test_path.parent.mkdir(parents=True, exist_ok=True)
                # Try to open file for append
                with open(path, 'a') as f:
                    pass
                file_path = path
                break
            except (PermissionError, OSError):
                continue

    if file_path:
        try:
            file_handler = logging.FileHandler(file_path, mode='a')
            file_handler.setLevel(level)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        except Exception as e:
            # Log to console that file logging failed
            print(f"Warning: Could not setup file logging at {file_path}: {e}",
                  file=sys.stderr)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )

    # Also configure projector_display logger
    logger = logging.getLogger("projector_display")
    logger.setLevel(level)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
