# StudyAny

StudyAny is an AI-assisted learning skill for Claude and Codex. It turns a
concrete learning goal into short lessons, active practice, evidence-based
assessment, spaced review, and persistent local study records.

The workflow chooses the medium that best demonstrates the current objective:
conversation for explanation and recall, a learner workspace artifact for
external work, or a mixture of both. It does not treat reading a lesson as
proof of mastery. Immediate correction is kept separate from long-term
retention: the skill schedules delayed retrieval, expanding intervals, and
changed-context checks before stable mastery.

StudyAny also gives evidence-based coaching feedback when a session is too
long, progress is fragile or stalled, the work drifts from its goal, or the
learner explicitly reports strain. It does not infer a psychological diagnosis
from ordinary tone or a single answer. Feedback events are stored separately
from learning evidence so a new chat can resume the latest adjustment without
treating it as a permanent learner label.

The bundled analytics engine calculates local weekly time, frequency, pacing,
review backlog, delayed retention, and separate evidence trends. It distinguishes
an unconfigured target from a measured shortfall, and reports an informational
above-plan signal separately from repeated-load overload risk.

## Global Install

Install the published package from npm:

```text
npm install -g studyany@latest --registry=https://registry.npmjs.org/
```

The postinstall step installs the skill at:

```text
~/.claude/skills/studyany/
$CODEX_HOME/skills/studyany/
```

When `CODEX_HOME` is not set, the Codex target defaults to
`~/.codex/skills/studyany/`. Claude also receives the `/learn` command at
`~/.claude/commands/learn.md`.

The explicit equivalent is:

```text
studyany install --scope global --client claude,codex
```

Restart Claude Code or Codex after installing so the client reloads its skill
catalog.

## Start A Session

In Claude Code, use natural language or the installed command:

```text
/learn I want to reach a concrete learning goal. Start with a short diagnostic.
```

In Codex, use natural language or explicitly mention the skill:

```text
Use the studyany skill. Start a study session for my current learning goal.
```

The skill records time through the bundled study clock when a shell is
available. It will not claim a precise duration, completed work, or mastery
without corresponding evidence.

## Project Install

For one project, install the package without `-g`:

```text
npm install --save-dev studyany
```

Project postinstall copies the skill to `.claude/skills/studyany/` and
`.cursor/skills/studyany/`, and installs `.claude/commands/learn.md`.

To select one client explicitly:

```text
npx studyany install --scope project --client claude
npx studyany install --scope project --client cursor
```

Inspect targets without writing files:

```text
studyany install --scope global --dry-run
```

If npm lifecycle scripts are disabled, install with `--ignore-scripts` and run
the explicit installer afterward. Set `STUDYANY_SKIP_INSTALL=1` to skip the
automatic postinstall path.

## Artifact-Based Practice

When the objective needs work outside the conversation, StudyAny identifies a
workspace and gives the learner a concrete handoff:

```text
Workspace: <where to work>
Artifact: <file, tool state, or external reference>
Learner action: <the exact task>
Review evidence: <what to return or what can be inspected>
```

It prefers existing learner material. When a starter is needed, it creates a
minimal non-destructive file under the visible project-root directory
`studyany-artifacts/<goal>/` by default, or in the learner's chosen project
path. It records the file's status, path, session, and review evidence in
`.study/artifacts.jsonl`. Comments, instructions, labels, sample text, and
other learner-readable content in generated artifacts use the learner's
current language. Required code keywords, API names, commands, and interface
fields remain exact. `.study/` is metadata-only. The starter is scaffolding,
not proof that the learner has mastered the objective.

## Persistent Study State

StudyAny keeps current continuity separate from historical evidence:

```text
.study/checkpoint.json   current stage, open loops, next action, and resume state
.study/sessions.jsonl    measured session history
.study/assessments.jsonl learning evidence
.study/reviews.jsonl     retrieval history and due dates
.study/decisions.jsonl   challenge decisions and route changes
.study/coaching_events.jsonl meaningful feedback and pacing adjustments
.study/summaries.jsonl   idempotent weekly, monthly, stage, and overall snapshots
.study/dashboard.md      derived human-readable summary
```

At the start of a new conversation, the skill reads the checkpoint and latest
records before teaching. When a shell is available, inspect the same state
directly:

```text
python .claude/skills/studyany/scripts/study_state.py --study-root .study status --json
```

