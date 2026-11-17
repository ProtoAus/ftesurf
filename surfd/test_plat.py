#!/usr/bin/env python3
"""P1603: a run's platform mark (`plat`, 1 = the Linux game, not mouse verified) ranks, is stored,
bound to its recording like `flags`, and reaches the boards only on the rows that carry it.

    python surfd/test_plat.py
"""
import hashlib
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_board  # noqa: E402

FAILS = []


def check(what, ok, detail=""):
    print(("ok    " if ok else "FAIL  ") + what + (("  [%s]" % (detail,)) if detail and not ok else ""))
    if not ok:
        FAILS.append(what)


def leaf(ticks, player):
    """FS_RunLeaf(ticks, who, "run", "rec") for a lobby's slug-less who."""
    return "%s_%s_run.rec" % (str(int(ticks)).zfill(7),
                              hashlib.sha256(player.encode("utf-8")).hexdigest()[:8])


def put_rec(mod, ticks, player, runid, plat=None):
    """A recording where a lobby on this box would have left it; `plat` in its header if given."""
    d = os.path.join(os.environ["SURFD_RUNS"], "surf_test", mod.leg_dir(0, 0))
    os.makedirs(d, exist_ok=True)
    name = leaf(ticks, player)
    head = ["FTESURF-REC 13", "map surf_test", "track 0", "startseg 0", "leg 0", "tickrate 0.015",
            "owner %s" % player, "runid %s" % runid, "flags 0         "]
    if plat is not None:
        head.append("plat %d" % plat)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(head + ["begin", "0.0000 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0",
                                   "end %d 1 0 0" % ticks]) + "\n")
    return name


def row(mod, player, table="runs"):
    conn = sqlite3.connect(mod._test_db)
    conn.row_factory = sqlite3.Row
    try:
        got = conn.execute("SELECT * FROM %s WHERE player=? ORDER BY rowid DESC" % table,
                           (player,)).fetchone()
        return dict(got) if got else None
    finally:
        conn.close()


def board_row(body, player):
    got = [r for r in body["rows"] if r["player"] == player] if isinstance(body, dict) else []
    return got[0] if got else None


