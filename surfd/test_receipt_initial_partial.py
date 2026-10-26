#!/usr/bin/env python3
"""Captured initial full-read interruptions finish; no legacy/backfill permission."""
import builtins
import contextlib
import io
import os
import sys
import time
from unittest import mock

import test_sweep as suite
from test_receipt_late_view import row, keys, put, restore_game

check = suite.check


def state(conn):
    return [tuple(r) for r in conn.execute(
        "SELECT k, v FROM sweepmeta WHERE k GLOB 'receipt_partial:*' ORDER BY k")]


def waits(conn):
    return tuple(conn.execute("SELECT COUNT(*) FROM sweepmeta WHERE k GLOB ?",
                              ('receipt_' + kind + '_wait:*',)).fetchone()[0]
                 for kind in ('view', 'rec'))


def setup(rid='20261026-000001-0', fault='signature'):
    s, sw, runs = suite.fresh()
    sw.TOOLS = suite.TOOLS
    conn = s.connect()
    now = int(time.time())
    old = now - s.JOURNAL_WAIT - 2 * s.EVIDENCE_SETTLE
    rec, view = suite.angle_pair(rid)
    clean_rec = rec
    if fault == 'nonce':
        rec = rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
    hid = suite._journal_text().encode()
    rp, _pub = suite.make_receipt(s.EVIDENCE_DIR, rid, age=old, hid=hid,
                                 view=view.encode(), tamper=fault == 'signature')
    rc = suite.with_rec(s, sw, rid, rec)
    replay = suite.add_replay(conn, runs, 'bhop_eazy', rid + '.rec', make_file=False)
    conn.execute("UPDATE replays SET runid=?, player='synthetic-partial' WHERE id=?",
                 (rid, replay))
    conn.commit()
    return s, sw, conn, rp, now, old, rc, clean_rec.encode(), view.encode(), hid


