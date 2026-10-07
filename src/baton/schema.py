"""The on-disk format: its version, and the read-time upgrades between versions.

The format is documented in docs/FORMAT.md. Rules that keep boards readable forever:
- Event lines are never rewritten. Older events are upgraded in memory as they are read.
- Every new event carries `"v": SCHEMA_VERSION`. Events without `v` were written by baton 0.x,
  whose fields match format 1.
- Within a format version, new fields are only ever added and are optional; readers ignore
  fields they don't know.
- A board that contains events from a *newer* format is refused, never half-read.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

# from-version -> function(event) -> event of version + 1. Empty until format 2 exists.
UPGRADES: dict[int, callable] = {}


class FormatError(Exception):
    pass


def version_of(event: dict) -> int:
    return int(event.get("v", 1))


def upgrade(event: dict, where: str) -> dict:
    """Return `event` upgraded to SCHEMA_VERSION (in memory only)."""
    v = version_of(event)
    if v > SCHEMA_VERSION:
        raise FormatError(f"{where}: written by a newer baton (format {v}; this baton reads up to "
                          f"{SCHEMA_VERSION}). Upgrade baton to read this board.")
    while v < SCHEMA_VERSION:
        event = UPGRADES[v](event)
        v += 1
    event["v"] = SCHEMA_VERSION
    return event


def check_config(cfg: dict, where: str) -> None:
    fmt = int(cfg.get("format", 1))
    if fmt > SCHEMA_VERSION:
        raise FormatError(f"{where}: the project uses board format {fmt}, newer than this baton "
                          f"supports ({SCHEMA_VERSION}). Upgrade baton.")
