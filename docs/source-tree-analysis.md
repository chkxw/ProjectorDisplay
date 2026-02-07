# Source Tree Analysis

**Generated:** 2026-02-07 | **Scan Level:** Exhaustive

## Repository Structure

The project root contains symlinks into `_bmad-worktree/` (tracked in a separate git worktree branch) for AI tooling scaffolds. These are gitignored from the main branch and not part of the application.

```
ProjectorDisplay/
├── projector_display/              # Main Python package (the application)
│   ├── __init__.py                 # Package exports: FieldCalibrator, Field, RigidBody,
│   │                               #   RigidBodyStyle, TrajectoryStyle, Scene, DisplayClient
│   ├── server.py                   # ★ ENTRY POINT — ProjectorDisplayServer + main()
│   │                               #   Multi-threaded server: render loop, socket server,
│   │                               #   command dispatch, vertex-transform pipeline
│   ├── client.py                   # DisplayClient — TCP/JSON client API with auto-reconnect
│   ├── storage.py                  # StorageManager — XDG-compliant persistent + session storage
│   │
│   ├── core/                       # Domain model (data-only, no rendering)
│   │   ├── __init__.py             # Re-exports all core types
│   │   ├── scene.py                # Scene — thread-safe container for all displayable state
│   │   ├── rigidbody.py            # RigidBody, RigidBodyStyle, TrajectoryStyle, RigidBodyShape
│   │   ├── draw_primitive.py       # DrawPrimitive, DrawPrimitiveType, Drawing
│   │   └── field_calibrator.py     # FieldCalibrator, Field — perspective homography via OpenCV
│   │
│   ├── rendering/                  # All rendering code
│   │   ├── __init__.py             # Re-exports Renderer, PygameRenderer, GLESRenderer
│   │   ├── renderer/               # Renderer protocol + implementations
│   │   │   ├── __init__.py         # Lazy import of GLESRenderer (optional OpenGL dependency)
│   │   │   ├── base.py             # Renderer Protocol + SDL display utilities (xrandr, SDL2)
│   │   │   ├── pygame_renderer.py  # PygameRenderer — software renderer (CPU, SRCALPHA surfaces)
│   │   │   └── gles_renderer.py    # ★ GLESRenderer — GPU-accelerated GLES2 renderer
│   │   │                           #   Direct ctypes GL bindings, buffer orphaning, text LRU cache
│   │   ├── primitives.py           # Shape drawing: draw_rigidbody(), draw_compound(), draw_label()
│   │   │                           #   Vertex-transform pipeline: body-local → world → screen
│   │   ├── trajectory.py           # Trajectory rendering: solid/dotted/dashed with RGBA gradients
│   │   ├── debug_layers.py         # GridLayer (coordinate grid) + FieldLayer (field boundaries)
│   │   └── background.py           # BackgroundRenderer — field backgrounds with perspective warp
│   │
│   ├── commands/                   # Command dispatch system
│   │   ├── __init__.py             # Exports CommandRegistry, register_command, get_registry()
│   │   ├── base.py                 # CommandRegistry + @register_command decorator
│   │   └── prebuilt/               # Built-in command handlers (~2000 lines total)
│   │       ├── __init__.py         # Auto-imports all command modules to register them
│   │       ├── rigidbody_commands.py   # create/remove/update_position/style/trajectory/get/list
│   │       ├── field_commands.py       # create/remove/get/list fields, set_calibration, backgrounds
│   │       ├── scene_commands.py       # clear/dump/load/save scenes, status, persistent storage
│   │       ├── debug_commands.py       # toggle/set/configure grid & field layers
│   │       ├── asset_commands.py       # check/upload/list/delete images (base64 + SHA256 verify)
│   │       ├── drawing_commands.py     # draw circle/box/line/arrow/polygon/text, remove/list/clear
│   │       └── mocap_commands.py       # set_mocap/enable/disable, auto_track per rigidbody
│   │
│   ├── utils/                      # Shared utilities
│   │   ├── __init__.py             # Re-exports logging + color utilities
│   │   ├── color.py                # parse_color() — hex/RGB/RGBA/float/CSV → RGBA tuple
│   │   ├── logging.py              # Dual-sink logging (stdout + file)
│   │   └── profiler.py             # FrameProfiler — per-section timing with periodic log reports
│   │
│   └── mocap/                      # MoCap integration (optional)
│       ├── __init__.py             # Exports MocapTracker, MocapConfig, DEFAULT_NATNET_PORT
│       └── tracker.py              # MocapTracker — OptiTrack NatNet polling thread, lazy import
│
├── config/                         # Configuration templates
│   ├── server_config.yaml          # Server settings (host, port, display, FPS)
│   └── calibration_example.yaml    # Calibration template (world↔screen mapping)
│
├── examples/                       # Visual integration test scripts
│   ├── basic_usage.py              # General client API demo
│   ├── test_all_shapes.py          # All 5 rigid body shapes
│   ├── test_drawings.py            # All persistent drawing overlay types
│   ├── test_trajectories.py        # Trajectory styles with gradients
│   ├── test_alpha_blending.py      # Overlapping semi-transparent shapes
│   ├── test_debug_layers.py        # Grid + field boundary overlays
│   ├── test_field_backgrounds.py   # Solid-color field backgrounds
│   ├── test_stress.py              # Performance benchmark (N bodies at 30 Hz)
│   ├── test_text_rendering.py      # Text sizes, colors, label pipeline
│   └── test_line_batch.py          # Line batch rendering + grid interaction
│
├── external/                       # Git submodules
│   ├── __init__.py                 # Makes external/ importable
│   └── MocapUtility/               # OptiTrack NatNet client (git submodule)
│       ├── MocapUtility.py         # Main MoCap client class
│       ├── Client.py               # NatNet protocol client
│       ├── NatNetTypes.py          # NatNet data types
│       └── Unpackers.py            # Binary data unpacking
│
├── pyproject.toml                  # Build configuration, dependencies, CLI entry point
├── README.md                       # Project documentation (legacy, partially current)
├── EXAMPLES.md                     # Detailed example script documentation
├── .gitmodules                     # Git submodule config (external/MocapUtility)
├── .gitignore                      # Ignores _bmad*, .claude, .codex, .gemini, _reference, Python artifacts
│
├── _bmad-worktree/                 # BMAD scaffolding (separate git worktree branch)
│   ├── _bmad/                      # → symlinked to project root as _bmad
│   ├── _bmad-output/               # → symlinked to project root as _bmad-output
│   ├── .claude/                    # → symlinked to project root as .claude
│   ├── .codex/                     # → symlinked to project root as .codex
│   └── .gemini/                    # → symlinked to project root as .gemini
│
├── _reference -> .../box_push_deploy/shared   # Symlink to legacy origin repo
│
└── docs/                           # Generated documentation (this output)
```

