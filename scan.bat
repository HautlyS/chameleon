@echo off
setlocal
set "CHAMELEON_DIR=%~dp0"
cd /d "%CHAMELEON_DIR%"
set "VENV_PYTHON=%CHAMELEON_DIR%.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=python"
"%VENV_PYTHON%" -m scripts.job_scanner.scanner %*
exit /b %errorlevel%
