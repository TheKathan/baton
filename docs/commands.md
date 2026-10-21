# Commands

<p align="center"><img alt="The baton commands in a terminal: a question is posted, a hand-off is refused while it is open, the question is answered and closed, and the hand-off goes through" src="../assets/demo.gif" width="800"></p>

**The `baton` command is the primary interface, and agents should prefer it.** It has every option and works in any shell. The [MCP tools](#mcp-tools) run the same commands with the same rules, and exist only for agents that cannot run shell commands.

`baton --help` lists every command, `baton <command> --help` shows its flags, and `baton guide` prints the one-screen guide to paste into an agent's brief. Commands that act as a role take `--as <role>`, or read `BATON_ROLE` (see [Configuration](configuration.md#environment-variables)). Agents should pass `--as` on every command, because many agents start each shell command fresh. New to baton? Start with [Getting started](getting-started.md).

Message bodies come from stdin when you pass `-`, from words on the command line, or from `--body-file FILE`.

## Agents read at three moments

Agents read the board at three moments only, and never poll:

1. **At start:** `baton brief --as <role> --ids C-206,H-232`, then `baton unread --as <role>`.
2. **Before changing a shared package:** `baton unread --as <role>`, then `baton open --as <role>`. Use `baton grep <text>` and `baton show C-206` to look things up.
3. **Before reporting done:** `baton unread --as <role>`.

Read entries by id with `baton show` instead of scanning the board. That keeps an agent's context small.

## Daily work

### `baton brief`

The start-up pack in one call: the guide, your status, questions waiting for your answer, the entries your brief cites, your replied-to threads and (in a repository with exported task boards) the live contracts of other tasks. It does not move your cursor.

| Flag | Meaning |
|---|---|
| `--as ROLE` | Your role. |
| `--ids IDS` | Comma-separated entry ids your brief cites. Ids that are not board entries are listed as skipped. |

```bash
baton brief --as backend --ids C-206,H-232
```

### `baton unread`

New entries and replies that concern you, in full. It advances your read cursor.

| Flag | Meaning |
|---|---|
| `--as ROLE` | Your role. |
| `--all` | Every unread event, not only yours. |
| `--peek` | Do not advance your cursor. |
| `--mark-read` | Advance your cursor without printing. Use it when a stale cursor makes `unread` huge. |

```console
$ baton unread --as backend
### [Q-005] frontend → backend · status: OPEN · 2026-10-12 12:49
**Which route serves health?**
Which route?

1 unread; 1 question(s)/blocker(s) await your answer: Q-005
```

### `baton open`

Open threads you wrote or are named in.

| Flag | Meaning |
|---|---|
| `--as ROLE` | Your role. Without it, every open thread. |
| `--kind KINDS` | Only these kinds, for example `Q,B`. |
| `--all` | Also threads addressed to `all`. |
| `--blocking` | Only blockers and entries with `--blocks`. |
| `--stale AGE` | Only threads idle at least `AGE`: `2d`, `36h`, `90m`. |

```console
$ baton open --as backend
[Q-005] frontend → backend · OPEN · 2026-10-12 12:49 · Which route serves health?
1 open (2 more addressed to all; --all shows them)
```

### `baton show`

Prints entries by id, from any sprint, with their replies.

```bash
baton show C-206 H-150
```

### `baton list`

One line per entry, with filters.

| Flag | Meaning |
|---|---|
| `--sprint NAME` | Only this sprint. |
| `--kind KINDS` | For example `C` or `Q,B`. |
| `--status STATUS` | `open` or `closed`. |
| `--as ROLE` | Only entries involving this role. |

```bash
baton list --kind C --status open
```

### `baton grep`

Searches titles, bodies and replies for the words you give.

```bash
baton grep route
```

### `baton post`

Posts an entry of a kind: `Q` question, `C` contract change (needs `--files`), `D` decision, `B` blocker. Use `baton handoff` for `H`.

| Flag | Meaning |
|---|---|
| `--as ROLE` | Your role. |
| `--to ROLES` | Comma-separated roles, or `all` (the default). Name the role that must answer. |
| `--title TEXT` | Required. |
| `--files FILES` | Comma-separated affected files. Required for `C`. |
| `--cites IDS` | Comma-separated doc, story or decision ids. |
| `--blocks IDS` | Comma-separated stories or tasks this blocks. |
| `--supersedes IDS` | With `C`: the contracts this one replaces. baton cites them and closes them as `superseded by C-…`, so only one shape stays live. |
| `--model NAME` | The model you are. See [Which model wrote it](#which-model-wrote-it). |
| `--body-file FILE` | Read the body from a file. |

```console
$ echo "Which route serves the company health page?" | baton post Q --as frontend --to backend --title "Which route serves health?" -
posted Q-001
```

### `baton reply`

Answers a thread. `--close` also closes it, which is right when your answer settles it.

```console
$ baton reply Q-001 --as backend --close "Use GET /api/health."
replied to Q-001 and closed it
```

### `baton close`

Closes threads that are settled.

| Flag | Meaning |
|---|---|
| `IDS` | Entry ids to close. |
| `--reason TEXT` | Why, for example `superseded by C-210`. |
| `--phase NAME` | Close every open hand-off posted for this phase, for example once it passes its QA gate. |
| `--sprint NAME` | Close every settled open thread of a sprint. Unanswered `Q` and `B` and live `C` entries stay open. |
| `--include-unanswered` | With `--sprint`, also close unanswered questions and blockers. For imports. |
| `--include-contracts` | With `--sprint`, also close `C` entries. For imports. |
| `--outcome accepted\|rework` | With hand-offs: your verdict on the work you received. `rework` means it came back wrong. Closing a hand-off through `handoff --closes` records `accepted`. |
| `--model NAME` | The model you are. See [Which model wrote it](#which-model-wrote-it). |

```bash
baton close Q-231 --as backend --reason "answered in C-240"
baton close --phase S8-A --as orchestrator --reason "S8-A passed QA"
```

### `baton handoff`

Posts a hand-off (`H`) and updates your status row. It is refused while a question addressed to you is unanswered, or when the body is over `handoff_max_lines` (20). Nothing is posted in that case:

```text
baton: hand-off refused:
  - unanswered threads addressed to you: Q-001
  answer first: baton show Q-001, then baton reply Q-001 --as backend --close "…"
  (or hand off anyway with --force and the reason in the body)
```

| Flag | Meaning |
|---|---|
| `--as ROLE` | Your role. |
| `--phase TEXT` | Required. For example `S1-A`. It is stored on the entry, so `close --phase` can settle the phase's hand-offs. |
| `--state TEXT` | Required. For example `"DONE pending QA"`. |
| `--to ROLES` | Who picks it up. Default `all`. |
| `--title TEXT` | Required. |
| `--files FILES`, `--cites IDS` | Affected files; cited ids. |
| `--closes IDS` | Threads this hand-off settles, for example the hand-offs to you that you checked. |
| `--force` | Hand off despite the refusal. Give the reason in the body. |
| `--model NAME` | The model you are. See [Which model wrote it](#which-model-wrote-it). |

```console
$ baton handoff --as backend --phase S1-A --state "DONE pending QA" --to qa --title "S1-A backend" -
posted H-002; status of backend set to 'DONE pending QA'
```

After posting, baton notes the hand-offs to you that are still open, so a QA gate can close what it checked. A refused hand-off is recorded in a local log, see [`baton metrics`](#baton-metrics).

### `baton status`

Shows the status table, one row per role. With `--state` it sets your own row.

| Flag | Meaning |
|---|---|
| `--as ROLE` | Your role, when setting. |
| `--phase TEXT`, `--state TEXT`, `--handoff ID` | The row's values. |

```console
$ baton status --as qa --phase S1 --state testing
backend        S1-A       DONE  (H-001, 2026-10-12 12:49)
qa             S1         testing  (—, 2026-10-12 12:49)
```

## Sandbox

One board per task, for AI developers that work each issue in its own sandbox. The full guide is [Sandbox mode](sandbox.md).

### `baton init --sandbox --task ID`

Creates the task's board in this checkout, or resumes it from `.baton/tasks/<task>.jsonl`.

| Flag | Meaning |
|---|---|
| `--sandbox` | Create a task board. Needs `--task`. |
| `--task ID` | The issue id, for example `LIN-123`. |
| `--roles ROLES` | Comma-separated allowed roles. Empty allows any. |
| `--force` | Start over when the checkout already has a sandbox board. |

```console
$ baton init --sandbox --task LIN-123 --roles orchestrator,backend,qa
sandbox board for LIN-123: new task board
```

### `baton contracts`

Lists live contracts: this board's own, and those of other tasks merged into your branch.

| Flag | Meaning |
|---|---|
| `--paths GLOBS` | Only contracts touching these comma-separated globs. |

```console
$ baton contracts --paths 'modules/network/**'
[LIN-100/C-001] backend · Subnet output shape · files: modules/network/outputs.tf
0 live contract(s) on this board, 1 from other tasks
```

### `baton finish`

Exports the board to `.baton/tasks/<task>.jsonl` and prints a Markdown summary for the PR. Sandbox boards only.

| Flag | Meaning |
|---|---|
| `--summary FILE` | Write the summary to `FILE` instead of printing it. |
| `--strict` | Exit 1 while questions or blockers are open. |

```bash
baton finish --strict --summary pr.md
```

### `baton report`

Reports on exported task boards (`.baton/tasks/<task>.jsonl`): the same Markdown summary as `finish`, one section per task. It needs no board and writes nothing to `.baton/`, so it suits a check that runs on the pull request. See [Use it in a workflow](sandbox.md#use-it-in-a-workflow).

| Flag | Meaning |
|---|---|
| `FILES` | Exported task files to report on. |
| `--since REF` | Instead of files, report every task file added or changed since this git ref, for example `origin/main`. Nothing changed prints a note and exits 0. |
| `--root DIR` | With `--since`: the repository. Default: the current directory. |
| `--strict` | Exit 1 while any task has open questions or blockers. |
| `--summary FILE` | Write the report to `FILE` instead of printing it. |
| `--json` | Machine-readable output: task, file, thread count, open question and blocker ids, summary. |

```bash
baton report --since origin/main --strict --summary report.md
```

## Orchestrator

### `baton sprint`

Archives the current sprint to `.baton/archive/` and starts a new one. Open threads carry over and stay on the live board.

| Flag | Meaning |
|---|---|
| `NAME` | The new sprint, for example `S2`. |
| `--force` | Accept a name without digits. |

```console
$ baton sprint S2
archived S1 to .baton/archive/BOARD-S1.md; current sprint is now S2
```

When threads are still open, a second line says how many carried over.

The orchestrator closes a phase after its gate passes with `baton close --phase S1-A --as orchestrator`, and a sprint with `baton open --blocking`, then `baton close --sprint S1 --as orchestrator`, then `baton sprint S2`.

### `baton metrics`

Board health: answer and close times, stale threads, quiet contracts, refused writes, per-role load and token cost, how roles behave around hand-offs, and the same by model.

- **Stale** threads are open threads idle for at least `--stale`. Open contracts are left out: a contract stays open while it holds.
- **Quiet contracts** are open `C` entries that nobody has replied to or cited for at least `--stale`. Check that they still hold, then supersede or close them.
- **Refused** counts the writes baton refused (hand-offs, contracts without files, policies) and the hand-offs forced with `--force`. It also says how many hand-offs refused on an open question were resolved by answering it. The log is `<dir>/.local/refusals.jsonl`: local to the checkout, git-ignored, and not part of the board.

- **Hand-offs by role** counts the hand-offs a role sent and how the receivers judged them (`accepted`, `rework`), and:
  - *bounced*: later threads from others that cite one of its hand-offs;
  - *median hold*: from a hand-off a role received to its next hand-off;
  - *median pickup*: from a hand-off a role received to its first event after it;
  - *refused* and *forced* hand-offs (from the local log).
- **By model** counts events and hand-offs per model, and the verdicts on those hand-offs. These numbers describe how work moves between agents, not how good the code is, so read them as a place to look, not a score. A model that only wrote a few hand-offs says little.

| Flag | Meaning |
|---|---|
| `--sprint NAME` | Only this sprint. Default: all. |
| `--stale AGE` | Idle time that counts as stale. Default `48h`. |
| `--json` | Machine-readable output. |

```bash
baton metrics --sprint S7 --stale 36h
```

### `baton lint`

Checks duplicate ids, unknown kinds, contracts without files, oversized hand-offs and bodies, and your [policies](policies.md). Exits 1 on errors, 0 on warnings. Imported entries are skipped, because their problems were reported at import time; `--all` checks them too.

| Flag | Meaning |
|---|---|
| `--all` | Also check imported entries. |
| `--suggest` | Propose [policies](policies.md#suggested-policies) that most of the board's entries already follow, as a config snippet. Changes nothing. |

```console
$ baton lint
warn  Q-003: policy named_to (Q): must be addressed to a role by name, not only to all (--to <role>)
3 entries, 0 error(s), 1 warning(s)
```

### `baton stats`

Estimated token cost of what each sprint holds and what each role would read now. `--as ROLE` limits it to one role.

### `baton serve`

A read-only local board in your browser. It accepts only GET requests and refreshes every 30 seconds.

The board puts each question, blocker and hand-off of the current sprint (or sandbox task) in one column that says its state:

| Column | What is in it |
|---|---|
| Blocked | An open blocker nobody has answered. |
| Needs an answer | An open question nobody has answered. Its card shows which hand-off it is locking. |
| Answered, close it | An open question or blocker the addressee replied to. |
| To pick up | An open hand-off that a recipient has not picked up (has not handed off since). |
| In progress | A role whose status row is active (not `DONE`, not waiting) and that has an open thread of its own. |
| Passed on | An open hand-off whose recipients have all handed off since. Close it. |
| Done | Closed questions, blockers and hand-offs, newest first. |

A card says who must act next. Above the columns, a card per role shows its status, who holds the baton and whether its next hand-off is locked. Decisions and contracts are records, not work, so they sit below the board and never count as open. A card is flagged "touches C-x" when its `--files` overlap a live contract.

| Page | Shows |
|---|---|
| `/` | The board. |
| `/contracts` | Live contracts by file area. `?f=new`, `old` or `touched` filters them. In a sandbox it includes the contracts of merged tasks. |
| `/metrics` | Answer and close times, stale threads, and the load per sprint and per role. |
| `/e/<id>` | One entry and its replies. |

| Flag | Meaning |
|---|---|
| `--host HOST` | Default `127.0.0.1`. |
| `--port PORT` | Default `8765`. |
| `--open` | Open it in the browser. |

```bash
baton serve --open
```

The board is also at `/api/board.json`, and the metrics at `/api/metrics.json`.

## Which model wrote it

Every entry, reply and close records the model that wrote it as `model`, with `model_src` saying where the name came from. baton looks in this order and stops at the first match:

1. `--model NAME` on `post`, `reply`, `close` or `handoff`. Any agent can pass it: it knows its own model id.
2. `$BATON_MODEL`, for a wrapper or hook that knows the model.
3. Detection. baton reads the model name from the tail of the session record of the agent running the command, and keeps nothing else. It works for Claude Code (found by `$CLAUDE_CODE_SESSION_ID`, and it follows `/model`) and for Codex (found by `$CODEX_THREAD_ID`). Those record layouts are not a documented interface, so detection is best effort: when it finds nothing, no model is recorded and no command fails. Set `BATON_MODEL_DETECT=0` to turn it off.

A hand-off that records no model prints a note asking for `--model`. A sub-agent on a different model from its parent is detected only if it runs as its own session, so pass `--model` there.

## Setup and maintenance

### `baton init`

Creates `.baton/config.json` and the board directory.

| Flag | Meaning |
|---|---|
| `--sprint NAME` | The first sprint. Default `S1`. |
| `--roles ROLES` | Comma-separated allowed roles. Empty allows any. |
| `--dir DIR` | The event directory. Default `.baton/events`. |
| `--root DIR` | The project root. Default: the current directory. |
| `--force` | Overwrite an existing config. |

```bash
baton init --sprint S1 --roles orchestrator,backend,frontend,qa
```

### `baton skill`

Prints or installs the agent skill (Claude Code format). Actions: `install` (the default), `show`, `path`. By default `install` writes to `~/.claude/skills/`, for every project on your machine. For other agents, see [Set up your agents](getting-started.md#4-set-up-your-agents).

| Flag | Meaning |
|---|---|
| `--project` | Install into the project's `.claude/skills/`, to commit. |
| `--dir DIR` | Install into `DIR/baton/SKILL.md`. |
| `--force` | Replace a different existing copy. Run it after upgrading baton. |

```bash
baton skill install --project
```

### `baton mcp`

Runs the MCP server on stdio (`serve`, the default), or registers it in `.mcp.json` (`install`).

| Flag | Meaning |
|---|---|
| `--command CMD` | The command MCP clients run. Default `baton`. Give a full path when `baton` isn't on the client's `PATH`. |
| `--file FILE` | The `.mcp.json` to update. Default: the project's. |

```bash
baton mcp install --command ~/.local/bin/baton
```

### `baton render`

Regenerates the Markdown views (`BOARD.md`, `STATUS.md`, `CONTRACTS-INDEX.md`). They are rewritten after every write, so you rarely need it. `--archives` also re-renders every past sprint.

### `baton import`

Imports a hand-written Markdown board as one sprint. Answers become replies and `CLOSED` markers become close events.

| Flag | Meaning |
|---|---|
| `FILE` | The Markdown file. |
| `--sprint NAME` | Required. The sprint to import it as. |
| `--dry-run` | Report what would be imported and write nothing. |

```bash
baton import old-board.md --sprint S0 --dry-run
```

### `baton migrate`

Reports the board's on-disk format and records the current one in the config. `--check` only reports. Event files are never rewritten. See the [board format](FORMAT.md).

### `baton demo`

A 20-second narrated walkthrough on a throwaway board, for a first look with no agents and no setup: frontend asks backend a question, backend's hand-off is refused, backend answers and the hand-off goes through, then `baton list` and `baton status`. Every step runs the real commands on a temporary board; your project and its `.baton/` are never touched.

| Flag | Meaning |
|---|---|
| `--fast` | No pauses, for tests and CI. |
| `--keep DIR` | Build the board in `DIR` (which must not have a `.baton/` yet) and keep it to explore. |

```bash
baton demo
baton demo --keep /tmp/baton-demo
```

### `baton where`

Prints the project root and the config in use as JSON. Inside a linked git worktree it shows `shared_from_worktree` too.

### `baton guide`

Prints the one-screen guide for an agent's brief.

## MCP tools

`baton mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server on stdio, with no dependencies. Its instructions tell clients to prefer the `baton` command when they can run shell commands. Each tool runs the matching command in-process, so the same rules apply: the hand-off cap, the unanswered-question check, `C` entries needing files and your policies.

Register it with `baton mcp install`. Each tool takes a `role` argument, or uses `BATON_ROLE`. The tools that write also take `model`, or use `BATON_MODEL`, and `baton_close` takes `outcome`. The board is found from the server's working directory, or from `BATON_ROOT`.

| Tool | Same as | Arguments |
|---|---|---|
| `baton_brief` | `baton brief` | `role`, `ids` |
| `baton_unread` | `baton unread` | `role`, `peek` |
| `baton_show` | `baton show` | `ids` |
| `baton_open` | `baton open` | `role`, `all`, `blocking`, `stale` |
| `baton_grep` | `baton grep` | `text` |
| `baton_list` | `baton list` | `sprint`, `kind`, `status`, `role` |
| `baton_post` | `baton post` | `role`, `kind`, `to`, `title`, `body`, `files`, `cites`, `blocks`, `supersedes` |
| `baton_reply` | `baton reply` | `role`, `id`, `body`, `close` |
| `baton_close` | `baton close` | `role`, `ids`, `reason`, `sprint`, `phase` |
| `baton_handoff` | `baton handoff` | `role`, `phase`, `state`, `to`, `title`, `body`, `files`, `cites`, `closes`, `force` |
| `baton_status` | `baton status` | `role`, `phase`, `state` (set your row when `state` is given) |
| `baton_sandbox_start` | `baton init --sandbox --task` | `task`, `roles`, `force` |
| `baton_contracts` | `baton contracts` | `paths` |
| `baton_finish` | `baton finish` | `strict` |
| `baton_sprint` | `baton sprint` | `name` |
| `baton_metrics` | `baton metrics` | `sprint`, `stale` |
| `baton_lint` | `baton lint` | `all`, `suggest` |

`baton_post` offers the entry kinds from your config, without `H`. Tools return the command's output as text, with `isError` set when the command failed.

There is no MCP tool for `init` (without `--sandbox`), `render`, `import`, `skill`, `migrate`, `stats`, `serve`, `report`, `demo` or `where`. Run those with the command.
