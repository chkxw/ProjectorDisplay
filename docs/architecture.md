# Architecture

**Generated:** 2026-02-07 | **Scan Level:** Exhaustive

## Executive Summary

ProjectorDisplay is a multi-threaded Python server that renders real-time visualizations onto a ceiling-mounted projector for robotics research. The architecture centers on three patterns: (1) a **Scene graph** holding all displayable state, (2) a **vertex-transform pipeline** that maps world-space meters to screen pixels via OpenCV perspective homography, and (3) a **command-dispatch** system that decouples the TCP/JSON protocol from domain logic.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProjectorDisplayServer                     │
│                                                              │
│  ┌─────────────┐    ┌────────────┐    ┌───────────────────┐ │
│  │  Main Thread │    │ Socket     │    │ ThreadPoolExecutor│ │
│  │  (Render     │    │ Thread     │    │ (Client Workers)  │ │
│  │   Loop)      │    │            │    │                   │ │
│  │  30 Hz       │    │ accept()   │───▶│ _handle_client()  │ │
│  └──────┬───────┘    └────────────┘    └────────┬──────────┘ │
│         │                                       │            │
│         │ snapshot read                  command │ write      │
│         ▼                                       ▼            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    Scene (lock-protected)                │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ │ │
│  │  │FieldCalibrator│ │ RigidBodies  │ │ Drawings        │ │ │
│  │  │  + "screen"   │ │ Dict[str,RB] │ │ Dict[str,Draw]  │ │ │
│  │  └──────────────┘ └──────────────┘ └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ CommandRegistry   │  │ Renderer (Protocol)              │ │
│  │ @register_command │  │  ├── PygameRenderer (CPU)        │ │
│  │ 7 command modules │  │  └── GLESRenderer (GPU/GLES2)    │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ MocapTracker      │  │ StorageManager (XDG)             │ │
│  │ (optional NatNet) │  │ persistent + session temp        │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Threading Model

| Thread | Role | Lifetime |
|---|---|---|
| **Main** | pygame event loop + `render_frame()` at configurable FPS (default 30 Hz) | Application lifetime |
| **Socket** | `_socket_server_loop()` — accepts TCP connections, dispatches to executor | Application lifetime (daemon) |
| **Client Workers** | `ThreadPoolExecutor(max_workers=10)` — each connection handled in a pooled thread | Per-connection |
| **MoCap** (optional) | Background polling at 30 Hz, updates `Scene.update_mocap_position()` | Application lifetime (daemon) |

**Thread safety:** The `Scene` object protects mutable state with `threading.Lock`. The render thread reads *snapshots* — shallow copies of the rigidbodies/drawings/fields dicts created under the lock — so it never holds the lock during rendering. Command handlers write through Scene methods that acquire the lock briefly.

## Coordinate System & Vertex-Transform Pipeline

This is the most architecturally significant subsystem. All geometry goes through perspective-correct coordinate transforms.

### Coordinate Spaces

| Space | Units | Description |
|---|---|---|
| **World ("base")** | Meters | Physical workspace floor. All positions stored internally in this space. |
| **Field (local)** | User-defined | Named rectangular regions with local coordinate systems (e.g., experiment zone, screen). |
| **Screen** | Pixels | Display output. The "screen" field maps world meters to display pixels. |
| **Body-local** | Normalized | Rigid body's own frame. Scaled by `body_size`, rotated by `body_world_angle`. |

### Transform Pipeline

```
 Body-local         World (base)        Screen (pixels)
  vertices    ──▶    vertices     ──▶    vertices
              scale+rotate         perspective
              _local_to_world()    homography (H)
                                   batch_world_to_screen()
```

**Key principle:** Geometry is ALWAYS expanded into vertices in its source coordinate space BEFORE applying homography. Never scale/rotate after perspective transform — this would break axis independence.

### Homography Implementation

`FieldCalibrator` uses `cv2.getPerspectiveTransform()` to compute 3x3 homography matrices between any two fields. Transforms are cached on field registration and composed for multi-hop conversions (field-local -> world -> screen).

Key methods:
- `convert(coords, from_field, to_field)` — Batch-capable coordinate transform via `cv2.perspectiveTransform()`
- `transform_orientation(from, to, pos, angle)` — Two-point probe method: converts position and position+probe, derives angle from difference
- `world_scale(world_pos, distance)` — Four-point probe: samples +-distance in X and Y, averages screen distances for position-aware size conversion

### Rigid Body Rendering Pipeline

