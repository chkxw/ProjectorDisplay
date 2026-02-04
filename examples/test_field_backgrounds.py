#!/usr/bin/env python3
"""
Test: Field backgrounds — solid colors with varying alpha.

Creates several fields side by side with different solid-color backgrounds
and alpha values. Places rigid bodies on top to verify draw ordering.

Usage:
    python examples/test_field_backgrounds.py [HOST]
"""

import time
import math
import sys
from projector_display.client import DisplayClient

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT = 9999


def main():
    client = DisplayClient(HOST, PORT)
    client.connect()

    # Create three side-by-side fields with colored backgrounds
    fields = [
        {
            "name": "bg_red",
            "world_points": [[-1.2, -0.5], [-0.5, -0.5], [-0.5, 0.5], [-1.2, 0.5]],
            "local_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "color": [180, 40, 40],
            "alpha": 150,
        },
        {
            "name": "bg_green",
            "world_points": [[-0.3, -0.5], [0.4, -0.5], [0.4, 0.5], [-0.3, 0.5]],
            "local_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "color": [40, 160, 40],
            "alpha": 200,
        },
        {
            "name": "bg_blue",
            "world_points": [[0.6, -0.5], [1.3, -0.5], [1.3, 0.5], [0.6, 0.5]],
            "local_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "color": [40, 60, 200],
            "alpha": 255,
        },
    ]

    for fld in fields:
        print(f"Creating field '{fld['name']}' with color {fld['color']} alpha={fld['alpha']}...")
        r = client.create_field(
            name=fld["name"],
            world_points=fld["world_points"],
            local_points=fld["local_points"],
            color=fld["color"],
        )
        print(f"  create -> {r.get('status')}")

        # Set alpha via low-level command
        r = client._send_command({
            "action": "set_field_background_color",
            "field": fld["name"],
            "color": fld["color"],
            "alpha": fld["alpha"],
        })
        print(f"  bg     -> {r.get('status')}")

    # Place a rigid body in each field to verify z-order
    bodies = [
        ("bg_rb_red",   -0.85, 0.0, [255, 255, 255]),
        ("bg_rb_green",  0.05, 0.0, [255, 255, 0]),
        ("bg_rb_blue",   0.95, 0.0, [255, 100, 0]),
    ]

    for name, x, y, color in bodies:
        r = client.create_rigidbody(name, style={
            "shape": "circle", "size": 0.06, "color": color,
            "label": True, "label_offset": [0, -0.12],
        }, trajectory={"enabled": False})
        client.update_position(name, x, y, orientation=0.0)
        print(f"  body '{name}' -> {r.get('status')}")

    # Add a text label above the fields
    r = client.draw_text("bg_title", x=0.0, y=0.7,
                         text="Field Background Test", color=[255, 255, 255],
                         font_size=28)
    print(f"  title -> {r.get('status')}")

    print("\nField backgrounds visible. Press Ctrl+C to clean up...")
    try:
        t = 0.0
        while True:
            # Slowly rotate the bodies
            for name, x, y, _ in bodies:
                client.update_position(name, x, y, orientation=t)
            t += 0.03
            time.sleep(0.033)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    for name, *_ in bodies:
        client.remove_rigidbody(name)
    client.remove_drawing("bg_title")
    for fld in fields:
        client.remove_field(fld["name"])
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
