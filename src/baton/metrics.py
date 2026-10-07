"""Board health metrics: how fast questions get answered, how threads close, who is loaded.

All numbers come from the event log. Times are hours between events. The exact UTC
`at` field is used when present (baton >= 1.1), otherwise the local `ts` (`YYYY-MM-DD HH:MM`).
Entries whose timestamps are missing or day-only (some imported ones) count in totals but not
in time-based numbers.
"""

from __future__ import annotations

import re
from datetime import datetime
from statistics import median

from . import render
from .store import Board

STALE_DEFAULT_HOURS = 48.0


def parse_ts(ts: str | None) -> datetime | None:
    """Minute-precision timestamps only; day-only or unknown dates give None."""
    try:
        return datetime.strptime(ts or "", "%Y-%m-%d %H:%M")  # noqa: DTZ007 - board times are local wall-clock
    except ValueError:
        return None


def parse_duration(text: str) -> float:
    """'2d', '36h', '90m' or a bare number of hours -> hours."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([dhm]?)\s*", text or "")
    if not m:
        raise ValueError(f"not a duration: {text!r} (use e.g. 2d, 36h or 90m)")
    value, unit = float(m.group(1)), m.group(2) or "h"
    return value * {"d": 24, "h": 1, "m": 1 / 60}[unit]


def moment(ts: str | None, at: str | None = None) -> datetime | None:
    """A local, naive datetime: from the exact UTC `at` if given, else the local `ts`."""
    if at:
        try:
            return datetime.fromisoformat(at).astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    return parse_ts(ts)


def hours_between(a: str | None, b: str | None, a_at: str | None = None, b_at: str | None = None) -> float | None:
    start, end = moment(a, a_at), moment(b, b_at)
    if start is None or end is None or end < start:
        return None
    return (end - start).total_seconds() / 3600


def age_hours(t: dict, now: datetime) -> float | None:
    """Hours since the thread's last activity (entry, reply or close)."""
    last = moment(t.get("last_ts") or t["ts"], t.get("last_at") or t.get("at"))
    return None if last is None else max(0.0, (now - last).total_seconds() / 3600)


def first_answer(t: dict) -> dict | None:
    return next((r for r in t["replies"] if r["from"] != t["from"]), None)


def _stats(values: list[float]) -> dict:
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "median": None, "p90": None}
    return {"n": len(values), "median": round(median(values), 1),
            "p90": round(values[min(len(values) - 1, int(len(values) * 0.9))], 1)}


def _summary(threads: list[dict], now: datetime, stale_h: float) -> dict:
    asks = [t for t in threads if t["kind"] in ("Q", "B")]
    open_ = [t for t in threads if t["status"] == "OPEN"]
    answered = [t for t in asks if first_answer(t)]
    stale = [t for t in open_ if (age_hours(t, now) or 0) >= stale_h]
    return {
        "entries": len(threads),
        "by_kind": {k: sum(t["kind"] == k for t in threads) for k in sorted({t["kind"] for t in threads})},
        "open": len(open_),
        "closed": len(threads) - len(open_),
        "close_rate": round((len(threads) - len(open_)) / len(threads), 2) if threads else None,
        "questions_and_blockers": len(asks),
        "answered": len(answered),
        "unanswered_open": sum(1 for t in asks if t["status"] == "OPEN" and not first_answer(t)),
        "hours_to_first_answer": _stats([hours_between(t["ts"], first_answer(t)["ts"], t.get("at"),
                                                       first_answer(t).get("at")) for t in answered]),
        "hours_to_close": _stats([hours_between(t["ts"], t["closed_ts"], t.get("at"), t.get("closed_at"))
                                  for t in threads if t["closed_ts"]]),
        "stale_open": len(stale),
        "stale_ids": [t["id"] for t in stale],
    }


def _tokens(text: str) -> int:
    return (len(text) + 3) // 4  # same estimate as `baton stats` (~4 characters per token)


