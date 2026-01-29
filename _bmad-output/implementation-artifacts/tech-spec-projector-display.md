---
title: 'Projector Display Utility'
slug: 'projector-display'
created: '2026-01-27'
updated: '2026-01-28'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
tech_stack: [python>3.10, pygame, opencv, pyyaml, numpy]
files_to_modify: [
  "projector_display/__init__.py",
  "projector_display/server.py",
  "projector_display/client.py",
  "projector_display/storage.py",
  "projector_display/core/__init__.py",
  "projector_display/core/field_calibrator.py",
  "projector_display/core/scene.py",
  "projector_display/core/rigidbody.py",
  "projector_display/core/draw_primitive.py",
  "projector_display/commands/__init__.py",
  "projector_display/commands/base.py",
  "projector_display/commands/prebuilt/__init__.py",
  "projector_display/commands/prebuilt/rigidbody_commands.py",
  "projector_display/commands/prebuilt/field_commands.py",
  "projector_display/commands/prebuilt/scene_commands.py",
  "projector_display/commands/prebuilt/debug_commands.py",
  "projector_display/commands/prebuilt/asset_commands.py",
  "projector_display/commands/prebuilt/mocap_commands.py",
  "projector_display/commands/prebuilt/drawing_commands.py",
  "projector_display/rendering/__init__.py",
  "projector_display/rendering/renderer.py",
  "projector_display/rendering/primitives.py",
  "projector_display/rendering/trajectory.py",
  "projector_display/rendering/debug_layers.py",
  "projector_display/rendering/background.py",
  "projector_display/mocap/__init__.py",
  "projector_display/mocap/tracker.py",
  "projector_display/utils/__init__.py",
  "projector_display/utils/logging.py",
  "projector_display/utils/color.py",
  "config/server_config.yaml",
  "pyproject.toml"
]
code_patterns: [dataclasses, protocol, decorator-registry, json-tcp]
test_patterns: []
---

# Tech-Spec: Projector Display Utility

**Created:** 2026-01-27
**Updated:** 2026-01-28

## Overview

### Problem Statement

Existing display utility (in `../box_push_deploy/shared/`) works but is disorganized, has hardcoded patterns, incorrect orientation transformation (uses raw orientation without point conversion), and poor modularity (adding toolbox features requires manual server command sync). Need a clean reimplementation that is generic, reusable across experiments, and fully configurable via YAML with bidirectional command serialization.

### Solution

Build a scene-based projector display server where:
- Server starts with minimal configuration, Scenes created via commands
- RigidBody is the first-class displayable entity (not "Robot")
- Scenes support multiple custom Fields (coordinate systems)
- Commands explicitly declare their target coordinate field
- YAML and Commands are interconvertible (same structure)
- FieldCalibrator handles all point transformations (reused from reference)
- Orientations transformed via point conversion (two points -> derive angle)
- DrawPrimitive provides a composable, data-driven building block for custom shapes and persistent overlays

### Scope

**In Scope:**
- Scene architecture (create, dump to YAML, no auto-persist)
- RigidBody management (explicit creation required)
- Multiple Fields per Scene with vertex convention: `[BL, BR, TR, TL]` (counter-clockwise from bottom-left)
- Built-in shapes: Circle, Box, Triangle, Polygon
- Compound rigid bodies: user-defined shape from list of DrawPrimitives in body-local coordinates
- Direct drawing overlays: persistent shapes positioned in field coordinates
- Drawing primitive types: Circle, Box, Line, Polygon, Text, Arrow
- Proper orientation transformation via point conversion
- JSON/TCP commands with YAML-mirroring structure
- Commands specify target field for coordinate interpretation
- Co-located command handlers with toolbox methods
- Dual-sink logging (stdout/stderr + /var/log)
- Optional MoCap integration (lazy-loaded when needed)
- Python client library
- Debug utility layers: togglable grid layer + experiment field layer
- State inspection commands: `get_scene`, `get_rigidbody`
- Flexible color parsing: hex, RGB, RGBA, float, CSV string formats
- RGBA color format throughout (ADR-8)
- XDG-compliant persistent storage with session working directories (ADR-10)
- Field background images with perspective warp via OpenCV
- Scene save/load to persistent storage

**Out of Scope:**
- Generic pygame command passthrough (future enhancement)
- Server-side auto-persistence (explicit dump only)
- WebSocket/HTTP interfaces (JSON/TCP only for v1)
- Planned/future trajectories (v1 supports history trails only)

## Context for Development

### Codebase Patterns

**Reference Implementation:** `../box_push_deploy/shared/`
- `display_toolbox.py` - Core visualization (1044 lines) - reference for drawing primitives
- `toolbox_display_server.py` - Socket server (681 lines) - reference for server architecture
- `display_client.py` - Client wrapper (252 lines) - reference for client API
- `field_calibrator.py` - Coordinate transformation (350 lines) - **COPY AND EXTEND** (add orientation transform, update terminology: `real_points` -> `world_points`, `virtual_points` -> `local_points`)

**Key Design Decisions:**
1. **Vertex Order Convention:** `[Bottom-Left, Bottom-Right, Top-Right, Top-Left]` - counter-clockwise from origin
2. **Coordinate Fields:** Each field maps between world coords (common reference, meters) and local coords (field-specific: pixels, experiment units, etc.)
3. **Orientation Bug Fix:** Must transform orientation via two-point conversion, not direct use
4. **Terminology:** "world" = common reference frame (meters), "local" = field's own coordinate space
5. **Drawing Primitives:** Data-driven, JSON-serializable building block shared by compound bodies and direct drawings

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `_reference/field_calibrator.py` | Core coordinate transformation - copy and extend |
| `_reference/display_toolbox.py` | Drawing primitives reference |
| `_reference/toolbox_display_server.py` | Server architecture reference |
| `_reference/display_client.py` | Client API reference |

### Technical Decisions

