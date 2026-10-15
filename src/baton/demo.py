"""`baton demo`: a narrated walkthrough of the core idea on a throwaway board.

Every step runs the real CLI in-process against a temporary board (``$BATON_ROOT``),
and what it prints is captured and shown as is. Nothing in the current directory or
any existing board is read or written.
"""

from __future__ import annotations

import contextlib
import io
import os
import shlex
import sys
import tempfile
import time
from pathlib import Path

from . import config
from .store import BoardError

ROLES = "frontend,backend,qa"
HANDOFF = ["handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE", "--to", "qa",
           "--title", "S1-A backend", "Health endpoint done."]
STEPS = [  # (narration, argv, pause after)
    ("a fresh board for three agents", ["init", "--roles", ROLES], 0.6),
    ("frontend asks backend a question",
     ["post", "Q", "--as", "frontend", "--to", "backend", "--title", "Which route serves health?",
      "For the status page."], 0.9),
    ("backend tries to hand off while that question is unanswered", HANDOFF, 2.0),
    ("backend answers and closes it", ["reply", "Q-001", "--as", "backend", "--close", "Use GET /api/health."], 0.9),
    ("now the hand-off goes through", HANDOFF, 1.2),
    ("the board: every entry, one line each", ["list"], 0.9),
    ("and who is where", ["status"], 0.6),
]


class _Style:
    def __init__(self, stream):
        on = stream.isatty() and not os.environ.get("NO_COLOR")
        self.dim, self.red, self.green, self.bold, self.reset = (
            ("\033[2m", "\033[31m", "\033[32m", "\033[1m", "\033[0m") if on else ("",) * 5)


def _call(argv: list[str]) -> tuple[bool, str]:
    """Run one real baton command; (succeeded, everything it printed)."""
    from .cli import main
    buf = io.StringIO()
    ok = True
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            main(argv)
        except SystemExit as e:
            ok = e.code in (None, 0)
            if isinstance(e.code, str):
                print(e.code)
    return ok, buf.getvalue().rstrip("\n")


@contextlib.contextmanager
def _isolated(root: Path):
    """Point baton at `root` only, whatever the caller's environment says."""
    saved = {k: os.environ.get(k) for k in ("BATON_ROOT", "BATON_ROLE")}
    os.environ["BATON_ROOT"] = str(root)
    os.environ.pop("BATON_ROLE", None)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _play(root: Path, fast: bool, out) -> None:
    s = _Style(out)
    root = root.resolve()

    def pause(seconds):
        if not fast:
            out.flush()
            time.sleep(seconds)

    def typed(text):
        out.write(f"{s.bold}$ {s.reset}")
        for ch in text:
            out.write(ch)
            if not fast:
                out.flush()
                time.sleep(0.018)
        out.write("\n")

    with _isolated(root):
        for i, (note, argv, wait) in enumerate(STEPS):
            out.write(f"{s.dim}# {note}{s.reset}\n")
            pause(0.3)
            typed(shlex.join(["baton", *argv]))
            if argv[0] == "init":  # init takes its root as a flag, never the current directory
                ok, text = _call([*argv, "--root", str(root)])
                text = text.replace(str(root) + os.sep, "")
            else:
                ok, text = _call(argv)
            colour = s.green if ok and argv[0] in ("handoff", "reply") else (s.red if not ok else "")
            if text:
                out.write(f"{colour}{text}{s.reset if colour else ''}\n")
            if argv[0] == "handoff" and not ok and i != 2:
                raise BoardError(f"demo step failed: {text}")
            out.write("\n")
            pause(wait)
    out.write(f"{s.bold}What just happened:{s.reset} baton refused backend's hand-off while frontend's "
              "question was open, and let it through once backend answered.\n")
    out.write("  Try it on your project: baton init --roles orchestrator,backend,frontend,qa\n")
    out.write("  Teach your agents:      baton guide / baton skill install\n")


def run(fast: bool = False, keep: str | None = None) -> None:
    out = sys.stdout
    if keep:
        root = Path(keep).expanduser().resolve()
        if (root / ".baton").exists() or (root / config.CONFIG_NAME).exists():
            raise BoardError(f"{root} already has a .baton/; pick an empty or new directory for --keep")
        root.mkdir(parents=True, exist_ok=True)
        _play(root, fast, out)
        out.write(f"\nThe demo board is kept in {root}. Explore it:\n"
                  f"  cd {shlex.quote(str(root))} && baton list && baton show Q-001 H-002\n")
        return
    with tempfile.TemporaryDirectory(prefix="baton-demo-") as tmp:
        _play(Path(tmp), fast, out)
