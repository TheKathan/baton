import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from legacy import make_legacy

from baton import config
from baton.cli import main
from baton.store import Board

ID = re.compile(r"^[A-Z]-[0-9A-F]{4,}$")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        main(list(argv))
    return out.getvalue() + err.getvalue()


def posted(text):
    return re.search(r"posted ([A-Z]-[0-9A-F~]+)", text).group(1)


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check,
                          env={**os.environ, **GIT_ENV})


def _post_many(args):
    root, role, count = args
    board = Board(Path(root), config.load(Path(root)))
    return [board.post("Q", role, ["all"], f"q{i}", "body")["id"] for i in range(count)]


class TeamLayoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root), "--roles", "orchestrator,backend,frontend,qa")

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))

    def test_new_boards_use_the_team_layout(self):
        self.assertEqual(json.loads((self.root / ".baton/config.json").read_text())["format"], 2)
        q = posted(run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "t", "x"))
        self.assertRegex(q, ID)
        run("reply", q.lower(), "--as", "backend", "--close", "done")  # ids are case-insensitive
        run("status", "--as", "backend", "--phase", "S1", "--state", "building")
        clone = (self.root / ".baton/events/.clone-id").read_text().strip()
        log = self.root / f".baton/events/S1/{clone}.jsonl"
        events = [json.loads(ln) for ln in log.read_text().splitlines()]
        self.assertEqual([e["type"] for e in events], ["entry", "reply", "close", "status"])
        self.assertEqual([e["seq"] for e in events], [1, 2, 3, 4])
        self.assertTrue(all(e["v"] == 2 and e["origin"] == clone and e["uid"] == f"{clone}.{e['seq']}"
                            for e in events))
        self.assertFalse((self.root / ".baton/events/status.json").exists())  # status rows are events
        self.assertEqual(self.board().status()["backend"]["state"], "building")
        ignored = (self.root / ".baton/.gitignore").read_text().split()
        for view in ("BOARD.md", "STATUS.md", "CONTRACTS-INDEX.md", "archive/"):
            self.assertIn(view, ignored)
        self.assertIn(".clone-id", (self.root / ".baton/events/.gitignore").read_text().split())
        self.assertEqual(self.board().get(q)["status"], "CLOSED")

    def test_everyday_flow_still_works(self):
        q = posted(run("post", "Q", "--as", "qa", "--to", "backend", "--title", "need answer", "x"))
        with self.assertRaises(SystemExit):
            run("handoff", "--as", "backend", "--phase", "S1", "--state", "DONE", "--to", "qa", "--title", "h", "x")
        run("reply", q, "--as", "backend", "--close", "answered")
        h = posted(run("handoff", "--as", "backend", "--phase", "S1", "--state", "DONE", "--to", "qa",
                       "--title", "done", "x"))
        self.assertIn(f"| backend | S1 | DONE | {h} |", (self.root / ".baton/STATUS.md").read_text())
        self.assertIn("reply from backend", run("unread", "--as", "qa"))
        self.assertIn("0 unread", run("unread", "--as", "qa"))
        run("sprint", "S2")
        self.assertIn("posted Q-", run("post", "Q", "--as", "qa", "--title", "next", "x"))
        self.assertTrue((self.root / ".baton/archive/BOARD-S1.md").exists())
        self.assertIn("0 error(s)", run("lint"))
        self.assertIn("Threads", run("metrics"))

    def test_concurrent_posts_in_one_clone(self):
        with ProcessPoolExecutor(max_workers=6) as ex:
            batches = list(ex.map(_post_many, [(str(self.root), r, 10) for r in ("backend", "qa") * 3]))
        ids = [i for b in batches for i in b]
        self.assertEqual(len(set(ids)), 60)
        seqs = sorted(e["seq"] for e in self.board().events())
        self.assertEqual(seqs, list(range(1, 61)))

    def test_lint_reports_an_id_posted_from_two_clones(self):
        q = posted(run("post", "Q", "--as", "qa", "--title", "mine", "x"))
        other = self.root / ".baton/events/S1/0ther0.jsonl"
        other.write_text(json.dumps({"v": 2, "type": "entry", "id": q, "kind": "Q", "from": "backend",
                                     "to": ["all"], "title": "theirs", "body": "", "files": [], "cites": [],
                                     "blocks": [], "sprint": "S1", "ts": "2026-10-07 10:00", "origin": "0ther0",
                                     "seq": 1, "uid": "0ther0.1", "rec": "2026-10-07T08:00:00Z"}) + "\n")
        with self.assertRaises(SystemExit):
            run("lint")


