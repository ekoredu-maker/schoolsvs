from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import form10_adaptive  # noqa: E402
import hwpx_engine  # noqa: E402

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
ET.register_namespace("hp", HP)
ET.register_namespace("hs", HS)


def q(uri, name): return f"{{{uri}}}{name}"


def cell(col, row, text, col_span=1, row_span=1, width=4000, height=2000):
    tc = ET.Element(q(HP, "tc"))
    ET.SubElement(tc, q(HP, "cellAddr"), {"colAddr": str(col), "rowAddr": str(row)})
    ET.SubElement(tc, q(HP, "cellSpan"), {"colSpan": str(col_span), "rowSpan": str(row_span)})
    ET.SubElement(tc, q(HP, "cellSz"), {"width": str(width), "height": str(height)})
    p = ET.SubElement(tc, q(HP, "p")); r = ET.SubElement(p, q(HP, "run")); t = ET.SubElement(r, q(HP, "t")); t.text = text
    return tc


def make_hwpx(path: Path):
    sec = ET.Element(q(HS, "sec"))
    tbl = ET.SubElement(sec, q(HP, "tbl"), {"rowCnt": "20", "colCnt": "15"})
    ET.SubElement(tbl, q(HP, "sz"), {"width": "47893", "height": "69613"})
    for i in range(20):
        tr = ET.SubElement(tbl, q(HP, "tr"))
        if i == 1:
            tr.extend([cell(0,i,"학교명"), cell(3,i,"교장",2)])
        elif i == 3:
            tr.extend([cell(0,i,"접수일시"), cell(1,i,"20 . 00. 00.",14)])
        elif i == 11:
            tr.extend([cell(0,i,"사실확인내용"), cell(1,i,"유형 □폭행 □언어폭력",14)])
        elif i == 12:
            tr.extend([cell(0,i,"관련학생",1,3), cell(10,i,"비고",5,1,19714,3702)])
        elif i in (13,14):
            tr.append(cell(10,i,"가해관련□ 피해관련□",5,1,19714,2175))
        elif i == 18:
            tr.extend([cell(0,i,"전담조사관 면담조사 가능시간",1,2,7115,5630), cell(1,i,"피해 관련",2,1,7398,2815), cell(3,i,"※ 학교자체 조사인 경우 빈칸",12,1,33380,2815)])
        elif i == 19:
            tr.extend([cell(1,i,"가해 관련",2,1,7398,2815), cell(3,i,"※ 학교자체 조사인 경우 빈칸",12,1,33380,2815)])
        else:
            tr.append(cell(0,i,f"row{i}",15))
    xml = ET.tostring(sec, encoding="UTF-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("Contents/section0.xml", xml)
        z.writestr("Contents/content.hpf", "<root/>")


class Form10AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.templates = self.root / "templates"; self.templates.mkdir()
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps({"documents":{"form10_case_report":{"template":"form10.hwpx"}}}), encoding="utf-8")
        make_hwpx(self.templates / "form10.hwpx")
        self.original = (self.templates / "form10.hwpx").read_bytes()
        self.old_registry = hwpx_engine.REGISTRY_PATH
        self.old_template = form10_adaptive.TEMPLATE_DIR
        self.old_adaptive = form10_adaptive.ADAPTIVE_DIR
        self.old_report = form10_adaptive.REPORT_DIR
        hwpx_engine.REGISTRY_PATH = self.registry
        form10_adaptive.TEMPLATE_DIR = self.templates
        form10_adaptive.ADAPTIVE_DIR = self.templates / "_adaptive"
        form10_adaptive.REPORT_DIR = self.templates / "_adaptive_reports"

    def tearDown(self):
        hwpx_engine.REGISTRY_PATH = self.old_registry
        form10_adaptive.TEMPLATE_DIR = self.old_template
        form10_adaptive.ADAPTIVE_DIR = self.old_adaptive
        form10_adaptive.REPORT_DIR = self.old_report
        self.tmp.cleanup()

    def test_adaptive_conversion_keeps_source_and_adds_2026_structure(self):
        report = form10_adaptive.build_adaptive_form10()
        self.assertFalse(report["official2026HwpxVerified"])
        self.assertEqual(report["table"], {"rows":22,"cols":15})
        self.assertEqual((self.templates / "form10.hwpx").read_bytes(), self.original)
        target = self.templates / "_adaptive" / "form10.hwpx"
        self.assertTrue(target.exists())
        with zipfile.ZipFile(target) as z:
            root = ET.fromstring(z.read("Contents/section0.xml"))
        table = next(x for x in root.iter() if x.tag.endswith("tbl"))
        self.assertEqual(table.get("rowCnt"), "22")
        text = " ".join((x.text or "") for x in root.iter() if x.tag.endswith("t"))
        self.assertIn("교감", text)
        self.assertIn("관계회복 프로그램 안내여부", text)
        self.assertIn("관계회복 프로그램 관련 학생 의견", text)
        self.assertIn("신체폭력", text)


if __name__ == "__main__": unittest.main(verbosity=2)
