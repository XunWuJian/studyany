#!/usr/bin/env python3
"""Write learner-first StudyAny summary workbooks without third-party dependencies."""

from __future__ import annotations

import html
import math
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


Cell = Tuple[Any, int]
SheetRows = List[List[Cell]]

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

STYLE_TITLE = 1
STYLE_SUBTITLE = 2
STYLE_SECTION = 3
STYLE_LABEL = 4
STYLE_HEADER = 5
STYLE_TEXT = 6
STYLE_NOTE = 7
STYLE_DATE = 8
STYLE_INTEGER = 9
STYLE_NUMBER = 10
STYLE_PERCENT = 11
STYLE_GOOD = 12
STYLE_WARN = 13
STYLE_BAD = 14
STYLE_FOCUS = 15
STYLE_FOCUS_WARN = 16
STYLE_QUIET = 17

NAMESPACES = {
    "main": MAIN_NS,
    "rel": REL_NS,
    "package": PACKAGE_REL_NS,
}


# These keys are deliberately stable. The second column in the workbook is
# editable; the key lets the generator apply the edited label safely later.
CUSTOMIZABLE_FIELDS: Sequence[str] = (
    "title",
    "period_week",
    "period_month",
    "period_stage",
    "period_overall",
    "as_of",
    "period_range",
    "to",
    "start_here",
    "one_sentence",
    "your_situation",
    "focus_now",
    "why_this",
    "proof",
    "where_now",
    "period_learning",
    "learning_progress",
    "data_note",
    "data_note_label",
    "learning_state",
    "energy",
    "distraction",
    "record_count",
    "latest_record",
    "state_recorded",
    "state_not_recorded",
    "state_explicit_note",
    "state_latest_note",
    "meaning_label",
    "time_meaning",
    "sessions_meaning",
    "days_meaning",
    "checks_meaning",
    "reviews_meaning",
    "overall_stage_note",
    "goal_note",
    "ability_changes",
    "evidence_intro",
    "ability_changes_note",
    "how_to_read",
    "evidence_explanation",
    "understanding_meaning",
    "retrieval_meaning",
    "application_meaning",
    "transfer_meaning",
    "retention_meaning",
    "next_steps",
    "review_list",
    "review_meaning",
    "overdue_note",
    "normal_note",
    "no_due_reviews_note",
    "risk_note",
    "risk_detail_default",
    "stage_not_ready_short",
    "stage_ready_short",
    "continue_reason",
    "continue_proof",
    "risk_data_quality",
    "risk_stage_gate",
    "risk_review_backlog",
    "risk_fragile_progress",
    "risk_stalled_progress",
    "risk_delayed_decay",
    "risk_overlong_session",
    "risk_overload_risk",
    "records_good",
    "not_enough_records",
    "no_records_headline",
    "template_headline",
    "template_situation",
    "template_focus",
    "template_why",
    "template_proof",
    "template_data_note",
    "template_action",
    "subject_placeholder",
    "goal_placeholder",
    "stage_placeholder",
    "stage_not_configured",
    "gate_satisfied",
    "gate_insufficient",
    "gate_still_needed",
    "gate_missing",
    "missing_topics",
    "no_repeated_failures_meaning",
    "delayed_rate_meaning",
    "review_rate_missing",
    "transfer_rate_meaning",
    "transfer_rate_missing",
    "unknown_subject",
    "assessments",
    "collect_evidence_action",
    "continue_action",
    "custom_labels_title",
    "delayed_pass_rate",
    "efficiency",
    "next_review",
    "passing",
    "review_attempts",
    "sessions",
    "stage_gates",
    "transfer_rate",
    "unknown_data",
    "item",
    "now",
    "what_means",
    "recorded_times",
    "recent_performance",
    "change_simple",
    "status",
    "note",
    "current_stage",
    "stage_progress",
    "goal_position",
    "time_spent",
    "planned_time",
    "planned_time_note",
    "study_sessions",
    "study_days",
    "checks_done",
    "reviews_done",
    "goal",
    "goal_evidence",
    "next_action",
    "overdue",
    "not_due",
    "priority",
    "high",
    "normal",
    "reminder",
    "recommendation",
    "no_due_reviews",
    "no_risks",
    "data_quality",
    "unknown",
    "none",
    "yes",
    "no",
    "minutes",
    "days",
    "complete",
    "partial",
    "measured",
    "not_ready",
    "not_required",
    "insufficient_data",
    "missing",
    "satisfied",
    "open",
    "warn",
    "building",
    "consolidating",
    "fragile",
    "stalled",
    "recovering",
)

COMMON_CUSTOMIZABLE_FIELDS = frozenset({
    "title",
    "period_week",
    "period_month",
    "period_stage",
    "period_overall",
    "start_here",
    "one_sentence",
    "your_situation",
    "focus_now",
    "why_this",
    "proof",
    "where_now",
    "learning_progress",
    "data_note",
    "learning_state",
    "energy",
    "distraction",
    "record_count",
    "latest_record",
    "state_recorded",
    "state_not_recorded",
    "state_explicit_note",
    "state_latest_note",
    "ability_changes",
    "next_steps",
    "review_list",
    "item",
    "now",
    "what_means",
    "status",
    "note",
    "current_stage",
    "stage_progress",
    "goal_position",
    "time_spent",
    "study_sessions",
    "study_days",
    "checks_done",
    "reviews_done",
    "next_action",
    "meaning_label",
    "data_note_label",
    "stage_not_ready_short",
    "stage_ready_short",
    "records_good",
    "not_enough_records",
    "no_records_headline",
    "template_headline",
    "template_situation",
    "template_focus",
    "template_why",
    "template_proof",
    "template_data_note",
    "template_action",
})

