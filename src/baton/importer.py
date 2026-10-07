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


ANSWER = re.compile(r"^>\s*\[A\]\s*(.*)$")
CLOSE_MARK = re.compile(r"`?>?\s*status:\s*CLOSED(?:\s+by\s+([\w.-]+))?`?", re.IGNORECASE)


def _split_answers(lines: list[str]) -> tuple[list[str], list[dict]]:
    """Split an entry body into its own text and the `> [A] …` answers appended under it."""
    main, answers, current = [], [], None
    for line in lines:
        m = ANSWER.match(line)
        if m:
            current = {"head": m.group(1), "lines": []}
            answers.append(current)
        elif current is not None and line.startswith(">"):
            current["lines"].append(line[1:].strip())
        else:
            current = None
            main.append(line)
    return main, answers


def _answer_event(a: dict, entry_ts: str) -> tuple[dict, str | None]:
    """(reply event, closer role if the answer also closed the thread)."""
    head, _, text = a["head"].partition(":")
    role = re.split(r"[\s·(]", head.strip(), maxsplit=1)[0] or "unknown"
    d = DATE.search(head)
    body = "\n".join([text.strip(), *a["lines"]]).strip()
    closer = None
    for m in CLOSE_MARK.finditer(body):
        closer = m.group(1) or role
    body = CLOSE_MARK.sub("", body).strip()
    return {"type": "reply", "from": role, "body": body, "ts": d.group(0) if d else entry_ts,
            "imported": True}, closer


def _shape(e: dict) -> list[dict]:
    """The entry event, then one reply per `> [A]` answer, then a close if the thread was closed."""
    parts = [p.strip() for p in e["rest"].split("·")]
    route, author, to, closed_by, date = parts[0] if parts else "", "unknown", [], None, ""
    if "→" in route:
        left, right = route.split("→", 1)
        author = left.strip().split(" ")[0] or "unknown"
        to = [r.strip() for r in right.split(",") if r.strip()]
    elif route:
        author = route.split(" ")[0]
    for p in parts[1:]:
        if p.lower().startswith("status:") and CLOSED.search(p):
            closed_by = author
        d = DATE.search(p)
        if d:
            date = d.group(0)
    ts = date or "unknown"
    main, answers = _split_answers(e["body"])
    body = "\n".join(main).strip()
    for m in CLOSE_MARK.finditer(body):  # a status line in the entry's own text
        closed_by = m.group(1) or author
    body = CLOSE_MARK.sub("", body).strip()
    entry_id = f"{e['kind']}-{e['num']}"
    events = [{
        "type": "entry", "id": entry_id, "kind": e["kind"], "n": int(e["num"]),
        "from": author, "to": to or ["all"], "title": "", "body": body, "files": [],
        "cites": [], "blocks": [], "ts": ts, "imported": True, "imported_header": e["rest"],
    }]
    close_ts = ts
    for a in answers:
        reply, closer = _answer_event(a, ts)
        if reply["body"]:
            events.append({**reply, "id": entry_id})
        if closer:
            closed_by, close_ts = closer, reply["ts"]
    if closed_by:
        events.append({"type": "close", "id": entry_id, "from": closed_by, "reason": "closed on the imported board",
                       "ts": close_ts, "imported": True})
    return events


def import_file(board: Board, path: Path, sprint: str, dry_run: bool = False) -> dict:
    parsed = parse(path.read_text())
    if not parsed:
        raise BoardError(f"{path}: no '### [X-NNN]' entries found")
    existing = set(board.entries())
    seen, renamed = set(), []
    counts = {"entries": 0, "replies": 0, "closes": 0}
    for events in parsed:
        base = events[0]["id"]
        new_id = base
        if base in existing or base in seen:
            k = 2
            while f"{base}~{k}" in existing or f"{base}~{k}" in seen:
                k += 1
            new_id = f"{base}~{k}"
            renamed.append(f"{base} → {new_id}")
        seen.add(new_id)
        for ev in events:
            ev["id"], ev["sprint"] = new_id, sprint
            counts[{"entry": "entries", "reply": "replies", "close": "closes"}[ev["type"]]] += 1
            if not dry_run:
                board.append_raw(ev)
    return {"file": str(path), "sprint": sprint, **counts, "renamed": renamed}