1. **Entity naming:** `RigidBody` (not Robot) - supports robots, payloads, any tracked object
2. **Command protocol:** JSON over TCP, newline-delimited, structure mirrors YAML for easy conversion
3. **Command-Field binding:** Every command specifies target field; all coordinates in command interpreted in that field's system
4. **Persistence:** Server holds state in memory only; explicit `dump_scene` command to serialize to YAML
5. **MoCap:** Optional module, lazy-loaded only when tracking features are used
6. **Logging:** Dual-sink to stdout/stderr AND /var/log file
7. **Modularity:** Co-locate command handlers with toolbox methods they wrap
8. **Color system:** Unified RGBA format with flexible multi-format parsing (hex, RGB, RGBA, float, CSV)
9. **Drawing primitives:** Data-only, JSON-serializable DrawPrimitive dataclass shared by compound bodies and persistent overlays - no code execution over the wire

### Architecture Decision Records

#### ADR-1: Command-Handler Co-location Pattern
**Decision:** Minimal decorator (`@register_command`)
**Rationale:** Balance of clean code and transparency. Decorator only handles registration, no hidden behavior.
```python
@register_command
def create_rigidbody(scene, name: str, style: dict = None):
    """Create a new rigid body for display."""
    # Implementation
    return {"status": "success", "name": name}
```

#### ADR-2: Single Scene Architecture
**Decision:** Single scene per server instance
**Rationale:** Config YAML lives client-side. Server is a stateless display renderer. Different experiments use different client configs pointing to the same server.
```
Server
+-- Scene (one per server instance)
    +-- FieldCalibrator
    |   +-- Fields: Dict[name, Field]
    |         +-- "screen" (world meters <-> screen pixels)
    |         +-- user-defined fields (world <-> local coords)
    +-- RigidBodies: Dict[name, RigidBody]
    +-- Drawings: Dict[id, Drawing]
```
To "switch" experiments: client sends commands to clear and rebuild scene.

**Field Transform Model:**
- All fields share "world" as common reference (physical meters)
- Each field defines: `world_points` (meters) <-> `local_points` (field-specific)
- Transform chain: `field_A local -> world -> field_B local`

#### ADR-3: Orientation Transform in FieldCalibrator
**Decision:** Add `transform_orientation()` method directly to FieldCalibrator
**Rationale:** Critical transformation belongs in the core transform class. Single source of truth for all coordinate conversions.
```python
def transform_orientation(self, field: str, position: tuple,
                          orientation: float, probe_distance: float = 0.1) -> float:
    """Transform orientation via two-point conversion."""
    probe_point = (
        position[0] + probe_distance * cos(orientation),
        position[1] + probe_distance * sin(orientation)
    )
    screen_pos = self.transform_point(field, position)
    screen_probe = self.transform_point(field, probe_point)
    return atan2(screen_probe[1] - screen_pos[1],
                 screen_probe[0] - screen_pos[0])
```

#### ADR-4: YAML <-> Command Bidirectionality
**Decision:** Direct YAML<->dict structure match
**Rationale:** Trivial bidirectional conversion. Command names match YAML keys exactly.
```yaml
# Scene YAML structure
fields:
  experiment:
    world_points: [[1,1], [3,1], [3,2], [1,2]]  # BL, BR, TR, TL (meters)
    local_points: [[0,0], [2,0], [2,1], [0,1]]  # BL, BR, TR, TL (experiment coords)
rigidbodies:
  robot1:
    style: {shape: circle, size: 0.1, color: [255, 0, 0, 200]}  # RGBA (semi-transparent red)
    trajectory:
      enabled: true
      mode: time
      length: 5.0
      color: gradient
      gradient_start: [255, 0, 0, 255]  # Opaque at current position
      gradient_end: [255, 0, 0, 0]      # Fade to transparent
drawings:
  waypoint_1:
    primitive: {type: circle, radius: 0.05, color: [0, 255, 0, 128], filled: true}
    world_x: 1.5
    world_y: 2.0
```
Conversion: `yaml.safe_load()` -> iterate -> generate commands. Inverse: `scene.to_dict()` -> `yaml.dump()`.

#### ADR-5: Renderer Abstraction
**Decision:** Isolate rendering behind `Renderer` interface, pygame as default implementation
**Rationale:** Future flexibility for GPU-accelerated rendering (OpenGL, etc.) without changing core logic.
```python
class Renderer(Protocol):
    def init(self, screen_index: int = 0) -> None: ...  # Always fullscreen
    def get_size(self) -> Tuple[int, int]: ...
    def clear(self, color: Tuple[int, int, int]) -> None: ...
    def draw_circle(self, center, radius, color, border=0) -> None: ...
    def draw_polygon(self, points, color, border=0) -> None: ...
    def draw_line(self, start, end, color, width=1) -> None: ...
    def draw_lines(self, points, color, width=1, closed=False) -> None: ...
    def draw_rect(self, rect, color, border=0) -> None: ...
    def draw_text(self, text, position, color, font_size=24,
                  background=None, angle=0.0) -> None: ...
    def flip(self) -> None: ...
    def quit(self) -> None: ...

class PygameRenderer:
    """Default renderer using pygame. Always fullscreen.
    Includes alpha-blending methods for RGBA support (ADR-8):
      - draw_polygon_alpha(points, color, alpha, border)
      - draw_line_alpha(start, end, color, alpha, width)
      - draw_circle_alpha(center, radius, color, alpha, border)
      - blit_surface(surface, position)  # For pre-rendered backgrounds
    """
```

#### ADR-6: Display Configuration
**Decision:** Always fullscreen, configurable refresh rate, explicit display selection
**Rationale:** Projector use requires fullscreen. Different experiments may need different refresh rates. Multi-monitor setups need explicit display selection.
```yaml
# Server config
display:
  screen_index: 0       # Explicit display selection for multi-monitor
  update_rate: 30       # Hz, configurable
```
**Multi-display approach:**
- SDL2: Uses `xrandr --listmonitors` to get display position, creates borderless (`NOFRAME`) window at that position (stays visible when unfocused)
- SDL1.2: Uses `SDL_VIDEO_FULLSCREEN_DISPLAY` environment variable

