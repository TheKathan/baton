import os
import tempfile
import unittest
from pathlib import Path

from test_board import run

from baton import config
from baton.store import Board

HO = ("handoff", "--as", "orchestrator", "--phase", "S1", "--state", "DONE", "--to", "qa", "--title", "t")


class CarryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        os.environ.pop("BATON_ROLE", None)
        run("init", "--root", str(self.root), "--sprint", "S1", "--roles", "orchestrator,backend,qa")
        run("post", "Q", "--as", "backend", "--to", "orchestrator", "--title", "retention?", "x")  # Q-001
        run("post", "Q", "--as", "backend", "--to", "orchestrator", "--title", "other", "x")      # Q-002

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))

    def handoff(self, *extra):
        return run(*HO, *extra, "short")

    def refused(self, *extra):
        with self.assertRaises(SystemExit) as cm:
            self.handoff(*extra)
        return str(cm.exception.code)

    def test_refusal_bypassed_only_for_listed_ids(self):
        self.assertIn("Q-001", self.refused())
        msg = self.refused("--keep-open", "Q-001:owner decides")
        self.assertIn("Q-002", msg)
        self.assertNotIn("Q-001,", msg.split("addressed to you:")[1].split("\n")[0] + ",")
        self.assertIn("posted H-003", self.handoff("--keep-open", "Q-001:owner decides",
                                                  "--keep-open", "Q-002:owner too"))

    def test_keep_open_records_reason_and_carries(self):
        self.handoff("--keep-open", "Q-001:owner decides", "--keep-open", "Q-002:same")
        b = self.board()
        self.assertEqual(b.get("H-003")["keeps_open"][0], {"id": "Q-001", "reason": "owner decides"})
        self.assertEqual(b.get("Q-001")["carried"]["reason"], "owner decides")
        self.assertEqual(b.get("Q-001")["status"], "OPEN")
        self.assertEqual(b.awaiting("orchestrator"), [])
        self.assertIn("posted H-004", self.handoff())  # later hand-offs are no longer blocked

    def test_carried_survives_close_sprint_and_normal_close_works(self):
        run("carry", "Q-001", "--as", "orchestrator", "--reason", "owner decision pending", "--until", "S3")
        run("reply", "Q-002", "--as", "orchestrator", "ok")
        out = run("close", "--sprint", "S1", "--as", "orchestrator", "--reason", "gate")
        self.assertIn("carried", out)
        self.assertEqual(self.board().get("Q-001")["status"], "OPEN")
        self.assertEqual(self.board().get("Q-002")["status"], "CLOSED")
        self.assertIn("closed Q-001", run("close", "Q-001", "--as", "orchestrator", "--reason", "decided"))
        self.assertEqual(self.board().get("Q-001")["status"], "CLOSED")

    def test_carry_even_when_replied_to(self):
        run("reply", "Q-001", "--as", "orchestrator", "deferring")
        run("carry", "Q-001", "--as", "orchestrator", "--reason", "owner")
        run("close", "--sprint", "S1", "--as", "orchestrator", "--reason", "gate")
        self.assertEqual(self.board().get("Q-001")["status"], "OPEN")

    def test_open_and_brief_show_it(self):
        run("carry", "Q-001", "--as", "orchestrator", "--reason", "owner decision pending", "--until", "S3")
        self.assertIn("carried: owner decision pending", run("open", "--as", "orchestrator"))
        brief = run("brief", "--as", "qa")
        self.assertIn("Carried", brief)
        self.assertIn("owner decision pending", brief)
        self.assertIn("until S3", brief)
        self.assertNotIn("[Q-001]", run("brief", "--as", "orchestrator").split("## Carried")[0])

    def test_carry_refusals(self):
        with self.assertRaises(SystemExit):
            run("carry", "Q-001", "--as", "orchestrator", "--reason", " ")
        run("post", "D", "--as", "backend", "--to", "all", "--title", "d", "x")
        with self.assertRaises(SystemExit):
            run("carry", "D-003", "--as", "orchestrator", "--reason", "no")
        with self.assertRaises(SystemExit):  # keep-open must still name a known thread
            self.handoff("--keep-open", "Q-099:x")

    def test_unread_shows_carry_event(self):
        run("carry", "Q-001", "--as", "orchestrator", "--reason", "owner")
        self.assertIn("CARRIED by orchestrator", run("unread", "--as", "backend"))

    def test_backward_compatible(self):
        self.assertIn("Q-001", self.refused())  # no flag: same refusal as before
        run("reply", "Q-001", "--as", "orchestrator", "--close", "done")
        run("reply", "Q-002", "--as", "orchestrator", "--close", "done")
        self.assertIn("posted H-003", self.handoff())
        self.assertIsNone(self.board().get("Q-001").get("carried"))

    def test_mcp_carry(self):
        from baton import mcp
        argv = mcp._argv("baton_carry", {"role": "orchestrator", "ids": ["Q-1"], "reason": "r", "until": "S3"}, None)
        self.assertEqual(argv, ["carry", "--as=orchestrator", "--reason=r", "--until=S3", "--", "Q-1"])
        self.assertIn("baton_carry", [t["name"] for t in mcp.TOOLS])


if __name__ == "__main__":
    unittest.main()
