#!/usr/bin/env python3
"""
Test: Line batch rendering — grid layer with many alpha lines.

Enables the grid overlay (which internally uses draw_line_batch for
efficiency) and also draws a custom "starburst" pattern via persistent
drawings to exercise line rendering at scale.

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_line_batch.py [HOST]
"""

import time
import math
import sys
from projector_display.client import DisplayClient

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT = 9999

F = "screen"


def main():
    client = DisplayClient(HOST, PORT)
    client.connect()

    lp = client.get_field("screen")["field"]["local_points"]
    CX = (min(p[0] for p in lp) + max(p[0] for p in lp)) / 2
    CY = (min(p[1] for p in lp) + max(p[1] for p in lp)) / 2

    # Enable grid layer (tests draw_line_batch with alpha lines)
    print("Enabling grid layer (exercises draw_line_batch)...")
    client.set_grid_layer(enabled=True)
    client.configure_grid_layer(
        show_minor=True,
        major_color=[120, 120, 120, 180],
        minor_color=[60, 60, 60, 80],
    )

    # Draw a starburst of lines from screen center
    print("Drawing starburst pattern (40 lines)...")
    num_rays = 40
    ray_length = 300  # pixels
    for i in range(num_rays):
        angle = 2 * math.pi * i / num_rays
        x2 = CX + ray_length * math.cos(angle)
        y2 = CY + ray_length * math.sin(angle)

        # Cycle through rainbow colors
        hue = i / num_rays
        r = int(255 * max(0, min(1, abs(hue * 6 - 3) - 1)))
        g = int(255 * max(0, min(1, 2 - abs(hue * 6 - 2))))
        b = int(255 * max(0, min(1, 2 - abs(hue * 6 - 4))))

        resp = client.draw_line(
            f"ray_{i:02d}", x1=CX, y1=CY, x2=x2, y2=y2,
            color=[r, g, b, 200], thickness=2, field=F,
        )
        if i == 0:
            print(f"  first ray -> {resp.get('status')}")

    print(f"  ... {num_rays} rays created")

    # Add a circle at the center
    client.draw_circle("ray_center", x=CX, y=CY, radius=0.02,
                       color=[255, 255, 255], filled=True, field=F)

    # Add a moving body to see it interact with the grid
    client.create_rigidbody("grid_mover", style={
        "shape": "triangle", "size": 0.04, "color": [255, 200, 50],
        "label": False,
    }, trajectory={
        "enabled": True, "mode": "time", "length": 3.0,
        "style": "solid", "thickness": 2,
        "color": [255, 200, 50, 180],
    })

    orbit_r = 200  # pixels
    print("\nLine batch test visible. Moving body... (Ctrl+C to stop)")
    try:
        t = 0.0
        while True:
            x = CX + orbit_r * math.cos(t * 0.7)
            y = CY + orbit_r * math.sin(t * 0.7)
            client.update_position("grid_mover", x, y,
                                   orientation=t * 0.7 + math.pi / 2, field=F)
            t += 0.05
            time.sleep(0.033)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    client.set_grid_layer(enabled=False)
    for i in range(num_rays):
        client.remove_drawing(f"ray_{i:02d}")
    client.remove_drawing("ray_center")
    client.remove_rigidbody("grid_mover")
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