#### ADR-7: Optional Orientation with Fallback
**Decision:** `RigidBody.orientation` is `Optional[float]` with last-known fallback
**Rationale:** MoCap usually provides orientation, but some updates may omit it. Styles that need orientation use last known value.
```python
@dataclass
class RigidBody:
    name: str
    position: Optional[Tuple[float, float]] = None
    orientation: Optional[float] = None
    _last_orientation: float = 0.0  # Internal fallback

    # MoCap-driven runtime state (not persisted)
    _mocap_position: Optional[Tuple[float, float]] = None
    _mocap_orientation: Optional[float] = None
    auto_track: bool = False
    tracking_lost: bool = False

    def get_display_position(self) -> Optional[Tuple[float, float]]:
        """MoCap takes priority when auto_track enabled."""
        if self.auto_track and self._mocap_position is not None:
            return self._mocap_position
        return self.position

    def get_effective_orientation(self) -> float:
        """Return best-available orientation for rendering."""
        display = self.get_display_orientation()
        return display if display is not None else self._last_orientation
```
**Rendering behavior:**
- Style requires orientation (arrow, rotated shapes): use `get_effective_orientation()`
- Style doesn't require orientation (circle without arrow): ignore orientation

**Position source priority:** MoCap (when `auto_track=True` and connected) > Manual position > None

#### ADR-8: RGBA Color Format
**Decision:** All colors use RGBA tuple (4 values). Multiple input formats accepted and auto-converted.
**Rationale:** Unifying alpha into the color tuple is more intuitive (standard in graphics APIs) and enables transparency gradients in trajectories.

**Supported input formats (via `parse_color()`):**
| Format | Example | Output |
|--------|---------|--------|
| RGB list/tuple | `[255, 0, 0]` | `(255, 0, 0, 255)` |
| RGBA list/tuple | `[255, 0, 0, 128]` | `(255, 0, 0, 128)` |
| Hex string | `"#FF0000"` or `"#FF000080"` | `(255, 0, 0, 255)` or `(255, 0, 0, 128)` |
| Float RGB | `[1.0, 0.0, 0.0]` | `(255, 0, 0, 255)` |
| Float RGBA | `[1.0, 0.0, 0.0, 0.5]` | `(255, 0, 0, 128)` |
| CSV string | `"255,0,0"` or `"(255, 0, 0)"` | `(255, 0, 0, 255)` |

**Internal representation:** Always `Tuple[int, int, int, int]` (RGBA, 0-255).

**Affected fields:**
- `RigidBodyStyle.color` - shape fill color with transparency
- `RigidBodyStyle.orientation_color` - orientation arrow color
- `TrajectoryStyle.color` - solid color mode (when not "gradient")
- `TrajectoryStyle.gradient_start` - gradient from (supports alpha fade)
- `TrajectoryStyle.gradient_end` - gradient to (supports alpha fade)
- `DrawPrimitive.color` - drawing overlay color

**Removed:** Separate `alpha` field from `RigidBodyStyle` (merged into `color[3]`)

#### ADR-9: Command Submodule Architecture
**Decision:** Commands as extensible submodule with layered structure
**Rationale:** Core commands for researchers (intuitive, fast). User custom commands easy to add.
```
commands/
+-- __init__.py            # Registry + @register_command
+-- base.py                # Base infrastructure (CommandRegistry)
+-- prebuilt/              # Researcher-friendly commands
    +-- __init__.py        # Auto-imports all command modules
    +-- rigidbody_commands.py
    +-- field_commands.py
    +-- scene_commands.py
    +-- debug_commands.py
    +-- asset_commands.py
    +-- mocap_commands.py
    +-- drawing_commands.py
```

**User custom command example:**
```python
from projector_display.commands import register_command

@register_command
def my_custom_display(scene, name: str, special_param: float):
    """Custom command for my experiment."""
    # Implementation
    return {"status": "success"}
```

**Auto-discovery:** Commands module auto-loads all `prebuilt/` commands on import. User commands registered via decorator.

#### ADR-10: Storage & Scene Persistence
**Decision:** XDG-compliant persistent storage with temporary working directory pattern.
**Rationale:** Clean separation between working state (temp) and saved scenes (persistent). Original filenames preserved for user clarity.

**Storage Structure:**
```
~/.local/share/projector_display/           # Persistent storage (XDG_DATA_HOME)
+-- calibration.yaml                        # Global screen calibration (required)
+-- scenes/
    +-- {scene_name}/                       # Saved scene
        +-- scene.yaml                      # Generated from Scene.to_dict()
        +-- images/
            +-- arena.png                   # Original filenames preserved

/tmp/projector_display/{session_id}/        # Ephemeral working directory
+-- images/
    +-- arena.png                           # Temp uploads during session
```

**Workflow:**
1. **Server Start**: Create temp session dir `/tmp/projector_display/{uuid}/`
2. **Working Phase**: Images uploaded to temp `images/` folder
3. **save_scene("name")**: Copy temp folder -> persistent location, generate `scene.yaml`

**Image Upload Protocol:**
```
Client                                      Server
  |                                           |
  |  set_field_background                     |
  |  {field, image: "arena.png",              |
  |   hash: "a1b2...", alpha: 200}            |
  | ----------------------------------------->|
  |                                           | Check: exists? hash match?
  |  Response (one of):                       |
  |  <----------------------------------------|
  |                                           |
  |  Case A: {need_upload: false}             |  # Hash matches
  |  Case B: {need_upload: true,              |  # File not found
  |           reason: "not_found"}            |
  |  Case C: {need_upload: true,              |  # Hash mismatch
  |           reason: "hash_mismatch"}        |
  |                                           |
  |  upload_image {name, data: base64}        |  # If need_upload
  | ----------------------------------------->|
  |  {status: success, action: "created"}     |
  | <-----------------------------------------|
```

