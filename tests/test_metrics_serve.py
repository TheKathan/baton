import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from baton import config, metrics, serve
from baton.cli import main
from baton.store import Board


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root), "--roles", "orchestrator,backend,frontend,qa")
        b = self.board()
        n = iter(range(1, 100))

        def entry(kind, frm, to, title, ts, **kw):
            i = next(n)
            b.append_raw({"type": "entry", "id": f"{kind}-{i:03d}", "kind": kind, "n": i, "from": frm,
                          "to": to, "title": title, "body": "", "files": kw.get("files", []), "cites": [],
                          "blocks": [], "ts": ts})
            return f"{kind}-{i:03d}"
        # Q-001 answered after 2h and closed after 4h; Q-002 unanswered; B-003 open blocker
        q1 = entry("Q", "frontend", ["backend"], "paginated?", "2026-10-01 10:00")
        b.append_raw({"type": "reply", "id": q1, "from": "backend", "body": "no", "ts": "2026-10-01 12:00"})
        b.append_raw({"type": "close", "id": q1, "from": "frontend", "reason": "", "ts": "2026-10-01 14:00"})
        entry("Q", "qa", ["frontend"], "badge <script>alert(1)</script>?", "2026-10-02 09:00")
        entry("B", "qa", ["backend"], "500 on runs", "2026-10-05 08:00")
        self.now = datetime(2026, 10, 5, 10, 0)  # noqa: DTZ001 - board times are naive local

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def board(self):
        return Board(self.root, config.load(self.root))


class MetricsTest(Base):
    def test_durations(self):
        self.assertEqual(metrics.parse_duration("2d"), 48)
        self.assertEqual(metrics.parse_duration("90m"), 1.5)
        self.assertEqual(metrics.parse_duration("36"), 36)
        with self.assertRaises(ValueError):
            metrics.parse_duration("soon")

    def test_compute(self):
        m = metrics.compute(self.board(), now=self.now)
        s = m["summary"]
        self.assertEqual((s["entries"], s["open"], s["closed"]), (3, 2, 1))
        self.assertEqual(s["hours_to_first_answer"], {"n": 1, "median": 2.0, "p90": 2.0})
        self.assertEqual(s["hours_to_close"]["median"], 4.0)
        self.assertEqual(s["unanswered_open"], 2)
        self.assertEqual(s["stale_ids"], ["Q-002"])  # idle 73h; B-003 only 2h
        self.assertEqual(m["roles"]["backend"]["answered"], 1)
        self.assertEqual(m["roles"]["backend"]["asked_of"], 2)
        self.assertEqual(m["roles"]["frontend"]["waiting_on"], 1)
        self.assertGreater(m["sprints"]["S1"]["tokens"], 0)
        self.assertEqual(m["roles"]["backend"]["unread"], 3)

    def test_cli_metrics_and_open_stale(self):
        text = run("metrics")
        self.assertIn("First answer   2.0h", text)
        self.assertIn("Sprint       threads", text)
        data = json.loads(run("metrics", "--json", "--stale", "1h"))
        self.assertEqual(data["summary"]["stale_open"], 2)
        everything = run("open", "--stale", "0m")  # independent of today's date
        self.assertIn("Q-002", everything)
        self.assertIn("B-003", everything)
        self.assertIn("0 open", run("open", "--stale", "1000d"))
        with self.assertRaises(SystemExit):
            run("open", "--stale", "soon")


class ServeTest(Base):
    def setUp(self):
        super().setUp()
        self.server = serve.make_server(self.board(), "127.0.0.1", 0)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def get(self, path, method="GET"):
        req = urllib.request.Request(self.url + path, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode(), r.headers
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode(), e.headers

    def test_dashboard(self):
        code, body, headers = self.get("/")
        self.assertEqual(code, 200)
        for text in ("Blockers", "B-003", "Questions waiting for an answer", "Q-002", "Metrics"):
            self.assertIn(text, body)
        self.assertNotIn("<script>alert(1)</script>", body)  # board text is escaped
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("Live contracts (0)", body)
        for text in ("Time to first answer (median)", "2.0h", "Time to close (median)", "4.0h",
                     "Questions answered", "Metrics by sprint", "Metrics by role", "Unread (~tokens)"):
            self.assertIn(text, body)

    def test_entry_api_and_errors(self):
        code, body, _ = self.get("/e/Q-1")
        self.assertEqual(code, 200)
        self.assertIn("paginated?", body)
        self.assertEqual(self.get("/e/Q-099")[0], 404)
        self.assertEqual(self.get("/nope")[0], 404)
        self.assertEqual(self.get("/", method="POST")[0], 405)
        data = json.loads(self.get("/api/board.json")[1])
        self.assertEqual(sorted(t["id"] for t in data["open"]), ["B-003", "Q-002"])
        self.assertIn("summary", json.loads(self.get("/api/metrics.json")[1]))


if __name__ == "__main__":
    unittest.main()
