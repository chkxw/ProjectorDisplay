#!/usr/bin/env python3
"""
Test: Stress test — many rigid bodies with trajectories.

Creates N rigid bodies all moving simultaneously to stress-test rendering
performance. Prints the command round-trip time so you can gauge server load.

Uses screen pixel coordinates (field="screen") so shapes are always visible.

Usage:
    python examples/test_stress.py [HOST] [COUNT]
    COUNT defaults to 20.
"""

import time
import math
import sys
from projector_display.client import DisplayClient

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 20
PORT = 9999

F = "screen"


def main():
    client = DisplayClient(HOST, PORT)
    client.connect()

    lp = client.get_field("screen")["field"]["local_points"]
    CX = (min(p[0] for p in lp) + max(p[0] for p in lp)) / 2
    CY = (min(p[1] for p in lp) + max(p[1] for p in lp)) / 2

    print(f"Creating {COUNT} rigid bodies with trajectories...")
    names = []
    for i in range(COUNT):
        name = f"stress_{i:03d}"
        hue = i / COUNT
        # HSV-like color cycle
        r_c = int(255 * max(0, min(1, abs(hue * 6 - 3) - 1)))
        g_c = int(255 * max(0, min(1, 2 - abs(hue * 6 - 2))))
        b_c = int(255 * max(0, min(1, 2 - abs(hue * 6 - 4))))

        client.create_rigidbody(name, style={
            "shape": "circle", "size": 0.03,
            "color": [r_c, g_c, b_c],
            "label": False,
        }, trajectory={
            "enabled": True, "mode": "time", "length": 3.0,
            "style": "solid", "thickness": 2,
            "color": [r_c, g_c, b_c, 150],
        })
        names.append(name)

    print(f"Created {COUNT} bodies. Moving them... (Ctrl+C to stop)")
    print("Reporting round-trip time for position updates.\n")

    try:
        t = 0.0
        iteration = 0
        while True:
            t0 = time.perf_counter()

            for i, name in enumerate(names):
                # Each body orbits a slightly different center (in screen pixels)
                phase = 2 * math.pi * i / COUNT
                orbit_r = 150 + 80 * math.sin(phase * 2)
                off_x = 250 * math.cos(phase)
                off_y = 200 * math.sin(phase)
                x = CX + off_x + orbit_r * math.cos(t + phase)
                y = CY + off_y + orbit_r * math.sin(t + phase)
                orientation = t + phase + math.pi / 2
                client.update_position(name, x, y, orientation=orientation, field=F)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            if iteration % 30 == 0:
                print(f"  [{iteration:5d}] {COUNT} updates in {elapsed_ms:.1f} ms "
                      f"({elapsed_ms / COUNT:.2f} ms/body)")

            t += 0.05
            iteration += 1
            time.sleep(max(0, 0.033 - elapsed_ms / 1000))
    except KeyboardInterrupt:
        pass

    print(f"\nCleaning up {COUNT} bodies...")
    client.clear_scene()
    client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
