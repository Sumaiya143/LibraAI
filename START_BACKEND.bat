@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3.10+ was not found. Install Python and enable PATH.
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
) else (
  set "PYTHON_CMD=py -3"
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :failed
)
echo Installing/verifying backend dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo Running local environment diagnostics...
".venv\Scripts\python.exe" project_doctor.py
if errorlevel 1 (
  echo Fix the required dependency errors above before starting.
  goto :failed
)
echo Starting LibraAI backend at http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto :failed
exit /b 0
:failed
echo LibraAI backend did not start successfully. Review the error above.
pause
exit /b 1
