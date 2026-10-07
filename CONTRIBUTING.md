# Contributing

## Ground rules
- **Standard library only.** baton must keep running anywhere Python ≥ 3.11 runs, with no installs.
- **The JSONL files are the source of truth.** Every change to state is a new appended event. Never rewrite or delete lines. The Markdown views are generated output.
- **Readers must not lose information.** Changes that save tokens may scope *which* entries are listed. They must not cut the text of the entries an agent asked for.
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
  - `feature/<topic>` or `feat/<topic>` bumps the minor version (`v0.2.0` → `v0.3.0`);
  - any other branch name (`fix/`, `docs/`, `chore/`, `refactor/`, `ci/` …) bumps the patch version.
- Merging the PR releases it. `.github/workflows/release.yml` tags the version, syncs it into `src/baton/__init__.py`, `package.json`, the README badge and `CHANGELOG.md`, and publishes a GitHub release.
- The release also publishes `agent-baton` to npm, with provenance, through npm trusted publishing. No npm token is stored: npmjs.com trusts `TheKathan/baton`, `release.yml` and the `release` environment. Publishing runs only while the `NPM_PUBLISH` repository variable is `true`, and skips a version that is already on npm.
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
