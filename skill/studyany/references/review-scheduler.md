# Review Scheduler

Use this simple, transparent scheduler for the MVP. The schedule is a
provisional recommendation based on evidence, not a promise about memory.
Keep the session clock separate from the memory clock: time spent and an
immediate correct repeat do not prove long-term retention. Review dates are
stored as calendar dates in the learner's local timezone.

## Default intervals

After a new item or a failed review, use the first interval. After successful
retrieval, select the row that best matches the evidence:

| Evidence | Next interval | Retention rule |
| --- | ---: | --- |
| Same-session correction or repeated answer | same session for repair, then 1 day | does not advance retention |
| No recall or incorrect core idea | 1 day or next available day | keep the item active; vary the cue |
| Correct only after a strong hint | 1 day | do not count as unaided retrieval |
| Correct with a light cue, no transfer | 3 days | keep application open |
| Unaided correct answer on a similar task | 7 days | first delayed retrieval evidence |
| Unaided correct answer plus changed-example application | 14 days | delayed application evidence |
| Delayed correct retrieval plus transfer | 30 days | candidate for maintenance |
| Stable long-term evidence across contexts | 60 days, then maintenance | review only when due or relevant |

Never schedule a same-session repeat as the only next review for a new or
fragile concept. A same-session attempt may repair an error, but the next
retention review must cross a meaningful interval, normally at least the next
calendar day.

Do not use confidence alone to move an item forward. When confidence and
performance disagree, schedule the item according to performance and add a
calibration prompt.

## Review record

Create one review event for each review attempt. Include:

- `concept_id`;
- `reviewed_at`;
- `scheduled_for`;
- `result`: `fail`, `hinted`, `pass`, or `transfer_pass`;
- `delay_type`: `same_session`, `next_day`, `spaced`, or `maintenance`;
- `interval_stage`: `repair`, `1d`, `3d`, `7d`, `14d`, `30d`, or `60d`;
- `same_session`: whether this was only an immediate correction check;
- `confidence_before` when available;
- `evidence_ref` pointing to a session or assessment;
- `next_review`;
- `notes` about the error or cue used.

Keep old events. The current due date can be derived from the latest event or
stored in the concept state for fast lookup.

## Failure handling

When a review fails:

1. Preserve the failure as evidence; never delete the historical pass.
2. Identify whether the failure is forgetting, misconception, missing
   prerequisite, or an execution error.
3. Give a short corrective activity if the learner can continue.
4. Schedule the next *spaced* attempt for the next available day. A same-day
   corrective attempt may happen sooner, but it does not replace that review.
5. Vary the retrieval cue or example on the next attempt.

Two failures in a row should trigger a prerequisite check. Three failures in a
row should trigger a roadmap adjustment or a smaller objective, not a longer
lecture by default.

## Overdue reviews

Group overdue items by priority:

- critical prerequisite for the current goal;
- recently failed item;
- due maintenance item;
- optional enrichment.

Start with the first two groups. Do not present a large backlog as a moral
failure. Offer a bounded recovery session and spread optional items across
future sessions.

## Scheduling constraints

Respect the learner's available time. A session should normally include no
more than three to five priority reviews before new material, with at least
one delayed or transfer-oriented item when available. If the queue exceeds
capacity, report the backlog and use a recovery plan:

- keep critical prerequisites;
- defer enrichment;
- shorten intervals only for failed or fragile items;
- remove obsolete items when the goal changes.

## Weekly review of the scheduler

Check whether the intervals are producing durable performance. If many items
pass immediately but fail at the next long interval, add an intermediate
review and classify the pattern as delayed decay. If the learner retains items
consistently, avoid unnecessary reviews and allocate time to transfer tasks.
Also check whether the learner is receiving useful corrective feedback without
being interrupted by unnecessary state commentary.

When `scripts/study_analytics.py` is available, use its `due_count`,
`overdue_count`, `delayed_pass_rate`, `transfer_pass_rate`, `failure_streaks`,
`delayed_decay`, and `capacity` projection in the weekly report. Capacity is a
rough planning estimate based on the configured target and preferred session;
it does not claim that a fixed number of items fits every session. Same-session
corrections remain excluded from the delayed metrics. If the projection reports
`insufficient_data`, identify the missing delayed attempt instead of treating
the item as failed.
