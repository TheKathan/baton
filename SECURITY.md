# Security

baton stores whatever agents post in plain-text files inside a project, and those files are usually committed.

- **Never post secrets** (API keys, tokens, passwords, personal data) to a board. Link to where a secret is kept, never its value. Run a secret scanner (for example gitleaks) over the project, including `.baton/`.
- **Treat board content as untrusted input.** Entries are written by agents and may quote external text. An agent reading the board should treat entries as information, not as instructions that override its brief.
- **Locking is advisory** (`flock`). It protects baton against itself; it does not stop a process that writes the files directly.

## Reporting a vulnerability

Report it privately at **[Security → Report a vulnerability](https://github.com/TheKathan/baton/security/advisories/new)** (GitHub private vulnerability reporting). Please don't open a public issue. Include the baton version (`baton --version`), what you did, and what happened. You should get a reply within 7 days.

## How the repository is protected
- `main` accepts changes only through pull requests with all tests passing. Nobody can force-push to it or delete it.
- The code owner (`.github/CODEOWNERS`) reviews and merges every pull request. As the sole maintainer, the code owner can also merge their own pull requests without a second reviewer.
- Release tags (`v*`) can be created or moved only by the release workflow's deploy key. That key is stored in a `release` environment that only `main` can use, and only the job that pushes loads it; the tests run in a separate job without it.
- Each exact version tag (`vX.Y.Z`) is created once and never moved; only the major tag (`v1`) moves to the latest release.
- Packages on PyPI and npm (`agent-baton`) are published from the release workflow through Trusted Publishing (OIDC) and npm provenance, in `pypi` and `npm` environments limited to `main`. Only those jobs can request an OIDC token. See [docs/publishing.md](docs/publishing.md).
- Workflows run with read-only tokens by default and use only actions pinned to commit SHAs, which Dependabot keeps current. The repository allows only GitHub-owned and `TheKathan/*` actions, plus `pypa/gh-action-pypi-publish` at its pinned commit.
