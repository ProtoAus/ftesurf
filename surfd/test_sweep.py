"""
test_sweep.py -- the falsifier for the verdict sweeper (sweep.py).

    SURFD_HOME=/tmp/surfd-test python3 test_sweep.py

Never touches a live instance: surfd is imported against a throwaway home and
run tree, and the engine is replaced by a stub runner that prints VERIFY lines,
so this tests the sweeper and not pm_verify (cfg/test/p349verify.cfg does that).
Each case has a control that fails if nothing landed.
"""

import contextlib
import importlib
import io
import os
import sqlite3
import sys
import tempfile
import time

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-60s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def fresh():
    home = tempfile.mkdtemp(prefix="surfd-sweep-")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    runs = os.path.join(home, "ftesurf", "data", "runs")    # <game>/ftesurf/data/runs
    os.makedirs(runs)
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"), SURFD_RUNS=runs,
                      SURFD_GAME=home, SURFD_VERIFIER=os.path.join(home, "noengine"))
    for k in ("SURFD_EVIDENCE", "SURFD_KEEP"):     # schema 6: beside runs / under home
        os.environ.pop(k, None)
    for m in ("surfd", "sweep"):
        sys.modules.pop(m, None)
    sweep = importlib.import_module("sweep")    # imports surfd, as cron does
    return sys.modules["surfd"], sweep, runs


def add_replay(conn, runs, map_dir, leaf, track=0, leg=0, make_file=True):
    cur = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player,"
        " name, ticks, tickrate, millis, flags, node, submitted)"
        " VALUES (?, ?, ?, ?, ?, 'ranked', 'normal', 'p', 'n', 662, 100, 6620, 0,"
        " '1', 1)", (map_dir.lower(), map_dir, track, leg, leaf))
    conn.commit()
    if make_file:
        d = os.path.join(runs, map_dir, "main" if leg <= 0 else "stage_%d" % leg)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, leaf), "w").write("FTESURF-REC 9\n")
    return cur.lastrowid


TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "tools")


def make_receipt(evdir, runid, mapname="bhop_eazy", seed=b"\x01" * 32,
                 view=b"FTESURF-VIEW 2\n", tamper=False, age=None):
    """A GENUINELY SIGNED receipt, with the sidecar it commits to.

    Signed here rather than copied from data/, because a fixture copied off this
    disk stops being a test of the format the moment the writer changes and
    nobody re-copies it -- and because a suite that cannot MAKE a valid
    signature cannot make an invalid one either, which is the arm that matters.
    """
    import hashlib
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import ed25519

    d = os.path.join(evdir, mapname)
    os.makedirs(d, exist_ok=True)
    vp = os.path.join(d, runid + ".view")
    with open(vp, "wb") as fh:
        fh.write(view)
    signed = [("server", "127.0.0.1:27696"),
              ("nonce", "d6c6820bca16750c77166d96dcf02787"),
              ("ticks", "-1"),
              ("hid", "- 0 0"),
              ("view", hashlib.sha256(view).hexdigest())]
    first = "FTESURF-RCPT 1"
    msg = (first + "\n" + "".join("%s %s\n" % kv for kv in signed)).encode("utf-8")
    pub = ed25519.publickey(seed)
    sig = ed25519.sign(seed, msg)
    if tamper:
        # One bit of the signed BODY, leaving the signature as it was: the
        # receipt still parses and still names this run, and only the
        # cryptography can tell.
        signed[0] = ("server", "127.0.0.1:27697")
    body = [first, "map " + mapname, "runid " + runid, "owner ^3T^7",
            "svticks -1", "svport 27696",
            "pub " + pub.hex(), "sig " + sig.hex()]
    body += ["signed %s %s" % kv for kv in signed]
    rp = os.path.join(d, runid + ".rcpt")
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body) + "\n")
    if age is not None:
        os.utime(rp, (age, age))
        os.utime(vp, (age, age))
    return rp, pub.hex()


def receipts(conn):
    return {r[0]: (r[1], r[2], r[3]) for r in
            conn.execute("SELECT runid, verdict, pub, angles FROM receipts")}


