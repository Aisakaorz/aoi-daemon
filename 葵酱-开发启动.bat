@echo off
setlocal
cd /d "%~dp0" || exit /b 1
chcp 65001 >nul
title AoiDaemon - dev launcher

rem One-click dev entry: console stays open while running, closes on a clean exit.
rem All text here is ASCII on purpose; the bat itself must not depend on codepage.

set "PY=.venv\Scripts\python.exe"
set "ENTRY=main.py"

if not exist "%PY%" (
    echo [ERROR] Virtualenv Python not found: %CD%\%PY%
    echo         Create it with: python -m venv .venv
    echo         Then install:   .venv\Scripts\pip install -r requirements-windows.txt
    echo.
    pause
    exit /b 1
)
if not exist "%ENTRY%" (
    echo [ERROR] main.py not found in %CD%
    echo.
    pause
    exit /b 1
)

rem Match console codepage and Python stdio so Chinese logs and tracebacks stay readable.
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

echo ============================================================
echo  AoiDaemon dev launcher
echo  Workdir : %CD%
echo  Python  : %PY%
echo  Logs    : this window [stdout/stderr], plus logs\aoi.log
echo  Stop    : Ctrl+C, or close this window
echo ============================================================
echo.
"%PY%" --version
echo.
"%PY%" "%ENTRY%" %*
set "CODE=%ERRORLEVEL%"
rem Clean exit (e.g. quitting from the tray/menu): close the window immediately.
rem Only a non-zero exit keeps it open, so crash logs stay readable.
if "%CODE%"=="0" exit /b 0
echo.
echo ============================================================
echo  Exited with code %CODE%. Window kept open so you can read the error log.
echo ============================================================
pause
exit /b %CODE%
