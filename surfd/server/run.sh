#!/bin/sh
# FTESurf lobby server -- Patch 275; lobbies 4 and 5 added in QC build 57.
# Usage: ./run.sh <1..5> [map]
#
# One process per lobby.  The five differ only in cfg/lobbyN.cfg, which sets
# the port, the hostname and the map rotation; everything else is cfg/lobby.cfg.
# 1-3 are the surf tiers, 4 and 5 bhop easy and hard.  Keep each DEF below the
# first entry of that lobby's lobby_maps, so a fresh start plays the rotation
# from the top.
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
  1) DEF=surf_kitsune      ;;
  2) DEF=surf_beginner     ;;
  3) DEF=surf_shady        ;;
  4) DEF=bhop_eazy         ;;
  5) DEF=bhop_benchpressed ;;
  *) echo "usage: run.sh <1..5> [map]" >&2; exit 2 ;;
esac
MAP="${2:-$DEF}"
cd /srv/nvme/ftesurf-server/game

# BUILD 57: REFUSE WITHOUT THE PER-LOBBY CFG, because every way this fails is
# quiet.  A missing +exec target is not fatal in FTE -- it prints "couldn't exec"
# and carries on -- and cfg/lobby.cfg deliberately sets no sv_port, so the server
# would bind the engine's DEFAULT QuakeWorld port 27500: the one port cfg/lobby1.cfg
# says must never be listening, and the one a stranger's scan finds first.  It
# would also take lobby.cfg's shared hostname and its empty rotation, so the
# directory would show a row whose port and name belong to nothing.
#
# The path is relative to this directory because the engine resolves +exec
# against the GAMEDIR (ftesurf/), which is one level down from the basedir.
if [ ! -f "ftesurf/cfg/lobby$N.cfg" ]; then
	echo "run.sh: ftesurf/cfg/lobby$N.cfg is missing -- refusing to start lobby $N." >&2
	echo "        Without it this binds the default port 27500 with no rotation." >&2
	echo "        Deploy the cfg first; see surfd/README.md." >&2
	exit 2
fi
exec ./fteqw-svarm64 -basedir /srv/nvme/ftesurf-server/game \
     +developer 1 \
     +exec cfg/lobby.cfg \
     +exec "cfg/lobby$N.cfg" \
     +exec cfg/lobby_local.cfg \
     +map "$MAP"
