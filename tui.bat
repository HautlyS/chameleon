@echo off
REM Chameleon Job TUI — launcher script (Windows)
setlocal enabledelayedexpansion

set "CHAMELEON_DIR=%~dp0"
set "VENV_PYTHON=%CHAMELEON_DIR%.venv\Scripts\python.exe"

if /I "%1"=="--help" goto :help
if /I "%1"=="-h" goto :help
if /I "%1"=="--version" goto :version

if not exist "%VENV_PYTHON%" (
    echo [!] Virtual environment not found at %VENV_PYTHON%
    echo     Run: make install-tools
    echo     Or: python -m venv .venv ^&^& .venv\Scripts\pip install textual pyyaml pypdf reportlab httpx beautifulsoup4 lxml markdownify
    pause
    exit /b 1
)

cd /d "%CHAMELEON_DIR%"
"%VENV_PYTHON%" -m scripts.tui_app %*
exit /b %errorlevel%

:help
echo Chameleon Job TUI — scan, score, tailor, and diff
echo.
echo Usage:  tui.bat [options]
echo.
echo Options:
echo   --help, -h    Show this help message
echo   --version     Show version info
echo.
echo Keybindings inside the TUI:
echo   Ctrl+S    Scan job platforms
echo   Ctrl+N    Paste a job description
echo   Ctrl+E    Edit selected job
echo   Ctrl+T    Tailor CV for selected job
echo   Ctrl+R    Rescore all jobs
echo   Ctrl+D    Delete selected job
echo   Ctrl+O    Open job URL in browser
echo   /         Search jobs
echo   F1        Help screen
echo   Ctrl+Q    Quit
echo   Ctrl+1-6  Switch tabs
echo.
exit /b 0

:version
echo Chameleon Job TUI v1.0
exit /b 0
