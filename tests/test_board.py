import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from legacy import make_legacy

from baton import config
from baton.cli import main
from baton.store import Board, BoardError

SRC = str(Path(__file__).resolve().parent.parent / "src")


def run(*argv, stdin=None):
    """Run the CLI in-process; return stdout. Raises SystemExit on errors."""
    out = io.StringIO()
    old_stdin = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out):
            main(list(argv))
    finally:
        sys.stdin = old_stdin
    return out.getvalue()


def _post_many(args):
    root, role, count = args
    board = Board(Path(root), config.load(Path(root)))
    return [board.post("Q", role, ["all"], f"q{i}", "body")["id"] for i in range(count)]


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        os.environ.pop("BATON_ROLE", None)
        run("init", "--root", str(self.root), "--sprint", "S1",
            "--roles", "orchestrator,backend,frontend,qa")
        make_legacy(self.root)

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))

    def test_post_allocates_sequential_ids_and_renders(self):
        self.assertIn("posted Q-001", run("post", "Q", "--as", "backend", "--to", "frontend",
                                          "--title", "Which route?", "body text"))
        self.assertIn("posted C-002", run("post", "C", "--as", "backend", "--to", "frontend,qa",
                                          "--title", "Health shape", "--files", "a.ts,b.ts", "-",
                                          stdin="line 1\nline 2\n"))
        md = (self.root / ".baton/BOARD.md").read_text()
        self.assertIn("### [Q-001] backend → frontend · status: OPEN", md)
        self.assertIn("Files: `a.ts`, `b.ts`", md)
        self.assertIn("| C-002 | backend → frontend, qa | Health shape | a.ts; b.ts | S1 | OPEN |",
                      (self.root / ".baton/CONTRACTS-INDEX.md").read_text())

    def test_validation(self):
        with self.assertRaises(SystemExit):
            run("post", "C", "--as", "backend", "--title", "no files", "x")
        with self.assertRaises(SystemExit):
            run("post", "Z", "--as", "backend", "--title", "bad kind", "x")
        with self.assertRaises(SystemExit):
            run("post", "Q", "--as", "intruder", "--title", "bad role", "x")
        with self.assertRaises(SystemExit):
            run("post", "Q", "--title", "no role", "x")

    def test_reply_close_and_show_by_unpadded_id(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "Q?", "why")
        run("reply", "q-1", "--as", "backend", "because", "--close")
        shown = run("show", "Q-1")
        self.assertIn("status: CLOSED", shown)
        self.assertIn("> [A] backend", shown)
        with self.assertRaises(SystemExit):
            run("close", "Q-001", "--as", "backend")

    def test_unread_is_addressed_and_advances_cursor(self):
        run("post", "Q", "--as", "backend", "--to", "frontend", "--title", "for fe", "x")
        run("post", "D", "--as", "orchestrator", "--to", "all", "--title", "for everyone", "x")
        run("post", "Q", "--as", "backend", "--to", "orchestrator", "--title", "not for qa", "x")
        out = run("unread", "--as", "qa")
        self.assertIn("for everyone", out)
        self.assertNotIn("for fe", out)
        self.assertNotIn("not for qa", out)
        self.assertIn("1 unread", out)
        self.assertIn("0 unread", run("unread", "--as", "qa"))
        # replies on a thread you started reach you
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "mine", "x")
        run("reply", "Q-004", "--as", "backend", "answer")
        self.assertIn("reply from backend", run("unread", "--as", "qa"))

    def test_handoff_refused_while_questions_await_and_size_capped(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "need answer", "x")
        with self.assertRaises(SystemExit) as cm:
            run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE",
                "--to", "qa", "--title", "done", "short")
        self.assertIn("Q-001", str(cm.exception.code))
        run("reply", "Q-001", "--as", "backend", "answered")
        long_body = "\n".join(f"line {i}" for i in range(25))
        with self.assertRaises(SystemExit):
            run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE",
                "--to", "qa", "--title", "done", "-", stdin=long_body)
        out = run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE pending QA",
                  "--to", "qa", "--title", "done", "--closes", "Q-001", "gates green")
        self.assertIn("posted H-002", out)
        self.assertEqual(self.board().get("Q-001")["status"], "CLOSED")
        status = (self.root / ".baton/STATUS.md").read_text()
        self.assertIn("| backend | S1-A | DONE pending QA | H-002 |", status)

    def test_sprint_rollover_archives_and_carries_open_threads(self):
        run("post", "Q", "--as", "backend", "--to", "qa", "--title", "still open", "x")
        run("post", "D", "--as", "orchestrator", "--title", "settled", "x")
        run("close", "D-002", "--as", "orchestrator")
        run("sprint", "S2")
        self.assertEqual(config.load(self.root)["sprint"], "S2")
        archive = (self.root / ".baton/archive/BOARD-S1.md").read_text()
        self.assertIn("[Q-001]", archive)
        live = (self.root / ".baton/BOARD.md").read_text()
        self.assertIn("Still open from earlier sprints", live)
        self.assertIn("Q-001", live)
        self.assertNotIn("D-002", live)
        self.assertIn("posted Q-003", run("post", "Q", "--as", "qa", "--title", "new", "x"))
        self.assertIn("[Q-001]", run("show", "Q-001"))

    def test_concurrent_posts_never_collide(self):
        with ProcessPoolExecutor(max_workers=6) as ex:
            batches = list(ex.map(_post_many, [(str(self.root), r, 15) for r in
                                               ["backend", "frontend", "qa", "orchestrator"] * 2]))
        ids = [i for b in batches for i in b]
        self.assertEqual(len(ids), 120)
        self.assertEqual(len(set(ids)), 120)
        evs = [json.loads(ln)["ev"] for ln in (self.root / ".baton/events/S1.jsonl").read_text().splitlines()]
        self.assertEqual(sorted(evs), list(range(1, 121)))
        self.assertIn("0 error(s)", run("lint"))

    def test_import_markdown_board(self):
        md = self.root / "OLD.md"
        md.write_text(
            "# Old board\n\n"
            "### [D-205] orchestrator → all · status: OPEN · 2026-10-06\n**S5 PASSED.** go\n\n"
            "### [Q-183] frontend → orchestrator · status: OPEN · 2026-10-04\nq?\n"
            "> [A] orchestrator · 2026-10-04: yes. `> status: CLOSED by orchestrator`\n\n"
            "### [H-212] ai → qa\nno status or date\n\n"
            "### [N-184] frontend → orchestrator · progress · 2026-10-04\nnote kind\n\n"
            "### [H-205] orchestrator (for ai) → backend, qa · status: OPEN · 2026-10-06\nsame number\n")
        live = self.root / ".baton/BOARD.md"
        live.write_text("# hand-written board\n")
        out = run("import", str(md), "--sprint", "S5")
        self.assertEqual(live.read_text(), "# hand-written board\n")
        with self.assertRaises(SystemExit):
            run("render")
        live.rename(self.root / "BOARD.pre.md")
        run("render", "--archives")
        self.assertTrue((self.root / ".baton/archive/BOARD-S5.md").exists())
        self.assertIn("imported 5 entries", out)
        b = self.board()
        self.assertEqual(b.get("Q-183")["status"], "CLOSED")
        self.assertEqual(b.get("H-205")["from"], "orchestrator")
        self.assertEqual(b.get("H-212")["to"], ["qa"])
        lint = run("lint")
        self.assertIn("0 error(s)", lint)
        self.assertIn("number 205", lint)
        self.assertIn("posted Q-213", run("post", "Q", "--as", "qa", "--title", "after import", "x"))
        again = run("import", str(md), "--sprint", "S5", "--dry-run")
        self.assertIn("D-205 → D-205~2", again)

    def test_migration_helpers_bulk_close_and_mark_read(self):
        run("post", "Q", "--as", "backend", "--to", "qa", "--title", "old", "x")
        run("post", "Q", "--as", "backend", "--to", "qa", "--title", "old too", "x")
        run("sprint", "S2")
        run("post", "Q", "--as", "backend", "--to", "qa", "--title", "current", "x")
        out = run("close", "--sprint", "S1", "--as", "orchestrator", "--reason", "archived",
                  "--include-unanswered")
        self.assertIn("closed Q-001", out)
        self.assertIn("closed Q-002", out)
        self.assertEqual([t["id"] for t in self.board().open_threads()], ["Q-003"])
        self.assertIn("marked", run("unread", "--as", "qa", "--mark-read"))
        self.assertIn("0 unread", run("unread", "--as", "qa"))

    def test_open_lists_named_threads_unless_all(self):
        run("post", "D", "--as", "orchestrator", "--to", "all", "--title", "broadcast", "x")
        run("post", "Q", "--as", "backend", "--to", "qa", "--title", "for qa", "x")
        out = run("open", "--as", "qa")
        self.assertIn("for qa", out)
        self.assertNotIn("broadcast", out)
        self.assertIn("1 open (1 more addressed to all; --all shows them)", out)
        self.assertIn("broadcast", run("open", "--as", "qa", "--all"))
        self.assertIn("2 open", run("open"))

    def test_long_contract_warns_but_posts(self):
        body = "\n".join(f"line {i}" for i in range(45))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = run("post", "C", "--as", "backend", "--title", "big", "--files", "a.ts", "-", stdin=body)
        self.assertIn("posted C-001", out)
        self.assertIn("45 lines (guideline 40 for C)", err.getvalue())
        self.assertIn("guideline 40", run("lint"))

    def test_unread_prints_everything_and_notes_large_backlogs(self):
        cfg = config.load(self.root)
        cfg["unread_warn_tokens"] = 50
        config.save(self.root, cfg)
        long_body = "detail that matters " * 40
        run("post", "D", "--as", "orchestrator", "--title", "big decision", long_body)
        out = run("unread", "--as", "qa")
        self.assertIn(long_body.strip(), out)
        self.assertIn("--mark-read` resets it", out)
        self.assertNotIn("note:", run("unread", "--as", "qa"))

    def test_brief_packs_guide_status_waiting_and_cited_without_moving_cursor(self):
        run("post", "C", "--as", "backend", "--to", "frontend", "--title", "shape", "--files", "a.ts", "spec")
        run("post", "Q", "--as", "backend", "--to", "frontend", "--title", "please confirm", "x")
        run("status", "--as", "frontend", "--phase", "S1-A", "--state", "building")
        out = run("brief", "--as", "frontend", "--ids", "C-1,Q-2")
        self.assertIn("Read at three moments only", out)
        self.assertIn("Your status: S1-A · building", out)
        self.assertIn("## Waiting for your answer (1)", out)
        self.assertEqual(out.count("[Q-002]"), 1)
        self.assertIn("### [C-001]", out)
        self.assertIn("2 unread event(s)", out)
        self.assertIn("2 unread", run("unread", "--as", "frontend"))
        self.assertIn("Not board entries (skipped): STORY-703", run("brief", "--as", "frontend", "--ids", "STORY-703,C-1"))

    def test_stats_reports_sprints_and_roles(self):
        run("post", "Q", "--as", "backend", "--to", "qa", "--title", "q", "x")
        out = run("stats")
        self.assertIn("S1", out)
        self.assertRegex(out, r"qa\s+1\s+\d+\s+1\s+1")
        self.assertIn("Entry bodies: median", out)

    def test_skill_install_show_and_refuse_to_clobber(self):
        dest = self.root / "skills"
        self.assertIn("installed the baton skill", run("skill", "install", "--dir", str(dest)))
        installed = (dest / "baton" / "SKILL.md").read_text()
        self.assertTrue(installed.startswith("---\nname: baton\ndescription: "))
        self.assertEqual(run("skill", "show"), installed)
        self.assertIn("installed", run("skill", "install", "--dir", str(dest)))  # identical: fine
        (dest / "baton" / "SKILL.md").write_text("local edits")
        with self.assertRaises(SystemExit):
            run("skill", "install", "--dir", str(dest))
        run("skill", "install", "--dir", str(dest), "--force")
        self.assertEqual((dest / "baton" / "SKILL.md").read_text(), installed)
        self.assertEqual(run("skill", "path", "--project").strip(),
                         str(self.root.resolve() / ".claude/skills/baton/SKILL.md"))

    def test_skill_mentions_only_real_commands(self):
        import re

        from baton.cli import build_parser
        text = run("skill", "show")
        parser = build_parser()
        sub = next(a for a in parser._actions if a.dest == "cmd")
        for cmd in set(re.findall(r"`baton ([a-z]+)", text)):
            self.assertIn(cmd, sub.choices, f"skill mentions unknown command baton {cmd}")
        for cmd, flag in set(re.findall(r"baton ([a-z]+)[^`\n]*?(--[a-z-]+)", text)):
            if cmd in sub.choices and flag not in ("--help",):
                opts = {o for a in sub.choices[cmd]._actions for o in a.option_strings}
                self.assertIn(flag, opts, f"skill uses unknown flag baton {cmd} {flag}")

    def test_handoff_with_closes_never_duplicates(self):
        run("post", "Q", "--as", "qa", "--to", "frontend", "--title", "badge?", "x")
        run("reply", "Q-001", "--as", "frontend", "yes", "--close")
        run("post", "B", "--as", "frontend", "--to", "backend", "--title", "500 error", "x")
        out = run("handoff", "--as", "frontend", "--phase", "S1", "--state", "DONE", "--to", "qa",
                  "--title", "done", "--closes", "Q-001,B-002", "short")
        self.assertIn("closed B-002", out)
        self.assertIn("already closed, left as is: Q-001", out)
        with self.assertRaises(SystemExit):  # unknown id: refused before anything is written
            run("handoff", "--as", "frontend", "--phase", "S1", "--state", "DONE", "--to", "qa",
                "--title", "again", "--closes", "Q-099", "short")
        self.assertEqual([t["id"] for t in self.board().entries().values() if t["kind"] == "H"], ["H-003"])

    def test_close_sprint_keeps_unanswered_questions_open(self):
        run("post", "Q", "--as", "qa", "--to", "frontend", "--title", "unanswered", "x")
        run("post", "Q", "--as", "backend", "--to", "orchestrator", "--title", "answered", "x")
        run("reply", "Q-002", "--as", "orchestrator", "yes")
        run("post", "B", "--as", "frontend", "--to", "backend", "--title", "self-reply only", "x")
        run("reply", "B-003", "--as", "frontend", "still broken")
        run("post", "D", "--as", "orchestrator", "--title", "scope", "x")
        run("post", "C", "--as", "backend", "--to", "frontend", "--title", "shape", "--files", "a.ts", "x")
        out = run("close", "--sprint", "S1", "--as", "orchestrator")
        self.assertIn("kept open (unanswered", out)
        self.assertIn("kept open (contracts", out)
        self.assertEqual(sorted(t["id"] for t in self.board().open_threads()), ["B-003", "C-005", "Q-001"])
        run("close", "--sprint", "S1", "--as", "orchestrator", "--include-unanswered", "--include-contracts")
        self.assertEqual(self.board().open_threads(), [])

    def test_sprint_rejects_names_without_digits(self):
        with self.assertRaises(SystemExit):
            run("sprint", "new")
        self.assertEqual(config.load(self.root)["sprint"], "S1")
        self.assertFalse((self.root / ".baton/archive/BOARD-S1.md").exists())
        run("sprint", "next", "--force")
        self.assertEqual(config.load(self.root)["sprint"], "next")

    def test_handoff_and_brief_point_out_own_threads_that_look_settled(self):
        run("post", "B", "--as", "frontend", "--to", "backend", "--title", "500 error", "x")
        run("reply", "B-001", "--as", "backend", "fixed")
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "no reply yet", "x")
        self.assertIn("## Yours, replied to: close if settled", run("brief", "--as", "frontend"))
        out = run("handoff", "--as", "frontend", "--phase", "S1", "--state", "DONE", "--to", "qa",
                  "--title", "done", "short")
        self.assertIn("B-001 (reply from backend)", out)
        self.assertNotIn("Q-002", out.split("note:")[-1])
        out = run("handoff", "--as", "frontend", "--phase", "S1", "--state", "DONE", "--to", "qa",
                  "--title", "done again", "--closes", "B-001", "short")
        self.assertNotIn("someone has replied", out)

    def test_shim_runs_without_install(self):
        shim = Path(__file__).resolve().parent.parent / "bin" / "baton"
        r = subprocess.run([sys.executable, str(shim), "list"], capture_output=True, text=True, check=False,
                           env={**os.environ, "BATON_ROOT": str(self.root)})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_corrupt_line_is_reported(self):
        run("post", "Q", "--as", "qa", "--title", "ok", "x")
        with (self.root / ".baton/events/S1.jsonl").open("a") as f:
            f.write("{not json\n")
        with self.assertRaises(BoardError):
            self.board().events()


if __name__ == "__main__":
    unittest.main()
