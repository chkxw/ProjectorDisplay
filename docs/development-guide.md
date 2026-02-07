# Development Guide

**Generated:** 2026-02-07 | **Scan Level:** Exhaustive

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.10 | Uses `match` statement, `\|` union types |
| pip | any recent | For editable install |
| SDL2 | system package | Required by pygame for display |
| OpenGL ES 2.0 | driver-level | Required for GLES renderer (Raspberry Pi or desktop with GLES support) |
| OptiTrack NatNet | optional | Only if using MoCap integration |

### System Dependencies (Debian/Ubuntu/Raspberry Pi OS)

```bash
sudo apt install python3-dev libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
# For OpenGL on Raspberry Pi:
sudo apt install libgles2-mesa-dev
```

## Installation

### From Source (Development)

```bash
git clone <repo-url> ProjectorDisplay
cd ProjectorDisplay
git submodule update --init --recursive   # Fetch MocapUtility submodule
pip install -e ".[dev]"                   # Editable install with dev tools
```

### Dependencies

**Runtime:**

| Package | Version | Purpose |
|---|---|---|
| pygame | >= 2.0.0 | Display window, event loop, software rendering |
| opencv-python | >= 4.0.0 | Perspective homography (`cv2.getPerspectiveTransform`) |
| PyYAML | >= 6.0 | Configuration and scene serialization |
| numpy | >= 1.20.0 | Coordinate array operations |
| PyOpenGL | >= 3.1.6 | GLES2 rendering backend |

**Dev:**

| Package | Version | Purpose |
|---|---|---|
| pytest | >= 7.0.0 | Test runner |
| pytest-cov | >= 4.0.0 | Coverage reporting |
| black | >= 23.0.0 | Code formatting (line-length=100) |
| ruff | >= 0.1.0 | Linting (E, F, W, I, UP rules) |

## Running the Server

### Calibration File (Required)

The server requires a calibration YAML mapping physical world coordinates (meters) to screen pixels. Example:

```yaml
screen_field:
  world_points:
    - [0.0, 0.0]       # Bottom-left (meters)
    - [1.2, 0.0]       # Bottom-right
    - [1.2, 0.8]       # Top-right
    - [0.0, 0.8]       # Top-left
  local_points:
    - [0, 1080]        # Bottom-left (pixels, Y-down)
    - [1920, 1080]     # Bottom-right
    - [1920, 0]        # Top-right
    - [0, 0]           # Top-left
```

Point order: BL, BR, TR, TL (counter-clockwise). World points are in meters; local points are in screen pixels.

Default location: `~/.local/share/projector_display/calibration.yaml`

### Start Commands

```bash
# Minimal (uses default calibration path)
projector-display-server

# With explicit calibration
projector-display-server --calibration config/calibration_example.yaml

# With server config + GLES renderer
projector-display-server -c config/server_config.yaml -C calibration.yaml --renderer gles

# Pygame (software) renderer for development
projector-display-server -C calibration.yaml --renderer pygame

# With profiling (report every 5 seconds)
projector-display-server -C calibration.yaml --profile

# With custom profiling interval
projector-display-server -C calibration.yaml --profile 10

# Full options
projector-display-server -C calibration.yaml -c config/server_config.yaml \
    --renderer gles --fullscreen --port 9999 --host 0.0.0.0 -v
```

### CLI Arguments

| Argument | Short | Default | Description |
|---|---|---|---|
| `--calibration` | `-C` | `~/.local/share/.../calibration.yaml` | Path to calibration YAML |
| `--config` | `-c` | none | Path to server config YAML |
| `--renderer` | `-r` | `gles` | Renderer backend: `gles` or `pygame` |
| `--fullscreen` | | `false` | True fullscreen (vs borderless window) |
| `--port` | `-p` | `9999` | TCP socket port |
| `--host` | | `0.0.0.0` | TCP socket bind address |
| `--verbose` | `-v` | `false` | Verbose logging |
| `--profile` | | disabled | Enable profiling (optional interval in seconds) |

