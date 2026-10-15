"""`baton demo`: a narrated walkthrough on a throwaway board, run through the real CLI."""

import os
import tempfile
import unittest
from pathlib import Path

from test_v11 import run

from baton import config
from baton.store import Board


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path.cwd()
        self.here = Path(self.tmp.name) / "here"
        self.here.mkdir()
        os.chdir(self.here)
        self.saved = os.environ.pop("BATON_ROOT", None)

    def tearDown(self):
        os.chdir(self.cwd)
        if self.saved is not None:
            os.environ["BATON_ROOT"] = self.saved
        self.tmp.cleanup()

    def test_fast_demo_shows_the_refusal_then_the_hand_off_and_leaves_nothing_behind(self):
        out = run("demo", "--fast")
        self.assertIn("hand-off refused", out)
        self.assertIn("Q-001", out)
        self.assertIn("posted H-002", out)
        self.assertIn("$ baton list", out)
        self.assertIn("baton skill install", out)
        self.assertNotIn("\033[", out)  # not a terminal: no colours
        self.assertEqual(list(self.here.iterdir()), [])
        self.assertNotIn("BATON_ROOT", os.environ)

    def test_keep_leaves_a_valid_board_and_refuses_an_existing_one(self):
        kept = Path(self.tmp.name) / "kept"
        out = run("demo", "--fast", "--keep", str(kept))
        self.assertIn(f"cd {kept.resolve()}", out)
        board = Board(kept, config.load(kept))
        self.assertEqual(board.get("Q-001")["status"], "CLOSED")
        self.assertEqual(board.get("H-002")["status"], "OPEN")
        self.assertEqual([r["what"] for r in board.refusals()], ["handoff"])
        with self.assertRaises(SystemExit):
            run("demo", "--fast", "--keep", str(kept))
        self.assertEqual(list(self.here.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
