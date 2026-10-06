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


def official_split_like_xml() -> bytes:
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
        row(cell(0, "사실확인 내용"), cell(1, "유형"), cell(3,
            "□", "신체폭력 ", "□", "언어폭력 ", "□", "금품갈취 ",
            "□", "강요 ", "□", "따돌림 ", "□", "성폭력 ",
            "□", "사이버폭력 ", "□", "기타 ", "□",
            "아동학대(접수여부:  )  ※중복체크 가능(", "■, □)")),
        row(cell(0, "관련학생"), cell(1, "학교명 학번 성명 성별 보호자 통보여부")),
        row(cell(0, "기타 사항"), cell(1, "경찰신고, 고소, 소송 여부 등")),
        row(cell(0, "타학교 관련 여부"), cell(1, "관련학교명"), cell(3, "안내문")),
        row(cell(1, "통보여부"), cell(3, "(통보 일시, 방법) (통보 받은 사람) (연락처)")),
        row(cell(0, "전담조사관 면담조사 가능시간"), cell(1, "피해 관련"), cell(3, "※ 학교자체 조사인 경우 빈칸")),
        row(cell(1, "가해 관련"), cell(3, "※ 학교자체 조사인 경우 빈칸")),
        row(cell(0, "관계회복 프로그램 관련 학생 의견"), cell(1, "피해 관련"), cell(3, "예시 피해")),
        row(cell(1, "가해 관련"), cell(3, "예시 가해")),
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
            "violenceTypes": ["신체폭력", "사이버폭력"],
            "separationExceptions": {"differentSchool": True},
            "otherMatters": "112 신고 완료",
            "otherSchoolRelated": False,
            "victimRecoveryOpinion": "사과 시 참여 의사 있음",
            "perpRecoveryOpinion": "대화 의사 있음",
        }},
    }


class OfficialSplitNodeViolenceTests(unittest.TestCase):
    def test_official_split_nodes_toggle_only_checkbox_glyphs(self):
        updated, report = apply_form10_markers_xml(official_split_like_xml(), case_data())
        root = ET.fromstring(updated)
        nodes = [(node.text or "") for node in root.iter() if node.tag.endswith("}t")]

        self.assertIn("■", nodes)
        self.assertIn("신체폭력 ", nodes)
        self.assertIn("사이버폭력 ", nodes)
        self.assertIn("□", nodes)
        self.assertIn("언어폭력 ", nodes)

        joined = "|".join(nodes)
        self.assertNotIn("■신체폭력 ■", joined)
        self.assertEqual(report["violence"]["missingOptions"], [])
        self.assertEqual(
            report["violence"]["markedOptions"],
            ["신체폭력", "언어폭력", "금품갈취", "강요", "따돌림", "성폭력", "사이버폭력", "기타", "아동학대"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
