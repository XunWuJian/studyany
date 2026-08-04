# Record Schema

Use JSON for current state and JSONL for append-only events. Keep timestamps in
ISO 8601 with an explicit offset when available. Use `null` for unknown values;
do not replace unknown data with a guessed value.

## profile.json

```json
{
  "version": 1,
  "learner_id": "local",
  "language": "en",
  "timezone": "Asia/Shanghai",
  "available_minutes_per_week": 240,
  "preferred_session_minutes": 45,
  "minimum_session_minutes": 10,
  "feedback_preferences": {
    "tone": "warm_direct",
    "celebrate_milestones": true,
    "playful_style": "off"
  },
  "created_at": "2026-08-03T19:00:00+08:00",
  "updated_at": "2026-08-03T19:00:00+08:00"
}
```

`language` is the learner-facing language preference, preferably a BCP 47-style
value such as `zh-CN` or `en`. It is not the programming language or subject
language. An explicit language request in the current turn takes precedence
for newly generated output.

Store only information needed to coach the learner. Do not store sensitive
personal data unless the learner explicitly asks and the local environment is
appropriate for it.

## goals.json

```json
{
  "version": 1,
  "subject": "example subject",
  "original_goal": "learn the subject",
  "operational_goal": "independently perform a defined task to a stated bar",
  "goal_type": "knowledge|exam|project|professional|personal_skill",
  "deadline": null,
  "success_evidence": ["artifact", "delayed_assessment"],
  "constraints": [],
  "status": "active",
  "created_at": "2026-08-03T19:00:00+08:00",
  "updated_at": "2026-08-03T19:00:00+08:00"
}
```

## roadmap.json

```json
{
  "version": 1,
  "subject": "example subject",
  "stages": [
    {
      "id": "stage-01",
      "title": "Foundations",
      "purpose": "Provide prerequisites for the target performance",
      "prerequisites": [],
      "concept_ids": ["concept-01"],
      "exit_criteria": ["Explain the core idea", "Complete an independent task"],
      "status": "current|blocked|complete|optional"
    }
  ],
  "current_stage_id": "stage-01",
  "assumptions": [],
  "updated_at": "2026-08-03T19:00:00+08:00"
}
```

## checkpoint.json

This is the mutable current-state pointer used to resume a new conversation.
It is not a replacement for append-only evidence logs.

```json
{
  "version": 1,
  "state": "ready|partial|blocked",
  "updated_at": "2026-08-03T19:00:00+08:00",
  "subject": "example subject",
  "current_stage_id": "stage-01",
  "current_stage_title": "Foundations",
  "last_activity_at": "2026-08-03T19:00:00+08:00",
  "last_session_id": "session-2026-08-03-001",
  "last_assessment_id": "assessment-2026-08-03-001",
  "last_review_id": "review-2026-08-03-001",
  "last_decision_id": "decision-2026-08-03-001",
  "last_coaching_event_id": "feedback-2026-08-03-001",
  "plan": {
    "version": "roadmap-v1",
    "status": "active|disputed|deferred",
    "decision_refs": []
  },
  "open_disputes": [
    {
      "decision_id": "decision-2026-08-03-001",
      "claim_id": "claim-stage-02-order",
      "kind": "fact|path|preference|assessment|question",
      "status": "pending_evidence|deferred",
      "summary": "The current route depends on one unresolved claim",
      "next_evidence": "A source, test, or changed-example result",
      "challenge_count": 1
    }
  ],
  "last_evidence": "Completed a changed-example task with a light cue",
  "last_feedback": "Keep the delayed review; application evidence is improving",
  "open_loops": [
    {
      "loop_id": "review-concept-01-unaided",
      "kind": "retrieval|evidence_gap|artifact|stage_gate|setup",
      "concept_id": "concept-01",
      "status": "open|resolved|deferred",
      "priority": "high|normal|low",
      "due_on": "2026-08-04",
      "summary": "Retrieve the idea without the previous cue",
      "expected_evidence": "Unaided explanation or changed-example task",
      "source_ref": "assessment-2026-08-03-001"
    }
  ],
  "next_action": "Complete one unaided retrieval task",
  "next_review": "2026-08-04",
  "resume_instruction": "Restore open loops before new material",
  "time_tracking": {
    "source": "sessions.jsonl|unknown|missing",
    "historical_minutes": null,
    "note": "Historical session log is missing"
  },
  "warnings": []
}
```

