from __future__ import annotations

import copy
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from lxml import etree

from hwpx_engine import TEMPLATE_DIR, load_registry

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS = {"hp": HP}
ADAPTIVE_DIR = TEMPLATE_DIR / "_adaptive"
REPORT_DIR = TEMPLATE_DIR / "_adaptive_reports"
DOCUMENT_KEY = "form10_case_report"
PROFILE_VERSION = "cb-form10-2026-pdf-adaptive-v0.14"


def _document() -> dict[str, Any]:
    doc = (load_registry().get("documents") or {}).get(DOCUMENT_KEY)
    if not doc:
        raise KeyError("서식10 문서 레지스트리를 찾을 수 없습니다.")
    return doc


def source_path() -> Path:
    return TEMPLATE_DIR / str(_document().get("template") or "")


def adaptive_path() -> Path:
    return ADAPTIVE_DIR / str(_document().get("template") or "")


def report_path() -> Path:
    return REPORT_DIR / f"{DOCUMENT_KEY}.json"


def load_adaptive_report() -> dict[str, Any] | None:
    path = report_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _cell_text(tc) -> str:
    return "".join(tc.xpath(".//hp:t/text()", namespaces=NS)).strip()


def _set_text(tc, text: str) -> None:
    nodes = tc.xpath(".//hp:t", namespaces=NS)
    if not nodes:
        raise ValueError("셀 안에 텍스트 노드가 없습니다.")
    nodes[0].text = text
    for node in nodes[1:]:
        node.text = ""


def _find_cell(row, col: int):
    for tc in row.xpath("./hp:tc", namespaces=NS):
        addr = tc.find("hp:cellAddr", namespaces=NS)
        if addr is not None and int(addr.get("colAddr", "-1")) == col:
            return tc
    return None


def _set_geometry(tc, *, col: int, row: int, col_span: int, row_span: int, width: int | None = None, height: int | None = None) -> None:
    addr = tc.find("hp:cellAddr", namespaces=NS)
    span = tc.find("hp:cellSpan", namespaces=NS)
    size = tc.find("hp:cellSz", namespaces=NS)
    if addr is None or span is None or size is None:
        raise ValueError("HWPX 셀 좌표 정보를 찾을 수 없습니다.")
    addr.set("colAddr", str(col))
    addr.set("rowAddr", str(row))
    span.set("colSpan", str(col_span))
    span.set("rowSpan", str(row_span))
    if width is not None:
        size.set("width", str(width))
    if height is not None:
        size.set("height", str(height))


def _main_table(root):
    candidates = root.xpath("//hp:tbl[@rowCnt='20' and @colCnt='15']", namespaces=NS)
    for table in candidates:
        text = " ".join(table.xpath(".//hp:t/text()", namespaces=NS))
        if "학교명" in text and "접수일시" in text and "전담조사관" in text:
            return table
    raise ValueError("2025 충북 서식10의 20행×15열 본문 표를 찾지 못했습니다.")


def _replace_violence_options(row) -> bool:
    target = _find_cell(row, 1)
    if target is None:
        return False
    for node in target.xpath(".//hp:t", namespaces=NS):
        if node.text and "□폭행" in node.text:
            node.text = "□신체폭력 □언어폭력 □금품갈취 □강요 □따돌림 □성폭력 □사이버폭력 □기타 □아동학대(접수여부:  )  ※중복체크 가능(■, □)"
            return True
    return False


def _split_student_note_cell(row, row_index: int, *, header: bool) -> None:
    old = _find_cell(row, 10)
    if old is None:
        raise ValueError(f"관련학생 {row_index}행의 비고 셀을 찾지 못했습니다.")
    right = copy.deepcopy(old)
    size = old.find("hp:cellSz", namespaces=NS)
    height = int(size.get("height", "2175")) if size is not None else 2175

    _set_geometry(old, col=10, row=row_index, col_span=2, row_span=1, width=7200, height=height)
    _set_geometry(right, col=12, row=row_index, col_span=3, row_span=1, width=12514, height=height)
    if header:
        _set_text(old, "관계회복 프로그램 안내여부")
        _set_text(right, "비고\n※중복체크 가능(■, □)")
    else:
        _set_text(old, "○, X")
        _set_text(right, "가해관련□ 피해관련□ 학생선수□ 장애학생□ 특수교육대상자□ 다문화학생□ 탈북학생□")
    old.addnext(right)


