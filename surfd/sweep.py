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
import json
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
    surfd.verdict_metrics(conn)
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


def parse_counts(lines):
    """Observe counts only within the engine's matching pm_recsim/VERIFY section."""
    out, active, observation, seen = {}, None, None, False
    for raw in lines:
        line = re.sub(r"\^[0-9]", "", raw).strip()
        header = re.fullmatch(r"pm_recsim\s+(\S+)", line)
        if header:
            active, observation, seen = header[1], None, False
            continue
        verdict = VERIFY_RE.match(line)
        if verdict:
            out[verdict[1]] = observation if active == verdict[1] else None
            active, observation, seen = None, None, False
            continue
        if active is None or not line.startswith("counts "):
            continue
        if seen:
            observation = None  # ambiguous duplicate, not an invented measurement
            continue
        seen = True
        if line == "counts    none -- the client predates Patch 376":
            observation = {"version": 1, "state": "no_records", "records": 0}
            continue
        good = re.fullmatch(r"counts\s+(\d{1,10}) record\(s\): what the input ring delivered is what the view read", line)
        bad = re.fullmatch(r"counts\s+(\d{1,10}) of (\d{1,10}) record\(s\) disagree, first at row (\d{1,10}) \(read - ring [-+\d.eE]{1,32} [-+\d.eE]{1,32}\)", line)
        if good and 0 < int(good[1]) <= 2**31-1:
            observation = {"version": 1, "state": "measured", "records": int(good[1]), "disagree": 0}
        elif bad and 0 < int(bad[1]) <= int(bad[2]) <= 2**31-1 and int(bad[3]) <= 2**31-1:
            observation = {"version": 1, "state": "measured", "records": int(bad[2]),
                           "disagree": int(bad[1]), "first_row": int(bad[3])}
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


def record(conn, rid, verdict, reason, ticks, engine, progs, t0, counts_metrics=None):
    conn.execute(
        "INSERT INTO verdicts (replay_id, verdict, reason, ticks, engine, progs, at, counts_metrics)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rid, verdict, reason[:300], ticks, engine, progs, t0,
         json.dumps(counts_metrics, sort_keys=True, separators=(",", ":")) if counts_metrics else ""))
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
        lines = list(runner(map_dir, [p for _, p in items]))
        verdicts, observations = parse(lines), parse_counts(lines)
        with conn:
            for row, path in items:
                v, reason, ticks = verdicts.get(path, ("ERROR", "no VERIFY line", -1))
                v, reason, ticks = abandoned_pass(row, v, reason) or (v, reason, ticks)
                if v != "ERROR":
                    v, reason = row_check(row, v, reason)
                    v, reason = stage_check(conn, row, v, reason)
                record(conn, row["id"], v, reason, ticks, engine, progs, t0, observations.get(path))
                counts[v] = counts.get(v, 0) + 1
    return counts


class ReceiptIdentityChanged(Exception):
    """The path no longer describes the receipt whose observation we stored."""


