import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "set_version.py"


def _old_python():
    """A Python older than 3.11 on this machine (a stock macOS has 3.9 at /usr/bin/python3)."""
    for exe in ("/usr/bin/python3", shutil.which("python3.10"), shutil.which("python3.9")):
        if exe and os.path.exists(exe):
            r = subprocess.run([exe, "-c", "import sys; print(sys.version_info < (3, 11))"],
                               capture_output=True, text=True, check=False)
            if r.stdout.strip() == "True":
                return exe
    return None


OLD_PYTHON = _old_python()


class ReleaseTest(unittest.TestCase):
    def test_versions_are_consistent(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_set_version_updates_files_and_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            for rel in ("scripts/set_version.py", "src/baton/__init__.py"):
                (t / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, t / rel)
            (t / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n- thing\n\n## [0.1.0] - 2026-10-07\n- first\n")
            # the README version badge is optional; when present it is kept in sync
            (t / "README.md").write_text('<img alt="Version 0.1.0" src="https://img.shields.io/badge/version-0.1.0-blue">\n')
            script = t / "scripts/set_version.py"
            subprocess.run([sys.executable, str(script), "v0.2.0"], check=True, capture_output=True)
            self.assertIn('__version__ = "0.2.0"', (t / "src/baton/__init__.py").read_text())
            self.assertIn("badge/version-0.2.0-blue", (t / "README.md").read_text())
            log = (t / "CHANGELOG.md").read_text()
            self.assertRegex(log, r"## \[Unreleased\]\n\n## \[0\.2\.0\] - \d{4}-\d{2}-\d{2}\n\n### Added\n- thing")
            notes = subprocess.run([sys.executable, str(script), "--notes", "v0.2.0"], check=True,
                                   capture_output=True, text=True).stdout
            self.assertEqual(notes.strip(), "### Added\n- thing")
            # idempotent: running again does not add a second heading
            subprocess.run([sys.executable, str(script), "0.2.0"], check=True, capture_output=True)
            self.assertEqual((t / "CHANGELOG.md").read_text().count("## [0.2.0]"), 1)

    def test_pyproject_metadata(self):
        text = (ROOT / "pyproject.toml").read_text()
        meta = tomllib.loads(text)["project"]
        self.assertEqual(meta["name"], "baton-handoff")
        self.assertEqual(meta["requires-python"], ">=3.11")
        self.assertEqual(meta["dependencies"], [])
        self.assertEqual(meta["scripts"], {"baton": "baton.cli:main", "baton-handoff": "baton.cli:main"})
        self.assertIn("Development Status :: 4 - Beta", meta["classifiers"])
        readme = (ROOT / "README.md").read_text()
        self.assertEqual(re.findall(r'(?:src|srcset)="(?!https?:)([^"]+)"', readme), [])


class LauncherTest(unittest.TestCase):
    """bin/baton runs baton from a checkout (install.sh's fallback), often with an old system python3."""

    def test_launcher_parses_on_old_pythons(self):
        ast.parse((ROOT / "bin" / "baton").read_text(), feature_version=(3, 6))

    @unittest.skipUnless(OLD_PYTHON, "no Python older than 3.11 found")
    def test_old_python3_is_explained_or_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "python3").symlink_to(OLD_PYTHON)
            env = {**os.environ, "PATH": f"{tmp}:/usr/bin:/bin"}
            env.pop("BATON_LAUNCHER_REEXEC", None)
            r = subprocess.run([str(ROOT / "bin" / "baton"), "--version"], env=env, capture_output=True,
                               text=True, check=False)
            if r.returncode:
                self.assertIn("baton needs Python 3.11 or newer", r.stderr)
                self.assertIn("uvx baton-handoff", r.stderr)
            (Path(tmp) / "python3.13").symlink_to(sys.executable)
            r = subprocess.run([str(ROOT / "bin" / "baton"), "--version"], env=env, capture_output=True,
                               text=True, check=True)
            self.assertTrue(r.stdout.startswith("baton "), r.stdout + r.stderr)


def _jobs(workflow: str) -> dict[str, str]:
    """The text of each job in a workflow, keyed by job id (stdlib has no YAML parser)."""
    body = workflow.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z0-9_-]*):\n", body, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


class ReleaseWorkflowTest(unittest.TestCase):
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    jobs = _jobs(workflow)

    def test_actions_are_pinned_to_a_sha(self):
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
            for ref in re.findall(r"uses:\s*(\S+.*)", workflow.read_text()):
                self.assertRegex(ref, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d", f"{workflow.name}: {ref}")

    def test_tests_run_without_the_deploy_key(self):
        self.assertIn("make test", self.jobs["test"])
        self.assertNotIn("RELEASE_DEPLOY_KEY", self.jobs["test"])
        for name, job in self.jobs.items():
            self.assertEqual("RELEASE_DEPLOY_KEY" in job, name == "release", name)
        self.assertNotIn("make test", self.jobs["release"])
        self.assertIn("needs: test", self.jobs["release"])

    def test_exact_tags_are_created_once_and_only_the_major_tag_moves(self):
        release = self.jobs["release"]
        self.assertIn('git push origin "refs/tags/$VERSION"', release)
        self.assertIn('git push --force origin "refs/tags/$MAJOR"', release)
        self.assertNotRegex(release, r"--force[^\n]*\$VERSION|-f \"?\$VERSION")
        self.assertLess(release.index("tag-sandbox.git"), release.index("TheKathan/trunk-semver@"))
        self.assertLess(release.index("TheKathan/trunk-semver@"), release.index('set-url origin "$ORIGIN_URL"'))

    def test_registry_publishing_is_off_by_default_and_least_privileged(self):
        self.assertIn("permissions: {}", self.workflow)
        for name in ("build", "pypi"):
            self.assertIn("if: vars.PUBLISH_PYPI == 'true'", self.jobs[name], name)
        for name, job in self.jobs.items():
            self.assertEqual("id-token: write" in job, name == "pypi", name)
        self.assertIn("name: pypi", self.jobs["pypi"])
        self.assertIn("pypa/gh-action-pypi-publish@", self.jobs["pypi"])
        self.assertEqual(sorted(self.jobs), ["build", "pypi", "release", "test"])


if __name__ == "__main__":
    unittest.main()
