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
The same pair arises from the other side when flush moves a linked row's time,
so flush drops a link it leaves out of slack and the link pass repairs old ones.
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


def setup(row_ms, rep_ms_list, link=None):
    """scenario()'s fixture without the link pass; the row points at
    rep_ms_list[link] when `link` is given.  -> (conn, replay ids)."""
    conn = S.connect()
    conn.execute("DELETE FROM runs WHERE tier IN ('momentum', 'ranked')")
    conn.execute("DELETE FROM replays WHERE kind IN ('momentum', 'run')")
    ids = []
    for i, ms in enumerate(rep_ms_list):
        ids.append(conn.execute(
            "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style,"
            " player, name, ticks, tickrate, millis, flags, node, submitted,"
            " bytes, kind, bound, runid) VALUES (?,?,"
            " 0,0,?,'momentum','clean',?,'x',1,66.67,?,0,'import',1,1,"
            " 'momentum',1,'r%d')" % i, (MP, MP, "leaf%d.rec" % i, SID, ms)).lastrowid)
    conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
        " tickrate, millis, flags, node, runid, submitted, replay_id)"
        " VALUES (?,0,0,'momentum','clean',?,'x',1,66.67,?,0,'import','',1,?)",
        (MP, SID, row_ms, ids[link] if link is not None else 0))
    conn.commit()
    return conn, ids


def linked(conn):
    """(the momentum row's millis, its replay_id)."""
    return tuple(conn.execute("SELECT millis, replay_id FROM runs WHERE tier='momentum'"
                              " AND map=? AND player=?", (MP, SID)).fetchone())


def api(ms):
    """One momfetch leaderboard row for SID, as main() hands flush()."""
    return (MP, 0, 0, SID, "x", int(round(ms / 15.0)), 1 / 0.015, ms, 2)


class RacingConn(object):
    """`conn`, except `before` runs once just before link_demos' first write --
    another process moving the row between the read and the write."""
    def __init__(self, conn, before):
        self.c, self.before = conn, before

    def execute(self, *a):
        return self.c.execute(*a)

    def executemany(self, *a):
        if self.before:
            f, self.before = self.before, None
            f()
        return self.c.executemany(*a)

    @property
    def total_changes(self):
        return self.c.total_changes

    def __enter__(self):
        return self.c.__enter__()

    def __exit__(self, *a):
        return self.c.__exit__(*a)


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
    # one, never the slower one, whatever order they were filed in.  These two
    # pass the pre-fix read too (it took the fastest demo not under the row), so
    # the third check is the falsifier: the WRITE's re-check of both bounds.
    got, ms, ids = scenario(85000, [90000, 85000])
    check("with a matching and a superseded demo held, the matching one links",
          (ms,), (85000,))
    got, ms, ids = scenario(85000, [85000, 90000])
    check("...and order of filing does not change that", (ms,), (85000,))
    conn, ids = setup(90000, [90000])
    other = S.connect()

    def improve():
        other.execute("UPDATE runs SET millis=85000 WHERE tier='momentum' AND map=?", (MP,))
        other.commit()
    MB.link_demos(RacingConn(conn, improve))
    check("...and a demo superseded between the read and the write is not linked",
          linked(conn), (85000, 0))
    other.close()
    conn.close()


def case_flush_drops_a_stale_link():
    # momindex filed the 90 s demo with its row; the API then reports the 85 s
    # that superseded it.  flush moves the row's time, so the 90 s link must go
    # (link_demos fills replay_id 0 only), and the link pass relinks the 85 s.
    conn, ids = setup(90000, [90000, 85000], link=0)
    MB.flush(conn, [api(85000)])
    check("flush moving a row past its demo's slack clears the link",
          linked(conn), (85000, 0))
    MB.link_demos(conn)
    check("...and the link pass relinks it to the matching demo",
          linked(conn), (85000, ids[1]))
    conn.close()
    conn, ids = setup(90000, [90000], link=0)
    MB.flush(conn, [api(90000 - MB.LINK_SLACK_MS)])
    check("...a new time still within the slack keeps its link",
          linked(conn), (90000 - MB.LINK_SLACK_MS, ids[0]))
    conn.close()
    conn, ids = setup(85000, [85000], link=0)
    MB.flush(conn, [api(90000)])
    check("...and a slower API time moves nothing", linked(conn), (85000, ids[0]))
    conn.close()


def case_stale_links_repaired():
    # A link flush left before it cleared them: an 85 s row on a 90 s demo.  The
    # link pass drops it, and relinks in the same pass when a match is held.
    conn, ids = setup(85000, [90000, 85000], link=0)
    MB.link_demos(conn)
    check("a stale link is replaced by the matching demo", linked(conn), (85000, ids[1]))
    conn.close()
    conn, ids = setup(85000, [90000], link=0)
    MB.link_demos(conn)
    check("...and with no match held it is cleared, not kept", linked(conn), (85000, 0))
    conn.close()
    conn, ids = setup(85000, [85000 + MB.LINK_SLACK_MS], link=0)
    MB.link_demos(conn)
    check("...a link within the slack is left alone",
          linked(conn), (85000, ids[0]))
    # Only the momentum tier: a ranked row's link is the submit path's business.
    rid = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player,"
        " name, ticks, tickrate, millis, flags, node, submitted, bytes, kind, bound,"
        " runid) VALUES (?,?,0,0,'own.rec','ranked','clean','p','x',1,66.67,90000,0,"
        " 'p27510',1,1,'run',1,'r')", (MP, MP)).lastrowid
    conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
        " tickrate, millis, flags, node, runid, submitted, replay_id)"
        " VALUES (?,0,0,'ranked','clean','p','x',1,66.67,85000,0,'p27510','r',1,?)",
        (MP, rid))
    conn.commit()
    MB.link_demos(conn)
    check("...and a ranked row's link is not the repair's to touch",
          conn.execute("SELECT replay_id FROM runs WHERE tier='ranked'").fetchone()[0], rid)
    conn.close()


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
                 case_already_linked_untouched, case_flush_drops_a_stale_link,
                 case_stale_links_repaired):
        print("\n%s:" % case.__name__)
        case()
    print("\n%d checks, %d failed" % (CHECKS[0], len(FAILED)))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
