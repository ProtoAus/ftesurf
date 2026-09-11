#!/usr/bin/env python3
"""
test_surfd.py -- the falsifier for surfd's address derivation.

Run it anywhere Flask is installed, against a THROWAWAY home directory:

    SURFD_HOME=/tmp/surfd-test python3 test_surfd.py

It never touches a live instance: every case re-imports surfd with a fresh
SURFD_HOME, its own DB and its own env file.

WHAT IT IS FOR.  PUBLIC_HOST is the single point where a lobby address does not
come from the socket, so it is the single point where getting it wrong hands
every player either an unreachable address or somebody else's server.  The two
cases that matter are the two that must NOT change:

    * an untrusted source must still be recorded at its own address, and
    * with SURFD_PUBLIC_HOST unset, the whole file must behave exactly as it did
      before the option existed.

A test that only proved the new path works would prove nothing about either.
"""

import importlib
import os
import shutil
import sys
import tempfile

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-58s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def fresh(public_host=None, trusted=None, key="testkey", file_settings=None):
    """Import surfd with a clean home dir and the given environment.

    `file_settings` go into surfd.env instead of the environment. That is the
    path that matters in the real deployment: surfd.service has no
    EnvironmentFile= line, so surfd.env is the ONLY place an operator's setting
    can live and still be seen.
    """
    home = tempfile.mkdtemp(prefix="surfd-test-")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=%s\n" % key)
        for k, v in (file_settings or {}).items():
            fh.write("%s=%s\n" % (k, v))
    os.environ["SURFD_HOME"] = home
    os.environ["SURFD_DB"] = os.path.join(home, "test.db")
    os.environ["SURFD_ENV"] = os.path.join(home, "surfd.env")
    os.environ.pop("SURFD_PUBLIC_HOST", None)
    os.environ.pop("SURFD_TRUSTED", None)
    if public_host is not None:
        os.environ["SURFD_PUBLIC_HOST"] = public_host
    if trusted is not None:
        os.environ["SURFD_TRUSTED"] = trusted
    sys.modules.pop("surfd", None)
    mod = importlib.import_module("surfd")
    mod._test_home = home
    return mod


def beat(mod, src, node="p27510", port=27510, key="testkey", mapname=None):
    """POST one heartbeat from `src` and return the addr surfd recorded for it.

    /lobbies.json returns EVERY live row, ordered by players then map -- so the
    row we just wrote is not necessarily rows[0].  Reading rows[0] made two
    cases here silently assert against the previous heartbeat instead of their
    own, which is exactly the shape of bug a directory test exists to catch.
    Each call therefore uses a unique map name and looks its own row up by it.
    """
    if mapname is None:
        mapname = "map_%s_%d" % (node, port)
    client = mod.app.test_client()
    resp = client.post(
        "/api/heartbeat",
        data={"key": key, "node": node, "map": mapname,
              "players": "0", "max": "32", "port": str(port), "name": "t"},
        environ_base={"REMOTE_ADDR": src},
    )
    if resp.status_code != 200:
        return "HTTP %d" % resp.status_code
    rows = client.get("/lobbies.json").get_json()["lobbies"]
    mine = [r for r in rows if r["map"] == mapname]
    if len(mine) != 1:
        return "expected 1 row for %s, saw %d" % (mapname, len(mine))
    return mine[0]["addr"]


