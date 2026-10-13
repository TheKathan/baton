"""Board health (v1.3): refusal log, closing by phase, supersedes, quiet contracts, suggestions."""

import json
import shutil
import unittest
from datetime import datetime, timedelta

import test_sandbox
from test_sandbox import git
from test_v11 import Base, run

from baton import metrics


def handoff(role, phase="S1-A", *extra):
    return run("handoff", "--as", role, "--phase", phase, "--state", "DONE", "--to", "qa",
               "--title", f"{phase} {role}", *extra, "x")


class RefusalLogTest(Base):
    def test_refusals_are_logged_locally_and_counted(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "which route?", "x")
        with self.assertRaises(SystemExit):
            handoff("backend")
        with self.assertRaises(SystemExit):
            run("post", "C", "--as", "backend", "--title", "no files", "x")
        board = self.board()
        rows = board.refusals()
        self.assertEqual([r["what"] for r in rows], ["handoff", "contract"])
        self.assertEqual(rows[0]["waiting"], ["Q-001"])
        self.assertIn(".local/", (self.root / ".baton/events/.gitignore").read_text())
        self.assertEqual(len(board.entries()), 1)  # the board holds only what was written
        r = metrics.compute(board)["summary"]["refusals"]
        self.assertEqual((r["refused"], r["handoffs_on_open_questions"], r["resolved_by_answering"]), (2, 1, 0))
        run("reply", "Q-001", "--as", "backend", "--close", "GET /api/health")
        handoff("backend")
        r = metrics.compute(self.board())["summary"]["refusals"]
        self.assertEqual(r["resolved_by_answering"], 1)
        self.assertIn("1 of 1 hand-offs refused on an open question were resolved", run("metrics"))

    def test_policy_refusals_and_forced_handoffs_are_logged(self):
        self.set_cfg(policies=[{"rule": "cites", "kinds": ["D"], "mode": "refuse"}])
        with self.assertRaises(SystemExit):
            run("post", "D", "--as", "orchestrator", "--title", "ruling", "x")
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "q", "x")
        handoff("backend", "S1-A", "--force")
        rows = self.board().refusals()
        self.assertEqual([(r["what"], r["forced"]) for r in rows], [("policy", False), ("handoff", True)])
        self.assertIn("1 forced with --force", run("metrics"))

    def test_a_damaged_log_line_is_ignored(self):
        path = self.board().refusals_path()
        path.parent.mkdir(parents=True)
        path.write_text('{"truncated\n')
        self.assertEqual(self.board().refusals(), [])
        self.assertIn("Refused        0 writes", run("metrics"))


class ClosingTest(Base):
    def test_hand_offs_record_their_phase_and_close_by_phase(self):
        handoff("backend", "S1-A")
        handoff("frontend", "S1-A")
        handoff("backend", "S1-B")
        self.assertEqual(self.board().get("H-001")["phase"], "S1-A")
        out = run("close", "--phase", "S1-A", "--as", "orchestrator", "--reason", "S1-A passed QA")
        self.assertIn("closed H-001", out)
        self.assertIn("closed H-002", out)
        self.assertEqual(self.board().get("H-003")["status"], "OPEN")
        self.assertIn("nothing to close", run("close", "--phase", "S1-A", "--as", "orchestrator"))

    def test_open_hand_offs_to_you_are_pointed_out(self):
        handoff("backend")
        brief = run("brief", "--as", "qa")
        self.assertIn("Hand-offs to you, still open (1)", brief)
        self.assertIn("H-001", brief)
        out = run("handoff", "--as", "qa", "--phase", "S1-A", "--state", "PASS", "--to", "orchestrator",
                  "--title", "S1-A gate", "x")
        self.assertIn("hand-offs to you are still open", out)
        self.assertIn("H-001 (backend)", out)
        out = run("handoff", "--as", "qa", "--phase", "S1-A", "--state", "PASS", "--to", "orchestrator",
                  "--title", "S1-A gate", "--closes", "H-001", "x")
        self.assertNotIn("still open", out)
        self.assertNotIn("Hand-offs to you", run("brief", "--as", "qa"))


