from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import hwpx_engine  # noqa: E402
import mapping_service  # noqa: E402
import template_builder  # noqa: E402


class TemplateBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.templates = self.root / "templates"
        self.built = self.templates / "_built"
        self.reports = self.templates / "_build_reports"
        self.mappings = self.root / "mappings"
        self.templates.mkdir()
        self.registry = self.root / "document_registry.json"
        self.registry.write_text(json.dumps({
            "version": "test",
            "documents": {
                "sample": {
                    "label": "테스트 서식",
                    "template": "sample.hwpx",
                    "fields": {
                        "SCHOOL_NAME": "school.name",
                        "CASE_NO": "case.caseNo"
                    }
                }
            }
        }, ensure_ascii=False), encoding="utf-8")

        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<hp:section xmlns:hp="urn:test"><hp:tbl><hp:tr>
<hp:tc><hp:p><hp:run><hp:t>학교명</hp:t></hp:run></hp:p></hp:tc>
<hp:tc><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:tc>
<hp:tc><hp:p><hp:run><hp:t>사안번호</hp:t></hp:run></hp:p></hp:tc>
<hp:tc><hp:p><hp:run><hp:t>예시값</hp:t></hp:run></hp:p></hp:tc>
</hp:tr></hp:tbl></hp:section>'''
        with zipfile.ZipFile(self.templates / "sample.hwpx", "w") as zf:
            zf.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            zf.writestr("Contents/section0.xml", xml, compress_type=zipfile.ZIP_DEFLATED)

        self.original_bytes = (self.templates / "sample.hwpx").read_bytes()

        self.old_hwpx_registry = hwpx_engine.REGISTRY_PATH
        self.old_hwpx_template = hwpx_engine.TEMPLATE_DIR
        self.old_hwpx_built = hwpx_engine.BUILT_DIR
        self.old_map_registry = mapping_service.REGISTRY_PATH
        self.old_map_dir = mapping_service.MAPPING_DIR
        self.old_builder_template = template_builder.TEMPLATE_DIR
        self.old_builder_built = template_builder.BUILT_DIR
        self.old_builder_report = template_builder.REPORT_DIR

        hwpx_engine.REGISTRY_PATH = self.registry
        hwpx_engine.TEMPLATE_DIR = self.templates
        hwpx_engine.BUILT_DIR = self.built
        mapping_service.REGISTRY_PATH = self.registry
        mapping_service.MAPPING_DIR = self.mappings
        template_builder.TEMPLATE_DIR = self.templates
        template_builder.BUILT_DIR = self.built
        template_builder.REPORT_DIR = self.reports

    def tearDown(self):
        hwpx_engine.REGISTRY_PATH = self.old_hwpx_registry
        hwpx_engine.TEMPLATE_DIR = self.old_hwpx_template
        hwpx_engine.BUILT_DIR = self.old_hwpx_built
        mapping_service.REGISTRY_PATH = self.old_map_registry
        mapping_service.MAPPING_DIR = self.old_map_dir
        template_builder.TEMPLATE_DIR = self.old_builder_template
        template_builder.BUILT_DIR = self.old_builder_built
        template_builder.REPORT_DIR = self.old_builder_report
        self.tmp.cleanup()

    def save_complete_mapping(self):
        mapping_service.save_mapping("sample", [
            {"token": "SCHOOL_NAME", "source": "school.name", "anchor": "학교명", "xmlFile": "Contents/section0.xml", "strategy": "next_cell_replace", "confirmed": True},
            {"token": "CASE_NO", "source": "case.caseNo", "anchor": "사안번호", "xmlFile": "Contents/section0.xml", "strategy": "next_cell_replace", "confirmed": True},
        ], status="reviewed")

    def test_build_keeps_official_original_unchanged(self):
        self.save_complete_mapping()
        report = template_builder.build_template("sample")
        self.assertTrue((self.built / "sample.hwpx").exists())
        self.assertEqual((self.templates / "sample.hwpx").read_bytes(), self.original_bytes)
        self.assertEqual(sorted(report["insertedTokens"]), ["CASE_NO", "SCHOOL_NAME"])

    def test_next_cell_strategy_inserts_tokens_into_value_cells(self):
        self.save_complete_mapping()
        template_builder.build_template("sample")
        with zipfile.ZipFile(self.built / "sample.hwpx") as zf:
            text = zf.read("Contents/section0.xml").decode("utf-8")
        self.assertIn("<hp:t>{{SCHOOL_NAME}}</hp:t>", text)
        self.assertIn("<hp:t>{{CASE_NO}}</hp:t>", text)
        self.assertNotIn("예시값", text)
        self.assertIn("<hp:t>학교명</hp:t>", text)
        self.assertIn("<hp:t>사안번호</hp:t>", text)

    def test_unconfirmed_mapping_blocks_build(self):
        mapping_service.save_mapping("sample", [
            {"token": "SCHOOL_NAME", "source": "school.name", "anchor": "학교명", "confirmed": True}
        ], status="reviewed")
        with self.assertRaises(ValueError) as ctx:
            template_builder.build_template("sample")
        self.assertIn("확정되지 않은 필드 매핑", str(ctx.exception))

    def test_missing_anchor_blocks_build_without_partial_output(self):
        mapping_service.save_mapping("sample", [
            {"token": "SCHOOL_NAME", "source": "school.name", "anchor": "없는문구", "confirmed": True},
            {"token": "CASE_NO", "source": "case.caseNo", "anchor": "사안번호", "confirmed": True},
        ], status="reviewed")
        with self.assertRaises(ValueError) as ctx:
            template_builder.build_template("sample")
        self.assertIn("토큰 삽입 위치", str(ctx.exception))
        self.assertFalse((self.built / "sample.hwpx").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
