<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/TheKathan/baton/main/assets/banner-dark.svg"><img alt="baton: hand-offs for AI agents that build software together" src="https://raw.githubusercontent.com/TheKathan/baton/main/assets/banner-light.svg" width="720"></picture></p>

<p align="center">
  <a href="https://github.com/TheKathan/baton/actions/workflows/test.yml"><img alt="tests" src="https://github.com/TheKathan/baton/actions/workflows/test.yml/badge.svg"></a>
  <img alt="latest release" src="https://img.shields.io/github/v/release/TheKathan/baton">
  <img alt="license" src="https://img.shields.io/github/license/TheKathan/baton">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB">
  <img alt="dependencies: none" src="https://img.shields.io/badge/dependencies-none-brightgreen">
</p>

**Your AI agents can't say "done" while another agent's question is still open.**

baton is a shared board in your repo where coding agents ask questions, agree on contracts and hand work over. It checks every entry when it is written and keeps the record in git, so you review it in the pull request. One CLI, plain files, no server, any agent that runs a shell.

<p align="center"><img alt="A real coding agent, acting as backend, runs baton handoff and is refused because frontend's question Q-001 (which route serves the health check?) is unanswered; it reads the refusal, answers and closes Q-001, and the hand-off goes through as H-002 without --force. Trimmed and captioned; the agent's output is unchanged" src="https://raw.githubusercontent.com/TheKathan/baton/main/assets/agent-demo.gif" width="800"><br><sub>A real agent (Claude Code), unscripted, trimmed and captioned: refused while a question is open, it answers and hands off.</sub></p>

## Try it in 60 seconds

With baton [installed](#install), paste this into a terminal. It replays the recording in a scratch folder:

```bash
mkdir baton-try && cd baton-try && git init -q
baton init --roles frontend,backend,qa
baton post Q --as frontend --to backend --title "Which route serves health?" "For the status page."
baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."
baton reply Q-001 --as backend --close "Use GET /api/health."
baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."
```

The first hand-off is refused (`answer first: baton show Q-001, then baton reply …`) and nothing is written; after the reply it goes through as `H-002`. Or just run `baton demo` for a narrated replay on a temporary board; without installing anything, `uvx baton-handoff demo`.

## Why baton

- **No half-done hand-offs.** An agent can't report done while a question to it is still open.
- **Decisions don't get lost.** Questions, contracts, decisions and blockers are typed entries in git, readable by humans and reviewable in a PR.
- **Cheap to read.** Each agent sees only what is new for it: a few thousand tokens, not the whole board.
- **Any agent.** Claude Code, Codex, Cursor or anything that runs a shell command.
- **Nothing to run.** No server, no database, no dependencies.

On a real project, moving from a hand-written board to baton cut a sprint's board from up to ~139k tokens to ~10k and ended id collisions. [See the evidence](docs/why-baton.md).

## What it's for

| Use | What you get |
|---|---|
| **Agents side by side on your machine** | One board for every agent, even across git worktrees. |
| **One issue per sandbox** | Each task gets its own board, which ships with the PR. [Sandbox mode](docs/sandbox.md) |
| **Your team's rules** | Policies refuse or flag entries that skip what your team expects. [Policies](docs/policies.md) |
| **CI on GitHub** | Actions that run a task's board around your agent and check it on the PR: [setup-baton](https://github.com/marketplace/actions/setup-baton-cli), [baton-task](https://github.com/marketplace/actions/baton-task-board), [baton-check](https://github.com/marketplace/actions/baton-pr-check) on the GitHub Marketplace. [How to use them](docs/sandbox.md#with-github-actions) |
| **Keeping an eye on the work** | A local dashboard and metrics: who is blocked, what is stale. [Commands](docs/commands.md) |

## How it works

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/TheKathan/baton/main/assets/how-it-works-animated-dark.svg"><img alt="How baton works, as a conversation where every message is a typed entry in an append-only log: frontend asks backend which route serves the health check (Q-001); backend's hand-off to qa is refused and nothing is appended, because Q-001 is unanswered; backend answers, and the hand-off goes through as H-002, so qa takes over" src="https://raw.githubusercontent.com/TheKathan/baton/main/assets/how-it-works-animated-light.svg" width="720"></picture></p>

Agents run `baton`. Each write appends one event to a log in `.baton/` under a lock, and readable views are generated from it. [More on how it works](docs/how-it-works.md).

## Install

baton is on PyPI as `baton-handoff` and installs the `baton` command. It needs Python 3.11 or newer on macOS or Linux; macOS ships Python 3.9, so `uv` is the easiest route: it fetches a recent Python for you.

```bash
uv tool install baton-handoff
```

`pipx install baton-handoff` works too, and the [getting started guide](docs/getting-started.md) shows it, then how to set up your agents.

## Documentation

- [Getting started](docs/getting-started.md): install, try it, set up your agents, troubleshooting
- [Why baton](docs/why-baton.md): evidence, how it compares, FAQ
- [How it works](docs/how-it-works.md): files, worktrees, stability, limits
- [Sandbox mode](docs/sandbox.md): one board per task
- [Commands](docs/commands.md): every command and flag, and the MCP tools
- [Policies](docs/policies.md) · [Configuration](docs/configuration.md) · [Board format](docs/FORMAT.md)

## Contribute

Bugs, questions and ideas go to [issues](https://github.com/TheKathan/baton/issues), and pull requests are welcome: see [CONTRIBUTING](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md). If baton helps your agents, a star helps others find it.

[CHANGELOG](CHANGELOG.md) · [SECURITY](SECURITY.md) · [LICENSE](LICENSE) (MIT)
