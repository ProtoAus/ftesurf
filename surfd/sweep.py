#!/usr/bin/env python3
"""
sweep.py -- verify every recording the lobbies index, and store the verdict.

Engine `pm_verify` (Patch 349) replays a finished FTESURF-REC 9 file exactly and
asks the timer's own zone scan where it finishes.  This runs it over the
`replays` ledger and records one verdict per attempt:

    PASS    every sample reproduces and the zones finish the run at its tick
    HOLD    something disagrees -- a reason for a human, never an accusation
    REFUSE  out of scope for v1 (old format, resumed, other map ...)
    ERROR   the verifier printed no verdict; retried up to MAX_ERRORS times

surfd owns the table (schema 5, surfd.VERDICTS_SQL).  A PASS as the latest
current non-ERROR verdict drives the public VERIFIED badge (surfd.VER_SQL);
reasons and HOLD stay in this table and the owner's review pages, never in a
public reply.  seen = last attempt, checked = 1 once a terminal verdict (not
ERROR) exists; the owner's re-check sets checked = 0 and replays.recheck_at.

Run from the proto user's crontab under flock.  One verifier process per map,
at idle CPU and IO priority, first in line for the OOM killer (the Pi is
shared).  Each run first does surfd's schema-6 evidence upkeep (evidence_step)
and reads any run receipts it has not read yet (receipt_step).
Usage:  python3 sweep.py [--limit N] [--dry-run]

THE RECEIPT STEP IS STORE-ONLY AND SO IS THIS WHOLE FILE.  It writes `receipts`
and `pubkeys` (schema 7) and moves no badge: nothing in surfd.VER_SQL reads
them.  What a signature is worth, and what a second key under one player's name
means, are policy questions -- a sweeper that started demoting runs on its own
would be answering them in a cron job.
"""

import argparse
import glob
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
# rcptcheck/reccheck/ed25519.  Deployed beside the game rather than beside
# surfd, because they are the tree's readers for the tree's own formats and the
# game directory is what gets updated when a format changes.
TOOLS = os.environ.get("SURFD_TOOLS", os.path.join(GAME, "tools"))
MAP_TIMEOUT = 900        # seconds for one verifier process (all of one map's files)
MAX_ERRORS = surfd.VERIFY_MAX_ERRORS

VERIFY_RE = re.compile(r"^VERIFY (\S+) (PASS|HOLD|REFUSE)\b ?(.*)$")
TICKS_RE = re.compile(r"\bticks (\d+)\b")


def ensure_schema(conn):
    # surfd's migrate() already ran at import; a no-op safety net.
    conn.executescript(surfd.VERDICTS_SQL)
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
    # Only ERRORs since the last submission or re-check count against the cap,
    # so a re-check (or an exact-tie resubmission) retries a spent replay.
    return conn.execute(
        """SELECT r.id, r.map_dir, r.track, r.leg, r.leaf, r.kind FROM replays r
           WHERE r.checked = 0 AND r.kind = 'run'
             AND (SELECT COUNT(*) FROM verdicts v
                  WHERE v.replay_id = r.id AND v.verdict = 'ERROR'
                    AND v.at >= MAX(r.submitted, r.recheck_at)) < ?
           ORDER BY r.recheck_at DESC, r.id LIMIT ?""",
        (MAX_ERRORS, limit)).fetchall()


def relpath(row):
    """The file as pm_verify names it (game-filesystem relative), or None.

    surfd.replay_file makes the checks /api/replay makes before it serves.
    Only a kind 'run' file lives under RUNS_DIR (schema 6)."""
    if "kind" in row.keys() and row["kind"] != "run":
        return None
    if surfd.replay_file(row)[0] is None:
        return None
    sub = os.path.join(row["map_dir"], surfd.leg_dir(row["track"], row["leg"]),
                       row["leaf"])
    root = os.path.realpath(surfd.RUNS_DIR)
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


