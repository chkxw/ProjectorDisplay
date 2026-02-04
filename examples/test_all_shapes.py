#!/usr/bin/env python3
"""
Test: All rigid body shapes rendered simultaneously.

Creates one of each shape type (circle, box, triangle, polygon, compound)
spread across the screen, each with a distinct color. Rotates them slowly
so you can verify orientation rendering.

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_all_shapes.py [HOST]
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

    print("Creating 5 shape types...")

    # 1. Circle — red
    r = client.create_rigidbody("shape_circle", style={
        "shape": "circle",
        "size": 0.08,
        "color": [255, 60, 60],
        "label": True,
        "label_offset": [0, -0.15],
        "orientation_length": 0.12,
    }, trajectory={"enabled": False})
    print(f"  circle  -> {r.get('status')}")

    # 2. Box — green
    r = client.create_rigidbody("shape_box", style={
        "shape": "box",
        "size": 0.07,
        "color": [60, 200, 60],
        "label": True,
        "label_offset": [0, -0.15],
        "orientation_length": 0.10,
    }, trajectory={"enabled": False})
    print(f"  box     -> {r.get('status')}")

    # 3. Triangle — blue
    r = client.create_rigidbody("shape_triangle", style={
        "shape": "triangle",
        "size": 0.08,
        "color": [60, 100, 255],
        "label": True,
        "label_offset": [0, -0.15],
        "orientation_length": 0.12,
    }, trajectory={"enabled": False})
    print(f"  triangle-> {r.get('status')}")

    # 4. Polygon — pentagon, magenta
    angle_step = 2 * math.pi / 5
    pentagon = [(math.cos(i * angle_step), math.sin(i * angle_step)) for i in range(5)]
    r = client.create_rigidbody("shape_polygon", style={
        "shape": "polygon",
        "size": 0.07,
        "color": [220, 60, 220],
        "label": True,
        "label_offset": [0, -0.15],
        "polygon_vertices": pentagon,
        "orientation_length": 0.10,
    }, trajectory={"enabled": False})
    print(f"  polygon -> {r.get('status')}")

    # 5. Compound — body with two wheels, orange
    r = client.create_rigidbody("shape_compound", style={
        "shape": "compound",
        "size": 0.07,
        "color": [255, 165, 0],
        "label": True,
        "label_offset": [0, -0.18],
        "orientation_length": 0.10,
        "draw_list": [
            # Main body — box
            {"type": "box", "x": 0, "y": 0, "width": 1.4, "height": 0.8,
             "color": [255, 165, 0], "filled": True},
            # Left wheel
            {"type": "circle", "x": -0.5, "y": -0.5, "radius": 0.25,
             "color": [80, 80, 80], "filled": True},
            # Right wheel
            {"type": "circle", "x": -0.5, "y": 0.5, "radius": 0.25,
             "color": [80, 80, 80], "filled": True},
            # Direction arrow
            {"type": "arrow", "x": 0, "y": 0, "x2": 0.8, "y2": 0,
             "color": [255, 255, 255], "thickness": 2},
        ],
    }, trajectory={"enabled": False})
    print(f"  compound-> {r.get('status')}")

    # Place them in a row across the screen center
    spacing = 250
    positions = [
        ("shape_circle",   CX - 2 * spacing, CY),
        ("shape_box",      CX - spacing,     CY),
        ("shape_triangle", CX,               CY),
        ("shape_polygon",  CX + spacing,     CY),
        ("shape_compound", CX + 2 * spacing, CY),
    ]

    for name, x, y in positions:
        client.update_position(name, x, y, orientation=0.0, field=F)

    print("\nRotating all shapes slowly... (Ctrl+C to stop)")
    try:
        t = 0.0
        while True:
            angle = t * 0.5  # half a radian per second
            for name, x, y in positions:
                client.update_position(name, x, y, orientation=angle, field=F)
            t += 0.033
            time.sleep(0.033)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    for name, _, _ in positions:
        client.remove_rigidbody(name)
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
