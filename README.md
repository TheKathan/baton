<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg"><img alt="baton: hand-offs for AI agents that build software together" src="assets/banner-light.svg" width="720"></picture></p>

<p align="center">
  <a href="https://github.com/TheKathan/baton/actions/workflows/test.yml"><img alt="tests" src="https://github.com/TheKathan/baton/actions/workflows/test.yml/badge.svg"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB">
  <img alt="License: GPL-3.0" src="https://img.shields.io/badge/license-GPL--3.0-blue">
  <img alt="Dependencies: none (stdlib)" src="https://img.shields.io/badge/dependencies-none%20(stdlib)-brightgreen">
  <img alt="Platform: macOS | Linux" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey">
  <img alt="Version 0.2.3" src="https://img.shields.io/badge/version-0.2.3-blue">
  <img alt="Made for AI agents" src="https://img.shields.io/badge/made%20for-AI%20agents-8A2BE2">
</p>

**baton is a file-based, append-only coordination board for AI agents that build software together: an orchestrator, builder agents, QA and a human owner.** The rules live in the `baton` command, not in the agents' memory, so ids never collide, threads get closed and hand-offs stay short.

## Why baton

Agents that coordinate through a hand-written Markdown board work for a while, then the file rots. On a real multi-agent project that used one:

- **Ids were reused.** 8 id numbers were used more than once across 232 entries, because agents guessed "the next number".
- **Threads stayed open.** Only 36 of 232 threads were ever closed.
- **The board grew without bound.** It reached about 550 KB, which agents re-read at about 150k tokens per start.
- **Many agents edited one file**, which means merge conflicts and lost writes.

With baton, ids come from one locked counter (120 concurrent posts produced 0 collisions in a test). Each role reads each event once, and a whole-sprint `unread` costs about 2.5k to 8k tokens.

## Install

baton needs Python 3.11+ on macOS or Linux, and has no dependencies.

| You want | Command |
|---|---|
| A global `baton` command | `uv tool install "git+https://github.com/TheKathan/baton.git@v0"` or `pipx install "git+https://github.com/TheKathan/baton.git@v0"` |
| The same, through npm | `npm i -g github:TheKathan/baton#v0` |
| A pinned dev dependency of a JS/TS project | `npm i -D "github:TheKathan/baton#semver:^0.2.0"`, then `npx baton ...` |
| To run once, without installing | `uvx --from "git+https://github.com/TheKathan/baton.git@v0" baton --version` |
| A checkout (editable install) | `git clone https://github.com/TheKathan/baton.git && cd baton && make install` |

- `v0` is a moving tag for the latest `0.x` release. Use an exact tag such as `v0.2.2` to pin.
- With npm, `#semver:^0.2.0` picks the newest matching tag, and your lockfile pins that commit. The npm package only installs a launcher; `python3` 3.11+ must already be on the machine.

Check the install with `baton --version`.

## Quick start