class MigrateTeamTest(unittest.TestCase):
    def test_legacy_board_switches_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["BATON_ROOT"] = str(root)
            try:
                run("init", "--root", str(root), "--roles", "backend,qa")
                make_legacy(root)
                run("post", "Q", "--as", "qa", "--to", "backend", "--title", "old", "x")
                run("status", "--as", "backend", "--phase", "S1", "--state", "legacy row")
                run("unread", "--as", "backend")  # backend has read Q-001
                out = run("migrate", "--team")
                self.assertIn("switched to the team layout", out)
                self.assertIn("git rm -r -q --cached", out)
                b = Board(root, config.load(root))
                self.assertEqual(b.get("Q-001")["title"], "old")  # old ids and history kept
                self.assertEqual(b.status()["backend"]["state"], "legacy row")  # status carried over
                self.assertIn("0 unread", run("unread", "--as", "backend"))  # the cursor survives
                new = posted(run("post", "Q", "--as", "backend", "--to", "qa", "--title", "new", "x"))
                self.assertRegex(new, ID)
                self.assertIn("new", run("unread", "--as", "qa"))
                self.assertIn("nothing to migrate", run("migrate"))
            finally:
                os.environ.pop("BATON_ROOT", None)

    def test_newer_format_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run("init", "--root", str(root))
            cfg = json.loads((root / ".baton/config.json").read_text())
            cfg["format"] = 3
            (root / ".baton/config.json").write_text(json.dumps(cfg))
            os.environ["BATON_ROOT"] = str(root)
            try:
                with self.assertRaises(SystemExit) as cm:
                    run("list")
                self.assertIn("newer than this baton", str(cm.exception.code))
            finally:
                os.environ.pop("BATON_ROOT", None)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class TwoClonesTest(unittest.TestCase):
    """Two people, two clones, one repository: the scenario that conflicted before team mode."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.saved = os.environ.pop("BATON_ROOT", None)
        self.cwd = Path.cwd()
        git(base, "init", "-q", "--bare", "origin.git")
        seed = base / "seed"
        git(base, "clone", "-q", "origin.git", "seed")
        git(seed, "checkout", "-q", "-b", "main")
        run("init", "--root", str(seed), "--roles", "orchestrator,backend,frontend,qa")
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "board")
        git(seed, "push", "-q", "origin", "main")
        self.alice, self.bob = base / "alice", base / "bob"
        for clone in (self.alice, self.bob):
            git(base, "clone", "-q", "-b", "main", "origin.git", clone.name)

    def tearDown(self):
        os.chdir(self.cwd)
        if self.saved is not None:
            os.environ["BATON_ROOT"] = self.saved
        self.tmp.cleanup()

    def baton(self, clone, *argv):
        os.environ["BATON_ROOT"] = str(clone)
        try:
            return run(*argv)
        finally:
            os.environ.pop("BATON_ROOT", None)

    def commit_push(self, clone, msg):
        git(clone, "add", "-A")
        git(clone, "commit", "-q", "-m", msg)
        return git(clone, "pull", "-q", "--no-rebase", "origin", "main", check=False)

    def test_two_clones_post_and_merge_without_conflicts(self):
        a = posted(self.baton(self.alice, "post", "C", "--as", "backend", "--to", "frontend",
                              "--title", "API shape", "--files", "api.ts", "x"))
        self.baton(self.alice, "status", "--as", "backend", "--phase", "S1", "--state", "alice building")
        self.assertEqual(self.commit_push(self.alice, "alice").returncode, 0)
        git(self.alice, "push", "-q", "origin", "main")
        b = posted(self.baton(self.bob, "post", "Q", "--as", "backend", "--to", "qa",
                              "--title", "bob asks", "x"))
        self.baton(self.bob, "status", "--as", "qa", "--phase", "S1", "--state", "bob testing")
        merge = self.commit_push(self.bob, "bob")
        self.assertEqual(merge.returncode, 0, merge.stdout + merge.stderr)  # no conflict
        self.assertEqual(git(self.bob, "diff", "--name-only", "--diff-filter=U").stdout, "")
        self.assertNotEqual(a, b)
        listing = self.baton(self.bob, "list")
        self.assertIn(a, listing)
        self.assertIn(b, listing)
        status = self.baton(self.bob, "status")
        self.assertIn("alice building", status)
        self.assertIn("bob testing", status)
        # the same role on another clone is another agent: bob's backend sees alice's backend's contract
        self.assertIn("API shape", self.baton(self.bob, "unread", "--as", "backend"))
        tracked = git(self.bob, "ls-files", ".baton").stdout.split()
        self.assertFalse([f for f in tracked if f.endswith(".md")], tracked)  # views are not committed
        self.assertFalse([f for f in tracked if ".clone-id" in f or ".cursors" in f], tracked)
        self.assertIn("0 error(s)", self.baton(self.bob, "lint"))
        git(self.bob, "push", "-q", "origin", "main")
        git(self.alice, "pull", "-q", "--no-rebase", "origin", "main")
        self.assertIn("bob asks", self.baton(self.alice, "list"))


if __name__ == "__main__":
    unittest.main()
