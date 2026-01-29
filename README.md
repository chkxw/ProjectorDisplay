# Projector Display

Scene-based projector display server for robot experiments. Renders rigid bodies, coordinate fields, trajectories, and drawing overlays onto a projector-mounted display, driven by a TCP/JSON command protocol.

## Features

- **Rigid bodies** -- circles, boxes, triangles, polygons, and compound shapes with orientation arrows and labels
- **Coordinate fields** -- define named rectangular regions with perspective-correct world-to-screen mapping
- **Trajectory visualization** -- time- or distance-based trails with solid, dashed, dotted, or gradient styles
- **Drawing overlays** -- persistent circles, boxes, lines, arrows, polygons, and text anchored in world coordinates
- **Field backgrounds** -- warp images onto field regions with perspective correction and alpha blending
- **MoCap integration** -- optional OptiTrack NatNet streaming for automatic rigid body tracking
- **Scene persistence** -- save and load named scenes with all assets
- **Debug layers** -- toggleable coordinate grid and field boundary overlays

## Installation

Requires Python >= 3.10 and Linux with `xrandr` installed.

```bash
# Clone and install in editable mode
git clone <repo-url>
cd ProjectorDisplay
pip install -e .

# Or install dev dependencies too
pip install -e ".[dev]"
```

**System dependency:**

```bash
# Debian/Ubuntu
sudo apt install x11-xserver-utils   # provides xrandr
```

