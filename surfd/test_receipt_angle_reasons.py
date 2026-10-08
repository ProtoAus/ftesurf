#!/usr/bin/env python3
"""Angle explanation observations, using signed temporary evidence, never live data.

Control: run this against the pre-change tree; a real pair is judged but its
explanation is lost. All verdicts/measurements still come from existing readers.
"""
import builtins
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from unittest import mock

import test_sweep as suite
from test_receipt_late_view import row, keys, restore_game, put

check = suite.check


def setup(kind='OK'):
    s, sw, runs = suite.fresh()
    sw.TOOLS = suite.TOOLS
    c = s.connect()
    now = int(time.time())
    rid = '20261006-000511-0'
    if suite.TOOLS not in sys.path:
        sys.path.insert(0, suite.TOOLS)
    import test_reccheck as fx
    lines = fx.build(packets=80 if kind == 'short' else 400, sweep=128,
                     ver=8 if kind == 'legacy' else 9)
    lines = [('runid ' + rid) if l.startswith('runid ') else l for l in lines]
    if kind == 'epoch':
        lines.insert(next(i for i, l in enumerate(lines) if l.startswith('in ')),
                     'resume 20260101-000000-0')
    view = '\n'.join(fx.view_for(lines, rot=0.5 if kind == 'FAULT' else 0,
                                dense=2 if kind == 'partial' else 1,
                                dense_lo=0.5)) + '\n'
    if kind == 'malformed':
        view = 'FTESURF-VIEW 2\nmap bhop_eazy\nhid 1\nbegin\n'
    rc = suite.with_rec(s, sw, rid, '\n'.join(lines) + '\n')
    rp, _ = suite.make_receipt(s.EVIDENCE_DIR, rid, view=view.encode(),
                               hid=suite._journal_text().encode(),
                               age=now - 2 * s.EVIDENCE_SETTLE)
    if kind == 'digest':
        put(rp[:-5] + '.view', b'not the signed view\n')
    return s, sw, c, now, rc, rp


def observed(rc, rp):
    r = rc.read(rp)
    rc.join_rec(r);rc.join_ticks(r);rc.join_uploaded(r, {});rc.join_angles(r, {})
    return r


def case_real_observations():
    for kind, verdict, phrase in (
            ('OK', 'OK', 'moves held one frame'),
            ('legacy', 'BLIND', 'in rows (.v_angle, pre-v9)'),
            ('epoch', 'BLIND', 'joined across a resume'),
            ('short', 'BLIND', 'under the 100 it needs'),
            ('partial', 'BLIND', 'PARTIAL COVER'),
            ('FAULT', 'FAULT', 'moves held one frame'),
            ('digest', 'FAULT', 'not the sidecar the receipt signed'),
            ('malformed', 'FAULT', 'no frames')):
        _s, sw, c, now, rc, rp = setup(kind)
        try:
            ctl = observed(rc, rp)
            check(kind + ': independent reader ACTS', (ctl.angles, bool(ctl.faults)),
                  (verdict, verdict == 'FAULT'))
            check(kind + ': reader detail names the measurement/abstention', phrase in ctl.angles_detail, True)
            check(kind + ': full sweep ACTS', sw.receipt_step(c, now=now), (1, int(verdict == 'FAULT')))
            stored = row(c)
            check(kind + ': measured verdict AND bounded detail persisted',
                  (stored['angles'], stored.get('angles_reason')), (verdict, ctl.angles_detail[:1000]))
            check(kind + ': signature/fault semantics unchanged',
                  (stored['verdict'], stored['reason']),
                  ('FAULT' if ctl.faults else 'VALID', ctl.faults[0][:300] if ctl.faults else ''))
            before_keys = keys(c)
            with mock.patch.object(rc, 'read', wraps=rc.read) as reads:
                got = sw.receipt_step(c, now=now + 60)
            check(kind + ': completed history never reconstructed', (got, reads.call_count, row(c), keys(c)),
                  ((0, 0), 0, stored, before_keys))
        finally:
            restore_game(rc)


def case_migration():
    s, _sw, _runs = suite.fresh()
    c = s.connect()
    if 'angles_reason' in {r[1] for r in c.execute('PRAGMA table_info(receipts)')}:
        c.execute('ALTER TABLE receipts DROP COLUMN angles_reason')
    c.execute("INSERT INTO receipts(runid,map,pub,verdict,angles,reason,at,sig,signed_at,stale,journal,journal_reason,identity)"
              " VALUES('old','map','key','FAULT','FAULT','old fault',123,'signature',45,0,'OK','old journal','captured')")
    c.execute("INSERT INTO sweepmeta(k,v) VALUES('receipt_view_wait:old',1)")
    c.commit()
    old = row(c); metadata = list(c.execute('SELECT * FROM sweepmeta'))
    c.close()
    for iteration in range(2):
        c = s.connect()
        s.receipts_v8(c)
        check('migration %d: empty detail, all old history preserved' % iteration, row(c), dict(old, angles_reason=''))
        check('migration %d: no scheduling metadata rewritten' % iteration,
              [tuple(r) for r in c.execute('SELECT * FROM sweepmeta')], [tuple(r) for r in metadata])
        c.close()


