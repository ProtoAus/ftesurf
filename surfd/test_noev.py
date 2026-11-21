#!/usr/bin/env python3
"""P1699: a WOS top-10 main-course or bonus run whose evidence never arrived carries `noev` on the board rows
(the reason: receipt, view or journal), once the receipt reader's watermark has passed it.

    python surfd/test_noev.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_board  # noqa: E402
from test_plat import check, FAILS  # noqa: E402


def eq(label, got, want):
    check(label, got == want, (got, want))


def sql(mod, query, args=()):
    conn = sqlite3.connect(mod._test_db)
    try:
        with conn:
            return conn.execute(query, args).fetchall()
    finally:
        conn.close()


def setup(mod):
    conn = sqlite3.connect(mod._test_db)
    try:
        conn.executescript(mod.RECEIPTS_SQL)
        mod.receipts_v8(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS sweepmeta (k TEXT PRIMARY KEY, v)")
        conn.commit()
    finally:
        conn.close()


def receipt(mod, runid, angles="OK", journal="OK"):
    sql(mod, "INSERT INTO receipts (runid, map, pub, verdict, angles, reason, at, sig, signed_at, journal)"
             " VALUES (?, 'surf_test', ?, 'VALID', ?, '', 1, 1, 1, ?)", (runid, "a" * 64, angles, journal))


def watermark(mod, v):
    sql(mod, "INSERT OR REPLACE INTO sweepmeta (k, v) VALUES ('receipts_through', ?)", (v,))


def marks(body):
    rows = body.get("rows", []) if isinstance(body, dict) else []
    return {r["player"]: r.get("noev") for r in rows}


def main():
    mod = test_board.fresh()
    setup(mod)
    # twelve WOS runs, p00 fastest; p11, p10 slowest (ranks 11, 12 -> never judged)
    for i in range(12):
        body = test_board.submit(mod, player="p%02d" % i, name="P%02d" % i, ticks=str(4000 + i * 100),
                                 runid="r-p%02d" % i, plat="1" if i == 4 else None)
        if not (isinstance(body, dict) and body.get("stored")):
            check("seed run %d stored" % i, False, body)
    for i in (0, 1, 5, 6, 7, 8, 9):
        receipt(mod, "r-p%02d" % i)
    receipt(mod, "r-p02", angles="")                     # no view
    receipt(mod, "r-p03", journal="ABSENT")              # a Windows run without its journal
    receipt(mod, "r-p04", journal="ABSENT")              # a Linux run (plat 1): no journal is expected
    # p10 and p11 (ranks 11 and 12) have no receipt
    m = marks(test_board.board(mod))
    eq("no watermark: nothing is marked", [k for k, v in m.items() if v], [])

    sub = max(r[0] for r in sql(mod, "SELECT submitted FROM runs"))
    watermark(mod, sub + mod.NOEV_MARGIN - 1)
    m = marks(test_board.board(mod))
    eq("the reader has not passed them: nothing is marked", [k for k, v in m.items() if v], [])

    watermark(mod, sub + mod.NOEV_MARGIN + 10)
    sql(mod, "DELETE FROM receipts WHERE runid = 'r-p09'")   # rank 10, no receipt
    m = marks(test_board.board(mod))
    eq("SURFD_NOEV unset (the default): nothing is marked", [k for k, v in m.items() if v], [])
    mod.NOEV_ON = True
    m = marks(test_board.board(mod))
    eq("ranked board: the missing pieces are named",
          {k: v for k, v in m.items() if v}, {"p02": "view", "p03": "journal", "p09": "receipt"})
    eq("a Linux run without a journal is not marked", m.get("p04"), None)
    eq("ranks 11 and 12 (no receipts) are not judged", (m.get("p10"), m.get("p11")), (None, None))
    eq("complete evidence carries no key", "noev" in [r for r in test_board.board(mod)["rows"]
                                                         if r["player"] == "p00"][0], False)

    # the combined board: an imported run ahead pushes p09 (WOS #10) to place 11 there; it is still marked
    sql(mod, "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis, flags, node,"
             " runid, submitted, replay_id) VALUES ('surf_test', 0, 0, 'momentum', 'clean', '7656', 'Imp', 100,"
             " 66.666667, 1000, 0, '', '', 1, 0)")
    m = marks(test_board.board(mod, tier="combined", limit="20"))
    eq("combined board: the same WOS runs are marked, p09 at place 11 included",
          {k: v for k, v in m.items() if v}, {"p02": "view", "p03": "journal", "p09": "receipt"})

    # runs before NOEV_SINCE are not judged
    old = mod.NOEV_SINCE
    mod.NOEV_SINCE = sub + 1
    try:
        m = marks(test_board.board(mod))
        eq("runs before NOEV_SINCE are not marked", [k for k, v in m.items() if v], [])
    finally:
        mod.NOEV_SINCE = old

    # a stage board is not judged
    test_board.submit(mod, player="st", name="St", ticks="500", leg="2", runid="r-st")
    m = marks(test_board.board(mod, leg=2))
    eq("a stage row is not marked", m.get("st"), None)

    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
