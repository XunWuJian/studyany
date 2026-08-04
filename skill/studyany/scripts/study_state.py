#!/usr/bin/env python3
"""Read and rebuild the persistent StudyAny resume state."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from study_analytics import analyze as analyze_study


class StateError(Exception):
    """An expected study-state error."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def read_json(path: Path, warnings: List[str]) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append("Could not read %s: %s" % (path.name, exc))
        return None
    if not isinstance(value, dict):
        warnings.append("Ignoring non-object JSON file: %s" % path.name)
        return None
    return value


def read_jsonl(path: Path, warnings: List[str]) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append("Could not read %s: %s" % (path.name, exc))
        return rows
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append("Ignoring invalid %s line %d: %s" % (path.name, line_number, exc))
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            warnings.append("Ignoring non-object %s line %d" % (path.name, line_number))
    return rows


def latest_by(rows: Iterable[Dict[str, Any]], field: str) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        value = row.get(field)
        if isinstance(value, str) and value:
            latest[value] = row
    return latest


def latest_decisions(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return the newest decision for each stable challenged claim."""
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        claim_id = row.get("claim_id") or row.get("decision_id")
        if isinstance(claim_id, str) and claim_id:
            latest[claim_id] = row
    return latest


def open_disputes(decisions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract only decisions that still need evidence or explicit deferral."""
    disputes: List[Dict[str, Any]] = []
    for row in decisions:
        status = row.get("status")
        if status not in ("pending_evidence", "deferred", "disputed", "open") and row.get("verdict") != "uncertain":
            continue
        disputes.append(
            {
                "decision_id": row.get("decision_id"),
                "claim_id": row.get("claim_id") or row.get("decision_id"),
                "kind": row.get("kind"),
                "status": status or "pending_evidence",
                "summary": row.get("decision") or row.get("original_claim"),
                "next_evidence": row.get("next_evidence"),
                "challenge_count": row.get("challenge_count", 0),
                "source_ref": row.get("decision_id"),
            }
        )
    return sorted(
        disputes,
        key=lambda item: (
            item.get("status") or "",
            item.get("claim_id") or "",
        ),
    )


def latest_row(rows: Iterable[Dict[str, Any]], time_fields: Iterable[str]) -> Optional[Dict[str, Any]]:
    candidates = list(rows)
    if not candidates:
        return None

    def sort_key(row: Dict[str, Any]) -> datetime:
        for field in time_fields:
            parsed = parse_time(row.get(field))
            if parsed is not None:
                return parsed
        return datetime.min.astimezone()

    return max(enumerate(candidates), key=lambda item: (sort_key(item[1]), item[0]))[1]


def dashboard_value(path: Path, label: str) -> Optional[str]:
    if not path.exists():
        return None
    prefix = label.lower() + ":"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def stage_state(roadmap: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not roadmap:
        return {"id": None, "title": None, "status": None}
    stages = roadmap.get("stages")
    if not isinstance(stages, list):
        stages = []
    current_id = roadmap.get("current_stage_id")
    selected = None
    if isinstance(current_id, str):
        selected = next((stage for stage in stages if stage.get("id") == current_id), None)
    if selected is None:
        selected = next((stage for stage in stages if stage.get("status") == "current"), None)
    if not isinstance(selected, dict):
        return {"id": current_id, "title": None, "status": None}
    return {
        "id": selected.get("id"),
        "title": selected.get("title"),
        "status": selected.get("status"),
    }


def due_reviews(concepts: List[Dict[str, Any]], today: str) -> List[Dict[str, Any]]:
    due: List[Dict[str, Any]] = []
    for concept in concepts:
        next_review = concept.get("next_review")
        if not isinstance(next_review, str) or not next_review or next_review > today:
            continue
        due.append(
            {
                "concept_id": concept.get("concept_id"),
                "title": concept.get("title"),
                "next_review": next_review,
                "mastery": concept.get("mastery"),
                "failure_count": concept.get("failure_count"),
            }
        )
    return sorted(due, key=lambda item: (item.get("next_review") or "", item.get("concept_id") or ""))


def next_review_date(concepts: List[Dict[str, Any]]) -> Optional[str]:
    dates = [
        concept.get("next_review")
        for concept in concepts
        if isinstance(concept.get("next_review"), str) and concept.get("next_review")
    ]
    return min(dates) if dates else None


def derived_open_loops(
    reviews: List[Dict[str, Any]],
    assessments: List[Dict[str, Any]],
    concepts: List[Dict[str, Any]],
    today: str,
) -> List[Dict[str, Any]]:
    loops: List[Dict[str, Any]] = []
    concept_map = {row.get("concept_id"): row for row in concepts}
    latest_reviews = latest_by(reviews, "concept_id")

    for concept_id, review in latest_reviews.items():
        result = review.get("result")
        if result not in ("hinted", "fail"):
            continue
        concept = concept_map.get(concept_id, {})
        title = concept.get("title") or concept_id
        loops.append(
            {
                "loop_id": "review-%s-unaided" % concept_id,
                "kind": "retrieval",
                "concept_id": concept_id,
                "status": "open",
                "priority": "high" if result == "fail" else "normal",
                "due_on": review.get("next_review") or today,
                "summary": "Retrieve %s without the previous cue." % title,
                "expected_evidence": "Unaided explanation or a changed-example task.",
                "source_ref": review.get("evidence_ref"),
            }
        )

    latest_assessment = latest_row(assessments, ("created_at",))
    if latest_assessment:
        for item in latest_assessment.get("items", []):
            if not isinstance(item, dict) or item.get("result") not in ("partial", "incorrect", "not_attempted"):
                continue
            concept_id = item.get("concept_id")
            if any(loop.get("concept_id") == concept_id for loop in loops):
                continue
            concept = concept_map.get(concept_id, {})
            loops.append(
                {
                    "loop_id": "evidence-%s" % (concept_id or "unknown"),
                    "kind": "evidence_gap",
                    "concept_id": concept_id,
                    "status": "open",
                    "priority": "normal",
                    "due_on": today,
                    "summary": item.get("feedback") or "Collect missing evidence for %s." % (concept.get("title") or concept_id),
                    "expected_evidence": item.get("prompt_type") or "observable evidence",
                    "source_ref": latest_assessment.get("assessment_id"),
                }
            )
    return loops


def time_summary(sessions: List[Dict[str, Any]], sessions_path: Path) -> Dict[str, Any]:
    measured_sessions = [
        row
        for row in sessions
        if row.get("status") in ("complete", "interrupted")
    ]
    durations = [
        row.get("duration_min")
        for row in measured_sessions
        if isinstance(row.get("duration_min"), (int, float))
        and not isinstance(row.get("duration_min"), bool)
        and row.get("duration_min") >= 0
    ]
    summary: Dict[str, Any] = {
        "session_count": len(measured_sessions),
        "completed_or_interrupted_count": len(measured_sessions),
        "total_minutes": round(sum(durations), 1) if durations else None,
        "source": "sessions.jsonl" if durations else "unknown",
    }
    if not sessions_path.exists():
        summary["source"] = "missing"
        summary["note"] = "No session history exists; do not infer time from chat turns."
    elif not durations:
        summary["note"] = "Session history has no measured durations."
    return summary


def build_state(study_root: Path) -> Dict[str, Any]:
    warnings: List[str] = []
    profile = read_json(study_root / "profile.json", warnings) or {}
    goals = read_json(study_root / "goals.json", warnings) or {}
    roadmap = read_json(study_root / "roadmap.json", warnings) or {}
    checkpoint = read_json(study_root / "checkpoint.json", warnings)
    concepts = list(latest_by(read_jsonl(study_root / "concepts.jsonl", warnings), "concept_id").values())
    assessments = read_jsonl(study_root / "assessments.jsonl", warnings)
    reviews = read_jsonl(study_root / "reviews.jsonl", warnings)
    decisions_path = study_root / "decisions.jsonl"
    decision_rows = read_jsonl(decisions_path, warnings)
    decision_map = latest_decisions(decision_rows)
    coaching_rows = read_jsonl(study_root / "coaching_events.jsonl", warnings)
    sessions_path = study_root / "sessions.jsonl"
    sessions = read_jsonl(sessions_path, warnings)
    active = read_json(study_root / "active-session.json", warnings)

    if checkpoint is None:
        warnings.append("checkpoint.json is missing; run study_state.py rebuild before starting new material")
    if not sessions_path.exists():
        warnings.append("sessions.jsonl is missing; historical study time is unknown")
    checkpoint_plan_has_decisions = (
        isinstance(checkpoint.get("plan"), dict)
        and checkpoint.get("plan", {}).get("decision_refs")
    ) if checkpoint else False
    if checkpoint and not decisions_path.exists() and (
        checkpoint.get("open_disputes") or checkpoint_plan_has_decisions
    ):
        warnings.append("decisions.jsonl is missing; challenge history is incomplete")
    if active is not None:
        warnings.append("an open session exists; reconcile it before starting another session")
    if not goals:
        warnings.append("goals.json is missing")
    if not roadmap:
        warnings.append("roadmap.json is missing")

    analytics = analyze_study(study_root)
    today = analytics.get("as_of") or datetime.now().astimezone().date().isoformat()
    latest_assessment = latest_row(assessments, ("created_at",))
    latest_review = latest_row(reviews, ("reviewed_at",))
    latest_decision = latest_row(decision_rows, ("created_at",))
    latest_coaching = latest_row(coaching_rows, ("created_at",))
    latest_session = latest_row(sessions, ("ended_at", "started_at"))
    stage = stage_state(roadmap)
    checkpoint_loops = checkpoint.get("open_loops") if checkpoint else None
    loops = checkpoint_loops if isinstance(checkpoint_loops, list) else derived_open_loops(reviews, assessments, concepts, today)
    due = due_reviews(concepts, today)
    next_action = (
        checkpoint.get("next_action") if checkpoint else None
    ) or dashboard_value(study_root / "dashboard.md", "Next action")
    next_review = checkpoint.get("next_review") if checkpoint else None
    if not next_review and due:
        next_review = due[0].get("next_review")
    if not next_review:
        next_review = next_review_date(concepts)

    disputes = open_disputes(decision_map.values())
    if not disputes and checkpoint:
        checkpoint_disputes = checkpoint.get("open_disputes")
        if isinstance(checkpoint_disputes, list):
            disputes = checkpoint_disputes
    decision_refs = [
        row.get("decision_id")
        for row in decision_map.values()
        if isinstance(row.get("decision_id"), str) and row.get("decision_id")
    ]
    checkpoint_plan = checkpoint.get("plan") if checkpoint else None
    if isinstance(checkpoint_plan, dict):
        plan = dict(checkpoint_plan)
    else:
        plan = {
            "version": roadmap.get("version") or "roadmap-v1",
            "status": "disputed" if disputes else "active",
            "decision_refs": [],
        }
    if decision_refs:
        plan["decision_refs"] = decision_refs
    elif not isinstance(plan.get("decision_refs"), list):
        plan["decision_refs"] = []

    activity_times = []
    for row in (latest_assessment, latest_review, latest_decision, latest_coaching, latest_session):
        if isinstance(row, dict):
            for field in ("created_at", "reviewed_at", "ended_at", "started_at", "updated_at"):
                parsed = parse_time(row.get(field))
                if parsed:
                    activity_times.append(parsed)
    last_activity_at = max(activity_times).isoformat(timespec="seconds") if activity_times else None
    latest_evidence = latest_assessment.get("summary") if latest_assessment else None
    latest_feedback = None
    if latest_coaching:
        latest_feedback = (
            latest_coaching.get("action")
            or latest_coaching.get("learning_interpretation")
            or latest_coaching.get("next_check")
        )
    if not latest_feedback and checkpoint:
        checkpoint_feedback = checkpoint.get("last_feedback")
        if isinstance(checkpoint_feedback, str) and checkpoint_feedback:
            latest_feedback = checkpoint_feedback

    return {
        "status": "partial" if warnings else "ready",
        "study_root": str(study_root),
        "subject": goals.get("subject"),
        "goal": goals.get("operational_goal") or goals.get("original_goal"),
        "current_stage": stage,
        "last_activity_at": last_activity_at,
        "last_evidence": latest_evidence,
        "latest_assessment_id": latest_assessment.get("assessment_id") if latest_assessment else None,
        "latest_review_id": latest_review.get("review_id") if latest_review else None,
        "latest_decision_id": latest_decision.get("decision_id") if latest_decision else None,
        "latest_coaching_event_id": latest_coaching.get("event_id") if latest_coaching else None,
        "latest_feedback": latest_feedback,
        "latest_coaching_event": latest_coaching,
        "latest_session_id": latest_session.get("session_id") if latest_session else None,
        "open_loops": loops,
        "due_reviews": due,
        "next_action": next_action,
        "next_review": next_review,
        "plan": plan,
        "open_disputes": disputes,
        "active_session": active,
        "time": time_summary(sessions, sessions_path),
        "analytics": analytics,
        "warnings": warnings,
        "sources": {
            "checkpoint": checkpoint is not None,
            "goals": bool(goals),
            "roadmap": bool(roadmap),
            "concepts": len(concepts),
            "assessments": len(assessments),
            "reviews": len(reviews),
            "decisions": len(decision_rows),
            "coaching_events": len(coaching_rows),
            "sessions": len(sessions),
        },
    }


def checkpoint_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    time_data = state.get("time", {})
    quality = "complete" if time_data.get("source") == "sessions.jsonl" and not state.get("warnings") else "partial"
    warnings = [
        warning
        for warning in state.get("warnings", [])
        if not warning.startswith("checkpoint.json is missing")
    ]
    return {
        "version": 1,
        "state": quality,
        "updated_at": now_iso(),
        "subject": state.get("subject"),
        "current_stage_id": (state.get("current_stage") or {}).get("id"),
        "current_stage_title": (state.get("current_stage") or {}).get("title"),
        "last_activity_at": state.get("last_activity_at"),
        "last_session_id": state.get("latest_session_id"),
        "last_assessment_id": state.get("latest_assessment_id"),
        "last_review_id": state.get("latest_review_id"),
        "last_decision_id": state.get("latest_decision_id"),
        "last_coaching_event_id": state.get("latest_coaching_event_id"),
        "plan": state.get(
            "plan",
            {
                "version": "roadmap-v1",
                "status": "active",
                "decision_refs": [],
            },
        ),
        "open_disputes": state.get("open_disputes", []),
        "last_evidence": state.get("last_evidence"),
        "last_feedback": state.get("latest_feedback"),
        "open_loops": state.get("open_loops", []),
        "next_action": state.get("next_action"),
        "next_review": state.get("next_review"),
        "resume_instruction": "Restore open loops before teaching new material; start with the highest-priority due review.",
        "time_tracking": {
            "source": time_data.get("source"),
            "historical_minutes": time_data.get("total_minutes"),
            "note": time_data.get("note"),
        },
        "warnings": warnings,
    }


def write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def print_human(state: Dict[str, Any]) -> None:
    print("StudyAny resume")
    print("Status: %s" % str(state.get("status", "unknown")).upper())
    print("Subject: %s" % (state.get("subject") or "unknown"))
    stage = state.get("current_stage") or {}
    print("Current stage: %s (%s)" % (stage.get("title") or "unknown", stage.get("id") or "unknown"))
    if state.get("last_activity_at"):
        print("Last activity: %s" % state["last_activity_at"])
    if state.get("last_evidence"):
        print("Last evidence: %s" % state["last_evidence"])
    if state.get("latest_feedback"):
        print("Last feedback: %s" % state["latest_feedback"])
    loops = state.get("open_loops") or []
    print("Open loops: %d" % len(loops))
    for loop in loops[:5]:
        print("- [%s] %s" % (loop.get("priority", "normal"), loop.get("summary", "unresolved item")))
    disputes = state.get("open_disputes") or []
    print("Open disputes: %d" % len(disputes))
    for dispute in disputes[:3]:
        print("- [%s] %s" % (dispute.get("status", "pending"), dispute.get("summary", "unresolved decision")))
    due = state.get("due_reviews") or []
    print("Due reviews: %s" % (", ".join(str(item.get("concept_id")) for item in due) or "none"))
    print("Next action: %s" % (state.get("next_action") or "reconcile state and choose one objective"))
    print("Next review: %s" % (state.get("next_review") or "unknown"))
    time_data = state.get("time") or {}
    print("Study time: %s minutes (%s)" % (time_data.get("total_minutes") if time_data.get("total_minutes") is not None else "unknown", time_data.get("source", "unknown")))
    analytics = state.get("analytics") or {}
    quality = analytics.get("data_quality") or {}
    print("Analytics: %s" % quality.get("status", "unknown"))
    pacing = analytics.get("pacing") or {}
    if pacing.get("target_status") == "not_configured":
        print("Pacing target: not configured")
    else:
        print("Pacing: minutes=%s, sessions=%s, days=%s" % (
            pacing.get("minute_status", "unknown"),
            pacing.get("session_status", "unknown"),
            pacing.get("day_status", "unknown"),
        ))
    reviews = analytics.get("reviews") or {}
    print("Review backlog: %s due, %s overdue" % (reviews.get("due_count", 0), reviews.get("overdue_count", 0)))
    for alert in (analytics.get("alerts") or [])[:3]:
        print("Analytics alert: %s" % alert.get("code", "unknown"))
    recommendation = analytics.get("recommendation") or {}
    print("Analytics next action: %s" % recommendation.get("code", "none"))
    for warning in state.get("warnings") or []:
        print("Warning: %s" % warning)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read and rebuild StudyAny continuity state.")
    parser.add_argument("--study-root", type=Path, default=Path(".study"))
    subcommands = parser.add_subparsers(dest="command", required=True)
    status = subcommands.add_parser("status", help="show the resume state")
    status.add_argument("--json", action="store_true", dest="json_output")
    rebuild = subcommands.add_parser("rebuild", help="rebuild a missing checkpoint from existing records")
    rebuild.add_argument("--force", action="store_true", help="replace an existing checkpoint")
    rebuild.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    study_root = args.study_root
    if not study_root.exists():
        raise StateError("study root does not exist: %s" % study_root)
    state = build_state(study_root)
    if args.command == "rebuild":
        checkpoint_path = study_root / "checkpoint.json"
        if checkpoint_path.exists() and not args.force:
            raise StateError("checkpoint already exists; use --force only after reviewing it")
        write_json_atomic(checkpoint_path, checkpoint_from_state(state))
        state = build_state(study_root)
    if getattr(args, "json_output", False):
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print_human(state)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StateError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
