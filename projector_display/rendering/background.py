"""
Background rendering for projector display.

Implements ADR-10: Field background rendering with perspective warp.
Uses OpenCV warpPerspective to transform images to match field quadrilaterals.

Renderer-agnostic: uses renderer.create_image / renderer.draw_image instead
of pygame.Surface directly.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, Callable

import cv2
import numpy as np

from projector_display.core.field_calibrator import Field
from projector_display.storage import get_storage_manager

logger = logging.getLogger(__name__)


class BackgroundRenderer:
    """
    Renders background images for fields with perspective warping.

    Caches warped images to avoid re-computing each frame.
    Cache is invalidated when field geometry or image changes.
    """

    def __init__(self):
        # Cache: field_name -> (image_handle, cache_key, offset, size)
        self._cache: Dict[str, Tuple[Any, str, Tuple[int, int], Tuple[int, int]]] = {}
        # Track which renderer created the cached handles so we can
        # invalidate when the renderer changes.
        self._cache_renderer_id: Optional[int] = None

    def _get_cache_key(self, field: Field, image_path: Path,
                       screen_points: np.ndarray) -> str:
        """Generate cache key based on field, image, and screen mapping."""
        return (
            f"{field.name}|{field.background_image}|{field.background_alpha}|"
            f"{image_path.stat().st_mtime}|{screen_points.tobytes().hex()[:32]}"
        )

    def _load_and_warp_image(self, field: Field, image_path: Path,
                             screen_points: np.ndarray
                             ) -> Optional[Tuple[bytes, int, int, Tuple[int, int]]]:
        """
        Load image and warp it to fit the field's screen quadrilateral.

        Args:
            field: Field with background configuration
            image_path: Path to the image file
            screen_points: 4x2 array of screen coordinates [BL, BR, TR, TL]

        Returns:
            (rgba_bytes, width, height, offset) or None on failure
        """
        try:
            # Load image with OpenCV (supports PNG with alpha)
            img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
            if img is None:
                logger.error(f"Failed to load image: {image_path}")
                return None

            # Convert BGR(A) to RGBA
            if len(img.shape) == 2:
                # Grayscale - convert to RGBA
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGBA)
            elif img.shape[2] == 3:
                # BGR - convert to RGBA
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
            elif img.shape[2] == 4:
                # BGRA - convert to RGBA
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)

            # Source points: corners of the original image
            h, w = img.shape[:2]
            # Order: BL, BR, TR, TL (matching our vertex convention)
            src_pts = np.array([
                [0, h],      # Bottom-left
                [w, h],      # Bottom-right
                [w, 0],      # Top-right
                [0, 0],      # Top-left
            ], dtype=np.float32)

            # Destination points: field corners in screen space
            dst_pts = screen_points.astype(np.float32)

            # Calculate output size (bounding box of destination)
            x_min, y_min = dst_pts.min(axis=0).astype(int)
            x_max, y_max = dst_pts.max(axis=0).astype(int)

            # Adjust destination points relative to output origin
            dst_pts_adjusted = dst_pts - np.array([x_min, y_min], dtype=np.float32)

            output_w = x_max - x_min
            output_h = y_max - y_min

            # Get perspective transform matrix
            M = cv2.getPerspectiveTransform(src_pts, dst_pts_adjusted)

            # Warp the image
            warped = cv2.warpPerspective(
                img, M, (output_w, output_h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)  # Transparent border
            )

            # Apply alpha from field settings
            if field.background_alpha < 255:
                # Scale the alpha channel
                alpha_scale = field.background_alpha / 255.0
                warped[:, :, 3] = (warped[:, :, 3] * alpha_scale).astype(np.uint8)

            rgba_bytes = warped.tobytes()
            offset = (int(x_min), int(y_min))

            return (rgba_bytes, output_w, output_h, offset)

        except Exception as e:
            logger.error(f"Failed to warp background image: {e}")
            return None

    def render_field_backgrounds(self, renderer, fields: Dict[str, Field],
                                 world_to_screen: Callable[[float, float], Tuple[int, int]]):
        """
        Render background images or solid colors for all fields that have them.

        Args:
            renderer: Renderer instance (PygameRenderer or GLESRenderer)
            fields: Dictionary of field_name -> Field
            world_to_screen: Function to convert world coords to screen coords
        """
        # Invalidate cache if renderer changed (e.g. switched backends)
        renderer_id = id(renderer)
        if self._cache_renderer_id is not None and self._cache_renderer_id != renderer_id:
            self._cache.clear()
        self._cache_renderer_id = renderer_id

        storage = get_storage_manager()
        images_dir = None  # lazy init

        for field_name, field in fields.items():
            # Handle solid color background
            if field.background_color is not None:
                screen_points = [
                    world_to_screen(pt[0], pt[1])
                    for pt in field.world_points
                ]
                renderer.draw_polygon(
                    screen_points, field.background_color,
                    field.background_alpha
                )
                continue

            if not field.background_image:
                continue

            # Lazy-init images directory only when needed
            if images_dir is None:
                images_dir = storage.get_session_images_dir()

            image_path = images_dir / field.background_image
            if not image_path.exists():
                logger.warning(f"Background image not found: {image_path}")
                continue

            # Convert field world points to screen points
            screen_points = np.array([
                world_to_screen(pt[0], pt[1])
                for pt in field.world_points
            ], dtype=np.float32)

            # Check cache
            cache_key = self._get_cache_key(field, image_path, screen_points)
            cached = self._cache.get(field_name)

            if cached and cached[1] == cache_key:
                # Use cached handle
                image_handle, _, offset, size = cached
            else:
                # Warp and cache
                result = self._load_and_warp_image(field, image_path, screen_points)
                if result is None:
                    continue
                rgba_bytes, output_w, output_h, offset = result
                size = (output_w, output_h)
                image_handle = renderer.create_image(rgba_bytes, output_w, output_h)
                self._cache[field_name] = (image_handle, cache_key, offset, size)

            # Draw the image at offset position
            renderer.draw_image(image_handle, offset, size)

    def invalidate_cache(self, field_name: Optional[str] = None):
        """
        Invalidate cached warped images.

        Args:
            field_name: Specific field to invalidate, or None for all
        """
        if field_name:
            self._cache.pop(field_name, None)
        else:
            self._cache.clear()

    def clear(self):
        """Clear all cached images."""
        self._cache.clear()
