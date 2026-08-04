#!/usr/bin/env python3
"""Compute deterministic StudyAny time, pacing, review, and evidence metrics."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python versions without zoneinfo
    ZoneInfo = None  # type: ignore


DIMENSIONS = ("understanding", "retrieval", "application", "transfer", "retention")
PROMPT_DIMENSIONS = {
    "explain": "understanding",
    "recall": "retrieval",
    "apply": "application",
    "produce": "application",
    "transfer": "transfer",
}
RESULT_SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
PASS_RESULTS = {"pass", "transfer_pass"}
FAIL_RESULTS = {"fail"}
VALID_REVIEW_RESULTS = {"fail", "hinted", "pass", "transfer_pass"}
SHORT_DELAY_TYPES = {"same_session", "immediate", "next_day"}
WEEKDAY_NAMES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def _number(value: Any, minimum: Optional[float] = None) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    if minimum is not None and value < minimum:
        return None
    return value


def _read_json(path: Path, reasons: List[str]) -> Dict[str, Any]:
    if not path.exists():
        reasons.append("%s_missing" % path.name)
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        reasons.append("%s_invalid" % path.name)
        return {}
    if not isinstance(value, dict):
        reasons.append("%s_not_object" % path.name)
        return {}
    return value


def _read_optional_json(path: Path, reasons: List[str]) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    value = _read_json(path, reasons)
    return value or None


def _read_jsonl(path: Path, reasons: List[str]) -> List[Dict[str, Any]]:
    if not path.exists():
        reasons.append("%s_missing" % path.name)
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        reasons.append("%s_unreadable" % path.name)
        return []
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            reasons.append("%s_invalid_line_%d" % (path.name, line_number))
            continue
        if not isinstance(value, dict):
            reasons.append("%s_non_object_line_%d" % (path.name, line_number))
            continue
        rows.append(value)
    return rows


def _local_timezone(profile: Dict[str, Any], reasons: List[str]):
    timezone_name = profile.get("timezone")
    if isinstance(timezone_name, str) and timezone_name and ZoneInfo is not None:
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            reasons.append("invalid_timezone")
    elif timezone_name:
        reasons.append("timezone_unavailable")
    return datetime.now().astimezone().tzinfo or timezone.utc


def _parse_datetime(value: Any, timezone_value, reasons: List[str], code: str) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        reasons.append("invalid_%s" % code)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone_value)
        reasons.append("naive_%s" % code)
    return parsed.astimezone(timezone_value)


def _parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value)


def _as_of_date(value: Any, timezone_value) -> date:
    if value is None:
        return datetime.now(timezone_value).date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone_value).date()
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError("as_of must be an ISO date (YYYY-MM-DD)")
    return parsed


def _window(as_of: date, kind: str) -> Tuple[date, date, int]:
    if kind == "week":
        start = as_of - timedelta(days=as_of.weekday())
        end = start + timedelta(days=6)
        return start, end, (as_of - start).days + 1
    if kind == "rolling-7d":
        return as_of - timedelta(days=6), as_of, 7
    raise ValueError("unsupported window: %s" % kind)


def _in_window(value: date, start: date, end: date) -> bool:
    return start <= value <= end


def _session_date(row: Dict[str, Any], timezone_value, reasons: List[str]) -> Optional[date]:
    parsed = _parse_datetime(row.get("ended_at") or row.get("started_at"), timezone_value, reasons, "session_timestamp")
    return parsed.date() if parsed else None


def _valid_target_days(value: Any, reasons: List[str]) -> List[int]:
    if not isinstance(value, list):
        return []
    result: List[int] = []
    for item in value:
        weekday: Optional[int] = None
        if isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 6:
            weekday = item
        elif isinstance(item, str):
            normalized = item.strip().lower()
            weekday = WEEKDAY_NAMES.get(normalized)
        if weekday is None:
            reasons.append("invalid_target_study_day")
        elif weekday not in result:
            result.append(weekday)
    return sorted(result)


def _profile_target(profile: Dict[str, Any], key: str, reasons: List[str]) -> Optional[float]:
    value = _number(profile.get(key), minimum=0.0001)
    if profile.get(key) is not None and value is None:
        reasons.append("invalid_%s" % key)
    return value


def _session_metrics(
    sessions: Sequence[Dict[str, Any]],
    profile: Dict[str, Any],
    timezone_value,
    start: date,
    end: date,
    observation_end: date,
    source_available: bool,
    active_session: Optional[Dict[str, Any]],
    reasons: List[str],
) -> Dict[str, Any]:
    preferred = _profile_target(profile, "preferred_session_minutes", reasons)
    maximum = _profile_target(profile, "maximum_session_minutes", reasons)
    measured: List[Dict[str, Any]] = []
    included_count = 0
    unknown_duration_count = 0
    unknown_timestamp_count = 0
    daily_minutes: Dict[str, float] = defaultdict(float)
    study_days = set()
    total = 0.0
    planned_total = 0.0
    planned_count = 0
    active_total = 0.0
    active_count = 0
    passive_total = 0.0
    passive_count = 0
    overlong: List[Dict[str, Any]] = []
    maximum_exceeded: List[Dict[str, Any]] = []
    active_overlong: List[Dict[str, Any]] = []
    active_maximum_exceeded: List[Dict[str, Any]] = []

    for row in sessions:
        status = row.get("status")
        if status not in ("complete", "interrupted"):
            continue
        session_date = _session_date(row, timezone_value, reasons)
        if session_date is None:
            if row.get("ended_at") is not None or row.get("started_at") is not None:
                unknown_timestamp_count += 1
            continue
        if not _in_window(session_date, start, min(end, observation_end)):
            continue
        included_count += 1
        study_days.add(session_date)
        duration = _number(row.get("duration_min"), minimum=0)
        if duration is None:
            unknown_duration_count += 1
        else:
            total += duration
            daily_minutes[session_date.isoformat()] += duration
            baseline = _number(row.get("planned_minutes"), minimum=0.0001)
            baseline_source = "planned_minutes"
            if baseline is None:
                baseline = preferred or 45.0
                baseline_source = "preferred_session_minutes" if preferred else "default_45_minutes"
            measured_row = {
                "session_id": row.get("session_id"),
                "date": session_date.isoformat(),
                "duration_min": _round(duration, 1),
                "baseline_min": _round(baseline, 1),
                "baseline_source": baseline_source,
                "evidence_refs": row.get("evidence_refs") or [],
            }
            measured.append(measured_row)
            if duration - baseline >= 15:
                overlong.append(dict(measured_row))
            if maximum is not None and duration > maximum:
                maximum_exceeded.append(dict(measured_row, maximum_min=_round(maximum, 1)))

        planned = _number(row.get("planned_minutes"), minimum=0)
        if planned is not None:
            planned_total += planned
            planned_count += 1
        active = _number(row.get("active_minutes"), minimum=0)
        if active is not None:
            active_total += active
            active_count += 1
        passive = _number(row.get("passive_minutes"), minimum=0)
        if passive is not None:
            passive_total += passive
            passive_count += 1

    active_info: Optional[Dict[str, Any]] = None
    if active_session:
        active_started = _parse_datetime(active_session.get("started_at"), timezone_value, reasons, "active_session_timestamp")
        if active_started:
            elapsed = max(0.0, (datetime.now(timezone_value) - active_started).total_seconds() / 60)
            baseline = _number(active_session.get("planned_minutes"), minimum=0.0001)
            baseline_source = "planned_minutes"
            if baseline is None:
                baseline = preferred or 45.0
                baseline_source = "preferred_session_minutes" if preferred else "default_45_minutes"
            active_info = {
                "session_id": active_session.get("session_id"),
                "status": "in_progress",
                "started_at": active_session.get("started_at"),
                "elapsed_min": _round(elapsed, 1),
                "baseline_min": _round(baseline, 1),
                "baseline_source": baseline_source,
                "planned_minutes": _round(_number(active_session.get("planned_minutes"), minimum=0), 1),
            }
            if elapsed - baseline >= 15:
                active_overlong.append(dict(active_info))
            if maximum is not None and elapsed > maximum:
                active_maximum_exceeded.append(dict(active_info, maximum_min=_round(maximum, 1)))

    if unknown_duration_count:
        reasons.append("unknown_duration")
    if unknown_timestamp_count:
        reasons.append("unknown_session_timestamp")
    if included_count == 0:
        reasons.append("no_sessions_in_window")

    if measured:
        measurement_status = "measured"
        actual_minutes: Optional[float] = _round(total, 1)
    elif unknown_duration_count or unknown_timestamp_count or not source_available:
        measurement_status = "unknown"
        actual_minutes = None
    else:
        measurement_status = "no_sessions"
        actual_minutes = 0.0

    return {
        "session_count": included_count,
        "session_count_status": "known" if source_available else "unknown",
        "measured_session_count": len(measured),
        "unknown_duration_count": unknown_duration_count,
        "unknown_timestamp_count": unknown_timestamp_count,
        "study_days": len(study_days),
        "study_dates": sorted(day.isoformat() for day in study_days),
        "measurement_status": measurement_status,
        "actual_minutes": actual_minutes,
        "planned_minutes": _round(planned_total, 1) if planned_count else None,
        "planned_session_count": planned_count,
        "active_minutes": _round(active_total, 1) if active_count else None,
        "passive_minutes": _round(passive_total, 1) if passive_count else None,
        "daily_minutes": {key: _round(value, 1) for key, value in sorted(daily_minutes.items())},
        "overlong_sessions": overlong,
        "maximum_exceeded_sessions": maximum_exceeded,
        "active_session": active_info,
        "active_overlong_sessions": active_overlong,
        "active_maximum_exceeded_sessions": active_maximum_exceeded,
    }


def _pace_metrics(
    profile: Dict[str, Any],
    time_data: Dict[str, Any],
    week_start: date,
    as_of: date,
    elapsed_days: int,
    reasons: List[str],
) -> Dict[str, Any]:
    target_minutes = _profile_target(profile, "target_minutes_per_week", reasons)
    target_sessions = _profile_target(profile, "target_sessions_per_week", reasons)
    target_days = _valid_target_days(profile.get("target_study_days"), reasons)
    actual_minutes = _number(time_data.get("actual_minutes"), minimum=0)
    actual_sessions = _number(time_data.get("session_count"), minimum=0) or 0.0
    target_configured = target_minutes is not None or target_sessions is not None or bool(target_days)
    pacing: Dict[str, Any] = {
        "target_status": "configured" if target_configured else "not_configured",
        "target_minutes_per_week": _round(target_minutes, 1),
        "target_sessions_per_week": _round(target_sessions, 1),
        "target_study_days": target_days,
        "elapsed_days": elapsed_days,
        "actual_minutes": _round(actual_minutes, 1),
        "actual_sessions": int(actual_sessions),
        "minute_status": "not_configured",
        "session_status": "not_configured",
        "day_status": "not_configured",
        "alerts_ready": elapsed_days >= 3,
    }
    if not target_configured:
        reasons.append("no_target")
        return pacing

    if target_minutes is not None:
        if actual_minutes is None:
            pacing["minute_status"] = "insufficient_data"
        else:
            expected = target_minutes * elapsed_days / 7
            pace_ratio = actual_minutes / expected if expected else None
            projected = actual_minutes / elapsed_days * 7 if elapsed_days else None
            shortfall = max(0.0, target_minutes - actual_minutes)
            surplus = max(0.0, actual_minutes - target_minutes)
            pacing.update(
                {
                    "expected_minutes_by_as_of": _round(expected, 1),
                    "pace_ratio": _round(pace_ratio),
                    "projected_week_minutes": _round(projected, 1),
                    "shortfall_minutes": _round(shortfall, 1),
                    "surplus_minutes": _round(surplus, 1),
                }
            )
            if elapsed_days >= 3:
                if actual_minutes < expected * 0.75:
                    pacing["minute_status"] = "behind_pace"
                elif actual_minutes > expected * 1.25:
                    pacing["minute_status"] = "above_plan"
                else:
                    pacing["minute_status"] = "on_track"
            else:
                pacing["minute_status"] = "early_week"

    if target_sessions is not None:
        if time_data.get("session_count_status") == "unknown":
            pacing["session_status"] = "insufficient_data"
        else:
            expected_sessions = target_sessions * elapsed_days / 7
            ratio = actual_sessions / expected_sessions if expected_sessions else None
            pacing.update(
                {
                    "expected_sessions_by_as_of": _round(expected_sessions),
                    "session_pace_ratio": _round(ratio),
                }
            )
            if elapsed_days >= 3:
                pacing["session_status"] = "behind_pace" if actual_sessions < expected_sessions * 0.75 else "on_track"
            else:
                pacing["session_status"] = "early_week"

    if target_days:
        if time_data.get("session_count_status") == "unknown":
            pacing["day_status"] = "insufficient_data"
        else:
            elapsed_dates = {week_start + timedelta(days=index) for index in range(elapsed_days)}
            due_days = {week_day for week_day in target_days if week_start + timedelta(days=week_day) in elapsed_dates}
            observed_days = {date.fromisoformat(value).weekday() for value in time_data.get("study_dates", [])}
            missed_days = sorted(day for day in due_days if day not in observed_days)
            pacing.update(
                {
                    "target_days_due": len(due_days),
                    "observed_target_days": len(due_days) - len(missed_days),
                    "missed_target_days": missed_days,
                }
            )
            pacing["day_status"] = "behind_pace" if missed_days and elapsed_days >= 3 else "on_track"

    return pacing


def _latest_by(rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            latest[value] = row
    return latest


def _review_metrics(
    profile: Dict[str, Any],
    concepts: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    as_of: date,
    timezone_value,
    start: date,
    end: date,
    reasons: List[str],
) -> Dict[str, Any]:
    latest_concepts = _latest_by(concepts, "concept_id")
    review_groups: Dict[str, List[Tuple[datetime, Dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(reviews):
        concept_id = row.get("concept_id")
        if not isinstance(concept_id, str) or not concept_id:
            reasons.append("review_missing_concept_id")
            continue
        reviewed_at = _parse_datetime(row.get("reviewed_at"), timezone_value, reasons, "reviewed_at")
        if reviewed_at is None:
            # Keep the row for no-date counts only when its scheduled date is usable.
            scheduled = _parse_date(row.get("scheduled_for"))
            if scheduled is None:
                continue
            reviewed_at = datetime.combine(scheduled, datetime.min.time(), tzinfo=timezone_value)
        if reviewed_at.date() > as_of:
            continue
        normalized = dict(row, _source_index=index, _reviewed_at=reviewed_at)
        review_groups[concept_id].append((reviewed_at, normalized))
    for values in review_groups.values():
        values.sort(key=lambda item: (item[0], item[1].get("_source_index", 0)))

    due_items: List[Dict[str, Any]] = []
    concept_ids = set(latest_concepts) | set(review_groups)
    for concept_id in concept_ids:
        concept = latest_concepts.get(concept_id, {})
        next_review = _parse_date(concept.get("next_review"))
        if next_review is None and review_groups.get(concept_id):
            next_review = _parse_date(review_groups[concept_id][-1][1].get("next_review"))
        if next_review is None:
            continue
        if next_review <= as_of:
            due_items.append(
                {
                    "concept_id": concept_id,
                    "next_review": next_review.isoformat(),
                    "overdue": next_review < as_of,
                    "title": concept.get("title"),
                    "priority": "high" if concept.get("mastery", 0) in (0, 1) else "normal",
                }
            )
    due_items.sort(key=lambda item: (item["next_review"], item["concept_id"]))

    window_attempts = []
    delayed_attempts = []
    transfer_pass_count = 0
    per_concept_streaks: Dict[str, int] = {}
    delayed_decay: List[Dict[str, Any]] = []
    for concept_id, values in review_groups.items():
        streak = 0
        prior_short_success: Optional[Dict[str, Any]] = None
        for _, row in values:
            result = row.get("result")
            same_session = _is_true(row.get("same_session")) or row.get("delay_type") == "same_session"
            review_date = row["_reviewed_at"].date()
            if _in_window(review_date, start, min(end, as_of)):
                window_attempts.append(row)
            if same_session:
                continue
            if result not in VALID_REVIEW_RESULTS:
                reasons.append("invalid_review_result")
                continue
            delayed_attempts.append(row)
            if result == "transfer_pass":
                transfer_pass_count += 1
            if result == "fail":
                streak += 1
                if prior_short_success is not None:
                    delayed_decay.append(
                        {
                            "concept_id": concept_id,
                            "prior_review_id": prior_short_success.get("review_id"),
                            "failed_review_id": row.get("review_id"),
                            "evidence_refs": [
                                value
                                for value in (
                                    prior_short_success.get("evidence_ref"),
                                    row.get("evidence_ref"),
                                )
                                if value
                            ],
                        }
                    )
                prior_short_success = None
            else:
                streak = 0
                delay_type = row.get("delay_type")
                interval = row.get("interval_stage")
                if result in PASS_RESULTS and (delay_type in SHORT_DELAY_TYPES or interval in ("repair", "1d", "3d")):
                    prior_short_success = row
                elif result in PASS_RESULTS:
                    prior_short_success = None
            per_concept_streaks[concept_id] = max(per_concept_streaks.get(concept_id, 0), streak)

    delayed_passes = sum(1 for row in delayed_attempts if row.get("result") in PASS_RESULTS)
    delayed_failures = sum(1 for row in delayed_attempts if row.get("result") in FAIL_RESULTS)
    overdue = [item for item in due_items if item["overdue"]]
    delayed_pass_rate = delayed_passes / len(delayed_attempts) if delayed_attempts else None
    transfer_pass_rate = transfer_pass_count / len(delayed_attempts) if delayed_attempts else None
    target_minutes = _profile_target(profile, "target_minutes_per_week", reasons)
    preferred_session = _profile_target(profile, "preferred_session_minutes", reasons)
    if target_minutes is not None and preferred_session is not None:
        estimated_sessions = target_minutes / preferred_session
        estimated_capacity = {
            "status": "estimated",
            "target_minutes_per_week": _round(target_minutes, 1),
            "preferred_session_minutes": _round(preferred_session, 1),
            "estimated_sessions_per_week": _round(estimated_sessions),
            "priority_reviews_per_week_low": _round(estimated_sessions * 3),
            "priority_reviews_per_week_high": _round(estimated_sessions * 5),
            "basis": "three to five priority reviews per preferred session",
        }
    else:
        estimated_capacity = {
            "status": "not_configured",
            "reason": "set target_minutes_per_week and preferred_session_minutes to estimate review capacity",
        }
    return {
        "due_count": len(due_items),
        "overdue_count": len(overdue),
        "due_items": due_items,
        "oldest_overdue": overdue[0]["next_review"] if overdue else None,
        "attempt_count": len(window_attempts),
        "delayed_attempt_count": len(delayed_attempts),
        "delayed_pass_count": delayed_passes,
        "delayed_failure_count": delayed_failures,
        "delayed_pass_rate": _round(delayed_pass_rate),
        "transfer_pass_count": transfer_pass_count,
        "transfer_pass_rate": _round(transfer_pass_rate),
        "failure_streaks": {key: value for key, value in sorted(per_concept_streaks.items()) if value},
        "delayed_decay": delayed_decay,
        "capacity": estimated_capacity,
        "_all_delayed_reviews": delayed_attempts,
    }


def _item_score(row: Dict[str, Any]) -> Optional[float]:
    result = row.get("result")
    if result == "not_attempted":
        return None
    value = _number(row.get("score"), minimum=0)
    if value is not None:
        return value if value <= 1 else None
    return RESULT_SCORES.get(result)


def _trend(
    samples: Sequence[Dict[str, Any]],
    dimension: str,
    delayed_evidence: bool = False,
    transfer_evidence: bool = False,
) -> Dict[str, Any]:
    ordered = sorted(samples, key=lambda row: (row.get("timestamp", ""), row.get("source_index", 0)))
    if len(ordered) < 2:
        return {
            "status": "insufficient_data",
            "sample_count": len(ordered),
            "missing_evidence": "one more comparable observation after a delay",
            "delta": None,
            "observations": ordered[-6:],
        }
    split_size = min(3, max(1, len(ordered) // 2))
    recent = ordered[-split_size:]
    previous = ordered[-(split_size * 2):-split_size]
    recent_mean = sum(row["score"] for row in recent) / len(recent)
    previous_mean = sum(row["score"] for row in previous) / len(previous)
    delta = recent_mean - previous_mean
    recent_failures = sum(1 for row in recent[-2:] if row.get("result") == "incorrect")
    had_decline = any(row.get("result") == "incorrect" for row in previous) or previous_mean < 0.6
    has_materially_weaker_delayed = bool(samples) and not (delayed_evidence or transfer_evidence)
    status = "consolidating"
    if delta >= 0.15 and had_decline:
        status = "recovering"
    elif recent_mean >= 0.75 and has_materially_weaker_delayed:
        status = "fragile"
    elif len(ordered) >= 3 and abs(delta) < 0.10 and not (delayed_evidence and transfer_evidence):
        status = "stalled"
    elif delta >= 0.15 and recent_failures == 0:
        status = "building"
    elif delayed_evidence and recent_mean >= 0.75:
        status = "consolidating"
    elif abs(delta) < 0.10:
        status = "consolidating" if delayed_evidence else "stalled"
    return {
        "status": status,
        "sample_count": len(ordered),
        "recent_mean": _round(recent_mean),
        "previous_mean": _round(previous_mean),
        "delta": _round(delta),
        "observations": ordered[-6:],
    }


def _learning_curve(
    assessments: Sequence[Dict[str, Any]],
    review_data: Dict[str, Any],
    timezone_value,
    observation_end: date,
    reasons: List[str],
) -> Dict[str, Any]:
    samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_concepts_by_dimension: Dict[str, set] = defaultdict(set)
    for assessment_index, assessment in enumerate(assessments):
        created_at = _parse_datetime(assessment.get("created_at"), timezone_value, reasons, "assessment_timestamp")
        if created_at is None:
            if assessment.get("created_at") is None:
                reasons.append("missing_assessment_timestamp")
            continue
        if created_at.date() > observation_end:
            continue
        timestamp = created_at.isoformat() if created_at else ""
        for item_index, item in enumerate(assessment.get("items") or []):
            if not isinstance(item, dict):
                continue
            dimension = PROMPT_DIMENSIONS.get(item.get("prompt_type"))
            score = _item_score(item)
            if dimension is None or score is None:
                continue
            concept_id = item.get("concept_id")
            sample = {
                "score": _round(score),
                "result": item.get("result"),
                "concept_id": concept_id,
                "assessment_id": assessment.get("assessment_id"),
                "evidence_ref": assessment.get("assessment_id"),
                "timestamp": timestamp,
                "source_index": assessment_index * 1000 + item_index,
            }
            samples[dimension].append(sample)
            if isinstance(concept_id, str):
                all_concepts_by_dimension[dimension].add(concept_id)

    delayed_by_concept = defaultdict(bool)
    transfer_by_concept = defaultdict(bool)
    for row in review_data.get("_all_delayed_reviews", []):
        concept_id = row.get("concept_id")
        if isinstance(concept_id, str):
            delayed_by_concept[concept_id] = True
            if row.get("result") == "transfer_pass":
                transfer_by_concept[concept_id] = True

    result: Dict[str, Any] = {}
    for dimension in ("understanding", "retrieval", "application", "transfer"):
        concept_ids = all_concepts_by_dimension[dimension]
        result[dimension] = _trend(
            samples.get(dimension, []),
            dimension,
            delayed_evidence=any(delayed_by_concept[concept_id] for concept_id in concept_ids),
            transfer_evidence=any(transfer_by_concept[concept_id] for concept_id in concept_ids)
            or dimension == "transfer",
        )

    retention_samples: List[Dict[str, Any]] = []
    for index, row in enumerate(review_data.get("_all_delayed_reviews", [])):
        result_value = row.get("result")
        if result_value not in ("fail", "hinted", "pass", "transfer_pass"):
            continue
        score = {"fail": 0.0, "hinted": 0.5, "pass": 1.0, "transfer_pass": 1.0}[result_value]
        retention_samples.append(
            {
                "score": score,
                "result": result_value,
                "concept_id": row.get("concept_id"),
                "review_id": row.get("review_id"),
                "evidence_ref": row.get("evidence_ref"),
                "timestamp": row.get("_reviewed_at").isoformat(),
                "source_index": index,
            }
        )
    result["retention"] = _trend(
        retention_samples,
        "retention",
        delayed_evidence=bool(retention_samples),
        transfer_evidence=any(row.get("result") == "transfer_pass" for row in review_data.get("_all_delayed_reviews", [])),
    )
    if all(item.get("status") == "insufficient_data" for item in result.values()):
        reasons.append("insufficient_evidence")
    return result


def _alert(code: str, severity: str, message_key: str, observations: Any, evidence_refs: Optional[List[Any]] = None, next_check: Optional[str] = None) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message_key": message_key,
        "observations": observations,
        "evidence_refs": evidence_refs or [],
        "next_check": next_check,
    }


def _recommendation(alerts: Sequence[Dict[str, Any]], curve: Dict[str, Any], pacing: Dict[str, Any], reviews: Dict[str, Any]) -> Dict[str, Any]:
    codes = {alert.get("code") for alert in alerts}
    if reviews.get("due_count", 0) or reviews.get("delayed_decay"):
        return {
            "code": "review_due",
            "reason": "prioritize a due or recently forgotten item before adding new material",
            "evidence_refs": [item.get("concept_id") for item in reviews.get("due_items", [])[:3]],
        }
    if "overload_risk" in codes or "overlong_session" in codes:
        return {
            "code": "take_break",
            "reason": "the measured session load crossed the pacing threshold; protect retrieval quality before continuing",
            "evidence_refs": [alert.get("code") for alert in alerts if alert.get("code") in ("overload_risk", "overlong_session")],
        }
    if pacing.get("minute_status") == "behind_pace" or pacing.get("session_status") == "behind_pace" or pacing.get("day_status") == "behind_pace":
        return {
            "code": "schedule_minimum_session",
            "reason": "the configured weekly pace is behind; schedule one small evidence-bearing session",
            "evidence_refs": [],
        }
    if any(value.get("status") in ("fragile", "stalled", "insufficient_data") for value in curve.values()):
        return {
            "code": "collect_evidence",
            "reason": "the next step should produce independent, delayed, or changed-context evidence",
            "evidence_refs": [],
        }
    return {"code": "none", "reason": "no computed adjustment is required", "evidence_refs": []}


def _quality_status(reasons: Sequence[str], time_data: Dict[str, Any], reviews: Dict[str, Any], curve: Dict[str, Any]) -> str:
    structural = any(
        "_missing" in reason
        or "_invalid" in reason
        or "_unreadable" in reason
        or reason.startswith("invalid_")
        for reason in reasons
    )
    if structural:
        return "partial"
    has_evidence = bool(reviews.get("delayed_attempt_count")) or any(
        value.get("sample_count", 0) for value in curve.values()
    )
    if time_data.get("measured_session_count", 0) == 0 and not has_evidence:
        return "insufficient_data"
    return "complete"


def analyze(study_root: Path, as_of: Any = None, window: str = "week") -> Dict[str, Any]:
    """Return a deterministic analytics projection for one study root."""
    study_root = Path(study_root)
    reasons: List[str] = []
    profile = _read_json(study_root / "profile.json", reasons)
    timezone_value = _local_timezone(profile, reasons)
    as_of_value = _as_of_date(as_of, timezone_value)
    window_start, window_end, elapsed_days = _window(as_of_value, window)
    sessions = _read_jsonl(study_root / "sessions.jsonl", reasons)
    active_session = None if as_of is not None else _read_optional_json(study_root / "active-session.json", reasons)
    concepts = _read_jsonl(study_root / "concepts.jsonl", reasons)
    reviews = _read_jsonl(study_root / "reviews.jsonl", reasons)
    assessments = _read_jsonl(study_root / "assessments.jsonl", reasons)

    time_data = _session_metrics(
        sessions,
        profile,
        timezone_value,
        window_start,
        window_end,
        as_of_value,
        (study_root / "sessions.jsonl").exists(),
        active_session,
        reasons,
    )
    pacing = _pace_metrics(
        profile,
        time_data,
        window_start,
        as_of_value,
        elapsed_days,
        reasons,
    )
    review_data = _review_metrics(
        profile,
        concepts,
        reviews,
        as_of_value,
        timezone_value,
        window_start,
        window_end,
        reasons,
    )
    curve = _learning_curve(assessments, review_data, timezone_value, as_of_value, reasons)

    alerts: List[Dict[str, Any]] = []
    overlong_observations = time_data["overlong_sessions"] + time_data["active_overlong_sessions"]
    maximum_observations = time_data["maximum_exceeded_sessions"] + time_data["active_maximum_exceeded_sessions"]
    if overlong_observations:
        alerts.append(
            _alert(
                "overlong_session",
                "warn",
                "session_elapsed_over_baseline",
                overlong_observations,
                [row.get("session_id") for row in overlong_observations if row.get("session_id")],
                "next major work block or session closeout",
            )
        )
    if maximum_observations:
        alerts.append(
            _alert(
                "maximum_exceeded",
                "warn",
                "session_elapsed_over_configured_maximum",
                maximum_observations,
                [row.get("session_id") for row in maximum_observations if row.get("session_id")],
                "next session start",
            )
        )
    if pacing.get("minute_status") == "behind_pace":
        alerts.append(_alert("behind_pace", "info", "weekly_minutes_behind_configured_target", pacing, [], "next available study day"))
    elif pacing.get("minute_status") == "above_plan":
        alerts.append(_alert("above_plan", "info", "weekly_minutes_above_configured_target", pacing, [], "next weekly review"))
    if pacing.get("session_status") == "behind_pace" or pacing.get("day_status") == "behind_pace":
        alerts.append(_alert("frequency_gap", "info", "study_frequency_behind_configured_target", pacing, [], "next available study day"))
    if review_data.get("overdue_count"):
        alerts.append(
            _alert(
                "review_backlog",
                "warn",
                "overdue_reviews_exist",
                {"overdue_count": review_data["overdue_count"], "oldest_overdue": review_data["oldest_overdue"]},
                [item.get("concept_id") for item in review_data.get("due_items", []) if item.get("overdue")][:5],
                "next study interaction",
            )
        )
    if review_data.get("delayed_decay"):
        alerts.append(
            _alert(
                "delayed_decay",
                "warn",
                "delayed_review_failed_after_short_delay_success",
                review_data["delayed_decay"],
                [item.get("failed_review_id") for item in review_data["delayed_decay"] if item.get("failed_review_id")],
                "next available review day",
            )
        )
    fragile_items = []
    stalled_items = []
    for dimension, value in curve.items():
        item = {"dimension": dimension, "status": value.get("status"), "delta": value.get("delta")}
        if value.get("status") == "fragile":
            fragile_items.append(item)
        elif value.get("status") == "stalled":
            stalled_items.append(item)
    if fragile_items:
        alerts.append(_alert("fragile_progress", "info", "evidence_needs_delayed_or_changed_context", fragile_items, [], "next independent or delayed check"))
    if stalled_items:
        alerts.append(_alert("stalled_progress", "info", "comparable_evidence_not_improving", stalled_items, [], "next smaller prerequisite or changed check"))

    if len(overlong_observations) >= 2 or (
        pacing.get("minute_status") == "above_plan" and (fragile_items or stalled_items or review_data.get("delayed_decay"))
    ):
        alerts.append(
            _alert(
                "overload_risk",
                "warn",
                "repeated_high_load_with_weak_or_repeating_evidence",
                {
                    "overlong_session_count": len(overlong_observations),
                    "fragile_or_stalled": fragile_items + stalled_items,
                },
                [],
                "before adding another major work block",
            )
        )

    # Avoid leaking datetime objects or helper-only fields into JSON output.
    public_reviews = dict(review_data)
    public_reviews.pop("_all_delayed_reviews", None)
    data_quality = {
        "status": _quality_status(reasons, time_data, public_reviews, curve),
        "reasons": sorted(set(reasons)),
    }
    result = {
        "version": 1,
        "as_of": as_of_value.isoformat(),
        "window": {
            "kind": window,
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "elapsed_days": elapsed_days,
        },
        "data_quality": data_quality,
        "time": time_data,
        "pacing": pacing,
        "reviews": public_reviews,
        "learning_curve": curve,
        "alerts": alerts,
        "recommendation": _recommendation(alerts, curve, pacing, public_reviews),
    }
    return result


def _format_number(value: Any) -> str:
    return "unknown" if value is None else str(value)


def print_human(result: Dict[str, Any]) -> None:
    quality = result.get("data_quality") or {}
    window = result.get("window") or {}
    time_data = result.get("time") or {}
    pacing = result.get("pacing") or {}
    reviews = result.get("reviews") or {}
    print("StudyAny analytics")
    print("Window: %s to %s (as of %s)" % (window.get("start"), window.get("end"), result.get("as_of")))
    print("Data quality: %s" % quality.get("status", "unknown"))
    if quality.get("reasons"):
        print("Data notes: %s" % ", ".join(quality["reasons"]))
    print("Study time: %s minutes across %s measured sessions" % (_format_number(time_data.get("actual_minutes")), time_data.get("measured_session_count", 0)))
    print("Study days: %s" % time_data.get("study_days", 0))
    print("Target: %s" % pacing.get("target_status", "not_configured"))
    if pacing.get("minute_status") not in (None, "not_configured"):
        print("Minute pace: %s" % pacing.get("minute_status"))
    print("Reviews: %s due, %s overdue, delayed pass rate %s" % (
        reviews.get("due_count", 0),
        reviews.get("overdue_count", 0),
        _format_number(reviews.get("delayed_pass_rate")),
    ))
    for alert in result.get("alerts", [])[:5]:
        print("Alert [%s]: %s" % (alert.get("severity", "info"), alert.get("code")))
    recommendation = result.get("recommendation") or {}
    print("Next action: %s" % recommendation.get("code", "none"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute StudyAny learning analytics.")
    parser.add_argument("--study-root", type=Path, default=Path(".study"))
    parser.add_argument("--as-of", help="local ISO date used for deterministic analysis")
    parser.add_argument("--window", choices=("week", "rolling-7d"), default="week")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        result = analyze(args.study_root, as_of=args.as_of, window=args.window)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
