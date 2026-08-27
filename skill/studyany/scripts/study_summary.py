#!/usr/bin/env python3
"""Generate deterministic, table-oriented StudyAny learning summaries."""

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

from study_analytics import analyze as analyze_analytics


DIMENSIONS = ("understanding", "retrieval", "application", "transfer", "retention")
PROMPT_DIMENSIONS = {
    "explain": "understanding",
    "recall": "retrieval",
    "apply": "application",
    "produce": "application",
    "transfer": "transfer",
}
RESULT_SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
REVIEW_SCORES = {"fail": 0.0, "hinted": 0.5, "pass": 1.0, "transfer_pass": 1.0}
VALID_REVIEW_RESULTS = set(REVIEW_SCORES)
PERIOD_KINDS = {"week", "month"}


LABELS = {
    "en": {
        "title": "StudyAny learning summary",
        "period_week": "Weekly summary",
        "period_month": "Monthly summary",
        "period_stage": "Stage summary",
        "period_overall": "Overall progress",
        "as_of": "As of",
        "data_quality": "Data quality",
        "overview": "Overview",
        "progress": "Progress",
        "stage_gates": "Stage exit evidence",
        "evidence": "Learning evidence",
        "efficiency": "Learning efficiency",
        "reviews_risks": "Reviews and risks",
        "next_actions": "Next actions",
        "metric": "Metric",
        "result": "Result",
        "basis": "Basis",
        "scope": "Scope",
        "status": "Status",
        "samples": "Samples",
        "change": "Change",
        "note": "Note",
        "period_learning": "This period",
        "stage_progress": "Stage progress",
        "overall_progress": "Overall progress",
        "goal_evidence": "Goal evidence",
        "sessions": "Sessions",
        "study_time": "Study time",
        "study_days": "Study days",
        "assessments": "Assessments",
        "review_attempts": "Review attempts",
        "required_stages": "required stages",
        "current_stage": "Current stage",
        "stage": "Stage",
        "artifact": "Artifact",
        "delayed_assessment": "Delayed assessment",
        "delayed_review": "Delayed review",
        "stage_exit": "Stage exit",
        "independent_task": "Independent task",
        "actual_planned": "Actual / planned time",
        "active_share": "Active-time share",
        "delayed_pass_rate": "Delayed-review pass rate",
        "transfer_rate": "Transfer pass rate",
        "evidence_trend": "Comparable evidence trend",
        "retrieval": "Retrieval",
        "understanding": "Understanding",
        "application": "Application",
        "transfer": "Transfer",
        "retention": "Retention",
        "retrieval_gate": "Retrieval evidence",
        "application_gate": "Independent application",
        "transfer_gate": "Changed-context evidence",
        "retention_gate": "Delayed retention",
        "no_repeated_failures": "No repeated failures",
        "met": "met",
        "not_ready": "not ready",
        "not_required": "not required",
        "insufficient_data": "insufficient data",
        "complete": "complete",
        "partial": "partial",
        "measured": "measured",
        "in_progress": "in progress",
        "no_sessions": "no sessions",
        "warn": "warning",
        "open": "open",
        "unknown": "unknown",
        "not_configured": "not configured",
        "satisfied": "satisfied",
        "missing": "missing",
        "not_observed": "not observed",
        "no_history": "no study history is available",
        "no_target": "no target is configured",
        "none": "none",
        "yes": "yes",
        "no": "no",
        "minutes": "min",
        "evidence": "evidence",
        "period_reason": "completed local calendar period",
        "stage_reason": "stage exit evidence is satisfied",
        "overall_reason": "requested on demand",
        "unknown_data": "not enough recorded data",
        "next_review": "Next review",
        "overdue": "Overdue reviews",
        "risk": "Risk",
        "action": "Action",
        "data_notes": "Data notes",
        "stage_not_ready": "This stage is not ready for a saved summary yet.",
        "stage_ready": "The stage exit evidence is ready to be recorded.",
        "no_automatic_background": "Automatic checks run when StudyAny is invoked; there is no background notifier.",
        "unknown_goal": "Goal not configured",
        "unknown_subject": "Subject not configured",
        "period_start": "Period",
        "recorded": "recorded",
        "current": "current",
        "completed": "completed",
        "required": "required",
        "missing_evidence": "missing evidence",
        "overdue_review_action": "Review overdue material before adding new content.",
        "collect_evidence_action": "Collect one independent, delayed, or changed-context evidence item.",
        "stage_action": "Complete the smallest missing stage-exit evidence item.",
        "continue_action": "Continue with the next roadmap objective and keep the next spaced review.",
    },
    "zh": {
        "title": "StudyAny 学习总结",
        "period_week": "周总结",
        "period_month": "月总结",
        "period_stage": "阶段总结",
        "period_overall": "总进度总结",
        "as_of": "截至",
        "data_quality": "数据质量",
        "overview": "概览",
        "progress": "学习进度",
        "stage_gates": "阶段出口证据",
        "evidence": "学习证据",
        "efficiency": "学习效率",
        "reviews_risks": "复习与风险",
        "next_actions": "下一步行动",
        "metric": "指标",
        "result": "结果",
        "basis": "依据",
        "scope": "范围",
        "status": "状态",
        "samples": "样本数",
        "change": "变化",
        "note": "说明",
        "period_learning": "本周期学习",
        "stage_progress": "阶段进度",
        "overall_progress": "总进度",
        "goal_evidence": "目标证据",
        "sessions": "学习次数",
        "study_time": "学习时间",
        "study_days": "学习天数",
        "assessments": "评估次数",
        "review_attempts": "复习次数",
        "required_stages": "个必需阶段",
        "current_stage": "当前阶段",
        "stage": "阶段",
        "artifact": "成果物",
        "delayed_assessment": "延迟评估",
        "delayed_review": "延迟复习",
        "stage_exit": "阶段出口",
        "independent_task": "独立任务",
        "actual_planned": "实际 / 计划时间",
        "active_share": "主动学习时间占比",
        "delayed_pass_rate": "延迟复习通过率",
        "transfer_rate": "迁移通过率",
        "evidence_trend": "可比较证据变化",
        "retrieval": "提取",
        "understanding": "理解",
        "application": "应用",
        "transfer": "迁移",
        "retention": "保持",
        "retrieval_gate": "提取证据",
        "application_gate": "独立应用",
        "transfer_gate": "变式或新情境证据",
        "retention_gate": "延迟保持",
        "no_repeated_failures": "没有重复失败",
        "met": "已满足",
        "not_ready": "未满足",
        "not_required": "不要求",
        "insufficient_data": "证据不足",
        "complete": "完整",
        "partial": "部分可用",
        "measured": "已测量",
        "in_progress": "进行中",
        "no_sessions": "没有学习记录",
        "warn": "提醒",
        "open": "待处理",
        "unknown": "未知",
        "not_configured": "未配置",
        "satisfied": "已满足",
        "missing": "缺少",
        "not_observed": "未观察到",
        "no_history": "没有可用的学习记录",
        "no_target": "没有配置学习目标",
        "none": "无",
        "yes": "是",
        "no": "否",
        "minutes": "分钟",
        "evidence": "证据",
        "period_reason": "已结束的本地自然周期",
        "stage_reason": "阶段出口证据已满足",
        "overall_reason": "用户主动请求",
        "unknown_data": "记录中的数据不足",
        "next_review": "下次复习",
        "overdue": "逾期复习",
        "risk": "风险",
        "action": "行动",
        "data_notes": "数据说明",
        "stage_not_ready": "当前阶段还没有达到可保存阶段总结的证据门槛。",
        "stage_ready": "当前阶段的出口证据已经达到保存条件。",
        "no_automatic_background": "自动检查只在 StudyAny 被调用时运行，不提供后台通知。",
        "unknown_goal": "尚未配置学习目标",
        "unknown_subject": "尚未配置学习主题",
        "period_start": "周期",
        "recorded": "已记录",
        "current": "当前",
        "completed": "已完成",
        "required": "必需",
        "missing_evidence": "缺少证据",
        "overdue_review_action": "先复习逾期内容，再加入新内容。",
        "collect_evidence_action": "补充一条独立、延迟或变式情境证据。",
        "stage_action": "先完成阶段出口中最小的缺失证据项。",
        "continue_action": "继续下一个路线目标，并保留下一次间隔复习。",
    },
}


