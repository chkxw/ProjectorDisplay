"""
Renderer protocol and pygame implementation.

Isolates rendering behind Renderer interface for future flexibility
(e.g., GPU-accelerated rendering).
"""

import os
from typing import Protocol, Tuple, List, Optional
import pygame


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

    def draw_text(self, text: str, position: Tuple[int, int],
                  color: Tuple[int, int, int], font_size: int = 24,
                  background: Optional[Tuple[int, int, int]] = None) -> None:
        """Draw text at position."""
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
        # Set environment variables for display selection
        os.environ.setdefault("DISPLAY", ":0")
        os.environ["SDL_VIDEODRIVER"] = os.getenv("SDL_VIDEO_DRIVER", "x11")
        os.environ["SDL_VIDEO_FULLSCREEN_DISPLAY"] = str(screen_index)
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "0,0")

        pygame.init()

        # Create fullscreen window
        flags = pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((0, 0), flags)
        pygame.display.set_caption("Projector Display Server")
        pygame.mouse.set_visible(False)

        self.clock = pygame.time.Clock()
        self.width, self.height = pygame.display.get_surface().get_size()

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
                  background: Optional[Tuple[int, int, int]] = None) -> None:
        """Draw text at position."""
        if not self.screen:
            return

        # Get or create cached font
        if font_size not in self._fonts:
            self._fonts[font_size] = pygame.font.Font(None, font_size)

        font = self._fonts[font_size]
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=position)

        # Draw background if specified
        if background:
            pygame.draw.rect(self.screen, background, text_rect.inflate(4, 2))

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
