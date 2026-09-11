#!/bin/sh
# FTESurf lobby server -- Patch 275.
# Usage: ./run.sh <1|2|3> [map]
#
# One process per lobby.  The three differ only in cfg/lobbyN.cfg, which sets
# the port, the hostname and the map rotation; everything else is cfg/lobby.cfg.
#
# EXEC ORDER IS LOAD-BEARING:
#   lobby.cfg        shared settings, including lobby_maps "" / lobby_cycle 0
#   lobbyN.cfg       the per-lobby port, name and rotation -- it must OVERRIDE
#                    those empty defaults, so it comes second
#   lobby_local.cfg  the surfd shared secret.  mode 0600, NOT in the repo.
#
# cfg/lobby.cfg is exec'd EXPLICITLY and is deliberately not called server.cfg:
# SV_ExecInitialConfigs would auto-prefer that name and silently stop
# cfg/default.cfg (and therefore pm_physicsmode/pm_ticrate/sv_bigcoords) running.
#
# THE PORT COMES FROM THE CFG, NOT FROM -port.  sv_port is read when the server
# binds, which is at +map -- i.e. after all three execs -- so the cfg wins and
# there is one place per lobby that says what its port is.
set -e
N="${1:-}"
case "$N" in
  1) DEF=surf_kitsune  ;;
  2) DEF=surf_beginner ;;
  3) DEF=surf_shady    ;;
  *) echo "usage: run.sh <1|2|3> [map]" >&2; exit 2 ;;
esac
MAP="${2:-$DEF}"
cd /srv/nvme/ftesurf-server/game
exec ./fteqw-svarm64 -basedir /srv/nvme/ftesurf-server/game \
     +developer 1 \
     +exec cfg/lobby.cfg \
     +exec "cfg/lobby$N.cfg" \
     +exec cfg/lobby_local.cfg \
     +map "$MAP"
