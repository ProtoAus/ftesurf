#!/bin/sh
# FTESurf launcher (Linux).
#   ./ftesurf.sh                  start the game
#   ./ftesurf.sh <map> [args...]  start on a map (as ftesurf.bat does)
#   ./ftesurf.sh --debug [...]    also log the console to ftesurf/logs (ftesurf_debug.bat)
#   ./ftesurf.sh -window +exec x  arguments starting with - or + go to the engine unchanged
# No set -e: each failure below is handled or deliberately ignored.

# stderr, plus a dialog when there is no terminal to read it (desktop launch).
# One tool only: zenity returns 1 when its dialog is closed, so a || chain stacks dialogs.
say() {
    printf 'ftesurf.sh: %s\n' "$1" >&2
    [ -t 2 ] && return
    if command -v zenity >/dev/null 2>&1; then zenity --warning --no-wrap --no-markup --text="$1"
    elif command -v kdialog >/dev/null 2>&1; then kdialog --sorry "$1"
    elif command -v xmessage >/dev/null 2>&1; then xmessage "$1"
    fi 2>/dev/null
}

# The engine takes its basedir from the working directory (sys_linux.c:1557-1582),
# so cd to this script's real folder, through any symlink pointing at it.
here=$(dirname -- "$(readlink -f -- "$0")") && cd -- "$here" || {
    echo "ftesurf.sh: cannot enter the folder this script is in" >&2; exit 1; }
if [ ! -f ./ftesurf64 ]; then
    say "$here/ftesurf64 is missing.
Extract the .tar.xz with tar or an archive manager."
    exit 1
elif [ ! -x ./ftesurf64 ]; then
    say "$here/ftesurf64 is not executable: extract with tar or an archive manager,
which keep the executable bit, onto a drive that allows running programs (not noexec or FAT)."
    exit 1
fi
# Everything the game saves goes inside this folder (default.fmf: DISABLEHOMEDIR 1).
if [ ! -w . ] || [ ! -w ftesurf ]; then
    say "FTESurf cannot write to $here,
so settings, runs and screenshots will not be saved.
Move the FTESurf folder somewhere you own, such as your home folder."
fi
# fs_addons.txt is untracked and rewritten by the engine; seed it from its annotated master.
[ -f ftesurf/fs_addons.txt ] || cp ftesurf/fs_addons.default.txt ftesurf/fs_addons.txt 2>/dev/null

debug=
if [ "${1-}" = --debug ]; then debug=1; shift; fi
case ${1-} in
    ''|-*|+*) ;;
    *) map=$1; shift; set -- "$@" +map "$map" ;;
esac
if [ -n "$debug" ]; then
    # log_dir on the command line too: -condebug opens the log before any cfg runs.
    set -- -condebug +set log_dir logs +set developer 1 "$@"
    echo "ftesurf.sh: console log: $here/ftesurf/logs/qconsole.log" >&2
fi

# Sys_Error (sys_linux.c:655) and crash backtraces print to stderr, which a desktop launch
# hides; append them to stderr.log. A crash also writes crash.log here (:1156).
log=stderr.log
if { [ -f "$log" ] && [ -w "$log" ]; } || { [ ! -e "$log" ] && [ -w . ]; }; then
    if [ -f "$log" ] && [ "$(wc -c < "$log")" -gt 1048576 ]; then mv -f -- "$log" "$log.1"; fi
    printf '=== %s  ftesurf.sh %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" >> "$log"
    if [ -t 2 ]; then
        echo "ftesurf.sh: engine errors go to $here/$log" >&2
        exec ./ftesurf64 "$@" 2>> "$log"
    fi
    # Desktop launch: no exec, so a failure the engine cannot report (old glibc, a crash,
    # no xmessage) still gets a dialog.  A normal quit is status 0.
    ./ftesurf64 "$@" 2>> "$log"
    rc=$?
    [ $rc -eq 0 ] || say "FTESurf stopped (status $rc).
See $here/$log and crash.log."
    exit $rc
fi
exec ./ftesurf64 "$@"
