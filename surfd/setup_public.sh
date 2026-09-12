#!/bin/sh
# setup_public.sh -- put the FTESurf directory on play.proto.bar.
#
#     cd /srv/nvme/surfd && sudo ./setup_public.sh            # phase 1
#     cd /srv/nvme/surfd && sudo ./setup_public.sh --advertise # phase 2
#
# TWO PHASES, AND THE SPLIT IS THE WHOLE DESIGN.
#
# Phase 1 makes the directory READABLE from the internet: nginx vhost, TLS,
# /lobbies.json and /admin. It does not change a single advertised address, so
# nothing that works today stops working. Strangers can read the list; the rows
# still say 192.168.1.102 and are still only useful on the LAN.
#
# Phase 2 changes what the directory ADVERTISES, by setting SURFD_PUBLIC_HOST.
# It must not run until the router actually forwards the game ports, because
# a row pointing at a port nobody can reach is worse than a row pointing at a
# LAN address: the player gets a lobby in the list, clicks it, and waits for a
# timeout instead of seeing "no lobbies". Phase 2 therefore refuses to run
# until you confirm the forwards exist, and tells you how to check.
#
# WHAT IT NEVER DOES: it does not touch SURFD_KEY, it does not open the game
# ports (that is the router, and it is not reachable from here), and it does
# not turn off SURFD_ADMIN_INSECURE_COOKIE for you -- phase 1 warns about that
# instead, because removing it is what makes the admin login safe over TLS and
# doing it silently would hide the decision.
set -e

HOME_DIR="${SURFD_HOME:-/srv/nvme/surfd}"
ENV_FILE="$HOME_DIR/surfd.env"
HOSTNAME_PUBLIC="${PUBLIC_HOST:-play.proto.bar}"
PORTS="27510 27520 27530 27540 27550"

[ "$(id -u)" = "0" ] || { echo "run me with sudo -- I install nginx config." >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "no $ENV_FILE -- is SURFD_HOME right?" >&2; exit 1; }

# --------------------------------------------------------------------------
# Phase 2: advertise the public host
# --------------------------------------------------------------------------
if [ "$1" = "--advertise" ]; then
    echo "PHASE 2 -- change what the directory advertises."
    echo
    echo "This sets SURFD_PUBLIC_HOST=$HOSTNAME_PUBLIC, after which every"
    echo "heartbeat from this machine is recorded as $HOSTNAME_PUBLIC:<port>"
    echo "instead of 192.168.1.102:<port>."
    echo
    echo "DO NOT DO THIS until the router forwards UDP $PORTS to"
    echo "192.168.1.102. Until then the rows point nowhere and a player gets a"
    echo "connection timeout rather than an empty list -- which is worse."
    echo
    echo "Check from a phone on mobile data (not wifi):"
    echo "    https://$HOSTNAME_PUBLIC/lobbies.json   should list five lobbies"
    echo "and then actually join one from a machine outside your network."
    echo
    printf 'Have you forwarded UDP %s at the router? [type yes] ' "$PORTS"
    read -r ANSWER
    [ "$ANSWER" = "yes" ] || { echo "Nothing changed."; exit 0; }

    cp -p "$ENV_FILE" "$ENV_FILE.bak-public"
    TMP=$(mktemp "$HOME_DIR/.surfd.env.XXXXXX")
    chmod 600 "$TMP"
    grep -v '^SURFD_PUBLIC_HOST=' "$ENV_FILE" > "$TMP"
    echo "SURFD_PUBLIC_HOST=$HOSTNAME_PUBLIC" >> "$TMP"
    mv -f "$TMP" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    chown --reference="$ENV_FILE.bak-public" "$ENV_FILE" 2>/dev/null || true
    echo "set SURFD_PUBLIC_HOST=$HOSTNAME_PUBLIC (backup: surfd.env.bak-public)"

    systemctl restart surfd
    sleep 3
    echo
    echo "The directory now says:"
    curl -fsS -m 5 http://127.0.0.1:8084/lobbies.json \
      | tr ',' '\n' | grep -i addr || echo "  (could not read /lobbies.json)"
    echo
    echo "Every addr above should say $HOSTNAME_PUBLIC. If any still says"
    echo "192.168.1.102, surfd did not accept the host -- look for a line"
    echo "mentioning SURFD_PUBLIC_HOST:  journalctl -u surfd -n 40"
    exit 0
fi

# --------------------------------------------------------------------------
# Phase 1: make the directory reachable
# --------------------------------------------------------------------------
echo "PHASE 1 -- publish the directory on https://$HOSTNAME_PUBLIC"
echo

# DNS first: certbot's HTTP-01 challenge cannot work without it, and the error
# it gives for a missing record is much less clear than this one.
RESOLVED=$(getent hosts "$HOSTNAME_PUBLIC" | awk '{print $1}' | head -1)
if [ -z "$RESOLVED" ]; then
    echo "$HOSTNAME_PUBLIC does not resolve. Add a DNS A record pointing at" >&2
    echo "your public IP before running this." >&2
    exit 1
