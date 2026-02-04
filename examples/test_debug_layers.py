#!/usr/bin/env python3
"""
Test: Debug layers — grid overlay and field boundaries.

Toggles the grid and field layers on, creates a custom field so the
field layer has something to draw, and places a rigid body on the grid
so you can verify coordinate labels.

Usage:
    python examples/test_debug_layers.py [HOST]
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

    # Create a custom field so field layer has something to show
    print("Creating custom field 'test_field'...")
    r = client.create_field(
        name="test_field",
        world_points=[[-1, -1], [1, -1], [1, 1], [-1, 1]],
        local_points=[[0, 0], [2, 0], [2, 2], [0, 2]],
    )
    print(f"  -> {r.get('status')}")

    # Enable both debug layers
    print("Enabling grid layer...")
    r = client.set_grid_layer(enabled=True)
    print(f"  -> {r}")

    print("Enabling field layer...")
    r = client.set_field_layer(enabled=True)
    print(f"  -> {r}")

    # Customize grid colors (brighter for visibility)
    print("Configuring grid colors...")
    r = client.configure_grid_layer(
        show_minor=True,
        major_color=[150, 150, 150, 200],
        minor_color=[70, 70, 70, 120],
    )
    print(f"  -> {r}")

    # Place a marker at (0,0) to verify origin
    r = client.create_rigidbody("grid_marker", style={
        "shape": "circle", "size": 0.05, "color": [255, 255, 0],
        "label": True, "label_offset": [0, -0.12],
    }, trajectory={"enabled": False})
    client.update_position("grid_marker", 0.0, 0.0)
    print(f"  origin marker  -> {r.get('status')}")

    # Place a second marker at (1,1)
    r = client.create_rigidbody("grid_marker_11", style={
        "shape": "triangle", "size": 0.05, "color": [0, 255, 0],
        "label": True, "label_offset": [0, -0.12],
    }, trajectory={"enabled": False})
    client.update_position("grid_marker_11", 1.0, 1.0, orientation=math.pi / 4)
    print(f"  (1,1) marker   -> {r.get('status')}")

    print("\nDebug layers visible. Press Ctrl+C to clean up...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    client.set_grid_layer(enabled=False)
    client.set_field_layer(enabled=False)
    client.remove_rigidbody("grid_marker")
    client.remove_rigidbody("grid_marker_11")
    client.remove_field("test_field")
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