def compute(board: Board, sprint: str | None = None, now: datetime | None = None,
            stale_hours: float = STALE_DEFAULT_HOURS) -> dict:
    now = now or datetime.now()  # noqa: DTZ005 - compared with local wall-clock board times
    every = list(board.entries().values())
    scope = [t for t in every if sprint is None or t["sprint"] == sprint]
    sprints: dict[str, list[dict]] = {}
    for t in every:
        sprints.setdefault(t["sprint"], []).append(t)
    order = sorted(sprints, key=lambda s: min(t["ev"] for t in sprints[s]))
    roles = board.cfg.get("roles") or sorted({t["from"] for t in every} | set(board.status()))
    from .cli import _unread_text  # lazy: cli imports this module
    per_role = {}
    for r in roles:
        unread_text, unread_count = _unread_text(board, r, False, peek=True)
        mine = [t for t in scope if t["from"] == r]
        asked = [t for t in scope if t["kind"] in ("Q", "B") and r in t["to"] and t["from"] != r]
        answers = [next((x for x in t["replies"] if x["from"] == r), None) for t in asked]
        per_role[r] = {
            "posted": len(mine),
            "replies": sum(1 for t in scope for x in t["replies"] if x["from"] == r),
            "asked_of": len(asked),
            "answered": sum(1 for a in answers if a),
            "hours_to_answer": _stats([hours_between(t["ts"], a["ts"], t.get("at"), a.get("at"))
                                       for t, a in zip(asked, answers) if a]),
            "waiting_on": len(board.awaiting(r)),
            "open_owned": sum(1 for t in mine if t["status"] == "OPEN"),
            "unread": unread_count,
            "unread_tokens": _tokens(unread_text),
        }
    return {
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "current_sprint": board.cfg["sprint"],
        "scope": sprint or "all sprints",
        "stale_hours": stale_hours,
        "summary": _summary(scope, now, stale_hours),
        "sprints": {s: {**_summary(sprints[s], now, stale_hours),
                        "tokens": _tokens("".join(render.entry_md(t) for t in sprints[s]))}
                    for s in order if sprint is None or s == sprint},
        "roles": per_role,
    }


def _h(stat: dict) -> str:
    return "—" if not stat["n"] else f"{stat['median']}h (p90 {stat['p90']}h, n={stat['n']})"


def format_text(m: dict) -> str:
    s = m["summary"]
    lines = [
        f"Board metrics: {m['scope']} (current sprint {m['current_sprint']}, {m['generated']})",
        "",
        f"Threads        {s['entries']} ({', '.join(f'{k} {v}' for k, v in s['by_kind'].items()) or 'none'})",
        f"Open / closed  {s['open']} / {s['closed']}" + (f"  (close rate {int(s['close_rate'] * 100)}%)"
                                                          if s["close_rate"] is not None else ""),
        f"First answer   {_h(s['hours_to_first_answer'])}  ({s['answered']} of {s['questions_and_blockers']} Q/B answered)",
        f"Time to close  {_h(s['hours_to_close'])}",
        f"Unanswered     {s['unanswered_open']} open Q/B with no answer",
        f"Stale          {s['stale_open']} open thread(s) idle >= {m['stale_hours']:g}h"
        + (f": {', '.join(s['stale_ids'][:10])}" + (" …" if len(s["stale_ids"]) > 10 else "") if s["stale_ids"] else ""),
        "",
        "Sprint       threads  open  closed  answered  median 1st answer  median close  stale  ~tokens",
    ]
    for name, x in m["sprints"].items():
        lines.append(f"{name:12} {x['entries']:7} {x['open']:5} {x['closed']:7} {x['answered']:9}  "
                     f"{_short(x['hours_to_first_answer']):>17}  {_short(x['hours_to_close']):>12}  {x['stale_open']:5}"
                     f"  {x['tokens']:7}")
    lines += ["", "Role           posted  replies  asked  answered  median answer  waiting on  open owned  unread (~tokens)"]
    for r, x in m["roles"].items():
        lines.append(f"{r:14} {x['posted']:6} {x['replies']:8} {x['asked_of']:6} {x['answered']:9}  "
                     f"{_short(x['hours_to_answer']):>13}  {x['waiting_on']:10}  {x['open_owned']:10}"
                     f"  {x['unread']} (~{x['unread_tokens']})")
    return "\n".join(lines)


def _short(stat: dict) -> str:
    return "—" if not stat["n"] else f"{stat['median']}h"
