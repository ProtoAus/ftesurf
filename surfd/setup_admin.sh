#!/bin/sh
# setup_admin.sh -- turn the FTESurf admin panel on, in one step.
#
#     cd /srv/nvme/surfd && ./setup_admin.sh
#
# Prompts for a password, generates the credentials, wires in the lobbies' rcon
# password, and restarts surfd. Re-run it any time to ROTATE the password; it
# replaces its own lines rather than appending duplicates.
#
# WHAT IT WILL NOT DO:
#   * It never prints a secret. The admin password is read with a hidden
#     prompt, the rcon password is copied out of cfg/lobby.cfg without being
#     displayed, and nothing is echoed back.
#   * It never rewrites SURFD_KEY. That is the game servers' shared secret and
#     losing it would silently stop every heartbeat; this script only ever
#     touches the three SURFD_ADMIN_* / SURFD_RCON_* lines, and it backs the
#     file up first regardless.
#   * It does not open the panel to the internet. That still needs the nginx
#     block in admin.nginx plus TLS, both deliberately not installed.
set -e

HOME_DIR="${SURFD_HOME:-/srv/nvme/surfd}"
ENV_FILE="$HOME_DIR/surfd.env"
LOBBY_CFG="${LOBBY_CFG:-/srv/nvme/ftesurf-server/game/ftesurf/cfg/lobby.cfg}"

cd "$HOME_DIR"

[ -f "$ENV_FILE" ] || { echo "no $ENV_FILE -- is SURFD_HOME right?" >&2; exit 1; }

# ---- the lobbies' rcon password, read not typed -----------------------------
# The panel reaches the game servers over rcon on 127.0.0.1; this is the value
# of rcon_password in the server's own config. Extracted rather than asked for,
# so it cannot be mistyped and does not end up in shell history.
RCON=$(sed -n 's/^[[:space:]]*\(set\|seta\)\{0,1\}[[:space:]]*rcon_password[[:space:]]*"\{0,1\}\([^"[:space:]]*\).*/\2/p' \
       "$LOBBY_CFG" 2>/dev/null | head -1)
if [ -z "$RCON" ]; then
    echo "WARNING: no rcon_password found in $LOBBY_CFG."
    echo "         The panel will load and show systemd state and the directory"
    echo "         table, but every game-server control will be refused."
    echo
fi

# ---- the admin password -----------------------------------------------------
printf 'New admin password (at least 12 characters): '
stty -echo 2>/dev/null || true
read -r PW1
stty echo 2>/dev/null || true
printf '\nAgain: '
stty -echo 2>/dev/null || true
read -r PW2
stty echo 2>/dev/null || true
printf '\n'

[ "$PW1" = "$PW2" ] || { echo "They do not match." >&2; exit 2; }
[ ${#PW1} -ge 12 ] || { echo "Too short (${#PW1}); this login faces the internet." >&2; exit 2; }

echo "hashing (scrypt, ~32 MB, a second or two) ..."
HASH=$(PW="$PW1" python3 -c '
import os, sys
sys.path.insert(0, os.environ.get("SURFD_HOME", "/srv/nvme/surfd"))
from admin import hash_password
print(hash_password(os.environ["PW"]))
')
SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')

# ---- write it ---------------------------------------------------------------
cp -p "$ENV_FILE" "$ENV_FILE.bak"
TMP=$(mktemp "$HOME_DIR/.surfd.env.XXXXXX")
chmod 600 "$TMP"

# Keep every line we do not own; drop our three so a re-run rotates rather
# than appends a second, shadowed copy.
grep -v '^SURFD_ADMIN_HASH=' "$ENV_FILE" \
  | grep -v '^SURFD_ADMIN_SECRET=' \
  | grep -v '^SURFD_RCON_PASSWORD=' > "$TMP"

{
  echo "SURFD_ADMIN_HASH=$HASH"
  echo "SURFD_ADMIN_SECRET=$SECRET"
  [ -n "$RCON" ] && echo "SURFD_RCON_PASSWORD=$RCON"
} >> "$TMP"

mv -f "$TMP" "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "wrote $ENV_FILE (previous copy kept as surfd.env.bak)"

# ---- restart ----------------------------------------------------------------
echo
echo "restarting surfd (sudo will ask for your password) ..."
if sudo systemctl restart surfd; then
    sleep 2
    if curl -fsS -m 5 http://127.0.0.1:8084/health >/dev/null 2>&1; then
        echo "surfd is up."
    else
        echo "surfd restarted but /health did not answer -- check: journalctl -u surfd -n 40"
        exit 1
    fi
else
    echo "restart failed. Run it yourself:  sudo systemctl restart surfd"
    exit 1
fi

echo
if journalctl -u surfd -n 60 --no-pager 2>/dev/null | grep -q "admin panel enabled"; then
    echo "The admin panel is ON."
else
    echo "surfd is running but did not log 'admin panel enabled'."
    echo "Check why:  journalctl -u surfd -n 40 | grep -i admin"
fi
echo
echo "  http://192.168.1.102:8084/admin      (LAN only -- see below)"
echo
echo "IT WILL NOT WORK OVER PLAIN HTTP FROM A BROWSER, and that is deliberate:"
echo "the session cookie is set Secure, because a login cookie sent in the clear"
echo "is the whole credential. For LAN testing only, add this line to surfd.env"
echo "and restart again:"
echo
echo "    SURFD_ADMIN_INSECURE_COOKIE=1"
echo
echo "Take it back out before the panel is reachable from anywhere else."
