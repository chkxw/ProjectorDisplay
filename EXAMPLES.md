# Examples

Test and demo scripts for the Projector Display Server. Each script connects to a running server, exercises a specific set of rendering features, and cleans up on exit (Ctrl+C).

## Prerequisites

Start the server before running any example:

```bash
# GLES2 renderer (default, GPU-accelerated)
projector-display-server --calibration path/to/calibration.yaml

# Pygame software renderer (fallback)
projector-display-server --calibration path/to/calibration.yaml --renderer pygame

# With performance profiling
projector-display-server --calibration path/to/calibration.yaml --profile 5
```

## Running

All scripts accept the server host as the first argument (defaults to `localhost`):

```bash
python examples/test_all_shapes.py 192.168.0.126
```

---

## `basic_usage.py`

**General-purpose demo of the client API.**

- Connects to the server using `DisplayClient`
- Creates two rigid bodies: a red circle (`robot1`) with trajectory and a blue box (`payload1`) without
- Moves `robot1` in a circle at ~30 Hz
- Demonstrates: `create_rigidbody`, `update_position`, `status`, `clear_scene`

```bash
python examples/basic_usage.py [HOST]
```

---

## `test_all_shapes.py`

**All five rigid body shape types rendered simultaneously.**

Creates one of each shape and places them in a horizontal row:

| Shape | Color | Notes |
|---|---|---|
| `circle` | Red | Standard filled circle with border |
| `box` | Green | Square, rotated by orientation |
| `triangle` | Blue | Points in orientation direction |
| `polygon` | Magenta | Regular pentagon via `polygon_vertices` |
| `compound` | Orange | Body box + two grey wheels + white arrow, via `draw_list` |

All shapes rotate slowly so you can verify that orientation affects each shape type correctly. Labels are displayed above each shape.

**Exercises:** `draw_circle`, `draw_polygon`, `draw_polygon_alpha`, `draw_rigidbody`, compound `draw_list` rendering, orientation arrow.

```bash
python examples/test_all_shapes.py [HOST]
```

---

## `test_drawings.py`

**Every persistent drawing overlay type.**

Creates 9 persistent drawings that remain visible until cleanup:

| Drawing | Type | Details |
|---|---|---|
| `d_circle_filled` | Filled circle | Red, radius 0.08m |
| `d_circle_outline` | Outlined circle | Green, thickness 3 |
| `d_box_filled` | Filled box | Blue, 0.15×0.10m |
| `d_box_outline` | Outlined rotated box | Yellow, rotated 45° |
| `d_line` | Line | Orange, thickness 3 |
| `d_arrow` | Arrow | Cyan, with arrowhead |
| `d_hexagon` | Filled polygon | Purple hexagon (6 vertices) |
| `d_text` | Text label | White, "GLES2 Test" |
| `d_alpha_poly` | Semi-transparent polygon | Yellow at alpha=100 |

Also calls `list_drawings` to verify server-side state.

**Exercises:** `draw_circle`, `draw_box`, `draw_line`, `draw_arrow`, `draw_polygon`, `draw_text`, `draw_polygon_alpha`, `list_drawings`, `clear_drawings`.

```bash
python examples/test_drawings.py [HOST]
```

---

## `test_trajectories.py`

**Trajectory line styles with gradient colors.**

Creates three rigid bodies, each orbiting a different center with a distinct trajectory style:

| Body | Shape | Trajectory Style | Color |
|---|---|---|---|
| `traj_solid` | Circle | Solid | Gradient: yellow (opaque) → red (transparent) |
| `traj_dotted` | Triangle | Dotted | Solid cyan at alpha=200 |
| `traj_dashed` | Box | Dashed | Gradient: green (opaque) → blue (semi-transparent) |

The gradient trajectories test RGBA interpolation — you should see the tail fade from one color to another, and from opaque to transparent.

**Exercises:** `draw_line_alpha`, `draw_circle_alpha`, `draw_line_batch`, `_interpolate_color`, `_draw_solid_trajectory`, `_draw_dotted_trajectory`, `_draw_dashed_trajectory`.

```bash
python examples/test_trajectories.py [HOST]
```

---

## `test_alpha_blending.py`

**Overlapping semi-transparent shapes.**

Two groups:

1. **Venn diagram** — Three large circles (red, green, blue) at ~47% opacity, overlapping. Where colors overlap you should see additive-style color mixing (red+green → yellowish, etc.).

2. **Alpha gradient row** — Five yellow boxes with alpha values 40, 80, 120, 180, 240, from nearly invisible to nearly opaque. Each is labeled with its alpha value.

3. **White overlay** — A large semi-transparent white polygon (alpha=50) covering the Venn diagram area.

**Exercises:** `draw_polygon_alpha`, `draw_circle_alpha`, RGBA color in `create_rigidbody` style, GL blending (`GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA`).

```bash
python examples/test_alpha_blending.py [HOST]
```

---

## `test_debug_layers.py`

**Grid overlay and field boundary visualization.**

