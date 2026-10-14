"""`baton report`: checking exported task boards without a board, as a PR check does."""

import json
import shutil
import unittest

import test_sandbox
from test_sandbox import git, run


@unittest.skipUnless(shutil.which("git"), "git not installed")
class ReportTest(unittest.TestCase):  # SandboxTest's repo fixture, without its tests
    setUp, tearDown, wipe_sandbox = (test_sandbox.SandboxTest.setUp, test_sandbox.SandboxTest.tearDown,
                                     test_sandbox.SandboxTest.wipe_sandbox)

    def task_branch(self, task, leave_open=False):
        """A sandbox on its own branch: post, maybe settle, finish and commit the export."""
        git(self.repo, "checkout", "-q", "-b", f"fix/{task}", "main")
        run("init", "--sandbox", "--task", task, "--roles", test_sandbox.ROLES)
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", f"{task} question", "x")
        if not leave_open:
            run("reply", "Q-001", "--as", "backend", "--close", "answered")
        run("post", "C", "--as", "backend", "--title", f"{task} shape", "--files", "api.ts", "x")
        run("finish")
        git(self.repo, "add", ".baton/tasks")
        git(self.repo, "commit", "-q", "-m", task)
        self.wipe_sandbox()  # CI sees only the committed tree

    def test_reports_the_tasks_changed_in_a_pr(self):
        self.task_branch("LIN-1")
        out = run("report", "--since", "main", "--strict")
        self.assertIn("### baton: LIN-1", out)
        self.assertIn("**C-002** LIN-1 shape (files: api.ts)", out)
        self.assertFalse((self.repo / ".baton/sandbox.json").exists())  # no board was created

    def test_strict_fails_on_open_questions(self):
        self.task_branch("LIN-2", leave_open=True)
        with self.assertRaises(SystemExit) as cm:
            run("report", "--since", "main", "--strict")
        self.assertIn("1 task board(s) with open questions", str(cm.exception.code))
        self.assertIn("Open questions and blockers", run("report", "--since", "main"))  # not strict: exit 0

    def test_only_changed_boards_and_explicit_files(self):
        self.task_branch("LIN-3")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "fix/LIN-3", "-m", "merge")
        self.task_branch("LIN-4")
        out = run("report", "--since", "main")
        self.assertIn("LIN-4", out)
        self.assertNotIn("LIN-3", out)  # merged before this PR
        self.assertIn("### baton: LIN-3", run("report", ".baton/tasks/LIN-3.jsonl"))
        data = json.loads(run("report", "--since", "main", "--json"))
        self.assertEqual([(r["task"], r["open_asks"]) for r in data], [("LIN-4", [])])
        run("report", "--since", "main", "--summary", "pr.md")
        self.assertIn("### baton: LIN-4", (self.repo / "pr.md").read_text())

    def test_nothing_changed_and_bad_input(self):
        self.assertIn("no task boards changed since main", run("report", "--since", "main", "--strict"))
        for argv in (["report"], ["report", "missing.jsonl"], ["report", "--since", "no-such-ref"]):
            with self.assertRaises(SystemExit):
                run(*argv)
        bad = self.repo / "bad.jsonl"
        bad.write_text('{"truncated\n')
        with self.assertRaises(SystemExit) as cm:
            run("report", str(bad))
        self.assertIn("bad.jsonl:1: not a baton event", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
