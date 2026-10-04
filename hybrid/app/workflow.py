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
ROUTE_LABELS = {
    "self_resolution_review": "학교장 자체해결 검토",
    "committee_review": "심의위원회 개최 요청 검토",
    "school_close_review": "학교장 종결 검토",
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


def _intake_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = []
    for key, label in [
        ("recvAt", "접수 일시"), ("incidentDate", "사건 발생일"),
        ("incidentPlace", "발생 장소"), ("reportType", "신고 유형"),
        ("violenceType", "폭력 유형"), ("summary", "사안 개요"),
    ]:
        if not str(data.get(key) or "").strip():
            missing.append(label)
    if not _has_named_person(data.get("victims") or []):
        missing.append("피해관련학생")
    if not _has_named_person(data.get("perps") or []):
        missing.append("가해관련학생")
    return not missing, missing


def _initial_response_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = []
    sep = str(data.get("separation") or "")
    if not sep:
        missing.append("분리 여부·방법 결정")
    elif sep == "즉시분리 시행":
        if not data.get("sepPeriod"):
            missing.append("분리기간")
        if not data.get("separationPlace"):
            missing.append("분리장소")
    elif sep == "즉시분리 미시행" and not data.get("sepReason"):
        missing.append("분리 미시행 사유")

    report = str(data.get("officeReport") or "")
    if not report:
        missing.append("교육(지원)청 보고 여부")
    elif report == "보고완료" and not data.get("officeDate"):
        missing.append("교육(지원)청 보고일")
    return not missing, missing


def _investigation_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = []
    if data.get("useInvestigator"):
        if not str(data.get("investigatorName") or "").strip():
            missing.append("전담조사관 성명")
        if not data.get("investigationDate"):
            missing.append("조사 예정일")
    # 조사관 미사용 사안은 자동 완료로 단정하지 않고, 현재 입력구조상 선행조건 없음으로 취급
    return not missing, missing


def _committee_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    if data.get("committeeDate"):
        return True, []
    return False, ["전담기구 개최일"]


def _decision_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    route = str(((data.get("_hybrid") or {}).get("route") or data.get("workflowRoute") or ""))
    if not route:
        return False, ["처리 분기 검토 결과"]
    if route == "committee_review":
        if data.get("actionDate") or data.get("actionCode") or data.get("actionContent"):
            return True, []
        return False, ["심의 결과 또는 조치 결정 기록"]
    # 자체해결/종결은 프로그램이 적법성 자체를 자동 판정하지 않음.
    # 담당자 검토 선택을 단계 진행 신호로만 사용한다.
    return True, []


def _implementation_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    if not (data.get("actionCode") or data.get("actionContent")):
        return True, []
    if data.get("completionDate"):
        return True, []
    return False, ["조치 이행완료일"]


def _close_ready(data: dict[str, Any]) -> tuple[bool, list[str]]:
    if data.get("closedDate"):
        return True, []
    return False, ["최종 종결일"]


def stage_gates(data: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        ("접수", _intake_ready),
        ("초기대응", _initial_response_ready),
        ("사실조사", _investigation_ready),
        ("전담기구", _committee_ready),
        ("심의", _decision_ready),
        ("조치이행", _implementation_ready),
        ("종결", _close_ready),
    ]
    gates = []
    prior_done = True
    for stage, fn in checks:
        complete, missing = fn(data)
        if not prior_done:
            state = "locked"
        else:
            state = "done" if complete else "current"
        gates.append({"stage": stage, "complete": complete, "state": state, "missing": missing})
        prior_done = prior_done and complete
    return gates


def route_state(data: dict[str, Any]) -> dict[str, Any]:
    selected = str(((data.get("_hybrid") or {}).get("route") or data.get("workflowRoute") or ""))
    committee_ready, _ = _committee_ready(data)
    enabled = committee_ready
    options = [
        {"key": "self_resolution_review", "label": ROUTE_LABELS["self_resolution_review"]},
        {"key": "committee_review", "label": ROUTE_LABELS["committee_review"]},
        {"key": "school_close_review", "label": ROUTE_LABELS["school_close_review"]},
    ]
    return {
        "enabled": enabled,
        "selected": selected or None,
        "selectedLabel": ROUTE_LABELS.get(selected),
        "options": options,
        "requiresHumanDecision": True,
        "notice": "프로그램은 자체해결·심의·종결의 적법성을 자동 확정하지 않습니다. 전담기구 검토와 담당자 판단 결과를 기록하는 보조 기능입니다.",
    }


def validate_case(data: dict[str, Any]) -> dict[str, Any]:
    rules = load_rules()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def required(key: str, label: str) -> None:
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append({"field": key, "message": f"{label}이(가) 없습니다."})

    labels = {
        "id": "사안 식별값", "caseNo": "사안번호", "status": "처리상태",
        "recvAt": "접수 일시", "incidentDate": "사건 발생일", "incidentPlace": "사건 발생 장소",
        "reportType": "신고 유형", "violenceType": "폭력 유형", "summary": "사안 개요",
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

    gates = stage_gates(data)
    declared = STATUS_TO_STAGE.get(str(data.get("status") or ""), "접수")
    stages = [x["stage"] for x in gates]
    declared_idx = stages.index(declared) if declared in stages else 0
    first_incomplete = next((i for i, g in enumerate(gates) if not g["complete"]), len(gates) - 1)
    if declared_idx > first_incomplete:
        missing = ", ".join(gates[first_incomplete]["missing"]) or "선행업무"
        warnings.append({"field": "status", "message": f"현재 상태값은 선행조건보다 앞서 있습니다. {gates[first_incomplete]['stage']} 단계의 {missing}을 확인하세요."})

    score = max(0, 100 - len(errors) * 12 - len(warnings) * 4)
    return {
        "ok": not errors, "errors": errors, "warnings": warnings, "score": score,
        "deadlines": deadlines, "gates": gates, "rulesVersion": rules.get("version"),
        "localRulesStatus": (rules.get("local_rules") or {}).get("status"),
    }


def workflow_state(data: dict[str, Any]) -> dict[str, Any]:
    rules = load_rules()
    validation = validate_case(data)
    deadlines = validation.get("deadlines") or []
    gates = validation.get("gates") or stage_gates(data)
    route = route_state(data)

    first_incomplete = next((g for g in gates if not g["complete"]), gates[-1])
    process_stage = first_incomplete["stage"]
    declared_stage = STATUS_TO_STAGE.get(str(data.get("status") or ""), "접수")
    steps = [{"name": g["stage"], "state": g["state"], "complete": g["complete"], "missing": g["missing"]} for g in gates]

    next_actions: list[str] = []
    overdue = [x for x in deadlines if x.get("status") == "overdue"]
    for item in overdue:
        next_actions.append(f"기한 경과: {item['label']}을 즉시 확인하세요.")

    if first_incomplete.get("missing"):
        next_actions.append(f"{process_stage} 단계 확인: {', '.join(first_incomplete['missing'])}")

    if process_stage == "심의" and not route.get("selected"):
        next_actions.append("전담기구 검토 후 처리 분기를 선택하세요. 프로그램은 자체해결 여부를 자동 확정하지 않습니다.")
    elif route.get("selected"):
        next_actions.append(f"선택한 처리 분기: {route.get('selectedLabel')}")

    if not next_actions:
        next_actions.append("현재 단계의 확인사항이 완료되었습니다. 다음 절차를 진행할 수 있습니다.")

    done_count = sum(1 for g in gates if g["complete"])
    completion = round((done_count / len(gates)) * 70 + validation["score"] * 0.30)

    return {
        "stage": process_stage,
        "currentStage": process_stage,
        "declaredStage": declared_stage,
        "steps": steps,
        "gates": gates,
        "route": route,
        "validation": validation,
        "deadlines": deadlines,
        "nextActions": next_actions,
        "completion": completion,
        "transitionReady": bool(first_incomplete.get("complete")),
        "rulesVersion": rules.get("version"),
        "localRulesStatus": (rules.get("local_rules") or {}).get("status"),
    }
