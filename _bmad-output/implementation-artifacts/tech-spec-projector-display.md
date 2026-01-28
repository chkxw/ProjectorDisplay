---
title: 'Projector Display Utility'
slug: 'projector-display'
created: '2026-01-27'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9]
tech_stack: [python>3.10, pygame, opencv, pyyaml]
files_to_modify: [
  "projector_display/__init__.py",
  "projector_display/server.py",
  "projector_display/client.py",
  "projector_display/core/__init__.py",
  "projector_display/core/field_calibrator.py",
  "projector_display/core/scene.py",
  "projector_display/core/rigidbody.py",
  "projector_display/commands/__init__.py",
  "projector_display/commands/base.py",
  "projector_display/commands/prebuilt/rigidbody_commands.py",
  "projector_display/commands/prebuilt/field_commands.py",
  "projector_display/commands/prebuilt/scene_commands.py",
  "projector_display/commands/prebuilt/debug_commands.py",
  "projector_display/rendering/__init__.py",
  "projector_display/rendering/renderer.py",
  "projector_display/rendering/primitives.py",
  "projector_display/rendering/trajectory.py",
  "projector_display/rendering/debug_layers.py",
  "projector_display/utils/__init__.py",
  "projector_display/utils/logging.py",
  "config/server_config.yaml",
  "pyproject.toml"
]
code_patterns: [dataclasses, protocol, decorator-registry, json-tcp]
test_patterns: []
---

# Tech-Spec: Projector Display Utility

**Created:** 2026-01-27

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
- Orientations transformed via point conversion (two points → derive angle)

### Scope

**In Scope:**
- Scene architecture (create, dump to YAML, no auto-persist)
- RigidBody management (explicit creation required)
- Multiple Fields per Scene with vertex convention: `[BL, BR, TR, TL]` (counter-clockwise from bottom-left)
- Drawing primitives: Circle, Box, Triangle, Polygon, Trajectory
- Proper orientation transformation via point conversion
- JSON/TCP commands with YAML-mirroring structure
- Commands specify target field for coordinate interpretation
- Co-located command handlers with toolbox methods
- Dual-sink logging (stdout/stderr + /var/log)
- Optional MoCap integration (lazy-loaded when needed)
- Python client library
- Debug utility layers: togglable grid layer + experiment field layer
- State inspection commands: `get_scene`, `get_rigidbody`

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
- `field_calibrator.py` - Coordinate transformation (350 lines) - **COPY AND EXTEND** (add orientation transform, update terminology: `real_points` → `world_points`, `virtual_points` → `local_points`)

**Key Design Decisions:**
1. **Vertex Order Convention:** `[Bottom-Left, Bottom-Right, Top-Right, Top-Left]` - counter-clockwise from origin
2. **Coordinate Fields:** Each field maps between world coords (common reference, meters) and local coords (field-specific: pixels, experiment units, etc.)
3. **Orientation Bug Fix:** Must transform orientation via two-point conversion, not direct use
4. **Terminology:** "world" = common reference frame (meters), "local" = field's own coordinate space

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

### Architecture Decision Records

#### ADR-1: Command-Handler Co-location Pattern
**Decision:** Minimal decorator (`@register_command`)
**Rationale:** Balance of clean code and transparency. Decorator only handles registration, no hidden behavior.
```python
@register_command
def create_rigidbody(self, name: str, style: dict = None):
    """Create a new rigid body for display."""
    # Implementation
    return {"status": "success", "name": name}
```

#### ADR-2: Single Scene Architecture
**Decision:** Single scene per server instance
**Rationale:** Config YAML lives client-side. Server is a stateless display renderer. Different experiments use different client configs pointing to the same server.
```
Server
└── Scene (one per server instance)
    ├── FieldCalibrator
    │   └── Fields: Dict[name, Field]
    │         ├── "screen" (world meters ↔ screen pixels)
    │         └── user-defined fields (world ↔ local coords)
    └── RigidBodies: Dict[name, RigidBody]
```
To "switch" experiments: client sends commands to clear and rebuild scene.

**Field Transform Model:**
- All fields share "world" as common reference (physical meters)
- Each field defines: `world_points` (meters) ↔ `local_points` (field-specific)
- Transform chain: `field_A local → world → field_B local`

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

