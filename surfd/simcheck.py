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

from contextlib import contextmanager
import json
import math
import os
import re
import sqlite3
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

# Operational work cap, not a statistic threshold or a completeness guarantee.
# Previously 50 source rows could each admit 200 peers in one cron pass.
MAX_PAIRS = 200
MAX_SECONDS = 10.0
# Selected SQLite read instructions only; not time, lock waits, writes or RSS.
MAX_SQL_STEPS = 1000000
# Operational ingestion limits, not a validity or similarity threshold. Sources
# over either budget abstain; no truncated prefix may become a measurement.
MAX_SOURCE_BYTES = 16 << 20
MAX_SOURCE_MOVES = 200000

# Stable store-only categories. Prose remains historical detail, not a schema.
SKIP_CODES = {
    "unreadable": "unreadable", "no sample rows": "no_rows",
    "too short": "too_short", "same file": "same_file",
    "malformed input": "malformed", "no comparison opportunities": "no_opportunities",
    "source limit": "source_limit",
}
KNOWN_SKIP_CODES = frozenset(SKIP_CODES.values()) | {"peer_unresolved", "unknown"}

SOURCE_SNAPSHOT_MAX = 512


def source_capture(value):
    """Allowlisted compared-buffer provenance, never current-source validation."""
    if (not isinstance(value, dict) or set(value) != {"version", "a", "b"}
            or type(value["version"]) is not int or value["version"] != 1):
        return None
    for side in ("a", "b"):
        item = value[side]
        if (not isinstance(item, dict) or set(item) != {"sha256", "bytes"}
                or not isinstance(item["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                or type(item["bytes"]) is not int
                or not 0 < item["bytes"] <= MAX_SOURCE_BYTES):
            return None
    return value


def source_snapshot(raw):
    """Bounded versioned storage projection; malformed/legacy input is unbound."""
    if isinstance(raw, bytes):
        if len(raw) > SOURCE_SNAPSHOT_MAX:
            return None
        try:
            raw = raw.decode("utf-8")
        except UnicodeError:
            return None
    if not isinstance(raw, str) or len(raw) > SOURCE_SNAPSHOT_MAX:
        return None
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate source snapshot key")
            value[key] = item
        return value
    try:
        return source_capture(json.loads(raw, object_pairs_hook=unique))
    except (ValueError, TypeError, RecursionError):
        return None


@contextmanager
def lock_wait(conn, milliseconds):
    """Owner opt-in to a per-lock-operation wait, not a pass deadline.

    Owns the busy-handler slot. Restore the previous numeric timeout, not an
    arbitrary external native handler (Python cannot retrieve that handler).
    """
    if type(milliseconds) is not int or not 0 <= milliseconds <= 2147483647:
        raise ValueError("lock wait must be an integer in 0..2147483647 ms")
    previous = _read(conn, "PRAGMA busy_timeout")[0][0]
    try:
        _read(conn, "PRAGMA busy_timeout=%d" % milliseconds)
        yield
    finally:
        _read(conn, "PRAGMA busy_timeout=%d" % previous)


class ReadLimit(Exception):
    """No complete result is available within the selected SQL read allowance."""


class ReadBudget:
    """Explicit connection-owner opt-in; owns the progress-handler slot per read.

    Python SQLite cannot retrieve an existing callback. Never use this on a
    connection whose callback belongs to another caller. Unbudgeted APIs leave
    that slot alone. A reserved final quantum conservatively charges residual
    instructions even for short statements; this may abstain before the cap.
    """
    def __init__(self, conn, steps):
        if type(steps) is not int or steps <= 0:
            raise ValueError("SQL read steps must be a positive integer")
        self.conn = conn
        self.remaining = steps
        self.exhausted = False

    def rows(self, sql, parameters=()):
        if self.remaining <= 0:
            self.exhausted = True
            raise ReadLimit()
        quantum = min(1000, self.remaining)
        self.remaining -= quantum
        def progress():
            if self.remaining < quantum:
                self.exhausted = True
                return 1
            self.remaining -= quantum
            return 0
        cursor = None
        self.conn.set_progress_handler(progress, quantum)
        try:
            cursor = self.conn.execute(sql, parameters)
            return cursor.fetchall()
        except sqlite3.OperationalError:
            if self.exhausted:
                raise ReadLimit() from None
            raise
        finally:
            if cursor is not None:
                cursor.close()
            self.conn.set_progress_handler(None, 0)


def _read(conn, sql, parameters=(), read_budget=None):
    if read_budget is not None:
        if read_budget.conn is not conn:
            raise ValueError("SQL read budget belongs to another connection")
        return read_budget.rows(sql, parameters)
    cursor = conn.execute(sql, parameters)
    try:
        return cursor.fetchall()
    finally:
        cursor.close()


class _PairBudget:
    def __init__(self, maximum, seconds):
        self.remaining = maximum
        self.attempted = 0
        self.deadline = time.monotonic() + seconds
        self.time_exhausted = False

    def expired(self):
        if time.monotonic() >= self.deadline:
            self.time_exhausted = True
        return self.time_exhausted

    def available(self):
        return self.remaining > 0 and not self.expired()

    def take(self):
        if not self.available():
            return False
        self.remaining -= 1
        self.attempted += 1
        return True


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
    if getattr(mod, "BOUNDED_INPUT_VERSION", None) != 1:
        return None, "recsim lacks bounded input capability (too old?)"
    if getattr(mod, "SOURCE_CAPTURE_VERSION", None) != 1:
        return None, "recsim lacks source capture capability (too old?)"
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
    skip_code   TEXT NOT NULL DEFAULT '',
    source_capture TEXT NOT NULL DEFAULT '',
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


CURSOR_SQL = """
CREATE TABLE IF NOT EXISTS sim_cursor (
    scope TEXT NOT NULL CHECK(scope IN ('source', 'peer')),
    source_id INTEGER NOT NULL,
    after_id INTEGER NOT NULL,
    PRIMARY KEY (scope, source_id)
);
"""


def _cursor(conn, scope, source_id=0, read_budget=None):
    """Read-only; historical databases have no admission state yet."""
    if not _read(conn, "SELECT 1 FROM sqlite_master WHERE name='sim_cursor'",
                 read_budget=read_budget):
        return 0
    rows = _read(conn, "SELECT after_id FROM sim_cursor WHERE scope=? AND source_id=?",
                 (scope, source_id), read_budget)
    return rows[0][0] if rows else 0


def _checkpoint(conn, scope, after_id, source_id=0):
    """Admission state; caller owns the short write transaction."""
    # Direct compare_run callers may have only the historical sims table.
    # Initialize only on an actual admitted checkpoint, never on a read.
    conn.execute(CURSOR_SQL)
    conn.execute("INSERT INTO sim_cursor(scope,source_id,after_id) VALUES(?,?,?)"
                 " ON CONFLICT(scope,source_id) DO UPDATE SET after_id=excluded.after_id",
                 (scope, source_id, after_id))


def _advance(conn, scope, after_id, source_id=0):
    """Short committed source admission, not completion or a reservation."""
    with conn:
        _checkpoint(conn, scope, after_id, source_id)


def ensure_schema(conn):
    """Collector's additive tables; idempotent and safe to race."""
    conn.executescript(SIMS_SQL + CURSOR_SQL)
    for column in ("skip_code", "source_capture"):
        if column not in {r[1] for r in conn.execute("PRAGMA table_info(sims)")}:
            try:
                conn.execute("ALTER TABLE sims ADD COLUMN %s TEXT NOT NULL DEFAULT ''" % column)
            except sqlite3.OperationalError:
                # Another schema initializer may have added it after our read.
                if column not in {r[1] for r in conn.execute("PRAGMA table_info(sims)")}:
                    raise


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


def _pair_result(rs, surfd, row, peer, pa, now):
    """Build one observation; exceptions leave this admitted pair unmeasured."""
    pb, why = _row_path(surfd, peer)
    if pb is None:
        verdict, reason, d = "skip", "peer unresolved: %s" % why, None
        skip_code = "peer_unresolved"
    else:
        verdict, reason = rs.compare_paths(pa, pb, max_bytes=MAX_SOURCE_BYTES,
                                          max_moves=MAX_SOURCE_MOVES)
        d = reason if verdict == "compared" else None
        skip_code = "" if verdict == "compared" else SKIP_CODES.get(verdict, "unknown")
        if verdict != "compared":
            verdict, reason = "skip", reason
    match = cover = 0.0
    prefix = offset = compared = ma = mb = 0
    ta = tb = 0.0
    who_a = who_b = ""
    same = 0
    captured = ""
    if d:
        match, cover = d["match"], d["cover"]
        prefix, offset, compared = d["prefix"], d["offset"], d["compared"]
        ma, mb = d["moves_a"], d["moves_b"]
        ta, tb = d["tickrate_a"], d["tickrate_b"]
        who_a, who_b = d["who_a"], d["who_b"]
        same = 1 if d["same_who"] else 0
        snapshot = source_capture(d.get("sources"))
        if snapshot is not None:
            captured = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return ((row["id"], peer["id"], row["map"], row["track"], row["leg"],
             row["tier"], row["player"], peer["player"], who_a, who_b, same,
             verdict, reason if not d else "", skip_code, match, cover, prefix, offset,
             compared, ma, mb, ta, tb, now, captured), d is not None, match)


def compare_run(surfd, conn, row, now=None, limit_peers=200, tools_dir=None,
                diagnostics=None, budget=None, read_budget=None):
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

    Optional diagnostics count unresolved primary sources for this pass only.
    An optional shared budget admits new pair attempts, including unresolved
    peers and raised comparisons; it never stores results for unattempted work.

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
    # Stored pairs must not occupy the bounded candidate window. Historical
    # observations use either orientation, so exclude both before LIMIT.
    after = _cursor(conn, "peer", a_id, read_budget=read_budget)
    peers = _read(conn,
        "SELECT p.* FROM replays p WHERE p.map = ? AND p.track = ? AND p.leg = ?"
        " AND p.kind = 'run' AND p.id != ?"
        " AND NOT EXISTS (SELECT 1 FROM sims s"
        "     WHERE (s.a_id = ? AND s.b_id = p.id)"
        "        OR (s.a_id = p.id AND s.b_id = ?))"
        " ORDER BY (p.id > ?) DESC, p.id LIMIT ?",
        (row["map"], row["track"], row["leg"], a_id, a_id, a_id,
         after, limit_peers), read_budget)
    if not peers:
        return 0, 0, 0
    pa, w = _row_path(surfd, row)
    if pa is None:
        if diagnostics is not None:
            diagnostics["source_unavailable"] += 1
        return 0, 0, 0
    found = []
    last_attempt = None
    for pr in peers:
        # Late recheck remains before admission and cursor advancement.
        try:
            have = _read(conn,
                "SELECT id FROM sims WHERE (a_id = ? AND b_id = ?) OR (a_id = ? AND b_id = ?)",
                (a_id, pr["id"], pr["id"], a_id), read_budget)
        except ReadLimit:
            break  # flush prior results; this peer was never admitted
        if have:
            continue
        if budget is not None:
            if not budget.take():
                break
        last_attempt = pr["id"]
        try:
            found.append(_pair_result(rs, surfd, row, pr, pa, t0))
        except Exception as exc:
            # One faulty pair must not discard prior measurements or prevent
            # later admitted peers. Never invent a skip/zero observation for it.
            if diagnostics is not None:
                diagnostics["pair_failed"] = diagnostics.get("pair_failed", 0) + 1
            print("simcheck: pair %s/%s failed: %r" % (a_id, pr["id"], exc),
                  file=sys.stderr)
    if last_attempt is None:
        return 0, 0, 0
    # Peer checkpoint and observations commit together, including an all-failed
    # admission with no observations. No file work holds this write transaction.
    with conn:
        _checkpoint(conn, "peer", last_attempt, a_id)
        conn.executemany(
            "INSERT OR IGNORE INTO sims (a_id, b_id, map, track, leg, tier,"
            " player_a, player_b, who_a, who_b, same_who, verdict, reason, skip_code,"
            " match, cover, prefix, offset, compared, moves_a, moves_b,"
            " tick_a, tick_b, at, source_capture) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [f[0] for f in found])
    skipped = sum(1 for f in found if not f[1])
    notable = sum(1 for f in found if f[1] and f[2] >= NOTABLE)
    return len(found), skipped, notable


def pending(conn, limit=50, read_budget=None):
    """Eligible sources after the last admitted ID first, then wrap ascending.

    Observations suppress only their own pairs; admission state is not evidence.
    Reads never advance/create state. Rotating finite source fixtures prevents an
    unavailable oldest source monopolizing later passes, not full fleet coverage.
    """
    after = _cursor(conn, "source", read_budget=read_budget)
    return _read(conn,
        "SELECT r.* FROM replays r WHERE r.kind = 'run'"
        " AND EXISTS (SELECT 1 FROM replays p WHERE p.map = r.map"
        "             AND p.track = r.track AND p.leg = r.leg"
        "             AND p.kind = 'run' AND p.id != r.id"
        "             AND NOT EXISTS (SELECT 1 FROM sims s"
        "                 WHERE (s.a_id = r.id AND s.b_id = p.id)"
        "                    OR (s.a_id = p.id AND s.b_id = r.id)))"
        " ORDER BY (r.id > ?) DESC, r.id LIMIT ?", (after, limit), read_budget)


def similarity_step(conn, surfd, limit=50, now=None, tools_dir=None,
                    max_pairs=MAX_PAIRS, max_seconds=MAX_SECONDS, read_budget=None):
    """The sweep's entry point.  -> (pairs stored, notable, note).

    `tools_dir` is the CALLER's resolved tools directory (sweep passes its TOOLS).
    Passing it rather than re-deriving it here is the point: a default is policy,
    and this module should not hold a second copy of the host layout.  The first cut
    did, guessed it wrong, and the guess named a steamcmd directory that exists.
    With no recsim the note is "similarity skipped: <why>", on every call.

    `limit` bounds selected source rows; `max_pairs` independently bounds admitted
    new pair attempts across all of them. Zero disables before loading support.
    Each comparison source is bounded by bytes and moves. `max_seconds` stops
    new row/pair admission cooperatively using a monotonic clock; in-flight work
    finishes and normal results flush. Loader/schema/query time counts too.
    An explicit owner ReadBudget interrupts selected SQL reads as whole queries,
    preserving prior comparisons. This is not a hard timeout, an overall RSS bound or
    complete/fair pair coverage.

    A fault here is printed and never stops the verification, exactly as the
    receipt and evidence steps do: this is a store-only measurement, and a
    measurement that cannot run must not take the checks that DO gate badges down
    with it.
    """
    if not math.isfinite(max_seconds):
        raise ValueError("max_seconds must be finite")
    if limit <= 0 or max_pairs <= 0 or max_seconds <= 0:
        return 0, 0, ""
    budget = _PairBudget(max_pairs, max_seconds)
    rs, why = _recsim(tools_dir)
    if rs is None:
        return 0, 0, "similarity skipped: %s" % why
    try:
        ensure_schema(conn)
        rows = pending(conn, limit, read_budget=read_budget)
    except ReadLimit:
        return 0, 0, "sims SQL read limit reached (coverage not measured)"
    except Exception as exc:
        return 0, 0, "similarity step failed: %r" % exc
    stored = skipped = notable = failed = 0
    diagnostics = {"source_unavailable": 0, "pair_failed": 0}
    for row in rows:
        if not budget.available():
            break
        try:
            # Advance admitted sources even if resolution/comparison later fails.
            # Commit before comparison so no file work holds a write transaction.
            _advance(conn, "source", row["id"])
            s, k, n = compare_run(surfd, conn, row, now=now, tools_dir=tools_dir,
                                  diagnostics=diagnostics, budget=budget,
                                  read_budget=read_budget)
        except ReadLimit:
            break
        except Exception as exc:
            print("simcheck: replay %s failed: %r" % (row["id"], exc),
                  file=sys.stderr)
            failed += 1
            continue
        stored += s
        skipped += k
        notable += n
        if read_budget is not None and read_budget.exhausted:
            break
    note = ""
    if stored:
        note = "sims +%d" % stored
        if skipped:
            note += " (%d unjudgeable)" % skipped
    unavailable = []
    if diagnostics["source_unavailable"]:
        unavailable.append("%d source unavailable" % diagnostics["source_unavailable"])
    if failed:
        unavailable.append("%d row failed" % failed)
    if diagnostics["pair_failed"]:
        unavailable.append("%d pair failed" % diagnostics["pair_failed"])
    if unavailable:
        note = (note + " " if note else "") + "sims unavailable: " + ", ".join(unavailable)
    if read_budget is not None and read_budget.exhausted:
        note = (note + " " if note else "") + "sims SQL read limit reached (coverage not measured)"
    if budget.remaining <= 0:
        note = (note + " " if note else "") + (
            "sims pair limit reached (%d attempted; coverage not measured)" % budget.attempted)
    if budget.expired():
        note = (note + " " if note else "") + (
            "sims time limit reached (cooperative; %d attempted; coverage not measured)"
            % budget.attempted)
    return stored, notable, note


def summary(conn, read_budget=None):
    """The stored sample, split the only way that means anything.

    -> dict.  A single max over all pairs is the number that misleads, because the
    hardest honest case is ONE PLAYER replaying ONE MAP and a corpus that is mostly
    one install measures that case while looking as though it measured the general
    one.  So every figure here is reported beside its identity split.
    """
    out = {"state": "empty", "pairs": 0, "compared": 0, "skipped": 0, "notable": 0,
           "same_max": None, "cross_max": None, "same_n": 0, "cross_n": 0,
           "unknown_n": 0, "unknown_max": None, "skip_codes": {}}
    try:
        exists = _read(conn,
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sims'",
            read_budget=read_budget)
        if not exists:
            return dict.fromkeys(out, None) | {"state": "missing"}
        # Old samples stay unknown; a read never migrates or infers old prose.
        columns = {r[1] for r in _read(conn, "PRAGMA table_info(sims)",
                                     read_budget=read_budget)}
        code = "skip_code" if "skip_code" in columns else "''"
        known = sorted(KNOWN_SKIP_CODES)
        # One sample query/snapshot. Fixed categories bound Python result rows
        # regardless of sample size or arbitrary stored prose/codes. SQLite still
        # scans the sample; only an explicit owner read budget bounds VM work.
        rows = _read(conn,
            "SELECT CASE WHEN verdict = 'compared' THEN"
            "   CASE WHEN who_a != '' AND who_b != '' THEN"
            "     CASE WHEN same_who THEN 'same' ELSE 'cross' END"
            "   ELSE 'unknown' END ELSE 'skip' END AS bucket,"
            " CASE WHEN verdict = 'compared' THEN ''"
            "   WHEN " + code + " IS NULL OR " + code + " = '' THEN 'legacy_unknown'"
            "   WHEN " + code + " IN (" + ",".join("?" for _ in known) + ")"
            "     THEN " + code + " ELSE 'unknown' END AS category,"
            " COUNT(*) AS n, MAX(match) AS maximum,"
            " SUM(CASE WHEN verdict = 'compared' AND match >= ? THEN 1 ELSE 0 END) AS notable"
            " FROM sims GROUP BY bucket, category", (*known, NOTABLE), read_budget)
    except ReadLimit:
        return dict.fromkeys(out, None) | {"state": "limited"}
    except Exception:
        return dict.fromkeys(out, None) | {"state": "error"}
    if rows:
        out["state"] = "available"
    for r in rows:
        n, bucket = r["n"], r["bucket"]
        out["pairs"] += n
        if bucket == "skip":
            out["skipped"] += n
            out["skip_codes"][r["category"]] = n
            continue
        out["compared"] += n
        out["notable"] += r["notable"]
        out[bucket + "_n"] = n
        out[bucket + "_max"] = r["maximum"]
    return out


def summary_line(conn, read_budget=None):
    """One read-only line, distinguishing no sample from an unavailable sample."""
    s = summary(conn, read_budget=read_budget)
    if s["state"] == "limited":
        return "sims: unavailable (SQL read limit; sample not measured)"
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
    if s["skip_codes"]:
        parts.append("skips " + ", ".join("%s=%d" % kv for kv in sorted(s["skip_codes"].items())))
    if not s["cross_n"]:
        # SAY WHAT WAS NOT MEASURED.  A sample with no cross-identity pairs has not
        # measured the case a threshold most needs, and printing only a max hides
        # that -- which is what the local census did before recsim grew the split.
        parts.append("NO CROSS-IDENTITY PAIR yet, so this sample cannot calibrate")
    return "sims: " + ", ".join(parts)
