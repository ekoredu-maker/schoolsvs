from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from hwpx_engine import ANALYSIS_DIR, REGISTRY_PATH, load_registry

MAPPING_DIR = REGISTRY_PATH.parent.parent / "mappings"

SOURCE_CATALOG = [
    {"source": "school.name", "label": "학교명", "keywords": ["학교명", "학교", "소속"]},
    {"source": "case.caseNo", "label": "사안번호", "keywords": ["사안번호", "접수번호", "관리번호"]},
    {"source": "case.recvAt", "label": "접수일시", "keywords": ["접수일시", "접수 일시", "신고일시", "신고 일시"]},
    {"source": "case._hybrid.atoz.reporterName", "label": "신고자 성명", "keywords": ["신고자", "성명"]},
    {"source": "case._hybrid.atoz.reporterRole", "label": "신고자 신분", "keywords": ["신고자", "신분"]},
    {"source": "case._hybrid.atoz.recognitionPath", "label": "접수·인지 경로", "keywords": ["접수·인지 경로", "접수인지경로", "인지 경로"]},
    {"source": "case._hybrid.atoz.receiverName", "label": "접수자·인지자", "keywords": ["접수자·인지자", "접수자", "인지자"]},
    {"source": "case._hybrid.atoz.investigationMode", "label": "조사관 배정요청", "keywords": ["조사관", "배정요청", "배정 요청"]},
    {"source": "case._hybrid.atoz.no2ActionDate", "label": "가해학생 제2호 조치", "keywords": ["제2호", "2호 조치", "가해학생"]},
    {"source": "case.incidentDate", "label": "사건 발생일", "keywords": ["발생일", "발생 일시", "사건일"]},
    {"source": "case.incidentPlace", "label": "사건 발생 장소", "keywords": ["발생장소", "발생 장소", "장소"]},
    {"source": "case.reportType", "label": "신고 유형", "keywords": ["신고유형", "신고 유형", "인지경위"]},
    {"source": "case.violenceType", "label": "학교폭력 유형", "keywords": ["폭력유형", "폭력 유형", "유형"]},
    {"source": "victims.names", "label": "피해관련학생", "keywords": ["피해관련학생", "피해학생", "피해 학생"]},
    {"source": "perps.names", "label": "가해관련학생", "keywords": ["가해관련학생", "가해학생", "가해 학생"]},
    {"source": "students.all.form10Rows", "label": "관련학생 정보", "keywords": ["관련학생", "관련 학생", "학번", "성별"]},
    {"source": "students.all.form12Rows", "label": "관련학생 조사정보", "keywords": ["관련학생", "가해관련", "피해관련"]},
    {"source": "case.summary", "label": "사안 개요", "keywords": ["사안개요", "사안 개요", "사안내용", "사안 내용"]},
    {"source": "case.separation", "label": "분리조치", "keywords": ["분리조치", "분리 조치", "분리 여부"]},
    {"source": "case.sepPeriod", "label": "분리기간", "keywords": ["분리기간", "분리 기간"]},
    {"source": "case.separationPlace", "label": "분리장소", "keywords": ["분리장소", "분리 장소"]},
    {"source": "case.officeDate", "label": "교육지원청 보고일", "keywords": ["보고일", "보고 일자", "교육지원청"]},
    {"source": "teacher.name", "label": "담당자명", "keywords": ["담당자", "작성자", "담당교사"]},
    {"source": "teacher.position", "label": "담당자 직위", "keywords": ["직위", "직급"]},
    {"source": "case.investigatorName", "label": "전담조사관", "keywords": ["전담조사관", "조사관"]},
    {"source": "case.investigationDate", "label": "조사일", "keywords": ["조사일", "조사 일시"]},
    {"source": "case.committeeDate", "label": "전담기구 개최일", "keywords": ["전담기구", "개최일", "심의일"]},
    {"source": "case.closedDate", "label": "종결일", "keywords": ["종결일", "처리일"]},
]