**scene.yaml Format:**
```yaml
created: "2026-01-28T12:00:00"
fields:
  experiment:
    world_points: [[0,0], [4,0], [4,3], [0,3]]
    local_points: [[0,1080], [1920,1080], [1920,0], [0,0]]
    background:
      image: arena.png        # Relative to images/ folder
      alpha: 200
rigidbodies:
  go1_1:
    position: [1.5, 2.0]
    orientation: 0.5
    style: {shape: triangle, color: [255,0,0,150], size: 0.2}
    trajectory: {enabled: true, color: gradient, ...}
drawings:
  waypoint:
    primitive: {type: circle, radius: 0.05, color: [0,255,0,200]}
    world_x: 1.5
    world_y: 2.0
```

#### ADR-11: Composable Drawing Primitives
**Decision:** Data-driven `DrawPrimitive` dataclass as the building block for both compound rigid bodies and persistent drawing overlays.
**Rationale:** Enables user-customizable rigid body shapes and direct drawing commands without code execution over the wire. Everything stays JSON/YAML-serializable.

**Two capabilities sharing one building block:**
1. **Compound rigid body** (`shape="compound"`) - shape defined by a list of primitives in body-local coordinates
2. **Direct drawings** - persistent overlays positioned in field coordinates, rendered every frame until removed

**DrawPrimitive types:** CIRCLE, BOX, LINE, POLYGON, TEXT, ARROW

**Coordinate semantics depend on context:**
| Context | Origin | Axes | Scale |
|---------|--------|------|-------|
| Compound body | `(0,0)` = body center | `+x` = orientation direction | `style.size` = pixels per local unit |
| Direct drawing | World meters | World axes | Meters (converted from field at creation) |

**Compound body example:**
```python
# Robot with a body circle and forward-pointing arrow
client.create_rigidbody("custom_bot", style={
    "shape": "compound",
    "size": 0.1,
    "draw_list": [
        {"type": "circle", "x": 0, "y": 0, "radius": 1.0,
         "color": [0, 100, 255, 200], "filled": True},
        {"type": "arrow", "x": 0, "y": 0, "x2": 1.5, "y2": 0,
         "color": [255, 255, 255, 255], "thickness": 3}
    ]
})
```

**Direct drawing example:**
```python
# Draw a circle at position (1.5, 2.0) in field "experiment"
client.draw_circle("marker_1", x=1.5, y=2.0, radius=0.05,
                   color=[0, 255, 0, 200], field="experiment")
```

**Persistence:** Direct drawings persist across frames until explicitly removed via `remove_drawing` or `clear_drawings`. Compound body primitives are part of `RigidBodyStyle` and persist with the rigid body.

**Serialization:** Both `DrawPrimitive` and `Drawing` have `to_dict()`/`from_dict()` for JSON/YAML round-trips. Scene serialization includes drawings.

### Pre-mortem Prevention Measures

Critical safeguards identified through failure analysis:

#### Debug Utility Layers
Two togglable overlay layers for on-demand debugging:
1. **Grid Layer**: Shows coordinate grid over display area
   - Major lines at 1.0m intervals (thicker)
   - Minor lines at 0.1m intervals (thinner, togglable)
   - Coordinate labels at major intersections
   - Origin marker (yellow crosshair)
2. **Field Layer**: Shows boundaries of all registered fields with labels
   - Field boundary polygons (yellow)
   - Corner markers with labels (BL, BR, TR, TL)
   - Field name label inside top-left corner, rotated to match field's top edge orientation

Commands: `toggle_grid_layer`, `toggle_field_layer`, `set_grid_layer`, `set_field_layer`, `configure_grid_layer`

#### Calibration File Integrity (REQUIRED)
**The "screen" field is set via a cached calibration YAML file. This file is REQUIRED - if not present, server cannot start.**

The cache file is immediately synced whenever user sets the 4-corner world<->screen coordinate relationship.

```yaml
# calibration.yaml (cached, auto-synced)
resolution:
  width: 1920
  height: 1080
screen_field:
  world_points: [[0,0], [8,0], [8,6], [0,6]]      # BL, BR, TR, TL (meters)
  local_points: [[0,1080], [1920,1080], [1920,0], [0,0]]  # BL, BR, TR, TL (pixels)
created: "2026-01-27T10:00:00"
```
**Validation on load:** Reject if current resolution doesn't match stored resolution.
**No calibration file:** Server refuses to start with clear error message.

#### Vertex Order Validation
On field registration, validate vertices form counter-clockwise polygon. Warn/reject if clockwise order detected.

#### Error Handling Policy
- **Malformed commands (bad JSON, missing params, invalid values):** Never crash. Log error, return informative error response, continue running.
- **Unhandled exceptions (bugs in command handlers, system errors):** Let them crash the server. Do not attempt recovery. This makes bugs visible immediately.

#### Orientation Safety
- Configurable `probe_distance` (default 0.1m) for two-point orientation transform
- Clamp positions to field bounds before transformation
- **Single render path:** ALL orientation rendering goes through one function that calls `transform_orientation()`

#### Logging & Inspection
- **Log levels:** DEBUG (every command), INFO (state changes), WARN, ERROR
- **`--verbose` flag:** Enable DEBUG logging
- **Inspection commands:** `get_scene` (full state), `get_rigidbody` (single entity)
- **Always respond:** Every command gets a response with status

#### MoCap Safety
- **Non-blocking connect:** 2s timeout, retry in background thread
- **Decoupled rates:** MoCap updates internal state; render loop reads at its own rate
- **Thread-safe:** Use `threading.Lock` for MoCap -> render communication
- **Tracking lost indicator:** Thick red outline on rigid body when MoCap signal lost

#### Thread Safety Model
- **Snapshot pattern:** Render loop works on deep copies (`get_rigidbodies_snapshot()`, `get_fields_snapshot()`, `get_drawings_snapshot()`) to avoid locking during render
- **Single lock:** `threading.Lock` protects all scene state mutations
- **ThreadPoolExecutor:** Command handlers run in thread pool (max 10 workers), auto-cleanup on shutdown

## Project Structure

