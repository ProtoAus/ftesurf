#!/bin/sh
# P1099: serve /ftesurf/media/ on play.proto.bar. Run once:
#   sudo sh /path/to/owned/install_media_nginx.sh [media.nginx]
# Backs the site file up outside sites-enabled (nginx loads everything in there),
# adds one include after ftesurf-maps.conf's, and puts both back if nginx -t fails.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE=${1:-"$HERE/media.nginx"}
EXPECTED=${2:-}
SITE=/etc/nginx/sites-enabled/play.proto.bar.conf
SNIP=/etc/nginx/snippets/ftesurf-media.conf
BAK=/etc/nginx/play.proto.bar.conf.pre-p1099-$(date -u +%Y%m%dT%H%M%SZ)
[ "$(id -u)" = 0 ] || { echo "run it with sudo"; exit 1; }
[ -f "$SITE" ] && [ ! -L "$SITE" ] || { echo "$SITE is not a regular file: nothing changed"; exit 1; }
[ -f "$SOURCE" ] && [ ! -L "$SOURCE" ] || { echo "media source is not a regular file: nothing changed"; exit 1; }
if [ -n "$EXPECTED" ]; then
    [ -f "$SNIP" ] && [ ! -L "$SNIP" ] || { echo "media preimage is not regular: nothing changed"; exit 1; }
    ACTUAL=$(sha256sum "$SNIP" | awk '{print $1}')
    [ "$ACTUAL" = "$EXPECTED" ] || { echo "media snippet changed since inspection: nothing changed"; exit 1; }
fi

# A rerun finds the snippet from the last run: it is put back, not deleted, or the
# restored site file would include a file that is gone (review 1).
undo() {
    cp -a "$BAK" "$SITE"
    if [ -f "$BAK.snippet" ]; then cp -a "$BAK.snippet" "$SNIP"; else rm -f "$SNIP"; fi
    nginx -t && echo "P1099 media: put back, nothing changed" || echo "P1099 media: PUT BACK BUT nginx -t STILL FAILS"
    exit 1
}

cp -a "$SITE" "$BAK"
[ ! -f "$SNIP" ] || cp -a "$SNIP" "$BAK.snippet"
install -m 644 -o root -g root "$SOURCE" "$SNIP"
if ! grep -q 'include snippets/ftesurf-media.conf;' "$SITE"; then
    sed -i 's|^\([[:space:]]*\)include snippets/ftesurf-maps.conf;|&\n\1include snippets/ftesurf-media.conf;|' "$SITE"
fi
[ "$(grep -c 'include snippets/ftesurf-media.conf;' "$SITE")" = 1 ] || { echo "the include was not added once"; undo; }
nginx -t || undo
systemctl reload nginx
echo "P1099 media: installed (site backup $BAK)"
