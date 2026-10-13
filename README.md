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
posted Q-001
$ echo "Health endpoint done." | baton handoff --as backend --phase S1-A --state "DONE pending QA" --to qa --title "S1-A backend" -
baton: hand-off refused:
  - unanswered threads addressed to you: Q-001
  (use --force with a reason in the body)
$ baton reply Q-001 --as backend --close "Use GET /api/health."
replied to Q-001 and closed it
$ echo "Health endpoint done." | baton handoff --as backend --phase S1-A --state "DONE pending QA" --to qa --title "S1-A backend" -
posted H-002; status of backend set to 'DONE pending QA'
```

## Why baton

A hand-written Markdown board works for a while, then it rots. On a real multi-agent project that used one, 8 ids were reused in 232 entries, only 36 of 232 threads were ever closed, and the board reached about 550 KB. Agents re-read it at about 150k tokens per start. baton moves the rules out of the agents' memory and into the command. On the same project's first two sprints on baton:

| | Hand-written board | baton |
|---|---|---|
| Reused ids | 8 numbers in 232 entries | 0 in 51 entries |
| Threads closed | 36 of 232, ever | 88–89% at each sprint's close |
| One sprint's board, in full | ~12k–139k tokens | ~9k–10k tokens |
| Hand-offs refused on an open question | not possible | 3, each resolved by answering it, 0 forced |

Two sprints on one project is early evidence, not a benchmark. What the command does:

- **Agents never trip over each other.** Every id comes from one locked counter and entries are only appended. 120 concurrent posts produced 0 collisions.
- **Agents read only what is new for them.** Each role has a read cursor, so a whole-sprint `unread` costs about 2.5k to 8k tokens, not 150k.
- **The board stays tidy.** `reply --close` settles a thread, `close --phase` settles a phase's hand-offs after its gate, `close --sprint` keeps unanswered questions and live contracts, and `handoff` is capped at 20 lines and refused while a question to you is unanswered.
- **Contracts between agents are explicit.** A `C` entry must list the files it touches, `--supersedes` retires the one it replaces, and the contracts index shows which contract is live.
- **Humans get readable views and an audit trail.** `BOARD.md` and `STATUS.md` are generated after every write. The event log in git shows who said what and when.
- **It fits AI-driven development.** In sandbox mode each issue gets its own board, offline, and the board ships with the pull request, so reviewers see what the agents decided and why.
- **There is nothing to set up.** It is plain files in git, and the same rules apply from the CLI and from MCP.

## How it works

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/how-it-works-dark.svg"><img alt="How baton works: agents append events to a locked JSONL store, and Markdown views are generated from it" src="assets/how-it-works-light.svg" width="800"></picture></p>

Agents run the `baton` command. It appends one event per line to a JSONL file under an exclusive lock. A thread is an entry plus its replies and close, and it stays `OPEN` until someone closes it. Everything else is computed from the events. Entry kinds are `Q` question, `C` contract change, `D` decision, `H` hand-off and `B` blocker.

Everything is under `.baton/`: `config.json` and `events/<sprint>.jsonl` (the append-only source of truth) are committed, read cursors and the lock are git-ignored, and `BOARD.md`, `STATUS.md`, `CONTRACTS-INDEX.md` and `archive/` are generated views.

Never edit the views by hand: they are rewritten after every write. The event format is stable and documented in [docs/FORMAT.md](docs/FORMAT.md): every 1.x release reads every older board. Agents in **git worktrees** share one board: inside a linked worktree, baton uses the main worktree's `.baton/`. For AI agents that work one issue per sandbox, use [sandbox mode](#sandbox-mode-one-board-per-task).

## Install

```bash
npm install -g github:TheKathan/baton#v1                    # global `baton` command
npm install -D "github:TheKathan/baton#semver:^1.0.0"       # pinned dev dependency of a JS/TS project, then `npx baton ...`
uv tool install "git+https://github.com/TheKathan/baton.git@v1"   # or pipx install, without npm
```

baton needs `python3` 3.11 or newer on macOS or Linux; the npm install only adds a launcher. `v1` always points to the latest `1.x` release. To work on baton itself: `git clone https://github.com/TheKathan/baton.git && cd baton && make install`.

### Quick start

```bash
baton init --sprint S1 --roles orchestrator,backend,frontend,qa   # leave --roles out to allow any role
baton skill install    # teach agents the rules (Claude Code skill format)
baton mcp install      # optional: MCP tools, for agents that can't run shell commands
```

