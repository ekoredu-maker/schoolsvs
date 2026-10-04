from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from form10_student_rows import apply_student_rows_to_hwpx  # noqa: E402

NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
ET.register_namespace("hp", NS)


def q(name: str) -> str:
    return f"{{{NS}}}{name}"


def cell(text: str, col: int, row: int, col_span: int = 1, row_span: int = 1, no_text_node: bool = False) -> ET.Element:
    tc = ET.Element(q("tc"))
    sub = ET.SubElement(tc, q("subList"))
    p = ET.SubElement(sub, q("p"))
    run = ET.SubElement(p, q("run"))
    if not no_text_node:
        ET.SubElement(run, q("t")).text = text
    ET.SubElement(tc, q("cellAddr"), {"colAddr": str(col), "rowAddr": str(row)})
    ET.SubElement(tc, q("cellSpan"), {"colSpan": str(col_span), "rowSpan": str(row_span)})
    return tc


def row(values: list[str], row_index: int, spans: list[int] | None = None, blank_gender: bool = False) -> ET.Element:
    tr = ET.Element(q("tr"))
    col = 0
    spans = spans or [1] * len(values)
    for idx, (value, span) in enumerate(zip(values, spans)):
        tr.append(cell(value, col, row_index, col_span=span, no_text_node=blank_gender and idx == 3))
        col += span
    return tr


def make_hwpx(path: Path) -> None:
    root = ET.Element(q("sec"))
    table = ET.SubElement(root, q("tbl"), {"rowCnt": "22", "colCnt": "15"})
    for i in range(12):
        table.append(row([f"기본행{i}"], i, [15]))
    header = ET.Element(q("tr"))
    header.append(cell("관련학생", 0, 12, row_span=3))
    for value, col, span in [
        ("학교명", 1, 1), ("학번", 2, 2), ("성명", 4, 2), ("성별", 6, 3),
        ("보호자 통보여부", 9, 1), ("관계회복 프로그램 안내여부", 10, 2), ("비고", 12, 3),
    ]:
        header.append(cell(value, col, 12, col_span=span))
    table.append(header)
    spans = [1, 2, 2, 3, 1, 2, 3]
    table.append(row(["00초", "60101", "예시1", "", "3.27 유선", "○", "피해관련□"], 13, spans, blank_gender=True))
    table.append(row(["00초", "60102", "예시2", "", "3.27 유선", "X", "가해관련□"], 14, spans, blank_gender=True))
    table.append(row(["기타 사항"], 15, [15]))
    for i in range(16, 22):
        table.append(row([f"후속행{i}"], i, [15]))
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", b"application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Contents/section1.xml", xml, compress_type=zipfile.ZIP_DEFLATED)


def case_with_students(count: int) -> dict:
    profiles = []
    for i in range(count):
        profiles.append({
            "role": "victim" if i == 0 else "perp",
            "name": f"학생{i + 1}",
            "schoolName": "테스트초" if i == 0 else "테스트중",
            "grade": "6" if i == 0 else "2",
            "classNo": str(i + 1),
            "number": str(i + 3),
            "gender": "여" if i == 0 else "남",
            "guardianNoticeAt": f"2026-10-05T09:{20 + i:02d}",
            "guardianNoticeMethod": "유선",
            "recoveryGuidance": "O" if i % 2 == 0 else "X",
            "athlete": i == 1,
            "specialEducation": i == 2,
        })
    return {"_hybrid": {"studentProfiles": profiles}}


def local(tag: str) -> str:
    return tag.split("}")[-1]


def text(row_elem: ET.Element) -> str:
    return " ".join(
        " ".join((node.text or "").split())
        for node in row_elem.iter()
        if local(node.tag) == "t" and (node.text or "").strip()
    )


class Form10StudentRowsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "form10.hwpx"
        make_hwpx(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def inspect_main_table(self):
        with zipfile.ZipFile(self.path) as zf:
            root = ET.fromstring(zf.read("Contents/section1.xml"))
            self.assertEqual(zf.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
        table = next(node for node in root.iter() if local(node.tag) == "tbl")
        rows = [child for child in list(table) if local(child.tag) == "tr"]
        return table, rows

    def test_three_students_expand_rows_and_reindex(self):
        report = apply_student_rows_to_hwpx(self.path, case_with_students(3))
        self.assertEqual(report["studentCount"], 3)
        self.assertEqual(report["rowCount"], 23)
        self.assertEqual(report["headerRowSpan"], 4)
        table, rows = self.inspect_main_table()
        self.assertEqual(table.get("rowCnt"), "23")
        self.assertIn("학생1", text(rows[13]))
        self.assertIn("학생2", text(rows[14]))
        self.assertIn("학생3", text(rows[15]))
        self.assertIn("기타 사항", text(rows[16]))
        self.assertIn("○", text(rows[13]))
        self.assertIn("X", text(rows[14]))
        first_header_cell = next(child for child in list(rows[12]) if local(child.tag) == "tc")
        span = next(node for node in first_header_cell.iter() if local(node.tag) == "cellSpan")
        self.assertEqual(span.get("rowSpan"), "4")
        for index, row_elem in enumerate(rows):
            cells = [child for child in list(row_elem) if local(child.tag) == "tc"]
            if not cells:
                continue
            addr = next(node for node in cells[0].iter() if local(node.tag) == "cellAddr")
            self.assertEqual(addr.get("rowAddr"), str(index))

    def test_one_student_contracts_sample_rows(self):
        report = apply_student_rows_to_hwpx(self.path, case_with_students(1))
        self.assertEqual(report["rowCount"], 21)
        table, rows = self.inspect_main_table()
        self.assertEqual(len(rows), 21)
        self.assertIn("학생1", text(rows[13]))
        self.assertIn("기타 사항", text(rows[14]))
        first_header_cell = next(child for child in list(rows[12]) if local(child.tag) == "tc")
        span = next(node for node in first_header_cell.iter() if local(node.tag) == "cellSpan")
        self.assertEqual(span.get("rowSpan"), "2")

    def test_empty_profiles_are_rejected(self):
        with self.assertRaises(ValueError):
            apply_student_rows_to_hwpx(self.path, {"_hybrid": {"studentProfiles": []}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
