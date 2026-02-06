"""
Pygame software renderer implementation.
"""

import os
import logging
from typing import Any, Tuple, List, Optional

import pygame

from projector_display.rendering.renderer.base import (
    _get_sdl_version, _init_display_sdl2, _init_display_sdl1,
)

logger = logging.getLogger(__name__)


class PygameRenderer:
    """Default renderer using pygame. Always fullscreen."""

    def __init__(self):
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.width: int = 0
        self.height: int = 0
        self._fonts: dict = {}  # Cache for fonts

    # ── Lifecycle ──────────────────────────────────────────────

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

    # ── Shape primitives ───────────────────────────────────────

    def draw_circle(self, center: Tuple[int, int], radius: int,
                    color: Tuple[int, int, int], alpha: int = 255,
                    border: int = 0) -> None:
        """Draw a circle. alpha < 255 uses a temp surface for transparency."""
        if not self.screen or alpha == 0:
            return

        if alpha >= 255:
            pygame.draw.circle(self.screen, color, center, radius, border)
            return

        # Create surface for the circle
        size = radius * 2 + 4
        temp_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        local_center = (radius + 2, radius + 2)

        circle_color = (*color[:3], alpha)
        pygame.draw.circle(temp_surface, circle_color, local_center, radius, border)

        self.screen.blit(temp_surface, (center[0] - radius - 2, center[1] - radius - 2))

    def draw_polygon(self, points: List[Tuple[int, int]],
                     color: Tuple[int, int, int], alpha: int = 255,
                     border: int = 0) -> None:
        """Draw a polygon. alpha < 255 uses a temp surface for transparency."""
        if not self.screen or len(points) < 3 or alpha == 0:
            return

        if alpha >= 255:
            pygame.draw.polygon(self.screen, color, points, border)
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

    def draw_line(self, start: Tuple[int, int], end: Tuple[int, int],
                  color: Tuple[int, int, int], alpha: int = 255,
                  width: int = 1) -> None:
        """Draw a line. alpha < 255 uses a temp surface for transparency."""
        if not self.screen or alpha == 0:
            return

        if alpha >= 255:
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

    def draw_lines(self, points: List[Tuple[int, int]],
                   color: Tuple[int, int, int], alpha: int = 255,
                   width: int = 1, closed: bool = False) -> None:
        """Draw connected line segments. alpha < 255 uses a temp surface."""
        if not self.screen or len(points) < 2 or alpha == 0:
            return

        if alpha >= 255:
            pygame.draw.lines(self.screen, color[:3], closed, points, width)
            return

        # Calculate bounding box with padding for line width
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x = min(xs) - width
        max_x = max(xs) + width
        min_y = min(ys) - width
        max_y = max(ys) + width
        surf_width = max(1, max_x - min_x + 2)
        surf_height = max(1, max_y - min_y + 2)

        temp_surface = pygame.Surface((surf_width, surf_height), pygame.SRCALPHA)
        local_points = [(p[0] - min_x + 1, p[1] - min_y + 1) for p in points]

        line_color = (*color[:3], alpha)
        pygame.draw.lines(temp_surface, line_color, closed, local_points, width)

        self.screen.blit(temp_surface, (min_x - 1, min_y - 1))

    # ── Batch primitives ───────────────────────────────────────

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

    def draw_circles_batch(self, circles: List[Tuple[Tuple[int, int], int]],
                           color: Tuple[int, int, int], alpha: int = 255,
                           border: int = 0) -> None:
        """Draw multiple circles with same color. Fallback: loop over individual draws."""
        if not self.screen or not circles:
            return
        for center, radius in circles:
            self.draw_circle(center, radius, color, alpha, border)

    def draw_lines_batch(self,
                         lines: List[Tuple[Tuple[int, int], Tuple[int, int]]],
                         color: Tuple[int, int, int], alpha: int = 255,
                         width: int = 1) -> None:
        """Draw multiple independent line segments with same color. Fallback: loop."""
        if not self.screen or not lines:
            return
        for start, end in lines:
            self.draw_line(start, end, color, alpha, width)

    # ── Text / Image ──────────────────────────────────────────

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

    def create_image(self, rgba_bytes: bytes, width: int, height: int) -> pygame.Surface:
        """Create a pygame Surface from RGBA pixel data."""
        return pygame.image.frombuffer(rgba_bytes, (width, height), 'RGBA')

    def draw_image(self, handle: pygame.Surface, position: Tuple[int, int],
                   size: Tuple[int, int] = None) -> None:
        """Draw a previously created image (pygame Surface) at position."""
        if self.screen:
            self.screen.blit(handle, position)

    def blit_surface(self, surface: pygame.Surface,
                     position: Tuple[int, int]) -> None:
        """
        Blit a pre-rendered surface to the screen.

        Used for background images and other pre-computed graphics.
        Delegates to draw_image for backwards compatibility.

        Args:
            surface: Pygame surface to blit
            position: (x, y) position to blit at
        """
        self.draw_image(surface, position)
