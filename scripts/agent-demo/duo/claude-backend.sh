#!/bin/bash
# Usage: claude-backend.sh <dir>   (Claude Code as the backend agent, once Q-001 is on the board)
cd "$1" || exit 1
clear
until baton show Q-001 >/dev/null 2>&1; do sleep 0.3; done
sleep 0.5
clear
BRIEF='You are the backend agent on this project. S1-A, the health endpoint in src/, is done. Hand off S1-A to qa now: `baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."`'
DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 \
exec "$HOME/.local/bin/claude" --model sonnet --disable-slash-commands --strict-mcp-config \
  --setting-sources project --permission-mode default --allowedTools Bash Read Grep Glob -- "$BRIEF"
