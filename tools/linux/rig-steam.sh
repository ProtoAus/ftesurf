#!/bin/bash
# Patch 386 Steam-path arms, as user surf in the Debian rig:  bash rig-steam.sh <install dir> <tag>
# Each arm gets a fresh HOME holding exactly one Steam layout's libraryfolders.vdf, pointing at a
# fake library with the three fs_addons.txt games; `fs_steamlibs` shows which layouts resolve.
set -u
D=${1:?install}; TAG=${2:?tag}
R=/home/surf/steamrig; rm -rf "$R"; mkdir -p "$R"
LIB=$R/lib/steamapps/common
for g in "Momentum Mod Playtest/momentum" "Counter-Strike Source/cstrike" "Half-Life 2/hl2"; do
	mkdir -p "$LIB/$g" && echo fake > "$LIB/$g/readme.txt"
done
vdf() { mkdir -p "$1"; printf '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' "$R/lib" > "$1/libraryfolders.vdf"; }
vdf "$R/plain/.steam/steam/steamapps"
vdf "$R/snap/snap/steam/common/.local/share/Steam/steamapps"
vdf "$R/deb/.steam/debian-installation/steamapps"
vdf "$R/xdg/xdgdata/Steam/steamapps"
mkdir -p "$R/none"
rm -f "$D/steam_libraries.txt"
HERE=$(dirname "$0")
for arm in plain snap deb xdg none; do
	if [ $arm = xdg ]; then X="XDG_DATA_HOME=$R/xdg/xdgdata"; else X="XDG_DATA_HOME="; fi
	env HOME=$R/$arm $X bash "$HERE/rig-run.sh" "$D" x11 "p386steam_${TAG}_$arm" cfg/test/p386lin.cfg >/dev/null
	L=/mnt/c/FTESurf/ftesurf/logs/linux/p386steam_${TAG}_$arm.log
	echo "$TAG $arm: ok=$(grep -c ' ok .*steam:' "$L") notfound=$(grep -c 'NOT FOUND' "$L") vdf=$(grep -c ' found .*libraryfolders.vdf' "$L")"
done
