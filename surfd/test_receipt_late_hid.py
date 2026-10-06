#!/usr/bin/env python3
"""Post-timeout HID scheduling; temporary signed fixtures, never live evidence.

Predictions: an ABSENT bound journal is checked when its final sibling arrives,
not on silence/.part. Identity drift and I/O defer before attribution. Automatic
joins preserve historical receipt/angle faults and key sightings, are budgeted
and fair, and never reconstruct an unknown legacy receipt. Reader controls
must actually judge each fixture. Late view/rec scheduling is a separate task.
"""
import builtins
import contextlib
import io
import os
import sys
import time
from unittest import mock

import test_sweep as suite

check = suite.check


def setup(rid, hid=None, tamper=False, expired=False):
    surfd, sweep, runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - (2 * surfd.EVIDENCE_SETTLE if expired else surfd.JOURNAL_WAIT + 60)
    rp, pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=hid, tamper=tamper)
    if hid is not None:
        os.remove(rp[:-5] + ".hid")
    replay = suite.add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
    conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?", (rid, replay))
    conn.commit()
    check(rid + ": first receipt observation acts", sweep.receipt_step(conn, now=now),
          (1, 1 if tamper else 0))
    if expired:
        check("expiry: initially PENDING", row(conn)["journal"], "PENDING")
        now = old + surfd.JOURNAL_WAIT + 1
        check("expiry: timeout actually reads", sweep.receipt_step(conn, now=now), (1, 0))
    check(rid + ": journal starts ABSENT", row(conn)["journal"], "ABSENT")
    return surfd, sweep, conn, rp, pub, now, old


def row(conn):
    return dict(conn.execute("SELECT * FROM receipts").fetchone())


def keys(conn):
    return [tuple(r) for r in conn.execute("SELECT * FROM pubkeys ORDER BY pub, player")]


