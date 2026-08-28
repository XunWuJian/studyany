#!/usr/bin/env python3
"""Generate deterministic StudyAny learning summaries as Excel workbooks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python versions without zoneinfo
    ZoneInfo = None  # type: ignore

from study_analytics import MAX_RELIABLE_INTERRUPTED_MINUTES, analyze as analyze_analytics
from study_workbook import (
    read_template_labels,
    summary_sheet_names,
    write_summary_workbook,
    write_template_workbook,
)


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
WORKBOOK_SCHEMA_VERSION = 2


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
        "period_end": "Period end",
        "period": "Period",
        "subject": "Subject",
        "goal": "Goal",
        "days": "days",
        "actual": "Actual",
        "planned": "Planned / baseline",
        "rate": "Rate",
        "recent": "Recent mean",
        "previous": "Previous mean",
        "passing": "Passing",
        "trigger": "Eligible",
        "concept": "Concept",
        "priority": "Priority",
        "normal": "normal",
        "workbook": "Workbook",
        "workbook_sheets": "Sheets",
        "generated_count": "Generated summaries",
        "no_new_summaries": "No new summaries were generated.",
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
        "period_end": "周期结束",
        "period": "周期",
        "subject": "主题",
        "goal": "目标",
        "days": "天",
        "actual": "实际",
        "planned": "计划 / 基准",
        "rate": "比率",
        "recent": "近期均值",
        "previous": "前期均值",
        "passing": "通过数",
        "trigger": "达到条件",
        "concept": "概念",
        "priority": "优先级",
        "normal": "普通",
        "workbook": "Excel 文件",
        "workbook_sheets": "工作表",
        "generated_count": "生成总结数",
        "no_new_summaries": "没有新的总结需要生成。",
        "recorded": "已记录",
        "current": "当前",
        "completed": "已完成",
        "required": "必需",
        "missing_evidence": "缺少证据",
        "overdue_review_action": "优先完成逾期内容的复习，再安排新内容。",
        "collect_evidence_action": "补充一条独立、延迟或变式情境证据。",
        "stage_action": "完成当前阶段缺少的最小证明项。",
        "continue_action": "继续下一个路线目标，并保留下一次间隔复习。",
    },
}


# The raw analytics labels above remain available for the structured report
# contract. These presentation labels are intentionally written for a first-
# time learner; the custom-label sheet can override them without changing the
# underlying evidence or scoring rules.
FRIENDLY_LABELS = {
    "en": {
        "data_quality": "Record completeness",
        "overview": "Start here",
        "progress": "Learning progress",
        "stage_gates": "What is still needed before moving on",
        "evidence": "What you can do",
        "efficiency": "How your time was used",
        "reviews_risks": "Next steps and reminders",
        "next_actions": "Next steps",
        "period_learning": "What happened in this period",
        "stage_progress": "Stage progress",
        "overall_progress": "Overall progress",
        "goal_evidence": "Proof of the final goal",
        "sessions": "sessions",
        "study_time": "time spent",
        "study_days": "study days",
        "assessments": "practice checks",
        "review_attempts": "reviews",
        "required_stages": "required stages",
        "current_stage": "current stage",
        "actual_planned": "time recorded / planned",
        "delayed_pass_rate": "remembered after a delay",
        "transfer_rate": "worked on a new example",
        "retrieval": "Can you remember it without looking?",
        "understanding": "Can you explain it in your own words?",
        "application": "Can you do a similar task yourself?",
        "transfer": "Can you do it with a new example?",
        "retention": "Can you still do it after a few days?",
        "retrieval_gate": "Remember it without looking",
        "application_gate": "Do a similar task yourself",
        "transfer_gate": "Do a new example",
        "retention_gate": "Remember it after a delay",
        "retrieval_gate": "Remember it without looking",
        "application_gate": "Do a similar task yourself",
        "transfer_gate": "Do a new example",
        "retention_gate": "Remember it after a delay",
        "met": "ready",
        "not_ready": "not ready yet",
        "not_required": "not needed yet",
        "insufficient_data": "more records needed",
        "complete": "records are complete",
        "partial": "some records are incomplete",
        "measured": "recorded",
        "no_sessions": "no study in this period",
        "warn": "needs attention",
        "open": "to do",
        "unknown": "not known yet",
        "not_configured": "not set up",
        "satisfied": "done",
        "missing": "still missing",
        "no_history": "there are no study records",
        "none": "none",
        "minutes": "min",
        "period_reason": "records inside this period",
        "unknown_data": "not enough records to tell",
        "period_start": "Period",
        "period_end": "Period end",
        "period": "Period",
        "actual": "Recorded",
        "planned": "Planned",
        "rate": "Share",
        "recent": "Recent results",
        "previous": "Earlier results",
        "passing": "Passed",
        "trigger": "Ready",
        "concept": "Topic",
        "priority": "Priority",
        "normal": "normal",
        "missing_evidence": "missing proof",
        "overdue_review_action": "Review the overdue topic before starting something new.",
        "collect_evidence_action": "Do one small task without help, or try a changed example.",
        "stage_action": "Complete the smallest missing proof for the current stage.",
        "continue_action": "Continue the next small task and keep the next spaced review.",
        "start_here": "Start here",
        "one_sentence": "One-sentence conclusion",
        "your_situation": "Your current situation",
        "focus_now": "Your one priority",
        "why_this": "Why this comes first",
        "proof": "What to show next",
        "where_now": "Where you are",
        "learning_progress": "Learning progress",
        "data_note": "Record note",
        "ability_changes": "What you can do",
        "next_steps": "What to do next",
        "review_list": "Reviews to do",
        "item": "Item",
        "now": "Current result",
        "what_means": "What it means",
        "recorded_times": "Times recorded",
        "recent_performance": "Recent results",
        "change_simple": "Change",
        "goal_position": "Final goal",
        "time_spent": "Time spent",
        "study_sessions": "Study sessions",
        "checks_done": "Practice checks",
        "reviews_done": "Reviews",
        "next_action": "Next action",
        "overdue": "overdue",
        "not_due": "due today",
        "high": "high",
        "reminder": "Reminder",
        "recommendation": "Suggested action",
        "no_due_reviews": "No reviews are due",
        "no_risks": "No special reminders",
        "custom_labels_title": "Custom labels",
        "period_range": "Report range",
        "to": "to",
        "meaning_label": "In short",
        "data_note_label": "How to read this",
        "time_meaning": "Time shows effort, not proof that the skill is learned.",
        "sessions_meaning": "Sessions show whether practice is continuing.",
        "days_meaning": "Spreading practice over days helps memory.",
        "checks_meaning": "Checks show whether you can do the task.",
        "reviews_meaning": "A delayed review shows whether you still remember.",
        "overall_stage_note": "Based on stage requirements, not time spent",
        "goal_note": "A result is needed, not just exposure",
        "evidence_intro": "This is not one total score. It looks at five different kinds of learning.",
        "ability_changes_note": "Read the words in the second column first; the percentages are supporting detail.",
        "how_to_read": "How to read this",
        "evidence_explanation": "One correct answer proves only that attempt. Delayed and changed-example work makes the conclusion stronger.",
        "review_meaning": "A spaced review checks whether the idea stayed with you.",
        "risk_note": "This is a next-step reminder, not a judgment of you.",
        "no_due_reviews_note": "Continue the current small practice task.",
        "overdue_note": "Do this before adding new material.",
        "normal_note": "Complete it as planned.",
        "stage_not_ready_short": "more proof is needed",
        "stage_ready_short": "ready to prepare for the next stage",
        "risk_data_quality": "Some records are incomplete, so part of the summary is only a reference.",
        "risk_stage_gate": "The current stage still needs its entry proof.",
        "risk_review_backlog": "A topic has reached its review date.",
        "risk_fragile_progress": "Recent work looks okay, but new-example or delayed proof is missing.",
        "risk_stalled_progress": "Recent records have not changed much; use a smaller task.",
        "risk_delayed_decay": "A previously correct topic was missed after a delay.",
        "risk_overlong_session": "One study block was unusually long; split the next one.",
        "risk_overload_risk": "Time and learning evidence both need attention.",
        "records_good": "The available records are usable for this summary.",
        "not_enough_records": "There are not enough records yet to make a useful conclusion.",
        "no_records_headline": "There is not enough learning evidence yet. Start with one small task that leaves a result.",
        "template_headline": "The main conclusion will appear here first.",
        "template_situation": "This explains what you can do and what is still missing.",
        "template_focus": "Your single most useful next action will appear here.",
        "template_why": "This explains why that action comes first.",
        "template_proof": "This describes the evidence to return.",
        "template_data_note": "These are examples; a real summary will replace them with your records.",
        "template_action": "Complete one small practice task and save the result.",
        "subject_placeholder": "Your subject",
        "goal_placeholder": "Your observable learning goal",
        "stage_placeholder": "Current stage",
        "stage_not_configured": "No stage requirements are set",
        "gate_satisfied": "Enough records are present",
        "gate_insufficient": "No record of this kind yet",
        "gate_still_needed": "but more is needed",
        "gate_missing": "More records are needed",
        "missing_topics": "Focus",
        "no_repeated_failures_meaning": "Avoid repeated review failures",
        "delayed_rate_meaning": "A higher rate means more topics stayed usable after a delay.",
        "review_rate_missing": "More delayed-review records are needed",
        "transfer_rate_meaning": "A new example checks understanding rather than memorization.",
        "transfer_rate_missing": "No new-example practice is recorded yet",
        "risk_detail_default": "This needs another check in the next practice.",
    },
    "zh": {
        "data_quality": "记录完整度",
        "overview": "结论与计划",
        "progress": "学习进度",
        "stage_gates": "阶段完成条件",
        "evidence": "能力证据",
        "efficiency": "学习投入与复习情况",
        "reviews_risks": "下一步和需要留意的事",
        "next_actions": "下一步行动",
        "period_learning": "本期学习记录",
        "stage_progress": "阶段进度",
        "overall_progress": "总进度",
        "goal_evidence": "最终目标的成果证明",
        "sessions": "次",
        "study_time": "花费时间",
        "study_days": "学习天数",
        "assessments": "练习或检查",
        "review_attempts": "复习",
        "required_stages": "个必需阶段",
        "current_stage": "当前阶段",
        "actual_planned": "记录时间 / 计划时间",
        "delayed_pass_rate": "间隔复习结果",
        "transfer_rate": "变换题目练习结果",
        "retrieval": "不看资料回忆",
        "understanding": "理解表达",
        "application": "独立完成",
        "transfer": "变换题目",
        "retention": "间隔后保持",
        "retrieval_gate": "不看资料完成回忆",
        "application_gate": "独立完成类似练习",
        "transfer_gate": "变换题目后完成练习",
        "retention_gate": "间隔后再次完成练习",
        "retrieval_gate": "不看资料想起来",
        "application_gate": "自己完成类似练习",
        "transfer_gate": "换个例子完成练习",
        "retention_gate": "隔一段时间后仍然记得",
        "met": "可以进入",
        "not_ready": "还不能进入",
        "not_required": "暂不要求",
        "insufficient_data": "记录还不够",
        "complete": "记录基本完整",
        "partial": "有些记录不完整",
        "measured": "有记录",
        "no_sessions": "这段时间没有学习",
        "warn": "需要留意",
        "open": "等你处理",
        "unknown": "暂时不知道",
        "not_configured": "还没有设置",
        "satisfied": "已经做到",
        "missing": "还缺少",
        "no_history": "还没有学习记录",
        "none": "无",
        "minutes": "分钟",
        "period_reason": "统计这个时间段内的记录",
        "unknown_data": "记录还不够，暂时无法判断",
        "period_start": "总结范围",
        "period_end": "周期结束",
        "period": "周期",
        "actual": "记录到的",
        "planned": "计划的",
        "rate": "占比",
        "recent": "最近表现",
        "previous": "之前表现",
        "passing": "做对",
        "trigger": "是否达到",
        "concept": "学习内容",
        "priority": "重要程度",
        "normal": "正常安排",
        "missing_evidence": "缺少证明",
        "overdue_review_action": "先复习已经到期的内容，再开始新内容。",
        "collect_evidence_action": "做一项不看提示的小练习，或换个例子再做一次。",
        "stage_action": "先完成当前阶段最小的缺失证明。",
        "continue_action": "继续下一个小练习，并保留下一次间隔复习。",
        "start_here": "结论与计划",
        "one_sentence": "一句话结论",
        "your_situation": "当前情况",
        "focus_now": "优先计划",
        "why_this": "安排依据",
        "proof": "预期结果",
        "where_now": "学习目标与阶段进度",
        "learning_progress": "学习进度",
        "data_note": "数据说明",
        "ability_changes": "能力证据",
        "next_steps": "复习与后续计划",
        "review_list": "复习安排",
        "item": "项目",
        "now": "当前情况",
        "what_means": "判断依据",
        "recorded_times": "记录数量",
        "recent_performance": "最近表现",
        "change_simple": "变化",
        "goal_position": "最终目标",
        "time_spent": "花费时间",
        "study_sessions": "学习次数",
        "checks_done": "练习或检查",
        "reviews_done": "复习次数",
        "next_action": "下一项计划",
        "overdue": "已经到期",
        "not_due": "今天到期",
        "high": "高优先级",
        "reminder": "需要留意",
        "recommendation": "建议",
        "no_due_reviews": "目前没有到期复习",
        "no_risks": "目前没有发现需要特别留意的地方",
        "custom_labels_title": "自定义文字",
        "period_range": "总结范围",
        "to": "至",
        "meaning_label": "判断说明",
        "data_note_label": "统计说明",
        "time_meaning": "时间只能说明投入过，不能单独证明已经学会。",
        "sessions_meaning": "次数可以看出是否持续学习。",
        "days_meaning": "分开几天学习，更有助于记住。",
        "checks_meaning": "练习和检查用来判断能不能自己做出来。",
        "reviews_meaning": "隔一段时间再做，才能确认是否记住。",
        "overall_stage_note": "按阶段要求判断，不按学习时间判断",
        "goal_note": "需要成果证明，不只是看过课程",
        "evidence_intro": "各项能力分别列出当前表现及其记录依据。",
        "ability_changes_note": "当前情况和记录数量是主要依据，百分比仅作补充。",
        "how_to_read": "能力判断说明",
        "evidence_explanation": "稳定掌握需要多次不同形式的记录确认，例如不看资料、变换题目和间隔复习。",
        "review_meaning": "间隔后再次完成，用于确认是否记住。",
        "risk_note": "这是对下一步的提醒，不是对人的评价。",
        "no_due_reviews_note": "继续完成当前阶段的小练习。",
        "overdue_note": "先完成这项，再开始新内容。",
        "normal_note": "按计划完成即可。",
        "stage_not_ready_short": "还需要更多练习证明",
        "stage_ready_short": "可以准备下一阶段",
        "risk_data_quality": "有些学习记录不完整，部分数字只能作为参考。",
        "risk_stage_gate": "当前阶段还缺少进入下一阶段的证明。",
        "risk_review_backlog": "有内容到了应该复习的时间。",
        "risk_fragile_progress": "最近会做，但还缺少换题或隔天复习来确认。",
        "risk_stalled_progress": "最近几次记录没有明显变化，可以换一个更小的练习。",
        "risk_delayed_decay": "之前会做，但隔一段时间后又忘了，需要缩短复习间隔。",
        "risk_overlong_session": "有一次学习时间明显偏长，下一次可以拆成小段。",
        "risk_overload_risk": "投入时间和学习表现同时出现需要留意的信号。",
        "records_good": "现有记录可以支持这次总结。",
        "not_enough_records": "记录还不够，暂时无法得出可靠结论。",
        "no_records_headline": "目前还没有足够的学习证明，先完成一项会留下结果的小练习。",
        "template_headline": "这里会先告诉你最重要的一句话结论。",
        "template_situation": "这里会解释你目前已经做到什么，还缺哪一步。",
        "template_focus": "这里会放下一次最值得做的一件事。",
        "template_why": "这里会填写该计划的安排依据。",
        "template_proof": "这里会告诉你做完后需要留下什么结果。",
        "template_data_note": "模板里的文字只是示例；生成真实总结后会替换成你的学习记录。",
        "template_action": "完成一次小练习，并把结果保存下来。",
        "subject_placeholder": "你的学习主题",
        "goal_placeholder": "你的可执行学习目标",
        "stage_placeholder": "当前阶段",
        "stage_not_configured": "还没有设置阶段要求",
        "gate_satisfied": "已经有足够记录",
        "gate_insufficient": "还没有这类记录",
        "gate_still_needed": "但还不够",
        "gate_missing": "还需要记录",
        "missing_topics": "重点",
        "no_repeated_failures_meaning": "复习时不要连续失败",
        "delayed_rate_meaning": "这个比例越可靠，说明隔几天后仍能做对的记录越多。",
        "review_rate_missing": "还没有足够的间隔复习记录",
        "transfer_rate_meaning": "换例子可以确认你是在理解，而不是只记住原题。",
        "transfer_rate_missing": "还没有换例子练习记录",
        "risk_detail_default": "这项内容需要在下一次练习中继续确认",
    },
}


def _presentation_labels(language: str) -> Dict[str, str]:
    labels = dict(LABELS[language])
    labels.update(FRIENDLY_LABELS[language])
    if language == "zh":
        labels.update({
            "understanding_meaning": "根据自己的理解进行说明",
            "retrieval_meaning": "不看资料完成回忆",
            "application_meaning": "独立完成类似练习",
            "transfer_meaning": "变换题目后继续完成",
            "retention_meaning": "间隔后再次完成练习",
            "continue_reason": "保持下一次练习小而明确，才能继续留下新的证明。",
            "continue_proof": "把练习结果或解释交回来，作为下一次检查的依据。",
            "building": "正在变好",
            "consolidating": "正在巩固",
            "fragile": "会做，但还不够稳定",
            "stalled": "最近没有明显变化",
            "recovering": "正在找回状态",
        })
    else:
        labels.update({
            "understanding_meaning": "Explain the idea in your own words",
            "retrieval_meaning": "Recall the idea without looking",
            "application_meaning": "Complete a similar task independently",
            "transfer_meaning": "Complete a changed task",
            "retention_meaning": "Complete the task again after a delay",
            "continue_reason": "Keep the next practice small and observable so it creates new proof.",
            "continue_proof": "Return the practice result or explanation for the next check.",
            "building": "building",
            "consolidating": "consolidating",
            "fragile": "works, but not stable yet",
            "stalled": "no clear recent change",
            "recovering": "recovering",
        })
    if language == "zh":
        # Keep the visible report conversational. Internal keys and scores
        # remain unchanged; these are only the words shown to a learner.
        labels.update({
            "overview": "先看结论",
            "progress": "学习进度",
            "stage_gates": "走下一步前还要会什么",
            "evidence": "你现在会什么",
            "efficiency": "投入和记忆情况",
            "period_learning": "这段时间做了什么",
            "stage_progress": "学习路线走到哪",
            "overall_progress": "总路线进度",
            "goal_evidence": "大目标完成情况",
            "assessments": "练习次数",
            "review_attempts": "隔段复习次数",
            "required_stages": "个学习步骤",
            "current_stage": "现在正在学",
            "actual_planned": "实际花费 / 原计划",
            "delayed_pass_rate": "隔一段时间还记得",
            "retrieval": "想起来",
            "understanding": "讲明白",
            "application": "自己做",
            "transfer": "换例子",
            "retention": "隔天记住",
            "retrieval_gate": "不看资料回忆",
            "application_gate": "自己完成练习",
            "transfer_gate": "换个例子练习",
            "retention_gate": "隔一段时间再做",
            "met": "可以进入下一步",
            "not_ready": "还不能进入下一步",
            "complete": "记录够用",
            "building": "开始会了",
            "consolidating": "还在记牢",
            "fragile": "会做，但还不稳定",
            "stalled": "最近没变化",
            "recovering": "正在找回来",
            "start_here": "结论与计划",
            "focus_now": "优先计划",
            "proof": "预期结果",
            "where_now": "学习目标与阶段进度",
            "data_note": "记录是否够用",
            "ability_changes": "能力证据",
            "review_list": "该复习的内容",
            "item": "项目",
            "now": "当前情况",
            "what_means": "判断依据",
            "recorded_times": "记录数量",
            "recent_performance": "最近表现",
            "change_simple": "和之前相比",
            "goal_position": "离大目标还有多远",
            "time_spent": "花了多少时间",
            "checks_done": "做了几次练习",
            "reviews_done": "隔段复习了几次",
            "next_action": "下一步",
            "not_due": "今日到期",
            "high": "高优先级",
            "meaning_label": "判断说明",
            "data_note_label": "统计说明",
            "time_meaning": "时间只能说明投入，不代表已经会了。",
            "sessions_meaning": "次数可以看出有没有持续练习。",
            "days_meaning": "分开几天学习，更有助于记住。",
            "checks_meaning": "练习用来判断能不能自己做出来。",
            "reviews_meaning": "隔一段时间再做，才能确认是否记住。",
            "overall_stage_note": "按会不会做来判断，不按花了多少时间",
            "goal_note": "要看得见的结果，不能只看过",
            "evidence_intro": "各项能力分别列出当前表现及其记录依据。",
            "ability_changes_note": "当前情况和记录数量是主要依据，百分比仅作补充。",
            "evidence_explanation": "稳定掌握需要多次不同形式的记录确认，例如不看资料、变换题目和间隔复习。",
            "review_meaning": "间隔后再次完成，用于确认是否记住。",
            "stage_not_ready_short": "还需要更多练习结果",
            "stage_ready_short": "可以准备下一步",
        })
    labels.update(
        {
            "title": "StudyAny 学习情况报告",
            "period_week": "周度学习报告",
            "period_month": "月度学习报告",
            "period_stage": "阶段进展报告",
            "period_overall": "总体进展报告",
            "overview": "结论与计划",
            "progress": "学习进展",
            "stage_gates": "阶段完成条件",
            "evidence": "能力证据",
            "efficiency": "学习投入与复习情况",
            "period_learning": "本期学习记录",
            "stage_progress": "阶段进度",
            "overall_progress": "总体进度",
            "goal_evidence": "学习目标完成情况",
            "actual_planned": "实际时间与计划时间",
            "delayed_pass_rate": "间隔复习结果",
            "transfer_rate": "变换题目练习结果",
            "retrieval": "不看资料回忆",
            "understanding": "理解表达",
            "application": "独立完成",
            "transfer": "变换题目",
            "retention": "间隔后保持",
            "retrieval_gate": "不看资料完成回忆",
            "application_gate": "独立完成类似练习",
            "transfer_gate": "变换题目后完成练习",
            "retention_gate": "间隔后再次完成练习",
            "start_here": "结论与计划",
            "one_sentence": "核心结论",
            "your_situation": "当前情况",
            "focus_now": "优先计划",
            "why_this": "安排依据",
            "proof": "预期结果",
            "where_now": "学习目标与阶段进度",
            "data_note": "数据说明",
            "data_note_label": "统计说明",
            "ability_changes": "能力证据",
            "evidence_intro": "各项能力分别列出当前表现及其记录依据。",
            "ability_changes_note": "当前情况和记录数量是主要依据，百分比仅作补充。",
            "how_to_read": "能力判断说明",
            "evidence_explanation": "稳定掌握需要多次不同形式的记录确认，例如不看资料、变换题目和间隔复习。",
            "next_steps": "复习与后续计划",
            "review_list": "复习安排",
            "item": "项目",
            "now": "当前情况",
            "what_means": "判断依据",
            "recorded_times": "记录数量",
            "recent_performance": "近期结果",
            "change_simple": "变化情况",
            "time_spent": "实际学习时间",
            "planned_time": "计划学习时间",
            "planned_time_note": "用于比较计划与实际执行情况",
            "study_sessions": "学习次数",
            "checks_done": "练习记录",
            "reviews_done": "复习记录",
            "goal_position": "学习目标",
            "goal_note": "需要可检查的成果记录",
            "overall_stage_note": "依据阶段完成条件判断",
            "time_meaning": "用于查看计划执行情况，不能单独判断是否掌握。",
            "sessions_meaning": "用于查看学习安排是否连续。",
            "days_meaning": "用于查看学习是否分布在不同日期。",
            "checks_meaning": "用于查看是否能独立完成目标任务。",
            "reviews_meaning": "用于查看一段时间后是否仍能完成。",
            "meaning_label": "判断说明",
            "reminder": "关注事项",
            "recommendation": "计划建议",
            "no_due_reviews": "当前无待复习内容",
            "no_risks": "当前无其他重点事项",
            "learning_state": "学习状态记录（辅助）",
            "energy": "精力状态",
            "distraction": "专注情况",
            "record_count": "记录数量",
            "latest_record": "最近一次明确填写",
            "state_recorded": "已记录",
            "state_not_recorded": "暂无明确记录",
            "state_explicit_note": "仅展示用户明确填写的内容，不根据成绩、次数或文字语气推断",
            "state_latest_note": "显示最近一次明确填写的内容",
            "overdue": "已到期",
            "not_due": "今日到期",
            "high": "高优先级",
            "normal": "常规安排",
            "unknown": "暂无数据",
            "not_configured": "尚未设置",
            "no_sessions": "本期无学习记录",
            "unknown_data": "记录不足，暂时无法判断",
        }
        if language == "zh"
        else {
            "title": "StudyAny Learning Progress Report",
            "period_week": "Weekly Learning Report",
            "period_month": "Monthly Learning Report",
            "period_stage": "Stage Progress Report",
            "period_overall": "Overall Progress Report",
            "overview": "Conclusion and plan",
            "progress": "Learning progress",
            "stage_gates": "Stage completion conditions",
            "evidence": "Ability evidence",
            "efficiency": "Study investment and retention",
            "period_learning": "Learning records in this period",
            "stage_progress": "Stage progress",
            "overall_progress": "Overall progress",
            "goal_evidence": "Progress toward the learning goal",
            "actual_planned": "Recorded time and planned time",
            "delayed_pass_rate": "Delayed review result",
            "transfer_rate": "Result with a changed task",
            "retrieval": "Recall",
            "understanding": "Explanation",
            "application": "Independent application",
            "transfer": "Application with a changed task",
            "retention": "Delayed review retention",
            "retrieval_gate": "Recall without looking",
            "application_gate": "Complete a similar task independently",
            "transfer_gate": "Complete a changed task",
            "retention_gate": "Complete the task again after a delay",
            "start_here": "Conclusion and plan",
            "one_sentence": "Main conclusion",
            "your_situation": "Current situation",
            "focus_now": "Priority plan",
            "why_this": "Basis for the plan",
            "proof": "Expected result",
            "where_now": "Learning goal and stage progress",
            "data_note": "Data notes",
            "data_note_label": "Statistical notes",
            "ability_changes": "Ability evidence",
            "evidence_intro": "Review ability by task type; more records make the judgment stronger.",
            "ability_changes_note": "Read the current situation and record count first; percentages are supporting detail.",
            "how_to_read": "Ability evidence notes",
            "evidence_explanation": "Stable ability needs more than one kind of record, such as recall without looking, changed tasks, or delayed review.",
            "next_steps": "Reviews and next plan",
            "review_list": "Review plan",
            "item": "Item",
            "now": "Current situation",
            "what_means": "Basis for the judgment",
            "recorded_times": "Recorded entries",
            "recent_performance": "Recent results",
            "change_simple": "Change",
            "time_spent": "Recorded study time",
            "planned_time": "Planned study time",
            "planned_time_note": "Compare recorded time with planned time",
            "study_sessions": "Study sessions",
            "checks_done": "Practice records",
            "reviews_done": "Review records",
            "goal_position": "Learning goal",
            "goal_note": "A checkable result is needed",
            "overall_stage_note": "Based on stage completion conditions",
            "time_meaning": "Used to observe plan execution; it does not by itself show mastery.",
            "sessions_meaning": "Used to observe continuity of the study plan.",
            "days_meaning": "Used to observe whether the plan is spread across dates.",
            "checks_meaning": "Used to check whether the goal task can be completed.",
            "reviews_meaning": "Used to observe whether the task can still be completed after time passes.",
            "meaning_label": "Evidence note",
            "reminder": "Items to monitor",
            "recommendation": "Plan recommendation",
            "no_due_reviews": "No review is currently due",
            "no_risks": "No other priority items",
            "learning_state": "Recorded learning conditions (secondary)",
            "energy": "Energy",
            "distraction": "Distraction",
            "record_count": "Recorded entries",
            "latest_record": "Latest explicit entry",
            "state_recorded": "Recorded",
            "state_not_recorded": "No explicit entry",
            "state_explicit_note": "Shows only what the learner explicitly recorded; it does not infer a state from scores, frequency, or wording.",
            "state_latest_note": "The latest explicitly recorded value",
        }
    )
    return labels


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
    excluded_session_count = 0
    excluded_session_ids: List[str] = []
    unknown_duration = 0
    unknown_timestamp = 0
    actual = 0.0
    planned = 0.0
    measured_count = 0
    planned_count = 0
    study_dates = set()
    state_entries: Dict[str, List[Dict[str, Any]]] = {"energy": [], "distraction": []}
    for source_index, row in enumerate(sessions):
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
        duration = _number(row.get("duration_min"), minimum=0)
        if row.get("status") == "interrupted" and duration is not None and duration > MAX_RELIABLE_INTERRUPTED_MINUTES:
            excluded_session_count += 1
            if row.get("session_id"):
                excluded_session_ids.append(str(row.get("session_id")))
            reasons.append("interrupted_duration_unreliable")
            continue
        included += 1
        study_dates.add(observed)
        for field in state_entries:
            value = row.get(field)
            if value is not None and value != "":
                state_entries[field].append(
                    {"value": value, "date": observed.isoformat(), "source_index": source_index}
                )
        if duration is None:
            unknown_duration += 1
        else:
            actual += duration
            measured_count += 1
        planned_value = _number(row.get("planned_minutes"), minimum=0)
        if planned_value is not None:
            planned += planned_value
            planned_count += 1
    if unknown_duration:
        reasons.append("unknown_duration")
    if unknown_timestamp:
        reasons.append("unknown_session_timestamp")
    if measured_count and not unknown_duration and not unknown_timestamp:
        measurement_status = "measured"
        actual_value: Optional[float] = _round(actual, 1)
    elif included or unknown_timestamp:
        measurement_status = "unknown"
        actual_value = None
    else:
        measurement_status = "no_sessions"
        actual_value = 0.0
    learning_state: Dict[str, Dict[str, Any]] = {}
    for field, entries in state_entries.items():
        ordered = sorted(entries, key=lambda item: (item.get("date") or "", item.get("source_index", 0)))
        latest = ordered[-1] if ordered else None
        learning_state[field] = {
            "recorded_count": len(ordered),
            "latest": latest.get("value") if latest else None,
            "latest_date": latest.get("date") if latest else None,
        }
    return {
        "session_count": included,
        "excluded_session_count": excluded_session_count,
        "excluded_session_ids": excluded_session_ids,
        "measured_session_count": measured_count,
        "unknown_duration_count": unknown_duration,
        "unknown_timestamp_count": unknown_timestamp,
        "study_days": len(study_dates),
        "study_dates": sorted(item.isoformat() for item in study_dates),
        "measurement_status": measurement_status,
        "actual_minutes": actual_value,
        "planned_minutes": _round(planned, 1) if planned_count else None,
        "planned_session_count": planned_count,
        "learning_state": learning_state,
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
        "concept_titles": {
            str(row.get("concept_id")): row.get("title")
            for row in concepts
            if isinstance(row, dict) and row.get("concept_id") in concept_ids and row.get("title")
        },
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
            "excluded_session_count": period_time.get("excluded_session_count", 0),
            "actual_minutes": period_time.get("actual_minutes"),
            "planned_minutes": period_time.get("planned_minutes"),
            "planned_session_count": period_time.get("planned_session_count", 0),
            "study_days": period_time.get("study_days", 0),
            "assessment_sample_count": len(assessment_samples),
            "review_attempt_count": len(review_samples),
            "learning_state": period_time.get("learning_state") or {},
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
    return {
        "actual_vs_planned": actual_planned,
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
        or reason == "interrupted_duration_unreliable"
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
                "action": _presentation_label(language, "overdue_review_action", "Review overdue material before adding new content."),
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
                "action": _presentation_label(language, "stage_action", "Complete the smallest missing stage evidence."),
                "evidence": current.get("id"),
            }
        )
    if not actions:
        evidence = snapshot.get("evidence") or {}
        if any(value.get("status") in ("fragile", "stalled", "insufficient_data") for value in evidence.values()):
            actions.append(
                {
                    "priority": "normal",
                    "action": _presentation_label(language, "collect_evidence_action", "Collect one more evidence item."),
                    "evidence": ", ".join(
                        dimension for dimension, value in evidence.items() if value.get("status") in ("fragile", "stalled", "insufficient_data")
                    ),
                }
            )
        else:
            actions.append(
                {
                    "priority": "normal",
                    "action": _presentation_label(language, "continue_action", "Continue with the next small task."),
                    "evidence": snapshot.get("progress", {}).get("stage", {}).get("current_stage_id"),
                }
            )
    return risks, actions


def _presentation_label(language: str, key: str, default: str) -> str:
    return FRIENDLY_LABELS.get(language, {}).get(key) or LABELS.get(language, {}).get(key) or default


def _current_stage_row(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    projection = snapshot.get("stage_projection") or {}
    current = projection.get("current_stage") or {}
    current_id = current.get("id")
    for row in projection.get("stages") or []:
        if isinstance(row, dict) and row.get("stage_id") == current_id:
            return row
    return {}


def _missing_evidence_text(snapshot: Dict[str, Any], language: str) -> str:
    stage = _current_stage_row(snapshot)
    missing_kind = stage.get("first_missing")
    labels = _presentation_labels(language)
    defaults = {
        "retrieval": "先做一次不看资料的回忆",
        "application": "先做一次自己完成的类似练习",
        "transfer": "先做一次换例子或换场景的练习",
        "retention": "先做一次隔一段时间后的复习",
        "no_repeated_failures": "先完成一次没有连续失败的复习",
    }
    if not missing_kind:
        return _presentation_label(language, "collect_evidence_action", "Collect one more evidence item.")
    gate = next((item for item in stage.get("gates") or [] if item.get("kind") == missing_kind), {})
    if gate.get("status") == "insufficient_data":
        base = {
            "retrieval": "还没有不看资料回忆的记录",
            "application": "还没有自己完成练习的记录",
            "transfer": "还没有换例子练习的记录",
            "retention": "还没有隔一段时间复习的记录",
            "no_repeated_failures": "还没有足够的复习记录",
        }.get(missing_kind, defaults.get(missing_kind, "还没有这类练习的记录"))
    else:
        base = defaults.get(missing_kind, "还缺少一项练习证明")
    titles = [
        (stage.get("concept_titles") or {}).get(concept_id)
        for concept_id in gate.get("missing_concepts") or []
        if (stage.get("concept_titles") or {}).get(concept_id)
    ]
    if titles:
        return "%s（重点：%s）" % (base, "、".join(str(title) for title in titles[:3]))
    return base


def _friendly_data_note(snapshot: Dict[str, Any], language: str) -> str:
    quality = snapshot.get("data_quality") or {}
    reasons = quality.get("reasons") or []
    period = (snapshot.get("progress") or {}).get("period") or {}
    excluded_count = period.get("excluded_session_count", 0) or 0
    reason_text = {
        "unknown_duration": "有些学习记录没有完整时间，所以总时间只能参考",
        "unknown_session_timestamp": "有些学习记录没有有效日期，所以时间段统计只能参考",
        "no_study_records": "目前还没有学习记录",
        "invalid_timezone": "时区设置有问题，时间段可能需要重新确认",
        "timezone_unavailable": "当前环境无法识别时区，时间段可能需要重新确认",
    }
    if language != "zh":
        reason_text = {
            "unknown_duration": "Some study records have no complete duration, so total time is only a reference",
            "unknown_session_timestamp": "Some study records have no valid date, so period totals are only a reference",
            "no_study_records": "No study records are available",
            "invalid_timezone": "The timezone setting is invalid, so the period may need review",
            "timezone_unavailable": "The timezone is unavailable, so the period may need review",
        }
    fallback = "部分记录格式不完整" if language == "zh" else "Some records are incomplete"
    readable = [reason_text.get(reason, fallback) for reason in reasons if reason != "interrupted_duration_unreliable"]
    if excluded_count:
        count_text = "一" if excluded_count == 1 else str(excluded_count)
        excluded_text = (
            "有%s条明显中断的记录未计入学习次数、学习天数、计划时间或实际学习时间，仅保留为数据说明"
            % count_text
            if language == "zh"
            else "%s clearly interrupted record(s) were excluded from session count, study days, planned time, and actual time; they are kept only as a data note"
            % excluded_count
        )
        readable.insert(0, excluded_text)
    if readable:
        return ("；".join(dict.fromkeys(readable)) + "。") if language == "zh" else ("; ".join(dict.fromkeys(readable)) + ".")
    if quality.get("status") == "complete":
        return _presentation_label(language, "records_good", "The available records are usable for this summary.")
    if quality.get("status") == "partial":
        return _presentation_label(language, "partial", "Some records are incomplete") + "。"
    return _presentation_label(language, "not_enough_records", "More records are needed before a useful conclusion can be made.")


def _learner_view(snapshot: Dict[str, Any], language: str) -> Dict[str, str]:
    """Turn the structured snapshot into a short, decision-oriented explanation."""
    labels = _presentation_labels(language)
    progress = snapshot.get("progress") or {}
    period = progress.get("period") or {}
    stage = progress.get("stage") or {}
    overall = progress.get("overall") or {}
    goal_evidence = snapshot.get("goal_evidence") or {}
    reviews = snapshot.get("reviews") or {}
    evidence = snapshot.get("evidence") or {}
    stage_row = _current_stage_row(snapshot)
    stage_title = stage.get("current_stage_title") or "当前正在学的部分"
    missing_text = _missing_evidence_text(snapshot, language)
    has_records = bool(
        period.get("session_count")
        or period.get("assessment_sample_count")
        or period.get("review_attempt_count")
    )
    goal_status = goal_evidence.get("status")
    if not has_records:
        headline = _presentation_label(language, "no_records_headline", "There is not enough learning evidence yet.")
    elif stage_title and not stage.get("current_stage_eligible") and stage_row:
        headline = "你已经在“%s”做过不少练习，但还不能进入下一部分。最关键的是：%s。" % (stage_title, missing_text) if language == "zh" else "You have practiced %s, but you are not ready to move on yet. The most important missing proof is: %s." % (stage_title, missing_text)
    elif stage.get("current_stage_eligible"):
        headline = "当前阶段的进入条件已经达到，可以准备下一阶段。" if language == "zh" else "The current stage has enough proof; you can prepare for the next stage."
    elif goal_status == "satisfied":
        headline = "目前已有成果证明最终目标，可以进入保持和应用阶段。" if language == "zh" else "There is enough result evidence for the final goal; keep applying and retaining it."
    else:
        headline = "你已经开始积累学习记录，下一步要把记录变成可检查的成果。" if language == "zh" else "You have started building records; the next step is to turn them into checkable results."

    weak_names: List[str] = []
    improving_names: List[str] = []
    for dimension in DIMENSIONS:
        value = evidence.get(dimension) or {}
        status = value.get("status")
        if status in ("fragile", "stalled", "insufficient_data"):
            weak_names.append(labels.get(dimension) or dimension)
        elif status in ("building", "recovering"):
            improving_names.append(labels.get(dimension) or dimension)
    activity = "%s 次练习，%s 次复习" % (period.get("assessment_sample_count", 0), period.get("review_attempt_count", 0)) if language == "zh" else "%s practice checks and %s reviews" % (period.get("assessment_sample_count", 0), period.get("review_attempt_count", 0))
    if weak_names:
        situation = "%s。已经有练习和复习记录，但还需要继续确认：%s。" % (activity, "、".join(weak_names[:3])) if language == "zh" else "%s. Practice and review records exist, but these areas still need checking: %s." % (activity, ", ".join(weak_names[:3]))
    elif improving_names:
        situation = "%s。最近有变化的是：%s。" % (activity, "、".join(improving_names[:3])) if language == "zh" else "%s. Recent improvement is visible in %s." % (activity, ", ".join(improving_names[:3]))
    elif has_records:
        situation = "%s。当前记录还不足以说明已经稳定掌握。" % activity if language == "zh" else "%s. The current records do not yet show stable mastery."
    else:
        situation = _presentation_label(language, "not_enough_records", "More records are needed before a useful conclusion can be made.")

    due_items = reviews.get("due_items") or []
    if due_items:
        first_title = due_items[0].get("title") or due_items[0].get("concept_id") or "这项内容"
        focus = "先复习“%s”，再开始新内容。" % first_title if language == "zh" else "Review %s before starting something new." % first_title
        why = "隔一段时间再做，才能确认这项内容是真的记住了。" if language == "zh" else "A delayed review checks whether the idea stayed with you."
        proof = "完成后留下复习结果；如果做错，记录错在哪里。" if language == "zh" else "Save the review result and note what went wrong if it fails."
    elif stage_row and not stage.get("current_stage_eligible"):
        missing_kind = stage_row.get("first_missing")
        actions = {
            "retrieval": "做一次不看资料的回忆，并保存答案。",
            "application": "自己完成一道类似练习，并保存结果。",
            "transfer": "换一个例子再做一次，并保存结果。",
            "retention": "隔一段时间再做一次复习，并记录结果。",
            "no_repeated_failures": "完成一次复习，并记录这次结果。",
        }
        english_actions = {
            "retrieval": "Do one recall task without looking and save the answer.",
            "application": "Complete one similar task by yourself and save the result.",
            "transfer": "Try one new example and save the result.",
            "retention": "Do one review after a delay and record the result.",
            "no_repeated_failures": "Complete one review and record the result.",
        }
        focus = actions.get(missing_kind, "补充一条能检查的练习结果。") if language == "zh" else english_actions.get(missing_kind, "Add one checkable practice result.")
        why = "想进入下一部分，不能只看过内容，还要看到你能自己想起来、做出来，或换个例子继续做。" if language == "zh" else "Moving on needs more than exposure; you should be able to remember, do, or adapt the idea yourself."
        proof = "把答案或练习结果保存下来，交给 StudyAny 检查。" if language == "zh" else "Save the answer or practice result and return it for checking."
    elif goal_status != "satisfied":
        focus = "完成一项能展示最终目标的成果，并留下可检查的结果。" if language == "zh" else "Complete one result that demonstrates the final goal and save it for checking."
        why = "最终目标需要成果证明，学习时间和看过课程本身不能代替成果。" if language == "zh" else "The final goal needs a result; time and exposure do not replace one."
        proof = "保存成果文件、运行结果或一段能说明你做法的解释。" if language == "zh" else "Save the artifact, runtime result, or explanation of your approach."
    else:
        actions = snapshot.get("next_actions") or []
        focus = actions[0].get("action") if actions and isinstance(actions[0], dict) else _presentation_label(language, "continue_action", "Continue the next small task.")
        why = _presentation_label(language, "continue_reason", "Keep the next evidence-bearing task small and observable.")
        proof = _presentation_label(language, "continue_proof", "Return the result or explanation for the next check.")

    required_count = overall.get("required_stage_count", 0)
    completed_count = overall.get("completed_stage_count", 0)
    projection = snapshot.get("stage_projection") or {}
    stage_rows = [row for row in projection.get("stages") or [] if isinstance(row, dict)]
    current_id = stage.get("current_stage_id") or (projection.get("current_stage") or {}).get("id")
    required_rows = [row for row in stage_rows if row.get("status") != "optional"]
    current_position = next(
        (index + 1 for index, row in enumerate(required_rows) if row.get("stage_id") == current_id),
        None,
    )
    if language == "zh":
        stage_line = "这一部分还没达到进入下一部分的条件。" if not stage.get("current_stage_eligible") else "这一部分已经达到进入下一部分的条件。"
        if current_position and required_count:
            stage_progress = "现在是第 %s 个学习步骤，共 %s 个；当前这一步%s。" % (current_position, required_count, "还没完成" if not stage.get("current_stage_eligible") else "已经完成")
        elif required_count:
            stage_progress = "已经完成 %s 个学习步骤，共 %s 个。" % (completed_count, required_count)
        else:
            stage_progress = "还没有设置学习步骤。"
        if goal_status == "satisfied":
            goal_line = "已经有成果可以说明大目标做到了。"
        elif goal_status == "not_configured":
            goal_line = "还没有写清楚大目标要交出什么成果。"
        else:
            goal_line = "还没有做出足以说明大目标完成的成果。"
    else:
        stage_line = "The current stage is not ready for the next stage." if not stage.get("current_stage_eligible") else "The current stage is ready for the next stage."
        stage_progress = "%s of %s required stages are complete." % (completed_count, required_count)
        goal_line = "There is result evidence for the final goal." if goal_status == "satisfied" else "There is not enough result evidence for the final goal."
    return {
        "headline": headline,
        "situation": situation,
        "focus": focus,
        "why": why,
        "proof": proof,
        "stage_line": stage_line,
        "stage_progress": stage_progress,
        "goal_line": goal_line,
        "data_note": _friendly_data_note(snapshot, language),
    }


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
    delayed = efficiency.get("delayed_review") or {}
    transfer = efficiency.get("transfer") or {}
    lines.append(
        _table(
            [_label(language, "metric"), _label(language, "result"), _label(language, "samples"), _label(language, "note")],
            [
                [_label(language, "actual_planned"), "%s / %s" % (_format_minutes(actual_planned.get("actual_minutes"), language), _format_minutes(actual_planned.get("planned_minutes"), language)), _label(language, actual_planned.get("status", "unknown")), "ratio=%s" % (actual_planned.get("ratio") if actual_planned.get("ratio") is not None else _label(language, "unknown"))],
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


def _default_summary_output_dir() -> Path:
    """Put learner-facing reports in the process working directory."""
    return Path.cwd() / "study-reports"


def _resolve_template_path(template_path: Optional[Path]) -> Optional[Path]:
    if template_path is None:
        default = _default_summary_output_dir() / "studyany-summary-template.xlsx"
        return default.resolve() if default.is_file() else None
    path = Path(template_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        raise SummaryError("template does not exist: %s" % path)
    return path.resolve()


def _template_details(language: str, template_path: Optional[Path]) -> Tuple[Dict[str, str], Optional[Path], Optional[str]]:
    resolved = _resolve_template_path(template_path)
    labels = _presentation_labels(language)
    if resolved is None:
        return labels, None, None
    labels.update(read_template_labels(resolved))
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return labels, resolved, digest


def _summary_workbook_path(
    summary_key: str,
    output_dir: Optional[Path] = None,
) -> Path:
    base = _default_summary_output_dir() if output_dir is None else Path(output_dir).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    safe_key = re.sub(r"[^A-Za-z0-9._-]+", "-", summary_key).strip("-.") or "summary"
    return (base.resolve() / ("studyany-%s.xlsx" % safe_key)).resolve()


def _stored_workbook_path(record: Dict[str, Any]) -> Optional[Path]:
    value = record.get("workbook_path")
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _stored_template_path(record: Dict[str, Any]) -> Optional[Path]:
    value = record.get("template_path")
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _has_workbook(
    record: Optional[Dict[str, Any]],
    expected_path: Path,
    expected_sheets: Optional[Sequence[str]] = None,
    template_path: Optional[Path] = None,
    template_hash: Optional[str] = None,
) -> bool:
    if (
        not record
        or record.get("workbook_format") != "xlsx"
        or record.get("workbook_schema_version") != WORKBOOK_SCHEMA_VERSION
        or not isinstance(record.get("workbook_sheets"), list)
        or not record.get("workbook_sheets")
    ):
        return False
    if expected_sheets is not None and record.get("workbook_sheets") != list(expected_sheets):
        return False
    stored = _stored_workbook_path(record)
    if stored is None or stored != expected_path.resolve() or not stored.is_file():
        return False
    if template_path is None:
        return not record.get("template_path") and not record.get("template_sha256")
    return _stored_template_path(record) == template_path.resolve() and record.get("template_sha256") == template_hash


def _existing_summary(path: Path, summary_key: str) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    found = None
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("summary_key") == summary_key:
            found = row
    return found


def _append_summary(path: Path, record: Dict[str, Any]) -> None:
    """Append a new record or replace one legacy record during migration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    output: List[str] = []
    replaced = False
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            output.append(line)
            continue
        if isinstance(row, dict) and row.get("summary_key") == record["summary_key"]:
            if not replaced:
                output.append(replacement)
                replaced = True
            continue
        output.append(line)
    if not replaced:
        output.append(replacement)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    temporary.replace(path)


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
        "learning_state": progress["period"].get("learning_state") or {},
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
    snapshot["learner_view"] = _learner_view(snapshot, context["language"])
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
    output_dir: Optional[Path] = None,
    template_path: Optional[Path] = None,
) -> Dict[str, Any]:
    built = build_summary(study_root, kind, as_of_value, stage_id, language)
    snapshot = built["snapshot"]
    summary_path = Path(study_root) / "summaries.jsonl"
    existing = _existing_summary(summary_path, snapshot["summary_key"])
    workbook_path = _summary_workbook_path(snapshot["summary_key"], output_dir)
    labels, effective_template, template_hash = _template_details(built["language"], template_path)
    expected_sheets = summary_sheet_names(built["language"])
    if _has_workbook(existing, workbook_path, expected_sheets, effective_template, template_hash):
        return {"summary_key": snapshot["summary_key"], "status": "already_exists", "persisted": False, "workbook_path": str(workbook_path), "record": existing}
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
        "workbook_path": str(workbook_path),
        "workbook_format": "xlsx",
        "workbook_schema_version": WORKBOOK_SCHEMA_VERSION,
    }
    if effective_template is not None:
        record["template_path"] = str(effective_template)
        record["template_sha256"] = template_hash
    eligible = snapshot.get("trigger", {}).get("eligible", True)
    if kind == "stage" and not eligible:
        return {"summary_key": snapshot["summary_key"], "status": "not_ready", "persisted": False, "record": record}
    if persist:
        sheet_names = write_summary_workbook(snapshot, labels, built["language"], workbook_path)
        record["workbook_sheets"] = sheet_names
        _append_summary(summary_path, record)
        return {
            "summary_key": snapshot["summary_key"],
            "status": "upgraded" if existing is not None else "generated",
            "persisted": True,
            "workbook_path": str(workbook_path),
            "record": record,
        }
    return {"summary_key": snapshot["summary_key"], "status": "preview", "persisted": False, "record": record}