#### ADR-4: YAML ↔ Command Bidirectionality
**Decision:** Direct YAML↔dict structure match
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
```
Conversion: `yaml.safe_load()` → iterate → generate commands. Inverse: `scene.to_dict()` → `yaml.dump()`.

#### ADR-5: Renderer Abstraction
**Decision:** Isolate rendering behind `Renderer` interface, pygame as default implementation
**Rationale:** Future flexibility for GPU-accelerated rendering (OpenGL, etc.) without changing core logic.
```python
class Renderer(Protocol):
    def init(self, screen_index: int = 0) -> None: ...  # Always fullscreen
    def get_size(self) -> Tuple[int, int]: ...
    def clear(self, color: Tuple[int, int, int]) -> None: ...
    def draw_circle(self, center: Tuple[int, int], radius: int, color: Tuple[int, int, int, int]) -> None: ...  # RGBA
    def draw_polygon(self, points: List[Tuple[int, int]], color: Tuple[int, int, int, int]) -> None: ...  # RGBA
    def draw_line(self, start: Tuple[int, int], end: Tuple[int, int], color: Tuple[int, int, int, int], width: int) -> None: ...  # RGBA
    def flip(self) -> None: ...

class PygameRenderer(Renderer):
    """Default renderer using pygame. Always fullscreen. Uses pygame.Surface with SRCALPHA for transparency."""
    ...
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

#### ADR-7: Optional Orientation with Fallback
**Decision:** `RigidBody.orientation` is `Optional[float]` with last-known fallback
**Rationale:** MoCap usually provides orientation, but some updates may omit it. Styles that need orientation use last known value.
```python
@dataclass
class RigidBody:
    name: str
    position: Tuple[float, float]
    orientation: Optional[float] = None
    _last_orientation: float = 0.0  # Internal fallback

    def update_position(self, x: float, y: float, orientation: Optional[float] = None):
        self.position = (x, y)
        if orientation is not None:
            self.orientation = orientation
            self._last_orientation = orientation
        else:
            self.orientation = None

    def get_effective_orientation(self) -> float:
        """Return orientation for rendering."""
        return self.orientation if self.orientation is not None else self._last_orientation
```
**Rendering behavior:**
- Style requires orientation (arrow, rotated shapes): use `get_effective_orientation()`
- Style doesn't require orientation (circle without arrow): ignore orientation

#### ADR-8: RGBA Color Format
**Decision:** All colors use RGBA tuple (4 values). RGB (3 values) accepted and auto-converted to RGBA with alpha=255.
**Rationale:** Unifying alpha into the color tuple is more intuitive (standard in graphics APIs) and enables transparency gradients in trajectories.

**Color format:**
- `[R, G, B]` → auto-converted to `[R, G, B, 255]` (fully opaque)
- `[R, G, B, A]` → used directly (A: 0=transparent, 255=opaque)

**Affected fields:**
- `RigidBodyStyle.color` - shape fill color with transparency
- `RigidBodyStyle.orientation_color` - orientation arrow color
- `TrajectoryStyle.color` - solid color mode (when not "gradient")
- `TrajectoryStyle.gradient_start` - gradient from (supports alpha fade)
- `TrajectoryStyle.gradient_end` - gradient to (supports alpha fade)

**Example - fade-out trajectory:**
```yaml
trajectory:
  color: gradient
  gradient_start: [255, 0, 0, 255]   # Opaque red at current position
  gradient_end: [255, 0, 0, 0]       # Fully transparent at trail end
```

**Removed:** Separate `alpha` field from `RigidBodyStyle` (merged into `color[3]`)