def case_receipt_valid_and_once():
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE
    _p, pub = make_receipt(surfd.EVIDENCE_DIR, "20260921-000001-0", age=old)
    n, bad = sweep.receipt_step(conn)
    check("a settled receipt is read", (n, bad), (1, 0))
    got = receipts(conn)
    check("stored VALID under its runid", got["20260921-000001-0"][0], "VALID")
    check("the signing key is stored", got["20260921-000001-0"][1], pub)
    check("no recording here, so no angle verdict is invented",
          got["20260921-000001-0"][2], "")
    check("CONTROL: a second pass re-reads nothing", sweep.receipt_step(conn), (0, 0))


def case_receipt_fault():
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000002-0", tamper=True, age=old)
    n, bad = sweep.receipt_step(conn)
    check("a tampered receipt is read and counted bad", (n, bad), (1, 1))
    row = conn.execute("SELECT verdict, reason FROM receipts").fetchone()
    check("stored FAULT", row[0], "FAULT")
    check("with a reason a human can read", "SIGNATURE DOES NOT VERIFY" in row[1], True)


def case_receipt_settle():
    """A RECEIPT IS WRITTEN BEFORE THE UPLOAD IT COMMITS TO ARRIVES.  Reading it
    the instant it appears records "no .view on this host" for a file in
    flight, and the row is INSERT OR REPLACE'd by runid, so that wrong answer
    would then be the one nothing ever revisits."""
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000003-0")      # mtime = now
    check("a receipt younger than the settle window is left alone",
          sweep.receipt_step(conn), (0, 0))
    check("CONTROL: and read once it has settled",
          sweep.receipt_step(conn, now=int(time.time()) + 2 * surfd.EVIDENCE_SETTLE),
          (1, 0))


def case_receipt_key_binding():
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE

    def bound():
        return sorted(tuple(r) for r in
                      conn.execute("SELECT pub, player, runs FROM pubkeys"))

    # run 1: a key nobody has seen, on a board row belonging to 'alice'
    a = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?",
                 ("20260921-000010-0", a))
    conn.commit()
    _p, pub = make_receipt(surfd.EVIDENCE_DIR, "20260921-000010-0", age=old)
    sweep.receipt_step(conn)
    check("trust on first use binds the key to the player", bound(), [(pub, "alice", 1)])

    # run 2: same key, same player
    b = add_replay(conn, runs, "bhop_eazy", "0000663_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?",
                 ("20260921-000011-0", b))
    conn.commit()
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000011-0", age=old)
    sweep.receipt_step(conn)
    check("a second run under the same key counts, it does not duplicate",
          bound(), [(pub, "alice", 2)])

    # run 3: SAME KEY, DIFFERENT PLAYER -- recorded as a second pair, not
    # resolved.  A shared machine does this and so does a borrowed account.
    c = add_replay(conn, runs, "bhop_eazy", "0000664_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET runid = ?, player = 'bob' WHERE id = ?",
                 ("20260921-000012-0", c))
    conn.commit()
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000012-0", age=old)
    sweep.receipt_step(conn)
    check("one key signing for two players is two rows, and no verdict",
          bound(), sorted([(pub, "alice", 2), (pub, "bob", 1)]))

    # run 4: same player, a DIFFERENT key -- a reinstall looks like this.
    d = add_replay(conn, runs, "bhop_eazy", "0000665_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?",
                 ("20260921-000013-0", d))
    conn.commit()
    _p, pub2 = make_receipt(surfd.EVIDENCE_DIR, "20260921-000013-0",
                            seed=b"\x02" * 32, age=old)
    sweep.receipt_step(conn)
    check("one player with two keys is two rows too",
          sorted(r for r in bound() if r[1] == "alice"),
          sorted([(pub, "alice", 2), (pub2, "alice", 1)]))


def case_receipt_unbound_is_not_a_fault():
    """A receipt for a run no board row names binds nothing and is still read.
    Most receipts on a lobby are exactly this: an abandoned run."""
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000020-0", age=old)
    check("read", sweep.receipt_step(conn), (1, 0))
    check("nothing bound", conn.execute("SELECT COUNT(*) FROM pubkeys").fetchone()[0], 0)


