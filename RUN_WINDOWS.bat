@echo off
setlocal
cd /d "%~dp0"
call START_LIBRAAI.bat
exit /b %errorlevel%
