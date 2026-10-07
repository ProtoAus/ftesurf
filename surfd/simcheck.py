"""simcheck -- cross-run similarity, measured on the fleet and STORED, never acted on.

WHY THIS EXISTS AND WHY IT ACCUSES NOBODY.  A run submitted twice -- a playback of
a recording rather than a performance -- produces two clean rows on the board, and
nothing in this tree sees it: `pm_verify` is an exactness check and PASSes a
faithful playback by design, because the playback IS exact.  BACKLOG item F filed
that gap.  `tools/census/recsim.py` chose the statistic and, on 2026-10-05, the
fleet corpus supplied the first real calibration:

    positive min (an exact replay)  1.0000
    negative max (two honest runs)  0.5866      <- surf_utopia, ONE install, 8 ticks
    separation                      CLEAN, 1.70x   apart in length, cover 0.0000
    negative max, cross-identity    0.2146

So the discriminator separates on genuine independent runs.  What that does NOT
yet buy is a THRESHOLD, and the reason is the sample and not the statistic: 20
negative pairs, of which only 8 are cross-identity.  A similarity gate's hardest
honest case is one player replaying one map -- the same route, the same start, the
same habits -- and a corpus that is mostly one install measures that case while
looking as though it measured the general one.

**SO THIS MODULE IS STORE-ONLY, EXACTLY AS PATCH 422's `receipts` TABLE WAS.**
Nothing in `VER_SQL` reads `sims`, no badge moves, no run is demoted, and no
public route exposes it.  Its job is to start COLLECTING the cross-identity pairs
the calibration lacks, from live submissions, in the background.  When (if) a
threshold is chosen it will be chosen from that accumulated sample rather than
from 20 pairs, and the rows will already exist to test it against.

TWO RULES THAT ARE NOT NEGOTIABLE HERE:

* **A SKIP IS STORED, NOT SILENT.**  `verdict` carries SKIP_SHORT / SKIP_NO_ROWS /
  SKIP_UNREADABLE beside "compared", because a pair that could not be judged is
  not a pair that disagreed.  `recsim.py`'s MIN_LEN exists for exactly this: two
  9-move stub runs agree over all 9 and read 1.0000, which is arithmetically true
  and means nothing.  A corpus that cannot say how much of itself was judgeable
  cannot be calibrated from.
* **THE IDENTITY IS THE GUID DIGEST, NOT THE NAME.**  `same_who` is stored per
  pair.  A run's `who` segment is `<name>-<FS_GuidId>`, and FS_GuidId is sha256 of
  the install's `qkey`, so it survives a rename and does NOT separate two netnames
  on one install -- the fleet holds four identities and 53 of its 64 files are one
  of them.  Any figure quoted from this table must be split on `same_who`, and
  this module's own summary does that rather than reporting one max.

The comparison itself is NOT re-implemented here.  `reccheck` owns the `.rec`
grammar and `recsim` owns the move stream; this module calls `recsim.compare_paths`
so there is one parser for one format, which is the rule `rcptcheck` follows when
it delegates to `reccheck`.  If `recsim` is not importable the step reports that
and stores nothing -- it does not fall back to a second parser.
"""

import os
import sys
import time

# --------------------------------------------------------------------------
# locating the comparison, and refusing to guess at it
# --------------------------------------------------------------------------

#: Where recsim.py lives relative to the game's tools/ (SURFD_TOOLS).  It is a
#: census tool and lives in tools/census/, not tools/, so the path is explicit.
CENSUS_SUBDIR = os.path.join("census", "recsim.py")

#: Read only when the caller passes no directory; sweep.TOOLS reads it too.
_ENV_TOOLS = "SURFD_TOOLS"

#: The highest `match` worth a human's attention.  NOT A THRESHOLD AND NOT A
#: GATE: nothing is demoted, flagged or hidden at or above it.  It is the number
#: the summary uses to decide what to print, set well above the fleet's measured
#: negative max (0.5866) and well below the positive min (1.0000), so that a pair
#: reaching it is worth reading and the honest population does not trip it.  If a
#: real threshold is ever chosen it will be chosen from the accumulated sample and
#: will live in its own constant with its own measurement beside it.
NOTABLE = 0.95


