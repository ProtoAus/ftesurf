#!/usr/bin/env python3
"""Late recording scheduling; signed temporary fixtures, no live evidence."""
import builtins
import contextlib
import io
import os
import sys
import time
from unittest import mock

import test_sweep as suite
from test_receipt_late_view import row, keys, angle_reason, put as put_bytes, restore_game, setup as view_setup

check = suite.check


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    put_bytes(path, data)


def resign(text):
    import ed25519
    lines = text.splitlines()
    msg = (lines[0] + '\n' + ''.join(line[7:] + '\n' for line in lines if line.startswith('signed '))).encode('utf-8')
    sig = ed25519.sign(b'\x01' * 32, msg).hex()
    return '\n'.join('sig ' + sig if line.startswith('sig ') else line for line in lines) + '\n'


def waits(conn, source='rec'):
    return conn.execute("SELECT COUNT(*) FROM sweepmeta WHERE k GLOB ?",
                        ('receipt_' + source + '_wait:*',)).fetchone()[0]


def setup(rid, missing_view=False, prior='clean', legacy=False):
    surfd, sweep, runs = suite.fresh()
    sweep.TOOLS = suite.TOOLS
    conn = surfd.connect()
    now = int(time.time())
    old = now - 2 * surfd.EVIDENCE_SETTLE
    rec, view = suite.angle_pair(rid, still=False, ver=8 if legacy else 9)
    hid = suite._journal_text(break_pitch=prior == 'journal').encode('utf-8')
    rp, pub = suite.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode('utf-8'),
                                hid=hid, tamper=prior == 'signature', age=old)
    os.remove(rp[:-5] + '.hid')
    if missing_view:
        os.remove(rp[:-5] + '.view')
    suite.add_replay(conn, runs, 'bhop_eazy', rid + '.rec', make_file=False)
    conn.execute('UPDATE replays SET runid=?, player=?', (rid, 'synthetic-late-rec'))
    conn.commit()
    rc = suite.with_rec(surfd, sweep, rid, rec)
    path = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', rid + '.rec')
    os.remove(path)
    if prior == 'journal':
        put(rp[:-5] + '.hid', hid)
    first = sweep.receipt_step(conn, now=now)
    check('initial full observation ACTS', first, (1, int(prior == 'signature')))
    check('initial no-rec pair is unjudged, readiness captured', (row(conn)['angles'], waits(conn)), ('', 1))
    return surfd, sweep, conn, rp, pub, now, old, rc, rec, view.encode('utf-8'), path, hid


def control(rc, rp, angles=None, fault=False):
    r = rc.read(rp)
    rc.join_rec(r); rc.join_ticks(r); rc.join_uploaded(r, ('hid',)); rc.join_angles(r, {})
    check('independent pair reader ACTS', (r.recpath is not None, r.ok, bool(r.faults), r.angles),
          (True, True, fault, angles))
    return r


