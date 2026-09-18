#!/bin/sh
# FTESurf lobby server -- Patch 275; lobbies 4 and 5 added in QC build 57;
# the fixed 1..5 list removed in QC build 67.
# Usage: ./run.sh <lobby number> [map]
#
# One process per lobby.  They differ only in cfg/lobby/lobbyN.cfg, which sets the
# port, the hostname and the map rotation; everything else is cfg/lobby/lobby.cfg.
# 1-3 are the surf tiers, 4 and 5 bhop easy and hard.
#
# BUILD 67: ANY N THAT HAS A CFG, AND THE START MAP COMES FROM THAT CFG.
#
# This used to be `case "$N" in 1)..5) *) exit 2`, with each lobby's start map
# written out again here as DEF and a comment asking whoever edits it to "keep
# each DEF the first entry of that lobby's lobby_maps".  Two problems, and
# build 67 turns both from latent into blocking:
#
#   THE CEILING.  /api/join grows the pool on demand, and the systemd template
#   is already generic -- %i goes straight through to `run.sh %i`, and
#   `systemctl is-enabled ftesurf@6` answers `disabled` rather than `not-found`.
#   So the ONLY thing that stopped a sixth lobby was this list: ftesurf@6 would
#   ExecStart, exit 2 in milliseconds, and with Restart=always and
#   StartLimitBurst=5 land in `failed` -- five restarts and a dead unit, for a
#   server whose config was perfectly good.
#
#   THE DUPLICATION.  A value that must equal another value, maintained by a
#   comment, in a file nobody opens unless something is already wrong.  Nothing
#   checks it and nothing could: a DEF that has drifted from its rotation is a
#   lobby that starts on a map the rotation then never returns to, which looks
#   exactly like a deliberate choice.
#
# Deriving DEF from lobby$N.cfg fixes both at once, and makes the sync rule
# structural instead of aspirational -- there is now one place per lobby that
# says what it plays, the same way there is already one place that says what
# port it binds (see below).
#
# EXEC ORDER IS LOAD-BEARING:
#   lobby.cfg        shared settings, including lobby_maps "" / lobby_cycle 0
#   lobbyN.cfg       the per-lobby port, name and rotation -- it must OVERRIDE
#                    those empty defaults, so it comes second
#   lobby_local.cfg  the surfd shared secret.  mode 0600, NOT in the repo.
#
# cfg/lobby/lobby.cfg is exec'd EXPLICITLY and is deliberately not called server.cfg:
# SV_ExecInitialConfigs would auto-prefer that name and silently stop
# cfg/default.cfg (and therefore pm_physicsmode/pm_ticrate/sv_bigcoords) running.
#
# THE PORT COMES FROM THE CFG, NOT FROM -port.  sv_port is read when the server
# binds, which is at +map -- i.e. after all three execs -- so the cfg wins and
# there is one place per lobby that says what its port is.
set -e
N="${1:-}"

# DIGITS ONLY, AND THIS IS THE CHECK THE `case` USED TO BE DOING BY ACCIDENT.
#
# N is interpolated into "ftesurf/cfg/lobby/lobby$N.cfg" below.  While the only legal
# values were the five literals, that string could not be anything but a path in
# this directory; now that any number is accepted, the validation has to be said
# out loud or `run.sh ../../something` becomes a config this script will exec.
# systemd's %i is not the only caller -- runall.sh and a human at a prompt both
# pass it directly.
case "$N" in
  ''|*[!0-9]*)
    echo "usage: run.sh <lobby number> [map]" >&2
    echo "       the number selects ftesurf/cfg/lobby/lobby<N>.cfg" >&2
    exit 2 ;;
esac

cd /srv/nvme/ftesurf-server/game

# BUILD 57: REFUSE WITHOUT THE PER-LOBBY CFG, because every way this fails is
# quiet.  A missing +exec target is not fatal in FTE -- it prints "couldn't exec"
# and carries on -- and cfg/lobby/lobby.cfg deliberately sets no sv_port, so the server
# would bind the engine's DEFAULT QuakeWorld port 27500: the one port cfg/lobby/lobby1.cfg
# says must never be listening, and the one a stranger's scan finds first.  It
# would also take lobby.cfg's shared hostname and its empty rotation, so the
# directory would show a row whose port and name belong to nothing.
#
# The path is relative to this directory because the engine resolves +exec
# against the GAMEDIR (ftesurf/), which is one level down from the basedir.
if [ ! -f "ftesurf/cfg/lobby/lobby$N.cfg" ]; then
	echo "run.sh: ftesurf/cfg/lobby/lobby$N.cfg is missing -- refusing to start lobby $N." >&2
	echo "        Without it this binds the default port 27500 with no rotation." >&2
	echo "        Deploy the cfg first; see surfd/README.md." >&2
	exit 2
fi

# THE START MAP IS THE FIRST ENTRY OF THIS LOBBY'S ROTATION, READ FROM THE CFG.
#
# Matches `set lobby_maps "first second ..."` and takes the first word.  Written
# to tolerate the spacing actually used across lobby1..5.cfg (which align the
# value into a column, so the gaps are runs of spaces, not single ones) and to
# ignore a commented-out line, since `//` is the comment marker in a .cfg and a
# naive grep would happily read one.
#
# NOT `set -e`-SAFE BY ACCIDENT: the assignment is its own statement so that a
# no-match leaves DEF empty and reaches the test below, rather than killing the
# script with a bare non-zero status nobody would be able to attribute.
DEF=$(sed -n 's|^[[:space:]]*set[[:space:]][[:space:]]*lobby_maps[[:space:]][[:space:]]*"\([^" ]*\).*|\1|p' \
      "ftesurf/cfg/lobby/lobby$N.cfg" | head -n 1)

MAP="${2:-$DEF}"

# AN EMPTY MAP IS THE SAME CLASS OF QUIET FAILURE AS A MISSING CFG, so it gets
# the same refusal rather than a `+map ""` that leaves the engine sitting at the
# console with a bound port and no world -- which heartbeats nothing, shows up
# nowhere, and reads as a crash.
if [ -z "$MAP" ]; then
	echo "run.sh: ftesurf/cfg/lobby/lobby$N.cfg sets no lobby_maps -- refusing to start lobby $N." >&2
	echo "        The start map is the first entry of that rotation." >&2
	echo "        Pass one explicitly (run.sh $N <map>) to override." >&2
	exit 2
fi

exec ./fteqw-svarm64 -basedir /srv/nvme/ftesurf-server/game \
     +developer 1 \
     +exec cfg/lobby/lobby.cfg \
     +exec "cfg/lobby/lobby$N.cfg" \
     +exec cfg/lobby_local.cfg \
     +map "$MAP"
