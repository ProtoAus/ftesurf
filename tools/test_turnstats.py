#!/usr/bin/env python3
"""
test_turnstats.py -- the falsifier for turnstats.py's integer plateau
comparator and its mc join.

    python tools/test_turnstats.py
    TURNSTATS=<other copy> python tools/test_turnstats.py    # the control

WHY THIS EXISTS.  A comparator that finds plateaus in a keyboard-turn file
proves nothing by itself.  It has to find ONE plateau where the wire dithers
163/164 and none where it alternates 160/165, and each arm has to fail on a
deliberately broken input, so every arm below carries its own negative.

BUILT FROM THE GRAMMAR (the block over SV_RecOpen in src/server/sv_timer.qc):
an `in` row per move with the yaw written as a 16-bit quantum times 360/65536
at %.4f, which is what the recorder prints and what the tool recovers; `mc`
rows carry cumulative mouse counts wrapped at 2^20, and the row for packet N
is in force from N until the next.  NOTHING IS WRITTEN UNDER data/: fixtures
go to a temporary directory and are removed.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TURNSTATS = os.environ.get("TURNSTATS") or os.path.join(HERE, "turnstats.py")

CHECKS = 0
FAILED = []
TMP = None
ts = None       # the module under test, loaded from TURNSTATS in main()


def check(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(what)
        print("  FAIL  %s" % what)
    else:
        print("  ok    %s" % what)


def load_tool():
    spec = importlib.util.spec_from_file_location("turnstats_under_test", TURNSTATS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures, from the grammar.
# ---------------------------------------------------------------------------
TICK = 0.015
QUANTUM = 360.0 / 65536.0
MC_MOD = 1 << 20


def rec(dqs, q0=9000, steps=None, mcs=(), tick=TICK):
    """-> lines.  One `in` row per yaw, from q0 and the per-move quanta `dqs`;
    mt advances `steps` (default 1) per move, pk advances 1 per row.  `mcs` is
    (pk, ax) -> an mc row after that packet's `in` row, ry = ay = 0, rx = ax
    (an honest client's ring equals its read), rej 0."""
    n = len(dqs) + 1
    steps = list(steps) if steps is not None else [1] * len(dqs)
    assert len(steps) == len(dqs)
    L = ["FTESURF-REC 10", "map test_fixture", "track 0", "startseg 0", "leg 0",
         "tickrate %g" % tick, "movetickrate %g" % tick, "clock counted",
         "owner Nobody", "runid 20261002-000000-0", "flags 0", "begin"]
    by_pk = {}
    for pk, ax in mcs:
        by_pk.setdefault(pk, []).append(ax % MC_MOD)
    q, mt = q0 % 65536, 500
    for row in range(n):
        L.append("in %d %d 0.005 450 0 0 0.0000 %.4f 0.0000 0 0"
                 % (row, mt, q * QUANTUM))
        for ax in by_pk.get(row, ()):
            L.append("mc %d %d %d 0 %d 0 0" % (row, row, ax, ax))
        if row < len(dqs):
            q = (q + dqs[row]) % 65536
            mt += steps[row]
    L.append("end %d %d 0 0 %d 0 0 0 0 0 0" % (n, n, n))
    return L


def still(n):
    return [0] * n


def dither(n, a=163, b=164):
    return [a if k % 2 == 0 else b for k in range(n)]


def write(lines, name):
    path = os.path.join(TMP, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run(args):
    p = subprocess.run([sys.executable, TURNSTATS] + list(args),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, p.stdout + p.stderr


def plats_of(path):
    head, rows, mcs = ts.read_rec(path)
    mv = ts.moves(rows)
    return ts.plateaus(mv), mv, rows, mcs


def longest(out):
    """The plateau line's longest, or None when the line has none."""
    m = re.search(r"plateau\s+longest\s+(\d+) moves", out)
    return int(m.group(1)) if m else None


def max_n(pl):
    return max((p.n for p in pl), default=0)


# The tool is a classifier.  None of these may appear in its output.
VERDICT = ("cheat", "suspicious", "guilty", "honest", "legit", "verdict",
           "forged", "fake", "clean", "flagged")


def no_verdict(out, what):
    hit = [w for w in VERDICT if w in out.lower()]
    check(not hit, "%s: no verdict word in the output%s"
          % (what, " (found %s)" % hit if hit else ""))


# ---------------------------------------------------------------------------
# Arms.
# ---------------------------------------------------------------------------
def case_dither_is_one_plateau():
    """Arm 1: a 163/164 dither is one plateau; 170 every 7th move splits it."""
    p = write(rec(still(10) + dither(54) + still(10)), "dither.rec")
    # The CLI first, so a control copy shows what ITS comparator prints here.
    rc, out = run([p])
    check(rc == 0 and longest(out) == 54,
          "the tool prints longest 54 (got %s)" % longest(out))
    check("163 x1" in out and "164 x" not in out,
          "the rate histogram carries one run at 163")
    no_verdict(out, "dither")
    pl, mv, rows, mcs = plats_of(p)
    check(all(abs(m.r) in (163, 164) for m in mv[10:64]),
          "the fixture's moves read 163 or 164 quanta/tick")
    check(len(pl) == 1, "one plateau in the dither stretch (got %d)" % len(pl))
    check(bool(pl) and pl[0].n == 54 and pl[0].rate == 163,
          "it is 54 moves at rate 163, the first move's (got %s)" % (pl[:3],))

    broken = [170 if k % 7 == 6 else d for k, d in enumerate(dither(54))]
    p2 = write(rec(still(10) + broken + still(10)), "dither_broken.rec")
    pl2 = plats_of(p2)[0]
    check(max_n(pl2) == 6,
          "every 7th move at 170 splits it into runs of 6 (got longest %d)" % max_n(pl2))
    rc, out = run([p2])
    check(longest(out) == 6,
          "the tool prints longest 6 for the split stretch (got %s)" % longest(out))


def case_far_apart_is_none():
    """Arm 2: 160/165 alternation is no plateau; 164/165, a quantum apart, is."""
    p = write(rec(still(10) + dither(54, 160, 165) + still(10)), "alt160_165.rec")
    pl = plats_of(p)[0]
    check(pl == [], "alternating 160/165 yields no plateau >= 4 (got %s)" % (pl,))
    rc, out = run([p])
    check(longest(out) == 0, "the tool prints longest 0 (got %s)" % longest(out))
    p = write(rec(still(10) + dither(54, 163, 165) + still(10)), "alt163_165.rec")
    check(plats_of(p)[0] == [], "two quanta apart (163/165) is still none")
    p = write(rec(still(10) + dither(54, 164, 165) + still(10)), "alt164_165.rec")
    pl = plats_of(p)[0]
    check(len(pl) == 1 and pl[0].n == 54,
          "one quantum apart (164/165) is one plateau of 54 (got %s)" % (pl,))


def case_still_and_one_quantum_are_none():
    """Arm 3: rate 0 and |rate| 1 never plateau; |rate| 2 (TURN_MIN) does."""
    for name, dq, want in (("still", 0, 0), ("plus1", 1, 0), ("minus1", -1, 0),
                           ("plus2", 2, 40), ("minus2", -2, 40)):
        p = write(rec(still(5) + [dq] * 40 + still(5)), name + ".rec")
        got = max_n(plats_of(p)[0])
        check(got == want, "dq %+d x40: longest plateau %d (got %d)" % (dq, want, got))
    rc, out = run([os.path.join(TMP, "still.rec")])
    check("cannot measure: 0 turning moves" in out,
          "a still file's plateau line says it cannot measure")
    rc, out = run([os.path.join(TMP, "plus1.rec")])
    check("cannot measure: 0 turning moves" in out,
          "one quantum per tick is not turning")


def case_wrap():
    """Arm 4: a plateau through yaw 0 is whole; a real half-turn jump is not."""
    p = write(rec(still(5) + [164] * 10 + still(5), q0=64908), "wrap_up.rec")
    pl, mv, rows, mcs = plats_of(p)
    yaws = [r["yaw"] for r in rows]
    check(min(yaws) < 10.0 and max(yaws) > 350.0,
          "the fixture's yaw really crosses 0 (%.4f .. %.4f)" % (min(yaws), max(yaws)))
    check(len(pl) == 1 and pl[0].n == 10 and pl[0].rate == 164,
          "+164/tick through the wrap: one plateau of 10 at 164 (got %s)" % (pl,))
    p = write(rec(still(5) + [-164] * 10 + still(5), q0=992), "wrap_down.rec")
    pl = plats_of(p)[0]
    check(len(pl) == 1 and pl[0].n == 10 and pl[0].rate == -164,
          "-164/tick through the wrap: one plateau of 10 at -164 (got %s)" % (pl,))
    p = write(rec(still(5) + [164] * 5 + [32768] + [164] * 5 + still(5), q0=64908),
              "wrap_jump.rec")
    pl = plats_of(p)[0]
    check(max_n(pl) == 5 and len(pl) == 2,
          "a 32768-quantum jump is not a wrap and splits the run (got %s)" % (pl,))


def case_two_tick_move_joins():
    """Arm 5: dq 328 over 2 ticks reads 164/tick and joins; dq 164 over 2 (82/tick) splits."""
    dqs = still(10) + [164] * 6 + [328] + [164] * 6 + still(10)
    steps = [1] * 16 + [2] + [1] * 16
    p = write(rec(dqs, steps=steps), "twotick.rec")
    pl, mv, rows, mcs = plats_of(p)
    m = mv[16]
    check(m.ticks == 2 and m.dq == 328 and m.r == 164,
          "the 2-tick move carries dq 328 and reads 164/tick (got %s)" % (m,))
    check(len(pl) == 1 and pl[0].n == 13 and pl[0].rate == 164,
          "it joins the 1-tick 164 moves into one plateau of 13 (got %s)" % (pl,))
    p = write(rec(still(10) + [164] * 13 + still(10), steps=steps), "twotick_broken.rec")
    pl = plats_of(p)[0]
    check(max_n(pl) == 6 and len(pl) == 2,
          "dq 164 over 2 ticks is 82/tick and splits the run (got %s)" % (pl,))


def case_inject_is_gone():
    """Arm 6: --inject is rejected and the help does not mention it."""
    p = write(rec(still(10) + dither(54) + still(10)), "inject_target.rec")
    rc, out = run(["--inject", p])
    check(rc != 0, "--inject exits non-zero (got %d)" % rc)
    rc, out = run(["--help"])
    check(rc == 0 and "inject" not in out.lower(), "the help text does not mention inject")
    check(not hasattr(ts, "inject_turn"), "no inject_turn in the module")


def case_mc_join():
    """Arm 7: counts behind a plateau make it a mouse one, zero counts a
    keyboard one, no mc rows no join at all -- and a 2^20 wrap is a small delta."""
    dqs = still(10) + dither(54) + still(10)
    # The plateau covers rows 10..64.  Move s draws on the counts of packet
    # s+1, so a mouse at constant speed advances ax at packets 11..64.
    mouse = [(0, 1000)] + [(pk, 1000 + 164 * (pk - 10)) for pk in range(11, 65)]
    p = write(rec(dqs, mcs=mouse), "mc_mouse.rec")
    head, rows, mcs = ts.read_rec(p)
    check(len(mcs) == len(mouse),
          "the fixture's %d mc rows parse (got %d)" % (len(mouse), len(mcs)))
    r = ts.analyse(p)
    check(r["plateaus"] == [(54, 163, 164 * 54)],
          "the plateau is reported with its counts, ax +%d (got %s)"
          % (164 * 54, r["plateaus"]))
    check(ts.keyboard_spans(rows, mcs) == [],
          "a plateau with counts behind it is not a keyboard span")
    rc, out = run([p])
    check("1 with counts (mouse at constant speed" in out
          and "0 runs at zero counts" in out,
          "the tool reports it with counts, apart from the zero-count runs")
    check("rates (with counts)  163 x1" in out and "rates (zero counts)  none" in out,
          "its rate is in the with-counts histogram only")
    no_verdict(out, "mouse")

    p = write(rec(dqs, mcs=[(0, 1000), (30, 1000)]), "mc_keyboard.rec")
    head, rows, mcs = ts.read_rec(p)
    spans = ts.keyboard_spans(rows, mcs)
    check(spans == [(10, 64, 163)],
          "constant counts: keyboard_spans gives (10, 64, 163) (got %s)" % (spans,))
    check(ts.analyse(p)["plateaus"] == [(54, 163, 0)], "and it is reported at zero counts")
    rc, out = run([p])
    check("1 runs at zero counts (keyboard-shaped, longest 54)" in out
          and "0 with counts" in out, "the tool reports it as keyboard-shaped")
    no_verdict(out, "keyboard")

    p = write(rec(dqs), "mc_none.rec")
    head, rows, mcs = ts.read_rec(p)
    check(mcs == [] and ts.keyboard_spans(rows, mcs) == [],
          "no mc rows: no keyboard spans")
    check(ts.analyse(p)["plateaus"] == [(54, 163, None)],
          "no mc rows: the plateau's counts are None, not zero")
    rc, out = run([p])
    check("cannot join" in out and "keyboard-shaped spans: none" in out,
          "the tool says it cannot join")
    check("keyboard-shaped, longest" not in out and "rates (not joined)   163 x1" in out,
          "and keeps the run in the not-joined histogram")

    p = write(rec(dqs, mcs=[(0, MC_MOD - 100), (40, 100)]), "mc_wrap_up.rec")
    check(ts.analyse(p)["plateaus"] == [(54, 163, 200)],
          "ax wrapping 2^20 upward reads as +200")
    p = write(rec(dqs, mcs=[(0, 100), (40, MC_MOD - 100)]), "mc_wrap_down.rec")
    check(ts.analyse(p)["plateaus"] == [(54, 163, -200)],
          "ax wrapping 2^20 downward reads as -200")
    head, rows, mcs = ts.read_rec(p)
    check(ts.keyboard_spans(rows, mcs) == [], "a wrapped delta is not zero counts")

    p = write(rec(dqs, mcs=[(70, 5)]), "mc_late.rec")
    head, rows, mcs = ts.read_rec(p)
    check(ts.analyse(p)["plateaus"] == [(54, 163, None)]
          and ts.keyboard_spans(rows, mcs) == [],
          "a run before the file's first mc row is not joined and not a keyboard span")
    rc, out = run([p])
    check("1 before the first mc row (not joined)" in out,
          "the tool says it was not joined")


def case_too_few_turning_moves():
    """Arm 8: 3 turning moves cannot be measured; 4 can."""
    p = write(rec(still(30) + [164] * 3 + still(30)), "three.rec")
    r = ts.analyse(p)
    check(r is not None and r["turning"] == 3,
          "the fixture has 3 turning moves (got %s)" % (r and r["turning"],))
    rc, out = run([p])
    plat = [l for l in out.splitlines() if l.strip().startswith("plateau")]
    check(len(plat) == 1 and "cannot measure: 3 turning moves, fewer than 4" in plat[0],
          "the plateau line says it cannot measure (got %s)" % plat)
    check("%" not in "".join(plat) and "0.00% of turning" not in out,
          "and prints no percentage")
    no_verdict(out, "three")
    p = write(rec(still(30) + [164] * 4 + still(30)), "four.rec")
    rc, out = run([p])
    plat = [l for l in out.splitlines() if l.strip().startswith("plateau")]
    check(len(plat) == 1 and "100.00% of turning" in plat[0] and "cannot measure" not in out,
          "4 turning moves in one run: 100.00%% of turning (got %s)" % plat)


def case_pooled_and_by_player():
    """--pooled and --by-player work on the new fields and keep the classes apart."""
    a = write(rec(still(10) + dither(54) + still(10), mcs=[(0, 1000), (30, 1000)]),
              "0000001_alpha-0123abcd_x.rec")
    b = write(rec(still(10) + dither(30, 164, 165) + still(10)),
              "0000002_beta-89abcdef_x.rec")
    rc, out = run(["--pooled", a, b])
    check(rc == 0 and "POOLED over 2 recordings: 124 moves, 84 turning" in out,
          "--pooled runs over both files (74 + 50 moves, 54 + 30 turning)")
    check("runs >= 4: 2   longest 54   moves in them 100.00% of turning" in out,
          "pooled plateau counts both files' runs")
    check("1 of 2 files have mc rows: 1 runs at zero counts" in out
          and "rates (not joined, 1 files without mc rows)  164 x1" in out
          and "rates (zero counts)  163 x1" in out,
          "pooled keeps the unjoined file's run apart from the joined one's")
    no_verdict(out, "pooled")
    rc, out = run(["--by-player", a, b])
    check(rc == 0 and out.count("PLAYER ") == 2
          and "0123abcd (alpha)" in out and "89abcdef (beta)" in out,
          "--by-player groups on the filename id")
    c = write(rec(still(30) + [164] * 3 + still(30)), "0000003_gamma-0123abcd_x.rec")
    rc, out = run(["--pooled", c])
    check("plateau    cannot measure: 3 turning moves" in out,
          "pooled says it cannot measure below 4 turning moves")


def main():
    global ts, TMP
    print("testing %s" % TURNSTATS)
    ts = load_tool()
    TMP = tempfile.mkdtemp(prefix="test_turnstats-")
    try:
        for fn in (case_dither_is_one_plateau, case_far_apart_is_none,
                   case_still_and_one_quantum_are_none, case_wrap,
                   case_two_tick_move_joins, case_inject_is_gone, case_mc_join,
                   case_too_few_turning_moves, case_pooled_and_by_player):
            # argv: case-name prefixes to run (default all).
            if sys.argv[1:] and not fn.__name__.startswith(tuple(sys.argv[1:])):
                continue
            print("%s:" % fn.__name__)
            try:
                fn()
            except Exception as e:
                # A control copy may lack the API: a FAIL, not a crash.
                check(False, "%s raised %s: %s" % (fn.__name__, type(e).__name__, e))
            print("")
    finally:
        shutil.rmtree(TMP)      # never swallowed: a leak here is a failure
    check(not os.path.exists(TMP), "the fixture directory is gone")
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
