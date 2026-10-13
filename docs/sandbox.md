# Sandbox mode: one board per task

Sandbox mode is for AI developers that work each issue in its own short-lived sandbox. Every task gets its own board. The board stays local while the agents work, needs no network, and ships with the pull request, so reviewers can read what the agents asked, decided and handed off.

After reading this guide you can start a task board, work on it, export it with `finish`, and wire the whole sequence into a trigger or CI job.

## When to use it, and when not

Use sandbox mode when:

- each issue or ticket runs in a fresh checkout (a container, a VM or a clone) that is thrown away afterwards;
- more than one agent works on the task (an orchestrator, a builder, QA), and you want their exchange in the PR;
- you want no server, no shared state and no network access during the run.

Use the normal board (`baton init`) instead when:

- agents work on one long-lived repository across many sprints, and the board should live on the main branch;
- agents need to coordinate live with agents working on a different task. Sandboxes do not talk to each other while they run (see [Limits](#limits)).

A single agent on a single task can use sandbox mode too, but you gain little: the board mostly records its own decisions.

## The lifecycle

All commands run in the sandbox's git checkout. Examples use the task id `LIN-123`; any id made of letters, digits, `.`, `_` and `-` works.

### 1. Start

```console
$ baton init --sandbox --task LIN-123 --roles orchestrator,backend,qa
sandbox board for LIN-123: new task board
```

This creates `.baton/sandbox.json` and an empty board in `.baton/sandbox/`, and lists both in `.git/info/exclude`. If the checkout has a committed `.baton/config.json`, the sandbox copies the team's settings from it: `policies`, `kinds`, limits and, unless you pass `--roles`, the roles. The output then ends with `policies, kinds, roles from .baton/config.json`. Without a project config, leave `--roles` out to allow any role name. A sandbox board takes precedence over a project board in the same checkout, and it is never redirected to a main worktree.

A checkout holds one sandbox board. A second `baton init --sandbox` in the same checkout is refused unless you pass `--force`, which starts over.

### 2. Work

Agents use the usual commands, and every rule applies unchanged: hand-offs are refused while a question to you is unanswered, `C` entries need `--files`, and your [policies](policies.md) are checked.

```bash
baton brief --as backend                                # start here
baton contracts --paths 'modules/network/**'            # before changing shared files
baton post Q --as backend --to qa --title "Which env for smoke tests?" -
baton handoff --as backend --phase P1 --state "DONE pending QA" --to qa --title "P1 backend" -
```

See [Commands](commands.md) for what each command does, and the "read at three moments" rule that keeps token cost low.

### 3. Finish

```console
$ baton finish
wrote .baton/tasks/LIN-123.jsonl (4 events, 4 threads): commit it with your PR

### baton: LIN-123

**Open questions and blockers**
- **Q-001** Which env for smoke tests? · backend

**Contracts**
- **C-003** Add route output (files: modules/network/outputs.tf) · backend

**Decisions**
- **D-002** Use dev for smoke tests · orchestrator

**Hand-offs**
- **H-004** P1 backend · backend

_Full board: `.baton/tasks/LIN-123.jsonl` · 4 thread(s)_
note: 1 question(s)/blocker(s) still open: Q-001
```

`finish` writes the whole board, in order, to `.baton/tasks/LIN-123.jsonl` and prints a Markdown summary. The `note:` line goes to stderr. It works only on a sandbox board; on a normal board it fails with `` `baton finish` is for sandbox boards ``.

### 4. Commit with the PR

```bash
git add .baton/tasks/LIN-123.jsonl
git commit -m "LIN-123: agent board"
```

Put the summary in the PR description or a comment, using whatever your tooling provides. See [Use it in a pipeline](#use-it-in-a-pipeline).

## What goes in the PR and what stays local

| Path | In the PR? | Why |
|---|---|---|
| `.baton/tasks/<task>.jsonl` | Yes | The task's whole board, one file per task, so two PRs never conflict. |
| `.baton/sandbox.json` | No | The live board's config, excluded in `.git/info/exclude`. |
| `.baton/sandbox/` | No | The live events, cursors, lock and views, excluded the same way. |

`.git/info/exclude` applies to this clone only and is never committed, so your `.gitignore` stays untouched. Check it yourself with `git status`: before `finish`, a sandbox with a board shows no `.baton` changes; after `finish`, only `.baton/tasks/LIN-123.jsonl` appears.

If the directory is not a git checkout, baton cannot write the exclude file and says so: add `.baton/sandbox*` to your ignores yourself.

## Resume: a second sandbox on the same task

If a task needs a second run (a reviewer asked for changes, or the first sandbox died), start the board the same way:

```console
$ baton init --sandbox --task LIN-123 --roles orchestrator,backend,qa
sandbox board for LIN-123: resumed 6 event(s) from .baton/tasks/LIN-123.jsonl
$ baton unread --as backend
0 unread
```

baton finds `.baton/tasks/LIN-123.jsonl` on the branch and rebuilds the board from it, with the same ids. Every role starts at the tip, so nobody re-reads the history. New entries continue the numbering, and the next `finish` rewrites the file with the whole board. The branch must contain the exported file, so check out the PR branch first.

## Live contracts from merged tasks

Other tasks' exported files appear on your branch once their PRs merge. baton reads them and lists their open `C` (contract) entries, labelled `<task>/<id>`.

`baton brief` includes them (up to 20):

```text
## Live contracts from other tasks (1)

- LIN-100/C-001 · Subnet output shape · files: modules/network/outputs.tf
```

`baton contracts` lists them, and `--paths` filters by file glob:

```console
$ baton contracts --paths 'modules/network/**'
[LIN-100/C-001] backend · Subnet output shape · files: modules/network/outputs.tf
0 live contract(s) on this board, 1 from other tasks
$ baton contracts --paths 'docs/**'
0 live contract(s) on this board, 0 from other tasks
```

Run it before you change a shared file. The command also lists your own board's open contracts first. A contract stays live until its task closes it, so an agent that replaces a contract posts the new `C` with `--supersedes C-…`, which closes the old one (the skill teaches this).

## The finish summary

`finish` prints the summary after the export line. Sections appear only when they have entries: open questions and blockers, contracts, decisions and hand-offs. A board without entries prints `_No entries._`. When baton refused writes in this sandbox, a line such as `_baton refused 2 write(s) in this sandbox (2 hand-offs)_` shows reviewers that the rules were enforced.

| Option | What it does |
|---|---|
| `--summary FILE` | Writes the summary to `FILE` and prints only the `wrote ...` lines. |
| `--strict` | Exits 1 while a question or blocker is still open. |

`--strict` still writes `.baton/tasks/<task>.jsonl` and the summary before it exits, so you can inspect them. It names the open ids on stderr:

```console
$ baton finish --strict --summary pr.md
wrote .baton/tasks/LIN-123.jsonl (4 events, 4 threads): commit it with your PR
wrote the PR summary to pr.md
baton: 1 question(s)/blocker(s) still open: Q-001
$ echo $?
1
```

Once the question is answered and closed, `finish --strict` exits 0:

```console
$ baton reply Q-001 --as qa --close "Use dev."
replied to Q-001 and closed it
$ baton finish --strict --summary pr.md >/dev/null; echo $?
0
```

## Use it in a pipeline

A trigger or CI job runs four steps around the agent: start the board, run the agent, `finish --strict`, then stage the board file. The script below is plain git and baton. It does not call any hosting, tracker or chat API: commit, push and report the way your own tooling does.

```sh
#!/bin/sh
# Usage: run-task.sh TASK-ID "agent command"
# Runs one task in the current git checkout: board -> agent -> export -> stage.
set -eu

task="$1"
agent="$2"
summary="${TMPDIR:-/tmp}/baton-$task-summary.md"

# 1. Start the task's board (resumes it if the branch already has .baton/tasks/$task.jsonl).
baton init --sandbox --task "$task" --roles orchestrator,backend,qa

# 2. Let the agent work. It reads and writes the board with the baton command.
sh -c "$agent"

# 3. Export the board. --strict exits 1 while a question or blocker is still open.
if ! baton finish --strict --summary "$summary"; then
  echo "open questions or blockers: not staging the board" >&2
  exit 1
fi

# 4. Stage the board next to the agent's own changes. Commit, push and open the PR your way.
git add ".baton/tasks/$task.jsonl"
git status --short
echo "PR summary: $summary"
```

How it behaves:

- With an agent that hands off and leaves nothing open, it exits 0, stages `.baton/tasks/LIN-7.jsonl` and leaves the summary in `$TMPDIR`.
- With an agent that leaves a question open, it prints `baton: 1 question(s)/blocker(s) still open: Q-001` and exits 1 without staging. The exported file is already on disk but untracked, so a later step can still read it.
- The agent's own changes are not staged. Add them with your own `git add` before you commit.

Decide for yourself what a failing `--strict` means: fail the job, comment on the task, or rerun the agent with the open question in its brief. Drop `--strict` if open questions should not block the PR; `finish` then prints a note and exits 0.

To tell agents their role and the rules, run `baton skill install --project` once in the repository (it writes `.claude/skills/`, which you commit) or paste `baton guide` into the agent's brief.

## Use it through MCP

The `baton` command is preferred. It has every option and works in any shell. Use MCP only for an agent that cannot run shell commands. Register the server once with `baton mcp install`, then the agent has:

| MCP tool | Same as |
|---|---|
| `baton_sandbox_start` (`task`, `roles`, `force`) | `baton init --sandbox --task` |
| `baton_contracts` (`paths`) | `baton contracts --paths` |
| `baton_finish` (`strict`) | `baton finish [--strict]` |

`baton_finish` returns the summary as text, so the agent can put it in its answer. It has no `--summary FILE` option. The board is found from the server's working directory, or from `BATON_ROOT`. All other tools (`baton_brief`, `baton_post`, `baton_handoff` and the rest) work on the sandbox board the same way. See [Commands](commands.md#mcp-tools).

## Limits

- **No live coordination between sandboxes.** Two sandboxes running at the same time do not see each other's boards. A task sees another task's contracts only after that task's PR merges. A question that needs an answer now belongs in your tracker or the PR.
- **One board per task.** A checkout holds one sandbox board, and the exported file is named after the task. Two tasks in one checkout need two checkouts.
- **Only open contracts cross over.** Other tasks' questions, decisions and hand-offs are not shown to you, only their live `C` entries.
- **Append-only.** You cannot edit or delete an entry, in a sandbox or anywhere else.

## FAQ

**Can I use a normal `.baton/config.json` and a sandbox board in the same repository?** Yes. In a checkout with `.baton/sandbox.json`, the sandbox board wins. Other checkouts keep using `config.json`.

**What does `finish` do if I run it twice?** It rewrites `.baton/tasks/<task>.jsonl` with the current board, so run it again after the agents post more.

**Do ids clash between tasks?** No. Ids restart at 001 in every task, and other tasks' contracts are labelled `<task>/<id>` (`LIN-100/C-001`).

**Is the exported file safe to review?** It is plain JSONL, one event per line, in the stable [board format](FORMAT.md). Do not post secrets: the file is committed.

**The task id is refused.** Use letters, digits, `.`, `_` or `-`, starting with a letter or digit, up to 64 characters.

**Where is the config?** [`.baton/sandbox.json`](configuration.md#batonsandboxjson), created from the project's `.baton/config.json` when there is one.
