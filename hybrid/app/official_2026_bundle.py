from __future__ import annotations

import hashlib
import io
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

from chungbuk_form10 import analyze_form10_structure, extract_form10_from_bundle
from chungbuk_form12 import analyze_form12_structure, extract_form12_from_bundle
from hwpx_engine import (
    ANALYSIS_DIR,
    ARCHIVE_DIR,
    BUILD_REPORT_DIR,
    BUILT_DIR,
    SOURCE_BUNDLE_DIR,
    TEMPLATE_DIR,
    load_registry,
    save_analysis,
)


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _direct(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(elem) if _local(child.tag) == name]


def _texts(elem: ET.Element) -> list[ET.Element]:
    return [node for node in elem.iter() if _local(node.tag) == "t"]


def _text(elem: ET.Element) -> str:
    return " ".join(" ".join((node.text or "").split()) for node in _texts(elem) if (node.text or "").strip()).strip()


def _tables(root: ET.Element) -> list[ET.Element]:
    return [node for node in root.iter() if _local(node.tag) == "tbl"]


def _ensure_text(cell: ET.Element) -> ET.Element:
    nodes = _texts(cell)
    if nodes:
        return nodes[0]
    run = next((node for node in cell.iter() if _local(node.tag) == "run"), None)
    if run is None:
        para = next((node for node in cell.iter() if _local(node.tag) == "p"), None)
        if para is None:
            raise ValueError("HWPX 셀에서 텍스트 삽입 위치를 찾지 못했습니다.")
        ns = para.tag.split("}")[0].lstrip("{") if "}" in para.tag else ""
        run_tag = f"{{{ns}}}run" if ns else "run"
        run = ET.SubElement(para, run_tag)
    ns = run.tag.split("}")[0].lstrip("{") if "}" in run.tag else ""
    text_tag = f"{{{ns}}}t" if ns else "t"
    return ET.SubElement(run, text_tag)


def _replace_cell(cell: ET.Element, value: str) -> None:
    nodes = _texts(cell)
    first = nodes[0] if nodes else _ensure_text(cell)
    first.text = value
    for node in nodes[1:]:
        node.text = ""


def _replace_nth_text(cell: ET.Element, index: int, value: str) -> None:
    nodes = _texts(cell)
    while len(nodes) <= index:
        nodes.append(_ensure_text(cell))
    nodes[index].text = value


def _main_form10_table(root: ET.Element) -> ET.Element:
    for table in _tables(root):
        text = _text(table)
        rows = _direct(table, "tr")
        if len(rows) >= 22 and all(key in text for key in ("학교명", "접수일시", "전담조사관", "관련학생", "관계회복")):
            return table
    raise ValueError("2026 서식10 본문 표를 찾지 못했습니다.")


def _facts_form10_table(root: ET.Element) -> ET.Element:
    for table in _tables(root):
        rows = _direct(table, "tr")
        text = _text(table)
        if len(rows) == 5 and all(key in text for key in ("관련학생", "일시", "장소", "내용", "유형", "신체폭력")):
            return table
    raise ValueError("2026 서식10 사실확인 세부표를 찾지 못했습니다.")


def _main_form12_table(root: ET.Element) -> ET.Element:
    for table in _tables(root):
        rows = _direct(table, "tr")
        text = _text(table)
        if len(rows) >= 38 and all(key in text for key in ("신고접수 일자", "사안조사 일자", "관련 학생", "학교폭력의", "특이사항")):
            return table
    raise ValueError("2026 서식12 본문 표를 찾지 못했습니다.")


def _cell(table: ET.Element, row_index: int, cell_index: int) -> ET.Element:
    rows = _direct(table, "tr")
    if row_index >= len(rows):
        raise ValueError(f"표 행 인덱스가 범위를 벗어났습니다: {row_index}")
    cells = _direct(rows[row_index], "tc")
    if cell_index >= len(cells):
        raise ValueError(f"표 셀 인덱스가 범위를 벗어났습니다: {row_index}/{cell_index}")
    return cells[cell_index]


