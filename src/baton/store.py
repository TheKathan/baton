"""Append-only event store.

Team layout (format 2, the default for new boards): every clone of the repository appends
only to its own files, `<dir>/<sprint>/<clone-id>.jsonl`, so merges never conflict. Each
event carries `origin` (the clone id), a per-clone `seq`, a unique `uid` and the UTC write
time `rec`; readers order events by (rec, origin, seq). Entry ids are short random hex
(`Q-7F3A`), unique across clones. Status rows are events too.

Legacy layout (format 1, boards created before 1.2): one `<dir>/<sprint>.jsonl` per sprint
and a global `ev` counter. Those boards keep working unchanged; `baton migrate --team`
switches them to the team layout, keeping their history and ids.

Within one clone, writes still take an exclusive flock on `<dir>/.lock`.

Event types:
  entry  {id, kind, n, from, to[], title, body, files[], cites[], blocks[]}
  reply  {id, from, body}
  close  {id, from, reason}
Every event also carries {v, type, ev, sprint, ts}. The format is documented in
docs/FORMAT.md; see schema.py for versioning.
"""

from __future__ import annotations

import fcntl
import json
import secrets
import time
from contextlib import contextmanager
from pathlib import Path

from . import policies
from .schema import LEGACY_ORIGIN, FormatError, check_config, upgrade

ALL = "all"


class BoardError(Exception):
    pass


