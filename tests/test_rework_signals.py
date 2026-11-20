"""Fix rounds (`handoff --fixes`), questions to idle roles, and work dispatched outside the board."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from baton import config, mcp, metrics, serve
from baton.cli import main
from baton.store import Board


def run(*argv, err=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err or io.StringIO()):
        main(list(argv))
    return out.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root), "--roles", "orchestrator,backend,qa,docs")
        self.n = 0

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))

    def entry(self, kind, frm, to, ts, **kw):
        self.n += 1
        i = f"{kind}-{self.n:03d}"
        self.board().append_raw({"type": "entry", "id": i, "kind": kind, "n": self.n, "from": frm, "to": to,
                                 "title": kw.get("title", "t"), "body": "", "files": [], "cites": [],
                                 "blocks": [], "ts": ts, **kw.get("extra", {})})
        return i


class FixesTest(Base):
    def handoff(self, *extra):
        return run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE", "--to", "qa",
                   "--title", "work", *extra, "--", "x")

    def test_fixes_is_stored_cited_and_validated(self):
        self.handoff()  # H-001
        run("post", "Q", "--as", "qa", "--to", "orchestrator", "--title", "q", "--", "x")  # Q-002
        self.assertIn("posted H-003", self.handoff("--fixes", "h-1", "--cites", "STORY-9"))
        t = self.board().get("H-003")
        self.assertEqual(t["fixes"], ["H-001"])
        self.assertEqual(t["cites"], ["STORY-9", "H-001"])
        self.assertNotIn("fixes", self.board().get("H-001"))  # the earlier hand-off is not rewritten
        for bad, msg in (("Q-002", "not a hand-off"), ("H-099", "no such entry")):
            with self.assertRaises(SystemExit) as e:
                self.handoff("--fixes", bad)
            self.assertIn(msg, str(e.exception.code))
        self.assertEqual(len([t for t in self.board().entries().values() if t["kind"] == "H"]), 2)

    def test_fixed_later_counts_the_senders_hand_offs(self):
        self.handoff()  # H-001, accepted by qa
        run("close", "H-001", "--as", "qa", "--outcome", "accepted")
        self.handoff()  # H-002, never fixed
        self.handoff("--fixes", "H-001")  # H-003
        self.handoff("--fixes", "H-001")  # a second round on the same hand-off counts it once
        m = metrics.compute(self.board())
        r = m["roles"]["backend"]
        self.assertEqual((r["handoffs_sent"], r["accepted"], r["rework"], r["fixed_later"]), (4, 1, 0, 1))
        self.assertEqual(m["roles"]["qa"]["fixed_later"], 0)
        self.assertIn("fixed later", metrics.format_text(m))
        self.assertIn('"fixed_later": 1', run("metrics", "--json"))

    def test_mcp_handoff_takes_fixes(self):
        tool = next(t for t in mcp.TOOLS if t["name"] == "baton_handoff")
        self.assertEqual(tool["inputSchema"]["properties"]["fixes"]["type"], "array")
        argv = mcp._argv("baton_handoff", {"role": "backend", "phase": "S1", "state": "DONE", "to": ["qa"],
                                           "title": "t", "body": "x", "fixes": ["H-001", "H-004"]}, "/tmp/b")
        self.assertIn("--fixes=H-001,H-004", argv)


class IdleAddresseeTest(Base):
    now = datetime(2026, 10, 10, 12, 0)

    def ids(self, now=None):
        return [x["id"] for x in metrics.compute(self.board(), now=now or self.now)["summary"]["idle_addressees"]]

    def test_done_and_quiet_is_listed(self):
        self.entry("H", "docs", ["orchestrator"], "2026-10-01 09:00")
        self.board().set_status("docs", "S1", "DONE pending QA", "H-001")
        q = self.entry("Q", "backend", ["docs"], "2026-10-09 09:00")
        self.assertEqual(self.ids(), [q])
        s = metrics.compute(self.board(), now=self.now)
        self.assertEqual(s["summary"]["idle_addressees"], [{"id": q, "to": ["docs"]}])
        self.assertIn(f"Idle addressee  1 open question(s) to a role with no running agent: {q} (docs)",
                      metrics.format_text(s))

    def test_recent_activity_or_a_working_status_is_not_idle(self):
        self.board().set_status("docs", "S1", "DONE", "")
        self.board().set_status("qa", "S1", "working", "")
        self.entry("D", "docs", ["all"], "2026-10-10 08:00")  # docs wrote 4h ago
        self.entry("Q", "backend", ["docs"], "2026-10-01 09:00")
        self.entry("Q", "backend", ["qa"], "2026-10-01 09:00")  # qa never wrote, but it is working
        self.assertEqual(self.ids(), [])
        self.assertEqual(self.ids(datetime(2026, 10, 13, 12, 0)), ["Q-002"])  # 76h later docs is idle

    def test_all_is_ignored_and_every_named_role_must_be_idle(self):
        self.board().set_status("backend", "S1", "working", "")
        bcast = self.entry("Q", "orchestrator", ["all"], "2026-10-01 09:00")
        both = self.entry("Q", "orchestrator", ["docs", "all"], "2026-10-01 09:00")
        mixed = self.entry("B", "orchestrator", ["docs", "backend"], "2026-10-01 09:00")
        pair = self.entry("Q", "orchestrator", ["docs", "qa"], "2026-10-01 09:00")
        answered = self.entry("Q", "orchestrator", ["qa"], "2026-10-01 09:00")
        self.board().append_raw({"type": "reply", "id": answered, "from": "qa", "body": "y", "ts": "2026-10-01 10:00"})
        ids = self.ids()
        self.assertNotIn(bcast, ids)
        self.assertNotIn(mixed, ids)
        self.assertNotIn(answered, ids)
        self.assertEqual(ids, [both, pair])

    def test_sprint_rollover_notes_idle_addressees(self):
        self.entry("Q", "backend", ["docs"], "2026-01-01 09:00")
        err = io.StringIO()
        run("sprint", "S2", err=err)
        self.assertIn("note: 1 open question(s) wait on a role with no running agent", err.getvalue())
        self.assertIn("Q-001 (docs)", err.getvalue())
        self.assertIn("Answer, reassign or close them", err.getvalue())
        run("close", "Q-001", "--as", "backend", "--reason", "moot")
        err = io.StringIO()
        run("sprint", "S3", err=err)
        self.assertNotIn("no running agent", err.getvalue())


class DispatchTest(Base):
    def test_hint_shows_when_hand_offs_only_flow_to_the_orchestrator(self):
        self.entry("H", "backend", ["orchestrator"], "2026-10-01 09:00")
        m = metrics.compute(self.board())
        self.assertEqual(m["dispatch"], {"sprint": "S1", "to_orchestrator": 1, "from_orchestrator": 0,
                                         "off_board": True})
        self.assertIn("builders seem briefed outside the board", metrics.format_text(m))
        self.assertTrue(json.loads(run("metrics", "--json"))["dispatch"]["off_board"])
        self.assertIn("they seem to be briefed outside the board", serve.metrics_page(self.board()))

    def test_no_hint_when_the_orchestrator_dispatches_or_nothing_was_handed_off(self):
        self.assertFalse(metrics.compute(self.board())["dispatch"]["off_board"])
        self.entry("H", "backend", ["orchestrator"], "2026-10-01 09:00")
        self.entry("H", "orchestrator", ["backend"], "2026-10-01 08:00")
        m = metrics.compute(self.board())
        self.assertFalse(m["dispatch"]["off_board"])
        self.assertNotIn("Dispatch", metrics.format_text(m))
        self.assertNotIn("briefed outside the board", serve.metrics_page(self.board()))


class DashboardTest(Base):
    def test_idle_group_sits_between_blocked_and_unanswered_and_lists_each_thread_once(self):
        now = datetime(2026, 10, 10, 12, 0)
        blocker = self.entry("B", "backend", ["docs"], "2026-10-01 09:00")  # blocked and idle
        q = self.entry("Q", "backend", ["docs"], "2026-10-01 09:00")  # idle, unanswered and stale
        self.entry("Q", "docs", ["backend"], "2026-10-01 08:00")  # unanswered and stale; backend is active
        self.board().set_status("backend", "S1", "working", "")
        page = serve.metrics_page(self.board(), now)
        att = page.split('id="attention"', 1)[1].split("</section>", 1)[0]
        order = [att.index(f'id="{g}"') for g in ("blocked", "idle", "unanswered", "stale")]
        self.assertEqual(order, sorted(order))
        self.assertIn("To an idle role", att)
        self.assertEqual(att.count(f'href="/e/{q}"'), 1)
        self.assertEqual(att.count(f'href="/e/{blocker}"'), 1)
        idle = att.split('id="idle"', 1)[1].split('id="unanswered"', 1)[0]
        self.assertIn(f'href="/e/{q}"', idle)
        self.assertIn("1 listed above", idle)  # the blocker
        self.assertIn("To an idle role", page.split('id="defs"', 1)[1])  # defined in How to read this
        self.assertIn("Fixed later", page.split('id="defs"', 1)[1])


if __name__ == "__main__":
    unittest.main()
