"""The docs can't drift from the CLI: every `baton <command> --flag` they mention must exist."""

import re
import unittest
from pathlib import Path

from baton.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


def _commands():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    return {name: {o for a in p._actions for o in a.option_strings} for name, p in sub.choices.items()}


class DocsTest(unittest.TestCase):
    def test_commands_and_flags_in_docs_exist(self):
        commands = _commands()
        problems = []
        for doc in DOCS:
            for lineno, line in enumerate(doc.read_text().splitlines(), 1):
                for m in re.finditer(r"\bbaton ([a-z]+)\b((?:(?!\bbaton )[^`|#\n])*)", line):
                    cmd, rest = m.group(1), m.group(2)
                    if cmd not in commands:
                        continue  # prose such as "baton keeps…", not a command
                    for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", rest):
                        if flag not in commands[cmd] and flag not in ("--help", "--version"):
                            problems.append(f"{doc.relative_to(ROOT)}:{lineno}: baton {cmd} has no {flag}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_docs_link_to_files_that_exist(self):
        missing = []
        for doc in DOCS:
            for target in re.findall(r"\]\(((?!https?:|#)[^)#]+)", doc.read_text()):
                if not (doc.parent / target).exists():
                    missing.append(f"{doc.relative_to(ROOT)} → {target}")
        self.assertEqual(missing, [], "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
