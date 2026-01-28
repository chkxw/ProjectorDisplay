"""
Debug utility layers for projector display.

Two togglable overlay layers for on-demand debugging:
1. GridLayer: Shows coordinate grid over display area
2. FieldLayer: Shows boundaries of all registered fields with labels
"""

from typing import Callable, Dict, Tuple, List
from projector_display.rendering.renderer import PygameRenderer
from projector_display.core.field_calibrator import FieldCalibrator, Field


class GridLayer:
    """
    Grid overlay showing world coordinate system.

    Shows:
    - Thick lines every 1 meter
    - Thin lines every 0.1 meter (optional)
    - Origin marker and axis labels
    """

    def __init__(self,
                 major_spacing: float = 1.0,  # meters
                 minor_spacing: float = 0.1,  # meters
                 major_color: Tuple[int, int, int] = (100, 100, 100),
                 minor_color: Tuple[int, int, int] = (50, 50, 50),
                 label_color: Tuple[int, int, int] = (200, 200, 200),
                 show_minor: bool = False):
        """
        Initialize grid layer.

        Args:
            major_spacing: Spacing between major grid lines (meters)
            minor_spacing: Spacing between minor grid lines (meters)
            major_color: Color for major grid lines
            minor_color: Color for minor grid lines
            label_color: Color for axis labels
            show_minor: Whether to show minor grid lines
        """
        self.major_spacing = major_spacing
        self.minor_spacing = minor_spacing
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
        screen_w, screen_h = renderer.get_size()

        # Draw minor grid lines if enabled
        if self.show_minor:
            self._draw_grid_lines(renderer, world_to_screen, world_bounds,
                                  self.minor_spacing, self.minor_color, 1)

        # Draw major grid lines
        self._draw_grid_lines(renderer, world_to_screen, world_bounds,
                              self.major_spacing, self.major_color, 2)

        # Draw origin marker
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
            renderer.draw_text("(0,0)", (origin_screen[0] + 20, origin_screen[1] - 20),
                               self.label_color, 20)

    def _draw_grid_lines(self, renderer: PygameRenderer,
                         world_to_screen: Callable,
                         world_bounds: Tuple[float, float, float, float],
                         spacing: float,
                         color: Tuple[int, int, int],
                         thickness: int) -> None:
        """Draw grid lines at specified spacing."""
        min_x, min_y, max_x, max_y = world_bounds
        screen_w, screen_h = renderer.get_size()

        # Vertical lines (constant x)
        x = (min_x // spacing) * spacing
        while x <= max_x:
            p1 = world_to_screen(x, min_y)
            p2 = world_to_screen(x, max_y)

            # Clip to screen bounds
            if 0 <= p1[0] < screen_w or 0 <= p2[0] < screen_w:
                renderer.draw_line(p1, p2, color, thickness)

                # Label major lines
                if thickness > 1 and abs(x) > 0.01:
                    label_pos = world_to_screen(x, min_y)
                    if 0 <= label_pos[0] < screen_w and 0 <= label_pos[1] < screen_h:
                        renderer.draw_text(f"{x:.1f}", (label_pos[0], label_pos[1] - 15),
                                           self.label_color, 16)

            x += spacing

        # Horizontal lines (constant y)
        y = (min_y // spacing) * spacing
        while y <= max_y:
            p1 = world_to_screen(min_x, y)
            p2 = world_to_screen(max_x, y)

            if 0 <= p1[1] < screen_h or 0 <= p2[1] < screen_h:
                renderer.draw_line(p1, p2, color, thickness)

                # Label major lines
                if thickness > 1 and abs(y) > 0.01:
                    label_pos = world_to_screen(min_x, y)
                    if 0 <= label_pos[0] < screen_w and 0 <= label_pos[1] < screen_h:
                        renderer.draw_text(f"{y:.1f}", (label_pos[0] + 15, label_pos[1]),
                                           self.label_color, 16)

            y += spacing


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
