"""baton: a file-based coordination board for AI agents building software together."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from . import __version__, config, render
from .importer import import_file
from .store import Board, BoardError, normalise_id

GUIDE = """\
Read at three moments only: (1) at start, (2) before you change a shared package,
(3) before you report done. Never poll in a loop.

  baton unread --as <role>                    what is new for you (advances your cursor)
  baton show C-143 H-150                      read entries by id (any sprint)
  baton open --as <role>                      open threads you own or are asked in
  baton post Q --as <role> --to backend --title "..." -   (body on stdin)
  baton reply Q-231 --as <role> -             answer a thread
  baton close Q-231 --as <role> [--reason ..] close a thread you settled
  baton handoff --as <role> --phase S6-B --state "DONE pending QA" --to qa --title "..." -

Kinds: Q question · C contract change (needs --files) · D decision · H hand-off · B blocker.
Blocking questions go straight to the orchestrator, not to the board.
"""


def _board(args) -> Board:
    root = config.find_root()
    return Board(root, config.load(root))


def _body(args) -> str:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text()
    parts = getattr(args, "body", None) or []
    if parts == ["-"]:
        return sys.stdin.read()
    return " ".join(parts)


def _role(args) -> str:
    return args.role or os.environ.get("BATON_ROLE", "")


def _csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _after_write(board: Board) -> None:
    if board.cfg.get("auto_render", True):
        render.render_all(board)


def tokens(text: str) -> int:
    """Rough token estimate (about 4 characters per token)."""
    return (len(text) + 3) // 4


def _format_event(e: dict, threads: dict) -> str:
    t = threads[e["id"]]
    if e["type"] == "entry":
        return render.entry_md(t) + "\n"
    if e["type"] == "reply":
        return (f"[{e['id']}] reply from {e['from']} · {e['ts']} (thread: {render.one_line(t)})\n"
                + e["body"] + "\n\n")
    reason = f": {e['reason']}" if e.get("reason") else ""
    return f"[{e['id']}] CLOSED by {e['from']} · {e['ts']}{reason}\n\n"


def _unread_text(board: Board, role: str, everything: bool, peek: bool) -> tuple[str, int]:
    events = board.unread(role, everything=everything, peek=peek)
    threads = board.entries()
    return "".join(_format_event(e, threads) for e in events), len(events)


def _long_body_warnings(board: Board, t: dict) -> list[str]:
    limit = (board.cfg.get("body_warn_lines") or {}).get(t["kind"])
    n = len(t["body"].splitlines())
    if limit and n > limit:
        return [(f"{t['id']}: body is {n} lines (guideline {limit} for {t['kind']}); "
                 "readers pay for every line, so link long tables and evidence instead")]
    return []


# ---------------- commands ----------------
def cmd_init(args) -> None:
    root = Path(args.root).resolve() if args.root else Path.cwd()
    path = root / config.CONFIG_NAME
    if path.exists() and not args.force:
        raise BoardError(f"{path} exists (use --force to overwrite)")
    cfg = {k: v for k, v in config.DEFAULTS.items()}
    cfg["sprint"] = args.sprint
    if args.dir:
        cfg["dir"] = args.dir
    cfg["roles"] = _csv(args.roles)
    config.save(root, cfg)
    board = Board(root, cfg)
    board.dir.mkdir(parents=True, exist_ok=True)
    gi = board.dir / ".gitignore"
    if not gi.exists():
        gi.write_text(".lock\n.cursors/\n*.tmp\n")
    print(f"initialised {path} (board dir {cfg['dir']}, sprint {cfg['sprint']})")
    try:
        render.render_all(board)
    except BoardError as e:
        print(f"note: views not rendered yet: {e}")


def cmd_post(args) -> None:
    board = _board(args)
    t = board.post(args.kind, _role(args), _csv(args.to), args.title, _body(args),
                   _csv(args.files), _csv(args.cites), _csv(args.blocks))
    _after_write(board)
    print(f"posted {t['id']}")
    for w in _long_body_warnings(board, t):
        print(f"warning: {w}", file=sys.stderr)


def cmd_reply(args) -> None:
    board = _board(args)
    e = board.reply(args.id, _role(args), _body(args))
    if args.close:
        board.close(args.id, _role(args), "")
    _after_write(board)
    print(f"replied to {e['id']}" + (" and closed it" if args.close else ""))


def _unanswered(t: dict) -> bool:
    """A question or blocker that nobody but its author has replied to."""
    return t["kind"] in ("Q", "B") and not any(r["from"] != t["from"] for r in t["replies"])


def cmd_close(args) -> None:
    board = _board(args)
    ids = list(args.ids)
    if args.sprint:
        rows = [t for t in board.open_threads() if t["sprint"] == args.sprint]
        unanswered = [t for t in rows if _unanswered(t) and not args.include_unanswered]
        contracts = [t for t in rows if t["kind"] == "C" and not args.include_contracts]
        ids += [t["id"] for t in rows if t not in unanswered and t not in contracts]
        if unanswered:
            print("kept open (unanswered question/blocker; answer it, carry it over, or pass "
                  "--include-unanswered): " + ", ".join(t["id"] for t in unanswered))
        if contracts:
            print("kept open (contracts stay live until a newer C- entry supersedes them; close them "
                  "by id then, or pass --include-contracts): " + ", ".join(t["id"] for t in contracts))
    if not ids:
        if args.sprint:
            print("nothing to close")
            return
        raise BoardError("give entry ids, or --sprint <name> to close every settled open thread of a sprint")
    for i in ids:
        e = board.close(i, _role(args), args.reason or "")
        print(f"closed {e['id']}")
    _after_write(board)


def cmd_show(args) -> None:
    board = _board(args)
    for i in args.ids:
        print(render.entry_md(board.get(i)))


def cmd_list(args) -> None:
    board = _board(args)
    kinds = [k.upper() for k in _csv(args.kind)]
    for t in board.entries().values():
        if args.sprint and t["sprint"] != args.sprint:
            continue
        if kinds and t["kind"] not in kinds:
            continue
        if args.status and t["status"] != args.status.upper():
            continue
        if args.role and not board.involves(t, args.role):
            continue
        print(render.one_line(t))


def cmd_unread(args) -> None:
    board = _board(args)
    role = _role(args)
    text, count = _unread_text(board, role, args.all, args.peek or args.mark_read)
    if args.mark_read:
        board.unread(role, everything=True)
        print(f"marked {count} event(s) as read for {role}")
        return
    print(text, end="")
    waiting = board.awaiting(role)
    print(f"{count} unread" + (f"; {len(waiting)} question(s)/blocker(s) await your answer: "
                               + ", ".join(t["id"] for t in waiting) if waiting else ""))
    limit = board.cfg.get("unread_warn_tokens") or 0
    if limit and tokens(text) > limit:
        print(f"note: that was ~{tokens(text)} tokens (over {limit}). Everything was printed. If most of it "
              f"is old history (e.g. after an import), your cursor was stale; "
              f"`baton unread --as {role} --mark-read` resets it.")


def cmd_open(args) -> None:
    board = _board(args)
    kinds = [k.upper() for k in _csv(args.kind)] or None
    role = _role(args) or None
    rows = board.open_threads(role, kinds, args.blocking, named_only=bool(role) and not args.all)
    for t in rows:
        print(render.one_line(t) + (f" · blocks {', '.join(t['blocks'])}" if t.get("blocks") else ""))
    hidden = ""
    if role and not args.all:
        n_all = len(board.open_threads(role, kinds, args.blocking)) - len(rows)
        if n_all:
            hidden = f" ({n_all} more addressed to all; --all shows them)"
    print(f"{len(rows)} open{hidden}")


def cmd_handoff(args) -> None:
    board = _board(args)
    role, body = _role(args), _body(args)
    limit = board.cfg["handoff_max_lines"]
    n_lines = len([ln for ln in body.strip().splitlines()])
    problems = []
    if n_lines > limit:
        problems.append(f"body is {n_lines} lines (max {limit}); move tables and logs to a file and link it")
    waiting = board.awaiting(role)
    if waiting:
        problems.append("unanswered threads addressed to you: " + ", ".join(t["id"] for t in waiting))
    if problems and not args.force:
        raise BoardError("hand-off refused:\n  - " + "\n  - ".join(problems) + "\n  (use --force with a reason in the body)")
    # resolve --closes before writing anything, so a bad id never leaves a half-done hand-off behind
    to_close, already = [], []
    for i in _csv(args.closes):
        thread = board.get(i)
        (already if thread["status"] == "CLOSED" else to_close).append(thread["id"])
    t = board.post("H", role, _csv(args.to), args.title, body, _csv(args.files), _csv(args.cites))
    board.set_status(role, args.phase, args.state, t["id"])
    for i in to_close:
        board.close(i, role, f"settled by {t['id']}")
    _after_write(board)
    print(f"posted {t['id']}; status of {role} set to {args.state!r}"
          + (f"; closed {', '.join(to_close)}" if to_close else ""))
    if already:
        print(f"note: already closed, left as is: {', '.join(already)}")
    candidates = board.maybe_settled(role)
    if candidates:
        print("note: you started these and someone has replied; close them if they are settled "
              f"(`baton close <id> --as {role} --reason …`): "
              + "; ".join(f"{c['id']} (reply from {c['replies'][-1]['from']})" for c in candidates))


def cmd_status(args) -> None:
    board = _board(args)
    if args.state:
        board.set_status(_role(args), args.phase or "", args.state, args.handoff or "")
        _after_write(board)
    for role, r in sorted(board.status().items()):
        print(f"{role:14} {r['phase']:10} {r['state']}  ({r['handoff'] or '—'}, {r['updated']})")


def cmd_sprint(args) -> None:
    board = _board(args)
    old = board.cfg["sprint"]
    if not any(c.isdigit() for c in args.new) and not args.force:
        raise BoardError(f"{args.new!r} does not look like a sprint name (e.g. S2, M1-S3, 2026-W41); "
                         "pass --force if it really is one")
    if args.new == old:
        raise BoardError(f"{old} is already the current sprint")
    path = render.render_archive(board, old)
    cfg = config.load(board.root)
    cfg["sprint"] = args.new
    config.save(board.root, cfg)
    board = Board(board.root, cfg)
    render.render_all(board)
    carried = [t["id"] for t in board.open_threads() if t["sprint"] == old]
    print(f"archived {old} to {path.relative_to(board.root)}; current sprint is now {args.new}")
    if carried:
        print(f"{len(carried)} thread(s) from {old} are still open and listed on the live board: "
              + ", ".join(carried))


def cmd_render(args) -> None:
    board = _board(args)
    for p in render.render_all(board):
        print(f"wrote {p.relative_to(board.root)}")
    if args.archives:
        for s in sorted({t["sprint"] for t in board.entries().values()} - {board.cfg["sprint"]}):
            print(f"wrote {render.render_archive(board, s).relative_to(board.root)}")


def cmd_import(args) -> None:
    board = _board(args)
    res = import_file(board, Path(args.file), args.sprint, dry_run=args.dry_run)
    verb = "would import" if args.dry_run else "imported"
    noun = "entry" if res["entries"] == 1 else "entries"
    print(f"{verb} {res['entries']} {noun} from {res['file']} as sprint {res['sprint']}")
    for r in res["renamed"]:
        print(f"  duplicate id renamed: {r}")
    if not args.dry_run:
        print("views were not re-rendered; when every file is imported, move the old Markdown "
              "aside and run `baton render --archives`")


def cmd_grep(args) -> None:
    board = _board(args)
    q = " ".join(args.text).lower()
    for t in board.entries().values():
        hay = " ".join([t["title"], t["body"], *(r["body"] for r in t["replies"])]).lower()
        if q in hay:
            print(render.one_line(t))


def cmd_lint(args) -> None:
    board = _board(args)
    threads = board.entries()
    errors, warnings = [], []
    nums = Counter(t["n"] for t in threads.values())
    for t in threads.values():
        imported = t.get("imported")
        if nums[t["n"]] > 1:
            (warnings if imported else errors).append(f"{t['id']}: number {t['n']} is used by more than one entry")
        if t["kind"] not in board.cfg["kinds"]:
            (warnings if imported else errors).append(f"{t['id']}: unknown kind {t['kind']}")
        if not imported:
            if t["kind"] == "C" and not t.get("files"):
                errors.append(f"{t['id']}: contract change without files")
            if t["kind"] == "H" and len(t["body"].splitlines()) > board.cfg["handoff_max_lines"]:
                warnings.append(f"{t['id']}: hand-off longer than {board.cfg['handoff_max_lines']} lines")
            warnings.extend(_long_body_warnings(board, t))
    for w in warnings:
        print(f"warn  {w}")
    for e in errors:
        print(f"error {e}")
    print(f"{len(threads)} entries, {len(errors)} error(s), {len(warnings)} warning(s)")
    if errors:
        sys.exit(1)


def cmd_brief(args) -> None:
    """Everything a freshly started agent needs, in one call. Does not move the cursor."""
    board = _board(args)
    role = _role(args)
    board._check_role(role)
    out = [f"# Board brief for {role} (sprint {board.cfg['sprint']})", "", GUIDE]
    row = board.status().get(role)
    if row:
        out.append(f"Your status: {row['phase']} · {row['state']} · last hand-off {row['handoff'] or '—'}\n")
    waiting = board.awaiting(role)
    if waiting:
        out.append(f"## Waiting for your answer ({len(waiting)})\n")
        out += [render.entry_md(t) for t in waiting]
    shown = {t["id"] for t in waiting}
    cited, unknown = [], []
    for i in _csv(args.ids):
        try:
            t = board.get(i)
        except BoardError:
            unknown.append(i)  # e.g. a story or doc id from the brief, not a board entry
            continue
        if t["id"] not in shown:
            cited.append(t)
    if cited:
        out.append("## Entries cited by your brief\n")
        out += [render.entry_md(t) for t in cited]
    if unknown:
        out.append(f"Not board entries (skipped): {', '.join(unknown)}\n")
    candidates = board.maybe_settled(role)
    if candidates:
        out.append("## Yours, replied to: close if settled\n")
        out += [f"- {render.one_line(t)} (last reply from {t['replies'][-1]['from']})" for t in candidates]
        out.append("")
    _, count = _unread_text(board, role, False, peek=True)
    out.append(f"{count} unread event(s); run `baton unread --as {role}` to read them.")
    print("\n".join(out))


def cmd_stats(args) -> None:
    """Estimated token cost of what each role would read right now."""
    board = _board(args)
    threads = board.entries()
    sprints = {}
    for t in threads.values():
        sprints.setdefault(t["sprint"], []).append(t)
    print("Sprint       entries  open  ~tokens (full markdown)")
    for sp in sorted(sprints, key=lambda s: min(t["ev"] for t in sprints[s])):
        ts = sprints[sp]
        md = "".join(render.entry_md(t) for t in ts)
        print(f"{sp:12} {len(ts):7} {sum(t['status'] == 'OPEN' for t in ts):5}  {tokens(md):8}")
    roles = [_role(args)] if _role(args) else (board.cfg.get("roles") or sorted(board.status()))
    if roles:
        print("\nRole           unread now  ~tokens   open (named)  waiting on you")
        for r in roles:
            text, count = _unread_text(board, r, False, peek=True)
            named = len(board.open_threads(r, named_only=True))
            print(f"{r:14} {count:10} {tokens(text):8}   {named:12}  {len(board.awaiting(r)):14}")
    bodies = sorted(tokens(t["body"]) for t in threads.values())
    if bodies:
        print(f"\nEntry bodies: median ~{bodies[len(bodies) // 2]} tokens, "
              f"p90 ~{bodies[int(len(bodies) * 0.9)]}, max ~{bodies[-1]}")


def _skill_source() -> str:
    from importlib.resources import files
    return (files("baton") / "skill" / "SKILL.md").read_text()


def cmd_skill(args) -> None:
    """Print or install the agent skill that teaches baton (Claude Code skill format)."""
    text = _skill_source()
    if args.action == "show":
        print(text, end="")
        return
    if args.dir:
        base = Path(args.dir).expanduser()
    elif args.project:
        try:
            base = config.find_root() / ".claude" / "skills"
        except config.ConfigError:
            base = Path.cwd() / ".claude" / "skills"
    else:
        base = Path.home() / ".claude" / "skills"
    target = base / "baton" / "SKILL.md"
    if args.action == "path":
        print(target)
        return
    if target.exists() and target.read_text() != text and not args.force:
        raise BoardError(f"{target} exists and differs (use --force to replace it)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    print(f"installed the baton skill to {target}")


def cmd_where(args) -> None:
    root, worktree = config.locate()
    board = Board(root, config.load(root))
    info = {"root": str(board.root)}
    if worktree:
        info["shared_from_worktree"] = str(worktree)
    print(json.dumps({**info, **board.cfg}, indent=2))


# ---------------- parser ----------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="baton", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=GUIDE)
    p.add_argument("--version", action="version", version=f"baton {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, role=False):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if role:
            sp.add_argument("--as", dest="role", help="your role (or set $BATON_ROLE)")
        return sp

    def body(sp):
        sp.add_argument("body", nargs="*", help='message text, or "-" to read stdin')
        sp.add_argument("--body-file")

    sp = add("init", cmd_init, "create .baton/ (config and board) in this project")
    sp.add_argument("--sprint", default="S1")
    sp.add_argument("--dir")
    sp.add_argument("--roles", help="comma-separated allowed roles (empty = any)")
    sp.add_argument("--root")
    sp.add_argument("--force", action="store_true")

    sp = add("post", cmd_post, "post a new entry", role=True)
    sp.add_argument("kind", help="Q, C, D, H or B")
    sp.add_argument("--to", default="all", help="comma-separated roles, or all")
    sp.add_argument("--title", required=True)
    sp.add_argument("--files", help="comma-separated affected files (required for C)")
    sp.add_argument("--cites", help="comma-separated doc/story/decision ids")
    sp.add_argument("--blocks", help="comma-separated stories/tasks this blocks")
    body(sp)

    sp = add("reply", cmd_reply, "answer a thread", role=True)
    sp.add_argument("id")
    sp.add_argument("--close", action="store_true", help="also close the thread")
    body(sp)

    sp = add("close", cmd_close, "close one or more threads", role=True)
    sp.add_argument("ids", nargs="*")
    sp.add_argument("--sprint", help="close every settled open thread of this sprint; unanswered Q/B and "
                                     "contracts stay open")
    sp.add_argument("--include-unanswered", action="store_true",
                    help="with --sprint, also close questions and blockers nobody answered")
    sp.add_argument("--include-contracts", action="store_true",
                    help="with --sprint, also close contract (C) entries")
    sp.add_argument("--reason")

    sp = add("show", cmd_show, "print entries by id, from any sprint")
    sp.add_argument("ids", nargs="+", type=normalise_id)

    sp = add("list", cmd_list, "one line per entry, with filters")
    sp.add_argument("--sprint")
    sp.add_argument("--kind")
    sp.add_argument("--status", choices=["open", "closed", "OPEN", "CLOSED"])
    sp.add_argument("--as", dest="role", help="only entries involving this role")

    sp = add("unread", cmd_unread, "new entries and replies that concern you", role=True)
    sp.add_argument("--all", action="store_true", help="every unread event, not only yours")
    sp.add_argument("--peek", action="store_true", help="do not advance your cursor")
    sp.add_argument("--mark-read", action="store_true", help="advance your cursor without printing")

    sp = add("open", cmd_open, "open threads you wrote or are named in (with --as)", role=True)
    sp.add_argument("--kind")
    sp.add_argument("--all", action="store_true", help="also threads addressed to all")
    sp.add_argument("--blocking", action="store_true", help="only blockers and entries with --blocks")

    sp = add("handoff", cmd_handoff, "post a hand-off (H) and update your status row", role=True)
    sp.add_argument("--phase", required=True)
    sp.add_argument("--state", required=True)
    sp.add_argument("--to", default="all")
    sp.add_argument("--title", required=True)
    sp.add_argument("--files")
    sp.add_argument("--cites")
    sp.add_argument("--closes", help="comma-separated threads this hand-off settles")
    sp.add_argument("--force", action="store_true")
    body(sp)

    sp = add("status", cmd_status, "show the status table, or set your row with --state", role=True)
    sp.add_argument("--phase")
    sp.add_argument("--state")
    sp.add_argument("--handoff")

    sp = add("sprint", cmd_sprint, "archive the current sprint and start a new one")
    sp.add_argument("new", help="the new sprint's name, e.g. S2")
    sp.add_argument("--force", action="store_true", help="accept a name without digits")

    sp = add("render", cmd_render, "regenerate the Markdown views")
    sp.add_argument("--archives", action="store_true", help="also re-render every past sprint")

    sp = add("import", cmd_import, "import a hand-written Markdown board as one sprint")
    sp.add_argument("file")
    sp.add_argument("--sprint", required=True)
    sp.add_argument("--dry-run", action="store_true")

    sp = add("grep", cmd_grep, "search titles, bodies and replies")
    sp.add_argument("text", nargs="+")

    add("lint", cmd_lint, "check ids, kinds, contracts and entry sizes")

    sp = add("brief", cmd_brief, "one-call start-up pack: guide, status, waiting questions, cited entries",
             role=True)
    sp.add_argument("--ids", help="comma-separated entries the agent's brief cites")

    add("stats", cmd_stats, "estimated token cost per sprint and per role", role=True)
    sp = add("skill", cmd_skill, "show or install the agent skill (Claude Code format)")
    sp.add_argument("action", choices=["install", "show", "path"], nargs="?", default="install")
    sp.add_argument("--project", action="store_true",
                    help="install into this project's .claude/skills/ instead of ~/.claude/skills/")
    sp.add_argument("--dir", help="install into <dir>/baton/SKILL.md")
    sp.add_argument("--force", action="store_true", help="replace a different existing copy")

    add("where", cmd_where, "print the project root and config")
    add("guide", lambda a: print(GUIDE), "print the agent quick guide")
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    # parse_known_args: on Python < 3.12 a "*" positional placed after options is reported
    # as unrecognised, so message words that argparse left over are joined back into the body.
    args, extra = parser.parse_known_args(argv)
    if extra:
        flags = [x for x in extra if x.startswith("-") and x != "-"]
        if flags or not hasattr(args, "body"):
            parser.error(f"unrecognized arguments: {' '.join(extra)}")
        args.body = (args.body or []) + extra
    try:
        args.fn(args)
    except (BoardError, config.ConfigError) as e:
        sys.exit(f"baton: {e}")


if __name__ == "__main__":
    main()
