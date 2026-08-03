# Review Scheduler

Use this simple, transparent scheduler for the MVP. The schedule is a
provisional recommendation based on evidence, not a promise about memory.
Review dates are stored as calendar dates in the learner's local timezone.

## Default intervals

After a new item or a failed review, use the first interval. After successful
retrieval, select the row that best matches the evidence:

| Evidence | Next interval |
| --- | ---: |
| No recall or incorrect core idea | same day or 1 day |
| Correct only after a strong hint | 1 day |
| Correct with a light cue, no transfer | 3 days |
| Unaided correct answer on a similar task | 7 days |
| Unaided correct answer plus changed-example application | 14 days |
| Delayed correct retrieval plus transfer | 30 days |
| Stable long-term evidence | 60 days, then maintenance |

Do not use confidence alone to move an item forward. When confidence and
performance disagree, schedule the item according to performance and add a
calibration prompt.

## Review record

Create one review event for each review attempt. Include:

- `concept_id`;
- `reviewed_at`;
- `scheduled_for`;
- `result`: `fail`, `hinted`, `pass`, or `transfer_pass`;
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
3. Give a short corrective activity.
4. Schedule the next attempt at 1 day or sooner when the learner can continue.
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
more than three to five priority reviews before new material. If the queue
exceeds capacity, report the backlog and use a recovery plan:

- keep critical prerequisites;
- defer enrichment;
- shorten intervals only for failed or fragile items;
- remove obsolete items when the goal changes.

## Weekly review of the scheduler

Check whether the intervals are producing durable performance. If many items
pass immediately but fail at the next long interval, add an intermediate
review. If the learner retains items consistently, avoid unnecessary reviews
and allocate time to transfer tasks.
