#!/bin/sh
# =============================================================================
#  install.sh -- wire legacy /ftesurf and candidate /worldofsurf. Run as root:
#
#      sudo sh /srv/nvme/ftesurf-site/install.sh
#
#  This is the only step in the whole release pipeline that needs a password.
#  proto's sudo is (ALL:ALL) ALL but PASSWORD-REQUIRED except for fifteen
#  `systemctl ... ftesurf@1..5` rules, so a non-interactive script cannot touch
#  /etc/nginx.  Everything after this -- every future release -- is a plain scp
#  into /srv/nvme, which proto owns.
#
#  It is idempotent: run it again after editing ftesurf.nginx and it replaces
#  the snippet, notices the include line is already there, and reloads.
# =============================================================================
set -eu

SITE=/srv/nvme/ftesurf-site
VHOST=/etc/nginx/sites-enabled/filebrowsers.conf
SNIP=/etc/nginx/snippets/ftesurf.conf
SRC="$SITE/ftesurf.nginx"
TS=$(date +%Y%m%d-%H%M%S)

[ "$(id -u)" = "0" ] || { echo "install.sh must run as root:  sudo sh $SITE/install.sh" >&2; exit 1; }
[ -f "$SRC" ]   || { echo "missing $SRC -- run a release first, it scp's this file" >&2; exit 1; }
[ -f "$VHOST" ] || { echo "missing $VHOST -- is this the right box?" >&2; exit 1; }
# The /ftesurf/board/ block uses surfd's board zone; without it nginx -t fails.
grep -qs 'zone=surfdboard' /etc/nginx/conf.d/surfd-ratelimit.conf || {
    echo "no zone=surfdboard in /etc/nginx/conf.d/surfd-ratelimit.conf --" >&2
    echo "run install_board_endpoint.sh first:  sudo /srv/nvme/surfd/install_board_endpoint.sh" >&2
    exit 1
}
# ...and proxies to surfd's /board/, which only a surfd deployed with web/ serves.
SURFD=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8084/board/api/maps || true)
[ "$SURFD" = "200" ] || {
    echo "surfd's /board/api/maps answered ${SURFD:-nothing}, not 200 -- deploy surfd (with web/) first" >&2
    exit 1
}

echo "== baseline =="
BEFORE=$(nginx -T 2>/dev/null | grep -c 'server_name proto.bar;' || true)
echo "   server_name proto.bar count before: $BEFORE"

# -----------------------------------------------------------------------------
#  Back up the vhost -- to /etc/nginx, NOT beside the original.
#
#  nginx.conf line 28 is  include /etc/nginx/sites-enabled/*;  -- a BARE glob
#  with no *.conf filter.  That is why the extension-less `fastdl` vhost loads,
#  and it means ANY file dropped in sites-enabled is parsed.  A
#  filebrowsers.conf.bak-* left there would be a second complete copy of the
#  proto.bar server block: the count above goes 3 -> 5, nginx warns about a
#  conflicting server name, and certbot then rewrites both copies on renewal.
#
#  Note the habit this box already has -- surfd.conf.b64bak-*,
#  surfd-ratelimit.conf.b64bak-* -- is safe only by accident of location:
#  conf.d is globbed *.conf so a .b64bak suffix misses it.  In sites-enabled the
#  same habit is loaded.  Nothing includes /etc/nginx itself, so here is safe.
# -----------------------------------------------------------------------------
BAK="/etc/nginx/filebrowsers.conf.bak-$TS"
cp -p "$VHOST" "$BAK"
echo "== backed up vhost -> $BAK =="

echo "== installing snippet =="
SNIP_BAK=""
if [ -f "$SNIP" ]; then
    SNIP_BAK="/etc/nginx/ftesurf.conf.bak-$TS"
    cp -p "$SNIP" "$SNIP_BAK"
    echo "   previous snippet -> $SNIP_BAK (restore with the vhost backup)"
fi
install -m 0644 -o root -g root "$SRC" "$SNIP"
echo "   $SNIP  ($(wc -c < "$SNIP") bytes)"

# -----------------------------------------------------------------------------
#  Add the include line ABOVE the filebrowser catch-all, exactly like the
#  globe.conf / whodunchat.conf lines already in that server block.  Order
#  matters: `location ^~ /ftesurf/` must be parsed, and nginx picks the longest
#  matching ^~ prefix regardless of file order -- but keeping it above `location
#  / {` matches the house style and keeps the file readable.
# -----------------------------------------------------------------------------
if grep -q 'snippets/ftesurf.conf' "$VHOST"; then
    echo "== include line already present, leaving it =="
