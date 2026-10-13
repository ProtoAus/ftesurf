@echo off
REM FTESurf startup: signed-update bootstrap when present, engine-only fallback.
REM cd first: FTE takes basedir from the process CWD (sys_win.c:4787-4798),
REM not from the exe's directory, so launching from elsewhere finds no gamedir.
cd /d "%~dp0"
REM fs_addons.txt is not tracked: the engine rewrites it from its in-memory
REM mount list on fs_load/fs_unload and strips every comment out of it.  The
REM annotated master is fs_addons.default.txt; seed from it on a fresh clone.
if not exist "ftesurf\fs_addons.txt" copy /y "ftesurf\fs_addons.default.txt" "ftesurf\fs_addons.txt" >nul
setlocal DisableDelayedExpansion
set "runner=ftesurf64.exe"
set "handoff="
if exist "ftesurf-launcher.exe" (
    set "runner=ftesurf-launcher.exe"
    set "handoff=--"
    REM No consent and no terminal: play without a bootstrap check; don't save permission.
    if not exist ".ftesurf-updater\consent" (
        "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "if ([Console]::IsInputRedirected) { exit 1 }"
        if errorlevel 1 set "handoff=--offline --"
    )
)
REM A failed bootstrap must NOT bypass its update/signature/lock refusal.
REM Preserve the map shortcut, but pass option-first invocations unchanged.
set "first=%~1"
if not defined first goto args
if "%first:~0,1%"=="-" goto args
if "%first:~0,1%"=="+" goto args
"%runner%" %handoff% +map %*
exit /b %errorlevel%
:args
"%runner%" %handoff% %*
exit /b %errorlevel%