#### ADR-9: Command Submodule Architecture
**Decision:** Commands as extensible submodule with layered structure
**Rationale:** Core commands for researchers (intuitive, fast). Future pygame-level commands separate. User custom commands easy to add.
```
commands/
├── __init__.py            # Registry + @register_command
├── base.py                # Base infrastructure
├── prebuilt/              # Researcher-friendly commands
│   ├── rigidbody_commands.py
│   ├── field_commands.py
│   ├── scene_commands.py
│   └── debug_commands.py
└── pygame/                # Future: low-level pygame commands
    └── __init__.py
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

### Pre-mortem Prevention Measures

Critical safeguards identified through failure analysis:

#### Debug Utility Layers
Two togglable overlay layers for on-demand debugging:
1. **Grid Layer**: Shows coordinate grid over display area
2. **Experiment Field Layer**: Shows boundaries of all registered fields with labels

Commands: `toggle_grid_layer`, `toggle_field_layer`

#### Calibration File Integrity (REQUIRED)
**The "screen" field is set via a cached calibration YAML file. This file is REQUIRED - if not present, server cannot start.**

The cache file is immediately synced whenever user sets the 4-corner world↔screen coordinate relationship.

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
- **Malformed commands (bad JSON, missing params, invalid values):** Never crash. Log error, return informative error response (no strict schema, but must help user identify the problem), continue running.
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
- **Thread-safe:** Use `threading.Lock` or `queue.Queue` for MoCap → render communication

## Project Structure

```
ProjectorDisplay/
├── _reference/                    # Symlink to old code (read-only)
├── _bmad-output/                  # BMAD artifacts
├── MocapUtility/                  # Git submodule (optional)
│
├── projector_display/             # Main package
│   ├── __init__.py
│   ├── server.py                  # Display server entry point
│   ├── client.py                  # Client library
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── field_calibrator.py    # Copied + extended from reference
│   │   ├── scene.py               # Scene management
│   │   └── rigidbody.py           # RigidBody dataclass + styles
│   │
│   ├── commands/                  # Command submodule
│   │   ├── __init__.py            # Registry + @register_command
│   │   ├── base.py                # Base command infrastructure
│   │   ├── prebuilt/              # Prebuilt commands (researcher-friendly)
│   │   │   ├── __init__.py
│   │   │   ├── rigidbody_commands.py
│   │   │   ├── field_commands.py
│   │   │   ├── scene_commands.py
│   │   │   └── debug_commands.py
│   │   └── pygame/                # Future: low-level pygame commands
│   │       └── __init__.py
│   │
│   ├── rendering/
│   │   ├── __init__.py
│   │   ├── renderer.py            # Renderer protocol + PygameRenderer
│   │   ├── primitives.py          # Shape drawing
│   │   ├── trajectory.py          # Trajectory rendering
│   │   └── debug_layers.py        # Grid + field overlay
│   │
│   └── utils/
│       ├── __init__.py
│       └── logging.py             # Dual-sink logging
│
├── config/
│   └── server_config.yaml         # Default server config
│
├── examples/
│   └── basic_usage.py             # Example client usage
│
└── pyproject.toml                 # Python >3.10
```

## Implementation Plan

### Tasks

#### Phase 1: Project Setup
- [ ] **Task 1.1:** Create project structure and pyproject.toml
  - File: `pyproject.toml`
  - Action: Define project metadata, Python >3.10 requirement, dependencies (pygame, opencv-python, pyyaml)
  - Notes: Include dev dependencies for testing

- [ ] **Task 1.2:** Initialize package structure with __init__.py files
  - Files: All `__init__.py` files in package structure
  - Action: Create empty/minimal init files to establish package hierarchy
  - Notes: `projector_display/__init__.py` should expose main classes

- [ ] **Task 1.3:** Add MocapUtility as git submodule
  - Action: `git submodule add https://github.com/chkxw/MocapUtility.git MocapUtility`
  - Notes: Optional dependency, lazy-loaded

#### Phase 2: Core Layer
- [ ] **Task 2.1:** Copy and extend FieldCalibrator
  - File: `projector_display/core/field_calibrator.py`
  - Action: Copy from `_reference/field_calibrator.py`, rename `real_points` → `world_points`, `virtual_points` → `local_points`, add `transform_orientation()` method
  - Notes: Critical - this is the foundation of all coordinate transforms

- [ ] **Task 2.2:** Implement RigidBody and styles
  - File: `projector_display/core/rigidbody.py`
  - Action: Create `RigidBody` dataclass with position, optional orientation, fallback logic. Create `RigidBodyStyle` and `TrajectoryStyle` dataclasses
  - Notes: Reference `_reference/display_toolbox.py` for style fields
  - **Color format (ADR-8):** All colors are RGBA tuples. RGB input auto-converts to RGBA with alpha=255.
    - `RigidBodyStyle.color`: RGBA for shape fill (no separate alpha field)
    - `TrajectoryStyle.gradient_start/end`: RGBA for opacity fade support
  - **Trajectory modes:**
    - `mode: time, length: 5.0` = show all positions from last 5 seconds
    - `mode: distance, length: 1.0` = show trajectory of fixed 1 meter length

- [ ] **Task 2.3:** Implement Scene management
  - File: `projector_display/core/scene.py`
  - Action: Create `Scene` class holding FieldCalibrator and RigidBodies dict. Implement `to_dict()` for YAML serialization
  - Notes: Single scene per server instance