```python
# In server._render_rigidbody():
1. display_pos = rb.get_display_position()          # World coords (meters)
2. screen_pos  = world_to_screen(display_pos)        # H: world→screen
3. screen_size = fc.world_scale(display_pos, rb.size) # 4-point probe → pixels
4. trajectory  = batch_world_to_screen(traj_points)   # Batch H for trail

# In rendering/primitives.py draw_rigidbody():
5. world_verts = [body_pos + size*rot(local_vert) for local_vert in shape]  # Expand in world
6. screen_pts  = batch_fn(world_verts)               # Single batch H call
7. renderer.draw_polygon(screen_pts, color)           # Draw screen polygon
```

### Drawing Overlay Pipeline (server._render_polygon_drawing)

Two-phase pipeline for persistent drawings (circles, boxes, polygons):

```
Phase 1: shape → field-space vertices
  CIRCLE(x,y,r)  → N-gon vertices at (cx + r*cos, cy + r*sin)
  BOX(x,y,w,h,a) → 4 rotated corners
  POLYGON(verts)  → pass-through

Phase 2: field-space → screen
  if field != "base":
    world_verts = fc.convert(field_verts, field, "base")   # H1
  screen_pts = batch_world_to_screen(world_verts)          # H2
  draw_polygon(screen_pts, ...)
```

### Compound Shape Pipeline (primitives.draw_compound)

Three-phase approach for compound rigid bodies (multiple primitives per body):

```
Phase 1: Collect ALL world vertices from all primitives
  for each primitive:
    expand local vertices → _local_to_world() → append to all_world[]
    record (start_idx, count, prim) in prim_ranges[]

Phase 2: Single batch world→screen conversion
  all_screen = world_to_screen_batch_fn(all_world)

Phase 3: Distribute screen points and draw
  for (start, count, prim) in prim_ranges:
    pts = all_screen[start:start+count]
    draw_polygon/line/text(pts, ...)
```

This single-batch approach minimizes `cv2.perspectiveTransform()` calls.

## Command-Dispatch Architecture

### Registry Pattern

Commands use a **decorator-based global registry** (`commands/base.py`):

```python
@register_command
def create_rigidbody(scene, name: str, style: dict = None, ...):
    """Handler receives Scene + params, returns response dict."""
    rb = scene.create_rigidbody(name=name, style=style)
    return {"status": "success", "name": name}
```

The registry is a singleton (`_registry`). All command modules in `commands/prebuilt/` are auto-imported by `commands/prebuilt/__init__.py`, which triggers decorator registration at import time.

### Command Flow

```
TCP client → JSON line → server._process_command()
                              │
                              ▼
                    CommandRegistry.execute(action, scene, **params)
                              │
                              ▼
                    handler(scene, **params) → {"status": "success", ...}
                              │
                              ▼
                    JSON response → TCP client
```

### Command Modules

| Module | Commands | Description |
|---|---|---|
| `rigidbody_commands.py` | create, remove, update_position, update_style, update_trajectory, get, list | Rigid body CRUD + state |
| `field_commands.py` | create_field, remove_field, get_field, list_fields, set_calibration, set_field_background/color, remove_field_background | Coordinate field management |
| `scene_commands.py` | clear_scene, dump_scene, load_scene, save_scene, status | Scene lifecycle + persistence |
| `drawing_commands.py` | draw_circle, draw_box, draw_line, draw_arrow, draw_polygon, draw_text, remove_drawing, list_drawings, clear_drawings | Persistent drawing overlays |
| `debug_commands.py` | toggle_grid, toggle_field_layer, set_grid, configure_grid | Debug visualization |
| `asset_commands.py` | check_asset, upload_asset, list_assets, delete_asset | Image asset management (SHA256) |
| `mocap_commands.py` | set_mocap, enable_mocap, disable_mocap | Motion capture integration |

## Renderer Subsystem

### Protocol (renderer/base.py)

The `Renderer` Protocol defines the rendering API:

- **Lifecycle:** `init()`, `clear()`, `flip()`, `tick()`, `quit()`
- **Primitives:** `draw_circle()`, `draw_polygon()`, `draw_line()`, `draw_lines()`, `draw_text()`, `draw_image()`
- **Batch:** `draw_line_batch()`, `draw_circles_batch()`, `draw_lines_batch()`
- **Queries:** `get_size()`, `get_events()`

### PygameRenderer (CPU/Software)

- Uses `pygame.Surface` with `SRCALPHA` flag for alpha blending
- Temp surface pattern: draws to a transparent surface, then blits onto main display
- Font caching with `functools.lru_cache`
- Suitable for development and debugging

### GLESRenderer (GPU/Hardware)

- Direct OpenGL ES 2.0 via ctypes bindings (bypasses PyOpenGL overhead for 15-25x speedup)
- Two shader programs: solid color + textured (for text)
- Buffer orphaning VBO strategy: `glBufferData(NULL)` then `glBufferSubData()` to avoid GPU stalls
- Pre-computed unit circles at 16/32/64 segments
- Text rendering: pygame `Font.render()` → texture upload → quad draw, with LRU cache (max 256 entries)
- Orthographic projection matching display dimensions
- Target platform: Raspberry Pi with GLES2 support

