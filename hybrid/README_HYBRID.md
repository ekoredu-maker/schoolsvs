# SchoolSVS Hybrid v0.1

기존 HTML/JavaScript UI를 최대한 유지하면서 Python이 저장·검증·워크플로우·문서생성을 담당하도록 전환하기 위한 1차 골격입니다.

## 현재 포함

- `app/main.py` : localhost 전용 Python API + 기존 정적 파일 제공
- `app/storage.py` : SQLite 저장 계층
- `app/workflow.py` : 사안 검증 및 워크플로우 상태 계산
- `app/rules_2026.json` : 연도별 업무규칙 분리 초안
- `web/hybrid-bridge.js` : 기존 브라우저 UI와 Python API 연결
- `run_schoolsvs.bat` : 개발용 실행기

## 원칙

1. 기존 `index.html`의 UI와 사용자 입력 구조를 우선 보존한다.
2. `localStorage`는 1회 마이그레이션 후 SQLite로 이전한다.
3. 계산·검증·통계는 Python 단일 엔진에서 처리한다.
4. 법정/행정 기한은 공식 지침과 대조해 규칙 파일에 버전별로 관리한다.
5. HWPX는 실제 원본 서식을 템플릿으로 연결한다.
6. 배포본은 Python 미설치 PC에서도 실행되는 포터블 EXE를 목표로 한다.

## 1차 실행

저장소 루트에서 `hybrid/run_schoolsvs.bat`를 실행하면 `127.0.0.1:8768`에서 기존 `index.html`이 열립니다.

현재 단계에서는 기존 UI가 여전히 `localStorage`를 사용합니다. 이는 회귀오류를 막기 위한 의도적인 상태입니다.

브리지 연결 후 콘솔에서 다음 명령으로 기존 데이터를 SQLite로 복사할 수 있습니다.

```javascript
await SchoolSVSHybrid.migrateLocalStorage()
```

## 다음 작업

### 1. UI-엔진 연결

기존 `index.html`의 `DB.load/save/remove`, `saveCase()`, `saveSettings()`를 브리지 기반으로 단계적으로 교체합니다. 한 번에 바꾸지 않고 읽기 → 저장 → 삭제 순으로 전환합니다.

### 2. 데이터 모델 정규화

현재 사안 JSON 구조를 보존한 상태로 저장하고, 이후 학생·조치·문서이력·기한이력을 별도 테이블로 정규화합니다.

### 3. 업무규칙 정밀화

충북 학교폭력 사안처리 지침/A to Z의 각 단계와 서식을 실제 필드에 매핑합니다. 공식 지침 확인 전에는 임의의 기한 수치를 코드에 넣지 않습니다.

### 4. HWPX 엔진

실제 HWPX 원본 서식을 `templates/`에 두고, 사안 데이터의 필드를 표/문단/누름틀 등에 매핑합니다.

### 5. 포터블 배포

최종적으로 PyInstaller 기반 단일 실행기 또는 폴더형 포터블 배포본으로 패키징합니다.

## 권장 최종 구조

```text
schoolsvs/
├─ index.html
├─ assets/
├─ hybrid/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ storage.py
│  │  ├─ workflow.py
│  │  └─ rules_2026.json
│  ├─ web/
│  │  └─ hybrid-bridge.js
│  ├─ data/
│  │  └─ schoolsvs.db
│  ├─ templates/
│  │  └─ *.hwpx
│  └─ run_schoolsvs.bat
```
