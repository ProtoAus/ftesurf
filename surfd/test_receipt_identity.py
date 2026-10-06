#!/usr/bin/env python3
"""Delayed receipt rereads must stay bound to the originally stored observation.

Uses test_sweep's throwaway homes and genuinely signed fixtures. No live data.
"""
import contextlib
import io
import os
import sys
import time
from unittest import mock

import test_sweep as suite

check = suite.check


def case_binding():
    for kind in ("key", "signed", "header", "signature"):
        surfd, sweep, runs = suite.fresh()
        sweep.TOOLS = suite.TOOLS
        conn = surfd.connect()
        now = int(time.time())
        old = now - 2 * surfd.EVIDENCE_SETTLE
        rid = "20261006-000150-0"
        healthy = suite._journal_text().encode("utf-8")
        faulty = suite._journal_text(break_pitch=True).encode("utf-8")
        rp, pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy)
        original = open(rp, "rb").read()
        os.remove(rp[:-5] + ".hid")
        replay = suite.add_replay(conn, runs, "bhop_eazy", "0000662_p-2c8f36b6_run.rec")
        conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?", (rid, replay))
        conn.commit()
        check(kind + ": initial observation acts", sweep.receipt_step(conn, now=now), (1, 0))
        row = lambda: tuple(conn.execute("SELECT * FROM receipts WHERE runid = ?", (rid,)).fetchone())
        keys = lambda: [tuple(r) for r in conn.execute("SELECT * FROM pubkeys ORDER BY pub, player")]
        cols = {r[1] for r in conn.execute("PRAGMA table_info(receipts)")}
        check(kind + ": new observations persist a versioned identity",
              bool(conn.execute("SELECT identity FROM receipts").fetchone()[0]) if "identity" in cols else False, True)
        check(kind + ": CONTROL old join really is PENDING",
              conn.execute("SELECT journal FROM receipts").fetchone()[0], "PENDING")
        before, before_keys = row(), keys()
        # Same path, valid replacement signature, matching replacement upload.
        suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=faulty,
                           seed=bytes([2 if kind == "key" else 1] * 32))
        if kind in ("header", "signature"):
            with open(rp, "wb") as fh:
                fh.write(original.replace(b"svticks -1", b"svticks 662") if kind == "header"
                         else original.replace(b"sig ", b"sig 0", 1))
            with open(rp[:-5] + ".hid", "wb") as fh:
                fh.write(healthy)
            os.utime(rp, (old, old))
        import rcptcheck as rc
        replacement = rc.read(rp)
        check(kind + ": replacement signature control acts", bool(replacement.ok), kind != "signature")
        if kind in ("key", "signed"):
            rc.join_uploaded(replacement, {})
            rc.join_journal(replacement)
            check(kind + ": replacement journal really faults", replacement.journal, "FAULT")
        err = io.StringIO()
        with mock.patch.object(rc, "join_uploaded", wraps=rc.join_uploaded) as joined, contextlib.redirect_stderr(err):
            got = sweep.receipt_step(conn, now=now + 60)
        check(kind + ": replacement is deferred, not attributed", got, (0, 0))
        check(kind + ": guard acts BEFORE joins", joined.call_count, 0)
        check(kind + ": stored observation and key sightings unchanged", (row(), keys()), (before, before_keys))
        check(kind + ": operator sees deferral", "receipt identity changed" in err.getvalue(), True)
        sweep.mark_receipts_stale(conn)
        stale_before = row()
        with contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, now=now + surfd.JOURNAL_WAIT + 60)
        check(kind + ": explicit reread cannot waive binding or reap drift", (got, row(), keys()),
              ((0, 0), stale_before, before_keys))
        with open(rp, "wb") as fh:
            fh.write(original)
        os.utime(rp, (old, old))
        with open(rp[:-5] + ".hid", "wb") as fh:
            fh.write(healthy)
        with mock.patch.object(rc, "join_uploaded", wraps=rc.join_uploaded) as joined:
            got = sweep.receipt_step(conn, now=now + surfd.JOURNAL_WAIT + 120)
        check(kind + ": restored receipt really joins", (got, joined.call_count), ((1, 0), 1))
        # A successful explicit reread intentionally advances key last_at.
        stable_keys = lambda items: [r[:3] + r[4:] for r in items]
        check(kind + ": restoration completes without key transfer/recount",
              (tuple(conn.execute("SELECT pub, journal, stale FROM receipts").fetchone()), stable_keys(keys())),
              ((pub, "OK", 0), stable_keys(before_keys)))


