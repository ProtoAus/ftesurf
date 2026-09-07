@echo off
REM FTESurf debug launcher -- mirrors the console to a flushed log so a
REM crash-on-load is captured.  developer 1 makes the load verbose, so the
REM LAST line before a crash names the asset or lump that killed it.
REM
REM log_dir is set HERE as well as in cfg/default.cfg, and that is not a
REM duplicate: -condebug opens the log before any config is exec'd, so without
REM it on the command line the first lines of the launch -- exactly the ones a
REM crash-on-load needs -- still land in the gamedir root.
cd /d "%~dp0"
echo Log: %~dp0ftesurf\logs\qconsole.log
if "%~1"=="" (
    ftesurf64.exe -condebug +set log_dir logs +set developer 1
) else (
    ftesurf64.exe -condebug +set log_dir logs +set developer 1 +map %1
)
echo.
pause
