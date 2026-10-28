#!/bin/sh
# P1099: serve /ftesurf/media/ on play.proto.bar. Run once:
#   sudo sh /srv/nvme/agent-work/lexmaps-media1099/install_media_nginx.sh
# Backs the site file up outside sites-enabled (nginx loads everything in there),
# adds one include after ftesurf-maps.conf's, and puts both back if nginx -t fails.
set -eu
HERE=/srv/nvme/agent-work/lexmaps-media1099
SITE=/etc/nginx/sites-enabled/play.proto.bar.conf
SNIP=/etc/nginx/snippets/ftesurf-media.conf
BAK=/etc/nginx/play.proto.bar.conf.pre-p1099-$(date -u +%Y%m%dT%H%M%SZ)
[ "$(id -u)" = 0 ] || { echo "run it with sudo"; exit 1; }
[ -f "$SITE" ] && [ ! -L "$SITE" ] || { echo "$SITE is not a regular file: nothing changed"; exit 1; }

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
install -m 644 -o root -g root "$HERE/ftesurf-media.conf" "$SNIP"
if ! grep -q 'include snippets/ftesurf-media.conf;' "$SITE"; then
    sed -i 's|^\([[:space:]]*\)include snippets/ftesurf-maps.conf;|&\n\1include snippets/ftesurf-media.conf;|' "$SITE"
fi
[ "$(grep -c 'include snippets/ftesurf-media.conf;' "$SITE")" = 1 ] || { echo "the include was not added once"; undo; }
nginx -t || undo
systemctl reload nginx
echo "P1099 media: installed (site backup $BAK)"