- Creates a custom field (`test_field`) spanning [-1,-1] to [1,1] in world coordinates
- Enables both the **grid layer** and **field layer**
- Configures grid colors (brighter major lines, subtle minor lines with alpha)
- Places a yellow circle marker at the origin (0,0) and a green triangle at (1,1)

**What to check:**
- Major grid lines at every 1m with coordinate labels like `(0,0)`, `(1,0)`, etc.
- Minor grid lines at every 0.1m (if `show_minor=True`)
- Yellow crosshair at origin
- Field boundary polygon with corner markers (BL, BR, TR, TL) and field name label aligned along the top edge
- Grid lines drawn via `draw_line_batch` (single blit for performance)

**Exercises:** `GridLayer.draw`, `FieldLayer.draw`, `draw_line_batch`, `draw_text`, `set_grid_layer`, `set_field_layer`, `configure_grid_layer`.

```bash
python examples/test_debug_layers.py [HOST]
```

---

## `test_field_backgrounds.py`

**Solid-color field backgrounds at varying alpha.**

Creates three side-by-side fields:

| Field | Color | Alpha | Appearance |
|---|---|---|---|
| `bg_red` | Dark red | 150 | Semi-transparent |
| `bg_green` | Dark green | 200 | Mostly opaque |
| `bg_blue` | Dark blue | 255 | Fully opaque |

Each field has a rigid body placed on top that rotates slowly, so you can verify:
- Background renders behind rigid bodies (z-order)
- Alpha blending on field backgrounds works
- `draw_polygon` / `draw_polygon_alpha` path for solid-color backgrounds

Also draws a title text label above the fields.

**Exercises:** `create_field`, `set_field_background_color`, `draw_polygon_alpha`, `draw_polygon`, z-order rendering, `BackgroundRenderer.render_field_backgrounds`.

```bash
python examples/test_field_backgrounds.py [HOST]
```

---

## `test_stress.py`

**Performance stress test with many simultaneous rigid bodies.**

Creates N rigid bodies (default 20, configurable via second argument), each with a solid trajectory. All bodies move simultaneously in overlapping orbits at ~30 Hz.

Prints timing every 30 frames:
```
  [    0] 20 updates in 12.3 ms (0.62 ms/body)
  [   30] 20 updates in 11.8 ms (0.59 ms/body)
```

Use this to compare GLES2 vs pygame renderer performance. Run the server with `--profile 5` to see frame times on the server side.

**Exercises:** Renderer throughput under load, trajectory rendering at scale, `clear_scene` bulk cleanup.

```bash
# Default: 20 bodies
python examples/test_stress.py 192.168.0.126

# Heavy load: 50 bodies
python examples/test_stress.py 192.168.0.126 50
```

---

## `test_text_rendering.py`

**Text rendering at various sizes, colors, and positions.**

Three groups:

1. **Font sizes** — Text at sizes 16, 20, 24, 30, 36 px in a horizontal row. Verifies the text cache handles multiple font sizes.

2. **Colored text** — "Red", "Green", "Blue", "Yellow", "Magenta" each in their respective color.

3. **Labeled rigid bodies** — Circle, box, and triangle shapes with labels enabled, verifying that `draw_text` works in the `draw_rigidbody` → `draw_label` path.

In GLES2 mode, text rendering goes through: `pygame.font.render` → RGBA bytes → `glTexImage2D` → textured quad. This test verifies the full pipeline and exercises the LRU text cache (max 256 entries).

**Exercises:** `draw_text` (persistent drawings and rigid body labels), text with background, font caching, GLES2 text texture cache.

```bash
python examples/test_text_rendering.py [HOST]
```

---

## `test_line_batch.py`

**Line batch rendering with many colored lines.**

- Enables the **grid layer** with alpha-blended minor lines — the grid internally uses `draw_line_batch` to render all lines in a single call
- Draws a 40-ray **starburst** pattern from the origin, each ray a different rainbow color at alpha=200
- Adds a moving triangle body with trajectory to see interaction with the line pattern

**What to check:**
- All 40 rays render with correct colors (smooth rainbow)
- Grid lines render behind the starburst
- Alpha blending on grid minor lines (alpha=80) is visibly lighter than major lines (alpha=180)
- In GLES2 mode, `draw_line_batch` groups lines by (color, width) for fewer draw calls

**Exercises:** `draw_line_batch` (grid path), `draw_line` (individual rays), `draw_circle`, line width, alpha blending on lines.

```bash
python examples/test_line_batch.py [HOST]
```

---

## Renderer Comparison

To visually compare the two renderers, run the same test against each backend:

```bash
# Terminal 1: Start with GLES2
projector-display-server -C calibration.yaml --renderer gles --profile 5

# Terminal 2: Run a test
python examples/test_stress.py

# Restart server with pygame
projector-display-server -C calibration.yaml --renderer pygame --profile 5

# Run the same test again
python examples/test_stress.py
```

The `--profile` flag prints frame timing on the server. Expected results on a Pi 4 at 1920×1080:

| Metric | pygame | GLES2 |
|---|---|---|
| Frame time | ~120 ms | ~8 ms |
| FPS | ~8–20 | ~60–136 |
| `scene_snap` | ~15 ms (deep copy) | <1 ms (shallow copy) |
