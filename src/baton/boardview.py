"""The board page of `baton serve`: a kanban of the work, a strip of runners, and the contracts page.

Every Q, B and H thread of the current sprint (or sandbox task) sits in exactly one column, and the
column is its state. Decisions and contracts are records, never cards in the flow. Standard library only.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

from . import metrics, render, sandbox
from .store import Board

WORK = ("Q", "B", "H")
CAP = {"pick": 4, "done": 5}
COLUMNS = (
    ("blocked", "Blocked", "a blocker is open"),
    ("ask", "Needs an answer", "a question nobody has answered"),
    ("ans", "Answered, close it", "the addressee replied"),
    ("pick", "To pick up", "handed off, not picked up yet"),
    ("prog", "In progress", "working on an open thread"),
    ("passed", "Passed on", "recipient moved on, not closed"),
    ("done", "Done", "newest first"),
)
KIND = {"Q": "question", "B": "blocker", "H": "hand-off", "C": "contract", "D": "decision"}
PHASE = re.compile(r"\bS\d+[A-Za-z]?-[A-Z0-9]+\b")
BATON = ('<svg class="baton" viewBox="0 0 24 12" aria-hidden="true"><rect class="body" x="1" y="2" width="22" '
         'height="8" rx="4"/><rect class="band" x="7" y="2" width="2" height="8"/><rect class="band" x="15" '
         'y="2" width="2" height="8"/></svg>')
CONTRACT_FILTERS = ("all", "new", "old", "touched")

CSS = """
:root{color-scheme:light dark;--bg:#F6F8FA;--panel:#FFFFFF;--panel2:#F0F3F6;--line:#D0D7DE;--text:#1F2328;
--muted:#59636E;--indigo:#3B5BDB;--orange:#C2410C;--ok:#1A7F37;--bad:#CF222E;--warn:#9A6700;--bad-bg:#FFEBE9;
--warn-bg:#FFF8C5;--r0:#3B5BDB;--r1:#C2410C;--r2:#087F5B;--r3:#C2255C;--r4:#8F6B00;--r5:#0B7285;--r6:#9C36B5;
--r7:#5C940D;--r8:#1971C2;--r9:#495057}
@media (prefers-color-scheme:dark){:root{--bg:#0D1117;--panel:#161B22;--panel2:#1C2128;--line:#30363D;
--text:#E6EDF3;--muted:#9198A1;--indigo:#91A7FF;--orange:#FF922B;--ok:#3FB950;--bad:#F85149;--warn:#D29922;
--bad-bg:#2D1214;--warn-bg:#272011;--r0:#91A7FF;--r1:#FF922B;--r2:#63E6BE;--r3:#F783AC;--r4:#FFD43B;
--r5:#66D9E8;--r6:#DA77F2;--r7:#A9E34B;--r8:#74C0FC;--r9:#ADB5BD}}
.r0{--rc:var(--r0)}.r1{--rc:var(--r1)}.r2{--rc:var(--r2)}.r3{--rc:var(--r3)}.r4{--rc:var(--r4)}
.r5{--rc:var(--r5)}.r6{--rc:var(--r6)}.r7{--rc:var(--r7)}.r8{--rc:var(--r8)}.r9{--rc:var(--r9)}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text)}
body{font:13.5px/1.45 ui-sans-serif,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.mono,code,.id{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
a{color:inherit;text-decoration:none}a:focus-visible,summary:focus-visible{outline:2px solid var(--indigo);
outline-offset:2px;border-radius:4px}
.muted{color:var(--muted)}.wrap{max-width:1600px;margin:0 auto;padding:0 20px}
.top{background:var(--panel);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;gap:14px;padding-top:10px;padding-bottom:10px;flex-wrap:wrap}
.top h1{margin:0;font-size:18px;font-weight:700;letter-spacing:-.01em}.top h1 b{color:var(--orange)}
.scope{font:600 12px ui-monospace,SFMono-Regular,Menlo,monospace;padding:2px 9px;border-radius:999px;
border:1px solid var(--line);color:var(--muted)}.scope b{color:var(--text)}
.asof{font-size:12px;color:var(--muted)}.nav{margin-left:auto;display:flex;gap:14px;font-size:12.5px}
.nav a{color:var(--indigo)}.nav a:hover{text-decoration:underline}
.chip{display:inline-flex;align-items:center;gap:4px;font-size:11.5px;padding:0 7px;line-height:18px;
border-radius:999px;color:var(--rc);background:color-mix(in srgb,var(--rc) 13%,transparent);white-space:nowrap;
font-weight:550;min-width:62px;flex:0 1 auto}
.chip .cn{overflow:hidden;text-overflow:ellipsis}
.dot{width:7px;height:7px;border-radius:50%;background:var(--rc);flex:0 0 auto;display:inline-block}
.baton{width:24px;height:12px;flex:0 0 auto;vertical-align:-1px}
.baton .body{fill:var(--orange)}.baton .band{fill:var(--panel)}
.legend{display:flex;gap:8px;padding:10px 0;overflow-x:auto;align-items:stretch}
.legend .cap{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);align-self:center;
white-space:nowrap;margin-right:4px}
.role{flex:0 0 auto;display:grid;grid-template-columns:auto auto;column-gap:8px;align-items:center;
padding:5px 10px 5px 8px;border:1px solid var(--line);border-left:3px solid var(--rc);border-radius:8px;
background:var(--panel);max-width:310px}
.role .nm{font-weight:650;color:var(--rc);white-space:nowrap}
.role .ph{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);text-align:right;
white-space:nowrap}
.role .st{grid-column:1/3;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.role .st.ok{color:var(--ok)}.role .st.bad{color:var(--bad)}.role .st.warn{color:var(--warn)}
.role.away{opacity:.55}.role.holder{border-color:var(--orange);border-left-color:var(--rc);
box-shadow:0 0 0 1px var(--orange) inset}
.role .tag{grid-column:1/3;font-size:11px;display:flex;gap:4px;align-items:center;margin-top:2px}
.role .tag.perf{color:var(--muted)}.role .tag.hold{color:var(--orange);font-weight:600}.role .tag.lock{color:var(--warn);font-weight:600}
.board{display:flex;gap:10px;align-items:flex-start;padding:4px 0 10px}
.board.few .col:not(.rail){max-width:560px}
.calm{margin:2px 0 6px;padding:7px 12px;border:1px solid color-mix(in srgb,var(--ok) 45%,var(--line));
border-radius:9px;color:var(--ok);font-weight:600;background:var(--panel);display:flex;gap:10px;
align-items:baseline}.calm span{color:var(--muted);font-weight:400}
.col{flex:1 1 230px;min-width:190px;max-width:440px;background:var(--panel2);border:1px solid var(--line);
border-top:3px solid var(--cc,var(--line));border-radius:10px;display:flex;flex-direction:column}
.c-blocked{--cc:var(--bad)}.c-ask{--cc:var(--warn)}.c-ans{--cc:var(--indigo)}.c-pick{--cc:var(--orange)}
.c-prog{--cc:var(--r8)}.c-passed{--cc:var(--muted)}.c-done{--cc:var(--ok)}
.col-hd{padding:9px 12px 7px}.col-hd .row{display:flex;align-items:baseline;gap:8px}
.col-hd h2{margin:0;font-size:13px;font-weight:700}
.col-hd .n{font:700 12px ui-monospace,SFMono-Regular,Menlo,monospace;padding:0 7px;border-radius:999px;
background:var(--panel);border:1px solid var(--line);color:var(--muted)}
.col-hd p{margin:2px 0 0;font-size:11.5px;color:var(--muted)}
.col-bd{padding:2px 7px 10px;display:flex;flex-direction:column;gap:8px}
.col.rail{flex:0 0 42px;min-width:42px;max-width:42px;min-height:190px;background:transparent;
border-style:dashed;border-top-style:solid}
.rail .col-hd{padding:10px 0;display:flex;justify-content:center}
.rail .row{writing-mode:vertical-rl;gap:8px;align-items:center}
.rail h2{color:var(--muted);font-weight:600}.rail p,.rail .col-bd{display:none}
.rail .n{padding:0;border:0;background:none}
.empty{font-size:12px;color:var(--muted);padding:6px 4px}
.card{display:flex;flex-direction:column;gap:5px;background:var(--panel);border:1px solid var(--line);
border-left:4px solid var(--cc,var(--line));border-radius:9px;padding:8px 11px 9px}
.card:hover{border-color:var(--muted);border-left-color:var(--cc,var(--muted))}
.card .hd{display:flex;align-items:center;gap:7px;font-size:12px}
.k{font:700 10.5px ui-monospace,SFMono-Regular,Menlo,monospace;padding:0 5px;border-radius:4px;
line-height:17px;border:1px solid currentColor}
.k-Q .k{color:var(--warn)}.k-B .k{color:var(--bad)}.k-H .k{color:var(--orange)}
.card .id{font-weight:650;font-size:12px}
.card .ph.oc-rework{color:var(--bad);border-color:var(--bad)}.card .ph.oc-accepted{color:var(--ok);border-color:var(--ok)}
.card .ph{white-space:nowrap;font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);
border:1px solid var(--line);border-radius:4px;padding:0 5px;line-height:16px}
.card .age{margin-left:auto;color:var(--muted);font-size:11.5px;white-space:nowrap}
.card .ttl{font-size:13.5px;line-height:1.35;font-weight:600;display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden}
.card .who{display:flex;gap:4px;align-items:center;color:var(--muted);font-size:12px;min-width:0;overflow:hidden}
.who .arr{flex:0 0 auto}.card.prog .id{color:var(--muted)}
.card .lock{font-size:12px;color:var(--bad);font-weight:600}
.risk{align-self:flex-start;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
font-size:11.5px;font-weight:650;color:var(--warn);background:var(--warn-bg);
border:1px solid color-mix(in srgb,var(--warn) 45%,transparent);border-radius:5px;padding:0 6px;line-height:18px}
.card .next{font-size:12.5px;border-top:1px solid var(--line);padding-top:6px;display:flex;gap:7px;
align-items:baseline}
.card .next b{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);flex:0 0 auto}
.c-passed .card .ttl{font-weight:500}
.c-blocked .card{background:var(--bad-bg);border-color:color-mix(in srgb,var(--bad) 40%,var(--line))}
.card.prog .st{font-size:13px;font-weight:600}.card.prog .st.bad{color:var(--bad)}
.card.mini{padding:5px 10px 6px;gap:3px}
.card.mini .ttl{font-size:12.5px;font-weight:500;-webkit-line-clamp:1;color:var(--muted)}
.card.mini .who{font-size:11px}.card.mini .chip{font-size:11px;line-height:16px}
details.more>summary{cursor:pointer;list-style:none;font-size:12px;color:var(--muted);padding:6px 8px;
border:1px dashed var(--line);border-radius:8px;text-align:center}
details.more>summary::-webkit-details-marker{display:none}
details.more>summary:hover{color:var(--text);border-color:var(--muted)}
details.more[open]>summary{margin-bottom:8px}
details.more .stack{display:flex;flex-direction:column;gap:8px}
.records{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;align-items:start;padding-bottom:6px}
.rec{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.rec>summary,.rec>.sm{cursor:pointer;list-style:none;padding:8px 12px;display:flex;align-items:baseline;
gap:8px;font-size:12.5px}
.rec>summary::-webkit-details-marker{display:none}
.rec>summary::before{content:"\\25B8";font-size:10px;color:var(--muted)}
.rec[open]>summary::before{content:"\\25BE"}.rec>.sm{cursor:default}
a.rec:hover{border-color:var(--muted)}.rec b{font-size:12px;text-transform:uppercase;letter-spacing:.05em}
.rec .s{color:var(--muted);font-size:12px;margin-left:auto;white-space:nowrap}
.rec ul{list-style:none;margin:0;padding:0 0 6px;border-top:1px solid var(--line);max-height:300px;overflow:auto}
.rec li{display:grid;grid-template-columns:14px 1fr auto;gap:6px;padding:5px 12px;font-size:12.5px;
align-items:baseline}.rec li:hover{background:var(--panel2)}
.rec li .mk{color:var(--indigo)}.rec li .id{font-size:11.5px;color:var(--muted)}
.rec li .x{font-size:11.5px;color:var(--muted);white-space:nowrap}.rec li.bad{color:var(--bad)}
.rec .ft{padding:0 12px 8px;font-size:11.5px;color:var(--muted)}
a.rec .warn{color:var(--warn);font-weight:650}a.rec .lnk{color:var(--indigo)}
.seg{display:flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.seg a{padding:2px 10px;font-size:12px;color:var(--muted)}
.seg a[aria-current="true"]{background:var(--panel2);color:var(--text);font-weight:600}
.h2{display:flex;align-items:baseline;gap:10px;margin:16px 0 9px;flex-wrap:wrap}
.h2 h2{margin:0;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.h2 .hint{font-size:12px;color:var(--muted)}.back{color:var(--indigo)}
.cpage{columns:2 520px;column-gap:20px;padding-top:6px}
.cgroup{break-inside:avoid;background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:8px 10px;margin:0 0 14px}
.cgroup h3{margin:2px 2px 6px;font:600 12.5px ui-monospace,SFMono-Regular,Menlo,monospace;display:flex}
.cgroup h3 .c{margin-left:auto;color:var(--muted);font-weight:400}
.cgroup ul{list-style:none;margin:0;padding:0}
.cgroup li a{display:grid;grid-template-columns:10px 54px 1fr auto;gap:6px;align-items:baseline;padding:4px;
border-radius:5px;font-size:12.5px}.cgroup li a>span{min-width:0}.cgroup li a:hover{background:var(--panel2)}
.cgroup .id{color:var(--indigo);font-size:11.5px}
.cgroup .files{display:block;font-size:10.5px;color:var(--muted);white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.cgroup .src{font:10.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.cgroup li.new .src{color:var(--orange);font-weight:700}.cgroup li.hot a{background:var(--warn-bg)}
.crisk{display:inline-block;margin-top:3px;font-size:11px;font-weight:650;color:var(--warn)}
footer{margin-top:14px;padding:12px 0 18px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
@media (max-width:1100px){.board{overflow-x:auto}.records{grid-template-columns:1fr}}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def title_of(t: dict) -> str:
    return t["title"] or render.first_line(t["body"])


def dur(hours: float | None) -> str:
    if hours is None:
        return ""
    if hours >= 48:
        return f"{hours / 24:.1f}d"
    h, m = divmod(max(1, round(hours * 60)), 60)
    return f"{h}h {m}m" if h and m else f"{h}h" if h else f"{m}m"


def words(items: list[str]) -> str:
    return " and ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else "".join(items)


def named(t: dict) -> list[str]:
    return [r for r in t["to"] if r != "all"]


def answered(t: dict) -> bool:
    return metrics.first_answer(t) is not None


def phase_of(t: dict) -> str:
    if t.get("phase"):
        return t["phase"]
    found = PHASE.search(t.get("title") or "")
    if found:
        return found.group(0)
    return (t.get("blocks") or [""])[0] if t["kind"] == "B" else ""


def area(t: dict) -> str:
    f = (t.get("files") or [""])[0].lstrip("/")
    if not f:
        found = re.search(r"`((?:packages|apps|services|infra|e2e|coordination)/[^`\s]+)`", t.get("body", ""))
        f = found.group(1) if found else ""
    if not f:
        return ""
    parts = f.split("/")
    if parts[0] in ("packages", "apps", "services") and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0] if len(parts) > 1 else "(root files)"


class Model:
    """What the board shows, decided once: which column each thread is in, who holds what, what touches what."""

    def __init__(self, board: Board, now: datetime | None = None):
        cfg = board.cfg
        self.now = now or datetime.now()
        self.sandbox = bool(cfg.get("sandbox"))
        self.sprint, self.task = cfg["sprint"], cfg.get("task", "")
        self.status = board.status()
        every = sorted(board.entries().values(), key=lambda t: t.get("n", 0))
        self.threads = [t for t in every if t["sprint"] == self.sprint]
        self.contracts = [t for t in every if t["kind"] == "C" and t["status"] == "OPEN"]
        others = sandbox.live_contracts(board.root, self.task) if self.sandbox else []
        self.live = self.contracts + others
        seen = {r for t in self.threads for r in (t["from"], *named(t))} | set(self.status)
        self.roles = list(cfg.get("roles") or []) + sorted(seen - set(cfg.get("roles") or []))
        self.flow = metrics.hand_off_stats(board, self.threads, self.roles)["roles"]
        self.refusals = [r for r in board.refusals() if r["what"] == "handoff" and not r.get("forced")]
        self.open_ids = {t["id"] for t in self.threads if t["status"] == "OPEN"}
        self.awaiting = {r: [t["id"] for t in board.awaiting(r)] for r in self.roles}
        handoffs = [t for t in self.threads if t["kind"] == "H"]
        self.holders: dict[str, list[str]] = {}
        self.pending: dict[str, list[str]] = {}
        self.passed_on: dict[str, str] = {}
        for h in (x for x in handoffs if x["status"] == "OPEN"):
            to, later = named(h), {}
            for r in to:
                nxt = next((x for x in handoffs if x["from"] == r and x.get("n", 0) > h.get("n", 0)), None)
                if nxt:
                    later[r] = nxt["id"]
            self.pending[h["id"]] = [r for r in to if r not in later]
            if to and not self.pending[h["id"]]:
                self.passed_on[h["id"]] = next(iter(later.values()))
            for r in self.pending[h["id"]]:
                self.holders.setdefault(r, []).append(h["id"])
        by_file: dict[str, list[dict]] = {}
        for c in self.live:
            for f in c.get("files") or []:
                by_file.setdefault(f, []).append(c)
        self.by_file = by_file
        self.touched_by: dict[str, list[str]] = {}
        for t in self.threads:
            for c, _ in self.touches(t):
                self.touched_by.setdefault(self.ref(c), []).append(t["id"])
        self.decisions = [t for t in reversed(self.threads) if t["kind"] == "D"]
        self.columns = self._place()
        phases = {phase_of(t) for t in self.threads if t["kind"] in WORK} - {""}
        self.show_phase = not self.sandbox and len(phases) >= 2

    def rc(self, role: str) -> str:
        return f"r{self.roles.index(role) % 10}" if role in self.roles else "r9"

    def ref(self, c: dict) -> str:
        return c.get("ref") or c["id"]

    def hours(self, t: dict) -> float | None:
        return metrics.age_hours(t, self.now)

    def is_new(self, c: dict) -> bool:
        return "ref" not in c and c["sprint"] == self.sprint

    def touches(self, t: dict) -> list[tuple[dict, str]]:
        if t["kind"] == "C" or t["status"] != "OPEN":
            return []
        hit: list[tuple[dict, str]] = []
        for f in t.get("files") or []:
            for c in self.by_file.get(f, []):
                own = c["from"] == t["from"] and self.is_new(c)
                if not own and all(c is not h for h, _ in hit):
                    hit.append((c, f))
        return hit

    def locked_by(self, t: dict) -> list[str]:
        """Roles whose next hand-off is refused until they answer this thread."""
        return [r for r in named(t) if r != t["from"] and not any(x["from"] == r for x in t["replies"])]

    def refused_for(self, thread_id: str) -> list[dict]:
        return [r for r in self.refusals if thread_id in r["waiting"] and thread_id in self.open_ids]

    def column_of(self, t: dict) -> str:
        if t["status"] != "OPEN":
            return "done"
        if t["kind"] in ("Q", "B"):
            return "ans" if answered(t) else "blocked" if t["kind"] == "B" else "ask"
        return "passed" if t["id"] in self.passed_on else "pick"

    def _place(self) -> dict[str, list]:
        cols: dict[str, list] = {key: [] for key, _, _ in COLUMNS}
        for t in (x for x in self.threads if x["kind"] in WORK):
            cols[self.column_of(t)].append(t)
        cols["done"].sort(key=lambda t: self.hours(t) or 0)
        last_open = {t["from"]: t for t in self.threads if t["kind"] in WORK and t["status"] == "OPEN"}
        by_id = {t["id"]: t for t in self.threads}
        for role, row in self.status.items():
            state = row.get("state") or ""
            if not state or state.upper().startswith("DONE") or "wait" in state.lower():
                continue
            if not self.sandbox and not self.in_sprint(row.get("phase")):
                continue
            link = last_open.get(role)
            if not link and row.get("handoff"):
                cand = by_id.get(row["handoff"].split()[0])
                link = cand if cand and cand["status"] == "OPEN" else None
            if link:
                cols["prog"].append({"role": role, "row": row, "thread": link})
        cols["prog"].sort(key=lambda p: p["row"].get("updated") or "", reverse=True)
        return cols

    def in_sprint(self, phase: str | None) -> bool:
        return not phase or phase == self.sprint or phase.startswith(self.sprint + "-")

    def events(self) -> list[tuple[datetime, str, str, str]]:
        """(when, text, thread id, css class), newest first."""
        out = []
        for r in self.refusals:
            when = metrics.moment(r.get("ts"), r.get("at"))
            if when:
                out.append((when, f"{r['role']}'s hand-off was refused", "", "bad"))
        for t in self.threads:
            to = words(named(t)) or "everyone"
            verb = {"Q": f"{t['from']} asked {to}", "B": f"{t['from']} raised a blocker",
                    "C": f"{t['from']} agreed a contract", "D": f"{t['from']} recorded a decision",
                    "H": f"{t['from']} handed off to {to}"}[t["kind"]]
            when = metrics.moment(t["ts"], t.get("at"))
            if when:
                out.append((when, verb, t["id"], ""))
            for r in t["replies"]:
                when = metrics.moment(r.get("ts"), r.get("at"))
                if when:
                    asked = r["from"] != t["from"] and t["kind"] in ("Q", "B")
                    out.append((when, f"{r['from']} {'answered' if asked else 'replied on'} {t['id']}", t["id"], ""))
        return sorted(out, key=lambda e: e[0], reverse=True)

    def ago(self, when: datetime | None) -> str:
        return dur(None if when is None else max(0.0, (self.now - when).total_seconds() / 3600))


def chip(m: Model, role: str) -> str:
    return f'<span class="chip {m.rc(role)}"><span class="dot"></span><span class="cn">{esc(role)}</span></span>'


def chips(m: Model, roles: list[str], cap: int = 0) -> str:
    shown = roles[:cap] if cap and len(roles) > cap else roles
    extra = f' <span class="arr">+{len(roles) - len(shown)}</span>' if len(shown) < len(roles) else ""
    return " ".join(chip(m, r) for r in shown) + extra


def runners(m: Model) -> str:
    cards = []
    for role in m.roles:
        if role not in m.status and not any(role in (t["from"], *named(t)) for t in m.threads):
            continue
        row = m.status.get(role) or {"phase": "", "state": "no status row"}
        state, phase = row.get("state", ""), row.get("phase", "")
        away = not m.sandbox and not m.in_sprint(phase)
        tone = ("bad" if re.match(r"(NEEDS|BLOCK|FAIL)", state, re.IGNORECASE) else "ok" if state.upper().startswith("DONE")
                else "warn" if "wait" in state.lower() else "")
        tags = ""
        hold = m.holders.get(role, [])
        if hold:
            tags += f'<span class="tag hold">{BATON}holds {esc(f"{len(hold)} batons" if len(hold) > 2 else ", ".join(hold))}</span>'
        owed = [i for i in m.awaiting.get(role, []) if i in m.open_ids]
        if owed:
            refused = sum(1 for r in m.refusals if r["role"] == role and set(r["waiting"]) & m.open_ids)
            tags += (f'<span class="tag lock">pass locked: {esc(", ".join(owed))} unanswered'
                     f'{f" · refused {refused}×" if refused else ""}</span>')
        flow = m.flow.get(role) or {}
        if flow.get("handoffs_sent"):
            bits = [f'{flow["handoffs_sent"]} hand-off{"" if flow["handoffs_sent"] == 1 else "s"}']
            if flow["rework"]:
                bits.append(f'{flow["rework"]} rework')
            if flow["hours_held"]["n"]:
                bits.append(f'hold {dur(flow["hours_held"]["median"])}')
            tags += f'<span class="tag perf">{esc(" · ".join(bits))}</span>'
        shown = "" if m.sandbox and phase == m.task else phase or ("" if m.sandbox else "—")
        tip = f'{role} · {phase} · {state}' + (f' · last {row["handoff"]}' if row.get("handoff") else "") \
            + (f' · {row["updated"]}' if row.get("updated") else "")
        cards.append(f'<div class="role {m.rc(role)}{" away" if away else ""}{" holder" if hold else ""}" '
                     f'title="{esc(tip)}"><span class="nm">{esc(role)}</span><span class="ph">{esc(shown)}</span>'
                     f'<span class="st {tone}">{esc(state)}</span>{tags}</div>')
    return f'<nav class="legend" aria-label="Runners"><span class="cap">Runners</span>{"".join(cards)}</nav>'


def next_step(m: Model, t: dict, col: str) -> str:
    to = named(t)
    if col == "blocked":
        return f"{esc(words(to) or 'someone')} clears it, then closes {esc(t['id'])}."
    if col == "ask":
        return f"{esc(words(to))} answers; {esc(t['from'])} closes it."
    if col == "pick":
        return f"{esc(words(m.pending.get(t['id']) or to) or 'someone')} picks it up."
    if col == "ans":
        who = metrics.first_answer(t)["from"]
        return f"{esc(t['from'])} can close it ({esc(who)} {'answered' if t['kind'] == 'Q' else 'replied'})."
    if col == "passed":
        return f"{esc(words(to))} passed it on in {esc(m.passed_on[t['id']])}; close it."
    return ""


def card(m: Model, t: dict, col: str, mini: bool = False) -> str:
    to = named(t)
    tip = (f"{KIND[t['kind']]} {t['id']} · {title_of(t)} · {t['from']} → {', '.join(to) or 'everyone'}"
           + (f" · {t['model']}" if t.get("model") else ""))
    tag = f'<span class="ph">{esc(phase_of(t))}</span>' if m.show_phase and phase_of(t) else ""
    if t.get("closed_outcome"):
        tag += f'<span class="ph oc-{t["closed_outcome"]}">{esc(t["closed_outcome"])}</span>'
    head = (f'<div class="hd"><span class="k">{t["kind"]}</span><span class="id">{esc(t["id"])}</span>{tag}'
            f'<span class="age" title="last activity">{esc(dur(m.hours(t)))}</span></div>')
    who = (f'<div class="who">{chip(m, t["from"])}<span class="arr">→</span>'
           f'{chips(m, to, 2) if to else "<span>everyone</span>"}</div>')
    extra = ""
    if not mini:
        if col == "ask":
            refs = m.refused_for(t["id"])
            refused = (f' · baton refused "{esc(refs[0]["title"])}"' + (f" +{len(refs) - 1}" if len(refs) > 1 else "")
                       if refs else "")
            extra += f'<div class="lock">{esc(words(m.locked_by(t)))} can\'t hand off until answered{refused}</div>'
        hits = m.touches(t)
        if hits:
            tips = "\n".join(f"{f} is covered by {m.ref(c)}: {title_of(c)}" for c, f in hits)
            extra += (f'<span class="risk" title="{esc(tips)}">⚠ touches '
                      f'{esc(", ".join(m.ref(c) for c, _ in hits))}</span>')
        step = next_step(m, t, col)
        if step:
            extra += f'<div class="next"><b>Next</b><span>{step}</span></div>'
    return (f'<a class="card k-{t["kind"]}{" mini" if mini else ""}" href="/e/{esc(t["id"])}" title="{esc(tip)}">'
            f'{head}<div class="ttl">{esc(title_of(t))}</div>{who}{extra}</a>')


def progress_card(m: Model, p: dict) -> str:
    row, t = p["row"], p["thread"]
    tone = "bad" if re.match(r"(NEEDS|BLOCK|FAIL)", row["state"], re.IGNORECASE) else ""
    tag = f'<span class="ph">{esc(row["phase"])}</span>' if m.show_phase and row.get("phase") else ""
    updated = metrics.parse_ts(row.get("updated"))
    return (f'<a class="card prog k-{t["kind"]}" href="/e/{esc(t["id"])}" '
            f'title="{esc(p["role"])} · {esc(row["state"])} · {esc(t["id"])} {esc(title_of(t))}">'
            f'<div class="hd">{chip(m, p["role"])}{tag}<span class="age">updated {esc(m.ago(updated))} ago</span></div>'
            f'<div class="st {tone}">{esc(row["state"])}</div>'
            f'<div class="ttl"><span class="id">{esc(t["id"])}</span> {esc(title_of(t))}</div></a>')


def column(m: Model, key: str, name: str, hint: str) -> str:
    items = m.columns[key]
    rail = not items and key != "done"
    mini = key == "done"
    one = (lambda x: progress_card(m, x)) if key == "prog" else (lambda x: card(m, x, key, mini))
    shown = CAP.get(key, len(items))
    body = "".join(one(x) for x in items[:shown])
    if len(items) > shown:
        body += (f'<details class="more"><summary>+{len(items) - shown} more</summary><div class="stack">'
                 f'{"".join(one(x) for x in items[shown:])}</div></details>')
    body = body or '<div class="empty">Nothing here.</div>'
    return (f'<section class="col c-{key}{" rail" if rail else ""}" aria-label="{esc(name)} ({len(items)})">'
            f'<div class="col-hd"><div class="row"><h2>{esc(name)}</h2><span class="n">{len(items)}</span></div>'
            f'<p>{esc(hint)}</p></div><div class="col-bd">{body}</div></section>')


def board_html(m: Model) -> str:
    empty = sum(1 for k, _, _ in COLUMNS if k != "done" and not m.columns[k])
    calm = ""
    if not m.columns["blocked"] and not m.columns["ask"] and empty >= 3:
        n = len(m.columns["pick"])
        waiting = f"{n} hand-off{'' if n == 1 else 's'} to pick up." if n else ""
        calm = f'<div class="calm">Nothing blocked, nothing waiting for an answer.<span>{waiting}</span></div>'
    few = len(COLUMNS) - empty <= 3
    cols = "".join(column(m, k, n, h) for k, n, h in COLUMNS)
    return f'{calm}<main class="board{" few" if few else ""}">{cols}</main>'


def records(m: Model) -> str:
    if m.decisions:
        rows = "".join(f'<li><span class="mk">◆</span><a href="/e/{esc(t["id"])}" title="{esc(title_of(t))}">'
                       f'{esc(title_of(t))}</a><span class="x"><span class="id">{esc(t["id"])}</span> · '
                       f'{esc(m.ago(metrics.moment(t["ts"], t.get("at"))))}</span></li>' for t in m.decisions)
        decided = (f'<details class="rec"><summary><b>◆ Decided</b><span class="s">{len(m.decisions)} in force</span>'
                   f'</summary><ul>{rows}</ul><div class="ft">Records, not tasks: nothing to answer or close.</div></details>')
    else:
        decided = '<div class="rec"><div class="sm"><b>◆ Decided</b><span class="s">none yet</span></div></div>'
    touched = len(m.touched_by)
    flag = f' · <span class="warn">{touched} touched by open work</span>' if touched else ""
    contracts = (f'<a class="rec" href="/contracts"><div class="sm"><b>Contracts in force</b><span class="s">'
                 f'<span class="lnk">{len(m.live)}{flag} →</span></span></div></a>')
    events = m.events()[:30]
    rows = "".join(f'<li class="{cls}"><span></span><span>{esc(text)}'
                   f'{f" · <span class=id>{esc(tid)}</span>" if tid else ""}</span><span class="x">{esc(m.ago(when))}'
                   f'</span></li>' for when, text, tid, cls in events)
    last = f"last: {m.ago(events[0][0])} ago" if events else "—"
    recent = f'<details class="rec"><summary><b>Recent</b><span class="s">{esc(last)}</span></summary><ul>{rows}</ul></details>'
    return f'<div class="records">{decided}{contracts}{recent}</div>'


def contracts_html(m: Model, filt: str) -> str:
    filt = filt if filt in CONTRACT_FILTERS else "all"
    labels = {"all": "all", "new": "this task" if m.sandbox else f"made in {m.sprint}",
              "old": "other tasks" if m.sandbox else "older sprints", "touched": "touched by open work"}

    def keep(c: dict, k: str) -> bool:
        return (k == "all" or (k == "new" and m.is_new(c)) or (k == "old" and not m.is_new(c))
                or (k == "touched" and m.ref(c) in m.touched_by))
    seg = "".join(f'<a href="/contracts?f={k}" aria-current="{str(filt == k).lower()}">{esc(labels[k])} '
                  f'<span class="muted">{sum(keep(c, k) for c in m.live)}</span></a>' for k in CONTRACT_FILTERS)
    nav = (f'<div class="h2"><a class="back" href="/">← board</a><h2>Contracts in force</h2><div class="seg">{seg}</div>'
           '<span class="hint">A contract holds until a newer one supersedes it.</span></div>')
    groups: dict[str, list[dict]] = {}
    for c in (x for x in m.live if keep(x, filt)):
        groups.setdefault(area(c) or "(no files named)", []).append(c)
    if not groups:
        return nav + '<div class="empty">No contracts here.</div>'
    order = sorted(groups, key=lambda a: (a.startswith("("), -len(groups[a]), a))
    out = []
    for a in order:
        items = sorted(groups[a], key=lambda c: (m.ref(c) not in m.touched_by, not m.is_new(c), -c.get("n", 0)))
        rows = []
        for c in items:
            hot = m.touched_by.get(m.ref(c))
            src = c["task"] if "ref" in c else "this task" if m.sandbox and m.is_new(c) else c["sprint"]
            files = f'<span class="files mono">{esc(" · ".join(c["files"]))}</span>' if c.get("files") else ""
            risk = f'<span class="crisk">open work changes these files: {esc(", ".join(hot))}</span>' if hot else ""
            rows.append(f'<li class="{"new" if m.is_new(c) else ""}{" hot" if hot else ""}">'
                        f'<a href="/e/{esc(m.ref(c))}"><span class="dot {m.rc(c["from"])}"></span>'
                        f'<span class="id mono">{esc(c["id"])}</span><span>{esc(title_of(c))}{files}{risk}</span>'
                        f'<span class="src">{esc(src)}</span></a></li>')
        out.append(f'<section class="cgroup"><h3>{esc(a)}<span class="c">{len(items)}</span></h3>'
                   f'<ul>{"".join(rows)}</ul></section>')
    return nav + f'<div class="cpage">{"".join(out)}</div>'


def document(project: str, m: Model, body: str, title: str) -> str:
    scope = (f"task <b>{esc(m.task)}</b> · sandbox" if m.sandbox else f"sprint <b>{esc(m.sprint)}</b>")
    head = (f'<header class="top"><div class="wrap"><h1><b>baton</b> · {esc(project)}</h1><span class="scope">{scope}'
            f'</span><span class="asof">updated {m.now:%H:%M} · read-only</span>'
            '<span class="nav"><a href="/">board</a><a href="/contracts">contracts</a><a href="/metrics">metrics</a>'
            '</span></div></header>')
    foot = ('<footer>baton serve · read-only · refreshes every 30 s · cards open <code>/e/&lt;id&gt;</code> · a '
            'hand-off is refused while a question to that role has no answer · Q question, B blocker, H hand-off '
            'are work; decisions and contracts are records</footer>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30">'
            f'<title>{esc(title)}</title><style>{CSS}</style></head><body>{head}<div class="wrap">{body}{foot}'
            '</div></body></html>')


def board_page(board: Board, now: datetime | None = None) -> str:
    m = Model(board, now)
    return document(board.root.name, m, runners(m) + board_html(m) + records(m), f"baton · {board.root.name}")


def contracts_page(board: Board, filt: str = "all", now: datetime | None = None) -> str:
    m = Model(board, now)
    return document(board.root.name, m, contracts_html(m, filt), f"contracts · {board.root.name}")
