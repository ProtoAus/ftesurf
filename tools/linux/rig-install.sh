#!/bin/bash
# Assemble a Linux install on ext4 for tests, as user surf in the Debian rig distro:
#   bash rig-install.sh <build dir with fteqw64 + fteplug_hl2_amd64.so> <install dir>
# Game files come from the newest release stage (release/stage-*), cfg/test from the tree.
set -eu
B=${1:?build dir}; D=${2:?install dir}
T=/mnt/c/FTESurf
STAGE=$(ls -d $T/release/stage-0.* | sort -V | tail -1)
rm -rf "$D" && mkdir -p "$D"
cp -r "$STAGE/ftesurf" "$STAGE/default.fmf" "$D/"
rm -f "$D"/*.exe "$D"/*.dll "$D"/*.bat
cp "$B/fteqw64" "$D/ftesurf64" && cp "$B/fteplug_hl2_amd64.so" "$D/"
[ -f "$B/fteqw-sv64" ] && cp "$B/fteqw-sv64" "$D/"
chmod 0755 "$D/ftesurf64" "$D"/fteqw-sv64 2>/dev/null || chmod 0755 "$D/ftesurf64"
cp $T/ftesurf/cfg/default.cfg "$D/ftesurf/cfg/"	# the tree's, which may be newer than the stage's
mkdir -p "$D/ftesurf/cfg/test" && cp $T/ftesurf/cfg/test/p38[6-9]*.cfg $T/ftesurf/cfg/test/p322det.cfg "$D/ftesurf/cfg/test/" 2>/dev/null || true
[ -f $T/ftesurf.sh ] && cp $T/ftesurf.sh "$D/" && chmod 0755 "$D/ftesurf.sh"
echo "rig-install: $D from $(basename "$STAGE") + $(sed -n 's/^revision *//p' "$B/BUILDINFO.txt" 2>/dev/null)"
