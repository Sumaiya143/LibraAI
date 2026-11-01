@echo off
setlocal
cd /d "%~dp0frontend"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 20+ was not found. Install Node.js with npm enabled.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js with npm enabled.
  pause
  exit /b 1
)
if not exist "package-lock.json" (
  echo Generating the initial npm lockfile. Internet access is required once.
  call npm install --package-lock-only --ignore-scripts --no-audit --no-fund
  if errorlevel 1 goto :failed
  echo Lockfile generated at frontend\package-lock.json. Keep this file with the project.
)
if not exist "node_modules" (
  echo Installing frontend from package-lock.json...
  call npm ci --no-audit --no-fund
  if errorlevel 1 goto :failed
) else (
  call npm ls --depth=0 >nul 2>nul
  if errorlevel 1 (
    echo Existing frontend dependencies are inconsistent; reinstalling from lockfile...
    call npm ci --no-audit --no-fund
    if errorlevel 1 goto :failed
  )
)
call node scripts/verify-lockfile.mjs
if errorlevel 1 goto :failed
call npm run verify:shell
if errorlevel 1 goto :failed
call npm run verify:security-headers
if errorlevel 1 goto :failed
echo Starting LibraAI frontend at http://localhost:3000
call npm run dev
if errorlevel 1 goto :failed
exit /b 0
:failed
echo Frontend startup failed. Review the error above.
pause
exit /b 1
