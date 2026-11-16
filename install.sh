#!/usr/bin/env bash
# Copy every skill in this repository into ~/.claude/skills so Claude Code can load it.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.claude/skills"
for dir in "$here"/skills/*/; do
  name="$(basename "$dir")"
  rm -rf "$HOME/.claude/skills/$name"
  cp -r "$dir" "$HOME/.claude/skills/$name"
  echo "installed $name"
done
