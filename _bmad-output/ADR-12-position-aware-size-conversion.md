# ADR-12: Position-Aware Size Conversion

## Status

Accepted (implemented)

## Context

`meters_to_pixels()` in `server.py` uses `screen_width / world_width` -- a single scalar approximation that assumes uniform pixel density across the projected surface. This is wrong when the screen and world aspect ratios differ or when perspective distortion is present.

**Symptom:** A 1.0m radius circle renders as ~1.71m on the projector. The grid is accurate because it converts each endpoint through the full perspective transform, but sizes (radius, box dimensions, label offsets) use the broken scalar.

**Root cause:** `meters_to_pixels` divides `screen_width` by `world_width`, ignoring the Y axis entirely. For a projector mapping a 2.47m x 4.39m world area (ratio 1.78), this overestimates sizes by ~1.78x.

## Decision

Remove the global scalar `meters_to_pixels()` and replace it with a position-aware method on `FieldCalibrator`.

### Design

**Principle:** Users specify sizes in the same coordinate system as positions. A rigid body at `field="base"` has `size` in meters. A drawing at `field="experiment_zone"` has `radius` in that field's local units. The FieldCalibrator -- the single source of truth for coordinate math -- handles the conversion.

**Method: `FieldCalibrator.world_scale(world_pos, distance)`**

Converts a scalar distance to screen pixels at a specific world position using a four-point probe:

```
Given world position (wx, wy) and distance d:

1. Convert four probe points through the perspective transform:
   p_center = convert((wx, wy), "base", "screen")
   p_right  = convert((wx + d, wy), "base", "screen")
   p_left   = convert((wx - d, wy), "base", "screen")
   p_up     = convert((wx, wy + d), "base", "screen")
   p_down   = convert((wx, wy - d), "base", "screen")

2. Compute screen distances:
   dx = (dist(p_center, p_right) + dist(p_center, p_left)) / 2
   dy = (dist(p_center, p_up) + dist(p_center, p_down)) / 2

3. Return average: (dx + dy) / 2
```

The four-point probe (instead of two) averages out asymmetric perspective distortion around the position. This gives a good circular approximation even on a perspective-warped surface.

### Call sites to update (all in `server.py`)

| Current call | World position available |
|---|---|
| `self.meters_to_pixels(rb.style.size)` | `display_pos` |
| `self.meters_to_pixels(rb.style.label_offset[0/1])` | `display_pos` |
| `self.meters_to_pixels` passed to `draw_trajectory()` | trajectory points |
| `self.meters_to_pixels(prim.radius)` | `drawing.world_x/y` |
| `self.meters_to_pixels(prim.width/height)` | `drawing.world_x/y` |

Every call site already has the world position. No API changes needed for commands or client.

### What stays the same

- Command API: users already specify sizes in field units (meters for "base")
- Drawing commands: `radius`, `width`, `height` are already in field units, converted to world at command time
- Field coordinate conversion at command time (unchanged)

## Consequences

- Circles, boxes, and all sized elements render at correct scale regardless of projector geometry
- Slight per-frame compute cost for the four extra `convert()` calls per sized element (negligible vs. rendering)
- `meters_to_pixels()` removed from server -- all coordinate math lives in `FieldCalibrator`
