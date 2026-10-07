# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

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
