import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from baton import config
from baton.cli import main
from baton.schema import SCHEMA_VERSION
from baton.store import Board, BoardError


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


class FormatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root), "--roles", "a,b")
        self.log = self.root / ".baton/events/S1.jsonl"

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))

    def test_new_events_and_config_carry_the_format_version(self):
        run("post", "Q", "--as", "a", "--title", "t", "x")
        run("reply", "Q-001", "--as", "b", "y")
        lines = [json.loads(ln) for ln in self.log.read_text().splitlines()]
        self.assertEqual([e["v"] for e in lines], [SCHEMA_VERSION] * 2)
        self.assertTrue(self.log.read_text().startswith('{"v": 1,'))
        self.assertEqual(json.loads((self.root / ".baton/config.json").read_text())["format"], 1)

    def test_0x_events_without_v_are_read_and_never_rewritten(self):
        legacy = {"type": "entry", "id": "Q-001", "kind": "Q", "n": 1, "from": "a", "to": ["all"],
                  "title": "old", "body": "", "files": [], "cites": [], "blocks": [], "ev": 1,
                  "sprint": "S1", "ts": "2026-10-01 10:00"}
        self.log.write_text(json.dumps(legacy) + "\n")
        before = self.log.read_text()
        self.assertEqual(self.board().get("Q-001")["title"], "old")
        self.assertIn("1 event(s) predate format tags", run("migrate", "--check"))
        run("post", "Q", "--as", "a", "--title", "new", "x")
        self.assertTrue(self.log.read_text().startswith(before))  # old line untouched
        self.assertIn("posted D-003", run("post", "D", "--as", "a", "--title", "n", "x"))

    def test_newer_event_format_is_refused(self):
        run("post", "Q", "--as", "a", "--title", "t", "x")
        with self.log.open("a") as f:
            f.write(json.dumps({"v": SCHEMA_VERSION + 1, "type": "reply", "id": "Q-001", "ev": 2,
                                "from": "b", "body": "?", "sprint": "S1", "ts": "x"}) + "\n")
        with self.assertRaises(BoardError) as cm:
            self.board().events()
        self.assertIn("newer baton", str(cm.exception))
        with self.assertRaises(SystemExit):
            run("list")

    def test_newer_config_format_is_refused(self):
        cfg = json.loads((self.root / ".baton/config.json").read_text())
        cfg["format"] = SCHEMA_VERSION + 1
        (self.root / ".baton/config.json").write_text(json.dumps(cfg))
        with self.assertRaises(SystemExit):
            run("list")

    def test_migrate_records_the_format_once(self):
        cfg = json.loads((self.root / ".baton/config.json").read_text())
        del cfg["format"]
        (self.root / ".baton/config.json").write_text(json.dumps(cfg))
        self.assertIn("1 (unset)", run("migrate", "--check"))
        self.assertIn("recorded format 1", run("migrate"))
        self.assertIn("nothing to migrate", run("migrate"))


if __name__ == "__main__":
    unittest.main()
