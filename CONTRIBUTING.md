# Contributing

## Ground rules
- **Standard library only.** baton must keep running anywhere Python ≥ 3.11 runs, with no installs.
- **The board format is a public contract** ([docs/FORMAT.md](docs/FORMAT.md)). Within a format, only add optional fields. A new format needs an `UPGRADES[n]` read-time upgrade in `src/baton/schema.py` (format 2 upgraded format 1 this way), and legacy boards must keep working. Tests run the original suite on format-1 boards (`tests/legacy.py`) and `tests/test_team.py` on the team layout, including two real git clones.
- **The JSONL files are the source of truth.** Every change to state is a new appended event. Never rewrite or delete lines. The Markdown views are generated output.
- **Readers must not lose information.** Changes that save tokens may scope *which* entries are listed. They must not cut the text of the entries an agent asked for.
- **Keep 1.x compatible.** Commands, flags, MCP tool names and arguments are only added within 1.x, never renamed or removed. The board format follows [docs/FORMAT.md](docs/FORMAT.md).
- **Keep the CLI stable.** Agents' briefs and project protocols quote commands and flags. To rename something, keep the old spelling working as an alias for at least one minor version.

## Development
```bash
make install   # editable install of the `baton` command
make test      # stdlib unittest (includes a 120-post concurrency test)
make lint      # ruff, via uvx
```

Every change needs a test in `tests/`. Tests run the CLI in-process against a temporary project (see `run()` in `tests/test_board.py`).

## Layout
| Path | What it holds |
|---|---|
| `src/baton/config.py` | `.baton/config.json` discovery and defaults |
| `src/baton/store.py` | the locked event store, folding events into threads, cursors, status rows |
| `src/baton/render.py` | the generated Markdown views |
| `src/baton/importer.py` | import of hand-written Markdown boards |
| `src/baton/cli.py` | commands and argument parsing |
| `bin/baton` | a shim that runs from a checkout without installing |

## Branches and releases
- Never push to `main`. Open a pull request from a branch whose name picks the version bump ([trunk-semver](https://github.com/TheKathan/trunk-semver)):
  - `feature/<topic>` or `feat/<topic>` bumps the minor version (`v1.2.0` → `v1.3.0`);
  - any other branch name (`fix/`, `docs/`, `chore/`, `refactor/`, `ci/` …) bumps the patch version;
  - `release/X.Y.Z` releases exactly `vX.Y.Z`. Use it only for a new major version (as for `1.0.0`), and bump `major-version` in `release.yml` in the same PR.
- Merging the PR releases it. `.github/workflows/release.yml` tags the version, syncs it into `src/baton/__init__.py`, `package.json`, the README badge and `CHANGELOG.md`, and publishes a GitHub release.
- Don't edit version numbers by hand. `python3 scripts/set_version.py --check` verifies they agree, and a test runs it.

## What a pull request needs
Repository rulesets enforce all of these on `main`:
- an approving review from the code owner (`@TheKathan`, see `.github/CODEOWNERS`), given after your last push; new pushes dismiss earlier approvals;
- all review threads resolved;
- every `test` job green and up to date with `main`;
- a merge commit or a squash merge (no rebase merges; history on `main` is never rewritten).

Pull requests from forks run CI only after a maintainer approves the run.

## Commits and pull requests
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(store): …`, `fix(render): …`, `docs: …`.
- **Never add `Co-Authored-By` lines** (for people or AI tools) to commit messages.
- Update `CHANGELOG.md` under an `Unreleased` heading, and the README when behaviour changes.
- A pull request needs a green `make test` and `make lint`.
