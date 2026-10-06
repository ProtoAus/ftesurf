#!/usr/bin/env python3
"""Receipt snapshot storage and lifecycle controls; temporary evidence only."""
import builtins
import contextlib
import io
import json
import os
import sys
from unittest import mock

import test_sweep as suite
from test_receipt_angle_reasons import setup
from test_receipt_late_view import row, keys, put, restore_game

check = suite.check


def observation(rc, rp):
    r = rc.read(rp)
    rc.join_journal(r)
    return r


def snapshot(c):
    text = row(c).get('journal_metrics', '')
    return json.loads(text) if text else None


def case_full_and_no_backfill():
    for kind in ('OK', 'FAULT', 'ABSENT', 'digest'):
        s, sw, c, now, rc, rp = setup()
        try:
            if kind == 'ABSENT':
                os.remove(rp[:-5] + '.hid')
            elif kind == 'digest':
                put(rp[:-5] + '.hid', b'not signed bytes')
            elif kind == 'FAULT':
                from test_journal_diagnostics import fault_journal
                hid = fault_journal().encode()
                suite.make_receipt(s.EVIDENCE_DIR, os.path.basename(rp)[:-5], hid=hid,
                                   view=open(rp[:-5]+'.view', 'rb').read(),
                                   age=now - 2*s.EVIDENCE_SETTLE)
            ctl = observation(rc, rp)
            got = sw.receipt_step(c, now=now)
            check(kind + ': full CONTROL ACTS', got, (1, int(kind == 'digest')))
            check(kind + ': stored snapshot equals captured reader', snapshot(c), ctl.journal_metrics)
            if kind in ('OK', 'FAULT'):
                check(kind + ': measured comparisons present', snapshot(c)['metrics']['identity_judged'] > 0, True)
                check(kind + ': content/signature separated', (row(c)['journal'], row(c)['verdict']), (kind, 'VALID'))
            saved, sightings = row(c), keys(c)
            with mock.patch.object(rc, 'join_journal', wraps=rc.join_journal) as acted:
                got = sw.receipt_step(c, now=now + 60)
            check(kind + ': no unsolicited historical reread', (got, acted.call_count, row(c), keys(c)),
                  ((0, 0), 0, saved, sightings))
        finally:
            restore_game(rc)


def case_migration():
    s, sw, c, now, rc, rp = setup()
    try:
        sw.receipt_step(c, now=now)
        if 'journal_metrics' in {r[1] for r in c.execute('PRAGMA table_info(receipts)')}:
            c.execute('ALTER TABLE receipts DROP COLUMN journal_metrics')
        c.commit()
        saved, sightings = row(c), keys(c)
        meta = [tuple(r) for r in c.execute('SELECT * FROM sweepmeta')]
        for i in range(2):
            s.receipts_v8(c)
            check('migration: historical metrics unavailable %d' % i, row(c), dict(saved, journal_metrics=''))
            check('migration: no key/metadata scheduling changes %d' % i,
                  (keys(c), [tuple(r) for r in c.execute('SELECT * FROM sweepmeta')]), (sightings, meta))
    finally:
        restore_game(rc)


def case_late_journal_and_io():
    s, sw, c, now, rc, rp = setup()
    try:
        hp = rp[:-5] + '.hid'
        hid = open(hp, 'rb').read()
        os.remove(hp)
        check('late: absent initial CONTROL ACTS', sw.receipt_step(c, now=now), (1, 0))
        check('late: pending has no metric fiction', (row(c)['journal'], snapshot(c)), ('PENDING', None))
        before, sightings = row(c), keys(c)
        put(hp, hid)
        real_open = builtins.open

        def eio(p, *args, **kw):
            if p == hp:
                raise OSError(5, 'control')
            return real_open(p, *args, **kw)

        with mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
            check('late: unread bytes retry', sw.receipt_step(c, now=now+60), (0, 0))
        check('late: I/O changes no history', (row(c), keys(c)), (before, sightings))
        with mock.patch.object(rc, 'join_angles', wraps=rc.join_angles) as angles:
            got = sw.receipt_step(c, now=now+120)
        ctl = observation(rc, rp)
        check('late: journal-only CONTROL ACTS', (got, angles.call_count), ((1, 0), 0))
        check('late: measured snapshot installed', snapshot(c), ctl.journal_metrics)
        check('late: no key sighting replay', keys(c), sightings)
    finally:
        restore_game(rc)


def case_partial_history():
    for content_fault in (False, True):
        s, sw, c, now, rc, rp = setup()
        try:
            if content_fault:
                from test_journal_diagnostics import fault_journal
                suite.make_receipt(s.EVIDENCE_DIR, os.path.basename(rp)[:-5], hid=fault_journal().encode(),
                                   view=open(rp[:-5]+'.view', 'rb').read(),
                                   age=now - 2*s.EVIDENCE_SETTLE)
            check('partial: original CONTROL ACTS', sw.receipt_step(c, now=now), (1, 0))
            before = row(c)
            sw.mark_receipts_stale(c)
            rec = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', os.path.basename(rp)[:-5]+'.rec')
            saved = open(rec, 'rb').read()
            put(rec, saved.replace(b'\nbegin', b'\nnonce '+b'0'*32+b'\nbegin', 1))
            real_open = builtins.open

            def eio(p, *args, **kw):
                if p == rp[:-5]+'.hid':
                    raise OSError(5, 'control')
                return real_open(p, *args, **kw)

            with mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
                check('partial: independent fault measured', sw.receipt_step(c, now=now+60), (1, 1))
            check('partial: journal triplet preserved',
                  tuple(row(c).get(k) for k in ('journal', 'journal_reason', 'journal_metrics')),
                  tuple(before.get(k) for k in ('journal', 'journal_reason', 'journal_metrics')))
            put(rec, saved)
            os.remove(rp[:-5]+'.hid')
            check('partial: recovery ACTS with missing journal', sw.receipt_step(c, now=now+120), (1, 1))
            check('partial: retained verdict retains exact snapshot',
                  tuple(row(c).get(k) for k in ('journal', 'journal_reason', 'journal_metrics')),
                  tuple(before.get(k) for k in ('journal', 'journal_reason', 'journal_metrics')))
        finally:
            restore_game(rc)


def case_late_view_and_identity():
    import test_receipt_late_view as late
    s, sw, c, rp, pub, now, old, rc, view = late.setup('20261006-000519-0')
    try:
        before = row(c)
        put(rp[:-5]+'.view', view)
        check('view: late pair CONTROL ACTS', sw.receipt_step(c, now=now+60), (1, 0))
        check('view: unrelated snapshot untouched', row(c).get('journal_metrics'), before.get('journal_metrics'))
        sw.mark_receipts_stale(c)
        saved = row(c)
        put(rp, open(rp, 'rb').read().replace(b'pub '+pub.encode(), b'pub '+b'0'*64))
        with contextlib.redirect_stderr(io.StringIO()):
            check('identity: replacement rejected before measurement', sw.receipt_step(c, now=now+120), (0, 0))
        check('identity: history untouched', row(c), saved)
    finally:
        restore_game(rc)


def main():
    for case in (case_full_and_no_backfill, case_migration, case_late_journal_and_io,
                 case_partial_history, case_late_view_and_identity):
        try:
            case()
        except Exception as e:
            check(case.__name__, '%s: %s' % (type(e).__name__, e), 'no exception')
    print('%d failed' % len(suite.FAILED))
    return int(bool(suite.FAILED))


if __name__ == '__main__':
    sys.exit(main())
