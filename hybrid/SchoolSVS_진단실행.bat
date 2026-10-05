@echo off
setlocal
cd /d "%~dp0"
set SCHOOLSVS_PORT=

echo ==============================================
echo   SchoolSVS Portable Diagnostic Launcher
echo ==============================================
echo.

if exist "runtime\python.exe" (
  echo [OK] Embedded Python: runtime\python.exe
  "runtime\python.exe" app\main.py
  goto :done
)

echo [WARN] Embedded Python not found. Trying installed Python for development...
py -3 app\main.py 2>nul || python app\main.py
if errorlevel 1 (
  echo.
  echo [ERROR] Python runtime could not be found.
  echo Use the official SchoolSVS portable ZIP containing the runtime folder.
  pause
)

:done
endlocal
