import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
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
from study_workbook import read_template_labels, summary_sheet_names, template_sheet_names, write_template_workbook  # noqa: E402


class StudySummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.root = self.workspace / ".study"
        self.root.mkdir(parents=True)
        self.output_dir = self.workspace / "custom-reports"
        self.original_cwd = Path.cwd()
        os.chdir(self.workspace)
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
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")

    def write_jsonl(self, name, rows):
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        (self.root / name).write_text(content, encoding="utf-8")

    def edit_template_label(self, source, target, key, value):
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(source) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for info, data in entries:
                if info.filename == "xl/worksheets/sheet5.xml":
                    worksheet = ET.fromstring(data)
                    for row in worksheet.findall("main:sheetData/main:row", namespace):
                        cells = row.findall("main:c", namespace)
                        key_cell = next((cell for cell in cells if cell.attrib.get("r", "").startswith("A")), None)
                        if key_cell is None:
                            continue
                        key_text = "".join(item.text or "" for item in key_cell.findall(".//main:t", namespace))
                        if key_text != key:
                            continue
                        value_cell = next((cell for cell in cells if cell.attrib.get("r", "").startswith("B")), None)
                        if value_cell is None:
                            continue
                        text_node = value_cell.find(".//main:t", namespace)
                        if text_node is None:
                            raise AssertionError("template label cell is not inline text")
                        text_node.text = value
                        data = ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)
                        break
                archive.writestr(info, data)

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
        self.assertEqual(preview["record"]["workbook_format"], "xlsx")
        self.assertNotIn("markdown", preview["record"])
        self.assertFalse(Path(preview["record"]["workbook_path"]).exists())

    def test_default_output_uses_working_directory(self):
        run_dir = self.workspace / "invocation"
        run_dir.mkdir()
        os.chdir(run_dir)
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])

        result = generate_summary(self.root, "overall", as_of_value="2026-08-31")

        self.assertEqual(Path(result["workbook_path"]).parent, run_dir / "study-reports")
        self.assertTrue(Path(result["workbook_path"]).is_file())
        os.chdir(self.workspace)

    def test_new_clock_session_records_total_time_fields_without_time_categories(self):
        args = study_clock.build_parser().parse_args(
            [
                "--study-root",
                str(self.root),
                "start",
                "--subject",
                "Python",
                "--planned-minutes",
                "30",
            ]
        )

        with contextlib.redirect_stdout(io.StringIO()):
            study_clock.command_start(args)

        session = json.loads((self.root / "active-session.json").read_text(encoding="utf-8"))
        self.assertIn("duration_min", session)
        self.assertIn("planned_minutes", session)
        self.assertNotIn("active_minutes", session)
        self.assertNotIn("passive_minutes", session)

    def test_legacy_time_categories_are_ignored_but_total_time_is_kept(self):
        legacy = self.session("legacy", "2026-08-24", minutes=30, planned=45)
        legacy.update({"active_minutes": 20, "passive_minutes": 10})
        self.write_jsonl("sessions.jsonl", [legacy])

        result = generate_summary(self.root, "overall", as_of_value="2026-08-31")
        snapshot = result["record"]["snapshot"]
        self.assertEqual(snapshot["progress"]["period"]["actual_minutes"], 30.0)
        self.assertEqual(snapshot["efficiency"]["actual_vs_planned"]["planned_minutes"], 45.0)
        self.assertNotIn("active_time_share", snapshot["efficiency"])
        self.assertNotIn("active_minutes", json.dumps(result["record"], ensure_ascii=False))
        self.assertNotIn("passive_minutes", json.dumps(result["record"], ensure_ascii=False))

        with zipfile.ZipFile(result["workbook_path"]) as archive:
            workbook_text = "\n".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith(".xml")
            )
        for forbidden in ("active_minutes", "passive_minutes", "active_time_share", "主动练习", "被动学习"):
            self.assertNotIn(forbidden, workbook_text)

        source = json.loads((self.root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(source["active_minutes"], 20)
        self.assertEqual(source["passive_minutes"], 10)

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
        self.assertTrue(Path(first["workbook_path"]).is_file())

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

    def test_unreliable_interrupted_span_is_not_presented_as_learning_time(self):
        self.write_jsonl(
            "sessions.jsonl",
            [
                self.session("normal", "2026-08-24", minutes=30),
                {
                    "session_id": "interrupted",
                    "started_at": "2026-08-25T10:00:00+08:00",
                    "ended_at": "2026-08-29T10:00:00+08:00",
                    "duration_min": 5760,
                    "status": "interrupted",
                },
            ],
        )

        result = build_summary(self.root, "overall", as_of_value="2026-08-31")
        snapshot = result["snapshot"]

        self.assertEqual(snapshot["progress"]["period"]["actual_minutes"], 30.0)
        self.assertEqual(snapshot["progress"]["period"]["session_count"], 1)
        self.assertEqual(snapshot["progress"]["period"]["study_days"], 1)
        self.assertEqual(snapshot["progress"]["period"]["excluded_session_count"], 1)
        self.assertEqual(snapshot["progress"]["period"]["planned_minutes"], 45.0)
        self.assertEqual(snapshot["data_quality"]["status"], "partial")
        self.assertIn("interrupted_duration_unreliable", snapshot["data_quality"]["reasons"])

    def test_due_generation_skips_empty_workspace_and_is_idempotent(self):
        empty = generate_due(self.root, as_of_value="2026-08-31")
        self.assertEqual(empty["generated_count"], 0)
        self.assertFalse((self.root / "summaries.jsonl").exists())

        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        pending = check_due(self.root, as_of_value="2026-08-31")
        self.assertEqual(pending["status"], "awaiting_confirmation")
        self.assertTrue(pending["confirmation_required"])
        self.assertEqual(pending["due_count"], 2)
        self.assertEqual(pending["generated_count"], 0)
        self.assertEqual(len(pending["due_summaries"]), 2)
        self.assertFalse((self.root / "summaries.jsonl").exists())

        first = generate_due(self.root, as_of_value="2026-08-31")
        second = generate_due(self.root, as_of_value="2026-08-31")

        self.assertEqual(first["generated_count"], 2)
        self.assertEqual(first["content_language"], "zh-CN")
        self.assertEqual(second["generated_count"], 0)
        self.assertTrue(all(Path(item["workbook_path"]).is_file() for item in first["generated"]))
        self.assertTrue(all(item["workbook_sheets"] for item in first["generated"]))
        due = check_due(self.root, as_of_value="2026-08-31")
        self.assertEqual(due["due_count"], 0)

    def test_state_status_only_asks_before_generating_due_summaries(self):
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = state_main(["--study-root", str(self.root), "status", "--json"])

        self.assertEqual(code, 0)
        state = json.loads(output.getvalue())
        self.assertEqual(state["summaries"]["status"], "awaiting_confirmation")
        self.assertTrue(state["summaries"]["confirmation_required"])
        self.assertEqual(state["summaries"]["due_count"], 2)
        self.assertEqual(state["summaries"]["generated_count"], 0)
        self.assertEqual(state["summaries"]["content_language"], "zh-CN")
        self.assertIn("是否现在生成", state["summaries"]["prompt"])
        self.assertEqual(len(state["summaries"]["due_summaries"]), 2)
        self.assertFalse((self.root / "summaries.jsonl").exists())
        self.assertFalse((self.workspace / "study-reports").exists())

    def test_clock_stop_only_asks_before_generating_due_summaries(self):
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
        self.assertEqual(result["summaries"]["status"], "awaiting_confirmation")
        self.assertTrue(result["summaries"]["confirmation_required"])
        self.assertEqual(result["summaries"]["due_count"], 2)
        self.assertEqual(result["summaries"]["generated_count"], 0)
        self.assertFalse((self.root / "active-session.json").exists())
        session_rows = (self.root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(session_rows), 1)
        self.assertNotIn("summaries", json.loads(session_rows[0]))
        self.assertFalse((self.root / "summaries.jsonl").exists())
        self.assertFalse((self.workspace / "study-reports").exists())

    def test_clock_stop_keeps_session_when_summary_log_is_unusable(self):
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
        self.assertEqual(result["summaries"]["status"], "awaiting_confirmation")
        self.assertEqual(result["summaries"]["generated_count"], 0)
        self.assertEqual(result["summaries"]["due_count"], 2)
        self.assertEqual(len((self.root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_cli_json_output_can_be_requested_before_or_after_command(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = summary_main(
                [
                    "--study-root",
                    str(self.root),
                    "--json",
                    "--output-dir",
                    str(self.output_dir),
                    "generate",
                    "--kind",
                    "overall",
                    "--as-of",
                    "2026-08-31",
                ]
            )

        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["record"]["content_language"], "zh-CN")
        self.assertEqual(result["record"]["workbook_format"], "xlsx")
        self.assertEqual(result["record"]["workbook_schema_version"], 2)
        self.assertEqual(result["record"]["workbook_sheets"], summary_sheet_names("zh"))
        self.assertTrue(Path(result["record"]["workbook_path"]).is_file())
        self.assertNotIn("markdown", result["record"])

    def test_generated_workbook_is_valid_and_contains_localized_sheets(self):
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])

        result = generate_summary(self.root, "overall", as_of_value="2026-08-31")
        workbook_path = Path(result["workbook_path"])

        self.assertTrue(workbook_path.is_file())
        with zipfile.ZipFile(workbook_path) as archive:
            self.assertIsNone(archive.testzip())
            names = set(archive.namelist())
            self.assertIn("[Content_Types].xml", names)
            self.assertIn("xl/workbook.xml", names)
            self.assertIn("xl/worksheets/sheet1.xml", names)
            workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
            namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            sheet_names = [item.attrib["name"] for item in workbook_xml.findall("main:sheets/main:sheet", namespace)]
            self.assertEqual(sheet_names, summary_sheet_names("zh"))
            self.assertNotIn("自定义文字", sheet_names)
            for index in range(1, 5):
                ET.fromstring(archive.read("xl/worksheets/sheet%d.xml" % index))
            overview_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("\u6838\u5fc3\u7ed3\u8bba", overview_xml)
            self.assertIn("\u4f18\u5148\u8ba1\u5212", overview_xml)
            self.assertIn("\u5b89\u6392\u4f9d\u636e", overview_xml)
            self.assertIn("\u9884\u671f\u7ed3\u679c", overview_xml)
            self.assertNotIn("\u81ea\u5b9a\u4e49\u6587\u5b57", overview_xml)
            for obsolete in ("\u5148\u770b\u8fd9\u91cc", "\u8fd9\u4efd\u603b\u7ed3\u662f\u4ec0\u4e48\u7528", "\u4e3a\u4ec0\u4e48\u4e0d\u53ea\u770b\u65f6\u95f4"):
                self.assertNotIn(obsolete, overview_xml)

    def test_cli_text_output_is_a_workbook_path_not_a_markdown_table(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = summary_main(
                [
                    "--study-root",
                    str(self.root),
                    "generate",
                    "--kind",
                    "overall",
                    "--as-of",
                    "2026-08-31",
                    "--output-dir",
                    str(self.output_dir),
                ]
            )

        self.assertEqual(code, 0)
        rendered = output.getvalue()
        self.assertIn(".xlsx", rendered)
        self.assertNotIn("|", rendered)
        self.assertNotIn("markdown", rendered.lower())

    def test_legacy_markdown_summary_is_upgraded_to_workbook_record(self):
        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        self.write_jsonl(
            "summaries.jsonl",
            [
                {
                    "summary_key": "week:2026-08-24..2026-08-30",
                    "kind": "week",
                    "markdown": "# legacy summary",
                }
            ],
        )

        result = generate_summary(self.root, "week", as_of_value="2026-08-31")

        self.assertEqual(result["status"], "upgraded")
        rows = (self.root / "summaries.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        record = json.loads(rows[0])
        self.assertNotIn("markdown", record)
        self.assertEqual(record["workbook_format"], "xlsx")
        self.assertTrue(Path(record["workbook_path"]).is_file())

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

    def test_template_command_creates_editable_workbook(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = summary_main(
                ["template", "--output-dir", str(self.output_dir)]
            )

        self.assertEqual(code, 0)
        template_path = self.output_dir / "studyany-summary-template.xlsx"
        self.assertTrue(template_path.is_file())
        self.assertEqual(read_template_labels(template_path)["one_sentence"], "核心结论")
        self.assertEqual(len(summary_sheet_names("zh")), 4)
        self.assertEqual(template_sheet_names("zh")[-1], "自定义文字")
        self.assertIn(".xlsx", output.getvalue())
        with zipfile.ZipFile(template_path) as archive:
            workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
            namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            sheet_names = [item.attrib["name"] for item in workbook_xml.findall("main:sheets/main:sheet", namespace)]
        self.assertEqual(sheet_names, template_sheet_names("zh"))

    def test_custom_template_label_is_used_by_generated_workbook(self):
        source = self.output_dir / "source-template.xlsx"
        edited = self.output_dir / "edited-template.xlsx"
        write_template_workbook(source, {}, "zh")
        self.edit_template_label(source, edited, "one_sentence", "我的结论")

        self.write_jsonl("sessions.jsonl", [self.session("s1", "2026-08-24")])
        result = generate_summary(
            self.root,
            "overall",
            as_of_value="2026-08-31",
            template_path=edited,
        )

        self.assertEqual(read_template_labels(edited)["one_sentence"], "我的结论")
        self.assertEqual(result["record"]["template_path"], str(edited.resolve()))
        with zipfile.ZipFile(result["workbook_path"]) as archive:
            overview_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("我的结论", overview_xml)

    def test_explicit_learning_state_is_reported_without_inference(self):
        rows = [
            dict(self.session("s1", "2026-08-24"), energy="精力一般", distraction="偶尔分心"),
            self.session("s2", "2026-08-25"),
        ]
        self.write_jsonl("sessions.jsonl", rows)

        result = build_summary(self.root, "overall", as_of_value="2026-08-31")
        state = result["snapshot"]["learning_state"]

        self.assertEqual(state["energy"]["recorded_count"], 1)
        self.assertEqual(state["energy"]["latest"], "精力一般")
        self.assertEqual(state["distraction"]["recorded_count"], 1)
        self.assertEqual(state["distraction"]["latest"], "偶尔分心")
        self.assertNotIn("meaning", result["snapshot"]["learner_view"])

    def test_unreliable_interrupted_record_is_excluded_from_state_observation(self):
        self.write_jsonl(
            "sessions.jsonl",
            [
                {
                    "session_id": "broken",
                    "started_at": "2026-08-25T10:00:00+08:00",
                    "ended_at": "2026-08-29T10:00:00+08:00",
                    "duration_min": 5760,
                    "planned_minutes": 120,
                    "energy": "精力很低",
                    "status": "interrupted",
                }
            ],
        )

        result = build_summary(self.root, "overall", as_of_value="2026-08-31")
        snapshot = result["snapshot"]

        self.assertEqual(snapshot["progress"]["period"]["session_count"], 0)
        self.assertEqual(snapshot["progress"]["period"]["study_days"], 0)
        self.assertIsNone(snapshot["progress"]["period"]["planned_minutes"])
        self.assertEqual(snapshot["learning_state"]["energy"]["recorded_count"], 0)
        self.assertIn("明显中断", snapshot["learner_view"]["data_note"])


if __name__ == "__main__":
    unittest.main()
