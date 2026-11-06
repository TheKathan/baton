"""The `/metrics` page of `baton serve`: board health as a dashboard, in the board's shell and colours.

Every number comes from `metrics.compute()`. Charts are inline SVG or CSS widths, so the page needs no
script under the dashboard's CSP. Standard library only.
"""

from __future__ import annotations

from datetime import datetime

from . import metrics
from .boardview import Model, chip, document, esc
from .store import Board

CSS = """
.mhd{display:flex;align-items:baseline;gap:10px;margin:16px 0 10px;flex-wrap:wrap}
.mhd h2{margin:0;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.mhd .hint{font-size:12px;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--kc,var(--line));
border-radius:10px;padding:9px 12px 10px;min-width:0}
.kpi .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.kpi .v{font:700 24px/1.2 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin-top:2px}
.kpi .s{font-size:11.5px;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.t-ok{--kc:var(--ok)}.t-warn{--kc:var(--warn)}.t-bad{--kc:var(--bad)}
.t-warn .v{color:var(--warn)}.t-bad .v{color:var(--bad)}
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:12px;margin-top:12px}
.pnl{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px 12px;min-width:0}
.pnl.wide{grid-column:1/-1}
.pnl>h2{margin:0 0 2px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.pnl>.hint{margin:0 0 8px;font-size:12px;color:var(--muted)}
.empty{font-size:12.5px;color:var(--muted);padding:6px 0}
.hrow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;padding:7px 0;border-top:1px solid var(--line)}
.hrow:first-of-type{border-top:0}.hrow .l{font-size:12.5px;font-weight:600}
.hrow .v{font:700 13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;text-align:right;white-space:nowrap}
.hrow .v.warn{color:var(--warn)}.hrow .v.ok{color:var(--ok)}
.hrow .s{grid-column:1/3;font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.hrow .viz{grid-column:1/3;margin-top:3px}
.ids a{color:var(--indigo);font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;margin-right:6px}
.ids a:hover{text-decoration:underline}
.bar{display:flex;height:10px;border-radius:999px;background:var(--panel2);overflow:hidden;min-width:60px}
.bar i{display:block;height:100%;flex:0 0 auto}.bar i+i{border-left:1px solid var(--panel)}
.s-acc{background:var(--ok)}.s-rew{background:var(--bad)}.s-bnc{background:var(--warn)}
.s-und{background:color-mix(in srgb,var(--muted) 45%,transparent)}
.s-Q{background:var(--warn)}.s-B{background:var(--bad)}.s-H{background:var(--orange)}.s-C{background:var(--indigo)}
.s-D{background:var(--r2)}.s-x{background:var(--r9)}.s-ans{background:var(--ok)}
.s-own{background:var(--rc)}.s-rep{background:color-mix(in srgb,var(--rc) 40%,transparent)}
.s-ev{background:var(--indigo)}.s-tot{background:color-mix(in srgb,var(--indigo) 30%,transparent)}.rk{--rc:var(--muted)}
.key{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:11.5px;color:var(--muted);margin:2px 0 8px}
.key span{display:inline-flex;align-items:center;gap:5px}.key i{width:9px;height:9px;border-radius:3px;display:inline-block}
.tbl{overflow-x:auto;margin:0 -4px}
.tbl table{border-collapse:collapse;width:100%;font-size:12.5px}
.tbl th,.tbl td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
.tbl th{font-size:11px;font-weight:600;color:var(--muted);white-space:nowrap}
.tbl tr:last-child td{border-bottom:0}.tbl tbody tr:hover{background:var(--panel2)}
.tbl .num{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:nowrap}
.tbl .z{color:var(--muted)}.tbl .vz{width:28%;min-width:110px}.tbl .mods{color:var(--muted);font-size:12px}
.tm{position:relative;height:14px;margin:4px 0 2px}
.tm .tr{position:absolute;left:0;right:0;top:5px;height:4px;border-radius:2px;background:var(--panel2)}
.tm .md{position:absolute;left:0;top:3px;height:8px;border-radius:4px;background:var(--indigo)}
.tm .p9{position:absolute;top:0;width:3px;height:14px;margin-left:-1px;border-radius:2px;background:var(--orange)}
.cols{display:flex;align-items:flex-end;gap:10px;overflow-x:auto;padding:4px 2px 0}
.sp{flex:0 0 auto;min-width:44px;display:flex;flex-direction:column;align-items:center;gap:3px}
.sp .n{font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
.sp .col2{width:26px;height:96px;display:flex;align-items:flex-end;background:var(--panel2);border-radius:5px;overflow:hidden}
.sp .tot{width:100%;display:flex;align-items:flex-end;background:color-mix(in srgb,var(--indigo) 30%,transparent)}
.sp .cl{width:100%;background:var(--ok)}
.sp .nm{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;max-width:64px;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}.sp.cur .nm{color:var(--orange);font-weight:700}
.trend{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 28px;align-items:end;margin-bottom:6px}
.trend>div{min-width:0}.spark{display:block;width:100%;height:110px;margin:4px 0 2px}
@media (max-width:640px){.trend{grid-template-columns:minmax(0,1fr)}}
.spark .g{stroke:var(--line);stroke-width:1}.spark polyline{fill:none;stroke-width:2;stroke-linejoin:round;
stroke-linecap:round;vector-effect:non-scaling-stroke}.spark .fa{stroke:var(--indigo)}.spark .cz{stroke:var(--orange)}
.sk-fa{background:var(--indigo)}.sk-cz{background:var(--orange)}.sk-p9{background:var(--orange)}.sk-md{background:var(--indigo)}
@media (max-width:640px){.wrap{padding:0 12px}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi .v{font-size:20px}.pnl{padding:10px 10px 12px}}
"""


