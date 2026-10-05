#!/bin/sh
# The engine deploy gate on the Pi (AGENTS.md, the Pi engine paragraph), as one
# script since Patch 492:
#   sh pigate.sh <binary> <port> <dir holding p492voy.rec and surf_voyager.json>
# pm_dettest on bhop_eazy and surf_ace -- compare every line with the Windows
# build's; surf_ace's displacements reach the triangle path bhop_eazy lacks --
# then pm_verify of a pin-1 file the sweeper PASSed (PASSMAP/PASSREC override
# it), and of p492voy.rec (pmsrcver 2) through a throwaway overlay, since the
# Pi has no zone file for surf_voyager.  A
# pre-492 binary REFUSEs p492voy.rec: that is the control.  Port != 27698.
set -u
BIN="$1"
PORT="$2"
FIX="$3"
PASSMAP="${PASSMAP:-surf_boreas}"
PASSREC="${PASSREC:-data/runs/surf_boreas/main/0003107_proto-26c95e00_run.rec}"
GAME=/srv/nvme/ftesurf-server/game
OV=/tmp/pigate-ov.$$
echo "== $BIN md5 $(md5sum "$BIN" | cut -c1-32)"
cd "$GAME" || exit 2
for m in bhop_eazy surf_ace; do
  timeout 600 "$BIN" -basedir "$GAME" +set sv_public 0 +set sv_port "$PORT" +set rec_enable 0 \
    +set lobby_master "" +map "$m" +wait +wait +wait +pm_dettest +quit 2>&1 \
    | grep -a "pm_dettest [a-z]" | grep -av tickcensus | sed "s/^/$m /"
done
timeout 600 "$BIN" -basedir "$GAME" +set sv_public 0 +set sv_port "$PORT" +set rec_enable 0 \
  +set lobby_master "" +map "$PASSMAP" +wait +wait +wait +pm_verify "$PASSREC" +quit 2>&1 \
  | grep -a "VERIFY\|pmsrcver"

mkdir -p "$OV/ftesurf/maps/zones/local" "$OV/ftesurf/data/runs/surf_voyager/main" || exit 2
for e in "$GAME"/*; do
  n=$(basename "$e")
  [ "$n" = ftesurf ] || ln -s "$e" "$OV/$n"
done
for e in "$GAME"/ftesurf/*; do
  n=$(basename "$e")
  case "$n" in data|logs|maps) ;; *) ln -s "$e" "$OV/ftesurf/$n" ;; esac
done
cp "$FIX/surf_voyager.json" "$OV/ftesurf/maps/zones/local/"
cp "$FIX/p492voy.rec" "$OV/ftesurf/data/runs/surf_voyager/main/"
cd "$OV" || exit 2
timeout 900 "$BIN" -basedir "$OV" +set sv_public 0 +set sv_port "$PORT" +set rec_enable 0 \
  +set lobby_master "" +map surf_voyager +wait +wait +wait \
  +pm_verify data/runs/surf_voyager/main/p492voy.rec +quit 2>&1 | grep -a "VERIFY\|pmsrcver"
cd /
rm -r "$OV"   # links only; rm -r does not follow them
[ -e "$OV" ] && echo "OVERLAY LEFT AT $OV" || echo "overlay removed"