```
ProjectorDisplay/
+-- _reference/                    # Symlink to old code (read-only)
+-- _bmad-output/                  # BMAD artifacts
+-- external/
|   +-- MocapUtility/              # Git submodule (optional, OptiTrack)
|
+-- projector_display/             # Main package
|   +-- __init__.py                # Package exports
|   +-- server.py                  # Display server entry point (~763 lines)
|   +-- client.py                  # Client library (~736 lines)
|   +-- storage.py                 # Storage manager (ADR-10, ~254 lines)
|   |
|   +-- core/
|   |   +-- __init__.py            # Exports: Scene, RigidBody, Field, DrawPrimitive, Drawing, etc.
|   |   +-- field_calibrator.py    # Copied + extended from reference (~411 lines)
|   |   +-- scene.py               # Scene management (~477 lines)
|   |   +-- rigidbody.py           # RigidBody, RigidBodyStyle, TrajectoryStyle (~356 lines)
|   |   +-- draw_primitive.py      # DrawPrimitive, DrawPrimitiveType, Drawing (ADR-11, ~176 lines)
|   |
|   +-- commands/                  # Command submodule (ADR-9)
|   |   +-- __init__.py            # Registry + @register_command
|   |   +-- base.py                # CommandRegistry class (~134 lines)
|   |   +-- prebuilt/              # Prebuilt commands (researcher-friendly)
|   |       +-- __init__.py        # Auto-imports all command modules
|   |       +-- rigidbody_commands.py  # RigidBody CRUD (~219 lines)
|   |       +-- field_commands.py      # Field management (~250 lines)
|   |       +-- scene_commands.py      # Scene operations + persistence (~390 lines)
|   |       +-- debug_commands.py      # Debug layer toggles (~138 lines)
|   |       +-- asset_commands.py      # Image upload/management (ADR-10, ~303 lines)
|   |       +-- mocap_commands.py      # MoCap integration (~150 lines)
|   |       +-- drawing_commands.py    # Drawing overlays (ADR-11, ~283 lines)
|   |
|   +-- mocap/                     # MoCap integration (optional)
|   |   +-- __init__.py
|   |   +-- tracker.py             # MocapTracker, MocapConfig (~100 lines)
|   |
|   +-- rendering/
|   |   +-- __init__.py
|   |   +-- renderer.py            # Renderer protocol + PygameRenderer (~387 lines)
|   |   +-- primitives.py          # Shape drawing + compound rendering (~574 lines)
|   |   +-- trajectory.py          # Trajectory rendering (~257 lines)
|   |   +-- background.py          # Field background rendering (ADR-10, ~205 lines)
|   |   +-- debug_layers.py        # Grid + field debug overlays
|   |
|   +-- utils/
|       +-- __init__.py
|       +-- logging.py             # Dual-sink logging
|       +-- color.py               # Color parsing (ADR-8, ~196 lines)
|
+-- config/
|   +-- server_config.yaml         # Default server config
|   +-- calibration_example.yaml   # Calibration template
|
+-- examples/
|   +-- basic_usage.py             # Example client usage
|
+-- pyproject.toml                 # Python >3.10, MIT license
```

## Data Model

### Core Entities

#### RigidBody
First-class displayable entity supporting robots, payloads, any tracked object.

**Position sources (priority order):**
1. MoCap-driven (when `auto_track=True` and connected)
2. Manual position (set via commands)
3. None (not yet positioned)

```python
@dataclass
class RigidBody:
    name: str
    position: Optional[Tuple[float, float]] = None      # Manual (world coords, meters)
    orientation: Optional[float] = None                  # Manual (radians)
    _mocap_position: Optional[Tuple[float, float]]       # MoCap-driven (runtime)
    _mocap_orientation: Optional[float]                   # MoCap-driven (runtime)
    auto_track: bool = False
    tracking_lost: bool = False
    mocap_name: Optional[str] = None
    style: RigidBodyStyle
    trajectory_style: TrajectoryStyle
    position_history: deque                              # For trajectory rendering
```

#### RigidBodyStyle
```python
@dataclass
class RigidBodyStyle:
    shape: RigidBodyShape       # CIRCLE, BOX, TRIANGLE, POLYGON, COMPOUND
    size: float = 0.1           # Size in meters
    color: RGBA = (0, 0, 255, 255)
    label: bool = True
    label_offset: (float, float) = (0, -0.2)   # Meters
    orientation_length: float = 0.15            # Arrow length in meters
    orientation_color: RGBA = (255, 255, 255, 255)
    orientation_thickness: int = 2              # Pixels
    polygon_vertices: Optional[List[(float, float)]]  # For POLYGON shape
    draw_list: Optional[List[DrawPrimitive]]           # For COMPOUND shape (ADR-11)
```

**Shape types:**
| Shape | Description | Orientation |
|-------|------------|-------------|
| CIRCLE | Circle with border | No rotation, arrow shows direction |
| BOX | Square, rotated by orientation | Rotated |
| TRIANGLE | Equilateral, points in orientation direction | Rotated |
| POLYGON | Custom vertices, relative to center | Rotated |
| COMPOUND | List of DrawPrimitives in body-local coords | All sub-primitives rotated |

#### TrajectoryStyle
```python
@dataclass
class TrajectoryStyle:
    enabled: bool = True
    mode: str = "time"          # "time" or "distance"
    length: float = 5.0         # Seconds or meters
    style: str = "solid"        # "solid", "dotted", "dashed"
    thickness: int = 2          # Pixels
    color: RGBA | "gradient"    # Solid color or gradient mode
    gradient_start: RGBA        # Near body (RGBA, supports alpha)
    gradient_end: RGBA          # At tail (RGBA, supports alpha fade)
    dot_spacing: float = 0.05   # Meters (dotted)
    dash_length: float = 0.1    # Meters (dashed)
```

#### DrawPrimitive (ADR-11)
```python
class DrawPrimitiveType(Enum):
    CIRCLE, BOX, LINE, POLYGON, TEXT, ARROW

@dataclass
class DrawPrimitive:
    type: DrawPrimitiveType
    x: float = 0.0             # Position / offset
    y: float = 0.0
    x2: float = 0.0            # LINE/ARROW end point
    y2: float = 0.0
    radius: float = 0.05       # CIRCLE
    width: float = 0.1         # BOX
    height: float = 0.1        # BOX
    angle: float = 0.0         # BOX local rotation (radians)
    vertices: Optional[List]   # POLYGON
    text: str = ""             # TEXT
    font_size: int = 24        # TEXT
    color: RGBA = (255, 255, 255, 255)
    thickness: int = 0         # 0=filled, >0=outline width (pixels)
    filled: bool = True
```