else
    echo "== adding include line to $VHOST =="
    TMP=$(mktemp)
    awk '
        /^[[:space:]]*location \/ \{/ && !done {
            print "    # proto.bar/ftesurf -- the download page.  All of its config lives in"
            print "    # one snippet, so a certbot rewrite can only lose this single line."
            print "    include /etc/nginx/snippets/ftesurf.conf;"
            print ""
            done = 1
        }
        { print }
    ' "$VHOST" > "$TMP"
    # Refuse a no-op or a truncation rather than installing a broken vhost.
    if ! grep -q 'snippets/ftesurf.conf' "$TMP"; then
        rm -f "$TMP"
        echo "FAILED: could not find a 'location / {' line to insert above in $VHOST" >&2
        echo "        add this line by hand, above the catch-all:" >&2
        echo "            include /etc/nginx/snippets/ftesurf.conf;" >&2
        exit 1
    fi
    if [ "$(wc -l < "$TMP")" -le "$(wc -l < "$VHOST")" ]; then
        rm -f "$TMP"; echo "FAILED: rewritten vhost is not longer than the original; aborting" >&2; exit 1
    fi
    cat "$TMP" > "$VHOST"        # preserves the original mode/owner
    rm -f "$TMP"
fi

# -----------------------------------------------------------------------------
#  Content dirs.  proto owns /srv/nvme, so every future release needs no sudo.
# -----------------------------------------------------------------------------
mkdir -p "$SITE/releases" "$SITE/.incoming"
chown -R proto:proto "$SITE" 2>/dev/null || true
chmod -R a+rX "$SITE"

echo "== nginx -t =="
if ! OUT=$(nginx -t 2>&1); then
    echo "$OUT" >&2
    echo "FAILED: nginx -t did not pass; no reload performed." >&2
    echo "Restore vhost: cp -p $BAK $VHOST" >&2
    if [ -n "$SNIP_BAK" ]; then
        echo "Restore snippet: cp -p $SNIP_BAK $SNIP" >&2
    fi
    echo "Then: nginx -t (and reload only after it passes)." >&2
    exit 1
fi
echo "$OUT"
# The direct detector for a stray copy of the server block. It fires immediately
# and by name, where a count is only a second opinion.
if echo "$OUT" | grep -qi 'conflicting server name'; then
    echo "FAILED: nginx reports a conflicting server name -- something is duplicating the" >&2
    echo "        proto.bar server block. Check for stray files in /etc/nginx/sites-enabled/." >&2
    exit 1
fi

systemctl reload nginx
echo "== reloaded =="

AFTER=$(nginx -T 2>/dev/null | grep -c 'server_name proto.bar;' || true)
echo "   server_name proto.bar count after: $AFTER  (must equal $BEFORE)"
[ "$AFTER" = "$BEFORE" ] || { echo "FAILED: the server_name count changed -- a duplicate vhost got loaded" >&2; exit 1; }

# Probe both prefixes through this nginx, not public DNS. A filebrowser SPA
# can answer 200 too: require the marker, JSON type and actual board envelope.
PROBE=$(mktemp -d)
trap 'rm -f "$PROBE/headers" "$PROBE/body"; rmdir "$PROBE"' EXIT
trap 'exit 1' HUP INT TERM
for BASE in ftesurf worldofsurf; do
    curl --fail --silent --show-error --max-time 10 \
        --resolve proto.bar:443:127.0.0.1 \
        -D "$PROBE/headers" -o "$PROBE/body" \
        "https://proto.bar/$BASE/board/api/maps"
    python3 - "$PROBE/headers" "$PROBE/body" <<'PY'
import json
import pathlib
import re
import sys
headers = pathlib.Path(sys.argv[1]).read_text().lower()
if not re.search(r"^x-ftesurf-site:\s*1\s*$", headers, re.M):
    sys.exit("FAILED: missing site marker (filebrowser fallback?)")
if not re.search(r"^content-type:\s*application/json(?:[;\s]|$)", headers, re.M):
    sys.exit("FAILED: board did not serve JSON")
body = json.loads(pathlib.Path(sys.argv[2]).read_text())
if not isinstance(body, dict) or body.get("v") != 1 or not isinstance(body.get("maps"), list):
    sys.exit("FAILED: not the board maps envelope")
PY
    echo "   GET /$BASE/board/api/maps -> marked board JSON"
done

echo
echo "Installed parallel routes; SURFD_BOARD_URL and release defaults are unchanged."
echo "This is NOT the canonical-path/account cutover. See REBRANDING_PLAN.md."
echo "If a page is already staged: sh $SITE/publish.sh <version>"
echo "Check both paths: curl -sI https://proto.bar/worldofsurf/ | grep -i x-ftesurf-site"
