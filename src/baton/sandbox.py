"""Sandbox mode: one board per task, local to the checkout that works on it.

    baton init --sandbox --task LIN-123   create (or resume) the task's board
    ... agents coordinate on it with the usual commands, offline ...
    baton finish                          export it to .baton/tasks/LIN-123.jsonl for the PR

The live board is `.baton/sandbox.json` plus `.baton/sandbox/`, listed in `.git/info/exclude`,
so nothing of it appears in the diff. `finish` writes the task's whole board, as JSONL, to
`.baton/tasks/<task>.jsonl` in the working tree: commit it with the PR. The name is unique per
task, so it never conflicts, and reviewers can read the agents' decisions in the diff. A later
sandbox on the same task resumes from that file, and other tasks read its live contracts once
it has merged.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import config
from .store import Board, BoardError, fold

TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LOCAL_PATHS = (f"/{config.SANDBOX_NAME}", f"/{config.BATON_DIR}/sandbox/")


def task_file(root: Path, task: str) -> Path:
    return root / config.TASKS_DIR / f"{task}.jsonl"


def sandbox_config(task: str, roles: list[str]) -> dict:
    base = f"{config.BATON_DIR}/sandbox"
    return {**config.DEFAULTS, "sandbox": True, "task": task, "sprint": task, "roles": roles,
            "dir": f"{base}/events", "board_md": f"{base}/BOARD.md", "status_md": f"{base}/STATUS.md",
            "contracts_index": f"{base}/CONTRACTS-INDEX.md", "archive_dir": f"{base}/archive",
            "auto_render": False, "shared_worktrees": False, "format": 1}


def _exclude_locally(root: Path) -> bool:
    """List the live board in .git/info/exclude (this clone only, never committed)."""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute",
                            "--git-path", "info/exclude"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if r.returncode != 0 or not r.stdout.strip():
        return False
    path = Path(r.stdout.strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    have = path.read_text().splitlines() if path.exists() else []
    missing = [p for p in LOCAL_PATHS if p not in have]
    if missing:
        with path.open("a") as f:
            f.write("".join(f"{p}\n" for p in ["# baton sandbox board (local)", *missing]))
    return True


def init(root: Path, task: str, roles: list[str], force: bool = False) -> str:
    if not TASK_RE.match(task):
        raise BoardError(f"--task {task!r}: use letters, digits, '.', '_' or '-' (e.g. LIN-123)")
    if (root / config.SANDBOX_NAME).exists() and not force:
        raise BoardError(f"{config.SANDBOX_NAME} exists (this checkout already has a sandbox board; "
                         "use --force to start over)")
    cfg = sandbox_config(task, roles)
    config.save(root, cfg)
    board = Board(root, cfg)
    board.dir.mkdir(parents=True, exist_ok=True)
    excluded = _exclude_locally(root)
    resumed = 0
    exported = task_file(root, task)
    if exported.exists() and not any(board.dir.glob("*.jsonl")):
        events = [json.loads(ln) for ln in exported.read_text().splitlines() if ln.strip()]
        events.sort(key=lambda e: e.get("ev", 0))
        for e in events:
            board.append_raw({k: v for k, v in e.items() if k != "ev"})
        resumed = len(events)
        roles_seen = roles or sorted({e["from"] for e in events if e.get("from")})  # all, when unrestricted
        for role in roles_seen:  # the history was read by the previous sandbox: start at the tip
            board.unread(role)
    note = f"resumed {resumed} event(s) from {exported.relative_to(root)}" if resumed else "new task board"
    if not excluded:
        note += "; not a git checkout, so add .baton/sandbox* to your ignores yourself"
    return f"sandbox board for {task}: {note}"


def other_tasks(root: Path, own: str) -> dict[str, dict[str, dict]]:
    """Threads of every other exported task on this branch: {task: {id: thread}}."""
    out = {}
    tasks_dir = root / config.TASKS_DIR
    for f in sorted(tasks_dir.glob("*.jsonl")) if tasks_dir.exists() else []:
        if f.stem == own:
            continue
        events = []
        for ln in f.read_text().splitlines():
            if not ln.strip():
                continue
            try:
                events.append(json.loads(ln))
            except json.JSONDecodeError:
                continue  # a damaged exported line never blocks this task
        events.sort(key=lambda e: e.get("ev", 0))
        out[f.stem] = fold(events)
    return out


def live_contracts(root: Path, own: str) -> list[dict]:
    """Open C entries from other tasks' exported boards, labelled with their task."""
    rows = []
    for task, threads in other_tasks(root, own).items():
        for t in threads.values():
            if t["kind"] == "C" and t["status"] == "OPEN":
                rows.append({**t, "task": task, "ref": f"{task}/{t['id']}"})
    return rows


def finish(board: Board) -> tuple[Path, dict]:
    """Write the task's board to .baton/tasks/<task>.jsonl; return (path, counts)."""
    task = board.cfg["task"]
    events = board.events()
    path = task_file(board.root, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
    tmp.replace(path)
    threads = board.entries()
    open_asks = [t for t in threads.values() if t["status"] == "OPEN" and t["kind"] in ("Q", "B")]
    return path, {"events": len(events), "threads": len(threads), "open_asks": open_asks}


def summary(board: Board) -> str:
    """A Markdown summary for the PR comment: decisions, contracts, hand-offs, open asks."""
    task = board.cfg["task"]
    threads = list(board.entries().values())

    def lines(kinds, only_open=False):
        out = []
        for t in threads:
            if t["kind"] not in kinds or (only_open and t["status"] != "OPEN"):
                continue
            extra = f" (files: {', '.join(t['files'])})" if t.get("files") else ""
            out.append(f"- **{t['id']}** {t['title'] or t['body'][:80]}{extra} · {t['from']}"
                       + ("" if t["status"] == "OPEN" else " · closed"))
        return out
    parts = [f"### baton: {task}", ""]
    for title, kinds, only_open in (("Open questions and blockers", ("Q", "B"), True),
                                    ("Contracts", ("C",), False), ("Decisions", ("D",), False),
                                    ("Hand-offs", ("H",), False)):
        rows = lines(kinds, only_open)
        if rows:
            parts += [f"**{title}**", *rows, ""]
    if len(parts) == 2:
        parts += ["_No entries._", ""]
    parts.append(f"_Full board: `{config.TASKS_DIR}/{task}.jsonl` · {len(threads)} thread(s)_")
    return "\n".join(parts)
