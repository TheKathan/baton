"""Policy rules: team rules that baton checks on every new entry.

Configured in .baton/config.json under "policies", for example:

    "policies": [
      {"rule": "cites",      "kinds": ["H"],      "mode": "refuse"},
      {"rule": "named_to",   "kinds": ["Q", "B"], "mode": "warn"},
      {"rule": "max_lines",  "kinds": ["D"], "lines": 15, "mode": "warn"},
      {"rule": "title_match", "kinds": ["H"], "pattern": "^S\\\\d+", "mode": "refuse",
       "message": "hand-off titles start with the sprint, e.g. S7-A backend"}
    ]

Rules: `cites` (at least one --cites), `files` (at least one --files), `named_to` (address a
role by name, not only "all"), `max_lines` (body at most `lines` lines), `title_match` (title
matches the regex `pattern`). `kinds` limits a rule to entry kinds (default: all kinds).
`mode` is "warn" (the entry is posted with a warning) or "refuse" (nothing is written).
`message` replaces the default explanation.
"""

from __future__ import annotations

import re

RULES = ("cites", "files", "named_to", "max_lines", "title_match")
MODES = ("warn", "refuse")


class PolicyError(Exception):
    pass


def validate(policies) -> list[dict]:
    """Return the policies, or raise PolicyError describing what is wrong with the config."""
    if policies in (None, []):
        return []
    if not isinstance(policies, list):
        raise PolicyError('"policies" must be a list of rules')
    for i, p in enumerate(policies):
        where = f"policies[{i}]"
        if not isinstance(p, dict) or p.get("rule") not in RULES:
            raise PolicyError(f"{where}: unknown rule {p.get('rule') if isinstance(p, dict) else p!r}; "
                              f"known: {', '.join(RULES)}")
        if p.get("mode", "warn") not in MODES:
            raise PolicyError(f"{where}: mode must be warn or refuse")
        if p["rule"] == "max_lines" and not isinstance(p.get("lines"), int):
            raise PolicyError(f"{where}: max_lines needs an integer \"lines\"")
        if p["rule"] == "title_match":
            try:
                re.compile(p.get("pattern", ""))
            except re.error as e:
                raise PolicyError(f"{where}: bad pattern ({e})") from None
            if not p.get("pattern"):
                raise PolicyError(f"{where}: title_match needs a \"pattern\"")
        if "kinds" in p and not isinstance(p["kinds"], list):
            raise PolicyError(f"{where}: kinds must be a list")
    return policies


def _broken(p: dict, entry: dict) -> str | None:
    rule = p["rule"]
    if rule == "cites" and not entry.get("cites"):
        return "must cite what it relates to (--cites STORY-…,DG-…)"
    if rule == "files" and not entry.get("files"):
        return "must list the affected files (--files)"
    if rule == "named_to" and not [r for r in entry.get("to", []) if r != "all"]:
        return "must be addressed to a role by name, not only to all (--to <role>)"
    if rule == "max_lines" and len(entry.get("body", "").splitlines()) > p["lines"]:
        return f"body must be at most {p['lines']} lines (link long details from a file)"
    if rule == "title_match" and not re.search(p["pattern"], entry.get("title", "")):
        return f"title must match {p['pattern']!r}"
    return None


def check(policies, entry: dict) -> tuple[list[str], list[str]]:
    """(refusals, warnings) for a new entry, as human-readable messages."""
    refusals, warnings = [], []
    for p in validate(policies):
        if p.get("kinds") and entry["kind"] not in p["kinds"]:
            continue
        why = _broken(p, entry)
        if why:
            msg = f"policy {p['rule']} ({entry['kind']}): {p.get('message') or why}"
            (refusals if p.get("mode", "warn") == "refuse" else warnings).append(msg)
    return refusals, warnings