#### Phase 3: Rendering Layer
- [ ] **Task 3.1:** Implement Renderer protocol and PygameRenderer
  - File: `projector_display/rendering/renderer.py`
  - Action: Define `Renderer` Protocol, implement `PygameRenderer` with fullscreen init, draw methods, flip
  - Notes: Always fullscreen, explicit screen_index

- [ ] **Task 3.2:** Implement shape primitives
  - File: `projector_display/rendering/primitives.py`
  - Action: Implement `draw_circle`, `draw_box`, `draw_triangle`, `draw_polygon` with rotation support. ALL must use transformed orientation via single render path
  - Notes: Reference `_reference/display_toolbox.py` draw methods

- [ ] **Task 3.3:** Implement trajectory rendering
  - File: `projector_display/rendering/trajectory.py`
  - Action: Implement trajectory drawing with solid/dotted/dashed styles, gradient support
  - Notes: History trails only for v1

- [ ] **Task 3.4:** Implement debug layers
  - File: `projector_display/rendering/debug_layers.py`
  - Action: Implement `GridLayer` and `FieldLayer` classes, togglable overlay rendering
  - Notes: Grid shows world coordinates, FieldLayer shows all registered field boundaries

#### Phase 4: Commands Infrastructure
- [ ] **Task 4.1:** Implement command registry and decorator
  - File: `projector_display/commands/base.py`
  - Action: Create `CommandRegistry` class, `@register_command` decorator that adds to registry
  - Notes: Decorator only registers, no hidden behavior

- [ ] **Task 4.2:** Setup commands module with auto-discovery
  - File: `projector_display/commands/__init__.py`
  - Action: Export `register_command`, auto-import all `core/` commands on module load
  - Notes: Make custom command registration easy

#### Phase 5: Core Commands
- [ ] **Task 5.1:** Implement RigidBody commands
  - File: `projector_display/commands/prebuilt/rigidbody_commands.py`
  - Action: Implement `create_rigidbody`, `remove_rigidbody`, `update_position`, `update_style`, `update_trajectory`, `get_rigidbody`
  - Notes: All position commands must specify `field` parameter

- [ ] **Task 5.2:** Implement Field commands
  - File: `projector_display/commands/prebuilt/field_commands.py`
  - Action: Implement `create_field`, `remove_field`, `list_fields`
  - Notes: Validate vertex order on create (counter-clockwise)

- [ ] **Task 5.3:** Implement Scene commands
  - File: `projector_display/commands/prebuilt/scene_commands.py`
  - Action: Implement `clear_scene`, `dump_scene`, `get_scene`, `load_calibration`
  - Notes: `dump_scene` returns YAML-serializable dict

- [ ] **Task 5.4:** Implement Debug commands
  - File: `projector_display/commands/prebuilt/debug_commands.py`
  - Action: Implement `toggle_grid_layer`, `toggle_field_layer`
  - Notes: Simple boolean toggles

#### Phase 6: Server
- [ ] **Task 6.1:** Implement display server
  - File: `projector_display/server.py`
  - Action: Create main server with: config loading, socket listener (JSON/TCP), render loop, command dispatch, signal handling
  - Notes: Reference `_reference/toolbox_display_server.py` for architecture. Never crash on bad commands.

- [ ] **Task 6.2:** Add MoCap integration (optional)
  - File: `projector_display/server.py` (or separate module)
  - Action: Lazy-load MocapUtility, non-blocking connect with 2s timeout, thread-safe position updates
  - Notes: Only initialize if MoCap features are used

#### Phase 7: Client Library
- [ ] **Task 7.1:** Implement client library
  - File: `projector_display/client.py`
  - Action: Create `DisplayClient` class with socket connection, command methods mirroring server commands, context manager support
  - Notes: Reference `_reference/display_client.py`

#### Phase 8: Utilities & Config
- [ ] **Task 8.1:** Implement dual-sink logging
  - File: `projector_display/utils/logging.py`
  - Action: Create logging setup function with stdout/stderr AND file output, configurable log levels, `--verbose` support
  - Notes: Log to `/var/log/projector_display.log` if writable, else fallback to `/tmp/projector_display.log`

- [ ] **Task 8.2:** Create default server config
  - File: `config/server_config.yaml`
  - Action: Create template config with display settings, socket settings, logging settings
  - Notes: Document all options with comments