def case_receipt_reread():
    """--reread-receipts forgets the VERDICTS and keeps the KEY SIGHTINGS.

    The distinction is the whole reason the flag is not a DELETE FROM both
    tables: re-reading the same files would count every run's key a second
    time, so a player's `runs` would double every time the checker changed."""
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE
    rid = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?",
                 ("20260921-000040-0", rid))
    conn.commit()
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000040-0", age=old)
    sweep.receipt_step(conn)
    check("read once", conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 1)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        sweep.main(["--reread-receipts", "--limit", "0"])
    check("the flag says how many it forgot", "forgot 1 receipt" in out.getvalue(), True)
    conn2 = surfd.connect()
    check("...and read them again in the same pass",
          conn2.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 1)
    check("CONTROL: the key sighting was NOT counted twice",
          conn2.execute("SELECT runs FROM pubkeys").fetchone()[0], 1)


def angle_pair(runid, rot=0.0, still=True):
    """A .rec and the sidecar that goes with it, from reccheck's own fixtures.

    BUILT BY tools/test_reccheck.py AND NOT HERE.  That file assembles the .rec
    grammar from the block comment over SV_RecOpen, and a second writer in this
    tree is a second thing to keep in step with the recorder -- the same reason
    read_receipt imports rcptcheck instead of re-parsing a receipt.

    `still` is the default because it is what the fleet records: every run on a
    lobby is driven with the camera where the player left it, and a still camera
    is exactly the case the sweep rule cannot judge.
    """
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import test_reccheck as fx
    lines = fx.build(packets=400, sweep=0.0 if still else 128)
    lines = [("runid " + runid) if l.startswith("runid ") else l for l in lines]
    return "\n".join(lines) + "\n", "\n".join(fx.view_for(lines, rot=rot)) + "\n"


def with_rec(surfd, sweep, runid, rec, mapname="bhop_eazy"):
    """Put the recording where rcptcheck looks for it, and point it there."""
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import rcptcheck
    game = os.path.join(os.environ["SURFD_HOME"], "game")
    d = os.path.join(game, "data", "evidence", mapname)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, runid + ".rec"), "w", encoding="utf-8") as fh:
        fh.write(rec)
    rcptcheck.GAME = game
    return rcptcheck


def case_receipt_angles_reach_the_database():
    """THE COLUMN THE REVIEW PAGE PRINTS, WITH A RECORDING TO JOIN TO.

    Every other receipt arm here has nothing on disk to check the sidecar
    against, so `angles` comes back "" and the whole cross-check is untested
    from this side.  Patch 421 is what makes the answer interesting on a lobby's
    files: before it, a still camera meant the sweep rule had nothing to scale
    and the verdict was BLIND whatever the sidecar said.
    """
    surfd, sweep, runs = fresh()
    sweep.TOOLS = TOOLS
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE

    rec, view = angle_pair("20260921-000070-0")   # view_for's map is bhop_eazy
    rc = with_rec(surfd, sweep, "20260921-000070-0", rec)
    try:
        make_receipt(surfd.EVIDENCE_DIR, "20260921-000070-0",
                     view=view.encode("utf-8"), age=old)
        n, bad = sweep.receipt_step(conn)
        check("the receipt is read", (n, bad), (1, 0))
        got = receipts(conn)["20260921-000070-0"]
        check("a still camera with its own sidecar reads OK, not BLIND",
              (got[0], got[2]), ("VALID", "OK"))

        # AND THE SAME PAIR WITH THE SIDECAR TURNED HALF A DEGREE.  Separate
        # runid, because a receipt is read once by design and re-reading it is
        # a different arm.
        rec2, view2 = angle_pair("20260921-000071-0", rot=0.5)
        with_rec(surfd, sweep, "20260921-000071-0", rec2)
        make_receipt(surfd.EVIDENCE_DIR, "20260921-000071-0",
                     view=view2.encode("utf-8"), age=old)
        n, bad = sweep.receipt_step(conn)
        check("a 0.5 deg rotation is a fault in the evidence", (n, bad), (1, 1))
        got = receipts(conn)["20260921-000071-0"]
        check("...and the database says so in both columns",
              (got[0], got[2]), ("FAULT", "FAULT"))
        # AND A SIDECAR THAT CANNOT BE READ AT ALL IS NOT A PASS.  A .view with
        # no usable frames used to leave the cross-check unrun, the verdict
        # empty and the receipt VALID -- the review page drew no angles pill,
        # which reads as "nothing to say" rather than "this file is broken".
        rec3, _v3 = angle_pair("20260921-000072-0")
        with_rec(surfd, sweep, "20260921-000072-0", rec3)
        make_receipt(surfd.EVIDENCE_DIR, "20260921-000072-0",
                     view=b"\n".join([b"FTESURF-VIEW 2", b"map bhop_eazy",
                                      b"hid 1", b"begin", b""]),
                     age=old)
        n, bad = sweep.receipt_step(conn)
        check("an unreadable sidecar is a fault in the evidence", (n, bad), (1, 1))
        got = receipts(conn)["20260921-000072-0"]
        check("...and the verdict is not left empty",
              (got[0], got[2]), ("FAULT", "FAULT"))
    finally:
        rc.GAME = os.path.join(os.path.dirname(TOOLS), "ftesurf")


