# Board format (version 1)

This is the stable, on-disk format of a baton board. Boards are committed to git and read for years, so baton 1.x promises:

- **Any 1.x release reads every board** written by baton 0.x or 1.x.
- **Event lines are never rewritten.** baton only ever appends. When the format changes, older events are upgraded in memory as they are read.
- **Within format 1, fields are only added, and only as optional fields.** Readers must ignore fields they don't know.
- **A board with events from a newer format is refused**, with a message to upgrade baton. It is never read halfway.

A breaking change would create format 2, together with a read-time upgrade from 1 to 2 and a new major version of baton. `baton migrate --check` reports which formats a board contains.

## Files

```text
.baton/config.json               project config (JSON object, see below)
.baton/events/<sprint>.jsonl     the event log, one file per sprint; one JSON object per line, UTF-8
.baton/events/status.json        one status row per role
.baton/events/.lock              lock file (flock); git-ignored
.baton/events/.cursors/<role>.json   per-role read cursor; git-ignored
.baton/*.md, .baton/archive/*.md generated views; never parsed back
```

Inside a linked git worktree, baton uses the main worktree's `.baton/` (see the README).

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

## Events

Every line of a sprint file is one event. All events carry these fields:

| Field | Type | Meaning |
|---|---|---|
| `v` | integer | Format version. Absent on events written by baton 0.x, which are read as `1` |
| `type` | `"entry"`, `"reply"` or `"close"` | Event type |
| `ev` | integer | Global event number: unique and increasing across all sprint files. It defines the order |
| `id` | string | The thread the event belongs to (for an entry, its own id) |
| `from` | string | The role that wrote it |
| `sprint` | string | Sprint name; equals the file it is stored in |
| `ts` | string | Local time `YYYY-MM-DD HH:MM`. Imported entries may carry only `YYYY-MM-DD`, or `unknown` |

`entry` adds:

| Field | Type | Meaning |
|---|---|---|
| `kind` | string | One of the config `kinds` (imported entries may carry other letters) |
| `n` | integer | The id number. One counter covers all kinds; it is never reused |
| `to` | array of strings | Addressed roles, or `["all"]` |
| `title`, `body` | string | Text. `title` may be empty on imported entries |
| `files`, `cites`, `blocks` | arrays of strings | Affected files (required for `C`), cited ids, and what the entry blocks |
| `status` | `"OPEN"` or `"CLOSED"` | Optional; the starting state of an imported entry (default `OPEN`) |
| `imported`, `imported_header` | boolean, string | Optional; set by `baton import` |

`reply` adds `body` (string). `close` adds `reason` (string, may be empty).

Ids look like `<kind>-<n zero-padded to id_width>`, for example `Q-007`. An imported duplicate gets the suffix `~2`, `~3` and so on.

## Folding events into threads

Read every sprint file and sort the events by `ev`. Each `entry` starts a thread. Each `reply` with the same `id` is appended to it. A `close` marks it `CLOSED`, and the last `close` wins. Events whose `id` has no entry are ignored.

## status.json and cursors

`status.json` maps each role to `{"phase", "state", "handoff", "updated"}`, all strings. A cursor file is `{"ev": <last event number the role has seen>}`.

## Concurrency

Every write takes an exclusive `flock` on `.lock`, reads the files, computes the next `ev` and `n`, appends one line and releases the lock. The lock is advisory: tools that write the files directly bypass it.