#### Phase 9: Examples & Documentation
- [ ] **Task 9.1:** Create basic usage example
  - File: `examples/basic_usage.py`
  - Action: Demonstrate client connection, creating fields, creating rigid bodies, position updates
  - Notes: Should be runnable standalone

#### Phase 10: Interactive Visual Testing
- [ ] **Task 10.1:** Create interactive visual test suite
  - File: `projector_display/tests/visual_tests.py`
  - Action: Implement interactive test runner that displays visual behaviors and prompts user for verification
  - Tests to include:
    - All shape primitives (circle, box, triangle, polygon)
    - Orientation arrows at various angles
    - Trajectory rendering (time mode, distance mode, styles)
    - Debug layers (grid, field boundaries)
    - Coordinate transform verification (known positions)
  - Notes: Run with `python -m projector_display.tests.visual_tests`

### Acceptance Criteria

#### Core Functionality
- [ ] **AC-1:** Given a calibration file with world_points and local_points, when the server loads it, then coordinate transforms work correctly between world and screen coordinates
- [ ] **AC-2:** Given a RigidBody with position (1.0, 2.0) in world coords, when rendered, then it appears at the correct screen position matching the calibration
- [ ] **AC-3:** Given a RigidBody with orientation π/4, when rendered with orientation arrow, then the arrow direction is correctly transformed via two-point method
- [ ] **AC-4:** Given orientation not provided in update, when style requires orientation, then last known orientation is used

#### Commands & Protocol
- [ ] **AC-5:** Given a JSON command `{"action": "create_rigidbody", "params": {"name": "robot1"}}`, when sent to server, then RigidBody is created and success response returned
- [ ] **AC-6:** Given a malformed JSON command, when sent to server, then error response is returned and server continues running (no crash)
- [ ] **AC-7:** Given `dump_scene` command, when executed, then returned dict can be YAML-serialized and used to recreate identical scene

#### Field Management
- [ ] **AC-8:** Given field vertices in clockwise order, when `create_field` called, then warning/rejection occurs
- [ ] **AC-9:** Given custom field "experiment" registered, when position sent with `field: "experiment"`, then coordinates transform through experiment → world → screen

#### Debug Layers
- [ ] **AC-10:** Given `toggle_grid_layer` command, when executed, then grid overlay toggles on/off
- [ ] **AC-11:** Given multiple fields registered, when field layer enabled, then all field boundaries displayed with labels

#### Client Library
- [ ] **AC-12:** Given DisplayClient connected, when `update_position("robot1", 1.0, 2.0)` called, then server receives and processes command
- [ ] **AC-13:** Given DisplayClient as context manager, when block exits, then connection cleanly closed

#### Error Handling
- [ ] **AC-14:** Given unhandled exception in command handler, when it occurs, then server crashes (does not silently continue)
- [ ] **AC-15:** Given malformed command (bad JSON, missing params), when received, then error logged and error response sent (no crash)

## Additional Context

### Dependencies

- Python >3.10 (required for MocapUtility compatibility)
- pygame
- OpenCV (cv2) - for FieldCalibrator perspective transforms
- PyYAML - for configuration and scene serialization
- MocapUtility - git submodule from `https://github.com/chkxw/MocapUtility.git` (optional)

### Testing Strategy

- **Unit tests:** Field transforms, orientation conversion, command parsing (non-graphical)
- **Interactive visual tests:** Since graphics require human verification, implement an interactive test suite that:
  - Displays a specific visual behavior (e.g., "Circle at position (1,1) with arrow pointing right")
  - Prompts user: "Does this look correct? [y/n]"
  - Proceeds to next test on 'y', logs failure on 'n'
  - Covers all primitives, trajectory styles, orientation transforms, debug layers
- **Integration tests:** Client-server communication, scene serialization (non-graphical)
- **Post-v1 validation:** Run against old experiment code to verify coverage

**Interactive test runner:** `python -m projector_display.tests.visual_tests`

### Notes

- Reference repo at `../box_push_deploy/shared/` should remain untouched for functionality comparison
- Orientation transformation is critical fix - all angle-dependent rendering must use point conversion
- Scene dump should produce YAML that can be converted back to commands and sent to recreate the scene
- **Terminology update for FieldCalibrator:** When copying, rename `real_points` → `world_points`, `virtual_points` → `local_points`. "world" = common reference (meters), "local" = field-specific coords
