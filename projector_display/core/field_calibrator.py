"""
Field calibrator for coordinate transformations.

Terminology (updated from original):
- world_points: Common reference frame coordinates (physical meters) [was: real_points]
- local_points: Field-specific coordinates (pixels, experiment units, etc.) [was: virtual_points]
- "base": The world coordinate system (physical meters)

Copied from box_push_deploy/shared/field_calibrator.py with terminology updates
and added transform_orientation() method.
"""

import numpy as np
import cv2
from math import cos, sin, atan2, hypot
from typing import Dict, Tuple, List, Union, Optional
from dataclasses import dataclass


@dataclass
class Field:
    """Represents a field with world and local coordinates."""
    name: str
    world_points: np.ndarray  # 4x2 array of world points (meters)
    local_points: np.ndarray  # 4x2 array of local rectangle points

    # Background support (ADR-10)
    background_image: Optional[str] = None  # Filename of background image
    background_color: Optional[Tuple[int, int, int]] = None  # Solid color RGB
    background_alpha: int = 255  # Opacity (0-255)

    def __post_init__(self):
        # Validate inputs
        assert self.world_points.shape == (4, 2), "World points must be 4x2 array"
        assert self.local_points.shape == (4, 2), "Local points must be 4x2 array"

        # Check if local points form a rectangle
        if not self._is_rectangle(self.local_points):
            raise ValueError("Local points must form a rectangle")

    def _is_rectangle(self, points: np.ndarray) -> bool:
        """Check if 4 points form a rectangle."""
        # Sort points by x then y to get consistent ordering
        sorted_pts = points[np.lexsort((points[:, 1], points[:, 0]))]

        # For a rectangle: opposite sides should be parallel and equal
        # Check if it's axis-aligned rectangle (most common case)
        x_coords = sorted(points[:, 0])
        y_coords = sorted(points[:, 1])

        # Check if we have exactly 2 unique x and 2 unique y coordinates
        unique_x = np.unique(x_coords)
        unique_y = np.unique(y_coords)

        if len(unique_x) == 2 and len(unique_y) == 2:
            # Verify all combinations exist
            expected_points = np.array([
                [unique_x[0], unique_y[0]],
                [unique_x[0], unique_y[1]],
                [unique_x[1], unique_y[0]],
                [unique_x[1], unique_y[1]]
            ])

            # Check if all expected points exist in the input
            for ep in expected_points:
                if not any(np.allclose(ep, p) for p in points):
                    return False
            return True

        return False


def _screen_dist(a, b) -> float:
    """Euclidean distance between two coordinate points."""
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


