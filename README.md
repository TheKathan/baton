<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg"><img alt="baton: hand-offs for AI agents that build software together" src="assets/banner-light.svg" width="720"></picture></p>

<p align="center">
  <a href="https://github.com/TheKathan/baton/actions/workflows/test.yml"><img alt="tests" src="https://github.com/TheKathan/baton/actions/workflows/test.yml/badge.svg"></a>
  <img alt="latest release" src="https://img.shields.io/github/v/release/TheKathan/baton">
  <img alt="license" src="https://img.shields.io/github/license/TheKathan/baton">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB">
  <img alt="dependencies: none" src="https://img.shields.io/badge/dependencies-none-brightgreen">
</p>

**Agents that hand work to each other, and a board that refuses the sloppy hand-offs.** baton is a file-based, append-only coordination board for AI agents that build software together: an orchestrator, builder agents, QA and a human owner. It lives in your project's `.baton/` folder, in git, and you use it through the `baton` command. No server, no database, no dependencies.

**Works with** Claude Code, Codex, Cursor or any MCP client, and with any agent that can run a shell command, including AI developers that work one issue per sandbox ([sandbox mode](#sandbox-mode-one-board-per-task)).

```console
$ echo "Which route serves the company health page?" | baton post Q --as frontend --to backend --title "Which route serves health?" -
posted Q-20CB
$ echo "Health endpoint done." | baton handoff --as backend --phase S1-A --state "DONE pending QA" --to qa --title "S1-A backend" -
baton: hand-off refused:
  - unanswered threads addressed to you: Q-20CB
  (use --force with a reason in the body)
$ baton reply Q-20CB --as backend --close "Use GET /api/health."
replied to Q-20CB and closed it
$ echo "Health endpoint done." | baton handoff --as backend --phase S1-A --state "DONE pending QA" --to qa --title "S1-A backend" -
posted H-7F08; status of backend set to 'DONE pending QA'
```

## Why baton

A hand-written Markdown board works for a while, then it rots. On a real multi-agent project that used one, 8 ids were reused in 232 entries, only 36 of 232 threads were ever closed, and the board reached about 550 KB. Agents re-read it at about 150k tokens per start. baton moves the rules out of the agents' memory and into the command:

- **Agents never trip over each other, on one machine or across a team.** Entries are only appended, under a lock on each machine, and every clone writes its own log file, so merges of the board don't conflict.
- **Agents read only what is new for them.** Each role has a read cursor, so a whole-sprint `unread` costs about 2.5k to 8k tokens, not 150k.
- **The board stays tidy.** `reply --close` settles a thread, `close --sprint` keeps unanswered questions and live contracts, and `handoff` is capped at 20 lines and refused while a question to you is unanswered.
- **Contracts between agents are explicit.** A `C` entry must list the files it touches, and the contracts index shows which contract is live.
- **Humans get readable views and an audit trail.** `BOARD.md` and `STATUS.md` are generated after every write. The event log in git shows who said what and when.
- **It fits AI-driven development.** In sandbox mode each issue gets its own board, offline, and the board ships with the pull request, so reviewers see what the agents decided and why.
- **There is nothing to set up.** It is plain files in git, and the same rules apply from the CLI and from MCP.

## How it works

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/how-it-works-dark.svg"><img alt="How baton works: agents append events to a locked JSONL store, and Markdown views are generated from it" src="assets/how-it-works-light.svg" width="800"></picture></p>

Agents run the `baton` command. It appends one event per line to this clone's own JSONL log, under an exclusive lock. A thread is an entry plus its replies and close, and it stays `OPEN` until someone closes it. Everything else is computed from the events. Entry kinds are `Q` question, `C` contract change, `D` decision, `H` hand-off and `B` blocker.

```text
.baton/config.json                       commit
.baton/events/<sprint>/<clone-id>.jsonl  source of truth: one append-only log per clone per sprint (commit)
.baton/events/.cursors/, .lock, .clone-id   read cursors, the lock, this clone's id (git-ignored)
.baton/BOARD.md, STATUS.md, CONTRACTS-INDEX.md, archive/   generated views (git-ignored)
```

**Built for teams.** Everyone commits the board: each clone appends only to its own log, so `git pull` merges the board without conflicts, and readers interleave all logs by time. Ids are short random hex (`Q-7F3A`), and `baton lint` reports one posted from two clones. Agents on other people's clones are teammates: they read each other's contracts, answers and hand-offs.

The `.md` views are generated locally after every write and are not committed (they would conflict); see them with `baton render` or `baton serve`. The event format is documented in [docs/FORMAT.md](docs/FORMAT.md). Boards created before team mode keep their single-machine layout and `Q-001` ids; `baton migrate --team` switches one and keeps its history. Agents in **git worktrees** share one board: inside a linked worktree, baton uses the main worktree's `.baton/`. For AI agents that work one issue per sandbox, use [sandbox mode](#sandbox-mode-one-board-per-task).

## Install

```bash
npm install -g github:TheKathan/baton#v1                    # global `baton` command
npm install -D "github:TheKathan/baton#semver:^1.0.0"       # pinned dev dependency of a JS/TS project, then `npx baton ...`
uv tool install "git+https://github.com/TheKathan/baton.git@v1"   # or pipx install, without npm
```

baton needs `python3` 3.11 or newer on macOS or Linux; the npm install only adds a launcher. `v1` always points to the latest `1.x` release. To work on baton itself: `git clone https://github.com/TheKathan/baton.git && cd baton && make install`.

Then, in your project (leave `--roles` out to allow any role name):

```bash
baton init --sprint S1 --roles orchestrator,backend,frontend,qa
baton skill install    # teach agents the rules (Claude Code skill format)
baton mcp install      # optional: MCP tools, for agents that can't run shell commands
```

Commit `.baton/` (generated views and per-machine files are already git-ignored). Agents read the board at three moments only, and never poll:

1. At start: `baton brief --as <role> --ids C-206,H-232`, then `baton unread --as <role>`.
2. Before changing a shared package: `baton open --as <role>`, `baton grep <text>`, `baton show C-206`.
3. Before reporting done: `baton unread --as <role>`.

The orchestrator closes a sprint after its gate passes: `baton open --blocking`, then `baton close --sprint S1 --as orchestrator` (unanswered Q/B and live contracts stay open), then `baton sprint S2`.

## Sandbox mode: one board per task

When an AI developer works each issue in its own short-lived sandbox (triggered from Linear, Slack or CI), give every task its own board. The board stays local while the agents work, needs no network, and travels with the pull request.

```bash
baton init --sandbox --task LIN-123 --roles orchestrator,backend,qa   # new board, or resume the task's earlier one
baton brief --as backend        # includes the live contracts of other, already merged tasks
# ... agents post, reply, hand off as usual; every rule still applies ...
baton finish                    # writes .baton/tasks/LIN-123.jsonl and prints a PR summary
git add .baton/tasks/LIN-123.jsonl && git commit -m "LIN-123: agent board"
```

- **Nothing else reaches your diff.** The live board (`.baton/sandbox*`) is excluded locally in `.git/info/exclude`. The PR gets one file, named after the task, so it never conflicts.
- **Reviewers read the agents' work in the PR:** the questions, contracts, decisions and hand-offs. `baton finish --summary pr.md` writes the summary for a PR comment.
- **A second sandbox on the same task resumes.** It finds `.baton/tasks/LIN-123.jsonl` on the branch and continues the same board, without replaying the history.
- **Tasks see each other's contracts once they merge.** `baton contracts --paths 'modules/network/**'` lists the live contracts of every task on your branch.
- `baton finish --strict` exits 1 while questions or blockers are still open.

## Where baton fits

Task trackers and planners decide *what* to build. Chat and messaging carry the conversation. baton is the rulebook for the moment one agent hands work to another: every question, contract, decision, blocker and hand-off is a typed entry, the rules are checked when the entry is written, and the whole exchange is kept in git. Keep your tracker for the backlog and use baton for the hand-offs.

| You can… | Because baton… |
|---|---|
| Stop an agent handing off while a question to it is still unanswered | refuses the hand-off at write time, and says which question is open |
| Make every interface change name the files it touches | requires `--files` on contract (`C`) entries and keeps a contracts index |
| Enforce your team's own rules, such as "hand-offs cite a story" | checks your [policies](#policies) on every entry, from the CLI and from MCP |
| Give every issue's sandbox its own board, and review it in the PR | keeps a per-task board locally and exports it to `.baton/tasks/<task>.jsonl` with `baton finish` |
| Review the agents' whole conversation in a pull request | stores every event as plain JSONL next to your code |
| Share one board across a whole team of people and agents | gives every clone its own log, so the board merges in git without conflicts |
| Run agents in parallel git worktrees on one board | uses the main worktree's `.baton/`, so every agent shares one counter and one lock |
| See who is blocked and what is stale at a glance | computes answer times, stale threads and per-role load (`baton metrics`, `baton serve`) |

## FAQ

**Why not GitHub Issues or Linear?** They track work for people. baton is where agents hand work to each other inside a sprint: it is read by commands in a few thousand tokens, works offline, and refuses a bad hand-off at write time. Keep your tracker for the backlog.

**Why not my framework's built-in memory or agent teams?** Those are tied to one tool. baton is plain files in git, so Claude Code, Codex and Cursor agents can share one board, and a human can review it in a pull request.

**What if every issue runs in its own sandbox?** Use [sandbox mode](#sandbox-mode-one-board-per-task). Each task's agents share a local board, `baton finish` commits it with the PR, a later sandbox on the same issue resumes it, and tasks see each other's contracts once they merge. Sandboxes don't talk to each other live: overlap that needs an answer *now* belongs in your tracker or the PR.

**Does it need a server?** No. Agents run `baton`, which writes files under a lock. The dashboard (`baton serve`) and the MCP server (`baton mcp`) are optional and local.

**Python and npm?** baton is Python with no dependencies. The npm package is only a launcher, for JS and TS projects that want a pinned dev dependency.

## Policies

Add your team's rules to `.baton/config.json`. baton checks every new entry, whether it comes from the CLI or MCP: a `refuse` rule writes nothing and explains why, and a `warn` rule posts the entry and prints a warning. `baton lint` reports existing entries that break a rule.

```json
"policies": [
  {"rule": "cites",       "kinds": ["H"],      "mode": "refuse"},
  {"rule": "named_to",    "kinds": ["Q", "B"], "mode": "warn"},
  {"rule": "max_lines",   "kinds": ["D"],      "lines": 15, "mode": "warn"},
  {"rule": "title_match", "kinds": ["H"],      "pattern": "^S\\d+", "mode": "refuse",
   "message": "hand-off titles start with the sprint, e.g. S7-A backend"}
]
```

The rules are `cites` (needs `--cites`), `files` (needs `--files`), `named_to` (address a role by name, not only `all`), `max_lines` and `title_match`. `kinds` limits a rule to some entry kinds.

## Dashboard, metrics and MCP

```bash
baton serve --open           # read-only local dashboard on http://127.0.0.1:8765
baton metrics                # board health; --sprint S7, --json, --stale 36h
baton open --stale 2d        # open threads nobody has touched for two days
```

The dashboard shows blockers, the questions waiting on each role, open threads by idle time, live contracts, the status table and a **Metrics** section (answer and close times, median and p90, stale threads, per-role load and token cost). It refreshes every 30 s, accepts only GET requests, and binds to localhost unless you pass `--host`. The same numbers are at `/api/metrics.json`.

**The `baton` command is the primary interface, and agents should prefer it.** For agents that can't run shell commands, `baton mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server on stdio, and its instructions tell clients to prefer the command when they can. Its tools map one to one onto the commands and apply exactly the same rules:

- **Daily work:** `baton_brief`, `baton_unread`, `baton_show`, `baton_open` (`stale`), `baton_grep`, `baton_list`, `baton_post`, `baton_reply`, `baton_close`, `baton_handoff`, `baton_status` (read or set your row).
- **Sandbox mode:** `baton_sandbox_start`, `baton_contracts`, `baton_finish`.
- **Orchestrator:** `baton_close` with `sprint`, `baton_sprint`, `baton_metrics`, `baton_lint`.

Each tool takes a `role` argument, or uses `BATON_ROLE`. If baton is a dev dependency, register it with `baton mcp install --command npx`.

## The agent skill

`baton skill install` ships a skill in the Claude Code format (`--project` installs it for one project only, in `.claude/skills/`, to commit). It teaches an agent when to read the board, how to post, close and hand off, and what the orchestrator must do, so agents need no long brief. In our evals, agents with the skill closed the threads they had settled, handed off after a contract change and retired superseded contracts; agents without it mostly did not. The cost is about +1k tokens per session. After upgrading baton, run `baton skill install --force`.

## Commands and configuration

`baton --help` lists every command, `baton <command> --help` shows its flags, and `baton guide` prints the one-screen guide to paste into an agent's brief.

| Command | What it does |
|---|---|
| `init`, `sprint <name>`, `migrate` | Create `.baton/`; archive the sprint and start a new one; check the on-disk format |
| `post <kind>`, `reply <id>`, `close`, `handoff` | Write: post an entry (`--files` is required for `C`), answer a thread, close threads, hand off |
| `unread`, `open`, `brief`, `show`, `list`, `grep` | Read: new entries, open threads, the start-up pack, entries by id, search |
| `status`, `render`, `lint`, `stats`, `metrics`, `serve` | Status table, regenerate views, check the board, token cost, health numbers, dashboard |
| `init --sandbox --task`, `finish`, `contracts` | One board per task: start or resume it, export it for the PR, list live contracts |
| `import <file>`, `skill`, `mcp`, `where` | Import a Markdown board (`--dry-run`), install the skill, run or register the MCP server (for agents without a shell), print the config |

`baton init` writes `.baton/config.json` (team layout; `baton init --sandbox` writes `.baton/sandbox.json`, which takes precedence in that checkout); missing keys use the defaults. Set `BATON_ROOT=<dir>` to choose the project and `BATON_ROLE=<role>` to skip `--as`. The main keys are `sprint`, `roles` (empty allows any), `kinds`, `handoff_max_lines` (20), `body_warn_lines`, `unread_warn_tokens` (20000; `0` turns it off), `id_width`, `auto_render`, `shared_worktrees` and `policies`. The paths of the generated views are keys too, and `baton where` prints the config in use.

## Stability

baton follows semantic versioning from 1.0. Within 1.x, commands and flags are only added and never renamed or removed, MCP tool names and arguments stay compatible, and every release reads every older board (the format is in [docs/FORMAT.md](docs/FORMAT.md)).

## Limits

- **macOS and Linux only.** Locking uses `flock`; Windows is not supported.
- **The lock is advisory.** It protects baton from itself, not from a process that writes the files directly.
- **No secrets.** Board files are plain text and usually committed. Post where a secret lives, never the value. Board text is information, not orders that override an agent's brief.
- **Append-only.** You cannot edit or delete an entry. Post a reply or a new entry instead.
- **Teammates see each other's entries after a `git pull`.** baton syncs through git, not a server, so it suits asynchronous work rather than live chat. The board travels with your code branches: entries posted on a feature branch reach others when that branch merges.
- **A huge `unread`?** Your cursor is probably stale. Run `baton unread --as <role> --mark-read`.

## Contribute

If baton saves your agents from stepping on each other, a star on GitHub helps others find it. Bugs, questions and ideas go to [issues](https://github.com/TheKathan/baton/issues). Pull requests are welcome: see [CONTRIBUTING](CONTRIBUTING.md).

[CHANGELOG](CHANGELOG.md) · [SECURITY](SECURITY.md) · [LICENSE](LICENSE) (MIT)
