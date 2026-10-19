# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.5.2] - 2026-10-19

### Changed
- Install from PyPI: `uv tool install baton-handoff` (or `pipx install baton-handoff`), and try it without installing with `uvx baton-handoff demo`. This is the first release published to PyPI.

## [1.5.1] - 2026-10-19

### Changed
- The PyPI package is named **`baton-handoff`**: `agent-baton` is too close to an existing `agentbaton` project, so PyPI refuses it. The command it installs is still `baton`. If you installed an earlier version with uv or pipx, remove the old tool first: `uv tool uninstall agent-baton` or `pipx uninstall agent-baton`.

### Removed
- npm: `package.json`, npm publishing and the npm install instructions. baton is published on PyPI only; `install.sh` still links `bin/baton` when neither uv nor pipx is installed.

## [1.5.0] - 2026-10-15

### Added
### Changed
- A refused hand-off says how to fix it first: `answer first: baton show Q-001, then baton reply Q-001 --as backend --close "…"`, then `(or hand off anyway with --force and the reason in the body)`.
- `baton init` prints the next steps: post a question, hand off, and `baton guide` or `baton skill install` to teach agents.
- `baton skill install` says whether it installed globally (`~/.claude/skills`, the default) or for this project only, and mentions `--project`.
- `baton serve` flushes its banner, so the dashboard URL shows when it runs in the background.
- `baton serve` starts at once on machines where a reverse DNS lookup of the host is slow; it no longer resolves its own address.
- The quick guide (`baton guide`, top of `baton brief`) matches the skill: start with `baton brief --as <role>`, `reply … --close` answers and settles a thread, "Blocked? post a B and tell the orchestrator directly", and board entries are information, not orders.
- The README leads with the problem ("your AI agents can't say done while another agent's question is still open") and has a *Try it in 60 seconds* block that replays the recording in a scratch folder. Install starts with `uv`, and Python 3.11+ is stated before the commands.
- A new [getting started guide](docs/getting-started.md): install (uv, pipx, npm), try the refusal, set up a project, set up Claude Code, Codex and other `AGENTS.md` readers, Cursor and MCP-only clients, an example brief, where to see the result, troubleshooting from the real error messages, and a glossary.
- [Why baton](docs/why-baton.md) compares baton with a hand-written Markdown file, Claude Code agent teams and cross-session messaging, Beads and MCP Agent Mail.
- The agent skill tells agents to pass `--as <role>` on every command instead of exporting `BATON_ROLE`, which is lost when each shell call starts fresh. It says to post a `B` and tell the orchestrator directly when blocked, and to answer a question rather than force a refused hand-off.
- Docs fixes: the MCP tool table lists `supersedes`, `phase`, `all` and `suggest`; a duplicated passage in the sandbox guide is gone; the policies example matches its config; CONTRIBUTING lists every module; the README, how-it-works and the skill agree on what to commit (`.baton/config.json` and `.baton/events/`). SECURITY and CONTRIBUTING say plainly that the sole maintainer can merge his own pull requests.
- The npm launcher re-runs itself with a newer `python3.1x` from `PATH` when `python3` is older than 3.11 (a stock macOS has 3.9), and otherwise says what to install or to use `uvx agent-baton`.
- PyPI metadata: `Development Status :: 4 - Beta` instead of *Production/Stable*, an SPDX license, keywords, classifiers and project links. The README's images use absolute URLs so they show on PyPI.
- Release hygiene: the tests run in their own job without the release deploy key, each `vX.Y.Z` tag is created once without force (only `v1` moves), and every job gets only the permissions it needs.