def pct(value: float, top: float) -> float:
    """A share of `top` as a CSS percentage; a non-zero value stays visible."""
    if not top or not value:
        return 0.0
    return max(2.0, round(100 * value / top, 1))


def hrs(stat: dict) -> str:
    return metrics._short(stat)


def bar(parts: list[tuple[str, float, str]], top: float, label: str) -> str:
    """A horizontal stacked bar: (css class, value, tooltip) per segment, scaled to `top`."""
    segs = "".join(f'<i class="{c}" style="width:{pct(v, top)}%" title="{esc(tip)}"></i>' for c, v, tip in parts if v)
    return f'<div class="bar" role="img" aria-label="{esc(label)}">{segs}</div>'


def key(items: list[tuple[str, str]]) -> str:
    return '<div class="key">' + "".join(f'<span><i class="{c}"></i>{esc(t)}</span>' for c, t in items) + "</div>"


def ids(values: list[str], cap: int = 12) -> str:
    links = "".join(f'<a href="/e/{esc(i)}">{esc(i)}</a>' for i in values[:cap])
    more = f' <span class="muted">+{len(values) - cap} more</span>' if len(values) > cap else ""
    return f'<span class="ids">{links}{more}</span>' if values else "none"


def table(headers: list[tuple[str, str]], rows: list[list[tuple[str, str]]]) -> str:
    """Headers and cells are (css class, html); cell html is already escaped."""
    head = "".join(f'<th class="{c}" scope="col">{esc(h)}</th>' for c, h in headers)
    body = "".join("<tr>" + "".join(f'<td class="{c}">{v}</td>' for c, v in r) + "</tr>" for r in rows)
    return f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def num(value, zero_dim: bool = True) -> tuple[str, str]:
    return ("num z" if zero_dim and value in (0, "—") else "num", esc(value))


def panel(title: str, hint: str, body: str, wide: bool = False) -> str:
    return (f'<section class="pnl{" wide" if wide else ""}"><h2>{esc(title)}</h2>'
            f'<p class="hint">{esc(hint)}</p>{body}</section>')