FIELD_PURPOSES = {
    "zh": {
        "title": "文件最上方的标题",
        "period_week": "周总结的名称",
        "period_month": "月总结的名称",
        "period_stage": "阶段总结的名称",
        "period_overall": "总进度总结的名称",
        "as_of": "显示统计截止日期",
        "start_here": "打开文件后首先查看的结论与计划区域",
        "one_sentence": "本期学习的核心结论",
        "your_situation": "根据已有记录概括当前学习情况",
        "focus_now": "当前优先执行的计划",
        "why_this": "该计划的安排依据",
        "proof": "完成计划后应留下的结果",
        "where_now": "当前阶段与总体学习进度",
        "period_learning": "本报告覆盖的学习记录",
        "learning_progress": "本期记录、阶段目标和投入情况",
        "data_note": "说明记录完整程度及统计范围",
        "learning_state": "记录中明确填写的学习状态，仅作辅助参考",
        "energy": "精力状态",
        "distraction": "专注情况",
        "record_count": "状态记录数量",
        "latest_record": "最近一次明确填写的状态",
        "state_recorded": "已记录",
        "state_not_recorded": "暂无明确记录",
        "state_explicit_note": "仅展示用户明确填写的内容，不根据成绩、次数或文字语气推断",
        "state_latest_note": "显示最近一次明确填写的内容",
        "ability_changes": "显示不同任务类型下的能力表现",
        "next_steps": "复习与后续计划",
        "review_list": "复习安排",
        "item": "表格中的项目名称",
        "now": "项目当前结果",
        "what_means": "说明当前判断所依据的记录",
        "recorded_times": "已经留下多少条相关记录",
        "recent_performance": "最近几次记录的结果",
        "change_simple": "与前期记录相比的变化",
        "status": "项目当前状态",
        "note": "补充说明",
        "current_stage": "正在学习的阶段",
        "stage_progress": "已经完成的阶段数量",
        "goal_position": "距离最终目标的证明情况",
        "time_spent": "这段时间花了多少学习时间",
        "planned_time": "这段时间原计划安排的学习时间",
        "planned_time_note": "说明计划时间与实际时间的关系",
        "study_sessions": "这段时间学习了几次",
        "study_days": "这段时间分几天学习",
        "checks_done": "做过几次练习或小检查",
        "reviews_done": "做过几次复习",
        "goal": "当前学习目标",
        "goal_evidence": "是否有成果证明目标完成",
        "next_action": "建议下一步做什么",
        "overdue": "是否已经超过复习日期",
        "not_due": "还没有超过复习日期",
        "priority": "这件事的重要程度",
        "high": "优先处理",
        "normal": "正常安排",
        "reminder": "需要留意的情况",
        "recommendation": "建议采取的动作",
        "no_due_reviews": "目前没有到期复习",
        "no_risks": "目前没有发现需要特别留意的地方",
        "data_quality": "记录完整程度",
        "unknown": "暂无数据",
        "none": "无",
        "yes": "是",
        "no": "否",
        "minutes": "分钟",
        "days": "天",
        "complete": "记录完整",
        "partial": "有些记录不完整",
        "measured": "有记录",
        "not_ready": "尚未达到",
        "not_required": "暂不需要",
        "insufficient_data": "记录不足",
        "missing": "尚有缺项",
        "satisfied": "已经满足",
        "open": "待处理",
        "warn": "需要关注",
        "building": "正在变好",
        "consolidating": "正在巩固",
        "fragile": "会做，但还不够稳定",
        "stalled": "最近没有明显变化",
        "recovering": "正在找回状态",
    },
    "en": {
        "title": "StudyAny learning summary",
        "period_week": "Weekly summary",
        "period_month": "Monthly summary",
        "period_stage": "Stage summary",
        "period_overall": "Overall progress",
        "as_of": "As of",
        "start_here": "Start here",
        "one_sentence": "One-sentence conclusion",
        "your_situation": "Your current situation",
        "focus_now": "Your one priority",
        "why_this": "Why this comes first",
        "proof": "What to show next",
        "where_now": "Where you are",
        "period_learning": "This period",
        "learning_progress": "Learning progress",
        "data_note": "Record and scope notes",
        "learning_state": "Explicitly recorded learning conditions for reference",
        "energy": "Energy",
        "distraction": "Distraction",
        "record_count": "Recorded entries",
        "latest_record": "Latest entry",
        "state_recorded": "Recorded",
        "state_not_recorded": "No explicit entry",
        "state_explicit_note": "Shows only what the learner explicitly recorded; it does not infer a state from scores, frequency, or wording.",
        "state_latest_note": "The latest explicitly recorded value",
        "ability_changes": "Ability evidence",
        "next_steps": "Reviews and next plan",
        "review_list": "Review plan",
        "item": "Item",
        "now": "Current result",
        "what_means": "Basis for the judgment",
        "recorded_times": "Recorded entries",
        "recent_performance": "Recent results",
        "change_simple": "Change from the previous period",
        "status": "Status",
        "note": "Note",
        "current_stage": "Current stage",
        "stage_progress": "Stage progress",
        "goal_position": "Goal evidence",
        "time_spent": "Time spent",
        "planned_time": "Planned study time",
        "planned_time_note": "Explains the planned-versus-recorded time comparison",
        "study_sessions": "Study sessions",
        "study_days": "Study days",
        "checks_done": "Checks completed",
        "reviews_done": "Reviews completed",
        "goal": "Goal",
        "goal_evidence": "Goal evidence",
        "next_action": "Next action",
        "overdue": "Overdue",
        "not_due": "Not overdue",
        "priority": "Priority",
        "high": "High priority",
        "normal": "Normal",
        "reminder": "Reminder",
        "recommendation": "Recommendation",
        "no_due_reviews": "No reviews are due",
        "no_risks": "No special risks were found",
        "data_quality": "Record completeness",
        "unknown": "Not known yet",
        "none": "None",
        "yes": "Yes",
        "no": "No",
        "minutes": "min",
        "days": "days",
        "complete": "Complete records",
        "partial": "Some records are incomplete",
        "measured": "Recorded",
        "not_ready": "Not ready yet",
        "not_required": "Not needed yet",
        "insufficient_data": "More records needed",
        "missing": "Still missing",
        "satisfied": "Satisfied",
        "open": "Open",
        "warn": "Needs attention",
        "building": "Building",
        "consolidating": "Consolidating",
        "fragile": "Works, but not stable yet",
        "stalled": "No clear recent change",
        "recovering": "Recovering",
    },
}


def _label(labels: Dict[str, str], key: str, default: str) -> str:
    value = labels.get(key)
    return value if isinstance(value, str) and value else default


def _status(labels: Dict[str, str], value: Any) -> str:
    if value is None or value == "":
        return _label(labels, "unknown", "Unknown")
    return _label(labels, str(value), str(value))


def _status_style(value: Any) -> int:
    text = str(value or "").strip().lower()
    if text in {
        "met", "satisfied", "complete", "measured", "completed", "building",
        "recovering", "pass", "通过", "已满足", "完整", "已测量", "已完成", "正在变好", "正在找回状态",
    }:
        return STYLE_GOOD
    if text in {
        "not_ready", "insufficient_data", "missing", "unknown", "not_observed", "fail",
        "未满足", "记录还不够", "缺少", "未知", "还没达到", "还缺少",
    }:
        return STYLE_BAD
    return STYLE_WARN


def _cell(value: Any, style: int = STYLE_TEXT) -> Cell:
    return value, style


def _row(values: Sequence[Any], styles: Optional[Sequence[int]] = None) -> List[Cell]:
    selected = list(styles) if styles is not None else [STYLE_TEXT] * len(values)
    return [_cell(value, selected[index] if index < len(selected) else STYLE_TEXT) for index, value in enumerate(values)]


