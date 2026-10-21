import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from baton import agentmodel, config, metrics, serve
from baton.cli import main
from baton.store import Board, BoardError

CLEAN = {"BATON_MODEL_DETECT": "0"}


def run(*argv, expect_error=False):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main(list(argv))
        except SystemExit as e:
            if not expect_error:
                raise
            err.write(str(e.code))
    return out.getvalue() + err.getvalue()


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        patch = mock.patch.dict(os.environ, {"BATON_MODEL_DETECT": "1"}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        for key in ("BATON_MODEL", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID",
                    "CLAUDE_CONFIG_DIR", "CODEX_HOME"):
            os.environ.pop(key, None)
        self.addCleanup(self.tmp.cleanup)

    def claude_session(self, *models, sid="0a1b2c3d-1111-2222-3333-444455556666"):
        folder = self.home / "claude" / "projects" / "-some-project"
        folder.mkdir(parents=True)
        (folder / f"{sid}.jsonl").write_text("".join(
            json.dumps({"type": "assistant", "message": {"model": m}}) + "\n" for m in models))
        os.environ.update(CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=sid, CLAUDE_CONFIG_DIR=str(self.home / "claude"))

    def codex_session(self, model, thread="01a15922-2673-7183-9a86-368276e1489a"):
        folder = self.home / "codex" / "sessions" / "2026" / "10" / "20"
        folder.mkdir(parents=True)
        (folder / f"rollout-2026-10-20T10-00-00-{thread}.jsonl").write_text(
            json.dumps({"type": "turn_context", "payload": {"model": model}}) + "\n")
        os.environ.update(CODEX_THREAD_ID=thread, CODEX_HOME=str(self.home / "codex"))

    def test_nothing_to_go_on(self):
        self.assertEqual(agentmodel.resolve(), {})

    def test_flag_beats_env_beats_detection(self):
        self.claude_session("claude-detected")
        self.assertEqual(agentmodel.resolve(), {"model": "claude-detected", "model_src": "detected"})
        os.environ["BATON_MODEL"] = "from-env"
        self.assertEqual(agentmodel.resolve(), {"model": "from-env", "model_src": "env"})
        self.assertEqual(agentmodel.resolve(" from-flag "), {"model": "from-flag", "model_src": "flag"})

    def test_claude_code_follows_the_latest_message(self):
        self.claude_session("claude-opus-5-5", "<synthetic>", "claude-sonnet-5-5")
        self.assertEqual(agentmodel.detect(), "claude-sonnet-5-5")

    def test_codex_is_found_by_its_thread(self):
        self.codex_session("gpt-test")
        self.assertEqual(agentmodel.detect(), "gpt-test")

    def test_codex_wins_when_it_runs_inside_claude_code(self):
        self.claude_session("claude-outer")
        self.codex_session("gpt-inner")
        self.assertEqual(agentmodel.detect(), "gpt-inner")

    def test_detection_can_be_switched_off(self):
        self.claude_session("claude-detected")
        os.environ["BATON_MODEL_DETECT"] = "0"
        self.assertEqual(agentmodel.resolve(), {})

    def test_a_session_id_cannot_point_outside_the_records(self):
        self.claude_session("claude-detected")
        os.environ["CLAUDE_CODE_SESSION_ID"] = "../../../etc/passwd"
        self.assertEqual(agentmodel.detect(), "")


class FlowTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, CLEAN)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("BATON_MODEL", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        self.addCleanup(os.environ.pop, "BATON_ROOT", None)
        run("init", "--root", str(self.root), "--roles", "orchestrator,backend,frontend,qa")

    def board(self):
        return Board(self.root, config.load(self.root))

    def events(self):
        return self.board().events()

    def test_writes_carry_the_model_that_wrote_them(self):
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "ready?", "--model", "claude-test", "ok")
        run("reply", "Q-1", "--as", "backend", "--model", "gpt-test", "yes")
        os.environ["BATON_MODEL"] = "env-model"
        run("close", "Q-1", "--as", "qa")
        got = [(e["type"], e.get("model"), e.get("model_src")) for e in self.events()]
        self.assertEqual(got, [("entry", "claude-test", "flag"), ("reply", "gpt-test", "flag"),
                               ("close", "env-model", "env")])

    def test_events_without_a_model_stay_as_before(self):
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "ready?", "ok")
        self.assertNotIn("model", self.events()[0])

    def test_handoff_stores_its_state_and_asks_for_a_model(self):
        said = run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE pending QA", "--to", "qa",
                   "--title", "backend done", "ok")
        self.assertIn("no model recorded", said)
        self.assertEqual(self.board().entries()["H-001"]["state"], "DONE pending QA")
        said = run("handoff", "--as", "qa", "--phase", "S1-A", "--state", "DONE", "--to", "all", "--title",
                   "qa done", "--model", "claude-test", "ok")
        self.assertNotIn("no model recorded", said)

    def test_the_receiver_judges_a_handoff_when_closing_it(self):
        run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE", "--to", "qa", "--title", "b", "ok")
        run("close", "H-1", "--as", "qa", "--outcome", "rework", "--reason", "tests fail")
        t = self.board().entries()["H-001"]
        self.assertEqual((t["closed_outcome"], t["closed_reason"]), ("rework", "tests fail"))

    def test_outcome_is_for_handoffs_and_must_be_known(self):
        run("post", "Q", "--as", "qa", "--to", "backend", "--title", "ready?", "ok")
        self.assertIn("judges a hand-off", run("close", "Q-1", "--as", "qa", "--outcome", "accepted",
                                                expect_error=True))
        self.assertEqual(self.board().entries()["Q-001"]["status"], "OPEN")
        self.assertIn("invalid choice", run("close", "Q-1", "--as", "qa", "--outcome", "great", expect_error=True))
        with self.assertRaises(BoardError):
            self.board().close("Q-1", "qa", "", "great")

    def test_handing_on_work_you_received_accepts_it(self):
        run("handoff", "--as", "backend", "--phase", "S1-A", "--state", "DONE", "--to", "qa", "--title", "b", "ok")
        run("handoff", "--as", "qa", "--phase", "S1-A", "--state", "DONE", "--to", "all", "--title", "q",
            "--closes", "H-1", "ok")
        self.assertEqual(self.board().entries()["H-001"]["closed_outcome"], "accepted")

    def stats(self):
        b = self.board()
        for i, (kind, frm, to, ts, extra) in enumerate([
                ("H", "backend", ["qa"], "2026-10-05 10:00", {"model": "m-a"}),
                ("Q", "qa", ["backend"], "2026-10-05 10:30", {"cites": ["H-001"], "model": "m-b"}),
                ("H", "qa", ["orchestrator"], "2026-10-05 12:00", {"model": "m-b"})], 1):
            b.append_raw({"type": "entry", "id": f"{kind}-{i:03d}", "kind": kind, "n": i, "from": frm, "to": to,
                          "title": "t", "body": "", "files": [], "cites": [], "blocks": [], "ts": ts, **extra})
        b.append_raw({"type": "close", "id": "H-001", "from": "orchestrator", "reason": "", "outcome": "rework",
                      "ts": "2026-10-05 12:30", "model": "m-c"})
        b.log_refusal("handoff", "backend", "H", "again", ["x"], ["Q-002"])
        b.log_refusal("handoff", "backend", "H", "again", ["x"], ["Q-002"], forced=True)
        return metrics.compute(self.board(), now=datetime(2026, 10, 5, 13, 0))

    def test_how_roles_behave_around_handoffs(self):
        m = self.stats()
        backend, qa = m["roles"]["backend"], m["roles"]["qa"]
        self.assertEqual((backend["handoffs_sent"], backend["rework"], backend["accepted"]), (1, 1, 0))
        self.assertEqual(backend["bounced"], 1)  # qa's question cites backend's hand-off
        self.assertEqual((backend["refused"], backend["forced"]), (1, 1))
        self.assertEqual(qa["hours_to_pickup"]["median"], 0.5)  # first event by qa after H-001
        self.assertEqual(qa["hours_held"]["median"], 2.0)  # H-001 received to H-003 sent
        self.assertEqual(m["roles"]["orchestrator"]["hours_to_pickup"]["median"], 0.5)  # H-003 to its close
        self.assertEqual(qa["models"], {"m-b": 2})

    def test_models_are_compared_by_what_their_handoffs_became(self):
        models = self.stats()["models"]
        self.assertEqual(models["m-a"], {"events": 1, "handoffs": 1, "accepted": 0, "rework": 1})
        self.assertEqual(models["m-b"], {"events": 2, "handoffs": 1, "accepted": 0, "rework": 0})
        self.assertEqual(models["m-c"]["events"], 1)

    def test_the_numbers_reach_the_text_and_the_pages(self):
        self.stats()
        text = run("metrics")
        self.assertIn("Hand-offs      sent  accepted  rework", text)
        self.assertIn("m-a", text)
        page = serve.metrics_page(self.board())
        for expected in ("Hand-offs by role", "By model", "m-a"):
            self.assertIn(expected, page)
        entry = serve.entry_page(self.board(), "H-001")
        self.assertIn("posted by backend with <code>m-a</code>", entry)
        self.assertIn("closed (rework) by orchestrator", entry)


if __name__ == "__main__":
    unittest.main()
