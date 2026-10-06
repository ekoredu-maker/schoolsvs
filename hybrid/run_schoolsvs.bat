@echo off
setlocal
cd /d "%~dp0"

rem 고정 포트를 지정하지 않는다. Python 서버가 사용 가능한 localhost 포트를 자동 선택한다.
set SCHOOLSVS_PORT=

if exist "runtime\python.exe" (
  "runtime\python.exe" app\main.py
  goto :done
)

rem 개발 환경에서는 설치된 Python을 대체 실행기로 사용한다.
py -3 app\main.py 2>nul || python app\main.py
if errorlevel 1 (
  echo.
  echo [오류] SchoolSVS 실행용 Python을 찾지 못했습니다.
  echo 배포본은 runtime 폴더에 Python이 포함된 포터블 ZIP으로 제공됩니다.
  pause
)

:done
endlocal
