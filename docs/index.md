# ProjectorDisplay Documentation Index

**Generated:** 2026-02-07 | **Scan Level:** Exhaustive | **Mode:** Initial Scan

## Project Overview

- **Type:** Monolith (single Python package)
- **Primary Language:** Python >= 3.10
- **Architecture:** Multi-threaded server with command-dispatch pattern and vertex-transform pipeline

## Quick Reference

- **Tech Stack:** pygame + OpenCV + PyOpenGL (GLES2) + NumPy + PyYAML
- **Entry Point:** `projector-display-server` CLI (`projector_display.server:main`)
- **Architecture Pattern:** Scene graph + perspective homography pipeline + decorator-based command registry
- **Renderer Backends:** GLESRenderer (GPU, production) / PygameRenderer (CPU, development)
- **Protocol:** TCP/JSON on port 9999 (newline-delimited)
- **Source:** ~8100 LOC across 27 source files

## Generated Documentation

- [Project Overview](./project-overview.md) -- Executive summary, core concepts, tech stack, origin
- [Architecture](./architecture.md) -- Threading model, coordinate system, vertex-transform pipeline, command dispatch, renderer subsystem, data model, render loop, key design decisions
- [Source Tree Analysis](./source-tree-analysis.md) -- Annotated directory tree, critical directories, entry points, file statistics
- [Development Guide](./development-guide.md) -- Prerequisites, installation, running the server, CLI arguments, client library usage, examples, code style, testing approach

## Existing Documentation (Legacy)

These documents predate the current codebase and may not reflect the current state. Use for origin/purpose context only.

- [README.md](../README.md) -- Original project documentation (partially current)
- [EXAMPLES.md](../EXAMPLES.md) -- Detailed guide to the 10 example/test scripts

## Getting Started

1. Install: `pip install -e ".[dev]"` (after cloning and `git submodule update --init --recursive`)
2. Create or copy a calibration YAML mapping world meters to screen pixels (see [Development Guide](./development-guide.md#calibration-file-required))
3. Start server: `projector-display-server -C calibration.yaml --renderer pygame`
4. Connect client: `python examples/basic_usage.py`
5. Read the [Architecture](./architecture.md) for the vertex-transform pipeline and coordinate system design

## For AI-Assisted Development

When creating features or fixes, start with the [Architecture](./architecture.md) document to understand:
- The **vertex-transform pipeline** (expand vertices in source space, THEN apply homography)
- The **command-dispatch** pattern (add `@register_command` handlers in `commands/prebuilt/`)
- The **Renderer Protocol** (any new drawing primitive must be implemented in both backends)
- The **Scene threading model** (lock-protected writes, snapshot-based reads)
