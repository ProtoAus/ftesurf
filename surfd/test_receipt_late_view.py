#!/usr/bin/env python3
"""Observed-missing views wake once; no live evidence or historical backfill.

Reader controls must judge uploads, not merely list them. Late views are hashed
and paired where a recording exists; journal observations and key sightings are
not reinterpreted. Silence/partial uploads, identity drift, I/O, legacy unknowns
and missing receipts are negative controls. Rec-only arrivals remain separate.
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


def row(conn):
    return dict(conn.execute('SELECT * FROM receipts').fetchone())


def keys(conn):
    return [tuple(r) for r in conn.execute('SELECT * FROM pubkeys ORDER BY pub, player')]


def waits(conn):
    return conn.execute("SELECT COUNT(*) FROM sweepmeta WHERE k GLOB 'receipt_view_wait:*'").fetchone()[0]


def put(path, data):
    with open(path, 'wb') as fh:
        fh.write(data)


def setup(rid, rot=0, tamper=False, no_rec=False, nonce_fault=False, ver=9, journal_fault=False):
    surfd, sweep, runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - surfd.JOURNAL_WAIT - surfd.EVIDENCE_SETTLE - 60
    rec, view = suite.angle_pair(rid, rot=rot, ver=ver)
    if nonce_fault:
        rec = rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
    rc = suite.with_rec(surfd, sweep, rid, rec)
    if no_rec:
        os.remove(os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', rid + '.rec'))
    healthy = suite._journal_text(break_pitch=journal_fault).encode('utf-8')
    rp, pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old,
                                 hid=healthy, view=view.encode('utf-8'), tamper=tamper)
    os.remove(rp[:-5] + '.view')
    replay = suite.add_replay(conn, runs, 'bhop_eazy', '0000662_p-2c8f36b6_run.rec')
    conn.execute("UPDATE replays SET runid = ?, player = 'alice' WHERE id = ?", (rid, replay))
    conn.commit()
    check(rid + ': initial full receipt ACTS', sweep.receipt_step(conn, now=now), (1, int(tamper or nonce_fault)))
    check(rid + ': missing view is a durable observation', waits(conn), 1)
    check(rid + ': journal CONTROL actually judged', row(conn)['journal'], 'FAULT' if journal_fault else 'OK')
    return surfd, sweep, conn, rp, pub, now, old, rc, view.encode('utf-8')


def restore_game(rc):
    rc.GAME = os.path.join(os.path.dirname(suite.TOOLS), 'ftesurf')


def case_outcomes():
    for i, kind in enumerate(('matching', 'legacy-pair', 'off-angle', 'digest', 'unsigned',
                              'no-rec', 'signature', 'nonce', 'prior-angle', 'prior-journal')):
        rid = '20261006-0003%02d-0' % i
        surfd, sweep, conn, rp, _pub, now, old, rc, view = setup(
            rid, rot=0.5 if kind == 'off-angle' else 0,
            tamper=kind == 'signature', no_rec=kind == 'no-rec', nonce_fault=kind == 'nonce',
            ver=8 if kind == 'legacy-pair' else 9, journal_fault=kind == 'prior-journal')
        try:
            if kind == 'unsigned':
                # Re-sign before a fresh full observation to commit no view.
                rp, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=suite._journal_text().encode('utf-8'))
                data = open(rp, 'rb').read()
                # Use the fixture's normal valid message/signature machinery.
                import ed25519
                lines = data.decode().splitlines()
                lines = ['signed view -' if l.startswith('signed view ') else l for l in lines]
                msg = ('FTESURF-RCPT 1\n' + '\n'.join(l[7:] for l in lines if l.startswith('signed ')) + '\n').encode()
                sig = ed25519.sign(bytes([1] * 32), msg).hex()
                lines = ['sig ' + sig if l.startswith('sig ') else l for l in lines]
                put(rp, ('\n'.join(lines) + '\n').encode());os.utime(rp, (old, old))
                os.remove(rp[:-5] + '.view')
                conn.execute('DELETE FROM receipts');conn.execute('DELETE FROM pubkeys');conn.commit()
                check('unsigned: new no-view statement ACTS', sweep.receipt_step(conn, now=now + 1), (1, 0))
            if kind == 'prior-angle':
                conn.execute("UPDATE receipts SET verdict='FAULT', angles='FAULT', reason='historical angle fault'")
                conn.commit()
            before, before_keys = row(conn), keys(conn)
            with mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                got = sweep.receipt_step(conn, now=now + 60)
            check(kind + ': silence never rereads', (got, reads.call_count), ((0, 0), 0))
            os.mkdir(rp[:-5] + '.view')
            check(kind + ': directory not an arrival', sweep.receipt_step(conn, now=now + 90), (0, 0))
            os.rmdir(rp[:-5] + '.view')
            put(rp[:-5] + '.view.part', view if kind != 'digest' else b'not the signed view\n')
            check(kind + ': part is not an arrival', sweep.receipt_step(conn, now=now + 120), (0, 0))
            os.replace(rp[:-5] + '.view.part', rp[:-5] + '.view')
            control = rc.read(rp);rc.join_rec(control);rc.join_uploaded(control, {'hid': True});rc.join_angles(control, {})
            check(kind + ': CONTROL view digest ACTS', bool(control.digest_bad), kind in ('digest', 'unsigned'))
            check(kind + ': CONTROL pair ACTS', control.angles,
                  '' if kind == 'no-rec' else 'FAULT' if kind in ('off-angle', 'digest', 'unsigned')
                  else 'BLIND' if kind == 'legacy-pair' else 'OK')
            # Even a replaced/unreadable HID must not be read on this source retry.
            put(rp[:-5] + '.hid', b'unrelated late journal replacement')
            with mock.patch.object(rc, 'join_rec', wraps=rc.join_rec) as rec_join, \
                    mock.patch.object(rc, 'join_angles', wraps=rc.join_angles) as angle_join, \
                    mock.patch.object(rc, 'join_journal', wraps=rc.join_journal) as hid_join:
                got = sweep.receipt_step(conn, now=now + 180)
            new_fault = kind in ('off-angle', 'digest', 'unsigned')
            check(kind + ': late view ACTS with pair, no HID', (got, rec_join.call_count, angle_join.call_count, hid_join.call_count),
                  ((1, int(new_fault)), 1, 1, 0))
            after = row(conn)
            expected = dict(before)
            if new_fault:expected.update(verdict='FAULT', reason=control.faults[0][:300])
            if before['angles'] != 'FAULT' and control.angles:expected['angles'] = control.angles
            check(kind + ': only monotonic view findings change', after, expected)
            check(kind + ': no key sightings or waiting marker', (keys(conn), waits(conn)), (before_keys, 0))
            with mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                got = sweep.receipt_step(conn, now=now + 240)
            check(kind + ': completion is not reinterpreted', (got, reads.call_count), ((0, 0), 0))
        finally:
            restore_game(rc)


def case_binding():
    for kind in ('key', 'signed', 'header'):
        rid = '20261006-000310-0'
        surfd, sweep, conn, rp, _pub, now, old, rc, view = setup(rid)
        try:
            original = open(rp, 'rb').read()
            before, before_keys = row(conn), keys(conn)
            suite.make_receipt(surfd.EVIDENCE_DIR, rid, age=old, hid=suite._journal_text().encode('utf-8'),
                               view=view if kind != 'signed' else b'replacement view', seed=bytes([2 if kind == 'key' else 1] * 32))
            if kind == 'header':
                put(rp, original.replace(b'svticks -1', b'svticks 662'));os.utime(rp, (old, old))
            check(kind + ': replacement cryptographic CONTROL', bool(rc.read(rp).ok), True)
            with mock.patch.object(rc, 'join_rec', wraps=rc.join_rec) as joined, \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                got = sweep.receipt_step(conn, limit=1, now=now + 60)
            check(kind + ': guard refuses before joins', (got, joined.call_count), ((0, 0), 0))
            check(kind + ': history/key/readiness unchanged', (row(conn), keys(conn), waits(conn)), (before, before_keys, 1))
            check(kind + ': refusal observable', 'receipt identity changed' in err.getvalue(), True)
            put(rp, original);os.utime(rp, (old, old));put(rp[:-5] + '.view', view)
            check(kind + ': restored original ACTS', sweep.receipt_step(conn, now=now + 120), (1, 0))
            check(kind + ': restoration no attribution change', (row(conn)['pub'], keys(conn)), (before['pub'], before_keys))
        finally:
            restore_game(rc)


def case_io_fairness():
    surfd, sweep, conn, rp, _pub, now, old, rc, view = setup('20261006-000311-0', no_rec=True)
    try:
        before = row(conn)
        rp2, _pub = suite.make_receipt(surfd.EVIDENCE_DIR, '20261006-000312-0', age=old,
                                      hid=suite._journal_text().encode('utf-8'), view=view)
        os.remove(rp2[:-5] + '.view')
        check('IO: second missing view ACTS', sweep.receipt_step(conn, now=now), (1, 0))
        before_keys = keys(conn)
        put(rp[:-5] + '.view', view);put(rp2[:-5] + '.view', view)
        real_open = builtins.open

        def eio(path, *args, **kwargs):
            if path == rp[:-5] + '.view':raise OSError(5, 'Input/output error')
            return real_open(path, *args, **kwargs)

        for i in range(3):
            with mock.patch('builtins.open', side_effect=eio), mock.patch.object(rc, 'read', wraps=rc.read) as reads, \
                    contextlib.redirect_stderr(io.StringIO()):
                got = sweep.receipt_step(conn, limit=1, now=now + 60 * (i + 1))
            check('IO: pass %d bounded and fair' % i, (reads.call_count, got), (1, (1, 0) if i == 1 else (0, 0)))
        first = dict(conn.execute("SELECT * FROM receipts WHERE runid='20261006-000311-0'").fetchone())
        check('IO: unmeasured source leaves row/key/readiness', (first, keys(conn), waits(conn)), (before, before_keys, 1))
        check('IO: error removal ACTS', sweep.receipt_step(conn, now=now + 240), (1, 0))
        check('IO: recovered wait retired', waits(conn), 0)
    finally:
        restore_game(rc)


def case_races_and_coarrival():
    surfd, sweep, conn, rp, _pub, now, _old, rc, view = setup('20261006-000315-0')
    try:
        before = row(conn)
        put(rp[:-5] + '.view', view)
        real_read = rc.read

        def vanish(path):
            got = real_read(path)
            os.remove(rp[:-5] + '.view')
            return got

        with mock.patch.object(rc, 'read', side_effect=vanish):
            got = sweep.receipt_step(conn, now=now + 60)
        check('race: listing was positive, missing bytes defer', (got, row(conn), waits(conn)), ((0, 0), before, 1))
        put(rp[:-5] + '.view', view)
        check('race: source restoration ACTS', sweep.receipt_step(conn, now=now + 120), (1, 0))
        # Re-establish absence by explicit full observation, both sources now missing.
        os.remove(rp[:-5] + '.view');os.remove(rp[:-5] + '.hid')
        sweep.mark_receipts_stale(conn)
        check('coarrival: full absence CONTROL ACTS', sweep.receipt_step(conn, now=now + 180), (1, 0))
        before, before_keys = row(conn), keys(conn)
        check('coarrival: both missing states captured', (before['journal'], waits(conn)), ('ABSENT', 1))
        put(rp[:-5] + '.view', view);put(rp[:-5] + '.hid', suite._journal_text().encode('utf-8'))
        check('coarrival: bounded first source ACTS', sweep.receipt_step(conn, limit=1, now=now + 240), (1, 0))
        check('coarrival: view moves, journal untouched', (row(conn)['angles'], row(conn)['journal'], waits(conn)), ('OK', 'ABSENT', 0))
        check('coarrival: bounded second source ACTS', sweep.receipt_step(conn, limit=1, now=now + 300), (1, 0))
        check('coarrival: journal recovery preserves pair/keys', (row(conn)['angles'], row(conn)['journal'], keys(conn)), ('OK', 'OK', before_keys))
    finally:
        restore_game(rc)


def case_source_fairness():
    for failed in ('view', 'hid'):
        surfd, sweep, conn, rp, _pub, now, _old, rc, view = setup('20261006-000317-0')
        try:
            os.remove(rp[:-5] + '.hid')
            sweep.mark_receipts_stale(conn)
            check(failed + ': both missing CONTROL ACTS', sweep.receipt_step(conn, now=now + 60), (1, 0))
            if failed == 'hid':
                conn.execute("UPDATE sweepmeta SET v=2 WHERE k GLOB 'receipt_view_wait:*'")
                conn.commit()
            put(rp[:-5] + '.view', view);put(rp[:-5] + '.hid', suite._journal_text().encode('utf-8'))
            before_keys = keys(conn)
            real_open = builtins.open

            def eio(path, *args, **kwargs):
                if path == rp[:-5] + '.' + failed:raise OSError(5, 'Input/output error')
                return real_open(path, *args, **kwargs)

            for i in range(2):
                with mock.patch('builtins.open', side_effect=eio), mock.patch.object(rc, 'read', wraps=rc.read) as reads, \
                        contextlib.redirect_stderr(io.StringIO()):
                    got = sweep.receipt_step(conn, limit=1, now=now + 120 + 60 * i)
                check(failed + ': co-ready source pass %d bounded/ACTS' % i, (got, reads.call_count), ((i, 0), 1))
            check(failed + ': healthy source not blocked on same receipt',
                  (row(conn)['angles'], row(conn)['journal'], keys(conn)),
                  (('', 'OK', before_keys) if failed == 'view' else ('OK', 'ABSENT', before_keys)))
            check(failed + ': failed source restoration ACTS', sweep.receipt_step(conn, now=now + 300), (1, 0))
            check(failed + ': both sources complete without key recount',
                  (row(conn)['angles'], row(conn)['journal'], waits(conn), keys(conn)), ('OK', 'OK', 0, before_keys))
        finally:
            restore_game(rc)


def case_no_partial_baseline():
    surfd, sweep, conn, rp, _pub, now, _old, rc, _view = setup('20261006-000318-0', tamper=True)
    try:
        conn.execute('DELETE FROM receipts');conn.execute('DELETE FROM pubkeys')
        conn.execute("DELETE FROM sweepmeta WHERE k GLOB 'receipt_view_wait:*'");conn.commit()
        real_open = builtins.open

        def eio(path, *args, **kwargs):
            if path == rp[:-5] + '.hid':raise OSError(5, 'Input/output error')
            return real_open(path, *args, **kwargs)

        with mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, now=now + 60)
        check('baseline: partial independent fault ACTS without inventing readiness', (got, waits(conn)), ((1, 1), 0))
        # Existing initial-partial recovery only rechecks the journal; it does
        # not claim a complete full observation. Establish one explicitly.
        sweep.mark_receipts_stale(conn)
        check('baseline: explicit full recovery ACTS', sweep.receipt_step(conn, now=now + 120), (1, 1))
        check('baseline: only completed full observation creates wait', waits(conn), 1)
    finally:
        restore_game(rc)


def case_selection_race():
    for journal_fault in (False, True):
        for loss in ('disappear', 'stat-loss'):
            surfd, sweep, conn, rp, _pub, now, _old, rc, view = setup(
                '20261006-000319-0', journal_fault=journal_fault)
            try:
                before, before_keys = row(conn), keys(conn)
                os.remove(rp[:-5] + '.hid')
                put(rp[:-5] + '.view', view)
                real_isfile = sweep.os.path.isfile
                checks = []

                def lose_readiness(path):
                    if path == rp[:-5] + '.view':
                        checks.append(path)
                        if len(checks) == 1:
                            if loss == 'disappear':os.remove(path)
                            return True  # queued by the first positive stat
                        return False     # no longer eligible at source selection
                    return real_isfile(path)

                label = ('FAULT' if journal_fault else 'OK') + '/' + loss
                with mock.patch.object(sweep.os.path, 'isfile', side_effect=lose_readiness), \
                        mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                    got = sweep.receipt_step(conn, limit=1, now=now + 60)
                check(label + ': CONTROL crossed both eligibility checks', len(checks), 2)
                check(label + ': no ready source means no evidence read', (got, reads.call_count), ((0, 0), 0))
                check(label + ': completed HID/history/readiness preserved', (row(conn), keys(conn), waits(conn)),
                      (before, before_keys, 1))
                put(rp[:-5] + '.view', view)
                with mock.patch.object(rc, 'join_journal', wraps=rc.join_journal) as journal:
                    got = sweep.receipt_step(conn, now=now + 120)
                check(label + ': stable-view restoration ACTS without HID', (got, journal.call_count), ((1, 0), 0))
                check(label + ': restored join preserves completed HID finding', row(conn), dict(before, angles='OK'))
                check(label + ': completion retires only view readiness', (waits(conn), keys(conn)), (0, before_keys))
            finally:
                restore_game(rc)


def case_captured_absence():
    surfd, sweep, conn, rp, _pub, now, _old, rc, view = setup('20261006-000316-0')
    try:
        real_join = rc.join_uploaded

        def arrive_after_capture(receipt, want):
            real_join(receipt, want)
            put(rp[:-5] + '.view', view)

        sweep.mark_receipts_stale(conn)
        with mock.patch.object(rc, 'join_uploaded', side_effect=arrive_after_capture):
            got = sweep.receipt_step(conn, now=now + 60)
        check('capture: full read acts, late bytes do not change its snapshot',
              (got, row(conn)['angles'], waits(conn)), ((1, 0), '', 1))
        check('capture: subsequent observed arrival actually joins', sweep.receipt_step(conn, now=now + 120), (1, 0))
        check('capture: pair judged and readiness retired', (row(conn)['angles'], waits(conn)), ('OK', 0))
    finally:
        restore_game(rc)


def case_deferred_fault():
    rid = '20261006-000314-0'
    surfd, sweep, conn, rp, _pub, now, _old, rc, view = setup(rid)
    try:
        before, before_keys = row(conn), keys(conn)
        recpath = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', rid + '.rec')
        text = open(recpath, encoding='utf-8').read().replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
        put(recpath, text.encode('utf-8'))
        control = rc.read(rp);rc.join_rec(control)
        check('partial: CONTROL nonce contradiction ACTS', bool(control.faults), True)
        put(rp[:-5] + '.view', view)
        real_open = builtins.open

        def eio(path, *args, **kwargs):
            if path == rp[:-5] + '.view':raise OSError(5, 'Input/output error')
            return real_open(path, *args, **kwargs)

        with mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
            got = sweep.receipt_step(conn, now=now + 60)
        check('partial: independent measured nonce fault stored', got, (1, 1))
        expected = dict(before, verdict='FAULT', reason=control.faults[0][:300])
        check('partial: no unmeasured columns or sightings changed', (row(conn), keys(conn), waits(conn)),
              (expected, before_keys, 1))
        # Remove the newly observed contradiction, but its historical finding
        # must survive the completion of this source's interrupted read.
        put(recpath, text.replace('\nnonce ' + '0' * 32, '').encode('utf-8'))
        check('partial: recovery actually finishes view check', sweep.receipt_step(conn, now=now + 120), (1, 0))
        check('partial: recovery cannot erase fault', row(conn), dict(expected, angles='OK'))
        check('partial: only completed view retires readiness', (waits(conn), keys(conn)), (0, before_keys))
    finally:
        restore_game(rc)


def case_unknown_and_loss():
    for kind in ('readiness', 'identity', 'loss', 'incomplete'):
        surfd, sweep, conn, rp, pub, now, _old, rc, view = setup('20261006-000313-0', no_rec=True)
        try:
            if kind == 'readiness':conn.execute("DELETE FROM sweepmeta WHERE k GLOB 'receipt_view_wait:*'")
            if kind == 'identity':conn.execute("UPDATE receipts SET identity='' ")
            conn.commit()
            before = row(conn)
            if kind == 'loss':os.remove(rp)
            put(rp[:-5] + '.view', view)
            if kind == 'incomplete':
                with mock.patch.object(sweep.os, 'scandir', side_effect=OSError('unreadable')), \
                        contextlib.redirect_stderr(io.StringIO()):
                    got = sweep.receipt_step(conn, now=now + 60)
                check('incomplete: readiness not reaped', (got, waits(conn), row(conn)), ((0, 0), 1, before))
                check('incomplete: coverage restoration ACTS', sweep.receipt_step(conn, now=now + 120), (1, 0))
                continue
            with mock.patch.object(rc, 'read', wraps=rc.read) as reads, contextlib.redirect_stderr(io.StringIO()):
                got = sweep.receipt_step(conn, now=now + 60)
            check(kind + ': no guessed historical join', (got, reads.call_count, row(conn)), ((0, 0), 0, before))
            if kind == 'loss':
                check('loss: completed listing reaps only readiness', waits(conn), 0)
                continue
            # Explicit full observation is permitted, not an automatic guess.
            os.remove(rp[:-5] + '.view')
            sweep.mark_receipts_stale(conn)
            check(kind + ': explicit full observation ACTS', sweep.receipt_step(conn, now=now + 120), (1, 0))
            check(kind + ': current readiness established', (row(conn)['pub'], bool(row(conn)['identity']), waits(conn)), (pub, True, 1))
            put(rp[:-5] + '.view', view)
            check(kind + ': now observed arrival ACTS', sweep.receipt_step(conn, now=now + 180), (1, 0))
        finally:
            restore_game(rc)


def main():
    for case in (case_outcomes, case_binding, case_io_fairness, case_races_and_coarrival,
                 case_source_fairness, case_no_partial_baseline, case_selection_race, case_captured_absence,
                 case_deferred_fault, case_unknown_and_loss):
        print(case.__name__ + ':')
        try:case()
        except Exception as exc:check(case.__name__ + ' ran to completion', '%s: %s' % (type(exc).__name__, exc), 'no exception')
    print('\n%d failed' % len(suite.FAILED))
    return 1 if suite.FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
