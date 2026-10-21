"""Which model wrote an event, so metrics can be read per model.

Where the name comes from, first match wins:
  --model NAME      the agent says it (any agent can: it knows its own model id)
  $BATON_MODEL      a wrapper or hook says it
  detected          the session record of the agent that is running this command

Detection reads only the model name from the tail of the session record, and keeps nothing else. It is
best effort: when the record is missing or its layout changes, no model is recorded and nothing fails.
Set BATON_MODEL_DETECT=0 to turn it off.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

TAIL = 256 * 1024
MODEL = re.compile(rb'"model"\s*:\s*"([^"<]{1,80})"')


def _last_model(path: Path) -> str:
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL))
        found = MODEL.findall(f.read())
    return found[-1].decode("utf-8", "replace") if found else ""


def _claude_code() -> str:
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not (os.environ.get("CLAUDECODE") and re.fullmatch(r"[0-9A-Za-z-]{8,64}", session)):
        return ""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return next((m for p in (home / "projects").glob(f"*/{session}.jsonl") if (m := _last_model(p))), "")


def _codex() -> str:
    thread = os.environ.get("CODEX_THREAD_ID", "")
    if not re.fullmatch(r"[0-9A-Za-z-]{8,64}", thread):
        return ""
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return next((m for p in (home / "sessions").glob(f"*/*/*/rollout-*-{thread}.jsonl") if (m := _last_model(p))), "")


def detect() -> str:
    if os.environ.get("BATON_MODEL_DETECT", "1") == "0":
        return ""
    for look in (_codex, _claude_code):
        try:
            if model := look():
                return model
        except OSError:
            continue
    return ""


def resolve(flag: str | None = None) -> dict:
    """The fields to add to an event: {"model": name, "model_src": "flag" | "env" | "detected"}, or {}."""
    for name, src in ((flag, "flag"), (os.environ.get("BATON_MODEL"), "env")):
        if name and name.strip():
            return {"model": name.strip()[:80], "model_src": src}
    model = detect()
    return {"model": model, "model_src": "detected"} if model else {}
