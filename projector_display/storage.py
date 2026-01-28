"""
Storage manager for projector display server.

Implements ADR-10: XDG-compliant persistent storage with temporary working directory pattern.

Storage Structure:
    ~/.local/share/projector_display/           # Persistent storage (XDG_DATA_HOME)
    ├── calibration.yaml                        # Global screen calibration
    └── scenes/
        └── {scene_name}/                       # Saved scene
            ├── scene.yaml                      # Generated from Scene.to_dict()
            └── images/
                └── arena.png                   # Original filenames preserved

    /tmp/projector_display/{session_id}/        # Ephemeral working directory
    └── images/
        └── arena.png                           # Temp uploads during session
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages storage locations for projector display.

    Follows XDG Base Directory specification for persistent data
    and uses /tmp for session-specific ephemeral data.
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize storage manager.

        Args:
            session_id: Optional session ID for temp directory.
                       If not provided, generates a new UUID.
        """
        self._session_id = session_id or str(uuid.uuid4())
        self._data_dir: Optional[Path] = None
        self._session_dir: Optional[Path] = None

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return self._session_id

    def get_data_dir(self) -> Path:
        """
        Get persistent data directory (XDG-compliant).

        Returns:
            Path to ~/.local/share/projector_display/
            Creates directory if it doesn't exist.
        """
        if self._data_dir is None:
            # Use XDG_DATA_HOME if set, otherwise default to ~/.local/share
            xdg_data_home = os.environ.get('XDG_DATA_HOME')
            if xdg_data_home:
                base_dir = Path(xdg_data_home)
            else:
                base_dir = Path.home() / '.local' / 'share'

            self._data_dir = base_dir / 'projector_display'
            self._data_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Data directory: {self._data_dir}")

        return self._data_dir

    def get_session_dir(self) -> Path:
        """
        Get ephemeral session directory.

        Returns:
            Path to /tmp/projector_display/{session_id}/
            Creates directory if it doesn't exist.
        """
        if self._session_dir is None:
            self._session_dir = Path('/tmp') / 'projector_display' / self._session_id
            self._session_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Session directory: {self._session_dir}")

        return self._session_dir

    def get_session_images_dir(self) -> Path:
        """
        Get session images directory.

        Returns:
            Path to /tmp/projector_display/{session_id}/images/
            Creates directory if it doesn't exist.
        """
        images_dir = self.get_session_dir() / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir

    def get_calibration_path(self) -> Path:
        """
        Get path to calibration file.

        Returns:
            Path to ~/.local/share/projector_display/calibration.yaml
        """
        return self.get_data_dir() / 'calibration.yaml'

    def get_scenes_dir(self) -> Path:
        """
        Get scenes directory.

        Returns:
            Path to ~/.local/share/projector_display/scenes/
            Creates directory if it doesn't exist.
        """
        scenes_dir = self.get_data_dir() / 'scenes'
        scenes_dir.mkdir(parents=True, exist_ok=True)
        return scenes_dir

    def get_scene_dir(self, name: str) -> Path:
        """
        Get directory for a specific scene.

        Args:
            name: Scene name

        Returns:
            Path to ~/.local/share/projector_display/scenes/{name}/
            Creates directory if it doesn't exist.
        """
        scene_dir = self.get_scenes_dir() / name
        scene_dir.mkdir(parents=True, exist_ok=True)
        return scene_dir

    def get_scene_images_dir(self, name: str) -> Path:
        """
        Get images directory for a specific scene.

        Args:
            name: Scene name

        Returns:
            Path to ~/.local/share/projector_display/scenes/{name}/images/
            Creates directory if it doesn't exist.
        """
        images_dir = self.get_scene_dir(name) / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir

    def get_scene_yaml_path(self, name: str) -> Path:
        """
        Get path to scene YAML file.

        Args:
            name: Scene name

        Returns:
            Path to ~/.local/share/projector_display/scenes/{name}/scene.yaml
        """
        return self.get_scene_dir(name) / 'scene.yaml'

    def list_scenes(self) -> list:
        """
        List all saved scenes.

        Returns:
            List of scene names
        """
        scenes_dir = self.get_scenes_dir()
        if not scenes_dir.exists():
            return []

        return [
            d.name for d in scenes_dir.iterdir()
            if d.is_dir() and (d / 'scene.yaml').exists()
        ]

    def scene_exists(self, name: str) -> bool:
        """
        Check if a scene exists in persistent storage.

        Args:
            name: Scene name

        Returns:
            True if scene exists
        """
        return self.get_scene_yaml_path(name).exists()

    def delete_scene(self, name: str) -> bool:
        """
        Delete a scene from persistent storage.

        Args:
            name: Scene name

        Returns:
            True if deleted, False if not found
        """
        scene_dir = self.get_scene_dir(name)
        if not scene_dir.exists():
            return False

        shutil.rmtree(scene_dir)
        logger.info(f"Deleted scene: {name}")
        return True

    def cleanup_session(self):
        """
        Clean up session temporary directory.

        Called when session ends or server shuts down.
        """
        if self._session_dir and self._session_dir.exists():
            shutil.rmtree(self._session_dir)
            logger.debug(f"Cleaned up session directory: {self._session_dir}")
            self._session_dir = None


# Global storage manager instance (initialized per server)
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """
    Get the global storage manager instance.

    Initializes a new instance if none exists.
    """
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager


def init_storage_manager(session_id: Optional[str] = None) -> StorageManager:
    """
    Initialize or reset the global storage manager.

    Args:
        session_id: Optional session ID

    Returns:
        The initialized StorageManager
    """
    global _storage_manager
    _storage_manager = StorageManager(session_id)
    return _storage_manager