def _mapping_path(document_key: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", document_key)
    return MAPPING_DIR / f"{safe}.json"


def load_mapping(document_key: str) -> dict[str, Any]:
    path = _mapping_path(document_key)
    if not path.exists():
        return {"documentKey": document_key, "version": 2, "status": "draft", "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_mapping(document_key: str, items: list[dict[str, Any]], status: str = "draft") -> dict[str, Any]:
    registry = load_registry()
    if document_key not in (registry.get("documents") or {}):
        raise KeyError(f"등록되지 않은 문서입니다: {document_key}")
    allowed_strategies = {"next_cell_replace", "same_text_append", "replace_anchor"}
    normalized = []
    for raw in items:
        token = str(raw.get("token") or "").strip()
        source = str(raw.get("source") or "").strip()
        anchor = str(raw.get("anchor") or "").strip()
        if not token or not source:
            continue
        strategy = str(raw.get("strategy") or "next_cell_replace")
        if strategy not in allowed_strategies:
            strategy = "next_cell_replace"
        normalized.append({
            "token": token,
            "source": source,
            "anchor": anchor,
            "xmlFile": str(raw.get("xmlFile") or ""),
            "occurrence": max(1, int(raw.get("occurrence") or 1)),
            "strategy": strategy,
            "confirmed": bool(raw.get("confirmed")),
            "note": str(raw.get("note") or ""),
        })
    payload = {
        "documentKey": document_key,
        "version": 2,
        "status": status if status in {"draft", "reviewed", "verified"} else "draft",
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "items": normalized,
    }
    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    _mapping_path(document_key).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def source_catalog() -> list[dict[str, Any]]:
    return SOURCE_CATALOG


def _analysis_snippets(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """v0.7 분석 포맷(textSamples)과 초기 매핑 테스트 포맷(textSnippets)을 모두 지원한다."""
    direct = analysis.get("textSnippets") or []
    if direct:
        return [
            {"file": str(x.get("file") or ""), "text": str(x.get("text") or "")}
            for x in direct if isinstance(x, dict)
        ]
    flattened: list[dict[str, str]] = []
    for group in analysis.get("textSamples") or []:
        if not isinstance(group, dict):
            continue
        file_name = str(group.get("file") or "")
        for text in group.get("items") or []:
            value = str(text or "").strip()
            if value:
                flattened.append({"file": file_name, "text": value})
    return flattened


def build_mapping_workspace(document_key: str) -> dict[str, Any]:
    registry = load_registry()
    doc = (registry.get("documents") or {}).get(document_key)
    if not doc:
        raise KeyError(f"등록되지 않은 문서입니다: {document_key}")
    analysis_path = ANALYSIS_DIR / f"{document_key}.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else None
    current = load_mapping(document_key)
    fields = [{"token": token, "source": source} for token, source in (doc.get("fields") or {}).items()]
    suggestions = suggest_anchors(fields, analysis or {})
    confirmed = sum(1 for x in current.get("items", []) if x.get("confirmed"))
    return {
        "documentKey": document_key,
        "label": doc.get("label"),
        "template": doc.get("template"),
        "analysisReady": bool(analysis),
        "fields": fields,
        "sourceCatalog": SOURCE_CATALOG,
        "suggestions": suggestions,
        "mapping": current,
        "progress": {
            "total": len(fields),
            "saved": len(current.get("items", [])),
            "confirmed": confirmed,
        },
    }


def suggest_anchors(fields: list[dict[str, str]], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    snippets = _analysis_snippets(analysis)
    catalog = {x["source"]: x for x in SOURCE_CATALOG}
    output = []
    for field in fields:
        source = field.get("source") or ""
        meta = catalog.get(source, {"label": source, "keywords": []})
        candidates = []
        for snippet in snippets:
            text = str(snippet.get("text") or "").strip()
            if not text:
                continue
            score = 0
            for kw in meta.get("keywords", []):
                if kw and kw in text:
                    score = max(score, 100 if text == kw else 80)
            if meta.get("label") and meta["label"] in text:
                score = max(score, 90)
            if score:
                candidates.append({
                    "text": text,
                    "xmlFile": snippet.get("file") or "",
                    "score": score,
                })
        candidates.sort(key=lambda x: (-x["score"], len(x["text"])))
        output.append({
            "token": field.get("token"),
            "source": source,
            "label": meta.get("label", source),
            "candidates": candidates[:5],
        })
    return output