def _date_value(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _number_value(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)


def _unknown_value(value: Any, labels: Dict[str, str]) -> Any:
    return value if value is not None else _label(labels, "unknown", "Unknown")


def _format_period(snapshot: Dict[str, Any], labels: Dict[str, str]) -> str:
    period = snapshot.get("period") or {}
    start = period.get("start")
    end = period.get("end") or snapshot.get("as_of")
    if start and end:
        return "%s %s %s" % (start, _label(labels, "to", "to"), end)
    if end:
        return "%s %s" % (_label(labels, "as_of", "As of"), end)
    return _label(labels, "unknown", "Unknown")


def _view(snapshot: Dict[str, Any], labels: Dict[str, str]) -> Dict[str, Any]:
    view = snapshot.get("learner_view")
    if isinstance(view, dict):
        return view
    return {
        "headline": _label(labels, "not_enough_records", "More records are needed before a useful conclusion can be made."),
        "situation": _label(labels, "not_enough_records", "More records are needed before a useful conclusion can be made."),
        "focus": _label(labels, "next_action", "Continue with the next saved learning task."),
        "why": _label(labels, "why_this", "Use the next recorded learning need to choose the plan."),
        "proof": _label(labels, "proof", "Return a saved result or explanation."),
        "stage_line": _label(labels, "unknown", "Unknown"),
        "stage_progress": _label(labels, "unknown", "Unknown"),
        "goal_line": _label(labels, "unknown", "Unknown"),
        "data_note": _label(labels, "unknown", "Unknown"),
    }


def _section(text: str, column_count: int) -> List[Cell]:
    return _row([text] + [None] * (column_count - 1), [STYLE_SECTION] * column_count)


def _narrative_row(label: str, value: Any, column_count: int, style: int = STYLE_TEXT) -> List[Cell]:
    return _row(
        [label, value] + [None] * (column_count - 2),
        [STYLE_LABEL, style] + [style] * (column_count - 2),
    )


def _style_number(value: Any, style: int, labels: Dict[str, str]) -> int:
    return style if _number_value(value) is not None else STYLE_TEXT


def _overview_rows(snapshot: Dict[str, Any], labels: Dict[str, str], language: str) -> Tuple[SheetRows, List[float], List[str]]:
    column_count = 6
    subject = snapshot.get("subject") or _label(labels, "unknown_subject", "Subject not configured")
    kind = snapshot.get("kind") or "overall"
    title_text = _label(labels, "title", "StudyAny 学习情况报告" if language == "zh" else "StudyAny Learning Progress Report")
    period_text = _label(labels, "period_%s" % kind, kind)
    title = "%s：%s" % (title_text, subject) if language == "zh" else "%s: %s" % (title_text, subject)
    view = _view(snapshot, labels)
    progress = snapshot.get("progress") or {}
    period = progress.get("period") or {}
    stage = progress.get("stage") or {}
    overall = progress.get("overall") or {}
    quality = snapshot.get("data_quality") or {}
    goal_evidence = snapshot.get("goal_evidence") or {}
    stage_status = "met" if stage.get("current_stage_eligible") else "not_ready"
    stage_status_label = _status(labels, stage_status)
    rows: SheetRows = []
    merges: List[str] = []

    def add_section(text: str) -> None:
        rows.append(_section(text, column_count))
        row_number = len(rows)
        merges.append("A%d:F%d" % (row_number, row_number))

    def add_narrative(label: str, value: Any, style: int = STYLE_TEXT) -> None:
        rows.append(_narrative_row(label, value, column_count, style))
        row_number = len(rows)
        merges.append("B%d:F%d" % (row_number, row_number))

    rows.append(_row([title] + [None] * 5, [STYLE_TITLE] * column_count))
    merges.append("A1:F1")
    rows.append(_row(["%s · %s：%s" % (period_text, _label(labels, "period_range", "统计期间"), _format_period(snapshot, labels))] + [None] * 5, [STYLE_SUBTITLE] * column_count))
    merges.append("A2:F2")
    rows.append([])
    add_section(_label(labels, "start_here", "结论与计划"))
    add_narrative(_label(labels, "one_sentence", "核心结论"), view.get("headline"), STYLE_FOCUS)
    add_narrative(_label(labels, "goal", "学习目标"), snapshot.get("goal") or _label(labels, "unknown_goal", "尚未配置学习目标"), STYLE_TEXT)
    add_narrative(_label(labels, "your_situation", "当前情况"), view.get("situation"), STYLE_TEXT)
    add_narrative(_label(labels, "focus_now", "优先计划"), view.get("focus"), STYLE_FOCUS_WARN)
    add_narrative(_label(labels, "why_this", "安排依据"), view.get("why"), STYLE_NOTE)
    add_narrative(_label(labels, "proof", "预期结果"), view.get("proof"), STYLE_NOTE)
    rows.append([])
    add_section(_label(labels, "where_now", "学习目标与阶段进度"))
    rows.append(_row([
        _label(labels, "item", "项目"), _label(labels, "now", "当前情况"), _label(labels, "what_means", "判断依据"),
        _label(labels, "recorded_times", "记录数量"), _label(labels, "status", "状态"), _label(labels, "note", "说明"),
    ], [STYLE_HEADER] * column_count))
    rows.append(_row([
        _label(labels, "current_stage", "当前阶段"), stage.get("current_stage_title") or _label(labels, "unknown", "暂时不知道"),
        view.get("stage_line"), None, stage_status_label, _label(labels, "stage_not_ready_short", "还需要更多学习记录") if stage_status == "not_ready" else _label(labels, "stage_ready_short", "可以准备下一阶段"),
    ], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_TEXT, _status_style(stage_status), STYLE_NOTE]))
    rows.append(_row([
        _label(labels, "stage_progress", "阶段进度"), "%s / %s" % (overall.get("completed_stage_count", 0), overall.get("required_stage_count", 0)),
        view.get("stage_progress"), overall.get("required_stage_count", 0), _status_style(stage_status), _label(labels, "overall_stage_note", "依据阶段完成条件判断"),
    ], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(stage_status), STYLE_NOTE]))
    rows.append(_row([
        _label(labels, "goal_position", "学习目标"), _status(labels, goal_evidence.get("status")), view.get("goal_line"),
        len(goal_evidence.get("requirements") or []), _status_style(goal_evidence.get("status")), _label(labels, "goal_note", "需要可检查的成果记录"),
    ], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(goal_evidence.get("status")), STYLE_NOTE]))
    rows.append([])
    add_section(_label(labels, "period_learning", "本期学习记录"))
    rows.append(_row([
        _label(labels, "item", "项目"), _label(labels, "now", "当前情况"), _label(labels, "what_means", "判断依据"),
        _label(labels, "recorded_times", "记录数量"), _label(labels, "status", "状态"), _label(labels, "note", "说明"),
    ], [STYLE_HEADER] * column_count))
    rows.append(_row([
        _label(labels, "time_spent", "实际学习时间"), period.get("actual_minutes") if period.get("actual_minutes") is not None else _label(labels, "unknown", "暂时不知道"),
        _label(labels, "time_meaning", "用于观察计划执行，不单独代表掌握程度"), period.get("session_count", 0),
        _status(labels, "measured" if period.get("actual_minutes") is not None else "insufficient_data"), _label(labels, "minutes", "分钟"),
    ], [STYLE_TEXT, _style_number(period.get("actual_minutes"), STYLE_NUMBER, labels), STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("actual_minutes") is not None else "insufficient_data"), STYLE_NOTE]))
    rows.append(_row([
        _label(labels, "study_sessions", "学习次数"), period.get("session_count", 0), _label(labels, "sessions_meaning", "用于观察计划执行的连续性"),
        period.get("session_count", 0), _status(labels, "measured" if period.get("session_count") else "no_sessions"), _label(labels, "sessions", "次"),
    ], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("session_count") else "no_sessions"), STYLE_NOTE]))
    rows.append(_row([
        _label(labels, "study_days", "学习天数"), period.get("study_days", 0), _label(labels, "days_meaning", "用于观察计划是否分散到不同日期"),
        period.get("study_days", 0), _status(labels, "measured" if period.get("study_days") else "no_sessions"), _label(labels, "days", "天"),
    ], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("study_days") else "no_sessions"), STYLE_NOTE]))
    rows.append(_row([
        _label(labels, "checks_done", "练习记录"), period.get("assessment_sample_count", 0), _label(labels, "checks_meaning", "用于判断能否完成目标任务"),
        period.get("assessment_sample_count", 0), _status(labels, "measured" if period.get("assessment_sample_count") else "insufficient_data"), _label(labels, "assessments", "项"),
    ], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("assessment_sample_count") else "insufficient_data"), STYLE_NOTE]))
    rows.append(_row([
        _label(labels, "reviews_done", "复习记录"), period.get("review_attempt_count", 0), _label(labels, "reviews_meaning", "用于观察一段时间后是否仍能完成"),
        period.get("review_attempt_count", 0), _status(labels, "measured" if period.get("review_attempt_count") else "insufficient_data"), _label(labels, "review_attempts", "次"),
    ], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("review_attempt_count") else "insufficient_data"), STYLE_NOTE]))
    rows.append([])
    add_section(_label(labels, "data_note", "数据说明"))
    add_narrative(_label(labels, "data_note_label", "统计说明"), view.get("data_note") or _label(labels, "unknown", "暂时不知道"), STYLE_NOTE)
    return rows, [22, 23, 38, 12, 15, 34], merges


