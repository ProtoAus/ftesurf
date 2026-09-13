#!/usr/bin/env python3
"""
test_join.py -- the falsifier for /api/join and the heartbeat control channel
(schema 4, build 67).

Run it anywhere Flask is installed, against a THROWAWAY home directory:

    SURFD_HOME=/tmp/surfd-test python3 test_join.py

It never touches a live instance: every case re-imports surfd with a fresh
SURFD_HOME, its own DB, its own env file and its own fake map library -- the
same harness the other three suites use, and for the same reason.

WHAT IT IS FOR.  This is the first endpoint in surfd that causes WORK ON A GAME
SERVER, and it is public and unauthenticated because the menu calls it before
the player has connected to anything.  So the cases that matter are the ones
where it would move a server it must not move, send two people to one server for
two different maps, or name a map that cannot be loaded:

  * A LOBBY WITH PLAYERS ON IT BEING MOVED (s4).  This is the entire anti-abuse
    rule and the only structural one there is.  Nobody may ever be thrown out of
    a run by a stranger's menu.
  * THE CLAIM LOSING A RACE IT SHOULD LOSE (s5).  Between the assignment and the
    lobby's next heartbeat a player can join.  The claim must lose, every time.
  * THE ON-DISK SPELLING (s2, s5).  `clean_map` lowercases because the board key
    must; ext4 does not, and six maps in the library carry capitals.  A
    `changelevel` argument rebuilt from the key misses every one of them and the
    symptom is "that map is not installed" for a map that is.  R3 and R4 both
    shipped this defect before it was caught; this suite is where it dies.
  * TWO ASKS, ONE SERVER (s3).  A second request in the load window must return
    the server already on its way, not claim a second one.
  * A MAP NAME FROM THE WIRE REACHING `changelevel` (s2).  The reply body is a
    console command on the other end.

Section 6 pins the schema-3 -> 4 upgrade against a seeded database, because
surfd migrates at import time and a database created afterwards is never a v3
one.
"""

import importlib
import json
import os
import sqlite3
import sys
import tempfile

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-58s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


# THE FAKE LIBRARY.  Deliberately mirrors the real one's awkward cases rather
# than a tidy set: a capitalised name, a name that differs from its own key only
# in case, and a map with no zone file -- which is the majority case in the
# shipped library (781 of 1312) and the one most likely to be handled by
# accident rather than on purpose.
LIBRARY = ["surf_kitsune", "surf_lux", "surf_ace", "Bhop_Mukiology", "bhop_HeLL"]
ZONED = ["surf_kitsune", "surf_lux", "Bhop_Mukiology"]


def fresh(key="testkey", seed_v3=False, library=None, zoned=None):
    """Import surfd with a clean home dir and a fake map library."""
    home = tempfile.mkdtemp(prefix="surfd-join-")
    db = os.path.join(home, "test.db")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=%s\n" % key)

    if seed_v3:
        conn = sqlite3.connect(db)
        conn.executescript(
            """
            CREATE TABLE lobbies (
                node       TEXT    PRIMARY KEY,
                map        TEXT    NOT NULL,
                players    INTEGER NOT NULL,
                maxplayers INTEGER NOT NULL,
                addr       TEXT    NOT NULL,
                name       TEXT    NOT NULL,
                last_seen  INTEGER NOT NULL
            );
            INSERT INTO lobbies VALUES
                ('p27510','surf_legacy',0,16,'10.0.0.1:27510','Legacy',2000000000);
            PRAGMA user_version=3;
            """
        )
        conn.commit()
        conn.close()

    # The library is per-case and MUST be set before the import: MAPS_DIR and
    # ZONES_DIR are module constants read once at import, which is exactly what
    # stops a test ever reaching the live /srv/nvme default.
    maps = os.path.join(home, "maps")
    zones = os.path.join(maps, "zones", "online")
    os.makedirs(zones, exist_ok=True)
    for name in (LIBRARY if library is None else library):
        open(os.path.join(maps, name + ".bsp"), "wb").close()
    for name in (ZONED if zoned is None else zoned):
        open(os.path.join(zones, name + ".json"), "wb").close()

    os.environ["SURFD_HOME"] = home
    os.environ["SURFD_DB"] = db
    os.environ["SURFD_MAPS"] = maps
    os.environ["SURFD_ZONES"] = zones
    os.environ["SURFD_ENV"] = os.path.join(home, "surfd.env")
    os.environ.pop("SURFD_PUBLIC_HOST", None)
    os.environ.pop("SURFD_TRUSTED", None)
    sys.modules.pop("surfd", None)
    mod = importlib.import_module("surfd")
    mod._test_home = home
    mod._test_db = db
    mod._test_maps = maps
    mod._test_zones = zones
    return mod


