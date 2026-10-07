# Skill evaluation results

These rounds were run with the skill-creator loop: 3 tasks, each done by a Sonnet agent with the skill and by one without it. Each agent worked in a fresh copy of the test project, built by `make_fixture.sh`, and `grade.py` scored the runs (11, 12 and 9 checks per task). To reproduce a round, create the run directories with `make_fixture.sh`, start the 6 runs using the prompts in `evals.json`, then run `python3 evals/grade.py <iteration-dir>`.

| Round | What changed | With skill | Without skill | Cost of the skill |
|---|---|---|---|---|
| 1 | First draft | 77% | 80% | +4.2k tokens, +7 s |
| 2 | Skill: "settled" rules, hand-off tidy-up, safe sprint close. CLI: `handoff --closes` checks before writing, `close --sprint` keeps unanswered Q/B, `sprint` name check. Fixture: pagination question really open | 94% | 83% | +3.4k tokens, +11 s |
| 3 | Skill: close blockers on the fixer's word (say "not re-verified"). CLI: `close --sprint` keeps live contracts | 97% | 88% | +3.6k tokens, +9 s |
| 4 | Skill trimmed 1,832 → 977 words (mechanics moved into the CLI). CLI: `handoff`/`brief` point out your own threads that have replies | **100%** | 86% | **+1.0k tokens, +4 s** |

Scores in this table are on the final grader (12/12/11 checks per task). From round 4 on, the grader also checks the behaviours that told the two sides apart: closing a question you answered, closing a superseded contract, and handing off after a contract change.

## What we learned
- **Round 1: the skill made one task worse.** It told the orchestrator to bulk-close with `close --sprint`, which closed a question nobody had answered.
- **Most of the gains came from fixing baton itself.** The runs exposed duplicate hand-offs and sprint closes that dropped open threads. Once the CLI enforced the right behaviour, agents without the skill did well too. That is why the two scores meet in round 3.
- **The skill still changes behaviour where the CLI can't enforce it.** Agents with the skill close their own settled threads: in rounds 2 and 3 the frontend without the skill left its fixed blocker open. They also state an interim choice when they ask a question, and keep summaries short. Its only miss in round 3 was a 16-line summary against a ~15-line guideline.
- **What the skill adds** (rounds 2–4, against agents without it): the backend posts a hand-off after a contract change (3 of 3 vs 0 of 3) and closes the contract it superseded (3 of 3 vs 0 of 3); the frontend closes the question it answered and its own fixed blocker; questions state an interim choice.
- **The trimmed skill is cheaper and no worse.** Moving mechanics into the CLI let it shrink by half while scoring 100%.
- **The checks are now saturated.** For the next round, add harder tasks: a hand-off refused because a question is waiting; a contract that supersedes an older one; a stale cursor after an import; an entry that tries to give the agent orders.
