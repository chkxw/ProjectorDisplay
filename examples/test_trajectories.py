#!/usr/bin/env python3
"""
Test: Trajectory line styles — solid, dotted, dashed, with gradients.

Creates three rigid bodies side by side, each with a different trajectory
style. Moves them in circles so the trajectories build up visually.

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_trajectories.py [HOST]
"""

import time
import math
import sys
from projector_display.client import DisplayClient

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT = 9999

# Screen layout
SW, SH = 1920, 1080
CX, CY = SW // 2, SH // 2
F = "screen"


def main():
    client = DisplayClient(HOST, PORT)
    client.connect()

    print("Creating 3 bodies with different trajectory styles...")

    # 1. Solid gradient (yellow -> transparent red)
    r = client.create_rigidbody("traj_solid", style={
        "shape": "circle", "size": 0.06, "color": [255, 200, 0],
        "label": True, "label_offset": [0, -0.12],
    }, trajectory={
        "enabled": True, "mode": "time", "length": 4.0,
        "style": "solid", "thickness": 3,
        "color": "gradient",
        "gradient_start": [255, 255, 0, 255],
        "gradient_end": [255, 0, 0, 0],
    })
    print(f"  solid gradient  -> {r.get('status')}")

    # 2. Dotted, single color (cyan)
    r = client.create_rigidbody("traj_dotted", style={
        "shape": "triangle", "size": 0.06, "color": [0, 220, 220],
        "label": True, "label_offset": [0, -0.12],
    }, trajectory={
        "enabled": True, "mode": "time", "length": 4.0,
        "style": "dotted", "thickness": 3, "dot_spacing": 0.04,
        "color": [0, 220, 220, 200],
    })
    print(f"  dotted cyan     -> {r.get('status')}")

    # 3. Dashed gradient (green -> transparent blue)
    r = client.create_rigidbody("traj_dashed", style={
        "shape": "box", "size": 0.05, "color": [100, 255, 100],
        "label": True, "label_offset": [0, -0.12],
    }, trajectory={
        "enabled": True, "mode": "time", "length": 4.0,
        "style": "dashed", "thickness": 3, "dash_length": 0.08,
        "color": "gradient",
        "gradient_start": [0, 255, 0, 255],
        "gradient_end": [0, 100, 255, 60],
    })
    print(f"  dashed gradient -> {r.get('status')}")

    # Move them in circles (screen pixel coords)
    orbit_r = 150  # orbit radius in pixels
    centers = [
        ("traj_solid",  CX - 350, CY, orbit_r),
        ("traj_dotted", CX,       CY, orbit_r),
        ("traj_dashed", CX + 350, CY, orbit_r),
    ]

    print("\nMoving in circles... (Ctrl+C to stop)")
    try:
        t = 0.0
        while True:
            for name, cx, cy, rad in centers:
                x = cx + rad * math.cos(t)
                y = cy + rad * math.sin(t)
                orientation = t + math.pi / 2  # tangent
                client.update_position(name, x, y, orientation=orientation, field=F)
            t += 0.05
            time.sleep(0.033)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    for name, *_ in centers:
        client.remove_rigidbody(name)
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
