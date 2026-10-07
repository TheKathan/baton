"""Project configuration: `.baton.json` at the project root."""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_NAME = ".baton.json"

DEFAULTS: dict = {
    "dir": "coordination/bbs",
    "sprint": "S1",
    "board_md": "coordination/BOARD.md",
    "archive_dir": "coordination/board-archive",
    "status_md": "coordination/STATUS.md",
    "contracts_index": "coordination/board-archive/CONTRACTS-INDEX.md",
    "kinds": {
        "Q": "question",
        "C": "contract change",
        "D": "decision",
        "H": "hand-off",
        "B": "blocker",
    },
    "roles": [],
    "handoff_max_lines": 20,
    "body_warn_lines": {"C": 40, "D": 40},
    "unread_warn_tokens": 20000,
    "id_width": 3,
    "auto_render": True,
}


class ConfigError(Exception):
    pass


def find_root(start: Path | None = None) -> Path:
    """Return the project root: $BATON_ROOT, or the nearest parent holding .baton.json."""
    env = os.environ.get("BATON_ROOT")
    if env:
        root = Path(env).resolve()
        if not (root / CONFIG_NAME).exists():
            raise ConfigError(f"BATON_ROOT={env} has no {CONFIG_NAME}")
        return root
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / CONFIG_NAME).exists():
            return d
    raise ConfigError(f"no {CONFIG_NAME} found from {here} upwards; run `baton init` first")


def load(root: Path) -> dict:
    raw = json.loads((root / CONFIG_NAME).read_text())
    cfg = {**DEFAULTS, **raw}
    cfg["kinds"] = {**raw.get("kinds", DEFAULTS["kinds"])}
    return cfg


def save(root: Path, cfg: dict) -> None:
    (root / CONFIG_NAME).write_text(json.dumps(cfg, indent=2) + "\n")
