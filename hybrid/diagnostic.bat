@echo off
setlocal
cd /d "%~dp0"
set SCHOOLSVS_PORT=

echo ==============================================
echo   SchoolSVS Portable Diagnostic
echo ==============================================
echo.

if not exist "runtime\python.exe" (
  echo [ERROR] Embedded Python is missing: runtime\python.exe
  echo.
  pause
  exit /b 2
)

if not exist "app\portable_entry.py" (
  echo [ERROR] Program entry is missing: app\portable_entry.py
  echo.
  pause
  exit /b 3
)

echo [OK] Embedded Python found.
echo [OK] Program entry found.
echo [INFO] Starting SchoolSVS in diagnostic mode...
echo [INFO] Keep this window open while testing.
echo.

"runtime\python.exe" "app\portable_entry.py"
set EXITCODE=%ERRORLEVEL%

echo.
echo ==============================================
echo SchoolSVS stopped. Exit code: %EXITCODE%
echo ==============================================
if exist "data\startup.log" (
  echo.
  echo ----- startup.log -----
  type "data\startup.log"
  echo -----------------------
)
echo.
pause
exit /b %EXITCODE%