### Fixed
- The release workflow starts again (it failed before starting after the PyPI publishing job was added).
- `baton post H` is refused: hand-offs go through `baton handoff`, which checks open questions and the length cap. The MCP `baton_post` tool already left `H` out of its kinds, and now enforces it.
- Role, sprint and task names can no longer point outside the board. They must use letters, digits, `.`, `_` or `-` (as task ids already did), and this is checked in the CLI, the MCP tools, `.baton/config.json`, `init --roles`/`--sprint`, `status`, `sprint` and `import --sprint`. Every file baton writes is also checked to resolve inside the board or project. Before, `baton unread --as ../../../package` overwrote the project's `package.json`, and `baton sprint ../../../outside1` sent later events outside the repository.
- Duplicate ids and event numbers, e.g. from two clones that each posted `Q-001` and were then merged, are no longer lost silently. `baton lint` checks the raw lines and reports each duplicate as an error with both titles; other commands warn once on stderr. History is never rewritten.
- One unreadable line (a crash mid-append, a git conflict marker) no longer breaks every command. It is skipped with one warning naming `file:line`, and `baton lint` reports it as an error. The read cursors and the config are now written atomically, like `status.json`, and a damaged cursor, status or config file is a clear error instead of a traceback.
- The MCP server validates every call against the tool's `inputSchema` (required fields, types, enums, arrays of strings; a lone string where an array is expected is wrapped). Bad input gets a JSON-RPC `-32602` error naming the problem, an unexpected failure gets `-32603`, and neither stops the server. Values that start with `-` are never read as flags. Before, `"to": "frontend"` was stored as eight roles, a missing argument was reported as "unknown tool", and a wrong type crashed the server.

## [1.4.4] - 2026-10-15

### Changed
- The README opens with a 17-second recording of a real, unscripted agent (Claude Code) on a baton board: its hand-off is refused while frontend's question is open, it answers and closes the question, and the hand-off goes through without `--force`. It's trimmed, with a caption bar for each step and the account's plan name masked in Claude Code's header; the agent's output is unchanged. `scripts/agent-demo/` records and edits it again. The [commands guide](docs/commands.md) opens with a terminal recording of the same commands, built from `assets/demo.tape` with [VHS](https://github.com/charmbracelet/vhs).
- The README's *How it works* diagram is a new animation: the agents' exchange as a conversation where every message is a typed entry in the append-only log. backend's hand-off is struck out and kept out of the log while frontend's question is unanswered, next to baton's real refusal and the rule; backend answers and the hand-off goes through. `scripts/animate_how_it_works.py` builds the light and dark versions, and readers who prefer reduced motion see the final frame.

### Added
- A code of conduct (Contributor Covenant 2.0), issue templates for bugs and feature requests, and a pull request template.

### Removed
- `scripts/enable-public-security.sh`, a one-time setup script that is no longer needed.

## [1.4.3] - 2026-10-14

## [1.4.2] - 2026-10-14

