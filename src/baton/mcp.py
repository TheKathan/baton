"""A Model Context Protocol server for baton: `baton mcp`.

It speaks JSON-RPC 2.0 over stdio, one message per line, using only the standard library.
Every tool runs the matching `baton` command in-process, so the same rules apply: the
hand-off cap, the unanswered-question check, `C` entries needing files, and so on.
The board is found from the server's working directory, the same way the CLI finds it.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__, config

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

_ROLE = {"type": "string", "description": "your role, e.g. backend (defaults to $BATON_ROLE)"}
_IDS = {"type": "array", "items": {"type": "string"}}
_STRS = {"type": "array", "items": {"type": "string"}}


def _tool(name, description, props, required=()):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props, "required": list(required),
                            "additionalProperties": False}}


TOOLS = [
    _tool("baton_brief", "Start-up pack: quick guide, your status, questions waiting on you, "
          "the cited entries in full, and your own replied-to threads. Call it first.",
          {"role": _ROLE, "ids": {**_IDS, "description": "entry ids your brief cites"}}),
    _tool("baton_unread", "New entries and replies that concern you, in full. Moves your read cursor "
          "unless peek is true.", {"role": _ROLE, "peek": {"type": "boolean"}}),
    _tool("baton_show", "Print entries by id, from any sprint, with their replies.",
          {"ids": _IDS}, ["ids"]),
    _tool("baton_open", "Open threads you wrote or are named in (all=true adds broadcasts; "
          "blocking=true lists only blockers).",
          {"role": _ROLE, "all": {"type": "boolean"}, "blocking": {"type": "boolean"}}),
    _tool("baton_post", "Post a new entry. kind: Q question, C contract change (needs files), "
          "D decision, B blocker. Address roles by name.",
          {"role": _ROLE, "kind": {"type": "string", "enum": ["Q", "C", "D", "B"]},
           "to": {**_STRS, "description": "roles, or [\"all\"]"}, "title": {"type": "string"},
           "body": {"type": "string"}, "files": _STRS, "cites": _STRS, "blocks": _STRS},
          ["kind", "to", "title", "body"]),
    _tool("baton_reply", "Answer a thread; close=true also closes it as settled.",
          {"role": _ROLE, "id": {"type": "string"}, "body": {"type": "string"},
           "close": {"type": "boolean"}}, ["id", "body"]),
    _tool("baton_close", "Close threads that are settled (answered, fixed or superseded).",
          {"role": _ROLE, "ids": _IDS, "reason": {"type": "string"}}, ["ids"]),
    _tool("baton_handoff", "Hand off finished work (at most 20 lines) and update your status row. "
          "Refused while a question addressed to you is unanswered.",
          {"role": _ROLE, "phase": {"type": "string"}, "state": {"type": "string"},
           "to": _STRS, "title": {"type": "string"}, "body": {"type": "string"},
           "files": _STRS, "cites": _STRS, "closes": _IDS, "force": {"type": "boolean"}},
          ["phase", "state", "to", "title", "body"]),
    _tool("baton_status", "The status table: one row per role.", {}),
    _tool("baton_grep", "Search titles, bodies and replies.", {"text": {"type": "string"}}, ["text"]),
]


def _csv(values) -> str:
    return ",".join(values or [])


def _argv(name: str, a: dict, body_file: str | None) -> list[str]:
    role = ["--as", a["role"]] if a.get("role") else []
    if name == "baton_brief":
        return ["brief", *role] + (["--ids", _csv(a["ids"])] if a.get("ids") else [])
    if name == "baton_unread":
        return ["unread", *role] + (["--peek"] if a.get("peek") else [])
    if name == "baton_show":
        return ["show", *a["ids"]]
    if name == "baton_open":
        return (["open", *role] + (["--all"] if a.get("all") else [])
                + (["--blocking"] if a.get("blocking") else []))
    if name == "baton_post":
        out = ["post", a["kind"], *role, "--to", _csv(a["to"]), "--title", a["title"], "--body-file", body_file]
        for key in ("files", "cites", "blocks"):
            if a.get(key):
                out += [f"--{key}", _csv(a[key])]
        return out
    if name == "baton_reply":
        return ["reply", a["id"], *role, "--body-file", body_file] + (["--close"] if a.get("close") else [])
    if name == "baton_close":
        return ["close", *a["ids"], *role] + (["--reason", a["reason"]] if a.get("reason") else [])
    if name == "baton_handoff":
        out = ["handoff", *role, "--phase", a["phase"], "--state", a["state"], "--to", _csv(a["to"]),
               "--title", a["title"], "--body-file", body_file]
        for key in ("files", "cites", "closes"):
            if a.get(key):
                out += [f"--{key}", _csv(a[key])]
        return out + (["--force"] if a.get("force") else [])
    if name == "baton_status":
        return ["status"]
    if name == "baton_grep":
        return ["grep", a["text"]]
    raise KeyError(name)


def call_tool(name: str, args: dict) -> tuple[str, bool]:
    """Run a tool; return (text, is_error)."""
    from .cli import main as cli_main
    body_file = None
    try:
        if "body" in args:
            fd, body_file = tempfile.mkstemp(prefix="baton-mcp-", suffix=".txt")
            with os.fdopen(fd, "w") as f:
                f.write(args["body"])
        argv = _argv(name, args, body_file)
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                cli_main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                if e.code and not isinstance(e.code, int):
                    err.write(str(e.code))
        text = (out.getvalue() + err.getvalue()).strip() or "(no output)"
        return text, code != 0
    except KeyError:
        return f"unknown tool {name}", True
    finally:
        if body_file:
            with contextlib.suppress(OSError):
                os.unlink(body_file)


def handle(msg: dict) -> dict | None:
    """Handle one JSON-RPC message; return the response, or None for notifications."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (e.g. notifications/initialized)
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        from .cli import GUIDE
        return ok({"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "baton", "version": __version__},
                   "instructions": "baton is this project's coordination board.\n" + GUIDE})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        text, is_error = call_tool(params.get("name", ""), params.get("arguments") or {})
        return ok({"content": [{"type": "text", "text": text}], "isError": is_error})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def serve(stdin=None, stdout=None) -> None:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


def install(path: Path, command: str = "baton") -> bool:
    """Register `<command> mcp` as the "baton" server in an .mcp.json file.

    Merges into the existing file and keeps every other server. Returns False when the
    entry was already there.
    """
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text() or "{}")
        except ValueError as e:
            raise config.ConfigError(f"{path} is not valid JSON ({e}); fix it by hand first") from None
        if not isinstance(data, dict):
            raise config.ConfigError(f"{path} must contain a JSON object")
    servers = data.setdefault("mcpServers", {})
    entry = {"command": command, "args": ["mcp"]}
    if servers.get("baton") == entry:
        return False
    servers["baton"] = entry
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return True
