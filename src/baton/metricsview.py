"""The `/metrics` page of `baton serve`: board health as a dashboard, in the board's shell and colours.

Every number comes from `metrics.compute()`. Charts are inline SVG or CSS widths, so the page needs no
script under the dashboard's CSP. Colour has one meaning each: role hues for roles, ok/warn/bad for
outcomes and tones, and neutral greys with one dark accent for every other series. Standard library only.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from . import metrics
from .boardview import Model, chip, dur, esc, scope_of, shell, title_of
from .store import Board

CSS = """
:root{--m1:var(--text);--m2:color-mix(in srgb,var(--muted) 85%,var(--panel));
--mtrack:color-mix(in srgb,var(--muted) 72%,var(--panel))}
.mhd{display:flex;align-items:center;gap:10px 14px;margin:16px 0 10px;flex-wrap:wrap}
.mhd h2{margin:0;font-size:15px;font-weight:700}.mhd .hint{font-size:12px;color:var(--muted)}
.mhd .seg{flex-wrap:wrap}.mhd .seg a{min-height:24px;display:inline-flex;align-items:center}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{display:block;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--kc,var(--line));
border-radius:10px;padding:9px 12px 10px;min-width:0}a.kpi:hover{border-color:var(--muted);border-left-color:var(--kc,var(--muted))}
.kpi .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.kpi .v{font:700 24px/1.2 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin-top:2px}
.kpi .s{font-size:11.5px;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.t-ok{--kc:var(--ok)}.t-warn{--kc:var(--warn)}.t-bad{--kc:var(--bad)}
.t-warn .v{color:var(--warn)}.t-bad .v{color:var(--bad)}
.mstack{display:flex;flex-direction:column;gap:12px;margin-top:12px}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:12px;align-items:start}
.pnl{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px 12px;min-width:0}
.pnl>h2{margin:0 0 2px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.pnl>.hint{margin:0 0 8px;font-size:12px;color:var(--muted)}
.empty{font-size:12.5px;color:var(--muted);padding:6px 0}.empty code{color:var(--text)}
.rows>.hrow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;padding:7px 0;
border-top:1px solid var(--line)}.rows>.hrow:first-child{border-top:0}
.hrow .l{font-size:12.5px;font-weight:600}
.hrow .v{font:700 13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;text-align:right;white-space:nowrap}
.hrow .v.warn{color:var(--warn)}.hrow .v.ok{color:var(--ok)}
.hrow .s{grid-column:1/3;font-size:12px;color:var(--muted)}.hrow .viz{grid-column:1/3;margin-top:3px}
.ids a{display:inline-block;white-space:nowrap;color:var(--indigo);font:11.5px/18px ui-monospace,SFMono-Regular,
Menlo,monospace;padding:3px 2px;margin-right:4px}.ids a:hover{text-decoration:underline}
.ids details{display:inline}.ids summary{display:inline;cursor:pointer;color:var(--muted);font-size:12px}
.bar{display:flex;height:10px;border-radius:999px;background:var(--panel2);overflow:hidden;min-width:60px;
box-shadow:inset 0 0 0 1px var(--mtrack)}
.bar i{display:block;height:100%;flex:0 1 auto}.bar i+i{border-left:1px solid var(--panel)}
.s-acc{background:var(--ok)}.s-rew{background:var(--bad)}.s-und{background:var(--m2)}
.s-m1{background:var(--m1)}.s-m2{background:var(--m2)}
.s-own{background:var(--rc)}.s-rep{background:repeating-linear-gradient(135deg,var(--rc) 0 2px,
color-mix(in srgb,var(--rc) 45%,var(--panel)) 2px 4px)}.rk{--rc:var(--muted)}
.key{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:11.5px;color:var(--muted);margin:2px 0 8px}
.key span{display:inline-flex;align-items:center;gap:5px}.key i{width:10px;height:10px;border-radius:3px;display:inline-block}
.tbl{overflow-x:auto;margin:0 -4px}
.tbl table{border-collapse:collapse;width:100%;font-size:12.5px}
.tbl th,.tbl td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
.tbl th{font-size:11px;font-weight:600;color:var(--muted);white-space:nowrap}.tbl th[title]{cursor:help}
.tbl th.grp{text-align:center;border-bottom:2px solid var(--line);color:var(--text);text-transform:uppercase;
letter-spacing:.06em;font-size:10.5px}
.tbl tr:last-child td{border-bottom:0}.tbl tbody tr:hover{background:var(--panel2)}
.tbl .num{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:nowrap}
.tbl th.num{font-family:inherit}.tbl .z{color:var(--muted)}.tbl .num.warn{color:var(--warn);font-weight:700}
.tbl .vz{width:26%;min-width:110px}.tbl .mods{color:var(--muted);font-size:12px}.tbl code{white-space:nowrap}
.tbl .id{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
"""
CSS += """
.tm{position:relative;height:14px;margin:4px 0 2px}
.tm .tr{position:absolute;left:0;right:0;top:5px;height:4px;border-radius:2px;background:var(--panel2);
box-shadow:inset 0 0 0 1px var(--mtrack)}
.tm .md{position:absolute;left:0;top:3px;height:8px;border-radius:4px;background:var(--m2)}
.tm .p9{position:absolute;top:0;width:3px;height:14px;transform:translateX(-50%);border-radius:2px;background:var(--m1)}
.scale{display:flex;justify-content:space-between;font:11px ui-monospace,SFMono-Regular,Menlo,monospace;
color:var(--muted);border-top:1px dashed var(--line);padding-top:3px;margin-top:4px}
.att{list-style:none;margin:0;padding:0}.att li{display:grid;grid-template-columns:62px minmax(0,1fr) auto;gap:2px 10px;
align-items:baseline;padding:5px 0;border-top:1px solid var(--line);font-size:12.5px}.att li:first-child{border-top:0}
.att .id{color:var(--indigo);font:600 12px/24px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}
.att .id:hover{text-decoration:underline}
.att .ttl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.att .who{grid-column:2/3;display:flex;gap:4px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:12px}
.att .age{grid-row:1/3;grid-column:3;color:var(--muted);font-size:12px;white-space:nowrap}
.agrp{margin-top:6px}.agrp>h3{margin:8px 0 2px;font-size:12px;display:flex;gap:8px;align-items:baseline}
.agrp>h3 .n{font:700 11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.agrp.bad>h3{color:var(--bad)}.agrp.warn>h3{color:var(--warn)}
.agrp details>summary{cursor:pointer;color:var(--muted);font-size:12px;padding:4px 0;min-height:24px}
.cols{display:flex;align-items:flex-end;gap:10px;overflow-x:auto;padding:4px 2px 0}
.sp{flex:0 0 auto;min-width:44px;display:flex;flex-direction:column;align-items:center;gap:3px}
.sp .n{font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.sp .col2{width:26px;height:96px;display:flex;align-items:flex-end;background:var(--panel2);border-radius:5px;
overflow:hidden;box-shadow:inset 0 0 0 1px var(--mtrack)}
.sp .tot{width:100%;display:flex;align-items:flex-end;background:var(--m2)}.sp .cl{width:100%;background:var(--m1)}
.sp .nm{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;max-width:64px;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}.sp.cur .nm{color:var(--text);font-weight:700;text-decoration:underline;text-underline-offset:3px}
.trend{display:grid;grid-template-columns:auto minmax(0,560px);gap:8px 36px;align-items:end;margin-bottom:8px}
.trend>div{min-width:0}
.tline{position:relative;height:120px;margin:16px 0 0 34px}
.tline svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.tline .g{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}.tline .g.top{stroke-dasharray:3 3}
.tline polyline{fill:none;stroke-width:2;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.tline .fa{stroke:var(--m2)}.tline .cz{stroke:var(--m1)}
.tline .yl{position:absolute;left:-34px;width:30px;text-align:right;transform:translateY(-50%);
font:10.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.tline .pt{position:absolute;width:8px;height:8px;border-radius:50%;transform:translate(-50%,-50%);
border:2px solid var(--panel)}.tline .pt.fa{background:var(--m2)}.tline .pt.cz{background:var(--m1)}
.tline .pv{position:absolute;transform:translate(-50%,-150%);font:600 10.5px ui-monospace,SFMono-Regular,Menlo,monospace;
white-space:nowrap}.tline .pv.fa{color:var(--muted);transform:translate(-50%,40%)}
.xl{position:relative;height:30px;margin-left:34px}.xl span{position:absolute;transform:translateX(-50%);
text-align:center;font:11px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}
.xl small{display:block;color:var(--muted);font-size:10px}
.sk-fa{background:var(--m2)}.sk-cz{background:var(--m1)}
.defs dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px 14px;margin:4px 0 0;font-size:12.5px}
.defs dt{font-weight:650}.defs dd{margin:0;color:var(--muted)}
@media (max-width:640px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi .v{font-size:20px}
.pnl{padding:10px 10px 12px}.trend{grid-template-columns:minmax(0,1fr)}
.tbl th:first-child,.tbl td:first-child{position:sticky;left:0;background:var(--panel);z-index:1}
.tbl .vz{display:none}.defs dl{grid-template-columns:minmax(0,1fr)}.defs dd{margin-bottom:4px}}
"""

PLURAL = {"Q": "questions", "B": "blockers", "H": "hand-offs", "C": "contracts", "D": "decisions"}
CAP_IDS = 12
CAP_ATTENTION = 5


def pct(value: float, top: float) -> float:
    """A share of `top` as a CSS percentage; a non-zero value stays visible."""
    if not top or not value:
        return 0.0
    return min(100.0, max(2.0, round(100 * value / top, 1)))


def hrs(stat: dict) -> str:
    return "—" if not stat["n"] else f"{stat['median']}h"


def bar(parts: list[tuple[str, float, str]], top: float, label: str) -> str:
    """A horizontal stacked bar: (css class, value, tooltip) per segment, scaled to `top`.

    Each non-zero segment is at least 2% wide; the widths are then scaled so they never sum past 100%."""
    shown = [(c, pct(v, top), tip) for c, v, tip in parts if v]
    total = sum(w for _, w, _ in shown)
    if total > 100:
        shown = [(c, round(w * 100 / total, 2), tip) for c, w, tip in shown]
    segs = "".join(f'<i class="{c}" style="width:{w}%" title="{esc(tip)}"></i>' for c, w, tip in shown)
    return f'<div class="bar" role="img" aria-label="{esc(label)}">{segs}</div>'


def key(items: list[tuple[str, str]]) -> str:
    """A legend; an item with no class is plain text, with no swatch."""
    out = []
    for c, t in items:
        swatch = f'<i class="{c}"></i>' if c else ""
        out.append(f"<span>{swatch}{esc(t)}</span>")
    return '<div class="key">' + "".join(out) + "</div>"


def link(entry_id: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f'<a{attr} href="/e/{esc(entry_id)}">{esc(entry_id)}</a>'


def ids(values: list[str], cap: int = CAP_IDS) -> str:
    """Linked ids; past `cap` the rest fold into a native <details>."""
    if not values:
        return "none"
    rest = values[cap:]
    more = (f'<details><summary>+{len(rest)} more</summary>{"".join(map(link, rest))}</details>') if rest else ""
    return f'<span class="ids">{"".join(map(link, values[:cap]))}{more}</span>'


def table(headers: list[tuple[str, str, str]], rows: list[list[tuple[str, str]]], groups: str = "") -> str:
    """Headers are (css class, label, definition); cells are (css class, html) with the html already escaped.

    `groups` is an optional first header row (trusted HTML) that groups the columns."""
    head = "".join(f'<th class="{c}" scope="col"' + (f' title="{esc(d)}"' if d else "") + f">{esc(h)}</th>"
                   for c, h, d in headers)
    body = "".join("<tr>" + "".join(f'<td class="{c}">{v}</td>' for c, v in r) + "</tr>" for r in rows)
    return (f'<div class="tbl"><table><thead>{groups}<tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def num(value, tone: str = "") -> tuple[str, str]:
    return ("num z" if value in (0, "—") else f"num {tone}".strip(), esc(value))


def panel(title: str, hint: str, body: str, anchor: str = "") -> str:
    attr = f' id="{anchor}"' if anchor else ""
    return f'<section class="pnl"{attr}><h2>{esc(title)}</h2><p class="hint">{esc(hint)}</p>{body}</section>'


def hrow(label: str, value, sub: str = "", viz: str = "", tone: str = "", define: str = "") -> str:
    """One labelled number in a panel; `sub` and `viz` are trusted HTML."""
    tip = f' title="{esc(define)}"' if define else ""
    return (f'<div class="hrow"><span class="l"{tip}>{esc(label)}</span><span class="v {tone}">{esc(value)}</span>'
            + (f'<div class="viz">{viz}</div>' if viz else "") + (f'<span class="s">{sub}</span>' if sub else "")
            + "</div>")


def defs(stale_h: str) -> dict[str, str]:
    return {
        "owes": "Open questions and blockers addressed to this role that it has not answered yet.",
        "hold": "Held for: from a hand-off this role received to its own next hand-off (median).",
        "pickup": "Picked up in: from a hand-off this role received to its first event after it (median).",
        "stale": f"An open thread with no reply, close or new entry for {stale_h}. Decisions count; contracts "
                 "count as quiet instead.",
        "quiet": f"An open contract nobody has replied to or cited for {stale_h}. Still in force? Supersede or close it.",
        "cited": "Threads by other roles that cite a hand-off this role sent. Any citation counts, not only rework.",
        "fixed": "Hand-offs this role sent that a later hand-off names with --fixes: a fix round found after "
                 "the receiver judged it. Accepted and rework stay the receiver's own verdict.",
        "idle": f"An open question or blocker with no answer whose every named role shows DONE (or has no status "
                f"row) and has written nothing for {stale_h}: no agent is running to answer it. Answer, reassign "
                "or close it.",
        "refused": "Posts and hand-offs baton refused, from this checkout's local log, not the shared board.",
        "unread": "Events after each role's read cursor. Cursors live in this checkout, so other checkouts differ.",
        "tokens": "About 4 characters per token: roughly what an agent spends to read that text.",
        "p90": "p90: the slowest 10% took at least this long.",
    }


def kpis(m: dict, att: dict[str, list[dict]]) -> str:
    s = m["summary"]
    fa, rate, empty = s["hours_to_first_answer"], s["close_rate"], not s["entries"]
    blockers = len(att["blocked"])

    def jump(group: str) -> str:
        return f"#{group}" if att[group] else "#attention"

    def tone(bad: bool, kind: str) -> str:
        return "" if empty else kind if bad else "t-ok"
    tiles = [
        ("Open threads", s["open"], f'of {s["entries"]} threads', "", "#attention"),
        ("Blockers", blockers, "open B or blocking", tone(bool(blockers), "t-bad"), jump("blocked")),
        ("Unanswered Q/B", s["unanswered_open"], "open with no answer", tone(bool(s["unanswered_open"]), "t-warn"),
         jump("unanswered")),
        (f'Stale (≥{m["stale_hours"]:g}h)', s["stale_open"], "open threads gone idle",
         tone(bool(s["stale_open"]), "t-warn"), jump("stale")),
        ("Median first answer", f'{fa["median"]}h' if fa["n"] else "—",
         f'p90 {fa["p90"]}h · n={fa["n"]}' if fa["n"] else "no answers yet", "", "#times"),
        ("Close rate", f"{int(rate * 100)}%" if rate is not None else "—",
         f'{s["closed"]} of {s["entries"]} closed' if s["entries"] else "nothing posted yet",
         "t-ok" if rate is not None and rate >= 0.5 and not s["stale_open"] else "", "#health"),
    ]
    return '<div class="kpis">' + "".join(
        f'<a class="kpi {tn}" href="{href}"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
        f'<div class="s">{esc(sub)}</div></a>' for label, value, sub, tn, href in tiles) + "</div>"


def attention_item(view: Model, t: dict) -> str:
    to = [r for r in t["to"] if r != "all"] or list(t["to"])
    who = chip(view, t["from"]) + ' <span class="arr">→</span> ' + " ".join(chip(view, r) for r in to)
    idle = dur(view.hours(t))
    return (f'<li>{link(t["id"], "id")}<span class="ttl">{esc(title_of(t))}</span>'
            f'<span class="age">{"idle " + esc(idle) if idle else ""}</span><span class="who">{who}</span></li>')


def attention(view: Model, att: dict[str, list[dict]]) -> str:
    groups = (("blocked", "Blocked", "bad"), ("idle", "To an idle role", "warn"),
              ("unanswered", "Unanswered questions and blockers", "warn"), ("stale", "Stale", "warn"))
    if not any(att.values()):
        return panel("Needs attention", "open blockers, unanswered questions and stale threads in this scope",
                     '<div class="empty">Nothing is blocked, unanswered or stale.</div>', "attention")
    out, shown = [], set()
    for key_, name, tn in groups:
        if not att[key_]:
            continue
        # A thread is listed once, in its most urgent group; the count still matches the KPI tile.
        items = [t for t in att[key_] if t["id"] not in shown]
        shown.update(t["id"] for t in items)
        above = len(att[key_]) - len(items)
        note = f'<span class="muted"> · {above} listed above</span>' if above else ""
        first = "".join(attention_item(view, t) for t in items[:CAP_ATTENTION])
        rest = items[CAP_ATTENTION:]
        more = (f'<details><summary>+{len(rest)} more</summary><ul class="att">'
                f'{"".join(attention_item(view, t) for t in rest)}</ul></details>') if rest else ""
        listed = f'<ul class="att">{first}</ul>' if first else ""
        out.append(f'<div class="agrp {tn}" id="{key_}"><h3>{esc(name)}<span class="n">{len(att[key_])}</span>'
                   f'{note}</h3>{listed}{more}</div>')
    return panel("Needs attention", "open blockers, unanswered questions and stale threads in this scope, "
                 "longest idle first", "".join(out), "attention")


def times(m: dict, d: dict) -> str:
    """Median and p90 of answer and close time, on one shared, labelled scale."""
    s = m["summary"]
    rows = [("Time to first answer (median)", s["hours_to_first_answer"]),
            ("Time to close (median)", s["hours_to_close"])]
    top = max((x["p90"] or 0 for _, x in rows if x["n"]), default=0)
    out = []
    for label, x in rows:
        if not x["n"]:
            out.append(hrow(label, "—", "no data yet"))
            continue
        tip = f'median {x["median"]}h, p90 {x["p90"]}h'
        chart = (f'<div class="tm" role="img" aria-label="{esc(tip)}"><span class="tr"></span>'
                 f'<span class="md" style="width:{pct(x["median"], top)}%"></span>'
                 f'<span class="p9" style="left:{min(99.5, pct(x["p90"], top))}%"></span></div>')
        out.append(hrow(label, f'{x["median"]}h', esc(f'p90 {x["p90"]}h · n={x["n"]}'), chart, define=d["p90"]))
    data = any(x["n"] for _, x in rows)
    legend = key([("sk-fa", "median"), ("s-m1", "p90 (slowest 10%)")]) if data else ""
    scale = f'<div class="scale"><span>0h</span><span>{esc(f"{top:g}")}h</span></div>' if data else ""
    return panel("Response times", "hours from a post to its first answer by someone else, and to its close",
                 legend + f'<div class="rows">{"".join(out)}</div>' + scale, "times")


def health(m: dict, view: Model, d: dict) -> str:
    s, rf = m["summary"], m["summary"]["refusals"]
    roles = list(m["roles"].values())
    stale_h = f'{m["stale_hours"]:g}h'
    kinds = ", ".join(f'{PLURAL.get(k) or view.kinds.get(k) or k} {v}' for k, v in
                      sorted(s["by_kind"].items(), key=lambda kv: -kv[1]))
    asks, empty = s["questions_and_blockers"], not s["entries"]
    closed = bar([("s-m1", s["closed"], f'{s["closed"]} closed')], s["entries"],
                 f'{s["closed"]} of {s["entries"]} closed') if s["entries"] else ""
    answered = bar([("s-m1", s["answered"], f'{s["answered"]} answered')], asks,
                   f'{s["answered"]} of {asks} answered') if asks else ""
    calm = "" if empty else "ok"
    out = [
        hrow("Closed of opened", f'{s["closed"]} / {s["entries"]}', "" if s["entries"] else "nothing posted yet",
             closed),
        hrow("Threads by kind", s["entries"], esc(kinds) if kinds else "none yet"),
        hrow("Questions answered", f'{s["answered"]} / {asks}', esc(f'{s["unanswered_open"]} open with no answer'),
             answered, "warn" if s["unanswered_open"] else ""),
        hrow(f"Stale (idle ≥ {stale_h})", s["stale_open"], ids(s["stale_ids"]), "",
             "warn" if s["stale_open"] else calm, d["stale"]),
        hrow(f"Quiet contracts (≥ {stale_h})", s["quiet_contracts"], ids(s["quiet_contract_ids"]), "",
             "warn" if s["quiet_contracts"] else calm, d["quiet"]),
        hrow("Refused writes (this checkout)", rf["refused"],
             esc(f'{rf["resolved_by_answering"]} of {rf["handoffs_on_open_questions"]} hand-offs refused on an open '
                 f'question were resolved by answering it; {rf["overridden"]} forced'), define=d["refused"]),
        hrow("Unread now (all roles)", sum(x["unread"] for x in roles),
             esc(f'~{sum(x["unread_tokens"] for x in roles)} tokens to read · read cursors in this checkout'),
             define=d["unread"]),
    ]
    return panel("Board health", "closes, kinds, answers, idle work and refused writes",
                 f'<div class="rows">{"".join(out)}</div>', "health")


FIRST_STEP = ('<div class="empty">Nothing on the board yet. Start with <code>baton post Q --to backend '
              '--title "…"</code> or <code>baton handoff</code>; these panels fill in as roles post.</div>')


def by_role(m: dict, view: Model, d: dict) -> str:
    roles = m["roles"]
    hint = "who owes answers, who holds open work, who posts; bars in each role's colour"
    if not roles:
        return panel("By role", hint, '<div class="empty">No roles yet. Add them with <code>baton init --roles'
                     "</code>.</div>")
    if not m["summary"]["entries"] and not any(x["replies"] or x["unread"] for x in roles.values()):
        return panel("By role", hint, '<div class="empty">No activity yet: '
                     + " ".join(chip(view, r) for r in roles) + "</div>")
    top = max(x["posted"] + x["replies"] for x in roles.values())
    rows = []
    for r, x in roles.items():
        load = (f'<div class="{view.rc(r)}">' + bar([("s-own", x["posted"], f'{x["posted"]} posted'),
                                                      ("s-rep", x["replies"], f'{x["replies"]} replies')],
                                                     top, f'{r}: {x["posted"]} posted, {x["replies"]} replies')
                + "</div>") if top else '<span class="muted">no activity</span>'
        asked = f'{x["answered"]}/{x["asked_of"]}' if x["asked_of"] else "—"
        rows.append([("", chip(view, r)), num(x["waiting_on"], "warn"), num(x["open_owned"]), ("vz", load),
                     num(x["posted"]), num(x["replies"]), num(asked), num(hrs(x["hours_to_answer"])),
                     num(f'{x["unread"]} (~{x["unread_tokens"]})')])
    heads = [("", "Role", ""), ("num", "Owes answers", d["owes"]), ("num", "Open owned", "Open threads it posted."),
             ("vz", "Activity", "Posted (solid) and replies (striped)."), ("num", "Posted", ""),
             ("num", "Replies", ""), ("num", "Answered", "Answered of the questions and blockers addressed to it."),
             ("num", "Median answer", ""), ("num", "Unread (~tokens)", d["unread"] + " " + d["tokens"])]
    legend = key([("s-own rk", "posted"), ("s-rep rk", "replies")]) if top else ""
    return panel("By role", hint, legend + table(heads, rows))


def handoffs(m: dict, view: Model, d: dict) -> str:
    roles = m["roles"]
    hint = "as sender: how receivers judged its hand-offs · as receiver: how long it took to pick up and pass on"
    if not any(x["handoffs_sent"] or x["bounced"] or x["refused"] or x["forced"] or x["hours_held"]["n"]
               or x["hours_to_pickup"]["n"] for x in roles.values()):
        return panel("Hand-offs by role", hint, '<div class="empty">No hand-offs yet. A role passes work on with '
                     "<code>baton handoff</code>.</div>")
    top = max(x["handoffs_sent"] for x in roles.values())
    rows = []
    for r, x in roles.items():
        open_ = max(0, x["handoffs_sent"] - x["accepted"] - x["rework"])
        parts = [("s-acc", x["accepted"], f'{x["accepted"]} accepted'), ("s-rew", x["rework"], f'{x["rework"]} rework'),
                 ("s-und", open_, f"{open_} not judged yet")]
        viz = (bar(parts, top, f'{r}: ' + ", ".join(t for _, _, t in parts)) if x["handoffs_sent"]
               else '<span class="muted">none sent</span>')
        rows.append([("", chip(view, r)), ("vz", viz), num(x["handoffs_sent"]), num(x["accepted"]), num(x["rework"]),
                     num(x.get("fixed_later", 0), "t-warn" if x.get("fixed_later") else ""), num(x["bounced"]),
                     num(x["refused"]), num(x["forced"]), num(hrs(x["hours_held"])), num(hrs(x["hours_to_pickup"]))])
    heads = [("", "Role", ""), ("vz", "Outcomes", "Sent hand-offs: accepted, rework, not judged yet."),
             ("num", "Sent", ""), ("num", "Accepted", ""), ("num", "Rework", ""), ("num", "Fixed later", d["fixed"]),
             ("num", "Cited later", d["cited"]),
             ("num", "Refused", d["refused"]), ("num", "Forced", "Hand-offs pushed through with --force."),
             ("num", "Median hold", d["hold"]), ("num", "Median pickup", d["pickup"])]
    groups = ('<tr><td></td><td class="vz"></td><th class="grp" scope="colgroup" colspan="7">As sender</th>'
              '<th class="grp" scope="colgroup" colspan="2">As receiver</th></tr>')
    legend = key([("s-acc", "accepted"), ("s-rew", "rework"), ("s-und", "not judged yet")]) if top else ""
    return panel("Hand-offs by role", hint, legend + table(heads, rows, groups) + dispatch_note(m))


def dispatch_note(m: dict) -> str:
    d = m.get("dispatch") or {}
    if not d.get("off_board"):
        return ""
    return ('<p class="muted dispatch">Builders hand work to the orchestrator, but it has posted no hand-off to '
            f'them in {esc(d["sprint"])}: they seem to be briefed outside the board. Posting '
            "<code>baton handoff --as orchestrator --to &lt;role&gt;</code> at dispatch fills To pick up and "
            "In progress.</p>")


SERIES = (("fa", "hours_to_first_answer", "median first answer"), ("cz", "hours_to_close", "median close"))


def trend(sprints: dict) -> str:
    """Median first answer and median close per sprint, with points, values, a 0h and a top gridline and sprint
    names under each point; drawn once two sprints have a value. A sprint with no median leaves a gap."""
    names = list(sprints)
    series = {c: [sprints[s][k]["median"] if sprints[s][k]["n"] else None for s in names] for c, k, _ in SERIES}
    drawn = {c: vs for c, vs in series.items() if sum(v is not None for v in vs) >= 2}
    if len(names) < 2 or not drawn:
        return ""
    top = max(v for vs in drawn.values() for v in vs if v is not None) or 1

    def x(i):
        return round(6 + 88 * i / (len(names) - 1), 2)

    def y(v):
        return round(90 - 78 * v / top, 2)
    lines, marks = [], []
    for c, vs in drawn.items():
        pts = [(x(i), y(v), v) for i, v in enumerate(vs) if v is not None]
        lines.append(f'<polyline class="{c}" points="{" ".join(f"{a},{b}" for a, b, _ in pts)}"/>')
        marks += [f'<span class="pt {c}" style="left:{a}%;top:{b}%"></span>'
                  f'<span class="pv {c}" style="left:{a}%;top:{b}%">{esc(f"{v:g}")}h</span>' for a, b, v in pts]
    label = "; ".join(f"{name}: " + ", ".join(f"{n} {series[c][i]}h" for c, _, n in SERIES if series[c][i] is not None)
                      for i, name in enumerate(names))
    xl = "".join(f'<span style="left:{x(i)}%">{esc(name)}<small>n={sprints[name]["hours_to_close"]["n"]}</small></span>'
                 for i, name in enumerate(names))
    return (f'<div class="tline" role="img" aria-label="{esc(label)}"><svg viewBox="0 0 100 100" '
            'preserveAspectRatio="none" aria-hidden="true"><line class="g top" x1="0" y1="12" x2="100" y2="12"/>'
            f'<line class="g" x1="0" y1="90" x2="100" y2="90"/>{"".join(lines)}</svg>'
            f'<span class="yl" style="top:12%">{esc(f"{top:g}")}h</span><span class="yl" style="top:90%">0h</span>'
            f'{"".join(marks)}</div><div class="xl">{xl}</div>'
            + key([(f"sk-{c}", n) for c, _, n in SERIES if c in drawn] + [("", "n = closes in the sprint")]))


def by_sprint(m: dict, current: str, d: dict) -> str:
    sprints = m["sprints"]
    hint = "every sprint, whatever the scope above: threads and closes, and how the median times move"
    if not sprints:
        return panel("By sprint", hint, '<div class="empty">No sprints yet.</div>')
    top = max(x["entries"] for x in sprints.values())
    cols = "".join(
        f'<div class="sp{" cur" if name == current else ""}" title="{esc(name)}: '
        f'{x["closed"]} of {x["entries"]} closed"><span class="n">{x["closed"]}/{x["entries"]}</span>'
        f'<span class="col2"><span class="tot" style="height:{pct(x["entries"], top)}%">'
        f'<span class="cl" style="height:{pct(x["closed"], x["entries"])}%"></span></span></span>'
        f'<span class="nm">{esc(name)}</span></div>' for name, x in sprints.items())
    chart = (f'<div class="cols" role="img" aria-label="closed of threads per sprint">{cols}</div>'
             + key([("s-m1", "closed"), ("s-m2", "threads"), ("", "current sprint underlined")]))
    rows = [[("id", esc(name)), num(x["entries"]), num(x["open"]), num(x["closed"]), num(x["answered"]),
             num(hrs(x["hours_to_first_answer"])), num(hrs(x["hours_to_close"])), num(x["stale_open"]),
             num(f'~{x["tokens"]}')] for name, x in sprints.items()]
    heads = [("", "Sprint", ""), ("num", "Threads", ""), ("num", "Open", ""), ("num", "Closed", ""),
             ("num", "Answered", ""), ("num", "Median 1st answer", ""), ("num", "Median close", ""),
             ("num", "Stale", d["stale"]), ("num", "~Tokens", "Size of the sprint's entries. " + d["tokens"])]
    return panel("By sprint", hint, f'<div class="trend"><div>{chart}</div><div>{trend(sprints)}</div></div>'
                 + table(heads, rows))


def by_model(m: dict, view: Model) -> str:
    models = sorted(m["models"].items(), key=lambda kv: -kv[1]["events"])
    hint = "events written per model, how its hand-offs were judged, and which role wrote with which model"
    if not models:
        return panel("By model", hint, '<div class="empty">No events yet. Each entry records the model that wrote '
                     "it (<code>--model</code> or <code>$BATON_MODEL</code>).</div>")
    top = max(x["events"] for _, x in models)
    rows = [[("mods", f"<code>{esc(k)}</code>"),
             ("vz", bar([("s-m1", x["events"], f'{x["events"]} events')], top, f'{k}: {x["events"]} events')),
             num(x["events"]), num(x["handoffs"]), num(x["accepted"]), num(x["rework"])] for k, x in models]
    heads = [("", "Model", ""), ("vz", "Share", "Events, relative to the busiest model."), ("num", "Events", ""),
             ("num", "Hand-offs", ""), ("num", "Accepted", ""), ("num", "Rework", "")]
    per_role = [[("", chip(view, r)), ("mods", esc(", ".join(
        f"{k} {v}" for k, v in sorted(x["models"].items(), key=lambda kv: -kv[1]))))]
        for r, x in m["roles"].items() if x["models"]]
    roles = table([("", "Role", ""), ("", "Events by model", "Every event the role wrote, by model.")], per_role) \
        if per_role else ""
    return panel("By model", hint, table(heads, rows) + roles)


def glossary(d: dict) -> str:
    terms = [("Owes answers", d["owes"]), ("Stale", d["stale"]), ("Quiet contract", d["quiet"]),
             ("To an idle role", d["idle"]), ("Fixed later", d["fixed"]), ("Cited later", d["cited"]), ("Median hold", d["hold"]), ("Median pickup", d["pickup"]),
             ("Refused writes", d["refused"]), ("Unread", d["unread"]), ("~tokens", d["tokens"]), ("p90", d["p90"])]
    body = "".join(f"<dt>{esc(t)}</dt><dd>{esc(x)}</dd>" for t, x in terms)
    return panel("How to read this", "times are hours between events; every number is also in baton metrics",
                 f'<div class="defs"><dl>{body}</dl></div>', "defs")


def pick_scope(view: Model, known: list[str], wanted: str | None) -> str | None:
    """The sprint to show: `?sprint=all` is every sprint, a known sprint is itself, anything else is the current
    sprint. A sandbox keeps every sprint: its scope is the task, not a sprint."""
    if view.sandbox or wanted == "all":
        return None
    return wanted if wanted in known else view.sprint


def scope_row(view: Model, known: list[str], scope: str | None) -> str:
    if view.sandbox:
        return ""
    opts = [(view.sprint, f"This sprint ({view.sprint})"), ("all", "All sprints")]
    opts += [(s, s) for s in reversed(known) if s != view.sprint]
    current = scope or "all"
    links = "".join(f'<a href="/metrics?sprint={quote(v, safe="")}"'
                    + (' aria-current="true"' if v == current else "") + f">{esc(label)}</a>" for v, label in opts)
    return f'<nav class="seg" aria-label="Scope">{links}</nav>'


def attention_lists(board: Board, view: Model, m: dict, scope: str | None) -> dict[str, list[dict]]:
    open_ = [t for t in board.entries().values() if t["status"] == "OPEN" and (scope is None or t["sprint"] == scope)]
    open_.sort(key=lambda t: -(view.hours(t) or 0))
    stale = set(m["summary"]["stale_ids"])
    idle = {x["id"] for x in m["summary"].get("idle_addressees") or []}
    return {"blocked": [t for t in open_ if t["kind"] == "B" or t.get("blocks")],
            "idle": [t for t in open_ if t["id"] in idle],
            "unanswered": [t for t in open_ if t["kind"] in ("Q", "B") and not metrics.first_answer(t)],
            "stale": [t for t in open_ if t["id"] in stale]}


FOOT = "numbers from <code>baton metrics</code> · also at <code>/api/metrics.json</code> · times are hours between events"


def metrics_page(board: Board, now: datetime | None = None, sprint: str | None = None) -> str:
    now = now or datetime.now()
    view = Model(board, now)
    every = metrics.compute(board, now=now)
    known = list(every["sprints"])
    scope = pick_scope(view, known, sprint)
    m = every if scope is None else metrics.compute(board, sprint=scope, now=now)
    label = "all sprints" if scope is None else f"sprint {scope}"
    d = defs(f'{m["stale_hours"]:g}h')
    att = attention_lists(board, view, m, scope)
    head = (f'<div class="mhd"><h2>Metrics · {esc(label)}</h2>{scope_row(view, known, scope)}'
            f'<span class="hint">stale after {m["stale_hours"]:g}h</span></div>')
    start = "" if every["summary"]["entries"] else f'<section class="pnl">{FIRST_STEP}</section>'
    body = (head + kpis(m, att) + '<div class="mstack">' + start + attention(view, att) + by_role(m, view, d)
            + handoffs(m, view, d) + f'<div class="pair">{times(m, d)}{health(m, view, d)}</div>'
            + by_sprint(every, view.sprint, d) + by_model(m, view) + glossary(d) + "</div>")
    pill = scope_of(board.cfg) + ("" if view.sandbox else f" · showing <b>{esc(label)}</b>")
    return shell(board.root.name, pill, now, body, f"metrics · {board.root.name}", "metrics", FOOT, CSS)
