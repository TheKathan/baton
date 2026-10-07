#!/usr/bin/env bash
# Install the `baton` command for the current user.
#   ./install.sh            editable install (uv tool, else pipx, else a symlink shim)
#   ./install.sh --uninstall
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${BATON_BIN_DIR:-$HOME/.local/bin}"

if [[ "${1:-}" == "--uninstall" ]]; then
  if command -v uv >/dev/null && uv tool list 2>/dev/null | grep -q '^agent-baton '; then uv tool uninstall agent-baton; fi
  if command -v pipx >/dev/null && pipx list --short 2>/dev/null | grep -q '^agent-baton '; then pipx uninstall agent-baton; fi
  if [[ -L "$BIN/baton" ]]; then rm "$BIN/baton"; fi
  echo "baton uninstalled"
  exit 0
fi

if command -v uv >/dev/null; then
  uv tool install --force --editable "$HERE"
elif command -v pipx >/dev/null; then
  pipx install --force --editable "$HERE"
else
  mkdir -p "$BIN"
  ln -sf "$HERE/bin/baton" "$BIN/baton"
  echo "linked $BIN/baton -> $HERE/bin/baton"
fi

if ! command -v baton >/dev/null; then
  echo "note: $BIN is not on your PATH; add it to use baton"
else
  echo "installed: $(baton --version)"
fi
