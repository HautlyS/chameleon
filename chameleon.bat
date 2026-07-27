@echo off
setlocal enabledelayedexpansion

REM Chameleon CLI — unified entry point for Windows
set "CHAMELEON_DIR=%~dp0"
set "VENV_PYTHON=%CHAMELEON_DIR%.venv\Scripts\python.exe"

REM Resolve Python
set "PYTHON_BIN="
if exist "%VENV_PYTHON%" (
    set "PYTHON_BIN=%VENV_PYTHON%"
) else (
    where python >nul 2>&1 && set "PYTHON_BIN=python"
)

if "%PYTHON_BIN%"=="" (
    echo [!] No Python found. Install Python 3.10+ and run: make install-tools
    exit /b 1
)

if "%~1"=="" goto :help
if /I "%~1"=="help" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--version" goto :version
if /I "%~1"=="-v" goto :version

if /I "%~1"=="tailor" goto :tailor
if /I "%~1"=="tailor-cv" goto :tailor
if /I "%~1"=="score" goto :score
if /I "%~1"=="score-cv" goto :score
if /I "%~1"=="match" goto :score
if /I "%~1"=="scan" goto :scan
if /I "%~1"=="scan-jobs" goto :scan
if /I "%~1"=="cover" goto :cover
if /I "%~1"=="cover-letter" goto :cover
if /I "%~1"=="render" goto :render
if /I "%~1"=="init" goto :init
if /I "%~1"=="init-cv" goto :init
if /I "%~1"=="tui" goto :tui

echo Unknown command: %~1
echo Run 'chameleon help' for usage.
exit /b 1

REM ════════════════════════════════════════════════════════════════════════
REM  TAILOR
REM ════════════════════════════════════════════════════════════════════════
:tailor
shift
set "JD_INPUT="
set "COMPANY="
set "TITLE="
set "EXTRA_ARGS="

:tailor_parse
if "%~1"=="" goto :tailor_run
if /I "%~1"=="--company" (
    set "COMPANY=%~2"
    shift & shift
    goto :tailor_parse
)
if /I "%~1"=="--title" (
    set "TITLE=%~2"
    shift & shift
    goto :tailor_parse
)
if /I "%~1"=="--no-review" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --no-review"
    shift
    goto :tailor_parse
)
if /I "%~1"=="--no-render" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --no-render"
    shift
    goto :tailor_parse
)
if /I "%~1"=="--json" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --json"
    shift
    goto :tailor_parse
)
if /I "%~1"=="--cv" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --cv %~2"
    shift & shift
    goto :tailor_parse
)
if "%~1"=="-" (
    echo Unknown option: %~2
    exit /b 1
)
set "JD_INPUT=%~1"
shift
goto :tailor_parse

:tailor_run
if "%JD_INPUT%"=="" (
    echo Error: No job description provided.
    echo Usage: chameleon tailor ^<jd_text_or_url_or_file^> [--company X] [--title Y]
    exit /b 1
)

REM Check if input is a URL and crawl it
echo %JD_INPUT% | findstr /R "^https*://" >nul 2>&1
if %errorlevel%==0 (
    echo [*] Crawling URL: %JD_INPUT%
    for /f "delims=" %%i in ('"%PYTHON_BIN%" -c "import sys; import httpx; r=httpx.get('%JD_INPUT%',timeout=30,follow_redirects=True,headers={'User-Agent':'Mozilla/5.0'}); text=r.text; import re; text=re.sub(r'<script[^>]*>.*?</script>','',text,flags=re.DOTALL|re.IGNORECASE); text=re.sub(r'<style[^>]*>.*?</style>','',text,flags=re.DOTALL|re.IGNORECASE); text=re.sub(r'<[^>]+>',' ',text); import html; text=html.unescape(text); text=re.sub(r'\s+',' ',text).strip(); print(text[:10000])" 2^>nul') do set "JD_TEXT=%%i"
    if "!JD_TEXT!"=="" (
        echo Error: Failed to crawl URL
        exit /b 1
    )
    goto :tailor_exec
)

REM Check if input is a file
if exist "%JD_INPUT%" (
    set /p JD_TEXT=<"%JD_INPUT%"
) else (
    set "JD_TEXT=%JD_INPUT%"
)

:tailor_exec
cd /d "%CHAMELEON_DIR%"
"%PYTHON_BIN%" -m scripts.tailor_cv "%JD_TEXT%" --company "%COMPANY%" --title "%TITLE%" %EXTRA_ARGS%
exit /b %errorlevel%

REM ════════════════════════════════════════════════════════════════════════
REM  SCORE
REM ════════════════════════════════════════════════════════════════════════
:score
shift
set "JD_INPUT="
set "EXTRA_ARGS="