def _current_stage_projection(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    projection = snapshot.get("stage_projection") or {}
    current_id = (projection.get("current_stage") or {}).get("id")
    for stage in projection.get("stages") or []:
        if isinstance(stage, dict) and stage.get("stage_id") == current_id:
            return stage
    selected = projection.get("selected_stage")
    return selected if isinstance(selected, dict) else {}


def _stage_gate_rows(snapshot: Dict[str, Any], labels: Dict[str, str], language: str) -> List[List[Cell]]:
    stage = _current_stage_projection(snapshot)
    if not stage:
        return [_row([
            _label(labels, "current_stage", "当前阶段"), _label(labels, "unknown", "暂时不知道"),
            _label(labels, "stage_not_configured", "还没有设置阶段要求"), None,
            _status(labels, "insufficient_data"), _label(labels, "unknown_data", "记录还不够"),
        ], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_TEXT, STYLE_BAD, STYLE_NOTE])]
    result: List[List[Cell]] = []
    meanings = {
        "retrieval": "不看资料，能不能想起来",
        "application": "不看示范，能不能自己做类似练习",
        "transfer": "换一个例子或场景，能不能继续做",
        "retention": "隔一段时间后，能不能再次做对",
        "no_repeated_failures": "复习时不要连续失败",
    }
    for gate in stage.get("gates") or []:
        kind = gate.get("kind")
        label = _label(labels, "%s_gate" % kind, meanings.get(kind, "完成这项练习"))
        status = gate.get("status")
        samples = gate.get("sample_count", 0)
        passing = gate.get("passing_sample_count", 0)
        if status == "met":
            current = _label(labels, "gate_satisfied", "已经有足够记录")
        elif status == "insufficient_data":
            current = _label(labels, "gate_insufficient", "还没有这类记录")
        elif passing:
            current = "%s %s，%s" % (passing, _label(labels, "passing", "做对"), _label(labels, "gate_still_needed", "但还不够"))
        else:
            current = _label(labels, "gate_missing", "还需要记录")
        missing = []
        titles = stage.get("concept_titles") or {}
        for concept_id in gate.get("missing_concepts") or []:
            missing.append(titles.get(concept_id) or str(concept_id))
        note = "%s：%s" % (_label(labels, "missing_topics", "重点"), "、".join(missing[:3])) if missing else gate.get("note") or _label(labels, "none", "无")
        if language == "en" and missing:
            note = "Focus: " + ", ".join(missing[:3])
        result.append(_row([
            label,
            current,
            _label(labels, "%s_meaning" % kind, meanings.get(kind, "Complete this practice")),
            samples,
            _status(labels, status),
            note,
        ], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(status), STYLE_NOTE]))
    return result or [_row([
        _label(labels, "current_stage", "当前阶段"), _label(labels, "unknown", "暂时不知道"),
        _label(labels, "stage_not_configured", "还没有设置阶段要求"), None,
        _status(labels, "insufficient_data"), _label(labels, "unknown_data", "记录还不够"),
    ], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_TEXT, STYLE_BAD, STYLE_NOTE])]


def _efficiency_rows(snapshot: Dict[str, Any], labels: Dict[str, str], language: str) -> List[List[Cell]]:
    efficiency = snapshot.get("efficiency") or {}
    actual_planned = efficiency.get("actual_vs_planned") or {}
    delayed = efficiency.get("delayed_review") or {}
    transfer = efficiency.get("transfer") or {}
    unknown = _label(labels, "unknown", "暂时不知道")
    rows: List[List[Cell]] = []
    actual = actual_planned.get("actual_minutes")
    planned = actual_planned.get("planned_minutes")
    planned_text = ("计划 %s 分钟" % planned) if planned is not None and language == "zh" else ("planned %s min" % planned) if planned is not None else _label(labels, "time_meaning", "时间只能作为投入参考")
    rows.append(_row([
        _label(labels, "time_spent", "花费时间"), actual if actual is not None else unknown, planned_text,
        1 if actual is not None else 0, _status(labels, actual_planned.get("status")),
        _label(labels, "time_meaning", "时间只能说明投入过，不能单独证明已经学会。"),
    ], [STYLE_TEXT, _style_number(actual, STYLE_NUMBER, labels), STYLE_NOTE, STYLE_INTEGER, _status_style(actual_planned.get("status")), STYLE_NOTE]))
    delayed_rate = delayed.get("pass_rate")
    delayed_result = delayed_rate if delayed_rate is not None else unknown
    delayed_explanation = "%s / %s 次" % (delayed.get("pass_count", 0), delayed.get("attempt_count", 0)) if delayed.get("attempt_count") else _label(labels, "review_rate_missing", "还没有足够的间隔复习记录")
    rows.append(_row([
        _label(labels, "delayed_pass_rate", "隔一段时间后还记得"), delayed_result, delayed_explanation,
        delayed.get("attempt_count", 0), _status(labels, delayed.get("status")), _label(labels, "delayed_rate_meaning", "这个比例越可靠，说明隔几天后仍能做对的记录越多。"),
    ], [STYLE_TEXT, STYLE_PERCENT if delayed_rate is not None else STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(delayed.get("status")), STYLE_NOTE]))
    transfer_rate = transfer.get("pass_rate")
    transfer_result = transfer_rate if transfer_rate is not None else unknown
    transfer_explanation = "%s / %s 次" % (transfer.get("pass_count", 0), transfer.get("attempt_count", 0)) if transfer.get("attempt_count") else _label(labels, "transfer_rate_missing", "还没有换例子练习记录")
    rows.append(_row([
        _label(labels, "transfer_rate", "换个例子还能做"), transfer_result, transfer_explanation,
        transfer.get("attempt_count", 0), _status(labels, transfer.get("status")), _label(labels, "transfer_rate_meaning", "换例子可以确认你是在理解，而不是只记住原题。"),
    ], [STYLE_TEXT, STYLE_PERCENT if transfer_rate is not None else STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(transfer.get("status")), STYLE_NOTE]))
    return rows


def _learning_state_rows(snapshot: Dict[str, Any], labels: Dict[str, str]) -> List[List[Cell]]:
    state = snapshot.get("learning_state") or ((snapshot.get("progress") or {}).get("period") or {}).get("learning_state") or {}
    header = _row([
        _label(labels, "item", "项目"),
        _label(labels, "record_count", "记录数量"),
        _label(labels, "latest_record", "最近一次明确填写"),
        _label(labels, "what_means", "判断依据"),
        _label(labels, "status", "状态"),
        _label(labels, "note", "说明"),
    ], [STYLE_HEADER] * 6)
    rows = [header]
    for field in ("energy", "distraction"):
        item = state.get(field) or {}
        count = item.get("recorded_count", 0)
        latest = item.get("latest")
        current = latest if latest is not None else _label(labels, "state_not_recorded", "暂无明确记录")
        status = "measured" if count else "insufficient_data"
        rows.append(_row([
            _label(labels, field, field),
            count,
            current,
            _label(labels, "state_latest_note", "显示最近一次明确填写的内容") if count else _label(labels, "state_explicit_note", "仅展示用户明确填写的内容，不根据成绩、次数或文字语气推断"),
            _label(labels, "state_recorded", "已记录") if count else _label(labels, "state_not_recorded", "暂无明确记录"),
            _label(labels, "state_explicit_note", "仅展示用户明确填写的内容，不根据成绩、次数或文字语气推断"),
        ], [STYLE_TEXT, STYLE_INTEGER, STYLE_TEXT, STYLE_NOTE, _status_style(status), STYLE_NOTE]))
    return rows