def case_outcomes():
    for kind in ('OK', 'BLIND', 'angles', 'nonce', 'digest', 'unsigned', 'ticks', 'sessions'):
        rid = '20261006-000401-0'
        s, sw, c, rp, _pub, now, _old, rc, rec, view, path, _hid = setup(rid, legacy=kind == 'BLIND')
        try:
            before, before_keys = row(c), keys(c)
            if kind == 'angles':
                rec, _ = suite.angle_pair(rid, rot=0.0, still=False)
                _unused, off = suite.angle_pair(rid, rot=23.0, still=False)
                # Re-sign before the full observation, not a delayed identity swap.
                suite.make_receipt(s.EVIDENCE_DIR, rid, view=off.encode('utf-8'), age=_old)
                c.execute('DELETE FROM receipts'); c.execute('DELETE FROM pubkeys'); c.commit()
                sw.receipt_step(c, now=now)
                before, before_keys = row(c), keys(c)
            if kind == 'nonce':
                rec = rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
            if kind == 'sessions':
                rec = rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
                rec += 'session 2\nnonce 400 d6c6820bca16750c77166d96dcf02787\n'
            if kind == 'digest':
                put(rp[:-5] + '.view', view + b'changed\n')
            if kind == 'unsigned':
                text = open(rp, encoding='utf-8').read()
                # This field is signed; establish the unsigned receipt explicitly.
                text = resign('\n'.join('signed view -' if line.startswith('signed view ') else line for line in text.splitlines()) + '\n')
                put(rp, text.encode('utf-8')); os.utime(rp, (_old,) * 2)
                c.execute('DELETE FROM receipts'); c.execute('DELETE FROM pubkeys'); c.commit()
                sw.receipt_step(c, now=now)
                before, before_keys = row(c), keys(c)
            if kind == 'ticks':
                text = open(rp, encoding='utf-8').read().replace('svticks -1', 'svticks 27')
                put(rp, text.encode('utf-8')); os.utime(rp, (_old,) * 2)
                c.execute('DELETE FROM receipts'); c.execute('DELETE FROM pubkeys'); c.commit()
                sw.receipt_step(c, now=now)
                before, before_keys = row(c), keys(c)
            put(path, rec.encode('utf-8'))
            expected_angle = 'BLIND' if kind == 'BLIND' else 'FAULT' if kind in ('angles', 'digest', 'unsigned') else 'OK'
            ctl = control(rc, rp, expected_angle, kind in ('angles', 'nonce', 'digest', 'unsigned', 'ticks'))
            with mock.patch.object(rc, 'join_rec', wraps=rc.join_rec) as joins, \
                    mock.patch.object(rc, 'join_journal', wraps=rc.join_journal) as journal:
                got = sw.receipt_step(c, limit=1, now=now + 60)
            check(kind + ': recording join ACTS, never HID', (got, joins.call_count, journal.call_count),
                  ((1, int(bool(ctl.faults) and before['verdict'] != 'FAULT')), 1, 0))
            want = dict(before, angles=ctl.angles or '', angles_reason=ctl.angles_detail[:1000],
                        verdict='FAULT' if before['verdict'] == 'FAULT' or ctl.faults else 'VALID',
                        reason=before['reason'] if before['verdict'] == 'FAULT' else ctl.faults[0][:300] if ctl.faults else '')
            check(kind + ': only measured pair findings change', (row(c), keys(c), waits(c)), (want, before_keys, 0))
            # A completed source replacement is outside this scheduler.
            put(path, rec.replace('\nbegin', '\nnonce ' + 'f' * 32 + '\nbegin', 1).encode('utf-8'))
            check(kind + ': completed recording replacement not scheduled', sw.receipt_step(c, now=now + 120), (0, 0))
        finally:
            restore_game(rc)