def put(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


def case_outcomes():
    healthy = suite._journal_text().encode("utf-8")
    faulty = suite._journal_text(break_pitch=True).encode("utf-8")
    blind = suite._journal_text(teleport=True).encode("utf-8")
    for i, (kind, signed, arrived, journal, bad) in enumerate((
            ("honest", healthy, healthy, "OK", 0),
            ("expired", healthy, healthy, "OK", 0),
            ("content", faulty, faulty, "FAULT", 0),
            ("blind", blind, blind, "BLIND", 0),
            ("digest", healthy, faulty, "FAULT", 1),
            ("unsigned", None, healthy, "FAULT", 1),
            ("prior-fault", healthy, healthy, "OK", 0))):
        rid = "20261006-0002%02d-0" % i
        surfd, sweep, conn, rp, pub, now, old = setup(
            rid, signed, tamper=kind == "prior-fault", expired=kind == "expired")
        import rcptcheck as rc
        before, before_keys = row(conn), keys(conn)
        with mock.patch.object(rc, "read", wraps=rc.read) as reads:
            check(kind + ": silence does not reread", sweep.receipt_step(conn, now=now + 60), (0, 0))
        check(kind + ": silence control read count", reads.call_count, 0)
        os.mkdir(rp[:-5] + ".hid")
        check(kind + ": a directory is not a journal upload", sweep.receipt_step(conn, now=now + 90), (0, 0))
        os.rmdir(rp[:-5] + ".hid")
        put(rp[:-5] + ".hid.part", arrived)
        check(kind + ": incomplete upload does not act", sweep.receipt_step(conn, now=now + 120), (0, 0))
        os.replace(rp[:-5] + ".hid.part", rp[:-5] + ".hid")
        # Independent reader control proves this file is judged, not just listed.
        control = rc.read(rp)
        rc.join_uploaded(control, {})
        rc.join_journal(control)
        check(kind + ": CONTROL journal verdict", control.journal, journal)
        check(kind + ": CONTROL sibling digest verdict", bool(control.digest_bad), bool(bad))
        with mock.patch.object(rc, "join_uploaded", wraps=rc.join_uploaded) as uploaded, \
                mock.patch.object(rc, "join_rec", wraps=rc.join_rec) as rec, \
                mock.patch.object(rc, "join_angles", wraps=rc.join_angles) as angles:
            got = sweep.receipt_step(conn, now=now + 180)
        check(kind + ": late arrival actually joins", (got, uploaded.call_count), ((1, bad), 1))
        check(kind + ": no historical rec/angle reinterpretation", (rec.call_count, angles.call_count), (0, 0))
        after = row(conn)
        expected = dict(before, journal=journal, journal_reason=control.journal_detail[:300])
        if bad:
            expected.update(verdict="FAULT", reason=control.faults[0][:300])
        check(kind + ": only permitted evidence columns move", after, expected)
        check(kind + ": key sightings unchanged", keys(conn), before_keys)
        with mock.patch.object(rc, "read", wraps=rc.read) as reads:
            got = sweep.receipt_step(conn, now=now + 240)
        check(kind + ": completed verdict is not repeatedly checked", (got, reads.call_count), ((0, 0), 0))
        check(kind + ": attempt queue retired", conn.execute(
            "SELECT COUNT(*) FROM sweepmeta WHERE k GLOB 'receipt_retry:*'").fetchone()[0], 0)


def case_pruned_recording():
    rid = "20261006-000210-0"
    healthy = suite._journal_text().encode("utf-8")
    surfd, sweep, conn, rp, _pub, now, _old = setup(rid, healthy)
    rc = suite.with_rec(surfd, sweep, rid,
                        "FTESURF-REC 9\nrunid %s\nnonce %s\nbegin\n" % (rid, "0" * 32))
    try:
        sweep.mark_receipts_stale(conn)
        check("prune: explicit full read ACTS on a nonce fault", sweep.receipt_step(conn, now=now + 60), (1, 1))
        before, before_keys = row(conn), keys(conn)
        check("prune: recorded fault really names the nonce", "the .rec states" in before["reason"], True)
        for root, _dirs, files in os.walk(os.path.dirname(surfd.RUNS_DIR)):
            for leaf in files:
                if leaf.endswith(".rec"):
                    os.remove(os.path.join(root, leaf))
        put(rp[:-5] + ".hid", healthy)
        with mock.patch.object(rc, "join_rec", wraps=rc.join_rec) as rec:
            got = sweep.receipt_step(conn, now=now + 120)
        check("prune: late HID acts without rejoining removed recording", (got, rec.call_count), ((1, 0), 0))
        after = row(conn)
        check("prune: primary historical fault preserved", {k: v for k, v in after.items()
              if k not in ("journal", "journal_reason")}, {k: v for k, v in before.items()
              if k not in ("journal", "journal_reason")})
        check("prune: journal now OK, no new key sighting", (after["journal"], keys(conn)), ("OK", before_keys))
    finally:
        rc.GAME = os.path.join(os.path.dirname(suite.TOOLS), "ftesurf")


def case_pruned_angles():
    surfd, sweep, _runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - surfd.JOURNAL_WAIT - 60
    rid = "20261006-000216-0"
    healthy = suite._journal_text().encode("utf-8")
    rec, view = suite.angle_pair(rid, rot=0.5)
    rc = suite.with_rec(surfd, sweep, rid, rec)
    try:
        rp, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old,
                                     hid=healthy, view=view.encode("utf-8"))
        os.remove(rp[:-5] + ".hid")
        check("angles: first full read ACTS on rotation", sweep.receipt_step(conn, now=now), (1, 1))
        before = row(conn)
        check("angles: stored primary and angle fault ACT", (before["verdict"], before["angles"], before["journal"]),
              ("FAULT", "FAULT", "ABSENT"))
        os.remove(os.path.join(rc.GAME, "data", "evidence", "bhop_eazy", rid + ".rec"))
        os.remove(rp[:-5] + ".view")
        put(rp[:-5] + ".hid", healthy)
        check("angles: late HID still ACTS after pair pruning", sweep.receipt_step(conn, now=now + 60), (1, 0))
        after = row(conn)
        check("angles: historical angle fault cannot be erased", {k: v for k, v in after.items()
              if k not in ("journal", "journal_reason")}, {k: v for k, v in before.items()
              if k not in ("journal", "journal_reason")})
        check("angles: arrived journal now OK", after["journal"], "OK")
    finally:
        rc.GAME = os.path.join(os.path.dirname(suite.TOOLS), "ftesurf")


