from __future__ import annotations

import copy
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _local(tag: str) -> str:
    return tag.split('}')[-1]


def _text(elem: ET.Element) -> str:
    parts: list[str] = []
    for node in elem.iter():
        if _local(node.tag) != 't':
            continue
        text = ' '.join(''.join(node.itertext()).split()).strip()
        if text:
            parts.append(text)
    return ' '.join(parts)


def _direct_rows(tbl: ET.Element) -> list[ET.Element]:
    return [child for child in list(tbl) if _local(child.tag) == 'tr']


def _direct_cells(row: ET.Element) -> list[ET.Element]:
    return [child for child in list(row) if _local(child.tag) == 'tc']


def _first_desc(elem: ET.Element, name: str) -> ET.Element | None:
    return next((node for node in elem.iter() if _local(node.tag) == name), None)


def _set_cell_text(cell: ET.Element, value: str) -> None:
    texts = [node for node in cell.iter() if _local(node.tag) == 't']
    if not texts:
        run = next((node for node in cell.iter() if _local(node.tag) == 'run'), None)
        if run is None:
            raise ValueError('학생 행 셀의 실행(run) 노드를 찾을 수 없습니다.')
        namespace = run.tag.split('}')[0].lstrip('{') if '}' in run.tag else ''
        tag = f'{{{namespace}}}t' if namespace else 't'
        texts = [ET.SubElement(run, tag)]
    texts[0].text = value
    for extra in texts[1:]:
        extra.text = ''


def _student_code(profile: dict[str, Any]) -> str:
    explicit = str(profile.get('studentNo') or profile.get('studentNumber') or '').strip()
    if explicit:
        return explicit
    grade = re.sub(r'\D', '', str(profile.get('grade') or ''))
    class_no = re.sub(r'\D', '', str(profile.get('classNo') or ''))
    number = re.sub(r'\D', '', str(profile.get('number') or ''))
    if grade and class_no and number:
        return f'{grade}{class_no.zfill(2)}{number.zfill(2)}'
    return '-'.join(value for value in (grade, class_no, number) if value)


def _notice_text(profile: dict[str, Any]) -> str:
    raw = str(profile.get('guardianNoticeAt') or '').strip()
    method = str(profile.get('guardianNoticeMethod') or '').strip()
    display = raw
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            display = f'{dt.month}. {dt.day}. {dt.hour:02d}:{dt.minute:02d}'
        except ValueError:
            pass
    return f'{display} ({method})'.strip() if method else display


def _guidance_text(profile: dict[str, Any]) -> str:
    value = profile.get('recoveryGuidance')
    if isinstance(value, bool):
        return '○' if value else 'X'
    text = str(value or '').strip().upper()
    if text in {'O', '○', '안내', 'Y', 'YES', 'TRUE', '1'}:
        return '○'
    if text in {'X', '미안내', 'N', 'NO', 'FALSE', '0'}:
        return 'X'
    return text


def _flag_text(profile: dict[str, Any]) -> str:
    role = str(profile.get('role') or '')

    def mark(condition: bool) -> str:
        return '■' if condition else '□'

    return ' '.join([
        f'가해관련{mark(role == "perp")}',
        f'피해관련{mark(role == "victim")}',
        f'학생선수{mark(bool(profile.get("athlete")))}',
        f'장애학생{mark(bool(profile.get("disabled")))}',
        f'특수교육대상자{mark(bool(profile.get("specialEducation")))}',
        f'다문화학생{mark(bool(profile.get("multicultural")))}',
        f'탈북학생{mark(bool(profile.get("northKoreanDefector")))}',
    ])


