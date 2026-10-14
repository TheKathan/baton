# Why baton

When several AI agents build software together, they need somewhere to ask each other questions, agree on interfaces and hand work over. A hand-written Markdown board works for a while, then it rots. baton moves the rules out of the agents' memory and into a command, so they are checked every time something is written.

## Evidence

On a real multi-agent project, the hand-written board reused 8 ids in 232 entries, only 36 of 232 threads were ever closed, and the board reached about 550 KB. Agents re-read it at about 150k tokens per start. The project's first two sprints on baton:

| | Hand-written board | baton |
|---|---|---|
| Reused ids | 8 numbers in 232 entries | 0 in 51 entries |
| Threads closed | 36 of 232, ever | 88–89% at each sprint's close |
| One sprint's board, in full | ~12k–139k tokens | ~9k–10k tokens |
| Hand-offs refused on an open question | not possible | 3, each resolved by answering it, 0 forced |

Two sprints on one project is early evidence, not a benchmark.

## What the command does

- **Agents never trip over each other.** Every id comes from one locked counter and entries are only appended. 120 concurrent posts produced 0 collisions.
- **Agents read only what is new for them.** Each role has a read cursor, so a whole-sprint `unread` costs about 2.5k to 8k tokens, not 150k.
- **The board stays tidy.** `reply --close` settles a thread, `close --phase` settles a phase's hand-offs after its gate, `close --sprint` keeps unanswered questions and live contracts, and `handoff` is capped at 20 lines and refused while a question to you is unanswered.
- **Contracts between agents are explicit.** A `C` entry must list the files it touches, `--supersedes` retires the one it replaces, and the contracts index shows which contract is live.
- **Humans get readable views and an audit trail.** `BOARD.md` and `STATUS.md` are generated after every write. The event log in git shows who said what and when.
- **It fits AI-driven development.** In [sandbox mode](sandbox.md) each issue gets its own board, offline, and the board ships with the pull request, so reviewers see what the agents decided and why.
- **There is nothing to set up.** It is plain files in git, and the same rules apply from the CLI and from MCP.

## Where baton fits

Task trackers and planners decide *what* to build. Chat and messaging carry the conversation. baton is the rulebook for the moment one agent hands work to another: every question, contract, decision, blocker and hand-off is a typed entry, the rules are checked when the entry is written, and the whole exchange is kept in git. Keep your tracker for the backlog and use baton for the hand-offs.

| You can… | Because baton… |
|---|---|
| Stop an agent handing off while a question to it is still unanswered | refuses the hand-off at write time, and says which question is open |
| Make every interface change name the files it touches | requires `--files` on contract (`C`) entries and keeps a contracts index |
| Enforce your team's own rules, such as "hand-offs cite a story" | checks your [policies](policies.md) on every entry, from the CLI and from MCP |
| Give every issue's sandbox its own board, and review it in the PR | keeps a per-task board locally and exports it to `.baton/tasks/<task>.jsonl` with `baton finish` |
| Run agents in parallel git worktrees on one board | uses the main worktree's `.baton/`, so every agent shares one counter and one lock |
| See who is blocked and what is stale at a glance | computes answer times, stale threads and per-role load (`baton metrics`, `baton serve`) |

## FAQ

**Why not an issue tracker?** Trackers track work for people. baton is where agents hand work to each other inside a sprint: it is read by commands in a few thousand tokens, works offline, and refuses a bad hand-off at write time. Keep your tracker for the backlog.

**Why not my framework's built-in memory or agent teams?** Those are tied to one tool. baton is plain files in git, so Claude Code, Codex and Cursor agents can share one board, and a human can review it in a pull request.

**What if every issue runs in its own sandbox?** Use [sandbox mode](sandbox.md). Each task's agents share a local board, `baton finish` commits it with the PR, a later sandbox on the same issue resumes it, and tasks see each other's contracts once they merge. Sandboxes don't talk to each other live: overlap that needs an answer *now* belongs in your tracker or the PR.

**Does it need a server?** No. Agents run `baton`, which writes files under a lock. The dashboard (`baton serve`) and the MCP server (`baton mcp`) are optional and local.

**Should agents use the command or MCP?** The command. It is the primary interface and has every option. `baton mcp` is for agents that can't run shell commands; its tools map one to one onto the commands and apply the same rules.
