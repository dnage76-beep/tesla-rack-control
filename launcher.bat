@echo off
REM Tesla Rack Control - double-click launcher.
REM Runs launcher.py with the system Python (32-bit Python is required
REM because USBCAN32.dll is 32-bit). The console stays open if the
REM launcher exits with an error so you can see what happened.

setlocal
cd /d "%~dp0"
title Tesla Rack Control

REM Prefer the Python launcher (py) which respects shebang lines and
REM is what comes with python.org installs on Windows. Fall back to
REM whatever "python" resolves to.
where py >nul 2>&1
if %errorlevel%==0 (
    py launcher.py %*
) else (
    python launcher.py %*
)

if errorlevel 1 (
    echo.
    echo Launcher exited with an error. Press any key to close.
    pause >nul
)

endlocal
