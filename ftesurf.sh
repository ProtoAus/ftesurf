#!/bin/sh
# FTESurf startup (Linux): signed-update bootstrap, or engine-only if absent.
#   ./ftesurf.sh                  start the game
#   ./ftesurf.sh <map> [args...]  start on a map (as ftesurf.bat does)
#   ./ftesurf.sh --debug [...]    also log the console to ftesurf/logs (ftesurf_debug.bat)
#   ./ftesurf.sh -window +map x   options starting with - or +: WOS-Launcher forwards only +map, +connect,
#                                 -window, -fullscreen, -width, -height and --debug's -condebug,
#                                 +set log_dir logs, +set developer 1 (engine-only fallback: all)
#   WOS_NO_DESKTOP=1 ./ftesurf.sh  do not write the menu entry and icons (desktop_entry below)
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

# The engine names its window worldofsurf (Wayland app_id, X11 WM_CLASS); taskbars take the icon from the
# .desktop file of that name. Writes it and the hicolor icons when their content differs. An existing entry
# is replaced only when its Exec runs this install or a program that no longer exists (a moved install);
# another install's, a wrapper's (gamescope, flatpak) or a symlinked entry is left alone.
desktop_entry() (
    case ${XDG_DATA_HOME-} in /*) data=$XDG_DATA_HOME ;; *) [ -n "${HOME-}" ] || return; data=$HOME/.local/share ;; esac
    icons=ftesurf/gfx/icons
    [ -f "$icons/worldofsurf-256.png" ] || return
    case $here in *[\"\`\$\\%]*|*'
'*) return ;; esac  # no Exec escaping needed in what is left
    changed=
    for n in 48 64 128 256 512; do
        src=$icons/worldofsurf-$n.png dir=$data/icons/hicolor/${n}x$n/apps
        [ -f "$src" ] || continue
        [ -f "$dir/worldofsurf.png" ] && [ "$(cksum < "$src")" = "$(cksum < "$dir/worldofsurf.png")" ] && continue
        mkdir -p -- "$dir" && cp -- "$src" "$dir/.worldofsurf.png.$$" && mv -f -- "$dir/.worldofsurf.png.$$" "$dir/worldofsurf.png" && changed=1
    done
    # GTK ignores a user icon-theme.cache older than its theme folder.
    [ -n "$changed" ] && touch -- "$data/icons/hicolor"
    entry=$data/applications/worldofsurf.desktop
    [ -L "$entry" ] && return
    if [ -f "$entry" ]; then
        old=$(sed -n 's/^Exec=//p' "$entry" | head -n 1)
        case $old in \"*) old=${old#\"}; old=${old%%\"*} ;; *) old=${old%% *} ;; esac
        case $old in */*) ;; ?*) old=$(command -v "$old") || old= ;; esac
        if [ -n "$old" ] && [ -e "$old" ] && [ "$(readlink -f -- "$old")" != "$self" ]; then
            [ -t 2 ] && printf 'ftesurf.sh: %s starts %s; left as it is\n' "$entry" "$old" >&2
            return
        fi
    fi
    want="[Desktop Entry]
Type=Application
Name=World of Surf
GenericName=Surf and bhop
Exec=\"$self\"
Path=$here
Icon=worldofsurf
Terminal=false
Categories=Game;
StartupWMClass=worldofsurf"
    [ "$(cat -- "$entry" 2>/dev/null)" = "$want" ] && return
    mkdir -p -- "$data/applications" && printf '%s\n' "$want" > "$entry.$$" && mv -f -- "$entry.$$" "$entry" || rm -f -- "$entry.$$"
)

# The engine takes its basedir from the working directory (sys_linux.c:1557-1582),
# so cd to this script's real folder, through any symlink pointing at it.
self=$(readlink -f -- "$0") && here=$(dirname -- "$self") && cd -- "$here" || {
    echo "ftesurf.sh: cannot enter the folder this script is in" >&2; exit 1; }
runner=./ftesurf64
# P1209: the launcher is WOS-Launcher; an install from before it has ftesurf-launcher.
launcher=
for l in ./WOS-Launcher ./ftesurf-launcher; do
    if [ -e "$l" ] || [ -L "$l" ]; then launcher=$l; break; fi
done
if [ -n "$launcher" ]; then
    if [ -L "$launcher" ] || [ ! -f "$launcher" ] || [ ! -x "$launcher" ]; then
        say "$here/${launcher#./} is not executable (or is a link).
Extract the official archive onto a drive that allows running programs."
        exit 1
    fi
    runner=$launcher
elif [ ! -f ./ftesurf64 ]; then
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
    say "World of Surf cannot write to $here,
so settings, runs and screenshots will not be saved.
Move the FTESurf folder somewhere you own, such as your home folder."
fi
# fs_addons.txt is untracked and rewritten by the engine; seed it from its annotated master.
[ -f ftesurf/fs_addons.txt ] || cp ftesurf/fs_addons.default.txt ftesurf/fs_addons.txt 2>/dev/null
case ${WOS_NO_DESKTOP-} in ''|0) desktop_entry ;; esac

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

# Do not bypass a present bootstrap after a failure; it may be refusing a bad update.
if [ "$runner" != ./ftesurf64 ]; then
    # First desktop start has no terminal for consent; play without a check.
    # Leave permission unset so Play online in the game can ask for opt-in.
    if [ ! -t 0 ] && [ ! -e ./.ftesurf-updater/consent ] && [ ! -L ./.ftesurf-updater/consent ]; then
        set -- --offline -- "$@"
    else
        set -- -- "$@"
    fi
fi

# Sys_Error (sys_linux.c:655) and crash backtraces print to stderr, which a desktop launch
# hides; append them to stderr.log. A crash also writes crash.log here (:1156).
log=stderr.log
if { [ -f "$log" ] && [ -w "$log" ]; } || { [ ! -e "$log" ] && [ -w . ]; }; then
    if [ -f "$log" ] && [ "$(wc -c < "$log")" -gt 1048576 ]; then mv -f -- "$log" "$log.1"; fi
    printf '=== %s  ftesurf.sh %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" >> "$log"
    if [ -t 2 ]; then
        echo "ftesurf.sh: engine errors go to $here/$log" >&2
        exec "$runner" "$@" 2>> "$log"
    fi
    # Desktop launch: no exec, so a failure the engine cannot report (old glibc, a crash,
    # no xmessage) still gets a dialog.  A normal quit is status 0.
    "$runner" "$@" 2>> "$log"
    rc=$?
    [ $rc -eq 0 ] || say "World of Surf stopped (status $rc).
See $here/$log and crash.log."
    exit $rc
fi
exec "$runner" "$@"
