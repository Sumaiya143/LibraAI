@echo off
setlocal
cd /d "%~dp0"
call START_FRONTEND.bat
exit /b %errorlevel%
