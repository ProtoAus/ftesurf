#!/usr/bin/env python3
"""
sweep.py -- verify every recording the lobbies index, and store the verdict.

Engine `pm_verify` (Patch 349) replays a finished FTESURF-REC 9 file exactly and
asks the timer's own zone scan where it finishes.  This runs it over the
`replays` ledger and records one verdict per attempt:

    PASS    every sample reproduces and the zones finish the run at its tick
    HOLD    something disagrees -- a reason for a human, never an accusation
    REFUSE  out of scope for v1 (old format, resumed, ghosted, other map ...)
    ERROR   the verifier printed no verdict; retried up to MAX_ERRORS times

STORE ONLY (decided 2026-09-18).  Nothing here changes a board or a rank; the
full reason stays in this table and in no public reply.

THE TABLE IS THE SWEEPER'S.  `verdicts` is created here, not by surfd's
migrate(), so shipping the sweeper needs no surfd deploy; surfd adopts it when
the board starts showing verdicts.  `replays.seen`/`checked` were reserved for
exactly this (surfd.py, schema 3): seen = last attempt, checked = 1 once a
terminal verdict (not ERROR) exists.

Run from the proto user's crontab under flock.  One verifier process per map,
at idle CPU and IO priority, first in line for the OOM killer (the Pi is
shared).  Usage:  python3 sweep.py [--limit N] [--dry-run]
"""

import argparse
import hashlib
import logging
import os
import re
import subprocess
import sys
import time

# Importing surfd logs "surfd ready" to surfd.log, which would read as a restart
# every five minutes.  A handler already on its logger makes surfd skip its own:
# only warnings, on our stderr.
_quiet = logging.StreamHandler(sys.stderr)
_quiet.setLevel(logging.WARNING)
logging.getLogger("surfd").addHandler(_quiet)

import surfd   # one source for DB_PATH, RUNS_DIR, leg_dir and the name checks

GAME = os.environ.get("SURFD_GAME", "/srv/nvme/ftesurf-server/game")
ENGINE = os.environ.get("SURFD_VERIFIER", os.path.join(GAME, "fteqw-svarm64"))
PROGS = os.path.join(GAME, "ftesurf", "qwprogs.dat")
PORT = int(os.environ.get("SURFD_VERIFY_PORT", "27698"))
MAP_TIMEOUT = 900        # seconds for one verifier process (all of one map's files)
MAX_ERRORS = 3

VERIFY_RE = re.compile(r"^VERIFY (\S+) (PASS|HOLD|REFUSE)\b ?(.*)$")
TICKS_RE = re.compile(r"\bticks (\d+)\b")

SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_id  INTEGER NOT NULL,
    verdict    TEXT    NOT NULL,
    reason     TEXT    NOT NULL,
    ticks      INTEGER NOT NULL DEFAULT -1,
    engine     TEXT    NOT NULL,
    progs      TEXT    NOT NULL,
    at         INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS verdicts_replay ON verdicts (replay_id, id);
