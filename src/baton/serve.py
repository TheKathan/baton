"""`baton serve`: a read-only local dashboard of the board (standard library only).

Routes (GET only; anything else gets 405):
  /                 the board: a kanban of the work, who holds the baton, decisions and recent activity
  /contracts        live contracts by file area (?f=all|new|old|touched)
  /metrics          board health as a dashboard (metricsview.py): key numbers, times, per-role, per-sprint, per-model
  /e/<id>           one entry with its replies (a sandbox's other tasks: /e/<task>/<id>)
  /api/board.json   open threads and the status table
  /api/metrics.json the same numbers as `baton metrics --json`
The board is re-read on every request, and the page refreshes itself every 30 s.
"""

from __future__ import annotations

import json
import socketserver
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import __version__, boardview, metrics, metricsview, render, sandbox
from .boardview import esc
from .store import Board, BoardError, normalise_id

CSS = """
.ent{display:flex;align-items:baseline;gap:10px;margin:16px 0 10px;flex-wrap:wrap}
.ent h2{margin:0;font:700 15px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.ent .st{font-size:12px;color:var(--muted)}.ent .back{color:var(--indigo);font-size:12.5px}
pre.md{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:14px;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.by{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 14px;margin-top:12px}
.by h3{margin:2px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.by ul{margin:0;padding-left:18px;color:var(--muted);font-size:12.5px}
.msg{margin:16px 0}
"""


def page(title: str, body: str, board: Board | None = None, now: datetime | None = None) -> str:
    """A page in the shared shell for the entry and error routes (no board model needed)."""
    cfg = board.cfg if board is not None else {}
    project = board.root.name if board is not None else "baton"
    return boardview.shell(project, boardview.scope_of(cfg), now or datetime.now(), body, title,
                           foot=f"baton {esc(__version__)}", css=CSS)


def error_page(board: Board, message: str) -> str:
    return page("baton", f'<pre class="md msg">{esc(message)}</pre>', board)


def metrics_page(board: Board, now: datetime | None = None) -> str:
    return metricsview.metrics_page(board, now)


def entry_page(board: Board, entry_id: str) -> str:
    if "/" in entry_id:  # a sandbox's other tasks: <task>/<id>
        task, _, key = entry_id.partition("/")
        threads = sandbox.other_tasks(board.root, board.cfg.get("task", "")).get(task, {})
        key = normalise_id(key)
        kind, _, num = key.partition("-")
        t = threads.get(key) or (threads.get(board.format_id(kind, int(num))) if num.isdigit() else None)
        if t is None:
            raise BoardError(f"no entry {entry_id}")
    else:
        t = board.get(entry_id)
    return page(f"{t['id']} · baton", f'<div class="ent"><a class="back" href="/">← board</a><h2>{esc(t["id"])}</h2>'
                f'<span class="st">{esc(t["status"])} · {esc(t["sprint"])}</span></div>'
                f'<pre class="md">{esc(render.entry_md(t))}</pre>{_written_by(t)}', board)


def _written_by(t: dict) -> str:
    """Who wrote each part of a thread, with the model when one was recorded."""
    def line(role: str, what: str, e: dict) -> str:
        model = f' with <code>{esc(e["model"])}</code> <span class="muted">({esc(e.get("model_src", ""))})</span>' \
            if e.get("model") else ""
        return f"<li>{esc(what)} by {esc(role)}{model}</li>"
    rows = [line(t["from"], "posted", t)] + [line(r["from"], "replied", r) for r in t["replies"]]
    if t["closed_by"]:
        outcome = f' ({esc(t["closed_outcome"])})' if t.get("closed_outcome") else ""
        rows.append(f'<li>closed{outcome} by {esc(t["closed_by"])}'
                    + (f' with <code>{esc(t["closed_model"])}</code>' if t.get("closed_model") else "") + "</li>")
    return f'<section class="by"><h3>Written by</h3><ul>{"".join(rows)}</ul></section>'


def board_json(board: Board) -> dict:
    now = datetime.now()
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
            url = urlsplit(self.path)
            path = unquote(url.path)
            try:
                if path == "/":
                    return self._send(200, boardview.board_page(board))
                if path == "/contracts":
                    return self._send(200, boardview.contracts_page(board, parse_qs(url.query).get("f", ["all"])[0]))
                if path == "/metrics":
                    return self._send(200, metrics_page(board))
                if path == "/api/metrics.json":
                    return self._send(200, json.dumps(metrics.compute(board), indent=2), "application/json")
                if path == "/api/board.json":
                    return self._send(200, json.dumps(board_json(board), indent=2), "application/json")
                if path.startswith("/e/"):
                    return self._send(200, entry_page(board, path[3:]))
            except BoardError as e:
                code = 404 if path.startswith("/e/") else 500
                return self._send(code, error_page(board, str(e)))
            return self._send(404, error_page(board, "Not found. Try /"))

        def _deny(self):
            self._send(405, error_page(board, "The baton dashboard is read-only."))

        do_POST = do_PUT = do_PATCH = do_DELETE = _deny

    return Handler


class _Server(ThreadingHTTPServer):
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = str(self.server_address[0]), self.server_address[1]


def make_server(board: Board, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return _Server((host, port), make_handler(board))


def run(board: Board, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = make_server(board, host, port)
    url = f"http://{host}:{server.server_address[1]}/"
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"warning: serving on {host}; anyone who can reach it can read the board", flush=True)
    print(f"baton dashboard on {url} (read-only; Ctrl-C to stop)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