Update the checkpoint atomically after a session. Keep it concise and link
claims to evidence IDs. A missing or rebuilt checkpoint must use `partial` and
must list missing data instead of filling it with estimates.

## concepts.jsonl

Each line represents the latest state for a concept. Historical changes belong
in `assessments.jsonl` and `reviews.jsonl`.

```json
{
  "concept_id": "concept-01",
  "subject": "example subject",
  "title": "Core concept",
  "mode": "conceptual",
  "prerequisites": [],
  "mastery": 2,
  "understanding": 2,
  "retrieval": 1,
  "application": 1,
  "transfer": 0,
  "retention_stage": "new|repair|1d|3d|7d|14d|30d|maintenance",
  "last_reviewed": "2026-08-03",
  "next_review": "2026-08-04",
  "review_streak": 0,
  "failure_count": 0,
  "evidence_refs": ["session-2026-08-03-001"]
}
```

Mastery is a current estimate. It must be updated only with an evidence
reference and should move slowly when evidence is sparse.

## artifacts.jsonl

Each line records the lifecycle and evidence linkage of a learner workspace
item. Do not copy the artifact contents into the log.

```json
{
  "artifact_id": "artifact-2026-08-03-001",
  "session_id": "session-2026-08-03-001",
  "subject": "example subject",
  "content_language": "zh-CN",
  "kind": "file|external_result|procedure|performance|other",
  "workspace": ".",
  "path": "studyany-artifacts/goal-slug/starter.ext",
  "external_ref": null,
  "status": "planned|in_progress|submitted|reviewed|abandoned|missing_evidence",
  "created_at": "2026-08-03T19:00:00+08:00",
  "updated_at": "2026-08-03T19:30:00+08:00",
  "learner_action": "Complete the defined task",
  "expected_evidence": "A saved result plus a short explanation",
  "evidence_refs": ["assessment-2026-08-03-001"],
  "review_notes": "First consequential error and correction"
}
```

Use a project-relative `path` when possible. Use `external_ref` for a result
that is not represented by a local path, and use `null` for unavailable values.
The artifact record describes evidence state; it does not establish duration or
mastery by itself.

## decisions.jsonl

Each line records an adjudication or explicit reopening of a challenged claim.
The file is append-only. Use the same `claim_id` when revising the same claim;
increment `revision` and `challenge_count`. A later record is the current
decision for that claim.

```json
{
  "decision_id": "decision-2026-08-03-001",
  "claim_id": "claim-roadmap-stage-02-order",
  "kind": "fact|path|preference|assessment|question",
  "original_claim": "The prerequisite should come before the workflow",
  "challenge": "The learner proposed the reverse order",
  "verdict": "ai_error|ai_position_supported|valid_alternative|bad_question|uncertain",
  "status": "resolved|locked|pending_evidence|deferred",
  "assumptions": ["The goal includes independent troubleshooting"],
  "evidence_refs": ["assessment-2026-08-03-002"],
  "revision": 1,
  "challenge_count": 1,
  "decision": "Keep the prerequisite first for the current goal",
  "alternatives": [],
  "affected_items": ["stage-02"],
  "next_evidence": "A changed-example troubleshooting task",
  "created_at": "2026-08-03T19:00:00+08:00"
}
```

`ai_position_supported` means the evidence still supports the current
position; it is not a claim that the route is universally optimal.

## sessions.jsonl