#### Drawing
```python
@dataclass
class Drawing:
    """Persistent screen overlay, rendered every frame until removed."""
    id: str
    primitive: DrawPrimitive
    world_x: float = 0.0       # Anchor in world coords
    world_y: float = 0.0
    world_x2: float = 0.0      # LINE/ARROW second endpoint
    world_y2: float = 0.0
```

#### Field
```python
@dataclass
class Field:
    name: str
    world_points: np.ndarray   # 4x2 [BL, BR, TR, TL] in meters
    local_points: np.ndarray   # 4x2 [BL, BR, TR, TL] in local coords
    background_image: Optional[str]     # Image filename
    background_color: Optional[RGB]     # Solid color
    background_alpha: int = 255         # Opacity 0-255
```

## Rendering Pipeline

**Frame render order** (in `ProjectorDisplayServer.render_frame()`):

```
1. Clear screen (background color)
2. Field backgrounds (perspective-warped images / solid colors)
3. Debug layers (grid + field boundaries, if enabled)
4. For each RigidBody (snapshot):
   a. Trajectory (if enabled) - drawn behind body
   b. Body shape (circle/box/triangle/polygon/compound)
   c. Tracking lost indicator (red outline, if MoCap lost)
   d. Orientation arrow
   e. Name label
5. Persistent drawings (snapshot)
6. Flip display
```

**Coordinate transform pipeline:**
```
Field coords (command input)
  --> world_to_screen() via FieldCalibrator
    --> screen pixels (rendering)
```

**Key transform functions:**
- `world_to_screen(x, y)` - Convert world meters to screen pixels via "screen" field
- `meters_to_pixels(meters)` - Approximate scale conversion using world bounds
- `transform_orientation(field, position, orientation)` - Two-point angle transform

## Command Reference

### RigidBody Commands (`rigidbody_commands.py`)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `create_rigidbody` | `name, style?, trajectory?, mocap_name?, auto_track?` | Create rigid body (required before updates) |
| `remove_rigidbody` | `name` | Remove rigid body |
| `update_position` | `name, x, y, orientation?, field?` | Update position (auto-creates if missing) |
| `update_style` | `name, shape?, size?, color?, label?, ...` | Update visualization style |
| `update_trajectory` | `name, enabled?, mode?, length?, style?, ...` | Update trajectory settings |
| `get_rigidbody` | `name` | Inspect state (includes runtime info) |
| `list_rigidbodies` | - | List all rigid body names |

### Field Commands (`field_commands.py`)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `create_field` | `name, world_points, local_points` | Register coordinate frame |
| `remove_field` | `name` | Remove field (except "screen") |
| `list_fields` | - | List all field names |
| `get_field` | `name` | Field info with points |
| `set_field_background` | `field, image, alpha?` | Set image background (ADR-10) |
| `remove_field_background` | `field` | Clear background |
| `set_field_background_color` | `field, color, alpha?` | Set solid color background |

### Drawing Commands (`drawing_commands.py`, ADR-11)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `draw_circle` | `id, x, y, radius, color?, field?, filled?, thickness?` | Persistent circle overlay |
| `draw_box` | `id, x, y, width, height, color?, field?, filled?, thickness?, angle?` | Persistent box overlay |
| `draw_line` | `id, x1, y1, x2, y2, color?, thickness?, field?` | Persistent line overlay |
| `draw_arrow` | `id, x1, y1, x2, y2, color?, thickness?, field?` | Persistent arrow overlay |
| `draw_polygon` | `id, vertices, color?, field?, filled?, thickness?` | Persistent polygon overlay |
| `draw_text` | `id, x, y, text, color?, font_size?, field?` | Persistent text overlay |
| `remove_drawing` | `id` | Remove a drawing by ID |
| `list_drawings` | - | List all drawing IDs |
| `clear_drawings` | - | Remove all drawings |

### Scene Commands (`scene_commands.py`)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `clear_scene` | - | Remove all rigid bodies (keep fields) |
| `clear_all` | - | Remove everything except "screen" field |
| `dump_scene` | - | Export scene state as dict |
| `get_scene` | - | Full scene state inspection |
| `load_scene` | `scene_data` | Restore scene from dict |
| `status` | - | Server status (MoCap, fields, bodies) |
| `save_scene` | `name` | Save to persistent storage (ADR-10) |
| `load_scene_from_file` | `name` | Load from persistent storage |
| `list_saved_scenes` | - | List saved scene names |
| `delete_saved_scene` | `name` | Delete saved scene |

### Debug Commands (`debug_commands.py`)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `toggle_grid_layer` | - | Toggle grid visibility |
| `toggle_field_layer` | - | Toggle field boundaries |
| `set_grid_layer` | `enabled` | Explicitly set grid state |
| `set_field_layer` | `enabled` | Explicitly set field state |
| `configure_grid_layer` | `show_minor?, major_color?, minor_color?` | Configure grid appearance |
| `get_grid_settings` | - | Get current grid settings |

### Asset Commands (`asset_commands.py`, ADR-10)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `check_image` | `name, hash` | Check if image exists with matching hash |
| `upload_image` | `name, data` | Upload base64-encoded image |
| `list_images` | - | List uploaded image names |
| `delete_image` | `name` | Delete uploaded image |

### MoCap Commands (`mocap_commands.py`)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `set_mocap` | `ip?, port?, enabled?` | Configure MoCap connection |
| `enable_mocap` | - | Enable MoCap tracking |
| `disable_mocap` | - | Disable MoCap tracking |
| `get_mocap_status` | - | Connection and tracking status |
| `get_mocap_bodies` | - | List available MoCap bodies |
| `set_auto_track` | `name, mocap_name?, enabled?` | Configure per-body tracking |
| `enable_tracking` | `name` | Enable tracking for body |
| `disable_tracking` | `name` | Disable tracking for body |