def case_arrival_order_and_locations():
    for leg in ('evidence', 'main', 'stage_2', 'bonus_1'):
        for first in ('view', 'rec'):
            rid = '20261006-000402-0'
            s, sw, c, rp, _pub, now, _old, rc, rec, view, path, _hid = setup(rid, missing_view=True)
            try:
                before, before_keys = row(c), keys(c)
                if leg != 'evidence':
                    path = os.path.join(rc.GAME, 'data', 'runs', 'bhop_eazy', leg, 'renamed.rec')
                else:
                    path = os.path.join(os.path.dirname(path), 'renamed.rec')
                if leg == 'main':
                    s.RUNS_DIR = os.path.join(rc.GAME, 'data', 'runs')
                    c.execute('UPDATE replays SET leaf=?', ('renamed.rec',)); c.commit()
                if first == 'view':
                    put(rp[:-5] + '.view', view)
                    check('view-first: view read ACTS without recording', sw.receipt_step(c, now=now + 60), (1, 0))
                    check('view-first: view completion retains recording readiness', (waits(c, 'view'), waits(c)), (0, 1))
                    put(path, rec.encode('utf-8'))
                else:
                    put(path, rec.encode('utf-8'))
                    check('rec-first: nonce read ACTS without view', sw.receipt_step(c, now=now + 60), (1, 0))
                    check('rec-first: only recording readiness retired', (waits(c, 'view'), waits(c)), (1, 0))
                    put(rp[:-5] + '.view', view)
                control(rc, rp, 'OK')
                check(leg + '/' + first + ': final pair ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
                check('arrival order: pair only, no history/key reset', (row(c), keys(c), waits(c), waits(c, 'view')),
                      (dict(before, angles='OK', angles_reason=angle_reason(rc, rp)), before_keys, 0, 0))
            finally:
                restore_game(rc)


def case_history_and_missing_view():
    for prior in ('signature', 'journal', 'angle', 'nonce'):
        s, sw, c, rp, _pub, now, _old, rc, rec, view, path, _hid = setup('20261006-000403-0', prior=prior if prior in ('signature', 'journal') else 'clean')
        try:
            if prior in ('angle', 'nonce'):
                broken, off = suite.angle_pair('20261006-000403-0', rot=22, still=False)
                if prior == 'nonce': broken = broken.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
                if prior == 'angle':
                    # Change recording angles instead of the signed view.
                    broken, _ = suite.angle_pair('20261006-000403-0', still=True)
                put(path, broken.encode('utf-8'))
                check(prior + ': old fault CONTROL ACTS', sw.receipt_step(c, now=now + 60), (1, 1))
                # A partial explicit reread followed by recovery captures rec
                # absence while retaining the previously measured findings.
                sw.mark_receipts_stale(c)
                put(path, rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1).encode('utf-8'))
                real_open = builtins.open

                def blocked(p, *args, **kwargs):
                    if p == rp[:-5] + '.hid': raise OSError(5, 'Input/output error')
                    return real_open(p, *args, **kwargs)

                with mock.patch('builtins.open', side_effect=blocked), contextlib.redirect_stderr(io.StringIO()):
                    check(prior + ': partial reread ACTS', sw.receipt_step(c, now=now + 90), (1, 0))
                os.remove(path)
                check(prior + ': recovery captures missing rec', sw.receipt_step(c, now=now + 120), (1, 1))
            before, before_keys = row(c), keys(c)
            os.remove(rp[:-5] + '.view')
            put(path, rec.encode('utf-8'))
            with mock.patch.object(rc, 'join_journal', wraps=rc.join_journal) as journal:
                got = sw.receipt_step(c, now=now + 180)
            check(prior + ': pruned view still checks nonce without HID', (got, journal.call_count), ((1, 0), 0))
            check(prior + ': no invented pair or history/key reset', (row(c), keys(c), waits(c)), (before, before_keys, 0))
        finally:
            restore_game(rc)