def _progress_rows(snapshot: Dict[str, Any], labels: Dict[str, str], language: str) -> Tuple[SheetRows, List[float], List[str]]:
    column_count = 6
    subject = snapshot.get("subject") or _label(labels, "unknown_subject", "Subject not configured")
    title_text = _label(labels, "learning_progress", "学习进展")
    title = "%s：%s" % (title_text, subject) if language == "zh" else "%s: %s" % (title_text, subject)
    progress = snapshot.get("progress") or {}
    period = progress.get("period") or {}
    stage = progress.get("stage") or {}
    overall = progress.get("overall") or {}
    goal_evidence = snapshot.get("goal_evidence") or {}
    view = _view(snapshot, labels)
    status_value = "met" if stage.get("current_stage_eligible") else "not_ready"
    rows: SheetRows = []
    merges: List[str] = []

    def add_section(text: str) -> None:
        rows.append(_section(text, column_count))
        row_number = len(rows)
        merges.append("A%d:F%d" % (row_number, row_number))

    rows.append(_row([title] + [None] * 5, [STYLE_TITLE] * column_count))
    merges.append("A1:F1")
    rows.append(_row(["%s：%s" % (_label(labels, "period_range", "统计期间"), _format_period(snapshot, labels))] + [None] * 5, [STYLE_SUBTITLE] * column_count))
    merges.append("A2:F2")
    rows.append([])
    add_section(_label(labels, "period_learning", "本期学习记录"))
    rows.append(_row([_label(labels, "item", "项目"), _label(labels, "now", "当前情况"), _label(labels, "what_means", "判断依据"), _label(labels, "recorded_times", "记录数量"), _label(labels, "status", "状态"), _label(labels, "note", "说明")], [STYLE_HEADER] * column_count))
    rows.append(_row([_label(labels, "time_spent", "实际学习时间"), _unknown_value(period.get("actual_minutes"), labels), _label(labels, "time_meaning", "用于观察计划执行，不单独代表掌握程度"), period.get("session_count", 0), _status(labels, "measured" if period.get("actual_minutes") is not None else "insufficient_data"), _label(labels, "minutes", "分钟")], [STYLE_TEXT, _style_number(period.get("actual_minutes"), STYLE_NUMBER, labels), STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("actual_minutes") is not None else "insufficient_data"), STYLE_NOTE]))
    rows.append(_row([_label(labels, "planned_time", "计划学习时间"), _unknown_value(period.get("planned_minutes"), labels), _label(labels, "planned_time_note", "用于比较计划与实际执行情况"), period.get("planned_session_count", 0), _status(labels, "measured" if period.get("planned_minutes") is not None else "insufficient_data"), _label(labels, "minutes", "分钟")], [STYLE_TEXT, _style_number(period.get("planned_minutes"), STYLE_NUMBER, labels), STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("planned_minutes") is not None else "insufficient_data"), STYLE_NOTE]))
    rows.append(_row([_label(labels, "study_sessions", "学习次数"), period.get("session_count", 0), _label(labels, "sessions_meaning", "用于观察计划执行的连续性"), period.get("session_count", 0), _status(labels, "measured" if period.get("session_count") else "no_sessions"), _label(labels, "sessions", "次")], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("session_count") else "no_sessions"), STYLE_NOTE]))
    rows.append(_row([_label(labels, "study_days", "学习天数"), period.get("study_days", 0), _label(labels, "days_meaning", "用于观察计划是否分散到不同日期"), period.get("study_days", 0), _status(labels, "measured" if period.get("study_days") else "no_sessions"), _label(labels, "days", "天")], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("study_days") else "no_sessions"), STYLE_NOTE]))
    rows.append(_row([_label(labels, "checks_done", "练习记录"), period.get("assessment_sample_count", 0), _label(labels, "checks_meaning", "用于判断能否完成目标任务"), period.get("assessment_sample_count", 0), _status(labels, "measured" if period.get("assessment_sample_count") else "insufficient_data"), _label(labels, "assessments", "项")], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("assessment_sample_count") else "insufficient_data"), STYLE_NOTE]))
    rows.append(_row([_label(labels, "reviews_done", "复习记录"), period.get("review_attempt_count", 0), _label(labels, "reviews_meaning", "用于观察一段时间后是否仍能完成"), period.get("review_attempt_count", 0), _status(labels, "measured" if period.get("review_attempt_count") else "insufficient_data"), _label(labels, "review_attempts", "次")], [STYLE_TEXT, STYLE_INTEGER, STYLE_NOTE, STYLE_INTEGER, _status_style("measured" if period.get("review_attempt_count") else "insufficient_data"), STYLE_NOTE]))
    rows.append([])
    add_section(_label(labels, "where_now", "学习目标与阶段进度"))
    rows.append(_row([_label(labels, "item", "项目"), _label(labels, "now", "当前情况"), _label(labels, "what_means", "判断依据"), _label(labels, "recorded_times", "记录数量"), _label(labels, "status", "状态"), _label(labels, "note", "说明")], [STYLE_HEADER] * column_count))
    rows.append(_row([_label(labels, "current_stage", "当前阶段"), stage.get("current_stage_title") or _label(labels, "unknown", "暂时不知道"), view.get("stage_line"), None, _status(labels, status_value), _label(labels, "stage_not_ready_short", "还需要更多学习记录") if status_value == "not_ready" else _label(labels, "stage_ready_short", "可以准备下一阶段")], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_TEXT, _status_style(status_value), STYLE_NOTE]))
    rows.append(_row([_label(labels, "stage_progress", "阶段进度"), "%s / %s" % (overall.get("completed_stage_count", 0), overall.get("required_stage_count", 0)), view.get("stage_progress"), overall.get("required_stage_count", 0), _status(labels, status_value), _label(labels, "overall_stage_note", "依据阶段完成条件判断")], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(status_value), STYLE_NOTE]))
    rows.append(_row([_label(labels, "goal_position", "学习目标"), _status(labels, goal_evidence.get("status")), view.get("goal_line"), len(goal_evidence.get("requirements") or []), _status_style(goal_evidence.get("status")), _label(labels, "goal_note", "需要可检查的成果记录")], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_INTEGER, _status_style(goal_evidence.get("status")), STYLE_NOTE]))
    rows.append([])
    add_section(_label(labels, "stage_gates", "阶段完成条件"))
    rows.append(_row([_label(labels, "item", "完成条件"), _label(labels, "now", "当前结果"), _label(labels, "what_means", "判断依据"), _label(labels, "recorded_times", "记录数量"), _label(labels, "status", "状态"), _label(labels, "note", "说明")], [STYLE_HEADER] * column_count))
    rows.extend(_stage_gate_rows(snapshot, labels, language))
    rows.append([])
    add_section(_label(labels, "efficiency", "学习投入与保持情况"))
    rows.append(_row([_label(labels, "item", "项目"), _label(labels, "now", "当前结果"), _label(labels, "what_means", "判断依据"), _label(labels, "recorded_times", "记录数量"), _label(labels, "status", "状态"), _label(labels, "note", "说明")], [STYLE_HEADER] * column_count))
    rows.extend(_efficiency_rows(snapshot, labels, language))
    rows.append([])
    add_section(_label(labels, "learning_state", "学习状态观察（辅助）"))
    rows.extend(_learning_state_rows(snapshot, labels))
    return rows, [22, 23, 38, 12, 15, 34], merges


def _dimension_meaning(labels: Dict[str, str], dimension: str) -> str:
    defaults = {
        "understanding": "能不能用自己的话讲明白",
        "retrieval": "不看资料能不能想起来",
        "application": "能不能自己做出类似题",
        "transfer": "换个例子或场景还能不能做",
        "retention": "隔几天再做是否还记得",
    }
    return _label(labels, "%s_meaning" % dimension, defaults.get(dimension, "记录中的表现"))


def _evidence_rows(snapshot: Dict[str, Any], labels: Dict[str, str], language: str) -> Tuple[SheetRows, List[float], List[str]]:
    column_count = 6
    subject = snapshot.get("subject") or _label(labels, "unknown_subject", "Subject not configured")
    title_text = _label(labels, "ability_changes", "能力证据")
    title = "%s：%s" % (title_text, subject) if language == "zh" else "%s: %s" % (title_text, subject)
    rows: SheetRows = [
        _row([title] + [None] * 5, [STYLE_TITLE] * column_count),
        _row([_label(labels, "evidence_intro", "按任务类型查看当前能力表现；记录数量越多，判断依据越充分。")]+[None]*5, [STYLE_SUBTITLE]*column_count),
        [],
        _row([_label(labels, "ability_changes_note", "重点查看当前情况和记录数量，百分比作为补充。")]+[None]*5, [STYLE_NOTE]*column_count),
        _row([
            _label(labels, "item", "能力项目"), _label(labels, "now", "当前情况"), _label(labels, "what_means", "判断依据"),
            _label(labels, "recorded_times", "记录数量"), _label(labels, "recent_performance", "近期结果"), _label(labels, "change_simple", "变化情况"),
        ], [STYLE_HEADER] * column_count),
    ]
    evidence = snapshot.get("evidence") or {}
    for dimension in ("understanding", "retrieval", "application", "transfer", "retention"):
        value = evidence.get(dimension) or {}
        status_value = value.get("status")
        recent = value.get("recent_mean") if value.get("recent_mean") is not None else _label(labels, "unknown", "Unknown")
        delta = value.get("delta") if value.get("delta") is not None else _label(labels, "unknown", "Unknown")
        rows.append(_row([
            _label(labels, dimension, dimension), _status(labels, status_value), _dimension_meaning(labels, dimension), value.get("sample_count", 0), recent, delta,
        ], [STYLE_TEXT, _status_style(status_value), STYLE_NOTE, STYLE_INTEGER, STYLE_PERCENT if value.get("recent_mean") is not None else STYLE_TEXT, STYLE_PERCENT if value.get("delta") is not None else STYLE_TEXT]))
    rows.extend([
        [],
        _section(_label(labels, "how_to_read", "能力表现说明"), column_count),
        _narrative_row(_label(labels, "meaning_label", "判断说明"), _label(labels, "evidence_explanation", "较稳定的能力需要通过不看资料、变换题目或延迟复习等不同记录来确认。"), column_count, STYLE_NOTE),
    ])
    merges = ["A1:F1", "A2:F2", "A4:F4", "A12:F12", "B13:F13"]
    return rows, [25, 22, 42, 12, 16, 14], merges


