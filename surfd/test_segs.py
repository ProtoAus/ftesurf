#!/usr/bin/env python3
"""P1615: a segmented board row carries `segs`, 1 + the `resume` records in its recording.

    python surfd/test_segs.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_board  # noqa: E402

FAILS = []


def check(what, ok, detail=""):
    print(("ok    " if ok else "FAIL  ") + what + (("  [%s]" % detail) if detail and not ok else ""))
    if not ok:
        FAILS.append(what)


def write(d, name, text, mode="w"):
    p = os.path.join(d, name)
    with open(p, mode) as f:
        f.write(text)
    return p


def case_rec_segments(mod):
    d = tempfile.mkdtemp(prefix="segs_t")
    body = "in 1 0 0 400 0 0 0 0 0 0 0\n"
    p = write(d, "a.rec", "FTESURF-REC 14\nowner A\nresume 9 9\nbegin\n" + body
              + "resume 1 9\n" + body + "resume 2 40\ntakeover 40 Bob\n" + body + "resume 3 80\n")
    check("rec_segments: 1 + each resume after begin (a header line is not one)", mod.rec_segments(p) == 4,
          mod.rec_segments(p))
    p = write(d, "b.rec", "FTESURF-REC 14\r\nbegin\r\n" + body + "resume 1 9\r\n", "w")
    check("rec_segments: CRLF lines", mod.rec_segments(p) == 2, mod.rec_segments(p))
    p = write(d, "c.rec", "FTESURF-REC 14\nbegin\n" + body)
    check("rec_segments: no resume is one segment", mod.rec_segments(p) == 1)
    p = write(d, "d.rec", "FTESURF-REC 14\nowner A\n" + body)
    check("rec_segments: no begin is unknown (0)", mod.rec_segments(p) == 0)
    check("rec_segments: an unreadable file is unknown (0)", mod.rec_segments(os.path.join(d, "none.rec")) == 0)
    # Records straddling the read chunk: every split point of the 9-byte pattern, counted once each.
    head = "FTESURF-REC 14\nbegin\n"
    for cut in range(0, 12):
        text = head + "x" * (64 - len(head) + cut) + "\nresume 1 9\n" + "y" * 50 + "\nresume 2 9\n"
        p = write(d, "e%d.rec" % cut, text)
        got = mod.rec_segments(p, chunk=64)
        if got != 3:
            check("rec_segments: a record across a chunk boundary (cut %d)" % cut, False, got)
            break
    else:
        check("rec_segments: records across every chunk boundary counted once", True)
    p = write(d, "f.rec", head + ("resume 1 9\n" * 40))
    check("rec_segments: past the limit is unknown (0), not a partial count",
          mod.rec_segments(p, limit=128, chunk=64) == 0, mod.rec_segments(p, limit=128, chunk=64))
    check("rec_segments: a file ending exactly at the limit is counted",
          mod.rec_segments(p, limit=os.path.getsize(p), chunk=64) == 41,
          mod.rec_segments(p, limit=os.path.getsize(p), chunk=64))


def case_board(mod):
    with mod.app.app_context():
        db = mod.get_db()
        body = test_board.submit(mod, flags=128 | 8, player="sam", name="Sam", ticks="5000", runid="s1")
        check("a segmented run is accepted", isinstance(body, dict), body)
        test_board.submit(mod, flags=128, player="nor", name="Nor", ticks="5100", runid="s2")
        test_board.submit(mod, flags=0, player="cle", name="Cle", ticks="4000", runid="s3")
        db.execute("UPDATE runs SET replay_id=88 WHERE player='sam'")
        db.execute("UPDATE runs SET replay_id=89 WHERE player='cle'")
        db.execute("INSERT INTO replays (id, map, map_dir, track, leg, leaf, tier, style, player, name, ticks,"
                   " tickrate, millis, flags, node, submitted) SELECT 88, map, map, track, leg, 's.rec', tier,"
                   " style, player, name, ticks, tickrate, millis, flags, node, submitted FROM runs"
                   " WHERE player='sam'")
        db.execute("INSERT INTO replays (id, map, map_dir, track, leg, leaf, tier, style, player, name, ticks,"
                   " tickrate, millis, flags, node, submitted) SELECT 89, map, map, track, leg, 'c.rec', tier,"
                   " style, player, name, ticks, tickrate, millis, flags, node, submitted FROM runs"
                   " WHERE player='cle'")
        db.commit()
        d = tempfile.mkdtemp(prefix="segs_b")
        rec = write(d, "s.rec", "FTESURF-REC 14\nbegin\nresume 1 9\nresume 2 19\n")
        real_rf = mod.replay_file
        mod.replay_file = lambda r: (rec, None)
        try:
            tier = db.execute("SELECT tier FROM runs WHERE player='sam'").fetchone()["tier"]
            rows = mod.board_rows(db, "surf_test", 0, 0, tier, mod.STYLE_SEGMENTED, 10, 0)
            sam = [r for r in rows if r["player"] == "sam"]
            nor = [r for r in rows if r["player"] == "nor"]
            check("the segmented row carries segs = 1 + its resumes", sam and sam[0].get("segs") == 3, sam)
            check("segs comes after ver (ver stays the row's last ordinary key)",
                  sam and list(sam[0])[list(sam[0]).index("ver") + 1:] == ["segs"], sam and list(sam[0]))
            check("a segmented row with no recording has no segs key", nor and "segs" not in nor[0], nor)
            tier = db.execute("SELECT tier FROM runs WHERE player='cle'").fetchone()["tier"]
            rows = mod.board_rows(db, "surf_test", 0, 0, tier, mod.STYLE_CLEAN, 10, 0)
            cle = [r for r in rows if r["player"] == "cle"]
            check("a clean row has no segs key (its bytes unchanged)", cle and "segs" not in cle[0], cle)
            # Cached by file identity: a re-filed recording is read again.
            write(d, "s.rec", "FTESURF-REC 14\nbegin\nresume 1 9\n")
            os.utime(rec, ns=(os.stat(rec).st_atime_ns, os.stat(rec).st_mtime_ns + 10 ** 9))
            tier = db.execute("SELECT tier FROM runs WHERE player='sam'").fetchone()["tier"]
            rows = mod.board_rows(db, "surf_test", 0, 0, tier, mod.STYLE_SEGMENTED, 10, 0)
            sam = [r for r in rows if r["player"] == "sam"]
            check("a changed file is counted again", sam and sam[0].get("segs") == 2, sam)
        finally:
            mod.replay_file = real_rf


def main():
    mod = test_board.fresh()
    with mod.app.app_context():
        mod.migrate()
    case_rec_segments(mod)
    case_board(mod)
    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