def case_identity():
    healthy = suite._journal_text().encode("utf-8")
    faulty = suite._journal_text(break_pitch=True).encode("utf-8")
    for kind in ("key", "signed", "header"):
        rid = "20261006-000211-0"
        surfd, sweep, conn, rp, _pub, now, old = setup(rid, healthy)
        with open(rp, "rb") as fh:
            original = fh.read()
        before, before_keys = row(conn), keys(conn)
        suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=faulty,
                           seed=bytes([2 if kind == "key" else 1] * 32))
        if kind == "header":
            put(rp, original.replace(b"svticks -1", b"svticks 662"))
            os.utime(rp, (old, old))
        import rcptcheck as rc
        check(kind + ": replacement is genuinely signed", bool(rc.read(rp).ok), True)
        with mock.patch.object(rc, "read", wraps=rc.read) as reads, \
                mock.patch.object(rc, "join_uploaded", wraps=rc.join_uploaded) as joined, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            got = sweep.receipt_step(conn, limit=1, now=now + 60)
        check(kind + ": refusal acts before joins", (got, reads.call_count, joined.call_count), ((0, 0), 1, 0))
        check(kind + ": historical row and key not transferred", (row(conn), keys(conn)), (before, before_keys))
        check(kind + ": refusal is observable", "receipt identity changed" in err.getvalue(), True)
        put(rp, original)
        os.utime(rp, (old, old))
        put(rp[:-5] + ".hid", healthy)
        check(kind + ": original restored control acts", sweep.receipt_step(conn, now=now + 120), (1, 0))
        check(kind + ": recovery retains identity and keys", (row(conn)["identity"], row(conn)["journal"], keys(conn)),
              (before["identity"], "OK", before_keys))


def case_io_fairness():
    healthy = suite._journal_text().encode("utf-8")
    surfd, sweep, conn, rp, _pub, now, old = setup("20261006-000212-0", healthy)
    before, before_keys = row(conn), keys(conn)
    rp2, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, "20261006-000213-0", age=old, hid=healthy)
    os.remove(rp2[:-5] + ".hid")
    check("IO: second absent observation acts", sweep.receipt_step(conn, now=now), (1, 0))
    put(rp[:-5] + ".hid", healthy)
    put(rp2[:-5] + ".hid", healthy)
    real_open = builtins.open

    def eio(path, *args, **kwargs):
        if path == rp[:-5] + ".hid":
            raise OSError(5, "Input/output error")
        return real_open(path, *args, **kwargs)

    import rcptcheck as rc
    for i in range(3):
        with mock.patch("builtins.open", side_effect=eio), \
                mock.patch.object(rc, "read", wraps=rc.read) as reads, \
                contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, limit=1, now=now + 60 * (i + 1))
        check("IO: bounded pass %d actually attempts one" % i, reads.call_count, 1)
        check("IO: healthy queue progresses in pass %d" % i, got, (1, 0) if i == 1 else (0, 0))
    first = dict(conn.execute("SELECT * FROM receipts WHERE runid = '20261006-000212-0'").fetchone())
    check("IO: failed late read leaves history unchanged", (first, keys(conn)), (before, before_keys))
    check("IO: error removal recovery ACTS", sweep.receipt_step(conn, limit=1, now=now + 240), (1, 0))
    check("IO: both journals judged after recovery", [r[0] for r in conn.execute("SELECT journal FROM receipts")], ["OK", "OK"])


def case_legacy_and_loss():
    healthy = suite._journal_text().encode("utf-8")
    rid = "20261006-000214-0"
    surfd, sweep, conn, rp, pub, now, old = setup(rid, healthy)
    conn.execute("UPDATE receipts SET identity = ''")
    conn.commit()
    before = row(conn)
    put(rp[:-5] + ".hid", healthy)
    import rcptcheck as rc
    with mock.patch.object(rc, "read", wraps=rc.read) as reads:
        got = sweep.receipt_step(conn, now=now + 60)
    check("legacy: no automatic baseline or late attribution", (got, reads.call_count, row(conn)), ((0, 0), 0, before))
    sweep.mark_receipts_stale(conn)
    check("legacy: explicit same-pub baseline ACTS", sweep.receipt_step(conn, now=now + 120), (1, 0))
    check("legacy: current baseline and journal established", (row(conn)["pub"], bool(row(conn)["identity"]), row(conn)["journal"]),
          (pub, True, "OK"))
    surfd, sweep, conn, rp, _pub, now, _old = setup("20261006-000215-0", healthy)
    before = row(conn)
    os.remove(rp)
    put(rp[:-5] + ".hid", healthy)
    with mock.patch.object(rc, "read", wraps=rc.read) as reads:
        got = sweep.receipt_step(conn, now=now + 60)
    check("loss: journal alone cannot reconstruct receipt", (got, reads.call_count, row(conn)), ((0, 0), 0, before))


def main():
    for case in (case_outcomes, case_pruned_recording, case_pruned_angles,
                 case_identity, case_io_fairness, case_legacy_and_loss):
        print(case.__name__ + ":")
        try:
            case()
        except Exception as exc:
            check(case.__name__ + " ran to completion", "%s: %s" % (type(exc).__name__, exc), "no exception")
    print("\n%d failed" % len(suite.FAILED))
    return 1 if suite.FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