def _friendly_risk(code: Any, labels: Dict[str, str]) -> str:
    mapping = {
        "data_quality": "有些学习记录不完整，部分数字只能作为参考",
        "stage_gate": "当前阶段还没有达到进入下一阶段的条件",
        "review_backlog": "有内容到了应该复习的时间",
        "fragile_progress": "最近会做，但还缺少换题或隔天复习来确认",
        "stalled_progress": "最近几次记录没有明显变化，需要换一个更小的练习",
        "delayed_decay": "之前会做，但隔一段时间后又忘了，需要缩短复习间隔",
        "overlong_session": "有一次学习时间明显偏长，建议拆成小段",
        "overload_risk": "投入时间和学习表现同时出现需要留意的信号",
    }
    return _label(labels, "risk_%s" % code, mapping.get(str(code), "有一项学习记录需要留意"))


def _next_rows(snapshot: Dict[str, Any], labels: Dict[str, str], language: str) -> Tuple[SheetRows, List[float], List[str]]:
    column_count = 6
    subject = snapshot.get("subject") or _label(labels, "unknown_subject", "Subject not configured")
    title_text = _label(labels, "next_steps", "复习与后续计划")
    title = "%s：%s" % (title_text, subject) if language == "zh" else "%s: %s" % (title_text, subject)
    view = _view(snapshot, labels)
    reviews = snapshot.get("reviews") or {}
    risks = snapshot.get("risks") or []
    actions = snapshot.get("next_actions") or []
    primary_action = actions[0].get("action") if actions and isinstance(actions[0], dict) else view.get("focus")
    primary_evidence = actions[0].get("evidence") if actions and isinstance(actions[0], dict) else None
    rows: SheetRows = [
        _row([title] + [None] * 5, [STYLE_TITLE] * column_count),
        _row(["%s：%s" % (_label(labels, "period_range", "统计期间"), _format_period(snapshot, labels))] + [None] * 5, [STYLE_SUBTITLE] * column_count),
        [],
        _section(_label(labels, "focus_now", "下一项计划"), column_count),
        _narrative_row(_label(labels, "next_action", "下一项计划"), primary_action or _label(labels, "continue_action", "Continue with the next learning task."), column_count, STYLE_FOCUS_WARN),
        _narrative_row(_label(labels, "why_this", "安排依据"), view.get("why"), column_count, STYLE_NOTE),
        _narrative_row(_label(labels, "proof", "预期结果"), view.get("proof") or primary_evidence or _label(labels, "proof", "Return a saved result or explanation."), column_count, STYLE_NOTE),
        [],
        _section(_label(labels, "review_list", "复习安排"), column_count),
        _row([_label(labels, "item", "学习内容"), _label(labels, "next_review", "计划日期"), _label(labels, "status", "当前状态"), _label(labels, "priority", "优先级"), _label(labels, "what_means", "安排依据"), _label(labels, "note", "说明")], [STYLE_HEADER] * column_count),
    ]
    due_items = reviews.get("due_items") or []
    for item in due_items:
        overdue = bool(item.get("overdue"))
        rows.append(_row([
            item.get("title") or item.get("concept_id") or _label(labels, "unknown", "Unknown"),
            _date_value(item.get("next_review")) or _label(labels, "unknown", "Unknown"),
            _label(labels, "overdue", "已到期") if overdue else _label(labels, "not_due", "今天到期"),
            _label(labels, item.get("priority") or "normal", item.get("priority") or "normal"),
            _label(labels, "review_meaning", "隔一段时间再做，才能确认是否记住"),
            _label(labels, "overdue_note", "先完成这项，再开始新内容") if overdue else _label(labels, "normal_note", "按计划完成即可"),
        ], [STYLE_TEXT, STYLE_DATE if _date_value(item.get("next_review")) else STYLE_TEXT, _status_style("warn" if overdue else "open"), STYLE_TEXT, STYLE_NOTE, STYLE_NOTE]))
    if not due_items:
        rows.append(_row([_label(labels, "no_due_reviews", "目前没有到期复习"), None, _status(labels, "complete"), None, _label(labels, "no_due_reviews_note", "继续完成当前阶段的练习"), None], [STYLE_TEXT, STYLE_TEXT, STYLE_GOOD, STYLE_TEXT, STYLE_NOTE, STYLE_TEXT]))
    risk_section_row = len(rows) + 2
    rows.extend([
        [],
        _section(_label(labels, "reminder", "关注事项"), column_count),
        _row([_label(labels, "reminder", "事项"), _label(labels, "now", "当前情况"), _label(labels, "recommendation", "计划建议"), _label(labels, "priority", "优先级"), _label(labels, "status", "状态"), _label(labels, "note", "说明")], [STYLE_HEADER] * column_count),
    ])
    for risk in risks:
        code = risk.get("code") if isinstance(risk, dict) else None
        if code == "stage_gate":
            risk_detail = view.get("stage_line")
        elif code == "data_quality":
            risk_detail = view.get("data_note")
        elif code == "review_backlog":
            risk_detail = "%s：%s" % (_label(labels, "overdue", "已经到期"), reviews.get("overdue_count", 0))
        else:
            risk_detail = _label(labels, "risk_detail_default", "这项内容需要在下一次练习中继续确认")
        rows.append(_row([
            _friendly_risk(code, labels), risk_detail,
            (actions[0].get("action") if actions and isinstance(actions[0], dict) else _label(labels, "collect_evidence_action", "Collect one more evidence item.")),
            _label(labels, "high", "High priority"), _status(labels, risk.get("status") if isinstance(risk, dict) else "warn"),
            _label(labels, "risk_note", "这是对下一步的提醒，不是对人的评价"),
        ], [STYLE_TEXT, STYLE_NOTE, STYLE_NOTE, STYLE_TEXT, _status_style(risk.get("status") if isinstance(risk, dict) else "warn"), STYLE_NOTE]))
    if not risks:
        rows.append(_row([_label(labels, "no_risks", "目前没有发现需要特别留意的地方"), None, _label(labels, "continue_action", "继续当前学习路线"), _label(labels, "normal", "Normal"), _status(labels, "complete"), None], [STYLE_TEXT, STYLE_TEXT, STYLE_NOTE, STYLE_TEXT, STYLE_GOOD, STYLE_TEXT]))
    data_section_row = len(rows) + 2
    rows.extend([
        [],
        _section(_label(labels, "data_note", "数据说明"), column_count),
        _narrative_row(_label(labels, "data_note_label", "统计说明"), view.get("data_note") or _label(labels, "unknown", "Unknown"), column_count, STYLE_NOTE),
    ])
    data_note_row = data_section_row + 1
    merges = ["A1:F1", "A2:F2", "A4:F4", "B5:F5", "B6:F6", "B7:F7", "A9:F9", "A%d:F%d" % (risk_section_row, risk_section_row), "A%d:F%d" % (data_section_row, data_section_row), "B%d:F%d" % (data_note_row, data_note_row)]
    return rows, [31, 16, 23, 16, 37, 31], merges


def _field_purpose(key: str, language: str) -> str:
    default = "可修改的显示文字" if language == "zh" else "Learner-facing label"
    return FIELD_PURPOSES.get(language, FIELD_PURPOSES["en"]).get(key, default)