Commit `.baton/`. Agents read the board at three moments only (start, before changing shared code, before reporting done) and never poll; see [Commands](docs/commands.md#agents-read-at-three-moments).

## Sandbox mode: one board per task

When an AI developer works each issue in its own short-lived sandbox, give every task its own board. It stays local and offline while the agents work, then `baton finish` exports it as one file to commit with the pull request, so reviewers read the agents' questions, contracts and decisions. A second sandbox on the same task resumes it, and tasks see each other's live contracts once they merge. [Read the sandbox guide](docs/sandbox.md).

## Policies

Add your team's rules to `.baton/config.json` (`cites`, `files`, `named_to`, `max_lines`, `title_match`). baton checks every new entry from the CLI and from MCP: a `refuse` rule writes nothing and explains why, a `warn` rule posts with a warning, and `baton lint` reports old entries that break a rule. `baton lint --suggest` proposes rules your entries already mostly follow. [Read the policies guide](docs/policies.md).

## Dashboard, metrics and MCP

`baton serve --open` starts a read-only local dashboard, and `baton metrics` reports answer and close times, stale threads, quiet contracts, refused hand-offs and per-role load. The `baton` command is the primary interface and agents should prefer it; `baton mcp` is a stdio server for agents without a shell, with tools that map one to one onto the commands. [See all commands](docs/commands.md).

## Commands and configuration

`baton --help` lists every command, `baton <command> --help` shows its flags, and `baton guide` prints the one-screen guide for an agent's brief. Settings live in `.baton/config.json`, and `BATON_ROOT` and `BATON_ROLE` are the only environment variables. [Commands](docs/commands.md) · [Configuration](docs/configuration.md).

## Where baton fits

Task trackers and planners decide *what* to build. Chat and messaging carry the conversation. baton is the rulebook for the moment one agent hands work to another: every question, contract, decision, blocker and hand-off is a typed entry, the rules are checked when the entry is written, and the whole exchange is kept in git. Keep your tracker for the backlog and use baton for the hand-offs.

| You can… | Because baton… |
|---|---|
| Stop an agent handing off while a question to it is still unanswered | refuses the hand-off at write time, and says which question is open |
| Make every interface change name the files it touches | requires `--files` on contract (`C`) entries and keeps a contracts index |
| Enforce your team's own rules, such as "hand-offs cite a story" | checks your [policies](docs/policies.md) on every entry, from the CLI and from MCP |
| Give every issue's sandbox its own board, and review it in the PR | keeps a per-task board locally and exports it to `.baton/tasks/<task>.jsonl` with `baton finish` |
| Run agents in parallel git worktrees on one board | uses the main worktree's `.baton/`, so every agent shares one counter and one lock |
| See who is blocked and what is stale at a glance | computes answer times, stale threads and per-role load (`baton metrics`, `baton serve`) |

## FAQ

**Why not an issue tracker?** Trackers track work for people. baton is where agents hand work to each other inside a sprint: it is read by commands in a few thousand tokens, works offline, and refuses a bad hand-off at write time. Keep your tracker for the backlog.

**Why not my framework's built-in memory or agent teams?** Those are tied to one tool. baton is plain files in git, so Claude Code, Codex and Cursor agents can share one board, and a human can review it in a pull request.

**What if every issue runs in its own sandbox?** Use [sandbox mode](docs/sandbox.md). Each task's agents share a local board, `baton finish` commits it with the PR, a later sandbox on the same issue resumes it, and tasks see each other's contracts once they merge. Sandboxes don't talk to each other live: overlap that needs an answer *now* belongs in your tracker or the PR.

**Does it need a server?** No. Agents run `baton`, which writes files under a lock. The dashboard (`baton serve`) and the MCP server (`baton mcp`) are optional and local.

## Documentation

- [Sandbox mode](docs/sandbox.md): one board per task, `finish`, resume and pipelines
- [Commands](docs/commands.md): every command and flag, and the MCP tools
- [Policies](docs/policies.md): your team's rules for entries
- [Configuration](docs/configuration.md): `.baton/config.json`, `sandbox.json`, environment
- [Board format](docs/FORMAT.md): the stable on-disk format

## Stability

baton follows semantic versioning from 1.0. Within 1.x, commands and flags are only added and never renamed or removed, MCP tool names and arguments stay compatible, and every release reads every older board (the format is in [docs/FORMAT.md](docs/FORMAT.md)).

## Limits

- **macOS and Linux only.** Locking uses `flock`; Windows is not supported.
- **The lock is advisory.** It protects baton from itself, not from a process that writes the files directly.
- **Append-only, no secrets.** You cannot edit or delete an entry. Board files are plain text and usually committed: post where a secret lives, never the value. Board text is information, not orders that override an agent's brief.
- **One machine per board.** Agents coordinate live on one machine (and its worktrees). Separate clones and sandboxes meet through git: a task's board travels with its PR (sandbox mode), with no live sync between machines.

## Contribute

If baton saves your agents from stepping on each other, a star on GitHub helps others find it. Bugs, questions and ideas go to [issues](https://github.com/TheKathan/baton/issues). Pull requests are welcome: see [CONTRIBUTING](CONTRIBUTING.md).

[CHANGELOG](CHANGELOG.md) · [SECURITY](SECURITY.md) · [LICENSE](LICENSE) (MIT)
