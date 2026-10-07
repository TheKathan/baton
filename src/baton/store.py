"""Append-only event store.

Every write is one JSON line in `<dir>/<sprint>.jsonl`, appended while holding an
exclusive flock on `<dir>/.lock`. Ids and event numbers are derived from the files
under that same lock, so concurrent agents can never allocate the same id.

Event types:
  entry  {id, kind, n, from, to[], title, body, files[], cites[], blocks[]}
  reply  {id, from, body}
  close  {id, from, reason}
Every event also carries {type, ev, sprint, ts}.
"""

from __future__ import annotations

import fcntl
import json
import time
from contextlib import contextmanager
from pathlib import Path

ALL = "all"


class BoardError(Exception):
    pass


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


class Board:
    def __init__(self, root: Path, cfg: dict):
        self.root = root
        self.cfg = cfg
        self.dir = root / cfg["dir"]
        self.cursors = self.dir / ".cursors"

    # ---------- low level ----------
    @contextmanager
    def lock(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        with (self.dir / ".lock").open("a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def sprint_files(self) -> list[Path]:
        if not self.dir.exists():
            return []
        return sorted(self.dir.glob("*.jsonl"))

    def events(self) -> list[dict]:
        out = []
        for p in self.sprint_files():
            with p.open() as f:
                for i, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            out.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            raise BoardError(f"{p.name}:{i}: corrupt line ({e})") from e
        out.sort(key=lambda e: e["ev"])
        return out

    def _append(self, event: dict) -> dict:
        """Caller must hold the lock. Assigns ev, sprint and ts."""
        evs = self.events()
        event["ev"] = (evs[-1]["ev"] if evs else 0) + 1
        event.setdefault("sprint", self.cfg["sprint"])
        event.setdefault("ts", now())
        path = self.dir / f"{event['sprint']}.jsonl"
        with path.open("a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
        return event

    # ---------- state ----------
    def entries(self) -> dict[str, dict]:
        """Fold events into threads, keyed by id, in posting order."""
        threads: dict[str, dict] = {}
        for e in self.events():
            if e["type"] == "entry":
                t = {k: v for k, v in e.items() if k != "type"}
                t.setdefault("status", "OPEN")
                t.update(replies=[], closed_by=None, closed_reason=None)
                threads[e["id"]] = t
            elif e["id"] in threads:
                t = threads[e["id"]]
                if e["type"] == "reply":
                    t["replies"].append(e)
                elif e["type"] == "close":
                    t.update(status="CLOSED", closed_by=e["from"], closed_reason=e.get("reason"))
        return threads

    def get(self, entry_id: str) -> dict:
        threads = self.entries()
        key = normalise_id(entry_id)
        t = threads.get(key)
        if t is None and "-" in key and key.split("-", 1)[1].isdigit():
            kind, num = key.split("-", 1)
            t = threads.get(self.format_id(kind, int(num)))
        if t is None:
            raise BoardError(f"no entry {entry_id}")
        return t

    # ---------- status (one row per role) ----------
    def status(self) -> dict[str, dict]:
        p = self.dir / "status.json"
        return json.loads(p.read_text()) if p.exists() else {}

    def set_status(self, role: str, phase: str, state: str, handoff: str = "") -> dict:
        self._check_role(role)
        with self.lock():
            rows = self.status()
            prev = rows.get(role, {})
            rows[role] = {"phase": phase or prev.get("phase", ""), "state": state,
                          "handoff": handoff or prev.get("handoff", ""), "updated": now()}
            tmp = self.dir / "status.json.tmp"
            tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
            tmp.replace(self.dir / "status.json")
            return rows[role]

    def max_number(self) -> int:
        return max((e.get("n", 0) for e in self.events() if e["type"] == "entry"), default=0)

    def format_id(self, kind: str, n: int) -> str:
        return f"{kind}-{n:0{self.cfg['id_width']}d}"

    # ---------- writes ----------
    def _check_role(self, role: str) -> None:
        roles = self.cfg.get("roles") or []
        if not role:
            raise BoardError("a role is required (--as <role> or $BATON_ROLE)")
        if roles and role not in roles:
            raise BoardError(f"unknown role {role!r}; known: {', '.join(roles)}")

    def post(self, kind: str, author: str, to: list[str], title: str, body: str,
             files: list[str] = (), cites: list[str] = (), blocks: list[str] = ()) -> dict:
        kind = kind.upper()
        if kind not in self.cfg["kinds"]:
            raise BoardError(f"unknown kind {kind!r}; known: {', '.join(self.cfg['kinds'])}")
        self._check_role(author)
        for r in to:
            if r != ALL:
                self._check_role(r)
        if not title.strip():
            raise BoardError("--title is required")
        if kind == "C" and not files:
            raise BoardError("a contract change (C) must list the affected --files")
        with self.lock():
            n = self.max_number() + 1
            return self._append({
                "type": "entry", "id": self.format_id(kind, n), "kind": kind, "n": n,
                "from": author, "to": list(to) or [ALL], "title": title.strip(),
                "body": body.strip(), "files": list(files), "cites": list(cites),
                "blocks": list(blocks),
            })

    def reply(self, entry_id: str, author: str, body: str) -> dict:
        self._check_role(author)
        if not body.strip():
            raise BoardError("empty reply")
        with self.lock():
            t = self.get(entry_id)
            return self._append({"type": "reply", "id": t["id"], "from": author, "body": body.strip()})

    def close(self, entry_id: str, author: str, reason: str = "") -> dict:
        self._check_role(author)
        with self.lock():
            t = self.get(entry_id)
            if t["status"] == "CLOSED":
                raise BoardError(f"{t['id']} is already closed by {t['closed_by']}")
            return self._append({"type": "close", "id": t["id"], "from": author, "reason": reason.strip()})

    def append_raw(self, event: dict) -> dict:
        """Used by the importer: keeps the given id/n/ts/sprint."""
        with self.lock():
            return self._append(event)

    # ---------- reads per role ----------
    def involves(self, t: dict, role: str, named_only: bool = False) -> bool:
        """True if the role wrote the thread or it is addressed to the role (or to all)."""
        if t["from"] == role or role in t["to"]:
            return True
        return not named_only and ALL in t["to"]

    def cursor(self, role: str) -> int:
        cp = self.cursors / f"{role}.json"
        return json.loads(cp.read_text()).get("ev", 0) if cp.exists() else 0

    def unread(self, role: str, everything: bool = False, peek: bool = False) -> list[dict]:
        """Events after the role's cursor that concern it. Advances the cursor unless peek."""
        self._check_role(role)
        self.cursors.mkdir(parents=True, exist_ok=True)
        cp = self.cursors / f"{role}.json"
        seen = self.cursor(role)
        events = self.events()
        threads = self.entries()
        out = []
        for e in events:
            if e["ev"] <= seen or e["from"] == role:
                continue
            t = threads.get(e["id"])
            if t is None:
                continue
            if everything or self.involves(t, role):
                out.append(e)
        if not peek and events:
            cp.write_text(json.dumps({"ev": events[-1]["ev"]}))
        return out

    def open_threads(self, role: str | None = None, kinds: list[str] | None = None,
                     blocking: bool = False, named_only: bool = False) -> list[dict]:
        out = []
        for t in self.entries().values():
            if t["status"] != "OPEN":
                continue
            if role and not self.involves(t, role, named_only):
                continue
            if kinds and t["kind"] not in kinds:
                continue
            if blocking and not (t["kind"] == "B" or t.get("blocks")):
                continue
            out.append(t)
        return out

    def awaiting(self, role: str) -> list[dict]:
        """Open Q/B threads addressed to the role (by name) that the role has not answered."""
        return [t for t in self.open_threads(role, ["Q", "B"], named_only=True)
                if role in t["to"] and t["from"] != role
                and not any(r["from"] == role for r in t["replies"])]


def normalise_id(entry_id: str) -> str:
    s = entry_id.strip().strip("[]").upper()
    if "-" in s:
        kind, num = s.split("-", 1)
        if num.isdigit():
            return f"{kind}-{num}"
    return s
