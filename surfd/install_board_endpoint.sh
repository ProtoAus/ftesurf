#!/bin/sh
# install_board_endpoint.sh -- put GET /api/board on the public vhost.
#
# WHY THIS EXISTS AS ITS OWN SCRIPT.  setup_public.sh does the whole public
# deployment, certbot included, and re-running it to add one location block is
# a much bigger action than the change deserves on a live service.  This does
# only the two things that are missing, and refuses to reload nginx unless the
# resulting config tests clean.
#
# It is idempotent: running it twice changes nothing the second time.
#
#   sudo /srv/nvme/surfd/install_board_endpoint.sh
#
# Everything it touches is backed up next to the original with a .b64bak-<ts>
# suffix, and the exact restore commands are printed at the end.

set -e

[ "$(id -u)" = "0" ] || { echo "run me with sudo -- I install nginx config." >&2; exit 1; }

HOME_DIR=/srv/nvme/surfd
TS=$(date +%Y%m%d-%H%M%S)

[ -f "$HOME_DIR/surfd.nginx" ] || {
    echo "$HOME_DIR/surfd.nginx is missing -- deploy the repo copy first." >&2
    exit 1
}

echo "== backing up =="
for f in /etc/nginx/snippets/surfd.conf /etc/nginx/conf.d/surfd-ratelimit.conf; do
    if [ -f "$f" ]; then
        cp -p "$f" "$f.b64bak-$TS"
        echo "  $f -> $f.b64bak-$TS"
    fi
done

echo "== the rate-limit zones (http{} scope -- limit_req_zone is not valid in a location) =="
# BOTH zones, every time. The board zone is what keeps one player from spending
# everybody's budget: surfd sees 127.0.0.1 for every request that arrives
# through this proxy, so nginx is the only party that still knows who is who.
cat > /etc/nginx/conf.d/surfd-ratelimit.conf <<'ZONES'
limit_req_zone $binary_remote_addr zone=surfdlogin:1m rate=12r/m;
limit_req_zone $binary_remote_addr zone=surfdboard:4m rate=120r/m;
ZONES
echo "  wrote surfdlogin + surfdboard"

echo "== the snippet =="
install -m 0644 "$HOME_DIR/surfd.nginx" /etc/nginx/snippets/surfd.conf
echo "  installed /etc/nginx/snippets/surfd.conf"

echo "== nginx -t =="
if ! nginx -t; then
    echo "" >&2
    echo "CONFIG TEST FAILED -- rolling back, nginx was NOT reloaded." >&2
    for f in /etc/nginx/snippets/surfd.conf /etc/nginx/conf.d/surfd-ratelimit.conf; do
        [ -f "$f.b64bak-$TS" ] && cp -p "$f.b64bak-$TS" "$f"
    done
    # A zone file that did not exist before must go, not be left empty.
    [ -f /etc/nginx/conf.d/surfd-ratelimit.conf.b64bak-$TS ] ||
        rm -f /etc/nginx/conf.d/surfd-ratelimit.conf
    nginx -t >/dev/null 2>&1 && echo "rolled back cleanly." >&2
    exit 1
fi

echo "== reload =="
systemctl reload nginx
sleep 1

echo "== verify =="
# The query string is the thing to check, not just the status code: if
# proxy_pass ever drops it, surfd answers 400 "bad map" rather than a board --
# so a 200 with rows here proves the args survived the hop.
CODE=$(curl -s -o /tmp/b64board.out -w '%{http_code}' \
    "https://play.proto.bar/api/board?map=bhop_eazy&track=0&leg=0&tier=ranked&style=clean")
echo "  GET /api/board -> $CODE"
head -c 200 /tmp/b64board.out; echo
rm -f /tmp/b64board.out

echo "  heartbeat must STILL be absent (it must never be proxied):"
echo "    /api/heartbeat -> $(curl -s -o /dev/null -w '%{http_code}' \
    -X POST https://play.proto.bar/api/heartbeat)"
echo "  /api/run must also still be absent (write path):"
echo "    /api/run -> $(curl -s -o /dev/null -w '%{http_code}' \
    -X POST https://play.proto.bar/api/run)"

echo ""
echo "done.  To undo:"
echo "  sudo cp /etc/nginx/snippets/surfd.conf.b64bak-$TS /etc/nginx/snippets/surfd.conf"
echo "  sudo nginx -t && sudo systemctl reload nginx"