def case_receipt_step_never_takes_the_sweep_down():
    """THE ARM THE WHOLE ADDITION RESTS ON.  This step imports three files that
    live outside surfd; on a host where they are not deployed the verification
    that has run every five minutes since Patch 349 must carry on unchanged."""
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    old = int(time.time()) - 2 * surfd.EVIDENCE_SETTLE
    make_receipt(surfd.EVIDENCE_DIR, "20260921-000030-0", age=old)
    # AND THE FIRST CUT OF THIS ARM COULD NOT FAIL.  Pointing sweep.TOOLS at an
    # empty directory changes nothing once an earlier case in the same process
    # has imported rcptcheck: the import is served from sys.modules and the step
    # reported (1, 0) -- a pass that measured the opposite of what it claimed.
    # The deployment being modelled is an interpreter that has never seen these
    # modules, so the arm has to make one.
    sweep.TOOLS = os.path.join(os.environ["SURFD_HOME"], "no-tools-here")
    saved = {m: sys.modules.pop(m) for m in ("rcptcheck", "reccheck", "ed25519")
             if m in sys.modules}
    savedpath = list(sys.path)
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) != os.path.abspath(TOOLS)]
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            got = sweep.receipt_step(conn)
    finally:
        sys.path[:] = savedpath
        sys.modules.update(saved)
    check("no tools: the step reports nothing read", got, (0, 0))
    check("...and says why, on stderr", "receipt step failed" in err.getvalue(), True)
    rid = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    sweep.sweep(conn, 20, runner=lambda m, p:
                ["VERIFY %s PASS ticks 662 rows 634" % q for q in p], now=99)
    check("CONTROL: the verdict sweep is untouched", latest(conn, rid)[0], "PASS")


def latest(conn, rid):
    return conn.execute("SELECT verdict, reason, ticks FROM verdicts WHERE replay_id = ?"
                        " ORDER BY id DESC LIMIT 1", (rid,)).fetchone()


def case_parse():
    _, sweep, _ = fresh()
    got = sweep.parse([
        "junk",
        "VERIFY data/runs/a/main/x.rec PASS ticks 662 rows 634",
        "VERIFY data/runs/a/main/y.rec HOLD ticks: the zones say 662, the file says 663",
        "VERIFY data/runs/a/main/z.rec REFUSE a save-state resume or retry",
        "  pm_recsim  data/runs/a/main/x.rec",
    ])
    check("parse: PASS carries its ticks", got["data/runs/a/main/x.rec"], ("PASS", "ticks 662 rows 634", 662))
    check("parse: HOLD keeps its reason, no ticks", got["data/runs/a/main/y.rec"][0::2], ("HOLD", -1))
    check("parse: REFUSE", got["data/runs/a/main/z.rec"][0], "REFUSE")
    check("parse: nothing else becomes a verdict", len(got), 3)


