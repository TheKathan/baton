# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Published on npm as [`agent-baton`](https://www.npmjs.com/package/agent-baton)**: `npm install -g agent-baton`, `npx agent-baton`, or `npm install -D agent-baton`. Releases publish automatically with npm provenance through trusted publishing (no stored npm token), once the `NPM_PUBLISH` repository variable is `true`.

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