def record(conn, rid, verdict, reason, ticks, engine, progs, t0):
    conn.execute(
        "INSERT INTO verdicts (replay_id, verdict, reason, ticks, engine, progs, at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rid, verdict, reason[:300], ticks, engine, progs, t0))
    # A row resubmitted (exact tie) or re-checked after t0 stays pending.
    done = "" if verdict == "ERROR" else ", checked = 1"
    conn.execute("UPDATE replays SET seen = ?" + done + " WHERE id = ?"
                 " AND submitted <= ? AND recheck_at <= ?", (t0, rid, t0, t0))


def sweep(conn, limit, runner=run_verifier, now=None):
    """Verify up to `limit` unchecked replays.  -> {verdict: count}."""
    ensure_schema(conn)
    # Every verdict is stamped t0, taken before pending() reads the rows, so a
    # tie landing mid-run is newer (not current: at < submitted).  The -1 covers
    # one landing in t0's own second.
    t0 = now if now is not None else int(time.time()) - 1
    engine = file_hash(ENGINE, "md5")
    progs = file_hash(PROGS, "sha256")
    counts = {}
    bymap = {}
    for row in pending(conn, limit):
        path = relpath(row)
        if path is None:
            with conn:
                record(conn, row["id"], "REFUSE", "file missing or unusable name",
                       -1, engine, progs, t0)
            counts["REFUSE"] = counts.get("REFUSE", 0) + 1
            continue
        bymap.setdefault(row["map_dir"], []).append((row["id"], path))

    for map_dir, items in sorted(bymap.items()):
        verdicts = parse(runner(map_dir, [p for _, p in items]))
        with conn:
            for rid, path in items:
                v, reason, ticks = verdicts.get(path, ("ERROR", "no VERIFY line", -1))
                record(conn, rid, v, reason, ticks, engine, progs, t0)
                counts[v] = counts.get(v, 0) + 1
    return counts


def read_receipt(path):
    """One receipt, fully joined.
    -> (verdict, pub, map, angles, reason, sig) or None; `sig` is 1 when the
    signature verified, which a FAULT for any other reason can still have.

    IMPORTED INSIDE THE FUNCTION so that a host without the tools deployed runs
    the verification it has always run.  This step is an addition to the sweep,
    never a precondition for it: the first version imported at module scope and
    would have taken every lobby's verdict sweep down with it on any box where
    game/tools was not there yet, which is every box until the day it is.
    """
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import rcptcheck

    r = rcptcheck.read(path)
    rcptcheck.join_rec(r)
    rcptcheck.join_ticks(r)
    rcptcheck.join_hid(r)
    rcptcheck.join_uploaded(r, {})
    rcptcheck.join_angles(r, {})
    verdict = "VALID" if (r.ok is True and not r.faults) else "FAULT"
    reason = r.faults[0] if r.faults else ""
    return (verdict, r.head.get("pub", ""), r.head.get("map", ""),
            r.angles, reason[:300], 1 if r.ok is True else 0)


def receipt_step(conn, limit=200, now=None):
    """Read every receipt not read yet, store the verdict, bind the key.

    -> (read, faults).  A fault here is a fault in the EVIDENCE, not in this
    step; a fault in this step is printed and returns (0, 0).
    """
    t0 = int(time.time()) if now is None else now
    try:
        conn.executescript(surfd.RECEIPTS_SQL)
        # A RECEIPT IS READ ONCE AND THE ROW OUTLIVES THE FILE, which is the
        # point: `run_evidence_days` reaps the .rcpt and the verdict stays.  It
        # also means this set only grows -- about 200 bytes a run, so a year of
        # the current fleet is tens of MB, and a GC for it would be a policy
        # about how long a verdict is worth keeping that nobody has asked for.
        #
        # Nothing re-reads on its own, and that is deliberate rather than
        # missing: the two files a receipt joins to are both written at the
        # run's end edge, so a .rec that is not there once the settle window has
        # passed is a run that never kept one.  What DOES go stale is the
        # thresholds -- reccheck's are measured, and measuring them again will
        # move them -- so an operator can say so with --reread-receipts.
        rows = {r[0]: r[1] for r in conn.execute("SELECT runid, stale FROM receipts")}
        # THE SAME SETTLE WINDOW THE EVIDENCE INDEX USES, and for the same
        # reason one level along: the receipt is written at the run's end edge
        # and the upload it commits to arrives AFTERWARDS, so a receipt read the
        # instant it appears records "no .view on this host" for a file that is
        # on its way.  Ten minutes is far past the 25 s a two-minute sidecar
        # takes at 30 ms RTT.
        cutoff = t0 - surfd.EVIDENCE_SETTLE
        files = sorted(glob.glob(os.path.join(surfd.EVIDENCE_DIR, "*", "*.rcpt")))
        # Never-read files first: a --reread-receipts backlog (stale = 1, kept
        # until replaced) must not hold back a new run's receipt.
        name = lambda f: os.path.basename(f)[:-5]
        todo = ([f for f in files if name(f) not in rows] +
                [f for f in files if rows.get(name(f)) == 1])
        n = bad = 0
        fresh_cut = False
        for path in todo:
            runid = name(path)
            if n >= limit:
                fresh_cut = fresh_cut or runid not in rows
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime > cutoff:
                continue
            got = read_receipt(path)
            if got is None:
                continue
            verdict, pub, mapname, angles, reason, sig = got
            # signed_at is the file's mtime: the lobby writes it at the run's
            # end, and a resumed run's runid is its FIRST session's.
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO receipts"
                    " (runid, map, pub, verdict, angles, reason, at, sig, signed_at, stale)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                    (runid, mapname, pub, verdict, angles, reason, t0, sig, int(mtime)))
                bind_key(conn, runid, pub, t0)
            n += 1
            bad += verdict != "VALID"
        # THE WATERMARK.  Every never-read receipt up to `cutoff` is now in the
        # table, so a board run submitted well before it with no signed receipt
        # has none.  A pass cut short, or one that raised, does not move it:
        # admin's "unsigned" then pauses instead of reading "not read yet" as
        # "not signed" -- the three hours this step failed on 2026-09-21 would
        # otherwise have flagged every signer's runs.
        if not fresh_cut:
            with conn:
                conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v)"
                             " VALUES ('receipts_through', ?)", (cutoff,))
        return n, bad
    except Exception as exc:
        print("sweep: receipt step failed: %r" % exc, file=sys.stderr)
        return 0, 0


