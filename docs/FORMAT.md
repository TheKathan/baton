# Board format (versions 1 and 2)

This is the stable, on-disk format of a baton board. Boards are committed to git and read for years, so baton 1.x promises:

- **Any 1.x release reads every board** written by baton 0.x or 1.x.
- **Event lines are never rewritten.** baton only ever appends. When the format changes, older events are upgraded in memory as they are read.
- **Within format 1, fields are only added, and only as optional fields.** Readers must ignore fields they don't know.
- **A board with events from a newer format is refused**, with a message to upgrade baton. It is never read halfway.

**Format 2 (the team layout, baton ≥ 1.2, the default for new boards)** lets several clones commit one board without conflicts. Format-1 boards (single-machine layout) keep working unchanged; `baton migrate --team` switches one to format 2. Format-1 events are upgraded to format 2 in memory as they are read. A baton older than 1.2 refuses a format-2 board. `baton migrate --check` reports which formats a board contains.

## Files

```text
.baton/config.json               project config (JSON object, see below)
.baton/events/<sprint>/<origin>.jsonl   format 2: one append-only log per clone (origin) per sprint
.baton/events/<sprint>.jsonl     format 1: one shared log per sprint (and legacy history after migrate)
.baton/events/status.json        format 1 only: one status row per role (format 2 stores status as events)
.baton/events/.clone-id          format 2: this clone's origin id, 6 hex; git-ignored
.baton/events/.lock              lock file (flock); git-ignored
.baton/events/.cursors/<role>.json   per-role read cursor; git-ignored
.baton/*.md, .baton/archive/*.md generated views; never parsed back
```

Inside a linked git worktree, baton uses the main worktree's `.baton/` (see the README).

## Sandbox boards

`baton init --sandbox --task <id>` writes `.baton/sandbox.json` (the same keys as `config.json`, plus `"sandbox": true` and `"task"`) and keeps the live board in `.baton/sandbox/`. Both are listed in `.git/info/exclude`. A sandbox board takes precedence over a project board in the same checkout. Its events carry an extra `task` field (string).

`baton finish` writes every event of the task, in order, to `.baton/tasks/<task>.jsonl`, the file committed with the pull request. Its lines are ordinary events (as below). A later sandbox on the same task re-reads that file to resume. Other tasks fold it read-only to list its open `C` entries as live contracts (`<task>/<id>`); damaged lines are skipped.

## config.json

A JSON object. Missing keys take these defaults:

| Key | Type | Default |
|---|---|---|
| `format` | integer | `1` |
| `dir` | path | `".baton/events"` |
| `sprint` | string | `"S1"` |
| `board_md`, `status_md`, `contracts_index` | path | `.baton/BOARD.md`, `.baton/STATUS.md`, `.baton/CONTRACTS-INDEX.md` |
| `archive_dir` | path | `".baton/archive"` |
| `kinds` | object, kind letter → label | `Q`, `C`, `D`, `H`, `B` |
| `roles` | array of strings (empty = any) | `[]` |
| `handoff_max_lines` | integer | `20` |
| `body_warn_lines` | object, kind → integer | `{"C": 40, "D": 40}` |
| `unread_warn_tokens` | integer (0 = off) | `20000` |
| `id_width` | integer | `3` |
| `auto_render` | boolean | `true` |
| `shared_worktrees` | boolean | `true` |
| `policies` | array of rule objects (see the README) | `[]` |

## Events

Every line of a sprint file is one event. All events carry these fields:

| Field | Type | Meaning |
|---|---|---|
| `v` | integer | Format version. Absent on events written by baton 0.x, which are read as `1` |
| `type` | `"entry"`, `"reply"` or `"close"` | Event type |
| `ev` | integer | Format 1: global event number, unique and increasing; it defines the order. Format 2: not stored (readers number events locally) |
| `origin` | string | Format 2: the writing clone's id (`legacy` for upgraded format-1 events) |
| `seq` | integer | Format 2: 1, 2, 3… per origin; never reused |
| `uid` | string | Format 2: `<origin>.<seq>`, globally unique |
| `rec` | string | Format 2: UTC time the event was written (ISO 8601); orders events across clones |
| `id` | string | The thread the event belongs to (for an entry, its own id) |
| `from` | string | The role that wrote it |
| `sprint` | string | Sprint name; equals the file it is stored in |
| `ts` | string | Local time `YYYY-MM-DD HH:MM`. Imported entries may carry only `YYYY-MM-DD`, or `unknown` |
| `at` | string | Optional (baton ≥ 1.1): the exact time in UTC, ISO 8601 (`2026-10-07T18:55:03Z`). Metrics prefer it to `ts`. Imported events have none |

`entry` adds:

| Field | Type | Meaning |
|---|---|---|
| `kind` | string | One of the config `kinds` (imported entries may carry other letters) |
| `n` | integer | Format 1 (and imported entries): the id number from one counter for all kinds. Format 2 ids are `<kind>-<4+ uppercase hex>`, random, and have no `n` |
| `to` | array of strings | Addressed roles, or `["all"]` |
| `title`, `body` | string | Text. `title` may be empty on imported entries |
| `files`, `cites`, `blocks` | arrays of strings | Affected files (required for `C`), cited ids, and what the entry blocks |
| `status` | `"OPEN"` or `"CLOSED"` | Optional; the starting state of an imported entry (default `OPEN`) |
| `imported`, `imported_header` | boolean, string | Optional; set by `baton import` |

`status` (format 2) adds `role`, `phase`, `state` and `handoff` (strings); the latest status event per role is that role's row. `reply` adds `body` (string). `close` adds `reason` (string, may be empty). Replies and closes created by `baton import` (from `> [A]` answer lines and `status: CLOSED` markers) also carry `"imported": true`.

Ids look like `<kind>-<n zero-padded to id_width>`, for example `Q-007`. An imported duplicate gets the suffix `~2`, `~3` and so on.

## Folding events into threads

Read every sprint file. Format 1: sort by `ev`. Format 2: upgraded format-1 (`legacy`) events first in `ev` order, then the rest by (`rec`, `origin`, `seq`). Each `entry` starts a thread. Each `reply` with the same `id` is appended to it. A `close` marks it `CLOSED`, and the last `close` wins. Events whose `id` has no entry are ignored.

## status.json and cursors

Format 1: `status.json` maps each role to `{"phase", "state", "handoff", "updated"}`, all strings. A cursor file is `{"seen": {<origin>: <last seq seen>}, "ev": <the legacy part, for older readers>}`; an older `{"ev": n}` cursor means `{"seen": {"legacy": n}}`.

## Concurrency

Every write takes an exclusive `flock` on `.lock` (one per clone), computes the next `seq` (format 2) or `ev` and `n` (format 1), appends one line and releases the lock. Across clones there is no lock: each clone writes only its own files, and git merges them. The lock is advisory: tools that write the files directly bypass it.
