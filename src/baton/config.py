"""Project configuration: `.baton/config.json` at the project root."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BATON_DIR = ".baton"
CONFIG_NAME = f"{BATON_DIR}/config.json"

DEFAULTS: dict = {
    "dir": ".baton/events",
    "sprint": "S1",
    "board_md": ".baton/BOARD.md",
    "archive_dir": ".baton/archive",
    "status_md": ".baton/STATUS.md",
    "contracts_index": ".baton/CONTRACTS-INDEX.md",
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
    # In a linked git worktree, use the main worktree's board, so every agent shares one
    # id counter and one lock (see find_root).
    "shared_worktrees": True,
}


class ConfigError(Exception):
    pass


def main_worktree(path: Path) -> Path | None:
    """The main worktree's root if `path` is inside a *linked* git worktree, else None."""
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "--path-format=absolute",
                            "--git-dir", "--git-common-dir"], capture_output=True, text=True, timeout=5,
                           check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None  # no git: nothing to share
    if r.returncode != 0:
        return None
    parts = r.stdout.split("\n")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    git_dir, common = Path(parts[0]).resolve(), Path(parts[1]).resolve()
    if git_dir == common or common.name != ".git":
        return None  # the main worktree itself, a plain clone, or a bare repository
    return common.parent


def _shared(root: Path) -> bool:
    try:
        return bool(json.loads((root / CONFIG_NAME).read_text()).get("shared_worktrees", True))
    except (OSError, ValueError):
        return True


def locate(start: Path | None = None) -> tuple[Path, Path | None]:
    """(board root, worktree it was redirected from or None).

    $BATON_ROOT wins. Otherwise the nearest parent holding .baton/config.json; inside a
    linked git worktree that is replaced by the main worktree's board, so all worktrees
    share one board, one id counter and one lock.
    """
    env = os.environ.get("BATON_ROOT")
    if env:
        root = Path(env).resolve()
        if not (root / CONFIG_NAME).exists():
            raise ConfigError(f"BATON_ROOT={env} has no {CONFIG_NAME}")
        return root, None
    here = (start or Path.cwd()).resolve()
    found = next((d for d in (here, *here.parents) if (d / CONFIG_NAME).exists()), None)
    main = main_worktree(found or here)
    if (main and (main / CONFIG_NAME).exists() and (found is None or _shared(found))
            and (found is None or found.resolve() != main.resolve())):
        return main, (found or here)
    if found:
        return found, None
    raise ConfigError(f"no {CONFIG_NAME} found from {here} upwards; run `baton init` first")


def find_root(start: Path | None = None) -> Path:
    """The board root (see locate)."""
    return locate(start)[0]


def load(root: Path) -> dict:
    raw = json.loads((root / CONFIG_NAME).read_text())
    cfg = {**DEFAULTS, **raw}
    cfg["kinds"] = {**raw.get("kinds", DEFAULTS["kinds"])}
    return cfg


def save(root: Path, cfg: dict) -> None:
    (root / BATON_DIR).mkdir(parents=True, exist_ok=True)
    (root / CONFIG_NAME).write_text(json.dumps(cfg, indent=2) + "\n")
