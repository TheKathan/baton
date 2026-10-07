#!/usr/bin/env python3
"""Write a release version into every file that carries it.

  scripts/set_version.py 0.2.0          update the files and the changelog
  scripts/set_version.py --check        exit 1 if the files disagree

Files: src/baton/__init__.py (the source of truth at runtime), package.json, the README
version badge, and
CHANGELOG.md (the "Unreleased" section becomes "[X.Y.Z] - <date>"). pyproject.toml
reads the version from src/baton/__init__.py, so it needs no edit.
Used by .github/workflows/release.yml after trunk-semver picks the version.
"""

import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "src/baton/__init__.py"
PKG = ROOT / "package.json"
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"
BADGE = re.compile(r'<img alt="Version ([^"]+)" src="https://img\.shields\.io/badge/version-([^-]+)-blue">')
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def current() -> dict[str, str]:
    init = re.search(r'__version__ = "([^"]+)"', INIT.read_text()).group(1)
    found = {"src/baton/__init__.py": init, "package.json": json.loads(PKG.read_text())["version"]}
    if README.exists() and (m := BADGE.search(README.read_text())):
        found["README.md badge"] = m.group(2)
    return found


def set_version(version: str) -> None:
    INIT.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"', INIT.read_text()))
    pkg = json.loads(PKG.read_text())
    pkg["version"] = version
    PKG.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
    if README.exists():
        README.write_text(BADGE.sub(
            f'<img alt="Version {version}" src="https://img.shields.io/badge/version-{version}-blue">',
            README.read_text()))
    text = CHANGELOG.read_text()
    if "## [Unreleased]" in text and f"## [{version}]" not in text:
        today = datetime.datetime.now(datetime.UTC).date().isoformat()
        text = text.replace("## [Unreleased]", f"## [Unreleased]\n\n## [{version}] - {today}", 1)
        CHANGELOG.write_text(text)


def notes(version: str) -> str:
    """The changelog section of a version, for the GitHub release body."""
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", CHANGELOG.read_text(),
                  re.DOTALL | re.MULTILINE)
    return (m.group(1).strip() if m else "") or f"Release {version}."


def main(argv: list[str]) -> None:
    if argv == ["--check"]:
        found = current()
        if len(set(found.values())) != 1:
            sys.exit(f"version mismatch: {found}")
        print(f"version {next(iter(found.values()))} is consistent")
    elif len(argv) == 2 and argv[0] == "--notes":
        print(notes(argv[1].lstrip("v")))
    elif len(argv) == 1 and SEMVER.match(argv[0].lstrip("v")):
        set_version(argv[0].lstrip("v"))
        print(f"set version {argv[0].lstrip('v')}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
