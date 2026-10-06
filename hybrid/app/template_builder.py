from __future__ import annotations

import json
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from form10_adaptive import adaptive_path, build_adaptive_form10, load_adaptive_report
from hwpx_engine import BUILT_DIR, TEMPLATE_DIR, load_registry
from mapping_service import load_mapping

REPORT_DIR = TEMPLATE_DIR / "_build_reports"
CELL_OPEN_RE = re.compile(r"<(?P<prefix>[A-Za-z0-9_]+:)?tc\b[^>]*>", re.I)
CELL_CLOSE_RE = re.compile(r"</(?P<prefix>[A-Za-z0-9_]+:)?tc\s*>", re.I)
TEXT_OPEN_RE = re.compile(r"<(?P<prefix>[A-Za-z0-9_]+:)?t\b[^>]*>", re.I)
TEXT_CLOSE_RE = re.compile(r"</(?P<prefix>[A-Za-z0-9_]+:)?t\s*>", re.I)


def _nth_index(text: str, needle: str, occurrence: int) -> int:
    if not needle:
        return -1
    pos = -1
    start = 0
    for _ in range(max(1, occurrence)):
        pos = text.find(needle, start)
        if pos < 0:
            return -1
        start = pos + len(needle)
    return pos


def _replace_nth(text: str, needle: str, replacement: str, occurrence: int) -> tuple[str, bool]:
    pos = _nth_index(text, needle, occurrence)
    if pos < 0:
        return text, False
    return text[:pos] + replacement + text[pos + len(needle):], True


def _same_text_append(xml: str, anchor: str, token: str, occurrence: int) -> tuple[str, bool, str]:
    pos = _nth_index(xml, anchor, occurrence)
    if pos < 0:
        return xml, False, "앵커 문구를 찾지 못했습니다."
    open_matches = list(TEXT_OPEN_RE.finditer(xml, 0, pos + 1))
    if not open_matches:
        return xml, False, "앵커가 텍스트 노드 안에 있지 않습니다."
    close_match = TEXT_CLOSE_RE.search(xml, pos)
    if not close_match:
        return xml, False, "앵커 텍스트 노드의 끝을 찾지 못했습니다."
    marker = "{{" + token + "}}"
    return xml[:close_match.start()] + marker + xml[close_match.start():], True, "같은 텍스트 노드 뒤에 토큰을 삽입했습니다."


def _next_cell_replace(xml: str, anchor: str, token: str, occurrence: int) -> tuple[str, bool, str]:
    pos = _nth_index(xml, anchor, occurrence)
    if pos < 0:
        return xml, False, "앵커 문구를 찾지 못했습니다."
    cell_opens = list(CELL_OPEN_RE.finditer(xml, 0, pos + 1))
    if not cell_opens:
        return xml, False, "앵커가 표 셀 안에 있지 않습니다."
    current_close = CELL_CLOSE_RE.search(xml, max(pos, cell_opens[-1].end()))
    if not current_close:
        return xml, False, "앵커 셀의 끝을 찾지 못했습니다."
    next_open = CELL_OPEN_RE.search(xml, current_close.end())
    if not next_open:
        return xml, False, "앵커 다음 값 셀을 찾지 못했습니다."
    next_close = CELL_CLOSE_RE.search(xml, next_open.end())
    if not next_close:
        return xml, False, "다음 값 셀의 끝을 찾지 못했습니다."
    text_open = TEXT_OPEN_RE.search(xml, next_open.end(), next_close.start())
    if not text_open:
        return xml, False, "다음 값 셀 안의 텍스트 영역을 찾지 못했습니다."
    text_close = TEXT_CLOSE_RE.search(xml, text_open.end(), next_close.start())
    if not text_close:
        return xml, False, "다음 값 셀의 텍스트 영역 끝을 찾지 못했습니다."
    marker = "{{" + token + "}}"
    return xml[:text_open.end()] + marker + xml[text_close.start():], True, "앵커 다음 셀의 첫 텍스트 값을 토큰으로 교체했습니다."


def _apply_item(xml: str, item: dict[str, Any]) -> tuple[str, bool, str]:
    anchor = str(item.get("anchor") or "")
    token = str(item.get("token") or "")
    occurrence = max(1, int(item.get("occurrence") or 1))
    strategy = str(item.get("strategy") or "next_cell_replace")
    marker = "{{" + token + "}}"
    if marker in xml:
        return xml, True, "이미 토큰이 존재합니다."
    if strategy == "replace_anchor":
        updated, ok = _replace_nth(xml, anchor, marker, occurrence)
        return updated, ok, "앵커 자체를 토큰으로 교체했습니다." if ok else "앵커 문구를 찾지 못했습니다."
    if strategy == "same_text_append":
        return _same_text_append(xml, anchor, token, occurrence)
    return _next_cell_replace(xml, anchor, token, occurrence)