fi
echo "  DNS: $HOSTNAME_PUBLIC -> $RESOLVED"

command -v certbot >/dev/null 2>&1 || {
    echo "certbot is not installed. apt install certbot python3-certbot-nginx" >&2
    exit 1
}

install -m 0644 "$HOME_DIR/surfd.nginx"  /etc/nginx/snippets/surfd.conf
install -m 0644 "$HOME_DIR/admin.nginx"  /etc/nginx/snippets/surfd-admin.conf
echo "  installed /etc/nginx/snippets/surfd.conf and surfd-admin.conf"

# The rate-limit zone must live in http{}, not in a location -- nginx refuses
# to start otherwise, which would take every other site on this box down too.
ZONE='limit_req_zone $binary_remote_addr zone=surfdlogin:1m rate=12r/m;'
if ! grep -qrs "zone=surfdlogin" /etc/nginx/nginx.conf /etc/nginx/conf.d/ 2>/dev/null; then
    printf '%s\n' "$ZONE" > /etc/nginx/conf.d/surfd-ratelimit.conf
    echo "  added the surfdlogin rate-limit zone in conf.d"
else
    echo "  rate-limit zone already present"
fi

# The vhost references a certificate that does not exist yet, and nginx will
# not start without it. Install a cert-less port-80 stub first, let certbot
# create the cert and rewrite the vhost, then drop the real file in.
cat > /etc/nginx/sites-available/play.proto.bar.conf <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $HOSTNAME_PUBLIC;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 404; }
}
EOF
ln -sf /etc/nginx/sites-available/play.proto.bar.conf \
       /etc/nginx/sites-enabled/play.proto.bar.conf
nginx -t
systemctl reload nginx
echo "  port-80 stub live; requesting a certificate"

if [ ! -d "/etc/letsencrypt/live/$HOSTNAME_PUBLIC" ]; then
    # --nginx first: it is the plugin this box's other certificates were issued
    # with (every vhost carries certbot's "# managed by Certbot" markers), so it
    # is the path known to work here. It serves the challenge by editing nginx
    # itself, which means it does not care what the port-80 docroot is.
    #
    # --webroot is the fallback for the case where the plugin cannot parse a
    # vhost. It needs the challenge to land under the same root the stub above
    # serves, hence -w /var/www/html matching `root /var/www/html`.
    if certbot certonly --nginx -d "$HOSTNAME_PUBLIC" \
            --non-interactive --agree-tos --register-unsafely-without-email; then
        echo "  certificate obtained (nginx plugin)"
    elif certbot certonly --webroot -w /var/www/html -d "$HOSTNAME_PUBLIC" \
            --non-interactive --agree-tos --register-unsafely-without-email; then
        echo "  certificate obtained (webroot)"
    else
        echo >&2
        echo "certbot failed both ways. The usual causes, in order:" >&2
        echo "  * TCP 80 is not reaching this machine from the internet." >&2
        echo "    Let's Encrypt validates over port 80 even for an https site." >&2
        echo "  * DNS for $HOSTNAME_PUBLIC does not point at this network." >&2
        echo "  * Rate limit: 5 failures per account per hostname per hour." >&2
        echo "Nothing has been broken -- the port-80 stub is harmless and the" >&2
        echo "other sites on this box are untouched." >&2
        exit 1
    fi
else
    echo "  certificate already exists, keeping it"
fi

install -m 0644 "$HOME_DIR/play.nginx" \
        /etc/nginx/sites-available/play.proto.bar.conf
nginx -t
systemctl reload nginx
echo "  vhost live"

echo
echo "Checking from this machine:"
curl -fsS -m 8 "https://$HOSTNAME_PUBLIC/health" && echo || \
    echo "  /health did not answer over TLS"
curl -fsS -o /dev/null -w "  /admin/login -> HTTP %{http_code}\n" -m 8 \
    "https://$HOSTNAME_PUBLIC/admin/login" || true
echo "  /api/heartbeat should be 404 from outside:"
curl -fsS -o /dev/null -w "  /api/heartbeat -> HTTP %{http_code}\n" -m 8 \
    "https://$HOSTNAME_PUBLIC/api/heartbeat" 2>/dev/null || \
    echo "  /api/heartbeat -> refused or 404 (correct)"

echo
if grep -q '^SURFD_ADMIN_INSECURE_COOKIE=' "$ENV_FILE"; then
    echo "!! SURFD_ADMIN_INSECURE_COOKIE is still set in surfd.env."
    echo "   The admin session cookie will be sent without the Secure flag,"
    echo "   which is exactly what you no longer need now that TLS works."
    echo "   Remove that line and restart surfd:"
    echo "       sudo sed -i '/^SURFD_ADMIN_INSECURE_COOKIE=/d' $ENV_FILE"
    echo "       sudo systemctl restart surfd"
    echo
fi
echo "Phase 1 done. The directory is readable at https://$HOSTNAME_PUBLIC"
echo "but still advertises LAN addresses, which is correct until the router"
echo "forwards UDP $PORTS to 192.168.1.102."
echo
echo "Then:  sudo ./setup_public.sh --advertise"
