from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import chungbuk_form10  # noqa: E402

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
OPF = "http://www.idpf.org/2007/opf/"
ET.register_namespace("hp", HP)
ET.register_namespace("hs", HS)
ET.register_namespace("opf", OPF)


def _text_run(text: str):
    run = ET.Element(f"{{{HP}}}run", {"charPrIDRef": "0"})
    t = ET.SubElement(run, f"{{{HP}}}t")
    t.text = text
    return run


def _cell(row: int, col: int, text: str):
    tc = ET.Element(f"{{{HP}}}tc")
    sub = ET.SubElement(tc, f"{{{HP}}}subList")
    p = ET.SubElement(sub, f"{{{HP}}}p", {"id": "1", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
    p.append(_text_run(text))
    ET.SubElement(tc, f"{{{HP}}}cellAddr", {"colAddr": str(col), "rowAddr": str(row)})
    ET.SubElement(tc, f"{{{HP}}}cellSpan", {"colSpan": "1", "rowSpan": "1"})
    return tc


def _main_table():
    tbl = ET.Element(f"{{{HP}}}tbl", {"id": "1909429768", "rowCnt": "20", "colCnt": "15"})
    rows = {
        1: [(0, "학교명"), (1, "○○○○학교"), (3, "교장")],
        3: [(0, "접수일시"), (1, "20 . 00. 00.(요일) 00:00")],
        16: [(0, "타학교 관련 여부")],
        18: [(0, "전담조사관 면담조사 가능시간")],
    }
    for row_no, items in rows.items():
        tr = ET.SubElement(tbl, f"{{{HP}}}tr")
        for col_no, text in items:
            tr.append(_cell(row_no, col_no, text))
    return tbl


def _section(text: str = "", include_form10: bool = False, next_form: bool = False):
    root = ET.Element(f"{{{HS}}}sec")
    p0 = ET.SubElement(root, f"{{{HP}}}p", {"id": "0", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
    run0 = ET.SubElement(p0, f"{{{HP}}}run", {"charPrIDRef": "0"})
    ET.SubElement(run0, f"{{{HP}}}secPr")
    if text:
        p = ET.SubElement(root, f"{{{HP}}}p", {"id": "2", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
        p.append(_text_run(text))
    if include_form10:
        title = ET.SubElement(root, f"{{{HP}}}p", {"id": "3", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "1", "columnBreak": "0", "merged": "0"})
        title.append(_text_run("<서식10> 학교폭력 사안접수 보고서"))
        body = ET.SubElement(root, f"{{{HP}}}p", {"id": "4", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
        body.append(_text_run("학교폭력 사안접수 보고"))
        table_p = ET.SubElement(root, f"{{{HP}}}p", {"id": "5", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
        table_run = ET.SubElement(table_p, f"{{{HP}}}run", {"charPrIDRef": "0"})
        table_run.append(_main_table())
    if next_form:
        p = ET.SubElement(root, f"{{{HP}}}p", {"id": "6", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "1", "columnBreak": "0", "merged": "0"})
        p.append(_text_run("<서식11> 다음 서식"))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _content_hpf():
    package = ET.Element(f"{{{OPF}}}package")
    manifest = ET.SubElement(package, f"{{{OPF}}}manifest")
    ET.SubElement(manifest, f"{{{OPF}}}item", {"id": "header", "href": "Contents/header.xml", "media-type": "application/xml"})
    for no in range(3):
        ET.SubElement(manifest, f"{{{OPF}}}item", {"id": f"section{no}", "href": f"Contents/section{no}.xml", "media-type": "application/xml"})
    spine = ET.SubElement(package, f"{{{OPF}}}spine")
    ET.SubElement(spine, f"{{{OPF}}}itemref", {"idref": "header"})
    for no in range(3):
        ET.SubElement(spine, f"{{{OPF}}}itemref", {"idref": f"section{no}"})
    return ET.tostring(package, encoding="utf-8", xml_declaration=True)


def sample_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Contents/header.xml", "<header/>")
        zf.writestr("Contents/section0.xml", _section("앞쪽 서식"))
        zf.writestr("Contents/section1.xml", _section(include_form10=True, next_form=True))
        zf.writestr("Contents/section2.xml", _section("뒤쪽 서식"))
        zf.writestr("Contents/content.hpf", _content_hpf())
        zf.writestr("Preview/PrvText.txt", "전체 서식모음")
    return buf.getvalue()


class ChungbukForm10Tests(unittest.TestCase):
    def test_extracts_only_form10_page(self):
        extracted = chungbuk_form10.extract_form10_from_bundle(sample_bundle())
        with zipfile.ZipFile(io.BytesIO(extracted), "r") as zf:
            names = zf.namelist()
            self.assertIn("Contents/section1.xml", names)
            self.assertNotIn("Contents/section0.xml", names)
            self.assertNotIn("Contents/section2.xml", names)
            self.assertEqual(zf.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
            text = zf.read("Contents/section1.xml").decode("utf-8")
            self.assertIn("학교폭력 사안접수 보고서", text)
            self.assertNotIn("다음 서식", text)

    def test_structure_detects_2025_reference_signals(self):
        extracted = chungbuk_form10.extract_form10_from_bundle(sample_bundle())
        result = chungbuk_form10.analyze_form10_structure(extracted)
        self.assertEqual(result["rows"], 20)
        self.assertEqual(result["cols"], 15)
        self.assertEqual(result["managerTitle"], "교장")
        self.assertEqual(result["sourceYearDetected"], 2025)
        self.assertFalse(result["productionReadyFor2026"])

    def test_prepare_keeps_original_source_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "source"
            prepared, meta = chungbuk_form10.prepare_form10_upload(sample_bundle(), "서식모음집.hwpx", source_dir)
            self.assertTrue(meta["extractedFromBundle"])
            self.assertTrue((source_dir / meta["sourceStoredAs"]).exists())
            self.assertLess(len(prepared), len(sample_bundle()))
            self.assertFalse(meta["structure"]["productionReadyFor2026"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
