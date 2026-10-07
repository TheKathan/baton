"""Import an existing hand-written Markdown board into the event store.

Expected entry shape (loose; every part after the id is optional):
    ### [C-143] backend → frontend, qa · status: OPEN · 2026-10-02
    body lines …
    > [A] frontend · 2026-10-02: answer …
    > status: CLOSED by backend

Ids, authors, dates and bodies are kept verbatim. Unknown kinds (e.g. N-) are kept.
"""

from __future__ import annotations

import re
from pathlib import Path

from .store import Board, BoardError

HEADING = re.compile(r"^### \[([A-Za-z]+)-(\d+)\]\s*(.*)$")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CLOSED = re.compile(r"status:\s*CLOSED", re.IGNORECASE)


def parse(text: str) -> list[dict]:
    entries, cur = [], None
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"kind": m.group(1).upper(), "num": m.group(2), "rest": m.group(3), "body": []}
        elif cur is not None:
            cur["body"].append(line)
    if cur:
        entries.append(cur)
    return [_shape(e) for e in entries]


def _shape(e: dict) -> dict:
    parts = [p.strip() for p in e["rest"].split("·")]
    route, author, to, status, date = parts[0] if parts else "", "unknown", [], "OPEN", ""
    if "→" in route:
        left, right = route.split("→", 1)
        author = left.strip().split(" ")[0] or "unknown"
        to = [r.strip() for r in right.split(",") if r.strip()]
    elif route:
        author = route.split(" ")[0]
    for p in parts[1:]:
        if p.lower().startswith("status:") and CLOSED.search(p):
            status = "CLOSED"
        d = DATE.search(p)
        if d:
            date = d.group(0)
    body = "\n".join(e["body"]).strip()
    if CLOSED.search(body):
        status = "CLOSED"
    return {
        "type": "entry", "id": f"{e['kind']}-{e['num']}", "kind": e["kind"], "n": int(e["num"]),
        "from": author, "to": to or ["all"], "title": "", "body": body, "files": [],
        "cites": [], "blocks": [], "ts": date or "unknown", "status": status,
        "imported": True, "imported_header": e["rest"],
    }


def import_file(board: Board, path: Path, sprint: str, dry_run: bool = False) -> dict:
    parsed = parse(path.read_text())
    existing = set(board.entries())
    seen, added, renamed = set(), 0, []
    for ev in parsed:
        base = ev["id"]
        if base in existing or base in seen:
            k = 2
            while f"{base}~{k}" in existing or f"{base}~{k}" in seen:
                k += 1
            ev["id"] = f"{base}~{k}"
            renamed.append(f"{base} → {ev['id']}")
        seen.add(ev["id"])
        ev["sprint"] = sprint
        if not dry_run:
            board.append_raw(ev)
        added += 1
    if not parsed:
        raise BoardError(f"{path}: no '### [X-NNN]' entries found")
    return {"file": str(path), "sprint": sprint, "entries": added, "renamed": renamed}
