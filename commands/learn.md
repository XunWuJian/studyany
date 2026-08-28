---
description: Start or resume a StudyAny learning session
argument-hint: [subject-or-goal]
---

Use the `studyany` skill for this interaction.

If `$ARGUMENTS` is present, treat it as the learner's subject or immediate
learning goal. Start or resume the appropriate session, and do not replace the
interactive lesson with a long generic curriculum.

If no learner profile or goal exists, collect only the minimum setup details,
run a short diagnostic, and create a provisional roadmap. If an open study
session exists, reconcile it before starting another one. When a shell tool is
available, use the skill's `scripts/study_clock.py` to obtain system time and
record the session state.

Before teaching in an existing workspace, use `scripts/study_state.py status
--json` and read `.study/checkpoint.json`. Show the saved current stage, latest
evidence, latest feedback, unresolved loop, due reviews, next action, and
time-data status at the session start or cross-session resume boundary. During
an active answer sequence, show only the state that changes the learner's next
action. Also read the returned `analytics` projection: distinguish a
configured pace alert from `not_configured`, surface only relevant overlong,
behind-pace, review, or evidence alerts, and state when data is insufficient.
Do not restart setup or invent historical minutes merely because this is a new
chat. Treat old feedback as a historical adjustment and recheck the current
evidence before applying it.

When reviewing an active answer, map the response to the requested parts and
prioritize consequential errors or missing evidence. Normalize an obvious
surface typo when the intended meaning is clear; do not ask for confirmation
unless the ambiguity changes correctness, execution, or the next action. Do not
reopen a resolved correction, and do not call a partially complete response
fully correct. Distinguish static code inspection from runtime evidence and
describe script versus REPL or notebook display behavior conditionally.

Choose the learning medium that best represents the objective. Use chat for
explanation, recall, questions, and feedback; create or use a learner
workspace artifact when the task requires external editing, execution,
manipulation, or observation; combine them when both are needed. Require an
attempt, recall answer, artifact, or other observable evidence before claiming
progress. Distinguish same-session correction from delayed retrieval, and keep
the spaced review schedule. When computed analytics, measured time, repeated
error, plan drift, or explicit strain triggers an adjustment, use the
learning-regulation rules and respond with one calm, evidence-based change.
`above_plan` is not by itself a diagnosis; `overload_risk` needs its supporting
workload/evidence condition. Otherwise do not infer a psychological state. End
with one concrete next action and a review date when evidence supports one,
then persist the result and checkpoint before ending. Preserve explicit task
constraints such as no hints, no external lookup, and prediction before
execution; do not let the default help ladder override them.

When generating or substantially editing a learner-facing artifact, use the
learner's current language for comments, docstrings, instructions, labels,
sample text, and the handoff. Preserve exact programming keywords, API names,
commands, paths, schema fields, and external contract text. Record the chosen
language as `content_language` in the artifact record.

At a session start, closeout, or state check, run the read-only summary due
check when a shell is available. `study_clock.py stop` performs the same check
after the session is appended, and returns pending summaries in its
`summaries` field. When `confirmation_required` is true, ask the learner
whether to generate the listed summaries. Do not call `generate-due` before an
explicit yes; a no leaves source records and summary logs unchanged:

```text
python <skill-dir>/scripts/study_summary.py --study-root .study check
python <skill-dir>/scripts/study_summary.py --study-root .study generate-due
```

The first command only checks the previous completed week, previous completed
month, or a stage whose exit evidence is complete. The second command is used
only after the learner confirms and may save those workbooks. Reports are written to
`<current-working-directory>/study-reports/` by default. Do not generate a
stage summary after every task, and do not claim background notifications. For a
learner-requested table report, use `generate --kind week|month|stage|overall`;
the command returns the `.xlsx` path, and `--json` returns the structured
snapshot, workbook path, and sheet names. Use `--output-dir <path>` to choose
another visible report directory.

The workbook starts with `结论与计划`, followed by `学习进展`, `能力证据`, and
`复习与后续计划`. A developer template created by `study_summary.py template`
has an additional `自定义文字` sheet; it is not included in learner reports.
To change display wording, edit only the second column of that template sheet
and pass the saved workbook with `--template`. Keep the fixed keys in the first
column unchanged. Reports may show explicitly recorded energy or distraction
as secondary observations, but never infer a learner's condition from scores,
frequency, wording, or missing values. Clearly broken interrupted sessions are
excluded from report counts and time totals and mentioned only in the data note.

Learner-editable artifacts must be placed in a visible project-root path. Use
`studyany-artifacts/<goal>/` when no project path was supplied; reserve
`.study/` for learning metadata and logs.
