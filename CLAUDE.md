# CLAUDE.md

Instructions for coding agents that work on **baton** itself. Projects that only *use* baton should follow the README instead.

- Read `CONTRIBUTING.md` first. Its ground rules apply: standard library only, append-only events, no loss of information for readers, a stable CLI.
- Run `make test` and `make lint` before reporting done. Add a test for every behaviour change.
- Commit messages follow Conventional Commits and **never include `Co-Authored-By` lines**.
- baton is **standalone**. Docs, code comments and examples must not reference the projects it was first used in; use generic examples (roles like `backend`, `qa`, ids like `C-143`).
- Don't commit unless the owner asks.
