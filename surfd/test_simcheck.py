"""
test_simcheck.py -- the falsifier for surfd/simcheck.py (schema 10, BACKLOG item F).

    SURFD_HOME=/tmp/surfd-test python3 test_simcheck.py

Never touches a live instance: surfd is imported against a throwaway home and run
tree, and the `.rec` files are written here, so this tests the step and not the
recorder.  Each case has a control that fails if nothing landed.

WHAT IS BEING FALSIFIED, and it is not "the metric works".  recsim.py's own census
established the metric on the fleet corpus (positive min 1.0000 against negative
max 0.5866, a clean 1.70x separation).  What this suite asks is narrower and more
likely to be wrong:

  1. that the step STORES and does not ACCUSE -- nothing in VER_SQL reads `sims`,
     no badge moves, and a pair at match 1.0000 leaves its run's verdict exactly
     where it was.  This is the arm that would catch the step being wired into a
     gate by accident, which is the one defect here that would hurt a player.
  2. that a SKIP is stored as a skip and never as a low score.  A pair that could
     not be judged reading 0.0 is the same false reading as one reading 1.0, and
     MIN_LEN exists because two 9-move stub runs agree over all 9 and report a
     perfect score that means nothing.
  3. that a re-run is idempotent rather than a second opinion.
  4. that the summary SPLITS ON IDENTITY, because a single max over all pairs is
     the number that misleads: the hardest honest case is one player replaying one
     map, and a corpus that is mostly one install measures that while looking as
     though it measured the general one.
  5. that a host without recsim.py keeps migrating and keeps sweeping.  This is the
     rule the receipt step's lazy imports exist for, and it is the one most likely
     to be broken silently -- a module that raises at import takes the whole cron
     tick with it.
"""

import importlib
import importlib.util
import os
import sqlite3
import sys
import tempfile

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def truthy(label, got):
    ok = bool(got)
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, bool(got)))
    if not ok:
        FAILED.append("%s: got %r, want truthy" % (label, got))


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CENSUS = os.path.join(REPO, "tools", "census", "recsim.py")


def fresh(with_census=True):
    """A throwaway surfd + sweep + simcheck, and a run tree to put files in."""
    home = tempfile.mkdtemp(prefix="surfd-sim-")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    runs = os.path.join(home, "ftesurf", "data", "runs")
    os.makedirs(runs)
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"), SURFD_RUNS=runs,
                      SURFD_GAME=home, SURFD_VERIFIER=os.path.join(home, "noengine"))
    for k in ("SURFD_EVIDENCE", "SURFD_KEEP"):
        os.environ.pop(k, None)
    # "A host with no recsim" has to be armed honestly: SURFD_TOOLS pointed at an
    # empty directory AND a module location with no ../tools/census beside it.
    # The first cut of this suite set an environment override to a missing path and
    # the search fell through to the repo copy, so the arm passed by measuring the
    # opposite of what it claimed -- which is why simcheck has no such override.
    if with_census:
        os.environ["SURFD_TOOLS"] = os.path.join(REPO, "tools")
    else:
        empty = os.path.join(home, "emptytools")
        os.makedirs(empty, exist_ok=True)
        os.environ["SURFD_TOOLS"] = empty
    for m in ("surfd", "sweep", "simcheck"):
        sys.modules.pop(m, None)
    sys.path.insert(0, HERE)
    surfd = importlib.import_module("surfd")
    sweep = importlib.import_module("sweep")
    if with_census:
        simcheck = importlib.import_module("simcheck")
    else:
        # Loaded from outside the repo, so its fallback path (../tools/census)
        # resolves to nothing: this is the host layout, not the workstation one.
        stage = os.path.join(home, "stage")
        os.makedirs(stage, exist_ok=True)
        with open(os.path.join(HERE, "simcheck.py"), "r", encoding="utf-8") as fh:
            src = fh.read()
        with open(os.path.join(stage, "simcheck.py"), "w", encoding="utf-8") as fh:
            fh.write(src)
        spec = importlib.util.spec_from_file_location(
            "simcheck", os.path.join(stage, "simcheck.py"))
        simcheck = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(simcheck)
    sweep._SIMCHECK = None
    surfd.migrate()          # takes no connection: it opens its own
    conn = surfd.connect()
    return surfd, sweep, simcheck, conn, runs, home


# --------------------------------------------------------------------------
# making .rec files, and the one grammar line that matters
# --------------------------------------------------------------------------