def case_partial_history():
    for kind in ('OK', 'FAULT', 'legacy'):
        _s, sw, c, now, rc, rp = setup(kind)
        try:
            check(kind + ': history CONTROL ACTS', sw.receipt_step(c, now=now), (1, int(kind == 'FAULT')))
            before = row(c)
            sw.mark_receipts_stale(c)
            recpath = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', '20261006-000511-0.rec')
            saved_rec = open(recpath, encoding='utf-8').read()
            put(recpath, saved_rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1).encode())
            real_open = builtins.open

            def eio(path, *args, **kwargs):
                if path == rp[:-5] + '.hid':
                    raise OSError(5, 'Input/output error')
                return real_open(path, *args, **kwargs)

            with mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
                check(kind + ': partial explicit reread ACTS with independent fault',
                      sw.receipt_step(c, now=now + 60), (1, int(kind != 'FAULT')))
            partial = row(c)
            check(kind + ': partial reread preserves angle pair',
                  (partial['angles'], partial.get('angles_reason')), (before['angles'], before.get('angles_reason')))
            rec = saved_rec
            if kind == 'FAULT':
                # Repair the recording to match the still-signed rotated view.
                # A retry must preserve history even when the new pair is OK.
                lines = []
                for line in rec.splitlines():
                    if line.startswith('in '):
                        fields = line.split();fields[8] = str(float(fields[8]) + 0.5)
                        line = ' '.join(fields)
                    lines.append(line)
                rec = '\n'.join(lines) + '\n'
            put(recpath, rec.encode())
            ctl = observed(rc, rp)
            check(kind + ': repaired reader CONTROL ACTS', (ctl.angles, bool(ctl.faults)),
                  ('BLIND' if kind == 'legacy' else 'OK', False))
            check(kind + ': recovery full read ACTS (historical fault still counted)',
                  sw.receipt_step(c, now=now + 120), (1, 1))
            recovered = row(c)
            wanted = (before['angles'], before.get('angles_reason')) if kind == 'FAULT' else (ctl.angles, ctl.angles_detail[:1000])
            check(kind + ': recovery keeps FAULT detail or installs newly judged pair',
                  (recovered['angles'], recovered.get('angles_reason')), wanted)
            # Operator-initiated completed reread is allowed to replace both.
            if kind == 'FAULT':
                sw.mark_receipts_stale(c)
                check('explicit: completed reread ACTS', sw.receipt_step(c, now=now + 180), (1, 0))
                check('explicit: verdict AND detail replaced together',
                      (row(c)['angles'], row(c).get('angles_reason')), (ctl.angles, ctl.angles_detail[:1000]))
        finally:
            restore_game(rc)


def case_initial_partial_and_bound():
    _s, sw, c, now, rc, rp = setup('OK')
    try:
        path = os.path.join(rc.GAME, 'data', 'evidence', 'bhop_eazy', '20261006-000511-0.rec')
        rec = open(path, encoding='utf-8').read()
        put(path, rec.replace('\nbegin', '\nnonce ' + '0' * 32 + '\nbegin', 1).encode())
        real_open = builtins.open

        def eio(p, *args, **kwargs):
            if p == rp[:-5] + '.hid':raise OSError(5, 'Input/output error')
            return real_open(p, *args, **kwargs)

        with mock.patch('builtins.open', side_effect=eio), contextlib.redirect_stderr(io.StringIO()):
            check('no history: partial read ACTS with independent fault', sw.receipt_step(c, now=now), (1, 1))
        check('no history: deferred angle verdict explains no measurement',
              (row(c)['angles'], row(c).get('angles_reason')),
              ('BLIND', 'angle check deferred after signed sibling I/O; no angle measurement'))
        put(path, rec.encode())
        ctl = observed(rc, rp)
        check('no history: automatic journal recovery ACTS', sw.receipt_step(c, now=now + 60), (1, 0))
        check('no history: journal-only retry does not invent an angle measurement',
              (row(c)['angles'], row(c).get('angles_reason'), row(c)['journal']),
              ('BLIND', 'angle check deferred after signed sibling I/O; no angle measurement', 'OK'))
        sw.mark_receipts_stale(c)
        check('no history: explicit full reread ACTS', sw.receipt_step(c, now=now + 90), (1, 0))
        check('no history: completed full read replaces deferred pair together',
              (row(c)['angles'], row(c).get('angles_reason')), ('OK', ctl.angles_detail[:1000]))
        sw.mark_receipts_stale(c)
        real_join = rc.join_angles

        def large_detail(r, want):
            real_join(r, want)
            r.angles_detail = 'measured detail ' + 'x' * 2000

        with mock.patch.object(rc, 'join_angles', side_effect=large_detail):
            check('bound: reader CONTROL supplies oversized diagnostic', sw.receipt_step(c, now=now + 120), (1, 0))
        check('bound: diagnostic capped, verdict unchanged',
              (row(c)['angles'], row(c).get('angles_reason')), ('OK', ('measured detail ' + 'x' * 2000)[:1000]))
    finally:
        restore_game(rc)


