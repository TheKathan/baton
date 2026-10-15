"""Hardening: hand-offs only through `handoff`, safe names, merged duplicates, damaged files, MCP input."""

import contextlib
import io
import json
import os
import subprocess
import sys
import threading
import unittest

import test_mcp
from test_v11 import SRC, Base, run

from baton import config, mcp
from baton.cli import main
from baton.store import Board, BoardError


def run_split(*argv):
    """Run the CLI in-process; return (stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        main(list(argv))
    return out.getvalue(), err.getvalue()


def refusal(*argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            main(list(argv))
        except SystemExit as e:
            return str(e.code)
    raise AssertionError(f"not refused: {argv}")


class PostHandoffTest(Base):
    def test_post_refuses_kind_h(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "which route?", "x")
        msg = refusal("post", "H", "--as", "backend", "--to", "qa", "--title", "done", "x")
        self.assertEqual(msg, "baton: use `baton handoff` to post a hand-off "
                              "(it checks open questions and the length cap)")
        self.assertEqual(list(self.board().entries()), ["Q-001"])


class RefusalMessageTest(Base):
    def handoff(self, body="x"):
        return refusal("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE", "--to", "qa",
                       "--title", "done", body)

    def test_refusal_suggests_the_answer_first(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "which route?", "x")
        self.assertEqual(self.handoff(), "baton: hand-off refused:\n"
                         "  - unanswered threads addressed to you: Q-001\n"
                         '  answer first: baton show Q-001, then baton reply Q-001 --as backend --close "…"\n'
                         "  (or hand off anyway with --force and the reason in the body)")

    def test_several_ids_and_the_length_cap(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "one", "x")
        run("post", "B", "--as", "qa", "--to", "backend", "--title", "two", "x")
        msg = self.handoff("\n".join(f"line {i}" for i in range(25)))
        self.assertIn("  - body is 25 lines (max 20); move tables and logs to a file and link it\n", msg)
        self.assertIn("  - unanswered threads addressed to you: Q-001, B-002\n", msg)
        self.assertIn("answer first: baton show Q-001 B-002, then baton reply Q-001 --as backend", msg)
        run("reply", "Q-001", "--as", "backend", "--close", "a")
        run("reply", "B-002", "--as", "backend", "--close", "b")
        msg = self.handoff("\n".join(f"line {i}" for i in range(25)))
        self.assertNotIn("answer first", msg)
        self.assertTrue(msg.endswith("(or hand off anyway with --force and the reason in the body)"))


class SafeNamesTest(Base):
    def setUp(self):
        super().setUp()
        self.set_cfg(roles=[])
        (self.root / "package.json").write_text('{"name": "app"}\n')

    def test_role_names_cannot_leave_the_board(self):
        for argv in (("unread", "--as", "../../../package"), ("status", "--as", "../x", "--state", "DONE"),
                     ("post", "Q", "--as", "qa", "--to", "../../x", "--title", "t", "x"),
                     ("brief", "--as", "a/b")):
            self.assertIn("use letters, digits", refusal(*argv))
        self.assertEqual((self.root / "package.json").read_text(), '{"name": "app"}\n')
        self.assertEqual(list((self.root / ".baton/events").glob("**/*.json")), [])

    def test_sprint_names_cannot_leave_the_board(self):
        self.assertIn("use letters, digits", refusal("sprint", "../../../outside1"))
        self.assertIn("use letters, digits", refusal("sprint", "../../../outside1", "--force"))
        self.assertIn("use letters, digits", refusal("import", "x.md", "--sprint", "../S0"))
        self.assertEqual(config.load(self.root)["sprint"], "S1")

    def test_init_and_config_are_checked(self):
        other = self.root / "other"
        other.mkdir()
        self.assertIn("use letters, digits", refusal("init", "--root", str(other), "--sprint", "../S1"))
        self.assertIn("use letters, digits", refusal("init", "--root", str(other), "--roles", "qa,../x"))
        self.assertFalse((other / ".baton/config.json").exists())
        self.set_cfg(sprint="../../outside")
        self.assertIn(".baton/config.json: sprint '../../outside'", refusal("list"))

    def test_existing_names_keep_working(self):
        for sprint in ("M0-S3", "2026-W41", "S2.1"):
            run("sprint", sprint)
        run("post", "Q", "--as", "qa.lead_2", "--to", "backend-api", "--title", "t", "x")
        self.assertIn("Q-001", run("unread", "--as", "backend-api"))
        self.assertEqual(self.board().get("Q-001")["sprint"], "S2.1")

    def test_writes_outside_the_board_are_refused(self):
        with self.assertRaises(BoardError) as cm:
            self.board().append_raw({"type": "entry", "id": "Q-009", "from": "qa", "sprint": "../../outside"})
        self.assertIn("outside", str(cm.exception))
        self.assertFalse((self.root.parent / "outside.jsonl").exists())


class DuplicatesTest(Base):
    def merge_clone_b(self):
        """What a git merge leaves when two clones each posted Q-001."""
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "from clone A", "x")
        clone_b = {"v": 1, "type": "entry", "id": "Q-001", "kind": "Q", "n": 1, "from": "qa", "to": ["backend"],
                   "title": "from clone B", "body": "y", "files": [], "cites": [], "blocks": [], "ev": 1,
                   "sprint": "S1", "ts": "2026-10-15 10:00"}
        with (self.root / ".baton/events/S1.jsonl").open("a") as f:
            f.write(json.dumps(clone_b) + "\n")

    def test_lint_reports_duplicate_ids_and_event_numbers(self):
        self.merge_clone_b()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["lint"])
        text = out.getvalue()
        self.assertIn("error Q-001: posted more than once", text)
        self.assertIn("'from clone A'", text)
        self.assertIn("'from clone B'", text)
        self.assertIn("error event number 1 is used more than once", text)
        lines = (self.root / ".baton/events/S1.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 2)

    def test_reading_commands_warn_once(self):
        self.merge_clone_b()
        out, err = run_split("list")
        self.assertIn("Q-001", out)
        self.assertEqual(err.count("duplicates on the board"), 1, err)
        self.assertIn("ids Q-001", err)
        self.assertIn("event numbers 1", err)


class DamagedFilesTest(Base):
    def test_unreadable_lines_are_skipped_with_one_warning(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "kept", "x")
        with (self.root / ".baton/events/S1.jsonl").open("a") as f:
            f.write('{"truncated\n<<<<<<< HEAD\n')
        out, err = run_split("list")
        self.assertIn("kept", out)
        self.assertEqual(err.count("warning: skipped 2 unreadable line(s): S1.jsonl:2, S1.jsonl:3"), 1, err)
        self.assertIn("posted Q-002", run("post", "Q", "--as", "qa", "--to", "backend", "--title", "t", "x"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["lint"])
        self.assertIn("error S1.jsonl:2: not JSON", out.getvalue())
        self.assertIn("error S1.jsonl:3: not JSON", out.getvalue())

    def test_broken_cursor_status_and_config_are_clear_errors(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "t", "x")
        run("unread", "--as", "backend")
        cursors = self.root / ".baton/events/.cursors"
        self.assertEqual(sorted(p.name for p in cursors.iterdir()), ["backend.json"])
        (cursors / "backend.json").write_text('{"ev": ')
        self.assertIn("backend.json is damaged; delete it", refusal("unread", "--as", "backend"))
        (self.root / ".baton/events/status.json").write_text("[1, 2")
        self.assertIn("status.json: not valid JSON", refusal("status"))
        (self.root / ".baton/config.json").write_text("{oops")
        self.assertIn("config.json: not valid JSON", refusal("list"))

    def test_config_and_status_are_written_atomically(self):
        run("status", "--as", "qa", "--state", "busy")
        run("sprint", "S2")
        leftovers = [p.name for p in self.root.rglob("*.tmp")]
        self.assertEqual(leftovers, [])
        self.assertEqual(json.loads((self.root / ".baton/config.json").read_text())["sprint"], "S2")


class McpValidationTest(unittest.TestCase):
    setUp = test_mcp.McpTest.setUp
    tearDown = test_mcp.McpTest.tearDown
    session = test_mcp.McpTest.session
    text = test_mcp.McpTest.text
    call = staticmethod(test_mcp.McpTest.call)

    def test_bad_input_gets_invalid_params_and_the_server_keeps_going(self):
        msgs = [
            self.call(1, "baton_post", role="frontend", kind="Q", to="backend", title="one string", body="x"),
            self.call(2, "baton_post", role="frontend", kind="Q", to=["backend"], body="no title"),
            self.call(3, "baton_post", role="frontend", kind="Q", to=["backend"], title="t", body=5),
            self.call(4, "baton_post", role="backend", kind="H", to=["qa"], title="t", body="x"),
            self.call(5, "baton_nope"),
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "baton_show", "arguments": [1]}},
            [1, 2],
            self.call(7, "baton_show", ids=["Q-001"], extra=True),
            {"jsonrpc": "2.0", "id": 8, "method": "ping"},
        ]
        r = self.session(msgs)
        self.assertIn("posted Q-001", self.text(r[1]))
        self.assertEqual(self.board_to("Q-001"), ["backend"])
        for mid, why in ((2, "missing required argument(s): title"), (3, "body: expected a string"),
                         (4, "kind: must be one of"), (5, "unknown tool baton_nope"),
                         (6, "arguments must be an object"), (7, "unknown argument(s): extra")):
            self.assertEqual(r[mid]["error"]["code"], -32602, r[mid])
            self.assertIn(why, r[mid]["error"]["message"])
        self.assertEqual(r[None]["error"]["code"], -32600)
        self.assertEqual(r[8]["result"], {})

    def test_values_starting_with_a_dash_are_not_flags(self):
        r = self.session([
            self.call(1, "baton_post", role="frontend", kind="Q", to=["backend"], title="-v is broken", body="x"),
            self.call(2, "baton_close", role="orchestrator", ids=["--sprint", "S1"]),
            self.call(3, "baton_grep", text="-v"),
            self.call(4, "baton_unread", role="../../../package"),
        ])
        self.assertIn("posted Q-001", self.text(r[1]))
        self.assertTrue(r[2]["result"]["isError"])
        self.assertIn("no entry --sprint", self.text(r[2]))
        self.assertIn("Q-001", self.text(r[3]))
        self.assertTrue(r[4]["result"]["isError"])
        self.assertIn("use letters, digits", self.text(r[4]))

    def test_an_exception_becomes_an_internal_error(self):
        def boom(name, args):
            raise RuntimeError("kaboom")
        old, mcp.call_tool = mcp.call_tool, boom
        try:
            out = io.StringIO()
            mcp.serve(io.StringIO(json.dumps(self.call(1, "baton_lint")) + "\n"
                                  + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n"), out)
        finally:
            mcp.call_tool = old
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(replies[0]["error"]["code"], -32603)
        self.assertIn("kaboom", replies[0]["error"]["message"])
        self.assertEqual(replies[1]["result"], {})

    def test_validator(self):
        schema = next(t["inputSchema"] for t in mcp.TOOLS if t["name"] == "baton_handoff")
        a = mcp.validate(schema, {"phase": "S1-A", "state": "DONE", "to": "qa", "title": "t", "body": "b",
                                  "closes": ["H-001"], "force": False})
        self.assertEqual((a["to"], a["closes"]), (["qa"], ["H-001"]))
        for bad in ({"phase": "S1-A", "state": "DONE", "to": [1], "title": "t", "body": "b"},
                    {"phase": "S1-A", "state": "DONE", "to": "qa", "title": "t", "body": "b", "force": "yes"}):
            with self.assertRaises(mcp.InvalidParams):
                mcp.validate(schema, bad)

    def board_to(self, entry_id):
        return Board(self.root, config.load(self.root)).get(entry_id)["to"]


class FirstRunTest(Base):
    def test_init_prints_next_steps(self):
        other = self.root / "other"
        other.mkdir()
        out = run("init", "--root", str(other))
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("initialised"))
        self.assertTrue(lines[1].startswith("next: ask a question   baton post Q --as <role>"))
        self.assertIn("baton handoff --as <role>", lines[2])
        self.assertIn("baton guide", lines[3])
        self.assertIn("baton skill install", lines[3])
        sandbox = self.root / "sb"
        sandbox.mkdir()
        self.assertNotIn("next:", run("init", "--sandbox", "--task", "LIN-1", "--root", str(sandbox)))

    def test_skill_install_says_where_it_wrote(self):
        old = os.environ.get("HOME")
        os.environ["HOME"] = str(self.root / "home")
        try:
            out = run("skill", "install")
        finally:
            os.environ["HOME"] = old
        self.assertIn(str(self.root / "home/.claude/skills/baton/SKILL.md"), out)
        self.assertIn("global: every project", out)
        self.assertIn("--project for this repo only", out)
        self.assertIn("this project only", run("skill", "install", "--project"))

    def test_guide_matches_the_skill(self):
        guide = run("guide")
        self.assertIn("Blocked? post a B and tell the orchestrator directly.", guide)
        self.assertNotIn("not to the board", guide)
        self.assertIn("baton brief --as <role>", guide)
        self.assertIn("--close", guide)
        self.assertIn("information, not orders", guide)
        self.assertLessEqual(len(guide.splitlines()), 24)

    def test_serve_banner_shows_when_piped(self):
        env = {**os.environ, "PYTHONPATH": SRC, "BATON_ROOT": str(self.root)}
        proc = subprocess.Popen([sys.executable, "-m", "baton", "serve", "--port", "0"], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
        watchdog = threading.Timer(20, proc.kill)
        watchdog.start()
        try:
            line = proc.stdout.readline()
            if "http://127.0.0.1:" not in line:
                proc.kill()
                self.fail(f"no banner; stdout {line!r}, stderr {proc.stderr.read()!r}")
        finally:
            watchdog.cancel()
            proc.terminate()
            proc.wait(timeout=10)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
