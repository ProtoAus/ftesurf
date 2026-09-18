#!/bin/sh
# Start every FTESurf lobby.  Patch 275; five since QC build 57; the fixed list
# of five replaced by discovery in QC build 67.
# Idempotent: a lobby that is already up is left alone rather than started
# twice -- two processes on one port means one of them fails to bind and the
# failure is quiet.
#
# SYSTEMD FIRST, nohup as the fallback.  Once ftesurf@.service is installed this
# script must NOT start a second, unsupervised copy alongside the managed one --
# so it delegates instead.  Keeping the name means every note and habit that
# says "stopall && runall" keeps working across the switch, which is the whole
# reason this is a wrapper rather than a message telling you to use systemctl.
cd /srv/nvme/ftesurf-server

# WHICH LOBBIES EXIST IS A QUESTION WITH AN ANSWER ON DISK, so stop writing it
# out.  Build 67: /api/join sizes the pool on demand, and a hardcoded `1 2 3 4 5`
# here would mean a new lobby starts only when somebody remembers to edit three
# shell scripts as well as adding its cfg -- and the failure is silent in the
# worst direction, because runall would report complete success having skipped it.
#
# A lobby IS its cfg: run.sh refuses to start without one (it would otherwise
# bind the default port 27500), so the set of startable lobbies and the set of
# cfgs are the same set by construction rather than by agreement.
#
# `sort -n` because the glob gives lobby10 before lobby2, and a start order that
# jumps around makes two runs hard to compare in a log.
lobby_list() {
	for f in game/ftesurf/cfg/lobby[0-9]*.cfg; do
		[ -f "$f" ] || continue           # no match: the glob stays literal
		n=${f##*/lobby}
		n=${n%.cfg}
		case "$n" in ''|*[!0-9]*) continue ;; esac
		echo "$n"
	done | sort -n
}

LOBBIES=$(lobby_list)
if [ -z "$LOBBIES" ]; then
	echo "runall: no game/ftesurf/cfg/lobby/lobbyN.cfg found -- nothing to start." >&2
	exit 2
fi
echo "runall: lobbies found: $(echo $LOBBIES | tr '\n' ' ')"

if systemctl list-unit-files 'ftesurf@.service' >/dev/null 2>&1 &&
   systemctl list-unit-files 'ftesurf@.service' 2>/dev/null | grep -q '^ftesurf@'; then
	echo "runall: ftesurf@.service is installed -- using systemd"
	rc=0
	for N in $LOBBIES; do
		if sudo systemctl start "ftesurf@$N"; then
			echo "lobby $N: started (systemd)"
		else
			echo "lobby $N: FAILED -- systemctl status ftesurf@$N" >&2
			rc=1
		fi
	done
	exit $rc
fi
echo "runall: no ftesurf@.service installed -- nohup fallback, nothing will"
echo "        restart these if they crash or the Pi reboots"
for N in $LOBBIES; do
	PID="lobby$N.pid"
	if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
		echo "lobby $N: already running (pid $(cat "$PID"))"
		continue
	fi
	# run.sh execs the engine, so $! stays the engine's own pid.
	nohup ./run.sh "$N" >> "server$N.log" 2>&1 &
	echo $! > "$PID"
	echo "lobby $N: started (pid $!)  log server$N.log"
done
