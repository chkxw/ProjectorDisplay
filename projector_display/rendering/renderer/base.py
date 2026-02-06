"""
Renderer protocol and shared display utilities.

Isolates rendering behind Renderer interface for future flexibility
(e.g., GPU-accelerated rendering).
"""

import os
import logging
from typing import Any, Protocol, Tuple, List, Optional
import pygame

logger = logging.getLogger(__name__)


def _get_sdl_version() -> Tuple[int, int, int]:
    """Get SDL version tuple (major, minor, patch)."""
    return pygame.get_sdl_version()


def _get_display_position_xrandr(screen_index: int) -> Tuple[int, int]:
    """
    Get display position using xrandr (required dependency).

    Args:
        screen_index: Target display index

    Returns:
        (x, y) position of the display

    Raises:
        RuntimeError: If xrandr is not available or parsing fails
    """
    import subprocess

    try:
        result = subprocess.run(['xrandr', '--listmonitors'], capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("xrandr not found. Please install xrandr (required dependency).")

    if result.returncode != 0:
        raise RuntimeError(f"xrandr failed: {result.stderr}")

    lines = result.stdout.strip().split('\n')
    for line in lines[1:]:  # Skip header "Monitors: N"
        # Format: " 0: +*eDP 2560/345x1600/215+0+0  eDP"
        # or: " 1: +HDMI-A-0 1920/1600x1080/900+352+1600  HDMI-A-0"
        parts = line.split()
        if parts and parts[0].rstrip(':') == str(screen_index):
            # Parse geometry: WxH+X+Y (e.g., "1920/1600x1080/900+352+1600")
            geom = parts[2]
            plus_parts = geom.split('+')
            if len(plus_parts) >= 3:
                x = int(plus_parts[-2])
                y = int(plus_parts[-1])
                logger.info(f"Display {screen_index} position from xrandr: ({x}, {y})")
                return (x, y)

    raise RuntimeError(f"Display {screen_index} not found in xrandr output")


def _init_display_sdl2(screen_index: int) -> pygame.Surface:
    """
    Initialize fullscreen display using SDL2 approach.

    Uses borderless window (NOFRAME) instead of true FULLSCREEN
    so the window stays visible when focus is lost.

    Args:
        screen_index: Target display index

    Returns:
        pygame.Surface for the display
    """
    num_displays = pygame.display.get_num_displays()
    if screen_index >= num_displays:
        logger.warning(f"screen_index {screen_index} not available (have {num_displays}), using 0")
        screen_index = 0

    # Get target display size
    desktop_sizes = pygame.display.get_desktop_sizes()
    target_width, target_height = desktop_sizes[screen_index]
    logger.info(f"Target display {screen_index}: {target_width}x{target_height}")

    # Get display position from xrandr (required)
    display_x, display_y = _get_display_position_xrandr(screen_index)

    # Position window on target display
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{display_x},{display_y}"

    # Create borderless window (stays visible when unfocused, unlike FULLSCREEN)
    screen = pygame.display.set_mode(
        (target_width, target_height),
        pygame.NOFRAME
    )
    return screen


def _init_display_sdl1(screen_index: int) -> pygame.Surface:
    """
    Initialize fullscreen display using SDL1.2 approach (env vars).

    Args:
        screen_index: Target display index

    Returns:
        pygame.Surface for the display
    """
    os.environ["SDL_VIDEO_FULLSCREEN_DISPLAY"] = str(screen_index)
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return screen


class Renderer(Protocol):
    """Protocol for rendering backends. Always fullscreen."""

    # ── Lifecycle ──────────────────────────────────────────────

    def init(self, screen_index: int = 0) -> None:
        """Initialize renderer on specified display. Always fullscreen."""
        ...

    def get_size(self) -> Tuple[int, int]:
        """Get screen dimensions (width, height)."""
        ...

    def clear(self, color: Tuple[int, int, int]) -> None:
        """Clear screen with specified color."""
        ...

    def flip(self) -> None:
        """Update display."""
        ...

    def tick(self, fps: int) -> float:
        """Tick clock and return time since last tick in seconds."""
        ...

    def get_events(self) -> List:
        """Get input events."""
        ...

    def quit(self) -> None:
        """Cleanup and quit renderer."""
        ...

    # ── Shape primitives (alpha=255 default -> opaque) ─────────

    def draw_circle(self, center: Tuple[int, int], radius: int,
                    color: Tuple[int, int, int], alpha: int = 255,
                    border: int = 0) -> None:
        """Draw a circle. border=0 means filled. alpha < 255 for transparency."""
        ...

    def draw_polygon(self, points: List[Tuple[int, int]],
                     color: Tuple[int, int, int], alpha: int = 255,
                     border: int = 0) -> None:
        """Draw a polygon. border=0 means filled. alpha < 255 for transparency."""
        ...

    def draw_line(self, start: Tuple[int, int], end: Tuple[int, int],
                  color: Tuple[int, int, int], alpha: int = 255,
                  width: int = 1) -> None:
        """Draw a line. alpha < 255 for transparency."""
        ...

    def draw_lines(self, points: List[Tuple[int, int]],
                   color: Tuple[int, int, int], alpha: int = 255,
                   width: int = 1, closed: bool = False) -> None:
        """Draw connected line segments. alpha < 255 for transparency."""
        ...

    # ── Batch primitives ───────────────────────────────────────

    def draw_line_batch(self, lines: List[Tuple[Tuple[int, int], Tuple[int, int],
                                                Tuple[int, ...], int]]) -> None:
        """Draw many lines in a single blit. Each line is (start, end, color_rgba, width)."""
        ...

    def draw_circles_batch(self, circles: List[Tuple[Tuple[int, int], int]],
                           color: Tuple[int, int, int], alpha: int = 255,
                           border: int = 0) -> None:
        """Draw multiple circles with same color in a single batch.

        Args:
            circles: List of (center, radius) tuples
            color: RGB color
            alpha: Transparency (0-255)
            border: Border width (0 = filled)
        """
        ...

    def draw_lines_batch(self,
                         lines: List[Tuple[Tuple[int, int], Tuple[int, int]]],
                         color: Tuple[int, int, int], alpha: int = 255,
                         width: int = 1) -> None:
        """Draw multiple independent line segments with same color in a single batch.

        Args:
            lines: List of (start, end) tuples
            color: RGB color
            alpha: Transparency (0-255)
            width: Line width
        """
        ...

    # ── Text / Image ──────────────────────────────────────────

    def draw_text(self, text: str, position: Tuple[int, int],
                  color: Tuple[int, int, int], font_size: int = 24,
                  background: Optional[Tuple[int, int, int]] = None,
                  angle: float = 0.0) -> None:
        """Draw text at position. angle in degrees, counter-clockwise."""
        ...

    def create_image(self, rgba_bytes: bytes, width: int, height: int) -> Any:
        """Create a renderer-specific image handle from RGBA pixel data."""
        ...

    def draw_image(self, handle: Any, position: Tuple[int, int],
                   size: Tuple[int, int]) -> None:
        """Draw a previously created image at position with given size."""
        ...