**Optional:** For MoCap support, place [MocapUtility](https://github.com/your-org/MocapUtility) in `external/`.

## Quick Start

### 1. Create a calibration file

The server requires a calibration file that maps world coordinates (meters) to screen pixels. Copy and edit the example:

```bash
cp config/calibration_example.yaml my_calibration.yaml
```

Edit the `world_points` to match your physical setup (see [Calibration](#calibration-file-required) below).

### 2. Start the server

```bash
projector-display-server --calibration my_calibration.yaml
```

The server opens a fullscreen borderless window on your display and listens for client connections on port 9999.

### 3. Connect a client

```python
import time
import math
from projector_display import DisplayClient

with DisplayClient("localhost") as client:
    # Create a robot marker
    client.create_rigidbody("robot1", style={
        "shape": "circle",
        "size": 0.15,           # 15cm radius in world meters
        "color": [255, 0, 0],   # Red
        "label": True,
        "orientation_length": 0.2,
    }, trajectory={
        "enabled": True,
        "mode": "time",
        "length": 5.0,          # Show last 5 seconds
        "style": "solid",
        "color": "gradient",
        "gradient_start": [255, 0, 0],
        "gradient_end": [100, 0, 0],
    })

    # Move in a circle
    t = 0
    while t < 10:
        x = 2.0 + 0.5 * math.cos(t)
        y = 1.5 + 0.5 * math.sin(t)
        client.update_position("robot1", x, y, orientation=t + math.pi / 2)
        t += 0.05
        time.sleep(0.033)

    client.clear_scene()
```

See `examples/basic_usage.py` for a complete runnable example.

## Configuration

### Calibration File (required)

Maps the physical projected area to screen pixels. The server will not start without this file.

```yaml
# Vertex order: [BL, BR, TR, TL] -- counter-clockwise from bottom-left

resolution:
  width: 1920
  height: 1080

screen_field:
  world_points:        # Physical corners in meters
    - [0.0, 0.0]      # BL
    - [4.0, 0.0]      # BR
    - [4.0, 3.0]      # TR
    - [0.0, 3.0]      # TL

  local_points:        # Screen corners in pixels (Y=0 is top)
    - [0, 1080]       # BL
    - [1920, 1080]    # BR
    - [1920, 0]       # TR
    - [0, 0]          # TL

created: "2026-01-27T12:00:00"
```

The resolution must match the display's current resolution or the server rejects the file.

### Server Config (optional)

```yaml
server:
  socket_host: "0.0.0.0"    # Bind address
  socket_port: 9999          # Listen port

display:
  screen_index: 0            # Display index (0 = primary)
  update_rate: 30            # Target FPS
  background_color: [50, 50, 50]
```

### CLI Arguments

```
projector-display-server [options]

  -C, --calibration PATH   Path to calibration YAML (required)
  -c, --config PATH        Path to server config YAML
  -p, --port PORT          Override listen port (default: 9999)
  --host HOST              Override bind address (default: 0.0.0.0)
  -v, --verbose            Enable debug logging
```

## Client API

### Connection

```python
from projector_display import DisplayClient

# Using context manager (recommended)
with DisplayClient("192.168.1.100", port=9999, timeout=5.0) as client:
    ...

# Or manual connection
client = DisplayClient("192.168.1.100", auto_reconnect=True)
client.connect()
...
client.disconnect()
```

### Rigid Bodies

```python
# Create with style and trajectory options
client.create_rigidbody("robot1", style={...}, trajectory={...})

# Update position (auto-creates if body doesn't exist)
client.update_position("robot1", x=1.5, y=2.0, orientation=0.7, field="base")

# Modify appearance
client.update_style("robot1", color=[0, 255, 0], size=0.2, shape="box")
client.update_trajectory("robot1", enabled=True, mode="distance", length=2.0)

# Inspect
info = client.get_rigidbody("robot1")
bodies = client.list_rigidbodies()

# Remove
client.remove_rigidbody("robot1")
```

**Shapes:** `circle`, `box`, `triangle`, `polygon`, `compound`

**Style fields:** `shape`, `size`, `color`, `alpha`, `label`, `label_offset`, `orientation_length`, `orientation_color`, `orientation_thickness`, `polygon_vertices`, `draw_list` (compound only)

**Trajectory fields:** `enabled`, `mode` (`time`/`distance`), `length`, `style` (`solid`/`dashed`/`dotted`), `thickness`, `color` (`single`/`gradient`), `gradient_start`, `gradient_end`, `dot_spacing`, `dash_length`

### Coordinate Fields

Fields define named rectangular regions with their own coordinate system. Positions and drawings can reference any field by name.

```python
# Create a 3x2 meter field mapped to a specific area
client.create_field("experiment_zone",
    world_points=[[1, 0], [3, 0], [3, 2], [1, 2]],  # [BL, BR, TR, TL] in meters
    local_points=[[0, 0], [3, 0], [3, 2], [0, 2]]    # [BL, BR, TR, TL] in field-local coords
)

# Position a body using field-local coordinates
client.update_position("robot1", x=1.5, y=1.0, field="experiment_zone")

client.list_fields()
client.get_field("experiment_zone")
client.remove_field("experiment_zone")
```

### Drawing Overlays

Persistent drawings anchored in world coordinates. IDs are replace-on-collision (sending a drawing with an existing ID replaces it).

```python
client.draw_circle("zone1", x=2.0, y=1.5, radius=0.3, color=[255, 255, 0], field="base")
client.draw_box("area1", x=1.0, y=1.0, width=0.5, height=0.3, color=[0, 255, 0])
client.draw_line("path1", x1=0.0, y1=0.0, x2=3.0, y2=2.0, color=[255, 255, 255], thickness=2)
client.draw_arrow("dir1", x1=1.0, y1=1.0, x2=2.0, y2=1.0, color=[255, 0, 0])
client.draw_polygon("tri1", vertices=[[1, 1], [2, 1], [1.5, 2]], color=[0, 0, 255])
client.draw_text("label1", x=2.0, y=2.5, text="Start", color=[255, 255, 255], font_size=32)

client.list_drawings()
client.remove_drawing("zone1")
client.clear_drawings()
```

### Scene Management

```python
client.clear_scene()              # Remove all rigid bodies (keep fields)
client.clear_all()                # Remove everything except screen field

scene_data = client.dump_scene()  # Export current scene
client.load_scene(scene_data)     # Import scene

client.save_scene("experiment1")  # Save to persistent storage
client.load_scene_from_file("experiment1")
client.list_saved_scenes()
client.delete_saved_scene("experiment1")

client.status()                   # Server info
```

### Field Backgrounds

```python
# High-level: auto-uploads image file and sets as background
client.set_field_background("experiment_zone", "/path/to/floor_plan.png", alpha=200)

# Remove background
client.remove_field_background("experiment_zone")
```

### Debug Layers

```python
client.toggle_grid_layer()     # Toggle coordinate grid
client.toggle_field_layer()    # Toggle field boundaries

client.set_grid_layer(True)    # Explicit on/off
client.set_field_layer(False)

client.configure_grid_layer(show_minor=True, major_color=[100, 100, 100])
```

### MoCap Integration

Requires [MocapUtility](https://github.com/your-org/MocapUtility) in `external/`.

```python
client.set_mocap(ip="192.168.1.50", port=1511, enabled=True)
client.get_mocap_status()
client.get_mocap_bodies()

# Link a rigid body to a MoCap body for automatic tracking
client.set_auto_track("robot1", mocap_name="Robot1_MoCap", enabled=True)
client.disable_tracking("robot1")
```

## Raw TCP/JSON Protocol

The server accepts newline-delimited JSON over TCP. You can control it from any language (Python, C++, MATLAB) or even `netcat`:

```bash
# Enable debug grid
echo '{"action":"set_grid_layer", "enabled":true}' | nc -q 1 localhost 9999

# Create a rigid body
echo '{"action":"create_rigidbody", "name":"robot1", "style":{"color":"blue", "shape":"circle", "size":0.2}}' | nc -q 1 localhost 9999

# Move it
echo '{"action":"update_position", "name":"robot1", "x":1.5, "y":0.5}' | nc -q 1 localhost 9999

# Draw an arrow
echo '{"action":"draw_arrow", "id":"vec1", "x1":0, "y1":0, "x2":1, "y2":1, "color":"red"}' | nc -q 1 localhost 9999
```

Every command returns `{"status": "success", ...}` or `{"status": "error", "message": "..."}`.

## Coordinate System

All internal positions are stored in **world coordinates** (meters). The `"base"` field is the world coordinate system defined by the calibration file.

```
World (meters)           Screen (pixels)
+Y                       +---------> +X (pixels)
^                        |
|                        |  Y=0 is TOP
|                        v
+-------> +X             +Y (pixels)
(0,0) = origin
```

Custom fields provide local coordinate systems with perspective-correct mapping. When you pass `field="my_field"` to a position or drawing command, coordinates are converted to world meters at command time and stored that way.

## Keyboard Controls

When the display window is focused:

| Key   | Action                    |
|-------|---------------------------|
| `ESC` | Quit server               |
| `G`   | Toggle coordinate grid    |
| `F`   | Toggle field boundaries   |

## Architecture

The server uses a multi-threaded architecture:

- **Main thread** -- pygame render loop at 30 Hz
- **Socket thread** -- accepts TCP connections
- **Worker threads** -- `ThreadPoolExecutor` handles client commands concurrently

Commands are JSON messages over TCP. The render loop reads scene state through thread-safe deep-copy snapshots (`get_rigidbodies_snapshot()`, `get_drawings_snapshot()`, etc.) to avoid lock contention.

Render order: backgrounds -> debug layers -> trajectories -> rigid bodies -> drawings -> flip.

For detailed architecture, see `_bmad-output/implementation-artifacts/tech-spec-projector-display.md`.

## Project Structure

```
ProjectorDisplay/
├── projector_display/
│   ├── __init__.py              # Package exports
│   ├── server.py                # Display server (main entry)
│   ├── client.py                # DisplayClient (user-facing API)
│   ├── core/
│   │   ├── field_calibrator.py  # Coordinate field management
│   │   ├── rigidbody.py         # RigidBody, RigidBodyStyle, TrajectoryStyle
│   │   ├── draw_primitive.py    # DrawPrimitive, Drawing (overlays + compound)
│   │   └── scene.py             # Thread-safe scene state
│   ├── rendering/
│   │   ├── renderer.py          # PygameRenderer (SDL2 multi-display)
│   │   ├── primitives.py        # Shape rendering dispatch
│   │   └── debug_layers.py      # Grid and field boundary overlays
│   ├── commands/
│   │   ├── base.py              # Command registry (@register_command)
│   │   └── prebuilt/            # Built-in command modules
│   │       ├── rigidbody_commands.py
│   │       ├── field_commands.py
│   │       ├── scene_commands.py
│   │       ├── debug_commands.py
│   │       ├── asset_commands.py
│   │       ├── drawing_commands.py
│   │       └── mocap_commands.py
│   ├── utils/
│   │   ├── color.py             # parse_color() -- hex/RGB/RGBA/float/CSV
│   │   └── storage.py           # Persistent scene & image storage
│   └── mocap/                   # MoCap integration (optional)
├── config/
│   ├── calibration_example.yaml
│   └── server_config.yaml
├── examples/
│   └── basic_usage.py
├── external/                    # Optional: MocapUtility
└── pyproject.toml
```

## License

MIT
