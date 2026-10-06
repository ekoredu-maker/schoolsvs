from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import hwpx_engine  # noqa: E402
import mapping_service  # noqa: E402


class MappingServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_registry = hwpx_engine.REGISTRY_PATH
        self.old_analysis = hwpx_engine.ANALYSIS_DIR
        self.old_mapping_dir = mapping_service.MAPPING_DIR
        self.old_mapping_registry = mapping_service.REGISTRY_PATH
        self.old_mapping_analysis = mapping_service.ANALYSIS_DIR

        registry = self.root / "document_registry.json"
        registry.write_text(json.dumps({
            "version": "test",
            "documents": {
                "form10_case_report": {
                    "label": "[서식10] 학교폭력 사안접수 보고서",
                    "template": "form10.hwpx",
                    "fields": {
                        "SCHOOL_NAME": "school.name",
                        "CASE_NO": "case.caseNo",
                        "VICTIM_NAMES": "victims.names",
                        "INCIDENT_SUMMARY": "case.summary"
                    }
                }
            }
        }, ensure_ascii=False), encoding="utf-8")

        analysis_dir = self.root / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "form10_case_report.json").write_text(json.dumps({
            "textSnippets": [
                {"file": "Contents/section0.xml", "text": "학교명"},
                {"file": "Contents/section0.xml", "text": "사안번호"},
                {"file": "Contents/section0.xml", "text": "피해관련학생"},
                {"file": "Contents/section0.xml", "text": "사안 개요"}
            ]
        }, ensure_ascii=False), encoding="utf-8")

        hwpx_engine.REGISTRY_PATH = registry
        hwpx_engine.ANALYSIS_DIR = analysis_dir
        mapping_service.REGISTRY_PATH = registry
        mapping_service.ANALYSIS_DIR = analysis_dir
        mapping_service.MAPPING_DIR = self.root / "mappings"

    def tearDown(self):
        hwpx_engine.REGISTRY_PATH = self.old_registry
        hwpx_engine.ANALYSIS_DIR = self.old_analysis
        mapping_service.REGISTRY_PATH = self.old_mapping_registry
        mapping_service.ANALYSIS_DIR = self.old_mapping_analysis
        mapping_service.MAPPING_DIR = self.old_mapping_dir
        self.tmp.cleanup()

    def test_workspace_suggests_anchor_candidates(self):
        ws = mapping_service.build_mapping_workspace("form10_case_report")
        self.assertTrue(ws["analysisReady"])
        school = next(x for x in ws["suggestions"] if x["token"] == "SCHOOL_NAME")
        self.assertEqual(school["candidates"][0]["text"], "학교명")
        summary = next(x for x in ws["suggestions"] if x["token"] == "INCIDENT_SUMMARY")
        self.assertEqual(summary["candidates"][0]["text"], "사안 개요")

    def test_save_and_reload_mapping(self):
        saved = mapping_service.save_mapping("form10_case_report", [
            {"token": "SCHOOL_NAME", "source": "school.name", "anchor": "학교명", "confirmed": True},
            {"token": "CASE_NO", "source": "case.caseNo", "anchor": "사안번호", "confirmed": False},
        ], status="reviewed")
        self.assertEqual(saved["status"], "reviewed")
        loaded = mapping_service.load_mapping("form10_case_report")
        self.assertEqual(len(loaded["items"]), 2)
        self.assertTrue(loaded["items"][0]["confirmed"])

    def test_progress_counts_confirmed_fields(self):
        mapping_service.save_mapping("form10_case_report", [
            {"token": "SCHOOL_NAME", "source": "school.name", "anchor": "학교명", "confirmed": True},
        ])
        ws = mapping_service.build_mapping_workspace("form10_case_report")
        self.assertEqual(ws["progress"]["total"], 4)
        self.assertEqual(ws["progress"]["confirmed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