def _settings_rows(labels: Dict[str, str], language: str, template_mode: bool) -> Tuple[SheetRows, List[float], List[str]]:
    column_count = 4
    if language == "zh":
        instruction = "只修改第二列的文字并保存。生成新总结时，使用 --template 加上本文件路径；学习记录和判断规则不会被改动。常用文字排在前面。"
        note = "第一列是程序识别用的固定标识，不要修改；第二列是你可以随时修改的显示文字。"
        headers = ["固定标识（不要改）", "显示文字（可以改）", "它会出现在哪里", "分类"]
        common = "常用"
        advanced = "其他文字"
        title_default = "自定义文字"
    else:
        instruction = "Edit only the second column and save. Use this file with --template when generating a new summary; study records and assessment rules stay unchanged. Common labels come first."
        note = "The first column is a stable key for the generator. The second column is the text you may change."
        headers = ["Stable key (do not change)", "Display text (editable)", "Where it appears", "Group"]
        common = "Common"
        advanced = "Other labels"
        title_default = "Custom labels"
    rows: SheetRows = [
        _row([_label(labels, "custom_labels_title", title_default)] + [None] * 3, [STYLE_TITLE] * column_count),
        _row([instruction] + [None] * 3, [STYLE_FOCUS] * column_count),
        _row([note] + [None] * 3, [STYLE_NOTE] * column_count),
        [],
        _row(headers, [STYLE_HEADER] * column_count),
    ]
    for key in CUSTOMIZABLE_FIELDS:
        group = common if key in COMMON_CUSTOMIZABLE_FIELDS else advanced
        rows.append(_row([key, _label(labels, key, key), _field_purpose(key, language), group], [STYLE_TEXT, STYLE_FOCUS, STYLE_NOTE, STYLE_TEXT]))
    merges = ["A1:D1", "A2:D2", "A3:D3"]
    return rows, [31, 31, 48, 15], merges


def _template_snapshot(labels: Dict[str, str], language: str) -> Dict[str, Any]:
    placeholder = "[生成总结后会显示]" if language == "zh" else "[Shown after a real summary is generated]"
    status = "insufficient_data"
    return {
        "version": 1,
        "kind": "overall",
        "as_of": "2026-01-01",
        "period": {"kind": "overall", "start": None, "end": "2026-01-01", "key": "overall:2026-01-01"},
        "subject": _label(labels, "subject_placeholder", "你的学习主题" if language == "zh" else "Your subject"),
        "goal": _label(labels, "goal_placeholder", "你的可执行学习目标" if language == "zh" else "Your observable learning goal"),
        "data_quality": {"status": status, "reasons": []},
        "progress": {
            "period": {
                "session_count": 0,
                "excluded_session_count": 0,
                "actual_minutes": None,
                "planned_minutes": None,
                "planned_session_count": 0,
                "study_days": 0,
                "assessment_sample_count": 0,
                "review_attempt_count": 0,
                "learning_state": {
                    "energy": {"recorded_count": 0, "latest": None, "latest_date": None},
                    "distraction": {"recorded_count": 0, "latest": None, "latest_date": None},
                },
            },
            "stage": {"current_stage_title": _label(labels, "stage_placeholder", "当前阶段" if language == "zh" else "Current stage"), "current_stage_eligible": False},
            "overall": {"completed_stage_count": 0, "required_stage_count": 0},
        },
        "goal_evidence": {"status": "missing", "requirements": []},
        "learner_view": {
            "headline": _label(labels, "template_headline", "这里会先告诉你最重要的一句话结论。" if language == "zh" else "The main conclusion will appear here first."),
            "situation": _label(labels, "template_situation", "这里会解释你目前已经做到了什么，还缺哪一步。" if language == "zh" else "This explains what you can do and what is still missing."),
            "focus": _label(labels, "template_focus", "这里会放下一次最值得做的一件事。" if language == "zh" else "Your single most useful next action will appear here."),
            "why": _label(labels, "template_why", "这里会填写该计划的安排依据。" if language == "zh" else "This records the basis for the plan."),
            "proof": _label(labels, "template_proof", "这里会告诉你做完后需要留下什么结果。" if language == "zh" else "This describes the evidence to return."),
            "stage_line": placeholder,
            "stage_progress": placeholder,
            "goal_line": placeholder,
            "data_note": _label(labels, "template_data_note", "模板里的文字只是示例；生成真实总结后会替换成你的学习记录。" if language == "zh" else "These are examples; a real summary will replace them with your records."),
        },
        "evidence": {dimension: {"status": status, "sample_count": 0, "recent_mean": None, "delta": None} for dimension in ("understanding", "retrieval", "application", "transfer", "retention")},
        "reviews": {"due_items": [], "overdue_count": 0, "due_count": 0},
        "risks": [],
        "next_actions": [{"priority": "normal", "action": _label(labels, "template_action", "完成一次小练习，并把结果保存下来。" if language == "zh" else "Complete one small practice task and save the result."), "evidence": placeholder}],
    }


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _column_number(value: str) -> int:
    result = 0
    for character in value:
        if not character.isalpha():
            break
        result = result * 26 + ord(character.upper()) - 64
    return result


def _excel_serial(value: Any) -> Optional[float]:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return float((value - date(1899, 12, 30)).days)
    return None