def case_schema():
    def seed(db):                       # a schema-2 board: `runs` without the column
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE lobbies (node TEXT PRIMARY KEY, map TEXT NOT NULL, players INTEGER NOT NULL,
                maxplayers INTEGER NOT NULL, addr TEXT NOT NULL, name TEXT NOT NULL,
                last_seen INTEGER NOT NULL);
            CREATE TABLE runs (map TEXT NOT NULL, track INTEGER NOT NULL, leg INTEGER NOT NULL,
                tier TEXT NOT NULL, style TEXT NOT NULL, player TEXT NOT NULL, name TEXT NOT NULL,
                ticks INTEGER NOT NULL, tickrate REAL NOT NULL, millis INTEGER NOT NULL,
                flags INTEGER NOT NULL, node TEXT NOT NULL, runid TEXT NOT NULL,
                submitted INTEGER NOT NULL, PRIMARY KEY (map, track, leg, tier, style, player));
            INSERT INTO runs VALUES ('surf_test',0,0,'ranked','clean','old','Old',5000,66.666667,
                75000,0,'p27510','r-old',2000000000);
            PRAGMA user_version=2;
            """)
        conn.commit()
        conn.close()

    mod = test_board.fresh(seed=seed)
    conn = sqlite3.connect(mod._test_db)
    try:
        for t in ("runs", "replays"):
            cols = {r[1]: r for r in conn.execute("PRAGMA table_info(%s)" % t)}
            check("migrate adds %s.plat INTEGER NOT NULL DEFAULT 0" % t,
                  "plat" in cols and cols["plat"][2] == "INTEGER" and cols["plat"][3] == 1
                  and cols["plat"][4] == "0", cols.get("plat"))
        check("a row from before reads plat 0",
              conn.execute("SELECT plat FROM runs WHERE player='old'").fetchone() == (0,))
        mod.runs_plat(conn)             # idempotent: every migrate() runs it
        check("runs_plat again is harmless",
              sum(1 for r in conn.execute("PRAGMA table_info(runs)") if r[1] == "plat") == 1)
        check("the schema version is not bumped", conn.execute("PRAGMA user_version").fetchone()[0]
              == mod.SCHEMA_VERSION)
    finally:
        conn.close()
    b = test_board.board(mod)
    check("an old row carries no plat key", board_row(b, "old") is not None
          and "plat" not in board_row(b, "old"), board_row(b, "old"))


def case_post_and_board():
    mod = test_board.fresh()
    body = test_board.submit(mod, player="lin", name="Lin", ticks="4000", runid="r-lin", plat="1")
    check("a plat 1 run is stored on the ranked board", isinstance(body, dict) and body.get("stored")
          and body.get("tier") == "ranked", body)
    check("runs.plat is 1", (row(mod, "lin") or {}).get("plat") == 1, row(mod, "lin"))
    test_board.submit(mod, player="win", name="Win", ticks="4100", runid="r-win")
    check("a run without plat stores 0", (row(mod, "win") or {}).get("plat") == 0, row(mod, "win"))
    b = test_board.board(mod)
    check("/api/board: the marked row says plat 1", (board_row(b, "lin") or {}).get("plat") == 1,
          board_row(b, "lin"))
    check("/api/board: an unmarked row has no plat key (its bytes unchanged)",
          board_row(b, "win") is not None and "plat" not in board_row(b, "win"), board_row(b, "win"))
    for bad in ("2", "x", "-1", "1.5", ""):
        p = "bad%s" % len(FAILS)
        body = test_board.submit(mod, player="p" + hashlib.md5(bad.encode()).hexdigest()[:6],
                                 name="P", ticks="4200", runid="r-" + p, plat=bad)
        who = [r for r in test_board.board(mod)["rows"] if r["ticks"] == 4200]
        check("plat %r: the run is accepted and filed unmarked" % bad,
              isinstance(body, dict) and body.get("stored") and who and "plat" not in who[-1], (body, who))
        conn = sqlite3.connect(mod._test_db)
        conn.execute("DELETE FROM runs WHERE ticks=4200")
        conn.commit()
        conn.close()
    resp = mod.app.test_client().get("/board/api/map", query_string={"map": "surf_test"},
                                      environ_base={"REMOTE_ADDR": "127.0.0.1"})
    web = json.loads(resp.get_data(as_text=True)) if resp.status_code == 200 else {}
    rows = web.get("rows", [])
    lin = [r for r in rows if r.get("name") == "Lin"]
    win = [r for r in rows if r.get("name") == "Win"]
    check("/board/api/map: the marked row says plat 1", lin and lin[0].get("plat") == 1, (resp.status_code, rows))
    check("/board/api/map: an unmarked row has no plat key", win and "plat" not in win[0], win)
    # A stage post carries it the same way (Lobby_RunBody is shared).
    test_board.submit(mod, player="lin", name="Lin", ticks="900", leg="2", runid="r-lin", plat="1")
    b = test_board.board(mod, leg=2)
    check("a stage row keeps the mark", (board_row(b, "lin") or {}).get("plat") == 1, b)


def case_recording():
    mod = test_board.fresh()
    name = put_rec(mod, 4000, "lin", "r-lin", plat=1)
    body = test_board.submit(mod, player="lin", name="Lin", ticks="4000", runid="r-lin", plat="1", rec=name)
    rep = row(mod, "lin", "replays")
    check("a marked run's recording is filed, plat 1, bound", isinstance(body, dict) and body.get("rep")
          and rep and rep["plat"] == 1 and rep["bound"] == 1, (body, rep))
    # A re-post of the same file that drops the mark: the header binds it (_rec_disagrees).
    body = test_board.submit(mod, player="lin", name="Lin", ticks="4000", runid="r-lin", rec=name)
    check("a re-post below its file's plat drops the leaf and leaves the row marked",
          isinstance(body, dict) and body.get("rep") == 0 and (row(mod, "lin") or {}).get("plat") == 1
          and (row(mod, "lin", "replays") or {}).get("plat") == 1, (body, row(mod, "lin")))
    # Windows start, Linux resume: the header has no plat and the run's post does.
    name = put_rec(mod, 4100, "res", "r-res")
    body = test_board.submit(mod, player="res", name="Res", ticks="4100", runid="r-res", plat="1", rec=name)
    check("a post above its header's mark (a later session's client) binds, plat 1",
          isinstance(body, dict) and body.get("rep") and (row(mod, "res", "replays") or {}).get("bound") == 1
          and (row(mod, "res") or {}).get("plat") == 1, (body, row(mod, "res", "replays")))
    # restand rebuilds a board row from its replay: the mark comes with it.
    rid = row(mod, "lin", "replays")["id"]
    conn = sqlite3.connect(mod._test_db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("DELETE FROM runs WHERE player='lin'")
        got = mod.restand(conn, rid)
        conn.commit()
        back = conn.execute("SELECT plat FROM runs WHERE player='lin' AND leg=0").fetchone()
    finally:
        conn.close()
    check("restand stands the row with its replay's mark", got == "moved" and back and back[0] == 1, (got, back))


def case_disagrees(mod):
    d = mod._rec_disagrees
    base = dict(map="surf_test", track="0", leg="0")
    check("_rec_disagrees: header plat 1, post 0 disagrees",
          "plat" in d(dict(base, plat="1"), "surf_test", 0, 0, "", 0, 0, 0))
    check("_rec_disagrees: header plat 1, post 1 agrees", d(dict(base, plat="1"), "surf_test", 0, 0, "", 0, 0, 1) == "")
    check("_rec_disagrees: no header plat, post 1 agrees", d(dict(base), "surf_test", 0, 0, "", 0, 0, 1) == "")
    check("_rec_disagrees: plat not compared (None) never disagrees",
          d(dict(base, plat="1"), "surf_test", 0, 0, "", 0) == "")
    check("_rec_disagrees: an unreadable header plat is not the row's fault",
          d(dict(base, plat="x"), "surf_test", 0, 0, "", 0, 0, 0) == "")


def main():
    case_schema()
    case_post_and_board()
    case_recording()
    case_disagrees(test_board.fresh())
    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
