from __future__ import annotations

import copy
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
T = f"{{{HP}}}t"
TBL = f"{{{HP}}}tbl"
TR = f"{{{HP}}}tr"
TC = f"{{{HP}}}tc"
ADDR = f"{{{HP}}}cellAddr"
SPAN = f"{{{HP}}}cellSpan"
RUN = f"{{{HP}}}run"
FORM10 = "form10_case_report"
FORM12 = "form12_investigation_report"


@dataclass
class DirectDocumentResult:
    document_key: str
    output_path: Path
    replaced_tokens: list[str]
    missing_tokens: list[str]
    direct_fields: list[str]


def _text_nodes(node: ET.Element) -> list[ET.Element]:
    return list(node.iter(T))


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join(" ".join((x.text or "").split()) for x in _text_nodes(node) if (x.text or "").strip()).strip()


def _rows(table: ET.Element) -> list[ET.Element]:
    return [x for x in list(table) if x.tag == TR]


def _cells(row: ET.Element) -> list[ET.Element]:
    return [x for x in list(row) if x.tag == TC]


def _cell(row: ET.Element, col: int) -> ET.Element | None:
    for cell in _cells(row):
        addr = cell.find(ADDR)
        if addr is not None and int(addr.get("colAddr") or -1) == col:
            return cell
    return None


def _set(cell: ET.Element | None, value: Any) -> None:
    if cell is None:
        raise ValueError("HWPX 값 셀을 찾지 못했습니다.")
    nodes = _text_nodes(cell)
    if not nodes:
        run = next(cell.iter(RUN), None)
        if run is None:
            raise ValueError("HWPX 값 셀에 run 노드가 없습니다.")
        nodes = [ET.SubElement(run, T)]
    nodes[0].text = "" if value is None else str(value)
    for node in nodes[1:]:
        node.text = ""


def _date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return f"{dt.year}. {dt.month:02d}. {dt.day:02d}."
    except ValueError:
        match = re.match(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text)
        if not match:
            return text
        y, m, d = match.groups()
        return f"{int(y)}. {int(m):02d}. {int(d):02d}."


def _datetime(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        weekdays = "월화수목금토일"
        return f"{dt.year}. {dt.month:02d}. {dt.day:02d}.({weekdays[dt.weekday()]}) {dt.hour:02d}:{dt.minute:02d}"
    except ValueError:
        return text


def _hybrid(case: dict[str, Any], key: str) -> dict[str, Any]:
    value = ((case.get("_hybrid") or {}).get(key) or {})
    return value if isinstance(value, dict) else {}


def _profiles(case: dict[str, Any]) -> list[dict[str, Any]]:
    value = ((case.get("_hybrid") or {}).get("studentProfiles") or [])
    if isinstance(value, list) and value:
        return [x for x in value if isinstance(x, dict)]
    out: list[dict[str, Any]] = []
    for role, key in (("victim", "victims"), ("perp", "perps")):
        for index, item in enumerate(case.get(key) or []):
            if not isinstance(item, dict):
                continue
            out.append({
                "profileId": f"{role}-{index}", "role": role, "name": item.get("name"),
                "schoolName": case.get("school"), "grade": item.get("grade"),
                "classNo": item.get("classNum"), "number": item.get("studentNum"),
                "gender": item.get("gender"), "athlete": str(item.get("athlete") or "") == "V",
            })
    return out


def _main_table(root: ET.Element, key: str) -> ET.Element:
    for table in root.iter(TBL):
        value = _text(table)
        if key == FORM10 and table.get("rowCnt") == "22" and table.get("colCnt") == "15":
            if all(x in value for x in ("학교명", "접수일시", "관계회복 프로그램 관련 학생 의견")):
                return table
        if key == FORM12 and table.get("rowCnt") == "38" and table.get("colCnt") == "14":
            if all(x in value for x in ("신고접수 일자", "시행령 제19조 판단요소", "특이사항 및 고려사항")):
                return table
    raise ValueError("확인된 2026 공식 HWPX 본문 구조를 찾지 못했습니다.")


def is_official_2026_template(key: str, path: Path) -> bool:
    if key not in {FORM10, FORM12} or not path.exists() or not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path, "r") as archive:
            for name in sorted(archive.namelist()):
                if not re.fullmatch(r"Contents/section\d+\.xml", name):
                    continue
                try:
                    root = ET.fromstring(archive.read(name))
                    table = _main_table(root, key)
                except (ET.ParseError, ValueError):
                    continue
                value = _text(table)
                if key == FORM10:
                    return all(x in value for x in ("교감", "관계회복 프로그램 안내여부", "아동학대"))
                return all(x in value for x in ("이주배경학생", "학교폭력의 심각성", "가해학생 학교폭력 재발 현황"))
    except Exception:
        return False
    return False


