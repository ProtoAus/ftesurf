#!/usr/bin/env python3
"""
sweep.py -- verify every recording the lobbies index, and store the verdict.

Engine `pm_verify` (Patch 349) replays a finished FTESURF-REC 9 file exactly and
asks the timer's own zone scan where it finishes.  This runs it over the
`replays` ledger and records one verdict per attempt:

    PASS    every sample reproduces and the zones finish the run at its tick
            (stage evidence of an abandoned run: reproduces to its abandon)
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
import filecmp
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

# The simcheck module, resolved once by _simcheck(): (module, why) or (None, why).
# Module-level and not a plain import, because a host without simcheck.py must
# keep running every other step -- the same rule the receipt step's imports follow.
_SIMCHECK = None


class _NoNotable(object):
    """Stands in for simcheck.NOTABLE in the one line that cannot be reached
    without simcheck having imported; a fallback that is never read is still
    better than an AttributeError in the sweep's summary."""
    NOTABLE = 0.95


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
        """SELECT r.id, r.map, r.map_dir, r.track, r.leg, r.leaf, r.kind, r.runid,
                  r.flags, r.tickrate FROM replays r
           WHERE r.checked = 0 AND r.kind IN ('run', 'evidence')
             AND (SELECT COUNT(*) FROM verdicts v
                  WHERE v.replay_id = r.id AND v.verdict = 'ERROR'
                    AND v.at >= MAX(r.submitted, r.recheck_at)) < ?
           ORDER BY r.recheck_at DESC, r.id LIMIT ?""",
        (MAX_ERRORS, limit)).fetchall()


def relpath(row):
    """The file as pm_verify names it (game-filesystem relative), or None.

    surfd.replay_file makes the checks /api/replay makes before it serves.  A
    kind 'evidence' row's kept copy is under SURFD_KEEP, outside the game tree
    pm_verify reads (Patch 425), so it names the lobby's copy -- the same file
    while the lobby keeps it (a hard link; compared, in case KEEP is a copy)."""
    kept = surfd.replay_file(row)[0]
    if kept is None:
        return None
    gamedir = os.path.realpath(os.path.join(GAME, "ftesurf"))
    if "kind" in row.keys() and row["kind"] == "evidence":
        root = os.path.realpath(surfd.EVIDENCE_DIR)
        sub = os.path.join(row["map_dir"], row["leaf"])
        if not root.startswith(gamedir + os.sep):
            return None
        try:
            if not filecmp.cmp(kept, os.path.join(root, sub), shallow=False):
                return None
        except OSError:
            return None
    else:
        root = os.path.realpath(surfd.RUNS_DIR)
        sub = os.path.join(row["map_dir"], surfd.leg_dir(row["track"], row["leg"]),
                           row["leaf"])
    # pm_verify opens files through the game filesystem, i.e. relative to the
    # gamedir; RUNS_DIR is normally <gamedir>/data/runs.
    base = os.path.relpath(root, gamedir)
    return (base + "/" + sub).replace(os.sep, "/")


# pm_verify's reasons when every earlier check in its verdict chain passed
# (sv_ccmds.c): on a finished run findings, on an abandoned one the expected
# answer -- the zones never end it, or it was abandoned BY a cancel zone, which
# the replay crosses on the file's last input row (measured, p426cl.cfg).
# Exact, so a reworded verifier holds.
NO_FINISH = "no finish: the zones never end this run"
CANCEL_RE = re.compile(r"^a cancel zone is crossed at row (\d+)$")