def kpis(m: dict, blockers: int) -> str:
    s = m["summary"]
    fa = s["hours_to_first_answer"]
    rate = s["close_rate"]
    tiles = [
        ("Open threads", s["open"], f'of {s["entries"]} threads', ""),
        ("Blockers", blockers, "open B or blocking", "t-bad" if blockers else "t-ok"),
        ("Unanswered Q/B", s["unanswered_open"], "open with no answer", "t-warn" if s["unanswered_open"] else "t-ok"),
        (f'Stale (≥{m["stale_hours"]:g}h)', s["stale_open"], "open threads gone idle",
         "t-warn" if s["stale_open"] else "t-ok"),
        ("Median first answer", f'{fa["median"]}h' if fa["n"] else "—",
         f'p90 {fa["p90"]}h · n={fa["n"]}' if fa["n"] else "no answers yet", ""),
        ("Close rate", f"{int(rate * 100)}%" if rate is not None else "—",
         f'{s["closed"]} of {s["entries"]} closed' if s["entries"] else "nothing posted yet",
         "" if rate is None else "t-ok" if rate >= 0.5 else "t-warn"),
    ]
    return '<div class="kpis">' + "".join(
        f'<div class="kpi {tone}"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
        f'<div class="s">{esc(sub)}</div></div>' for label, value, sub, tone in tiles) + "</div>"


def hrow(label: str, value, sub: str = "", viz: str = "", tone: str = "") -> str:
    """One labelled number in a panel; `sub` and `viz` are trusted HTML."""
    return (f'<div class="hrow"><span class="l">{esc(label)}</span><span class="v {tone}">{esc(value)}</span>'
            + (f'<div class="viz">{viz}</div>' if viz else "") + (f'<span class="s">{sub}</span>' if sub else "")
            + "</div>")


def times(m: dict) -> str:
    """Median and p90 of answer and close time, on one shared scale."""
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
                 f'<span class="p9" style="left:{pct(x["p90"], top)}%"></span></div>')
        out.append(hrow(label, f'{x["median"]}h', esc(f'p90 {x["p90"]}h · n={x["n"]}'), chart))
    legend = key([("sk-md", "median"), ("sk-p9", "p90")]) if any(x["n"] for _, x in rows) else ""
    return panel("Response times", "hours from a post to its first answer by someone else, and to its close",
                 legend + "".join(out))


KINDS = ("Q", "B", "H", "C", "D")


def health(m: dict) -> str:
    s, rf = m["summary"], m["summary"]["refusals"]
    roles = list(m["roles"].values())
    kinds = s["by_kind"]
    seg = [(f"s-{k}" if k in KINDS else "s-x", v, f"{k} {v}") for k, v in kinds.items()]
    mix = (bar(seg, s["entries"], ", ".join(t for _, _, t in seg)) + key([(c, t) for c, _, t in seg])) if kinds else ""
    asks, stale_h = s["questions_and_blockers"], f'{m["stale_hours"]:g}h'
    answered = bar([("s-ans", s["answered"], f'{s["answered"]} answered')], asks,
                   f'{s["answered"]} of {asks} answered') if asks else ""
    out = [
        hrow("Opened / closed", f'{s["entries"]} / {s["closed"]}', "" if kinds else "nothing posted yet", mix),
        hrow("Questions answered", f'{s["answered"]} / {asks}', esc(f'{s["unanswered_open"]} open with no answer'),
             answered, "warn" if s["unanswered_open"] else ""),
        hrow(f"Stale (idle ≥ {stale_h})", s["stale_open"], ids(s["stale_ids"]), "",
             "warn" if s["stale_open"] else "ok"),
        hrow(f"Quiet contracts (≥ {stale_h})", s["quiet_contracts"], ids(s["quiet_contract_ids"]), "",
             "warn" if s["quiet_contracts"] else "ok"),
        hrow("Refused writes", rf["refused"],
             esc(f'{rf["resolved_by_answering"]} of {rf["handoffs_on_open_questions"]} hand-offs resolved by '
                 f'answering; {rf["overridden"]} forced')),
        hrow("Unread now (all roles)", sum(x["unread"] for x in roles),
             esc(f'~{sum(x["unread_tokens"] for x in roles)} tokens to read')),
    ]
    return panel("Board health", "threads by kind, answers, idle work and refused writes", "".join(out))


def role_cell(view: Model, role: str) -> tuple[str, str]:
    return ("", chip(view, role))


