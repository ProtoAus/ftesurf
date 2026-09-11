#!/bin/sh
# Start surfd under gunicorn, detached so it survives the SSH session.
# Same pattern as the existing game server: setsid nohup ... </dev/null &
#
# There is no systemd unit installed (that needs root). surfd.service is
# written next to this file for a human to install later.

set -e

HOME_DIR=/srv/nvme/surfd
PIDFILE="$HOME_DIR/surfd.pid"
LOGFILE="$HOME_DIR/logs/gunicorn.log"
BIND=0.0.0.0:8084

cd "$HOME_DIR"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/data"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
	echo "surfd already running as pid $(cat "$PIDFILE")"
	exit 0
fi

# --forwarded-allow-ips '' : never honour X-Forwarded-* from anyone. The
# heartbeat's advertised address comes from the real socket peer, and this
# service is reachable directly on the LAN, so trusting a forwarded header
# would let any client claim any source IP.
#
# One worker on purpose: the rate limiter and the node cap are per-process.
setsid nohup /usr/bin/gunicorn \
	--bind "$BIND" \
	--workers 1 \
	--threads 4 \
	--worker-class gthread \
	--timeout 30 \
	--graceful-timeout 20 \
	--keep-alive 5 \
	--max-requests 5000 \
	--max-requests-jitter 500 \
	--forwarded-allow-ips '' \
	--pid "$PIDFILE" \
	--access-logfile - \
	--error-logfile - \
	--log-level info \
	--chdir "$HOME_DIR" \
	surfd:app \
	</dev/null >>"$LOGFILE" 2>&1 &

sleep 2
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
	echo "surfd started on $BIND as pid $(cat "$PIDFILE")"
else
	echo "surfd FAILED to start; tail of $LOGFILE:" >&2
	tail -20 "$LOGFILE" >&2
	exit 1
fi