## Client API

The `DisplayClient` class provides a Python API mirroring all server commands.

### Connection
```python
from projector_display.client import DisplayClient

# Context manager (auto-connect/disconnect)
with DisplayClient("localhost", 9999) as client:
    client.create_rigidbody("robot1", style={"shape": "circle", "size": 0.1})
    client.update_position("robot1", 1.0, 2.0, field="experiment")

# Manual connection
client = DisplayClient("localhost", 9999)
client.connect()
# ... use client ...
client.disconnect()
```

### Method Categories

**RigidBody:** `create_rigidbody`, `remove_rigidbody`, `update_position`, `update_style`, `update_trajectory`, `get_rigidbody`, `list_rigidbodies`

**Field:** `create_field`, `remove_field`, `list_fields`, `get_field`

**Drawing (ADR-11):** `draw_circle`, `draw_box`, `draw_line`, `draw_arrow`, `draw_polygon`, `draw_text`, `remove_drawing`, `list_drawings`, `clear_drawings`

**Scene:** `clear_scene`, `clear_all`, `dump_scene`, `get_scene`, `load_scene`, `status`

**Storage (ADR-10):** `save_scene`, `load_scene_from_file`, `list_saved_scenes`, `delete_saved_scene`

**Assets (ADR-10):** `check_image`, `upload_image`, `list_images`, `delete_image`, `set_field_background` (high-level: handles hash check + upload + assign), `remove_field_background`

**Debug:** `toggle_grid_layer`, `toggle_field_layer`, `set_grid_layer`, `set_field_layer`, `configure_grid_layer`, `get_grid_settings`

**MoCap:** `set_mocap`, `enable_mocap`, `disable_mocap`, `get_mocap_status`, `get_mocap_bodies`, `set_auto_track`, `enable_tracking`, `disable_tracking`

## Server Architecture

### Threading Model

```
Main Thread (render loop)
  +-- 30 Hz render cycle
  +-- pygame event handling (keyboard, window)
  +-- Reads snapshots of scene state

Socket Server Thread (daemon)
  +-- Accepts TCP connections
  +-- Spawns handler per client

Client Handler Threads (ThreadPoolExecutor, max 10)
  +-- Reads JSON commands
  +-- Executes via CommandRegistry
  +-- Returns JSON responses

MoCap Thread (daemon, optional)
  +-- 30 Hz polling
  +-- Updates _mocap_position on RigidBodies
  +-- Detects tracking loss
```

### Command Execution Flow

```
Client sends JSON over TCP
    |
Server._handle_client() reads newline-delimited message
    |
Server._process_command() extracts "action" + params
    |
CommandRegistry.execute(action, scene, **params)
    |
Handler function executes (mutates scene under lock)
    |
Response dict returned, JSON-encoded, sent back
    |
Client receives response
```

### Initialization Sequence

1. Parse CLI arguments (`--config`, `--calibration`, `--verbose`, `--port`, `--host`)
2. Initialize storage manager (session temp dir)
3. Load server config (YAML)
4. Load calibration (creates "screen" field) - **REQUIRED, exits if missing**
5. Initialize PygameRenderer (fullscreen on target display)
6. Register all commands (auto-import `prebuilt/`)
7. Start socket server thread (daemon)
8. Enter render loop

### Shutdown

- Graceful on SIGTERM/SIGINT (first signal)
- Force exit on second signal
- Cleanup: socket close, thread pool shutdown, pygame quit, storage session cleanup

### Default Settings

| Setting | Default |
|---------|---------|
| Port | 9999 |
| Host | 0.0.0.0 |
| FPS | 30 |
| Background color | Black (0, 0, 0) |
| Screen index | 0 |

## Implementation Plan

### Tasks

#### Phase 1: Project Setup
- [x] **Task 1.1:** Create project structure and pyproject.toml
- [x] **Task 1.2:** Initialize package structure with __init__.py files
- [x] **Task 1.3:** Add MocapUtility as external dependency

#### Phase 2: Core Layer
- [x] **Task 2.1:** Copy and extend FieldCalibrator (`world_points`/`local_points` terminology, `transform_orientation()`)
- [x] **Task 2.2:** Implement RigidBody, RigidBodyStyle, TrajectoryStyle with RGBA colors (ADR-8)
- [x] **Task 2.3:** Implement Scene management (thread-safe, snapshot-based)

#### Phase 3: Rendering Layer
- [x] **Task 3.1:** Implement Renderer protocol and PygameRenderer (fullscreen, multi-display, alpha methods)
- [x] **Task 3.2:** Implement shape primitives (circle, box, triangle, polygon) with RGBA + rotation
- [x] **Task 3.3:** Implement trajectory rendering (solid, dotted, dashed with RGBA gradients)
- [x] **Task 3.4:** Implement debug layers (GridLayer with minor/major lines, FieldLayer with rotated labels)

#### Phase 4: Commands Infrastructure
- [x] **Task 4.1:** Implement command registry and `@register_command` decorator
- [x] **Task 4.2:** Setup commands module with auto-discovery

#### Phase 5: Core Commands
- [x] **Task 5.1:** Implement RigidBody commands (create, remove, update_position, update_style, update_trajectory, get, list)
- [x] **Task 5.2:** Implement Field commands (create, remove, list, get, backgrounds)
- [x] **Task 5.3:** Implement Scene commands (clear, dump, get, load, save, status)
- [x] **Task 5.4:** Implement Debug commands (toggle, set, configure grid)

#### Phase 6: Server
- [x] **Task 6.1:** Implement display server (config loading, TCP socket, render loop, command dispatch, signal handling)
- [x] **Task 6.2:** Add MoCap integration (lazy-load, background polling, per-body tracking, tracking lost)

#### Phase 7: Client Library
- [x] **Task 7.1:** Implement DisplayClient (socket connection, all command methods, context manager, auto-reconnect, message buffering)

#### Phase 8: Utilities & Config
- [x] **Task 8.1:** Implement dual-sink logging
- [x] **Task 8.2:** Create default server config
- [x] **Task 8.3:** Implement color parsing utility (hex, RGB, RGBA, float, CSV)

