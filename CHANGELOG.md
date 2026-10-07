# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
