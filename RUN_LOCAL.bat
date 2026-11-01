@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer and enable PATH.
  pause
  exit /b 1
)
echo Starting LibraAI catalog development server...
echo Keep this server on localhost; do not expose it directly to the internet.
python catalog_server.py
pause
