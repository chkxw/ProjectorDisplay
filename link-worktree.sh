#!/usr/bin/env bash
# Creates symlinks from the project root into _bmad-worktree/.
# Safe to run from any directory — resolves paths from script location.

set -euo pipefail

# Resolve the absolute path of this script's directory (_bmad-worktree/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root is the parent of _bmad-worktree/
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# Name of the worktree directory (for relative symlinks)
WORKTREE_DIR="$(basename "$SCRIPT_DIR")"

# Symlinks to create: project_root/<name> -> <worktree>/<target>
LINKS=(
    "_bmad:${WORKTREE_DIR}/_bmad"
    "_bmad-output:${WORKTREE_DIR}/_bmad-output"
    ".claude:${WORKTREE_DIR}/.claude"
    ".codex:${WORKTREE_DIR}/.codex"
    ".gemini:${WORKTREE_DIR}/.gemini"
    "docs:${WORKTREE_DIR}/docs"
)

cd "$PROJECT_ROOT"

for entry in "${LINKS[@]}"; do
    name="${entry%%:*}"
    target="${entry#*:}"

    if [ -L "$name" ]; then
        existing="$(readlink "$name")"
        if [ "$existing" = "$target" ]; then
            echo "  ok  $name -> $target"
            continue
        fi
        echo "  fix $name: $existing -> $target"
        rm "$name"
    elif [ -e "$name" ]; then
        echo "  SKIP $name (exists and is not a symlink)"
        continue
    else
        echo "  new $name -> $target"
    fi

    ln -s "$target" "$name"
done

echo "Done. All links verified in $PROJECT_ROOT"
