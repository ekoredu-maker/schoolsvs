@echo off
setlocal
cd /d "%~dp0"
set SCHOOLSVS_PORT=8768
py -3 app\main.py 2>nul || python app\main.py
if errorlevel 1 (
  echo.
  echo [오류] Python 실행 환경을 찾지 못했습니다.
  echo 배포본에서는 Python을 포함한 포터블 EXE로 제공할 예정입니다.
  pause
)
endlocal