:score_parse
if "%~1"=="" goto :score_run
if /I "%~1"=="--cv" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --cv %~2"
    shift & shift
    goto :score_parse
)
if /I "%~1"=="--json" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --json"
    shift
    goto :score_parse
)
set "JD_INPUT=%~1"
shift
goto :score_parse

:score_run
if "%JD_INPUT%"=="" (
    echo Error: No job description provided.
    echo Usage: chameleon score ^<jd_text_or_url_or_file^> [--cv path] [--json]
    exit /b 1
)

cd /d "%CHAMELEON_DIR%"
"%PYTHON_BIN%" -m scripts.job_matcher "%JD_INPUT%" %EXTRA_ARGS%
exit /b %errorlevel%

REM ════════════════════════════════════════════════════════════════════════
REM  SCAN
REM ════════════════════════════════════════════════════════════════════════
:scan
shift
cd /d "%CHAMELEON_DIR%"
set "SCAN_ARGS="
:scan_parse
if "%~1"=="" goto :scan_run
set "SCAN_ARGS=!SCAN_ARGS! %~1"
shift
goto :scan_parse
:scan_run
"%PYTHON_BIN%" -m scripts.job_scanner.scanner %SCAN_ARGS%
exit /b %errorlevel%

REM ════════════════════════════════════════════════════════════════════════
REM  COVER
REM ════════════════════════════════════════════════════════════════════════
:cover
shift
echo [*] Cover letter generation requires an AI assistant.
echo     Use: opencode  then  /cover-letter ^<url-or-text^>
exit /b 0

REM ════════════════════════════════════════════════════════════════════════
REM  RENDER
REM ════════════════════════════════════════════════════════════════════════
:render
shift
if "%~1"=="" (
    echo Error: No YAML path provided.
    echo Usage: chameleon render ^<yaml_path^>
    exit /b 1
)
cd /d "%CHAMELEON_DIR%"
"%PYTHON_BIN%" scripts/render.py %~1
exit /b %errorlevel%

REM ════════════════════════════════════════════════════════════════════════
REM  INIT
REM ════════════════════════════════════════════════════════════════════════
:init
shift
echo [*] CV initialization requires an AI assistant.
echo     Use: opencode  then  /init-cv %~1
exit /b 0

REM ════════════════════════════════════════════════════════════════════════
REM  TUI
REM ════════════════════════════════════════════════════════════════════════
:tui
shift
cd /d "%CHAMELEON_DIR%"
call tui.bat %*
exit /b %errorlevel%

REM ════════════════════════════════════════════════════════════════════════
REM  HELP
REM ════════════════════════════════════════════════════════════════════════
:help
echo Chameleon CLI — AI Resume Tailor
echo.
echo Usage:
echo   chameleon tailor ^<jd_text_or_url_or_file^> [options]   Tailor CV for a job
echo   chameleon score ^<jd_text_or_url_or_file^> [options]   Score job match
echo   chameleon scan  [options]                            Scan job platforms
echo   chameleon cover ^<jd_text_or_url_or_file^> [options]   Generate cover letter
echo   chameleon render ^<yaml_path^>                         Render YAML to PDF
echo   chameleon init ^<pdf_or_yaml_path^>                    Import master CV
echo   chameleon tui                                        Launch the TUI
echo   chameleon help                                       Show this help
echo.
echo TAILOR options:
echo   --company ^<name^>      Company name (auto-detected if omitted)
echo   --title ^<role^>        Role title (auto-detected if omitted)
echo   --no-review           Skip AI review pass
echo   --no-render           Skip PDF rendering
echo   --cv ^<path^>           Master CV path
echo   --json                Output JSON instead of text
echo.
echo SCORE options:
echo   --cv ^<path^>           CV path to score against
echo   --json                Output JSON
echo.
echo SCAN options:
echo   -q, --query ^<query^>   Search keywords
echo   -p, --platforms ^<list^> Comma-separated platforms
echo   -a, --all             Scan all platforms
echo   --tier1               Tier 1 platforms only
echo   -n, --limit ^<n^>       Max jobs per platform (default: 25)
echo   -o, --output ^<file^>   Save results to JSON file
echo   --json                Output JSON
echo.
echo INPUT:
echo   ^<text^>                Job description text in quotes
echo   ^<url^>                 Job posting URL (will be crawled)
echo   ^<file^>                Path to a text file with the JD
echo.
echo EXAMPLES:
echo   chameleon tailor "Senior Rust Engineer at Acme..." --company Acme
echo   chameleon tailor https://jobs.example.com/senior-rust
echo   chameleon score "Python developer, Django, PostgreSQL..."
echo   chameleon scan -q "rust engineer" --tier1 --json
echo   chameleon render templates\david_acme_rust_engineer_cv.yaml
echo.
exit /b 0

:version
echo Chameleon CLI v1.0
exit /b 0
