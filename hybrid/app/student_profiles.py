from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "cb-atoz-2026-v0.10"

ROLE_LABELS = {
    "victim": "피해관련",
    "perp": "가해관련",
}

FORM10_REQUIRED = [
    ("schoolName", "소속학교"),
    ("grade", "학년"),
    ("classNo", "반"),
    ("number", "번호"),
    ("gender", "성별"),
    ("guardianNoticeAt", "보호자 통보일시"),
    ("guardianNoticeMethod", "보호자 통보방법"),
]

CONSENT_REQUIRED = [
    ("schoolName", "소속학교"),
    ("grade", "학년"),
    ("classNo", "반"),
    ("name", "학생성명"),
    ("guardianName", "보호자성명"),
]


def student_profiles(case: dict[str, Any]) -> list[dict[str, Any]]:
    hybrid = case.get("_hybrid") or {}
    profiles = hybrid.get("studentProfiles") or []
    if not isinstance(profiles, list):
        return []
    return [p for p in profiles if isinstance(p, dict)]


def profiles_by_role(case: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [p for p in student_profiles(case) if str(p.get("role") or "") == role]


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _profile_label(profile: dict[str, Any], index: int) -> str:
    role = ROLE_LABELS.get(str(profile.get("role") or ""), "관련")
    name = str(profile.get("name") or "").strip() or f"학생 {index + 1}"
    return f"{role} {name}"


def profile_readiness(case: dict[str, Any], required: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    required = required or FORM10_REQUIRED
    profiles = student_profiles(case)
    if not profiles:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "total": 0,
            "complete": 0,
            "score": 0,
            "ready": False,
            "missing": [{"profile": "관련학생", "fields": ["관련학생 상세정보 미등록"]}],
        }

    missing: list[dict[str, Any]] = []
    complete = 0
    required_count = max(1, len(required) * len(profiles))
    filled_count = 0

    for idx, profile in enumerate(profiles):
        fields = []
        for key, label in required:
            if _blank(profile.get(key)):
                fields.append(label)
            else:
                filled_count += 1
        if fields:
            missing.append({"profile": _profile_label(profile, idx), "fields": fields})
        else:
            complete += 1

    score = round(filled_count / required_count * 100)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "total": len(profiles),
        "complete": complete,
        "score": score,
        "ready": complete == len(profiles),
        "missing": missing,
    }


def consent_readiness(case: dict[str, Any]) -> dict[str, Any]:
    return profile_readiness(case, required=CONSENT_REQUIRED)


def _student_number(profile: dict[str, Any]) -> str:
    grade = str(profile.get("grade") or "").strip()
    class_no = str(profile.get("classNo") or "").strip()
    number = str(profile.get("number") or "").strip()
    if grade and class_no and number:
        return f"{grade}-{class_no}-{number}"
    return "-".join(x for x in (grade, class_no, number) if x)


def _yes_no(value: Any) -> str:
    return "O" if bool(value) else ""


def form10_rows(case: dict[str, Any]) -> str:
    rows = []
    for profile in student_profiles(case):
        flags = []
        for key, label in [
            ("athlete", "학생선수"),
            ("disabled", "장애학생"),
            ("specialEducation", "특수교육대상자"),
            ("multicultural", "다문화학생"),
            ("northKoreanDefector", "탈북학생"),
        ]:
            if profile.get(key):
                flags.append(label)
        notice = " ".join(
            x for x in [str(profile.get("guardianNoticeAt") or "").strip(), str(profile.get("guardianNoticeMethod") or "").strip()]
            if x
        )
        rows.append(" | ".join([
            ROLE_LABELS.get(str(profile.get("role") or ""), "관련"),
            str(profile.get("schoolName") or ""),
            _student_number(profile),
            str(profile.get("name") or ""),
            str(profile.get("gender") or ""),
            notice,
            ", ".join(flags),
        ]))
    return "\n".join(rows)


def form12_rows(case: dict[str, Any]) -> str:
    rows = []
    for profile in student_profiles(case):
        rows.append(" | ".join([
            str(profile.get("schoolName") or ""),
            _student_number(profile),
            str(profile.get("name") or ""),
            str(profile.get("gender") or ""),
            str(profile.get("relatedSchoolCaseNo") or ""),
            _yes_no(profile.get("athlete")) if profile.get("role") == "perp" else "",
            ROLE_LABELS.get(str(profile.get("role") or ""), "관련"),
        ]))
    return "\n".join(rows)


def consent_rows(case: dict[str, Any], role: str | None = None) -> str:
    profiles = student_profiles(case)
    if role:
        profiles = [p for p in profiles if p.get("role") == role]
    rows = []
    for profile in profiles:
        grade_class = "-".join(
            x for x in [str(profile.get("grade") or "").strip(), str(profile.get("classNo") or "").strip()] if x
        )
        rows.append(" | ".join([
            str(profile.get("schoolName") or ""),
            grade_class,
            str(profile.get("name") or ""),
            str(profile.get("guardianName") or ""),
        ]))
    return "\n".join(rows)


def document_context(case: dict[str, Any]) -> dict[str, str]:
    victims = profiles_by_role(case, "victim")
    perps = profiles_by_role(case, "perp")
    return {
        "students.all.form10Rows": form10_rows(case),
        "students.all.form12Rows": form12_rows(case),
        "students.all.consentRows": consent_rows(case),
        "students.victims.consentRows": consent_rows(case, "victim"),
        "students.perps.consentRows": consent_rows(case, "perp"),
        "students.victims.names": ", ".join(str(x.get("name") or "").strip() for x in victims if str(x.get("name") or "").strip()),
        "students.perps.names": ", ".join(str(x.get("name") or "").strip() for x in perps if str(x.get("name") or "").strip()),
    }