def _append_recovery_opinion_rows(table, rows) -> None:
    row20 = copy.deepcopy(rows[18])
    row21 = copy.deepcopy(rows[19])

    c0 = _find_cell(row20, 0)
    c1 = _find_cell(row20, 1)
    c3 = _find_cell(row20, 3)
    if c0 is None or c1 is None or c3 is None:
        raise ValueError("피해 관련 관계회복 의견 행의 기준 셀을 찾지 못했습니다.")
    _set_geometry(c0, col=0, row=20, col_span=1, row_span=2, width=7115, height=4400)
    _set_geometry(c1, col=1, row=20, col_span=2, row_span=1, width=7398, height=2200)
    _set_geometry(c3, col=3, row=20, col_span=12, row_span=1, width=33380, height=2200)
    _set_text(c0, "관계회복 프로그램 관련 학생 의견")
    _set_text(c1, "피해 관련")
    _set_text(c3, "예> 상대방이 사과할 경우 관계회복 프로그램 참여 의사 있음")

    c1b = _find_cell(row21, 1)
    c3b = _find_cell(row21, 3)
    if c1b is None or c3b is None:
        raise ValueError("가해 관련 관계회복 의견 행의 기준 셀을 찾지 못했습니다.")
    _set_geometry(c1b, col=1, row=21, col_span=2, row_span=1, width=7398, height=2200)
    _set_geometry(c3b, col=3, row=21, col_span=12, row_span=1, width=33380, height=2200)
    _set_text(c1b, "가해 관련")
    _set_text(c3b, "예> 상대와 오해가 있으며, 대화로 풀고 싶은 의사가 있음")

    table.append(row20)
    table.append(row21)
    table.set("rowCnt", "22")
    size = table.find("hp:sz", namespaces=NS)
    if size is not None and size.get("height"):
        size.set("height", str(int(size.get("height")) + 4400))


def _write_package(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w") as out:
        mimetype = source_dir / "mimetype"
        if mimetype.exists():
            out.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file() or path == mimetype:
                continue
            out.write(path, path.relative_to(source_dir).as_posix(), compress_type=zipfile.ZIP_DEFLATED)


def build_adaptive_form10() -> dict[str, Any]:
    source = source_path()
    if not source.exists():
        raise FileNotFoundError("서식10 기준 HWPX를 먼저 등록하세요.")
    if not zipfile.is_zipfile(source):
        raise ValueError("등록된 서식10 기준파일이 유효한 HWPX가 아닙니다.")

    output = adaptive_path()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(source, "r") as zf:
            zf.extractall(tmp)
        section_files = sorted((tmp / "Contents").glob("section*.xml"))
        target_section: Path | None = None
        parsed = None
        table = None
        parser = etree.XMLParser(remove_blank_text=False)
        for section in section_files:
            tree = etree.parse(str(section), parser)
            try:
                candidate = _main_table(tree)
            except ValueError:
                continue
            target_section = section
            parsed = tree
            table = candidate
            break
        if target_section is None or parsed is None or table is None:
            raise ValueError("서식10 본문 표가 포함된 section XML을 찾지 못했습니다.")

        rows = table.xpath("./hp:tr", namespaces=NS)
        if len(rows) != 20:
            raise ValueError(f"예상한 20행 구조가 아닙니다: {len(rows)}행")

        manager = _find_cell(rows[1], 3)
        if manager is None or "교장" not in _cell_text(manager):
            raise ValueError("2025 구조의 '교장' 셀을 찾지 못했습니다. 공식 2026 HWPX 여부를 다시 확인하세요.")
        _set_text(manager, "교감")
        violence_updated = _replace_violence_options(rows[11])
        _split_student_note_cell(rows[12], 12, header=True)
        _split_student_note_cell(rows[13], 13, header=False)
        _split_student_note_cell(rows[14], 14, header=False)
        _append_recovery_opinion_rows(table, rows)

        parsed.write(str(target_section), encoding="UTF-8", xml_declaration=True, standalone=True, pretty_print=False)
        _write_package(tmp, output)

    report = {
        "documentKey": DOCUMENT_KEY,
        "profileVersion": PROFILE_VERSION,
        "builtAt": datetime.now().isoformat(timespec="seconds"),
        "sourceTemplate": source.name,
        "adaptiveTemplate": output.relative_to(TEMPLATE_DIR).as_posix(),
        "basis": {
            "structure": "2025 충북 A to Z 서식모음집 HWPX 서식10",
            "content": "2026 충북 A to Z PDF 서식10(page 40)",
        },
        "official2026HwpxVerified": False,
        "changes": [
            "관리직 표기를 교장에서 교감으로 변경",
            "폭력유형 항목을 2026 PDF 순서·용어에 맞게 보정",
            "관련학생 표에 관계회복 프로그램 안내여부 영역 추가",
            "피해·가해 관련학생 관계회복 프로그램 의견 2행 추가",
        ],
        "warnings": [
            "공식 2026 HWPX 원본과 1:1 대조 전인 PDF 기반 적응형 시험본입니다.",
            "한글에서 페이지 넘침·열 너비·글자 줄바꿈을 반드시 출력 비교해야 합니다.",
        ],
        "table": {"rows": 22, "cols": 15},
        "violenceOptionsUpdated": violence_updated,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
