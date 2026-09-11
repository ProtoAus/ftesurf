#!/bin/sh
# Start all three FTESurf lobbies.  Patch 275.  Idempotent: a lobby that is
# already up is left alone rather than started twice -- two processes on one
# port means one of them fails to bind and the failure is quiet.
#
# SYSTEMD FIRST, nohup as the fallback.  Once ftesurf@.service is installed this
# script must NOT start a second, unsupervised copy alongside the managed one --
# so it delegates instead.  Keeping the name means every note and habit that
# says "stopall && runall" keeps working across the switch, which is the whole
# reason this is a wrapper rather than a message telling you to use systemctl.
cd /srv/nvme/ftesurf-server
if systemctl list-unit-files 'ftesurf@.service' >/dev/null 2>&1 &&
   systemctl list-unit-files 'ftesurf@.service' 2>/dev/null | grep -q '^ftesurf@'; then
	echo "runall: ftesurf@.service is installed -- using systemd"
	rc=0
	for N in 1 2 3; do
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
for N in 1 2 3; do
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