def _transform(path: Path, key: str, transform: Callable[[ET.Element], list[str]]) -> list[str]:
    with zipfile.ZipFile(path, "r") as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]
    found = False
    fields: list[str] = []
    output_entries = []
    for info, data in entries:
        if not found and re.fullmatch(r"Contents/section\d+\.xml", info.filename):
            try:
                root = ET.fromstring(data)
                _main_table(root, key)
            except (ET.ParseError, ValueError):
                pass
            else:
                fields = transform(root)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                found = True
        output_entries.append((info, data))
    if not found:
        raise ValueError("2026 공식 HWPX 본문을 갱신하지 못했습니다.")
    temp = path.with_suffix(path.suffix + ".direct.tmp")
    try:
        with zipfile.ZipFile(temp, "w") as output:
            for info, data in output_entries:
                output.writestr(info.filename, data, compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return fields


def _fill_form10(root: ET.Element, case: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    table = _main_table(root, FORM10)
    rows = _rows(table)
    atoz = _hybrid(case, "atoz")
    school = str(case.get("school") or settings.get("school") or "")
    teacher = str(case.get("teacher") or settings.get("teacher") or "")
    _set(_cell(rows[0], 0), f"* 사안번호: {case.get('caseNo') or ''}")
    _set(_cell(rows[1], 1), school)
    _set(_cell(rows[1], 8), settings.get("vicePrincipal") or "")
    _set(_cell(rows[1], 14), teacher)
    _set(_cell(rows[2], 8), settings.get("viceMobile") or "")
    _set(_cell(rows[2], 14), settings.get("teacherMobile") or "")
    _set(_cell(rows[3], 1), _datetime(case.get("recvAt")))
    reporter = " / ".join(x for x in (str(atoz.get("reporterName") or "").strip(), str(atoz.get("reporterRole") or "").strip()) if x)
    _set(_cell(rows[4], 1), reporter or case.get("reporter") or "")
    _set(_cell(rows[4], 11), atoz.get("recognitionPath") or case.get("reportType") or "")
    receiver = " / ".join(x for x in (str(atoz.get("receiverName") or teacher).strip(), str(atoz.get("receiverRole") or settings.get("position") or "").strip()) if x)
    _set(_cell(rows[5], 1), receiver)
    nested = [x for x in root.iter(TBL) if x is not table and x.get("rowCnt") == "5" and x.get("colCnt") == "2" and "관련학생" in _text(x) and "유형" in _text(x)]
    if nested:
        nrows = _rows(nested[0])
        _set(_cell(nrows[1], 1), _datetime(case.get("incidentDate")) or _date(case.get("incidentDate")))
        _set(_cell(nrows[2], 1), case.get("incidentPlace") or "")
        _set(_cell(nrows[3], 1), case.get("summary") or "")
    return ["caseNo", "school", "vicePrincipal", "teacher", "recvAt", "reporter", "recognitionPath", "receiver", "incidentDate", "incidentPlace", "summary"]


def _shift_rows(rows: list[ET.Element], start: int, delta: int) -> None:
    for row in rows:
        for cell in _cells(row):
            addr = cell.find(ADDR)
            if addr is not None and int(addr.get("rowAddr") or 0) >= start:
                addr.set("rowAddr", str(int(addr.get("rowAddr") or 0) + delta))


def _student_rows(table: ET.Element, count: int) -> list[ET.Element]:
    rows = _rows(table)
    data = [r for r in rows if any(c.find(ADDR) is not None and int(c.find(ADDR).get("rowAddr") or -1) in (5, 6) for c in _cells(r))]
    if count <= 2:
        return data[:2]
    extra = count - 2
    template = data[-1]
    note = next(r for r in rows if any(c.find(ADDR) is not None and int(c.find(ADDR).get("rowAddr") or -1) == 7 for c in _cells(r)))
    _shift_rows(rows, 7, extra)
    header = _cell(rows[4], 0)
    if header is not None:
        span = header.find(SPAN)
        if span is not None:
            span.set("rowSpan", str(int(span.get("rowSpan") or 4) + extra))
    insert_at = list(table).index(note)
    result = list(data[:2])
    for index in range(extra):
        clone = copy.deepcopy(template)
        for cell in _cells(clone):
            addr = cell.find(ADDR)
            if addr is not None:
                addr.set("rowAddr", str(7 + index))
            _set(cell, "")
        table.insert(insert_at + index, clone)
        result.append(clone)
    table.set("rowCnt", str(int(table.get("rowCnt") or 38) + extra))
    return result


def _role_note(profile: dict[str, Any]) -> str:
    marks = [
        (profile.get("role") == "perp", "가해관련"), (profile.get("role") == "victim", "피해관련"),
        (bool(profile.get("disabled")), "장애학생"), (bool(profile.get("specialEducation")), "특수교육대상자"),
        (bool(profile.get("multicultural")), "이주배경학생"), (bool(profile.get("northKoreanDefector")), "탈북학생"),
    ]
    return " ".join(("■" if on else "□") + label for on, label in marks)


def _criterion(value: Any) -> str:
    return {"met": "충족", "not_met": "미충족", "checking": "확인 중"}.get(str(value or ""), str(value or ""))


def _fill_form12(root: ET.Element, case: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    table = _main_table(root, FORM12)
    rows = _rows(table)
    inv = _hybrid(case, "investigation")
    atoz = _hybrid(case, "atoz")
    profiles = _profiles(case)
    teacher = str(case.get("teacher") or settings.get("teacher") or "")
    author = str(inv.get("authorName") or case.get("investigatorName") or "")
    _set(_cell(rows[0], 1), _date(case.get("recvAt")))
    _set(_cell(rows[0], 9), " / ".join(x for x in (teacher, str(settings.get("teacherMobile") or "")) if x))
    _set(_cell(rows[1], 1), _date(inv.get("investigationDate") or case.get("investigationDate")))
    _set(_cell(rows[1], 9), " / ".join(x for x in (author, str(inv.get("authorContact") or "")) if x))
    _set(_cell(rows[2], 1), f"유형: {case.get('violenceType') or ''}")
    _set(_cell(rows[3], 1), "1차 조사 ■ / 보완조사 □" if inv.get("kind") == "first" else "1차 조사 □ / 보완조사 ■" if inv.get("kind") == "supplement" else "")
    srows = _student_rows(table, max(2, len(profiles)))
    for index, row in enumerate(srows):
        profile = profiles[index] if index < len(profiles) else {}
        _set(_cell(row, 1), profile.get("schoolName") or case.get("school") or settings.get("school") or "")
        _set(_cell(row, 2), f"{profile.get('grade') or ''}/{profile.get('classNo') or ''}-{profile.get('number') or ''}".strip("/-"))
        _set(_cell(row, 4), profile.get("name") or "")
        _set(_cell(row, 8), profile.get("gender") or "")
        _set(_cell(row, 9), profile.get("relatedSchoolCaseNo") or "")
        _set(_cell(row, 10), "V" if profile.get("athlete") and profile.get("role") == "perp" else "")
        _set(_cell(row, 12), _role_note(profile) if profile else "")
    rowmap: dict[int, ET.Element] = {}
    for row in _rows(table):
        addresses = [int(c.find(ADDR).get("rowAddr") or -1) for c in _cells(row) if c.find(ADDR) is not None]
        if addresses:
            rowmap[min(addresses)] = row
    shift = max(0, len(profiles) - 2)
    rr = lambda original: rowmap[original + shift]
    _set(_cell(rr(8), 1), case.get("summary") or "")
    _set(_cell(rr(9), 1), inv.get("chronology") or "")
    separation = str(case.get("separation") or "")
    _set(_cell(rr(11), 1), "■" if separation == "즉시분리 시행" else "□")
    _set(_cell(rr(11), 3), "■" if separation == "즉시분리 미시행" else "□")
    _set(_cell(rr(12), 1), f"분리기간: {case.get('sepPeriod') or ''}")
    _set(_cell(rr(12), 3), "√" if separation == "즉시분리 미시행" else "")
    criteria = inv.get("selfResolutionCriteria") or {}
    nested = [x for x in root.iter(TBL) if x is not table and x.get("rowCnt") == "5" and x.get("colCnt") == "2" and "학교장 자체해결 요건" in _text(x)]
    if nested:
        nrows = _rows(nested[0])
        for index, key in enumerate(("noLongTreatment", "noPropertyDamage", "notPersistent", "notRetaliation"), 1):
            _set(_cell(nrows[index], 1), _criterion(criteria.get(key)))
    _set(_cell(rr(14), 13), inv.get("selfResolutionConsent") or "")
    issues = inv.get("issues") if isinstance(inv.get("issues"), list) else []
    if issues and isinstance(issues[0], dict):
        issue = issues[0]
        _set(_cell(rr(15), 1), f"주요 쟁점 1. {issue.get('title') or ''}")
        _set(_cell(rr(15), 2), issue.get("summary") or issue.get("title") or "")
        _set(_cell(rr(15), 11), issue.get("evidence") or "")
        _set(_cell(rr(16), 2), issue.get("victimClaim") or "")
        _set(_cell(rr(17), 2), issue.get("perpClaim") or "")
        _set(_cell(rr(18), 2), issue.get("witnessStatement") or "")
    factors = inv.get("judgmentFactors") or {}
    for key, original in {"severity":22, "persistence":23, "intentionality":24, "remorse":25, "reconciliation":26, "guidancePossibility":29, "victimDisability":30}.items():
        _set(_cell(rr(original), 1), factors.get(key) or "")
    _set(_cell(rr(27), 1), atoz.get("victimRecoveryOpinion") or "")
    _set(_cell(rr(28), 1), atoz.get("perpRecoveryOpinion") or "")
    emergency = inv.get("emergencyMeasures") or ""
    _set(_cell(rr(31), 2), emergency)
    _set(_cell(rr(32), 2), emergency)
    _set(_cell(rr(33), 1), inv.get("recurrenceHistory") or "")
    _set(_cell(rr(37), 1), inv.get("specialNotes") or "")
    others = [x for x in root.iter(TBL) if x is not table and x.get("rowCnt") == "2" and x.get("colCnt") == "3" and "기타 사항" in _text(x)]
    if others:
        _set(_cell(_rows(others[0])[1], 1), inv.get("otherNotes") or "")
    return ["recvAt", "teacher", "investigationDate", "author", "violenceType", "investigationKind", "studentProfiles", "summary", "chronology", "separation", "selfResolutionCriteria", "issues", "judgmentFactors", "emergencyMeasures", "recurrenceHistory", "specialNotes"]


def generate_official_2026(key: str, template_path: Path, case: dict[str, Any], settings: dict[str, Any], output_path: Path) -> DirectDocumentResult:
    if key not in {FORM10, FORM12}:
        raise ValueError("직접 생성은 서식10·서식12만 지원합니다.")
    if not is_official_2026_template(key, template_path):
        raise ValueError("등록된 HWPX가 확인된 2026 공식 구조와 일치하지 않습니다.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, output_path)
    fields = _transform(output_path, key, lambda root: _fill_form10(root, case, settings) if key == FORM10 else _fill_form12(root, case, settings))
    return DirectDocumentResult(key, output_path, [], [], fields)
