# 학교폭력 업무 담당자용 업무 처리 보조 프로그램(학교용)

이 저장소는 단일 HTML 기반 프로그램을 **GitHub 저장소용 구조**로 정리한 패키지입니다.

## 포함 파일
- `index.html` : 메인 앱
- `manifest.webmanifest` : 설치형 웹앱(PWA) 정보
- `sw.js` : 오프라인 캐시용 서비스 워커
- `.github/workflows/pages.yml` : GitHub Pages 배포용 워크플로
- `assets/icons/*` : 아이콘
- `SECURITY-NOTICE.md` : 민감정보 운영 주의사항
- `LICENSE.txt` : 기본 권리 고지

## 빠른 사용법
1. 새 GitHub 저장소를 만듭니다.
2. 이 폴더의 파일을 저장소 루트에 업로드합니다.
3. 기본 브랜치를 `main`으로 사용합니다.
4. 저장소의 **Settings → Pages**에서 GitHub Actions를 사용해 배포하거나,
   워크플로가 자동 실행되도록 둡니다.
5. 첫 배포 후 `https://사용자명.github.io/저장소명/` 주소에서 실행합니다.

## 중요한 주의
이 앱은 현재 `localStorage` 기반입니다.
따라서 **공개 GitHub Pages에서 실데이터를 운영하는 것은 권장하지 않습니다.**
공개 웹판은 데모 또는 샘플 데이터 용도로만 사용하세요.

## 권장 운영 방식
- 공개용: GitHub Pages 데모판
- 실무용: 비공개 저장소 + Tauri 또는 Python 설치형 앱
- 장기적으로: SQLite/암호화 저장 구조 도입

## 저작권
기본 상태는 오픈소스가 아닙니다. 자세한 내용은 `LICENSE.txt`를 확인하세요.
