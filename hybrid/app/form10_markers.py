from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

VIOLENCE_OPTIONS = ["신체폭력", "언어폭력", "금품갈취", "강요", "따돌림", "성폭력", "사이버폭력", "기타", "아동학대"]
EXCEPTION_KEYS = {"victimOpposed":"피해학생 반대의사","notInEducationActivity":"교육활동 중이 아님","alreadySeparatedByEmergency":"학교장이 긴급선도조치를 시행","differentSchool":"타학교에 재학","offCampusExperience":"학교장 허가 교외체험학습","selfResolutionFourCriteria":"학교장 자체해결 가능 요건"}
LEGACY_REASON_TO_KEY = {"반대 의사를 표명":"victimOpposed","교육활동 중이 아닌":"notInEducationActivity","긴급 선도조치를 시행":"alreadySeparatedByEmergency","소속교가 다른":"differentSchool","교외체험학습":"offCampusExperience","자체해결 가능 요건":"selfResolutionFourCriteria"}

def _local(tag: str) -> str: return tag.split("}")[-1]
def _texts(elem: ET.Element) -> list[ET.Element]: return [n for n in elem.iter() if _local(n.tag)=="t"]
def _text(elem: ET.Element) -> str: return " ".join(" ".join((n.text or "").split()) for n in _texts(elem) if (n.text or "").strip()).strip()
def _rows(table: ET.Element) -> list[ET.Element]: return [c for c in list(table) if _local(c.tag)=="tr"]
def _cells(row: ET.Element) -> list[ET.Element]: return [c for c in list(row) if _local(c.tag)=="tc"]
def _cell_by_col(row: ET.Element, col: int) -> ET.Element | None:
    for cell in _cells(row):
        addr = next((x for x in cell if _local(x.tag)=="cellAddr"), None)
        if addr is not None and int(addr.get("colAddr","-1"))==col: return cell
    return None

def _set_cell_text(cell: ET.Element, value: str) -> None:
    nodes=_texts(cell)
    if not nodes: raise ValueError("서식10 셀의 텍스트 노드를 찾지 못했습니다.")
    nodes[0].text=value
    for node in nodes[1:]: node.text=""

def _row(table: ET.Element,*keywords:str)->ET.Element|None:
    for row in _rows(table):
        text=_text(row)
        if all(k in text for k in keywords): return row
    return None

def _main_table(root:ET.Element)->ET.Element:
    for table in root.iter():
        if _local(table.tag)=="tbl" and all(x in _text(table) for x in ("학교명","접수일시","전담조사관","관련학생")): return table
    raise ValueError("서식10 본문 표를 찾지 못했습니다.")
def _atoz(case:dict[str,Any])->dict[str,Any]:
    v=((case.get("_hybrid") or {}).get("atoz") or {}); return v if isinstance(v,dict) else {}
def _format_date(value:Any)->str:
    text=str(value or "").strip()
    if not text:return ""
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00")); return f"{dt.year}. {dt.month:02d}. {dt.day:02d}."
    except ValueError: pass
    m=re.match(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})",text)
    if m:
        y,mo,d=m.groups(); return f"{int(y)}. {int(mo):02d}. {int(d):02d}."
    return text
def _format_datetime(value:Any)->str:
    text=str(value or "").strip()
    if not text:return ""
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00")); return f"{dt.month}. {dt.day}. {dt.hour:02d}:{dt.minute:02d}"
    except ValueError:return text

def _selected_violence_types(case:dict[str,Any])->tuple[list[str],bool]:
    atoz=_atoz(case); raw=atoz.get("violenceTypes"); selected=[]
    if isinstance(raw,list): selected=[str(x).strip() for x in raw if str(x).strip()]
    elif isinstance(raw,str) and raw.strip(): selected=[x.strip() for x in re.split(r"[,/|;]",raw) if x.strip()]
    legacy=str(case.get("violenceType") or "").strip(); detail_required=False
    if not selected and legacy:
        if legacy=="복합(2개 이상)": detail_required=True
        else: selected=[legacy]
    out=[]; aliases={"폭행":"신체폭력"}
    for item in selected:
        value=aliases.get(item,item)
        if value in VIOLENCE_OPTIONS and value not in out: out.append(value)
    return out,detail_required

