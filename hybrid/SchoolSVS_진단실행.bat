@echo off
setlocal
cd /d "%~dp0"
set SCHOOLSVS_PORT=

echo ==============================================
echo   SchoolSVS Portable Diagnostic Launcher
echo ==============================================
echo.

echo [1] Folder: %CD%
if not exist "runtime\python.exe" (
  echo [ERROR] Embedded Python not found: runtime\python.exe
  echo.
  pause
  exit /b 2
)
if not exist "app\portable_entry.py" (
  echo [ERROR] portable_entry.py not found: app\portable_entry.py
  echo.
  pause
  exit /b 3
)

echo [2] Embedded Python found.
echo [3] Starting SchoolSVS portable entry...
echo     This window will remain open while SchoolSVS is running.
echo.

"runtime\python.exe" app\portable_entry.py
set EXITCODE=%ERRORLEVEL%

echo.
echo ==============================================
echo SchoolSVS process ended. Exit code: %EXITCODE%
echo ==============================================
if exist "data\startup.log" (
  echo.
  echo ----- startup.log -----
  type "data\startup.log"
  echo ----- end log -----
) else (
  echo [INFO] startup.log was not created.
)
echo.
echo Press any key to close this diagnostic window.
pause >nul
exit /b %EXITCODE%