class BoardFormatError(BoardError, FormatError):
    pass


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def utc_now() -> str:
    """Exact time in UTC (ISO 8601), stored as `at` next to the human-readable local `ts`."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Board:
    def __init__(self, root: Path, cfg: dict):
        self.root = root
        self.cfg = cfg
        self.dir = root / cfg["dir"]
        self.cursors = self.dir / ".cursors"
        self.team = int(cfg.get("format", 1)) >= 2
        self.last_warnings: list[str] = []
        try:
            policies.validate(cfg.get("policies"))
        except policies.PolicyError as e:
            raise BoardError(f".baton/config.json: {e}") from None
        try:
            check_config(cfg, str(root / ".baton/config.json"))
        except FormatError as e:
            raise BoardFormatError(str(e)) from None

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
        return sorted(self.dir.glob("*.jsonl")) + sorted(self.dir.glob("*/*.jsonl"))

    def clone_id(self) -> str:
        """This clone's writer id (team layout): random, created once, never committed."""
        p = self.dir / ".clone-id"
        if p.exists() and p.read_text().strip():
            return p.read_text().strip()
        self.dir.mkdir(parents=True, exist_ok=True)
        cid = secrets.token_hex(3)
        p.write_text(cid + "\n")
        return cid

    @staticmethod
    def _order(e: dict):
        if e.get("origin", LEGACY_ORIGIN) == LEGACY_ORIGIN:
            return (0, "", "", int(e.get("seq", e.get("ev", 0))))
        return (1, e.get("rec") or e.get("at") or "", e["origin"], int(e["seq"]))

    def events(self) -> list[dict]:
        out = []
        for p in self.sprint_files():
            with p.open() as f:
                for i, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            raw = json.loads(line)
                        except json.JSONDecodeError as e:
                            raise BoardError(f"{p.name}:{i}: corrupt line ({e})") from e
                        try:
                            out.append(upgrade(raw, f"{p.relative_to(self.dir)}:{i}"))
                        except FormatError as e:
                            raise BoardFormatError(str(e)) from None
        out.sort(key=self._order)
        if self.team:  # a virtual, local sequence number; the stored identity is origin + seq
            for i, e in enumerate(out, 1):
                e["ev"] = i
        return out

    def _append(self, event: dict, stamp: bool = True) -> dict:
        """Caller must hold the lock. Adds the identity fields, sprint and ts (and `at` if stamp)."""
        event = {k: v for k, v in event.items() if k != "v"}
        event.setdefault("sprint", self.cfg["sprint"])
        if self.cfg.get("task"):  # sandbox boards: every event records its task
            event.setdefault("task", self.cfg["task"])
        event.setdefault("ts", now())
        if stamp:
            event.setdefault("at", utc_now())
        if self.team:
            origin = self.clone_id()
            mine = sorted(self.dir.glob(f"*/{origin}.jsonl"))
            seq = sum(1 for f in mine for line in f.open() if line.strip()) + 1
            event = {"v": 2, **event, "origin": origin, "seq": seq, "uid": f"{origin}.{seq}", "rec": utc_now()}
            path = self.dir / event["sprint"] / f"{origin}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            evs = self.events()
            event = {"v": 1, **event, "ev": (evs[-1]["ev"] if evs else 0) + 1}
            path = self.dir / f"{event['sprint']}.jsonl"
        with path.open("a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
        return event

    # ---------- state ----------
    def entries(self) -> dict[str, dict]:
        """Fold events into threads, keyed by id, in posting order."""
        return fold(self.events())

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
        if self.team:  # status rows are events, so clones never conflict
            rows: dict[str, dict] = {}
            for e in self.events():
                if e["type"] == "status":
                    rows[e["role"]] = {"phase": e["phase"], "state": e["state"], "handoff": e["handoff"],
                                       "updated": e["ts"]}
            return rows
        p = self.dir / "status.json"
        return json.loads(p.read_text()) if p.exists() else {}

    def set_status(self, role: str, phase: str, state: str, handoff: str = "") -> dict:
        self._check_role(role)
        with self.lock():
            rows = self.status()
            prev = rows.get(role, {})
            row = {"phase": phase or prev.get("phase", ""), "state": state,
                   "handoff": handoff or prev.get("handoff", ""), "updated": now()}
            if self.team:
                self._append({"type": "status", "from": role, "role": role, "phase": row["phase"],
                              "state": state, "handoff": row["handoff"]})
                return row
            rows[role] = row
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
        entry = {"type": "entry", "kind": kind, "from": author, "to": list(to) or [ALL],
                 "title": title.strip(), "body": body.strip(), "files": list(files),
                 "cites": list(cites), "blocks": list(blocks)}
        refusals, self.last_warnings = policies.check(self.cfg.get("policies"), entry)
        if refusals:
            raise BoardError("refused by the project's policies (.baton/config.json):\n  - "
                             + "\n  - ".join(refusals))
        with self.lock():
            if self.team:
                taken = set(self.entries())
                width = 4
                while True:  # random short ids never collide across clones in practice; check locally anyway
                    new_id = f"{kind}-{secrets.token_hex(4)[:width].upper()}"
                    if new_id not in taken:
                        break
                    width += 1
                ident = {"id": new_id}
            else:
                n = self.max_number() + 1
                ident = {"id": self.format_id(kind, n), "n": n}
            return self._append({"type": "entry", **ident, "kind": kind,
                                 **{k: v for k, v in entry.items() if k not in ("type", "kind")}})

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
        """Used by the importer: keeps the given id/n/ts/sprint and adds no `at`."""
        with self.lock():
            return self._append(event, stamp=False)

    # ---------- reads per role ----------
    def involves(self, t: dict, role: str, named_only: bool = False) -> bool:
        """True if the role wrote the thread or it is addressed to the role (or to all)."""
        if t["from"] == role or role in t["to"]:
            return True
        return not named_only and ALL in t["to"]

    def _seen(self, role: str) -> dict[str, int]:
        """The role's cursor as {origin: last seq seen}. A legacy cursor {"ev": n} covers the legacy events."""
        cp = self.cursors / f"{role}.json"
        if not cp.exists():
            return {}
        data = json.loads(cp.read_text())
        return dict(data.get("seen") or {LEGACY_ORIGIN: int(data.get("ev", 0))})

    def cursor(self, role: str) -> int:
        return self._seen(role).get(LEGACY_ORIGIN, 0)

    def _own(self, e: dict, role: str) -> bool:
        """Written by this role on this clone. The same role on another clone is someone else's agent."""
        if e["from"] != role:
            return False
        return not self.team or e.get("origin") in (LEGACY_ORIGIN, self.clone_id())

    def unread(self, role: str, everything: bool = False, peek: bool = False) -> list[dict]:
        """Events after the role's cursor that concern it. Advances the cursor unless peek."""
        self._check_role(role)
        self.cursors.mkdir(parents=True, exist_ok=True)
        cp = self.cursors / f"{role}.json"
        seen = self._seen(role)
        events = self.events()
        threads = self.entries()
        out = []
        for e in events:
            if e["type"] not in ("entry", "reply", "close"):
                continue
            if e["seq"] <= seen.get(e["origin"], 0) or self._own(e, role):
                continue
            t = threads.get(e["id"])
            if t is None:
                continue
            if everything or self.involves(t, role):
                out.append(e)
        if not peek and events:
            latest = dict(seen)
            for e in events:
                latest[e["origin"]] = max(latest.get(e["origin"], 0), int(e["seq"]))
            # "ev" keeps the cursor readable by baton 1.1 on legacy boards
            cp.write_text(json.dumps({"seen": latest, "ev": latest.get(LEGACY_ORIGIN, 0)}))
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

    def maybe_settled(self, role: str) -> list[dict]:
        """Open threads the role started that someone else has since replied to: probably settled."""
        return [t for t in self.open_threads(role) if t["from"] == role
                and t["kind"] in ("Q", "B") and any(r["from"] != role for r in t["replies"])]

    def awaiting(self, role: str) -> list[dict]:
        """Open Q/B threads addressed to the role (by name) that the role has not answered."""
        return [t for t in self.open_threads(role, ["Q", "B"], named_only=True)
                if role in t["to"] and t["from"] != role
                and not any(r["from"] == role for r in t["replies"])]


def fold(events: list[dict]) -> dict[str, dict]:
    """Fold an ordered event list into threads keyed by id. Replies or closes that arrive
    before their entry are kept and attached (two passes), so ordering quirks never drop them."""
    threads: dict[str, dict] = {}
    for e in events:
        if e["type"] == "entry":
            t = {k: v for k, v in e.items() if k != "type"}
            t.setdefault("status", "OPEN")
            t.update(replies=[], closed_by=None, closed_reason=None, closed_ts=None, closed_at=None,
                     last_ts=e["ts"], last_at=e.get("at"))
            threads[e["id"]] = t
    for e in events:
        t = threads.get(e.get("id"))
        if t is None or e["type"] not in ("reply", "close"):
            continue
        t["last_ts"], t["last_at"] = e["ts"], e.get("at")
        if e["type"] == "reply":
            t["replies"].append(e)
        else:
            t.update(status="CLOSED", closed_by=e["from"], closed_reason=e.get("reason"),
                     closed_ts=e["ts"], closed_at=e.get("at"))
    return threads


def normalise_id(entry_id: str) -> str:
    s = entry_id.strip().strip("[]").upper()
    if "-" in s:
        kind, num = s.split("-", 1)
        if num.isdigit():
            return f"{kind}-{num}"
    return s
