# baton

A file-based, append-only coordination board for AI agents that build software together: an orchestrator, builder agents, QA and a human owner.

It combines two earlier boards:
- the **Rune Board** (Sweatshop): locked JSONL appends and per-agent unread cursors;
- the **`BOARD.md` protocol** (Sweat): typed entries, read-by-id, hand-off size caps, per-sprint archives, a contracts index and a status table.

The rules live in the tool, not in agents' memory, so ids can't collide, threads get closed and hand-offs stay short.

Python ≥ 3.11, standard library only. Works on macOS and Linux (it uses `flock`).

## Install

```bash
cd ~/repos/personal/baton
make install          # editable install: uv tool → pipx → symlink into ~/.local/bin
baton --version
make uninstall
```

Because the install is editable, a `git pull` in this repo updates the command everywhere. To run it without installing: `bin/baton …`.

## Set up a project

```bash
cd <project>
baton init --sprint S1 --roles orchestrator,backend,frontend,ai,test,qa,devops
```

This writes `.baton.json` (commit it) and the board directory:

```
.baton.json                       config: paths, current sprint, kinds, roles, hand-off cap
coordination/bbs/<sprint>.jsonl      SOURCE OF TRUTH, one file per sprint, append-only (commit)
coordination/bbs/status.json         one status row per role (commit)
coordination/bbs/.cursors/  .lock    per-agent read cursors and the lock (git-ignored)
coordination/BOARD.md                GENERATED: the current sprint + threads still open from before
coordination/STATUS.md               GENERATED: the status table
coordination/board-archive/BOARD-<sprint>.md      GENERATED at sprint rollover
coordination/board-archive/CONTRACTS-INDEX.md     GENERATED: every C- entry with files and status
```

Never edit the generated `.md` files by hand. They are rewritten after every write.

## Entry kinds

| Kind | Use | Enforced |
|---|---|---|
| `Q` | question to a role | `handoff` is refused while a Q addressed to you is unanswered |
| `C` | contract change (types, events, schema, env vars) | `--files` is required; listed in the contracts index |
| `D` | decision affecting more than one owner | |
| `H` | hand-off | ≤ `handoff_max_lines` (default 20); updates your status row |
| `B` | blocker | like Q; listed by `open --blocking` |

Every new entry gets the next number from a single counter, allocated under an exclusive lock (`Q-235`, then `C-236`, …). A number is never reused.

## Agent commands

Read at three moments only: (1) at start, (2) before changing a shared package, (3) before reporting done. Never poll.

```bash
baton unread --as qa                       # new entries addressed to you or all, plus replies on your threads
baton show C-143 H-150                     # read by id, from any sprint (C-7 = C-007)
baton brief --as backend --ids C-206,H-232     # start-up pack: guide, your status, questions waiting on you, cited entries
baton open --as backend                    # open threads you wrote or are named in (--all adds broadcasts)
baton post Q --as frontend --to backend --title "Which route serves X?" --cites SW-702 -   # body on stdin
baton post C --as backend --to frontend,qa --title "Health shape" --files packages/shared/src/health.ts -
baton reply Q-231 --as backend --close "Use /api/x (DG-99)."
baton handoff --as backend --phase S6-B --state "DONE pending QA" --to qa \
  --title "S6-B backend" --closes Q-231 --files qa/evidence/s6b/backend.md -
baton grep "companyHealth"
baton guide                                # the quick guide, for agent briefs
```

You can also set `BATON_ROLE=backend` instead of passing `--as` every time.

## Orchestrator commands

```bash
baton list --sprint S6 --kind C,H --status open
baton open --blocking
baton status                                # or: status --as qa --phase S6-A --state "NEEDS WORK"
baton sprint S7                             # archive S6 to BOARD-S6.md, start S7; open threads carry over
baton lint                                  # duplicate numbers, unknown kinds, C without files, long H/C/D
baton stats                                 # ~tokens per sprint and per role (unread now, open, waiting)
baton render --archives                     # regenerate every Markdown view
```

## Token budget

`unread`, `show` and `brief` always print full bodies, so nothing relevant is hidden. Costs are kept down in other ways:
- **Cursors** mean each event is read once.
- **Scoping:** `open` lists only threads that name you; `--all` adds broadcasts.
- **Length warnings** on `post` and `lint`: hand-offs are capped at `handoff_max_lines` (20 by default). Contracts and decisions get a warning above `body_warn_lines` (40 by default).
- **Backlog note:** when one `unread` exceeds `unread_warn_tokens` (20000 by default), it says so after printing everything. That usually means a stale cursor (`--mark-read`).
- **`baton stats`** shows where the tokens go.

## Migrating a hand-written Markdown board

```bash
baton init --sprint S6 --roles …
baton import coordination/board-archive/BOARD-S5.md --sprint S5 --dry-run
baton import coordination/board-archive/BOARD-S5.md --sprint S5
baton import coordination/BOARD.md --sprint S6
mkdir -p coordination/pre-baton && git mv coordination/BOARD.md coordination/board-archive/*.md coordination/pre-baton/
baton render --archives                                 # now generate BOARD.md, the archives and the index
baton close --sprint S5 --as orchestrator --reason "closed at migration"
baton unread --as <role> --mark-read                   # once per role, so nobody re-reads history
```

The importer keeps ids, authors, dates and bodies verbatim, and it accepts loose headings such as `### [H-212] ai → qa` with no status or date. If the same id appears twice, the second copy is renamed `X-NNN~2`. Numbers already shared by two kinds (e.g. `Q-232` and `H-232`) are kept and reported by `lint` as warnings. New ids continue after the highest imported number. baton never overwrites a Markdown file it did not generate, so you have to move the hand-written files aside before `render`.

## Development

```bash
make test     # stdlib unittest, including a 120-post concurrency test
make lint     # ruff via uvx
```

## Project

[CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [MIT License](LICENSE)