def case_legacy():
    surfd, sweep, _runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - 2 * surfd.EVIDENCE_SETTLE
    rid = "20261006-000151-0"
    healthy = suite._journal_text().encode("utf-8")
    rp, pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy)
    original = open(rp, "rb").read()
    os.remove(rp[:-5] + ".hid")
    sweep.receipt_step(conn, now=now)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(receipts)")}
    check("legacy: migration has explicit unknown identity", "identity" in cols, True)
    if "identity" in cols:
        conn.execute("UPDATE receipts SET identity = ''")
        conn.commit()
    row = lambda: tuple(conn.execute("SELECT * FROM receipts").fetchone())
    before = row()
    surfd.receipts_v8(conn)
    surfd.receipts_v8(conn)
    check("legacy: startup repair neither backfills nor marks historical rows", row(), before)
    with open(rp[:-5] + ".hid", "wb") as fh:
        fh.write(healthy)
    with contextlib.redirect_stderr(io.StringIO()):
        got = sweep.receipt_step(conn, now=now + surfd.JOURNAL_WAIT + 60)
    check("legacy: automatic read/timeout cannot reinterpret unknown binding", (got, row()), ((0, 0), before))
    conn.execute("UPDATE receipts SET signed_at = 0")
    conn.commit()
    surfd.receipts_v8(conn)
    migrated = row()
    check("legacy: pre-8 migration actually marks the old signature stale",
          conn.execute("SELECT stale FROM receipts").fetchone()[0], 1)
    with contextlib.redirect_stderr(io.StringIO()):
        got = sweep.receipt_step(conn, now=now + 60)
    check("legacy: migration mark is not explicit baseline permission", (got, row()), ((0, 0), migrated))
    os.remove(rp)
    with contextlib.redirect_stderr(io.StringIO()):
        got = sweep.receipt_step(conn, now=now + surfd.JOURNAL_WAIT + 120)
    check("legacy: missing receipt timeout cannot backfill an unknown join", (got, row()), ((0, 0), migrated))
    sweep.mark_receipts_stale(conn)
    before = row()
    suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy, seed=bytes([2] * 32))
    with contextlib.redirect_stderr(io.StringIO()):
        got = sweep.receipt_step(conn, now=now + 60)
    check("legacy: explicit baseline cannot transfer known public key", (got, row()), ((0, 0), before))
    with open(rp, "wb") as fh:
        fh.write(original)
    os.utime(rp, (old, old))
    check("legacy: explicit same-key reread ACTS", sweep.receipt_step(conn, now=now + 120), (1, 0))
    check("legacy: explicit reread establishes a current baseline",
          tuple(conn.execute("SELECT pub, journal, stale, identity != '' FROM receipts").fetchone())
          if "identity" in cols else None, (pub, "OK", 0, 1))


def case_budget():
    surfd, sweep, _runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - 2 * surfd.EVIDENCE_SETTLE
    healthy = suite._journal_text().encode("utf-8")
    paths = []
    for rid in ("20261006-000152-0", "20261006-000153-0"):
        rp, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy)
        paths.append(rp)
        os.remove(rp[:-5] + ".hid")
    sweep.receipt_step(conn, now=now)
    suite.make_receipt(surfd.EVIDENCE_DIR, "20261006-000152-0", age=old, hid=healthy, seed=bytes([2] * 32))
    with open(paths[1][:-5] + ".hid", "wb") as fh:
        fh.write(healthy)
    import rcptcheck as rc
    for i in range(2):
        with mock.patch.object(rc, "read", wraps=rc.read) as reads, contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, limit=1, now=now + 60 * (i + 1))
        check("budget: pass %d attempts exactly one receipt" % i, reads.call_count, 1)
        check("budget: refusal cannot monopolize recovery pass %d" % i, got, (0, 0) if i == 0 else (1, 0))
    check("budget: healthy queued receipt leaves PENDING",
          conn.execute("SELECT journal FROM receipts WHERE runid = '20261006-000153-0'").fetchone()[0], "OK")