def _build_form10_xml(raw: bytes) -> bytes:
    root = ET.fromstring(raw)
    main = _main_form10_table(root)
    facts = _facts_form10_table(root)
    _replace_nth_text(_cell(main, 0, 0), 1, "{{CASE_NO}}")
    _replace_cell(_cell(main, 1, 1), "{{SCHOOL_NAME}}")
    _replace_cell(_cell(main, 1, 7), "{{TEACHER_NAME}}")
    _replace_cell(_cell(main, 3, 1), "{{RECEIVED_AT}}")
    _replace_cell(_cell(main, 4, 1), "{{REPORTER_NAME}} ({{REPORTER_ROLE}})\n* 신고자가 익명을 희망할 경우 익명 처리")
    _replace_cell(_cell(main, 4, 3), "{{RECOGNITION_PATH}}")
    _replace_cell(_cell(main, 5, 1), "{{RECEIVER_NAME}} ({{RECEIVER_ROLE}})")
    _replace_cell(_cell(facts, 0, 1), "{{VICTIM_NAMES}} / {{PERP_NAMES}}\n※ 육하원칙에 의거 접수한 내용을 간략히 기재")
    _replace_cell(_cell(facts, 1, 1), "{{INCIDENT_DATE}}")
    _replace_cell(_cell(facts, 2, 1), "{{INCIDENT_PLACE}}")
    _replace_cell(_cell(facts, 3, 1), "{{INCIDENT_SUMMARY}}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _build_form12_xml(raw: bytes) -> bytes:
    root = ET.fromstring(raw)
    main = _main_form12_table(root)
    _replace_cell(_cell(main, 0, 1), "{{RECEIVED_AT}}")
    _replace_cell(_cell(main, 0, 3), "{{RESPONSIBLE_TEACHER_NAME}}")
    _replace_cell(_cell(main, 1, 1), "{{INVESTIGATION_DATE}}")
    _replace_cell(_cell(main, 1, 3), "{{INVESTIGATOR_NAME}} / {{INVESTIGATOR_CONTACT}}")
    _replace_cell(_cell(main, 2, 1), "유형: {{VIOLENCE_TYPE}}")
    _replace_cell(_cell(main, 8, 1), "{{INCIDENT_SUMMARY}}")
    _replace_cell(_cell(main, 9, 1), "{{INCIDENT_CHRONOLOGY}}")
    _replace_cell(_cell(main, 11, 0), "{{SEPARATION}}")
    _replace_cell(_cell(main, 12, 0), "분리기간: {{SEPARATION_PERIOD}}")
    _replace_cell(_cell(main, 14, 0), "1. 2주 이상 치료 진단서 없음: {{SELF_RESOLUTION_CRITERION_1}}\n2. 재산상 피해 없음/복구: {{SELF_RESOLUTION_CRITERION_2}}\n3. 지속적이지 않음: {{SELF_RESOLUTION_CRITERION_3}}\n4. 보복행위 아님: {{SELF_RESOLUTION_CRITERION_4}}\n조사 의견: {{SELF_RESOLUTION_OPINION}}")
    _replace_cell(_cell(main, 14, 1), "{{SELF_RESOLUTION_CONSENT}}")
    _replace_cell(_cell(main, 15, 2), "피해·쟁점 관련: {{DAMAGE}}")
    _replace_cell(_cell(main, 15, 3), "{{EVIDENCE}}")
    _replace_cell(_cell(main, 22, 1), "{{JUDGMENT_SEVERITY}}")
    _replace_cell(_cell(main, 23, 1), "{{JUDGMENT_PERSISTENCE}}")
    _replace_cell(_cell(main, 24, 1), "{{JUDGMENT_INTENTIONALITY}}")
    _replace_cell(_cell(main, 25, 1), "{{JUDGMENT_REMORSE}}")
    _replace_cell(_cell(main, 26, 1), "{{JUDGMENT_RECONCILIATION}}")
    _replace_cell(_cell(main, 29, 1), "{{JUDGMENT_GUIDANCE}}")
    _replace_cell(_cell(main, 30, 1), "{{JUDGMENT_VICTIM_DISABILITY}}")
    _replace_cell(_cell(main, 31, 2), "{{EMERGENCY_MEASURES}}")
    _replace_cell(_cell(main, 33, 1), "{{RECURRENCE_HISTORY}}")
    _replace_cell(_cell(main, 37, 1), "{{SPECIAL_NOTES}}\n{{OTHER_NOTES}}\n피해측 관계회복 의견: {{VICTIM_RECOVERY_OPINION}}\n가해측 관계회복 의견: {{PERP_RECOVERY_OPINION}}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _transform_hwpx(payload: bytes, transformer: Callable[[bytes], bytes]) -> bytes:
    if not payload or not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError("유효한 HWPX ZIP 패키지가 아닙니다.")
    output = io.BytesIO()
    changed = False
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zin, zipfile.ZipFile(output, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if not changed and info.filename.startswith("Contents/section") and info.filename.endswith(".xml"):
                try:
                    candidate = transformer(data)
                except (ET.ParseError, ValueError):
                    pass
                else:
                    data = candidate
                    changed = True
            compress = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(info.filename, data, compress_type=compress)
    if not changed:
        raise ValueError("공식 2026 서식 본문을 찾아 생성용 템플릿으로 변환하지 못했습니다.")
    return output.getvalue()


def build_form10_official_2026(source: bytes) -> bytes:
    return _transform_hwpx(source, _build_form10_xml)


def build_form12_official_2026(source: bytes) -> bytes:
    return _transform_hwpx(source, _build_form12_xml)


def _archive(path: Path) -> str | None:
    if not path.exists():
        return None
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = ARCHIVE_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, target)
    return target.name


def _write_document(key: str, source_bytes: bytes, built_bytes: bytes, structure: dict[str, Any], source_sha256: str, original_name: str) -> dict[str, Any]:
    registry = load_registry()
    doc = (registry.get("documents") or {}).get(key) or {}
    template_name = str(doc.get("template") or "").strip()
    if not template_name:
        raise ValueError(f"{key} 템플릿 파일명이 레지스트리에 없습니다.")
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    BUILT_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    source_path = TEMPLATE_DIR / template_name
    built_path = BUILT_DIR / template_name
    archived = _archive(source_path)
    source_path.write_bytes(source_bytes)
    built_path.write_bytes(built_bytes)
    structure_report = dict(structure or {})
    structure_report.update({"sourceYear": 2026, "sourceKind": "official_hwpx_bundle", "sourceOriginalName": original_name, "sourceSha256": source_sha256, "officialSourceRegistered": True, "structureLocked": True, "hancomVisualVerified": False, "official2026HwpxVerified": False})
    (ANALYSIS_DIR / f"{key}_structure.json").write_text(json.dumps(structure_report, ensure_ascii=False, indent=2), encoding="utf-8")
    save_analysis(key)
    build_report = {"documentKey": key, "sourceTemplate": template_name, "sourceKind": "official_2026_hwpx_direct", "sourceSha256": source_sha256, "officialSourceRegistered": True, "official2026HwpxVerified": False, "hancomVisualVerified": False, "builtTemplate": built_path.relative_to(TEMPLATE_DIR).as_posix(), "builtAt": datetime.now().isoformat(timespec="seconds"), "mappingStatus": "official_2026_structural", "note": "공식 2026 HWPX 원본에서 직접 추출·토큰화한 시험 템플릿. 한컴오피스 화면·인쇄 대조 전에는 제출용으로 사용하지 않음."}
    (BUILD_REPORT_DIR / f"{key}.json").write_text(json.dumps(build_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"documentKey": key, "template": template_name, "sourceBytes": len(source_bytes), "builtBytes": len(built_bytes), "archivedPrevious": archived, "structure": structure_report, "buildReport": build_report}


def register_official_2026_bundle(payload: bytes, original_name: str) -> dict[str, Any]:
    if not payload or not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError("유효한 2026 HWPX 서식모음집 파일이 아닙니다.")
    source_sha256 = hashlib.sha256(payload).hexdigest()
    SOURCE_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    stored = SOURCE_BUNDLE_DIR / "2026_official_forms_bundle.hwpx"
    stored.write_bytes(payload)
    form10_source = extract_form10_from_bundle(payload)
    form12_source = extract_form12_from_bundle(payload)
    form10_structure = analyze_form10_structure(form10_source)
    form12_structure = analyze_form12_structure(form12_source)
    form10_built = build_form10_official_2026(form10_source)
    form12_built = build_form12_official_2026(form12_source)
    for label, data in (("서식10", form10_built), ("서식12", form12_built)):
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            bad = zf.testzip()
            if bad:
                raise ValueError(f"{label} 생성용 HWPX 무결성 검사 실패: {bad}")
    form10 = _write_document("form10_case_report", form10_source, form10_built, form10_structure, source_sha256, original_name)
    form12 = _write_document("form12_investigation_report", form12_source, form12_built, form12_structure, source_sha256, original_name)
    return {"sourceOriginalName": original_name, "sourceStoredAs": stored.name, "sourceSha256": source_sha256, "officialSourceRegistered": True, "official2026HwpxVerified": False, "hancomVisualVerified": False, "documents": [form10, form12], "warning": "공식 2026 HWPX에서 직접 빌드했습니다. 한컴오피스 화면·인쇄 1:1 대조 전에는 제출용으로 사용하지 마세요."}
