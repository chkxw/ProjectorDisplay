# Commit Patterns

Guidelines for commit messages in this project.

## Format

```
<type>: <short summary>

<optional body with details>
```

## Types

- **Implement** - New feature or phase implementation
- **Fix** - Bug fix
- **Refactor** - Code restructuring without behavior change
- **Add** - Adding new files/modules
- **Update** - Modifications to existing functionality
- **Mark** - Documentation/tracking updates (tech-spec checkboxes, etc.)

## Branch Conventions

| Branch | Content | Commit Style |
|--------|---------|--------------|
| `main` | Implementation code | `Implement`, `Fix`, `Refactor`, `Add` |
| `bmad` | Scaffold/docs (tech-specs, ADRs) | `Mark`, `Add`, `Update` |

## Examples

### Main Branch (Code)

```
Implement Phase 11: Storage & Assets (ADR-10)

Add XDG-compliant persistent storage and image asset management:

Storage Manager (storage.py):
- get_data_dir() -> ~/.local/share/projector_display/
- get_session_dir() -> /tmp/projector_display/{session_id}/

Asset Commands (asset_commands.py):
- check_image, upload_image, list_images, delete_image
```

```
Fix path traversal vulnerability in asset_commands

Sanitize filename input to prevent directory traversal attacks.
```

```
Refactor colors to RGBA format (ADR-8)
```

### BMAD Branch (Docs/Scaffold)

```
Mark Phase 11 tasks and ACs complete in tech-spec

- Tasks 11.1-11.7: All marked [x] complete
- ACs 16-21: All marked [x] satisfied
```

```
Add ADR-10: Storage & Scene Persistence
```

## Rules

1. **No co-author lines** - Do not include `Co-Authored-By` trailers
2. **Reference ADRs** - Include `(ADR-X)` when implementing architectural decisions
3. **Keep summary under 72 chars** - First line should be concise
4. **Use imperative mood** - "Add feature" not "Added feature"
5. **Body is optional** - Use for complex changes needing explanation