```json
{
  "session_id": "session-2026-08-03-001",
  "subject": "example subject",
  "mode": "lesson",
  "started_at": "2026-08-03T19:00:00+08:00",
  "ended_at": "2026-08-03T19:45:00+08:00",
  "duration_min": 45,
  "duration_source": "clock|timestamps|user_estimate|unknown",
  "status": "complete|interrupted|planned|in_progress",
  "evidence_mode": "conversation|artifact|mixed",
  "planned_minutes": null,
  "objectives": ["objective-01"],
  "active_minutes": 35,
  "passive_minutes": 10,
  "recall_score": 0.75,
  "practice_score": 0.8,
  "confidence_before": 0.6,
  "confidence_after": 0.75,
  "coaching_event_ids": ["feedback-2026-08-03-001"],
  "feedback_summary": "Independent changed-example evidence; delayed retention still pending",
  "summary": "Completed a changed-example task with a light cue",
  "energy": null,
  "distraction": null,
  "evidence_refs": ["assessment-2026-08-03-001"],
  "artifact_ids": ["artifact-2026-08-03-001"],
  "mistakes": ["misconception or error category"],
  "next_action": "Complete one transfer task",
  "next_review": "2026-08-06"
}
```

`active_minutes` and `passive_minutes` are optional. When not measured, use
`null` rather than claiming precision.

When the bundled clock is used, an open `in_progress` record is stored at
`.study/active-session.json` until `stop` appends it to `sessions.jsonl`. Do
not copy the open record into the history log manually or start a second
session while it exists. The session ID is the idempotence key: if a stop is
retried after the event was appended, do not append a duplicate.

## reviews.jsonl

```json
{
  "review_id": "review-2026-08-03-001",
  "concept_id": "concept-01",
  "subject": "example subject",
  "scheduled_for": "2026-08-03",
  "reviewed_at": "2026-08-03T19:15:00+08:00",
  "result": "fail|hinted|pass|transfer_pass",
  "delay_type": "same_session|next_day|spaced|maintenance",
  "interval_stage": "repair|1d|3d|7d|14d|30d|60d",
  "same_session": false,
  "confidence_before": 0.7,
  "evidence_ref": "assessment-2026-08-03-001",
  "next_review": "2026-08-04",
  "notes": "Failed to distinguish two similar cases"
}
```

## assessments.jsonl

```json
{
  "assessment_id": "assessment-2026-08-03-001",
  "subject": "example subject",
  "kind": "diagnostic|exit|review|weekly|stage|transfer",
  "created_at": "2026-08-03T19:40:00+08:00",
  "items": [
    {
      "concept_id": "concept-01",
      "prompt_type": "recall|explain|apply|transfer|produce",
      "result": "correct|partial|incorrect|not_attempted",
      "score": 0.75,
      "confidence_before": 0.6,
      "hint_level": 1,
      "feedback": "Identify the missing prerequisite",
      "artifact_id": null
    }
  ],
  "summary": "Partial application; revisit the prerequisite",
  "evidence_quality": "observed|self_reported|estimated"
}
```

## coaching_events.jsonl

This append-only log stores meaningful feedback and pacing decisions. It is
not a transcript and must not contain inferred diagnoses or stable labels about
the learner. Do not create an event for every answer; create one when a
milestone, trigger, review adjustment, recovery choice, or plan-alignment
correction changes the next action.

```json
{
  "event_id": "feedback-2026-08-03-001",
  "session_id": "session-2026-08-03-001",
  "subject": "example subject",
  "created_at": "2026-08-03T19:45:00+08:00",
  "kind": "milestone|regulation|review_adjustment|recovery|plan_alignment",
  "trigger": "milestone_evidence|overlong_session|fragile_fast_progress|stalled_progress|plan_drift|explicit_strain|confidence_mismatch|delayed_decay",
  "observations": [
    "Solved a changed example without a cue",
    "Delayed retention has not yet been tested"
  ],
  "learning_interpretation": "Application evidence improved; retention remains open",
  "action": "Keep the next spaced review and add one transfer check",
  "tone": "warm_direct|calm|celebratory|firm",
  "learner_choice": null,
  "evidence_refs": ["assessment-2026-08-03-001"],
  "next_check": "Unaided retrieval on the next available day"
}
```

`observations` must be evidence that could be checked. `learning_interpretation`
is a provisional learning-design interpretation, not a psychological
diagnosis. The checkpoint may point to the latest event for continuity, but a
new session must recheck the current condition before applying its action.

## dashboard.md

This file is derived from the logs. Include the generation date, subject
filters, time totals, evidence trends, due reviews, recurring errors, current
stage, artifact status, feedback or regulation trends, and next actions. Never
use it to overwrite raw events without an explicit reconciliation step.
