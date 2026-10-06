@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1

where pwsh >nul 2>&1
if errorlevel 1 (
    echo PowerShell 7 ^(pwsh^) is required to start Pi.
    if "%~1"=="" pause
    exit /b 1
)

pwsh -NoProfile -File "%~dp0tools\pi-start.ps1" %*
set "pi_exit=%errorlevel%"
if not "%pi_exit%"=="0" (
    echo Pi exited with error %pi_exit%.
    if "%~1"=="" pause
)
exit /b %pi_exit%
