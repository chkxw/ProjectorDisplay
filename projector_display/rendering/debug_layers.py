"""
Debug utility layers for projector display.

Two togglable overlay layers for on-demand debugging:
1. GridLayer: Shows coordinate grid over display area
2. FieldLayer: Shows boundaries of all registered fields with labels
"""

import math
from typing import Callable, Dict, Tuple, List
from projector_display.rendering.renderer import PygameRenderer
from projector_display.core.field_calibrator import FieldCalibrator, Field


# Grid colors (matching reference implementation)
GRID_MAJOR_COLOR = (100, 100, 100)
GRID_MINOR_COLOR = (50, 50, 50)
LABEL_COLOR = (200, 200, 200)


class GridLayer:
    """
    Grid overlay showing world coordinate system.

    Shows:
    - Thick lines every 1 meter
    - Thin lines every 0.1 meter
    - Coordinate labels at each 1m intersection
    - Origin marker
    """

    def __init__(self,
                 major_color: Tuple[int, int, int] = GRID_MAJOR_COLOR,
                 minor_color: Tuple[int, int, int] = GRID_MINOR_COLOR,
                 label_color: Tuple[int, int, int] = LABEL_COLOR,
                 show_minor: bool = True):
        """
        Initialize grid layer.

        Args:
            major_color: Color for major grid lines (1m)
            minor_color: Color for minor grid lines (0.1m)
            label_color: Color for coordinate labels
            show_minor: Whether to show minor grid lines
        """
        self.major_color = major_color
        self.minor_color = minor_color
        self.label_color = label_color
        self.show_minor = show_minor

    def draw(self, renderer: PygameRenderer,
             world_to_screen: Callable[[float, float], Tuple[int, int]],
             world_bounds: Tuple[float, float, float, float]) -> None:
        """
        Draw grid overlay.

        Args:
            renderer: Renderer instance
            world_to_screen: Function to convert world coords to screen coords
            world_bounds: (min_x, min_y, max_x, max_y) in world coordinates
        """
        min_x, min_y, max_x, max_y = world_bounds

        # Extend to nearest meter for clean grid
        grid_min_x = math.floor(min_x)
        grid_max_x = math.ceil(max_x)
        grid_min_y = math.floor(min_y)
        grid_max_y = math.ceil(max_y)

        # Draw minor grid lines (0.1m spacing)
        if self.show_minor:
            self._draw_minor_grid(renderer, world_to_screen,
                                  grid_min_x, grid_max_x, grid_min_y, grid_max_y)

        # Draw major grid lines (1.0m spacing)
        self._draw_major_grid(renderer, world_to_screen,
                              grid_min_x, grid_max_x, grid_min_y, grid_max_y)

        # Draw coordinate labels at each 1m intersection
        self._draw_labels(renderer, world_to_screen,
                          grid_min_x, grid_max_x, grid_min_y, grid_max_y)

        # Draw origin marker if visible
        self._draw_origin_marker(renderer, world_to_screen)

    def _draw_minor_grid(self, renderer: PygameRenderer,
                         world_to_screen: Callable,
                         grid_min_x: int, grid_max_x: int,
                         grid_min_y: int, grid_max_y: int) -> None:
        """Draw minor grid lines at 0.1m spacing."""
        # Vertical lines (0.1m spacing, skip major lines)
        for x_10 in range(grid_min_x * 10, grid_max_x * 10 + 1):
            if x_10 % 10 == 0:  # Skip major lines
                continue
            x = x_10 / 10.0
            p1 = world_to_screen(x, grid_min_y)
            p2 = world_to_screen(x, grid_max_y)
            renderer.draw_line(p1, p2, self.minor_color, 1)

        # Horizontal lines (0.1m spacing, skip major lines)
        for y_10 in range(grid_min_y * 10, grid_max_y * 10 + 1):
            if y_10 % 10 == 0:  # Skip major lines
                continue
            y = y_10 / 10.0
            p1 = world_to_screen(grid_min_x, y)
            p2 = world_to_screen(grid_max_x, y)
            renderer.draw_line(p1, p2, self.minor_color, 1)

    def _draw_major_grid(self, renderer: PygameRenderer,
                         world_to_screen: Callable,
                         grid_min_x: int, grid_max_x: int,
                         grid_min_y: int, grid_max_y: int) -> None:
        """Draw major grid lines at 1.0m spacing."""
        # Vertical lines (1m spacing)
        for x in range(grid_min_x, grid_max_x + 1):
            p1 = world_to_screen(x, grid_min_y)
            p2 = world_to_screen(x, grid_max_y)
            renderer.draw_line(p1, p2, self.major_color, 2)

        # Horizontal lines (1m spacing)
        for y in range(grid_min_y, grid_max_y + 1):
            p1 = world_to_screen(grid_min_x, y)
            p2 = world_to_screen(grid_max_x, y)
            renderer.draw_line(p1, p2, self.major_color, 2)

    def _draw_labels(self, renderer: PygameRenderer,
                     world_to_screen: Callable,
                     grid_min_x: int, grid_max_x: int,
                     grid_min_y: int, grid_max_y: int) -> None:
        """Draw coordinate labels at each 1m intersection."""
        screen_w, screen_h = renderer.get_size()

        for x in range(grid_min_x, grid_max_x + 1):
            for y in range(grid_min_y, grid_max_y + 1):
                pos = world_to_screen(x, y)
                # Only draw if on screen
                if 0 <= pos[0] < screen_w and 0 <= pos[1] < screen_h:
                    label = f"({x},{y})"
                    # Offset label slightly from intersection
                    renderer.draw_text(label, (pos[0] + 25, pos[1] - 10),
                                        self.label_color, 18)

    def _draw_origin_marker(self, renderer: PygameRenderer,
                            world_to_screen: Callable) -> None:
        """Draw origin marker if visible."""
        screen_w, screen_h = renderer.get_size()
        origin_screen = world_to_screen(0, 0)

        if 0 <= origin_screen[0] < screen_w and 0 <= origin_screen[1] < screen_h:
            # Draw crosshair at origin
            renderer.draw_circle(origin_screen, 10, (255, 255, 0), 2)
            renderer.draw_line((origin_screen[0] - 15, origin_screen[1]),
                               (origin_screen[0] + 15, origin_screen[1]),
                               (255, 255, 0), 2)
            renderer.draw_line((origin_screen[0], origin_screen[1] - 15),
                               (origin_screen[0], origin_screen[1] + 15),
                               (255, 255, 0), 2)


