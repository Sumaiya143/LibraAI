@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.12 or newer and enable PATH.
  pause
  exit /b 1
)
echo [1/5] Installing pinned backend dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. No tests were reported as passed.
  pause
  exit /b 1
)
echo [2/6] Verifying Flask runtime dependencies...
python -c "import flask, werkzeug; print('Flask and Werkzeug imports OK')"
if errorlevel 1 goto :failed
echo [3/6] Checking release package hygiene...
python -B buyer_preflight.py
if errorlevel 1 goto :failed
echo [4/6] Running fail-closed payment callback integration tests...
python -B verify_payment_route_tests.py
if errorlevel 1 goto :failed
echo [5/6] Running the complete Python test suite...
python -B verify_full_test_suite.py
if errorlevel 1 goto :failed
echo [6/6] Compiling Python sources...
python -B -m compileall -q .
if errorlevel 1 goto :failed
echo.
echo All local backend verification steps passed with zero skipped tests. This does NOT verify live payments, licensing, production AI, HTTPS, or independent security review.
pause
exit /b 0
:failed
echo.
echo VERIFICATION FAILED. Fix the reported issue; do not deploy based on a partial pass.
pause
exit /b 1
