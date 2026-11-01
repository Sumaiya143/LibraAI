@echo off
setlocal
cd /d "%~dp0frontend"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 20 or newer was not found. Install Node.js and enable PATH.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js with npm enabled.
  pause
  exit /b 1
)
if not exist node_modules (
  echo Installing frontend dependencies. An internet connection is required on first run...
  call npm install
  if errorlevel 1 (
    echo Dependency installation failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)
echo Checking shared page shell and navigation routes...
call npm run verify:shell
if errorlevel 1 (
  echo Page shell verification failed. Fix route/header mismatches before building.
  pause
  exit /b 1
)
echo Building the Next.js frontend...
call npm run build
if errorlevel 1 (
  echo Frontend build failed. Review the errors above before deploying.
  pause
  exit /b 1
)
echo Frontend build succeeded. Starting local development server...
call npm run dev