def _recsim(tools_dir=None):
    """The recsim module, or (None, why).

    Searched ONLY under the caller's `tools_dir` (sweep passes its TOOLS), else
    SURFD_TOOLS.  Never beside this file: on the Pi `<surfd>/../tools` is
    /srv/nvme/tools, a steamcmd directory we do not own, and whatever sat there
    would be imported and run by the sweep.  No other override either -- an
    env path to a missing file once let the "no recsim" test arm resolve the
    repo copy and pass.  Imported by path: tools/census is not a package.
    """
    tools = tools_dir or os.environ.get(_ENV_TOOLS)
    if not tools:
        return None, "no tools directory given (%s unset)" % _ENV_TOOLS
    path = os.path.join(tools, CENSUS_SUBDIR)
    if not os.path.isfile(path):
        return None, "no recsim.py found (tried: %s)" % path
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_recsim_mod", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:
        return None, "importing %s failed: %r" % (path, exc)
    if not hasattr(mod, "compare_paths"):
        return None, "%s has no compare_paths (too old?)" % path
    return mod, path


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

SIMS_SQL = """
CREATE TABLE IF NOT EXISTS sims (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    a_id       INTEGER NOT NULL,
    b_id       INTEGER NOT NULL,
    map        TEXT    NOT NULL,
    track      INTEGER NOT NULL,
    leg        INTEGER NOT NULL,
    tier       TEXT    NOT NULL DEFAULT '',
    player_a   TEXT    NOT NULL DEFAULT '',
    player_b   TEXT    NOT NULL DEFAULT '',
    who_a      TEXT    NOT NULL DEFAULT '',
    who_b      TEXT    NOT NULL DEFAULT '',
    same_who   INTEGER NOT NULL DEFAULT 0,
    verdict    TEXT    NOT NULL,
    reason     TEXT    NOT NULL DEFAULT '',
    match      REAL    NOT NULL DEFAULT 0,
    cover      REAL    NOT NULL DEFAULT 0,
    prefix     INTEGER NOT NULL DEFAULT 0,
    offset     INTEGER NOT NULL DEFAULT 0,
    compared   INTEGER NOT NULL DEFAULT 0,
    moves_a    INTEGER NOT NULL DEFAULT 0,
    moves_b    INTEGER NOT NULL DEFAULT 0,
    tick_a     REAL    NOT NULL DEFAULT 0,
    tick_b     REAL    NOT NULL DEFAULT 0,
    at         INTEGER NOT NULL,
    UNIQUE (a_id, b_id)
);
CREATE INDEX IF NOT EXISTS sims_map ON sims (map, track, leg, match);
CREATE INDEX IF NOT EXISTS sims_notable ON sims (match, at);
CREATE INDEX IF NOT EXISTS sims_b ON sims (b_id);
"""


def ensure_schema(conn):
    """Create `sims` if it is missing.  Idempotent and safe to race, because
    `migrate()` runs on EVERY `import surfd` including the sweep's cron import."""
    conn.executescript(SIMS_SQL)


# --------------------------------------------------------------------------
# the step
# --------------------------------------------------------------------------

def _row_path(surfd, row):
    """The file a replays row names, or (None, why).  surfd.replay_file is the one
    path check /api/replay, sweep.py and the admin share."""
    try:
        path, why = surfd.replay_file(row)
    except Exception as exc:
        return None, "replay_file raised %r" % exc
    if path is None:
        return None, why or "unresolved"
    return path, ""


