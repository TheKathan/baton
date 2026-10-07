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
| `src/baton/config.py` | `.baton.json` discovery and defaults |
| `src/baton/store.py` | the locked event store, folding events into threads, cursors, status rows |
| `src/baton/render.py` | the generated Markdown views |
| `src/baton/importer.py` | import of hand-written Markdown boards |
| `src/baton/cli.py` | commands and argument parsing |
| `bin/baton` | a shim that runs from a checkout without installing |

## Commits and pull requests
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(store): …`, `fix(render): …`, `docs: …`.
- **Never add `Co-Authored-By` lines** (for people or AI tools) to commit messages.
- Update `CHANGELOG.md` under an `Unreleased` heading, and the README when behaviour changes.
- A pull request needs a green `make test` and `make lint`.
