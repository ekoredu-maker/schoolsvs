from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import hwpx_engine  # noqa: E402


class HWPXEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.template_dir = self.root / "templates"
        self.output_dir = self.root / "output"
        self.analysis_dir = self.template_dir / "_analysis"
        self.archive_dir = self.template_dir / "_archive"
        self.template_dir.mkdir()
        self.output_dir.mkdir()

        self.old_template_dir = hwpx_engine.TEMPLATE_DIR
        self.old_output_dir = hwpx_engine.OUTPUT_DIR
        self.old_analysis_dir = hwpx_engine.ANALYSIS_DIR
        self.old_archive_dir = hwpx_engine.ARCHIVE_DIR
        self.old_registry_path = hwpx_engine.REGISTRY_PATH
        hwpx_engine.TEMPLATE_DIR = self.template_dir
        hwpx_engine.OUTPUT_DIR = self.output_dir
        hwpx_engine.ANALYSIS_DIR = self.analysis_dir
        hwpx_engine.ARCHIVE_DIR = self.archive_dir
        hwpx_engine.REGISTRY_PATH = self.root / "document_registry.json"

        registry = {
            "version": "test",
            "documents": {
                "sample": {
                    "label": "테스트 서식",
                    "template": "sample.hwpx",
                    "fields": {
                        "SCHOOL_NAME": "school.name",
                        "CASE_NO": "case.caseNo",
                        "VICTIM_NAMES": "victims.names",
                        "INCIDENT_SUMMARY": "case.summary"
                    }
                }
            }
        }
        hwpx_engine.REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

        with zipfile.ZipFile(self.template_dir / "sample.hwpx", "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", "application/hwp+zip")
            zf.writestr(
                "Contents/section0.xml",
                '<?xml version="1.0" encoding="UTF-8"?><root><p>{{SCHOOL_NAME}}</p><p>{{CASE_NO}}</p><p>{{VICTIM_NAMES}}</p><p>{{INCIDENT_SUMMARY}}</p></root>'
            )
            zf.writestr("META-INF/manifest.xml", '<?xml version="1.0" encoding="UTF-8"?><manifest/>')

    def tearDown(self):
        hwpx_engine.TEMPLATE_DIR = self.old_template_dir
        hwpx_engine.OUTPUT_DIR = self.old_output_dir
        hwpx_engine.ANALYSIS_DIR = self.old_analysis_dir
        hwpx_engine.ARCHIVE_DIR = self.old_archive_dir
        hwpx_engine.REGISTRY_PATH = self.old_registry_path
        self.tmp.cleanup()

    def sample_case(self):
        return {
            "id": "case_1",
            "caseNo": "2026-0001",
            "school": "제천테스트초",
            "summary": "교실에서 발생한 테스트 사안",
            "victims": [{"name": "피해학생1"}, {"name": "피해학생2"}],
            "perps": [{"name": "가해학생"}],
        }

    def _new_original_bytes(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            zf.writestr(
                "Contents/section0.xml",
                '<?xml version="1.0" encoding="UTF-8"?><root><p>학교명</p><p>접수번호</p><p>사안 개요</p></root>',
                compress_type=zipfile.ZIP_DEFLATED,
            )
            zf.writestr("META-INF/manifest.xml", '<manifest/>', compress_type=zipfile.ZIP_DEFLATED)
        return buf.getvalue()

    def test_inspect_template_finds_tokens(self):
        info = hwpx_engine.inspect_template(self.template_dir / "sample.hwpx")
        self.assertEqual(info["tokenCount"], 4)
        self.assertIn("CASE_NO", info["tokens"])
        self.assertIn("INCIDENT_SUMMARY", info["tokens"])
        self.assertTrue(any("CASE_NO" in item for group in info["textSamples"] for item in group["items"]))

    def test_generate_document_replaces_tokens(self):
        result = hwpx_engine.generate_document("sample", self.sample_case())
        self.assertTrue(result.output_path.exists())
        self.assertEqual(result.missing_tokens, [])
        with zipfile.ZipFile(result.output_path, "r") as zf:
            text = zf.read("Contents/section0.xml").decode("utf-8")
            self.assertEqual(zf.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
        self.assertIn("제천테스트초", text)
        self.assertIn("2026-0001", text)
        self.assertIn("피해학생1, 피해학생2", text)
        self.assertNotIn("{{CASE_NO}}", text)

    def test_document_list_reports_template_ready(self):
        docs = hwpx_engine.list_documents()
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0]["templateReady"])
        self.assertTrue(docs[0]["mappingReady"])
        self.assertFalse(docs[0]["analysisReady"])

    def test_register_template_archives_previous_and_saves_analysis(self):
        result = hwpx_engine.register_template("sample", self._new_original_bytes(), "공식원본.hwpx")
        self.assertEqual(result["template"], "sample.hwpx")
        self.assertEqual(result["originalName"], "공식원본.hwpx")
        self.assertIsNotNone(result["archivedPrevious"])
        self.assertTrue((self.archive_dir / result["archivedPrevious"]).exists())
        self.assertTrue((self.analysis_dir / "sample.json").exists())
        analysis = hwpx_engine.get_saved_analysis("sample")
        self.assertTrue(analysis["mimetypeStored"])
        self.assertTrue(any("학교명" in item for group in analysis["textSamples"] for item in group["items"]))
        docs = hwpx_engine.list_documents()
        self.assertTrue(docs[0]["analysisReady"])

    def test_missing_template_raises_clear_error(self):
        (self.template_dir / "sample.hwpx").unlink()
        with self.assertRaises(FileNotFoundError):
            hwpx_engine.generate_document("sample", self.sample_case())


if __name__ == "__main__":
    unittest.main(verbosity=2)