If an existing workspace has no checkpoint, rebuild only the current pointer
from its saved records:

```text
python .claude/skills/studyany/scripts/study_state.py --study-root .study rebuild
```

The rebuild reports missing historical session logs as unknown. It never
estimates past minutes from conversation length.

## Computed Learning Analytics

Configure a commitment only when you want adherence alerts. Capacity is not a
commitment:

```json
{
  "available_minutes_per_week": 240,
  "target_minutes_per_week": 180,
  "target_sessions_per_week": 4,
  "target_study_days": ["Mon", "Tue", "Thu", "Sat"],
  "preferred_session_minutes": 45,
  "maximum_session_minutes": 75
}
```

The state command includes the derived projection:

```text
python .claude/skills/studyany/scripts/study_analytics.py --study-root .study --json
python .claude/skills/studyany/scripts/study_state.py --study-root .study status --json
```

The projection reports `overlong_session`, `behind_pace`, `above_plan`,
`frequency_gap`, `review_backlog`, `delayed_decay`, `fragile_progress`,
`stalled_progress`, and `overload_risk` when observable thresholds are met.
Missing targets and sparse evidence are reported as `not_configured` or
`insufficient_data`, never as failure. Checks happen when the skill is invoked;
StudyAny does not run a background notifier.

## Table Summaries

Generate a previous completed calendar period, a stage milestone, or an
on-demand overall snapshot:

```text
python .claude/skills/studyany/scripts/study_summary.py --study-root .study generate --kind week
python .claude/skills/studyany/scripts/study_summary.py --study-root .study generate --kind month --json
python .claude/skills/studyany/scripts/study_summary.py --study-root .study generate --kind stage --stage-id stage-01
python .claude/skills/studyany/scripts/study_summary.py --study-root .study generate --kind overall
python .claude/skills/studyany/scripts/study_summary.py --study-root .study check
```

`generate-due` checks the previous local week, previous local month, and
observable stage exit gates. The same period or stage is never appended twice:
`.study/summaries.jsonl` uses a stable `summary_key`. Stage summaries require
evidence across the stage concepts, so one ordinary task or session does not
close a stage. The Markdown report uses tables for period activity, stage and
overall progress, evidence dimensions, efficiency, reviews, risks, and next
actions. Missing time, denominators, or evidence remain marked as unknown or
insufficient rather than being estimated. After a successful
`study_clock.py stop`, the same due check runs automatically; its result is
returned as command metadata under `summaries`, while the session record stays
unchanged.

## Challenge Handling

StudyAny treats disagreement as a verification signal, not as an instruction
to agree. It classifies the issue as a fact, method, preference, assessment, or
question; checks the relevant evidence; and records whether the current claim
is supported, needs correction, has a valid alternative, is based on a bad
question, or remains uncertain. A supported method stays the explicit default,
while a valid correction is propagated to affected plan items.

The same claim has a bounded adjudication cycle. Repeating a rejection without
new evidence does not make StudyAny alternate methods indefinitely. The claim
is held or deferred, the evidence that would reopen it is stated, and the
lesson returns to unaffected work. Decisions are kept in
`.study/decisions.jsonl` and summarized in the checkpoint for the next chat.

## Uninstall

Remove the current StudyAny installation for selected clients:

```text
studyany uninstall --scope global --client claude,codex --dry-run
studyany uninstall --scope global --client claude,codex
```

For a project installation, use `--scope project` and the relevant client.
Uninstall removes the selected `studyany` skill and the managed Claude
`learn.md` command.

## Publish

```text
npm login
npm version patch
npm publish --access public --registry=https://registry.npmjs.org/
```

The package name is the unscoped `studyany`; publishing requires an npm
account with permission for that package and the registry's current
authentication requirements.

## Study Clock

The skill calls the bundled Python script when a shell tool is available:

```text
python .claude/skills/studyany/scripts/study_clock.py start --subject "example" --mode lesson --objective "Complete one practice task"
python .claude/skills/studyany/scripts/study_clock.py status
python .claude/skills/studyany/scripts/study_clock.py stop --status complete --next-action "Review the evidence"
```

On Windows, use `py -3` if `python` is not on `PATH`. The script writes an
open session to `.study/active-session.json`, then appends the measured session
to `.study/sessions.jsonl` when stopped.
