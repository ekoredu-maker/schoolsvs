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

    victims = data.get("victims") or data.get("victimStudents") or []
    perps = data.get("perps") or data.get("perpStudents") or data.get("offenders") or []
    if not victims:
        warnings.append({"field": "victims", "message": "피해관련학생 정보가 비어 있습니다."})
    if not perps:
        warnings.append({"field": "perps", "message": "가해관련학생 정보가 비어 있습니다."})

    if data.get("status") == "종결" and not (data.get("closedDate") or data.get("closed_date")):
        errors.append({"field": "closedDate", "message": "종결 사안은 최종 종결일이 필요합니다."})

    if (data.get("actionCode") or data.get("actionContent")) and not data.get("actionDate"):
        errors.append({"field": "actionDate", "message": "조치내용이 있으면 조치 결정일이 필요합니다."})

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "score": max(0, 100 - len(errors) * 15 - len(warnings) * 5),
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

    return {
        "currentStage": current,
        "steps": steps,
        "validation": validation,
        "nextActions": next_actions,
    }