def case_formatting_control():
    surfd, sweep, _runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - 2 * surfd.EVIDENCE_SETTLE
    rid = "20261006-000154-0"
    healthy = suite._journal_text().encode("utf-8")
    rp, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy)
    os.remove(rp[:-5] + ".hid")
    check("format: initial read ACTS", sweep.receipt_step(conn, now=now), (1, 0))
    before = tuple(conn.execute("SELECT pub, verdict, sig, signed_at, at, identity FROM receipts").fetchone())
    data = open(rp, "rb").read()
    # Values and ordered signed message are identical despite blank lines,
    # CRLF and head ordering. Signed values/version bytes are not trimmed.
    lines = data.decode("utf-8").splitlines()
    lines[1:8] = reversed(lines[1:8])
    with open(rp, "wb") as fh:
        fh.write(("\r\n\r\n".join(lines) + "\r\n").encode("utf-8"))
    os.utime(rp, (old, old))
    with open(rp[:-5] + ".hid", "wb") as fh:
        fh.write(healthy)
    import rcptcheck as rc
    with mock.patch.object(rc, "join_uploaded", wraps=rc.join_uploaded) as joined:
        got = sweep.receipt_step(conn, now=now + 60)
    check("format: automatic delayed control really joins", (got, joined.call_count), ((1, 0), 1))
    check("format: automatic control moves ONLY the journal",
          (tuple(conn.execute("SELECT pub, verdict, sig, signed_at, at, identity FROM receipts").fetchone()),
           conn.execute("SELECT journal FROM receipts").fetchone()[0]), (before, "OK"))
    os.utime(rp, (old + 10, old + 10))
    sweep.mark_receipts_stale(conn)
    check("format: explicit reread of retimed identical receipt ACTS", sweep.receipt_step(conn, now=now + 120), (1, 0))
    check("format: reread preserves original signing-time observation",
          conn.execute("SELECT signed_at FROM receipts").fetchone()[0], before[3])


def case_partial_observation():
    import builtins
    surfd, sweep, _runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - 2 * surfd.EVIDENCE_SETTLE
    rid = "20261006-000155-0"
    healthy = suite._journal_text().encode("utf-8")
    rp, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy)
    rc = suite.with_rec(surfd, sweep, rid, "FTESURF-REC 9\nrunid %s\nnonce %s\nbegin\n" % (rid, "0" * 32))
    real_open = builtins.open

    def eio(path, *args, **kwargs):
        if path == rp[:-5] + ".hid":
            raise OSError(5, "Input/output error")
        return real_open(path, *args, **kwargs)

    try:
        with mock.patch("builtins.open", side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, now=now)
        check("partial: independent measured fault ACTS", got, (1, 1))
        row = lambda: tuple(conn.execute("SELECT * FROM receipts").fetchone())
        before = row()
        check("partial: captured receipt is bound despite deferred sibling",
              tuple(conn.execute("SELECT verdict, journal, identity != '' FROM receipts").fetchone()), ("FAULT", "PENDING", 1))
        suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=healthy, seed=bytes([2] * 32))
        with mock.patch.object(rc, "join_uploaded", wraps=rc.join_uploaded) as joined, contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, now=now + 60)
        check("partial: replacement cannot reinterpret partial history", (got, row(), joined.call_count), ((0, 0), before, 0))
    finally:
        rc.GAME = os.path.join(os.path.dirname(suite.TOOLS), "ftesurf")


def main():
    for case in (case_binding, case_legacy, case_budget, case_formatting_control, case_partial_observation):
        print(case.__name__ + ":")
        try:
            case()
        except Exception as exc:
            check(case.__name__ + " ran to completion", str(exc), "no exception")
    print("\n%d failed" % len(suite.FAILED))
    return 1 if suite.FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
