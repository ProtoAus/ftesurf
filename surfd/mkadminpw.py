#!/usr/bin/env python3
"""
mkadminpw.py -- generate the admin panel's credentials.

Run it ON THE PI, as the proto user:

    cd /srv/nvme/surfd
    python3 mkadminpw.py

It prompts for a password (twice, not echoed), prints the three lines to add to
surfd.env, and never writes anything itself. It does not write the file because
surfd.env already holds the game-server shared secret, and a script that
rewrites a secrets file is a script that can truncate one.

WHY A SCRIPT AND NOT A WEB "CHANGE PASSWORD" FORM: the panel is a public login,
and every authenticated write path is a way to lose the account. Rotating the
password means shell access to the Pi, which is a much smaller set of people
than "whoever currently holds a session". Rotation is:

    python3 mkadminpw.py          # gives new SURFD_ADMIN_HASH
    # paste it into surfd.env, keeping SURFD_ADMIN_SECRET the same
    sudo systemctl restart surfd  # or ./stop.sh && ./run.sh

Changing SURFD_ADMIN_SECRET as well invalidates every existing session, which
is what you want if you think one has been stolen.
"""

import getpass
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from admin import SCRYPT_N, SCRYPT_P, SCRYPT_R, hash_password  # noqa: E402

MIN_LEN = 12


def main():
    print(__doc__.strip().split("\n\n")[0])
    print()
    if sys.stdin.isatty():
        pw = getpass.getpass("New admin password: ")
        again = getpass.getpass("Again: ")
        if pw != again:
            print("They do not match.", file=sys.stderr)
            return 2
    else:
        # Allows `echo hunter2 | python3 mkadminpw.py` in a provisioning
        # script. Warns, because that puts the password in shell history.
        pw = sys.stdin.readline().rstrip("\n")
        print("(read from stdin -- remember it is in your shell history)",
              file=sys.stderr)

    if len(pw) < MIN_LEN:
        print("Too short: %d characters, minimum %d. This login is going to be "
              "reachable from the internet." % (len(pw), MIN_LEN), file=sys.stderr)
        return 2

    print("hashing with scrypt N=%d r=%d p=%d ..." % (SCRYPT_N, SCRYPT_R, SCRYPT_P),
          file=sys.stderr)
    encoded = hash_password(pw)
    session_secret = secrets.token_urlsafe(48)

    print()
    print("Add these to /srv/nvme/surfd/surfd.env (mode 0600), then restart surfd.")
    print("Keep SURFD_ADMIN_SECRET stable across restarts or everyone is logged out.")
    print()
    print("SURFD_ADMIN_HASH=%s" % encoded)
    print("SURFD_ADMIN_SECRET=%s" % session_secret)
    print()
    print("# The lobbies' rcon password, so the panel can reach them on loopback.")
    print("# This is the value of rcon_password in cfg/lobby.cfg. Once the panel")
    print("# is the only rcon user, move it out of lobby.cfg into lobby_local.cfg")
    print("# and set `sv_crypt_rcon 1` so the plaintext form is refused.")
    print("SURFD_RCON_PASSWORD=<the servers' rcon_password>")
    print()
    print("Optional, defaults shown:")
    print("#SURFD_ADMIN_LOBBIES=1:27510,2:27520,3:27530,4:27540,5:27550")
    print("#SURFD_ADMIN_INSECURE_COOKIE=0   # 1 only for LAN testing without TLS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
