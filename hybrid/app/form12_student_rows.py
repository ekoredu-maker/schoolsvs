from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _local(tag: str) -> str:
    return tag.split('}')[-1]


def _text(elem: ET.Element) -> str:
    parts=[]
    for node in elem.iter():
        if _local(node.tag)=='t' and (node.text or '').strip():
            parts.append(' '.join((node.text or '').split()))
    return ' '.join(parts)


def _rows(tbl: ET.Element) -> list[ET.Element]:
    return [x for x in list(tbl) if _local(x.tag)=='tr']


def _cells(row: ET.Element) -> list[ET.Element]:
    return [x for x in list(row) if _local(x.tag)=='tc']


def _desc(elem: ET.Element, name: str) -> ET.Element | None:
    return next((x for x in elem.iter() if _local(x.tag)==name),None)


def _cell_by_col(row: ET.Element, col: int) -> ET.Element | None:
    for cell in _cells(row):
        addr=_desc(cell,'cellAddr')
        if addr is not None and int(addr.get('colAddr','-1'))==col:
            return cell
    return None


def _set_cell_text(cell: ET.Element, value: str) -> None:
    texts=[n for n in cell.iter() if _local(n.tag)=='t']
    if not texts:
        run=_desc(cell,'run')
        if run is None:
            raise ValueError('서식12 관련학생 셀의 run 노드를 찾지 못했습니다.')
        ns=run.tag.split('}')[0].lstrip('{') if '}' in run.tag else ''
        texts=[ET.SubElement(run,f'{{{ns}}}t' if ns else 't')]
    texts[0].text=value
    for node in texts[1:]: node.text=''


def _profiles(case: dict[str,Any]) -> list[dict[str,Any]]:
    raw=((case.get('_hybrid') or {}).get('studentProfiles') or [])
    if not isinstance(raw,list): return []
    return [x for x in raw if isinstance(x,dict) and str(x.get('name') or '').strip()]


def _grade_class_number(p: dict[str,Any]) -> str:
    grade=re.sub(r'\D','',str(p.get('grade') or ''))
    cls=re.sub(r'\D','',str(p.get('classNo') or ''))
    num=re.sub(r'\D','',str(p.get('number') or ''))
    if grade and cls and num: return f'{grade}-{cls}/{num}'
    return '/'.join(x for x in ['-'.join(x for x in [grade,cls] if x),num] if x)


def _reindex(tbl: ET.Element) -> None:
    rows=_rows(tbl); tbl.set('rowCnt',str(len(rows)))
    for i,row in enumerate(rows):
        for cell in _cells(row):
            addr=_desc(cell,'cellAddr')
            if addr is not None: addr.set('rowAddr',str(i))


def apply_form12_student_rows_xml(xml_bytes: bytes, case: dict[str,Any]) -> tuple[bytes,dict[str,Any]]:
    root=ET.fromstring(xml_bytes)
    profiles=_profiles(case)
    if not profiles: raise ValueError('관련학생 상세정보가 없어 서식12 학생 행을 만들 수 없습니다.')
    target=None; header_i=None; foot_i=None
    for tbl in [x for x in root.iter() if _local(x.tag)=='tbl']:
        rows=_rows(tbl)
        for i,row in enumerate(rows):
            tx=_text(row)
            if not all(k in tx for k in ('관련 학생','학교','성 명','성 별')): continue
            for j in range(i+1,len(rows)):
                if '국민체육진흥법' in _text(rows[j]):
                    target=tbl; header_i=i; foot_i=j; break
            if target is not None: break
        if target is not None: break
    if target is None or header_i is None or foot_i is None:
        raise ValueError('서식12 관련학생 표 영역을 찾지 못했습니다.')
    rows=_rows(target); samples=rows[header_i+1:foot_i]
    if not samples: raise ValueError('서식12 관련학생 예시 행을 찾지 못했습니다.')
    prototype=samples[0]
    for row in samples: target.remove(row)
    header=rows[header_i]; insert_at=list(target).index(header)+1
    created=[]
    for offset,p in enumerate(profiles):
        row=copy.deepcopy(prototype)
        values={
            1:str(p.get('schoolName') or ''),
            2:_grade_class_number(p),
            4:str(p.get('name') or ''),
            8:str(p.get('gender') or ''),
            9:str(p.get('relatedSchoolCaseNo') or ''),
            10:'V' if p.get('role')=='perp' and bool(p.get('athlete')) else '',
            12:'가해관련' if p.get('role')=='perp' else '피해관련' if p.get('role')=='victim' else '관련',
        }
        for col,value in values.items():
            cell=_cell_by_col(row,col)
            if cell is not None: _set_cell_text(cell,value)
        target.insert(insert_at+offset,row)
        created.append(values)
    _reindex(target)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True),{'studentCount':len(profiles),'rowCount':int(target.get('rowCnt') or 0),'rows':created}


def apply_form12_student_rows_to_hwpx(path: Path, case: dict[str,Any]) -> dict[str,Any]:
    if not zipfile.is_zipfile(path): raise ValueError('유효한 HWPX 파일이 아닙니다.')
    with zipfile.ZipFile(path,'r') as source:
        entries=[(info,source.read(info.filename)) for info in source.infolist()]
    target_name=None; report=None; updated=[]
    for info,data in entries:
        if target_name is None and info.filename.lower().endswith('.xml'):
            try: candidate,candidate_report=apply_form12_student_rows_xml(data,case)
            except (ET.ParseError,ValueError): pass
            else: data=candidate; target_name=info.filename; report=candidate_report
        updated.append((info,data))
    if target_name is None or report is None: raise ValueError('HWPX에서 서식12 관련학생 표를 찾지 못했습니다.')
    tmp=path.with_suffix(path.suffix+'.rows.tmp')
    try:
        with zipfile.ZipFile(tmp,'w') as output:
            for info,data in updated:
                output.writestr(info.filename,data,compress_type=zipfile.ZIP_STORED if info.filename=='mimetype' else zipfile.ZIP_DEFLATED)
        tmp.replace(path)
    finally: tmp.unlink(missing_ok=True)
    return {'xmlFile':target_name,**report}
