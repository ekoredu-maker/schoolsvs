# SchoolSVS Hybrid v0.2

기존 HTML/JavaScript UI를 최대한 유지하면서 Python이 저장·검증·워크플로우를 담당하도록 단계적으로 전환하는 하이브리드 버전입니다.

## 현재 포함

- `app/main.py` : localhost 전용 Python API + 정적 파일 제공
- `app/storage.py` : SQLite 저장 계층
- `app/workflow.py` : 사안 검증 및 워크플로우 상태 계산
- `app/rules_2026.json` : 연도별 업무규칙 분리 초안
- `web/index.html` : 기존 UI를 그대로 담는 하이브리드 셸
- `web/bridge.js` : 기존 localStorage 변경 감지 + SQLite 동기화 + Python 검증 호출
- `tests/test_engine.py` : 저장·삭제·검증·워크플로우 회귀 테스트
- `run_schoolsvs.bat` : 개발용 Windows 실행기

## v0.2의 안전 원칙

1. 기존 `index.html` 자체는 수정하지 않는다.
2. 기존 브라우저 `localStorage`를 즉시 삭제하거나 강제 이전하지 않는다.
3. 하이브리드 실행 시 기존 데이터를 SQLite로 안전 복사한다.
4. 이후 저장·수정·삭제는 브리지에서 감지해 SQLite 상태와 동기화한다.
5. Python 엔진이 연결되지 않아도 기존 HTML/JavaScript 프로그램은 계속 사용할 수 있다.
6. SQLite 데이터가 있고 브라우저 데이터가 비어 있으면 사용자가 명시적으로 복원할 수 있다.
7. 법정·행정 기한은 공식 지침 검증 전 임의로 추가하지 않는다.

## 실행

`hybrid/run_schoolsvs.bat`를 실행합니다.

Python 서버가 `127.0.0.1:8768`에서 시작되고 다음 하이브리드 화면이 자동으로 열립니다.

```text
http://127.0.0.1:8768/hybrid/web/index.html
```

상단에 `Python 연결됨`이 표시되면 하이브리드 엔진과 SQLite가 정상 연결된 상태입니다.

## 데이터 동작

### 기존 데이터가 있는 경우

기존 `sv_assist_v2_*` localStorage 자료를 읽어 SQLite에 복사합니다. 원본 브라우저 데이터는 그대로 유지합니다.

### 이후 저장/수정/삭제

기존 화면에서 발생하는 localStorage 변경을 브리지가 감지하여 전체 사안 상태를 SQLite와 맞춥니다. 기존 화면에서 삭제된 사안은 SQLite에서도 제거됩니다.

### SQLite 복원

브라우저 저장자료가 비어 있고 SQLite에 자료가 남아 있으면 상단 `엔진 상태` 패널에서 `SQLite 데이터를 기존 화면으로 불러오기`를 사용할 수 있습니다.

## Python 검증

상단 `현재 사안 Python 검증` 버튼으로 현재 입력 폼을 Python 검증 엔진에 전달합니다.

현재 검증 범위:

- 사안번호/상태/접수일시 등 핵심 필수값
- 사건 발생일·장소·신고유형·폭력유형·사안개요
- 피해관련학생/가해관련학생 실명 입력 여부
- 교육지원청 보고완료 시 보고일
- 즉시분리 시행/미시행 관련 필드
- 조사관 지정 시 조사 예정일 확인
- 조치내용 입력 시 조치 결정일
- 종결 사안의 종결일
- 현재 처리상태에 따른 워크플로우 단계 및 완성도

## 회귀 테스트

저장소 루트 기준:

```bash
python hybrid/tests/test_engine.py
```

검증 항목:

- 정상 사안 검증
- 빈 학생명 탐지
- 종결일 누락 탐지
- 상태→워크플로우 단계 매핑
- SQLite 저장/읽기
- 같은 사안 수정 시 중복 방지
- 사안 삭제
- 설정/카운터 KV 저장

## 다음 단계

### v0.3 업무규칙 엔진 정밀화

충청북도교육청 `2026. 학교폭력 사안처리 A to Z`를 기준으로 업무단계·조건·기한·필요서식을 공식 자료와 대조해 `rules_2026.json`으로 이동합니다.

### v0.4 HWPX 엔진

실제 HWPX 원본 서식을 `templates/`에 두고 사안 데이터를 원본 표·문단·누름틀 구조에 매핑합니다.

### v0.5 데이터 모델 강화

현재 JSON 원형을 보존하면서 학생, 조치, 문서이력, 기한이력 등을 별도 구조로 분리합니다.

### 배포 단계

최종적으로 Python 미설치 PC에서도 실행할 수 있는 포터블 EXE/폴더형 배포본으로 패키징합니다.

## 목표 구조

```text
schoolsvs/
├─ index.html                 # 기존 UI 원본
├─ assets/
├─ hybrid/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ storage.py
│  │  ├─ workflow.py
│  │  └─ rules_2026.json
│  ├─ web/
│  │  ├─ index.html           # 하이브리드 셸
│  │  └─ bridge.js            # 기존 UI ↔ Python 연결
│  ├─ tests/
│  │  └─ test_engine.py
│  ├─ data/
│  │  └─ schoolsvs.db
│  ├─ templates/
│  │  └─ *.hwpx
│  └─ run_schoolsvs.bat
```