## Data Model

### Scene Graph

```
Scene
├── FieldCalibrator
│   ├── fields: Dict[str, Field]
│   │   ├── "screen" (required) — world meters ↔ display pixels
│   │   └── user-defined fields — world ↔ local coords
│   └── transform_matrix: Dict[str, Dict[str, Callable]]
│       (cached homography functions between all field pairs)
├── _rigidbodies: Dict[str, RigidBody]
│   └── RigidBody
│       ├── position / orientation (manual)
│       ├── mocap_position / mocap_orientation (MoCap-driven)
│       ├── position_history: deque (max 10000 entries)
│       ├── style: RigidBodyStyle (shape, color, size, ...)
│       ├── trajectory_style: TrajectoryStyle (mode, gradient, ...)
│       ├── z_order + _z_seq (render ordering)
│       └── auto_track, tracking_lost (MoCap state)
└── _drawings: Dict[str, Drawing]
    └── Drawing
        ├── id, field, z_order, _z_seq
        ├── world_x, world_y (cached world coords)
        └── primitive: DrawPrimitive
            (type, compact params, color, thickness, filled)
```

### RigidBody Position Sources

Rigid bodies support dual position sources for MoCap integration:

```
           ┌─────────────────────┐
           │     RigidBody       │
           │                     │
manual ───▶│ position            │
           │ orientation         │──▶ get_display_position()
           │                     │    returns mocap_position if
MoCap  ───▶│ mocap_position      │    auto_track else position
           │ mocap_orientation   │
           └─────────────────────┘
```

### Drawing Storage Pattern

Drawings store **compact shape parameters**, not pre-expanded vertices:
- CIRCLE: `(x, y, radius)` in field space
- BOX: `(x, y, width, height, angle)` in field space
- POLYGON: vertices in field space

Expansion to screen vertices happens at render time through the two-phase pipeline. This keeps the data model small and allows correct rendering when calibration changes.

## Networking

### Protocol

- **Transport:** TCP/IP, newline-delimited JSON
- **Port:** 9999 (default, configurable)
- **Message format:** `{"action": "command_name", "param1": value1, ...}\n`
- **Response:** `{"status": "success"|"error", ...}\n`

### Client Library (DisplayClient)

- Context manager support (`with DisplayClient(...) as client:`)
- Auto-reconnect with configurable retry/backoff
- Buffer-based message receiving (handles partial TCP reads)
- Full Python API wrapping all server commands
- High-level helpers (e.g., `set_field_background()` with hash-check upload to avoid redundant transfers)

## Storage

### XDG-Compliant Layout

```
~/.local/share/projector_display/
├── calibration.yaml          # Default calibration file
├── scenes/                   # Saved scene YAML files
├── assets/                   # Uploaded image assets (SHA256-verified)
└── [other persistent data]

/tmp/projector_display/{session_id}/
└── [session-temporary files]
```

## Optional Integrations

### MoCap (OptiTrack NatNet)

- Git submodule: `external/MocapUtility/`
- Lazy-imported — server starts without MoCap hardware
- Background polling thread at 30 Hz
- Quaternion → yaw conversion for 2D orientation
- Per-body error logging (rate-limited)
- Bodies with `auto_track=True` automatically update position from NatNet data

## Render Loop Order

```
1. clear(background_color)
2. render_field_backgrounds()     # Perspective-warped images/colors
3. draw grid_layer (if enabled)   # 1m major + 0.1m minor grid
4. draw field_layer (if enabled)  # Field boundaries + labels
5. snapshot rigidbodies + drawings
6. sort all renderables by (z_order, z_seq)
7. for each renderable:
     if rigidbody: trajectory → shape → orientation arrow → label
     if drawing:   dispatch to polygon/line/text pipeline
8. flip()
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Expand vertices before homography | Perspective transform is non-linear; scaling after transform breaks axis independence |
| Batch `cv2.perspectiveTransform()` | Single call for N points is much faster than N individual calls |
| Dual renderer backends | GLES2 for production (Raspberry Pi), pygame for development |
| Snapshot-based rendering | Render thread never holds Scene lock during draw calls |
| Compact drawing storage | Drawings store `(x,y,r)` not vertices; correct across calibration changes |
| Four-point size probe | `world_scale()` averages 4 directional probes for position-aware pixel conversion |
| Two-point orientation probe | `transform_orientation()` avoids Jacobian computation; works correctly under perspective |
| Command decorator registry | Zero-boilerplate command addition; auto-registration at import time |

## Links

- [Project Overview](./project-overview.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Development Guide](./development-guide.md)
- [Index](./index.md)
