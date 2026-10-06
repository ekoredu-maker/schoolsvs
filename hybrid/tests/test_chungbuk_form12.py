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

import chungbuk_form12  # noqa: E402

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
OPF = "http://www.idpf.org/2007/opf/"
ET.register_namespace("hp", HP)
ET.register_namespace("hs", HS)
ET.register_namespace("opf", OPF)


def _run(text: str):
    run = ET.Element(f"{{{HP}}}run", {"charPrIDRef": "0"})
    t = ET.SubElement(run, f"{{{HP}}}t")
    t.text = text
    return run


def _cell(row: int, col: int, text: str):
    tc = ET.Element(f"{{{HP}}}tc")
    sub = ET.SubElement(tc, f"{{{HP}}}subList")
    p = ET.SubElement(sub, f"{{{HP}}}p", {"id": "1", "paraPrIDRef": "0", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
    p.append(_run(text))
    ET.SubElement(tc, f"{{{HP}}}cellAddr", {"colAddr": str(col), "rowAddr": str(row)})
    ET.SubElement(tc, f"{{{HP}}}cellSpan", {"colSpan": "1", "rowSpan": "1"})
    return tc


def _table():
    tbl = ET.Element(f"{{{HP}}}tbl", {"id": "1909429775", "rowCnt": "38", "colCnt": "14"})
    rows = {
        0: [(0, "신고접수 일자"), (1, "년 월 일"), (5, "책임교사 성명&연락처"), (9, "")],
        1: [(0, "사안조사 일자"), (1, "년 월 일"), (5, "조사관 성명&연락처"), (9, "")],
        2: [(0, "사안 유형"), (1, "유형: 신체폭력/ 언어폭력/ 금품갈취")],
        4: [(0, "관련 학생"), (1, "학교")],
        8: [(0, "사안 개요 (주요 내용)"), (1, "신고내용과 관련하여 확인한 내용")],
        9: [(0, "사안 경위 (세부내용 전체)"), (1, "사건 내용을 시간의 흐름에 맞춰 구체적으로 기재")],
        13: [(0, "자체해결 요건 충족 여부"), (1, "조사관 의견")],
        14: [(1, "학교장 자체해결 요건 의견(충족 여부)"), (13, "현재까지 확인된 내용")],
        15: [(0, "쟁점 사안"), (1, "주요 쟁점 1.")],
        19: [(1, "주요 쟁점 2.")],
        21: [(0, "시행령 제19조 판단요소 관련 확인 사실 기재")],
        22: [(0, "학교폭력의 심각성"), (1, "•")],
        23: [(0, "학교폭력의 지속성"), (1, "•")],
        24: [(0, "학교폭력의 고의성"), (1, "•")],
        25: [(0, "가해학생의 반성 정도"), (1, "•")],
        26: [(0, "가해학생 및 보호자와 피해학생 및 보호자간 화해 정도"), (1, "•")],
        29: [(0, "해당 조치로 인한 가해학생의 선도 가능성"), (1, "•")],
        30: [(0, "피해학생이 장애학생인지 여부"), (1, "•")],
        33: [(0, "가해학생 학교폭력 재발 현황"), (1, "관리대장을 통해 확인")],
        37: [(0, "특이사항 및 고려사항"), (1, "피해학생이 다문화학생인지 여부")],
    }
    for row_no in range(38):
        tr = ET.SubElement(tbl, f"{{{HP}}}tr")
        for col, text in rows.get(row_no, [(0, "")]):
            tr.append(_cell(row_no, col, text))
    return tbl


def _section(include_form12=False, next_form=False):
    root = ET.Element(f"{{{HS}}}sec")
    control = ET.SubElement(root, f"{{{HP}}}p", {"id":"0","paraPrIDRef":"0","styleIDRef":"0","pageBreak":"0","columnBreak":"0","merged":"0"})
    run = ET.SubElement(control, f"{{{HP}}}run", {"charPrIDRef":"0"})
    ET.SubElement(run, f"{{{HP}}}secPr")
    if include_form12:
        marker = ET.SubElement(root, f"{{{HP}}}p", {"id":"1","paraPrIDRef":"0","styleIDRef":"0","pageBreak":"0","columnBreak":"0","merged":"0"})
        marker.append(_run("<서식12> 사안조사 보고서"))
        title = ET.SubElement(root, f"{{{HP}}}p", {"id":"2","paraPrIDRef":"0","styleIDRef":"0","pageBreak":"0","columnBreak":"0","merged":"0"})
        title.append(_run("(1차 조사 □ / 보완조사 □ ) 학교폭력 사안조사 보고서"))
        body = ET.SubElement(root, f"{{{HP}}}p", {"id":"3","paraPrIDRef":"0","styleIDRef":"0","pageBreak":"0","columnBreak":"0","merged":"0"})
        r = ET.SubElement(body, f"{{{HP}}}run", {"charPrIDRef":"0"})
        r.append(_table())
        ref = ET.SubElement(root, f"{{{HP}}}p", {"id":"4","paraPrIDRef":"0","styleIDRef":"0","pageBreak":"0","columnBreak":"0","merged":"0"})
        ref.append(_run("[참고] 시행령 제19조 판단요소 확인 시 참고 사항"))
    if next_form:
        p = ET.SubElement(root, f"{{{HP}}}p", {"id":"5","paraPrIDRef":"0","styleIDRef":"0","pageBreak":"1","columnBreak":"0","merged":"0"})
        p.append(_run("<공문5> 다음 문서"))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _content_hpf():
    package=ET.Element(f"{{{OPF}}}package")
    manifest=ET.SubElement(package,f"{{{OPF}}}manifest")
    ET.SubElement(manifest,f"{{{OPF}}}item",{"id":"section0","href":"Contents/section0.xml","media-type":"application/xml"})
    ET.SubElement(manifest,f"{{{OPF}}}item",{"id":"section1","href":"Contents/section1.xml","media-type":"application/xml"})
    spine=ET.SubElement(package,f"{{{OPF}}}spine")
    ET.SubElement(spine,f"{{{OPF}}}itemref",{"idref":"section0"});ET.SubElement(spine,f"{{{OPF}}}itemref",{"idref":"section1"})
    return ET.tostring(package,encoding="utf-8",xml_declaration=True)


def sample_bundle():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as zf:
        zf.writestr("mimetype","application/hwp+zip",compress_type=zipfile.ZIP_STORED)
        zf.writestr("Contents/section0.xml",_section())
        zf.writestr("Contents/section1.xml",_section(include_form12=True,next_form=True))
        zf.writestr("Contents/content.hpf",_content_hpf())
        zf.writestr("Preview/PrvText.txt","전체 서식모음")
    return buf.getvalue()


class ChungbukForm12Tests(unittest.TestCase):
    def test_extracts_form12_block_until_next_page_break(self):
        extracted=chungbuk_form12.extract_form12_from_bundle(sample_bundle())
        with zipfile.ZipFile(io.BytesIO(extracted),"r") as zf:
            self.assertIn("Contents/section1.xml",zf.namelist())
            self.assertNotIn("Contents/section0.xml",zf.namelist())
            self.assertEqual(zf.getinfo("mimetype").compress_type,zipfile.ZIP_STORED)
            text=zf.read("Contents/section1.xml").decode("utf-8")
            self.assertIn("학교폭력 사안조사 보고서",text)
            self.assertIn("시행령 제19조",text)
            self.assertNotIn("다음 문서",text)

    def test_structure_matches_verified_2025_reference(self):
        extracted=chungbuk_form12.extract_form12_from_bundle(sample_bundle())
        result=chungbuk_form12.analyze_form12_structure(extracted)
        self.assertEqual(result["rows"],38)
        self.assertEqual(result["cols"],14)
        self.assertTrue(result["reference2025Match"],result)
        self.assertTrue(result["usesMulticulturalTerm"])
        self.assertFalse(result["usesMigrationBackgroundTerm"])
        self.assertFalse(result["productionReadyFor2026"])

    def test_prepare_keeps_original_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepared,meta=chungbuk_form12.prepare_form12_upload(sample_bundle(),"서식모음집.hwpx",Path(tmp)/"source")
            self.assertTrue(meta["extractedFromBundle"])
            self.assertTrue((Path(tmp)/"source"/meta["sourceStoredAs"]).exists())
            self.assertLess(len(prepared),len(sample_bundle()))
            self.assertFalse(meta["structure"]["productionReadyFor2026"])


if __name__=="__main__":
    unittest.main(verbosity=2)
