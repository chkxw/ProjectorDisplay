#!/usr/bin/env python3
"""
Test: Text rendering — labels at various sizes, colors, and angles.

Creates persistent text drawings and rigid bodies with labels to verify
the text rendering path (which in GLES2 goes through pygame.font -> GL
texture -> textured quad).

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_text_rendering.py [HOST]
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

    print("Creating text at various sizes and positions...")

    # Row of text at different font sizes (top area)
    sizes = [16, 20, 24, 30, 36]
    for i, sz in enumerate(sizes):
        x = CX - 400 + i * 200
        name = f"txt_size_{sz}"
        r = client.draw_text(name, x=x, y=CY - 250,
                             text=f"Size {sz}", color=[255, 255, 255],
                             font_size=sz, field=F)
        print(f"  {name:15s} -> {r.get('status')}")

    # Colored text (middle area)
    colors = [
        ([255, 0, 0], "Red"),
        ([0, 255, 0], "Green"),
        ([0, 100, 255], "Blue"),
        ([255, 255, 0], "Yellow"),
        ([255, 0, 255], "Magenta"),
    ]
    for i, (color, label) in enumerate(colors):
        x = CX - 400 + i * 200
        name = f"txt_color_{label.lower()}"
        r = client.draw_text(name, x=x, y=CY - 100,
                             text=label, color=color, font_size=24, field=F)
        print(f"  {name:15s} -> {r.get('status')}")

    # Rigid bodies with labels (tests label rendering in draw_rigidbody path)
    print("\nCreating labeled rigid bodies...")
    label_bodies = [
        ("labeled_circle", "circle", CX - 250, CY + 100, [200, 100, 100]),
        ("labeled_box",    "box",    CX,       CY + 100, [100, 200, 100]),
        ("labeled_tri",    "triangle", CX + 250, CY + 100, [100, 100, 200]),
    ]
    for name, shape, x, y, color in label_bodies:
        r = client.create_rigidbody(name, style={
            "shape": shape, "size": 0.06, "color": color,
            "label": True, "label_offset": [0, -0.12],
            "orientation_length": 0.10,
        }, trajectory={"enabled": False})
        client.update_position(name, x, y, orientation=math.pi / 6, field=F)
        print(f"  {name:15s} -> {r.get('status')}")

    # A text overlay with background
    r = client.draw_text("txt_with_bg", x=CX, y=CY + 280,
                         text="Text with background", color=[0, 0, 0],
                         font_size=26, field=F)
    print(f"  txt_with_bg    -> {r.get('status')}")

    print("\nText rendering test visible. Press Ctrl+C to clean up...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    for sz in sizes:
        client.remove_drawing(f"txt_size_{sz}")
    for _, label in colors:
        client.remove_drawing(f"txt_color_{label.lower()}")
    client.remove_drawing("txt_with_bg")
    for name, *_ in label_bodies:
        client.remove_rigidbody(name)
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
