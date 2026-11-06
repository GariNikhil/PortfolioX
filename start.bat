@echo off
setlocal
rem PortfolioX launcher.
rem Runs the app from whichever folder this file sits in, using the
rem virtual environment inside that folder. Moving or renaming the
rem project does not break the launcher.

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo.
    echo PortfolioX cannot start: no virtual environment was found.
    echo.
    echo   expected: %PYTHON%
    echo.
    echo Create it once from this folder, then run this file again:
    echo.
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

"%PYTHON%" app.py
set "CODE=%errorlevel%"

if not "%CODE%"=="0" (
    echo.
    echo PortfolioX exited with error code %CODE%.
    pause
    exit /b %CODE%
)

endlocal
