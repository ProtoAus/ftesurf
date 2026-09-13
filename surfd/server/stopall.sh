#!/bin/sh
# Stop every FTESurf lobby.  Patch 275; five since QC build 57; the fixed list
# of five replaced by discovery in QC build 67.
#
# SIGTERM, then wait, then SIGKILL.  The engine writes nothing on shutdown that
# is worth protecting, but a lobby killed outright leaves its row in surfd until
# the 30s TTL expires it, and a clean exit is one less thing to explain when a
# lobby is missing from the picker.
#
# SYSTEMD FIRST, for the same reason as runall.sh -- and here it also matters
# that `kill` alone would not stop a managed lobby: Restart=always would bring
# it straight back and the operator would conclude the script is broken.
cd /srv/nvme/ftesurf-server

# A WIDER NET THAN runall.sh's, AND DELIBERATELY SO.
#
# runall asks "what can be started", which is exactly the set of cfgs.  stopall
# has to ask "what might be RUNNING", and those differ in the one case that
# matters: a lobby whose cfg was deleted or renamed while it was up.  Deriving
# from cfgs alone would walk straight past it, report success, and leave a
# process holding a port and heartbeating a row into the picker -- the exact
# "one of them fails to bind and the failure is quiet" that runall.sh's header
# is about, arriving from the other side.
#
# So: the cfgs, plus every ftesurf@N unit systemd currently knows about, minus
# duplicates.  `sort -un` does the dedupe and the numeric order in one pass.
lobby_list() {
	{
		for f in game/ftesurf/cfg/lobby[0-9]*.cfg; do
			[ -f "$f" ] || continue
			n=${f##*/lobby}; n=${n%.cfg}
			case "$n" in ''|*[!0-9]*) continue ;; esac
			echo "$n"
		done
		systemctl list-units 'ftesurf@*' --all --no-legend --no-pager 2>/dev/null |
			sed -n 's/^[^a-z]*ftesurf@\([0-9][0-9]*\)\.service.*/\1/p'
		for p in lobby[0-9]*.pid; do
			[ -f "$p" ] || continue
			n=${p#lobby}; n=${n%.pid}
			case "$n" in ''|*[!0-9]*) continue ;; esac
			echo "$n"
		done
	} | sort -un
}

LOBBIES=$(lobby_list)
if [ -z "$LOBBIES" ]; then
	echo "stopall: no lobby cfgs, units or pid files found -- nothing to stop."
	exit 0
fi
echo "stopall: lobbies found: $(echo $LOBBIES | tr '\n' ' ')"

if systemctl list-unit-files 'ftesurf@.service' 2>/dev/null | grep -q '^ftesurf@'; then
	echo "stopall: ftesurf@.service is installed -- using systemd"
	for N in $LOBBIES; do
		sudo systemctl stop "ftesurf@$N" && echo "lobby $N: stopped (systemd)"
	done
	# Leftovers from a pre-systemd nohup start would still be holding the ports
	# and would still be heartbeating. Say so rather than let the next runall
	# fail to bind for a reason nothing explains.
	for N in $LOBBIES; do
		P=$(cat "lobby$N.pid" 2>/dev/null) || continue
		if kill -0 "$P" 2>/dev/null; then
			echo "lobby $N: WARNING a pre-systemd copy is still alive (pid $P);" >&2
			echo "          kill $P by hand, then remove lobby$N.pid" >&2
		else
			rm -f "lobby$N.pid"
		fi
	done
	exit 0
fi
for N in $LOBBIES; do
	PID="lobby$N.pid"
	[ -f "$PID" ] || { echo "lobby $N: no pid file"; continue; }
	P=$(cat "$PID")
	if ! kill -0 "$P" 2>/dev/null; then
		echo "lobby $N: not running"; rm -f "$PID"; continue
	fi
	kill "$P" 2>/dev/null
	for i in 1 2 3 4 5; do
		kill -0 "$P" 2>/dev/null || break
		sleep 1
	done
	kill -0 "$P" 2>/dev/null && kill -9 "$P" 2>/dev/null
	rm -f "$PID"
	echo "lobby $N: stopped (pid $P)"
done
