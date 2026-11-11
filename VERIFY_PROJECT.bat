@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (echo Python 3.12+ is required.& pause & exit /b 1)
  set "PY=python"
) else (
  set "PY=py -3"
)
echo [1/6] Install backend and test dependencies in your active environment...
%PY% -m pip install -r requirements-dev.txt
if errorlevel 1 goto :failed
echo [2/6] Run environment doctor...
%PY% -B project_doctor.py
if errorlevel 1 goto :failed
echo [3/6] Run dependency-free release portability checks...
%PY% -B -m unittest -v test_release_portability.py test_environment_templates.py test_production_preflight.py test_extended_verification.py
if errorlevel 1 goto :failed
echo [4/6] Run the complete strict Python suite (no skips allowed)...
%PY% -B verify_full_test_suite.py
if errorlevel 1 goto :failed
echo [5/6] Verify frontend source contracts...
cd /d "%~dp0frontend"
where node >nul 2>nul
if errorlevel 1 (echo Node.js 20+ is required for frontend checks.& goto :failed)
node scripts/verify-client-enhancements.mjs
if errorlevel 1 goto :failed
node scripts/verify-page-shell.mjs
if errorlevel 1 goto :failed
node scripts/verify-live-integration-contracts.mjs
if errorlevel 1 goto :failed
node scripts/verify-security-headers.mjs
if errorlevel 1 goto :failed
node scripts/verify-language-bridge.mjs
if errorlevel 1 goto :failed
echo [6/6] Build production frontend if dependencies are installed...
if not exist "node_modules" (
  echo Frontend dependencies missing. Run START_FRONTEND.bat once with internet access, then rerun this verifier.
  goto :failed
)
call npm run build
if errorlevel 1 goto :failed
echo.
echo All requested local verification steps passed. This still does not verify live SSL, real payment providers, external AI credentials, or production deployment.
pause
exit /b 0
:failed
echo.
echo VERIFICATION FAILED OR IS INCOMPLETE. Do not deploy until all required checks pass.
pause
exit /b 1
