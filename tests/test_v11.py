import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from legacy import make_legacy

from baton import config, metrics
from baton.cli import main
from baton.store import Board

SRC = str(Path(__file__).resolve().parent.parent / "src")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        main(list(argv))
    return out.getvalue() + err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root), "--roles", "orchestrator,backend,frontend,qa")
        make_legacy(self.root)

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def set_cfg(self, **kw):
        path = self.root / ".baton/config.json"
        cfg = json.loads(path.read_text())
        cfg.update(kw)
        path.write_text(json.dumps(cfg))

    def board(self):
        return Board(self.root, config.load(self.root))


class UtcTest(Base):
    def test_every_new_event_has_an_exact_utc_time(self):
        run("post", "Q", "--as", "frontend", "--to", "backend", "--title", "t", "x")
        run("reply", "Q-001", "--as", "backend", "--close", "y")
        events = [json.loads(ln) for ln in (self.root / ".baton/events/S1.jsonl").read_text().splitlines()]
        self.assertEqual(len(events), 3)
        for e in events:
            self.assertRegex(e["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        t = self.board().get("Q-001")
        self.assertIsNotNone(t["closed_at"])

    def test_metrics_prefer_at_over_ts(self):
        # ts says 2h apart (and is ambiguous across timezones); at says 30 minutes
        self.assertEqual(metrics.hours_between("2026-10-01 10:00", "2026-10-01 12:00",
                                               "2026-10-01T08:00:00Z", "2026-10-01T08:30:00Z"), 0.5)
        self.assertEqual(metrics.hours_between("2026-10-01 10:00", "2026-10-01 12:00"), 2.0)


class PolicyTest(Base):
    def test_refuse_and_warn(self):
        self.set_cfg(policies=[
            {"rule": "cites", "kinds": ["H"], "mode": "refuse"},
            {"rule": "named_to", "kinds": ["Q"], "mode": "warn"},
            {"rule": "title_match", "kinds": ["D"], "pattern": "^S\\d+", "mode": "refuse",
             "message": "decision titles start with the sprint"},
            {"rule": "max_lines", "kinds": ["B"], "lines": 2, "mode": "warn"},
        ])
        with self.assertRaises(SystemExit) as cm:
            run("handoff", "--as", "backend", "--phase", "S1", "--state", "DONE", "--to", "qa", "--title", "done", "x")
        self.assertIn("policy cites", str(cm.exception.code))
        self.assertEqual(self.board().entries(), {})  # nothing written
        self.assertIn("posted H-001", run("handoff", "--as", "backend", "--phase", "S1", "--state", "DONE",
                                          "--to", "qa", "--title", "done", "--cites", "STORY-1", "x"))
        out = run("post", "Q", "--as", "qa", "--to", "all", "--title", "anyone?", "x")
        self.assertIn("posted Q-002", out)
        self.assertIn("warning: policy named_to", out)
        with self.assertRaises(SystemExit) as cm:
            run("post", "D", "--as", "orchestrator", "--title", "scope", "x")
        self.assertIn("decision titles start with the sprint", str(cm.exception.code))
        self.assertIn("warning: policy max_lines",
                      run("post", "B", "--as", "qa", "--to", "backend", "--title", "b", "a\nb\nc"))
        self.assertIn("policy named_to", run("lint"))

    def test_bad_policy_config_is_reported(self):
        self.set_cfg(policies=[{"rule": "spellcheck"}])
        with self.assertRaises(SystemExit) as cm:
            run("list")
        self.assertIn("unknown rule", str(cm.exception.code))

    def test_policies_apply_through_mcp(self):
        self.set_cfg(policies=[{"rule": "cites", "kinds": ["Q"], "mode": "refuse"}])
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "baton_post", "arguments": {
            "role": "qa", "kind": "Q", "to": ["backend"], "title": "t", "body": "x"}}}
        r = subprocess.run([sys.executable, "-m", "baton", "mcp"], input=json.dumps(msg) + "\n", text=True,
                           capture_output=True, env={**os.environ, "PYTHONPATH": SRC}, timeout=60, check=False)
        res = json.loads(r.stdout.splitlines()[0])["result"]
        self.assertTrue(res["isError"])
        self.assertIn("policy cites", res["content"][0]["text"])


class McpKindsTest(Base):
    def test_post_tool_offers_the_configured_kinds(self):
        self.set_cfg(kinds={"Q": "question", "D": "decision", "H": "hand-off", "R": "risk"})
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        r = subprocess.run([sys.executable, "-m", "baton", "mcp"], input=json.dumps(msg) + "\n", text=True,
                           capture_output=True, env={**os.environ, "PYTHONPATH": SRC}, timeout=60, check=False)
        tools = {t["name"]: t for t in json.loads(r.stdout.splitlines()[0])["result"]["tools"]}
        self.assertEqual(tools["baton_post"]["inputSchema"]["properties"]["kind"]["enum"], ["Q", "D", "R"])


class ImportAnswersTest(Base):
    def test_answers_become_replies_and_closes(self):
        md = self.root / "old.md"
        md.write_text(
            "### [Q-007] backend → orchestrator · status: OPEN · 2026-10-02\n"
            "Can S2 rename the field?\n"
            "> [A] orchestrator · 2026-10-03 (re Q-007): Yes, in S2.\n"
            ">   announce it as a contract first\n"
            "> [A] backend · 2026-10-04: thanks, posting C-008. `> status: CLOSED by backend`\n\n"
            "### [B-009] qa → backend · status: CLOSED · 2026-10-05\nfixed elsewhere\n\n"
            "### [Q-010] qa → frontend · status: OPEN · 2026-10-06\nstill open\n")
        out = run("import", str(md), "--sprint", "S1")
        self.assertIn("imported 3 entries", out)
        self.assertIn("(2 answers as replies, 2 closed)", out)
        b = self.board()
        q = b.get("Q-007")
        self.assertEqual(q["body"], "Can S2 rename the field?")
        self.assertEqual([r["from"] for r in q["replies"]], ["orchestrator", "backend"])
        self.assertEqual(q["replies"][0]["body"], "Yes, in S2.\nannounce it as a contract first")
        self.assertEqual(q["replies"][0]["ts"], "2026-10-03")
        self.assertNotIn("status: CLOSED", q["replies"][1]["body"])
        self.assertEqual((q["status"], q["closed_by"]), ("CLOSED", "backend"))
        self.assertEqual(b.get("B-009")["status"], "CLOSED")
        self.assertEqual(b.get("Q-010")["status"], "OPEN")
        self.assertEqual([t["id"] for t in b.awaiting("frontend")], ["Q-010"])  # answered ones no longer count
        self.assertTrue(re.search(r"0 error", run("lint")))


if __name__ == "__main__":
    unittest.main()
