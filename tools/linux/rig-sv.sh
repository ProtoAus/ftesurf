#!/bin/bash
# Run the Linux dedicated server in a rig install, as user surf in the Debian rig distro:
#   bash rig-sv.sh <install dir> <log_name> [engine args...]
# Adds -nohome, sv_public 0, the log cvars and cfg_save_auto 0; stdin is /dev/null.
# The log, .stdout and .env are copied to C:\FTESurf\ftesurf\logs\linux\ as rig-run.sh does.
set -u
D=${1:?install}; NAME=${2:?log name}; shift 2
cd "$D" || exit 1
rm -f "ftesurf/logs/$NAME.log"
timeout 180 ./fteqw-sv64 -nohome +set sv_public 0 +set log_enable 1 +set log_dir logs +set log_name "$NAME" +set cfg_save_auto 0 "$@" > "/tmp/$NAME.stdout" 2>&1 < /dev/null
RC=$?
OUT=/mnt/c/FTESurf/ftesurf/logs/linux; mkdir -p "$OUT"
cp "ftesurf/logs/$NAME.log" "$OUT/" 2>/dev/null
cp "/tmp/$NAME.stdout" "$OUT/$NAME.stdout"
{ echo "server rc $RC"; echo "args $*"; echo "user $(id -un) uid $(id -u)"; uname -r; (. /etc/os-release; echo "$PRETTY_NAME");
  sha256sum fteqw-sv64 | cut -c1-16; grep -a -o -m1 'git-[0-9]*-[A-Za-z0-9._-]*' fteqw-sv64; } > "$OUT/$NAME.env"
echo "rig-sv: $NAME rc=$RC"
exit $RC
