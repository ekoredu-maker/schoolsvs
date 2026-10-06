from __future__ import annotations

import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from form10_markers import apply_form10_markers_xml  # noqa: E402

NS = "urn:test:hp"
ET.register_namespace("hp", NS)


def q(name: str) -> str:
    return f"{{{NS}}}{name}"


def cell(col: int, *texts: str) -> ET.Element:
    tc = ET.Element(q("tc"))
    ET.SubElement(tc, q("cellAddr"), {"colAddr": str(col), "rowAddr": "0"})
    p = ET.SubElement(tc, q("p"))
    for value in texts:
        run = ET.SubElement(p, q("run"))
        node = ET.SubElement(run, q("t"))
        node.text = value
    return tc


def row(*items: ET.Element) -> ET.Element:
    tr = ET.Element(q("tr"))
    for item in items:
        tr.append(item)
    return tr


def fact_cell() -> ET.Element:
    outer = cell(1)
    nested = ET.SubElement(outer, q("tbl"), {"rowCnt": "5", "colCnt": "2"})
    nested.extend([
        row(cell(0, "관련학생"), cell(1, "※ 육하원칙에 의거 접수한 내용을 간략히 기재")),
        row(cell(0, "일시"), cell(1, "2026.10.05. 13:20")),
        row(cell(0, "장소"), cell(1, "복도")),
        row(cell(0, "내용"), cell(1, "단체대화방에서 언어폭력으로 신고되었다는 가상 요약")),
        row(cell(0, "유형"), cell(1,
            "□", "신체폭력 ", "□", "언어폭력 ", "□", "금품갈취 ",
            "□", "강요 ", "□", "따돌림 ", "□", "성폭력 ",
            "□", "사이버폭력 ", "□", "기타 ", "□",
            "아동학대(접수여부:  )  ※중복체크 가능(", "■, □)")),
    ])
    return outer


def sample_xml() -> bytes:
    root = ET.Element(q("sec"))
    table = ET.SubElement(root, q("tbl"), {"rowCnt": "14", "colCnt": "15"})
    table.extend([
        row(cell(0, "학교명"), cell(1, "테스트학교"), cell(3, "접수일시"), cell(4, "2026.10.05")),
        row(cell(0, "조사관 배정요청"), cell(1, "조사관 배정 요청 □       학교 자체 조사 □")),
        row(cell(0, "가해학생 제2호 조치 시행"), cell(1, "학교폭력예방법 제17조제4항에 따른 가해학생 제2호 조치 시행(2025.00.00.)")),
        row(cell(1, "분리기간: (         )일"), cell(7,
            "* 피해학생 반대의사 표명 [   ]",
            "* 교육활동 중이 아님 [    ]",
            "학교장이 긴급선도조치를 시행하여 가해학생이 이미 분리됨 [    ]",
            "* 타학교에 재학 중임 등 [     ]",
            "학교장 허가 교외체험학습으로 등교하지 않은 경우 [     ]",
            "학교장 자체해결 가능 요건(4개 항목)에 모두 해당 [     ]")),
        row(cell(0, "사실 확인 내용"), fact_cell()),
        row(cell(0, "관련학생"), cell(1, "학교명 학번 성명 성별 보호자 통보여부")),
        row(cell(0, "기타 사항"), cell(1, "경찰신고, 고소, 소송 여부 등")),
        row(cell(0, "타학교 관련 여부"), cell(1, "관련학교명"), cell(4, "안내문")),
        row(cell(1, "통보여부"), cell(4, "(통보 일시, 방법) (통보 받은 사람) (연락처)")),
        row(cell(0, "전담조사관 면담조사 가능시간"), cell(1, "피해 관련"), cell(4, "※ 학교자체 조사인 경우 빈칸")),
        row(cell(1, "가해 관련"), cell(4, "※ 학교자체 조사인 경우 빈칸")),
        row(cell(0, "관계회복 프로그램 관련 학생 의견"), cell(1, "피해 관련"), cell(4, "예시 피해")),
        row(cell(1, "가해 관련"), cell(4, "예시 가해")),
    ])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def case_data() -> dict:
    return {
        "violenceType": "복합(2개 이상)",
        "separation": "즉시분리 미시행",
        "sepPeriod": "",
        "sepReason": "피해관련학생이 분리 조치에 반대 의사를 표명한 경우",
        "_hybrid": {"atoz": {
            "investigationMode": "investigator",
            "no2ActionDate": "2026-10-05T09:30",
            "violenceTypes": ["신체폭력", "언어폭력"],
            "separationExceptions": {"differentSchool": True},
            "otherMatters": "112 신고 완료",
            "otherSchoolRelated": True,
            "otherSchoolName": "타학교",
            "otherSchoolNotifyAt": "2026-10-05T10:10",
            "otherSchoolNotifyMethod": "유선",
            "otherSchoolRecipient": "김교사",
            "otherSchoolContact": "010-0000-0000",
            "victimInterviewTime": "10.6. 10:00",
            "perpInterviewTime": "10.6. 14:00",
            "victimRecoveryOpinion": "사과 시 참여 의사 있음",
            "perpRecoveryOpinion": "대화 의사 있음",
        }},
    }


class OfficialNestedViolenceTests(unittest.TestCase):
    def test_summary_keyword_does_not_steal_checkbox_match(self):
        updated, report = apply_form10_markers_xml(sample_xml(), case_data())
        root = ET.fromstring(updated)

        type_row = None
        for table in root.iter():
            if not table.tag.endswith("}tbl") or table.get("rowCnt") != "5":
                continue
            for r in list(table):
                values = [node.text or "" for node in r.iter() if node.tag.endswith("}t")]
                if "유형" in values and any("신체폭력" in v for v in values):
                    type_row = r
                    break
        self.assertIsNotNone(type_row)

        values = [node.text or "" for node in type_row.iter() if node.tag.endswith("}t")]
        labels = {}
        for label in ["신체폭력", "언어폭력", "사이버폭력"]:
            idx = next(i for i, value in enumerate(values) if label in value)
            marker = next(
                value.strip()
                for value in reversed(values[max(0, idx - 4):idx])
                if value.strip() in {"□", "■"}
            )
            labels[label] = marker

        self.assertEqual(labels["신체폭력"], "■")
        self.assertEqual(labels["언어폭력"], "■")
        self.assertEqual(labels["사이버폭력"], "□")
        self.assertEqual(report["violence"]["missingOptions"], [])
        self.assertEqual(report["violence"]["selected"], ["신체폭력", "언어폭력"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
