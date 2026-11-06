import contextlib
import io
import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from baton import boardview, config, metrics, serve
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
        self.now = datetime(2026, 10, 5, 10, 0)

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

    def test_board(self):
        code, body, headers = self.get("/")
        self.assertEqual(code, 200)
        for text in ("Blocked", "B-003", "Needs an answer", "Q-002", "To pick up", "Done", "Runners",
                     "Contracts in force", 'href="/metrics"', 'href="/contracts"'):
            self.assertIn(text, body)
        self.assertNotIn("<script>alert(1)</script>", body)  # board text is escaped
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("<script", body)
        self.assertIn("frontend can't hand off until answered", body)  # the hand-off rule, on the card

    def test_metrics_page(self):
        code, body, _ = self.get("/metrics")
        self.assertEqual(code, 200)
        for text in ("Time to first answer (median)", "2.0h", "Time to close (median)", "4.0h",
                     "Questions answered", "By sprint", "By role", "Unread (~tokens)", "Board health",
                     "p90 2.0h · n=1", "Owes answers", "Needs attention", "How to read this"):
            self.assertIn(text, body)
        self.assertIn("No hand-offs yet.", body)  # the fixture has none
        self.assertIn("<code>(unknown)</code>", body)  # but it has events, so By model has a row
        self.assertNotIn("No events yet.", body)
        self.assertNotIn("<script", body)

    def test_metrics_page_shares_the_board_shell(self):
        _, body, _ = self.get("/metrics")
        _, board, _ = self.get("/")
        _, contracts, _ = self.get("/contracts")
        self.assertIn('<header class="top">', body)
        self.assertIn('<a href="/metrics" aria-current="page">metrics</a>', body)
        self.assertIn('<a href="/">board</a>', body)
        self.assertIn('<a href="/" aria-current="page">board</a>', board)
        self.assertIn('<a href="/contracts" aria-current="page">contracts</a>', contracts)
        self.assertIn("sprint <b>S1</b> · showing <b>sprint S1</b>", body)
        self.assertIn('http-equiv="refresh" content="30"', body)
        self.assertIn(boardview.CSS, body)  # the board's tokens, not a fork of them
        self.assertIn("<footer>baton serve · read-only · refreshes every 30 s", body)
        for kpi in ("Open threads", "Blockers", "Unanswered Q/B", "Stale (≥48h)", "Median first answer", "Close rate"):
            self.assertIn(kpi, body)
        self.assertIn('<a class="kpi t-bad" href="#blocked">', body)  # an open blocker, linked to its list

    def test_metrics_scope_defaults_to_the_current_sprint(self):
        self.board().append_raw({"type": "entry", "id": "B-050", "kind": "B", "n": 50, "from": "qa", "to": ["backend"],
                                 "title": "old blocker", "body": "", "files": [], "cites": [], "blocks": [],
                                 "ts": "2026-09-01 10:00", "sprint": "S0"})
        _, body, _ = self.get("/metrics")
        self.assertIn("Metrics · sprint S1", body)
        self.assertNotIn('href="/e/B-050"', body)  # S0's blocker is out of scope
        self.assertIn('<a href="/metrics?sprint=S1" aria-current="true">This sprint (S1)</a>', body)
        self.assertIn(">S0</span>", body)  # By sprint always shows every sprint
        _, body, _ = self.get("/metrics?sprint=all")
        self.assertIn("Metrics · all sprints", body)
        self.assertIn('href="/e/B-050"', body)
        self.assertIn('<a href="/metrics?sprint=all" aria-current="true">', body)
        _, body, _ = self.get("/metrics?sprint=S0")
        self.assertIn("Metrics · sprint S0", body)
        self.assertNotIn('href="/e/B-003"', body)
        _, body, _ = self.get("/metrics?sprint=%3Cscript%3Ex")  # unknown: the current sprint, never echoed raw
        self.assertIn("Metrics · sprint S1", body)
        self.assertNotIn("<script", body)

    def test_needs_attention_lists_and_links_the_work(self):
        page = serve.metrics_page(self.board(), self.now)
        self.assertIn('<div class="agrp bad" id="blocked">', page)
        self.assertIn('<a class="id" href="/e/B-003">B-003</a>', page)
        self.assertIn('<div class="agrp warn" id="unanswered">', page)
        self.assertIn("badge &lt;script&gt;alert(1)&lt;/script&gt;?", page)  # a title, escaped
        self.assertIn('<div class="agrp warn" id="stale">', page)

    def test_needs_attention_lists_each_thread_once(self):
        page = serve.metrics_page(self.board(), self.now)
        attention = page.split('id="attention"', 1)[1].split("</section>", 1)[0]
        self.assertEqual(attention.count('href="/e/B-003"'), 1)  # blocked, unanswered and stale
        self.assertIn("listed above", attention)

    def test_metrics_page_bars_use_role_colours(self):
        page = serve.metrics_page(self.board(), self.now)
        m = boardview.Model(self.board(), self.now)
        self.assertIn(f'<div class="{m.rc("qa")}"><div class="bar"', page)  # qa posted, so it has a bar
        self.assertIn('<i class="s-own"', page)
        self.assertIn('<i class="s-m1"', page)  # neutral series: closed, by-model share
        self.assertIn('class="tm"', page)  # median and p90 markers
        self.assertIn('class="sp cur"', page)  # the current sprint's column
        self.assertNotIn("<script", page)

    def test_hostile_model_and_custom_kind_are_escaped(self):
        bad = '"><img src=x onerror=1>'
        self.board().append_raw({"type": "entry", "id": "R-060", "kind": "R", "n": 60, "from": "qa", "to": ["backend"],
                                 "title": "risk", "body": "", "files": [], "cites": [], "blocks": [],
                                 "ts": "2026-10-05 09:00", "model": bad})
        page = serve.metrics_page(self.board(), self.now)
        self.assertNotIn("<img", page)
        self.assertIn("&quot;&gt;&lt;img src=x onerror=1&gt;", page)
        self.assertIn("R 1", page)  # a custom kind with no configured name falls back to its letter

    def test_handoff_outcomes_split_sent_and_cited_later_is_a_count(self):
        b = self.board()
        b.append_raw({"type": "entry", "id": "H-070", "kind": "H", "n": 70, "from": "backend", "to": ["qa"],
                      "title": "runs api", "body": "", "files": [], "cites": [], "blocks": [], "ts": "2026-10-05 08:00"})
        b.append_raw({"type": "entry", "id": "Q-071", "kind": "Q", "n": 71, "from": "qa", "to": ["backend"],
                      "title": "why 500?", "body": "", "files": [], "cites": ["H-070"], "blocks": [],
                      "ts": "2026-10-05 09:00"})
        b.append_raw({"type": "close", "id": "H-070", "from": "qa", "reason": "", "ts": "2026-10-05 09:30",
                      "outcome": "accepted"})
        page = serve.metrics_page(self.board(), self.now)
        self.assertIn('<th class="grp" scope="colgroup" colspan="6">As sender</th>', page)
        self.assertIn("As receiver", page)
        self.assertIn("Cited later", page)
        self.assertIn('<i class="s-acc" style="width:100.0%"', page)  # 1 of 1 sent accepted fills the bar
        self.assertNotIn("bounced", page.lower())

    def test_stacked_bars_never_pass_100_percent(self):
        from baton import metricsview
        html = metricsview.bar([("a", 1, ""), ("b", 1000, "")], 1001, "x")
        widths = [float(w) for w in re.findall(r"width:([\d.]+)%", html)]
        self.assertEqual(len(widths), 2)
        self.assertLessEqual(sum(widths), 100.0)

    def test_ids_fold_past_the_cap(self):
        from baton import metricsview
        html = metricsview.ids([f"Q-{i:03d}" for i in range(15)])
        self.assertIn("<details><summary>+3 more</summary>", html)
        self.assertIn('href="/e/Q-014"', html)
        self.assertEqual(metricsview.ids([]), "none")

    def test_sprint_trend_needs_two_sprints(self):
        self.assertNotIn('class="tline"', serve.metrics_page(self.board(), self.now))  # S1 only
        b = self.board()
        b.append_raw({"type": "entry", "id": "Q-080", "kind": "Q", "n": 80, "from": "frontend", "to": ["backend"],
                      "title": "earlier", "body": "", "files": [], "cites": [], "blocks": [], "ts": "2026-09-01 10:00",
                      "sprint": "S0"})
        b.append_raw({"type": "close", "id": "Q-080", "from": "frontend", "reason": "", "ts": "2026-09-01 16:00"})
        page = serve.metrics_page(self.board(), self.now)
        self.assertIn('class="tline"', page)
        self.assertEqual(page.count('class="pt cz"'), 2)  # a close median point per sprint
        self.assertIn("<small>n=1</small>", page)

    def test_entry_and_error_pages_share_the_shell(self):
        code, body, _ = self.get("/e/Q-1")
        self.assertIn('<header class="top">', body)
        self.assertIn("paginated?", body)
        code, body, _ = self.get("/nope")
        self.assertEqual(code, 404)
        self.assertIn('<header class="top">', body)
        self.assertIn("Not found. Try /", body)
        code, body, _ = self.get("/metrics", method="POST")
        self.assertEqual(code, 405)
        self.assertIn('<header class="top">', body)


    def test_contracts_page(self):
        code, body, _ = self.get("/contracts")
        self.assertEqual(code, 200)
        self.assertIn("No contracts here.", body)
        self.assertEqual(self.get("/contracts?f=nonsense")[0], 200)

    def test_entry_of_another_task(self):
        tasks = self.root / ".baton" / "tasks"
        tasks.mkdir(parents=True)
        entry = {"type": "entry", "ev": 1, "id": "C-001", "kind": "C", "n": 1, "from": "backend", "to": ["qa"],
                 "title": "Orders shape", "body": "", "files": ["api/orders.ts"], "cites": [], "blocks": [],
                 "ts": "2026-10-01 10:00", "sprint": "LIN-9"}
        (tasks / "LIN-9.jsonl").write_text(json.dumps(entry) + "\n")
        code, body, _ = self.get("/e/LIN-9/C-1")
        self.assertEqual(code, 200)
        self.assertIn("Orders shape", body)
        self.assertEqual(self.get("/e/LIN-9/C-099")[0], 404)
        self.assertEqual(self.get("/e/LIN-8/C-001")[0], 404)

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


