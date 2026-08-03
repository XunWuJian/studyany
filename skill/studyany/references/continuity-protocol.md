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
   concept records, the latest assessment/review events, and the latest
   decision for each challenged claim. Do not scan every historical line unless
   a report or audit requires it.
5. Surface a compact resume block before teaching:

   ```text
   Resume: <subject and current stage>
   Last evidence: <latest observed evidence or unknown>
   Open loops: <highest-priority unresolved evidence>
   Open disputes: <pending or deferred challenge decisions, or none>
   Due reviews: <items and dates>
   Next action: <the saved action>
   Time: <measured total or unknown, with the reason>
   ```

6. If a checkpoint, goal, and roadmap already exist, do not ask the learner to
   repeat setup or restart the diagnostic. Ask the saved open-loop question or
   assign the saved next action. Ask for clarification only when records
   conflict or the learner explicitly changes the goal. Do not reopen a
   locked challenge decision unless new evidence, a new version, or a changed
   constraint is present.

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

## Close Every Session

Before ending a learning interaction:

1. Preserve the learner's result, including failure or partial evidence, in
   the appropriate append-only assessment/review/artifact record.
2. Close the clock session when one was started. Use `interrupted` when the
   session stopped without a valid exit check. Never derive minutes from the
   number of messages.
3. Update `checkpoint.json` atomically with the latest evidence references,
   current stage, unresolved loops, next action, next review, and any missing
   data warning. Keep the checkpoint small enough to read at the next start.
4. Regenerate `dashboard.md` from the records or update its derived summary.
   Do not rewrite or delete historical JSONL events.
5. End with one concrete next action. A lesson is not persisted merely because
   the assistant displayed a summary in chat.

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
- Missing `sessions.jsonl` means historical time is unknown, not zero.
- Missing assessment dimensions remain `null`, not a failed score.
- If a record is malformed, preserve it, report the warning, and continue with
  the readable records. Never silently discard history.
