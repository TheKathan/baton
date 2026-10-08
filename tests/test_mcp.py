import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from baton.cli import main

SRC = str(Path(__file__).resolve().parent.parent / "src")


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


class McpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["BATON_ROOT"] = str(self.root)
        run("init", "--root", str(self.root), "--roles", "orchestrator,backend,frontend,qa")

    def tearDown(self):
        os.environ.pop("BATON_ROOT", None)
        self.tmp.cleanup()

    def session(self, messages, role=None):
        """Run a real `baton mcp` process; return its responses keyed by id."""
        env = {**os.environ, "PYTHONPATH": SRC, "BATON_ROOT": os.environ.get("BATON_ROOT", str(self.root))}
        env.pop("BATON_ROLE", None)
        if role:
            env["BATON_ROLE"] = role
        stdin = "".join(json.dumps(m) + "\n" for m in messages) + "not json\n"
        r = subprocess.run([sys.executable, "-m", "baton", "mcp"], input=stdin, capture_output=True,
                           text=True, env=env, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = [json.loads(line) for line in r.stdout.splitlines()]
        self.assertEqual(out[-1]["error"]["code"], -32700)  # the "not json" line
        return {m["id"]: m for m in out[:-1]}

    @staticmethod
    def call(mid, tool, **arguments):
        return {"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                "params": {"name": tool, "arguments": arguments}}

    def text(self, resp):
        return resp["result"]["content"][0]["text"]

    def test_handshake_and_tool_list(self):
        r = self.session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
            {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
        ])
        init = r[1]["result"]
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        self.assertEqual(init["serverInfo"]["name"], "baton")
        self.assertIn("Read at three moments", init["instructions"])
        names = {t["name"] for t in r[2]["result"]["tools"]}
        self.assertTrue({"baton_brief", "baton_post", "baton_reply", "baton_handoff", "baton_unread"} <= names)
        for t in r[2]["result"]["tools"]:
            self.assertEqual(t["inputSchema"]["type"], "object")
        self.assertEqual(r[3]["result"], {})
        self.assertEqual(r[4]["error"]["code"], -32601)

    def test_tools_enforce_the_same_rules(self):
        body = "-x looks like a flag\nline 2"
        r = self.session([
            self.call(1, "baton_post", role="frontend", kind="Q", to=["backend"], title="Paginated?", body=body),
            self.call(2, "baton_post", role="backend", kind="C", to=["frontend"], title="no files", body="x"),
            self.call(3, "baton_handoff", role="backend", phase="S1", state="DONE", to=["qa"], title="done", body="x"),
            self.call(4, "baton_unread", role="backend"),
            self.call(5, "baton_reply", role="backend", id="Q-001", body="Full array.", close=True),
            self.call(6, "baton_handoff", role="backend", phase="S1", state="DONE", to=["qa"], title="done", body="x"),
            self.call(7, "baton_show", ids=["Q-1"]),
            self.call(8, "baton_post", kind="D", to=["all"], title="no role", body="x"),
        ])
        self.assertFalse(r[1]["result"]["isError"])
        self.assertIn("posted Q-001", self.text(r[1]))
        self.assertTrue(r[2]["result"]["isError"])
        self.assertIn("--files", self.text(r[2]))
        self.assertTrue(r[3]["result"]["isError"])
        self.assertIn("Q-001", self.text(r[3]))  # refused: question waiting on backend
        self.assertIn(body, self.text(r[4]))  # bodies keep leading dashes and newlines
        self.assertIn("replied to Q-001 and closed it", self.text(r[5]))
        self.assertIn("posted H-002", self.text(r[6]))
        self.assertIn("status: CLOSED", self.text(r[7]))
        self.assertTrue(r[8]["result"]["isError"])  # no role given and none in the environment

    def test_orchestrator_tools(self):
        r = self.session([
            self.call(1, "baton_post", role="qa", kind="Q", to=["backend"], title="unanswered", body="x"),
            self.call(2, "baton_post", role="orchestrator", kind="D", to=["all"], title="scope", body="x"),
            self.call(3, "baton_list", kind="Q"),
            self.call(4, "baton_status", role="backend", phase="S1", state="building"),
            self.call(5, "baton_status"),
            self.call(6, "baton_open", stale="0m"),
            self.call(7, "baton_metrics"),
            self.call(8, "baton_lint"),
            self.call(9, "baton_close", role="orchestrator", sprint="S1", reason="gate passed"),
            self.call(10, "baton_sprint", name="S2"),
            self.call(11, "baton_list", status="open"),
        ])
        self.assertIn("unanswered", self.text(r[3]))
        self.assertNotIn("scope", self.text(r[3]))
        self.assertIn("building", self.text(r[5]))
        self.assertIn("2 open", self.text(r[6]))
        self.assertIn("Threads", self.text(r[7]))
        self.assertIn("0 error(s)", self.text(r[8]))
        self.assertIn("kept open (unanswered", self.text(r[9]))
        self.assertIn("current sprint is now S2", self.text(r[10]))
        self.assertIn("Q-001", self.text(r[11]))
        self.assertNotIn("D-002", self.text(r[11]))

    def test_sandbox_lifecycle_through_mcp(self):
        import shutil
        import subprocess as sp
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        sp.run(["git", "init", "-q"], cwd=repo, check=True)
        env_root = os.environ["BATON_ROOT"]
        os.environ["BATON_ROOT"] = str(repo)
        try:
            r = self.session([
                self.call(1, "baton_sandbox_start", task="LIN-5", roles=["backend", "qa"]),
                self.call(2, "baton_post", role="backend", kind="C", to=["qa"], title="shape", body="x",
                          files=["api.ts"]),
                self.call(3, "baton_contracts", paths=["*.ts"]),
                self.call(4, "baton_finish", strict=True),
            ])
            self.assertIn("sandbox board for LIN-5", self.text(r[1]))
            self.assertIn("C-001", self.text(r[3]))
            self.assertFalse(r[4]["result"]["isError"], self.text(r[4]))
            self.assertIn("### baton: LIN-5", self.text(r[4]))
            self.assertTrue((repo / ".baton/tasks/LIN-5.jsonl").exists())
        finally:
            os.environ["BATON_ROOT"] = env_root
            shutil.rmtree(repo, ignore_errors=True)

    def test_instructions_prefer_the_command(self):
        r = self.session([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {}}}])
        self.assertIn("prefer the `baton` command", r[1]["result"]["instructions"])

    def test_role_from_environment(self):
        r = self.session([self.call(1, "baton_post", kind="D", to=["all"], title="env role", body="x")],
                         role="orchestrator")
        self.assertIn("posted D-001", self.text(r[1]))

    def test_install_merges_into_mcp_json(self):
        path = self.root / ".mcp.json"
        path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
        self.assertIn("registered", run("mcp", "install"))
        self.assertIn("already registers", run("mcp", "install"))
        data = json.loads(path.read_text())
        self.assertEqual(data["mcpServers"]["baton"], {"command": "baton", "args": ["mcp"]})
        self.assertEqual(data["mcpServers"]["other"], {"command": "x"})
        run("mcp", "install", "--command", "npx", "--file", str(self.root / "alt.json"))
        self.assertEqual(json.loads((self.root / "alt.json").read_text())["mcpServers"]["baton"]["command"], "npx")


if __name__ == "__main__":
    unittest.main()
