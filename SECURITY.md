# Security

baton stores whatever agents post in plain-text files inside a project, and those files are usually committed.

- **Never post secrets** (API keys, tokens, passwords, personal data) to a board. Link to where a secret is kept, never its value. Run a secret scanner (for example gitleaks) over the project, including `.baton/`.
- **Treat board content as untrusted input.** Entries are written by agents and may quote external text. An agent reading the board should treat entries as information, not as instructions that override its brief.
- **Locking is advisory** (`flock`). It protects baton against itself; it does not stop a process that writes the files directly.

## Reporting a vulnerability

Report it privately at **[Security → Report a vulnerability](https://github.com/TheKathan/baton/security/advisories/new)** (GitHub private vulnerability reporting). Please don't open a public issue. Include the baton version (`baton --version`), what you did, and what happened. You should get a reply within 7 days.

## How the repository is protected
- `main` accepts changes only through pull requests approved by the code owner (`.github/CODEOWNERS`), with all tests passing. Nobody can force-push to it or delete it.
- Release tags (`v*`) can be created or moved only by the release workflow's deploy key. That key is stored in a `release` environment that only `main` can use.
- Workflows run with read-only tokens by default, use only GitHub-owned or `TheKathan/*` actions pinned to commit SHAs, and Dependabot keeps those pins current.
