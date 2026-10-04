from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

RULES_PATH = Path(__file__).with_name("rules_2026.json")
STATUS_TO_STAGE = {
    "접수중": "접수",
    "분리조치": "초기대응",
    "조사중": "사실조사",
    "심의중": "심의",
    "조치완료": "조치이행",
    "종결": "종결",
}


def load_rules() -> dict[str, Any]:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _has_named_person(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    return any(str((item or {}).get("name") or "").strip() for item in items if isinstance(item, dict))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _deadline_state(data: dict[str, Any], rule: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    base = _parse_dt(data.get(rule.get("base_field")))
    result: dict[str, Any] = {
        "label": rule.get("label", "기한"),
        "verified": bool(rule.get("verified")),
        "source": rule.get("source", ""),
        "status": "not_applicable",
        "dueAt": None,
        "remainingMinutes": None,
        "overdue": False,
    }
    if not base:
        result["status"] = "base_missing"
        return result

    due = base + timedelta(hours=int(rule.get("hours") or 0))
    result["dueAt"] = due.isoformat(timespec="minutes")

    completion_field = rule.get("completion_field")
    completion_status_field = rule.get("completion_status_field")
    completion_status_value = rule.get("completion_status_value")
    completed = False
    if completion_status_field and completion_status_value:
        completed = data.get(completion_status_field) == completion_status_value
    if completion_field and data.get(completion_field):
        completed = completed or bool(data.get(completion_field))
    if completed:
        result["status"] = "completed"
        return result

    current = now or datetime.now(base.tzinfo)
    remaining = int((due - current).total_seconds() // 60)
    result["remainingMinutes"] = remaining
    result["overdue"] = remaining < 0
    result["status"] = "overdue" if remaining < 0 else "pending"
    return result


def calculate_deadlines(data: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    rules = load_rules()
    items = []
    for key, rule in (rules.get("deadlines") or {}).items():
        state = _deadline_state(data, rule, now=now)
        state["key"] = key
        items.append(state)
    return items


def validate_case(data: dict[str, Any]) -> dict[str, Any]:
    rules = load_rules()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def required(key: str, label: str) -> None:
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append({"field": key, "message": f"{label}이(가) 없습니다."})

    labels = {
        "id": "사안 식별값",
        "caseNo": "사안번호",
        "status": "처리상태",
        "recvAt": "접수 일시",
        "incidentDate": "사건 발생일",
        "incidentPlace": "사건 발생 장소",
        "reportType": "신고 유형",
        "violenceType": "폭력 유형",
        "summary": "사안 개요",
    }
    for key in (rules.get("required_fields") or {}).get("base", []):
        required(key, labels.get(key, key))

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

    max_days = int((((rules.get("limits") or {}).get("separation_max_days") or {}).get("value") or 7))
    sep_period = str(data.get("sepPeriod") or "")
    if sep_period.endswith("일"):
        try:
            days = int(sep_period[:-1])
            if days > max_days:
                errors.append({"field": "sepPeriod", "message": f"분리기간은 현재 공통 기준상 최대 {max_days}일을 초과할 수 없습니다."})
        except ValueError:
            pass

    if data.get("useInvestigator") and not data.get("investigationDate"):
        warnings.append({"field": "investigationDate", "message": "조사관 지정 상태이나 조사 예정일이 비어 있습니다."})

    if data.get("status") == "종결" and not (data.get("closedDate") or data.get("closed_date")):
        errors.append({"field": "closedDate", "message": "종결 사안은 최종 종결일이 필요합니다."})

    if (data.get("actionCode") or data.get("actionContent")) and not data.get("actionDate"):
        errors.append({"field": "actionDate", "message": "조치내용이 있으면 조치 결정일이 필요합니다."})

    deadlines = calculate_deadlines(data)
    for item in deadlines:
        if item["status"] == "overdue":
            warnings.append({"field": item["key"], "message": f"{item['label']} 기한이 경과했습니다."})

    score = max(0, 100 - len(errors) * 12 - len(warnings) * 4)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "score": score,
        "deadlines": deadlines,
        "rulesVersion": rules.get("version"),
        "localRulesStatus": (rules.get("local_rules") or {}).get("status"),
    }


def workflow_state(data: dict[str, Any]) -> dict[str, Any]:
    rules = load_rules()
    stages = rules.get("workflow") or ["접수", "초기대응", "사실조사", "전담기구", "심의", "조치이행", "종결"]
    current = STATUS_TO_STAGE.get(str(data.get("status") or ""), "접수")
    current_idx = stages.index(current) if current in stages else 0
    steps = []
    for i, name in enumerate(stages):
        if i < current_idx:
            state = "done"
        elif i == current_idx:
            state = "current"
        else:
            state = "pending"
        steps.append({"name": name, "state": state})

    validation = validate_case(data)
    deadlines = validation.get("deadlines") or []
    next_actions: list[str] = []

    overdue = [x for x in deadlines if x.get("status") == "overdue"]
    pending = [x for x in deadlines if x.get("status") == "pending"]
    if overdue:
        for item in overdue:
            next_actions.append(f"기한 경과: {item['label']}을 즉시 확인하세요.")
    if validation["errors"]:
        next_actions.append("필수 입력 오류를 먼저 수정하세요.")
    if current in ("접수", "초기대응"):
        if not data.get("separation"):
            next_actions.append("피·가해 관련학생 분리 여부와 방법을 확인하세요.")
        if data.get("officeReport") != "보고완료":
            next_actions.append("교육(지원)청 사안접수 보고 상태를 확인하세요.")
    if current == "사실조사" and data.get("useInvestigator") and not data.get("investigationDate"):
        next_actions.append("전담조사관 조사 일정을 입력하세요.")
    if current in ("심의", "조치이행") and not data.get("actionDate"):
        next_actions.append("심의 결과 또는 조치 결정일 입력 여부를 확인하세요.")
    if pending and not next_actions:
        next_actions.append("현재 진행 중인 기한을 확인하며 다음 절차를 진행하세요.")
    if not next_actions:
        next_actions.append("현재 단계의 필수 기록이 확인되었습니다. 다음 절차로 진행할 수 있습니다.")

    completed_steps = sum(1 for step in steps if step["state"] == "done")
    stage_progress = round((completed_steps / max(1, len(stages) - 1)) * 100)
    completion = round(stage_progress * 0.55 + validation["score"] * 0.45)

    return {
        "stage": current,
        "currentStage": current,
        "steps": steps,
        "validation": validation,
        "deadlines": deadlines,
        "nextActions": next_actions,
        "completion": completion,
        "rulesVersion": rules.get("version"),
        "localRulesStatus": (rules.get("local_rules") or {}).get("status"),
    }
