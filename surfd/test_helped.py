#!/usr/bin/env python3
"""P1569: a helped run (TF_HELPED, a P1567 shared save) on the segmented board with its runners.

    python surfd/test_helped.py
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


def case_rec_runners(mod):
    d = tempfile.mkdtemp(prefix="helped_t")
    p = os.path.join(d, "t.rec")
    with open(p, "w", encoding="utf-8") as f:
        f.write("FTESURF-REC 14\nowner Alice Smith\nrunid r-a\nbegin\n0 1 2 3\n"
                "resume 1 9\ntakeover 9 Bob\n1 2 3 4\nresume 2 40\ntakeover 40 Carol \x01x\n2 3 4 5\n"
                "takeover x Nobody\n")
    got = mod.rec_runners(p)
    check("rec_runners: owner, then each takeover, in order", got[:3] == ["Alice Smith", "Bob", got[2]] and len(got) == 3,
          got)
    check("rec_runners: control characters cleaned", "\x01" not in got[2], got)
    check("rec_runners: a malformed takeover is not a runner", "Nobody" not in got, got)
    check("rec_runners: an unreadable file is no runners", mod.rec_runners(os.path.join(d, "none.rec")) == [])


def case_board(mod):
    flags = mod.TF_HELPED | 128 | 8
    body = test_board.submit(mod, flags=flags, player="bob", name="Bob", ticks="5000", runid="g1")
    check("a helped run is accepted onto the segmented board", isinstance(body, dict), body)
    with mod.app.app_context():
        db = mod.get_db()
        db.execute("UPDATE runs SET replay_id=77 WHERE player='bob'")
        db.execute("INSERT OR REPLACE INTO run_helpers (replay_id, names) VALUES (77, ?)", ('["Alice"]',))
        db.commit()
        row = db.execute("SELECT tier, style FROM runs WHERE player='bob'").fetchone()
        check("style_of files it under segmented", row is not None and row["style"] == mod.STYLE_SEGMENTED,
              row and dict(row))
        rows = mod.board_rows(db, "surf_test", 0, 0, row["tier"], mod.STYLE_SEGMENTED, 10, 0)
        bob = [r for r in rows if r["player"] == "bob"]
        check("the helped row carries its runners", bob and bob[0].get("helpers") == ["Alice"], bob)
        test_board.submit(mod, flags=128, player="carl", name="Carl", ticks="5100", runid="c1")
        rows = mod.board_rows(db, "surf_test", 0, 0, row["tier"], mod.STYLE_SEGMENTED, 10, 0)
        carl = [r for r in rows if r["player"] == "carl"]
        check("an ordinary row has no helpers key (its bytes unchanged)", carl and "helpers" not in carl[0], carl)


def case_simcheck():
    import simcheck

    class Rs(object):
        def compare_paths(self, *a, **k):
            raise AssertionError("a helped pair must not be compared")

    class Surfd(object):
        TF_HELPED = 1048576

    old = simcheck._row_path
    simcheck._row_path = lambda surfd, peer: ("peer.rec", None)
    try:
        base = {"id": 1, "map": "m", "track": 0, "leg": 0, "tier": "ranked", "player": "a", "flags": 128}
        helped = dict(base, id=2, player="b", flags=128 | 1048576)
        obs, compared, _ = simcheck._pair_result(Rs(), Surfd(), helped, base, "a.rec", 0)
        check("simcheck stores a helped pair as skip 'helped', never a score",
              obs[11] == "skip" and obs[13] == "helped" and not compared, obs[11:14])
        obs, compared, _ = simcheck._pair_result(Rs(), Surfd(), base, helped, "a.rec", 0)
        check("...either way round", obs[13] == "helped", obs[11:14])
        check("'helped' is a known skip code", "helped" in simcheck.KNOWN_SKIP_CODES)
    finally:
        simcheck._row_path = old


def main():
    mod = test_board.fresh()
    with mod.app.app_context():
        mod.migrate()
    case_rec_runners(mod)
    case_board(mod)
    case_simcheck()
    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
