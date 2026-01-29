---
project_name: 'ProjectorDisplay'
user_name: 'Chkxwlyh'
date: '2026-01-28'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
existing_patterns_found: 11
status: 'complete'
rule_count: 45
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Python** >=3.10 (required for MocapUtility compatibility)
- **pygame** >=2.0.0 -- rendering, fullscreen display, SDL2 multi-display
- **opencv-python** >=4.0.0 -- perspective transforms (FieldCalibrator), background image warp
- **PyYAML** >=6.0 -- config files, scene serialization
- **numpy** >=1.20.0 -- coordinate transform matrices
- **xrandr** -- Linux system dependency for multi-display positioning
- **MocapUtility** -- optional, in `external/` directory (OptiTrack NatNet protocol)

### Dev Tooling
- **black**: line-length 100, target py310
- **ruff**: select E/F/W/I/UP, line-length 100, ignore E501
- **Testing**: Visual verification -- standalone test scripts that exercise functionality, user verifies output by eye (not pytest)

## Critical Implementation Rules

### Python Language Rules

- **All colors are RGBA 4-tuples** `(R, G, B, A)` with values 0-255. Never use 3-tuple RGB internally. Use `parse_color()` from `utils/color.py` to accept user input in any format (hex, RGB, RGBA, float, CSV).
- **Dataclass serialization**: Every data model implements `to_dict()` and `from_dict()` classmethods. `from_dict()` must accept both old (RGB) and new (RGBA) formats for backwards compatibility.
- **Type-dependent fields**: `DrawPrimitive` has many fields but each type uses only a subset. `to_dict()` serializes only relevant fields per type; `from_dict()` provides defaults for all.
- **Optional with fallback**: `RigidBody.orientation` is `Optional[float]`. Always use `get_effective_orientation()` for rendering (falls back to `_last_orientation`). Never read `.orientation` directly for display.
- **Private fields with underscore**: `_mocap_position`, `_mocap_orientation`, `_last_orientation` are runtime-only. Never serialize these to scene YAML. `to_dict(include_runtime=True)` only for API inspection responses.
- **Enum values are lowercase strings**: `RigidBodyShape("circle")`, `DrawPrimitiveType("line")`. Serialization uses `.value` (string), deserialization uses `EnumClass(string)`.
- **deque for position history**: `position_history` uses `collections.deque(maxlen=10000)`. Deep copy required for thread-safe snapshot access.

### Architecture & Framework Rules

- **Command system**: All commands are functions decorated with `@register_command`. First parameter is always `scene` (Scene instance). Must return a `dict` with at least `"status"` key (`"success"` or `"error"`).
- **Command auto-discovery**: Adding a new command module requires importing it in `commands/prebuilt/__init__.py`. Module-level `@register_command` decorators run at import time.
- **Coordinate fields**: Every position command accepts a `field` parameter (default `"base"` = world meters). Convert to world coords at command time via `scene.field_calibrator.convert([x, y], field, "base")`. Never store field-local coords in scene state.
- **Vertex order convention**: Field corner points are always `[BL, BR, TR, TL]` -- counter-clockwise from bottom-left. Index 0=BL, 1=BR, 2=TR, 3=TL.
- **Orientation transform**: Never use raw orientation angles for screen rendering. Always transform via `field_calibrator.transform_orientation()` which uses two-point conversion (position + probe point).
- **Thread safety -- snapshot pattern**: Render loop must never read `_rigidbodies`, `_drawings`, or `_fields` directly. Use `get_rigidbodies_snapshot()`, `get_drawings_snapshot()`, `get_fields_snapshot()` which return deep copies under lock.
- **Scene mutations under lock**: All writes to `_rigidbodies`, `_drawings` must hold `self._lock`. Command handlers run in ThreadPoolExecutor threads.
- **Single render path**: ALL rigid body rendering goes through `draw_rigidbody()` in `primitives.py`. Never bypass this for individual shapes.
- **DrawPrimitive dual semantics**: Same `DrawPrimitive` type used in two contexts -- body-local coords (compound rigid body, `(0,0)` = center, `+x` = orientation, scaled by `style.size`) and world coords (direct drawings, converted from field at creation time). Context determines interpretation.
- **Renderer alpha methods**: For RGBA colors with alpha < 255, use `draw_polygon_alpha()`, `draw_line_alpha()`, `draw_circle_alpha()` which create temporary `SRCALPHA` surfaces. Opaque colors (alpha=255) use direct pygame draw calls for performance.

