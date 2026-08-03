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
  "created_at": "2026-08-03T19:00:00+08:00",
  "updated_at": "2026-08-03T19:00:00+08:00"
}
```

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
  "kind": "file|external_result|procedure|performance|other",
  "workspace": ".",
  "path": ".study/artifacts/goal-slug/starter.ext",
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
session while it exists.

## reviews.jsonl

```json
{
  "review_id": "review-2026-08-03-001",
  "concept_id": "concept-01",
  "subject": "example subject",
  "scheduled_for": "2026-08-03",
  "reviewed_at": "2026-08-03T19:15:00+08:00",
  "result": "fail|hinted|pass|transfer_pass",
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

## dashboard.md

This file is derived from the logs. Include the generation date, subject
filters, time totals, evidence trends, due reviews, recurring errors, current
stage, artifact status, and next actions. Never use it to overwrite raw events
without an explicit reconciliation step.
