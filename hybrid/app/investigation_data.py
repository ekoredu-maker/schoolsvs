from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "cb-atoz-2026-form12-v0.19"

CRITERIA = [
    ("noLongTreatment", "2주 이상 치료 필요 진단서가 제출되지 않은 경우"),
    ("noPropertyDamage", "재산상 피해가 없거나 즉시 복구·복구 약속이 있는 경우"),
    ("notPersistent", "학교폭력이 지속적이지 않은 경우"),
    ("notRetaliation", "신고·진술·자료제공 등에 대한 보복행위가 아닌 경우"),
]

JUDGMENT_FACTORS = [
    ("severity", "학교폭력의 심각성"),
    ("persistence", "학교폭력의 지속성"),
    ("intentionality", "학교폭력의 고의성"),
    ("remorse", "가해학생의 반성 정도"),
    ("reconciliation", "가해학생·보호자와 피해학생·보호자 간 화해 정도"),
    ("guidancePossibility", "해당 조치로 인한 가해학생의 선도 가능성"),
    ("victimDisability", "피해학생이 장애학생인지 여부"),
]


def investigation_data(case: dict[str, Any]) -> dict[str, Any]:
    hybrid = case.get("_hybrid") or {}
    data = hybrid.get("investigation") or {}
    return data if isinstance(data, dict) else {}


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def readiness(case: dict[str, Any]) -> dict[str, Any]:
    data = investigation_data(case)
    missing: list[str] = []
    recommended: list[str] = []

    kind = str(data.get("kind") or "").strip()
    if kind not in {"first", "supplement"}:
        missing.append("조사구분(1차 조사/보완조사)")

    investigation_date = data.get("investigationDate") or case.get("investigationDate")
    if _blank(investigation_date):
        missing.append("사안조사 일자")

    author = data.get("authorName") or case.get("investigatorName")
    if _blank(author):
        missing.append("조사 작성자 성명")

    if _blank(data.get("chronology")):
        missing.append("사안 경위(시간 흐름에 따른 세부내용)")

    criteria = data.get("selfResolutionCriteria") or {}
    if not isinstance(criteria, dict):
        criteria = {}
    for key, label in CRITERIA:
        value = str(criteria.get(key) or "").strip()
        if value not in {"met", "not_met", "checking"}:
            missing.append(f"자체해결 요건 의견: {label}")

    factors = data.get("judgmentFactors") or {}
    if not isinstance(factors, dict):
        factors = {}
    for key, label in JUDGMENT_FACTORS:
        if _blank(factors.get(key)):
            recommended.append(f"판단요소 확인 사실: {label}")

    issues = data.get("issues") or []
    if not isinstance(issues, list) or not any(isinstance(x, dict) and str(x.get("title") or "").strip() for x in issues):
        recommended.append("주요 쟁점 및 양측 주장·근거자료")

    if _blank(data.get("emergencyMeasures")):
        recommended.append("긴급조치 여부")
    if _blank(data.get("recurrenceHistory")):
        recommended.append("가해학생 학교폭력 재발 현황")
    if _blank(data.get("specialNotes")):
        recommended.append("특이사항 및 고려사항")

    required_total = 4 + len(CRITERIA)
    completed = max(0, required_total - len(missing))
    score = round(completed / required_total * 100) if required_total else 100
    return {
        "schemaVersion": data.get("schemaVersion") or SCHEMA_VERSION,
        "ready": not missing,
        "score": score,
        "missing": missing,
        "recommended": recommended,
        "purpose": "서식12 작성 준비도",
        "notice": "판단요소는 점수나 조치수준을 자동판정하지 않고 확인된 사실만 기록합니다.",
    }


def document_context(case: dict[str, Any]) -> dict[str, str]:
    data = investigation_data(case)
    criteria = data.get("selfResolutionCriteria") or {}
    factors = data.get("judgmentFactors") or {}
    issues = data.get("issues") or []

    def criterion(key: str) -> str:
        value = str(criteria.get(key) or "")
        return {"met": "충족", "not_met": "미충족", "checking": "확인 중"}.get(value, "")

    issue_lines = []
    for idx, item in enumerate(issues if isinstance(issues, list) else [], 1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        parts = [f"주요 쟁점 {idx}. {title}"]
        for key, label in [
            ("victimClaim", "피해(관련)학생 주장"),
            ("perpClaim", "가해(관련)학생 주장"),
            ("witnessStatement", "목격학생 진술"),
            ("evidence", "근거자료"),
        ]:
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(f"{label}: {value}")
        issue_lines.append("\n".join(parts))

    context = {
        "investigation.kind": "1차 조사" if data.get("kind") == "first" else "보완조사" if data.get("kind") == "supplement" else "",
        "investigation.date": str(data.get("investigationDate") or case.get("investigationDate") or ""),
        "investigation.authorName": str(data.get("authorName") or case.get("investigatorName") or ""),
        "investigation.authorContact": str(data.get("authorContact") or ""),
        "investigation.chronology": str(data.get("chronology") or ""),
        "investigation.selfResolutionOpinion": str(data.get("selfResolutionOpinion") or ""),
        "investigation.selfResolutionConsent": str(data.get("selfResolutionConsent") or ""),
        "investigation.criteria.noLongTreatment": criterion("noLongTreatment"),
        "investigation.criteria.noPropertyDamage": criterion("noPropertyDamage"),
        "investigation.criteria.notPersistent": criterion("notPersistent"),
        "investigation.criteria.notRetaliation": criterion("notRetaliation"),
        "investigation.issues": "\n\n".join(issue_lines),
        "investigation.emergencyMeasures": str(data.get("emergencyMeasures") or ""),
        "investigation.recurrenceHistory": str(data.get("recurrenceHistory") or ""),
        "investigation.specialNotes": str(data.get("specialNotes") or ""),
        "investigation.otherNotes": str(data.get("otherNotes") or ""),
    }
    for key, _ in JUDGMENT_FACTORS:
        context[f"investigation.factor.{key}"] = str(factors.get(key) or "")
    return context