### Testing Rules

- **No pytest**: This project uses standalone test scripts for visual verification, not pytest. Test files exercise functionality and the user verifies output by eye.
- **Test file location**: Test scripts live at project root or in a dedicated test directory. They connect to a running server as a client.
- **Test pattern**: Each test script creates a `DisplayClient`, sends commands, and produces visible output on the projector display for the user to verify manually.
- **No mocking framework**: Since testing is visual, there are no mock objects or assertion libraries. Correctness is judged by visual inspection.

### Code Quality & Style

- **Line length**: 100 characters (black + ruff configured)
- **File naming**: `snake_case.py` throughout. Command modules suffixed `_commands.py`.
- **Module docstrings**: Every `.py` file starts with a triple-quoted module docstring explaining purpose.
- **Class docstrings**: All public classes have docstrings. Dataclasses document non-obvious fields.
- **F-coded comments**: Inline implementation notes use `# F{N}:` prefix (e.g. `# F1: Snapshot for safe iteration`). These mark design decisions worth preserving.
- **ADR references in code**: When implementing an architectural decision, reference it in comments/docstrings: `(ADR-8)`, `(ADR-10)`, etc.
- **No over-engineering**: Only make changes directly requested. Don't add features, error handling for impossible cases, or abstractions for one-time operations.
- **Imports**: Standard library first, then third-party, then local. Lazy imports only when avoiding circular dependencies (e.g. `DrawPrimitive` in `RigidBodyStyle.from_dict()`).

### Development Workflow

- **Commit message format**: `<Type>: <short summary under 72 chars>`. Types: `Implement`, `Fix`, `Refactor`, `Add`, `Update`, `Mark`.
- **No co-author lines**: Never include `Co-Authored-By` trailers in commits.
- **Imperative mood**: "Add feature" not "Added feature".
- **ADR references in commits**: Include `(ADR-X)` when implementing architectural decisions (e.g. `Refactor colors to RGBA format (ADR-8)`).
- **Branch conventions**: `main` for implementation code, `bmad` for scaffold/docs.
- **No auto-push**: Never push to remote unless explicitly asked.
- **Commit body optional**: Use for complex changes needing explanation. Keep summary line self-sufficient.

### Critical Don't-Miss Rules

- **Never crash on bad commands**: Malformed JSON, missing params, invalid values return error responses. Server keeps running. But unhandled exceptions in command handlers (actual bugs) SHOULD crash -- do not catch generic `Exception` in handlers.
- **Never store field-local coordinates**: All positions in `RigidBody`, `Drawing`, and scene state are in world meters. Conversion from field coords happens once at command time, not at render time.
- **Never read scene state from render thread without snapshot**: Direct access to `_rigidbodies` or `_drawings` from the render loop causes race conditions. Always use the `get_*_snapshot()` methods.
- **Never serialize runtime MoCap state**: `_mocap_position`, `_mocap_orientation`, `tracking_lost` are transient. `to_dict()` excludes them by default. Only `to_dict(include_runtime=True)` includes them (for API inspection only).
- **Calibration file is mandatory**: Server refuses to start without `calibration.yaml`. The "screen" field must exist before any rendering occurs.
- **Drawing IDs are replace-on-collision**: Sending a drawing command with an existing ID silently replaces it. This is intentional -- enables update-in-place without remove+add.
- **Compound body scale**: `style.size` for COMPOUND shapes is the scale factor (pixels per local unit), not a radius. Local coords `(1, 0)` maps to `style.size` pixels from center in the orientation direction.
- **Render order matters**: Backgrounds -> debug layers -> trajectories -> bodies -> drawings -> flip. Persistent drawings render ON TOP of rigid bodies.
- **SDL2 borderless window**: Display uses `NOFRAME` (not `FULLSCREEN`) so the window stays visible when focus is lost. This is deliberate for projector use.

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Update this file if new patterns emerge

**For Humans:**

- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review periodically for outdated rules
- Remove rules that become obvious over time

Last Updated: 2026-01-28
