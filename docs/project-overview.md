# ProjectorDisplay — Project Overview

**Generated:** 2026-02-07 | **Scan Level:** Exhaustive | **Mode:** Initial Scan

## Executive Summary

ProjectorDisplay is a Python library and display server for projector-based robot experiment visualization. It renders rigid bodies, coordinate fields, trajectory trails, and drawing overlays onto a fullscreen projector display, driven by a TCP/JSON command protocol. The system is designed for research labs where a ceiling-mounted projector overlays visual information (markers, paths, zones) onto a physical workspace tracked by motion capture.

## Project Identity

| Property | Value |
|---|---|
| **Name** | `projector-display` |
| **Version** | 1.0.0 |
| **License** | MIT |
| **Python** | >= 3.10 |
| **Package** | `projector_display` |
| **CLI Entry** | `projector-display-server` |
| **Repository** | Monolith (single package) |

## Origin

The codebase evolved from `box_push_deploy/shared/display_toolbox.py` and related modules in a robotics research project. The `_reference` symlink in the project root points to that legacy repo. Module docstrings still reference the origin (`"Based on ... from box_push_deploy/shared/"`), but ProjectorDisplay is a standalone, pip-installable package.

## Core Concepts

1. **Scene** — Single scene per server instance. Contains all displayable state: rigid bodies, coordinate fields, persistent drawings. Thread-safe via lock + snapshot pattern.

2. **RigidBody** — First-class displayable entity. Represents robots, payloads, or any tracked object. Supports 5 shape types (circle, box, triangle, polygon, compound), orientation arrows, labels, and time/distance-based trajectory trails.

3. **Field** — Named rectangular coordinate region with perspective-correct mapping. Fields define local coordinate systems (e.g., an "experiment_zone" within the larger world space). The "screen" field maps world meters to display pixels via calibration.

4. **Drawing** — Persistent overlay anchored in world coordinates. Supports circles, boxes, lines, arrows, polygons, and text. Drawings remain visible until explicitly removed.

5. **Calibration** — Required YAML file mapping physical world corners (meters) to screen pixel corners. Establishes the perspective homography for all coordinate conversions.

## Technology Stack Summary

| Category | Technology | Version |
|---|---|---|
| Language | Python | >= 3.10 |
| Rendering (software) | pygame | >= 2.0.0 |
| Rendering (GPU) | PyOpenGL (GLES2) | >= 3.1.6 |
| Coordinate transforms | OpenCV (cv2) | >= 4.0.0 |
| Numerics | NumPy | >= 1.20.0 |
| Configuration | PyYAML | >= 6.0 |
| Networking | stdlib socket + json | — |
| Motion capture | MocapUtility (optional git submodule) | — |
| Build system | setuptools | >= 61.0 |

## Architecture Pattern

**Multi-threaded server with command-dispatch pattern:**

- Main thread: pygame render loop at configurable FPS (default 30 Hz)
- Socket thread: accepts TCP client connections
- Worker threads: `ThreadPoolExecutor` handles client commands concurrently
- Thread safety: scene state accessed via lock-protected snapshots (deep copy for render)

**Rendering pipeline:**
```
backgrounds → debug layers → trajectories → rigid bodies → drawings → flip
```

All shapes go through a **vertex-transform pipeline**: geometry is expanded in source coordinate space (field-space or body-local), then batch-converted to screen pixels via OpenCV perspective homography.

## Key Integration Points

- **Client library** (`DisplayClient`): Python API wrapping TCP/JSON protocol. Context manager support, auto-reconnect.
- **TCP/JSON protocol**: Language-agnostic. Any client (Python, C++, MATLAB, netcat) can control the server.
- **MoCap**: Optional OptiTrack NatNet integration via `external/MocapUtility` git submodule. Background polling thread updates rigid body positions automatically.
- **Persistent storage**: XDG-compliant (`~/.local/share/projector_display/`). Scenes saved/loaded with images.

## Links

- [Architecture](./architecture.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Development Guide](./development-guide.md)
- [Index](./index.md)
