@echo off
REM Tesla Rack Control - first-time setup (run from inside the repo).
REM
REM Most users should run Install_Tesla_Rack_Control.bat instead --
REM that one downloads the repo and then calls this script.
REM
REM Prerequisite: 32-bit Python 3.9+ from python.org with
REM   "Add Python to PATH" ticked. 32-bit is required because the
REM   SYS TEC USBCAN32.dll is 32-bit.
REM
REM This script:
REM   1. pip-installs requirements.txt
REM   2. creates a "Tesla Rack Control" shortcut on the desktop

setlocal
cd /d "%~dp0"
title Tesla Rack Control - Installer

echo ============================================
echo  Tesla Rack Control - setup
echo ============================================
echo.

REM --- Python check -----------------------------------------------
set "PYCMD="
where py >nul 2>&1
if %errorlevel%==0 set "PYCMD=py -3"
if not defined PYCMD (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYCMD=python"
)
if not defined PYCMD (
    echo ERROR: Python not found on PATH.
    echo Install 32-bit Python 3.9+ from https://www.python.org/
    echo and tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo Using Python:
%PYCMD% --version
echo.

REM --- Install Python deps ---------------------------------------
echo Installing Python dependencies...
%PYCMD% -m pip install --upgrade pip 2>nul
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
echo  Setup complete.
echo.
echo  Look for "Tesla Rack Control" on your desktop,
echo  or double-click launcher.bat in this folder.
echo.
echo  Updates are checked on every launch -- no git
echo  required. Files come from GitHub as a zip.
echo ============================================
echo.
pause
endlocal
