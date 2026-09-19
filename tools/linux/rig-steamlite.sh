#!/bin/bash
# A small Steam library on ext4 for live-lobby arms, as user surf in the Debian rig:
#   bash rig-steamlite.sh <lib dir> <map>...
# Why: over drvfs a client's connect-time FS rebuild takes ~27 s and the pure-package pass
# repeats it, so a lobby (timeout 30, lobby.cfg) drops the client before prespawn
# (logs/linux/p386lobby_A_drvfs.log).  Here the named BSPs, maps/zones and gameinfo.txt are copied;
# the CS:S and HL2 VPKs are per-file symlinks into /mnt/c.  Loose materials are not copied.
# Point an install at it with:  echo <lib dir> > <install>/steam_libraries.txt
set -eu
L=${1:?lib dir}; shift
S="/mnt/c/Program Files (x86)/Steam/steamapps/common"
C=$L/steamapps/common
rm -rf "$L"
mkdir -p "$C/Momentum Mod Playtest/momentum/maps" "$C/Counter-Strike Source/cstrike" "$C/Half-Life 2/hl2"
M="$C/Momentum Mod Playtest/momentum"
cp "$S/Momentum Mod Playtest/momentum/gameinfo.txt" "$M/"
cp -r "$S/Momentum Mod Playtest/momentum/maps/zones" "$M/maps/"
for m in "$@"; do cp "$S/Momentum Mod Playtest/momentum/maps/$m.bsp" "$M/maps/"; done
for g in "Counter-Strike Source/cstrike" "Half-Life 2/hl2"; do
	for v in "$S/$g"/*.vpk; do ln -s "$v" "$C/$g/$(basename "$v")"; done
done
echo "rig-steamlite: $L maps=$(ls "$M/maps"/*.bsp | wc -l) vpk-links=$(find "$L" -type l | wc -l) non-vpk-links=$(find "$L" -type l ! -name '*.vpk' | wc -l)"