## Critical Directories

| Directory | Purpose | Key Files |
|---|---|---|
| `projector_display/` | Main package | `server.py` (entry), `client.py` (API) |
| `projector_display/core/` | Domain model | `scene.py`, `rigidbody.py`, `field_calibrator.py` |
| `projector_display/rendering/renderer/` | Renderer backends | `gles_renderer.py` (GPU), `pygame_renderer.py` (CPU) |
| `projector_display/commands/prebuilt/` | Command handlers | 7 modules, ~2000 LOC total |
| `config/` | Configuration templates | `calibration_example.yaml` |
| `examples/` | Visual test scripts | 10 scripts covering all features |
| `external/MocapUtility/` | Optional MoCap client | Git submodule |

## Entry Points

| Entry Point | Invocation | Purpose |
|---|---|---|
| `projector_display.server:main` | `projector-display-server` CLI | Start the display server |
| `projector_display.DisplayClient` | `from projector_display import DisplayClient` | Client library import |
| `examples/*.py` | `python examples/test_*.py [HOST]` | Visual integration tests |

## File Statistics

| Category | Files | Approx LOC |
|---|---|---|
| Core domain model | 4 | ~850 |
| Server | 1 | ~1040 |
| Client | 1 | ~780 |
| Rendering | 6 | ~2200 |
| Commands | 9 | ~2100 |
| Utils | 3 | ~400 |
| MoCap | 2 | ~470 |
| Storage | 1 | ~250 |
| **Total source** | **27** | **~8100** |
| Examples | 10 | ~800 |
| Config | 2 | ~60 |
