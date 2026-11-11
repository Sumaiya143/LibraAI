@echo off
setlocal
cd /d "%~dp0"
call START_BACKEND.bat
exit /b %errorlevel%