def main():
    homes = []

    # ---- 1. the new path: a trusted source gets the public name -------------
    m = fresh(public_host="play.proto.bar", trusted="127.0.0.0/8,192.168.0.0/16")
    homes.append(m._test_home)
    check("trusted LAN source -> public host",
          beat(m, "192.168.1.102"), "play.proto.bar:27510")
    check("trusted loopback source -> public host",
          beat(m, "127.0.0.1", node="p27520", port=27520), "play.proto.bar:27520")

    # ---- 2. THE CASE THAT MUST NOT CHANGE: a stranger keeps their own IP ----
    check("UNTRUSTED source keeps its own address",
          beat(m, "203.0.113.9", node="pX", port=27500), "203.0.113.9:27500")

    # ---- 3. THE OTHER CASE THAT MUST NOT CHANGE: option off = old behaviour -
    m2 = fresh()                       # no SURFD_PUBLIC_HOST at all
    homes.append(m2._test_home)
    check("PUBLIC_HOST unset -> source address (old behaviour)",
          beat(m2, "192.168.1.102"), "192.168.1.102:27510")

    # ---- 4. trusted list empty: the option is inert -------------------------
    m3 = fresh(public_host="play.proto.bar", trusted="")
    homes.append(m3._test_home)
    check("PUBLIC_HOST set but nothing trusted -> source address",
          beat(m3, "192.168.1.102"), "192.168.1.102:27510")

    # ---- 5. a bad key is still rejected -------------------------------------
    m4 = fresh(public_host="play.proto.bar", trusted="192.168.0.0/16")
    homes.append(m4._test_home)
    check("wrong key rejected even from a trusted source",
          beat(m4, "192.168.1.102", key="wrong"), "HTTP 403")

    # ---- 6. malformed PUBLIC_HOST values are refused, not passed through ----
    for bad, why in (
        ("https://play.proto.bar", "scheme"),
        ("play.proto.bar:27510", "port"),
        ("play.proto.bar/lobbies", "path"),
        ("play proto bar", "space"),
        ("-bad.example.com", "leading dash"),
        ("a" * 60, "too long for the menu's 64-char addr"),
    ):
        mb = fresh(public_host=bad, trusted="192.168.0.0/16")
        homes.append(mb._test_home)
        check("refused (%s): falls back to source addr" % why,
              beat(mb, "192.168.1.102"), "192.168.1.102:27510")

    # ---- 7. a bare IPv4 literal is a legitimate PUBLIC_HOST -----------------
    m5 = fresh(public_host="180.150.62.57", trusted="192.168.0.0/16")
    homes.append(m5._test_home)
    check("bare IPv4 literal accepted",
          beat(m5, "192.168.1.102"), "180.150.62.57:27510")

    # ---- 8. the settings must be readable from surfd.env -------------------
    # surfd.service has no EnvironmentFile=, so surfd.env is the ONLY place an
    # operator can put these and have them seen. Reading os.environ alone made
    # the setting a no-op -- which for PUBLIC_HOST would mean quietly
    # advertising a LAN address to the internet at the exact moment of going
    # public, with nothing logged, because "unset" is a valid configuration.
    m6 = fresh(file_settings={"SURFD_PUBLIC_HOST": "play.proto.bar",
                              "SURFD_TRUSTED": "192.168.0.0/16"})
    homes.append(m6._test_home)
    check("PUBLIC_HOST read from surfd.env with an empty environment",
          beat(m6, "192.168.1.102"), "play.proto.bar:27510")
    check("TRUSTED read from surfd.env too (untrusted source unaffected)",
          beat(m6, "203.0.113.9", node="pX", port=27530), "203.0.113.9:27530")

    # Quoting: shell-style quotes must be stripped, as load_secret already does.
    m7 = fresh(file_settings={"SURFD_PUBLIC_HOST": '"play.proto.bar"',
                              "SURFD_TRUSTED": "192.168.0.0/16"})
    homes.append(m7._test_home)
    check("a quoted value in surfd.env is unquoted",
          beat(m7, "192.168.1.102"), "play.proto.bar:27510")

    # The environment still wins, so a systemd override beats the file.
    m8 = fresh(public_host="env.example.com", trusted="192.168.0.0/16",
               file_settings={"SURFD_PUBLIC_HOST": "file.example.com"})
    homes.append(m8._test_home)
    check("the environment overrides surfd.env",
          beat(m8, "192.168.1.102"), "env.example.com:27510")

    # PRESENT-BUT-EMPTY IS NOT ABSENT. `SURFD_TRUSTED=` means "trust nothing";
    # falling back to the default trust list there would silently re-enable the
    # address rewrite the operator just turned off. This caught a real
    # regression when the file fallback was added, so it is checked from the
    # file as well as from the environment.
    m9 = fresh(file_settings={"SURFD_PUBLIC_HOST": "play.proto.bar",
                              "SURFD_TRUSTED": ""})
    homes.append(m9._test_home)
    check("an EMPTY SURFD_TRUSTED in the file trusts nothing",
          beat(m9, "192.168.1.102"), "192.168.1.102:27510")

    for h in homes:
        shutil.rmtree(h, ignore_errors=True)

    print()
    if FAILED:
        print("%d FAILURE(S):" % len(FAILED))
        for f in FAILED:
            print("  " + f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
