from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import document_readiness  # noqa: E402
import hwpx_engine  # noqa: E402


class DocumentReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.templates = self.root / "templates"
        self.templates.mkdir()
        self.registry = self.root / "document_registry.json"
        self.registry.write_text(json.dumps({
            "version": "test",
            "documents": {
                "form10_case_report": {
                    "label": "[서식10] 학교폭력 사안접수 보고서",
                    "template": "form10.hwpx",
                    "fields": {"CASE_NO": "case.caseNo"}
                }
            }
        }, ensure_ascii=False), encoding="utf-8")

        self.old_registry = hwpx_engine.REGISTRY_PATH
        self.old_template_dir = document_readiness.TEMPLATE_DIR
        hwpx_engine.REGISTRY_PATH = self.registry
        document_readiness.TEMPLATE_DIR = self.templates

    def tearDown(self):
        hwpx_engine.REGISTRY_PATH = self.old_registry
        document_readiness.TEMPLATE_DIR = self.old_template_dir
        self.tmp.cleanup()

    def complete_case(self):
        return {
            "id": "case-1",
            "caseNo": "2026-001",
            "school": "테스트초",
            "recvAt": "2026-10-05T09:00",
            "incidentDate": "2026-10-04",
            "incidentPlace": "교실",
            "violenceType": "언어폭력",
            "summary": "테스트 사안",
            "victims": [{"name": "피해학생"}],
            "perps": [{"name": "가해학생"}],
            "separation": "즉시분리 시행",
            "sepPeriod": "3일",
            "separationPlace": "별도 공간",
            "officeReport": "보고완료",
            "officeDate": "2026-10-05",
            "_hybrid": {
                "atoz": {
                    "schemaVersion": "cb-atoz-2026-v0.9",
                    "reporterName": "신고자",
                    "reporterRole": "보호자",
                    "recognitionPath": "보호자 신고",
                    "receiverName": "담당교사",
                    "receiverRole": "학교폭력담당교사",
                    "investigationMode": "investigator",
                    "no2ActionDate": "2026-10-05T09:30",
                    "guardianNoticeChecked": True,
                    "interviewAvailabilityChecked": True,
                    "victimInterviewTime": "2026-10-05 11:00",
                    "perpInterviewTime": "2026-10-05 14:00",
                    "otherSchoolRelated": False,
                    "victimRecoveryOpinion": "참여 검토",
                    "perpRecoveryOpinion": "대화 의사 있음"
                },
                "studentProfiles": [
                    {
                        "role": "victim", "name": "피해학생", "schoolName": "테스트초",
                        "grade": "6", "classNo": "1", "number": "1", "gender": "여",
                        "guardianNoticeAt": "2026-10-05T09:20", "guardianNoticeMethod": "유선"
                    },
                    {
                        "role": "perp", "name": "가해학생", "schoolName": "테스트초",
                        "grade": "6", "classNo": "2", "number": "2", "gender": "남",
                        "guardianNoticeAt": "2026-10-05T09:25", "guardianNoticeMethod": "유선"
                    }
                ]
            }
        }

    def test_complete_content_and_template_is_ready(self):
        (self.templates / "form10.hwpx").write_bytes(b"placeholder")
        result = document_readiness.form10_readiness(self.complete_case())
        self.assertTrue(result["contentReady"], result)
        self.assertTrue(result["templateReady"], result)
        self.assertTrue(result["mappingReady"], result)
        self.assertTrue(result["ready"], result)
        self.assertEqual(result["score"], 100)

    def test_missing_student_details_blocks_generation(self):
        (self.templates / "form10.hwpx").write_bytes(b"placeholder")
        case = self.complete_case()
        case["_hybrid"]["studentProfiles"][0]["guardianNoticeMethod"] = ""
        result = document_readiness.form10_readiness(case)
        self.assertFalse(result["ready"])
        students = next(x for x in result["sections"] if x["key"] == "students")
        self.assertFalse(students["ready"])
        self.assertTrue(any("보호자 통보방법" in x for x in students["missing"]))

    def test_missing_template_blocks_generation_even_when_content_complete(self):
        result = document_readiness.form10_readiness(self.complete_case())
        self.assertTrue(result["contentReady"], result)
        self.assertFalse(result["templateReady"])
        self.assertFalse(result["ready"])
        self.assertTrue(any("템플릿 미등록" in x for x in result["blocking"]))

    def test_basic_missing_field_is_visible_by_section(self):
        (self.templates / "form10.hwpx").write_bytes(b"placeholder")
        case = self.complete_case()
        case["incidentPlace"] = ""
        result = document_readiness.form10_readiness(case)
        basic = next(x for x in result["sections"] if x["key"] == "basic")
        self.assertFalse(basic["ready"])
        self.assertIn("발생장소", basic["missing"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