def beat(mod, node, mapname, players=0, maxplayers=16, port=None, key="testkey"):
    """One heartbeat. Returns the reply BODY as text, which is the new channel."""
    if port is None:
        port = int(node[1:]) if node[1:].isdigit() else 27510
    resp = mod.app.test_client().post("/api/heartbeat", data={
        "key": key, "node": node, "map": mapname, "players": str(players),
        "max": str(maxplayers), "port": str(port), "name": "Lobby " + node,
    })
    if resp.status_code != 200:
        return "HTTP %d" % resp.status_code
    return resp.get_data(as_text=True)


def join(mod, mapname, src="203.0.113.7"):
    """GET /api/join. Returns (status, parsed-json-or-raw-text)."""
    resp = mod.app.test_client().get(
        "/api/join?map=%s" % mapname, environ_overrides={"REMOTE_ADDR": src})
    try:
        return resp.status_code, json.loads(resp.get_data(as_text=True))
    except ValueError:
        return resp.status_code, resp.get_data(as_text=True)


def assignments(mod):
    conn = sqlite3.connect(mod._test_db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT node, map, map_dir FROM assignments ORDER BY node")]
    finally:
        conn.close()


def user_version(mod):
    conn = sqlite3.connect(mod._test_db)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------
print("\n--- 1. the installed library --------------------------------------")

m = fresh()
bsp, zoned = m.map_index()
check("the library index found every bsp", len(bsp), len(LIBRARY))
check("...keyed lowercase", sorted(bsp), sorted(n.lower() for n in LIBRARY))
check("...storing the ON-DISK spelling", bsp["bhop_mukiology"], "Bhop_Mukiology")
check("...and again for the other capitalised one", bsp["bhop_hell"], "bhop_HeLL")
check("the zone set is separate and smaller", len(zoned), len(ZONED))
check("...and is keyed lowercase too", "bhop_mukiology" in zoned, True)

# CONTROL: a library directory that is not there must not take surfd down with
# it. Every other endpoint is unaffected by this one directory moving.
m2 = fresh()
m2.MAPS_DIR = os.path.join(m2._test_home, "gone")
m2.ZONES_DIR = os.path.join(m2._test_home, "gone", "zones")
m2.maps_reset()
bsp2, zoned2 = m2.map_index()
check("CONTROL: a missing library is empty, not an exception", (bsp2, len(zoned2)),
      ({}, 0))
check("...and /lobbies.json still answers",
      m2.app.test_client().get("/lobbies.json").status_code, 200)

# live_rows() GAINED A COLUMN FOR /api/join AND MUST NOT HAVE PUBLISHED ONE.
# The claim is keyed on `node` -- the primary key -- rather than on the address,
# which SURFD_PUBLIC_HOST rewrites. lobbies_json builds its own dict field by
# field so it should be unaffected, and "should be" is not a test.
m3 = fresh()
beat(m3, "p27510", "surf_lux", players=2)
pub = json.loads(m3.app.test_client().get("/lobbies.json").get_data(as_text=True))
check("the directory still publishes exactly its old fields",
      sorted(pub["lobbies"][0]), ["addr", "age", "map", "max", "name", "players"])


# --------------------------------------------------------------------------
print("\n--- 2. which maps may be asked for ---------------------------------")

# TWO LOBBIES, NOT ONE, AND THE FIRST DRAFT OF THIS SECTION HAD ONE.  With a
# single lobby the first ask CLAIMS it, so the second ask has nothing left and
# reads 503 -- which is the endpoint behaving correctly and the fixture asking
# the wrong question. Kept as a note because the same shape will catch the next
# person: an ask here is not a read, it has an effect on the next one.
m = fresh()
beat(m, "p27510", "surf_ace")            # live, idle, somewhere else
beat(m, "p27520", "surf_ace")            # the one the claim will take

status, body = join(m, "surf_kitsune")
check("an installed, zoned map is answered", status, 200)
check("...and reports that it can be timed", body["timed"], 1)

status, body = join(m, "surf_ace")
check("a map somebody is already on is answered", status, 200)
check("...and it is the one that is already running", body["state"], "ready")

# A MAP WITH NO ZONE FILE IS HOSTED, NOT REFUSED. 781 of the shipped library's
# 1312 maps are in this state: they load perfectly and can never be timed.
# Refusing them would be surfd deciding a player may not walk around a map they
# own; the honest answer is "yes, and you cannot set a time here".
m = fresh()
beat(m, "p27510", "surf_ace")
status, body = join(m, "bhop_hell")
check("an UNZONED map is still hosted", status, 200)
check("...and says so rather than pretending", body["timed"], 0)

status, body = join(m, "surf_doesnotexist")
check("a map that is not installed is refused", status, 404)
check("...with a sentence the menu can show", "not installed" in body["error"], True)

for hostile, why in [
    ("../../../etc/passwd", "traversal"),
    ("surf/../../x",        "separators"),
    ("",                    "empty"),
    ("surf_a;quit",         "a console separator"),
    ("surf_a b",            "a space"),
]:
    status, body = join(m, hostile)
    check("a name with %s never reaches a map" % why, status in (400, 404), True)

# THE CAPITALISATION TRAP, WHICH IS THE WHOLE REASON THE INDEX EXISTS.
m = fresh()
beat(m, "p27510", "surf_ace")
status, body = join(m, "bhop_mukiology")     # as the board would spell it
check("a capitalised map is found from the lowercased key", status, 200)
check("...and is claimed under the key", assignments(m)[0]["map"], "bhop_mukiology")
check("...while the CHANGELEVEL argument keeps the disk's spelling",
      assignments(m)[0]["map_dir"], "Bhop_Mukiology")


# --------------------------------------------------------------------------
print("\n--- 3. reuse before assignment -------------------------------------")

m = fresh()
beat(m, "p27510", "surf_lux", players=2)
beat(m, "p27520", "surf_ace", players=0)

status, body = join(m, "surf_lux")
check("a lobby already on the map is handed straight back", body["state"], "ready")
check("...naming that lobby", body["addr"], "127.0.0.1:27510")
check("...saying why", body["why"], "already running")
# THE CONTROL THAT MATTERS: reuse must write NOTHING. A claim here would hold an
# occupied server out of the candidate pool for ASSIGN_TTL for no reason.
check("CONTROL: reuse claims nothing", assignments(m), [])

# PEOPLE GATHER: with two lobbies on one map the fuller one wins. "Every map is
# a lobby" is worth nothing if two people asking for the same map land apart.
m = fresh()
beat(m, "p27510", "surf_lux", players=1)
beat(m, "p27520", "surf_lux", players=5)
beat(m, "p27530", "surf_lux", players=3)
status, body = join(m, "surf_lux")
check("the FULLEST lobby on the map wins", body["addr"], "127.0.0.1:27520")

# ...but not past its own limit.
m = fresh()
beat(m, "p27510", "surf_lux", players=16, maxplayers=16)
beat(m, "p27520", "surf_ace", players=0)
status, body = join(m, "surf_lux")
check("a FULL lobby is not offered", body["state"], "loading")
check("...so an idle one is moved instead", assignments(m)[0]["node"], "p27520")


# --------------------------------------------------------------------------
print("\n--- 4. an occupied lobby is NEVER moved ----------------------------")
#
# The entire anti-abuse rule, and the only structural one available: this
# endpoint is public and unauthenticated because the menu calls it before the
# player has connected to anything, so a stranger CAN cause a map load. What
# they can never do is interrupt somebody's run.

m = fresh()
beat(m, "p27510", "surf_ace", players=3)
beat(m, "p27520", "surf_ace", players=1)
status, body = join(m, "surf_kitsune")
check("with only occupied lobbies, the ask is refused", status, 503)
check("...with a sentence", "busy" in body["error"], True)
check("...and NOTHING is claimed", assignments(m), [])
check("...while the refusal lists what people ARE playing",
      sorted(r["map"] for r in body["lobbies"]), ["surf_ace", "surf_ace"])

# CONTROL: the same request with one idle lobby present DOES assign -- so the
# 503 above is the occupancy rule firing and not a broken endpoint.
m = fresh()
beat(m, "p27510", "surf_ace", players=3)
beat(m, "p27520", "surf_ace", players=0)
status, body = join(m, "surf_kitsune")
check("CONTROL: one idle lobby present and it is assigned", status, 200)
check("...and it is the IDLE one, never the busy one",
      [a["node"] for a in assignments(m)], ["p27520"])

# TWO ASKS FOR ONE MAP MUST NOT CLAIM TWO SERVERS.
m = fresh()
beat(m, "p27510", "surf_ace")
beat(m, "p27520", "surf_ace")
s1, b1 = join(m, "surf_kitsune")
s2, b2 = join(m, "surf_kitsune", src="198.51.100.9")
check("a second ask for the same map returns the same server", b2["addr"], b1["addr"])
check("...reporting that it is on its way", b2["state"], "loading")
check("...and only ONE server is claimed", len(assignments(m)), 1)

# ...while two asks for DIFFERENT maps take different servers.
s3, b3 = join(m, "surf_lux", src="198.51.100.10")
check("a different map takes a different server", b3["addr"] != b1["addr"], True)
check("...so both are now claimed", len(assignments(m)), 2)
check("...for the two maps asked for",
      sorted(a["map"] for a in assignments(m)), ["surf_kitsune", "surf_lux"])

# A CLAIMED LOBBY IS NOT STILL ON THE MAP IT REPORTS.  Both lobbies above are
# claimed for other maps but both still say `surf_ace`, truthfully, until their
# next heartbeat. Offering one to a surf_ace player would send them to a server
# that changelevels out from under them -- the exact experience this feature
# exists to remove. The suite found this; the first cut shipped it.
s4, b4 = join(m, "surf_ace", src="198.51.100.11")
check("a lobby under a claim is not offered under its OLD map", s4, 503)
check("...so nobody is sent somewhere that is about to leave",
      b4.get("state"), None)
check("...and the two standing claims are untouched", len(assignments(m)), 2)


# --------------------------------------------------------------------------
print("\n--- 5. the heartbeat is the control channel ------------------------")
#
# Not rcon, and that is not a style preference: FTE's amplification guard gates
# rcon BEFORE the password check with no loopback exemption, and 15 packets in
# 30 seconds is a self-extending 24-hour block only a restart clears.

m = fresh()
check("CONTROL: an unclaimed lobby is told nothing", beat(m, "p27510", "surf_ace"),
      "ok")

join(m, "surf_kitsune")
check("a claimed lobby is told to changelevel",
      beat(m, "p27510", "surf_ace"), "map surf_kitsune")
check("...and is told again until it arrives",
      beat(m, "p27510", "surf_ace"), "map surf_kitsune")

check("the lobby reporting the new map ends the claim",
      beat(m, "p27510", "surf_kitsune"), "ok")
check("...and the claim is gone from the table", assignments(m), [])
check("...so it is a candidate again", beat(m, "p27510", "surf_kitsune"), "ok")

# THE ON-DISK SPELLING GOES ON THE WIRE, because the other end puts it straight
# into `changelevel` and FTE's filesystem is case-sensitive on Linux.
m = fresh()
beat(m, "p27510", "surf_ace")
join(m, "bhop_mukiology")
check("the changelevel it is told is the DISK's spelling",
      beat(m, "p27510", "surf_ace"), "map Bhop_Mukiology")

# THE RACE, AND THE CLAIM LOSES IT.  A player can join in the window between the
# assignment and the next heartbeat. Moving the server then would throw them out
# of a run to satisfy a stranger's menu.
m = fresh()
beat(m, "p27510", "surf_ace")
join(m, "surf_kitsune")
check("a player arriving before the move cancels it",
      beat(m, "p27510", "surf_ace", players=1), "ok")
check("...and the claim is dropped, not merely deferred", assignments(m), [])
check("CONTROL: still idle, and it would have been told to move",
      beat(m, "p27520", "surf_ace"), "ok")

# A STALE CLAIM IS NOT ACTED ON.  Somebody asked, never connected, and the
# server must not be moved a minute later under a player who has since arrived.
m = fresh()
beat(m, "p27510", "surf_ace")
join(m, "surf_kitsune")
check("CONTROL: the fresh claim is live", beat(m, "p27510", "surf_ace"),
      "map surf_kitsune")
conn = sqlite3.connect(m._test_db)
conn.execute("UPDATE assignments SET asked_at = asked_at - ?", (m.ASSIGN_TTL + 5,))
conn.commit()
conn.close()
check("an expired claim is not acted on", beat(m, "p27510", "surf_ace"), "ok")
check("...and is reaped", assignments(m), [])

# A CLAIM ON A NODE THAT HAS GONE STALE IS NOT OFFERED TO ANYONE.
m = fresh()
beat(m, "p27510", "surf_ace")
join(m, "surf_kitsune")
conn = sqlite3.connect(m._test_db)
conn.execute("UPDATE lobbies SET last_seen = last_seen - ?", (m.LOBBY_TTL + 5,))
conn.commit()
conn.close()
status, body = join(m, "surf_kitsune", src="198.51.100.20")
check("a claim on a dead node is not handed out", status, 503)


# --------------------------------------------------------------------------
print("\n--- 6. rate limiting -----------------------------------------------")

m = fresh()
beat(m, "p27510", "surf_lux", players=1)     # the cheap reuse path, on purpose
codes = [join(m, "surf_lux", src="203.0.113.99")[0]
         for _ in range(m.JOIN_RATE_MAX + 1)]
check("the cap fires at exactly JOIN_RATE_MAX",
      (codes[m.JOIN_RATE_MAX - 1], codes[m.JOIN_RATE_MAX]), (200, 429))
check("CONTROL: another source is unaffected",
      join(m, "surf_lux", src="198.51.100.77")[0], 200)
check("CONTROL: the heartbeat has its own bucket and is untouched",
      beat(m, "p27510", "surf_lux", players=1), "ok")


# --------------------------------------------------------------------------
print("\n--- 7. the 3 -> 4 migration ----------------------------------------")

m = fresh()
check("a fresh database is stamped schema 4", user_version(m), 4)
check("...and SCHEMA_VERSION agrees", m.SCHEMA_VERSION, 4)

m = fresh(seed_v3=True)
check("a schema-3 database upgrades to 4", user_version(m), 4)
conn = sqlite3.connect(m._test_db)
kept = [r[0] for r in conn.execute("SELECT map FROM lobbies")]
cols = [r[1] for r in conn.execute("PRAGMA table_info(assignments)")]
conn.close()
check("...keeping the lobby rows it already held", kept, ["surf_legacy"])
check("...and gaining the assignments table",
      cols, ["node", "map", "map_dir", "asked_at", "src"])
check("...which starts empty", assignments(m), [])


# --------------------------------------------------------------------------
print("\n--- 8. the reply body is a console command on the other end --------")
#
# sv_lobby.qc puts this straight into `changelevel`, and SVC_RemoteCommand's
# `;` injection is already a proven live defect in this tree over rcon. Here the
# protection is that the name is never echoed from the request -- it comes back
# out of the LIBRARY INDEX, which only ever holds names that matched
# _MAPNAME_OK and exist as files. This checks that property holds rather than
# assuming it.

m = fresh()
beat(m, "p27510", "surf_ace")
for hostile in ["surf_lux;quit", "surf_lux\nquit", "surf lux", "surf_lux\"x"]:
    join(m, hostile)
check("no hostile spelling ever became a claim", assignments(m), [])
check("...and the lobby is still told nothing", beat(m, "p27510", "surf_ace"), "ok")

join(m, "surf_lux")
reply = beat(m, "p27510", "surf_ace")
check("the real one does land", reply, "map surf_lux")
check("...and carries no separator of any kind",
      [c for c in reply if c in ';\n\r"\\ ' and c != " "], [])


# --------------------------------------------------------------------------
if FAILED:
    print("\n%d FAILURE(S):" % len(FAILED))
    for line in FAILED:
        print("  " + line)
    sys.exit(1)
print("\nall join checks passed")
