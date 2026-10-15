"""A Model Context Protocol server for baton: `baton mcp`.

The `baton` command is the primary interface; these tools exist for agents that cannot run
shell commands, and the server's instructions tell clients to prefer the command.

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
          {"role": _ROLE, "all": {"type": "boolean"}, "blocking": {"type": "boolean"},
           "stale": {"type": "string", "description": "only threads idle at least this long, e.g. 2d, 36h"}}),
    _tool("baton_post", "Post a new entry. kind: Q question, C contract change (needs files), "
          "D decision, B blocker. Address roles by name.",
          {"role": _ROLE, "kind": {"type": "string", "enum": ["Q", "C", "D", "B"]},
           "to": {**_STRS, "description": "roles, or [\"all\"]"}, "title": {"type": "string"},
           "body": {"type": "string"}, "files": _STRS, "cites": _STRS, "blocks": _STRS,
           "supersedes": {**_IDS, "description": "with C: contracts this one replaces (they are closed)"}},
          ["kind", "to", "title", "body"]),
    _tool("baton_reply", "Answer a thread; close=true also closes it as settled.",
          {"role": _ROLE, "id": {"type": "string"}, "body": {"type": "string"},
           "close": {"type": "boolean"}}, ["id", "body"]),
    _tool("baton_close", "Close threads that are settled (answered, fixed or superseded). Orchestrators: "
          "pass sprint to close every settled thread of a sprint (unanswered Q/B and live contracts stay open), "
          "or phase to close a phase's hand-offs once it passes its gate.",
          {"role": _ROLE, "ids": _IDS, "reason": {"type": "string"}, "sprint": {"type": "string"},
           "phase": {"type": "string"}}),
    _tool("baton_handoff", "Hand off finished work (at most 20 lines) and update your status row. "
          "Refused while a question addressed to you is unanswered.",
          {"role": _ROLE, "phase": {"type": "string"}, "state": {"type": "string"},
           "to": _STRS, "title": {"type": "string"}, "body": {"type": "string"},
           "files": _STRS, "cites": _STRS, "closes": _IDS, "force": {"type": "boolean"}},
          ["phase", "state", "to", "title", "body"]),
    _tool("baton_status", "The status table: one row per role. Pass role and state to set your own row.",
          {"role": _ROLE, "phase": {"type": "string"}, "state": {"type": "string"}}),
    _tool("baton_grep", "Search titles, bodies and replies.", {"text": {"type": "string"}}, ["text"]),
    _tool("baton_list", "One line per entry, with filters.",
          {"sprint": {"type": "string"}, "kind": {"type": "string", "description": "e.g. C or Q,B"},
           "status": {"type": "string", "enum": ["open", "closed"]}, "role": _ROLE}),
    _tool("baton_contracts", "Live contracts: this board's and those of other tasks merged into the branch.",
          {"paths": {**_STRS, "description": "only contracts touching these globs, e.g. modules/network/**"}}),
    _tool("baton_sandbox_start", "Sandbox mode: create this task's board, or resume it from "
          ".baton/tasks/<task>.jsonl. Run once at the start of a sandbox.",
          {"task": {"type": "string", "description": "the issue id, e.g. LIN-123"}, "roles": _STRS,
           "force": {"type": "boolean"}}, ["task"]),
    _tool("baton_finish", "Sandbox mode: export the task's board to .baton/tasks/<task>.jsonl (commit it with "
          "the PR) and return the PR summary. strict=true fails while questions or blockers are open.",
          {"strict": {"type": "boolean"}}),
    _tool("baton_sprint", "Orchestrators: archive the current sprint and start a new one.",
          {"name": {"type": "string", "description": "the new sprint, e.g. S2"}}, ["name"]),
    _tool("baton_metrics", "Board health: answer and close times, stale threads, per-role load.",
          {"sprint": {"type": "string"}, "stale": {"type": "string"}}),
    _tool("baton_lint", "Check the board: duplicate ids, unknown kinds, contracts without files, policies. "
          "suggest=true proposes policies most entries already follow.",
          {"all": {"type": "boolean", "description": "also check imported entries"}, "suggest": {"type": "boolean"}}),
]


def tools() -> list[dict]:
    """TOOLS, with baton_post's kinds taken from the project's config (H goes through baton_handoff)."""
    try:
        kinds = [k for k in config.load(config.find_root())["kinds"] if k != "H"]
    except (config.ConfigError, OSError, ValueError):
        kinds = None
    if not kinds:
        return TOOLS
    out = []
    for t in TOOLS:
        if t["name"] == "baton_post":
            props = {**t["inputSchema"]["properties"], "kind": {"type": "string", "enum": kinds}}
            t = {**t, "inputSchema": {**t["inputSchema"], "properties": props}}
        out.append(t)
    return out


INVALID_PARAMS, INTERNAL_ERROR = -32602, -32603
_TYPES = {"string": str, "boolean": bool, "object": dict}


class InvalidParams(ValueError):
    pass


def _value(key: str, schema: dict, v):
    """Check one argument against its schema; a lone string where an array is expected is wrapped."""
    kind = schema.get("type")
    if kind == "array":
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise InvalidParams(f"{key}: expected an array of strings")
        return v
    if not isinstance(v, _TYPES[kind]):
        raise InvalidParams(f"{key}: expected a {kind}, got {type(v).__name__}")
    if "enum" in schema and v not in schema["enum"]:
        raise InvalidParams(f"{key}: must be one of {', '.join(map(str, schema['enum']))}")
    return v


def validate(schema: dict, args) -> dict:
    """`args` checked against a tool's inputSchema (the subset TOOLS use: object, required, enum,
    string, boolean, array of strings). Raises InvalidParams."""
    if not isinstance(args, dict):
        raise InvalidParams("arguments must be an object")
    props = schema.get("properties", {})
    unknown = sorted(k for k in args if k not in props)
    if unknown and schema.get("additionalProperties") is False:
        raise InvalidParams(f"unknown argument(s): {', '.join(unknown)}")
    missing = [k for k in schema.get("required", []) if args.get(k) is None]
    if missing:
        raise InvalidParams(f"missing required argument(s): {', '.join(missing)}")
    return {k: _value(k, props[k], v) for k, v in args.items() if v is not None and k in props}


def _csv(values) -> str:
    return ",".join(values or [])


def _opt(name: str, value: str) -> str:
    """`--name=value`, so a value that starts with '-' is never read as a flag."""
    return f"--{name}={value}"


def _argv(name: str, a: dict, body_file: str | None) -> list[str]:
    role = [_opt("as", a["role"])] if a.get("role") else []
    if name == "baton_brief":
        return ["brief", *role] + ([_opt("ids", _csv(a["ids"]))] if a.get("ids") else [])
    if name == "baton_unread":
        return ["unread", *role] + (["--peek"] if a.get("peek") else [])
    if name == "baton_show":
        return ["show", "--", *a["ids"]]
    if name == "baton_open":
        return (["open", *role] + (["--all"] if a.get("all") else [])
                + (["--blocking"] if a.get("blocking") else []) + ([_opt("stale", a["stale"])] if a.get("stale") else []))
    if name == "baton_post":
        out = ["post", *role, _opt("to", _csv(a["to"])), _opt("title", a["title"]), _opt("body-file", body_file)]
        for key in ("files", "cites", "blocks", "supersedes"):
            if a.get(key):
                out.append(_opt(key, _csv(a[key])))
        return out + ["--", a["kind"]]
    if name == "baton_reply":
        return ["reply", *role, _opt("body-file", body_file)] + (["--close"] if a.get("close") else []) + ["--", a["id"]]
    if name == "baton_close":
        return (["close", *role] + ([_opt("sprint", a["sprint"])] if a.get("sprint") else [])
                + ([_opt("phase", a["phase"])] if a.get("phase") else [])
                + ([_opt("reason", a["reason"])] if a.get("reason") else [])
                + (["--", *a["ids"]] if a.get("ids") else []))
    if name == "baton_handoff":
        out = ["handoff", *role, _opt("phase", a["phase"]), _opt("state", a["state"]), _opt("to", _csv(a["to"])),
               _opt("title", a["title"]), _opt("body-file", body_file)]
        for key in ("files", "cites", "closes"):
            if a.get(key):
                out.append(_opt(key, _csv(a[key])))
        return out + (["--force"] if a.get("force") else [])
    if name == "baton_status":
        if a.get("state"):
            return ["status", *role, _opt("state", a["state"])] + ([_opt("phase", a["phase"])] if a.get("phase") else [])
        return ["status"]
    if name == "baton_grep":
        return ["grep", "--", a["text"]]
    if name == "baton_list":
        out = ["list"]
        for key in ("sprint", "kind", "status"):
            if a.get(key):
                out.append(_opt(key, a[key]))
        return out + role
    if name == "baton_contracts":
        return ["contracts"] + ([_opt("paths", _csv(a["paths"]))] if a.get("paths") else [])
    if name == "baton_sandbox_start":
        root = os.environ.get("BATON_ROOT") or os.getcwd()
        return (["init", "--sandbox", _opt("task", a["task"]), _opt("root", root)]
                + ([_opt("roles", _csv(a["roles"]))] if a.get("roles") else [])
                + (["--force"] if a.get("force") else []))
    if name == "baton_finish":
        return ["finish"] + (["--strict"] if a.get("strict") else [])
    if name == "baton_sprint":
        return ["sprint", "--", a["name"]]
    if name == "baton_metrics":
        out = ["metrics"]
        for key in ("sprint", "stale"):
            if a.get(key):
                out.append(_opt(key, a[key]))
        return out
    if name == "baton_lint":
        return ["lint"] + (["--all"] if a.get("all") else []) + (["--suggest"] if a.get("suggest") else [])
    raise InvalidParams(f"unknown tool {name}")


def call_tool(name: str, args) -> tuple[str, bool]:
    """Run a tool; return (text, is_error). Raises InvalidParams for an unknown tool or bad arguments."""
    from .cli import main as cli_main
    schema = next((t["inputSchema"] for t in tools() if t["name"] == name), None)
    if schema is None:
        raise InvalidParams(f"unknown tool {name}")
    args = validate(schema, args)
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
    finally:
        if body_file:
            with contextlib.suppress(OSError):
                os.unlink(body_file)


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg) -> dict | None:
    """Handle one JSON-RPC message; return the response, or None for notifications."""
    if not isinstance(msg, dict):
        return _error(None, -32600, "invalid request: expected a JSON object")
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (e.g. notifications/initialized)
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return _error(mid, INVALID_PARAMS, "params must be an object")
    if method == "initialize":
        asked = params.get("protocolVersion")
        from .cli import GUIDE
        return ok({"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "baton", "version": __version__},
                   "instructions": ("baton is this project's coordination board. If you can run shell commands, "
                                    "prefer the `baton` command (it is the primary interface and has every option); "
                                    "these tools are the same commands for agents without a shell.\n" + GUIDE)})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": tools()})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            return _error(mid, INVALID_PARAMS, "params.name must be a tool name")
        try:
            text, is_error = call_tool(name, params.get("arguments") or {})
        except InvalidParams as e:
            return _error(mid, INVALID_PARAMS, f"{name}: {e}")
        return ok({"content": [{"type": "text", "text": text}], "isError": is_error})
    return _error(mid, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> None:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = _error(None, -32700, "parse error")
        else:
            try:
                reply = handle(msg)
            except Exception as e:  # noqa: BLE001
                mid = msg.get("id") if isinstance(msg, dict) else None
                reply = _error(mid, INTERNAL_ERROR, f"internal error: {type(e).__name__}: {e}")
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
