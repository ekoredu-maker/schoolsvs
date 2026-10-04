from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
REGISTRY_PATH = Path(__file__).with_name("document_registry.json")
TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")


@dataclass
class DocumentResult:
    document_key: str
    output_path: Path
    replaced_tokens: list[str]
    missing_tokens: list[str]


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"version": "0", "documents": {}}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_documents() -> list[dict[str, Any]]:
    registry = load_registry()
    docs = []
    for key, item in (registry.get("documents") or {}).items():
        template_name = item.get("template") or ""
        template_path = TEMPLATE_DIR / template_name if template_name else None
        docs.append({
            "key": key,
            "label": item.get("label") or key,
            "formNo": item.get("form_no"),
            "stage": item.get("stage"),
            "template": template_name,
            "templateReady": bool(template_path and template_path.exists()),
            "mappingReady": bool(item.get("fields")),
        })
    return docs


def _get_path(data: dict[str, Any], path: str, default: str = "") -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _first_name(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    names = [str((x or {}).get("name") or "").strip() for x in items if isinstance(x, dict)]
    return ", ".join(x for x in names if x)


def build_context(case: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, str]:
    settings = settings or {}
    ctx: dict[str, str] = {
        "case.id": str(case.get("id") or ""),
        "case.caseNo": str(case.get("caseNo") or ""),
        "case.recvAt": str(case.get("recvAt") or ""),
        "case.incidentDate": str(case.get("incidentDate") or ""),
        "case.incidentPlace": str(case.get("incidentPlace") or ""),
        "case.reportType": str(case.get("reportType") or ""),
        "case.violenceType": str(case.get("violenceType") or ""),
        "case.summary": str(case.get("summary") or ""),
        "case.damage": str(case.get("damage") or ""),
        "case.evidence": str(case.get("evidence") or ""),
        "case.separation": str(case.get("separation") or ""),
        "case.sepPeriod": str(case.get("sepPeriod") or ""),
        "case.separationPlace": str(case.get("separationPlace") or ""),
        "case.officeReport": str(case.get("officeReport") or ""),
        "case.officeDate": str(case.get("officeDate") or ""),
        "case.investigatorName": str(case.get("investigatorName") or ""),
        "case.investigationDate": str(case.get("investigationDate") or ""),
        "case.committeeDate": str(case.get("committeeDate") or ""),
        "case.actionCode": str(case.get("actionCode") or ""),
        "case.actionContent": str(case.get("actionContent") or ""),
        "case.actionDate": str(case.get("actionDate") or ""),
        "case.closedDate": str(case.get("closedDate") or ""),
        "victims.names": _first_name(case.get("victims")),
        "perps.names": _first_name(case.get("perps")),
        "school.name": str(case.get("school") or settings.get("school") or ""),
        "teacher.name": str(case.get("teacher") or settings.get("teacher") or ""),
        "teacher.position": str(case.get("teacherPosition") or settings.get("position") or ""),
        "school.address": str(settings.get("address") or ""),
        "school.phone": str(settings.get("phone") or ""),
        "school.office": str(settings.get("office") or ""),
        "school.principal": str(settings.get("principal") or ""),
        "school.vicePrincipal": str(settings.get("vicePrincipal") or ""),
    }
    return ctx


def _normalize_mapping(case: dict[str, Any], settings: dict[str, Any], fields: dict[str, Any]) -> dict[str, str]:
    base = build_context(case, settings)
    values: dict[str, str] = {}
    for token, spec in fields.items():
        if isinstance(spec, str):
            if spec in base:
                value = base.get(spec, "")
            elif spec.startswith("case."):
                value = _get_path(case, spec.removeprefix("case."), "")
            elif spec.startswith("settings."):
                value = _get_path(settings, spec.removeprefix("settings."), "")
            else:
                value = spec
        elif isinstance(spec, dict):
            source = str(spec.get("source") or "")
            value = base.get(source, _get_path(case, source.removeprefix("case."), ""))
            if spec.get("default") and not value:
                value = spec.get("default")
        else:
            value = ""
        values[token] = "" if value is None else str(value)
    return values


def _replace_text_nodes(xml_bytes: bytes, replacements: dict[str, str]) -> tuple[bytes, set[str], set[str]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        text = xml_bytes.decode("utf-8", errors="ignore")
        replaced: set[str] = set()
        for token, value in replacements.items():
            marker = "{{" + token + "}}"
            if marker in text:
                text = text.replace(marker, value)
                replaced.add(token)
        remaining = set(TOKEN_RE.findall(text))
        return text.encode("utf-8"), replaced, remaining

    replaced: set[str] = set()
    for elem in root.iter():
        if elem.text:
            original = elem.text
            for token, value in replacements.items():
                marker = "{{" + token + "}}"
                if marker in elem.text:
                    elem.text = elem.text.replace(marker, value)
                    replaced.add(token)
            if elem.text != original:
                pass
        if elem.tail:
            for token, value in replacements.items():
                marker = "{{" + token + "}}"
                if marker in elem.tail:
                    elem.tail = elem.tail.replace(marker, value)
                    replaced.add(token)
    serialized = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    remaining = set(TOKEN_RE.findall(serialized.decode("utf-8", errors="ignore")))
    return serialized, replaced, remaining


def inspect_template(template_path: Path) -> dict[str, Any]:
    if not template_path.exists():
        raise FileNotFoundError(f"HWPX 템플릿을 찾을 수 없습니다: {template_path.name}")
    if not zipfile.is_zipfile(template_path):
        raise ValueError("유효한 HWPX ZIP 패키지가 아닙니다.")
    tokens: set[str] = set()
    xml_files: list[str] = []
    with zipfile.ZipFile(template_path, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".xml", ".hpf")):
                continue
            xml_files.append(name)
            text = zf.read(name).decode("utf-8", errors="ignore")
            tokens.update(TOKEN_RE.findall(text))
    return {
        "template": template_path.name,
        "xmlFiles": xml_files,
        "tokens": sorted(tokens),
        "tokenCount": len(tokens),
    }


def generate_document(document_key: str, case: dict[str, Any], settings: dict[str, Any] | None = None, output_name: str | None = None) -> DocumentResult:
    registry = load_registry()
    doc = (registry.get("documents") or {}).get(document_key)
    if not doc:
        raise KeyError(f"등록되지 않은 문서입니다: {document_key}")
    template_name = str(doc.get("template") or "").strip()
    if not template_name:
        raise ValueError("문서 템플릿 파일명이 등록되지 않았습니다.")
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"템플릿 미등록: {template_name}")
    if not zipfile.is_zipfile(template_path):
        raise ValueError(f"유효한 HWPX 파일이 아닙니다: {template_name}")

    settings = settings or {}
    replacements = _normalize_mapping(case, settings, doc.get("fields") or {})
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_case_no = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", str(case.get("caseNo") or case.get("id") or "case"))
    out_name = output_name or f"{safe_case_no}_{document_key}.hwpx"
    output_path = OUTPUT_DIR / out_name

    replaced: set[str] = set()
    remaining: set[str] = set()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(template_path, "r") as src:
            src.extractall(tmp)
        for path in tmp.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".xml", ".hpf"}:
                continue
            raw = path.read_bytes()
            updated, rep, rem = _replace_text_nodes(raw, replacements)
            if rep:
                path.write_bytes(updated)
                replaced.update(rep)
            remaining.update(rem)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for path in sorted(tmp.rglob("*")):
                if path.is_file():
                    out.write(path, path.relative_to(tmp).as_posix())

    missing = sorted(token for token in replacements if token not in replaced)
    missing.extend(sorted(token for token in remaining if token not in missing))
    return DocumentResult(document_key, output_path, sorted(replaced), missing)
