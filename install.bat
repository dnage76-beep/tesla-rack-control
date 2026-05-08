@echo off
REM Tesla Rack Control - first-time setup.
REM
REM Prerequisites you have to do by hand BEFORE running this:
REM   1. Install 32-bit Python 3.9+ from python.org and tick
REM      "Add Python to PATH". 32-bit is required because the
REM      SYS TEC USBCAN32.dll is 32-bit.
REM   2. Install Git for Windows from git-scm.com (so the auto-
REM      updater works).
REM   3. Install the SYS TEC sysWORXX USB-CAN driver from
REM      https://www.systec-electronic.com/en/services-support/downloads
REM   4. Clone this repo somewhere stable, e.g.
REM      git clone https://github.com/dnage76-beep/tesla-rack-control
REM
REM Then double-click this file.

setlocal
cd /d "%~dp0"
title Tesla Rack Control - Installer

echo ============================================
echo  Tesla Rack Control - first-time setup
echo ============================================
echo.

REM --- Python check -----------------------------------------------
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=py"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYCMD=python"
    ) else (
        echo ERROR: Python not found on PATH.
        echo Install 32-bit Python 3.9+ from https://www.python.org/
        echo and tick "Add Python to PATH" during install.
        echo.
        pause
        exit /b 1
    )
)

echo Using Python:
%PYCMD% --version
echo.

REM --- Git check --------------------------------------------------
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: git is not on PATH. The auto-updater needs git.
    echo Install Git for Windows from https://git-scm.com/ then
    echo re-run this installer. Continuing anyway in case you only
    echo want to run the program once without updates.
    echo.
)

REM --- Install Python deps ---------------------------------------
echo Installing Python dependencies (python-can, etc.)...
%PYCMD% -m pip install --upgrade pip
if errorlevel 1 (
    echo WARNING: pip upgrade failed, continuing.
)
%PYCMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. See messages above.
    pause
    exit /b 1
)
echo.

REM --- Desktop shortcut ------------------------------------------
echo Creating desktop shortcut...
%PYCMD% make_shortcut.py
if errorlevel 1 (
    echo WARNING: shortcut creation failed. You can still launch
    echo the program by double-clicking launcher.bat in this folder.
)
echo.

echo ============================================
echo  Done.
echo.
echo  Look for "Tesla Rack Control" on your desktop,
echo  or double-click launcher.bat in this folder.
echo.
echo  The app will check GitHub for updates each time
echo  it starts and offer to pull the latest version.
echo ============================================
echo.
pause
endlocal
