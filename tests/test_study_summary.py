import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "studyany" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from study_analytics import analyze  # noqa: E402
import study_clock  # noqa: E402
from study_state import main as state_main  # noqa: E402
from study_summary import (  # noqa: E402
    build_summary,
    check_due,
    generate_due,
    generate_summary,
    main as summary_main,
)


class StudySummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.write_json(
            "profile.json",
            {
                "version": 1,
                "language": "zh-CN",
                "timezone": "Asia/Shanghai",
                "target_minutes_per_week": 180,
                "preferred_session_minutes": 45,
            },
        )
        self.write_json(
            "goals.json",
            {
                "subject": "Python",
                "original_goal": "learn Python",
                "operational_goal": "independently write small Python programs",
                "success_evidence": ["stage"],
            },
        )
        self.write_json("roadmap.json", {"version": "roadmap-v1", "stages": []})
        for name in ("sessions.jsonl", "concepts.jsonl", "reviews.jsonl", "assessments.jsonl"):
            (self.root / name).write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")

    def write_jsonl(self, name, rows):
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        (self.root / name).write_text(content, encoding="utf-8")

    def session(self, session_id, day, minutes=30, planned=45):
        return {
            "session_id": session_id,
            "started_at": "%sT10:00:00+08:00" % day,
            "ended_at": "%sT10:30:00+08:00" % day,
            "duration_min": minutes,
            "planned_minutes": planned,
            "status": "complete",
        }

    def assessment(self, assessment_id, day, items, kind="exit"):
        return {
            "assessment_id": assessment_id,
            "created_at": "%sT12:00:00+08:00" % day,
            "kind": kind,
            "evidence_quality": "observed",
            "items": items,
        }

    def item(self, concept_id, prompt_type, result="correct", hint_level=0):
        return {
            "concept_id": concept_id,
            "prompt_type": prompt_type,
            "result": result,
            "hint_level": hint_level,
        }

    def stage_roadmap(self):
        self.write_json(
            "roadmap.json",
            {
                "version": "roadmap-v1",
                "current_stage_id": "stage-01",
                "stages": [
                    {
                        "id": "stage-01",
                        "title": "Functions",
                        "status": "current",
                        "concept_ids": ["c1", "c2"],
                        "exit_criteria": ["Recall both concepts and complete an independent task"],
                    }
                ],
            },
        )
        self.write_jsonl(
            "concepts.jsonl",
            [
                {"concept_id": "c1", "title": "Parameters"},
                {"concept_id": "c2", "title": "Return values"},
            ],
        )

    def test_week_and_month_use_previous_completed_local_period(self):
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])

        week = build_summary(self.root, "week", as_of_value="2026-08-31")
        month = build_summary(self.root, "month", as_of_value="2026-09-01")

        self.assertEqual(week["snapshot"]["period"]["start"], "2026-08-24")
        self.assertEqual(week["snapshot"]["period"]["end"], "2026-08-30")
        self.assertEqual(week["snapshot"]["progress"]["period"]["actual_minutes"], 30.0)
        self.assertEqual(month["snapshot"]["period"]["start"], "2026-08-01")
        self.assertEqual(month["snapshot"]["period"]["end"], "2026-08-31")
        self.assertEqual(month["snapshot"]["progress"]["period"]["actual_minutes"], 30.0)
        preview = generate_summary(self.root, "week", as_of_value="2026-08-31", persist=False)
        self.assertIn("## \u5b66\u4e60\u8fdb\u5ea6", preview["record"]["markdown"])

    def test_timezone_boundary_is_assigned_to_local_period(self):
        self.write_jsonl(
            "sessions.jsonl",
            [
                {
                    "session_id": "boundary",
                    "started_at": "2026-08-23T16:00:00Z",
                    "ended_at": "2026-08-23T16:30:00Z",
                    "duration_min": 30,
                    "planned_minutes": 30,
                    "status": "complete",
                }
            ],
        )

        result = build_summary(self.root, "week", as_of_value="2026-08-31")

        self.assertEqual(result["snapshot"]["progress"]["period"]["study_days"], 1)
        self.assertEqual(result["snapshot"]["progress"]["period"]["actual_minutes"], 30.0)
        self.assertEqual(result["snapshot"]["period"]["start"], "2026-08-24")

    def test_stage_summary_does_not_trigger_from_one_concept_task(self):
        self.stage_roadmap()
        self.write_jsonl(
            "assessments.jsonl",
            [
                self.assessment(
                    "a1",
                    "2026-08-20",
                    [self.item("c1", "recall"), self.item("c1", "apply")],
                )
            ],
        )

        result = generate_summary(self.root, "stage", as_of_value="2026-08-27", stage_id="stage-01")

        self.assertEqual(result["status"], "not_ready")
        self.assertFalse(result["persisted"])
        self.assertEqual(result["record"]["snapshot"]["trigger"]["eligible"], False)
        self.assertFalse((self.root / "summaries.jsonl").exists())

    def test_stage_summary_requires_exit_evidence_across_concepts_and_is_idempotent(self):
        self.stage_roadmap()
        self.write_jsonl(
            "assessments.jsonl",
            [
                self.assessment(
                    "a1",
                    "2026-08-20",
                    [self.item("c1", "recall"), self.item("c1", "apply")],
                ),
                self.assessment(
                    "a2",
                    "2026-08-26",
                    [self.item("c2", "recall"), self.item("c2", "apply")],
                ),
            ],
        )

        first = generate_summary(self.root, "stage", as_of_value="2026-08-27", stage_id="stage-01")
        second = generate_summary(self.root, "stage", as_of_value="2026-08-27", stage_id="stage-01")

        self.assertEqual(first["status"], "generated")
        self.assertEqual(second["status"], "already_exists")
        rows = (self.root / "summaries.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        snapshot = json.loads(rows[0])["snapshot"]
        self.assertEqual(snapshot["period"]["start"], "2026-08-20")
        self.assertEqual(snapshot["progress"]["overall"]["completed_stage_count"], 1)

    def test_configured_transfer_and_retention_gates_are_required(self):
        self.write_json(
            "roadmap.json",
            {
                "version": "roadmap-v1",
                "current_stage_id": "stage-01",
                "stages": [
                    {
                        "id": "stage-01",
                        "title": "Functions",
                        "status": "current",
                        "concept_ids": ["c1"],
                        "exit_requirements": {
                            "retrieval": {"required": True, "min_score": 0.75},
                            "application": {"required": True, "min_score": 0.75, "independent": True},
                            "transfer": {"required": True, "min_score": 0.75},
                            "retention": {"required": True, "min_score": 0.75},
                        },
                    }
                ],
            },
        )
        self.write_jsonl("concepts.jsonl", [{"concept_id": "c1", "title": "Functions"}])
        self.write_jsonl(
            "assessments.jsonl",
            [
                self.assessment(
                    "a1",
                    "2026-08-20",
                    [self.item("c1", "recall"), self.item("c1", "apply"), self.item("c1", "transfer")],
                )
            ],
        )
        self.write_jsonl(
            "reviews.jsonl",
            [
                {
                    "review_id": "r1",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-25T10:00:00+08:00",
                    "result": "pass",
                    "delay_type": "spaced",
                }
            ],
        )

        result = generate_summary(self.root, "stage", as_of_value="2026-08-27", stage_id="stage-01")

        self.assertEqual(result["status"], "generated")
        gates = {gate["kind"]: gate for gate in result["record"]["snapshot"]["stage_projection"]["selected_stage"]["gates"]}
        self.assertEqual(gates["transfer"]["status"], "met")
        self.assertEqual(gates["retention"]["status"], "met")

    def test_transfer_rate_uses_transfer_attempts_only(self):
        self.write_jsonl(
            "reviews.jsonl",
            [
                {
                    "review_id": "r1",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-20T10:00:00+08:00",
                    "result": "pass",
                    "delay_type": "spaced",
                },
                {
                    "review_id": "r2",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-21T10:00:00+08:00",
                    "result": "fail",
                    "delay_type": "spaced",
                    "is_transfer": True,
                },
                {
                    "review_id": "r3",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-22T10:00:00+08:00",
                    "result": "transfer_pass",
                    "delay_type": "spaced",
                },
            ],
        )

        result = build_summary(self.root, "overall", as_of_value="2026-08-31")
        transfer = result["snapshot"]["efficiency"]["transfer"]

        self.assertEqual(transfer["attempt_count"], 2)
        self.assertEqual(transfer["pass_count"], 1)
        self.assertEqual(transfer["pass_rate"], 0.5)

    def test_missing_evidence_does_not_become_a_fake_efficiency_score(self):
        result = build_summary(self.root, "overall", as_of_value="2026-08-31")
        snapshot = result["snapshot"]

        self.assertEqual(snapshot["data_quality"]["status"], "insufficient_data")
        self.assertIsNone(snapshot["efficiency"]["actual_vs_planned"]["planned_minutes"])
        self.assertIsNone(snapshot["efficiency"]["actual_vs_planned"]["ratio"])
        self.assertEqual(snapshot["efficiency"]["delayed_review"]["status"], "insufficient_data")

    def test_due_generation_skips_empty_workspace_and_is_idempotent(self):
        empty = generate_due(self.root, as_of_value="2026-08-31")
        self.assertEqual(empty["generated_count"], 0)
        self.assertFalse((self.root / "summaries.jsonl").exists())

        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        first = generate_due(self.root, as_of_value="2026-08-31")
        second = generate_due(self.root, as_of_value="2026-08-31")

        self.assertEqual(first["generated_count"], 2)
        self.assertEqual(second["generated_count"], 0)
        due = check_due(self.root, as_of_value="2026-08-31")
        self.assertEqual(due["due_count"], 0)

    def test_state_status_auto_generates_due_summaries(self):
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = state_main(["--study-root", str(self.root), "status", "--json"])

        self.assertEqual(code, 0)
        state = json.loads(output.getvalue())
        self.assertEqual(state["summaries"]["generated_count"], 2)
        self.assertEqual(len((self.root / "summaries.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_clock_stop_auto_generates_due_summaries_after_session_append(self):
        started_at = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat(timespec="seconds")
        self.write_json(
            "active-session.json",
            {
                "session_id": "clock-session",
                "subject": "Python",
                "mode": "lesson",
                "started_at": started_at,
                "planned_minutes": 30,
                "status": "in_progress",
            },
        )
        args = study_clock.build_parser().parse_args(
            ["--study-root", str(self.root), "stop", "--status", "complete"]
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            study_clock.command_stop(args)

        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summaries"]["generated_count"], 2)
        self.assertFalse((self.root / "active-session.json").exists())
        session_rows = (self.root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(session_rows), 1)
        self.assertNotIn("summaries", json.loads(session_rows[0]))
        self.assertEqual(len((self.root / "summaries.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_clock_stop_keeps_session_when_summary_generation_fails(self):
        (self.root / "summaries.jsonl").mkdir()
        started_at = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat(timespec="seconds")
        self.write_json(
            "active-session.json",
            {
                "session_id": "clock-session-error",
                "subject": "Python",
                "mode": "lesson",
                "started_at": started_at,
                "planned_minutes": 30,
                "status": "in_progress",
            },
        )
        args = study_clock.build_parser().parse_args(
            ["--study-root", str(self.root), "stop", "--status", "complete"]
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            study_clock.command_stop(args)

        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summaries"]["generated_count"], 0)
        self.assertIn("error", result["summaries"])
        self.assertEqual(len((self.root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_cli_json_output_can_be_requested_before_or_after_command(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = summary_main(
                ["--study-root", str(self.root), "--json", "generate", "--kind", "overall", "--as-of", "2026-08-31"]
            )

        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["record"]["content_language"], "zh-CN")
        self.assertIn("markdown", result["record"])

    def test_analytics_month_window_and_transfer_denominator_are_additive(self):
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        self.write_jsonl(
            "reviews.jsonl",
            [
                {
                    "review_id": "r1",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-24T10:00:00+08:00",
                    "result": "pass",
                    "delay_type": "spaced",
                },
                {
                    "review_id": "r2",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-25T10:00:00+08:00",
                    "result": "transfer_pass",
                    "delay_type": "spaced",
                },
            ],
        )

        result = analyze(self.root, as_of="2026-08-31", window="month")

        self.assertEqual(result["window"]["start"], "2026-08-01")
        self.assertEqual(result["window"]["end"], "2026-08-31")
        self.assertEqual(result["reviews"]["transfer_attempt_count"], 1)
        self.assertEqual(result["reviews"]["transfer_pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
