#!/bin/sh
# Stop all five FTESurf lobbies.  Patch 275; five since QC build 57.
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
if systemctl list-unit-files 'ftesurf@.service' 2>/dev/null | grep -q '^ftesurf@'; then
	echo "stopall: ftesurf@.service is installed -- using systemd"
	for N in 1 2 3 4 5; do
		sudo systemctl stop "ftesurf@$N" && echo "lobby $N: stopped (systemd)"
	done
	# Leftovers from a pre-systemd nohup start would still be holding the ports
	# and would still be heartbeating. Say so rather than let the next runall
	# fail to bind for a reason nothing explains.
	for N in 1 2 3 4 5; do
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
for N in 1 2 3 4 5; do
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