def _mark_investigation(table:ET.Element,case:dict[str,Any])->dict[str,Any]:
    row=_row(table,"조사관","배정요청"); cell=_cell_by_col(row,1) if row is not None else None
    if cell is None: raise ValueError("조사 방식 값 셀을 찾지 못했습니다.")
    mode=str(_atoz(case).get("investigationMode") or "").strip()
    value="조사관 배정 요청 ■       학교 자체 조사 □" if mode=="investigator" else "조사관 배정 요청 □       학교 자체 조사 ■" if mode=="school" else "조사관 배정 요청 □       학교 자체 조사 □"
    _set_cell_text(cell,value); return {"mode":mode,"text":value}
def _mark_no2(table:ET.Element,case:dict[str,Any])->dict[str,Any]:
    row=_row(table,"제2호 조치 시행"); cell=_cell_by_col(row,1) if row is not None else None
    if cell is None: raise ValueError("제2호 조치 시행 값 셀을 찾지 못했습니다.")
    date=_format_date(_atoz(case).get("no2ActionDate")); value="학교폭력예방법 제17조제4항에 따른 가해학생 제2호 조치 시행"+(f"({date})" if date else "")
    _set_cell_text(cell,value); return {"date":date}
def _mark_bracket_near(nodes:list[ET.Element],phrase:str,selected:bool)->bool:
    for i,node in enumerate(nodes):
        if phrase not in (node.text or ""): continue
        for candidate in nodes[i:i+5]:
            text=candidate.text or ""
            if re.search(r"\[\s*\]",text):
                candidate.text=re.sub(r"\[\s*\]","[○]" if selected else "[ ]",text,count=1); return True
        return False
    return False
def _mark_separation(table:ET.Element,case:dict[str,Any])->dict[str,Any]:
    row=_row(table,"분리기간","피해학생 반대의사")
    period_cell=_cell_by_col(row,1) if row is not None else None; reason_cell=_cell_by_col(row,7) if row is not None else None
    if period_cell is None or reason_cell is None: raise ValueError("즉시분리 기간·사유 셀 구조가 예상과 다릅니다.")
    separation=str(case.get("separation") or "").strip(); period=str(case.get("sepPeriod") or "").strip(); number=re.sub(r"\D","",period)
    _set_cell_text(period_cell,f"분리기간: ( {number} )일" if separation=="즉시분리 시행" and number else "분리기간: (    )일")
    atoz=_atoz(case); exceptions=dict(atoz.get("separationExceptions") or {}); legacy_reason=str(case.get("sepReason") or "")
    for needle,key in LEGACY_REASON_TO_KEY.items():
        if needle in legacy_reason: exceptions[key]=True
    nodes=_texts(reason_cell); marked={}
    for key,phrase in EXCEPTION_KEYS.items(): marked[key]=_mark_bracket_near(nodes,phrase,separation=="즉시분리 미시행" and bool(exceptions.get(key)))
    return {"mode":separation,"period":period,"exceptions":exceptions,"marked":marked}
def _mark_violence(table:ET.Element,case:dict[str,Any])->dict[str,Any]:
    row=_row(table,"유형","신체폭력")
    if row is None: raise ValueError("학교폭력 유형 행을 찾지 못했습니다.")
    selected,detail_required=_selected_violence_types(case); nodes=_texts(row)
    target=next((n for n in nodes if "신체폭력" in (n.text or "") and "언어폭력" in (n.text or "")),None)
    if target is not None:
        target.text=" ".join(("■" if item in selected else "□")+item+("(접수여부:  )" if item=="아동학대" else "") for item in VIOLENCE_OPTIONS)+"  ※중복체크 가능(■, □)"
        found=False
        for node in nodes:
            if node is target: found=True; continue
            if found and any(x in (node.text or "") for x in ("아동학대(접수여부","성폭력(접수여부")): node.text=""
        return {"selected":selected,"detailRequired":detail_required,"layout":"combined"}
    marked={}
    for item in VIOLENCE_OPTIONS:
        label_index=next((i for i,n in enumerate(nodes) if item in (n.text or "")),None)
        if label_index is None:
            marked[item]=False
            continue
        checkbox=None
        for i in range(label_index-1,max(-1,label_index-4),-1):
            if (nodes[i].text or "").strip() in {"□","■"}:
                checkbox=nodes[i]; break
        if checkbox is None:
            marked[item]=False
            continue
        checkbox.text="■" if item in selected else "□"
        marked[item]=True
    if not any(marked.values()):
        raise ValueError("학교폭력 유형 체크 영역을 찾지 못했습니다.")
    return {"selected":selected,"detailRequired":detail_required,"layout":"split_nodes","marked":marked}

