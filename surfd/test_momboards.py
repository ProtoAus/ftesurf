#!/usr/bin/env python3
"""
test_momboards.py -- the falsifier for momboards.py's link pass.

    python surfd/test_momboards.py

Stdlib only, no network and no fixture: `link_demos` is pure DB logic.  The
case that matters is the upper bound -- a superseded personal best (slower than
the row it would watch) must NOT become that row's watch link.  Before the fix
`link_demos` filtered `recording >= row - LINK_SLACK_MS`, a lower bound only, so
a 90 s demo linked to an 85 s row; `link_exact` in momgrab.py has always used
`abs(millis - row) <= LINK_MS`, and this brings the top-up pass to the same rule.
"""

import os
import sys
import tempfile

FAILED = []
CHECKS = [0]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(label, got, want):
    CHECKS[0] += 1
    ok = got == want
    print("%-4s %-64s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


HOME = tempfile.mkdtemp(prefix="surfd-momb-")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"),
                  SURFD_MOMENTUM=os.path.join(HOME, "momentum"))
import surfd as S          # noqa: E402
import momboards as MB     # noqa: E402

SID = "76561198356066955"
MP = "surf_linktest"


def scenario(row_ms, rep_ms_list, replay_id=0):
    """One momentum runs row (time row_ms) and a set of held momentum replays
    (times rep_ms_list).  Run link_demos and return the row's replay_id and the
    millis of the replay it points at (0 / None when unlinked)."""
    conn = S.connect()
    try:
        conn.execute("DELETE FROM runs WHERE tier='momentum'")
        conn.execute("DELETE FROM replays WHERE kind='momentum'")
        conn.execute(
            "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
            " tickrate, millis, flags, node, runid, submitted, replay_id)"
            " VALUES (?,?,0,'momentum','clean',?,'x',1,66.67,?,0,'mom','',1,?)",
            (MP, 0, SID, row_ms, replay_id))
        ids = []
        for i, ms in enumerate(rep_ms_list):
            cur = conn.execute(
                "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
                " player, name, ticks, tickrate, millis, flags, node, submitted,"
                " bytes, kind, bound, runid) VALUES (?,?,"
                " 0,0,?,'momentum','clean',?,'x',1,66.67,?,0,'import',1,1,"
                " 'momentum',1,'r%d')" % i,
                (MP, MP, "leaf%d.rec" % i, SID, ms))
            ids.append(cur.lastrowid)
        conn.commit()
        MB.link_demos(conn)
        conn.commit()
        r = conn.execute("SELECT replay_id FROM runs WHERE tier='momentum'"
                         " AND map=? AND player=?", (MP, SID)).fetchone()
        got = r[0]
        ms = None
        if got:
            ms = conn.execute("SELECT millis FROM replays WHERE id=?", (got,)).fetchone()[0]
        return got, ms, ids
    finally:
        conn.close()


def case_exact_and_slack():
    got, ms, ids = scenario(85000, [85000])
    check("a recording whose time IS the row's links", (got > 0, ms), (True, 85000))
    got, ms, ids = scenario(85000, [85000 + MB.LINK_SLACK_MS])
    check("...one LINK_SLACK_MS slower (the boundary) still links",
          (got > 0, ms), (True, 85000 + MB.LINK_SLACK_MS))
    got, ms, ids = scenario(85000, [85000 - MB.LINK_SLACK_MS])
    check("...one LINK_SLACK_MS faster (the boundary) still links",
          (got > 0, ms), (True, 85000 - MB.LINK_SLACK_MS))


def case_superseded_not_linked():
    # THE FIX.  A player improved to 85 s; we hold only their old 90 s demo.
    # Before: 90000 >= 85000-20 was true, so the 90 s demo became the 85 s row's
    # watch link -- a run that does not match the time it is filed against.
    got, ms, ids = scenario(85000, [90000])
    check("a superseded PB (5 s slower) does NOT link", (got, ms), (0, None))
    got, ms, ids = scenario(85000, [85000 + MB.LINK_SLACK_MS + 1])
    check("...one ms past the slack does NOT link", (got, ms), (0, None))


def case_impossible_not_linked():
    # The lower bound that already existed, kept as a regression guard: a demo
    # dropped as impossible (0.405 s on a 92 s board) must not become the link.
    got, ms, ids = scenario(92000, [405])
    check("an impossible demo (0.405 s for a 92 s row) does NOT link",
          (got, ms), (0, None))


def case_picks_matching_over_superseded():
    # Both a superseded 90 s and the matching 85 s are held: link the matching
    # one, never the slower one, whatever order they were filed in.
    got, ms, ids = scenario(85000, [90000, 85000])
    check("with a matching and a superseded demo held, the matching one links",
          (ms,), (85000,))
    got, ms, ids = scenario(85000, [85000, 90000])
    check("...and order of filing does not change that", (ms,), (85000,))


def case_already_linked_untouched():
    # link_demos only fills replay_id=0 rows; an already-linked row is left as it
    # is even if a different-time demo is held.
    conn = S.connect()
    try:
        conn.execute("DELETE FROM runs WHERE tier='momentum'")
        conn.execute("DELETE FROM replays WHERE kind='momentum'")
        cur = conn.execute(
            "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
            " player, name, ticks, tickrate, millis, flags, node, submitted,"
            " bytes, kind, bound, runid) VALUES (?,?,"
            " 0,0,'own.rec','momentum','clean',?,'x',1,66.67,85000,0,'import',1,"
            " 1,'momentum',1,'r')", (MP, MP, SID))
        own = cur.lastrowid
        conn.execute(
            "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
            " tickrate, millis, flags, node, runid, submitted, replay_id)"
            " VALUES (?,?,0,'momentum','clean',?,'x',1,66.67,85000,0,'mom','',1,?)",
            (MP, 0, SID, own))
        # A second, slower demo also held; the row already points at its own.
        conn.execute(
            "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
            " player, name, ticks, tickrate, millis, flags, node, submitted,"
            " bytes, kind, bound, runid) VALUES (?,?,"
            " 0,0,'old.rec','momentum','clean',?,'x',1,66.67,90000,0,'import',1,"
            " 1,'momentum',1,'r2')", (MP, MP, SID))
        conn.commit()
        MB.link_demos(conn)
        conn.commit()
        got = conn.execute("SELECT replay_id FROM runs WHERE tier='momentum'"
                           " AND map=?", (MP,)).fetchone()[0]
        check("an already-linked row is never relinked", got, own)
    finally:
        conn.close()


def main():
    S.migrate()
    for case in (case_exact_and_slack, case_superseded_not_linked,
                 case_impossible_not_linked, case_picks_matching_over_superseded,
                 case_already_linked_untouched):
        print("\n%s:" % case.__name__)
        case()
    print("\n%d checks, %d failed" % (CHECKS[0], len(FAILED)))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
