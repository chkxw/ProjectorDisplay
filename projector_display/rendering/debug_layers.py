"""
Debug utility layers for projector display.

Two togglable overlay layers for on-demand debugging:
1. GridLayer: Shows coordinate grid over display area
2. FieldLayer: Shows boundaries of all registered fields with labels
"""

import math
from typing import Callable, Dict, Tuple, List
from projector_display.rendering.renderer import Renderer
from projector_display.core.field_calibrator import Field


# Grid colors (RGBA, matching reference implementation)
GRID_MAJOR_COLOR = (100, 100, 100, 255)
GRID_MINOR_COLOR = (50, 50, 50, 255)


class GridLayer:
    """
    Grid overlay showing world coordinate system.

    Shows:
    - Thick lines every 1 meter
    - Thin lines every 0.1 meter
    - Coordinate labels at each 1m intersection (same color as major lines)
    - Origin marker
    """

    def __init__(self,
                 major_color: Tuple[int, ...] = GRID_MAJOR_COLOR,
                 minor_color: Tuple[int, ...] = GRID_MINOR_COLOR,
                 show_minor: bool = True):
        """
        Initialize grid layer.

        Args:
            major_color: RGBA color for major grid lines and labels (1m)
            minor_color: RGBA color for minor grid lines (0.1m)
            show_minor: Whether to show minor grid lines
        """
        self.major_color = major_color
        self.minor_color = minor_color
        self.show_minor = show_minor

    def draw(self, renderer: Renderer,
             world_to_screen: Callable[[float, float], Tuple[int, int]],
             world_bounds: Tuple[float, float, float, float]) -> None:
        """
        Draw grid overlay.

        Collects all grid lines into a batch and renders in a single blit
        for efficient alpha support.

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

        # Collect all grid lines into a batch: (start, end, color_rgba, width)
        lines = []

        if self.show_minor:
            self._collect_minor_lines(lines, world_to_screen,
                                      grid_min_x, grid_max_x, grid_min_y, grid_max_y)

        self._collect_major_lines(lines, world_to_screen,
                                  grid_min_x, grid_max_x, grid_min_y, grid_max_y)

        # Draw all grid lines in a single blit
        if lines:
            renderer.draw_line_batch(lines)

        # Draw coordinate labels at each 1m intersection
        self._draw_labels(renderer, world_to_screen,
                          grid_min_x, grid_max_x, grid_min_y, grid_max_y)

        # Draw origin marker if visible
        self._draw_origin_marker(renderer, world_to_screen)

    def _collect_minor_lines(self, lines: List,
                             world_to_screen: Callable,
                             grid_min_x: int, grid_max_x: int,
                             grid_min_y: int, grid_max_y: int) -> None:
        """Collect minor grid lines at 0.1m spacing into batch."""
        color = self.minor_color
        # Vertical lines (0.1m spacing, skip major lines)
        for x_10 in range(grid_min_x * 10, grid_max_x * 10 + 1):
            if x_10 % 10 == 0:
                continue
            x = x_10 / 10.0
            p1 = world_to_screen(x, grid_min_y)
            p2 = world_to_screen(x, grid_max_y)
            lines.append((p1, p2, color, 1))

        # Horizontal lines (0.1m spacing, skip major lines)
        for y_10 in range(grid_min_y * 10, grid_max_y * 10 + 1):
            if y_10 % 10 == 0:
                continue
            y = y_10 / 10.0
            p1 = world_to_screen(grid_min_x, y)
            p2 = world_to_screen(grid_max_x, y)
            lines.append((p1, p2, color, 1))

    def _collect_major_lines(self, lines: List,
                             world_to_screen: Callable,
                             grid_min_x: int, grid_max_x: int,
                             grid_min_y: int, grid_max_y: int) -> None:
        """Collect major grid lines at 1.0m spacing into batch."""
        color = self.major_color
        # Vertical lines (1m spacing)
        for x in range(grid_min_x, grid_max_x + 1):
            p1 = world_to_screen(x, grid_min_y)
            p2 = world_to_screen(x, grid_max_y)
            lines.append((p1, p2, color, 2))

        # Horizontal lines (1m spacing)
        for y in range(grid_min_y, grid_max_y + 1):
            p1 = world_to_screen(grid_min_x, y)
            p2 = world_to_screen(grid_max_x, y)
            lines.append((p1, p2, color, 2))

    def _draw_labels(self, renderer: Renderer,
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
                                        self.major_color[:3], 18)

    def _draw_origin_marker(self, renderer: Renderer,
                            world_to_screen: Callable) -> None:
        """Draw origin marker if visible."""
        screen_w, screen_h = renderer.get_size()
        origin_screen = world_to_screen(0, 0)

        if 0 <= origin_screen[0] < screen_w and 0 <= origin_screen[1] < screen_h:
            # Draw crosshair at origin
            renderer.draw_circle(origin_screen, 10, (255, 255, 0), border=2)
            renderer.draw_line((origin_screen[0] - 15, origin_screen[1]),
                               (origin_screen[0] + 15, origin_screen[1]),
                               (255, 255, 0), width=2)
            renderer.draw_line((origin_screen[0], origin_screen[1] - 15),
                               (origin_screen[0], origin_screen[1] + 15),
                               (255, 255, 0), width=2)


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

    def draw(self, renderer: Renderer,
             fields: Dict[str, Field],
             world_to_screen: Callable[[float, float], Tuple[int, int]]) -> None:
        """
        Draw field boundaries overlay.

        Args:
            renderer: Renderer instance
            fields: Dictionary of field_name -> Field (use scene.get_fields_snapshot())
            world_to_screen: Function to convert world coords to screen coords
        """
        for name, field in fields.items():
            self._draw_field(renderer, name, field, world_to_screen)

    def _draw_field(self, renderer: Renderer,
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
                               self.boundary_color, width=2)

        # Draw corner markers
        corner_labels = ["BL", "BR", "TR", "TL"]
        for i, (point, label) in enumerate(zip(screen_points, corner_labels)):
            renderer.draw_circle(point, 5, self.corner_color)
            renderer.draw_text(label, (point[0] + 10, point[1] - 10),
                               self.corner_color, 16)

        # Draw field name at top-left corner, oriented along top edge
        #
        # Two axis directions derived from field corners:
        #   h_dir: TL -> TR (horizontal = along top edge)
        #   v_dir: TL -> BL (vertical = along left edge, into field)
        #
        # draw_text anchors at center, so we compute the text's
        # top-left position then shift by half-dimensions to get center.
        font_size = 24
        margin = font_size * 0.5
        tl = screen_points[3]  # TL (index 3 in BL,BR,TR,TL order)
        tr = screen_points[2]  # TR
        bl = screen_points[0]  # BL

        # Unit vectors for field edges from TL
        h_dx, h_dy = tr[0] - tl[0], tr[1] - tl[1]
        h_len = math.hypot(h_dx, h_dy) or 1.0
        h_ux, h_uy = h_dx / h_len, h_dy / h_len  # horizontal unit

        v_dx, v_dy = bl[0] - tl[0], bl[1] - tl[1]
        v_len = math.hypot(v_dx, v_dy) or 1.0
        v_ux, v_uy = v_dx / v_len, v_dy / v_len  # vertical unit

        # Rotation angle for text (align with top edge)
        edge_angle_rad = math.atan2(h_dy, h_dx)
        edge_angle_deg = -math.degrees(edge_angle_rad)

        # Approximate text dimensions (pygame default font)
        text_height = font_size * 0.75
        text_width = len(name) * font_size * 0.5

        # Top-left of text box = TL + margin along both axes
        tl_x = tl[0] + h_ux * margin + v_ux * margin
        tl_y = tl[1] + h_uy * margin + v_uy * margin

        # Center of text = top-left + half-width along h + half-height along v
        cx = tl_x + h_ux * text_width * 0.5 + v_ux * text_height * 0.5
        cy = tl_y + h_uy * text_width * 0.5 + v_uy * text_height * 0.5

        renderer.draw_text(name, (int(cx), int(cy)),
                           self.label_color, font_size, (0, 0, 0),
                           angle=edge_angle_deg)