def case_pass_and_group():
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    sweep.ensure_schema(conn)
    a = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    b = add_replay(conn, runs, "Bhop_Mukiology", "0000500_p-2c8f36b6_pb.rec")
    calls = []

    def runner(map_dir, paths):
        calls.append((map_dir, paths))
        return ["VERIFY %s PASS ticks 662 rows 634" % p for p in paths]

    counts = sweep.sweep(conn, 20, runner=runner, now=1234)
    check("one verifier process per map", sorted(m for m, _ in calls), ["Bhop_Mukiology", "bhop_eazy"])
    check("path is game-relative and keeps the disk spelling",
          dict(calls)["Bhop_Mukiology"], ["data/runs/Bhop_Mukiology/main/0000500_p-2c8f36b6_pb.rec"])
    check("PASS stored with its ticks", tuple(latest(conn, a)), ("PASS", "ticks 662 rows 634", 662))
    row = conn.execute("SELECT checked, seen FROM replays WHERE id = ?", (b,)).fetchone()
    check("a terminal verdict sets checked and seen", (row[0], row[1]), (1, 1234))
    check("counts", counts, {"PASS": 2})
    check("CONTROL: a second sweep finds nothing pending", sweep.sweep(conn, 20, runner=runner), {})


def case_missing_and_bad_names():
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    gone = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec", make_file=False)
    bad = add_replay(conn, runs, "bhop_eazy", "../../../etc/passwd", make_file=False)
    calls = []
    sweep.sweep(conn, 20, runner=lambda m, p: calls.append(m) or [])
    check("a missing file is REFUSED, not run", latest(conn, gone)[0], "REFUSE")
    check("an unusable leaf is REFUSED, not run", latest(conn, bad)[0], "REFUSE")
    check("CONTROL: the verifier was never started", calls, [])


def case_error_retry_cap():
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    rid = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    for _ in range(sweep.MAX_ERRORS):
        sweep.sweep(conn, 20, runner=lambda m, p: ["no verdict here"])
    n = conn.execute("SELECT COUNT(*) FROM verdicts WHERE replay_id = ? AND verdict = 'ERROR'",
                     (rid,)).fetchone()[0]
    check("no VERIFY line is an ERROR, retried", n, sweep.MAX_ERRORS)
    check("an ERROR leaves checked 0", conn.execute("SELECT checked FROM replays WHERE id = ?",
                                                    (rid,)).fetchone()[0], 0)
    check("after MAX_ERRORS it stops being pending", sweep.pending(conn, 20), [])


def case_schema_owned_by_surfd():
    surfd, sweep, _ = fresh()
    conn = surfd.connect()
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    check("verdicts exists after `import sweep` (surfd's migrate)", "verdicts" in names, True)
    check("sweep keeps no copy of the DDL", hasattr(sweep, "SCHEMA"), False)
    sweep.ensure_schema(conn)
    check("ensure_schema is still a harmless no-op", "verdicts_replay" in
          {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}, True)


def case_error_window():
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    rid = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    fail = lambda m, p: ["no verdict here"]
    for t in (1000, 1001, 1002):
        sweep.sweep(conn, 20, runner=fail, now=t)
    ids = lambda: [r["id"] for r in sweep.pending(conn, 20)]
    check("3 ERRORs: not pending", ids(), [])
    conn.execute("UPDATE replays SET recheck_at = 2000 WHERE id = ?", (rid,))
    conn.commit()
    check("a re-check bump makes it pending again", ids(), [rid])
    for t in (2000, 2001, 2002):
        sweep.sweep(conn, 20, runner=fail, now=t)
    check("control: 3 ERRORs after the re-check spend it again", ids(), [])
    conn.execute("UPDATE replays SET submitted = 3000, checked = 0 WHERE id = ?", (rid,))
    conn.commit()
    check("an exact-tie resubmission reopens it too", ids(), [rid])
    other = add_replay(conn, runs, "bhop_eazy", "0000663_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET recheck_at = 4000 WHERE id = ?", (other,))
    conn.commit()
    check("re-checks are verified first", ids(), [other, rid])