def mark_receipts_stale(conn):
    """--reread-receipts.  MARKED, NOT DELETED: the rows stay until each is
    read again (200 a pass), so admin never judges first keys from a partial
    table, and a row whose .rcpt is gone keeps its last verdict.  `pubkeys`
    is untouched -- re-reading the same files must not count a run twice."""
    with conn:
        conn.executescript(surfd.RECEIPTS_SQL)
        return conn.execute("UPDATE receipts SET stale = 1").rowcount


def bind_key(conn, runid, pub, t0):
    """Trust on first use, and NOTHING ELSE.

    The row is a (key, player) PAIR.  A key that signs for two players and a
    player who signs with two keys both become two rows, which is the whole
    point: `fskey` is a local file nobody backs up, so a reinstall legitimately
    makes a second key, and a shared machine legitimately makes a second player.
    A schema that stored "the" key per player would answer both questions by
    throwing away what was needed to ask them.

    `first_at`/`last_at` are when this pair was OBSERVED by this job, not when
    the runs were made -- a re-read moves `last_at`.  The run's own time is in
    `receipts.at` and on the board row.
    """
    if not pub:
        return
    row = conn.execute("SELECT player FROM replays WHERE runid = ? AND kind = 'run'"
                       " AND player <> '' LIMIT 1", (runid,)).fetchone()
    if not row:
        return          # nothing on a board names this run; there is no player yet
    player = row[0]
    conn.execute("INSERT OR IGNORE INTO pubkeys (pub, player, first_at, last_at, runs)"
                 " VALUES (?, ?, ?, ?, 0)", (pub, player, t0, t0))
    # `runs` IS RECOUNTED AND NEVER INCREMENTED, which is not a style choice:
    # the first cut did `runs = runs + 1` and --reread-receipts then counted
    # every run a second time -- the test's own control caught it saying 2 where
    # the comment beside the flag claimed 1.  A counter that is bumped by an
    # EVENT is wrong whenever the event can repeat; the quantity wanted is how
    # many distinct runs this pair has, and `receipts` already holds them.
    # It also self-heals: a run whose board row arrived after its receipt was
    # read is counted by the next run the same pair makes.
    conn.execute(
        """UPDATE pubkeys SET last_at = ?, runs = (
               SELECT COUNT(DISTINCT rc.runid) FROM receipts rc
                WHERE rc.pub = pubkeys.pub AND EXISTS (
                      SELECT 1 FROM replays rp WHERE rp.runid = rc.runid
                        AND rp.kind = 'run' AND rp.player = pubkeys.player))
            WHERE pub = ? AND player = ?""", (t0, pub, player))


