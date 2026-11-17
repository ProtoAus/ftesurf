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


def put_rec(mod, ticks, player, runid, plat=None, finish=None):
    """A recording where a lobby on this box would have left it; `plat` in its header if given, and
    a finish `plat` record if `finish` is."""
    d = os.path.join(os.environ["SURFD_RUNS"], "surf_test", mod.leg_dir(0, 0))
    os.makedirs(d, exist_ok=True)
    name = leaf(ticks, player)
    head = ["FTESURF-REC 13", "map surf_test", "track 0", "startseg 0", "leg 0", "tickrate 0.015",
            "owner %s" % player, "runid %s" % runid, "flags 0         "]
    if plat is not None:
        head.append("plat %d" % plat)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(head + ["begin", "0.0000 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"]
                           + (["prof ok", "plat %d" % finish] if finish is not None else [])
                           + ["end %d 1 0 0" % ticks]) + "\n")
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
    # An unknown positive mark is filed as the highest known (unverified is the safe side); garbage 0.
    for raw, want in (("2", 1), ("7", 1), ("99999999999999999999", 1), ("x", 0), ("-1", 0),
                      ("1.5", 0), ("1e3", 0), ("", 0)):
        body = test_board.submit(mod, player="p" + hashlib.md5(raw.encode()).hexdigest()[:6],
                                 name="P", ticks="4200", runid="r-" + raw, plat=raw)
        who = [r for r in test_board.board(mod)["rows"] if r["ticks"] == 4200]
        check("plat %r: the run is accepted and filed plat %d" % (raw, want),
              isinstance(body, dict) and body.get("stored") and who and who[-1].get("plat", 0) == want,
              (body, who))
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
    # The site's map list marks the WR holder (the main ranked clean row 1: Lin's 4000).
    resp = mod.app.test_client().get("/board/api/maps", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    maps = json.loads(resp.get_data(as_text=True)).get("maps", []) if resp.status_code == 200 else []
    st = [m for m in maps if m.get("map") == "surf_test"]
    check("/board/api/maps: a marked WR says plat 1", st and (st[0].get("wr") or {}).get("plat") == 1,
          (resp.status_code, st))
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
    # A post below its own file's mark is filed at the file's and keeps the leaf (submit_run, _rec_plat).
    name2 = put_rec(mod, 3990, "low", "r-low", plat=1)
    body = test_board.submit(mod, player="low", name="Low", ticks="3990", runid="r-low", rec=name2)
    rep = row(mod, "low", "replays")
    check("a post below its file's plat keeps the leaf and is filed at the file's mark",
          isinstance(body, dict) and body.get("rep") and rep and rep["bound"] == 1 and rep["plat"] == 1
          and (row(mod, "low") or {}).get("plat") == 1, (body, rep, row(mod, "low")))
    # Windows start, Linux resume: the header has no plat and the run's post does.
    name = put_rec(mod, 4100, "res", "r-res")
    body = test_board.submit(mod, player="res", name="Res", ticks="4100", runid="r-res", plat="1", rec=name)
    check("a post above its header's mark (a later session's client) binds, plat 1",
          isinstance(body, dict) and body.get("rep") and (row(mod, "res", "replays") or {}).get("bound") == 1
          and (row(mod, "res") or {}).get("plat") == 1, (body, row(mod, "res", "replays")))
    # The board row takes the replay's mark when it adopts it (plat = rep["plat"]): Res's replay is
    # plat 1 (above); its board row goes, and a re-post of the same file with no mark stands it again.
    conn = sqlite3.connect(mod._test_db)
    conn.execute("DELETE FROM runs WHERE player='res'")
    conn.commit()
    conn.close()
    body = test_board.submit(mod, player="res", name="Res", ticks="4100", runid="r-res", rec=name)
    check("a re-post adopting a marked replay stands the row marked",
          isinstance(body, dict) and body.get("stored") and (row(mod, "res") or {}).get("plat") == 1
          and (row(mod, "res", "replays") or {}).get("plat") == 1, (body, row(mod, "res")))
    # The mark only rises: a replay an older surfd filed at 0, re-posted with the same evidence and a
    # bound mark of 1, is raised, and its board row stands marked (max at adoption).
    name3 = put_rec(mod, 4300, "aged", "r-aged", plat=1)
    test_board.submit(mod, player="aged", name="Aged", ticks="4300", runid="r-aged", plat="1", rec=name3)
    conn = sqlite3.connect(mod._test_db)
    conn.execute("UPDATE replays SET plat = 0 WHERE player='aged'")
    conn.execute("DELETE FROM runs WHERE player='aged'")
    conn.commit()
    conn.close()
    body = test_board.submit(mod, player="aged", name="Aged", ticks="4300", runid="r-aged", plat="1", rec=name3)
    check("a same-evidence re-post stands the row at the higher mark",
          isinstance(body, dict) and (row(mod, "aged") or {}).get("plat") == 1, (body, row(mod, "aged")))
    check("...and raises the replay filed at 0", (row(mod, "aged", "replays") or {}).get("plat") == 1,
          row(mod, "aged", "replays"))
    # New evidence under the same leaf (an exact tie re-filed by another run) takes ITS mark: the
    # replays upsert's plat = excluded.plat.
    name4 = put_rec(mod, 4400, "tie", "r-tie1", plat=1)
    test_board.submit(mod, player="tie", name="Tie", ticks="4400", runid="r-tie1", plat="1", rec=name4)
    put_rec(mod, 4400, "tie", "r-tie2")
    body = test_board.submit(mod, player="tie", name="Tie", ticks="4400", runid="r-tie2", rec=name4)
    rep = row(mod, "tie", "replays")
    check("a leaf re-filed with new evidence and no mark carries the new evidence's 0",
          isinstance(body, dict) and rep and rep["runid"] == "r-tie2" and rep["plat"] == 0, (body, rep))
    # The finish's `plat` record binds too (a later session's client raised the run's mark).
    name5 = put_rec(mod, 4500, "fin", "r-fin", finish=1)
    body = test_board.submit(mod, player="fin", name="Fin", ticks="4500", runid="r-fin", rec=name5)
    check("a post below its file's finish `plat` is filed at it, leaf kept",
          isinstance(body, dict) and body.get("rep") and (row(mod, "fin") or {}).get("plat") == 1
          and (row(mod, "fin", "replays") or {}).get("plat") == 1, (body, row(mod, "fin")))
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


def case_upsert():
    mod = test_board.fresh()
    # A board row is the player's best: an improvement replaces its mark (plat = excluded.plat).
    test_board.submit(mod, player="flip", name="Flip", ticks="5000", runid="r-f1", plat="1")
    test_board.submit(mod, player="flip", name="Flip", ticks="4900", runid="r-f2")
    check("a Linux best beaten by a Windows run loses the mark", (row(mod, "flip") or {}).get("plat") == 0,
          row(mod, "flip"))
    resp = mod.app.test_client().get("/board/api/maps", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    st = [m for m in json.loads(resp.get_data(as_text=True)).get("maps", []) if m.get("map") == "surf_test"]
    check("/board/api/maps: an unmarked WR has no plat key", st and st[0].get("wr")
          and "plat" not in st[0]["wr"], st)
    test_board.submit(mod, player="flop", name="Flop", ticks="5000", runid="r-g1")
    test_board.submit(mod, player="flop", name="Flop", ticks="4900", runid="r-g2", plat="1")
    check("a Windows best beaten by a Linux run gains the mark", (row(mod, "flop") or {}).get("plat") == 1,
          row(mod, "flop"))
    test_board.submit(mod, player="flop", name="Flop", ticks="4950", runid="r-g3")
    check("a slower Windows run leaves the Linux best marked", (row(mod, "flop") or {}).get("plat") == 1,
          row(mod, "flop"))


def case_header(mod):
    hp = mod._rec_plat
    check("_rec_plat: absent, unreadable or negative is 0",
          (hp({}), hp({"plat": "x"}), hp({"plat": "-1"}), hp({"plat": " "})) == (0, 0, 0, 0))
    check("_rec_plat: 1 is 1, an unknown higher mark the highest known",
          (hp({"plat": "1"}), hp({"plat": "5 "}), hp({"plat": "9" * 30}), hp({"plat": "9" * 5000}))
          == (1, mod.PLAT_MAX, mod.PLAT_MAX, mod.PLAT_MAX))
    base = dict(map="surf_test", track="0", leg="0", plat="1")
    check("_rec_disagrees never drops a leaf over plat", mod._rec_disagrees(base, "surf_test", 0, 0, "", 0) == "")


def main():
    case_schema()
    case_post_and_board()
    case_recording()
    case_upsert()
    case_header(test_board.fresh())
    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
