"""
Asset commands for projector display server.

Pure asset transfer commands for image management (ADR-10).
Handles image upload, verification, and listing.
"""

import base64
import hashlib
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from projector_display.commands.base import register_command
from projector_display.storage import get_storage_manager

logger = logging.getLogger(__name__)

# Supported image formats (by file extension)
SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'}


def _compute_hash(data: bytes) -> str:
    """Compute SHA256 hash of data, return first 16 chars."""
    return hashlib.sha256(data).hexdigest()[:16]


def _format_size(size_bytes: int) -> str:
    """Format file size for human readability."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


@register_command
def check_image(scene, name: str, hash: Optional[str] = None) -> dict:
    """
    Check if an image exists and optionally verify its hash.

    Args:
        scene: Scene instance (unused but required by command interface)
        name: Image filename (e.g., "arena.png")
        hash: Optional SHA256 hash (first 16 chars) to verify

    Returns:
        Response indicating image status:
        - {exists: true, hash_match: true} when hash matches
        - {exists: true, hash_match: false, reason: "hash_mismatch"} when differs
        - {exists: false, reason: "not_found"} when not found
    """
    storage = get_storage_manager()
    images_dir = storage.get_session_images_dir()
    image_path = images_dir / name

    if not image_path.exists():
        return {
            "status": "success",
            "exists": False,
            "reason": "not_found"
        }

    # Image exists - check hash if provided
    if hash is not None:
        with open(image_path, 'rb') as f:
            existing_hash = _compute_hash(f.read())

        if existing_hash == hash:
            logger.debug(f"Image '{name}' hash matches")
            return {
                "status": "success",
                "exists": True,
                "hash_match": True
            }
        else:
            logger.debug(f"Image '{name}' hash mismatch: {existing_hash} != {hash}")
            return {
                "status": "success",
                "exists": True,
                "hash_match": False,
                "reason": "hash_mismatch"
            }

    # No hash provided, just report existence
    return {
        "status": "success",
        "exists": True
    }


def _validate_image_data(image_data: bytes) -> tuple:
    """
    Validate that binary data is a valid image.

    Args:
        image_data: Raw image bytes

    Returns:
        (is_valid, error_message, image_info)
        - is_valid: True if data is a valid image
        - error_message: Error description if invalid, None otherwise
        - image_info: Dict with width, height, channels if valid
    """
    try:
        # Try to decode with OpenCV
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)

        if img is None:
            return False, "Data is not a valid image (could not decode)", None

        height, width = img.shape[:2]
        channels = img.shape[2] if len(img.shape) > 2 else 1

        return True, None, {"width": width, "height": height, "channels": channels}

    except Exception as e:
        return False, f"Image validation failed: {e}", None


@register_command
def upload_image(scene, name: str, data: str) -> dict:
    """
    Upload an image to the session images folder.

    Args:
        scene: Scene instance (unused but required by command interface)
        name: Image filename (e.g., "arena.png")
        data: Base64-encoded image data

    Returns:
        Response with upload result:
        - {action: "created", message: "Saved 'arena.png' (102.4 KB)"}
        - {action: "replaced", message: "Replaced existing 'arena.png' (102.4 KB)"}
    """
    # Validate file extension
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        return {
            "status": "error",
            "message": f"Unsupported image format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
        }

    storage = get_storage_manager()
    images_dir = storage.get_session_images_dir()
    image_path = images_dir / name

    # Check if file exists before writing
    existed = image_path.exists()

    try:
        # Decode base64
        image_data = base64.b64decode(data)

        # Validate it's actually an image (F5 fix)
        is_valid, error_msg, image_info = _validate_image_data(image_data)
        if not is_valid:
            logger.warning(f"Rejected invalid image upload '{name}': {error_msg}")
            return {
                "status": "error",
                "message": error_msg
            }

        # Write the validated image
        with open(image_path, 'wb') as f:
            f.write(image_data)

        size_str = _format_size(len(image_data))
        dimensions = f"{image_info['width']}x{image_info['height']}"

        if existed:
            logger.warning(f"Replaced existing image '{name}' ({size_str}, {dimensions})")
            return {
                "status": "success",
                "action": "replaced",
                "message": f"Replaced existing '{name}' ({size_str}, {dimensions})"
            }
        else:
            logger.info(f"Saved image '{name}' ({size_str}, {dimensions})")
            return {
                "status": "success",
                "action": "created",
                "message": f"Saved '{name}' ({size_str}, {dimensions})"
            }

    except base64.binascii.Error as e:
        return {
            "status": "error",
            "message": f"Invalid base64 data: {e}"
        }
    except OSError as e:
        return {
            "status": "error",
            "message": f"Failed to write image: {e}"
        }


@register_command
def list_images(scene) -> dict:
    """
    List all images in the session.

    Args:
        scene: Scene instance (unused but required by command interface)

    Returns:
        Response with list of images and their sizes
    """
    storage = get_storage_manager()
    images_dir = storage.get_session_images_dir()

    images = []
    if images_dir.exists():
        for path in images_dir.iterdir():
            if path.is_file():
                size = path.stat().st_size
                with open(path, 'rb') as f:
                    file_hash = _compute_hash(f.read())
                images.append({
                    "name": path.name,
                    "size": size,
                    "size_formatted": _format_size(size),
                    "hash": file_hash
                })

    return {
        "status": "success",
        "images": images,
        "count": len(images)
    }


@register_command
def delete_image(scene, name: str) -> dict:
    """
    Remove an image from the session.

    Args:
        scene: Scene instance (unused but required by command interface)
        name: Image filename to delete

    Returns:
        Response with deletion result
    """
    storage = get_storage_manager()
    images_dir = storage.get_session_images_dir()
    image_path = images_dir / name

    if not image_path.exists():
        return {
            "status": "error",
            "message": f"Image '{name}' not found"
        }

    try:
        image_path.unlink()
        logger.info(f"Deleted image '{name}'")
        return {
            "status": "success",
            "message": f"Deleted '{name}'"
        }
    except OSError as e:
        return {
            "status": "error",
            "message": f"Failed to delete image: {e}"
        }


@register_command
def get_image_path(scene, name: str) -> dict:
    """
    Get the full path to an image in the session.

    This is an internal helper for rendering - returns the absolute path
    to an uploaded image so the renderer can load it.

    Args:
        scene: Scene instance (unused but required by command interface)
        name: Image filename

    Returns:
        Response with image path or error if not found
    """
    storage = get_storage_manager()
    images_dir = storage.get_session_images_dir()
    image_path = images_dir / name

    if not image_path.exists():
        return {
            "status": "error",
            "message": f"Image '{name}' not found"
        }

    return {
        "status": "success",
        "path": str(image_path)
    }