def abandoned_pass(row, verdict, reason):
    """(verdict, reason, ticks) for an abandoned evidence file whose replay
    reproduced to the abandon, else None.  pm_verify does not read `abandon`."""
    if verdict != "HOLD" or row["kind"] != "evidence":
        return None
    meta = surfd._rec_meta(surfd.replay_file(row)[0] or "")
    if meta is None or not meta[2] or meta[1] < 0:
        return None
    cancel = CANCEL_RE.match(reason)
    if reason == NO_FINISH:
        how = "the replay reproduces to there"
    elif cancel and meta[5] > 0 and int(cancel.group(1)) == meta[5] - 1:
        how = "by the cancel zone its replay crosses on the last row"
    else:
        return None
    return ("PASS", "abandoned at tick %d; %s (pm_verify: %s)" % (meta[1], how, reason),
            meta[1])


def row_check(row, verdict, reason):
    """(verdict, reason): a run's file must describe the row a PASS would badge
    -- a row filed while its file was absent was bound to nothing (Patch 425
    review round 5).  A mismatch is HOLD; evidence rows were checked when
    indexed."""
    if row["kind"] != "run":
        return verdict, reason
    meta = surfd._rec_meta(surfd.replay_file(row)[0] or "")
    if meta is None:
        return verdict, reason
    hdr = dict(meta[0])
    if row["runid"] in ("", "-"):
        hdr.pop("runid", None)            # sent none (a TF_SHADOW continuation)
    bad = surfd._rec_disagrees(hdr, row["map"], row["track"], row["leg"],
                               row["runid"], row["flags"], row["tickrate"])
    if not bad:
        return verdict, reason
    return "HOLD", "the file does not describe this row: %s (pm_verify %s%s)" % (
        bad, verdict, ": " + reason if reason else "")


def stage_check(conn, row, verdict, reason):
    """(verdict, reason) with the stage rows of the replay's run checked against
    the recording's `stagepost` records (pm_verify vouches for the trajectory,
    never for a stage row's number).  A mismatch is NOTED, never a verdict: a
    stage row is anyone's to post with the key, and it must not be able to take
    an honest recording's badge (Patch 425 review round 2)."""
    why = surfd.stage_binding(conn, row["id"], surfd.replay_file(row)[0])
    return verdict, ("%s; %s" % (reason, why) if reason else why) if why else reason


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


def sweep(conn, limit, runner=None, now=None):
    """Verify up to `limit` unchecked replays.  -> {verdict: count}."""
    runner = runner or run_verifier
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
            why = ("evidence file missing, or not under the game tree the verifier reads"
                   if row["kind"] == "evidence" else "file missing or unusable name")
            v, why = stage_check(conn, row, "REFUSE", why)
            with conn:
                record(conn, row["id"], v, why, -1, engine, progs, t0)
            counts[v] = counts.get(v, 0) + 1
            continue
        bymap.setdefault(row["map_dir"], []).append((row, path))

    for map_dir, items in sorted(bymap.items()):
        verdicts = parse(runner(map_dir, [p for _, p in items]))
        with conn:
            for row, path in items:
                v, reason, ticks = verdicts.get(path, ("ERROR", "no VERIFY line", -1))
                v, reason, ticks = abandoned_pass(row, v, reason) or (v, reason, ticks)
                if v != "ERROR":
                    v, reason = row_check(row, v, reason)
                    v, reason = stage_check(conn, row, v, reason)
                record(conn, row["id"], v, reason, ticks, engine, progs, t0)
                counts[v] = counts.get(v, 0) + 1
    return counts