def write_rec(runs, map_dir, leaf, moves, tickrate=100.0, track=0, leg=0,
              who="proto-26c95e00", ver=9):
    """A .rec with exactly the header keys recsim reads and `len(moves)` in rows.

    The `in` row grammar is recsim.parse_rec's, not reccheck's: it reads fields 2
    (mt), 4-6 (fwd side up) and 10 (bt), and needs 11 tokens to look at a row at
    all.  `moves` is a list of ((fwd, side, up), bt).
    """
    d = os.path.join(runs, map_dir, "main" if leg <= 0 else "stage_%d" % leg)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, leaf)
    out = ["FTESURF-REC %d" % ver, "map %s" % map_dir,
           "track %d" % track, "leg %d" % leg, "tickrate %.4f" % tickrate,
           "begin"]
    for i, (mv, bt) in enumerate(moves):
        out.append("in %d %d 0 %d %d %d 0 0 0 %d 1" % (i, i, mv[0], mv[1], mv[2], bt))
    out.append("end %d 0 0 0 0 0 0 0 0 0 0 0" % len(moves))
    with open(p, "w") as fh:
        fh.write("\n".join(out) + "\n")
    return p


def add_replay(conn, map_dir, leaf, player, track=0, leg=0, kind="run",
               tier="ranked", ticks=1000, submitted=1):
    cur = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player,"
        " name, ticks, tickrate, millis, flags, node, submitted, kind)"
        " VALUES (?,?,?,?,?,?,'normal',?,'n',?,100,?,?,?,?,?)",
        (map_dir.lower(), map_dir, track, leg, leaf, tier, player, ticks,
         ticks * 10, 0, "1", submitted, kind))
    conn.commit()
    return cur.lastrowid


def gen_moves(n, seed=1):
    """n distinct-looking moves, deterministic.  A strafe pattern, not noise: the
    move alphabet on a real run repeats, and a pair of unrelated random streams
    would agree less than two honest runs do."""
    out = []
    for i in range(n):
        fwd = int(400 * ((i * 7 + seed) % 5) / 4)
        side = int(400 * ((i * 3 + seed) % 7) / 6) - 200
        out.append(((fwd, side, 0), 4 if (i % 9) == 0 else 0))
    return out


def perturbed(moves, every=97):
    """The same performance with one move in `every` changed -- a human re-play,
    which is what an honest second attempt looks like."""
    out = []
    for i, (mv, bt) in enumerate(moves):
        if i % every == 0 and i:
            out.append(((mv[0], mv[1] + 1, mv[2]), bt))
        else:
            out.append((mv, bt))
    return out