### Changed
- The README and the [sandbox guide](docs/sandbox.md#with-github-actions) link to the actions' GitHub Marketplace pages: [Setup baton CLI](https://github.com/marketplace/actions/setup-baton-cli), [baton task board](https://github.com/marketplace/actions/baton-task-board) and [baton PR check](https://github.com/marketplace/actions/baton-pr-check).

## [1.4.1] - 2026-10-14

### Changed
- The sandbox guide's *Use it in a pipeline* section is now [*Use it in a workflow*](docs/sandbox.md#use-it-in-a-workflow). It starts with the GitHub Actions ([setup-baton](https://github.com/TheKathan/setup-baton), [baton-task](https://github.com/TheKathan/baton-task) and [baton-check](https://github.com/TheKathan/baton-check)), followed by the plain script and `baton report` for any other CI. The README links to the actions.

## [1.4.0] - 2026-10-14

### Added
- **`baton report`** reports on exported task boards without needing a board: the same Markdown summary as `finish`, for one or more `.baton/tasks/*.jsonl` files, or for every task file changed since a git ref with `--since origin/main`. `--strict` exits 1 while a task has open questions or blockers, so a pull-request check can keep the PR from merging. `--summary FILE` and `--json` are supported.

## [1.3.1] - 2026-10-14

### Changed
- **The README is a short pitch**: why to use baton, what it's for, how it works in one paragraph, and a three-line install. The evidence, comparison and FAQ moved to [docs/why-baton.md](docs/why-baton.md), and the file layout, install options, stability promise and limits to [docs/how-it-works.md](docs/how-it-works.md).

## [1.3.0] - 2026-10-13

### Added
- **Refusals are measured.** Every refused write (a hand-off on an open question or over the cap, a contract without files, a policy) and every `--force` override is recorded in `<dir>/.local/refusals.jsonl`. The log is local and git-ignored (baton adds `.local/` to the board's `.gitignore`), so the board still holds only what was written. `baton metrics` and the dashboard report refused writes, forced ones, and how many refused hand-offs were resolved by answering the question. A sandbox's `finish` summary says how many writes were refused.
- **Closing is part of the flow.** Hand-offs record their `--phase`, and `baton close --phase S8-A` closes a phase's hand-offs once it passes its gate. `baton brief` lists the hand-offs to you that are still open, and `baton handoff` notes them, so whoever checks the work closes it (with `--closes`).
- **`baton post C --supersedes C-240`** cites and closes the contract it replaces in one command, so only one shape stays live.
- **`baton lint --suggest`** proposes policies that most of the board's own entries already follow (cites, files, named roles, title patterns), as a config snippet to accept or ignore.
- MCP: `baton_post` takes `supersedes`, `baton_close` takes `phase`, `baton_lint` takes `all` and `suggest`.

### Changed
- **Open contracts are no longer counted as stale.** A contract stays open while it holds. `baton metrics` lists them separately as *quiet contracts*: open `C` entries that nobody has replied to or cited for the stale period.
- **`baton lint` skips imported entries** by default, since their problems were reported at import time. `--all` checks them too.
- **Sandbox boards inherit the team's settings.** `baton init --sandbox` copies `policies`, `kinds`, `roles` (unless `--roles` is given) and the limits from the project's `.baton/config.json`, so project rules apply in every sandbox.
- The README's *Why* section adds the first measurements from a project that moved from a hand-written board to baton.
- **The README is shorter; the details moved to guides:** [sandbox mode](docs/sandbox.md), [commands](docs/commands.md), [policies](docs/policies.md) and [configuration](docs/configuration.md). A test checks that every `baton <command> --flag` in the docs exists and that relative links resolve.

## [1.2.0] - 2026-10-08

### Added
- **Sandbox mode: one board per task**, for AI developers that work each issue in its own short-lived sandbox.
  - `baton init --sandbox --task LIN-123` creates the task's board locally (`.baton/sandbox*`, excluded through `.git/info/exclude`), or resumes it from `.baton/tasks/LIN-123.jsonl` without replaying the history.
  - `baton finish` exports the board to `.baton/tasks/<task>.jsonl` to commit with the PR (one file per task, so it never conflicts, and reviewers see the agents' questions, contracts, decisions and hand-offs). It prints a Markdown PR summary, `--summary FILE` writes it, and `--strict` exits 1 while questions or blockers are open.
  - `baton contracts [--paths GLOB]` and `baton brief` list the live contracts of other tasks merged into your branch.
  - No network, no sync, sequential ids: every existing rule applies unchanged.
- **MCP covers every agent workflow**, for agents without a shell:
  - sandbox tools: `baton_sandbox_start`, `baton_contracts`, `baton_finish`;
  - orchestrator tools: `baton_list`, `baton_sprint`, `baton_metrics`, `baton_lint`;
  - `baton_close` takes a `sprint`, `baton_open` takes `stale`, and `baton_status` can set your row.

### Changed
- **The `baton` command is the primary interface.** The skill, the README and the MCP server's own instructions tell agents to prefer the command when they can run shell commands, and to use the MCP tools only when they can't.

### Fixed
- A reply or close that sorts before its entry is no longer dropped: threads are folded in two passes.

## [1.1.0] - 2026-10-07

### Added
- **Policies:** team rules in `.baton/config.json` under `"policies"`, checked on every new entry from the CLI and MCP. The rules are `cites`, `files`, `named_to`, `max_lines` and `title_match`, each limited to some `kinds` if you want, with mode `warn` or `refuse` and an optional `message`. A refused entry writes nothing. `baton lint` reports existing entries that break a rule, and a bad policy config is reported clearly.
- **Exact UTC time on every event** (`at`, ISO 8601), next to the local `ts`. Metrics use it, so answer and close times are exact and correct across timezones. Optional in format 1, so older boards are unaffected.
- **The importer keeps answers and closes:** `> [A] role · date: …` lines become reply events (with their date), and `status: CLOSED` markers or headers become close events. Imported boards now have real answered and closed state, and real metrics.
- The MCP `baton_post` tool offers the entry kinds configured for the project.

## [1.0.1] - 2026-10-07

### Changed
- **License changed from GPL-3.0-or-later to MIT**, the same as the other tools in this space, so baton is easy to adopt in any project.

## [1.0.0] - 2026-10-07

**baton 1.0: the first stable release.** It brings together the 0.4–0.8 work: one board across git worktrees, a documented and versioned board format, the MCP server, `baton metrics` and the `baton serve` dashboard.

### Stability
- Semantic versioning from here on. Within 1.x, commands, flags, MCP tool names and arguments are only added, never renamed or removed. Every 1.x release reads every older board ([docs/FORMAT.md](docs/FORMAT.md)).

### Changed
- Releases count from `v1`: install with `#v1` or `@v1`, or pin `#semver:^1.0.0`. `v0` stays on the last 0.x release.
- The release workflow can release an exact version from a `release/X.Y.Z` branch, which a bump can't reach for a new major.

## [0.8.0] - 2026-10-07

### Added
- **The dashboard shows the full metrics**: a Metrics section with time to first answer and time to close (median, p90, n), opened vs closed by kind, questions answered, stale threads with their ids, and the total unread backlog. The sprint and role tables add token cost (~tokens per sprint; unread events and ~tokens per role). `baton metrics` and `/api/metrics.json` carry the same token numbers.

## [0.7.0] - 2026-10-07

### Added
- **`baton metrics`**: board health from the event log. It reports the time to first answer and the time to close (median and p90), opened vs closed and close rate, unanswered Q/B, stale threads, and per-role load (posted, replies, answered, median answer time, waiting on them, open owned). Use `--sprint`, `--stale` and `--json`.
- **`baton serve`**: a read-only local dashboard, standard library only, bound to localhost by default. It shows blockers, questions waiting by role, open threads by idle time, collapsible live contracts, status, and sprint and role metrics, with `/e/<id>`, `/api/board.json` and `/api/metrics.json`. All board text is HTML-escaped, a strict Content-Security-Policy applies, and anything but GET is refused.
- **`baton open --stale AGE`** (`2d`, `36h`, `90m`): only threads idle at least that long.

## [0.6.0] - 2026-10-07

### Added
- **MCP server: `baton mcp`.** A Model Context Protocol server on stdio, using only the standard library, with typed tools: `baton_brief`, `baton_unread`, `baton_show`, `baton_open`, `baton_post`, `baton_reply`, `baton_close`, `baton_handoff`, `baton_status`, `baton_grep`. Tools run the same commands in-process, so every rule still applies. The role comes from the `role` argument or `BATON_ROLE`. `baton mcp install` registers it in the project's `.mcp.json` and keeps other servers.

## [0.5.0] - 2026-10-07

### Added
- **Board format v1, documented and versioned** ([docs/FORMAT.md](docs/FORMAT.md)). Every new event carries `"v": 1`, and the config records `"format": 1`. Events from baton 0.x (without `v`) are read as format 1 and never rewritten. Boards with events or a config from a newer format are refused with an upgrade message, never half-read. `baton migrate --check` reports the formats on disk, and `baton migrate` records the current format in the config.

## [0.4.0] - 2026-10-07

### Added
- **One board across git worktrees.** Inside a linked worktree, baton uses the main worktree's `.baton/`, so agents in separate worktrees share one id counter and one lock instead of each writing a diverging copy. `baton where` shows `shared_from_worktree`. Opt out with `"shared_worktrees": false`; `BATON_ROOT` still wins.

## [0.3.1] - 2026-10-07

### Changed
- npm registry publishing is postponed. Install from GitHub (`npm install -g github:TheKathan/baton#v0`, or `uv tool install "git+https://…@v0"`). `package.json` is private again, and the publish step is removed from the release workflow until it can be enabled.

## [0.3.0] - 2026-10-07

### Added
- npm publishing prepared for `agent-baton` (trusted publishing, off behind `NPM_PUBLISH`). It was never enabled, and 0.3.1 removes it again; see Unreleased.

### Changed
- README reorganised: why baton (its benefits), how it works, then install.

## [0.2.4] - 2026-10-07

## [0.2.3] - 2026-10-07

### Changed
- The repository is public: the README installs over HTTPS (`git+https://…`, `github:TheKathan/baton#…`), and no GitHub key is needed.

## [0.2.2] - 2026-10-07

### Security
- `CODEOWNERS`, and repository rulesets on `main` (code-owner approval, passing tests, no force-push or deletion) and on `v*` tags (release deploy key only).
- The release workflow pushes through a deploy key held in a `release` environment that only `main` can use.
- Workflow actions are pinned to commit SHAs and kept current by Dependabot. Only GitHub-owned and `TheKathan/*` actions are allowed.
- SECURITY.md: private vulnerability reporting, and how the repository is protected.

## [0.2.1] - 2026-10-07

### Changed
- **License changed from MIT to GPL-3.0-or-later.**

## [0.2.0] - 2026-10-07

### Changed
- Everything now lives in one `.baton/` folder: `.baton/config.json` (was `.baton.json`), `.baton/events/<sprint>.jsonl`, and the generated `.baton/BOARD.md`, `.baton/STATUS.md`, `.baton/archive/` and `.baton/CONTRACTS-INDEX.md` (previously under `coordination/`).
- `open --as <role>` lists only threads that name the role; `--all` adds broadcasts.

### Added
- `brief` and `stats` commands; length warnings for C/D entries; a note when one `unread` is unusually large.
- The **agent skill** (`src/baton/skill/SKILL.md`, Claude Code format) and `baton skill install|show|path` (`--project`, `--dir`, `--force`). Evaluated with skill-creator: 3 tasks × with/without skill (see `evals/`).
- npm install straight from git: `package.json` with a `baton` bin (`npm i -g` / `npm i -D "git+ssh://…#semver:^0.2.0"`, `npx baton`). The launcher checks for Python ≥ 3.11.
- Release workflow on TheKathan/trunk-semver: merging a PR tags `vX.Y.Z` (feature/* → minor, else patch) plus a moving `v0`, syncs the version into the files, and publishes a GitHub release from this changelog. `scripts/set_version.py` keeps the versions consistent.

### Fixed
- Message text after options is accepted on Python 3.11 (argparse could not handle a `*` positional placed after options).
- `handoff --closes` resolves every id before writing, so a bad id no longer leaves a posted hand-off behind (agents then retried and duplicated it). Already-closed threads are noted, not an error.
- `close --sprint` keeps unanswered questions/blockers and live contracts open (`--include-unanswered`, `--include-contracts` to override).
- `sprint` refuses names without a digit (e.g. `baton sprint new`) unless `--force`.
- `handoff` and `brief` point out threads you started that someone has replied to (probably settled: close them).
- `brief --ids` skips ids that aren't board entries (e.g. story ids) instead of failing.
- The package is named `agent-baton` (PyPI/npm name); the command stays `baton`.

## [0.1.0] - 2026-10-07

### Added
- Append-only JSONL event store, one file per sprint, with an exclusive `flock` on every write. Ids come from a single counter and are never reused.
- Typed entries: `Q` question, `C` contract change (`--files` required), `D` decision, `H` hand-off, `B` blocker.
- Commands: `init`, `post`, `reply`, `close` (also `--sprint` to bulk-close), `show`, `list`, `grep`, `unread` (per-role cursors, `--peek`, `--mark-read`), `open` (named threads; `--all`, `--blocking`), `handoff`, `status`, `brief`, `stats`, `sprint`, `render`, `import`, `lint`, `where`, `guide`.
- Hand-off rules: a line cap, and a hand-off is refused while a question or blocker addressed to the author is unanswered. `--closes` settles threads.
- Length warnings for contracts and decisions, and a note when a single `unread` is unusually large.
- Generated Markdown views: the live board (with threads carried over from earlier sprints), per-sprint archives, the status table and the contracts index. baton never overwrites a Markdown file it did not generate.
- Importer for hand-written Markdown boards (`### [X-NNN] from → to · status · date`).
- `install.sh` and `make install`: editable install through uv, then pipx, then a symlink shim.
