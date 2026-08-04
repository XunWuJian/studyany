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
from study_state import build_state  # noqa: E402


class StudyAnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.write_json(
            "profile.json",
            {
                "version": 1,
                "timezone": "Asia/Shanghai",
                "available_minutes_per_week": 240,
                "preferred_session_minutes": 45,
            },
        )
        for name in ("sessions.jsonl", "concepts.jsonl", "reviews.jsonl", "assessments.jsonl"):
            (self.root / name).write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")

    def write_jsonl(self, name, rows):
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        (self.root / name).write_text(content, encoding="utf-8")

    def session(self, session_id, day, minutes, planned=None, status="complete"):
        row = {
            "session_id": session_id,
            "started_at": "%sT10:00:00+08:00" % day,
            "ended_at": "%sT10:30:00+08:00" % day,
            "duration_min": minutes,
            "status": status,
        }
        if planned is not None:
            row["planned_minutes"] = planned
        return row

    def test_overlong_sessions_and_weekly_overload_signal(self):
        self.write_json(
            "profile.json",
            {
                "version": 1,
                "timezone": "Asia/Shanghai",
                "target_minutes_per_week": 100,
                "target_sessions_per_week": 2,
                "preferred_session_minutes": 45,
                "maximum_session_minutes": 75,
            },
        )
        self.write_jsonl(
            "sessions.jsonl",
            [
                self.session("s1", "2026-08-03", 70, planned=45),
                self.session("s2", "2026-08-05", 70, planned=45),
            ],
        )

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["time"]["actual_minutes"], 140.0)
        self.assertEqual(len(result["time"]["overlong_sessions"]), 2)
        self.assertEqual(result["pacing"]["minute_status"], "above_plan")
        codes = {alert["code"] for alert in result["alerts"]}
        self.assertIn("overlong_session", codes)
        self.assertIn("overload_risk", codes)
        self.assertEqual(result["recommendation"]["code"], "take_break")

    def test_behind_pace_requires_configured_target(self):
        self.write_json("profile.json", {"timezone": "Asia/Shanghai", "target_minutes_per_week": 240})
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-03", 30)])

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["pacing"]["minute_status"], "behind_pace")
        self.assertIn("behind_pace", {alert["code"] for alert in result["alerts"]})
        self.assertEqual(result["recommendation"]["code"], "schedule_minimum_session")

    def test_session_and_study_day_targets_are_independent(self):
        self.write_json(
            "profile.json",
            {
                "timezone": "Asia/Shanghai",
                "target_sessions_per_week": 4,
                "target_study_days": ["Mon", "Wed", "Fri"],
            },
        )
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-03", 30)])

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["pacing"]["minute_status"], "not_configured")
        self.assertEqual(result["pacing"]["session_status"], "behind_pace")
        self.assertEqual(result["pacing"]["missed_target_days"], [2, 4])
        self.assertIn("frequency_gap", {alert["code"] for alert in result["alerts"]})

    def test_no_target_is_not_under_study(self):
        self.write_json("profile.json", {"timezone": "Asia/Shanghai", "available_minutes_per_week": 240})
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-03", 30)])

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["pacing"]["target_status"], "not_configured")
        self.assertEqual(result["pacing"]["minute_status"], "not_configured")
        self.assertNotIn("behind_pace", {alert["code"] for alert in result["alerts"]})
        self.assertIn("no_target", result["data_quality"]["reasons"])

    def test_missing_session_log_does_not_create_frequency_gap(self):
        self.write_json(
            "profile.json",
            {"timezone": "Asia/Shanghai", "target_sessions_per_week": 4, "target_study_days": ["Mon", "Wed"]},
        )
        (self.root / "sessions.jsonl").unlink()

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["pacing"]["session_status"], "insufficient_data")
        self.assertEqual(result["pacing"]["day_status"], "insufficient_data")
        self.assertNotIn("frequency_gap", {alert["code"] for alert in result["alerts"]})

    def test_open_and_unknown_sessions_are_not_measured(self):
        self.write_jsonl(
            "sessions.jsonl",
            [
                self.session("s1", "2026-08-03", None),
                self.session("s2", "2026-08-04", 45, status="in_progress"),
            ],
        )

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["time"]["session_count"], 1)
        self.assertEqual(result["time"]["measured_session_count"], 0)
        self.assertEqual(result["time"]["unknown_duration_count"], 1)
        self.assertIsNone(result["time"]["actual_minutes"])
        self.assertEqual(result["time"]["measurement_status"], "unknown")
        self.assertIn("unknown_duration", result["data_quality"]["reasons"])

    def test_active_session_can_trigger_pacing_without_counting_as_completed(self):
        started_at = (datetime.now().astimezone() - timedelta(minutes=65)).isoformat()
        self.write_json(
            "active-session.json",
            {
                "session_id": "active",
                "started_at": started_at,
                "planned_minutes": 45,
                "status": "in_progress",
            },
        )

        result = analyze(self.root)

        self.assertEqual(result["time"]["measured_session_count"], 0)
        self.assertEqual(result["time"]["actual_minutes"], 0.0)
        self.assertEqual(len(result["time"]["active_overlong_sessions"]), 1)
        self.assertIn("overlong_session", {alert["code"] for alert in result["alerts"]})

    def test_timezone_boundary_uses_learner_timezone(self):
        self.write_jsonl(
            "sessions.jsonl",
            [
                {
                    "session_id": "boundary",
                    "started_at": "2026-08-02T16:00:00Z",
                    "ended_at": "2026-08-02T16:30:00Z",
                    "duration_min": 30,
                    "status": "complete",
                }
            ],
        )

        result = analyze(self.root, as_of="2026-08-03")

        self.assertEqual(result["window"]["start"], "2026-08-03")
        self.assertEqual(result["time"]["study_dates"], ["2026-08-03"])
        self.assertEqual(result["time"]["actual_minutes"], 30.0)

    def test_fixed_as_of_excludes_future_records_from_all_evidence(self):
        self.write_json("profile.json", {"timezone": "Asia/Shanghai"})
        self.write_jsonl(
            "sessions.jsonl",
            [self.session("future-session", "2026-08-05", 45)],
        )
        self.write_jsonl(
            "reviews.jsonl",
            [
                {
                    "review_id": "future-review",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-05T10:00:00+08:00",
                    "result": "pass",
                    "delay_type": "spaced",
                }
            ],
        )
        self.write_jsonl(
            "assessments.jsonl",
            [
                {
                    "assessment_id": "future-assessment",
                    "created_at": "2026-08-05T10:00:00+08:00",
                    "items": [{"concept_id": "c1", "prompt_type": "recall", "result": "correct"}],
                }
            ],
        )

        result = analyze(self.root, as_of="2026-08-04")

        self.assertEqual(result["time"]["session_count"], 0)
        self.assertEqual(result["time"]["actual_minutes"], 0.0)
        self.assertEqual(result["reviews"]["delayed_attempt_count"], 0)
        self.assertEqual(result["learning_curve"]["retrieval"]["sample_count"], 0)

    def test_reviews_exclude_same_session_and_detect_delayed_decay(self):
        self.write_jsonl("concepts.jsonl", [{"concept_id": "c1", "title": "Core", "next_review": "2026-08-04", "mastery": 2}])
        self.write_jsonl(
            "reviews.jsonl",
            [
                {
                    "review_id": "r1",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-03T10:00:00+08:00",
                    "result": "pass",
                    "delay_type": "same_session",
                    "same_session": True,
                },
                {
                    "review_id": "r2",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-03T10:05:00+08:00",
                    "result": "transfer_pass",
                    "delay_type": "next_day",
                    "same_session": False,
                },
                {
                    "review_id": "r3",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-05T10:00:00+08:00",
                    "result": "fail",
                    "delay_type": "spaced",
                    "same_session": False,
                },
            ],
        )

        result = analyze(self.root, as_of="2026-08-06")
        reviews = result["reviews"]

        self.assertEqual(reviews["due_count"], 1)
        self.assertEqual(reviews["overdue_count"], 1)
        self.assertEqual(reviews["delayed_attempt_count"], 2)
        self.assertEqual(reviews["delayed_pass_count"], 1)
        self.assertEqual(reviews["delayed_pass_rate"], 0.5)
        self.assertEqual(reviews["transfer_pass_count"], 1)
        self.assertEqual(reviews["transfer_pass_rate"], 0.5)
        self.assertEqual(reviews["capacity"]["status"], "not_configured")
        self.assertEqual(len(reviews["delayed_decay"]), 1)
        self.assertEqual(result["learning_curve"]["retention"]["sample_count"], 2)
        self.assertEqual(result["recommendation"]["code"], "review_due")

    def test_review_capacity_is_estimated_only_from_target_and_preferred_session(self):
        self.write_json(
            "profile.json",
            {
                "timezone": "Asia/Shanghai",
                "target_minutes_per_week": 180,
                "preferred_session_minutes": 45,
            },
        )
        self.write_jsonl(
            "concepts.jsonl",
            [{"concept_id": "c1", "next_review": "2026-08-04"}],
        )

        result = analyze(self.root, as_of="2026-08-04")
        capacity = result["reviews"]["capacity"]

        self.assertEqual(capacity["status"], "estimated")
        self.assertEqual(capacity["estimated_sessions_per_week"], 4.0)
        self.assertEqual(capacity["priority_reviews_per_week_low"], 12.0)
        self.assertEqual(capacity["priority_reviews_per_week_high"], 20.0)

    def test_unknown_review_result_and_out_of_range_score_are_not_counted(self):
        self.write_jsonl(
            "reviews.jsonl",
            [
                {
                    "review_id": "bad-review",
                    "concept_id": "c1",
                    "reviewed_at": "2026-08-03T10:00:00+08:00",
                    "result": "unknown",
                    "delay_type": "spaced",
                }
            ],
        )
        self.write_jsonl(
            "assessments.jsonl",
            [
                {
                    "assessment_id": "bad-assessment",
                    "created_at": "2026-08-03T10:00:00+08:00",
                    "items": [{"concept_id": "c1", "prompt_type": "recall", "score": 2}],
                }
            ],
        )

        result = analyze(self.root, as_of="2026-08-04")

        self.assertEqual(result["reviews"]["delayed_attempt_count"], 0)
        self.assertIn("invalid_review_result", result["data_quality"]["reasons"])
        self.assertEqual(result["learning_curve"]["retrieval"]["sample_count"], 0)

    def test_learning_curve_labels_sparse_and_recovering_evidence(self):
        self.write_jsonl(
            "assessments.jsonl",
            [
                {
                    "assessment_id": "a1",
                    "created_at": "2026-08-01T10:00:00+08:00",
                    "items": [{"concept_id": "c1", "prompt_type": "recall", "result": "incorrect", "score": 0.2}],
                },
                {
                    "assessment_id": "a2",
                    "created_at": "2026-08-02T10:00:00+08:00",
                    "items": [{"concept_id": "c1", "prompt_type": "recall", "result": "partial", "score": 0.5}],
                },
                {
                    "assessment_id": "a3",
                    "created_at": "2026-08-03T10:00:00+08:00",
                    "items": [{"concept_id": "c1", "prompt_type": "recall", "result": "correct", "score": 0.9}],
                },
                {
                    "assessment_id": "a4",
                    "created_at": "2026-08-03T11:00:00+08:00",
                    "items": [{"concept_id": "c2", "prompt_type": "transfer", "result": "correct", "score": 0.9}],
                },
            ],
        )

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["learning_curve"]["retrieval"]["status"], "recovering")
        self.assertEqual(result["learning_curve"]["transfer"]["status"], "insufficient_data")

    def test_empty_records_report_insufficient_data(self):
        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["data_quality"]["status"], "insufficient_data")
        self.assertEqual(result["recommendation"]["code"], "collect_evidence")

    def test_malformed_jsonl_is_partial_but_does_not_crash(self):
        (self.root / "sessions.jsonl").write_text("{bad json\n", encoding="utf-8")

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["data_quality"]["status"], "partial")
        self.assertIn("sessions.jsonl_invalid_line_1", result["data_quality"]["reasons"])

    def test_invalid_timestamp_and_target_are_reported(self):
        self.write_json("profile.json", {"timezone": "Asia/Shanghai", "target_minutes_per_week": 0})
        self.write_jsonl(
            "sessions.jsonl",
            [{"session_id": "bad", "ended_at": "not-a-time", "duration_min": 30, "status": "complete"}],
        )

        result = analyze(self.root, as_of="2026-08-08")

        self.assertEqual(result["data_quality"]["status"], "partial")
        self.assertIn("invalid_target_minutes_per_week", result["data_quality"]["reasons"])
        self.assertIn("no_sessions_in_window", result["data_quality"]["reasons"])
        self.assertEqual(result["time"]["measurement_status"], "unknown")
        self.assertIsNone(result["time"]["actual_minutes"])
        self.assertEqual(result["time"]["unknown_timestamp_count"], 1)

    def test_state_projection_matches_standalone_analyzer(self):
        self.write_json("goals.json", {"subject": "test", "operational_goal": "produce evidence"})
        self.write_json("roadmap.json", {"stages": [{"id": "s1", "title": "Start", "status": "current"}]})
        self.write_json("checkpoint.json", {"next_action": "test"})
        for name in ("decisions.jsonl", "coaching_events.jsonl"):
            (self.root / name).write_text("", encoding="utf-8")

        state = build_state(self.root)

        self.assertEqual(state["analytics"], analyze(self.root))


if __name__ == "__main__":
    unittest.main()
