# Continuity Protocol

StudyAny uses three layers of local state, similar to a task system with a
current pointer, durable history, and a readable summary:

```text
.study/
├── checkpoint.json       # mutable current resume pointer
├── sessions.jsonl        # append-only session history
├── assessments.jsonl     # append-only learning evidence
├── reviews.jsonl         # append-only retrieval events
├── concepts.jsonl        # latest concept state
├── roadmap.json          # current plan and stage pointer
├── goals.json            # goal contract
├── artifacts.jsonl       # artifact lifecycle and evidence links
├── decisions.jsonl       # challenge adjudications and route decisions
├── coaching_events.jsonl  # meaningful feedback and pacing adjustments
├── summaries.jsonl        # generated period and milestone snapshots
└── dashboard.md          # derived human-readable report
```

`checkpoint.json` is the source for what to resume now. The JSONL files are
the evidence history. `dashboard.md` is useful for a person but must not be the
only state read by a new session. Do not store a full conversation transcript;
store concise unresolved loops and references to evidence instead.

## Start Every Session

For every non-setup learning interaction:

1. Resolve the learner's current workspace and read `.study/` there. Do not
   confuse the skill installation directory with the learner's study root.
2. If `.study/active-session.json` exists, run the clock status command and
   reconcile that open session before creating another one.
3. When a shell is available, run:

   ```text
   python <skill-dir>/scripts/study_state.py --study-root .study status --json
   ```

   Use `py -3` on Windows when needed. If `checkpoint.json` is missing, inspect
   the status output and run `rebuild` only after confirming the workspace and
   goal. A rebuilt checkpoint is `partial` when source evidence or time is
   missing.
4. Read `checkpoint.json`, the current roadmap stage, the latest relevant
   concept records, the latest assessment/review events, the latest decision
   for each challenged claim, and the latest coaching event. Do not scan every
   historical line unless a report or audit requires it.
5. Surface a compact resume block before teaching:

   ```text
   Resume: <subject and current stage>
   Last evidence: <latest observed evidence or unknown>
   Open loops: <highest-priority unresolved evidence>
   Open disputes: <pending or deferred challenge decisions, or none>
   Last feedback: <latest evidence-based adjustment or milestone, or none>
   Due reviews: <items and dates>
   Next action: <the saved action>
   Time: <measured total or unknown, with the reason>
   ```

   When `study_state.py status --json` is available, add one compact analytics
   line containing data quality, configured pace status, review backlog, the
   most relevant evidence trend, and the highest-priority alert. Do not turn
   `not_configured` or `insufficient_data` into a negative learner judgment.

6. If a checkpoint, goal, and roadmap already exist, do not ask the learner to
   repeat setup or restart the diagnostic. Ask the saved open-loop question or
   assign the saved next action. Ask for clarification only when records
   conflict or the learner explicitly changes the goal. Do not reopen a
   locked challenge decision unless new evidence, a new version, or a changed
   constraint is present. Treat a previous coaching signal as a prompt to
   recheck current evidence, not as a current mood or ability label.

   The same rule applies within an active answer sequence: once a surface slip
   or correction is resolved, close it. Do not ask the learner to confirm it
   again unless it recurs, changes the current assessment, or is an exact
   executable token that still needs verification.

## Keep Open Loops Small

An open loop is a short item that must be resolved before a progress claim can
advance. It should contain:

- a stable `loop_id`;
- the concept or stage when applicable;
- a concise summary of the missing evidence or pending action;
- the expected evidence;
- a due date or priority;
- a source reference to an assessment, review, session, dashboard, or artifact.

Record the substance of a pending task, not every question from the dialogue.
For example, `retrieve the exception category without a cue` is enough to
resume a review; the entire prior lesson is not required.

Do not create an open loop for an obvious typo, label, or formatting slip that
does not affect the objective. Keep an open loop only for missing evidence,
an unresolved consequential error, a material ambiguity, or a next action that
must be resumed later.

## Close Every Session

Before ending a learning interaction:

1. Preserve the learner's result, including failure or partial evidence, in
   the appropriate append-only assessment/review/artifact record.
2. If a meaningful milestone, trigger, recovery choice, review adjustment, or
   plan-alignment correction occurred, append one evidence-based event to
   `coaching_events.jsonl`. Do not log every tone impression.
3. Close the clock session when one was started. Use `interrupted` when the
   session stopped without a valid exit check. Never derive minutes from the
   number of messages.
4. Update `checkpoint.json` atomically with the latest evidence references,
   current stage, unresolved loops, next action, next review, and any missing
   data warning. Keep the checkpoint small enough to read at the next start.
5. Regenerate `dashboard.md` from the records or update its derived summary.
   Use the current `analytics` projection when available so time, pacing,
   review, and evidence sections agree. Do not rewrite or delete historical
   JSONL events.
6. End with one concrete next action. A lesson is not persisted merely because
   the assistant displayed a summary in chat.

At a session start, closeout, or explicit state check, run the summary due
check when a shell is available. It may append the previous completed local
week/month or a stage whose exit gates are satisfied. It must not append a
stage summary after every task. `summaries.jsonl` is idempotent by
`summary_key`, and a missing or partial source record remains visible in the
summary's data-quality table.

If the learner changes the goal, preserve the old history, update `goals.json`
and `roadmap.json`, and explain which open loops were deferred or made
obsolete. If a new conversation ends unexpectedly, leave the active session or
checkpoint intact for reconciliation; do not create a duplicate session on the
next turn.

## Conflict And Missing Data

- The explicit `roadmap.current_stage_id` is authoritative for the current
  stage; a stale `status: current` on another stage is advisory and should be
  corrected during the next checkpoint update.
- Latest observed assessment/review evidence outranks a prose dashboard line.
- A checkpoint points to evidence; it does not replace that evidence.
- A settled challenge decision is part of the resume boundary. Reopen it only
   through `references/challenge-protocol.md` and record the new evidence and
   revision; do not let the latest conversational assertion override it.
- A coaching event describes a past observation and adjustment. Recheck the
  current session before applying it; never carry an inferred psychological
  state across conversations.
- Missing `sessions.jsonl` means historical time is unknown, not zero.
- Missing assessment dimensions remain `null`, not a failed score.
- If a record is malformed, preserve it, report the warning, and continue with
  the readable records. Never silently discard history.
