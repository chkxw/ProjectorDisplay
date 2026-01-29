"""
Renderer protocol and pygame implementation.

Isolates rendering behind Renderer interface for future flexibility
(e.g., GPU-accelerated rendering).
"""

import os
import logging
from typing import Protocol, Tuple, List, Optional
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

    def init(self, screen_index: int = 0) -> None:
        """Initialize renderer on specified display. Always fullscreen."""
        ...

    def get_size(self) -> Tuple[int, int]:
        """Get screen dimensions (width, height)."""
        ...

    def clear(self, color: Tuple[int, int, int]) -> None:
        """Clear screen with specified color."""
        ...

    def draw_circle(self, center: Tuple[int, int], radius: int,
                    color: Tuple[int, int, int], border: int = 0) -> None:
        """Draw a circle. border=0 means filled."""
        ...

    def draw_polygon(self, points: List[Tuple[int, int]],
                     color: Tuple[int, int, int], border: int = 0) -> None:
        """Draw a polygon. border=0 means filled."""
        ...

    def draw_line(self, start: Tuple[int, int], end: Tuple[int, int],
                  color: Tuple[int, int, int], width: int = 1) -> None:
        """Draw a line."""
        ...

    def draw_lines(self, points: List[Tuple[int, int]],
                   color: Tuple[int, int, int], width: int = 1,
                   closed: bool = False) -> None:
        """Draw connected line segments."""
        ...

    def draw_rect(self, rect: Tuple[int, int, int, int],
                  color: Tuple[int, int, int], border: int = 0) -> None:
        """Draw a rectangle. rect=(x, y, width, height). border=0 means filled."""
        ...

    def draw_line_batch(self, lines: List[Tuple[Tuple[int, int], Tuple[int, int],
                                                Tuple[int, ...], int]]) -> None:
        """Draw many lines in a single blit. Each line is (start, end, color_rgba, width)."""
        ...

    def draw_text(self, text: str, position: Tuple[int, int],
                  color: Tuple[int, int, int], font_size: int = 24,
                  background: Optional[Tuple[int, int, int]] = None,
                  angle: float = 0.0) -> None:
        """Draw text at position. angle in degrees, counter-clockwise."""
        ...

    def flip(self) -> None:
        """Update display."""
        ...

    def quit(self) -> None:
        """Cleanup and quit renderer."""
        ...


