#!/usr/bin/env python3
"""Record local study sessions using the system clock."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ClockError(Exception):
    """An expected user or state error from the clock CLI."""


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ClockError("invalid stored timestamp: %s" % value) from exc
    if parsed.tzinfo is None:
        raise ClockError("stored timestamp has no timezone: %s" % value)
    return parsed


def emit(value: Dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClockError("cannot read %s: %s" % (path, exc)) from exc


def write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def append_jsonl(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def check_due_summaries(study_root: Path) -> Dict[str, Any]:
    """Check due summaries without writing files or losing a session record."""
    try:
        from study_summary import SummaryError, check_due
    except (ImportError, OSError, ValueError) as exc:
        return {
            "status": "check_failed",
            "error": str(exc),
            "confirmation_required": False,
            "due_count": 0,
            "due_summaries": [],
            "generated_count": 0,
            "generated": [],
        }

    try:
        return check_due(study_root)
    except (OSError, SummaryError, ValueError) as exc:
        return {
            "status": "check_failed",
            "error": str(exc),
            "confirmation_required": False,
            "due_count": 0,
            "due_summaries": [],
            "generated_count": 0,
            "generated": [],
        }


def history_contains(path: Path, session_id: str) -> bool:
    if not path.exists():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("session_id") == session_id:
                return True
    except OSError as exc:
        raise ClockError("cannot inspect session history: %s" % exc) from exc
    return False


def session_paths(study_root: Path) -> Dict[str, Path]:
    return {
        "root": study_root,
        "active": study_root / "active-session.json",
        "sessions": study_root / "sessions.jsonl",
    }


def command_now(_: argparse.Namespace) -> None:
    emit({"now": timestamp()})


def command_start(args: argparse.Namespace) -> None:
    paths = session_paths(args.study_root)
    if paths["active"].exists():
        active = read_json(paths["active"])
        session_id = active.get("session_id", "unknown")
        raise ClockError(
            "an active session already exists (%s); run status or stop first"
            % session_id
        )

    started_at = timestamp()
    session = {
        "session_id": "session-%s-%s" % (
            started_at.replace(":", "").replace("+", "-"),
            uuid.uuid4().hex[:8],
        ),
        "subject": args.subject,
        "mode": args.mode,
        "started_at": started_at,
        "ended_at": None,
        "duration_min": None,
        "duration_source": "clock",
        "planned_minutes": args.planned_minutes,
        "status": "in_progress",
        "evidence_mode": args.evidence_mode,
        "objectives": args.objective or [],
        "recall_score": None,
        "practice_score": None,
        "confidence_before": None,
        "confidence_after": None,
        "evidence_refs": [],
        "artifact_ids": args.artifact_id or [],
        "coaching_event_ids": args.coaching_event_id or [],
        "summary": None,
        "mistakes": [],
        "next_action": None,
        "next_review": None,
    }
    write_json(paths["active"], session)
    emit(session)


def command_status(args: argparse.Namespace) -> None:
    paths = session_paths(args.study_root)
    if not paths["active"].exists():
        emit({"status": "idle", "now": timestamp()})
        return

    session = read_json(paths["active"])
    started_at = parse_timestamp(session["started_at"])
    elapsed = max(0.0, (datetime.now().astimezone() - started_at).total_seconds() / 60)
    session["elapsed_min"] = round(elapsed, 1)
    session["now"] = timestamp()
    emit(session)


def command_stop(args: argparse.Namespace) -> None:
    paths = session_paths(args.study_root)
    if not paths["active"].exists():
        raise ClockError("no active session exists; start a session first")

    session = read_json(paths["active"])
    if history_contains(paths["sessions"], session.get("session_id", "")):
        paths["active"].unlink()
        session["status"] = "already_recorded"
        emit(session)
        return
    ended_at = timestamp()
    started_at = parse_timestamp(session["started_at"])
    ended = parse_timestamp(ended_at)
    duration = max(0.0, (ended - started_at).total_seconds() / 60)

    session["ended_at"] = ended_at
    session["duration_min"] = round(duration, 1)
    session["duration_source"] = "clock"
    session["status"] = args.status
    if args.summary is not None:
        session["summary"] = args.summary
    if args.evidence_mode is not None:
        session["evidence_mode"] = args.evidence_mode
    if args.artifact_id:
        session["artifact_ids"] = args.artifact_id
    if args.coaching_event_id:
        existing_ids = session.get("coaching_event_ids") or []
        session["coaching_event_ids"] = list(dict.fromkeys(existing_ids + args.coaching_event_id))
    if args.next_action is not None:
        session["next_action"] = args.next_action
    if args.next_review is not None:
        session["next_review"] = args.next_review
    for field in (
        "recall_score",
        "practice_score",
        "confidence_before",
        "confidence_after",
    ):
        value = getattr(args, field)
        if value is not None:
            session[field] = value
    if args.mistake:
        session["mistakes"] = args.mistake

    append_jsonl(paths["sessions"], session)
    paths["active"].unlink()
    response = dict(session)
    response["summaries"] = check_due_summaries(args.study_root)
    emit(response)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record study sessions using the local system clock."
    )
    parser.add_argument(
        "--study-root",
        type=Path,
        default=Path(".study"),
        help="study data directory (default: .study)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("now", help="print the current timezone-aware time")

    start = commands.add_parser("start", help="start an open study session")
    start.add_argument("--subject", required=True)
    start.add_argument("--mode", default="lesson")
    start.add_argument("--objective", action="append")
    start.add_argument("--planned-minutes", type=float)
    start.add_argument(
        "--evidence-mode",
        choices=("conversation", "artifact", "mixed"),
        default="conversation",
    )
    start.add_argument("--artifact-id", action="append")
    start.add_argument("--coaching-event-id", action="append")

    commands.add_parser("status", help="show the open session and elapsed time")

    stop = commands.add_parser("stop", help="close and append the open session")
    stop.add_argument("--status", choices=("complete", "interrupted"), default="complete")
    stop.add_argument("--summary")
    stop.add_argument("--next-action")
    stop.add_argument("--next-review")
    stop.add_argument("--recall-score", type=float)
    stop.add_argument("--practice-score", type=float)
    stop.add_argument("--confidence-before", type=float)
    stop.add_argument("--confidence-after", type=float)
    stop.add_argument("--mistake", action="append")
    stop.add_argument(
        "--evidence-mode",
        choices=("conversation", "artifact", "mixed"),
    )
    stop.add_argument("--artifact-id", action="append")
    stop.add_argument("--coaching-event-id", action="append")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "now":
            command_now(args)
        elif args.command == "start":
            command_start(args)
        elif args.command == "status":
            command_status(args)
        elif args.command == "stop":
            command_stop(args)
        else:
            parser.error("unknown command")
    except ClockError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
