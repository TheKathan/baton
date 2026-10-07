"""Test helper: turn a freshly initialised board into a legacy (format 1) board.

Boards created before baton 1.2 use the single-machine layout. They keep working, so the
original test suite runs against that layout; tests/test_team.py covers the team layout."""

import json
from pathlib import Path


def make_legacy(root) -> None:
    path = Path(root) / ".baton/config.json"
    cfg = json.loads(path.read_text())
    cfg["format"] = 1
    path.write_text(json.dumps(cfg, indent=2) + "\n")