@contextlib.contextmanager
def interrupted(path):
    real_open = builtins.open

    def fail(p, *args, **kwargs):
        if p == path:
            raise OSError(5, 'synthetic sibling I/O failure')
        return real_open(p, *args, **kwargs)

    with mock.patch('builtins.open', side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
        yield


def first_partial(sw, conn, rp, now, failed='hid'):
    with interrupted(rp[:-5] + '.' + failed):
        got = sw.receipt_step(conn, limit=1, now=now)
    check('CONTROL independent fault ACTS despite sibling I/O', got, (1, 1))
    check('CONTROL incomplete contents, no readiness invented',
          (row(conn)['verdict'], row(conn)['angles'], waits(conn)), ('FAULT', 'BLIND', (0, 0)))
    check('captured initial interruption retains known-signature retry',
          (row(conn)['stale'], [v for _k, v in state(conn)]), (2, [2]))
    return row(conn), keys(conn)


def unchanged_history(after, before):
    return {k: after[k] for k in ('verdict', 'reason', 'at', 'sig', 'pub', 'identity', 'signed_at', 'map')} == {
        k: before[k] for k in ('verdict', 'reason', 'at', 'sig', 'pub', 'identity', 'signed_at', 'map')}


def case_completion():
    for failed in ('hid', 'view'):
        s, sw, c, rp, now, _old, rc, _rec, _view, _hid = setup()
        try:
            before, key_before = first_partial(sw, c, rp, now, failed)
            control = sw.read_receipt(rp)
            check('CONTROL uninterrupted actual readers judge contents',
                  (control[0], control[3], control[6], control[9]), ('FAULT', 'OK', 'OK', False))
            with mock.patch.object(rc, 'join_angles', wraps=rc.join_angles) as angles, \
                    mock.patch.object(rc, 'join_journal', wraps=rc.join_journal) as journal:
                got = sw.receipt_step(c, limit=1, now=now + 60)
            check(failed + ': automatic full completion ACTS',
                  (got, angles.call_count, journal.call_count), ((1, 0), 1, 1))
            check(failed + ': fault attribution/time/key observations preserved',
                  (unchanged_history(row(c), before), keys(c)), (True, key_before))
            check(failed + ': newly measured contents and completion stored',
                  (row(c)['angles'], row(c)['journal'], row(c)['stale'], state(c)), ('OK', 'OK', 0, []))
            put(rp[:-5] + '.view', b'completed source replacement')
            with mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                got = sw.receipt_step(c, now=now + 120)
            check('completed replacement is NOT scheduled', (got, reads.call_count), ((0, 0), 0))
        finally:
            restore_game(rc)
            c.close()


def case_repeated_partial():
    s, sw, c, rp, now, _old, rc, clean_rec, view, _hid = setup(fault='nonce')
    try:
        before, key_before = first_partial(sw, c, rp, now)
        recpath = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', os.path.basename(rp)[:-5] + '.rec')
        put(recpath, clean_rec)
        put(rp[:-5] + '.view', b'a different signed-view digest contradiction')
        with interrupted(rp[:-5] + '.hid'):
            control = sw.read_receipt(rp)
            check('CONTROL later partial observes a DIFFERENT independent fault',
                  bool(control and control[9] and control[4] != before['reason']), True)
            with mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                got = sw.receipt_step(c, limit=1, now=now + 60)
        check('repeated interruption bounded and actually read', (got, reads.call_count), ((1, 0), 1))
        check('repeated partial cannot replace original reason/time/key history',
              (row(c), keys(c), [v for _k, v in state(c)]), (before, key_before, [2]))
        put(rp[:-5] + '.view', view)
        check('recovery after repeat ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
        check('recovery retains original fault but measures recovered contents',
              (unchanged_history(row(c), before), row(c)['angles'], row(c)['journal'], keys(c)),
              (True, 'OK', 'OK', key_before))
    finally:
        restore_game(rc)
        c.close()


def case_identity_and_loss():
    for changed in ('key', 'signed', 'header', 'missing', 'unknown'):
        s, sw, c, rp, now, old, rc, _rec, view, hid = setup()
        try:
            before, key_before = first_partial(sw, c, rp, now)
            original = open(rp, 'rb').read()
            if changed in ('key', 'signed'):
                suite.make_receipt(s.EVIDENCE_DIR, os.path.basename(rp)[:-5], age=old,
                                   seed=bytes([2 if changed == 'key' else 1] * 32),
                                   view=b'a different signed view' if changed == 'signed' else view, hid=hid)
            elif changed == 'header':
                put(rp, original.replace(b'svticks -1', b'svticks 662'))
                os.utime(rp, (old, old))
            elif changed == 'missing':
                os.remove(rp)
            else:
                c.execute("UPDATE receipts SET identity=''")
                c.commit()
                before = row(c)
            with mock.patch.object(rc, 'join_rec', wraps=rc.join_rec) as joined, \
                    contextlib.redirect_stderr(io.StringIO()):
                got = sw.receipt_step(c, limit=1, now=now + 60)
            check(changed + ': no identity/loss waiver before content joins', (got, joined.call_count), ((0, 0), 0))
            expected = dict(before)
            if changed == 'missing':
                # Existing settled-receipt loss expiry is availability, not a
                # measured journal fault or authority to invent its contents.
                expected.update(journal='ABSENT', journal_reason='the journal never arrived')
            check(changed + ': no historical or key mutation', (row(c), keys(c)), (expected, key_before))
            if changed == 'unknown':
                # Restore the previously captured identity, NOT operator baseline permission.
                c.execute('UPDATE receipts SET identity=?', (sw.receipt_identity(rc.read(rp)),))
                c.commit()
            put(rp, original)
            os.utime(rp, (old, old))
            put(rp[:-5] + '.view', view)
            check(changed + ': original restoration full completion ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
            check(changed + ': restored result complete, sightings unchanged',
                  (row(c)['angles'], row(c)['journal'], state(c), keys(c)), ('OK', 'OK', [], key_before))
        finally:
            restore_game(rc)
            c.close()


def case_absence_and_arrival():
    s, sw, c, rp, now, _old, rc, rec, view, _hid = setup()
    try:
        before, key_before = first_partial(sw, c, rp, now)
        recpath = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', os.path.basename(rp)[:-5] + '.rec')
        os.remove(recpath)
        os.remove(rp[:-5] + '.view')
        check('completion with captured absent sources ACTS', sw.receipt_step(c, now=now + 60), (1, 0))
        check('only complete observation establishes both missing-source waits',
              (waits(c), row(c)['angles'], row(c)['journal']), ((1, 1), '', 'OK'))
        put(rp[:-5] + '.view', view)
        check('late view ACTS and retains observed missing recording', sw.receipt_step(c, now=now + 120), (1, 0))
        check('late view did not invent recording completion', waits(c), (0, 1))
        put(recpath, rec)
        check('late recording ACTS on original receipt', sw.receipt_step(c, now=now + 180), (1, 0))
        check('late pair retains history and key sightings',
              (unchanged_history(row(c), before), row(c)['angles'], waits(c), keys(c)),
              (True, 'OK', (0, 0), key_before))
    finally:
        restore_game(rc)
        c.close()


def case_queue_and_pure_io():
    s, sw, c, rp, now, old, rc, _rec, view, hid = setup()
    try:
        first_partial(sw, c, rp, now)
        rid2 = '20261026-000002-0'
        rec2, view2 = suite.angle_pair(rid2)
        suite.make_receipt(s.EVIDENCE_DIR, rid2, age=old, view=view2.encode(), hid=hid)
        suite.with_rec(s, sw, rid2, rec2)
        for i in range(2):
            with interrupted(rp[:-5] + '.hid'), mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                got = sw.receipt_step(c, limit=1, now=now + 60 * (i + 1))
            check('queue pass%d one attempt, other receipt not starved' % i,
                  (got, reads.call_count), ((1, 0), 1))
        check('CONTROL healthy second receipt actually stored',
              c.execute('SELECT verdict FROM receipts WHERE runid=?', (rid2,)).fetchone()[0], 'VALID')
        check('failed first remains pending FULL, not journal-only',
              (c.execute('SELECT stale FROM receipts WHERE runid=?', (os.path.basename(rp)[:-5],)).fetchone()[0], [v for _k, v in state(c)]),
              (2, [2]))
    finally:
        restore_game(rc)
        c.close()
    s, sw, c, rp, now, _old, rc, _rec, _view, _hid = setup(fault='none')
    try:
        with interrupted(rp[:-5] + '.hid'):
            got = sw.receipt_step(c, limit=1, now=now)
        check('pure I/O is NOT an evidence row or partial-fault marker',
              (got, c.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], state(c)), ((0, 0), 0, []))
        check('pure I/O original fresh retry still ACTS', sw.receipt_step(c, now=now + 60), (1, 0))
    finally:
        restore_game(rc)
        c.close()


def case_explicit_reread():
    s, sw, c, rp, now, _old, rc, _rec, _view, _hid = setup()
    try:
        first_partial(sw, c, rp, now)
        sw.mark_receipts_stale(c)
        check('operator explicitly supersedes automatic scheduling token', [v for _k, v in state(c)], [1])
        check('operator full read retains existing verdict counting', sw.receipt_step(c, now=now + 60), (1, 1))
        check('operator still intentionally records its fresh key observation', keys(c)[0][3], now + 60)
    finally:
        restore_game(rc)
        c.close()


def main():
    for case in (case_completion, case_repeated_partial, case_identity_and_loss,
                 case_absence_and_arrival, case_queue_and_pure_io, case_explicit_reread):
        print(case.__name__ + ':')
        try:
            case()
        except Exception as exc:
            check(case.__name__ + ' ran to completion', '%s: %s' % (type(exc).__name__, exc), 'no exception')
    print('\n%d failed' % len(suite.FAILED))
    return bool(suite.FAILED)


if __name__ == '__main__':
    sys.exit(main())
