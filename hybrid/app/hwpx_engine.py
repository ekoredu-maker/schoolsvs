from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
ANALYSIS_DIR = TEMPLATE_DIR / "_analysis"
ARCHIVE_DIR = TEMPLATE_DIR / "_archive"
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


def _document_definition(document_key: str) -> dict[str, Any]:
    doc = (load_registry().get("documents") or {}).get(document_key)
    if not doc:
        raise KeyError(f"등록되지 않은 문서입니다: {document_key}")
    return doc


def list_documents() -> list[dict[str, Any]]:
    registry = load_registry()
    docs = []
    for key, item in (registry.get("documents") or {}).items():
        template_name = item.get("template") or ""
        template_path = TEMPLATE_DIR / template_name if template_name else None
        analysis_path = ANALYSIS_DIR / f"{key}.json"
        docs.append({
            "key": key,
            "label": item.get("label") or key,
            "formNo": item.get("form_no"),
            "stage": item.get("stage"),
            "template": template_name,
            "templateReady": bool(template_path and template_path.exists()),
            "mappingReady": bool(item.get("fields")),
            "analysisReady": analysis_path.exists(),
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
    return {
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


def _replace_raw_xml(xml_bytes: bytes, replacements: dict[str, str]) -> tuple[bytes, set[str], set[str]]:
    """원본 XML 구조를 다시 직렬화하지 않고 토큰 문자열만 최소 치환한다."""
    text = xml_bytes.decode("utf-8", errors="strict")
    replaced: set[str] = set()
    for token, value in replacements.items():
        marker = "{{" + token + "}}"
        if marker in text:
            text = text.replace(marker, value)
            replaced.add(token)
    remaining = set(TOKEN_RE.findall(text))
    return text.encode("utf-8"), replaced, remaining


def _extract_text_samples(xml_bytes: bytes, max_items: int = 240) -> list[str]:
    """원본을 수정하지 않고 XML의 실제 텍스트 조각만 분석용으로 추출한다."""
    samples: list[str] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return samples
    for elem in root.iter():
        if not elem.text:
            continue
        text = " ".join(elem.text.split()).strip()
        if not text or text in samples:
            continue
        samples.append(text)
        if len(samples) >= max_items:
            break
    return samples


def inspect_template(template_path: Path) -> dict[str, Any]:
    if not template_path.exists():
        raise FileNotFoundError(f"HWPX 템플릿을 찾을 수 없습니다: {template_path.name}")
    if not zipfile.is_zipfile(template_path):
        raise ValueError("유효한 HWPX ZIP 패키지가 아닙니다.")
    tokens: set[str] = set()
    xml_files: list[str] = []
    text_samples: list[dict[str, Any]] = []
    with zipfile.ZipFile(template_path, "r") as zf:
        names = zf.namelist()
        for name in names:
            if not name.lower().endswith((".xml", ".hpf")):
                continue
            xml_files.append(name)
            raw = zf.read(name)
            text = raw.decode("utf-8", errors="ignore")
            tokens.update(TOKEN_RE.findall(text))
            samples = _extract_text_samples(raw)
            if samples:
                text_samples.append({"file": name, "items": samples})
        mimetype_stored = False
        if "mimetype" in names:
            mimetype_stored = zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    return {
        "template": template_path.name,
        "size": template_path.stat().st_size,
        "packageFiles": len(names),
        "xmlFiles": xml_files,
        "xmlFileCount": len(xml_files),
        "tokens": sorted(tokens),
        "tokenCount": len(tokens),
        "mimetypeStored": mimetype_stored,
        "textSamples": text_samples,
    }


def save_analysis(document_key: str) -> dict[str, Any]:
    doc = _document_definition(document_key)
    template_name = str(doc.get("template") or "").strip()
    if not template_name:
        raise ValueError("문서 템플릿 파일명이 등록되지 않았습니다.")
    info = inspect_template(TEMPLATE_DIR / template_name)
    info["documentKey"] = document_key
    info["documentLabel"] = doc.get("label") or document_key
    info["analyzedAt"] = datetime.now().isoformat(timespec="seconds")
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    path = ANALYSIS_DIR / f"{document_key}.json"
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def get_saved_analysis(document_key: str) -> dict[str, Any] | None:
    path = ANALYSIS_DIR / f"{document_key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def register_template(document_key: str, payload: bytes, original_name: str = "") -> dict[str, Any]:
    """공식 원본 HWPX를 등록하고 기존 파일은 자동 보관한다."""
    doc = _document_definition(document_key)
    template_name = str(doc.get("template") or "").strip()
    if not template_name:
        raise ValueError("레지스트리에 템플릿 파일명이 없습니다.")
    if not payload:
        raise ValueError("업로드된 HWPX 파일이 비어 있습니다.")

    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    try:
        if not zipfile.is_zipfile(tmp_path):
            raise ValueError("유효한 HWPX ZIP 패키지가 아닙니다.")
        inspect_template(tmp_path)
        target = TEMPLATE_DIR / template_name
        archived = None
        if target.exists():
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archived = ARCHIVE_DIR / f"{target.stem}_{stamp}{target.suffix}"
            shutil.copy2(target, archived)
        shutil.copy2(tmp_path, target)
        analysis = save_analysis(document_key)
        return {
            "documentKey": document_key,
            "template": template_name,
            "originalName": original_name,
            "archivedPrevious": archived.name if archived else None,
            "analysis": analysis,
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_hwpx_package(source_dir: Path, output_path: Path) -> None:
    files = [p for p in source_dir.rglob("*") if p.is_file()]
    mimetype = source_dir / "mimetype"
    with zipfile.ZipFile(output_path, "w") as out:
        if mimetype.exists():
            out.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(files):
            relative = path.relative_to(source_dir).as_posix()
            if relative == "mimetype":
                continue
            out.write(path, relative, compress_type=zipfile.ZIP_DEFLATED)


def generate_document(document_key: str, case: dict[str, Any], settings: dict[str, Any] | None = None, output_name: str | None = None) -> DocumentResult:
    doc = _document_definition(document_key)
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
            try:
                updated, rep, rem = _replace_raw_xml(raw, replacements)
            except UnicodeDecodeError:
                continue
            if rep:
                path.write_bytes(updated)
                replaced.update(rep)
            remaining.update(rem)
        _write_hwpx_package(tmp, output_path)

    missing = sorted(token for token in replacements if token not in replaced)
    missing.extend(sorted(token for token in remaining if token not in missing))
    return DocumentResult(document_key, output_path, sorted(replaced), missing)