class FieldLayer:
    """
    Field boundaries overlay showing all registered coordinate fields.

    Shows:
    - Boundary polygon for each field
    - Field name label
    - Corner markers
    """

    def __init__(self,
                 boundary_color: Tuple[int, int, int] = (255, 200, 0),
                 label_color: Tuple[int, int, int] = (255, 255, 255),
                 corner_color: Tuple[int, int, int] = (255, 100, 100)):
        """
        Initialize field layer.

        Args:
            boundary_color: Color for field boundaries
            label_color: Color for field name labels
            corner_color: Color for corner markers
        """
        self.boundary_color = boundary_color
        self.label_color = label_color
        self.corner_color = corner_color

    def draw(self, renderer: PygameRenderer,
             field_calibrator: FieldCalibrator,
             world_to_screen: Callable[[float, float], Tuple[int, int]]) -> None:
        """
        Draw field boundaries overlay.

        Args:
            renderer: Renderer instance
            field_calibrator: FieldCalibrator with registered fields
            world_to_screen: Function to convert world coords to screen coords
        """
        for name, field in field_calibrator.fields.items():
            self._draw_field(renderer, name, field, world_to_screen)

    def _draw_field(self, renderer: PygameRenderer,
                    name: str,
                    field: Field,
                    world_to_screen: Callable) -> None:
        """Draw a single field boundary."""
        # Convert world points to screen coordinates
        screen_points = []
        for point in field.world_points:
            screen_pt = world_to_screen(point[0], point[1])
            screen_points.append(screen_pt)

        if len(screen_points) < 3:
            return

        # Draw boundary polygon (closed)
        screen_points_closed = screen_points + [screen_points[0]]
        for i in range(len(screen_points)):
            renderer.draw_line(screen_points_closed[i], screen_points_closed[i + 1],
                               self.boundary_color, 2)

        # Draw corner markers
        corner_labels = ["BL", "BR", "TR", "TL"]
        for i, (point, label) in enumerate(zip(screen_points, corner_labels)):
            renderer.draw_circle(point, 5, self.corner_color)
            renderer.draw_text(label, (point[0] + 10, point[1] - 10),
                               self.corner_color, 16)

        # Calculate center for field name label
        center_x = sum(p[0] for p in screen_points) // len(screen_points)
        center_y = sum(p[1] for p in screen_points) // len(screen_points)

        # Draw field name
        renderer.draw_text(name, (center_x, center_y),
                           self.label_color, 24, (0, 0, 0))
