from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import storage  # noqa: E402
from workflow import calculate_deadlines, route_state, stage_gates, validate_case, workflow_state  # noqa: E402


SAMPLE = {
    "id": "case_test_001",
    "caseNo": "2026-0001",
    "recvAt": "2026-10-04T09:00",
    "incidentDate": "2026-10-03",
    "incidentPlace": "교실",
    "reportType": "교사 인지",
    "violenceType": "언어폭력",
    "status": "접수중",
    "summary": "테스트 사안",
    "victims": [{"name": "피해학생"}],
    "perps": [{"name": "가해학생"}],
}


def initial_complete() -> dict:
    data = dict(SAMPLE)
    data.update({
        "separation": "즉시분리 미시행",
        "sepReason": "피해관련학생이 분리 조치에 반대 의사를 표명한 경우",
        "officeReport": "보고완료",
        "officeDate": "2026-10-05",
    })
    return data


class WorkflowTests(unittest.TestCase):
    def test_valid_sample(self):
        result = validate_case(dict(SAMPLE))
        self.assertTrue(result["ok"], result)

    def test_missing_named_student_is_error(self):
        data = dict(SAMPLE)
        data["victims"] = [{"name": ""}]
        result = validate_case(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any(x["field"] == "victims" for x in result["errors"]))

    def test_closed_case_requires_closed_date(self):
        data = dict(SAMPLE)
        data["status"] = "종결"
        result = validate_case(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any(x["field"] == "closedDate" for x in result["errors"]))

    def test_declared_stage_cannot_skip_initial_response_gate(self):
        data = dict(SAMPLE)
        data["status"] = "조사중"
        result = workflow_state(data)
        self.assertEqual(result["declaredStage"], "사실조사")
        self.assertEqual(result["stage"], "초기대응")
        self.assertTrue(any(x["field"] == "status" for x in result["validation"]["warnings"]))

    def test_stage_gates_progress_in_order(self):
        gates = stage_gates(initial_complete())
        self.assertTrue(gates[0]["complete"])
        self.assertTrue(gates[1]["complete"])
        self.assertEqual(gates[2]["state"], "done")  # 조사관 미사용 시 현재 입력구조상 선행조건 없음
        self.assertEqual(gates[3]["state"], "current")
        self.assertIn("전담기구 개최일", gates[3]["missing"])

    def test_route_disabled_before_committee(self):
        route = route_state(initial_complete())
        self.assertFalse(route["enabled"])
        self.assertIsNone(route["selected"])

    def test_route_is_human_selected_after_committee(self):
        data = initial_complete()
        data["committeeDate"] = "2026-10-08"
        data["_hybrid"] = {"route": "self_resolution_review"}
        route = route_state(data)
        self.assertTrue(route["enabled"])
        self.assertTrue(route["requiresHumanDecision"])
        self.assertEqual(route["selectedLabel"], "학교장 자체해결 검토")

    def test_24_hour_separation_deadline(self):
        items = calculate_deadlines(dict(SAMPLE), now=datetime.fromisoformat("2026-10-05T08:00"))
        sep = next(x for x in items if x["key"] == "separation_decision")
        self.assertEqual(sep["dueAt"], "2026-10-05T09:00")
        self.assertEqual(sep["status"], "pending")
        self.assertEqual(sep["remainingMinutes"], 60)

    def test_24_hour_separation_deadline_overdue(self):
        items = calculate_deadlines(dict(SAMPLE), now=datetime.fromisoformat("2026-10-05T09:01"))
        sep = next(x for x in items if x["key"] == "separation_decision")
        self.assertEqual(sep["status"], "overdue")
        self.assertTrue(sep["overdue"])

    def test_48_hour_office_report_deadline(self):
        items = calculate_deadlines(dict(SAMPLE), now=datetime.fromisoformat("2026-10-06T08:59"))
        report = next(x for x in items if x["key"] == "office_report")
        self.assertEqual(report["dueAt"], "2026-10-06T09:00")
        self.assertEqual(report["status"], "pending")
        self.assertEqual(report["remainingMinutes"], 1)

    def test_completed_report_stops_deadline_warning(self):
        data = dict(SAMPLE)
        data["officeReport"] = "보고완료"
        data["officeDate"] = "2026-10-05"
        items = calculate_deadlines(data, now=datetime.fromisoformat("2026-10-07T09:00"))
        report = next(x for x in items if x["key"] == "office_report")
        self.assertEqual(report["status"], "completed")
        self.assertFalse(report["overdue"])

    def test_separation_limit_over_7_days_is_error(self):
        data = dict(SAMPLE)
        data["separation"] = "즉시분리 시행"
        data["sepPeriod"] = "8일"
        data["separationPlace"] = "별도 공간"
        result = validate_case(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any(x["field"] == "sepPeriod" for x in result["errors"]))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.DB_PATH = Path(self.tmp.name) / "schoolsvs.db"
        storage.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_upsert_and_read(self):
        storage.upsert_case(dict(SAMPLE))
        saved = storage.get_case(SAMPLE["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["caseNo"], SAMPLE["caseNo"])

    def test_update_does_not_duplicate(self):
        storage.upsert_case(dict(SAMPLE))
        changed = dict(SAMPLE)
        changed["status"] = "조사중"
        storage.upsert_case(changed)
        self.assertEqual(len(storage.list_cases()), 1)
        self.assertEqual(storage.get_case(SAMPLE["id"])["status"], "조사중")

    def test_delete(self):
        storage.upsert_case(dict(SAMPLE))
        self.assertTrue(storage.delete_case(SAMPLE["id"]))
        self.assertIsNone(storage.get_case(SAMPLE["id"]))

    def test_key_value_state(self):
        storage.set_value("counter", 7)
        self.assertEqual(storage.get_value("counter", 1), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