def case_journal_only():
    _s, sw, c, now, rc, rp = setup('legacy')
    try:
        hid = open(rp[:-5] + '.hid', 'rb').read()
        os.remove(rp[:-5] + '.hid')
        check('journal-only: initial read ACTS', sw.receipt_step(c, now=now), (1, 0))
        before = row(c)
        put(rp[:-5] + '.hid', hid)
        with mock.patch.object(rc, 'join_angles', wraps=rc.join_angles) as angles:
            got = sw.receipt_step(c, now=now + 60)
        check('journal-only: journal read ACTS without angle reinterpretation', (got, angles.call_count, row(c)['journal']),
              ((1, 0), 0, 'OK'))
        check('journal-only: exact prior angle pair survives',
              (row(c)['angles'], row(c).get('angles_reason')), (before['angles'], before.get('angles_reason')))
    finally:
        restore_game(rc)


def case_render_text():
    template = os.path.join(os.path.dirname(__file__), 'templates', 'admin_run.html')
    text = open(template, encoding='utf-8').read()
    block = text[text.index('  const card = document.getElementById("rcptcard");'):text.index('  renderKey(j);')]
    helpers = text[text.index('function renderReceiptAssociations('):text.index('function renderRun(')]
    harness = helpers + r'''
const j = {receipt: JSON.parse(process.argv[2])};
class Element {
  constructor(tag, cls, text) { this.tag=tag; this.text=text || ''; this.children=[]; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children=[]; }
  set innerHTML(value) { throw new Error('untrusted HTML assignment'); }
}
const nodes={rcptcard:new Element('div'), rcpt:new Element('dl')};
const document={getElementById: id=>nodes[id]};
const el=(tag,cls,text)=>new Element(tag,cls,text);
const pill=(text,cls)=>el('span',cls,text);
const RCPT_CLS={}, ANG_CLS={}, JRN_CLS={};
const fmtDate=()=> 'date';
let summary;
const summarise=(id, bad)=>{summary=bad;};
'''
    harness += block + r'''
const flatten=n=>n.text+n.children.map(flatten).join('');
const fields={};
for(let i=0;i<nodes.rcpt.children.length;i+=2)
  fields[flatten(nodes.rcpt.children[i])]=flatten(nodes.rcpt.children[i+1]);
console.log(JSON.stringify({fields, summary}));
'''
    import tempfile
    with tempfile.TemporaryDirectory(prefix='angle-dom-') as tmp:
        path = os.path.join(tmp, 'render.js')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(harness)
        for angles, reason, wanted in (
                ('BLIND', '<img src=x onerror=alert(1)> & <script>bad</script>', '<img src=x onerror=alert(1)> & <script>bad</script>'),
                ('BLIND', '', 'detail unavailable (historical observation)'),
                ('FAULT', 'a measured fault', 'a measured fault'),
                ('OK', 'a measurement', 'a measurement'),
                ('', '', None)):
            receipt = dict(angles=angles, angles_reason=reason, verdict='VALID', pub='key', at=1,
                           journal='', journal_reason='', reason='', identity_bound=True)
            result = subprocess.run(['node', path, json.dumps(receipt)], capture_output=True, text=True)
            check('DOM ' + (angles or 'unchecked') + ': actual receipt renderer ACTS', result.returncode, 0)
            if result.returncode:
                continue
            output = json.loads(result.stdout)
            check('DOM: explanation/fallback rendered literally', output['fields'].get('angles says'), wanted)
            check('DOM: explanation does not affect existing summary', output['summary'], angles == 'FAULT')
            if not angles:
                check('DOM: unchecked does not invent missing recording', output['fields']['angles'], 'not checked by this sweep')


def main():
    cases = [case_real_observations, case_migration, case_partial_history,
             case_initial_partial_and_bound, case_journal_only]
    if shutil.which('node'):
        cases.append(case_render_text)
    else:
        print('SKIP DOM: Node unavailable; running Python storage/migration controls only')
    for case in cases:
        try:
            case()
        except Exception as exc:
            check(case.__name__ + ' completed', '%s: %s' % (type(exc).__name__, exc), 'no exception')
    print('\n%d failed' % len(suite.FAILED))
    return 1 if suite.FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