def _profiles(case: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = ((case.get('_hybrid') or {}).get('studentProfiles') or [])
    if not isinstance(profiles, list):
        return []
    return [
        profile for profile in profiles
        if isinstance(profile, dict) and str(profile.get('name') or '').strip()
    ]


def _reindex_rows(tbl: ET.Element) -> None:
    rows = _direct_rows(tbl)
    tbl.set('rowCnt', str(len(rows)))
    for row_index, row in enumerate(rows):
        for cell in _direct_cells(row):
            addr = _first_desc(cell, 'cellAddr')
            if addr is not None:
                addr.set('rowAddr', str(row_index))


def apply_student_rows_xml(xml_bytes: bytes, case: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    profiles = _profiles(case)
    if not profiles:
        raise ValueError('관련학생 상세정보가 없어 서식10 학생 행을 만들 수 없습니다.')

    target: ET.Element | None = None
    header_index: int | None = None
    end_index: int | None = None

    for table in [node for node in root.iter() if _local(node.tag) == 'tbl']:
        rows = _direct_rows(table)
        for index, row in enumerate(rows):
            text = _text(row)
            if not all(keyword in text for keyword in ['관련학생', '학교명', '학번', '성명', '성별', '보호자']):
                continue
            for next_index in range(index + 1, len(rows)):
                if '기타 사항' in _text(rows[next_index]):
                    target = table
                    header_index = index
                    end_index = next_index
                    break
            if target is not None:
                break
        if target is not None:
            break

    if target is None or header_index is None or end_index is None:
        raise ValueError('서식10 관련학생 표 영역을 찾지 못했습니다.')

    rows = _direct_rows(target)
    sample_rows = rows[header_index + 1:end_index]
    if not sample_rows:
        raise ValueError('서식10 관련학생 예시 행을 찾지 못했습니다.')

    prototype = sample_rows[0]
    if len(_direct_cells(prototype)) < 7:
        raise ValueError('서식10 관련학생 행의 셀 구조가 예상과 다릅니다.')

    for row in sample_rows:
        target.remove(row)

    header_row = rows[header_index]
    header_child_index = list(target).index(header_row)
    insert_at = header_child_index + 1
    created_rows: list[list[str]] = []

    for offset, profile in enumerate(profiles):
        row = copy.deepcopy(prototype)
        cells = _direct_cells(row)
        values = [
            str(profile.get('schoolName') or ''),
            _student_code(profile),
            str(profile.get('name') or ''),
            str(profile.get('gender') or ''),
            _notice_text(profile),
            _guidance_text(profile),
            _flag_text(profile),
        ]
        for cell, value in zip(cells[:7], values):
            _set_cell_text(cell, value)
        target.insert(insert_at + offset, row)
        created_rows.append(values)

    new_rows = _direct_rows(target)
    header_row = new_rows[header_index]
    header_cells = _direct_cells(header_row)
    if header_cells:
        span = _first_desc(header_cells[0], 'cellSpan')
        if span is not None:
            span.set('rowSpan', str(1 + len(profiles)))

    _reindex_rows(target)
    output = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return output, {
        'studentCount': len(profiles),
        'rowCount': int(target.get('rowCnt') or 0),
        'headerRowSpan': 1 + len(profiles),
        'rows': created_rows,
    }


def apply_student_rows_to_hwpx(path: Path, case: dict[str, Any]) -> dict[str, Any]:
    if not zipfile.is_zipfile(path):
        raise ValueError('유효한 HWPX 파일이 아닙니다.')

    with zipfile.ZipFile(path, 'r') as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    target_name: str | None = None
    report: dict[str, Any] | None = None
    updated_entries: list[tuple[zipfile.ZipInfo, bytes]] = []

    for info, data in entries:
        if info.filename.lower().endswith('.xml') and target_name is None:
            try:
                updated, candidate_report = apply_student_rows_xml(data, case)
            except (ET.ParseError, ValueError):
                pass
            else:
                data = updated
                target_name = info.filename
                report = candidate_report
        updated_entries.append((info, data))

    if target_name is None or report is None:
        raise ValueError('HWPX에서 서식10 관련학생 표를 찾지 못했습니다.')

    temp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with zipfile.ZipFile(temp_path, 'w') as output:
            for info, data in updated_entries:
                compression = zipfile.ZIP_STORED if info.filename == 'mimetype' else zipfile.ZIP_DEFLATED
                output.writestr(info.filename, data, compress_type=compression)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)

    return {'xmlFile': target_name, **report}