def case_identity():
    for kind in ('key', 'signed', 'header', 'path'):
        s, sw, c, rp, _pub, now, old, rc, rec, view, path, hid = setup('20261006-000404-0')
        try:
            saved = open(rp, 'rb').read(); before, before_keys = row(c), keys(c)
            if kind == 'key':
                suite.make_receipt(s.EVIDENCE_DIR, '20261006-000404-0', seed=b'\x02' * 32, view=view, hid=hid, age=old)
                os.remove(rp[:-5] + '.hid')
            if kind in ('signed', 'header', 'path'):
                text = saved.decode('utf-8').replace(*{'signed': ('signed nonce d6', 'signed nonce a6'), 'header': ('owner ^3T^7', 'owner replacement'), 'path': ('runid 20261006-000404-0', 'runid 20261006-000499-0')}[kind])
                put(rp, text.encode('utf-8')); os.utime(rp, (old,) * 2)
            put(path, rec.encode('utf-8'))
            with mock.patch.object(rc, 'join_rec', wraps=rc.join_rec) as joins, contextlib.redirect_stderr(io.StringIO()):
                got = sw.receipt_step(c, limit=1, now=now + 60)
            check(kind + ': replacement rejected before joins', (got, joins.call_count, row(c), keys(c), waits(c)), ((0, 0), 0, before, before_keys, 1))
            put(rp, saved); os.utime(rp, (old,) * 2); put(rp[:-5] + '.view', view)
            check(kind + ': original recovery ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
            check(kind + ': recovery preserves binding and keys', (row(c), keys(c)), (dict(before, angles='OK', angles_reason=angle_reason(rc, rp)), before_keys))
        finally:
            restore_game(rc)


def case_io_races_and_fairness():
    for failure in ('tail', 'view', 'vanish', 'drift'):
        s, sw, c, rp, _pub, now, _old, rc, rec, view, path, _hid = setup('20261006-000405-0')
        try:
            before, before_keys = row(c), keys(c)
            put(path, rec.encode('utf-8'))
            hints = sw.receipt_rec_runids; real_open = builtins.open

            class TailError:
                def __init__(self, fh): self.fh = fh
                def __enter__(self): return self
                def __exit__(self, *args): return self.fh.__exit__(*args)
                def __iter__(self): return iter(self.fh)
                def __getattr__(self, attr): return getattr(self.fh, attr)
                def read(self, *args): raise OSError(5, 'Input/output error')

            def failed_open(p, *args, **kwargs):
                if failure == 'view' and p == rp[:-5] + '.view': raise OSError(5, 'Input/output error')
                fh = real_open(p, *args, **kwargs)
                return TailError(fh) if failure == 'tail' and p == path else fh

            def vanished(mapname):
                got = hints(mapname)
                if failure == 'vanish': os.remove(path)
                if failure == 'drift': put(path, rec.replace('runid 20261006-000405-0', 'runid 20261006-000499-0').encode('utf-8'))
                return got

            with mock.patch.object(sw, 'receipt_rec_runids', side_effect=vanished), \
                    mock.patch('builtins.open', side_effect=failed_open), contextlib.redirect_stderr(io.StringIO()):
                got = sw.receipt_step(c, limit=1, now=now + 60)
            check(failure + ': unmeasured read keeps history and readiness', (got, row(c), keys(c), waits(c)), ((0, 0), before, before_keys, 1))
            put(path, rec.encode('utf-8'))
            check(failure + ': recovery ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
            check(failure + ': pair measured and readiness retired', (row(c), waits(c)), (dict(before, angles='OK', angles_reason=angle_reason(rc, rp)), 0))
        finally:
            restore_game(rc)
    s, sw, c, rp, _pub, now, old, rc, rec, view, path, hid = setup('20261006-000406-0', missing_view=True)
    try:
        # All sources co-ready; rec has a persistent selected-tail error.
        put(path, rec.encode('utf-8')); put(rp[:-5] + '.view', view); put(rp[:-5] + '.hid', hid)
        suite.make_receipt(s.EVIDENCE_DIR, '20261006-000407-0', age=old)
        calls = []; real_read = sw.read_receipt; real_open = builtins.open

        def trace(p, **kw):
            calls.append((os.path.basename(p), kw.get('rec_only'), kw.get('view_only'), kw.get('journal_only')))
            return real_read(p, **kw)

        def eio(p, *args, **kwargs):
            fh = real_open(p, *args, **kwargs)
            return TailError(fh) if p == path else fh

        per_pass = []
        with mock.patch.object(sw, 'read_receipt', side_effect=trace), mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
            for turn in range(8):
                before = len(calls); sw.receipt_step(c, limit=1, now=now + 60 + turn); per_pass.append(len(calls) - before)
        check('fairness: every pass respects one attempt cap', per_pass, [1] * 8)
        check('fairness: rec, view and independent HID actually attempted', {v[1:] for v in calls if v[0] == os.path.basename(rp)}, {(True, False, False), (False, True, False), (False, False, True)})
        check('fairness: healthy fresh receipt and HID progressed', (c.execute("SELECT COUNT(*) FROM receipts WHERE runid='20261006-000407-0'").fetchone()[0], row(c)['journal']), (1, 'OK'))
        check('fairness: pair readiness retained', (waits(c), waits(c, 'view')), (2, 1))
        check('fairness: error removal ACTS', sw.receipt_step(c, now=now + 180), (1, 0))
        check('fairness: pair resolved without losing HID', (row(c)['angles'], row(c)['journal']), ('OK', 'OK'))
    finally:
        restore_game(rc)


def case_completed_and_unknown_rec_not_rearmed():
    for kind in ('completed', 'unknown'):
        rid = '20261006-000410-0'
        if kind == 'completed':
            s, sw, c, rp, _pub, now, _old, rc, view = view_setup(rid)
            path = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', rid + '.rec')
            rec = open(path, encoding='utf-8').read(); os.remove(path)
        else:
            s, sw, c, rp, _pub, now, _old, rc, rec, view, path, _hid = setup(rid, missing_view=True)
            # Pre-slice captured view absence says nothing about rec absence.
            c.execute("DELETE FROM sweepmeta WHERE k GLOB 'receipt_rec_wait:*'"); c.commit()
        try:
            before, before_keys = row(c), keys(c)
            put(rp[:-5] + '.view', view)
            check(kind + ': late view without rec ACTS', sw.receipt_step(c, now=now + 60), (1, 0))
            check(kind + ': late view cannot invent rec readiness', (row(c), keys(c), waits(c), waits(c, 'view')), (before, before_keys, 0, 0))
            put(path, rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1).encode('utf-8'))
            control(rc, rp, 'OK', fault=True)
            with mock.patch.object(rc, 'join_rec', wraps=rc.join_rec) as joins:
                got = sw.receipt_step(c, now=now + 120)
            check(kind + ': completed/unknown rec replacement not auto-scheduled', (got, joins.call_count, row(c), keys(c)), ((0, 0), 0, before, before_keys))
            sw.mark_receipts_stale(c)
            check(kind + ': explicit full reread contradiction CONTROL ACTS', sw.receipt_step(c, now=now + 180), (1, 1))
        finally:
            restore_game(rc)


def case_partial_fault_and_scan_io():
    s, sw, c, rp, _pub, now, _old, rc, rec, view, path, _hid = setup('20261006-000409-0')
    try:
        before, before_keys = row(c), keys(c)
        bad = rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1)
        put(path, bad.encode('utf-8'))
        real_open = builtins.open

        def view_eio(p, *args, **kwargs):
            if p == rp[:-5] + '.view': raise OSError(5, 'Input/output error')
            return real_open(p, *args, **kwargs)

        r = rc.read(rp); rc.join_rec(r)
        check('partial fault: independent nonce contradiction ACTS', bool(r.faults), True)
        with mock.patch('builtins.open', side_effect=view_eio), contextlib.redirect_stderr(io.StringIO()):
            got = sw.receipt_step(c, now=now + 60)
        expected = dict(before, verdict='FAULT', reason=r.faults[0][:300])
        check('partial fault: only measured nonce fault moves', (got, row(c), keys(c), waits(c)), ((1, 1), expected, before_keys, 1))
        # Lose the contradiction and prune the view before completing this read.
        put(path, rec.encode('utf-8')); os.remove(rp[:-5] + '.view')
        unrelated = os.path.join(os.path.dirname(path), 'unrelated.rec')
        put(unrelated, b'FTESURF-REC 9\nrunid 20261006-000499-0\nbegin\n')

        def scan_eio(p, *args, **kwargs):
            if p == unrelated: raise OSError(5, 'Input/output error')
            return real_open(p, *args, **kwargs)

        with mock.patch('builtins.open', side_effect=scan_eio):
            got = sw.receipt_step(c, now=now + 120)
        check('partial fault: unrelated scan I/O cannot block matching nonce recovery', got, (1, 0))
        check('partial fault: history preserved, no guessed pair or sighting', (row(c), keys(c), waits(c)), (expected, before_keys, 0))
    finally:
        restore_game(rc)


