# Policies

Policies are your team's own rules for board entries, such as "hand-offs cite a story" or "decisions stay short". baton checks them on every new entry, whether it comes from the CLI or from MCP.

After reading this guide you can add rules to `.baton/config.json`, choose between a warning and a refusal, and find existing entries that break a rule.

## Add a rule

Put a `"policies"` list in `.baton/config.json`:

```json
"policies": [
  {"rule": "cites",       "kinds": ["H"],      "mode": "refuse"},
  {"rule": "named_to",    "kinds": ["Q", "B"], "mode": "warn"},
  {"rule": "max_lines",   "kinds": ["D"],      "lines": 2,  "mode": "warn"},
  {"rule": "files",       "kinds": ["D"],      "mode": "warn"},
  {"rule": "title_match", "kinds": ["H"],      "pattern": "^S\\d+", "mode": "refuse",
   "message": "hand-off titles start with the sprint, e.g. S7-A backend"}
]
```

Each rule is an object with these keys:

| Key | Required | Meaning |
|---|---|---|
| `rule` | yes | One of the [rules](#rules). |
| `kinds` | no | A list of entry kinds the rule applies to, for example `["H"]`. Default: every kind. |
| `mode` | no | `warn` (the default) or `refuse`. |
| `message` | no | Replaces the default explanation in the output. |
| `lines` | `max_lines` only | The maximum body length, as an integer. |
| `pattern` | `title_match` only | A regular expression the title must match (Python `re.search`). |

In JSON, write a backslash in a pattern twice: `"^S\\d+"`.

## Rules

| Rule | The entry must... | Fix it with |
|---|---|---|
| `cites` | cite at least one id. | `--cites STORY-703` |
| `files` | list at least one affected file. | `--files src/api.ts` |
| `named_to` | be addressed to at least one role by name, not only `all`. | `--to backend` |
| `max_lines` | have a body of at most `lines` lines. | shorten the body, link long details from a file |
| `title_match` | have a title that matches `pattern`. | rename the title |

Rules apply to entries written with `post` and `handoff`. Replies and closes are not checked.

## Modes

**`refuse`** writes nothing and exits 1. The output names every broken rule, so the agent can fix them all in one retry:

```console
$ echo "done" | baton handoff --as backend --phase S1-A --state DONE --to qa --title "backend health" -
baton: refused by the project's policies (.baton/config.json):
  - policy cites (H): must cite what it relates to (--cites STORY-…,DG-…)
  - policy title_match (H): hand-off titles start with the sprint, e.g. S7-A backend
```

The second line shows `message` replacing the default text. The agent fixes the entry and posts again.

**`warn`** posts the entry and prints each broken rule on stderr:

```console
$ printf 'a\nb\nc\n' | baton post D --as orchestrator --title "Use dev" -
warning: policy max_lines (D): body must be at most 2 lines (link long details from a file)
warning: policy files (D): must list the affected files (--files)
posted D-002
```

Use `refuse` for rules agents can always satisfy, and `warn` while you introduce a rule.

## Check existing entries

`baton lint` runs your policies over the whole board. It reports every violation as a warning, whatever the rule's mode, and exits 0 unless the board has real errors (duplicate ids, unknown kinds, contracts without files):

```console
$ baton lint
warn  D-002: policy max_lines (D): body must be at most 2 lines (link long details from a file)
warn  D-002: policy files (D): must list the affected files (--files)
warn  Q-003: policy named_to (Q): must be addressed to a role by name, not only to all (--to <role>)
3 entries, 0 error(s), 3 warning(s)
```

Entries imported with `baton import` are skipped, because old boards were not written under your rules. The MCP tool `baton_lint` does the same.

## Suggested policies

`baton lint --suggest` reads the board and proposes rules that most entries of a kind already follow. It needs at least 5 entries of a kind (imported ones are left out) and skips rules your config already covers. A rule that at least 90% of the entries follow is suggested as `refuse`, and one that 50% to 90% follow as `warn`. A `title_match` rule is suggested only when at least 80% of titles share a pattern: a sprint prefix (`^S\d+`), a ticket id at the start, or a ticket id anywhere.

```console
$ baton lint --suggest
Suggested policies, from 51 entries (not imported). Each rule is already followed by most entries of its kind:
  - cites for D: 100% of 8 D entries cite an id → refuse
  - title_match for H: 81% of 27 H entries have titles that start with a sprint, e.g. S7-A → warn

Add the ones you want to .baton/config.json under "policies":

"policies": [
  {"rule": "cites", "kinds": ["D"], "mode": "refuse"},
  {"rule": "title_match", "kinds": ["H"], "pattern": "^S\\d+", "message": "H titles start with a sprint, e.g. S7-A", "mode": "warn"}
]
```

It changes nothing. Copy the rules you agree with into your config.

## Examples

Every contract names its files, and every blocker names a role:

```json
"policies": [
  {"rule": "files",    "kinds": ["C"], "mode": "refuse"},
  {"rule": "named_to", "kinds": ["B"], "mode": "refuse"}
]
```

Hand-offs cite a story and start with a sprint tag:

```json
"policies": [
  {"rule": "cites",       "kinds": ["H"], "mode": "refuse", "message": "cite the story, e.g. --cites STORY-703"},
  {"rule": "title_match", "kinds": ["H"], "pattern": "^S\\d+-[A-Z] ", "mode": "refuse"}
]
```

Keep every entry short, as a warning:

```json
"policies": [{"rule": "max_lines", "lines": 20, "mode": "warn"}]
```

## When the config is wrong

A bad policy stops every write and read of the board until you fix it, with a message that names the rule:

```console
$ baton post Q --as backend --to qa --title t x
baton: .baton/config.json: policies[0]: unknown rule 'bogus'; known: cites, files, named_to, max_lines, title_match
```

A `max_lines` rule needs an integer `lines`, a `title_match` rule needs a `pattern` that compiles, `mode` must be `warn` or `refuse`, and `kinds` must be a list.

In [sandbox mode](sandbox.md) the board reads `.baton/sandbox.json`, not `config.json`, so put the policies there (see [Configuration](configuration.md#batonsandboxjson)).