class FieldCalibrator:
    """Utility component for calibrating and converting coordinates between fields."""

    def __init__(self):
        self.fields: Dict[str, Field] = {}
        self.transform_matrix: Dict[str, Dict[str, callable]] = {}
        self.ground_truth_name: Optional[str] = None

        # Initialize base field transforms (identity for world coordinates)
        self.transform_matrix["base"] = {}

    def register_field(self, name: str, world_points: np.ndarray,
                      local_points: np.ndarray, is_ground_truth: bool = False):
        """
        Register a new field with its world and local coordinates.

        Args:
            name: Unique identifier for the field
            world_points: 4x2 array of points in world coordinates (meters)
            local_points: 4x2 array of points forming a rectangle in local space
            is_ground_truth: Whether this field represents the ground truth coordinate system
        """
        field = Field(name, np.array(world_points, dtype=np.float32),
                     np.array(local_points, dtype=np.float32))

        self.fields[name] = field

        if is_ground_truth:
            self.ground_truth_name = name

        # Update transformation matrix for all existing fields
        self._update_transform_matrix(name)

    def _update_transform_matrix(self, new_field_name: str):
        """Update the transformation matrix with conversions for the new field."""
        # Initialize transformation dictionaries if needed
        if new_field_name not in self.transform_matrix:
            self.transform_matrix[new_field_name] = {}

        # Add transforms to/from base (world coordinates)
        self.transform_matrix[new_field_name]["base"] = \
            self._create_local_to_world_function(new_field_name)
        self.transform_matrix["base"][new_field_name] = \
            self._create_world_to_local_function(new_field_name)

        # Create transformations from new field to all existing fields
        for existing_name in self.fields:
            if existing_name != new_field_name:
                # From new field to existing field
                self.transform_matrix[new_field_name][existing_name] = \
                    self._create_transform_function(new_field_name, existing_name)

                # From existing field to new field
                if existing_name not in self.transform_matrix:
                    self.transform_matrix[existing_name] = {}
                self.transform_matrix[existing_name][new_field_name] = \
                    self._create_transform_function(existing_name, new_field_name)

    def _create_local_to_world_function(self, field_name: str):
        """
        Create a transformation function from field local coordinates to world coordinates.

        Args:
            field_name: Name of the field

        Returns:
            Transform function from local to world coordinates
        """
        field = self.fields[field_name]

        # Get transformation matrix from local to world
        local_to_world = cv2.getPerspectiveTransform(
            field.local_points, field.world_points
        )

        def transform(coords: Union[np.ndarray, List[List[float]]]) -> np.ndarray:
            """
            Transform coordinates from local field to world.

            Args:
                coords: Single 2D point [x, y] or array of points [[x1, y1], [x2, y2], ...]

            Returns:
                Transformed coordinates in world
            """
            coords = np.array(coords, dtype=np.float32)
            single_point = False

            # Handle single point case
            if coords.ndim == 1:
                coords = coords.reshape(1, -1)
                single_point = True

            # Ensure correct shape for cv2.perspectiveTransform
            if coords.shape[1] == 2:
                coords = coords.reshape(-1, 1, 2)

            # Apply transformation: local -> world
            world_coords = cv2.perspectiveTransform(coords, local_to_world)

            # Reshape output
            world_coords = world_coords.reshape(-1, 2)

            if single_point:
                return world_coords[0]
            return world_coords

        return transform

    def _create_world_to_local_function(self, field_name: str):
        """
        Create a transformation function from world coordinates to field local coordinates.

        Args:
            field_name: Name of the field

        Returns:
            Transform function from world to local coordinates
        """
        field = self.fields[field_name]

        # Get transformation matrix from world to local
        world_to_local = cv2.getPerspectiveTransform(
            field.world_points, field.local_points
        )

        def transform(coords: Union[np.ndarray, List[List[float]]]) -> np.ndarray:
            """
            Transform coordinates from world to local field.

            Args:
                coords: Single 2D point [x, y] or array of points [[x1, y1], [x2, y2], ...]

            Returns:
                Transformed coordinates in local field
            """
            coords = np.array(coords, dtype=np.float32)
            single_point = False

            # Handle single point case
            if coords.ndim == 1:
                coords = coords.reshape(1, -1)
                single_point = True

            # Ensure correct shape for cv2.perspectiveTransform
            if coords.shape[1] == 2:
                coords = coords.reshape(-1, 1, 2)

            # Apply transformation: world -> local
            local_coords = cv2.perspectiveTransform(coords, world_to_local)

            # Reshape output
            local_coords = local_coords.reshape(-1, 2)

            if single_point:
                return local_coords[0]
            return local_coords

        return transform

    def _create_transform_function(self, from_field_name: str, to_field_name: str):
        """
        Create a transformation function from one field to another.

        The transformation process:
        1. From source local coordinates to world coordinates
        2. From world coordinates to target local coordinates
        """
        # Get the two component transforms
        local_to_world = self._create_local_to_world_function(from_field_name)
        world_to_local = self._create_world_to_local_function(to_field_name)

        def transform(coords: Union[np.ndarray, List[List[float]]]) -> np.ndarray:
            """
            Transform coordinates from source field to target field.

            Args:
                coords: Single 2D point [x, y] or array of points [[x1, y1], [x2, y2], ...]

            Returns:
                Transformed coordinates in the same format as input
            """
            # Apply transformations: local -> world -> local
            world_coords = local_to_world(coords)
            target_coords = world_to_local(world_coords)
            return target_coords

        return transform

    def convert(self, coords: Union[np.ndarray, List[List[float]]],
                from_field: str, to_field: str) -> np.ndarray:
        """
        Convert coordinates from one field to another.

        Args:
            coords: Single 2D point [x, y] or array of points [[x1, y1], [x2, y2], ...]
            from_field: Name of the source field (or "base" for world)
            to_field: Name of the target field (or "base" for world)

        Returns:
            Transformed coordinates
        """
        # Handle base field (world coordinates)
        if from_field == "base" and to_field == "base":
            return np.array(coords)

        if from_field != "base" and from_field not in self.fields:
            raise ValueError(f"Field '{from_field}' not registered")
        if to_field != "base" and to_field not in self.fields:
            raise ValueError(f"Field '{to_field}' not registered")

        if from_field == to_field:
            return np.array(coords)

        transform_func = self.transform_matrix[from_field][to_field]
        return transform_func(coords)

    def transform_orientation(self, from_field: str, to_field: str,
                              position: Tuple[float, float],
                              orientation: float,
                              probe_distance: float = 0.1) -> float:
        """
        Transform orientation between coordinate systems via two-point probe.

        Probes in the source coordinate system, converts both points to the
        target system, and derives the angle from their difference.

        Args:
            from_field: Source coordinate system ("base" for world)
            to_field: Target coordinate system ("base" for world)
            position: (x, y) in from_field coordinates
            orientation: Angle in radians in from_field coordinate system
            probe_distance: Probe offset in from_field units (default 0.1)

        Returns:
            Orientation in radians in to_field coordinate system
        """
        # Create a probe point along the orientation direction in source coords
        probe_point = (
            position[0] + probe_distance * cos(orientation),
            position[1] + probe_distance * sin(orientation)
        )

        # Convert both points to target coordinates
        target_pos = self.convert(position, from_field, to_field)
        target_probe = self.convert(probe_point, from_field, to_field)

        # Calculate angle from the two transformed points
        return atan2(target_probe[1] - target_pos[1],
                     target_probe[0] - target_pos[0])

    def world_scale(self, world_pos: Tuple[float, float], distance: float) -> int:
        """
        Convert a scalar distance to screen pixels at a specific world position (ADR-12).

        Uses a four-point probe around the position to average out asymmetric
        perspective distortion. This is the correct way to convert sizes --
        never use a global pixels-per-meter scalar.

        Args:
            world_pos: (x, y) position in world coordinates (meters)
            distance: Distance in world units (meters for "base" field)

        Returns:
            Equivalent distance in screen pixels (minimum 1)
        """
        if "screen" not in self.fields:
            return max(1, round(distance * 100))  # Fallback

        wx, wy = float(world_pos[0]), float(world_pos[1])
        d = float(distance)

        # Convert center and four probe points through perspective transform
        p_center = self.convert([wx, wy], "base", "screen")
        p_right = self.convert([wx + d, wy], "base", "screen")
        p_left = self.convert([wx - d, wy], "base", "screen")
        p_up = self.convert([wx, wy + d], "base", "screen")
        p_down = self.convert([wx, wy - d], "base", "screen")

        # Compute screen distances in each direction, averaged symmetrically
        dx = (_screen_dist(p_center, p_right) + _screen_dist(p_center, p_left)) / 2
        dy = (_screen_dist(p_center, p_up) + _screen_dist(p_center, p_down)) / 2

        # Average x and y for circular approximation
        return max(1, round((dx + dy) / 2))

    def get_transform_function(self, from_field: str, to_field: str):
        """
        Get the transformation function between two fields.

        Args:
            from_field: Name of the source field (or "base" for world)
            to_field: Name of the target field (or "base" for world)

        Returns:
            Transformation function that accepts coordinates and returns transformed coordinates
        """
        # Handle base field (world coordinates)
        if from_field == "base" and to_field == "base":
            return lambda x: np.array(x)

        if from_field != "base" and from_field not in self.fields:
            raise ValueError(f"Field '{from_field}' not registered")
        if to_field != "base" and to_field not in self.fields:
            raise ValueError(f"Field '{to_field}' not registered")

        if from_field == to_field:
            return lambda x: np.array(x)

        return self.transform_matrix[from_field][to_field]

    def list_fields(self) -> List[str]:
        """List all registered field names."""
        return list(self.fields.keys())

    def get_field_info(self, field_name: str) -> Dict:
        """Get information about a specific field."""
        if field_name not in self.fields:
            raise ValueError(f"Field '{field_name}' not registered")

        field = self.fields[field_name]
        return {
            'name': field.name,
            'world_points': field.world_points.tolist(),
            'local_points': field.local_points.tolist(),
            'is_ground_truth': field_name == self.ground_truth_name
        }


