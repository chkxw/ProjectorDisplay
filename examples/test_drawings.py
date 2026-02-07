#!/usr/bin/env python3
"""
Test: Persistent drawing overlays — every DrawPrimitive type.

Creates persistent drawings (circle, box, line, arrow, polygon, text)
scattered across the screen. Leaves them visible for visual inspection,
then cleans up on Ctrl+C.

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_drawings.py [HOST]
"""

import sys
import time
import math
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

    print("Creating persistent drawing overlays...")

    # 1. Filled circle
    r = client.draw_circle("d_circle_filled", x=CX - 350, y=CY - 150,
                           radius=0.06, color=[255, 100, 100], filled=True,
                           field=F)
    print(f"  filled circle  -> {r.get('status')}")

    # 2. Outlined circle
    r = client.draw_circle("d_circle_outline", x=CX - 350, y=CY + 100,
                           radius=0.06, color=[100, 255, 100], filled=False,
                           thickness=3, field=F)
    print(f"  outline circle -> {r.get('status')}")

    # 3. Filled box
    r = client.draw_box("d_box_filled", x=CX - 100, y=CY - 150,
                        width=0.10, height=0.07,
                        color=[100, 100, 255], filled=True, field=F)
    print(f"  filled box     -> {r.get('status')}")

    # 4. Outlined box, rotated 45 deg
    r = client.draw_box("d_box_outline", x=CX - 100, y=CY + 100,
                        width=0.10, height=0.07,
                        color=[255, 255, 100], filled=False, thickness=2,
                        angle=0.785, field=F)
    print(f"  rotated box    -> {r.get('status')}")

    # 5. Line
    r = client.draw_line("d_line", x1=CX + 100, y1=CY - 200,
                         x2=CX + 200, y2=CY + 150,
                         color=[255, 165, 0], thickness=3, field=F)
    print(f"  line           -> {r.get('status')}")

    # 6. Arrow
    r = client.draw_arrow("d_arrow", x1=CX + 250, y1=CY - 200,
                          x2=CX + 400, y2=CY + 100,
                          color=[0, 255, 200], thickness=3, field=F)
    print(f"  arrow          -> {r.get('status')}")

    # 7. Polygon — hexagon
    hex_cx, hex_cy, hex_r = CX + 500, CY, 80
    hex_verts = [
        [hex_cx + hex_r * math.cos(i * math.pi / 3),
         hex_cy + hex_r * math.sin(i * math.pi / 3)]
        for i in range(6)
    ]
    r = client.draw_polygon("d_hexagon", vertices=hex_verts,
                            color=[200, 100, 255], filled=True, field=F)
    print(f"  hexagon        -> {r.get('status')}")

    # 8. Text label
    r = client.draw_text("d_text", x=CX, y=CY - 350,
                         text="GLES2 Test", color=[255, 255, 255],
                         font_size=30, field=F)
    print(f"  text           -> {r.get('status')}")

    # 9. Semi-transparent filled polygon (RGBA alpha test)
    r = client.draw_polygon("d_alpha_poly",
                            vertices=[[CX - 500, CY - 100],
                                      [CX - 350, CY - 100],
                                      [CX - 350, CY + 200],
                                      [CX - 500, CY + 200]],
                            color=[255, 255, 0, 100], filled=True, field=F)
    print(f"  alpha polygon  -> {r.get('status')}")

    # Verify we can list them
    listing = client.list_drawings()
    ids = listing.get("drawings", [])
    print(f"\nDrawings on server ({len(ids)}): {ids}")

    print("\nAll drawings rendered. Press Ctrl+C to clean up...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    client.clear_drawings()
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