def read_receipt(path):
    """One receipt, fully joined.
    -> (verdict, pub, map, angles, reason, sig, journal, journal_reason, owed)
    or None; `sig` is 1 when the signature verified, which a FAULT for any other
    reason can still have; `owed` is 1 when the journal is ABSENT and the
    receipt signs a kept one's digest, i.e. it may still be uploading.

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
    # THE JOURNAL'S CONTENTS, and the reason this line is here rather than in a
    # tool nobody runs.  join_hid checks the digest the signature commits to and
    # join_uploaded hashes the sibling file against it, so "is this the journal
    # the client signed" was answered -- but "could this journal have been
    # produced by a real device" was asked by hidcheck.py and hidcheck.py HAD NO
    # CALLER OUTSIDE tools/ AND cfg/test/.  Every input check the tree built
    # (the angle identity on both axes, the injection counters, the counts join,
    # the device-provenance table) ran only when an operator typed a path.
    rcptcheck.join_journal(r)
    verdict = "VALID" if (r.ok is True and not r.faults) else "FAULT"
    reason = r.faults[0] if r.faults else ""
    return (verdict, r.head.get("pub", ""), r.head.get("map", ""),
            r.angles, reason[:300], 1 if r.ok is True else 0,
            r.journal, (r.journal_detail or "")[:300],
            1 if getattr(r, "journal_owed", False) else 0)


def receipt_step(conn, limit=200, now=None):
    """Read every receipt not read yet, store the verdict, bind the key.

    -> (read, faults).  A fault here is a fault in the EVIDENCE, not in this
    step; a fault in this step is printed and returns (0, 0).  `faults` counts
    the RECEIPT verdict only -- a journal-content fault is stored in its own
    column and does not move a badge (see rcptcheck.join_journal).
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
        # Nothing re-reads on its own except a PENDING journal (below), and
        # that is deliberate rather than missing: the .rec and .view a receipt
        # joins to are written at the run's end edge, so a .rec that is not there
        # once the settle window has passed is a run that never kept one.  A
        # journal is the one upload that can outlast that window.  What DOES go
        # stale is the thresholds -- reccheck's are measured, and measuring them
        # again will move them -- so an operator can say so with --reread-receipts.
        rows = {r[0]: (r[1], r[2]) for r in
                conn.execute("SELECT runid, stale, journal FROM receipts")}
        # THE SAME SETTLE WINDOW THE EVIDENCE INDEX USES, and for the same
        # reason one level along: the receipt is written at the run's end edge
        # and the upload it commits to arrives AFTERWARDS, so a receipt read the
        # instant it appears records "no .view on this host" for a file that is
        # on its way.  Ten minutes is far past the 25 s a two-minute sidecar
        # takes at 30 ms RTT.
        cutoff = t0 - surfd.EVIDENCE_SETTLE
        # glob answers [] for a directory that is missing or unreadable, which
        # would pass for a complete pass and move the watermark; listdir raises.
        os.listdir(surfd.EVIDENCE_DIR)
        files = sorted(glob.glob(os.path.join(surfd.EVIDENCE_DIR, "*", "*.rcpt")))
        # Never-read files first and OLDEST first, so a pass that runs out of
        # room still covers everything older than what it left; then the
        # --reread-receipts backlog (stale = 1, kept until replaced) and the
        # rows whose journal is PENDING.
        name = lambda f: os.path.basename(f)[:-5]
        fresh = []
        for f in files:
            if name(f) not in rows:
                try:
                    fresh.append((os.path.getmtime(f), f))
                except OSError:
                    pass
        fresh.sort()

        def due(f):
            stale, journal = rows[name(f)]
            if stale in (1, 2):
                return True
            # PENDING: one stat a pass, and a re-read only when the journal has
            # arrived or the wait is over (to close it ABSENT).
            try:
                return journal == "PENDING" and (
                    os.path.exists(f[:-5] + ".hid")
                    or t0 - os.path.getmtime(f) >= surfd.JOURNAL_WAIT)
            except OSError:
                return False
        todo = [(m, f, True) for m, f in fresh] + \
               [(None, f, False) for f in files if name(f) in rows and due(f)]
        n = bad = jfault = 0
        through = cutoff
        for mtime, path, is_fresh in todo:
            runid = name(path)
            if mtime is None:
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
            if mtime > cutoff:
                continue
            if n >= limit:
                if is_fresh:
                    through = min(through, int(mtime) - 1)
                continue
            got = read_receipt(path)
            # Gone since the listing: rcptcheck reports "cannot read" as a FAULT,
            # and a stored row is never read again -- skip it, as a failed stat is.
            if got is None or not os.path.exists(path):
                continue
            verdict, pub, mapname, angles, reason, sig, journal, jreason, owed = got
            if not is_fresh and rows[runid][0] not in (1, 2):
                # Due only because its journal was PENDING: move the journal
                # columns and nothing else.  The rest was read when the receipt
                # was, and a .rec pruned since must not turn a stored FAULT
                # into VALID (review of 692503c).
                if journal == "ABSENT" and owed and t0 - mtime < surfd.JOURNAL_WAIT:
                    continue
                with conn:
                    conn.execute("UPDATE receipts SET journal = ?, journal_reason = ?"
                                 " WHERE runid = ?", (journal, jreason, runid))
                n += 1
                jfault += journal == "FAULT"
                continue
            # A signed journal that is not here yet may still be uploading, one
            # chunk per round trip: PENDING, read again when it arrives, ABSENT
            # once JOURNAL_WAIT after signing has passed without it.
            if journal == "ABSENT" and owed and t0 - mtime < surfd.JOURNAL_WAIT:
                journal = "PENDING"
                jreason = "the receipt signs a journal that has not arrived yet"
            # signed_at is the file's mtime: the lobby writes it at the run's
            # end, and a resumed run's runid is its FIRST session's.
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO receipts"
                    " (runid, map, pub, verdict, angles, reason, at, sig, signed_at, stale,"
                    "  journal, journal_reason)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
                    (runid, mapname, pub, verdict, angles, reason, t0, sig,
                     max(1, int(mtime)),      # 0 means "pre-8 row" to receipts_v8
                     journal, jreason))
                bind_key(conn, runid, pub, t0)
            n += 1
            bad += verdict != "VALID"
            jfault += journal == "FAULT"
        # A PENDING row whose receipt was reaped is never read again, and its
        # journal went with it: ABSENT once the wait is over.
        listed = set(name(f) for f in files)
        gone = [rid for rid, (_st, jr) in rows.items()
                if jr == "PENDING" and rid not in listed]
        if gone:
            with conn:
                conn.executemany(
                    "UPDATE receipts SET journal = 'ABSENT', journal_reason = ?"
                    " WHERE runid = ? AND journal = 'PENDING' AND signed_at < ?",
                    [("the journal never arrived", rid, t0 - surfd.JOURNAL_WAIT)
                     for rid in gone])
        # THE WATERMARK.  Every never-read receipt with an mtime up to `through`
        # is now in the table -- `cutoff`, or just short of the oldest one this
        # pass had no room for -- so a board run submitted well before it with
        # no signed receipt has none.  A pass that raised writes nothing, and
        # admin's "unsigned" pauses rather than reading "not read yet" as "not
        # signed" (the three hours this step failed on 2026-09-21 would have
        # flagged every signer's runs).  A flood only slows it: 200 a pass,
        # oldest first.
        with conn:
            conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v)"
                         " VALUES ('receipts_through', ?)", (through,))
        if jfault:
            # SAID, because the column it lands in is not on any board and
            # nothing else would mention it.  A journal that does not hold up is
            # the finding the whole input-evidence chain exists to produce, and
            # this is the only place in the cron path that would ever see one.
            print("sweep: %d receipt(s) have a journal beside them that does not "
                  "hold up (receipts.journal = FAULT)" % jfault, file=sys.stderr)
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
        # 2, not receipts_v8's 1: the row's sig is KNOWN, so admin keeps
        # judging on it until the re-read replaces it.  A row already at 1
        # stays there -- its sig is still unknown.
        return conn.execute("UPDATE receipts SET stale = 2 WHERE stale = 0").rowcount


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
    row = conn.execute("SELECT player FROM replays WHERE runid = ?"
                       " AND kind IN ('run', 'evidence') AND player <> ''"
                       " ORDER BY kind = 'evidence' LIMIT 1", (runid,)).fetchone()
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
                        AND rp.kind IN ('run', 'evidence')
                        AND rp.player = pubkeys.player))
            WHERE pub = ? AND player = ?""", (t0, pub, player))


def evidence_step(conn):
    """surfd schema 6's upkeep: index and GC the evidence behind stage rows.
    A fault is reported and never stops the verification.
    -> (rows indexed, rows dropped)."""
    try:
        added = surfd.index_evidence(conn)["indexed"]
        surfd.requeue_evidence(conn)
        surfd.restage_rejected(conn)
        return added, surfd.gc_evidence(conn)
    except Exception as exc:
        print("sweep: evidence step failed: %r" % exc, file=sys.stderr)
        return 0, 0


def similarity_step(conn, limit=50):
    """surfd schema 10: store the cross-run similarity sample.  STORE-ONLY --
    nothing here moves a badge or a verdict, and a fault is printed rather than
    raised, because a measurement that cannot run must not take the checks that DO
    gate badges down with it.  -> (pairs stored, notable, note)."""
    mod = _simcheck()
    if mod is None:
        return 0, 0, ""
    try:
        return mod.similarity_step(conn, surfd, limit=limit, tools_dir=TOOLS)
    except Exception as exc:
        print("sweep: similarity step failed: %r" % exc, file=sys.stderr)
        return 0, 0, ""


def _simcheck():
    """The simcheck module, or None with the reason already printed once.

    Imported lazily and cached, exactly as the receipt step imports its checkers
    inside the function: a host without simcheck.py must keep running the
    verification it has run since Patch 349.  The failure is printed once rather
    than on every tick, because a cron job that repeats one unfixable line every
    five minutes teaches the reader to skip the log.
    """
    global _SIMCHECK
    if _SIMCHECK is not None:
        return _SIMCHECK[0]
    try:
        import simcheck
        _SIMCHECK = (simcheck, "")
    except Exception as exc:
        print("sweep: similarity step unavailable: %r" % exc, file=sys.stderr)
        _SIMCHECK = (None, repr(exc))
    return _SIMCHECK[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be verified or indexed and exit")
    ap.add_argument("--reread-receipts", action="store_true",
                    help="forget every stored receipt verdict so the next pass "
                         "reads them again (after a checker change)")
    ap.add_argument("--sims", type=int, default=50,
                    help="how many runs to compare per pass (store-only, "
                         "schema 10; 0 disables the step)")
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
        try:
            import simcheck
            simcheck.ensure_schema(conn)
            print("sims pending: %d run(s) with no pair stored yet"
                  % len(simcheck.pending(conn, 10 ** 6)))
            line = simcheck.summary_line(conn)
            print(line or "sims: no pairs stored yet")
        except Exception as exc:
            print("sims: unavailable (%r)" % exc)
        return 0
    if args.reread_receipts:
        n = mark_receipts_stale(conn)
        print("sweep: marked %d receipt verdict(s) to read again" % n)
    added, dropped = evidence_step(conn)
    rcpts, rbad = receipt_step(conn)
    sims, simnotable, simnote = similarity_step(conn, limit=args.sims)
    counts = sweep(conn, args.limit)
    line = " ".join("%s %d" % kv for kv in sorted(counts.items())) or "nothing to verify"
    if added or dropped:
        line += " evidence +%d -%d" % (added, dropped)
    if simnote:
        line += " " + simnote
    if simnotable:
        # PRINTED WHEN IT IS NOT ZERO, for the receipt step's reason: this is the
        # one line in this step worth a human reading.  It is NOT an accusation --
        # nothing was demoted and nothing will be -- but a pair at or over 0.95 is
        # worth opening, and the sweep log is where somebody looks.
        line += " (%d SIMILAR PAIR(S) OVER %.2f -- store-only, no badge moved)" % (
            simnotable, (_simcheck() or _NoNotable).NOTABLE)
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
