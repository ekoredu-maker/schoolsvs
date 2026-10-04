from __future__ import annotations

from pathlib import Path
from typing import Any

from hwpx_engine import TEMPLATE_DIR, load_registry
from student_profiles import profile_readiness
from workflow import atoz_form10_readiness


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _named(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    return any(str((item or {}).get("name") or "").strip() for item in items if isinstance(item, dict))


def _section(key: str, label: str, missing: list[str], total: int) -> dict[str, Any]:
    missing_count = len(missing)
    completed = max(0, total - missing_count)
    score = round(completed / total * 100) if total else 100
    return {
        "key": key,
        "label": label,
        "ready": not missing,
        "score": score,
        "missing": missing,
    }


def _basic_section(case: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    fields = [
        (case.get("caseNo"), "사안번호"),
        (case.get("school") or settings.get("school"), "학교명"),
        (case.get("recvAt"), "접수일시"),
        (case.get("incidentDate"), "발생일"),
        (case.get("incidentPlace"), "발생장소"),
        (case.get("violenceType"), "학교폭력 유형"),
        (case.get("summary"), "사안 개요"),
    ]
    for value, label in fields:
        if _blank(value):
            missing.append(label)
    if not _named(case.get("victims") or []):
        missing.append("피해관련학생")
    if not _named(case.get("perps") or []):
        missing.append("가해관련학생")
    return _section("basic", "기본정보", missing, 9)


def _initial_section(case: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    sep = str(case.get("separation") or "")
    if not sep:
        missing.append("즉시분리 여부·방법")
    elif sep == "즉시분리 시행":
        if _blank(case.get("sepPeriod")):
            missing.append("분리기간")
        if _blank(case.get("separationPlace")):
            missing.append("분리장소")
    elif sep == "즉시분리 미시행" and _blank(case.get("sepReason")):
        missing.append("분리 미시행 사유")

    office = str(case.get("officeReport") or "")
    if not office:
        missing.append("교육(지원)청 보고 여부")
    elif office == "보고완료" and _blank(case.get("officeDate")):
        missing.append("교육(지원)청 보고일")

    # 분리 3요소 + 보고 2요소를 기준으로 단순 준비도를 산정한다.
    return _section("initial", "초기대응", missing, 5)


def _atoz_section(case: dict[str, Any]) -> dict[str, Any]:
    result = atoz_form10_readiness(case)
    return {
        "key": "atoz",
        "label": "A to Z 추가정보",
        "ready": bool(result.get("ready")),
        "score": int(result.get("score") or 0),
        "missing": [str(x.get("label") or x.get("field") or "") for x in result.get("missing") or []],
        "recommended": [str(x.get("label") or x.get("field") or "") for x in result.get("recommended") or []],
    }


def _student_section(case: dict[str, Any]) -> dict[str, Any]:
    result = profile_readiness(case)
    missing: list[str] = []
    for item in result.get("missing") or []:
        profile = str(item.get("profile") or "관련학생")
        fields = ", ".join(str(x) for x in item.get("fields") or [])
        missing.append(f"{profile}: {fields}" if fields else profile)
    return {
        "key": "students",
        "label": "관련학생 상세",
        "ready": bool(result.get("ready")),
        "score": int(result.get("score") or 0),
        "missing": missing,
        "total": result.get("total", 0),
        "complete": result.get("complete", 0),
    }


def _template_state(document_key: str) -> dict[str, Any]:
    registry = load_registry()
    doc = (registry.get("documents") or {}).get(document_key) or {}
    template_name = str(doc.get("template") or "")
    template_path = TEMPLATE_DIR / template_name if template_name else None
    template_ready = bool(template_path and template_path.exists())
    mapping_ready = bool(doc.get("fields"))
    return {
        "templateReady": template_ready,
        "mappingReady": mapping_ready,
        "template": template_name,
    }


def form10_readiness(case: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or {}
    sections = [
        _basic_section(case, settings),
        _initial_section(case),
        _student_section(case),
        _atoz_section(case),
    ]
    template = _template_state("form10_case_report")
    content_ready = all(bool(x.get("ready")) for x in sections)
    score = round(sum(int(x.get("score") or 0) for x in sections) / len(sections)) if sections else 100
    blocking = []
    for section in sections:
        for item in section.get("missing") or []:
            blocking.append(f"{section['label']}: {item}")
    if not template["templateReady"]:
        blocking.append("공식 서식10 HWPX 템플릿 미등록")
    if not template["mappingReady"]:
        blocking.append("서식10 필드 매핑 미등록")
    return {
        "documentKey": "form10_case_report",
        "label": "[서식10] 학교폭력 사안접수 보고서",
        "contentReady": content_ready,
        "ready": content_ready and template["templateReady"] and template["mappingReady"],
        "score": score,
        "sections": sections,
        "blocking": blocking,
        **template,
    }


def document_readiness(document_key: str, case: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    if document_key == "form10_case_report":
        return form10_readiness(case, settings=settings)
    template = _template_state(document_key)
    return {
        "documentKey": document_key,
        "contentReady": True,
        "ready": template["templateReady"] and template["mappingReady"],
        "score": 100,
        "sections": [],
        "blocking": [] if template["templateReady"] and template["mappingReady"] else ["템플릿 또는 필드 매핑을 확인하세요."],
        **template,
    }