class SupersedesTest(Base):
    def test_a_new_contract_supersedes_and_closes_the_old_one(self):
        run("post", "C", "--as", "backend", "--title", "v1 shape", "--files", "api.ts", "x")
        out = run("post", "C", "--as", "backend", "--title", "v2 shape", "--files", "api.ts",
                  "--supersedes", "C-001", "x")
        self.assertIn("posted C-002; closed C-001 as superseded", out)
        b = self.board()
        self.assertEqual(b.get("C-001")["closed_reason"], "superseded by C-002")
        self.assertEqual(b.get("C-002")["supersedes"], ["C-001"])
        self.assertEqual(b.get("C-002")["cites"], ["C-001"])

    def test_bad_supersedes_writes_nothing(self):
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "q", "x")
        for argv in (["C", "--supersedes", "Q-001"], ["C", "--supersedes", "C-404"], ["D", "--supersedes", "Q-001"]):
            with self.assertRaises(SystemExit):
                run("post", argv[0], "--as", "backend", "--title", "t", "--files", "a.ts", *argv[1:], "x")
        self.assertEqual(len(self.board().entries()), 1)


class QuietContractTest(Base):
    def test_open_contracts_are_not_stale_but_quiet(self):
        run("post", "C", "--as", "backend", "--title", "shape", "--files", "api.ts", "x")
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "q", "x")
        later = datetime.now() + timedelta(days=3)
        s = metrics.compute(self.board(), now=later)["summary"]
        self.assertEqual(s["stale_ids"], ["Q-002"])
        self.assertEqual(s["quiet_contract_ids"], ["C-001"])
        run("post", "D", "--as", "frontend", "--title", "build on it", "--cites", "C-001", "x")
        s = metrics.compute(self.board(), now=datetime.now() + timedelta(hours=1))["summary"]
        self.assertEqual(s["quiet_contract_ids"], [])


class LintTest(Base):
    def test_suggests_policies_the_board_already_follows(self):
        for i in range(6):
            handoff("backend", f"S1-{i}", "--cites", f"SW-{i}")
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "q", "x")
        out = run("lint", "--suggest")
        self.assertIn("cites for H: 100% of 6 H entries cite an id → refuse", out)
        self.assertIn("title_match for H", out)
        snippet = json.loads(out.split('"policies": ', 1)[1])
        self.assertIn({"rule": "cites", "kinds": ["H"], "mode": "refuse"}, snippet)
        self.set_cfg(policies=[{"rule": "cites", "kinds": ["H"], "mode": "warn"}])
        self.assertNotIn("cites for H", run("lint", "--suggest"))  # already covered

    def test_no_suggestions_on_a_small_board(self):
        handoff("backend")
        self.assertIn("no suggestions", run("lint", "--suggest"))


@unittest.skipUnless(shutil.which("git"), "git not installed")
class SandboxInheritsTest(unittest.TestCase):  # SandboxTest's repo fixture, without its tests
    setUp, tearDown, = test_sandbox.SandboxTest.setUp, test_sandbox.SandboxTest.tearDown

    def test_sandbox_takes_the_projects_policies_and_roles(self):
        run("init", "--roles", "orchestrator,backend,qa")
        cfg_path = self.repo / ".baton/config.json"
        cfg = json.loads(cfg_path.read_text())
        cfg["policies"] = [{"rule": "cites", "kinds": ["H"], "mode": "refuse"}]
        cfg_path.write_text(json.dumps(cfg))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "board")
        out = run("init", "--sandbox", "--task", "LIN-5")
        self.assertIn("policies, kinds, roles from .baton/config.json", out)
        with self.assertRaises(SystemExit) as cm:
            run("handoff", "--as", "backend", "--phase", "LIN-5", "--state", "DONE", "--to", "qa",
                "--title", "done", "x")
        self.assertIn("policy cites", str(cm.exception.code))
        with self.assertRaises(SystemExit):
            run("post", "Q", "--as", "nobody", "--to", "qa", "--title", "q", "x")  # roles inherited
        run("handoff", "--as", "backend", "--phase", "LIN-5", "--state", "DONE", "--to", "qa",
            "--title", "done", "--cites", "LIN-5", "x")
        self.assertIn("baton refused 1 write(s) in this sandbox", run("finish"))
        self.assertEqual(git(self.repo, "status", "--porcelain").stdout.split(), ["??", ".baton/tasks/"])


if __name__ == "__main__":
    unittest.main()
