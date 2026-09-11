#!/bin/sh
# Stop surfd. Only ever touches surfd's own pidfile / its own gunicorn
# master - it must never signal the globe service or the game server.

HOME_DIR=/srv/nvme/surfd
PIDFILE="$HOME_DIR/surfd.pid"

if [ ! -f "$PIDFILE" ]; then
	echo "no pidfile at $PIDFILE; surfd does not appear to be running"
	exit 0
fi

PID=$(cat "$PIDFILE")
if ! kill -0 "$PID" 2>/dev/null; then
	echo "stale pidfile (pid $PID is gone); removing"
	rm -f "$PIDFILE"
	exit 0
fi

echo "stopping surfd pid $PID"
kill -TERM "$PID"

i=0
while [ "$i" -lt 20 ]; do
	kill -0 "$PID" 2>/dev/null || break
	sleep 0.5
	i=$((i + 1))
done

if kill -0 "$PID" 2>/dev/null; then
	echo "did not exit on TERM, sending KILL"
	kill -KILL "$PID" 2>/dev/null
fi

rm -f "$PIDFILE"
echo "surfd stopped"