def _write_package(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = [p for p in source_dir.rglob("*") if p.is_file()]
    with zipfile.ZipFile(output_path, "w") as out:
        mimetype = source_dir / "mimetype"
        if mimetype.exists():
            out.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(files):
            relative = path.relative_to(source_dir).as_posix()
            if relative != "mimetype":
                out.write(path, relative, compress_type=zipfile.ZIP_DEFLATED)


def _source_for_build(document_key: str, registered_source: Path) -> tuple[Path, str, dict[str, Any] | None]:
    if document_key != "form10_case_report":
        return registered_source, "registered_source", None
    if adaptive_path().exists():
        return adaptive_path(), "2026_pdf_adaptive", load_adaptive_report()
    try:
        adaptive_report = build_adaptive_form10()
        return adaptive_path(), "2026_pdf_adaptive", adaptive_report
    except ValueError:
        # 공식 2026 HWPX처럼 2025 20행×15열 구조가 아니면 등록 원본을 그대로 사용한다.
        return registered_source, "registered_source", None


def build_template(document_key: str) -> dict[str, Any]:
    registry = load_registry()
    doc = (registry.get("documents") or {}).get(document_key)
    if not doc:
        raise KeyError(f"등록되지 않은 문서입니다: {document_key}")
    template_name = str(doc.get("template") or "").strip()
    if not template_name:
        raise ValueError("원본 HWPX 파일명이 등록되지 않았습니다.")
    registered_source = TEMPLATE_DIR / template_name
    if not registered_source.exists():
        raise FileNotFoundError(f"공식 원본 HWPX가 등록되지 않았습니다: {template_name}")
    if not zipfile.is_zipfile(registered_source):
        raise ValueError("등록된 원본이 유효한 HWPX ZIP 패키지가 아닙니다.")

    source, source_kind, adaptive_report = _source_for_build(document_key, registered_source)
    mapping = load_mapping(document_key)
    confirmed = [x for x in mapping.get("items") or [] if x.get("confirmed")]
    registry_fields = doc.get("fields") or {}
    confirmed_tokens = {str(x.get("token") or "") for x in confirmed}
    missing_mapping = [token for token in registry_fields if token not in confirmed_tokens]
    if missing_mapping:
        raise ValueError("확정되지 않은 필드 매핑이 있습니다: " + ", ".join(missing_mapping[:12]))

    output = BUILT_DIR / template_name
    report_items: list[dict[str, Any]] = []
    inserted_tokens: set[str] = set()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(source, "r") as zf:
            zf.extractall(tmp)
        xml_paths = [p for p in tmp.rglob("*") if p.is_file() and p.suffix.lower() in {".xml", ".hpf"}]
        for item in confirmed:
            token = str(item.get("token") or "")
            requested_file = str(item.get("xmlFile") or "").strip()
            candidate_paths = xml_paths
            if requested_file:
                specific = tmp / requested_file
                candidate_paths = [specific] if specific.exists() else []
            applied = False; detail = ""; applied_file = ""
            for path in candidate_paths:
                try:
                    xml = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                updated, ok, message = _apply_item(xml, item)
                if not ok:
                    detail = message; continue
                path.write_text(updated, encoding="utf-8")
                inserted_tokens.add(token); applied = True; detail = message
                applied_file = path.relative_to(tmp).as_posix(); break
            report_items.append({"token": token, "anchor": item.get("anchor"), "strategy": item.get("strategy") or "next_cell_replace", "requestedXmlFile": requested_file, "appliedXmlFile": applied_file, "success": applied, "message": detail or "삽입 위치를 찾지 못했습니다."})
        unresolved = [x["token"] for x in report_items if not x["success"]]
        if unresolved:
            raise ValueError("토큰 삽입 위치를 확정하지 못했습니다: " + ", ".join(unresolved[:12]))
        _write_package(tmp, output)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "documentKey": document_key,
        "sourceTemplate": template_name,
        "sourceKind": source_kind,
        "adaptiveOfficial2026Verified": bool((adaptive_report or {}).get("official2026HwpxVerified")) if adaptive_report else None,
        "builtTemplate": output.relative_to(TEMPLATE_DIR).as_posix(),
        "builtAt": datetime.now().isoformat(timespec="seconds"),
        "mappingStatus": mapping.get("status"),
        "insertedTokens": sorted(inserted_tokens),
        "items": report_items,
    }
    (REPORT_DIR / f"{document_key}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_build_report(document_key: str) -> dict[str, Any] | None:
    path = REPORT_DIR / f"{document_key}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def invalidate_built_template(document_key: str) -> None:
    registry = load_registry()
    doc = (registry.get("documents") or {}).get(document_key) or {}
    template_name = str(doc.get("template") or "").strip()
    if template_name:
        (BUILT_DIR / template_name).unlink(missing_ok=True)
    (REPORT_DIR / f"{document_key}.json").unlink(missing_ok=True)