class SummaryError(Exception):
    """An expected summary-generation error."""


def _language(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower().startswith("zh"):
        return "zh"
    return "en"


def _label(language: str, key: str) -> str:
    return LABELS[language].get(key, LABELS["en"].get(key, key))


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def _number(value: Any, minimum: Optional[float] = None) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if minimum is not None and number < minimum:
        return None
    return number


def _read_json(path: Path, reasons: List[str], optional: bool = False) -> Dict[str, Any]:
    if not path.exists():
        if not optional:
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


def _read_jsonl(path: Path, reasons: List[str], optional: bool = False) -> List[Dict[str, Any]]:
    if not path.exists():
        if not optional:
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


def _timezone(profile: Dict[str, Any], reasons: List[str]):
    name = profile.get("timezone")
    if isinstance(name, str) and name and ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            reasons.append("invalid_timezone")
    elif name:
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


def _as_of(value: Any, timezone_value) -> date:
    if value is None:
        return datetime.now(timezone_value).date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone_value).date()
    parsed = _parse_date(value)
    if parsed is None:
        raise SummaryError("as_of must be an ISO date (YYYY-MM-DD)")
    return parsed


def _record_date(
    row: Dict[str, Any],
    fields: Sequence[str],
    timezone_value,
    reasons: List[str],
    code: str,
) -> Optional[date]:
    found = False
    for field in fields:
        if row.get(field) is None:
            continue
        found = True
        parsed = _parse_datetime(row.get(field), timezone_value, reasons, code)
        if parsed is not None:
            return parsed.date()
    if found:
        return None
    return None


def _in_scope(value: Optional[date], start: Optional[date], end: date) -> bool:
    if value is None or value > end:
        return False
    return start is None or value >= start


def _latest_by(rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            latest[value] = row
    return latest


def _period(as_of_value: date, kind: str) -> Tuple[Optional[date], date, str]:
    if kind == "week":
        current_start = as_of_value - timedelta(days=as_of_value.weekday())
        start = current_start - timedelta(days=7)
        end = current_start - timedelta(days=1)
        return start, end, "%s..%s" % (start.isoformat(), end.isoformat())
    if kind == "month":
        current_start = as_of_value.replace(day=1)
        end = current_start - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, "%s..%s" % (start.isoformat(), end.isoformat())
    if kind == "overall":
        return None, as_of_value, "overall:%s" % as_of_value.isoformat()
    raise SummaryError("unsupported summary kind: %s" % kind)


def _score(row: Dict[str, Any]) -> Optional[float]:
    if row.get("result") == "not_attempted":
        return None
    value = _number(row.get("score"), minimum=0)
    if value is not None:
        return value if value <= 1 else None
    return RESULT_SCORES.get(row.get("result"))


def _review_score(result: Any) -> Optional[float]:
    return REVIEW_SCORES.get(result)


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value)


def _is_transfer(row: Dict[str, Any]) -> bool:
    return (
        _is_true(row.get("is_transfer"))
        or _is_true(row.get("transfer"))
        or row.get("prompt_type") == "transfer"
        or row.get("kind") == "transfer"
        or row.get("result") == "transfer_pass"
    )


def _independent(item: Dict[str, Any], assessment: Dict[str, Any]) -> Optional[bool]:
    explicit = item.get("independent")
    if isinstance(explicit, bool):
        return explicit
    hint_level = _number(item.get("hint_level"), minimum=0)
    if hint_level is not None:
        return hint_level == 0
    if assessment.get("kind") in ("exit", "stage", "transfer"):
        return True
    return None


def _assessment_samples(
    assessments: Sequence[Dict[str, Any]],
    timezone_value,
    start: Optional[date],
    end: date,
    reasons: List[str],
    concept_ids: Optional[set] = None,
) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for assessment_index, assessment in enumerate(assessments):
        observed = _record_date(assessment, ("created_at",), timezone_value, reasons, "assessment_timestamp")
        if not _in_scope(observed, start, end):
            continue
        items = assessment.get("items")
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            concept_id = item.get("concept_id")
            if concept_ids is not None and concept_id not in concept_ids:
                continue
            prompt_type = item.get("prompt_type")
            dimension = PROMPT_DIMENSIONS.get(prompt_type)
            score = _score(item)
            if dimension is None or score is None:
                continue
            samples.append(
                {
                    "score": _round(score),
                    "result": item.get("result"),
                    "concept_id": concept_id,
                    "prompt_type": prompt_type,
                    "dimension": dimension,
                    "assessment_id": assessment.get("assessment_id"),
                    "assessment_kind": assessment.get("kind"),
                    "evidence_ref": assessment.get("assessment_id"),
                    "timestamp": observed.isoformat() if observed else None,
                    "source_index": assessment_index * 1000 + item_index,
                    "independent": _independent(item, assessment),
                }
            )
    return samples


def _review_samples(
    reviews: Sequence[Dict[str, Any]],
    timezone_value,
    start: Optional[date],
    end: date,
    reasons: List[str],
    concept_ids: Optional[set] = None,
) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for review_index, row in enumerate(reviews):
        concept_id = row.get("concept_id")
        if concept_ids is not None and concept_id not in concept_ids:
            continue
        observed = _record_date(row, ("reviewed_at",), timezone_value, reasons, "review_timestamp")
        if observed is None:
            observed = _parse_date(row.get("scheduled_for"))
        if not _in_scope(observed, start, end):
            continue
        result = row.get("result")
        score = _review_score(result)
        if score is None:
            if result is not None:
                reasons.append("invalid_review_result")
            continue
        same_session = _is_true(row.get("same_session")) or row.get("delay_type") == "same_session"
        samples.append(
            {
                "score": _round(score),
                "result": result,
                "concept_id": concept_id,
                "review_id": row.get("review_id"),
                "evidence_ref": row.get("evidence_ref"),
                "timestamp": observed.isoformat() if observed else None,
                "source_index": review_index,
                "same_session": same_session,
                "delayed": not same_session,
                "is_transfer": _is_transfer(row),
                "delay_type": row.get("delay_type"),
                "interval_stage": row.get("interval_stage"),
            }
        )
    return samples


def _time_metrics(
    sessions: Sequence[Dict[str, Any]],
    timezone_value,
    start: Optional[date],
    end: date,
    reasons: List[str],
    stage_id: Optional[str] = None,
    stage_concept_ids: Optional[set] = None,
    stage_assessment_ids: Optional[set] = None,
) -> Dict[str, Any]:
    included = 0
    unknown_duration = 0
    unknown_timestamp = 0
    actual = 0.0
    planned = 0.0
    active = 0.0
    passive = 0.0
    measured_count = 0
    planned_count = 0
    active_count = 0
    passive_count = 0
    study_dates = set()
    for row in sessions:
        if row.get("status") not in ("complete", "interrupted"):
            continue
        if stage_id is not None and not _session_matches_stage(row, stage_id, stage_concept_ids or set(), stage_assessment_ids or set()):
            continue
        observed = _record_date(row, ("ended_at", "started_at"), timezone_value, reasons, "session_timestamp")
        if observed is None:
            if row.get("ended_at") is not None or row.get("started_at") is not None:
                unknown_timestamp += 1
            continue
        if not _in_scope(observed, start, end):
            continue
        included += 1
        study_dates.add(observed)
        duration = _number(row.get("duration_min"), minimum=0)
        if duration is None:
            unknown_duration += 1
        else:
            actual += duration
            measured_count += 1
        planned_value = _number(row.get("planned_minutes"), minimum=0)
        if planned_value is not None:
            planned += planned_value
            planned_count += 1
        active_value = _number(row.get("active_minutes"), minimum=0)
        if active_value is not None:
            active += active_value
            active_count += 1
        passive_value = _number(row.get("passive_minutes"), minimum=0)
        if passive_value is not None:
            passive += passive_value
            passive_count += 1
    if unknown_duration:
        reasons.append("unknown_duration")
    if unknown_timestamp:
        reasons.append("unknown_session_timestamp")
    if measured_count:
        measurement_status = "measured"
        actual_value: Optional[float] = _round(actual, 1)
    elif included or unknown_timestamp:
        measurement_status = "unknown"
        actual_value = None
    else:
        measurement_status = "no_sessions"
        actual_value = 0.0
    return {
        "session_count": included,
        "measured_session_count": measured_count,
        "unknown_duration_count": unknown_duration,
        "unknown_timestamp_count": unknown_timestamp,
        "study_days": len(study_dates),
        "study_dates": sorted(item.isoformat() for item in study_dates),
        "measurement_status": measurement_status,
        "actual_minutes": actual_value,
        "planned_minutes": _round(planned, 1) if planned_count else None,
        "planned_session_count": planned_count,
        "active_minutes": _round(active, 1) if active_count else None,
        "passive_minutes": _round(passive, 1) if passive_count else None,
    }