def by_role(m: dict, view: Model) -> str:
    roles = m["roles"]
    if not roles:
        return panel("By role", "load per role", '<div class="empty">No roles yet.</div>', wide=True)
    top = max(x["posted"] + x["replies"] for x in roles.values())
    rows = []
    for r, x in roles.items():
        load = (f'<span class="{view.rc(r)}">' + bar([("s-own", x["posted"], f'{x["posted"]} posted'),
                                                       ("s-rep", x["replies"], f'{x["replies"]} replies')],
                                                      top, f'{r}: {x["posted"]} posted, {x["replies"]} replies')
                + "</span>") if top else '<span class="muted">no activity</span>'
        rows.append([role_cell(view, r), ("vz", load), num(x["posted"]), num(x["replies"]),
                     num(f'{x["answered"]}/{x["asked_of"]}', False), num(hrs(x["hours_to_answer"])),
                     num(x["waiting_on"]), num(x["open_owned"]), num(f'{x["unread"]} (~{x["unread_tokens"]})', False)])
    heads = [("", "Role"), ("vz", "Activity"), ("num", "Posted"), ("num", "Replies"), ("num", "Answered"),
             ("num", "Median answer"), ("num", "Waiting on"), ("num", "Open owned"), ("num", "Unread (~tokens)")]
    legend = key([("s-own rk", "posted"), ("s-rep rk", "replies")]) if top else ""
    return panel("By role", "who posts, who answers, who is waited on; bars in each role's colour",
                 legend + table(heads, rows), wide=True)


def handoffs(m: dict, view: Model) -> str:
    roles = m["roles"]
    if not any(x["handoffs_sent"] or x["bounced"] or x["refused"] or x["forced"] or x["models"]
               for x in roles.values()):
        return panel("Hand-offs by role", "how receivers judged each role's hand-offs",
                     '<div class="empty">No hand-offs yet.</div>', wide=True)

    def parts(x):
        open_ = max(0, x["handoffs_sent"] - x["accepted"] - x["rework"])
        return [("s-acc", x["accepted"], f'{x["accepted"]} accepted'), ("s-rew", x["rework"], f'{x["rework"]} rework'),
                ("s-und", open_, f"{open_} not judged yet"), ("s-bnc", x["bounced"], f'{x["bounced"]} bounced back')]
    top = max(sum(v for _, v, _ in parts(x)) for x in roles.values())
    rows = []
    for r, x in roles.items():
        p = parts(x)
        viz = bar(p, top, f'{r}: ' + ", ".join(t for _, _, t in p)) if top else '<span class="muted">none sent</span>'
        models = ", ".join(f"{k} {v}" for k, v in sorted(x["models"].items(), key=lambda kv: -kv[1])) or "—"
        rows.append([role_cell(view, r), ("vz", viz), num(x["handoffs_sent"]), num(x["accepted"]), num(x["rework"]),
                     num(x["bounced"]), num(hrs(x["hours_held"])), num(hrs(x["hours_to_pickup"])),
                     num(x["refused"]), num(x["forced"]), ("mods", esc(models))])
    heads = [("", "Role"), ("vz", "Outcomes"), ("num", "Sent"), ("num", "Accepted"), ("num", "Rework"),
             ("num", "Bounced"), ("num", "Median hold"), ("num", "Median pickup"), ("num", "Refused"),
             ("num", "Forced"), ("", "Models")]
    legend = key([("s-acc", "accepted"), ("s-rew", "rework"), ("s-und", "not judged yet"),
                  ("s-bnc", "bounced back (cited by a later thread)")]) if top else ""
    return panel("Hand-offs by role", "how receivers judged each role's hand-offs; hold and pickup are medians",
                 legend + table(heads, rows), wide=True)


def spark(sprints: dict) -> str:
    """Median first answer and median close per sprint, as two lines; drawn once two sprints have a value."""
    names = list(sprints)
    series = {c: [sprints[s][k]["median"] if sprints[s][k]["n"] else None for s in names]
              for c, k in (("fa", "hours_to_first_answer"), ("cz", "hours_to_close"))}
    if len(names) < 2 or not any(sum(v is not None for v in vs) >= 2 for vs in series.values()):
        return ""
    top = max((v for vs in series.values() for v in vs if v is not None), default=0) or 1
    step = 100 / (len(names) - 1)
    lines = "".join(
        f'<polyline class="{c}" points="'
        + " ".join(f"{i * step:.1f},{38 - 34 * v / top:.1f}" for i, v in enumerate(vs) if v is not None) + '"/>'
        for c, vs in series.items() if sum(v is not None for v in vs) >= 2)
    label = f"median hours per sprint, {names[0]} to {names[-1]}; highest {top:g}h"
    return (f'<svg class="spark" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" '
            f'aria-label="{esc(label)}"><line class="g" x1="0" y1="38" x2="100" y2="38"/>{lines}</svg>'
            + key([("sk-fa", "median first answer"), ("sk-cz", "median close"), ("", f"top {top:g}h")]))


