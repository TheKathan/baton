import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "set_version.py"


class ReleaseTest(unittest.TestCase):
    def test_versions_are_consistent(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_set_version_updates_files_and_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            for rel in ("scripts/set_version.py", "src/baton/__init__.py", "package.json", "README.md"):
                (t / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, t / rel)
            (t / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n- thing\n\n## [0.1.0] - 2026-10-07\n- first\n")
            script = t / "scripts/set_version.py"
            subprocess.run([sys.executable, str(script), "v0.2.0"], check=True, capture_output=True)
            self.assertIn('__version__ = "0.2.0"', (t / "src/baton/__init__.py").read_text())
            self.assertEqual(json.loads((t / "package.json").read_text())["version"], "0.2.0")
            self.assertIn("badge/version-0.2.0-blue", (t / "README.md").read_text())
            log = (t / "CHANGELOG.md").read_text()
            self.assertRegex(log, r"## \[Unreleased\]\n\n## \[0\.2\.0\] - \d{4}-\d{2}-\d{2}\n\n### Added\n- thing")
            notes = subprocess.run([sys.executable, str(script), "--notes", "v0.2.0"], check=True,
                                   capture_output=True, text=True).stdout
            self.assertEqual(notes.strip(), "### Added\n- thing")
            # idempotent: running again does not add a second heading
            subprocess.run([sys.executable, str(script), "0.2.0"], check=True, capture_output=True)
            self.assertEqual((t / "CHANGELOG.md").read_text().count("## [0.2.0]"), 1)

    @unittest.skipUnless(shutil.which("npm"), "npm not installed")
    def test_npm_pack_installs_a_working_baton_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "npm_config_cache": str(Path(tmp) / "cache"), "npm_config_update_notifier": "false"}
            pack = subprocess.run(["npm", "pack", "--json", "--pack-destination", tmp], cwd=ROOT, env=env,
                                  capture_output=True, text=True, check=True)
            info = json.loads(pack.stdout)[0]
            files = {f["path"] for f in info["files"]}
            self.assertIn("bin/baton", files)
            self.assertIn("src/baton/cli.py", files)
            self.assertIn("src/baton/skill/SKILL.md", files)
            self.assertFalse(any(p.startswith(("tests/", "assets/", ".github/")) for p in files), files)
            prefix = Path(tmp) / "prefix"
            subprocess.run(["npm", "install", "-g", "--prefix", str(prefix), str(Path(tmp) / info["filename"])],
                           env=env, capture_output=True, text=True, check=True)
            out = subprocess.run([str(prefix / "bin" / "baton"), "--version"], capture_output=True, text=True,
                                 check=True).stdout
            self.assertEqual(out.strip(), f"baton {info['version']}")
            skill = subprocess.run([str(prefix / "bin" / "baton"), "skill", "show"], capture_output=True,
                                   text=True, check=True).stdout
            self.assertTrue(skill.startswith("---\nname: baton\n"))


if __name__ == "__main__":
    unittest.main()