"""


def ensure_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def file_hash(path, algo):
    h = hashlib.new(algo)
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return "?"
    return h.hexdigest()


def pending(conn, limit):
    return conn.execute(
        """SELECT r.id, r.map_dir, r.track, r.leg, r.leaf FROM replays r
           WHERE r.checked = 0
             AND (SELECT COUNT(*) FROM verdicts v
                  WHERE v.replay_id = r.id AND v.verdict = 'ERROR') < ?
           ORDER BY r.id LIMIT ?""", (MAX_ERRORS, limit)).fetchall()


def relpath(row):
    """The file as pm_verify names it (game-filesystem relative), or None.

    The same checks /api/replay makes before it serves a file: validated
    names, and a real path that stays inside RUNS_DIR."""
    leaf, map_dir = row["leaf"], row["map_dir"]
    if not surfd._LEAF_OK.match(leaf) or not surfd._MAPNAME_OK.match(map_dir):
        return None
    sub = os.path.join(map_dir, surfd.leg_dir(row["track"], row["leg"]), leaf)
    root = os.path.realpath(surfd.RUNS_DIR)
    path = os.path.realpath(os.path.join(root, sub))
    if not path.startswith(root + os.sep) or not os.path.isfile(path):
        return None
    # pm_verify opens files through the game filesystem, i.e. relative to the
    # gamedir; RUNS_DIR is normally <gamedir>/data/runs.
    base = os.path.relpath(root, os.path.realpath(os.path.join(GAME, "ftesurf")))
    return (base + "/" + sub).replace(os.sep, "/")


def parse(lines):
    """VERIFY lines -> {path: (verdict, reason, ticks)}."""
    out = {}
    for ln in lines:
        m = VERIFY_RE.match(ln.strip())
        if not m:
            continue
        path, verdict, reason = m.group(1), m.group(2), m.group(3).strip()
        t = TICKS_RE.search(reason) if verdict == "PASS" else None
        out[path] = (verdict, reason, int(t.group(1)) if t else -1)
    return out


def _oom_first():
    # Raising our own oom_score_adj needs no privilege: if the box runs short,
    # the verifier dies before a lobby or the co-tenant does.
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass


def run_verifier(map_dir, paths):
    """One headless server: load the map once, verify every file, quit."""
    cmd = ["nice", "-n", "19", "ionice", "-c", "3", ENGINE, "-basedir", GAME,
           "+set", "sv_public", "0", "+set", "sv_port", str(PORT),
           "+set", "rec_enable", "0", "+set", "lobby_master", "",
           "+map", map_dir, "+wait", "+wait", "+wait"]
    for p in paths:
        cmd += ["+pm_verify", p]
    cmd += ["+quit"]
    try:
        res = subprocess.run(cmd, cwd=GAME, capture_output=True, text=True,
                             errors="replace", timeout=MAP_TIMEOUT,
                             preexec_fn=_oom_first)
        return res.stdout.splitlines() + res.stderr.splitlines()
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ["sweep: verifier failed: %s" % exc]


def record(conn, rid, verdict, reason, ticks, engine, progs, now):
    conn.execute(
        "INSERT INTO verdicts (replay_id, verdict, reason, ticks, engine, progs, at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rid, verdict, reason[:300], ticks, engine, progs, now))
    if verdict == "ERROR":
        conn.execute("UPDATE replays SET seen = ? WHERE id = ?", (now, rid))
    else:
        conn.execute("UPDATE replays SET seen = ?, checked = 1 WHERE id = ?",
                     (now, rid))


def sweep(conn, limit, runner=run_verifier, now=None):
    """Verify up to `limit` unchecked replays.  -> {verdict: count}."""
    ensure_schema(conn)
    engine = file_hash(ENGINE, "md5")
    progs = file_hash(PROGS, "sha256")
    counts = {}
    bymap = {}
    for row in pending(conn, limit):
        path = relpath(row)
        if path is None:
            with conn:
                record(conn, row["id"], "REFUSE", "file missing or unusable name",
                       -1, engine, progs, now or int(time.time()))
            counts["REFUSE"] = counts.get("REFUSE", 0) + 1
            continue
        bymap.setdefault(row["map_dir"], []).append((row["id"], path))

    for map_dir, items in sorted(bymap.items()):
        verdicts = parse(runner(map_dir, [p for _, p in items]))
        stamp = now or int(time.time())
        with conn:
            for rid, path in items:
                v, reason, ticks = verdicts.get(path, ("ERROR", "no VERIFY line", -1))
                record(conn, rid, v, reason, ticks, engine, progs, stamp)
                counts[v] = counts.get(v, 0) + 1
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be verified and exit")
    args = ap.parse_args(argv)
    conn = surfd.connect()
    ensure_schema(conn)
    if args.dry_run:
        for row in pending(conn, args.limit):
            print(row["id"], row["map_dir"], relpath(row))
        return 0
    counts = sweep(conn, args.limit)
    print("%s sweep: %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"),
                             " ".join("%s %d" % kv for kv in sorted(counts.items()))
                             or "nothing to verify"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