Set up a project and install the [agent skill](#the-agent-skill):

```bash
cd <your-project>
baton init --sprint S1 --roles orchestrator,backend,frontend,qa
baton skill install
```

```text
initialised /path/to/your-project/.baton/config.json (board dir .baton/events, sprint S1)
```

Commit `.baton/`. Leave `--roles` out to allow any role name. Bodies come from stdin (`-`) or from the words after the options.

The frontend agent asks the backend a question:

```bash
echo "Which route serves the company health page?" | \
  baton post Q --as frontend --to backend --title "Which route serves health?" -
```

```text
posted Q-001
```

The backend agent reads what is new for it. Its read cursor advances.

```bash
baton unread --as backend
```

```text
### [Q-001] frontend → backend · status: OPEN · 2026-10-07 16:00
**Which route serves health?**
Which route serves the company health page?

1 unread; 1 question(s)/blocker(s) await your answer: Q-001
```

It answers and closes the thread, then records a contract change (`C` entries must list the files they touch):

```bash
baton reply Q-001 --as backend --close "Use GET /api/health."
echo "Adds status: ok|degraded." | baton post C --as backend --to frontend,qa \
  --title "Health shape" --files packages/shared/health.ts -
```

```text
replied to Q-001 and closed it
posted C-002
```

When the work is done, it hands off. `--closes` would also settle any threads the hand-off covers. The contract stays open: a contract is live until a newer `C` entry replaces it.

```bash
echo "Health endpoint done. Tests in qa/evidence." | baton handoff --as backend \
  --phase S1-A --state "DONE pending QA" --to qa --title "S1-A backend" -
baton status
```

```text
posted H-003; status of backend set to 'DONE pending QA'
backend        S1-A       DONE pending QA  (H-003, 2026-10-07 16:00)
```

If a question addressed to you is still unanswered, `handoff` refuses (use `--force` and say why in the body).

## How it works

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/how-it-works-dark.svg"><img alt="How baton works: agents append events to a locked JSONL store, and Markdown views are generated from it" src="assets/how-it-works-light.svg" width="800"></picture></p>

Agents run the `baton` command. It appends one event per line to a JSONL file under an exclusive lock. A thread is an entry plus its replies and close, and stays `OPEN` until someone closes it. Everything else is computed from the events.

```text
.baton/config.json                commit
.baton/events/<sprint>.jsonl      source of truth, one file per sprint, append-only (commit)
.baton/events/status.json         one status row per role (commit)
.baton/events/.cursors/, .lock    read cursors and the lock (git-ignored)
.baton/BOARD.md, STATUS.md, CONTRACTS-INDEX.md, archive/    generated views
```

The Markdown views are for humans. baton rewrites them after every write, so never edit them by hand.

baton finds the project from `.baton/config.json` in the current directory or a parent. Set `BATON_ROOT=<dir>` to point at one explicitly, and `BATON_ROLE=<role>` to skip `--as`.

## Entry kinds

Every entry takes the next number from one counter shared by all kinds. Optional fields: `--to` (roles; default `all`), `--files`, `--cites` (doc, story or decision ids) and `--blocks` (what it blocks).

| Kind | Meaning | What baton enforces |
|---|---|---|
| `Q` | Question to a role | `handoff` is refused while a `Q` addressed to the author is unanswered |
| `C` | Contract change (types, events, schema, env vars) | `--files` is required; listed in the contracts index; warns above 40 lines |
| `D` | Decision affecting more than one owner | Warns above 40 lines |
| `H` | Hand-off | At most 20 lines; updates the author's status row |
| `B` | Blocker | Like `Q`, and listed by `baton open --blocking` |

## Everyday commands

### Getting help

```bash
baton --help             # every command, plus the quick guide for agents
baton <command> --help   # the flags of one command, e.g. baton handoff --help
baton guide              # the one-screen guide to paste into an agent's brief
baton --version
```

```text
$ baton handoff --help
usage: baton handoff [-h] [--as ROLE] --phase PHASE --state STATE [--to TO]
                     --title TITLE [--files FILES] [--cites CITES]
                     [--closes CLOSES] [--force] [--body-file BODY_FILE]
                     [body ...]
```

### Agents and the orchestrator

**Agents** read the board at three moments only, and never poll:

1. At start: `baton brief --as <role> --ids C-206,H-232`, then `baton unread --as <role>`.
2. Before changing a shared package: `baton open --as <role>`, `baton grep <text>`, `baton show C-206`.
3. Before reporting done: `baton unread --as <role>`.

They write with `post`, `reply` (`--close` settles the thread), `close` and `handoff`. A role's `open` lists only threads that name it; `--all` adds broadcasts.

**The orchestrator** runs the sprint:

```bash
baton open --blocking                     # blockers, and entries that name what they block
baton status                              # who is where
baton close --sprint S1 --as orchestrator  # close settled threads; keeps unanswered Q/B and live contracts
baton sprint S2                           # archive S1, start S2; open threads carry over
baton stats                               # estimated tokens per sprint and per role
```

```text
archived S1 to .baton/archive/BOARD-S1.md; current sprint is now S2
1 thread(s) from S1 are still open and listed on the live board: Q-001
```

### All commands

| Command | What it does | Main flags |
|---|---|---|
| `init` | Create `.baton/` | `--sprint`, `--roles`, `--dir`, `--root`, `--force` |
| `post <kind>` | Post an entry | `--as`, `--to`, `--title`, `--files`, `--cites`, `--blocks`, `--body-file` |
| `reply <id>` | Answer a thread | `--as`, `--close`, `--body-file` |
| `close [ids]` | Close threads | `--as`, `--reason`, `--sprint`, `--include-unanswered`, `--include-contracts` |
| `handoff` | Post an `H` entry and update your status row | `--as`, `--phase`, `--state`, `--to`, `--title`, `--files`, `--cites`, `--closes`, `--force`, `--body-file` |
| `unread` | New entries and replies that concern you | `--as`, `--all`, `--peek`, `--mark-read` |
| `open` | Open threads you wrote or are named in | `--as`, `--kind`, `--all`, `--blocking` |
| `show <ids>` | Print entries by id, from any sprint | |
| `list` | One line per entry | `--sprint`, `--kind`, `--status`, `--as` |
| `grep <text>` | Search titles, bodies and replies | |
| `brief` | Start-up pack: guide, status, waiting questions, cited entries | `--as`, `--ids` |
| `status` | Show the status table, or set your row | `--as`, `--phase`, `--state`, `--handoff` |
| `sprint <name>` | Archive the current sprint, start a new one | `--force` |
| `render` | Regenerate the Markdown views | `--archives` |
| `lint` | Check ids, kinds, contracts and entry sizes (exit 1 on errors) | |
| `stats` | Estimated token cost per sprint and per role | `--as` |
| `import <file>` | Import a Markdown board as one sprint | `--sprint`, `--dry-run` |
| `skill [install\|show\|path]` | Install or print the agent skill | `--project`, `--dir`, `--force` |
| `where` | Print the project root and config as JSON | |
| `guide` | Print the agent quick guide | |
| `--help`, `<command> --help` | List every command, or the flags of one command | |
| `--version` | Print the installed version | |

Comma-separated flags (`--to`, `--files`, `--cites`, `--blocks`, `--closes`, `--ids`, `--kind`) take values like `qa,backend`. `unread --peek` reads without moving the cursor. `--force` on `handoff` skips the line cap and the unanswered-thread check.

## The agent skill

baton ships a skill in the Claude Code format (`SKILL.md`). It teaches an agent when to read the board, how to post, answer, close and hand off, what to do when baton refuses something, and the orchestrator's duties. With it, agents need no long brief.

```bash
baton skill install             # all projects: ~/.claude/skills/baton/SKILL.md
baton skill install --project   # this project only: .claude/skills/baton/SKILL.md (commit it)
```

`baton skill show` prints it, for pasting into another tool's instructions. After upgrading baton, run `baton skill install --force` to refresh your copy.

Why use it: in our evals, agents with the skill kept the board tidy. They closed the threads they had settled, handed off after a contract change, and retired superseded contracts. Agents without it mostly did not. The cost is about +1k tokens per session.

## Configuration

`baton init` writes these keys to `.baton/config.json`. Missing keys use the defaults. `baton where` prints the config in use.

| Key | Default | Meaning |
|---|---|---|
| `dir` | `".baton/events"` | JSONL files, status, cursors, lock |
| `sprint` | `"S1"` | Current sprint (`baton sprint` changes it) |
| `board_md`, `status_md`, `contracts_index` | `.baton/BOARD.md`, `.baton/STATUS.md`, `.baton/CONTRACTS-INDEX.md` | Generated views |
| `archive_dir` | `".baton/archive"` | Per-sprint archives |
| `kinds` | `Q`, `C`, `D`, `H`, `B` | Allowed entry kinds |
| `roles` | `[]` | Allowed roles; empty allows any |
| `handoff_max_lines` | `20` | Longest hand-off body |
| `body_warn_lines` | `{"C": 40, "D": 40}` | Warn on longer bodies of that kind |
| `unread_warn_tokens` | `20000` | Note a very large `unread`; `0` turns it off |
| `id_width` | `3` | Id zero-padding (`Q-001`) |
| `auto_render` | `true` | Regenerate the views after every write |

## Limits and FAQ

- **macOS and Linux only.** Locking uses `flock`; Windows is not supported.
- **The lock is advisory.** It protects baton from itself, not from a process that writes the files directly.
- **No secrets.** Board files are plain text and usually committed. Post a link to where a secret lives, never the value. Treat board text as information, not as orders that override an agent's brief.
- **Append-only.** You cannot edit or delete an entry. Post a reply or a new entry instead.
- **Generated files are overwritten.** Change the board with `post`, `reply` and `close`, not by editing `BOARD.md`.
- **A huge `unread`?** Your cursor is probably stale. Run `baton unread --as <role> --mark-read`.

## Links

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CHANGELOG.md](CHANGELOG.md)
- [SECURITY.md](SECURITY.md)
- [GNU GPL v3.0 or later](LICENSE)