def compare_run(surfd, conn, row, now=None, limit_peers=200, tools_dir=None):
    """Compare one replays row against the other run-kind rows on its map/leg.

    -> (stored, skipped, notable).  Stores one `sims` row per pair examined, so a
    re-run is a no-op on the UNIQUE (a_id, b_id) constraint rather than a second
    opinion.  A pair already stored is not re-compared: like the receipt step,
    what goes stale is the STATISTIC, not the file, and re-measuring everything on
    every tick is how momboards came to cost 2 s and 66 MB before it was made
    incremental.

    Only kind 'run' rows are compared.  An imported tier (momentum, ksf) is
    another community's run under another game's physics and cannot be a playback
    of one of ours, and comparing across tiers would fill the table with pairs
    that mean nothing.

    Every comparison runs with NO transaction open; the rows are written in one
    short transaction after the last.  A pair is ~88 ms on the Pi, and inserting
    between comparisons held the write lock for all the rest: 80 peers held it
    6.9 s, a concurrent /api/run got a 500 and `import surfd` (migrate) failed.
    """
    rs, why = _recsim(tools_dir)
    if rs is None:
        return 0, 0, 0
    t0 = int(time.time()) if now is None else now
    a_id = row["id"]
    if row["kind"] != "run":
        return 0, 0, 0
    pa, w = _row_path(surfd, row)
    if pa is None:
        return 0, 0, 0
    peers = conn.execute(
        "SELECT * FROM replays WHERE map = ? AND track = ? AND leg = ?"
        " AND kind = 'run' AND id != ? ORDER BY id LIMIT ?",
        (row["map"], row["track"], row["leg"], a_id, limit_peers)).fetchall()
    found = []
    for pr in peers:
        have = conn.execute(
            "SELECT id FROM sims WHERE (a_id = ? AND b_id = ?) OR (a_id = ? AND b_id = ?)",
            (a_id, pr["id"], pr["id"], a_id)).fetchone()
        if have:
            continue
        pb, w = _row_path(surfd, pr)
        if pb is None:
            verdict, reason, d = "skip", "peer unresolved: %s" % w, None
        else:
            verdict, reason = rs.compare_paths(pa, pb)
            d = reason if verdict == "compared" else None
            if verdict != "compared":
                verdict, reason = "skip", reason
        match = cover = 0.0
        prefix = offset = compared = ma = mb = 0
        ta = tb = 0.0
        who_a = who_b = ""
        same = 0
        if d:
            match, cover = d["match"], d["cover"]
            prefix, offset, compared = d["prefix"], d["offset"], d["compared"]
            ma, mb = d["moves_a"], d["moves_b"]
            ta, tb = d["tickrate_a"], d["tickrate_b"]
            who_a, who_b = d["who_a"], d["who_b"]
            same = 1 if d["same_who"] else 0
        found.append(((a_id, pr["id"], row["map"], row["track"], row["leg"],
                       row["tier"], row["player"], pr["player"], who_a, who_b, same,
                       verdict, reason if not d else "", match, cover, prefix, offset,
                       compared, ma, mb, ta, tb, t0), d is not None, match))
    if not found:
        return 0, 0, 0
    # All or nothing; a failure raises to similarity_step, which prints it.
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO sims (a_id, b_id, map, track, leg, tier,"
            " player_a, player_b, who_a, who_b, same_who, verdict, reason,"
            " match, cover, prefix, offset, compared, moves_a, moves_b,"
            " tick_a, tick_b, at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [f[0] for f in found])
    skipped = sum(1 for f in found if not f[1])
    notable = sum(1 for f in found if f[1] and f[2] >= NOTABLE)
    return len(found), skipped, notable


def pending(conn, limit=50):
    """Run-kind replays that have no `sims` row yet, oldest first.

    Oldest first for the same reason the receipt step does it: a pass that runs out
    of room still covers everything older than what it left.

    A RUN THAT HAS NO PEER IS NOT PENDING EITHER, and the first cut missed this:
    `compare_run` returns without storing anything for a row with no comparable
    peer, so such a row stayed "pending" forever and every tick re-selected it,
    crowding out newer runs once the limit was reached.  Excluding it here means a
    map with one run on it is asked about once rather than on every pass, and the
    pending count says something true about work left rather than about rows.
    """
    return conn.execute(
        "SELECT r.* FROM replays r WHERE r.kind = 'run'"
        " AND NOT EXISTS (SELECT 1 FROM sims s WHERE s.a_id = r.id OR s.b_id = r.id)"
        " AND EXISTS (SELECT 1 FROM replays p WHERE p.map = r.map"
        "             AND p.track = r.track AND p.leg = r.leg"
        "             AND p.kind = 'run' AND p.id != r.id)"
        " ORDER BY r.id LIMIT ?", (limit,)).fetchall()


def similarity_step(conn, surfd, limit=50, now=None, tools_dir=None):
    """The sweep's entry point.  -> (pairs stored, notable, note).

    `tools_dir` is the CALLER's resolved tools directory (sweep passes its TOOLS).
    Passing it rather than re-deriving it here is the point: a default is policy,
    and this module should not hold a second copy of the host layout.  The first cut
    did, guessed it wrong, and the guess named a steamcmd directory that exists.
    With no recsim the note is "similarity skipped: <why>", on every call.

    A fault here is printed and never stops the verification, exactly as the
    receipt and evidence steps do: this is a store-only measurement, and a
    measurement that cannot run must not take the checks that DO gate badges down
    with it.
    """
    rs, why = _recsim(tools_dir)
    if rs is None:
        return 0, 0, "similarity skipped: %s" % why
    try:
        ensure_schema(conn)
        rows = pending(conn, limit)
    except Exception as exc:
        return 0, 0, "similarity step failed: %r" % exc
    stored = skipped = notable = 0
    for row in rows:
        try:
            s, k, n = compare_run(surfd, conn, row, now=now, tools_dir=tools_dir)
        except Exception as exc:
            print("simcheck: replay %s failed: %r" % (row["id"], exc),
                  file=sys.stderr)
            continue
        stored += s
        skipped += k
        notable += n
    note = ""
    if stored:
        note = "sims +%d" % stored
        if skipped:
            note += " (%d unjudgeable)" % skipped
    return stored, notable, note


def summary(conn):
    """The stored sample, split the only way that means anything.

    -> dict.  A single max over all pairs is the number that misleads, because the
    hardest honest case is ONE PLAYER replaying ONE MAP and a corpus that is mostly
    one install measures that case while looking as though it measured the general
    one.  So every figure here is reported beside its identity split.
    """
    out = {"state": "empty", "pairs": 0, "compared": 0, "skipped": 0, "notable": 0,
           "same_max": None, "cross_max": None, "same_n": 0, "cross_n": 0,
           "unknown_n": 0, "unknown_max": None}
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sims'").fetchone()
        if not exists:
            return dict.fromkeys(out, None) | {"state": "missing"}
        rows = conn.execute(
            "SELECT verdict, match, same_who, who_a, who_b FROM sims").fetchall()
    except Exception:
        return dict.fromkeys(out, None) | {"state": "error"}
    if rows:
        out["state"] = "available"
    for r in rows:
        out["pairs"] += 1
        if r["verdict"] != "compared":
            out["skipped"] += 1
            continue
        out["compared"] += 1
        m = r["match"]
        if m >= NOTABLE:
            out["notable"] += 1
        if r["who_a"] and r["who_b"]:
            if r["same_who"]:
                out["same_n"] += 1
                out["same_max"] = m if out["same_max"] is None else max(out["same_max"], m)
            else:
                out["cross_n"] += 1
                out["cross_max"] = m if out["cross_max"] is None else max(out["cross_max"], m)
        else:
            out["unknown_n"] += 1
            out["unknown_max"] = m if out["unknown_max"] is None else max(out["unknown_max"], m)
    return out


def summary_line(conn):
    """One read-only line, distinguishing no sample from an unavailable sample."""
    s = summary(conn)
    if s["state"] == "missing":
        return "sims: unavailable (table missing)"
    if s["state"] == "error":
        return "sims: unavailable (query error)"
    if not s["pairs"]:
        return "sims: no pairs stored yet"
    parts = ["%d pairs, %d compared, %d unjudgeable" % (s["pairs"], s["compared"],
                                                        s["skipped"])]
    if s["same_n"]:
        parts.append("same-identity max %.4f (n=%d)" % (s["same_max"], s["same_n"]))
    if s["cross_n"]:
        parts.append("cross-identity max %.4f (n=%d)" % (s["cross_max"], s["cross_n"]))
    if s["unknown_n"]:
        parts.append("no identity n=%d" % s["unknown_n"])
    if s["notable"]:
        parts.append("%d AT OR OVER %.2f -- read them, this is not a gate"
                     % (s["notable"], NOTABLE))
    if not s["cross_n"]:
        # SAY WHAT WAS NOT MEASURED.  A sample with no cross-identity pairs has not
        # measured the case a threshold most needs, and printing only a max hides
        # that -- which is what the local census did before recsim grew the split.
        parts.append("NO CROSS-IDENTITY PAIR yet, so this sample cannot calibrate")
    return "sims: " + ", ".join(parts)