### Keyboard Shortcuts (While Server Running)

| Key | Action |
|---|---|
| `Escape` | Shut down server |
| `G` | Toggle coordinate grid overlay |
| `F` | Toggle field boundary overlay |

## Using the Client Library

```python
from projector_display import DisplayClient

with DisplayClient("localhost", 9999) as client:
    # Create a rigid body
    client.create_rigidbody("robot1", style={
        "shape": "circle",
        "color": [0, 255, 0],
        "size": 0.05,
        "label": True
    })

    # Update position (world meters)
    client.update_position("robot1", x=0.5, y=0.3, orientation=1.57)

    # Draw a persistent overlay
    client.draw_circle("zone1", x=0.6, y=0.4, radius=0.1,
                       color=[255, 0, 0, 128])
```

## Server Configuration

`config/server_config.yaml`:

```yaml
server:
  socket_host: "0.0.0.0"
  socket_port: 9999

display:
  screen_index: 0
  update_rate: 30
  background_color: [0, 0, 0]
  renderer: gles        # "gles" or "pygame"
  fullscreen: false
```

## Running Examples / Visual Tests

The `examples/` directory contains visual integration test scripts. Each connects to a running server:

```bash
# Start server in one terminal
projector-display-server -C config/calibration_example.yaml --renderer pygame

# Run examples in another terminal
python examples/basic_usage.py              # General API demo
python examples/test_all_shapes.py          # All 5 rigid body shapes
python examples/test_drawings.py            # Persistent drawing overlays
python examples/test_trajectories.py        # Trajectory styles + gradients
python examples/test_alpha_blending.py      # Semi-transparent overlapping shapes
python examples/test_debug_layers.py        # Grid + field boundary overlays
python examples/test_field_backgrounds.py   # Field background colors
python examples/test_stress.py              # Performance benchmark (N bodies)
python examples/test_text_rendering.py      # Text sizes, colors, labels
python examples/test_line_batch.py          # Line batch rendering
```

Most scripts accept an optional host argument: `python examples/test_all_shapes.py 192.168.1.100`

## Code Style

| Tool | Configuration |
|---|---|
| **black** | `line-length = 100`, `target-version = ["py310"]` |
| **ruff** | `line-length = 100`, `target-version = "py310"`, rules: E, F, W, I, UP (E501 ignored) |

## Project Structure for Development

When adding new features, the key files to understand are:

| Task | Primary Files |
|---|---|
| Add a new command | Create handler in `commands/prebuilt/`, use `@register_command` decorator |
| Add a new shape type | Add to `RigidBodyShape` enum, add rendering case in `primitives.py:draw_rigidbody()` |
| Add a new drawing type | Add to `DrawPrimitiveType` enum, add expansion in `server._render_polygon_drawing()` or `_render_drawing()` |
| Modify coordinate transforms | `core/field_calibrator.py` |
| Modify render pipeline | `server.py:render_frame()` and `_render_rigidbody()` / `_render_drawing()` |
| Add a renderer feature | Add to `Renderer` Protocol in `renderer/base.py`, implement in both `pygame_renderer.py` and `gles_renderer.py` |
| Modify rigid body data model | `core/rigidbody.py` |
| Modify scene serialization | `core/scene.py:to_dict()` / `from_dict()` |

## Testing

There is no formal unit test suite. Testing is done via visual integration scripts in `examples/`. The `pyproject.toml` configures pytest to look in a `tests/` directory, but this directory does not yet exist.

To verify changes:
1. Start the server with the pygame renderer (`--renderer pygame`)
2. Run the relevant example script(s)
3. Visually confirm correct behavior

## Logging

Dual-sink logging:
- **stdout**: All levels (configurable via `--verbose`)
- **File**: `/var/log/projector_display.log` (falls back to `/tmp/projector_display.log` if no write permission)

## Links

- [Project Overview](./project-overview.md)
- [Architecture](./architecture.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Index](./index.md)
