@echo off
REM ============================================================
REM  Tesla Rack Control - One-Click Installer
REM
REM  Email/Slack this single file to anyone you want to set up.
REM  They double-click it once. It downloads the latest installer
REM  from GitHub, runs it with their existing Python, and drops a
REM  "Tesla Rack Control" shortcut on the desktop.
REM
REM  Prerequisites: Python 3.9+ already installed (32-bit, with
REM  "Add Python to PATH" ticked). Internet connection.
REM
REM  After install, the SYS TEC USB-CAN driver still has to be
REM  installed from systec-electronic.com - that one is vendor
REM  proprietary so it cannot be auto-installed.
REM ============================================================

setlocal
title Tesla Rack Control - One-Click Installer

echo ============================================
echo  Tesla Rack Control - One-Click Installer
echo ============================================
echo.

set "TMP_PY=%TEMP%\tesla_rack_install.py"
set "INSTALLER_URL=https://raw.githubusercontent.com/dnage76-beep/tesla-rack-control/main/install_one_click.py"

REM --- Find Python ---------------------------------------------
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=py -3"
    goto have_python
)
where python >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=python"
    goto have_python
)

echo ERROR: Python is not on PATH.
echo.
echo Install 32-bit Python 3.9+ from https://www.python.org/
echo Tick "Add Python to PATH" during install, then re-run this file.
echo.
pause
exit /b 1

:have_python
echo Python found:
%PYCMD% --version
echo.

REM --- Download installer --------------------------------------
echo Downloading installer from GitHub...
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%INSTALLER_URL%' -OutFile '%TMP_PY%'"
if errorlevel 1 (
    echo.
    echo ERROR: Could not download the installer. Check your internet
    echo connection and try again.
    pause
    exit /b 1
)
echo.

REM --- Run installer -------------------------------------------
%PYCMD% "%TMP_PY%"
set "RC=%errorlevel%"

del /q "%TMP_PY%" >nul 2>&1

if not "%RC%"=="0" (
    echo.
    echo Installer exited with code %RC%.
    pause
    exit /b %RC%
)

endlocal
