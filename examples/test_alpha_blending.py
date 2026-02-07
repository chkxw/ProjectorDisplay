#!/usr/bin/env python3
"""
Test: Alpha blending — overlapping semi-transparent shapes.

Creates several overlapping shapes with different alpha values to verify
that the renderer's blending works correctly. You should see the colors
mixing where shapes overlap.

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_alpha_blending.py [HOST]
"""

import time
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

    print("Creating overlapping semi-transparent shapes...")

    # Three large overlapping circles (RGB at 50% alpha) — classic alpha test
    r = client.create_rigidbody("alpha_r", style={
        "shape": "circle", "size": 0.15,
        "color": [255, 0, 0, 120],  # Red, 47% alpha
        "label": False,
    }, trajectory={"enabled": False})
    print(f"  red circle     -> {r.get('status')}")

    r = client.create_rigidbody("alpha_g", style={
        "shape": "circle", "size": 0.15,
        "color": [0, 255, 0, 120],  # Green
        "label": False,
    }, trajectory={"enabled": False})
    print(f"  green circle   -> {r.get('status')}")

    r = client.create_rigidbody("alpha_b", style={
        "shape": "circle", "size": 0.15,
        "color": [0, 0, 255, 120],  # Blue
        "label": False,
    }, trajectory={"enabled": False})
    print(f"  blue circle    -> {r.get('status')}")

    # Venn diagram arrangement (upper half of screen)
    venn_y = CY - 100
    client.update_position("alpha_r", CX - 80, venn_y + 60, field=F)
    client.update_position("alpha_g", CX + 80, venn_y + 60, field=F)
    client.update_position("alpha_b", CX,      venn_y - 60, field=F)

    # Semi-transparent boxes at different alphas (lower half)
    alphas = [40, 80, 120, 180, 240]
    box_y = CY + 200
    for i, alpha in enumerate(alphas):
        name = f"alpha_box_{alpha}"
        x = CX - 300 + i * 150
        r = client.create_rigidbody(name, style={
            "shape": "box", "size": 0.06,
            "color": [255, 200, 0, alpha],
            "label": True, "label_offset": [0, -0.10],
        }, trajectory={"enabled": False})
        client.update_position(name, x, box_y, field=F)
        print(f"  box alpha={alpha:3d}  -> {r.get('status')}")

    # Semi-transparent white overlay across the Venn diagram
    margin = 150
    r = client.draw_polygon("alpha_overlay",
                            vertices=[[CX - margin, venn_y - margin],
                                      [CX + margin, venn_y - margin],
                                      [CX + margin, venn_y + margin],
                                      [CX - margin, venn_y + margin]],
                            color=[255, 255, 255, 50], filled=True, field=F)
    print(f"  white overlay  -> {r.get('status')}")

    print("\nAlpha blending test visible. Press Ctrl+C to clean up...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\nCleaning up...")
    names = ["alpha_r", "alpha_g", "alpha_b"]
    names += [f"alpha_box_{a}" for a in alphas]
    for name in names:
        client.remove_rigidbody(name)
    client.remove_drawing("alpha_overlay")
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
