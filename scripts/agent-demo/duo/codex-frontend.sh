#!/bin/bash
# Usage: codex-frontend.sh <dir>   (Codex as the frontend agent; reads only the project and baton's install)
P=$1
BRIEF='You are the frontend agent on this project. The status page needs the health check endpoint. Ask the backend agent which route serves it, using the `baton` command (`baton post Q --as frontend --to backend --title "…" "…"`), then stop.'
cd "$P" && clear
FS="{ \"$HOME\" = \"none\", \"$P\" = \"write\", \"$HOME/.local/share/uv\" = \"read\" }"
exec /opt/homebrew/bin/codex --no-daemon -a never -C "$P" \
  -c 'default_permissions="demo"' -c 'permissions.demo.extends=":workspace"' \
  -c "permissions.demo.filesystem=$FS" \
  -c 'model_reasoning_effort="low"' \
  "$BRIEF"