print("--- 1. the module finds its comparison, and says so when it cannot ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
mod, why = simcheck._recsim()
truthy("recsim.py resolved from SURFD_TOOLS", mod is not None)
truthy("...and it has compare_paths", mod is not None and hasattr(mod, "compare_paths"))

surfd2, sweep2, simcheck2, conn2, runs2, home2 = fresh(with_census=False)
mod2, why2 = simcheck2._recsim()
check("a host with no recsim.py resolves to None", mod2, None)
truthy("...and the reason names what it tried", "no recsim.py found" in why2)
check("...migrate() still stamped the head schema",
      conn2.execute("PRAGMA user_version").fetchone()[0], surfd2.SCHEMA_VERSION)
# And the step must return cleanly rather than raise: a module that cannot find
# its comparison is a host that has not had tools/ deployed, which is a normal
# state and not an error.
res = simcheck2.similarity_step(conn2, surfd2, limit=10)
check("...and the step stores nothing and raises nothing", res[0], 0)
check("...and it reports no notable pair", res[1], 0)
# The note is NOT empty here, and that is deliberate: simcheck.similarity_step
# returns "similarity skipped: <why>" so a reader of the module's own return can
# tell "no recsim" from "nothing to compare".  sweep.similarity_step is the one
# that must stay quiet, because a cron line repeating one unfixable reason every
# five minutes teaches the reader to skip the log -- and that is arm 9's control.
truthy("...and its note names the reason rather than pretending all is well",
       res[2].startswith("similarity skipped"))
truthy("...and the reason says what it tried", "no recsim.py found" in res[2])

print("\n--- 2. a run compared against itself and against an honest re-play ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
check("the sims table exists after migrate",
      [r[0] for r in conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='sims'")],
      ["sims"])

N = 120
base = gen_moves(N, seed=1)
# THREE identities, and the fixture has to be deliberate about which is which:
# the guid hex, NOT the netname, is the identity (it is sha256 of the install's
# qkey), so `proto-26c95e00` and `kap-26c95e00` are ONE install under two names.
# The first cut of this arm wrote `player-26c95e00` intending a second player and
# got a second netname on the first one, then asserted the pair was cross-identity
# -- the assertion failed and the CODE was right, which is the useful direction
# for a test to fail in.
write_rec(runs, "surf_test", "0001000_proto-26c95e00_run.rec", base)
write_rec(runs, "surf_test", "0001000_kap-26c95e00_run.rec", base)         # SAME install: a playback
write_rec(runs, "surf_test", "0001200_other-ab9ae4aa_run.rec", perturbed(base, every=7))

id_a = add_replay(conn, "surf_test", "0001000_proto-26c95e00_run.rec", "pa")
id_b = add_replay(conn, "surf_test", "0001000_kap-26c95e00_run.rec", "pb")
id_c = add_replay(conn, "surf_test", "0001200_other-ab9ae4aa_run.rec", "pc")

P = os.path.join(runs, "surf_test", "main")
# The direct call first, so a failure here is about the comparison and not about
# the sweep's plumbing around it.
rs = simcheck._recsim()[0]
v, d = rs.compare_paths(os.path.join(P, "0001000_proto-26c95e00_run.rec"),
                        os.path.join(P, "0001000_kap-26c95e00_run.rec"))
check("an identical move stream compares", v, "compared")
check("...and reads match 1.0000", round(d["match"], 6), 1.0)
check("...cover 1.0000", round(d["cover"], 6), 1.0)
check("...prefix is the whole run", d["prefix"], N)
check("...two netnames on ONE guid read as the SAME identity", d["same_who"], True)
check("...and both hexes are the guid, not the name",
      (d["who_a"], d["who_b"]), ("26c95e00", "26c95e00"))

v3, d3 = rs.compare_paths(os.path.join(P, "0001000_proto-26c95e00_run.rec"),
                          os.path.join(P, "0001200_other-ab9ae4aa_run.rec"))
check("a different guid reads as a CROSS identity pair", d3["same_who"], False)
check("...and the two hexes differ", d3["who_a"] != d3["who_b"], True)

v2, d2 = rs.compare_paths(os.path.join(P, "0001000_proto-26c95e00_run.rec"),
                          os.path.join(P, "0001200_other-ab9ae4aa_run.rec"))
check("an honest re-play compares", v2, "compared")
truthy("...and reads well under the identical pair (%.4f < 1.0)" % d2["match"],
       d2["match"] < 1.0)
truthy("...its exact prefix is short, not the whole run (%d < %d)" % (d2["prefix"], N),
       d2["prefix"] < N)

print("\n--- 3. the step stores every pair, and a skip as a skip ---")

stored, notable, note = simcheck.similarity_step(conn, surfd, limit=10)
truthy("the step stored pairs (%d)" % stored, stored >= 3)
truthy("...and reported at least one notable (%d)" % notable, notable >= 1)
rows = conn.execute("SELECT * FROM sims ORDER BY id").fetchall()
truthy("sims rows landed (%d)" % len(rows), len(rows) >= 3)
verds = sorted({r["verdict"] for r in rows})
check("every stored row is a comparison or a named skip",
      [v for v in verds if v not in ("compared", "skip")], [])
mx = max(r["match"] for r in rows if r["verdict"] == "compared")
check("the highest stored match is the playback at 1.0", round(mx, 6), 1.0)

print("\n--- 4. STORE-ONLY: a match of 1.0000 moves no verdict and no badge ---")

# This is the arm that would catch the step being wired into a gate by accident.
# Nothing may read `sims`, so a run whose recording is byte-for-byte another
# player's must still verify exactly as it did before the table existed.
check("VER_SQL does not mention sims", "sims" in surfd.VER_SQL, False)
src = open(os.path.join(HERE, "surfd.py"), "r", errors="replace").read()
truthy("no board query in surfd.py reads the sims table",
       "FROM sims" not in src and "JOIN sims" not in src)
sweepsrc = open(os.path.join(HERE, "sweep.py"), "r", errors="replace").read()
truthy("the sweep never passes a sims row into a verdict",
       "simcheck" not in sweepsrc.split("def sweep(")[1].split("\ndef ")[0])
admin = open(os.path.join(HERE, "admin.py"), "r", errors="replace").read()
truthy("admin.py does not read sims either (no badge moves)", "sims" not in admin)

print("\n--- 5. a run too short to judge is stored as a skip, never as a score ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
short = gen_moves(9)                       # MIN_LEN is 50, and 9 is the measured
write_rec(runs, "surf_short", "0000100_proto-26c95e00_run.rec", short)   # stub length
write_rec(runs, "surf_short", "0000100_kap-26c95e00_run.rec", short)     # recsim warns about
add_replay(conn, "surf_short", "0000100_proto-26c95e00_run.rec", "pa")
add_replay(conn, "surf_short", "0000100_kap-26c95e00_run.rec", "pb")
simcheck.similarity_step(conn, surfd, limit=10)
r = conn.execute("SELECT verdict, reason, match FROM sims").fetchone()
truthy("a 9-move pair stored a row", r is not None)
if r:
    check("...and it is a SKIP, not a comparison", r["verdict"], "skip")
    truthy("...its reason says the floor (%r)" % r["reason"], "floor" in r["reason"])
    check("...and its match is 0, not the 1.0000 two identical stubs would read",
          r["match"], 0.0)
    # THE CONTROL FOR THAT: the same two files, compared directly, DO agree over
    # all nine rows.  Without this the arm above would pass on a comparison that
    # never ran, which is the shape that made Patch 484's arm A useless.
    v, d = simcheck._recsim()[0].compare_paths(
        os.path.join(runs, "surf_short", "main", "0000100_proto-26c95e00_run.rec"),
        os.path.join(runs, "surf_short", "main", "0000100_kap-26c95e00_run.rec"),
        min_len=1)
    check("CONTROL: with the floor lifted the same pair reads 1.0000", round(d["match"], 6), 1.0)

print("\n--- 6. a re-run is idempotent, not a second opinion ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
big = gen_moves(80)
write_rec(runs, "surf_idem", "0001000_proto-26c95e00_run.rec", big)
write_rec(runs, "surf_idem", "0001000_kap-ab9ae4aa_run.rec", perturbed(big))
add_replay(conn, "surf_idem", "0001000_proto-26c95e00_run.rec", "pa")
add_replay(conn, "surf_idem", "0001000_kap-ab9ae4aa_run.rec", "pb")
s1, n1, _ = simcheck.similarity_step(conn, surfd, limit=10)
c1 = conn.execute("SELECT COUNT(*) FROM sims").fetchone()[0]
s2, n2, _ = simcheck.similarity_step(conn, surfd, limit=10)
c2 = conn.execute("SELECT COUNT(*) FROM sims").fetchone()[0]
truthy("the first pass stored something (%d)" % s1, s1 > 0)
check("the second pass stored nothing new", s2, 0)
check("...and the row count did not move", (c1, c2), (c1, c1))
check("a re-run reports no new notable pairs", n2, 0)

print("\n--- 7. the summary splits on identity, and says when it cannot ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
big = gen_moves(80)
# one same-identity pair and one cross-identity pair, deliberately at DIFFERENT
# match levels, so a summary that reported one max would be caught by the other.
write_rec(runs, "surf_split", "0001000_proto-26c95e00_run.rec", big)
write_rec(runs, "surf_split", "0001100_kap-26c95e00_run.rec", perturbed(big, every=5))
write_rec(runs, "surf_split", "0001200_other-ab9ae4aa_run.rec", perturbed(big, every=40))
for leaf, pl in (("0001000_proto-26c95e00_run.rec", "pa"),
                 ("0001100_kap-26c95e00_run.rec", "pb"),
                 ("0001200_other-ab9ae4aa_run.rec", "pc")):
    add_replay(conn, "surf_split", leaf, pl)
simcheck.similarity_step(conn, surfd, limit=10)
s = simcheck.summary(conn)
truthy("the summary counted pairs (%d)" % s["pairs"], s["pairs"] >= 3)
truthy("...and split them: %d same, %d cross" % (s["same_n"], s["cross_n"]),
       s["same_n"] >= 1 and s["cross_n"] >= 1)
check("same-identity pairs carry the SAME guid",
      sorted({r["same_who"] for r in conn.execute(
          "SELECT same_who FROM sims WHERE who_a != '' AND who_a = who_b")}), [1])
line = simcheck.summary_line(conn)
truthy("the summary line reports both halves", "same-identity" in line and "cross-identity" in line)
truthy("...and does NOT claim it cannot calibrate when it can", "cannot calibrate" not in line)

# THE CONTROL: a corpus with no cross-identity pair must SAY SO.  This is the
# local census's exact situation (3 same, 4 unknown, 0 cross), and the first cut of
# recsim's note reported a max that looked general.
surfd, sweep, simcheck, conn, runs, home = fresh()
write_rec(runs, "surf_oneid", "0001000_proto-26c95e00_run.rec", big)
write_rec(runs, "surf_oneid", "0001100_kap-26c95e00_run.rec", perturbed(big, every=5))
add_replay(conn, "surf_oneid", "0001000_proto-26c95e00_run.rec", "pa")
add_replay(conn, "surf_oneid", "0001100_kap-26c95e00_run.rec", "pb")
simcheck.similarity_step(conn, surfd, limit=10)
s1 = simcheck.summary(conn)
check("CONTROL: one install gives zero cross-identity pairs", s1["cross_n"], 0)
truthy("CONTROL: ...and the summary line says the sample cannot calibrate",
       "cannot calibrate" in simcheck.summary_line(conn))

print("\n--- 8. an imported tier is never compared against a native run ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
write_rec(runs, "surf_tier", "0001000_proto-26c95e00_run.rec", big)
write_rec(runs, "surf_tier", "0001000_imported_run.rec", big)
add_replay(conn, "surf_tier", "0001000_proto-26c95e00_run.rec", "pa", kind="run")
add_replay(conn, "surf_tier", "0001000_imported_run.rec", "pi", kind="momentum",
           tier="momentum")
simcheck.similarity_step(conn, surfd, limit=10)
check("no pair was stored across tiers", conn.execute("SELECT COUNT(*) FROM sims").fetchone()[0], 0)
check("...and neither row is pending as a run",
      [r["id"] for r in simcheck.pending(conn, 10)], [])

# THE DEFECT THAT CHECK CATCHES, stated on its own: a run with NO comparable peer
# must not stay pending forever.  compare_run stores nothing for it, so a `pending`
# that selected on "has no sims row" alone re-picked it on every tick and crowded
# out newer runs once the limit was reached.  The native row above has no peer of
# its own kind, and this is a second, cleaner case: one run alone on a map.
surfd, sweep, simcheck, conn, runs, home = fresh()
write_rec(runs, "surf_alone", "0001000_proto-26c95e00_run.rec", big)
add_replay(conn, "surf_alone", "0001000_proto-26c95e00_run.rec", "pa", kind="run")
check("a lone run on a map is not pending", [r["id"] for r in simcheck.pending(conn, 10)], [])
st, no, note = simcheck.similarity_step(conn, surfd, limit=10)
check("...and the step stores nothing for it", (st, no), (0, 0))
# and once a peer arrives, both become pending
write_rec(runs, "surf_alone", "0001100_kap-ab9ae4aa_run.rec", perturbed(big))
add_replay(conn, "surf_alone", "0001100_kap-ab9ae4aa_run.rec", "pb", kind="run")
check("a second run on the map makes both pending",
      sorted(r["id"] for r in simcheck.pending(conn, 10)), [1, 2])

print("\n--- 9. the sweep runs the step and prints its line ---")

surfd, sweep, simcheck, conn, runs, home = fresh()
write_rec(runs, "surf_sweep", "0001000_proto-26c95e00_run.rec", big)
write_rec(runs, "surf_sweep", "0001000_player-26c95e00_run.rec", big)
add_replay(conn, "surf_sweep", "0001000_proto-26c95e00_run.rec", "pa")
add_replay(conn, "surf_sweep", "0001000_player-26c95e00_run.rec", "pb")
st, no, note = sweep.similarity_step(conn, limit=10)
truthy("sweep.similarity_step stored pairs (%d)" % st, st > 0)
truthy("...and its note is printable (%r)" % note, note.startswith("sims +"))
truthy("...and it flagged the playback (%d notable)" % no, no >= 1)
st2, no2, note2 = sweep.similarity_step(conn, limit=10)
check("a second sweep pass adds nothing", (st2, no2), (0, 0))

# A host with no recsim: the sweep must still run every OTHER step.  This is the
# arm that would catch the lazy import having become a module-level one, which
# takes the whole cron tick down on a host that has not had tools/ deployed.
surfd3, sweep3, simcheck3, conn3, runs3, home3 = fresh(with_census=False)
st3, no3, note3 = sweep3.similarity_step(conn3, limit=10)
check("with no recsim the sweep's step stores nothing", (st3, no3), (0, 0))
check("...and raises nothing", note3, "")

print("\n" + "=" * 70)
if FAILED:
    print("%d FAILED" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print("all simcheck checks passed")
sys.exit(0)