def evidence_step(conn):
    """surfd schema 6's upkeep: index and GC the evidence behind stage rows.
    A fault is reported and never stops the verification.
    -> (rows indexed, rows dropped)."""
    try:
        added = surfd.index_evidence(conn)["indexed"]
        return added, surfd.gc_evidence(conn)
    except Exception as exc:
        print("sweep: evidence step failed: %r" % exc, file=sys.stderr)
        return 0, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be verified or indexed and exit")
    ap.add_argument("--reread-receipts", action="store_true",
                    help="forget every stored receipt verdict so the next pass "
                         "reads them again (after a checker change)")
    args = ap.parse_args(argv)
    conn = surfd.connect()
    ensure_schema(conn)
    if args.dry_run:
        for row in pending(conn, args.limit):
            print(row["id"], row["map_dir"], relpath(row))
        print("evidence:", surfd.index_evidence(conn, dry_run=True))
        done = {row[0] for row in conn.execute(
            "SELECT runid FROM receipts WHERE stale = 0")} \
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table'"
                            " AND name='receipts'").fetchone() else set()
        todo = [p for p in sorted(glob.glob(os.path.join(surfd.EVIDENCE_DIR,
                                                         "*", "*.rcpt")))
                if os.path.basename(p)[:-5] not in done]
        print("receipts: %d unread" % len(todo))
        through = conn.execute("SELECT v FROM sweepmeta WHERE k = 'receipts_through'")\
            .fetchone() if conn.execute("SELECT name FROM sqlite_master WHERE type='table'"
                                        " AND name='sweepmeta'").fetchone() else None
        print("receipts read through: %s" % (time.strftime("%Y-%m-%dT%H:%M:%S",
              time.localtime(through[0])) if through else "never"))
        return 0
    if args.reread_receipts:
        n = mark_receipts_stale(conn)
        print("sweep: marked %d receipt verdict(s) to read again" % n)
    added, dropped = evidence_step(conn)
    rcpts, rbad = receipt_step(conn)
    counts = sweep(conn, args.limit)
    line = " ".join("%s %d" % kv for kv in sorted(counts.items())) or "nothing to verify"
    if added or dropped:
        line += " evidence +%d -%d" % (added, dropped)
    if rcpts:
        line += " receipts %d" % rcpts
        # PRINTED WHEN IT IS NOT ZERO, not only under a flag: a receipt that
        # does not check out is the one line in this job worth a human reading,
        # and the sweep log is where somebody looks.
        if rbad:
            line += " (%d WITH FAULTS)" % rbad
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    note = disk_note()
    if note:
        print("%s sweep: %s" % (stamp, note))     # before the sweep line, which stays last
    print("%s sweep: %s" % (stamp, line))
    return 0


def disk_note():
    """Patch 423: one line while the data drive is low, '' otherwise.  A check
    that cannot read the drive says so rather than staying quiet."""
    try:
        d = surfd.disk_status()
    except Exception as exc:
        return "disk check failed: %r" % exc
    if not d["warn"]:
        return ""
    return ("DISK LOW %.1f GB free of %.1f GB (%.0f%% used) on %s, warns under %.1f GB"
            % (d["free"] / 2 ** 30, d["total"] / 2 ** 30, d["used_pct"], d["path"],
               d["floor"] / 2 ** 30))


if __name__ == "__main__":
    sys.exit(main())