def _fill_atoz_cells(table:ET.Element,case:dict[str,Any])->dict[str,Any]:
    atoz=_atoz(case); report={}
    other=_row(table,"기타 사항")
    if other is not None:
        cell=_cell_by_col(other,1); value=str(atoz.get("otherMatters") or "").strip()
        if cell is not None and value:_set_cell_text(cell,value+"\n※ 아동·청소년대상 성관련 사안은 수사기관 신고 일시를 확인")
        report["otherMatters"]=bool(value)
    other_school=_row(table,"타학교 관련 여부","관련학교명"); notice=_row(table,"통보여부","통보 일시"); related=bool(atoz.get("otherSchoolRelated"))
    if other_school is not None:
        cell=_cell_by_col(other_school,3)
        if cell is not None:_set_cell_text(cell,str(atoz.get("otherSchoolName") or "").strip() if related else "")
    if notice is not None:
        cell=_cell_by_col(notice,3)
        if cell is not None:
            pieces=[_format_datetime(atoz.get("otherSchoolNotifyAt")),str(atoz.get("otherSchoolNotifyMethod") or "").strip(),str(atoz.get("otherSchoolRecipient") or "").strip(),str(atoz.get("otherSchoolContact") or "").strip()] if related else []
            _set_cell_text(cell," / ".join(x for x in pieces if x))
    report["otherSchoolRelated"]=related
    victim=_row(table,"전담조사관","피해 관련"); perp=None
    if victim is not None:
        rows=_rows(table); idx=rows.index(victim); perp=rows[idx+1] if idx+1<len(rows) and "가해 관련" in _text(rows[idx+1]) else None
    mode=str(atoz.get("investigationMode") or "")
    if victim is not None and _cell_by_col(victim,3) is not None:_set_cell_text(_cell_by_col(victim,3),str(atoz.get("victimInterviewTime") or "").strip() if mode=="investigator" else "")
    if perp is not None and _cell_by_col(perp,3) is not None:_set_cell_text(_cell_by_col(perp,3),str(atoz.get("perpInterviewTime") or "").strip() if mode=="investigator" else "")
    report["interviewMode"]=mode
    victim_op=_row(table,"관계회복 프로그램 관련 학생 의견","피해 관련"); perp_op=None
    if victim_op is not None:
        rows=_rows(table); idx=rows.index(victim_op); perp_op=rows[idx+1] if idx+1<len(rows) and "가해 관련" in _text(rows[idx+1]) else None
        cell=_cell_by_col(victim_op,3)
        if cell is not None:_set_cell_text(cell,str(atoz.get("victimRecoveryOpinion") or "").strip())
    if perp_op is not None:
        cell=_cell_by_col(perp_op,3)
        if cell is not None:_set_cell_text(cell,str(atoz.get("perpRecoveryOpinion") or "").strip())
    report["recoveryOpinion"]=bool(victim_op); return report

def apply_form10_markers_xml(xml_bytes:bytes,case:dict[str,Any])->tuple[bytes,dict[str,Any]]:
    root=ET.fromstring(xml_bytes); table=_main_table(root)
    report={"investigation":_mark_investigation(table,case),"no2":_mark_no2(table,case),"separation":_mark_separation(table,case),"violence":_mark_violence(table,case),"atozCells":_fill_atoz_cells(table,case)}
    return ET.tostring(root,encoding="utf-8",xml_declaration=True),report

def apply_form10_markers_to_hwpx(path:Path,case:dict[str,Any])->dict[str,Any]:
    if not zipfile.is_zipfile(path): raise ValueError("유효한 HWPX 파일이 아닙니다.")
    with zipfile.ZipFile(path,"r") as source: entries=[(info,source.read(info.filename)) for info in source.infolist()]
    updated=[]; target_name=None; report=None
    for info,data in entries:
        if target_name is None and info.filename.lower().endswith(".xml"):
            try: candidate_data,candidate_report=apply_form10_markers_xml(data,case)
            except (ET.ParseError,ValueError): pass
            else: data=candidate_data; target_name=info.filename; report=candidate_report
        updated.append((info,data))
    if target_name is None or report is None: raise ValueError("HWPX에서 서식10 체크·복합 입력 영역을 찾지 못했습니다.")
    temp_path=path.with_suffix(path.suffix+".markers.tmp")
    try:
        with zipfile.ZipFile(temp_path,"w") as output:
            for info,data in updated: output.writestr(info.filename,data,compress_type=zipfile.ZIP_STORED if info.filename=="mimetype" else zipfile.ZIP_DEFLATED)
        temp_path.replace(path)
    finally: temp_path.unlink(missing_ok=True)
    return {"xmlFile":target_name,**report}