#### Phase 9: Examples
- [x] **Task 9.1:** Create basic usage example

#### Phase 10: Storage & Assets (ADR-10)
- [x] **Task 10.1:** Implement StorageManager (XDG-compliant, session temp, persistent scenes)
- [x] **Task 10.2:** Implement asset transfer commands (check_image, upload_image, list_images, delete_image)
- [x] **Task 10.3:** Implement field background commands (set_field_background, remove, solid color)
- [x] **Task 10.4:** Implement field background rendering (perspective warp via OpenCV, caching)
- [x] **Task 10.5:** Implement scene persistence (save_scene, load_scene_from_file)
- [x] **Task 10.6:** Add client-side image upload helper (hash check, conditional upload)

#### Phase 11: Composable Drawing Primitives (ADR-11)
- [x] **Task 11.1:** Create `DrawPrimitive`, `DrawPrimitiveType`, `Drawing` dataclasses with serialization
- [x] **Task 11.2:** Add `COMPOUND` to `RigidBodyShape`, `draw_list` to `RigidBodyStyle`
- [x] **Task 11.3:** Implement compound body rendering (`draw_compound`, `_draw_single_primitive`, body-local transform)
- [x] **Task 11.4:** Add drawings storage to Scene (CRUD, snapshots, serialization)
- [x] **Task 11.5:** Add drawing rendering to server render loop
- [x] **Task 11.6:** Create drawing commands (draw_circle, draw_box, draw_line, draw_arrow, draw_polygon, draw_text, remove, list, clear)
- [x] **Task 11.7:** Add client drawing convenience methods
- [x] **Task 11.8:** Update core exports (`__init__.py`)

#### Phase 12: Polish
- [x] **Task 12.1:** Tracking lost indicator (red outline for all shapes including compound)
- [x] **Task 12.2:** Field layer label positioning (inside top-left corner, rotated to match field edge)
- [x] **Task 12.3:** Text rotation support in renderer (`angle` parameter)

### Acceptance Criteria

#### Core Functionality
- [x] **AC-1:** Calibration file with world_points/local_points loads correctly, coordinate transforms work
- [x] **AC-2:** RigidBody at world position renders at correct screen position
- [x] **AC-3:** Orientation arrow correctly transformed via two-point method
- [x] **AC-4:** Missing orientation falls back to last known value

#### Commands & Protocol
- [x] **AC-5:** JSON command creates RigidBody and returns success response
- [x] **AC-6:** Malformed JSON returns error response, server continues (no crash)
- [x] **AC-7:** `dump_scene` returns dict that can recreate identical scene via `load_scene`

#### Field Management
- [x] **AC-8:** Clockwise vertex order produces warning/rejection
- [x] **AC-9:** Custom field coordinates transform through field -> world -> screen chain

#### Debug Layers
- [x] **AC-10:** `toggle_grid_layer` toggles grid overlay with major/minor lines and labels
- [x] **AC-11:** Field layer shows all field boundaries with rotated name labels

#### Client Library
- [x] **AC-12:** DisplayClient sends commands and receives responses
- [x] **AC-13:** Context manager cleanly connects and disconnects

#### Error Handling
- [x] **AC-14:** Unhandled exception in command handler crashes server (visible bugs)
- [x] **AC-15:** Malformed command returns error, server continues

#### Storage & Assets (ADR-10)
- [x] **AC-16:** Data directory created automatically on first use
- [x] **AC-17:** Duplicate image upload (same hash) skips transfer
- [x] **AC-18:** Changed image (hash mismatch) warns and replaces
- [x] **AC-19:** `save_scene` persists scene.yaml and images
- [x] **AC-20:** Field background perspective-warped to fit field quadrilateral
- [x] **AC-21:** `load_scene_from_file` reconstructs full scene

#### Drawing Primitives (ADR-11)
- [x] **AC-22:** Compound rigid body renders multiple sub-primitives that move and rotate with body
- [x] **AC-23:** Direct drawing commands create persistent overlays in field coordinates
- [x] **AC-24:** `remove_drawing` and `clear_drawings` correctly remove overlays
- [x] **AC-25:** DrawPrimitive serialization round-trips correctly via to_dict/from_dict
- [x] **AC-26:** Scene serialization includes drawings and compound body draw_lists
- [x] **AC-27:** Existing simple shapes (circle, box, triangle, polygon) remain backwards-compatible

## Additional Context

### Dependencies

- Python >3.10 (required for MocapUtility compatibility)
- pygame >=2.0.0
- OpenCV (cv2) >=4.0.0 - for FieldCalibrator perspective transforms and background warp
- PyYAML >=6.0 - for configuration and scene serialization
- numpy >=1.20.0 - for coordinate transforms
- xrandr - system dependency for multi-display positioning (Linux)
- MocapUtility - external directory from `https://github.com/chkxw/MocapUtility.git` (optional, OptiTrack)

### Testing Strategy

- **Unit tests:** Field transforms, orientation conversion, command parsing, color parsing, serialization round-trips (non-graphical)
- **Interactive visual tests:** Since graphics require human verification, implement an interactive test suite that:
  - Displays a specific visual behavior
  - Prompts user: "Does this look correct? [y/n]"
  - Covers all primitives, trajectory styles, compound bodies, orientation transforms, debug layers
- **Integration tests:** Client-server communication, scene serialization, drawing persistence (non-graphical)

### Notes

- Reference repo at `../box_push_deploy/shared/` should remain untouched for functionality comparison
- Orientation transformation is critical fix - all angle-dependent rendering must use point conversion
- Scene dump produces YAML that can be converted back to commands and sent to recreate the scene
- **Terminology update for FieldCalibrator:** `real_points` -> `world_points`, `virtual_points` -> `local_points`. "world" = common reference (meters), "local" = field-specific coords
- Drawing primitives are data-only - no code execution over the wire, preserving the system's security model
- All colors internally RGBA; `parse_color()` in `utils/color.py` handles all input format conversions