def mid_run(event):
    """Sweep one replay with a board row on real time; `event` (tie, recheck or
    None) lands through a second connection while the verifier runs, as
    submit_run or the admin's re-check would.  -> (surfd, conn, rid, sweep)."""
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    rid = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
        " tickrate, millis, flags, node, runid, submitted, replay_id)"
        " VALUES ('bhop_eazy', 0, 0, 'ranked', 'normal', 'p', 'n', 662, 100,"
        " 6620, 0, '1', '', 1, ?)", (rid,))
    conn.commit()

    def runner(map_dir, paths):
        other = surfd.connect()
        with other:
            if event == "tie":      # submit_run's upsert of the same row
                other.execute("UPDATE replays SET submitted = ?, seen = -1,"
                              " checked = 0 WHERE id = ?", (int(time.time()), rid))
            elif event == "recheck":
                other.execute("UPDATE replays SET checked = 0, recheck_at = ?"
                              " WHERE id = ?", (int(time.time()), rid))
        other.close()
        return ["VERIFY %s PASS ticks 662 rows 634" % p for p in paths]

    sweep.sweep(conn, 20, runner=runner)
    return surfd, conn, rid, sweep


def verdict_state(surfd, conn, rid, sweep):
    at = conn.execute("SELECT at FROM verdicts WHERE replay_id = ?", (rid,)).fetchone()[0]
    sub, checked = conn.execute("SELECT submitted, checked FROM replays WHERE id = ?",
                                (rid,)).fetchone()
    ver = conn.execute("SELECT " + surfd.VER_SQL + " FROM runs r WHERE r.replay_id = ?",
                       (rid,)).fetchone()[0]
    return {"current": at >= sub, "checked": checked,
            "pending": rid in [r["id"] for r in sweep.pending(conn, 20)], "ver": ver}


def case_mid_run_tie():
    got = verdict_state(*mid_run("tie"))
    check("a tie resubmitted mid-run: its PASS is not current, still pending, ver 0",
          got, {"current": False, "checked": 0, "pending": True, "ver": 0})
    got = verdict_state(*mid_run(None))
    check("control: no mid-run event -> current, checked, ver 1",
          got, {"current": True, "checked": 1, "pending": False, "ver": 1})


def case_mid_run_recheck():
    # Same bytes, so the PASS stands (ver 1); the re-check still gets its own run.
    got = verdict_state(*mid_run("recheck"))
    check("a re-check queued mid-run stays pending (the PASS still counts)",
          got, {"current": True, "checked": 0, "pending": True, "ver": 1})


def case_command_line():
    surfd, sweep, runs = fresh()
    seen = {}

    class R:
        stdout = "VERIFY data/runs/m/main/x.rec PASS ticks 1 rows 1\n"
        stderr = ""

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return R()

    real = sweep.subprocess.run
    sweep.subprocess.run = fake_run
    try:
        out = sweep.run_verifier("surf_x", ["data/runs/surf_x/main/a.rec", "data/runs/surf_x/main/b.rec"])
    finally:
        sweep.subprocess.run = real
    cmd = seen["cmd"]
    check("idle priority", cmd[:6], ["nice", "-n", "19", "ionice", "-c", "3"])
    check("the map once, then every file", [cmd[i + 1] for i, a in enumerate(cmd) if a in ("+map", "+pm_verify")],
          ["surf_x", "data/runs/surf_x/main/a.rec", "data/runs/surf_x/main/b.rec"])
    check("records nothing, advertises nothing",
          all(x in " ".join(cmd) for x in ("rec_enable 0", "sv_public 0")), True)
    check("ends with quit", cmd[-1], "+quit")
    check("first in line for the OOM killer", seen["kw"].get("preexec_fn") is sweep._oom_first, True)
    check("stdout comes back as lines", out[0].startswith("VERIFY"), True)


EVR = "20260918-142825-0-p27510"


