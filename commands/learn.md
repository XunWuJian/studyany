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
time-data status. Also read the returned `analytics` projection: distinguish a
configured pace alert from `not_configured`, surface only relevant overlong,
behind-pace, review, or evidence alerts, and state when data is insufficient.
Do not restart setup or invent historical minutes merely because this is a new
chat. Treat old feedback as a historical adjustment and recheck the current
evidence before applying it.

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
then persist the result and checkpoint before ending.

When generating or substantially editing a learner-facing artifact, use the
learner's current language for comments, docstrings, instructions, labels,
sample text, and the handoff. Preserve exact programming keywords, API names,
commands, paths, schema fields, and external contract text. Record the chosen
language as `content_language` in the artifact record.

Learner-editable artifacts must be placed in a visible project-root path. Use
`studyany-artifacts/<goal>/` when no project path was supplied; reserve
`.study/` for learning metadata and logs.
