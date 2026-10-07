"""`baton serve`: a read-only local dashboard of the board (standard library only).

Routes (GET only; anything else gets 405):
  /                 the dashboard: blockers, questions waiting, open threads by age, status, metrics
  /e/<id>           one entry with its replies
  /api/board.json   open threads and the status table
  /api/metrics.json the same numbers as `baton metrics --json`
The board is re-read on every request, and the page refreshes itself every 30 s.
"""

from __future__ import annotations

import html
import json
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from . import __version__, metrics, render
from .store import Board, BoardError

CSS = """
:root{--bg:#f6f8fa;--panel:#fff;--text:#1f2328;--muted:#59636e;--line:#d0d7de;--accent:#c2410c;
--chip:#eef1f4;--warn:#9a6700;--bad:#cf222e;--ok:#1a7f37;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--panel:#161b22;--text:#e6edf3;--muted:#9198a1;
--line:#30363d;--accent:#ff922b;--chip:#21262d;--warn:#d29922;--bad:#f85149;--ok:#3fb950}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.45 ui-sans-serif,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;margin-bottom:16px}
h1{font-size:20px;margin:0}h1 b{color:var(--accent)}h2{font-size:15px;margin:24px 0 8px}
.muted{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
.card .n{font-size:24px;font-weight:700}.card .l{color:var(--muted);font-size:12px}
.bad .n{color:var(--bad)}.warn .n{color:var(--warn)}.ok .n{color:var(--ok)}
.wrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);
vertical-align:top}th{font-size:12px;color:var(--muted);font-weight:600}tr:last-child td{border-bottom:0}
code,.id{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
a{color:inherit}a.id{color:var(--accent);text-decoration:none;white-space:nowrap}
details>summary{cursor:pointer;font-size:15px;font-weight:600;margin:24px 0 8px}a.id:hover{text-decoration:underline}
.nw{white-space:nowrap}.kind{display:inline-block;min-width:18px;text-align:center;border-radius:4px;background:var(--chip);padding:0 4px}
.empty{padding:12px;color:var(--muted)}pre{white-space:pre-wrap;background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:14px;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
footer{margin-top:28px;color:var(--muted);font-size:12px}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def _age(hours) -> str:
    if hours is None:
        return "—"
    return f"{hours / 24:.1f}d" if hours >= 48 else f"{hours:.0f}h"


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<div class="wrap"><div class="empty">{esc(empty)}</div></div>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _link(t: dict) -> str:
    return f'<a class="id" href="/e/{esc(t["id"])}">{esc(t["id"])}</a>'


def _thread_row(t: dict, now: datetime) -> list[str]:
    title = t["title"] or render.first_line(t["body"])
    return [_link(t), f'<span class="kind">{esc(t["kind"])}</span>', esc(t["from"]), esc(", ".join(t["to"])),
            esc(title), esc(_age(metrics.age_hours(t, now))), esc(t["sprint"])]


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30">'
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body><main>{body}"
            f'<footer>baton {esc(__version__)} · read-only · refreshes every 30 s</footer></main></body></html>')


def dashboard(board: Board) -> str:
    now = datetime.now()  # noqa: DTZ005 - board times are local wall-clock
    m = metrics.compute(board, now=now)
    s = m["summary"]
    threads = board.entries()
    open_ = sorted((t for t in threads.values() if t["status"] == "OPEN"),
                   key=lambda t: -(metrics.age_hours(t, now) or 0))
    blockers = [t for t in open_ if t["kind"] == "B" or t.get("blocks")]
    contracts = [t for t in open_ if t["kind"] == "C"]
    moving = [t for t in open_ if t["kind"] != "C"]
    waiting = [(t, r) for t in open_ if t["kind"] in ("Q", "B") and not metrics.first_answer(t)
               for r in t["to"] if r != "all"]
    cards = [
        ("Open threads", s["open"], ""), ("Blockers", len(blockers), "bad" if blockers else "ok"),
        ("Unanswered Q/B", s["unanswered_open"], "warn" if s["unanswered_open"] else "ok"),
        ("Stale (≥48h)", s["stale_open"], "warn" if s["stale_open"] else "ok"),
        ("Median first answer", (f'{s["hours_to_first_answer"]["median"]}h'
                                 if s["hours_to_first_answer"]["n"] else "—"), ""),
        ("Close rate", f'{int(s["close_rate"] * 100)}%' if s["close_rate"] is not None else "—", ""),
    ]
    cards_html = "".join(f'<div class="card {c}"><div class="n">{esc(v)}</div><div class="l">{esc(lbl)}</div></div>'
                         for lbl, v, c in cards)
    th = ["Id", "Kind", "From", "To", "Title", "Idle", "Sprint"]
    status = board.status()
    sprint_rows = [[esc(name), esc(x["entries"]), esc(x["open"]), esc(x["closed"]), esc(x["answered"]),
                    esc(metrics._short(x["hours_to_first_answer"])), esc(metrics._short(x["hours_to_close"])),
                    esc(x["stale_open"])] for name, x in m["sprints"].items()]
    role_rows = [[esc(r), esc(x["posted"]), esc(x["replies"]), esc(f'{x["answered"]}/{x["asked_of"]}'),
                  esc(metrics._short(x["hours_to_answer"])), esc(x["waiting_on"]), esc(x["open_owned"])]
                 for r, x in m["roles"].items()]
    body = f"""
