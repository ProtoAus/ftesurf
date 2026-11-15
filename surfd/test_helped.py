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
        db.commit()
        # The runners come from the recording when the row is shown (no table): stand in for its lookup.
        d = tempfile.mkdtemp(prefix="helped_b")
        rec = os.path.join(d, "g.rec")
        with open(rec, "w", encoding="utf-8") as f:
            f.write("FTESURF-REC 14\nowner Alice\nbegin\nresume 1 9\ntakeover 9 Bob\n")
        real_rf = mod.replay_file
        mod.replay_file = lambda r: (rec, None)
        db.execute("INSERT INTO replays (id, map, map_dir, track, leg, leaf, tier, style, player, name, ticks,"
                   " tickrate, millis, flags, node, submitted) SELECT 77, map, map, track, leg, 'g.rec', tier,"
                   " style, player, name, ticks, tickrate, millis, flags, node, submitted FROM runs"
                   " WHERE player='bob'")
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


def case_recsim():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "census"))
    import recsim
    d = tempfile.mkdtemp(prefix="helped_t")
    p = os.path.join(d, "t.rec")
    row = "in 1 %d 0 400 0 0 0 0 0 0 0"
    with open(p, "w", encoding="utf-8") as f:
        f.write("FTESURF-REC 11\nowner Alice\nbegin\n")     # recsim models 11; 12+ viewing clocks not yet
        f.write("".join(row % i + "\n" for i in range(30)))
        f.write("resume 1 30\ntakeover 30 Bob\n")
        f.write("".join(row % (100 + i) + "\n" for i in range(12)))
    r = recsim._parse_rec(p)
    check("recsim compares a helped file only after its last takeover", len(r.moves) == 12 and r.mt[0] == 100,
          (len(r.moves), r.mt[:1]))


def case_helpers_of(mod):
    check("helpers_of: the finisher is not their own helper, each once",
          mod.helpers_of(["A", "B", "B", "A"]) == ["B"], mod.helpers_of(["A", "B", "B", "A"]))
    long = ["r%d" % i for i in range(12)]
    check("helpers_of: a long chain keeps the finisher out and caps the rest",
          mod.helpers_of(long) == long[:mod.HELPERS_MAX], mod.helpers_of(long))
    check("helpers_of: one runner is no help", mod.helpers_of(["A"]) == [])


def case_simcheck():
    import simcheck

    class Rs(object):
        def compare_paths(self, *a, **k):
            raise AssertionError("a helped pair must not be compared")

    old = simcheck._row_path
    simcheck._row_path = lambda surfd, peer: ("peer.rec", None)
    try:
        base = {"id": 1, "map": "m", "track": 0, "leg": 0, "tier": "ranked", "player": "a", "flags": 128}
        helped = dict(base, id=2, player="b", flags=128 | 1048576)
        for a, b in ((helped, base), (base, helped)):
            obs, compared, _ = simcheck._pair_result(Rs(), object(), a, b, "a.rec", 0)
            check("simcheck stores a helped pair as skip 'helped' (%s first)" % a["player"],
                  obs[11] == "skip" and obs[13] == "helped" and not compared, obs[11:14])
        check("'helped' is a known skip code", "helped" in simcheck.KNOWN_SKIP_CODES)
    finally:
        simcheck._row_path = old


def main():
    mod = test_board.fresh()
    with mod.app.app_context():
        mod.migrate()
    case_rec_runners(mod)
    case_board(mod)
    case_recsim()
    case_helpers_of(mod)
    case_simcheck()
    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
