# Getting started

After this guide you have baton installed, you have seen it refuse a hand-off, and your agents use it on your own project. It takes about five minutes.

## 1. Install

**You need Python 3.11 or newer, on macOS or Linux.** macOS ships Python 3.9, and some Linux LTS releases ship 3.10. Windows is not supported (see [Limits](how-it-works.md#limits)). Check with `python3 --version`.

Pick one:

```bash
# uv (recommended): it downloads a recent Python if yours is too old
uv tool install "git+https://github.com/TheKathan/baton.git@v1"

# pipx: uses your Python, which must be 3.11 or newer
pipx install "git+https://github.com/TheKathan/baton.git@v1"

# npm: installs a launcher; it still needs python3 3.11 or newer and git
npm install -g github:TheKathan/baton#v1
```

Then check it with `baton --version`.

baton is installed from GitHub. The `baton` package on PyPI is an unrelated project, so `pip install baton` and `uvx baton` don't install this one. For a pinned dev dependency of a JS project, and for working on baton itself, see [Install options](how-it-works.md#install-options).

## 2. Try it

Run this in a scratch folder. frontend asks backend a question, backend tries to hand off to qa before answering, and baton refuses:

```bash
mkdir baton-try && cd baton-try && git init -q
baton init --roles frontend,backend,qa
baton post Q --as frontend --to backend --title "Which route serves health?" "For the status page."
baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."
```

```text
baton: hand-off refused:
  - unanswered threads addressed to you: Q-001
  answer first: baton show Q-001, then baton reply Q-001 --as backend --close "…"
  (or hand off anyway with --force and the reason in the body)
```

Nothing was written. Answer the question, then hand off again:

```console
$ baton reply Q-001 --as backend --close "Use GET /api/health."
replied to Q-001 and closed it
$ baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."
posted H-002; status of backend set to 'DONE'
$ baton unread --as qa
```

Message bodies can be words on the command line (as here), `-` to read stdin, or `--body-file FILE`. `baton demo` replays the same refusal in a temporary board, if you'd rather not type.

## 3. Set up your project

In your repository:

```bash
baton init --roles orchestrator,backend,frontend,qa
```

- **Roles** are the names your agents act as. `--roles` limits them to that list, so a typo is refused. Plain `baton init` allows any role name.
- **The orchestrator** is whoever assigns the work and closes sprints: you, or a lead agent.
- **Sprints** are optional. Every board starts in sprint `S1`, and `baton sprint S2` archives it when you want a fresh board.

**Commit `.baton/config.json` and `.baton/events/`.** The event log is the record. `BOARD.md`, `STATUS.md` and `CONTRACTS-INDEX.md` are generated from it after every write, so you don't need to commit them. Cursors and the lock are git-ignored already.

## 4. Set up your agents

Every agent needs two things: the rules (when to read, how to post and hand off) and its role. The rules come from a skill or a rules file. The role comes from your brief, and the agent passes `--as <role>` on every command, because many agents start each shell command fresh and don't keep an exported `BATON_ROLE`.

Agents should use the `baton` command. MCP is only for agents that can't run shell commands.

### Claude Code

```bash
baton skill install --project
```

This writes `.claude/skills/baton/SKILL.md`, which you commit so everyone on the project gets it. Without `--project`, the skill goes to your global `~/.claude/skills/`, for every project on your machine. After upgrading baton, run it again with `--force`.

### Codex and other agents that read AGENTS.md

```bash
baton guide >> AGENTS.md
```

`baton guide` is the one-screen cheat sheet. For the full rules (closing threads, blockers, the orchestrator's duties), paste the output of `baton skill show` instead.

### Cursor

Cursor reads `AGENTS.md` too, so the step above works. To use a project rule instead, write an `.mdc` file in `.cursor/rules/` that always applies:

```bash
mkdir -p .cursor/rules
{ printf -- '---\ndescription: Coordinate with other agents through baton\nalwaysApply: true\n---\n\n'; baton guide; } > .cursor/rules/baton.mdc
```

### Agents that can't run shell commands

```bash
baton mcp install
```

This registers the MCP server in the project's `.mcp.json`. For a client that keeps its MCP config elsewhere, add the same entry there: the command `baton` with the argument `mcp`. The [MCP tools](commands.md#mcp-tools) apply the same rules as the command.

### Brief each agent

Start each agent in its own terminal or [git worktree](how-it-works.md#worktrees-and-sandboxes) of the same repository, and give it a short brief like this one:

```text
You are backend. Coordinate with the other agents through baton.
Start with `baton brief --as backend`, and pass `--as backend` on every baton command.
Build the health endpoint. If the API shape is unclear, ask frontend with `baton post Q`.
When you're done, hand off to qa with `baton handoff`.
Blocked? Post a B and tell the orchestrator directly.
```

If the brief refers to board entries, list their ids so the agent reads them with `baton brief --as backend --ids C-003,H-002`.

## 5. See what happened

- `.baton/BOARD.md`: the current sprint's entries with their replies and status, readable in your editor.
- `.baton/STATUS.md` or `baton status`: one row per role that has handed off.
- `baton open --blocking`: what is blocking someone right now.
- `baton serve --open`: a read-only dashboard in your browser, with blockers, waiting questions and metrics.

## Troubleshooting

| You see | Do this |
|---|---|
| ``no .baton/config.json found from <dir> upwards; run `baton init` first`` | Run `baton init` at the project root, or `cd` into the project. |
| `a role is required (--as <role> or $BATON_ROLE)` | Pass `--as <role>` on the command. |
| `unknown role 'designer'; known: …` | Use a role from the list, or add it to `roles` in `.baton/config.json`. |
| `hand-off refused: unanswered threads addressed to you: Q-001` | Read it with `baton show Q-001`, answer with `baton reply Q-001 --as <role> --close "…"`, then hand off again. |
| `hand-off refused: body is 25 lines (max 20)` | Shorten the body, and link long tables or logs from a file with `--files`. |
| `a contract change (C) must list the affected --files` | Add `--files src/api.ts,…` to the `C` entry. |
| `refused by the project's policies` | Fix what each listed rule asks for. See [Policies](policies.md). |
| `unread` prints far too much after a long break | `baton unread --as <role> --mark-read` moves your cursor without printing. |
| Agents follow old rules after an upgrade | `baton skill install --project --force` (or without `--project` for the global copy). |
| `pip install baton` installed something else | That's a different package. Use one of the install commands above. |

## Glossary

| Term | Meaning |
|---|---|
| **Entry** | One message on the board, with a permanent id: `Q` question, `C` contract change, `D` decision, `B` blocker, `H` hand-off. An entry and its replies form a thread, which stays open until someone closes it. |
| **Role** | The name an agent acts as, such as `backend` or `qa`. Entries are addressed to roles. |
| **Sprint** | A named batch of work (`S1`). `baton sprint S2` archives it and carries open threads over. |
| **Phase** | A slice of a sprint, such as `S1-A`, named on each hand-off. `baton close --phase S1-A` settles its hand-offs once its check (often QA) passes. |
| **Contract** | An agreed interface between agents (an API, a schema, a type) and the files it touches. A newer `C` supersedes the old one, so only one shape is live. |
| **Cursor** | The last event a role has read. `unread` shows what came after it and moves it forward. |
| **Lock** | A file lock baton takes for every write, so two agents never write at once and ids never collide. |

## Next

- [Commands](commands.md): every command and flag.
- [Sandbox mode](sandbox.md): one board per issue, shipped with the PR.
- [Why baton](why-baton.md): the evidence and how it compares.
