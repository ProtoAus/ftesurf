@echo off
REM FTESurf launcher.
REM cd first: FTE takes basedir from the process CWD (sys_win.c:4787-4798),
REM not from the exe's directory, so launching from elsewhere finds no gamedir.
cd /d "%~dp0"
REM fs_addons.txt is not tracked: the engine rewrites it from its in-memory
REM mount list on fs_load/fs_unload and strips every comment out of it.  The
REM annotated master is fs_addons.default.txt; seed from it on a fresh clone.
if not exist "ftesurf\fs_addons.txt" copy /y "ftesurf\fs_addons.default.txt" "ftesurf\fs_addons.txt" >nul
if "%~1"=="" (
    ftesurf64.exe
) else (
    ftesurf64.exe +map %1
)