def _xml_text(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _xml_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _cell_xml(row_number: int, column_number: int, value: Any, style: int) -> str:
    reference = "%s%d" % (_column_name(column_number), row_number)
    style_attr = ' s="%d"' % style if style else ""
    if value is None:
        return '<c r="%s"%s/>' % (reference, style_attr) if style else ""
    serial = _excel_serial(value)
    if serial is not None:
        return '<c r="%s"%s><v>%s</v></c>' % (reference, style_attr, serial)
    if isinstance(value, bool):
        return '<c r="%s"%s t="b"><v>%d</v></c>' % (reference, style_attr, 1 if value else 0)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return '<c r="%s"%s><v>%s</v></c>' % (reference, style_attr, value)
    return '<c r="%s"%s t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (reference, style_attr, _xml_text(value))


def _merge_bounds(reference: str) -> Optional[Tuple[int, int, int, int]]:
    match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", reference)
    if not match:
        return None
    return _column_number(match.group(1)), int(match.group(2)), _column_number(match.group(3)), int(match.group(4))


def _cell_width(row_number: int, column_number: int, widths: Sequence[float], merges: Sequence[str]) -> float:
    for reference in merges:
        bounds = _merge_bounds(reference)
        if bounds is None:
            continue
        start_col, start_row, end_col, end_row = bounds
        if start_row == row_number and start_col == column_number:
            return sum(widths[start_col - 1:end_col]) or 12.0
    return widths[column_number - 1] if column_number <= len(widths) and widths[column_number - 1] else 12.0


def _row_height(row_number: int, row: Sequence[Cell], widths: Sequence[float], merges: Sequence[str]) -> float:
    height = 18.0
    for column_number, (value, style) in enumerate(row, start=1):
        if style == STYLE_TITLE:
            height = max(height, 29.0)
        elif style == STYLE_SECTION:
            height = max(height, 23.0)
        if not isinstance(value, str) or not value:
            continue
        width = _cell_width(row_number, column_number, widths, merges)
        characters_per_line = max(int(width * 1.5), 8)
        line_count = sum(max(1, int(math.ceil(len(line) / characters_per_line))) for line in value.splitlines())
        height = max(height, min(110.0, 15.0 * line_count + 3.0))
    return height


def _worksheet_xml(rows: SheetRows, widths: Sequence[float], freeze_rows: int = 0, merges: Sequence[str] = ()) -> str:
    max_columns = max([len(row) for row in rows] + [len(widths), 1])
    max_rows = max(len(rows), 1)
    cols = "".join('<col min="%d" max="%d" width="%.1f" customWidth="1"/>' % (index, index, width) for index, width in enumerate(widths, start=1) if width)
    sheet_rows: List[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(_cell_xml(row_number, column_number, value, style) for column_number, (value, style) in enumerate(row, start=1) if value is not None or style)
        sheet_rows.append('<row r="%d" ht="%.1f" customHeight="1">%s</row>' % (row_number, _row_height(row_number, row, widths, merges), cells))
    view = '<sheetView showGridLines="0" workbookViewId="0">'
    if freeze_rows:
        view += '<pane ySplit="%d" topLeftCell="A%d" activePane="bottomLeft" state="frozen"/>' % (freeze_rows, freeze_rows + 1)
    view += "</sheetView>"
    merge_xml = '<mergeCells count="%d">%s</mergeCells>' % (len(merges), "".join('<mergeCell ref="%s"/>' % _xml_attr(value) for value in merges)) if merges else ""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="%s" xmlns:r="%s"><dimension ref="A1:%s%d"/><sheetViews>%s</sheetViews>'
            '<sheetFormatPr defaultRowHeight="18"/><cols>%s</cols><sheetData>%s</sheetData>%s'
            '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/></worksheet>'
            % (MAIN_NS, REL_NS, _column_name(max_columns), max_rows, view, cols, "".join(sheet_rows), merge_xml))


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="4">
    <numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>
    <numFmt numFmtId="165" formatCode="#,##0"/>
    <numFmt numFmtId="166" formatCode="#,##0.0"/>
    <numFmt numFmtId="167" formatCode="0.0%"/>
  </numFmts>
  <fonts count="4">
    <font><sz val="11"/><color rgb="FF1F2937"/><name val="Calibri"/></font>
    <font><b/><sz val="16"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FF1F2937"/><name val="Calibri"/></font>
  </fonts>
  <fills count="9">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD9EAF7"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE2F0D9"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFCE4D6"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF7F9FC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEAF3F8"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD0D7DE"/></left><right style="thin"><color rgb="FFD0D7DE"/></right><top style="thin"><color rgb="FFD0D7DE"/></top><bottom style="thin"><color rgb="FFD0D7DE"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="18">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="7" borderId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="3" borderId="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="3" borderId="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="7" borderId="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" applyAlignment="1"><alignment horizontal="left" vertical="top"/></xf>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" applyAlignment="1"><alignment horizontal="right" vertical="top"/></xf>
    <xf numFmtId="166" fontId="0" fillId="0" borderId="1" applyAlignment="1"><alignment horizontal="right" vertical="top"/></xf>
    <xf numFmtId="167" fontId="0" fillId="0" borderId="1" applyAlignment="1"><alignment horizontal="right" vertical="top"/></xf>
    <xf numFmtId="0" fontId="3" fillId="4" borderId="1" applyAlignment="1"><alignment horizontal="center" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" applyAlignment="1"><alignment horizontal="center" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="6" borderId="1" applyAlignment="1"><alignment horizontal="center" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="8" borderId="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="7" borderId="0" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def _sheet_names(language: str) -> List[str]:
    """Return learner-facing sheet names only."""
    if language == "zh":
        return ["结论与计划", "学习进展", "能力证据", "复习与后续计划"]
    return ["Conclusion and plan", "Learning progress", "Ability evidence", "Reviews and next plan"]


def summary_sheet_names(language: str) -> List[str]:
    """Return the current learner-facing sheet names for a language."""
    return _sheet_names(language)


def template_sheet_names(language: str) -> List[str]:
    """Return the developer template sheet names, including editable labels."""
    if language == "zh":
        return summary_sheet_names(language) + ["自定义文字"]
    return summary_sheet_names(language) + ["Custom labels"]


def _workbook_xml(sheet_names: Sequence[str]) -> str:
    sheets = "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_xml_attr(name), index, index) for index, name in enumerate(sheet_names, start=1))
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="%s" xmlns:r="%s"><fileVersion appName="xl"/><bookViews><workbookView/></bookViews><sheets>%s</sheets><calcPr calcMode="auto"/></workbook>' % (MAIN_NS, REL_NS, sheets)


def _workbook_rels(sheet_count: int) -> str:
    relationships = "".join('<Relationship Id="rId%d" Type="%s/worksheet" Target="worksheets/sheet%d.xml"/>' % (index, REL_NS, index) for index in range(1, sheet_count + 1))
    styles_id = sheet_count + 1
    relationships += '<Relationship Id="rId%d" Type="%s/styles" Target="styles.xml"/>' % (styles_id, REL_NS)
    return '<Relationships xmlns="%s">%s</Relationships>' % (PACKAGE_REL_NS, relationships)


def _content_types(sheet_count: int) -> str:
    overrides = '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    overrides += "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % index for index in range(1, sheet_count + 1))
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>%s</Types>' % overrides


def _root_rels() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="%s"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>' % PACKAGE_REL_NS


def _relationship_target(target: str) -> str:
    target = target.lstrip("/")
    return target if target.startswith("xl/") else posixpath.normpath(posixpath.join("xl", target))


def _cell_text(cell: ET.Element, shared_strings: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(item.text or "" for item in cell.findall(".//main:t", NAMESPACES))
    value = cell.find("main:v", NAMESPACES)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (ValueError, IndexError):
            return ""
    return value.text


def read_template_labels(template_path: Path) -> Dict[str, str]:
    """Read editable display labels from a generated or user-edited workbook."""
    path = Path(template_path).expanduser()
    if not path.is_file():
        raise ValueError("template does not exist: %s" % path)
    try:
        with zipfile.ZipFile(path) as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            relmap = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
            selected = None
            for sheet in workbook.findall("main:sheets/main:sheet", NAMESPACES):
                if sheet.attrib.get("name") in ("自定义文字", "Custom labels"):
                    selected = sheet
                    break
            if selected is None:
                raise ValueError("template is missing the custom-label sheet")
            rel_id = selected.attrib.get("{%s}id" % REL_NS)
            if not rel_id or rel_id not in relmap:
                raise ValueError("template custom-label sheet has no relationship")
            worksheet = ET.fromstring(archive.read(_relationship_target(relmap[rel_id])))
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = ["".join(item.text or "" for item in node.findall(".//main:t", NAMESPACES)) for node in shared_root.findall("main:si", NAMESPACES)]
            rows: Dict[int, Dict[int, str]] = {}
            for row in worksheet.findall(".//main:sheetData/main:row", NAMESPACES):
                row_number = int(row.attrib.get("r", "0"))
                values: Dict[int, str] = {}
                for cell in row.findall("main:c", NAMESPACES):
                    reference = cell.attrib.get("r", "")
                    match = re.match(r"[A-Za-z]+", reference)
                    column = _column_number(match.group(0)) if match else 0
                    if column:
                        values[column] = _cell_text(cell, shared_strings)
                rows[row_number] = values
            result: Dict[str, str] = {}
            for row_number, values in rows.items():
                if row_number < 5:
                    continue
                key = values.get(1, "").strip()
                value = values.get(2, "").strip()
                if key in CUSTOMIZABLE_FIELDS and value:
                    result[key] = value
            return result
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        raise ValueError("cannot read template %s: %s" % (path, exc)) from exc


def _write_workbook(snapshot: Dict[str, Any], labels: Dict[str, str], language: str, output_path: Path, template_mode: bool = False) -> List[str]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = template_sheet_names(language) if template_mode else summary_sheet_names(language)
    sheet_specs = [
        _overview_rows(snapshot, labels, language),
        _progress_rows(snapshot, labels, language),
        _evidence_rows(snapshot, labels, language),
        _next_rows(snapshot, labels, language),
    ]
    if template_mode:
        sheet_specs.append(_settings_rows(labels, language, template_mode))
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", _content_types(len(sheet_names)))
            archive.writestr("_rels/.rels", _root_rels())
            archive.writestr("xl/workbook.xml", _workbook_xml(sheet_names))
            archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheet_names)))
            archive.writestr("xl/styles.xml", _styles_xml())
            for index, (rows, widths, merges) in enumerate(sheet_specs, start=1):
                archive.writestr("xl/worksheets/sheet%d.xml" % index, _worksheet_xml(rows, widths, freeze_rows=4, merges=merges))
    except Exception:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    temporary_path.replace(output_path)
    return sheet_names


def write_summary_workbook(snapshot: Dict[str, Any], labels: Dict[str, str], language: str, output_path: Path) -> List[str]:
    """Write one learner-facing summary snapshot to an `.xlsx` file."""
    return _write_workbook(snapshot, labels, language, output_path, template_mode=False)


def write_template_workbook(output_path: Path, labels: Dict[str, str], language: str) -> List[str]:
    """Write an editable example workbook whose custom-label sheet can be reused."""
    return _write_workbook(_template_snapshot(labels, language), labels, language, output_path, template_mode=True)


__all__ = ["CUSTOMIZABLE_FIELDS", "read_template_labels", "summary_sheet_names", "template_sheet_names", "write_summary_workbook", "write_template_workbook"]
