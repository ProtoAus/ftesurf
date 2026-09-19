#!/bin/bash
# Case rig (Patch 386 C3): an ext4 copy of the Steam library's loose content, as user surf in Debian:
#   bash rig-fakesteam.sh <map> [map...]      (on-disk spellings; re-run to add maps)
# Loose trees are copied, every *.vpk is a per-file symlink into /mnt/c (VPK lookups are
# lowercased by the plugin, so only loose lookups test the host's case), and HOME's
# libraryfolders.vdf points the engine at it.
set -eu
SRC="/mnt/c/Program Files (x86)/Steam/steamapps/common"
FS=$HOME/fakesteam; C=$FS/steamapps/common
MOM="Momentum Mod Playtest/momentum"; CSS="Counter-Strike Source/cstrike"; HL2="Half-Life 2/hl2"
mkdir -p "$C/$MOM/maps" "$C/Momentum Mod Playtest/mount" "$C/$CSS/maps" "$C/$HL2"
copy() {	# game dir, subdirs...
	local g=$1; shift
	for d in "$@"; do
		[ -e "$C/$g/$d" ] || cp -a "$SRC/$g/$d" "$C/$g/"
	done
}
copy "$MOM" materials models sound particles scripts resource gameinfo.txt
copy "$CSS" materials resource
for g in "$MOM" "Momentum Mod Playtest/mount" "$CSS" "$HL2"; do
	for v in "$SRC/$g"/*.vpk; do
		if [ -e "$v" ]; then ln -sfn "$v" "$C/$g/$(basename "$v")"; fi
	done
done
for m in "$@"; do
	hit=0
	for g in "$MOM" "$CSS" "$HL2"; do
		[ -f "$SRC/$g/maps/$m.bsp" ] || continue
		cp -a "$SRC/$g/maps/$m.bsp" "$C/$g/maps/"
		if [ -f "$SRC/$g/maps/$m.nav" ]; then cp -a "$SRC/$g/maps/$m.nav" "$C/$g/maps/"; fi
		find "$SRC/$g/maps/zones" -iname "$m.*" 2>/dev/null | while read -r z; do
			r=${z#"$SRC/$g/"}; mkdir -p "$C/$g/$(dirname "$r")"; cp -a "$z" "$C/$g/$r"
		done
		hit=1; break
	done
	if [ $hit = 0 ]; then echo "rig-fakesteam: $m.bsp not found" >&2; fi
done
V=$HOME/.steam/steam/steamapps
mkdir -p "$V"
printf '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' "$FS" > "$V/libraryfolders.vdf"
bad=$(find "$FS" -type l ! -name '*.vpk' | wc -l)
echo "rig-fakesteam: $(find "$FS" -type l -name '*.vpk' | wc -l) vpk links, $bad other links, $(find "$FS" -type f | wc -l) files, $(du -sh "$FS" | cut -f1)"
[ "$bad" = 0 ] || { echo "rig-fakesteam: non-vpk symlinks present" >&2; exit 1; }
