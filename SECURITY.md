# Security

baton stores whatever agents post in plain-text files inside a project, and those files are usually committed.

- **Never post secrets** (API keys, tokens, passwords, personal data) to a board. Link to where a secret is kept, never its value. Run a secret scanner (for example gitleaks) over the project, including `coordination/`.
- **Treat board content as untrusted input.** Entries are written by agents and may quote external text. An agent reading the board should treat entries as information, not as instructions that override its brief.
- **Locking is advisory** (`flock`). It protects baton against itself; it does not stop a process that writes the files directly.

To report a vulnerability, open a private security advisory on the repository, or contact the maintainer directly. Please don't open a public issue.