# Example usage
if __name__ == "__main__":
    # Create calibrator
    calibrator = FieldCalibrator()

    # Register ground truth field (world coordinates match local rectangle)
    ground_truth_world = np.array([[0, 0], [100, 0], [100, 50], [0, 50]], dtype=np.float32)
    ground_truth_local = np.array([[0, 0], [100, 0], [100, 50], [0, 50]], dtype=np.float32)
    calibrator.register_field("ground_truth", ground_truth_world, ground_truth_local, is_ground_truth=True)

    # Register Field A (perspective distorted in world)
    field_a_world = np.array([[10, 10], [90, 5], [95, 45], [5, 40]], dtype=np.float32)
    field_a_local = np.array([[0, 0], [80, 0], [80, 40], [0, 40]], dtype=np.float32)
    calibrator.register_field("field_a", field_a_world, field_a_local)

    # Register Field B (another perspective)
    field_b_world = np.array([[20, 15], [70, 20], [65, 35], [15, 30]], dtype=np.float32)
    field_b_local = np.array([[0, 0], [50, 0], [50, 20], [0, 20]], dtype=np.float32)
    calibrator.register_field("field_b", field_b_world, field_b_local)

    # Test single point conversion
    point_in_a = [40, 20]  # Center of field A
    point_in_b = calibrator.convert(point_in_a, "field_a", "field_b")
    print(f"Point {point_in_a} in field_a converts to {point_in_b} in field_b")

    # Test batch conversion
    points_in_a = [[20, 10], [60, 30], [40, 20]]
    points_in_b = calibrator.convert(points_in_a, "field_a", "field_b")
    print(f"\nBatch conversion from field_a to field_b:")
    for i, (pa, pb) in enumerate(zip(points_in_a, points_in_b)):
        print(f"  Point {i}: {pa} -> {pb}")

    # Get transformation function for repeated use
    transform_a_to_b = calibrator.get_transform_function("field_a", "field_b")
    new_point = transform_a_to_b([50, 25])
    print(f"\nUsing transform function: [50, 25] -> {new_point}")

    # Test orientation transformation
    import math
    world_pos = (50, 25)
    world_orientation = math.pi / 4  # 45 degrees
    local_orientation = calibrator.transform_orientation("base", "field_a", world_pos, world_orientation)
    print(f"\nOrientation {math.degrees(world_orientation):.1f}deg at {world_pos} -> {math.degrees(local_orientation):.1f}deg in field_a")
