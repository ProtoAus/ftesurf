#!/bin/sh
# install_board_endpoint.sh -- put surfd's public read endpoints on the vhost.
#
# THE NAME IS NARROWER THAN THE JOB, and keeping it is deliberate: the path is
# documented in three places and in the repo history, and renaming it to gain
# accuracy in one line would cost a working instruction everywhere else.  What
# it actually does is install $HOME_DIR/surfd.nginx WHOLESALE -- whatever
# read-only routes that file currently declares.  As of schema 3 that is
# /api/board AND /api/replay/<id>; the exposure manifest at the top of
# surfd.nginx is the authority, not this header.
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
# ALL THREE zones, every time. The board zone is what keeps one player from
# spending everybody's budget: surfd sees 127.0.0.1 for every request that
# arrives through this proxy, so nginx is the only party that still knows who
# is who.  surfdreplay is the same argument with a much smaller number, because
# a replay is ~1 MB where a board page is ~4 KB -- at the board's rate one
# address could pull the whole home upstream link indefinitely.
cat > /etc/nginx/conf.d/surfd-ratelimit.conf <<'ZONES'
limit_req_zone $binary_remote_addr zone=surfdlogin:1m rate=12r/m;
limit_req_zone $binary_remote_addr zone=surfdboard:4m rate=120r/m;
limit_req_zone $binary_remote_addr zone=surfdreplay:4m rate=20r/m;
ZONES
echo "  wrote surfdlogin + surfdboard + surfdreplay"

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

# /api/replay: a HEAD, because a GET here would pull a whole recording through
# the verification step for no extra information.  A 200 or 404 both prove the
# route is REACHED -- 404 only means this box has no replay id 1 -- whereas the
# 404 from `location / { return 404; }` is what it looked like before the
# snippet was installed, so the body is what distinguishes them.  surfd answers
# JSON; the vhost's catch-all answers nginx's HTML.
REP=$(curl -s -o /tmp/b64rep.out -w '%{http_code}' -I \
    "https://play.proto.bar/api/replay/1")
echo "  HEAD /api/replay/1 -> $REP"
curl -s "https://play.proto.bar/api/replay/99999999" | head -c 120; echo
echo "    (the line above must be surfd's JSON, not nginx HTML -- that is how"
echo "     you tell 'route installed, no such replay' from 'route missing')"
rm -f /tmp/b64rep.out

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
