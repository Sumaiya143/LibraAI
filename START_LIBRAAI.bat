@echo off
setlocal
cd /d "%~dp0"
echo Starting LibraAI backend and frontend in separate terminal windows...
start "LibraAI Backend" "%~dp0START_BACKEND.bat"
timeout /t 2 /nobreak >nul
start "LibraAI Frontend" "%~dp0START_FRONTEND.bat"
echo.
echo Backend:  http://127.0.0.1:5000
echo Frontend: http://localhost:3000
echo Stop each server by closing its terminal window.
echo This is a local development setup, not a production deployment.
pause
