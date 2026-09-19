#!/bin/bash
# Run the Linux client in a rig install, as user surf in the Debian rig distro:
#   bash rig-run.sh <install dir> x11|wayland|default <log_name> <cfg> [engine args...]
# x11 hides Wayland from the engine; wayland hides X11 and asks for the Wayland renderer.
# The log and an .env sidecar are copied to C:\FTESurf\ftesurf\logs\linux\.
set -u
D=${1:?install}; MODE=${2:?mode}; NAME=${3:?log name}; CFG=${4:?cfg}; shift 4
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}
case $MODE in
	x11)     ENVS="env -u WAYLAND_DISPLAY DISPLAY=${DISPLAY:-:0} XDG_SESSION_TYPE=x11"; EXTRA="" ;;
	wayland) ENVS="env -u DISPLAY WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} XDG_SESSION_TYPE=wayland"; EXTRA="+set vid_renderer wayland" ;;
	default) ENVS="env DISPLAY=${DISPLAY:-:0} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}"; EXTRA="" ;;
	*) echo "rig-run: mode x11|wayland|default" >&2; exit 2 ;;
esac
cd "$D" || exit 1
rm -f "ftesurf/logs/$NAME.log"
$ENVS timeout 180 ./ftesurf64 -nohome +set log_enable 1 +set log_dir logs +set log_name "$NAME" +set cfg_save_auto 0 $EXTRA "$@" +exec "$CFG" > "/tmp/$NAME.stdout" 2>&1
RC=$?
OUT=/mnt/c/FTESurf/ftesurf/logs/linux; mkdir -p "$OUT"
cp "ftesurf/logs/$NAME.log" "$OUT/" 2>/dev/null
cp "/tmp/$NAME.stdout" "$OUT/$NAME.stdout"
{ echo "mode $MODE rc $RC"; echo "user $(id -un) uid $(id -u)"; uname -r; (. /etc/os-release; echo "$PRETTY_NAME");
  sha256sum ftesurf64 | cut -c1-16; grep -a -o -m1 'git-[0-9]*-[A-Za-z0-9._-]*' ftesurf64; } > "$OUT/$NAME.env"
echo "rig-run: $NAME rc=$RC"
exit $RC
