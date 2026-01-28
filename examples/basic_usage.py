#!/usr/bin/env python3
"""
Basic usage example for projector display client.

This example demonstrates:
1. Connecting to the display server
2. Creating rigid bodies
3. Updating positions with orientation
4. Creating custom fields
5. Using trajectory visualization
6. Scene inspection

Prerequisites:
- Display server running: projector-display-server --calibration path/to/calibration.yaml
"""

import time
import math
from projector_display import DisplayClient


def main():
    # Connect to display server
    # Replace with your server's IP address
    server_host = "localhost"

    print(f"Connecting to display server at {server_host}...")

    with DisplayClient(server_host, port=9999) as client:
        if not client.is_connected:
            print("Failed to connect to display server")
            return

        print("Connected!")

        # Create a robot with custom style
        print("\nCreating robot1 with red circle style...")
        client.create_rigidbody(
            "robot1",
            style={
                "shape": "circle",
                "size": 0.15,  # 15cm radius
                "color": [255, 0, 0],  # Red
                "label": True,
                "orientation_length": 0.2,  # 20cm arrow
                "orientation_color": [255, 255, 255],
            },
            trajectory={
                "enabled": True,
                "mode": "time",
                "length": 5.0,  # Show last 5 seconds
                "style": "solid",
                "color": "gradient",
                "gradient_start": [255, 0, 0],
                "gradient_end": [100, 0, 0],
            }
        )

        # Create a box-shaped payload
        print("Creating payload1 with blue box style...")
        client.create_rigidbody(
            "payload1",
            style={
                "shape": "box",
                "size": 0.1,  # 10cm half-size (20x20cm box)
                "color": [0, 100, 255],  # Blue
                "label": True,
            },
            trajectory={
                "enabled": False,  # No trajectory for static object
            }
        )

        # Update initial positions
        print("\nSetting initial positions...")
        client.update_position("robot1", 1.0, 1.0, orientation=0.0)
        client.update_position("payload1", 2.0, 1.5)

        # Get server status
        status = client.status()
        print(f"\nServer status: {status}")

        # Simulate robot movement
        print("\nSimulating robot movement (press Ctrl+C to stop)...")
        try:
            t = 0
            while True:
                # Circular motion
                x = 2.0 + 0.5 * math.cos(t)
                y = 1.5 + 0.5 * math.sin(t)
                orientation = t + math.pi / 2  # Tangent to circle

                client.update_position("robot1", x, y, orientation=orientation)

                t += 0.05
                time.sleep(0.033)  # ~30 Hz

        except KeyboardInterrupt:
            print("\nStopping simulation...")

        # Clean up
        print("\nCleaning up...")
        client.clear_scene()

    print("Done!")


if __name__ == "__main__":
    main()
