from __future__ import annotations

import copy
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PROFILE_PATH = Path(__file__).with_name("form_profiles") / "chungbuk_form10_2025.json"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
OPF = "http://www.idpf.org/2007/opf/"
HP_P = f"{{{HP}}}p"
HP_T = f"{{{HP}}}t"
HP_TBL = f"{{{HP}}}tbl"
HP_TR = f"{{{HP}}}tr"
HP_TC = f"{{{HP}}}tc"
HP_ADDR = f"{{{HP}}}cellAddr"


class Form10StructureError(ValueError):
    pass


def load_profile() -> dict[str, Any]:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _register_namespaces(xml_bytes: bytes) -> None:
    head = xml_bytes[:12000].decode("utf-8", errors="ignore")
    for prefix, uri in re.findall(r'xmlns(?::([A-Za-z0-9_.-]+))?="([^"]+)"', head):
        prefix = prefix or ""
        if prefix.startswith("ns") and prefix[2:].isdigit():
            continue
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass


def _text(elem: ET.Element) -> str:
    parts = []
    for node in elem.iter(HP_T):
        if node.text:
            text = " ".join(node.text.split()).strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _contains_descendant(elem: ET.Element, tag: str) -> bool:
    return any(node.tag == tag for node in elem.iter())


def _write_package(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as out:
        if "mimetype" in entries:
            out.writestr("mimetype", entries["mimetype"], compress_type=zipfile.ZIP_STORED)
        for name in sorted(entries):
            if name == "mimetype":
                continue
            out.writestr(name, entries[name], compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def _section_entries(entries: dict[str, bytes]) -> list[str]:
    return sorted(name for name in entries if re.fullmatch(r"Contents/section\d+\.xml", name))


def _locate_form10_page(entries: dict[str, bytes]) -> tuple[str, ET.Element, list[ET.Element], int, int]:
    marker = str(load_profile().get("pageMarker") or "<서식10>")
    for name in _section_entries(entries):
        raw = entries[name]
        _register_namespaces(raw)
        root = ET.fromstring(raw)
        paragraphs = [child for child in list(root) if child.tag == HP_P]
        for index, paragraph in enumerate(paragraphs):
            if marker not in _text(paragraph):
                continue
            end = len(paragraphs)
            for next_index in range(index + 1, len(paragraphs)):
                if paragraphs[next_index].get("pageBreak") == "1":
                    end = next_index
                    break
            return name, root, paragraphs, index, end
    raise Form10StructureError("HWPX에서 <서식10> 페이지 표식을 찾지 못했습니다.")


def _section_control_paragraph(paragraphs: list[ET.Element]) -> ET.Element | None:
    sec_pr = f"{{{HP}}}secPr"
    page_num = f"{{{HP}}}pageNum"
    for paragraph in paragraphs:
        if not _contains_descendant(paragraph, sec_pr):
            continue
        control = copy.deepcopy(paragraph)
        control.set("pageBreak", "0")
        for child in list(control):
            if not (_contains_descendant(child, sec_pr) or _contains_descendant(child, page_num)):
                control.remove(child)
        return control
    return None


def _trim_content_hpf(raw: bytes, target_section: str) -> bytes:
    _register_namespaces(raw)
    root = ET.fromstring(raw)
    target_href = target_section
    target_id = None
    manifest = root.find(f"{{{OPF}}}manifest")
    if manifest is not None:
        for item in list(manifest):
            href = item.get("href") or ""
            if href == target_href:
                target_id = item.get("id")
            elif re.fullmatch(r"Contents/section\d+\.xml", href):
                manifest.remove(item)
    spine = root.find(f"{{{OPF}}}spine")
    if spine is not None:
        for item in list(spine):
            idref = item.get("idref") or ""
            if idref.startswith("section") and idref != target_id:
                spine.remove(item)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def extract_form10_from_bundle(payload: bytes) -> bytes:
    """서식모음집에서 <서식10>이 시작되는 페이지 하나만 독립 HWPX로 추출한다."""
    if not payload:
        raise Form10StructureError("HWPX 파일이 비어 있습니다.")
    source = io.BytesIO(payload)
    if not zipfile.is_zipfile(source):
        raise Form10StructureError("유효한 HWPX ZIP 패키지가 아닙니다.")
    source.seek(0)
    with zipfile.ZipFile(source, "r") as zf:
        entries = {name: zf.read(name) for name in zf.namelist()}

    section_name, root, paragraphs, start, end = _locate_form10_page(entries)
    selected = paragraphs[start:end]
    if not selected:
        raise Form10StructureError("서식10 페이지 범위를 추출하지 못했습니다.")

    new_root = ET.Element(root.tag, root.attrib)
    control = _section_control_paragraph(paragraphs)
    if control is not None:
        new_root.append(control)
    for pos, paragraph in enumerate(selected):
        cloned = copy.deepcopy(paragraph)
        if pos == 0:
            cloned.set("pageBreak", "0")
        new_root.append(cloned)

    entries[section_name] = ET.tostring(new_root, encoding="utf-8", xml_declaration=True)
    for name in _section_entries(entries):
        if name != section_name:
            entries.pop(name, None)
    if "Contents/content.hpf" in entries:
        entries["Contents/content.hpf"] = _trim_content_hpf(entries["Contents/content.hpf"], section_name)
    entries["Preview/PrvText.txt"] = "[서식10] 학교폭력 사안접수 보고서".encode("utf-8")
    return _write_package(entries)


def _find_main_table(root: ET.Element) -> ET.Element:
    profile = load_profile()
    match_texts = list((profile.get("mainTable") or {}).get("matchTexts") or [])
    candidates = []
    for table in root.iter(HP_TBL):
        text = _text(table)
        score = sum(1 for needle in match_texts if needle and needle in text)
        if score:
            candidates.append((score, len(text), table))
    if not candidates:
        raise Form10StructureError("서식10 본문 표를 찾지 못했습니다.")
    candidates.sort(key=lambda item: (-item[0], -item[1]))
    table = candidates[0][2]
    if candidates[0][0] < max(2, len(match_texts) - 1):
        raise Form10StructureError("서식10 본문 표 후보의 신뢰도가 낮습니다.")
    return table


def _cell_map(table: ET.Element) -> dict[tuple[int, int], ET.Element]:
    result: dict[tuple[int, int], ET.Element] = {}
    for row in list(table):
        if row.tag != HP_TR:
            continue
        for cell in list(row):
            if cell.tag != HP_TC:
                continue
            addr = cell.find(HP_ADDR)
            if addr is None:
                continue
            try:
                row_addr = int(addr.get("rowAddr") or 0)
                col_addr = int(addr.get("colAddr") or 0)
            except ValueError:
                continue
            result[(row_addr, col_addr)] = cell
    return result


def _analyze_section(raw: bytes) -> dict[str, Any]:
    _register_namespaces(raw)
    root = ET.fromstring(raw)
    table = _find_main_table(root)
    cells = _cell_map(table)
    profile = load_profile()
    main = profile.get("mainTable") or {}
    verified = profile.get("verifiedCells2025") or {}
    checked = []
    for key, spec in verified.items():
        row = spec.get("row")
        col = spec.get("col")
        if row is None or col is None:
            continue
        cell = cells.get((int(row), int(col)))
        actual = _text(cell) if cell is not None else ""
        expected = str(spec.get("expectedText") or "")
        checked.append({
            "key": key,
            "row": row,
            "col": col,
            "found": cell is not None,
            "expectedText": expected or None,
            "actualText": actual,
            "textMatched": (expected in actual) if expected else None,
        })

    whole_text = _text(table)
    manager_cell = cells.get((1, 3))
    manager_title = _text(manager_cell) if manager_cell is not None else ""
    recovery_guide = "관계회복" in whole_text and "안내" in whole_text
    recovery_opinion = "관계회복" in whole_text and "학생 의견" in whole_text
    source_year = 2025 if ("2025.00.00" in whole_text or manager_title == "교장") else None
    expected_rows = int(main.get("expectedRows") or 0)
    expected_cols = int(main.get("expectedCols") or 0)
    actual_rows = int(table.get("rowCnt") or 0)
    actual_cols = int(table.get("colCnt") or 0)
    reference_match = (
        actual_rows == expected_rows
        and actual_cols == expected_cols
        and all(item["found"] and item["textMatched"] is not False for item in checked)
    )
    current_2026_signals = manager_title == "교감" and recovery_guide and recovery_opinion
    return {
        "tableId": table.get("id"),
        "rows": actual_rows,
        "cols": actual_cols,
        "managerTitle": manager_title,
        "sourceYearDetected": source_year,
        "reference2025Match": reference_match,
        "recoveryGuideObserved": recovery_guide,
        "recoveryOpinionObserved": recovery_opinion,
        "current2026SignalsObserved": current_2026_signals,
        "checkedCells": checked,
        "observed2026Differences": profile.get("observed2026Differences") or [],
        "productionReadyFor2026": bool(current_2026_signals),
        "productionNote": (
            "2026 PDF에서 확인된 주요 구조 신호가 모두 관찰되었습니다. 그래도 공식 2026 HWPX 원본 대조가 필요합니다."
            if current_2026_signals
            else "2025 HWPX 구조는 검증됐지만 2026 PDF와 차이가 있어 2026 최종서식으로 확정할 수 없습니다."
        ),
    }


def analyze_form10_structure(payload: bytes) -> dict[str, Any]:
    source = io.BytesIO(payload)
    if not zipfile.is_zipfile(source):
        raise Form10StructureError("유효한 HWPX ZIP 패키지가 아닙니다.")
    source.seek(0)
    with zipfile.ZipFile(source, "r") as zf:
        for name in sorted(zf.namelist()):
            if not re.fullmatch(r"Contents/section\d+\.xml", name):
                continue
            raw = zf.read(name)
            try:
                result = _analyze_section(raw)
                result["section"] = name
                return result
            except Form10StructureError:
                continue
    raise Form10StructureError("HWPX에서 서식10 본문 구조를 찾지 못했습니다.")


def prepare_form10_upload(
    payload: bytes,
    original_name: str,
    source_dir: Path,
) -> tuple[bytes, dict[str, Any]]:
    """전체 서식모음집이면 원본을 보관하고 서식10 페이지만 추출하여 등록용 바이트를 돌려준다."""
    source_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^0-9A-Za-z가-힣_.() -]+", "_", original_name or "form10_source.hwpx")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stored = source_dir / f"{stamp}_{safe_name}"
    stored.write_bytes(payload)

    extracted = False
    prepared = payload
    try:
        prepared = extract_form10_from_bundle(payload)
        extracted = prepared != payload
    except Form10StructureError:
        # 단독 서식10 파일은 페이지 표식이 없을 수 있으므로 구조 분석 가능 여부로 판정한다.
        analyze_form10_structure(payload)

    structure = analyze_form10_structure(prepared)
    return prepared, {
        "sourceOriginalName": original_name,
        "sourceStoredAs": stored.name,
        "extractedFromBundle": extracted,
        "structure": structure,
    }
