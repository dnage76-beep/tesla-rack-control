@echo off
REM ============================================================
REM  Tesla Rack Control - One-Click Installer (self-contained)
REM
REM  Email/Slack this single file to anyone you want to set up.
REM  They double-click it once. It downloads the latest version
REM  of Tesla Rack Control from GitHub, extracts to
REM  %USERPROFILE%\TeslaRackControl, runs pip install, and drops
REM  a "Tesla Rack Control" shortcut on the desktop.
REM
REM  Network: only needs codeload.github.com and api.github.com,
REM  both of which are reachable from any network where GitHub
REM  itself works in a browser.
REM
REM  Prerequisites:
REM   - Python 3.9+ already installed (32-bit, with "Add Python
REM     to PATH" ticked).
REM
REM  After install, the SYS TEC USB-CAN driver still has to be
REM  installed by hand from systec-electronic.com - that one is
REM  vendor-proprietary so it cannot be auto-installed.
REM
REM  If Windows SmartScreen flags this file:
REM    "More info" -> "Run anyway"
REM ============================================================

setlocal enabledelayedexpansion
title Tesla Rack Control - One-Click Installer

set "REPO_OWNER=dnage76-beep"
set "REPO_NAME=tesla-rack-control"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\TeslaRackControl"
set "ZIP_URL=https://codeload.github.com/%REPO_OWNER%/%REPO_NAME%/zip/refs/heads/%BRANCH%"
set "API_URL=https://api.github.com/repos/%REPO_OWNER%/%REPO_NAME%/commits/%BRANCH%"

echo.
echo ============================================
echo  Tesla Rack Control - One-Click Installer
echo ============================================
echo.
echo Install location: %INSTALL_DIR%
echo.

REM --- Locate Python ----------------------------------------------
set "PYCMD="
where py >nul 2>&1
if %errorlevel%==0 set "PYCMD=py -3"
if not defined PYCMD (
    where python >nul 2>&1
    if %errorlevel%==0 set "PYCMD=python"
)
if not defined PYCMD (
    echo ERROR: Python is not on PATH.
    echo.
    echo Install 32-bit Python 3.9+ from https://www.python.org/
    echo Tick "Add Python to PATH" during install, then re-run.
    echo.
    pause
    exit /b 1
)
echo Python:
%PYCMD% --version
echo.

REM --- Download + extract via PowerShell --------------------------
REM Done in PowerShell so we don't depend on Python being able to
REM reach the internet (the user's pip mirror config is unknown).
echo Downloading and extracting from GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ErrorActionPreference='Stop';" ^
"try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { };" ^
"$zip = Join-Path $env:TEMP ('trc_' + [guid]::NewGuid().ToString('N') + '.zip');" ^
"$tmp = Join-Path $env:TEMP ('trc_extract_' + [guid]::NewGuid().ToString('N'));" ^
"Write-Host '  fetching zip from codeload.github.com...';" ^
"try {" ^
"  Invoke-WebRequest -UseBasicParsing -Uri '%ZIP_URL%' -OutFile $zip" ^
"} catch {" ^
"  Write-Host '  Invoke-WebRequest failed, trying curl...';" ^
"  & curl.exe -fsSL -o $zip '%ZIP_URL%';" ^
"  if ($LASTEXITCODE -ne 0) { throw 'Both Invoke-WebRequest and curl failed.' }" ^
"};" ^
"Write-Host '  expanding archive...';" ^
"if (Get-Command Expand-Archive -ErrorAction SilentlyContinue) {" ^
"  Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force" ^
"} else {" ^
"  Add-Type -AssemblyName System.IO.Compression.FileSystem;" ^
"  [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)" ^
"};" ^
"$src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName;" ^
"if (-not (Test-Path '%INSTALL_DIR%')) { New-Item -ItemType Directory -Path '%INSTALL_DIR%' -Force ^| Out-Null };" ^
"Write-Host '  copying files into install location...';" ^
"$preserve = @('logs','field_testing\\sessions','field_testing\\captures');" ^
"foreach ($item in (Get-ChildItem $src -Force)) {" ^
"  $rel = $item.Name;" ^
"  $skip = $false;" ^
"  foreach ($p in $preserve) { if ($rel -eq ($p -split '\\\\')[0]) { $skip = $true } };" ^
"  if ($skip -and (Test-Path (Join-Path '%INSTALL_DIR%' $rel))) { continue };" ^
"  Copy-Item -Path $item.FullName -Destination '%INSTALL_DIR%' -Recurse -Force" ^
"};" ^
"Remove-Item $zip,$tmp -Recurse -Force -ErrorAction SilentlyContinue;" ^
"Write-Host '  done.'"

if errorlevel 1 (
    echo.
    echo ERROR: Download or extract failed.
    echo.
    echo Common causes:
    echo   - No internet, corporate proxy blocking GitHub.
    echo   - Antivirus quarantining downloaded zip.
    echo   - Out of disk space on %%TEMP%%.
    echo.
    echo Manual fallback:
    echo   1. Open https://github.com/%REPO_OWNER%/%REPO_NAME%
    echo      in your browser and click "Code" -^> "Download ZIP".
    echo   2. Extract it to %INSTALL_DIR%.
    echo   3. Double-click install.bat inside that folder.
    echo.
    pause
    exit /b 1
)
echo.

REM --- Run install.bat from inside the extracted folder -----------
echo Running install.bat from inside %INSTALL_DIR%...
echo.
pushd "%INSTALL_DIR%"
call install.bat
set "RC=%errorlevel%"
popd

if not "%RC%"=="0" (
    echo.
    echo install.bat exited with code %RC%.
    pause
    exit /b %RC%
)

REM --- Write .version (commit SHA) so the launcher's update    ---
REM --- check has a baseline. If this fails the launcher will   ---
REM --- treat the install as "first run" and just record the    ---
REM --- current SHA on next launch.                             ---
echo Recording version stamp...
%PYCMD% -c "import urllib.request,json,sys,os; req=urllib.request.Request('%API_URL%', headers={'User-Agent':'trc-installer','Accept':'application/vnd.github+json'}); sha=json.load(urllib.request.urlopen(req,timeout=15))['sha']; open(os.path.join(r'%INSTALL_DIR%','.version'),'w').write(sha); print('  installed', sha[:7])" 2>nul
if errorlevel 1 (
    echo   (could not reach GitHub API -- launcher will detect on next start^)
)
echo.

echo ============================================
echo  Install complete.
echo.
echo  Look for "Tesla Rack Control" on your desktop.
echo.
echo  REMINDER: install the SYS TEC USB-CAN driver from
echo  https://www.systec-electronic.com/en/services-support/downloads
echo  if it isn't already on this machine.
echo ============================================
echo.
pause
endlocal
