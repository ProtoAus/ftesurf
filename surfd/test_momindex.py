"""Does importing Momentum runs change the ranked board?  It must not.

  SURFD_HOME=<tmp> python surfd/test_momindex.py --db <a copy of surfd.db> \
                                                 --momentum <data/momentum>

The claim this file exists to falsify is the one the whole design rests on:
imported runs sit in their own `tier`, every board query filters on `tier`, so
the ranked and community boards cannot move.  That is cheap to assert and cheap
to get wrong -- a stray join, a COUNT without the predicate, an ORDER BY that
ties differently once more rows exist -- so it is measured instead.

METHOD.  Snapshot /api/board for every (map, track, leg, style) that has a
ranked or community row, through the real Flask app against a copy of the LIVE
database.  Import.  Snapshot again.  Require equality.

`t` is excluded from the comparison and nothing else is: it is the response's
own clock and differs between any two calls a second apart.  Excluding a field
is how a comparison is made to pass, so it is named here and there is exactly
one.

AND THE TEST MUST PROVE THE IMPORT HAPPENED.  A no-op import leaves every board
identical too, which would make this green and vacuous.  So the momentum tier
is required to be non-empty afterwards, and a run is required to exist on a map
that ALSO has ranked rows -- an import that only touched maps nobody has played
would not exercise the predicate at all.
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def snapshot(client, boards, S):
    # Clear the rate buckets first.  130 boards snapshotted twice is 260 reads
    # in one 60 s window against WEB_RATE_MAX 120, and the FIRST cut of this
    # test read the resulting 429s as "the import changed 120 boards".  The
    # limiter is not under test here; leaving it armed made the arm measure
    # itself.  Any 429 that survives this is therefore a real finding.
    S._rate.clear()
    out = {}
    for (mp, track, leg, tier, style) in boards:
        r = client.get("/api/board", query_string={
            "map": mp, "track": track, "leg": leg, "tier": tier, "style": style,
            "limit": 200})
        body = json.loads(r.get_data(as_text=True)) if r.status_code == 200 else None
        if body is not None:
            body.pop("t", None)          # the response's own clock; see above
        out[(mp, track, leg, tier, style)] = (r.status_code, body)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="a COPY of a real surfd.db")
    ap.add_argument("--momentum", required=True)
    args = ap.parse_args()

    home = os.environ.get("SURFD_HOME")
    if not home:
        print("set SURFD_HOME to a scratch directory"); return 2
    os.makedirs(os.path.join(home, "data"), exist_ok=True)
    shutil.copyfile(args.db, os.path.join(home, "data", "surfd.db"))
    os.environ["SURFD_MOMENTUM"] = args.momentum

    import surfd as S
    import momindex

    db = S.connect()
    boards = [(r["map"], r["track"], r["leg"], r["tier"], r["style"])
              for r in db.execute(
                  "SELECT DISTINCT map, track, leg, tier, style FROM runs"
                  " WHERE tier IN (?, ?) ORDER BY 1,2,3,4,5",
                  (S.TIER_RANKED, S.TIER_COMMUNITY))]
    before_runs = db.execute("SELECT COUNT(*) FROM runs WHERE tier IN (?,?)",
                             (S.TIER_RANKED, S.TIER_COMMUNITY)).fetchone()[0]
    ranked_maps = {b[0] for b in boards}
    db.close()

    client = S.app.test_client()
    print("ranked/community boards to compare : %d  (%d rows, %d maps)"
          % (len(boards), before_runs, len(ranked_maps)))
    before = snapshot(client, boards, S)

    sys.argv = ["momindex", "--root", args.momentum]
    momindex.main()

    after = snapshot(client, boards, S)
    db = S.connect()
    mom = db.execute("SELECT COUNT(*) FROM runs WHERE tier=?",
                     (S.TIER_MOMENTUM,)).fetchone()[0]
    mom_maps = {r[0] for r in db.execute(
        "SELECT DISTINCT map FROM runs WHERE tier=?", (S.TIER_MOMENTUM,))}
    after_runs = db.execute("SELECT COUNT(*) FROM runs WHERE tier IN (?,?)",
                            (S.TIER_RANKED, S.TIER_COMMUNITY)).fetchone()[0]
    db.close()

    # WHAT MUST NOT MOVE, and what must.  `counts.momentum` is a field added for
    # this feature so a client can offer the imported board without spending a
    # request to find it empty -- so of course it changes, and comparing it
    # would make this test fail by design.  Excluding it quietly would be the
    # usual way to make a test pass, so it is not excluded quietly: it is
    # asserted in the other direction below, and it must be 0 everywhere BEFORE
    # and non-zero on exactly the boards that received runs.  Everything else --
    # every row, and both existing counts -- must be identical.
    overlap = ranked_maps & mom_maps
    fails, momdelta = [], {}
    for k in boards:
        (bs, bb), (as_, ab) = before[k], after[k]
        if bs != as_ or (bb is None) != (ab is None):
            fails.append(k)
            continue
        if bb is None:
            continue
        momdelta[k] = (bb.get("counts", {}).get(S.TIER_MOMENTUM, 0),
                       ab.get("counts", {}).get(S.TIER_MOMENTUM, 0))
        b2 = dict(bb); a2 = dict(ab)
        b2["counts"] = {t: bb.get("counts", {}).get(t) for t in S.TIERS}
        a2["counts"] = {t: ab.get("counts", {}).get(t) for t in S.TIERS}
        if b2 != a2:
            fails.append(k)

    pre_dirty = [k for k, (b, _a) in momdelta.items() if b != 0]
    got = {k for k, (_b, a) in momdelta.items() if a > 0}

    print()
    print("momentum rows after import        : %d on %d map(s)" % (mom, len(mom_maps)))
    print("maps with BOTH ranked and imported: %d  %s"
          % (len(overlap), sorted(overlap)[:6]))
    print("ranked/community row count        : %d -> %d" % (before_runs, after_runs))
    print("boards whose response changed     : %d" % len(fails))
    for k in fails[:4]:
        print("   CHANGED %s" % (k,))
        (bs, bb), (as_, ab) = before[k], after[k]
        if bs != as_:
            print("      status %s -> %s" % (bs, as_))
        if not (bb and ab):
            continue
        for f in sorted(set(bb) | set(ab)):
            if bb.get(f) != ab.get(f):
                if f == "rows":
                    for i, (x, y) in enumerate(zip(bb.get(f) or [], ab.get(f) or [])):
                        if x != y:
                            d = [kk for kk in set(x) | set(y) if x.get(kk) != y.get(kk)]
                            print("      rows[%d] differs in %s" % (i, d))
                            for kk in d[:4]:
                                print("           %-8s %r -> %r" % (kk, x.get(kk), y.get(kk)))
                            break
                else:
                    print("      %-8s %r -> %r" % (f, bb.get(f), ab.get(f)))

    print("ranked boards that gained a momentum count: %d" % len(got))

    ok = True
    if fails:
        print("\nFAIL: the import moved a board that is not its own."); ok = False
    if mom == 0:
        print("\nFAIL: nothing was imported -- this test proved nothing."); ok = False
    if not overlap:
        print("\nFAIL: no map has both ranked and imported rows, so the tier"
              "\n      predicate was never exercised. Not a pass."); ok = False
    if after_runs != before_runs:
        print("\nFAIL: the ranked/community row count moved."); ok = False
    if pre_dirty:
        print("\nFAIL: %d board(s) already had a momentum count before the"
              " import; the fixture is not clean." % len(pre_dirty)); ok = False
    if not got:
        print("\nFAIL: no ranked board's momentum count moved, so the field"
              "\n      excluded from the comparison was excluded for nothing"
              "\n      and the import never reached a board anyone plays."); ok = False
    if ok:
        print("\nPASS: %d boards' rows and ranked/community counts identical"
              " across an\n      import of %d runs; %d of those boards saw their"
              " momentum count\n      rise from 0, so the predicate was exercised"
              " rather than dodged." % (len(boards), mom, len(got)))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