class PygameRenderer:
    """Default renderer using pygame. Always fullscreen."""

    def __init__(self):
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.width: int = 0
        self.height: int = 0
        self._fonts: dict = {}  # Cache for fonts

    def init(self, screen_index: int = 0) -> None:
        """
        Initialize pygame display. Always fullscreen.

        Args:
            screen_index: Which display to use for multi-monitor setups
        """
        os.environ.setdefault("DISPLAY", ":0")

        pygame.init()

        # Detect SDL version and use appropriate approach
        sdl_version = _get_sdl_version()
        logger.info(f"SDL version {sdl_version[0]}.{sdl_version[1]}.{sdl_version[2]} detected")

        if sdl_version[0] >= 2:
            # SDL2: use display parameter
            logger.info(f"Using SDL2 multi-display (screen_index={screen_index})")
            self.screen = _init_display_sdl2(screen_index)
        else:
            # SDL1.2: use environment variable
            logger.info(f"Using SDL1.2 env var (screen_index={screen_index})")
            self.screen = _init_display_sdl1(screen_index)

        pygame.display.set_caption("Projector Display Server")
        pygame.mouse.set_visible(False)

        self.clock = pygame.time.Clock()
        self.width, self.height = pygame.display.get_surface().get_size()
        logger.info(f"Display initialized: {self.width}x{self.height}")

    def get_size(self) -> Tuple[int, int]:
        """Get screen dimensions."""
        return (self.width, self.height)

    def clear(self, color: Tuple[int, int, int]) -> None:
        """Clear screen with specified color."""
        if self.screen:
            self.screen.fill(color)

    def draw_circle(self, center: Tuple[int, int], radius: int,
                    color: Tuple[int, int, int], border: int = 0) -> None:
        """Draw a circle."""
        if self.screen:
            pygame.draw.circle(self.screen, color, center, radius, border)

    def draw_polygon(self, points: List[Tuple[int, int]],
                     color: Tuple[int, int, int], border: int = 0) -> None:
        """Draw a polygon."""
        if self.screen and len(points) >= 3:
            pygame.draw.polygon(self.screen, color, points, border)

    def draw_line(self, start: Tuple[int, int], end: Tuple[int, int],
                  color: Tuple[int, int, int], width: int = 1) -> None:
        """Draw a line."""
        if self.screen:
            pygame.draw.line(self.screen, color, start, end, width)

    def draw_lines(self, points: List[Tuple[int, int]],
                   color: Tuple[int, int, int], width: int = 1,
                   closed: bool = False) -> None:
        """Draw connected line segments."""
        if self.screen and len(points) >= 2:
            pygame.draw.lines(self.screen, color, closed, points, width)

    def draw_rect(self, rect: Tuple[int, int, int, int],
                  color: Tuple[int, int, int], border: int = 0) -> None:
        """Draw a rectangle."""
        if self.screen:
            pygame.draw.rect(self.screen, color, pygame.Rect(*rect), border)

    def draw_text(self, text: str, position: Tuple[int, int],
                  color: Tuple[int, int, int], font_size: int = 24,
                  background: Optional[Tuple[int, int, int]] = None,
                  angle: float = 0.0) -> None:
        """Draw text at position. angle in degrees, counter-clockwise."""
        if not self.screen:
            return

        # Get or create cached font
        if font_size not in self._fonts:
            self._fonts[font_size] = pygame.font.Font(None, font_size)

        font = self._fonts[font_size]
        text_surface = font.render(text, True, color)

        if background:
            # Create background surface with padding
            bg_rect = text_surface.get_rect().inflate(4, 2)
            bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            bg_surface.fill((*background, 255))
            bg_surface.blit(text_surface, (2, 1))
            text_surface = bg_surface

        if angle != 0.0:
            text_surface = pygame.transform.rotate(text_surface, angle)

        text_rect = text_surface.get_rect(center=position)
        self.screen.blit(text_surface, text_rect)

    def draw_polygon_alpha(self, points: List[Tuple[int, int]],
                           color: Tuple[int, int, int], alpha: int,
                           border: int = 0) -> None:
        """Draw a polygon with transparency."""
        if not self.screen or len(points) < 3:
            return

        # Calculate bounding box
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        width = max_x - min_x + 4
        height = max_y - min_y + 4

        # Create transparent surface
        temp_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        local_points = [(p[0] - min_x + 2, p[1] - min_y + 2) for p in points]

        fill_color = (*color[:3], alpha)
        pygame.draw.polygon(temp_surface, fill_color, local_points, border)

        self.screen.blit(temp_surface, (min_x - 2, min_y - 2))

    def draw_line_alpha(self, start: Tuple[int, int], end: Tuple[int, int],
                        color: Tuple[int, int, int], alpha: int,
                        width: int = 1) -> None:
        """Draw a line with transparency (ADR-8: RGBA support for trajectory gradients)."""
        if not self.screen or alpha == 0:
            return

        if alpha >= 255:
            # No transparency needed
            pygame.draw.line(self.screen, color[:3], start, end, width)
            return

        # Calculate bounding box with padding for line width
        min_x = min(start[0], end[0]) - width
        max_x = max(start[0], end[0]) + width
        min_y = min(start[1], end[1]) - width
        max_y = max(start[1], end[1]) + width
        surf_width = max(1, max_x - min_x + 2)
        surf_height = max(1, max_y - min_y + 2)

        # Create transparent surface
        temp_surface = pygame.Surface((surf_width, surf_height), pygame.SRCALPHA)
        local_start = (start[0] - min_x + 1, start[1] - min_y + 1)
        local_end = (end[0] - min_x + 1, end[1] - min_y + 1)

        line_color = (*color[:3], alpha)
        pygame.draw.line(temp_surface, line_color, local_start, local_end, width)

        self.screen.blit(temp_surface, (min_x - 1, min_y - 1))

    def draw_line_batch(self, lines: List[Tuple[Tuple[int, int], Tuple[int, int],
                                                Tuple[int, ...], int]]) -> None:
        """
        Draw many lines in a single blit. Supports RGBA colors.

        Each line is (start, end, color, width) where color is RGB or RGBA.
        When any color has alpha < 255, all lines are drawn onto one temporary
        SRCALPHA surface and blitted once. Fully opaque batches use direct draws.

        Args:
            lines: List of (start, end, color, width) tuples
        """
        if not self.screen or not lines:
            return

        # Check if any line needs alpha
        needs_alpha = any(len(c) >= 4 and c[3] < 255 for _, _, c, _ in lines)

        if not needs_alpha:
            for start, end, color, width in lines:
                pygame.draw.line(self.screen, color[:3], start, end, width)
            return

        # Compute bounding box of all lines
        all_x = []
        all_y = []
        max_width = 0
        for start, end, _, width in lines:
            all_x.extend([start[0], end[0]])
            all_y.extend([start[1], end[1]])
            max_width = max(max_width, width)

        min_x = min(all_x) - max_width
        max_x = max(all_x) + max_width
        min_y = min(all_y) - max_width
        max_y = max(all_y) + max_width
        surf_w = max(1, max_x - min_x + 2)
        surf_h = max(1, max_y - min_y + 2)

        temp_surface = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)

        for start, end, color, width in lines:
            rgba = (*color[:3], color[3] if len(color) >= 4 else 255)
            local_start = (start[0] - min_x + 1, start[1] - min_y + 1)
            local_end = (end[0] - min_x + 1, end[1] - min_y + 1)
            pygame.draw.line(temp_surface, rgba, local_start, local_end, width)

        self.screen.blit(temp_surface, (min_x - 1, min_y - 1))

    def draw_circle_alpha(self, center: Tuple[int, int], radius: int,
                          color: Tuple[int, int, int], alpha: int,
                          border: int = 0) -> None:
        """Draw a circle with transparency."""
        if not self.screen or alpha == 0:
            return

        if alpha >= 255:
            pygame.draw.circle(self.screen, color[:3], center, radius, border)
            return

        # Create surface for the circle
        size = radius * 2 + 4
        temp_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        local_center = (radius + 2, radius + 2)

        circle_color = (*color[:3], alpha)
        pygame.draw.circle(temp_surface, circle_color, local_center, radius, border)

        self.screen.blit(temp_surface, (center[0] - radius - 2, center[1] - radius - 2))

    def blit_surface(self, surface: pygame.Surface,
                     position: Tuple[int, int]) -> None:
        """
        Blit a pre-rendered surface to the screen.

        Used for background images and other pre-computed graphics.

        Args:
            surface: Pygame surface to blit
            position: (x, y) position to blit at
        """
        if self.screen:
            self.screen.blit(surface, position)

    def flip(self) -> None:
        """Update display."""
        pygame.display.flip()

    def tick(self, fps: int) -> float:
        """Tick clock and return time since last tick."""
        if self.clock:
            return self.clock.tick(fps) / 1000.0
        return 0.0

    def get_events(self) -> List:
        """Get pygame events (for input handling)."""
        return pygame.event.get()

    def quit(self) -> None:
        """Cleanup and quit pygame."""
        pygame.quit()