def by_sprint(m: dict) -> str:
    sprints = m["sprints"]
    if not sprints:
        return panel("By sprint", "threads and closes per sprint", '<div class="empty">No sprints yet.</div>',
                     wide=True)
    top = max(x["entries"] for x in sprints.values())
    cols = "".join(
        f'<div class="sp{" cur" if name == m["current_sprint"] else ""}" title="{esc(name)}: '
        f'{x["closed"]} of {x["entries"]} closed"><span class="n">{x["closed"]}/{x["entries"]}</span>'
        f'<span class="col2"><span class="tot" style="height:{pct(x["entries"], top)}%">'
        f'<span class="cl" style="height:{pct(x["closed"], x["entries"])}%"></span></span></span>'
        f'<span class="nm">{esc(name)}</span></div>' for name, x in sprints.items())
    chart = (f'<div class="cols" role="img" aria-label="closed of threads per sprint">{cols}</div>'
             + key([("s-ans", "closed"), ("s-tot", "threads"), ("", "current sprint in orange")]))
    rows = [[("id", esc(name)), num(x["entries"]), num(x["open"]), num(x["closed"]), num(x["answered"]),
             num(hrs(x["hours_to_first_answer"])), num(hrs(x["hours_to_close"])), num(x["stale_open"]),
             num(f'~{x["tokens"]}', False)] for name, x in sprints.items()]
    heads = [("", "Sprint"), ("num", "Threads"), ("num", "Open"), ("num", "Closed"), ("num", "Answered"),
             ("num", "Median 1st answer"), ("num", "Median close"), ("num", "Stale"), ("num", "~Tokens")]
    return panel("By sprint", "threads and closes per sprint, and how the median times move",
                 f'<div class="trend"><div>{chart}</div><div>{spark(sprints)}</div></div>' + table(heads, rows),
                 wide=True)


def by_model(m: dict) -> str:
    models = sorted(m["models"].items(), key=lambda kv: -kv[1]["events"])
    if not models:
        return panel("By model", "events written per model", '<div class="empty">No events yet.</div>')
    top = max(x["events"] for _, x in models)
    rows = [[("mods", f"<code>{esc(k)}</code>"),
             ("vz", bar([("s-ev", x["events"], f'{x["events"]} events')], top, f'{k}: {x["events"]} events')),
             num(x["events"]), num(x["handoffs"]), num(x["accepted"]), num(x["rework"])] for k, x in models]
    heads = [("", "Model"), ("vz", "Events"), ("num", "Events"), ("num", "Hand-offs"), ("num", "Accepted"),
             ("num", "Rework")]
    return panel("By model", "events written per model, and how its hand-offs were judged", table(heads, rows),
                 wide=True)


FOOT = ("numbers from <code>baton metrics</code> · also at <code>/api/metrics.json</code> · times are hours "
        "between events")


def metrics_page(board: Board, now: datetime | None = None) -> str:
    now = now or datetime.now()
    view = Model(board, now)
    m = metrics.compute(board, now=now)
    open_ = [t for t in board.entries().values() if t["status"] == "OPEN"]
    blockers = sum(1 for t in open_ if t["kind"] == "B" or t.get("blocks"))
    head = (f'<div class="mhd"><h2>Metrics</h2><span class="hint">{esc(m["scope"])} · generated '
            f'{esc(m["generated"])} · stale after {m["stale_hours"]:g}h</span></div>')
    body = (head + kpis(m, blockers) + '<div class="mgrid">' + times(m) + health(m) + by_role(m, view)
            + handoffs(m, view) + by_sprint(m) + by_model(m) + "</div>")
    return document(board.root.name, view, body, f"metrics · {board.root.name}", "metrics", FOOT, CSS)