def case_evidence_not_pending():
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    ev = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player,"
        " name, ticks, tickrate, millis, flags, node, submitted, checked, runid, kind)"
        " VALUES ('bhop_eazy', 'bhop_eazy', 0, 0, ?, '', '', 'p', 'n', 662, 100,"
        " 6620, 0, 'p27510', 1, 0, ?, 'evidence')", (EVR + ".rec", EVR)).lastrowid
    conn.commit()
    run = add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    check("an evidence row at checked 0 is not pending; the run is",
          [r["id"] for r in sweep.pending(conn, 20)], [run])
    calls = []

    def runner(map_dir, paths):
        calls.append(paths)
        return ["VERIFY %s PASS ticks 662 rows 1" % p for p in paths]

    sweep.sweep(conn, 20, runner=runner)
    check("...and the sweep verifies only the run, recording nothing for it",
          (calls, latest(conn, ev)),
          ([["data/runs/bhop_eazy/main/0000662_p-2c8f36b6_run.rec"]], None))


def case_main_evidence():
    surfd, sweep, runs = fresh()
    conn = surfd.connect()
    conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks,"
        " tickrate, millis, flags, node, runid, submitted, replay_id)"
        " VALUES ('surf_aser', 0, 2, 'ranked', 'clean', 'p', 'n', 454, 66.666667,"
        " 6810, 0, 'p27510', ?, 1, 0)", (EVR,))
    conn.commit()
    d = os.path.join(os.path.dirname(runs), "evidence", "surf_aser")
    os.makedirs(d)
    path = os.path.join(d, EVR + ".rec")
    with open(path, "w", newline="\n") as fh:
        fh.write("FTESURF-REC 9\nmap surf_aser\ntrack 0\nleg 0\ntickrate 0.015\n"
                 "runid %s\nflags 0\nbegin\n0.0000 0 0 0 0 0 0 0 0 1\n"
                 "abandon 8262\nend 8262 8519 256 0 8262 4 1 0 1 0\n" % EVR)
    os.utime(path, (1, 1))

    def cron(*argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = sweep.main(list(argv))
        return rc, out.getvalue()

    rc, text = cron("--dry-run")
    check("main --dry-run lists the evidence it would index",
          (rc, "'files': ['surf_aser/%s.rec']" % EVR in text), (0, True))
    n = lambda: conn.execute("SELECT COUNT(*) FROM replays WHERE kind = 'evidence'").fetchone()[0]
    check("...and writes nothing", n(), 0)
    rc, text = cron()
    check("main: the cron line reports what it indexed",
          (rc, text.rstrip().endswith("nothing to verify evidence +1 -0"), n()), (0, True, 1))
    check("control: a second run adds nothing and says nothing of it",
          "evidence" in cron()[1], False)
    conn.execute("DELETE FROM runs")
    conn.commit()
    check("...and the stage row gone, the next run drops it",
          (cron()[1].rstrip().endswith("evidence +0 -1"), n()), (True, 0))


def case_quiet_import():
    # Must run first: surfd's logger outlives re-imports within this process.
    surfd, _, _ = fresh()
    check("CONTROL: surfd's log file is under this test's home",
          surfd.LOG_PATH, os.path.join(os.environ["SURFD_HOME"], "logs", "surfd.log"))
    body = open(surfd.LOG_PATH).read() if os.path.exists(surfd.LOG_PATH) else ""
    check("importing via sweep writes no 'surfd ready' to surfd.log", "surfd ready" in body, False)


def main():
    for case in (case_quiet_import, case_parse, case_pass_and_group, case_missing_and_bad_names,
                 case_error_retry_cap, case_schema_owned_by_surfd, case_error_window,
                 case_mid_run_tie, case_mid_run_recheck, case_command_line,
                 case_evidence_not_pending, case_main_evidence,
                 case_receipt_valid_and_once, case_receipt_fault, case_receipt_settle,
                 case_receipt_key_binding, case_receipt_unbound_is_not_a_fault,
                 case_receipt_reread,
                 case_receipt_angles_reach_the_database,
                 case_receipt_step_never_takes_the_sweep_down):
        print("%s:" % case.__name__)
        try:
            case()
        except Exception as exc:                 # a pre-schema-6 surfd lands here
            check("%s ran to the end" % case.__name__,
                  "%s: %s" % (type(exc).__name__, exc), "no exception")
    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