def receipt_identity(r):
    # Bind the ordered signed message AND join-driving unsigned head keys,
    # including pub/signature. Formatting alone does not change parsed values.
    data = json.dumps(["FTESURF-receipt-identity-v1", r.first, r.head, r.signed, r.faults],
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "v1:" + hashlib.sha256(data.encode("ascii")).hexdigest()


def read_receipt(path, journal_only=False, expected_identity=None, expected_pub=None,
                 view_only=False, defer_view=False, rec_only=False):
    """One receipt, fully joined -- or, with journal_only, everything but the
    .rec joins: the signature, the sibling digests and the journal, for the
    delayed-journal re-read, where a .rec pruned since the first read must not move
    the verdict and a late .hid or .view must still be checked.
    -> (verdict, pub, map, angles, reason, sig, journal, journal_reason, owed,
        partial, identity, view_missing, rec_missing, angles_reason, journal_metrics), or None. view_only checks the view and
    recording/angles without observing HID. `view_missing` is a captured absence,
    not a later stat. `sig` is 1 when the signature verified, which a FAULT for any other
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
    if r.ioerror:
        return None             # retry a read failure, never store it as evidence
    identity = receipt_identity(r)
    if ((expected_identity and identity != expected_identity) or
            (expected_pub is not None and r.head.get("pub", "") != expected_pub)):
        # Before ANY joins: a replacement's signature cannot authorize content
        # under the original receipt's historical key attribution.
        raise ReceiptIdentityChanged("receipt identity changed; reread deferred")
    if view_only or rec_only:
        # A newly available pair is the only new source. No HID read/content join,
        # and no replacement of the original signature or signing observation.
        rcptcheck.join_rec(r)
        if rec_only and not r.recpath:
            return None  # discovery was only a hint; no selected bytes measured
        if rec_only:
            rcptcheck.join_ticks(r)
        observed = list(r.faults)
        rcptcheck.join_uploaded(r, {"hid": True})  # exclude the unrelated sibling
        observed.extend(f for f in r.digest_bad.values() if f not in observed)
        rcptcheck.join_angles(r, {})
        deferred = r.ioerror or (view_only and r.file_bytes.get(os.path.splitext(path)[0] + ".view", False) is None)
        if deferred and not observed:
            return None
        faults = observed if deferred else r.faults
        verdict = "FAULT" if faults or r.ok is not True else "VALID"
        return (verdict, r.head.get("pub", ""), r.head.get("map", ""),
                r.angles, faults[0][:300] if faults else "", 1 if r.ok is True else 0,
                "", "", 0, deferred, identity,
                r.file_bytes.get(os.path.splitext(path)[0] + ".view", False) is None, not r.recpath,
                r.angles_detail[:1000], "")
    if not journal_only:
        rcptcheck.join_rec(r)
        rcptcheck.join_ticks(r)
    rcptcheck.join_hid(r)
    observed = list(r.faults)
    # A separately scheduled missing view must not block a ready journal.
    rcptcheck.join_uploaded(r, {"view": True} if journal_only and defer_view else {})
    if r.ioerror:
        # An unread sibling is not a fault, but must not erase an independent
        # signature/recording/digest fault already observed on this read.
        observed.extend(f for f in r.digest_bad.values() if f not in observed)
        if journal_only or not observed:
            return None
        journal = "FAULT" if "hid" in r.digest_bad else "PENDING"
        detail = ("not the journal the receipt signed: %s" % r.digest_bad["hid"]
                  if journal == "FAULT" else "signed sibling read deferred after I/O")
        return ("FAULT", r.head.get("pub", ""), r.head.get("map", ""),
                "BLIND", observed[0][:300], 1 if r.ok is True else 0,
                journal, detail[:300], 0, True, identity, False, False,
                "angle check deferred after signed sibling I/O; no angle measurement", "")
    if not journal_only:
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
    if "hid" in r.digest_bad:
        # The file read is not the journal that was signed, so what its content
        # says is about some other journal (review of 70f1ea3).
        r.journal = "FAULT"
        r.journal_detail = "not the journal the receipt signed: %s" % r.digest_bad["hid"]
    verdict = "VALID" if (r.ok is True and not r.faults) else "FAULT"
    reason = r.faults[0] if r.faults else ""
    return (verdict, r.head.get("pub", ""), r.head.get("map", ""),
            r.angles, reason[:300], 1 if r.ok is True else 0,
            r.journal, (r.journal_detail or "")[:300],
            1 if getattr(r, "journal_owed", False) else 0, False, identity,
            not journal_only and r.file_bytes.get(os.path.splitext(path)[0] + ".view", False) is None,
            not journal_only and not r.recpath, r.angles_detail[:1000],
            json.dumps(r.journal_metrics, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if r.journal_metrics is not None else "")


def receipt_rec_runids(mapname):
    """Header-only readiness hints; actual receipt joins must re-observe bytes."""
    if surfd.clean_map(mapname) is None:
        return set()
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    try:
        import rcptcheck
    except ImportError:
        return set()

    roots = [os.path.join(rcptcheck.GAME, "data", "evidence", mapname)]
    for leg in ("main", "stage_*", "bonus_*"):
        roots.extend(glob.glob(os.path.join(rcptcheck.GAME, "data", "runs", mapname, leg)))
    found = set()
    for root in roots:
        for path in glob.glob(os.path.join(root, "*.rec")):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    head = {}
                    # Bounded hints only, not another recording parser. Unusual
                    # headers can still be assessed by an explicit full reread.
                    for _ in range(64):
                        line = fh.readline(4096)
                        if not line or len(line) == 4096:
                            break
                        if line.strip() == "begin":
                            if head.get("runid"):
                                found.add(head["runid"])
                            break
                        key, _sp, value = line.strip().partition(" ")
                        head[key] = value
            except OSError:
                continue  # unknown availability cannot produce an evidence fault
    return found


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
        # Source arrival is not permission to reinterpret an entire receipt.
        # Journals have explicit ABSENT/PENDING observations; a successful full
        # read captures a missing view in scheduling metadata. Unknown historical
        # readiness is not inferred from today's files. --reread-receipts remains
        # the explicit full-read/threshold decision, never an identity waiver.
        rows = {r[0]: tuple(r[1:]) for r in
                conn.execute("SELECT runid, stale, journal, identity, pub, signed_at, map FROM receipts")}
        baselines = {r[0][len("receipt_baseline:"):] for r in conn.execute(
            "SELECT k FROM sweepmeta WHERE k GLOB 'receipt_baseline:*'")}
        legacy_pending = sum(not ident and (jr == "PENDING" or st in (1, 2))
                             and rid not in baselines
                             for rid, (st, jr, ident, _pub, _at, _map) in rows.items())
        if legacy_pending:
            print("receipt identity unknown: %d legacy pending reread(s) deferred"
                  % legacy_pending, file=sys.stderr)
        # THE SAME SETTLE WINDOW THE EVIDENCE INDEX USES, and for the same
        # reason one level along: the receipt is written at the run's end edge
        # and the upload it commits to arrives AFTERWARDS, so a receipt read the
        # instant it appears records "no .view on this host" for a file that is
        # on its way.  Ten minutes is far past the 25 s a two-minute sidecar
        # takes at 30 ms RTT.
        cutoff = t0 - surfd.EVIDENCE_SETTLE
        vkey = lambda f: "receipt_view_wait:" + os.path.relpath(f, surfd.EVIDENCE_DIR)
        view_wait = {r[0]: r[1] for r in conn.execute(
            "SELECT k, v FROM sweepmeta WHERE k GLOB 'receipt_view_wait:*'")}
        rkey = lambda f: "receipt_rec_wait:" + os.path.relpath(f, surfd.EVIDENCE_DIR)
        rec_wait = {r[0]: r[1] for r in conn.execute(
            "SELECT k, v FROM sweepmeta WHERE k GLOB 'receipt_rec_wait:*'")}
        rec_hints = {}

        def rec_due(f):
            if rkey(f) not in rec_wait:
                return False
            mapname = rows[name(f)][5]
            if mapname not in rec_hints:
                rec_hints[mapname] = receipt_rec_runids(mapname)
            return name(f) in rec_hints[mapname]

        # glob hides unreadable map directories as well as an unreadable root.
        # Enumerate both levels explicitly: incomplete coverage must not move
        # the marker that lets admin distinguish unsigned from not read yet.
        files = []
        with os.scandir(surfd.EVIDENCE_DIR) as maps:
            for entry in maps:
                if entry.is_dir():
                    with os.scandir(entry.path) as evidence:
                        files.extend(f.path for f in evidence if f.name.endswith(".rcpt"))
        files.sort()
        # Base order: never-read oldest first, then stale/PENDING rereads.
        # Preserve queue identities across passes so failures and fresh arrivals
        # cannot monopolize the bounded attempt window. Coverage is separate from
        # ALL unread fresh files, not inferred from this processing order.
        name = lambda f: os.path.basename(f)[:-5]
        fresh = []
        stat_incomplete = False
        retry = 0
        for f in files:
            if name(f) not in rows:
                try:
                    fresh.append((os.path.getmtime(f), f))
                except OSError:
                    # Its age is unknown: no safe new coverage boundary.
                    stat_incomplete = True
                    retry += 1
                    fresh.append((None, f))  # retain identity even before the first stat
        fresh.sort(key=lambda item: (item[0] is None, item[0] or 0, item[1]))

        def journal_due(f):
            _st, journal, _identity, _pub, signed_at, _map = rows[name(f)]
            return journal in ("PENDING", "ABSENT") and (
                os.path.isfile(f[:-5] + ".hid")
                or (journal == "PENDING" and t0 - signed_at >= surfd.JOURNAL_WAIT))

        def due(f):
            stale, _journal, identity, _pub, _signed_at, _map = rows[name(f)]
            if not identity and name(f) not in baselines:
                return False    # migration's stale=1 is NOT operator permission
            if stale in (1, 2):
                return True
            # ABSENT is an observation, not a final verdict on a future upload.
            # Only a final .hid wakes an ABSENT row; only PENDING expires on the
            # ORIGINAL signing observation. Touching the path cannot reset it.
            try:
                if vkey(f) in view_wait and os.path.isfile(f[:-5] + ".view"):
                    return True
                return journal_due(f) or rec_due(f)
            except OSError:
                return False
        todo = [(m, f, True) for m, f in fresh] + \
               [(None, f, False) for f in files if name(f) in rows and due(f)]
        # A queue position belongs to a path, not an index into a rebuilt list.
        # New items join the tail; an attempted item goes back to the tail.
        # sweepmeta holds scheduling only -- never evidence or key sightings.
        qkey = lambda f: "receipt_retry:" + os.path.relpath(f, surfd.EVIDENCE_DIR)
        queued = {r[0]: r[1] for r in conn.execute(
            "SELECT k, v FROM sweepmeta WHERE k GLOB 'receipt_retry:*'")}
        active = {qkey(f) for _m, f, _fresh in todo}
        # A once-seen but unobserved receipt can disappear before recovery.
        # Forgetting it would later turn lost evidence into an unsigned run.
        lost = {k for k in queued if k not in active
                and name(k[len("receipt_retry:"):]) not in rows}
        if lost:
            stat_incomplete = True
            listed_keys = {qkey(f) for f in files}
            retry += sum(k not in listed_keys for k in lost)
        sequence = max(queued.values(), default=0)
        with conn:
            # Listing completed before here; incomplete enumeration never reaps
            # an observed-missing source. A journal/view alone cannot revive it.
            listed_views = {vkey(f) for f in files}
            conn.executemany("DELETE FROM sweepmeta WHERE k = ?",
                             [(k,) for k in view_wait if k not in listed_views])
            listed_recs = {rkey(f) for f in files}
            conn.executemany("DELETE FROM sweepmeta WHERE k = ?",
                             [(k,) for k in rec_wait if k not in listed_recs])
            conn.executemany("DELETE FROM sweepmeta WHERE k = ?",
                             [(k,) for k in queued if k not in active and k not in lost])
            for _mtime, path, _is_fresh in todo:
                key = qkey(path)
                if key not in queued:
                    sequence += 1
                    queued[key] = sequence
                    conn.execute("INSERT INTO sweepmeta (k, v) VALUES (?, ?)", (key, sequence))
        todo.sort(key=lambda item: queued[qkey(item[1])])
        unread = {f: m for m, f in fresh if m is not None and m <= cutoff}
        n = bad = jfault = attempts = 0
        for mtime, path, is_fresh in todo:
            if attempts >= limit:
                break
            runid = name(path)
            if mtime is None:
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    attempts += 1
                    sequence += 1
                    with conn:
                        conn.execute("UPDATE sweepmeta SET v = ? WHERE k = ?",
                                     (sequence, qkey(path)))
                    retry += 1
                    continue
            if mtime > cutoff:
                continue
            delayed = not is_fresh and rows[runid][0] not in (1, 2)
            view_ready = delayed and vkey(path) in view_wait and os.path.isfile(path[:-5] + ".view")
            journal_ready = delayed and journal_due(path)
            # Alternate co-ready sources, not just rows. An unreadable view must
            # not monopolize its own receipt's ready HID (and vice versa).
            view_only = view_ready and (not journal_ready or view_wait[vkey(path)] != 2)
            rec_ready = delayed and rec_due(path)
            # Alternate a pending recording with other sources; the existing
            # view/HID alternation then gives every co-ready source a turn.
            rec_only = rec_ready and (not (view_ready or journal_ready) or rec_wait[rkey(path)] != 2)
            view_only = view_only and not rec_only
            journal_only = delayed and journal_ready and not (view_only or rec_only)
            attempts += 1
            sequence += 1
            with conn:
                conn.execute("UPDATE sweepmeta SET v = ? WHERE k = ?", (sequence, qkey(path)))
                if rec_ready and (view_ready or journal_ready):
                    conn.execute("UPDATE sweepmeta SET v = ? WHERE k = ?",
                                 (2 if rec_only else 1, rkey(path)))
                if view_ready and journal_ready and not rec_only:
                    conn.execute("UPDATE sweepmeta SET v = ? WHERE k = ?",
                                 (2 if view_only else 1, vkey(path)))
            if delayed and not (view_only or journal_only or rec_only):
                # Eligibility can disappear after queueing. Consume/rotate this
                # bounded attempt, but never fall through to an unrelated source
                # (or a full reread) and erase its completed historical finding.
                retry += 1
                continue
            prior = rows.get(runid)
            try:
                got = read_receipt(path, journal_only=journal_only, view_only=view_only,
                                   rec_only=rec_only,
                                   defer_view=vkey(path) in view_wait or rkey(path) in rec_wait,
                                   expected_identity=prior[2] if prior else None,
                                   expected_pub=prior[3] if prior else None)
            except ReceiptIdentityChanged as exc:
                print("%s: %s" % (os.path.basename(path), exc), file=sys.stderr)
                retry += 1
                continue
            # A failed read or a file gone since listing measured no evidence.
            # Leave it retryable, and never claim coverage past an unread run.
            if got is None or not os.path.exists(path):
                retry += 1
                continue
            verdict, pub, mapname, angles, reason, sig, journal, jreason, owed = got[:9]
            partial, identity = got[9:11]
            areason = got[13]
            jmetrics = got[14]
            signed_at = prior[4] if prior else max(1, int(mtime))
            if view_only or rec_only:
                old = conn.execute("SELECT verdict FROM receipts WHERE runid = ?", (runid,)).fetchone()
                fault = verdict == "FAULT" and old is not None and old[0] != "FAULT"
                with conn:
                    if fault:
                        conn.execute("UPDATE receipts SET verdict = 'FAULT', reason = ?"
                                     " WHERE runid = ?", (reason, runid))
                    # Earlier angle faults are historical evidence; absence or a
                    # later clean/BLIND pair cannot clear them. No journal update.
                    if angles:
                        conn.execute("UPDATE receipts SET angles = ?, angles_reason = ?"
                                     " WHERE runid = ? AND angles != 'FAULT'", (angles, areason, runid))
                    if not partial:
                        conn.execute("DELETE FROM sweepmeta WHERE k = ?", (qkey(path),))
                        if view_only or (rec_only and not got[11]):
                            conn.execute("DELETE FROM sweepmeta WHERE k = ?", (vkey(path),))
                        if got[12]:
                            # A late view may retain an observed-missing rec,
                            # never rearm a completed/unknown recording source.
                            if rkey(path) in rec_wait:
                                conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v) VALUES (?, 1)", (rkey(path),))
                        else:
                            conn.execute("DELETE FROM sweepmeta WHERE k = ?", (rkey(path),))
                n += 1
                bad += fault
                retry += partial
                continue
            if partial and not is_fresh:
                # A stale FULL reread measured a new fault but not the content
                # joins. Preserve their prior evidence and the stale retry flag.
                old = conn.execute("SELECT verdict FROM receipts WHERE runid = ?",
                                   (runid,)).fetchone()
                with conn:
                    conn.execute("UPDATE receipts SET verdict = 'FAULT', reason = ?, at = ?,"
                                 " sig = CASE WHEN pub = ? THEN ? ELSE sig END,"
                                 " identity = CASE WHEN identity = '' THEN ? ELSE identity END"
                                 " WHERE runid = ?", (reason, t0, pub, sig, identity, runid))
                    conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v) VALUES (?, 1)",
                                 ("receipt_partial:" + os.path.relpath(path, surfd.EVIDENCE_DIR),))
                    if journal == "FAULT":  # a digest mismatch WAS measured
                        conn.execute("UPDATE receipts SET journal = ?, journal_reason = ?, journal_metrics = ?"
                                     " WHERE runid = ?", (journal, jreason, jmetrics, runid))
                n += 1
                bad += old is not None and old[0] != "FAULT"
                retry += 1
                continue
            if journal_only:
                # Due to a pending or post-timeout journal. The journal columns
                # move, and the verdict only TOWARD FAULT: a late .hid or .view
                # that does not hash to what was signed is a fault the first read
                # could not see, while a .rec pruned since must not clear one
                # (reviews of 692503c and 9c672d1).
                if journal == "ABSENT" and owed and t0 - signed_at < surfd.JOURNAL_WAIT:
                    continue
                old = conn.execute("SELECT verdict FROM receipts WHERE runid = ?",
                                   (runid,)).fetchone()
                fault = verdict == "FAULT" and old is not None and old[0] != "FAULT"
                with conn:
                    if fault:
                        conn.execute("UPDATE receipts SET verdict = 'FAULT', reason = ?"
                                     " WHERE runid = ?", (reason, runid))
                    conn.execute("UPDATE receipts SET journal = ?, journal_reason = ?, journal_metrics = ?"
                                 " WHERE runid = ?", (journal, jreason, jmetrics, runid))
                    conn.execute("DELETE FROM sweepmeta WHERE k = ?", (qkey(path),))
                n += 1
                bad += fault
                jfault += journal == "FAULT"
                continue
            # A signed journal that is not here yet may still be uploading, one
            # chunk per round trip: PENDING, read again when it arrives, ABSENT
            # once JOURNAL_WAIT after signing has passed without it.
            if journal == "ABSENT" and owed and t0 - signed_at < surfd.JOURNAL_WAIT:
                journal = "PENDING"
                jreason = "the receipt signs a journal that has not arrived yet"
            partial_key = "receipt_partial:" + os.path.relpath(path, surfd.EVIDENCE_DIR)
            recovering = conn.execute("SELECT v FROM sweepmeta WHERE k = ?", (partial_key,)).fetchone()
            if recovering:
                # This is completion of a partial reread, not a new operator
                # decision to reinterpret the old evidence. Missing sources
                # must not erase faults measured before the I/O interruption.
                old = conn.execute("SELECT verdict, reason, angles, journal, journal_reason, angles_reason, journal_metrics"
                                   " FROM receipts WHERE runid = ?", (runid,)).fetchone()
                if old:
                    if old[0] == "FAULT":
                        verdict, reason = old[0], old[1]
                    if old[2] == "FAULT" or not angles:
                        angles, areason = old[2], old[5]
                    if old[3] == "FAULT" or (old[3] == "OK" and journal in ("ABSENT", "PENDING", "BLIND")):
                        journal, jreason, jmetrics = old[3], old[4], old[6]
            # First signed_at is the file's mtime: the lobby writes it at the
            # run's end. Preserve that observation across known rereads; a
            # retimed copy is not a later signature. Resume runids start earlier.
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO receipts"
                    " (runid, map, pub, verdict, angles, reason, at, sig, signed_at, stale,"
                    "  journal, journal_reason, identity, angles_reason, journal_metrics)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)",
                    (runid, mapname, pub, verdict, angles, reason, t0, sig,
                     signed_at, journal, jreason, prior[2] if prior and prior[2] else identity, areason, jmetrics))
                bind_key(conn, runid, pub, t0)
                conn.execute("DELETE FROM sweepmeta WHERE k = ?", (qkey(path),))
                conn.execute("DELETE FROM sweepmeta WHERE k = ?", (partial_key,))
                conn.execute("DELETE FROM sweepmeta WHERE k = ?", ("receipt_baseline:" + runid,))
                # Readiness is established only by a complete captured full read,
                # never by a partial fault, a stat, or a journal-only observation.
                if not partial:
                    if got[11]:
                        conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v) VALUES (?, 1)", (vkey(path),))
                    else:
                        conn.execute("DELETE FROM sweepmeta WHERE k = ?", (vkey(path),))
                    if got[12]:
                        conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v) VALUES (?, 1)", (rkey(path),))
                    else:
                        conn.execute("DELETE FROM sweepmeta WHERE k = ?", (rkey(path),))
            unread.pop(path, None)
            n += 1
            bad += verdict != "VALID"
            jfault += journal == "FAULT"
        # A PENDING row whose receipt was reaped is never read again, and its
        # journal went with it: ABSENT once the wait is over.
        listed = set(name(f) for f in files)
        gone = [rid for rid, (_st, jr, ident, _pub, _at, _map) in rows.items()
                if ident and jr == "PENDING" and rid not in listed]
        if gone:
            with conn:
                conn.executemany(
                    "UPDATE receipts SET journal = 'ABSENT', journal_reason = ?"
                    " WHERE runid = ? AND journal = 'PENDING' AND signed_at < ?",
                    [("the journal never arrived", rid, t0 - surfd.JOURNAL_WAIT)
                     for rid in gone])
        # THE WATERMARK covers only the fully observed prefix, regardless of
        # rotation, budget, or failures. Unknown ages prevent any new boundary.
        through = min([cutoff] + [int(m) - 1 for m in unread.values()])
        with conn:
            if not stat_incomplete:
                conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v)"
                             " VALUES ('receipts_through', ?)", (through,))
        if retry:
            print("sweep: %d receipt read(s) deferred after I/O or identity loss; "
                  "coverage %s" % (retry, "unchanged (unknown file age)"
                                  if stat_incomplete else "bounded before unread receipts"),
                  file=sys.stderr)
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
        surfd.receipts_v8(conn)
        # Separate explicit baseline permission from migration's stale=1.
        # This establishes CURRENT metadata only; it cannot recover history.
        conn.execute("INSERT OR REPLACE INTO sweepmeta (k, v)"
                     " SELECT 'receipt_baseline:' || runid, 1 FROM receipts WHERE identity = ''")
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
    if limit <= 0:          # --sims 0: nothing imported, nothing said
        return 0, 0, ""
    mod = _simcheck()
    if mod is None:
        return 0, 0, ""
    try:
        return mod.similarity_step(conn, surfd, limit=limit, tools_dir=TOOLS)
    except Exception as exc:
        print("sweep: similarity step failed: %r" % exc, file=sys.stderr)
        return 0, 0, ""


def _simcheck():
    """The simcheck module, or None with the reason already printed.

    Imported lazily and cached, exactly as the receipt step imports its checkers
    inside the function: a host without simcheck.py must keep running the
    verification it has run since Patch 349.  The cache keeps the failure to one
    line per process; each cron tick is a new process, so a broken host prints it
    every tick, as a failing receipt step does.
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