<header><h1><b>baton</b> · {esc(board.root.name)}</h1>
<span class="muted">sprint <code>{esc(board.cfg["sprint"])}</code> · {esc(m["generated"])}</span></header>
<div class="cards">{cards_html}</div>
<h2>Blockers</h2>{_table(th, [_thread_row(t, now) for t in blockers], "No open blockers.")}
<h2>Questions waiting for an answer</h2>{_table(["Waiting on", *th],
    [[esc(r), *_thread_row(t, now)] for t, r in waiting], "Nobody is waiting for an answer.")}
<h2>Open threads, longest idle first</h2>{_table(th, [_thread_row(t, now) for t in moving], "Nothing open.")}
<details><summary>Live contracts ({len(contracts)})</summary>{_table(th, [_thread_row(t, now) for t in contracts],
    "No live contracts.")}</details>
<h2>Status</h2>{_table(["Role", "Phase", "State", "Last hand-off", "Updated"],
    [[esc(r), f'<span class="nw">{esc(x["phase"])}</span>', esc(x["state"]),
      f'<span class="nw">{esc(x["handoff"] or "—")}</span>', f'<span class="nw">{esc(x["updated"])}</span>']
     for r, x in sorted(status.items())], "No status rows yet.")}
<h2>Sprints</h2>{_table(["Sprint", "Threads", "Open", "Closed", "Answered", "Median 1st answer", "Median close",
                         "Stale"], sprint_rows, "No sprints yet.")}
<h2>Roles</h2>{_table(["Role", "Posted", "Replies", "Answered", "Median answer", "Waiting on", "Open owned"],
                       role_rows, "No roles yet.")}
"""
    return page(f"baton · {board.root.name}", body)


def entry_page(board: Board, entry_id: str) -> str:
    t = board.get(entry_id)
    return page(f"{t['id']} · baton", f'<header><h1><a class="id" href="/">baton</a> · {esc(t["id"])}</h1>'
                f'<span class="muted">{esc(t["status"])} · {esc(t["sprint"])}</span></header>'
                f"<pre>{esc(render.entry_md(t))}</pre>")


def board_json(board: Board) -> dict:
    now = datetime.now()  # noqa: DTZ005 - board times are local wall-clock
    open_ = [t for t in board.entries().values() if t["status"] == "OPEN"]
    return {"sprint": board.cfg["sprint"], "status": board.status(),
            "open": [{"id": t["id"], "kind": t["kind"], "from": t["from"], "to": t["to"],
                      "title": t["title"] or render.first_line(t["body"]), "sprint": t["sprint"],
                      "idle_hours": metrics.age_hours(t, now)} for t in open_]}


def make_handler(board: Board):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"baton/{__version__}"

        def log_message(self, *args):  # keep the terminal quiet
            pass

        def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8"):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = unquote(self.path.split("?", 1)[0])
            try:
                if path == "/":
                    return self._send(200, dashboard(board))
                if path == "/api/metrics.json":
                    return self._send(200, json.dumps(metrics.compute(board), indent=2), "application/json")
                if path == "/api/board.json":
                    return self._send(200, json.dumps(board_json(board), indent=2), "application/json")
                if path.startswith("/e/"):
                    return self._send(200, entry_page(board, path[3:]))
            except BoardError as e:
                code = 404 if path.startswith("/e/") else 500
                return self._send(code, page("baton", f"<pre>{esc(e)}</pre>"))
            return self._send(404, page("baton", "<pre>Not found. Try /</pre>"))

        def _deny(self):
            self._send(405, page("baton", "<pre>The baton dashboard is read-only.</pre>"))

        do_POST = do_PUT = do_PATCH = do_DELETE = _deny

    return Handler


def make_server(board: Board, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(board))


def run(board: Board, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = make_server(board, host, port)
    url = f"http://{host}:{server.server_address[1]}/"
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"warning: serving on {host}; anyone who can reach it can read the board")
    print(f"baton dashboard on {url} (read-only; Ctrl-C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