def _session_matches_stage(row: Dict[str, Any], stage_id: str, concept_ids: set, assessment_ids: set) -> bool:
    if row.get("stage_id") == stage_id:
        return True
    for field in ("stage_ids", "concept_ids", "objectives"):
        values = row.get(field)
        if isinstance(values, list) and (stage_id in values or concept_ids.intersection(values)):
            return True
    refs = row.get("evidence_refs")
    return isinstance(refs, list) and bool(assessment_ids.intersection(refs))


def _trend(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(samples, key=lambda item: (item.get("timestamp") or "", item.get("source_index", 0)))
    if len(ordered) < 2:
        return {
            "status": "insufficient_data",
            "sample_count": len(ordered),
            "recent_mean": _round(sum(item["score"] for item in ordered) / len(ordered)) if ordered else None,
            "previous_mean": None,
            "delta": None,
            "observations": ordered[-6:],
        }
    split_size = min(3, max(1, len(ordered) // 2))
    recent = ordered[-split_size:]
    previous = ordered[-(split_size * 2) : -split_size]
    recent_mean = sum(item["score"] for item in recent) / len(recent)
    previous_mean = sum(item["score"] for item in previous) / len(previous)
    delta = recent_mean - previous_mean
    had_decline = any(item.get("result") == "incorrect" for item in previous) or previous_mean < 0.6
    if delta >= 0.15 and had_decline:
        status = "recovering"
    elif recent_mean >= 0.75 and not any(item.get("delayed") for item in ordered):
        status = "fragile"
    elif len(ordered) >= 3 and abs(delta) < 0.10:
        status = "stalled"
    elif delta >= 0.15:
        status = "building"
    elif any(item.get("delayed") for item in ordered) and recent_mean >= 0.75:
        status = "consolidating"
    else:
        status = "consolidating"
    return {
        "status": status,
        "sample_count": len(ordered),
        "recent_mean": _round(recent_mean),
        "previous_mean": _round(previous_mean),
        "delta": _round(delta),
        "observations": ordered[-6:],
    }


def _evidence_metrics(
    assessment_samples: Sequence[Dict[str, Any]],
    review_samples: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    by_dimension: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for sample in assessment_samples:
        by_dimension[sample["dimension"]].append(sample)
    delayed = [item for item in review_samples if item["delayed"]]
    by_dimension["retention"].extend(delayed)
    result: Dict[str, Any] = {}
    for dimension in DIMENSIONS:
        result[dimension] = _trend(by_dimension.get(dimension, []))
    return result


def _review_metrics(review_samples: Sequence[Dict[str, Any]], concepts: Sequence[Dict[str, Any]], as_of_value: date, concept_ids: Optional[set] = None) -> Dict[str, Any]:
    eligible_concepts = [
        row for row in concepts
        if concept_ids is None or row.get("concept_id") in concept_ids
    ]
    due_items: List[Dict[str, Any]] = []
    for concept in eligible_concepts:
        next_review = _parse_date(concept.get("next_review"))
        if next_review is None or next_review > as_of_value:
            continue
        due_items.append(
            {
                "concept_id": concept.get("concept_id"),
                "title": concept.get("title"),
                "next_review": next_review.isoformat(),
                "overdue": next_review < as_of_value,
                "priority": "high" if concept.get("mastery", 0) in (0, 1) else "normal",
            }
        )
    due_items.sort(key=lambda item: (item["next_review"], item.get("concept_id") or ""))
    delayed = [item for item in review_samples if item["delayed"]]
    delayed_pass = sum(1 for item in delayed if item["result"] in ("pass", "transfer_pass"))
    transfer = [item for item in delayed if item["is_transfer"]]
    transfer_pass = sum(1 for item in transfer if item["result"] == "transfer_pass")
    failures_by_concept: Dict[str, int] = defaultdict(int)
    latest_failure_streak: Dict[str, int] = defaultdict(int)
    for item in sorted(review_samples, key=lambda value: (value.get("timestamp") or "", value.get("source_index", 0))):
        concept_id = item.get("concept_id")
        if item["result"] == "fail":
            latest_failure_streak[concept_id] += 1
            failures_by_concept[concept_id] = max(failures_by_concept[concept_id], latest_failure_streak[concept_id])
        else:
            latest_failure_streak[concept_id] = 0
    return {
        "attempt_count": len(review_samples),
        "delayed_attempt_count": len(delayed),
        "delayed_pass_count": delayed_pass,
        "delayed_failure_count": sum(1 for item in delayed if item["result"] == "fail"),
        "delayed_pass_rate": _round(delayed_pass / len(delayed)) if delayed else None,
        "transfer_attempt_count": len(transfer),
        "transfer_pass_count": transfer_pass,
        "transfer_pass_rate": _round(transfer_pass / len(transfer)) if transfer else None,
        "due_count": len(due_items),
        "overdue_count": sum(1 for item in due_items if item["overdue"]),
        "due_items": due_items,
        "oldest_overdue": next((item["next_review"] for item in due_items if item["overdue"]), None),
        "failure_streaks": {
            str(key): value for key, value in sorted(failures_by_concept.items()) if value
        },
    }


def _stage_text(stage: Dict[str, Any]) -> str:
    criteria = stage.get("exit_criteria")
    if not isinstance(criteria, list):
        criteria = []
    return " ".join(str(item) for item in criteria).lower()


def _requirement_spec(stage: Dict[str, Any], dimension: str) -> Dict[str, Any]:
    configured = stage.get("exit_requirements")
    if not isinstance(configured, dict):
        configured = {}
    explicit = configured.get(dimension)
    text = _stage_text(stage)
    default_required = dimension in ("retrieval", "application")
    if dimension == "transfer":
        default_required = any(token in text for token in ("transfer", "changed", "new context", "迁移", "变式", "新情境"))
    if dimension == "retention":
        default_required = any(token in text for token in ("retention", "delayed", "interval", "after a week", "保持", "延迟", "间隔"))
    if isinstance(explicit, bool):
        return {
            "required": explicit,
            "min_score": 0.75,
            "per_concept": dimension in ("retrieval", "application"),
            "independent": dimension == "application",
        }
    if not isinstance(explicit, dict):
        return {
            "required": default_required,
            "min_score": 0.75,
            "per_concept": dimension in ("retrieval", "application"),
            "independent": dimension == "application",
        }
    min_score = _number(explicit.get("min_score"), minimum=0)
    if min_score is None or min_score > 1:
        min_score = 0.75
    return {
        "required": _is_true(explicit.get("required", default_required)),
        "min_score": min_score,
        "per_concept": _is_true(explicit.get("per_concept", dimension in ("retrieval", "application"))),
        "minimum_samples": int(_number(explicit.get("minimum_samples"), minimum=1) or 0),
        "independent": _is_true(explicit.get("independent", dimension == "application")),
    }


def _stage_candidates(
    dimension: str,
    assessment_samples: Sequence[Dict[str, Any]],
    review_samples: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if dimension == "retrieval":
        return [item for item in assessment_samples if item["dimension"] == "retrieval" and item.get("assessment_kind") != "diagnostic"] + [
            dict(item, dimension="retrieval")
            for item in review_samples
            if item["delayed"] and item["result"] in VALID_REVIEW_RESULTS
        ]
    if dimension == "application":
        return [item for item in assessment_samples if item["dimension"] == "application" and item.get("assessment_kind") != "diagnostic"]
    if dimension == "transfer":
        return [item for item in assessment_samples if item["dimension"] == "transfer" and item.get("assessment_kind") != "diagnostic"] + [
            dict(item, dimension="transfer") for item in review_samples if item["is_transfer"]
        ]
    return [dict(item, dimension="retention") for item in review_samples if item["delayed"]]


def _evaluate_stage(
    stage: Dict[str, Any],
    assessments: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    concepts: Sequence[Dict[str, Any]],
    timezone_value,
    start: Optional[date],
    end: date,
    reasons: List[str],
) -> Dict[str, Any]:
    stage_id = stage.get("id")
    concept_ids = {
        value for value in (stage.get("concept_ids") or []) if isinstance(value, str) and value
    }
    assessment_samples = _assessment_samples(assessments, timezone_value, start, end, reasons, concept_ids)
    review_samples = _review_samples(reviews, timezone_value, start, end, reasons, concept_ids)
    gates: List[Dict[str, Any]] = []
    for dimension in ("retrieval", "application", "transfer", "retention"):
        spec = _requirement_spec(stage, dimension)
        candidates = _stage_candidates(dimension, assessment_samples, review_samples)
        if not spec["required"]:
            gates.append(
                {
                    "kind": dimension,
                    "status": "not_required",
                    "required": False,
                    "min_score": spec["min_score"],
                    "sample_count": len(candidates),
                    "missing_concepts": [],
                    "evidence_refs": [],
                    "note": "gate not configured as required",
                }
            )
            continue
        passing = [
            item for item in candidates
            if item.get("score") is not None
            and item["score"] >= spec["min_score"]
            and (not spec.get("independent") or item.get("independent") is True)
        ]
        passing_concepts = {item.get("concept_id") for item in passing}
        missing_concepts = sorted(concept_ids - passing_concepts) if spec.get("per_concept") else []
        minimum_samples = spec.get("minimum_samples") or (len(concept_ids) if spec.get("per_concept") else 1)
        enough_samples = len(passing) >= minimum_samples
        status = "met" if enough_samples and not missing_concepts else "not_ready"
        if not candidates:
            status = "insufficient_data"
        evidence_refs = [
            item.get("evidence_ref") or item.get("assessment_id") or item.get("review_id")
            for item in passing
            if item.get("evidence_ref") or item.get("assessment_id") or item.get("review_id")
        ]
        note = None
        if spec.get("independent") and candidates and not passing:
            note = "passing application evidence must be independent"
        elif missing_concepts:
            note = "one passing evidence item is still needed for each missing concept"
        elif not enough_samples:
            note = "more passing evidence is needed"
        gates.append(
            {
                "kind": dimension,
                "status": status,
                "required": True,
                "min_score": spec["min_score"],
                "per_concept": spec.get("per_concept", False),
                "sample_count": len(candidates),
                "passing_sample_count": len(passing),
                "missing_concepts": missing_concepts,
                "evidence_refs": sorted(set(evidence_refs)),
                "note": note,
            }
        )
    configured = stage.get("exit_requirements")
    if isinstance(configured, dict) and _is_true(configured.get("no_repeated_failures")):
        relevant_reviews = [item for item in review_samples if item["delayed"]]
        streaks: Dict[str, int] = defaultdict(int)
        maximum = 0
        for item in sorted(relevant_reviews, key=lambda value: (value.get("timestamp") or "", value.get("source_index", 0))):
            concept_id = item.get("concept_id")
            if item["result"] == "fail":
                streaks[concept_id] += 1
                maximum = max(maximum, streaks[concept_id])
            else:
                streaks[concept_id] = 0
        status = "met" if relevant_reviews and maximum < 2 else "insufficient_data" if not relevant_reviews else "not_ready"
        gates.append(
            {
                "kind": "no_repeated_failures",
                "status": status,
                "required": True,
                "sample_count": len(relevant_reviews),
                "passing_sample_count": 1 if status == "met" else 0,
                "missing_concepts": [],
                "evidence_refs": [],
                "note": "maximum consecutive delayed failures: %d" % maximum,
            }
        )
    required_gates = [gate for gate in gates if gate["required"]]
    eligible = bool(required_gates) and all(gate["status"] == "met" for gate in required_gates)
    if not required_gates:
        eligible = False
        reasons.append("stage_no_required_exit_gates")
    first_missing = next(
        (gate for gate in required_gates if gate["status"] != "met"),
        None,
    )
    return {
        "stage_id": stage_id,
        "title": stage.get("title"),
        "status": stage.get("status"),
        "concept_ids": sorted(concept_ids),
        "exit_criteria": stage.get("exit_criteria") if isinstance(stage.get("exit_criteria"), list) else [],
        "gates": gates,
        "eligible": eligible,
        "first_missing": first_missing.get("kind") if first_missing else None,
        "evidence_refs": sorted(
            {
                ref
                for gate in gates
                for ref in gate.get("evidence_refs", [])
                if ref
            }
        ),
    }


def _stage_lookup(roadmap: Dict[str, Any], stage_id: Optional[str]) -> Optional[Dict[str, Any]]:
    stages = roadmap.get("stages")
    if not isinstance(stages, list):
        return None
    requested = stage_id or roadmap.get("current_stage_id")
    if isinstance(requested, str):
        for stage in stages:
            if isinstance(stage, dict) and stage.get("id") == requested:
                return stage
    for stage in stages:
        if isinstance(stage, dict) and stage.get("status") == "current":
            return stage
    return None


def _stage_projections(
    roadmap: Dict[str, Any],
    assessments: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    concepts: Sequence[Dict[str, Any]],
    timezone_value,
    end: date,
    reasons: List[str],
) -> Dict[str, Any]:
    stages = roadmap.get("stages") if isinstance(roadmap.get("stages"), list) else []
    rows: List[Dict[str, Any]] = []
    valid_stages: List[Dict[str, Any]] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        valid_stages.append(stage)
        rows.append(_evaluate_stage(stage, assessments, reviews, concepts, timezone_value, None, end, reasons))
    required = [row for row, stage in zip(rows, valid_stages) if stage.get("status") != "optional"]
    completed = [row for row in required if row["eligible"]]
    current = _stage_lookup(roadmap, None)
    current_row = next((row for row in rows if row.get("stage_id") == (current or {}).get("id")), None)
    return {
        "required_stage_count": len(required),
        "completed_stage_count": len(completed),
        "completed_stage_ids": [row.get("stage_id") for row in completed],
        "current_stage": {
            "id": (current or {}).get("id"),
            "title": (current or {}).get("title"),
            "status": (current or {}).get("status"),
            "eligible": current_row.get("eligible") if current_row else False,
        },
        "stages": rows,
    }


def _goal_evidence(
    goals: Dict[str, Any],
    artifacts: Sequence[Dict[str, Any]],
    assessment_samples: Sequence[Dict[str, Any]],
    review_samples: Sequence[Dict[str, Any]],
    stage_projection: Dict[str, Any],
) -> Dict[str, Any]:
    requirements = goals.get("success_evidence")
    if not isinstance(requirements, list) or not requirements:
        return {"status": "not_configured", "requirements": []}
    results: List[Dict[str, Any]] = []
    for requirement in requirements:
        name = str(requirement)
        normalized = name.lower()
        refs: List[Any] = []
        satisfied = False
        if normalized == "artifact":
            for row in artifacts:
                if row.get("status") in ("submitted", "reviewed"):
                    satisfied = True
                    if row.get("artifact_id"):
                        refs.append(row.get("artifact_id"))
        elif normalized in ("delayed_assessment", "delayed_review", "retention"):
            for row in review_samples:
                if row.get("delayed") and row.get("result") in ("pass", "transfer_pass"):
                    satisfied = True
                    if row.get("review_id"):
                        refs.append(row.get("review_id"))
        elif normalized in ("transfer", "transfer_assessment"):
            for row in assessment_samples:
                if row.get("dimension") == "transfer" and row.get("score", 0) >= 0.75:
                    satisfied = True
                    if row.get("assessment_id"):
                        refs.append(row.get("assessment_id"))
            for row in review_samples:
                if row.get("is_transfer") and row.get("result") == "transfer_pass":
                    satisfied = True
                    if row.get("review_id"):
                        refs.append(row.get("review_id"))
        elif normalized in ("assessment", "independent_task", "application"):
            satisfied = any(
                row.get("dimension") == "application"
                and row.get("assessment_kind") != "diagnostic"
                and row.get("score", 0) >= 0.75
                and row.get("independent") is True
                for row in assessment_samples
            )
            refs = [
                row.get("assessment_id")
                for row in assessment_samples
                if row.get("dimension") == "application"
                and row.get("assessment_kind") != "diagnostic"
                and row.get("independent") is True
            ]
        elif normalized in ("stage", "stage_exit"):
            required_stage_count = stage_projection.get("required_stage_count", 0)
            completed_stage_count = stage_projection.get("completed_stage_count", 0)
            satisfied = required_stage_count > 0 and completed_stage_count >= required_stage_count
            refs = stage_projection.get("completed_stage_ids", [])
        else:
            results.append(
                {"requirement": name, "status": "not_configured", "evidence_refs": [], "note": "unsupported success_evidence value"}
            )
            continue
        results.append(
            {
                "requirement": name,
                "status": "satisfied" if satisfied else "missing",
                "evidence_refs": sorted(set(refs)),
            }
        )
    status = "satisfied" if results and all(item["status"] == "satisfied" for item in results) else "missing"
    return {"status": status, "requirements": results}


def _artifacts_as_of(
    artifacts: Sequence[Dict[str, Any]],
    timezone_value,
    end: date,
    reasons: List[str],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for row in artifacts:
        observed = _record_date(row, ("updated_at", "created_at"), timezone_value, reasons, "artifact_timestamp")
        if observed is not None and observed <= end:
            filtered.append(row)
        elif observed is None and row.get("updated_at") is None and row.get("created_at") is None:
            filtered.append(row)
    return filtered


def _progress(
    goals: Dict[str, Any],
    roadmap: Dict[str, Any],
    stage_projection: Dict[str, Any],
    goal_evidence: Dict[str, Any],
    period_time: Dict[str, Any],
    assessment_samples: Sequence[Dict[str, Any]],
    review_samples: Sequence[Dict[str, Any]],
    concepts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    observed_concepts = {
        item.get("concept_id") for item in list(assessment_samples) + list(review_samples) if item.get("concept_id")
    }
    current = stage_projection.get("current_stage") or {}
    return {
        "period": {
            "session_count": period_time.get("session_count", 0),
            "actual_minutes": period_time.get("actual_minutes"),
            "study_days": period_time.get("study_days", 0),
            "assessment_sample_count": len(assessment_samples),
            "review_attempt_count": len(review_samples),
        },
        "stage": {
            "current_stage_id": current.get("id"),
            "current_stage_title": current.get("title"),
            "current_stage_status": current.get("status"),
            "current_stage_eligible": current.get("eligible", False),
        },
        "overall": {
            "required_stage_count": stage_projection.get("required_stage_count", 0),
            "completed_stage_count": stage_projection.get("completed_stage_count", 0),
            "completed_stage_ids": stage_projection.get("completed_stage_ids", []),
            "concept_count": len(concepts),
            "concepts_with_observed_evidence": len(observed_concepts),
            "goal_evidence_status": goal_evidence.get("status"),
            "goal": goals.get("operational_goal") or goals.get("original_goal"),
            "subject": goals.get("subject"),
        },
    }


def _efficiency(time_data: Dict[str, Any], review_data: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    actual = _number(time_data.get("actual_minutes"), minimum=0)
    planned = _number(time_data.get("planned_minutes"), minimum=0)
    active = _number(time_data.get("active_minutes"), minimum=0)
    passive = _number(time_data.get("passive_minutes"), minimum=0)
    if actual is not None and planned is not None and planned > 0:
        actual_planned = {
            "status": "measured",
            "actual_minutes": _round(actual, 1),
            "planned_minutes": _round(planned, 1),
            "ratio": _round(actual / planned),
        }
    else:
        actual_planned = {
            "status": "insufficient_data",
            "actual_minutes": _round(actual, 1),
            "planned_minutes": _round(planned, 1) if planned is not None else None,
            "ratio": None,
        }
    if active is not None and passive is not None and active + passive > 0:
        active_share = {
            "status": "measured",
            "active_minutes": _round(active, 1),
            "passive_minutes": _round(passive, 1),
            "ratio": _round(active / (active + passive)),
        }
    else:
        active_share = {
            "status": "insufficient_data",
            "active_minutes": _round(active, 1) if active is not None else None,
            "passive_minutes": _round(passive, 1) if passive is not None else None,
            "ratio": None,
        }
    return {
        "actual_vs_planned": actual_planned,
        "active_time_share": active_share,
        "delayed_review": {
            "status": "measured" if review_data.get("delayed_attempt_count") else "insufficient_data",
            "attempt_count": review_data.get("delayed_attempt_count", 0),
            "pass_count": review_data.get("delayed_pass_count", 0),
            "pass_rate": review_data.get("delayed_pass_rate"),
        },
        "transfer": {
            "status": "measured" if review_data.get("transfer_attempt_count") else "insufficient_data",
            "attempt_count": review_data.get("transfer_attempt_count", 0),
            "pass_count": review_data.get("transfer_pass_count", 0),
            "pass_rate": review_data.get("transfer_pass_rate"),
        },
        "evidence_trend": {
            dimension: {
                "status": value.get("status"),
                "sample_count": value.get("sample_count", 0),
                "delta": value.get("delta"),
            }
            for dimension, value in evidence.items()
        },
    }


def _data_quality(reasons: Sequence[str], rows: Sequence[Sequence[Dict[str, Any]]]) -> Dict[str, Any]:
    unique_reasons = sorted(set(reasons))
    event_count = sum(len(group) for group in rows)
    structural = any(
        reason.endswith("_missing")
        or "_invalid" in reason
        or "_unreadable" in reason
        or reason.startswith("invalid_")
        for reason in unique_reasons
    )
    if event_count == 0:
        status = "insufficient_data"
        if "no_study_records" not in unique_reasons:
            unique_reasons.append("no_study_records")
            unique_reasons.sort()
    elif structural:
        status = "partial"
    else:
        status = "complete"
    return {"status": status, "reasons": unique_reasons}


def _format_rate(value: Any, language: str = "en") -> str:
    number = _number(value)
    return _label(language, "unknown") if number is None else "%s%%" % _round(number * 100, 1)


def _format_minutes(value: Any, language: str) -> str:
    number = _number(value)
    if number is None:
        return _label(language, "unknown")
    return "%s %s" % (_round(number, 1), _label(language, "minutes"))


def _format_delta(value: Any, language: str = "en") -> str:
    number = _number(value)
    if number is None:
        return _label(language, "unknown")
    rounded = _round(number, 2)
    return ("+" if rounded and rounded > 0 else "") + str(rounded)


def _status_text(value: Any, language: str) -> str:
    return _label(language, str(value)) if value is not None else _label(language, "unknown")


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(_cell(value) for value in headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _risk_and_actions(snapshot: Dict[str, Any], language: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    risks: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    quality = snapshot.get("data_quality") or {}
    if quality.get("status") != "complete":
        risks.append(
            {
                "code": "data_quality",
                "status": quality.get("status"),
                "detail": ", ".join(quality.get("reasons") or []) or _label(language, "unknown_data"),
            }
        )
    reviews = snapshot.get("reviews") or {}
    if reviews.get("overdue_count"):
        risks.append(
            {
                "code": "review_backlog",
                "status": "warn",
                "detail": "%s: %s" % (_label(language, "overdue"), reviews.get("overdue_count")),
            }
        )
        actions.append(
            {
                "priority": "high",
                "action": _label(language, "overdue_review_action"),
                "evidence": reviews.get("oldest_overdue"),
            }
        )
    stage = snapshot.get("stage_projection") or {}
    current = stage.get("current_stage") or {}
    if current.get("id") and not current.get("eligible"):
        risks.append(
            {
                "code": "stage_gate",
                "status": "open",
                "detail": "%s: %s" % (_label(language, "current_stage"), current.get("title") or current.get("id")),
            }
        )
        actions.append(
            {
                "priority": "high",
                "action": _label(language, "stage_action"),
                "evidence": current.get("id"),
            }
        )
    if not actions:
        evidence = snapshot.get("evidence") or {}
        if any(value.get("status") in ("fragile", "stalled", "insufficient_data") for value in evidence.values()):
            actions.append(
                {
                    "priority": "normal",
                    "action": _label(language, "collect_evidence_action"),
                    "evidence": ", ".join(
                        dimension for dimension, value in evidence.items() if value.get("status") in ("fragile", "stalled", "insufficient_data")
                    ),
                }
            )
        else:
            actions.append(
                {
                    "priority": "normal",
                    "action": _label(language, "continue_action"),
                    "evidence": snapshot.get("progress", {}).get("stage", {}).get("current_stage_id"),
                }
            )
    return risks, actions


def _render(snapshot: Dict[str, Any], language: str) -> str:
    kind = snapshot.get("kind")
    title = _label(language, "period_%s" % kind)
    period = snapshot.get("period") or {}
    quality = snapshot.get("data_quality") or {}
    subject = snapshot.get("subject") or _label(language, "unknown_subject")
    lines = [
        "# %s：%s" % (title, subject) if language == "zh" else "# %s: %s" % (title, subject),
        "> %s: %s | %s: %s | %s: `%s`" % (
            _label(language, "period_start"),
            "%s - %s" % (period.get("start") or "unknown", period.get("end") or "unknown"),
            _label(language, "as_of"),
            snapshot.get("as_of") or "unknown",
            _label(language, "data_quality"),
            _status_text(quality.get("status"), language),
        ),
        "",
        "## %s" % _label(language, "overview"),
    ]
    if kind == "stage":
        stage_notice = _label(language, "stage_ready") if snapshot.get("trigger", {}).get("eligible") else _label(language, "stage_not_ready")
        lines.insert(3, "> %s" % stage_notice)
    progress = snapshot.get("progress") or {}
    period_progress = progress.get("period") or {}
    stage_progress = progress.get("stage") or {}
    overall = progress.get("overall") or {}
    goal_evidence = snapshot.get("goal_evidence") or {}
    lines.append(
        _table(
            [_label(language, "metric"), _label(language, "result"), _label(language, "basis")],
            [
                [_label(language, "period_learning"), "%s %s, %s" % (period_progress.get("session_count", 0), _label(language, "sessions"), _format_minutes(period_progress.get("actual_minutes"), language)), "%s %s" % (period_progress.get("study_days", 0), _label(language, "study_days"))],
                [_label(language, "stage_progress"), "%s / %s" % (overall.get("completed_stage_count", 0), overall.get("required_stage_count", 0)), _label(language, "required_stages")],
                [_label(language, "current_stage"), stage_progress.get("current_stage_title") or _label(language, "unknown"), _status_text(stage_progress.get("current_stage_status"), language)],
                [_label(language, "goal_evidence"), _status_text(goal_evidence.get("status"), language), "; ".join(_label(language, item.get("requirement", "")) for item in goal_evidence.get("requirements", [])) or _label(language, "not_configured")],
            ],
        )
    )
    lines.extend(["", "## %s" % _label(language, "progress")])
    lines.append(
        _table(
            [_label(language, "scope"), _label(language, "result"), _label(language, "note")],
            [
                [_label(language, "period_learning"), "%s %s / %s %s" % (period_progress.get("assessment_sample_count", 0), _label(language, "assessments"), period_progress.get("review_attempt_count", 0), _label(language, "review_attempts")), _label(language, "period_reason")],
                [_label(language, "overall_progress"), "%s / %s %s" % (overall.get("completed_stage_count", 0), overall.get("required_stage_count", 0), _label(language, "required_stages")), "%s / %s %s" % (overall.get("concepts_with_observed_evidence", 0), overall.get("concept_count", 0), _label(language, "evidence"))],
                [_label(language, "current_stage"), stage_progress.get("current_stage_id") or _label(language, "unknown"), stage_progress.get("current_stage_title") or _label(language, "unknown")],
            ],
        )
    )
    lines.extend(["", "## %s" % _label(language, "stage_gates")])
    gate_rows: List[List[Any]] = []
    target_stage_id = snapshot.get("stage_id") or stage_progress.get("current_stage_id")
    target_stage = next((row for row in (snapshot.get("stage_projection") or {}).get("stages", []) if row.get("stage_id") == target_stage_id), None)
    if target_stage:
        for gate in target_stage.get("gates", []):
            gate_rows.append([
                _label(language, gate.get("kind", "")) if gate.get("kind") in DIMENSIONS else _label(language, "no_repeated_failures"),
                _status_text(gate.get("status"), language),
                gate.get("passing_sample_count", 0),
                ">= %s" % gate.get("min_score", "-") if gate.get("min_score") is not None else "-",
                gate.get("note") or ", ".join(gate.get("missing_concepts") or []) or _label(language, "none"),
            ])
    if not gate_rows:
        gate_rows.append([_label(language, "current_stage"), _label(language, "not_configured"), "-", "-", _label(language, "unknown_data")])
    lines.append(_table([_label(language, "scope"), _label(language, "status"), _label(language, "samples"), _label(language, "basis"), _label(language, "note")], gate_rows))
    lines.extend(["", "## %s" % _label(language, "evidence")])
    evidence_rows = []
    evidence = snapshot.get("evidence") or {}
    for dimension in DIMENSIONS:
        value = evidence.get(dimension) or {}
        evidence_rows.append([
            _label(language, dimension),
            _status_text(value.get("status"), language),
            value.get("sample_count", 0),
            _format_delta(value.get("delta"), language),
            _label(language, "unknown_data") if value.get("status") == "insufficient_data" else _label(language, "recorded"),
        ])
    lines.append(_table([_label(language, "scope"), _label(language, "status"), _label(language, "samples"), _label(language, "change"), _label(language, "note")], evidence_rows))
    lines.extend(["", "## %s" % _label(language, "efficiency")])
    efficiency = snapshot.get("efficiency") or {}
    actual_planned = efficiency.get("actual_vs_planned") or {}
    active_share = efficiency.get("active_time_share") or {}
    delayed = efficiency.get("delayed_review") or {}
    transfer = efficiency.get("transfer") or {}
    lines.append(
        _table(
            [_label(language, "metric"), _label(language, "result"), _label(language, "samples"), _label(language, "note")],
            [
                [_label(language, "actual_planned"), "%s / %s" % (_format_minutes(actual_planned.get("actual_minutes"), language), _format_minutes(actual_planned.get("planned_minutes"), language)), _label(language, actual_planned.get("status", "unknown")), "ratio=%s" % (actual_planned.get("ratio") if actual_planned.get("ratio") is not None else _label(language, "unknown"))],
                [_label(language, "active_share"), _format_rate(active_share.get("ratio"), language), _label(language, active_share.get("status", "unknown")), "%s / %s" % (_format_minutes(active_share.get("active_minutes"), language), _format_minutes(active_share.get("passive_minutes"), language))],
                [_label(language, "delayed_pass_rate"), _format_rate(delayed.get("pass_rate"), language), delayed.get("attempt_count", 0), "%s / %s" % (delayed.get("pass_count", 0), delayed.get("attempt_count", 0))],
                [_label(language, "transfer_rate"), _format_rate(transfer.get("pass_rate"), language), transfer.get("attempt_count", 0), "%s / %s" % (transfer.get("pass_count", 0), transfer.get("attempt_count", 0))],
            ],
        )
    )
    lines.extend(["", "## %s" % _label(language, "reviews_risks")])
    reviews = snapshot.get("reviews") or {}
    risks = snapshot.get("risks") or []
    lines.append(_table([_label(language, "metric"), _label(language, "result"), _label(language, "note")], [
        [_label(language, "overdue"), reviews.get("overdue_count", 0), reviews.get("oldest_overdue") or _label(language, "none")],
        [_label(language, "next_review"), reviews.get("oldest_overdue") or _label(language, "unknown"), "%s %s" % (reviews.get("due_count", 0), _label(language, "review_attempts"))],
        [_label(language, "risk"), len(risks), "; ".join(item.get("code", "") for item in risks) or _label(language, "none")],
    ]))
    lines.extend(["", "## %s" % _label(language, "next_actions")])
    actions = snapshot.get("next_actions") or []
    lines.append(_table(["#", _label(language, "action"), _label(language, "basis")], [
        [index, item.get("action"), item.get("evidence") or _label(language, "unknown")]
        for index, item in enumerate(actions, start=1)
    ] or [[1, _label(language, "continue_action"), _label(language, "unknown_data")]]))
    if quality.get("reasons"):
        lines.extend(["", "## %s" % _label(language, "data_notes"), "- " + "; ".join(quality["reasons"])])
    lines.extend(["", "> %s" % _label(language, "no_automatic_background")])
    return "\n".join(lines) + "\n"


def _context(study_root: Path, as_of_value: Optional[Any] = None, language: Optional[str] = None) -> Dict[str, Any]:
    reasons: List[str] = []
    profile = _read_json(study_root / "profile.json", reasons)
    timezone_value = _timezone(profile, reasons)
    observed_as_of = _as_of(as_of_value, timezone_value)
    goals = _read_json(study_root / "goals.json", reasons)
    roadmap = _read_json(study_root / "roadmap.json", reasons)
    concepts = list(_latest_by(_read_jsonl(study_root / "concepts.jsonl", reasons), "concept_id").values())
    sessions = _read_jsonl(study_root / "sessions.jsonl", reasons)
    reviews = _read_jsonl(study_root / "reviews.jsonl", reasons)
    assessments = _read_jsonl(study_root / "assessments.jsonl", reasons)
    artifacts = _read_jsonl(study_root / "artifacts.jsonl", reasons, optional=True)
    selected_language = _language(language or profile.get("language") or "en")
    return {
        "study_root": study_root,
        "profile": profile,
        "goals": goals,
        "roadmap": roadmap,
        "concepts": concepts,
        "sessions": sessions,
        "reviews": reviews,
        "assessments": assessments,
        "artifacts": artifacts,
        "timezone": timezone_value,
        "as_of": observed_as_of,
        "language": selected_language,
        "reasons": reasons,
    }


def _summary_key(kind: str, period_key: str, roadmap: Dict[str, Any], stage_id: Optional[str]) -> str:
    if kind == "stage":
        version = roadmap.get("version") or "roadmap-v1"
        return "stage:%s:%s" % (version, stage_id or "current")
    if kind == "overall":
        return "overall:%s" % period_key.split(":", 1)[-1]
    return "%s:%s" % (kind, period_key)


def _existing_summary(path: Path, summary_key: str) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("summary_key") == summary_key:
            return row
    return None


def _append_summary(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_summary(path, record["summary_key"])
    if existing is not None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _period_analytics(context: Dict[str, Any], kind: str, end: date) -> Dict[str, Any]:
    if kind not in PERIOD_KINDS:
        return {}
    try:
        return analyze_analytics(context["study_root"], as_of=end.isoformat(), window=kind)
    except (OSError, ValueError):
        return {}


def build_summary(
    study_root: Path,
    kind: str,
    as_of_value: Optional[Any] = None,
    stage_id: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a structured summary without appending it to the summary log."""
    if kind not in ("week", "month", "stage", "overall"):
        raise SummaryError("unsupported summary kind: %s" % kind)
    context = _context(Path(study_root), as_of_value, language)
    as_of_date = context["as_of"]
    if kind in PERIOD_KINDS or kind == "overall":
        start, end, period_key = _period(as_of_date, kind)
    else:
        stage = _stage_lookup(context["roadmap"], stage_id)
        if not stage:
            raise SummaryError("stage not found: %s" % (stage_id or "current"))
        start, end, period_key = None, as_of_date, "stage:%s" % (stage.get("id") or "current")
    selected_stage = _stage_lookup(context["roadmap"], stage_id) if kind == "stage" else None
    target_stage_id = selected_stage.get("id") if selected_stage else None
    target_concepts = set(selected_stage.get("concept_ids") or []) if selected_stage else None
    stage_assessment_samples = _assessment_samples(
        context["assessments"], context["timezone"], None, end, context["reasons"], target_concepts
    ) if selected_stage else []
    stage_assessment_ids = {item.get("assessment_id") for item in stage_assessment_samples if item.get("assessment_id")}
    if selected_stage:
        stage_dates = [
            parsed
            for item in stage_assessment_samples
            for parsed in [_parse_date(item.get("timestamp"))]
            if parsed is not None
        ]
        stage_review_samples = _review_samples(
            context["reviews"], context["timezone"], None, end, context["reasons"], target_concepts
        )
        stage_dates.extend(
            parsed
            for item in stage_review_samples
            for parsed in [_parse_date(item.get("timestamp"))]
            if parsed is not None
        )
        start = min(stage_dates) if stage_dates else None
    time_data = _time_metrics(
        context["sessions"],
        context["timezone"],
        start,
        end,
        context["reasons"],
        target_stage_id,
        target_concepts,
        stage_assessment_ids,
    )
    assessment_samples = _assessment_samples(
        context["assessments"], context["timezone"], start, end, context["reasons"], target_concepts
    )
    review_samples = _review_samples(
        context["reviews"], context["timezone"], start, end, context["reasons"], target_concepts
    )
    evidence = _evidence_metrics(assessment_samples, review_samples)
    reviews = _review_metrics(review_samples, context["concepts"], end, target_concepts)
    overall_assessment_samples = _assessment_samples(
        context["assessments"], context["timezone"], None, end, context["reasons"], target_concepts
    )
    overall_review_samples = _review_samples(
        context["reviews"], context["timezone"], None, end, context["reasons"], target_concepts
    )
    stage_projection = _stage_projections(
        context["roadmap"],
        context["assessments"],
        context["reviews"],
        context["concepts"],
        context["timezone"],
        end,
        context["reasons"],
    )
    selected_stage_projection = None
    if selected_stage:
        selected_stage_projection = _evaluate_stage(
            selected_stage,
            context["assessments"],
            context["reviews"],
            context["concepts"],
            context["timezone"],
            None,
            end,
            context["reasons"],
        )
        selected_stage_projection = selected_stage_projection
        stage_projection["selected_stage"] = selected_stage_projection
    goal_evidence = _goal_evidence(
        context["goals"],
        _artifacts_as_of(context["artifacts"], context["timezone"], end, context["reasons"]),
        overall_assessment_samples,
        overall_review_samples,
        stage_projection,
    )
    progress = _progress(
        context["goals"],
        context["roadmap"],
        stage_projection,
        goal_evidence,
        time_data,
        assessment_samples,
        review_samples,
        context["concepts"],
    )
    efficiency = _efficiency(time_data, reviews, evidence)
    quality = _data_quality(
        context["reasons"],
        (context["sessions"], context["assessments"], context["reviews"]),
    )
    analytics = _period_analytics(context, kind, end)
    summary_key = _summary_key(kind, period_key, context["roadmap"], target_stage_id)
    snapshot: Dict[str, Any] = {
        "version": 1,
        "summary_key": summary_key,
        "kind": kind,
        "as_of": as_of_date.isoformat(),
        "period": {
            "kind": kind,
            "start": start.isoformat() if start else None,
            "end": end.isoformat(),
            "key": period_key,
        },
        "subject": context["goals"].get("subject"),
        "goal": context["goals"].get("operational_goal") or context["goals"].get("original_goal"),
        "stage_id": target_stage_id,
        "data_quality": quality,
        "progress": progress,
        "overall": progress["overall"],
        "goal_evidence": goal_evidence,
        "stage_projection": stage_projection,
        "evidence": evidence,
        "efficiency": efficiency,
        "reviews": reviews,
        "analytics": {
            "data_quality": analytics.get("data_quality"),
            "pacing": analytics.get("pacing"),
            "alerts": analytics.get("alerts", []),
            "recommendation": analytics.get("recommendation"),
        } if analytics else {},
    }
    trigger_eligible = True
    trigger_reason = "period_complete" if kind in PERIOD_KINDS else "on_demand" if kind == "overall" else "stage_exit"
    if kind == "stage":
        trigger_eligible = bool(selected_stage_projection and selected_stage_projection.get("eligible"))
        trigger_reason = "stage_exit_evidence_satisfied" if trigger_eligible else "stage_exit_evidence_missing"
    snapshot["trigger"] = {"eligible": trigger_eligible, "reason": trigger_reason}
    snapshot["risks"], snapshot["next_actions"] = _risk_and_actions(snapshot, context["language"])
    if kind == "stage" and not trigger_eligible:
        snapshot["next_actions"] = [
            {
                "priority": "high",
                "action": _label(context["language"], "stage_action"),
                "evidence": selected_stage_projection.get("first_missing") if selected_stage_projection else None,
            }
        ]
    return {
        "snapshot": snapshot,
        "language": context["language"],
        "timezone": str(context["timezone"]),
        "source_counts": {
            "sessions": len(context["sessions"]),
            "assessments": len(context["assessments"]),
            "reviews": len(context["reviews"]),
            "concepts": len(context["concepts"]),
            "artifacts": len(context["artifacts"]),
        },
    }


def generate_summary(
    study_root: Path,
    kind: str,
    as_of_value: Optional[Any] = None,
    stage_id: Optional[str] = None,
    language: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    built = build_summary(study_root, kind, as_of_value, stage_id, language)
    snapshot = built["snapshot"]
    summary_path = Path(study_root) / "summaries.jsonl"
    existing = _existing_summary(summary_path, snapshot["summary_key"])
    if existing is not None:
        return {"summary_key": snapshot["summary_key"], "status": "already_exists", "persisted": False, "record": existing}
    markdown = _render(snapshot, built["language"])
    record = {
        "summary_id": "summary-%s" % snapshot["summary_key"].replace(":", "-").replace("/", "-"),
        "summary_key": snapshot["summary_key"],
        "kind": kind,
        "as_of": snapshot.get("as_of"),
        "period": snapshot.get("period"),
        "trigger": snapshot.get("trigger"),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "content_language": "zh-CN" if built["language"] == "zh" else "en",
        "subject": snapshot.get("subject"),
        "goal": snapshot.get("goal"),
        "data_quality": snapshot.get("data_quality"),
        "snapshot": snapshot,
        "markdown": markdown,
    }
    eligible = snapshot.get("trigger", {}).get("eligible", True)
    if kind == "stage" and not eligible:
        return {"summary_key": snapshot["summary_key"], "status": "not_ready", "persisted": False, "record": record}
    if persist:
        _append_summary(summary_path, record)
        return {"summary_key": snapshot["summary_key"], "status": "generated", "persisted": True, "record": record}
    return {"summary_key": snapshot["summary_key"], "status": "preview", "persisted": False, "record": record}


def check_due(
    study_root: Path,
    as_of_value: Optional[Any] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    context = _context(Path(study_root), as_of_value, language)
    as_of_date = context["as_of"]
    summary_path = Path(study_root) / "summaries.jsonl"
    history_exists = bool(context["sessions"] or context["assessments"] or context["reviews"])
    candidates: List[Dict[str, Any]] = []
    for kind in ("week", "month"):
        start, end, period_key = _period(as_of_date, kind)
        key = _summary_key(kind, period_key, context["roadmap"], None)
        existing = _existing_summary(summary_path, key)
        candidates.append(
            {
                "kind": kind,
                "summary_key": key,
                "period": {"start": start.isoformat() if start else None, "end": end.isoformat()},
                "eligible": history_exists,
                "due": history_exists and existing is None,
                "status": "already_exists" if existing else "due" if history_exists else "no_history",
            }
        )
    roadmap = context["roadmap"]
    stages = roadmap.get("stages") if isinstance(roadmap.get("stages"), list) else []
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("status") == "optional":
            continue
        stage_id = stage.get("id")
        key = _summary_key("stage", "stage:%s" % (stage_id or "current"), roadmap, stage_id)
        built = build_summary(Path(study_root), "stage", as_of_date, stage_id, language)
        eligible = bool(built["snapshot"].get("trigger", {}).get("eligible"))
        existing = _existing_summary(summary_path, key)
        candidates.append(
            {
                "kind": "stage",
                "stage_id": stage_id,
                "title": stage.get("title"),
                "summary_key": key,
                "eligible": eligible,
                "due": eligible and existing is None,
                "status": "already_exists" if existing else "due" if eligible else "not_ready",
                "first_missing": built["snapshot"].get("stage_projection", {}).get("selected_stage", {}).get("first_missing"),
            }
        )
    return {
        "version": 1,
        "as_of": as_of_date.isoformat(),
        "content_language": "zh-CN" if context["language"] == "zh" else "en",
        "data_quality": _data_quality(context["reasons"], (context["sessions"], context["assessments"], context["reviews"])),
        "candidates": candidates,
        "due_count": sum(1 for item in candidates if item.get("due")),
    }


def generate_due(
    study_root: Path,
    as_of_value: Optional[Any] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    due = check_due(study_root, as_of_value, language)
    results: List[Dict[str, Any]] = []
    for candidate in due["candidates"]:
        if not candidate.get("due"):
            continue
        result = generate_summary(
            Path(study_root),
            candidate["kind"],
            due["as_of"],
            candidate.get("stage_id"),
            language,
            persist=True,
        )
        results.append(
            {
                "kind": candidate["kind"],
                "summary_key": result["summary_key"],
                "status": result["status"],
                "persisted": result["persisted"],
            }
        )
    return {
        "version": 1,
        "as_of": due["as_of"],
        "generated": results,
        "generated_count": len(results),
        "check": due,
    }


def _print_check(result: Dict[str, Any], language: str) -> None:
    print("StudyAny %s" % ("总结检查" if language == "zh" else "summary check"))
    print("%s: %s" % (_label(language, "as_of"), result.get("as_of")))
    print("%s: %s" % (_label(language, "data_quality"), _status_text((result.get("data_quality") or {}).get("status"), language)))
    for item in result.get("candidates", []):
        print("- %s %s: %s" % (item.get("kind"), item.get("summary_key"), item.get("status")))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate table-oriented StudyAny summaries.")
    parser.add_argument("--study-root", type=Path, default=Path(".study"))
    parser.add_argument("--json", action="store_true", dest="global_json_output")
    subcommands = parser.add_subparsers(dest="command", required=True)

    generate = subcommands.add_parser("generate", help="generate one summary")
    generate.add_argument("--kind", choices=("week", "month", "stage", "overall"), required=True)
    generate.add_argument("--stage-id")
    generate.add_argument("--as-of")
    generate.add_argument("--language")
    generate.add_argument("--json", action="store_true", dest="json_output")

    due = subcommands.add_parser("generate-due", help="generate all due period and stage summaries")
    due.add_argument("--as-of")
    due.add_argument("--language")
    due.add_argument("--json", action="store_true", dest="json_output")

    check = subcommands.add_parser("check", help="check which summaries are due")
    check.add_argument("--as-of")
    check.add_argument("--language")
    check.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args(argv)
    json_output = bool(getattr(args, "json_output", False) or getattr(args, "global_json_output", False))
    try:
        if not args.study_root.exists():
            raise SummaryError("study root does not exist: %s" % args.study_root)
        if args.command == "generate":
            if args.kind == "stage" and not args.stage_id:
                raise SummaryError("--stage-id is required for a stage summary")
            result = generate_summary(args.study_root, args.kind, args.as_of, args.stage_id, args.language)
            if json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(result["record"].get("markdown", ""), end="")
            return 0
        if args.command == "generate-due":
            result = generate_due(args.study_root, args.as_of, args.language)
            if json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                for item in result.get("generated", []):
                    record = _existing_summary(args.study_root / "summaries.jsonl", item.get("summary_key"))
                    if record and record.get("markdown"):
                        print(record["markdown"], end="")
                    else:
                        print("Generated: %s" % item.get("summary_key"))
                print("Generated summaries: %s" % result.get("generated_count", 0))
            return 0
        result = check_due(args.study_root, args.as_of, args.language)
        language = _language(args.language or result.get("content_language") or "en")
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_check(result, language)
        return 0
    except (OSError, SummaryError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
