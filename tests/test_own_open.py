import json
import os
import tempfile
import unittest
from pathlib import Path

from test_board import run

from baton import config
from baton.store import Board

HO = ("handoff", "--as", "backend", "--phase", "S1", "--state", "DONE", "--to", "qa")


class OwnOpenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        os.environ.pop("BATON_ROLE", None)
        run("init", "--root", str(self.root), "--sprint", "S1", "--roles", "orchestrator,backend,frontend,qa")
        run("post", "D", "--as", "backend", "--to", "all", "--title", "use cursors", "x")      # D-001
        run("post", "Q", "--as", "backend", "--to", "frontend", "--title", "paginated?", "x")  # Q-002
        run("post", "C", "--as", "backend", "--to", "qa", "--title", "shape", "--files", "a.ts", "x")  # C-003

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))

    def policy(self, value):
        path = self.root / ".baton/config.json"
        cfg = json.loads(path.read_text())
        cfg["handoff_own_open"] = value
        path.write_text(json.dumps(cfg))

    def handoff(self, *extra, title="done"):
        return run(*HO, "--title", title, *extra, "short")

    def refused(self, *extra):
        with self.assertRaises(SystemExit) as cm:
            self.handoff(*extra)
        return str(cm.exception.code)

    def test_warn_by_default_lists_d_q_b_but_not_c_or_h(self):
        out = self.handoff()
        self.assertIn("posted H-004", out)
        note = next(ln for ln in out.splitlines() if "you posted these" in ln)
        self.assertIn("D-001", note)
        self.assertIn("Q-002", note)
        self.assertNotIn("C-003", note)
        self.assertNotIn("H-004", note)
        out = self.handoff(title="again")  # the first hand-off (H) is never listed either
        self.assertNotIn("H-004", next(ln for ln in out.splitlines() if "you posted these" in ln))

    def test_closes_ids_are_excluded(self):
        out = self.handoff("--closes", "D-001")
        note = next(ln for ln in out.splitlines() if "you posted these" in ln)
        self.assertNotIn("D-001", note)
        self.assertIn("Q-002", note)
        out = self.handoff("--closes", "Q-002", title="two")
        self.assertNotIn("you posted these", out)

    def test_keep_open_is_recorded_and_not_listed(self):
        out = self.handoff("--keep-open", "D-001:waits for S2, qa owes the check")
        note = next(ln for ln in out.splitlines() if "you posted these" in ln)
        self.assertNotIn("D-001", note)
        h = self.board().get("H-004")
        self.assertEqual(h["keeps_open"], [{"id": "D-001", "reason": "waits for S2, qa owes the check"}])
        self.assertEqual(self.board().get("D-001")["status"], "OPEN")

    def test_keep_open_needs_a_reason_and_an_own_open_thread(self):
        with self.assertRaises(SystemExit):
            self.handoff("--keep-open", "D-001")
        with self.assertRaises(SystemExit):
            self.handoff("--keep-open", "C-003:contract")
        self.assertEqual([t["id"] for t in self.board().entries().values() if t["kind"] == "H"], [])

    def test_require_refuses_then_succeeds(self):
        self.policy("require")
        msg = self.refused()
        self.assertIn("D-001", msg)
        self.assertIn("Q-002", msg)
        self.assertIn("--closes", msg)
        self.assertIn("--keep-open", msg)
        self.assertNotIn("C-003", msg)
        self.assertEqual([t["id"] for t in self.board().entries().values() if t["kind"] == "H"], [])
        self.assertIn("Q-002", self.refused("--closes", "D-001"))  # still one loose
        out = self.handoff("--closes", "D-001", "--keep-open", "Q-002:frontend owes the answer")
        self.assertIn("posted H-004", out)
        self.assertNotIn("you posted these", out)

    def test_require_force_overrides(self):
        self.policy("require")
        self.assertIn("posted H-004", self.handoff("--force"))

    def test_bad_policy_value_is_refused(self):
        self.policy("sometimes")
        self.assertIn("handoff_own_open", self.refused())

    def test_mcp_passes_keep_open(self):
        from baton import mcp
        a = {"role": "backend", "phase": "S1", "state": "DONE", "to": ["qa"], "title": "t", "body": "b",
             "keep_open": ["D-001:why"]}
        self.assertIn("--keep-open=D-001:why", mcp._argv("baton_handoff", a, "f.txt"))


if __name__ == "__main__":
    unittest.main()
