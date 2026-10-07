import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from legacy import make_legacy

from baton import config
from baton.cli import main


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


@unittest.skipUnless(shutil.which("git"), "git not installed")
class SharedWorktreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.main, self.wt = base / "main", base / "wt"
        self.main.mkdir()
        self.saved_root = os.environ.pop("BATON_ROOT", None)
        self.cwd = Path.cwd()
        git(self.main, "init", "-q", "-b", "main")
        run("init", "--root", str(self.main), "--roles", "backend,qa")
        make_legacy(self.main)
        git(self.main, "add", "-A")
        git(self.main, "commit", "-q", "-m", "board")
        git(self.main, "worktree", "add", "-q", str(self.wt), "-b", "feature/x")

    def tearDown(self):
        os.chdir(self.cwd)
        if self.saved_root is not None:
            os.environ["BATON_ROOT"] = self.saved_root
        self.tmp.cleanup()

    def events(self, root):
        return [json.loads(ln) for p in sorted((root / ".baton/events").glob("*.jsonl"))
                for ln in p.read_text().splitlines() if ln.strip()]

    def test_worktree_writes_go_to_the_main_board(self):
        os.chdir(self.wt / "")
        self.assertEqual(config.locate(), (self.main, self.wt))
        self.assertIn("posted Q-001", run("post", "Q", "--as", "backend", "--to", "qa", "--title", "from wt", "x"))
        os.chdir(self.main)
        self.assertIn("posted Q-002", run("post", "Q", "--as", "qa", "--to", "backend", "--title", "from main", "x"))
        self.assertEqual([e["id"] for e in self.events(self.main)], ["Q-001", "Q-002"])
        self.assertEqual(self.events(self.wt), [])  # the worktree's committed copy is untouched
        os.chdir(self.wt)
        where = json.loads(run("where"))
        self.assertEqual(where["root"], str(self.main))
        self.assertEqual(where["shared_from_worktree"], str(self.wt))

    def test_subdirectory_of_a_worktree_is_redirected_too(self):
        sub = self.wt / "src" / "deep"
        sub.mkdir(parents=True)
        self.assertEqual(config.locate(sub)[0], self.main)

    def test_main_worktree_and_opt_out(self):
        self.assertEqual(config.locate(self.main), (self.main, None))
        cfg = json.loads((self.wt / ".baton/config.json").read_text())
        cfg["shared_worktrees"] = False
        (self.wt / ".baton/config.json").write_text(json.dumps(cfg))
        self.assertEqual(config.locate(self.wt), (self.wt, None))

    def test_baton_root_still_wins(self):
        os.environ["BATON_ROOT"] = str(self.wt)
        try:
            self.assertEqual(config.locate(self.wt), (self.wt, None))
        finally:
            del os.environ["BATON_ROOT"]


if __name__ == "__main__":
    unittest.main()
