# Configuration

baton reads its settings from `.baton/config.json` at the project root. Keys you leave out use the defaults below. `baton init` writes the file, and `baton where` prints the configuration in use, together with the project root.

## `.baton/config.json`

| Key | Default | Meaning |
|---|---|---|
| `format` | `1` | The board format version. Set by `baton init`. See [FORMAT.md](FORMAT.md). |
| `dir` | `".baton/events"` | Where the event log, status file, cursors, lock and local refusal log (`.local/`) live. |
| `sprint` | `"S1"` | The current sprint. `baton sprint` changes it. |
| `roles` | `[]` | The allowed role names. An empty list allows any role. |
| `kinds` | `{"Q": "question", "C": "contract change", "D": "decision", "H": "hand-off", "B": "blocker"}` | Entry kinds and their names. |
| `handoff_max_lines` | `20` | The longest hand-off body baton accepts. Longer ones are refused. |
| `body_warn_lines` | `{"C": 40, "D": 40}` | Per-kind body length that triggers a warning. |
| `unread_warn_tokens` | `20000` | `unread` notes when its output passes this many tokens. `0` turns the note off. |
| `id_width` | `3` | Digits in ids: `Q-001`. |
| `auto_render` | `true` | Regenerate the Markdown views after every write. |
| `shared_worktrees` | `true` | In a linked git worktree, use the main worktree's board. |
| `board_md` | `".baton/BOARD.md"` | Path of the generated board view. |
| `status_md` | `".baton/STATUS.md"` | Path of the generated status view. |
| `contracts_index` | `".baton/CONTRACTS-INDEX.md"` | Path of the generated contracts index. |
| `archive_dir` | `".baton/archive"` | Where `baton sprint` writes archived sprints. |
| `policies` | none | Your team's rules. See [Policies](policies.md). |

The generated `.md` views are rewritten after every write. Never edit them by hand.

A small config:

```json
{
  "sprint": "S1",
  "roles": ["orchestrator", "backend", "frontend", "qa"],
  "handoff_max_lines": 15,
  "unread_warn_tokens": 10000
}
```

## `.baton/sandbox.json`

`baton init --sandbox --task LIN-123` writes this file instead of `config.json`. It takes the same keys, with these values for the task's board:

| Key | Value in a sandbox |
|---|---|
| `sandbox` | `true` |
| `task` | The task id you passed. |
| `sprint` | The task id. |
| `roles` | The `--roles` you passed, else the project's `roles`, else empty (any role). |
| `dir` | `".baton/sandbox/events"` |
| `board_md`, `status_md`, `contracts_index`, `archive_dir` | Files under `.baton/sandbox/`. |
| `auto_render` | `false` |
| `shared_worktrees` | `false` |

If the checkout has a `.baton/config.json`, the sandbox copies the team's settings from it when it is created: `policies`, `kinds`, `roles` (unless you pass `--roles`), `handoff_max_lines`, `body_warn_lines`, `unread_warn_tokens` and `id_width`. Every other key keeps its default, and you can still edit the copy in `sandbox.json`. It lives only in this checkout (it is listed in `.git/info/exclude`). A checkout with a `sandbox.json` uses it instead of `config.json`, and it is never redirected to another worktree. See [Sandbox mode](sandbox.md).

## Environment variables

| Variable | Meaning |
|---|---|
| `BATON_ROOT` | The project directory to use, instead of searching upwards from the current directory. It must contain `.baton/config.json` or `.baton/sandbox.json`. The MCP server also uses it for `baton_sandbox_start`. |
| `BATON_ROLE` | Your role, so you can skip `--as`. Used by the CLI and by MCP tools that take a `role`. |

```bash
export BATON_ROOT=/work/my-project
export BATON_ROLE=backend
baton unread
```

baton has no other environment variables.

## How baton finds the board

1. If `BATON_ROOT` is set, baton uses that directory.
2. Otherwise it searches upwards from the current directory for `.baton/sandbox.json`. A sandbox board is used as found.
3. Otherwise it searches upwards for `.baton/config.json`. Inside a linked git worktree, and with `shared_worktrees` on, baton uses the main worktree's `.baton/` instead, so every agent shares one counter and one lock.

If none is found, baton says `run baton init first`.
