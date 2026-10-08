import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from baton.cli import main

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
ROLES = "orchestrator,backend,qa"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        main(list(argv))
    return out.getvalue() + err.getvalue()


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check,
                          env={**os.environ, **GIT_ENV})


@unittest.skipUnless(shutil.which("git"), "git not installed")
class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "app.tf").write_text("x\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")
        self.saved = os.environ.pop("BATON_ROOT", None)
        self.cwd = Path.cwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.cwd)
        if self.saved is not None:
            os.environ["BATON_ROOT"] = self.saved
        self.tmp.cleanup()

    def wipe_sandbox(self):  # a fresh sandbox: only the committed tree exists
        shutil.rmtree(self.repo / ".baton/sandbox", ignore_errors=True)
        (self.repo / ".baton/sandbox.json").unlink(missing_ok=True)

    def test_task_board_lifecycle(self):
        self.assertIn("new task board", run("init", "--sandbox", "--task", "LIN-123", "--roles", ROLES))
        self.assertEqual(json.loads((self.repo / ".baton/sandbox.json").read_text())["task"], "LIN-123")
        self.assertEqual(git(self.repo, "status", "--porcelain").stdout, "")  # the live board is excluded
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "need a table?", "x")
        with self.assertRaises(SystemExit):  # the usual rules apply
            run("handoff", "--as", "backend", "--phase", "LIN-123", "--state", "DONE", "--to", "qa",
                "--title", "h", "x")
        with self.assertRaises(SystemExit):  # --strict refuses while a question is open
            run("finish", "--strict")
        run("reply", "Q-001", "--as", "backend", "--close", "yes")
        run("post", "C", "--as", "backend", "--title", "route table input", "--files", "net/vars.tf", "x")
        run("handoff", "--as", "backend", "--phase", "LIN-123", "--state", "DONE", "--to", "qa", "--title", "done", "x")
        out = run("finish", "--strict")
        self.assertIn("wrote .baton/tasks/LIN-123.jsonl (5 events, 3 threads)", out)
        self.assertIn("### baton: LIN-123", out)
        self.assertIn("**C-002** route table input (files: net/vars.tf)", out)
        events = [json.loads(ln) for ln in (self.repo / ".baton/tasks/LIN-123.jsonl").read_text().splitlines()]
        self.assertEqual(len(events), 5)
        self.assertTrue(all(e["task"] == "LIN-123" for e in events))
        self.assertEqual(git(self.repo, "status", "--porcelain").stdout.split(), ["??", ".baton/"])
        git(self.repo, "add", "-A")
        self.assertEqual(git(self.repo, "diff", "--cached", "--name-only").stdout.split(),
                         [".baton/tasks/LIN-123.jsonl"])  # only the export goes in the PR

    def test_a_second_sandbox_resumes_the_task(self):
        run("init", "--sandbox", "--task", "LIN-7", "--roles", ROLES)
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "first run", "x")
        run("finish")
        self.wipe_sandbox()
        self.assertIn("resumed 1 event(s)", run("init", "--sandbox", "--task", "LIN-7", "--roles", ROLES))
        self.assertIn("first run", run("show", "Q-001"))
        self.assertIn("0 unread", run("unread", "--as", "backend"))  # history isn't replayed
        self.assertIn("posted Q-002", run("post", "Q", "--as", "qa", "--to", "backend", "--title", "next", "x"))
        run("finish")
        lines = (self.repo / ".baton/tasks/LIN-7.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(ln)["id"] for ln in lines], ["Q-001", "Q-002"])

    def test_live_contracts_from_merged_tasks(self):
        git(self.repo, "checkout", "-q", "-b", "fix/LIN-124")
        run("init", "--sandbox", "--task", "LIN-124", "--roles", ROLES)
        run("post", "C", "--as", "backend", "--title", "subnet input", "--files", "modules/network/subnet/vars.tf", "x")
        run("post", "C", "--as", "backend", "--title", "old shape", "--files", "modules/old.tf", "x")
        run("close", "C-002", "--as", "backend", "--reason", "superseded")
        run("finish")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "LIN-124")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "fix/LIN-124", "-m", "merge")
        self.wipe_sandbox()
        git(self.repo, "checkout", "-q", "-b", "fix/LIN-123")
        run("init", "--sandbox", "--task", "LIN-123", "--roles", ROLES)
        brief = run("brief", "--as", "backend")
        self.assertIn("Live contracts from other tasks (1)", brief)
        self.assertIn("LIN-124/C-001 · subnet input", brief)
        self.assertNotIn("old shape", brief)  # closed contracts aren't live
        self.assertIn("LIN-124/C-001", run("contracts", "--paths", "modules/network/**"))
        self.assertIn("0 from other tasks", run("contracts", "--paths", "docs/**"))
        (self.repo / ".baton/tasks/BROKEN.jsonl").write_text('{"truncated\n')
        self.assertIn("LIN-124/C-001", run("contracts"))  # a damaged export never blocks a task

    def test_validation(self):
        with self.assertRaises(SystemExit):
            run("init", "--sandbox", "--roles", ROLES)  # --task is required
        with self.assertRaises(SystemExit):
            run("init", "--sandbox", "--task", "../etc", "--roles", ROLES)
        run("init", "--sandbox", "--task", "LIN-1", "--roles", ROLES)
        with self.assertRaises(SystemExit):
            run("init", "--sandbox", "--task", "LIN-1", "--roles", ROLES)  # already there
        self.assertIn("new task board", run("init", "--sandbox", "--task", "LIN-1", "--roles", ROLES, "--force"))

    def test_finish_needs_a_sandbox_board(self):
        run("init", "--roles", ROLES)  # a normal project board
        with self.assertRaises(SystemExit):
            run("finish")

    def test_sandbox_takes_precedence_over_a_project_board(self):
        run("init", "--roles", ROLES)
        run("init", "--sandbox", "--task", "LIN-9", "--roles", ROLES)
        run("post", "D", "--as", "orchestrator", "--title", "sandbox only", "x")
        self.assertEqual(list((self.repo / ".baton/events").glob("*.jsonl")), [])  # project board untouched
        self.assertIn("sandbox only", run("list"))


if __name__ == "__main__":
    unittest.main()
