from __future__ import annotations

import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from investigation_data import document_context, readiness  # noqa: E402


class InvestigationDataTests(unittest.TestCase):
    def complete_case(self):
        return {
            "investigationDate": "2026-10-08",
            "investigatorName": "김조사",
            "_hybrid": {
                "investigation": {
                    "schemaVersion": "cb-atoz-2026-form12-v0.19",
                    "kind": "first",
                    "investigationDate": "2026-10-08",
                    "authorName": "김조사",
                    "authorContact": "010-0000-0000",
                    "chronology": "10월 4일 신고 접수 후 관련학생 면담 및 자료를 확인함.",
                    "selfResolutionCriteria": {
                        "noLongTreatment": "met",
                        "noPropertyDamage": "met",
                        "notPersistent": "checking",
                        "notRetaliation": "met",
                    },
                    "selfResolutionOpinion": "현재까지 확인된 사실을 기준으로 검토 중",
                    "selfResolutionConsent": "피해학생·보호자 의사 확인 전",
                    "issues": [{
                        "title": "행위 횟수와 경위",
                        "victimClaim": "3회 있었다고 진술",
                        "perpClaim": "1회라고 진술",
                        "witnessStatement": "목격학생 진술 확보",
                        "evidence": "복도 CCTV 10월 4일 영상",
                    }],
                    "judgmentFactors": {
                        "severity": "상해 정도와 행위 방법 확인",
                        "persistence": "진술 간 횟수 차이를 추가 확인 중",
                        "intentionality": "행위 전후 상황을 확인함",
                        "remorse": "조사과정에서 사과 의사를 표현함",
                        "reconciliation": "관계회복 프로그램 참여 의사 확인 중",
                        "guidancePossibility": "재발방지 교육 참여 가능",
                        "victimDisability": "해당 없음",
                    },
                    "emergencyMeasures": "가해관련학생 제2호 조치 시행",
                    "recurrenceHistory": "확인된 재발 이력 없음",
                    "specialNotes": "특이사항 없음",
                    "otherNotes": "",
                }
            }
        }

    def test_complete_core_is_ready(self):
        result = readiness(self.complete_case())
        self.assertTrue(result["ready"], result)
        self.assertEqual(result["score"], 100)

    def test_missing_chronology_blocks_readiness(self):
        case = self.complete_case()
        case["_hybrid"]["investigation"]["chronology"] = ""
        result = readiness(case)
        self.assertFalse(result["ready"])
        self.assertTrue(any("사안 경위" in x for x in result["missing"]))

    def test_four_self_resolution_opinions_are_required_as_records(self):
        case = self.complete_case()
        case["_hybrid"]["investigation"]["selfResolutionCriteria"]["notRetaliation"] = ""
        result = readiness(case)
        self.assertFalse(result["ready"])
        self.assertTrue(any("보복행위" in x for x in result["missing"]))

    def test_judgment_factors_are_recommended_not_auto_judged(self):
        case = self.complete_case()
        case["_hybrid"]["investigation"]["judgmentFactors"] = {}
        result = readiness(case)
        self.assertTrue(result["ready"], result)
        self.assertGreaterEqual(len(result["recommended"]), 7)
        self.assertIn("점수나 조치수준을 자동판정하지 않고", result["notice"])

    def test_context_formats_criteria_and_issues(self):
        context = document_context(self.complete_case())
        self.assertEqual(context["investigation.criteria.noLongTreatment"], "충족")
        self.assertEqual(context["investigation.criteria.notPersistent"], "확인 중")
        self.assertIn("주요 쟁점 1. 행위 횟수와 경위", context["investigation.issues"])
        self.assertIn("복도 CCTV", context["investigation.issues"])
        self.assertIn("사과 의사", context["investigation.factor.remorse"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
