from __future__ import annotations

from typing import Any

STAGES = ["접수", "초기대응", "사실조사", "전담기구", "심의", "조치이행", "종결"]

STATUS_TO_STAGE = {
    "접수중": "접수",
    "분리조치": "초기대응",
    "조사중": "사실조사",
    "심의중": "심의",
    "조치완료": "조치이행",
    "종결": "종결",
}


def _has_named_person(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    return any(str((item or {}).get("name") or "").strip() for item in items if isinstance(item, dict))


def validate_case(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def required(key: str, label: str) -> None:
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append({"field": key, "message": f"{label}이(가) 없습니다."})

    required("id", "사안 식별값")
    required("caseNo", "사안번호")
    required("status", "처리상태")
    required("recvAt", "접수 일시")
    required("incidentDate", "사건 발생일")
    required("incidentPlace", "사건 발생 장소")
    required("reportType", "신고 유형")
    required("violenceType", "폭력 유형")
    required("summary", "사안 개요")

    victims = data.get("victims") or data.get("victimStudents") or []
    perps = data.get("perps") or data.get("perpStudents") or data.get("offenders") or []
    if not _has_named_person(victims):
        errors.append({"field": "victims", "message": "피해관련학생 성명이 1명 이상 필요합니다."})
    if not _has_named_person(perps):
        errors.append({"field": "perps", "message": "가해관련학생 성명이 1명 이상 필요합니다."})

    if data.get("officeReport") == "보고완료" and not data.get("officeDate"):
        errors.append({"field": "officeDate", "message": "교육(지원)청 보고완료 상태에는 보고일이 필요합니다."})

    if data.get("separation") == "즉시분리 시행":
        if not data.get("sepPeriod"):
            errors.append({"field": "sepPeriod", "message": "즉시분리 시행 시 분리기간을 확인하세요."})
        if not data.get("separationPlace"):
            errors.append({"field": "separationPlace", "message": "즉시분리 시행 시 분리장소를 확인하세요."})
    if data.get("separation") == "즉시분리 미시행" and not data.get("sepReason"):
        errors.append({"field": "sepReason", "message": "즉시분리 미시행 사유가 필요합니다."})

    if data.get("useInvestigator") and not data.get("investigationDate"):
        warnings.append({"field": "investigationDate", "message": "조사관 지정 상태이나 조사 예정일이 비어 있습니다."})

    if data.get("status") == "종결" and not (data.get("closedDate") or data.get("closed_date")):
        errors.append({"field": "closedDate", "message": "종결 사안은 최종 종결일이 필요합니다."})

    if (data.get("actionCode") or data.get("actionContent")) and not data.get("actionDate"):
        errors.append({"field": "actionDate", "message": "조치내용이 있으면 조치 결정일이 필요합니다."})

    score = max(0, 100 - len(errors) * 12 - len(warnings) * 4)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "score": score,
    }


def workflow_state(data: dict[str, Any]) -> dict[str, Any]:
    current = STATUS_TO_STAGE.get(str(data.get("status") or ""), "접수")
    current_idx = STAGES.index(current)
    steps = []
    for i, name in enumerate(STAGES):
        if i < current_idx:
            state = "done"
        elif i == current_idx:
            state = "current"
        else:
            state = "pending"
        steps.append({"name": name, "state": state})

    validation = validate_case(data)
    next_actions = []
    if validation["errors"]:
        next_actions.append("필수 입력 오류를 먼저 수정하세요.")
    if validation["warnings"]:
        next_actions.append("누락 가능성이 있는 항목을 확인하세요.")
    if not next_actions:
        next_actions.append("현재 단계의 처리기록을 확인한 뒤 다음 단계로 진행할 수 있습니다.")

    completed_steps = sum(1 for step in steps if step["state"] == "done")
    stage_progress = round((completed_steps / max(1, len(STAGES) - 1)) * 100)
    completion = round(stage_progress * 0.55 + validation["score"] * 0.45)

    return {
        "stage": current,
        "currentStage": current,
        "steps": steps,
        "validation": validation,
        "nextActions": next_actions,
        "completion": completion,
    }