class BoardViewTest(Base):
    def setUp(self):
        super().setUp()
        self.b = self.board()
        self.n = 3

    def add(self, kind, frm, to, title, ts="2026-10-05 09:00", **kw):
        self.n += 1
        eid = f"{kind}-{self.n:03d}"
        self.b.append_raw({"type": "entry", "id": eid, "kind": kind, "n": self.n, "from": frm, "to": to,
                           "title": title, "body": "", "files": kw.get("files", []), "cites": [], "blocks": [],
                           "ts": ts})
        return eid

    def reply(self, eid, frm):
        self.b.append_raw({"type": "reply", "id": eid, "from": frm, "body": "ok", "ts": "2026-10-05 09:30"})

    def model(self):
        return boardview.Model(self.board(), now=self.now)

    def ids(self, column):
        return [x["id"] for x in self.model().columns[column]]

    def test_work_sits_in_one_column_by_state(self):
        self.assertEqual((self.ids("blocked"), self.ids("ask"), self.ids("done")), (["B-003"], ["Q-002"], ["Q-001"]))
        self.reply("B-003", "backend")
        self.reply("Q-002", "frontend")
        self.assertEqual((self.ids("blocked"), self.ids("ask"), self.ids("ans")), ([], [], ["Q-002", "B-003"]))
        every = [t["id"] for col in self.model().columns.values() for t in col if "id" in t]
        self.assertEqual(sorted(every), sorted(set(every)))

    def test_a_reply_by_the_author_is_not_an_answer(self):
        self.reply("Q-002", "qa")
        self.assertEqual(self.ids("ask"), ["Q-002"])

    def test_handoffs_wait_then_are_passed_on(self):
        first = self.add("H", "backend", ["qa"], "backend done")
        self.assertEqual((self.ids("pick"), self.ids("passed")), ([first], []))
        second = self.add("H", "qa", ["orchestrator"], "qa done")
        self.assertEqual((self.ids("pick"), self.ids("passed")), ([second], [first]))
        self.assertEqual(self.model().passed_on[first], second)
        self.assertEqual(self.model().holders, {"orchestrator": [second]})

    def test_handoff_to_all_stays_to_pick_up(self):
        self.add("H", "backend", ["all"], "everyone")
        self.add("H", "qa", ["all"], "later")
        self.assertEqual(len(self.ids("pick")), 2)

    def test_in_progress_needs_a_thread_to_link(self):
        self.b.set_status("frontend", "S1", "working: ui")
        self.assertEqual(self.model().columns["prog"], [])
        self.b.set_status("qa", "S1", "testing")
        (card,) = self.model().columns["prog"]
        self.assertEqual((card["role"], card["thread"]["id"]), ("qa", "B-003"))
        self.b.set_status("qa", "S1", "DONE pending QA")
        self.assertEqual(self.model().columns["prog"], [])

    def test_open_work_that_changes_a_contracted_file_is_flagged(self):
        c = self.add("C", "backend", ["frontend", "qa"], "orders shape", files=["api/orders.ts"])
        mine = self.add("H", "backend", ["qa"], "backend done", files=["api/orders.ts"])
        other = self.add("H", "frontend", ["qa"], "frontend done", files=["api/orders.ts"])
        m = self.model()
        self.assertEqual(m.touches(next(t for t in m.threads if t["id"] == mine)), [])  # its own contract
        self.assertEqual([x.get("id") for x, _ in m.touches(next(t for t in m.threads if t["id"] == other))], [c])
        page = boardview.board_page(self.board(), self.now)
        self.assertIn("touches C-004", page)
        self.assertIn("1 touched by open work", page)
        touched = boardview.contracts_page(self.board(), "touched", self.now)
        self.assertIn("open work changes these files: H-006", touched)
        self.assertIn("orders shape", touched)
        self.assertNotIn("orders shape", boardview.contracts_page(self.board(), "old", self.now))

    def test_decisions_are_records_not_work(self):
        d = self.add("D", "orchestrator", ["all"], "ship on friday")
        m = self.model()
        self.assertNotIn(d, [t["id"] for col in m.columns.values() for t in col if "id" in t])
        page = boardview.board_page(self.board(), self.now)
        self.assertIn("ship on friday", page)
        self.assertIn("1 in force", page)

    def test_a_custom_kind_renders_generically(self):
        cfg = json.loads((self.root / ".baton/config.json").read_text())
        cfg["kinds"] = {**cfg.get("kinds", config.DEFAULTS["kinds"]), "R": "review"}
        (self.root / ".baton/config.json").write_text(json.dumps(cfg))
        r = self.add("R", "qa", ["backend"], "review the orders api")
        page = boardview.board_page(self.board(), self.now)
        self.assertIn("qa posted a review", page)
        m = self.model()
        self.assertIn(f'title="review {r}', boardview.card(m, next(t for t in m.threads if t["id"] == r), "done"))

    def test_quiet_board_says_so(self):
        quiet = boardview.board_page(self.board(), self.now)
        self.assertNotIn("Nothing blocked", quiet)
        self.reply("B-003", "backend")
        self.reply("Q-002", "frontend")
        self.b.append_raw({"type": "close", "id": "B-003", "from": "qa", "reason": "", "ts": "2026-10-05 10:00"})
        self.b.append_raw({"type": "close", "id": "Q-002", "from": "qa", "reason": "", "ts": "2026-10-05 10:00"})
        self.assertIn("Nothing blocked, nothing waiting for an answer.", boardview.board_page(self.board(), self.now))

    def test_done_and_pick_up_columns_are_capped(self):
        for i in range(7):
            self.add("H", "backend", ["qa"], f"hand-off {i}")
        page = boardview.board_page(self.board(), self.now)
        self.assertIn("+3 more", page)  # 7 waiting hand-offs fold after 4


class EmptyMetricsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root))

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def test_a_fresh_board_renders_calm_empty_states(self):
        page = serve.metrics_page(Board(self.root, config.load(self.root)))
        for text in ("No hand-offs yet.", "No sprints yet.", "No events yet.", "no data yet", "nothing posted yet"):
            self.assertIn(text, page)
        self.assertNotIn('class="bar"', page)  # nothing to chart
        self.assertNotIn('class="tline"', page)
        self.assertNotIn('class="tm"', page)
        self.assertNotIn('class="kpi t-ok"', page)  # an empty board is not "healthy": zeros stay neutral
        self.assertIn("<code>baton post Q", page)  # says what to do first
        self.assertIn("Nothing is blocked, unanswered or stale.", page)
        self.assertIn('aria-current="page">metrics', page)


if __name__ == "__main__":
    unittest.main()
