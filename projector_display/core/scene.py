"""
Scene management for projector display.

A Scene holds a FieldCalibrator, a collection of RigidBodies, and persistent Drawings.
Single scene per server instance - to "switch" experiments, client sends
commands to clear and rebuild the scene.
"""

import threading
from typing import Dict, Optional, List
from projector_display.core.field_calibrator import FieldCalibrator, Field
from projector_display.core.rigidbody import RigidBody, RigidBodyStyle, TrajectoryStyle
from projector_display.core.draw_primitive import Drawing


class Scene:
    """
    Scene management for display server.

    Architecture:
        Scene (one per server instance)
        ├── FieldCalibrator
        │   └── Fields: Dict[name, Field]
        │         ├── "screen" (world meters ↔ screen pixels)
        │         └── user-defined fields (world ↔ local coords)
        ├── RigidBodies: Dict[name, RigidBody]
        └── Drawings: Dict[id, Drawing]  (persistent overlays)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.field_calibrator = FieldCalibrator()
        self._rigidbodies: Dict[str, RigidBody] = {}
        self._drawings: Dict[str, Drawing] = {}
        self._z_counter: int = 0  # Monotonic counter for z-order tie-breaking

        # Debug layer toggles
        self.grid_layer_enabled: bool = False
        self.field_layer_enabled: bool = False

        # Grid layer settings
        self.grid_show_minor: bool = True
        self.grid_major_color: tuple = (100, 100, 100, 255)
        self.grid_minor_color: tuple = (50, 50, 50, 255)

    @property
    def rigidbodies(self) -> Dict[str, RigidBody]:
        """Access rigidbodies dict (for backwards compatibility)."""
        return self._rigidbodies

    def get_rigidbodies_snapshot(self) -> Dict[str, RigidBody]:
        """Get a lightweight snapshot of rigidbodies for safe iteration.

        Uses RigidBody.render_snapshot() which shallow-copies each RigidBody
        and only copies the position_history deque container (not the entry
        dicts, which are never mutated after creation).
        """
        with self._lock:
            return {name: rb.render_snapshot()
                    for name, rb in self._rigidbodies.items()}

    def get_fields_snapshot(self) -> Dict[str, 'Field']:
        """Get a snapshot copy of fields for safe iteration."""
        with self._lock:
            return dict(self.field_calibrator.fields)

    def get_drawings_snapshot(self) -> Dict[str, Drawing]:
        """Get a snapshot of drawings for safe render iteration.

        Shallow copy of the dict — Drawing objects are immutable after creation.
        """
        with self._lock:
            return dict(self._drawings)

    def _next_z_seq(self) -> int:
        """Return next monotonic sequence number for z-order tie-breaking.

        Must be called while self._lock is held.
        """
        self._z_counter += 1
        return self._z_counter

    # --- Drawing Management (persistent overlays) ---

    def add_drawing(self, drawing: Drawing) -> None:
        """Add or replace a persistent drawing overlay."""
        with self._lock:
            drawing._z_seq = self._next_z_seq()
            self._drawings[drawing.id] = drawing

    def remove_drawing(self, drawing_id: str) -> bool:
        """Remove a drawing by ID. Returns True if removed, False if not found."""
        with self._lock:
            if drawing_id in self._drawings:
                del self._drawings[drawing_id]
                return True
            return False

    def get_drawing(self, drawing_id: str) -> Optional[Drawing]:
        """Get a drawing by ID."""
        with self._lock:
            return self._drawings.get(drawing_id)

    def list_drawings(self) -> List[str]:
        """List all drawing IDs."""
        with self._lock:
            return list(self._drawings.keys())

    def clear_drawings(self) -> None:
        """Remove all persistent drawings."""
        with self._lock:
            self._drawings.clear()

    # --- RigidBody Management ---

    def create_rigidbody(self, name: str, style: Optional[dict] = None,
                         trajectory: Optional[dict] = None,
                         mocap_name: Optional[str] = None,
                         auto_track: bool = False,
                         z_order: int = 0) -> RigidBody:
        """
        Create a new rigid body for display.

        Args:
            name: Unique identifier for the rigid body
            style: Optional style configuration dict
            trajectory: Optional trajectory configuration dict
            mocap_name: Optional name in MoCap system
            auto_track: Enable auto-tracking from MoCap (default False)
            z_order: Render order (lower = behind, default 0)

        Returns:
            The created RigidBody

        Raises:
            ValueError: If rigid body with name already exists
        """
        with self._lock:
            if name in self._rigidbodies:
                raise ValueError(f"RigidBody '{name}' already exists")

            rb = RigidBody(name=name, mocap_name=mocap_name, auto_track=auto_track,
                           z_order=z_order)
            rb._z_seq = self._next_z_seq()

            if style:
                rb.style = RigidBodyStyle.from_dict(style)
            if trajectory:
                rb.trajectory_style = TrajectoryStyle.from_dict(trajectory)

            self._rigidbodies[name] = rb
            return rb

    def get_rigidbody(self, name: str) -> Optional[RigidBody]:
        """Get a rigid body by name."""
        with self._lock:
            return self._rigidbodies.get(name)

    def remove_rigidbody(self, name: str) -> bool:
        """
        Remove a rigid body from the scene.

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if name in self._rigidbodies:
                del self._rigidbodies[name]
                return True
            return False

    def list_rigidbodies(self) -> List[str]:
        """List all rigid body names."""
        with self._lock:
            return list(self._rigidbodies.keys())

    def update_position(self, name: str, x: float, y: float,
                        orientation: Optional[float] = None) -> bool:
        """
        Update rigid body manual position.

        Args:
            name: Rigid body name
            x: X position in world coordinates (meters)
            y: Y position in world coordinates (meters)
            orientation: Orientation in radians (optional)

        Returns:
            True if updated, False if rigid body not found
        """
        with self._lock:
            rb = self._rigidbodies.get(name)
            if rb is None:
                return False
            rb.update_position(x, y, orientation)
            return True

    def update_mocap_position(self, name: str, x: float, y: float,
                              orientation: Optional[float] = None) -> bool:
        """
        Update rigid body MoCap-driven position (runtime state).

        Args:
            name: Rigid body name
            x: X position in world coordinates (meters)
            y: Y position in world coordinates (meters)
            orientation: Orientation in radians (optional)

        Returns:
            True if updated, False if rigid body not found
        """
        with self._lock:
            rb = self._rigidbodies.get(name)
            if rb is None:
                return False
            rb.update_mocap_position(x, y, orientation)
            return True

    def set_rigidbody_tracking(self, name: str, mocap_name: Optional[str] = None,
                                auto_track: Optional[bool] = None) -> bool:
        """
        Configure MoCap tracking for a rigid body.

        Args:
            name: Rigid body name
            mocap_name: Name in MoCap system (None = don't change)
            auto_track: Enable/disable auto-tracking (None = don't change)

        Returns:
            True if updated, False if rigid body not found
        """
        with self._lock:
            rb = self._rigidbodies.get(name)
            if rb is None:
                return False
            if mocap_name is not None:
                rb.mocap_name = mocap_name
            if auto_track is not None and auto_track != rb.auto_track:
                rb.auto_track = auto_track
                rb.clear_history()
            return True

    def set_tracking_lost(self, name: str, lost: bool) -> bool:
        """
        Set tracking lost status for a rigid body.

        Args:
            name: Rigid body name
            lost: True if tracking is lost, False if tracking OK

        Returns:
            True if updated, False if rigid body not found
        """
        with self._lock:
            rb = self._rigidbodies.get(name)
            if rb is None:
                return False
            rb.tracking_lost = lost
            return True

    def update_style(self, name: str, **style_params) -> bool:
        """
        Update rigid body visualization style.

        Returns:
            True if updated, False if rigid body not found

        Note: F3 (setattr injection) is marked for future - trusted lab environment.
        """
        with self._lock:
            rb = self._rigidbodies.get(name)
            if rb is None:
                return False

            # Update individual style attributes
            # TODO (F3): Add whitelist validation for production use
            from projector_display.core.rigidbody import RigidBodyShape
            from projector_display.utils.color import parse_color

            for key, value in style_params.items():
                if hasattr(rb.style, key):
                    if key == 'shape' and isinstance(value, str):
                        value = RigidBodyShape(value)
                    elif key in ('color', 'orientation_color') and isinstance(value, (list, str)):
                        # ADR-8: Parse and normalize to RGBA (supports hex, RGB, RGBA, float)
                        value = parse_color(value)
                    elif key == 'label_offset' and isinstance(value, list):
                        value = tuple(value)
                    elif key == 'polygon_vertices' and value is not None:
                        value = [tuple(v) for v in value]
                    elif key == 'draw_list' and value is not None:
                        from projector_display.core.draw_primitive import DrawPrimitive
                        value = [DrawPrimitive.from_dict(p) if isinstance(p, dict) else p
                                 for p in value]
                    setattr(rb.style, key, value)

            return True

    def update_trajectory(self, name: str, **traj_params) -> bool:
        """
        Update rigid body trajectory style.

        Returns:
            True if updated, False if rigid body not found
        """
        with self._lock:
            rb = self._rigidbodies.get(name)
            if rb is None:
                return False

            from projector_display.utils.color import parse_color

            # Update individual trajectory attributes
            for key, value in traj_params.items():
                if hasattr(rb.trajectory_style, key):
                    if key in ('gradient_start', 'gradient_end', 'color') and isinstance(value, (list, str)):
                        # ADR-8: Parse and normalize to RGBA (supports hex, RGB, RGBA, float)
                        # Note: 'color' can also be the literal string "gradient"
                        if not (key == 'color' and value == 'gradient'):
                            value = parse_color(value)
                    setattr(rb.trajectory_style, key, value)

            return True

    # --- Field Management ---

    def create_field(self, name: str, world_points: list, local_points: list) -> bool:
        """
        Create a new coordinate field.

        Args:
            name: Unique identifier for the field
            world_points: 4x2 list of points in world coordinates (meters)
                         Order: [BL, BR, TR, TL] (counter-clockwise)
            local_points: 4x2 list of points in local coordinates
                         Order: [BL, BR, TR, TL] (counter-clockwise)

        Returns:
            True if created successfully
        """
        self.field_calibrator.register_field(name, world_points, local_points)
        return True

    def remove_field(self, name: str) -> bool:
        """
        Remove a registered field.

        Returns:
            True if removed, False if not found
        """
        if name not in self.field_calibrator.fields:
            return False
        del self.field_calibrator.fields[name]
        # Also remove from transform matrices
        if name in self.field_calibrator.transform_matrix:
            del self.field_calibrator.transform_matrix[name]
        for field_name in self.field_calibrator.transform_matrix:
            if name in self.field_calibrator.transform_matrix[field_name]:
                del self.field_calibrator.transform_matrix[field_name][name]
        return True

    def list_fields(self) -> List[str]:
        """List all registered field names."""
        return self.field_calibrator.list_fields()

    def get_field(self, name: str) -> Optional[Field]:
        """Get a field by name."""
        return self.field_calibrator.fields.get(name)

    # --- Debug Layers ---

    def toggle_grid_layer(self) -> bool:
        """Toggle grid layer visibility. Returns new state."""
        self.grid_layer_enabled = not self.grid_layer_enabled
        return self.grid_layer_enabled

    def toggle_field_layer(self) -> bool:
        """Toggle field layer visibility. Returns new state."""
        self.field_layer_enabled = not self.field_layer_enabled
        return self.field_layer_enabled

    # --- Scene Operations ---

    def clear(self):
        """Clear all rigid bodies and drawings from the scene (keeps fields)."""
        with self._lock:
            self._rigidbodies.clear()
            self._drawings.clear()
            self._z_counter = 0

    def clear_all(self):
        """Clear everything including fields (except screen field if exists)."""
        with self._lock:
            self._rigidbodies.clear()
            self._drawings.clear()
            self._z_counter = 0
            # Keep screen field if it exists
            screen_field = self.field_calibrator.fields.get("screen")
            self.field_calibrator = FieldCalibrator()
            if screen_field:
                self.field_calibrator.register_field(
                    "screen",
                    screen_field.world_points,
                    screen_field.local_points
                )

    def to_dict(self) -> dict:
        """
        Convert scene to dictionary for YAML serialization.

        Returns:
            Dictionary that can be YAML-serialized and used to recreate the scene
        """
        with self._lock:
            fields_dict = {}
            for name, field in self.field_calibrator.fields.items():
                if name == "screen":  # Don't include screen field in scene dump
                    continue

                field_data = {
                    'world_points': field.world_points.tolist(),
                    'local_points': field.local_points.tolist(),
                }

                # Include background info if present (ADR-10)
                if hasattr(field, 'background_image') and field.background_image:
                    field_data['background'] = {
                        'image': field.background_image,
                        'alpha': getattr(field, 'background_alpha', 255)
                    }

                fields_dict[name] = field_data

            return {
                'fields': fields_dict,
                'rigidbodies': {
                    name: rb.to_dict()
                    for name, rb in self._rigidbodies.items()
                },
                'drawings': {
                    did: d.to_dict()
                    for did, d in self._drawings.items()
                },
            }

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        """
        Create scene from dictionary.

        Args:
            data: Dictionary from to_dict() or YAML load

        Returns:
            Reconstructed Scene
        """
        scene = cls()

        # Load fields
        for name, field_data in data.get('fields', {}).items():
            scene.create_field(
                name=name,
                world_points=field_data['world_points'],
                local_points=field_data['local_points'],
            )

            # Load field background if present (ADR-10)
            background = field_data.get('background')
            if background:
                field = scene.get_field(name)
                if field:
                    field.background_image = background.get('image')
                    field.background_alpha = background.get('alpha', 255)

        # Load rigid bodies
        for name, rb_data in data.get('rigidbodies', {}).items():
            rb = scene.create_rigidbody(
                name=name,
                style=rb_data.get('style'),
                trajectory=rb_data.get('trajectory'),
                mocap_name=rb_data.get('mocap_name'),
                auto_track=rb_data.get('auto_track', False),
                z_order=rb_data.get('z_order', 0),
            )
            if rb_data.get('position'):
                rb.position = tuple(rb_data['position'])
            if rb_data.get('orientation') is not None:
                rb.orientation = rb_data['orientation']
                rb._last_orientation = rb_data['orientation']

        # Load drawings
        for did, d_data in data.get('drawings', {}).items():
            drawing = Drawing.from_dict(d_data)
            scene.add_drawing(drawing)

        return scene