def case_readiness_and_capture():
    for kind in ('unknown', 'identity', 'loss', 'incomplete', 'captured', 'partial', 'hints'):
        s, sw, c, rp, _pub, now, old, rc, rec, view, path, _hid = setup('20261006-000408-0')
        try:
            if kind == 'unknown': c.execute("DELETE FROM sweepmeta WHERE k GLOB 'receipt_rec_wait:*'")
            if kind == 'identity': c.execute("UPDATE receipts SET identity='' ")
            c.commit(); before = row(c)
            if kind == 'loss': os.remove(rp)
            if kind in ('captured', 'partial'):
                sw.mark_receipts_stale(c); joined = rc.join_uploaded

                def arrive_after_capture(r, want):
                    joined(r, want)
                    if kind == 'partial': r.ioerror = True
                    put(path, rec.encode('utf-8'))

                # Do not let previous readiness obscure the measured capture.
                c.execute("DELETE FROM sweepmeta WHERE k GLOB 'receipt_rec_wait:*'"); c.commit()
                with mock.patch.object(rc, 'join_uploaded', side_effect=arrive_after_capture):
                    got = sw.receipt_step(c, now=now + 60)
                check(kind + ': readiness based on completed read, not late stat', (got, waits(c)), ((int(kind == 'captured'), 0), int(kind == 'captured')))
                if kind == 'captured':
                    check('captured: next pass consumes late pair', sw.receipt_step(c, now=now + 120), (1, 0))
                continue
            put(path, rec.encode('utf-8'))
            if kind == 'hints':
                os.rename(path, path + '.part')
                os.mkdir(path)
                put(os.path.join(os.path.dirname(path), 'wrong.rec'), rec.replace('runid 20261006-000408-0', 'runid 20261006-000499-0').encode('utf-8'))
            ctx = mock.patch.object(sw.os, 'scandir', side_effect=OSError('unreadable')) if kind == 'incomplete' else contextlib.nullcontext()
            with ctx, mock.patch.object(rc, 'read', wraps=rc.read) as reads, contextlib.redirect_stderr(io.StringIO()):
                got = sw.receipt_step(c, now=now + 60)
            check(kind + ': no guessed historical observation', (got, reads.call_count, row(c)), ((0, 0), 0, before))
            check(kind + ': loss cleanup only after complete listing', waits(c), 0 if kind in ('unknown', 'loss') else 1)
            if kind == 'incomplete': check('incomplete: listing restoration ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
            if kind in ('unknown', 'identity'):
                os.remove(path); sw.mark_receipts_stale(c)
                check(kind + ': explicit missing observation ACTS', sw.receipt_step(c, now=now + 120), (1, 0))
                put(path, rec.encode('utf-8'))
                check(kind + ': newly captured readiness ACTS', sw.receipt_step(c, now=now + 180), (1, 0))
        finally:
            restore_game(rc)


def main():
    for case in (case_outcomes, case_arrival_order_and_locations, case_history_and_missing_view,
                 case_identity, case_io_races_and_fairness, case_completed_and_unknown_rec_not_rearmed,
                 case_partial_fault_and_scan_io, case_readiness_and_capture):
        print(case.__name__ + ':')
        try: case()
        except Exception as exc: check(case.__name__ + ' ran to completion', '%s: %s' % (type(exc).__name__, exc), 'no exception')
    print('\n%d failed' % len(suite.FAILED))
    return int(bool(suite.FAILED))


if __name__ == '__main__':
    sys.exit(main())