def check_due(
    study_root: Path,
    as_of_value: Optional[Any] = None,
    language: Optional[str] = None,
    output_dir: Optional[Path] = None,
    template_path: Optional[Path] = None,
) -> Dict[str, Any]:
    context = _context(Path(study_root), as_of_value, language)
    as_of_date = context["as_of"]
    summary_path = Path(study_root) / "summaries.jsonl"
    _, effective_template, template_hash = _template_details(context["language"], template_path)
    expected_sheets = summary_sheet_names(context["language"])
    history_exists = bool(context["sessions"] or context["assessments"] or context["reviews"])
    candidates: List[Dict[str, Any]] = []
    for kind in ("week", "month"):
        start, end, period_key = _period(as_of_date, kind)
        key = _summary_key(kind, period_key, context["roadmap"], None)
        existing = _existing_summary(summary_path, key)
        workbook_path = _summary_workbook_path(key, output_dir)
        workbook_exists = _has_workbook(existing, workbook_path, expected_sheets, effective_template, template_hash)
        candidates.append(
            {
                "kind": kind,
                "summary_key": key,
                "period": {"start": start.isoformat() if start else None, "end": end.isoformat()},
                "eligible": history_exists,
                "due": history_exists and not workbook_exists,
                "status": "already_exists" if workbook_exists else "due" if history_exists else "no_history",
                "workbook_path": str(workbook_path),
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
        workbook_path = _summary_workbook_path(key, output_dir)
        workbook_exists = _has_workbook(existing, workbook_path, expected_sheets, effective_template, template_hash)
        candidates.append(
            {
                "kind": "stage",
                "stage_id": stage_id,
                "title": stage.get("title"),
                "summary_key": key,
                "eligible": eligible,
                "due": eligible and not workbook_exists,
                "status": "already_exists" if workbook_exists else "due" if eligible else "not_ready",
                "workbook_path": str(workbook_path),
                "first_missing": built["snapshot"].get("stage_projection", {}).get("selected_stage", {}).get("first_missing"),
            }
        )
    due_candidates = [item for item in candidates if item.get("due")]
    if due_candidates:
        kind_labels = {
            "week": _label(context["language"], "period_week"),
            "month": _label(context["language"], "period_month"),
            "stage": _label(context["language"], "period_stage"),
        }
        due_labels = []
        for item in due_candidates:
            label = kind_labels.get(item.get("kind"), str(item.get("kind") or "summary"))
            if item.get("kind") == "stage" and item.get("title"):
                label = "%s（%s）" % (label, item["title"]) if context["language"] == "zh" else "%s (%s)" % (label, item["title"])
            due_labels.append(label)
        if context["language"] == "zh":
            prompt = "检测到%s已到生成时机，是否现在生成？你也可以选择暂不生成。" % "、".join(due_labels)
        else:
            prompt = "The following summaries are ready to generate: %s. Generate them now? You can also skip them for now." % ", ".join(due_labels)
        status = "awaiting_confirmation"
    else:
        prompt = None
        status = "up_to_date"
    return {
        "version": 1,
        "as_of": as_of_date.isoformat(),
        "content_language": "zh-CN" if context["language"] == "zh" else "en",
        "data_quality": _data_quality(context["reasons"], (context["sessions"], context["assessments"], context["reviews"])),
        "candidates": candidates,
        "due_count": len(due_candidates),
        "status": status,
        "confirmation_required": bool(due_candidates),
        "prompt": prompt,
        "due_summaries": due_candidates,
        "generated": [],
        "generated_count": 0,
    }


def generate_due(
    study_root: Path,
    as_of_value: Optional[Any] = None,
    language: Optional[str] = None,
    output_dir: Optional[Path] = None,
    template_path: Optional[Path] = None,
) -> Dict[str, Any]:
    due = check_due(study_root, as_of_value, language, output_dir, template_path)
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
            output_dir=output_dir,
            template_path=template_path,
        )
        results.append(
            {
                "kind": candidate["kind"],
                "summary_key": result["summary_key"],
                "status": result["status"],
                "persisted": result["persisted"],
                "workbook_path": result.get("workbook_path") or candidate.get("workbook_path"),
                "workbook_sheets": result.get("record", {}).get("workbook_sheets") or [],
            }
        )
    return {
        "version": 1,
        "as_of": due["as_of"],
        "content_language": due.get("content_language"),
        "generated": results,
        "generated_count": len(results),
        "check": due,
    }


def _print_check(result: Dict[str, Any], language: str) -> None:
    print("StudyAny %s" % ("总结检查" if language == "zh" else "summary check"))
    print("%s: %s" % (_label(language, "as_of"), result.get("as_of")))
    print("%s: %s" % (_label(language, "data_quality"), _status_text((result.get("data_quality") or {}).get("status"), language)))
    if result.get("prompt"):
        print("%s: %s" % ("确认" if language == "zh" else "Confirmation", result["prompt"]))
    for item in result.get("candidates", []):
        print("- %s %s: %s" % (item.get("kind"), item.get("summary_key"), item.get("status")))
        if item.get("workbook_path"):
            print("  %s: %s" % (_label(language, "workbook"), item["workbook_path"]))


def _print_workbook_result(result: Dict[str, Any], language: str) -> None:
    status = result.get("status")
    if status == "not_ready":
        print("%s: %s" % (_label(language, "status"), _label(language, "not_ready")))
        missing = (
            result.get("record", {})
            .get("snapshot", {})
            .get("stage_projection", {})
            .get("selected_stage", {})
            .get("first_missing")
        )
        if missing:
            print("%s: %s" % (_label(language, "missing_evidence"), missing))
        return
    workbook_path = result.get("workbook_path") or (result.get("record") or {}).get("workbook_path")
    if workbook_path:
        print("%s: %s" % (_label(language, "workbook"), workbook_path))
    sheets = result.get("record", {}).get("workbook_sheets") or []
    if sheets:
        print("%s: %s" % (_label(language, "workbook_sheets"), ", ".join(str(item) for item in sheets)))


def _template_output_path(output: Optional[Path], output_dir: Optional[Path]) -> Path:
    if output is not None:
        path = Path(output).expanduser()
        return (Path.cwd() / path).resolve() if not path.is_absolute() else path.resolve()
    base = _default_summary_output_dir() if output_dir is None else Path(output_dir).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    return (base / "studyany-summary-template.xlsx").resolve()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate StudyAny summary workbooks.")
    parser.add_argument("--study-root", type=Path, default=Path(".study"))
    parser.add_argument("--output-dir", type=Path, dest="global_output_dir", default=None)
    parser.add_argument("--template", type=Path, dest="global_template", default=None)
    parser.add_argument("--json", action="store_true", dest="global_json_output")
    subcommands = parser.add_subparsers(dest="command", required=True)

    generate = subcommands.add_parser("generate", help="generate one summary")
    generate.add_argument("--kind", choices=("week", "month", "stage", "overall"), required=True)
    generate.add_argument("--stage-id")
    generate.add_argument("--as-of")
    generate.add_argument("--language")
    generate.add_argument("--output-dir", type=Path, dest="command_output_dir")
    generate.add_argument("--template", type=Path, dest="command_template")
    generate.add_argument("--json", action="store_true", dest="json_output")

    due = subcommands.add_parser("generate-due", help="generate all due period and stage summaries")
    due.add_argument("--as-of")
    due.add_argument("--language")
    due.add_argument("--output-dir", type=Path, dest="command_output_dir")
    due.add_argument("--template", type=Path, dest="command_template")
    due.add_argument("--json", action="store_true", dest="json_output")

    check = subcommands.add_parser("check", help="check which summaries are due")
    check.add_argument("--as-of")
    check.add_argument("--language")
    check.add_argument("--output-dir", type=Path, dest="command_output_dir")
    check.add_argument("--template", type=Path, dest="command_template")
    check.add_argument("--json", action="store_true", dest="json_output")

    template = subcommands.add_parser("template", help="create an editable summary template")
    template.add_argument("--language", default="zh-CN")
    template.add_argument("--output-dir", type=Path, dest="command_output_dir")
    template.add_argument("--output", type=Path)
    template.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args(argv)
    json_output = bool(getattr(args, "json_output", False) or getattr(args, "global_json_output", False))
    output_dir = getattr(args, "command_output_dir", None) or getattr(args, "global_output_dir", None)
    template_path = getattr(args, "command_template", None) or getattr(args, "global_template", None)
    try:
        if args.command == "template":
            language = _language(args.language or "zh-CN")
            output_path = _template_output_path(args.output, output_dir)
            sheets = write_template_workbook(output_path, _presentation_labels(language), language)
            result = {"status": "generated", "workbook_path": str(output_path), "workbook_format": "xlsx", "workbook_sheets": sheets, "content_language": "zh-CN" if language == "zh" else "en"}
            if json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("%s: %s" % (_label(language, "workbook"), output_path))
                print("%s: %s" % (_label(language, "workbook_sheets"), ", ".join(sheets)))
            return 0
        if not args.study_root.exists():
            raise SummaryError("study root does not exist: %s" % args.study_root)
        if args.command == "generate":
            if args.kind == "stage" and not args.stage_id:
                raise SummaryError("--stage-id is required for a stage summary")
            result = generate_summary(args.study_root, args.kind, args.as_of, args.stage_id, args.language, output_dir=output_dir, template_path=template_path)
            if json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                _print_workbook_result(result, _language(args.language or (result.get("record") or {}).get("content_language") or "en"))
            return 0
        if args.command == "generate-due":
            result = generate_due(args.study_root, args.as_of, args.language, output_dir=output_dir, template_path=template_path)
            if json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                for item in result.get("generated", []):
                    print("- %s: %s" % (_label(_language(args.language or result.get("content_language") or "en"), "workbook"), item.get("workbook_path") or item.get("summary_key")))
                language = _language(args.language or result.get("content_language") or "en")
                if not result.get("generated"):
                    print(_label(language, "no_new_summaries"))
                print("%s: %s" % (_label(language, "generated_count"), result.get("generated_count", 0)))
            return 0
        result = check_due(args.study_root, args.as_of, args.language, output_dir=output_dir, template_path=template_path)
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
