#!/usr/bin/env python3
"""The soak reader must reject quiet, short, leaking and mis-counted runs. Read-only on the rig."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

from p603soak import PAIR_BOUND, grade, warm


class SoakControls(unittest.TestCase):
    rig = out = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='soak-reader-', dir=self.out)
        self.addCleanup(self.tmp.cleanup); self.copy = Path(self.tmp.name)
        shutil.copy2(self.rig / 'report.json', self.copy / 'report.json')
        for arm in json.loads((self.copy / 'report.json').read_text())['arms']:
            game = self.copy / arm / 'ftesurf'; game.mkdir(parents=True)
            for name in ('logs', 'screenshots'): shutil.copytree(self.rig / arm / 'ftesurf' / name, game / name)
        self.log = self.copy / 'native/ftesurf/logs/perf.log'

    def rejected(self, word):
        errors = grade(self.copy)[0]
        self.assertTrue(any(word in e for e in errors), errors)
    def sub(self, pattern, repl):
        text, n = re.subn(pattern, repl, self.log.read_text(errors='replace'), count=1, flags=re.S)
        self.assertEqual(n, 1); self.log.write_text(text)
    def report(self, fn):
        p = self.copy / 'report.json'; r = json.loads(p.read_text()); fn(r); p.write_text(json.dumps(r))

    def test_acting(self): self.assertEqual(grade(self.copy)[0], [])
    def test_quiet(self): self.log.write_text('P603 SOAK FINISHED\n'); self.rejected('incomplete/quiet')
    def test_failed_exit(self): self.report(lambda r: r['arms']['native'].update(returncode=1)); self.rejected('failed exit')
    def test_missing_arm(self): self.report(lambda r: r['arms'].pop('legacy')); self.rejected('arm set differs')
    def test_wrong_backend(self): self.sub('OpenGL renderer initialized', 'automatic fallback'); self.rejected('GL backend')
    def test_instrumented(self): self.sub('P603 SOAK BASE', 'P603 CAP model=1\nP603 SOAK BASE'); self.rejected('instrumented')
    def test_missing_cycle(self): self.sub(r'P603 SOAK CYCLE 40\b', 'P603 SOAK GONE 40'); self.rejected('cycle 40 counters missing')
    def test_native_never_opened(self):
        self.sub(r'(P603 SOAK OPEN 40\b.*?UIIMGUI STATUS [^\r\n]*?)live=1', r'\1live=0'); self.rejected('cycle 40: table did not open')
    def test_owner_left_open(self):
        self.sub(r'(P603 SOAK CYCLE 40\b.*?UIIMGUI STATUS [^\r\n]*?)live=0', r'\1live=1'); self.rejected('cycle 40: not released')
    def test_extra_upload(self):
        self.sub(r'(P603 SOAK CYCLE 40\b.*?UIIMGUI STATUS [^\r\n]*?uploads=)(\d+)', lambda m: m[1] + str(int(m[2]) + 1))
        self.rejected('cycle 40: opens/uploads')
    def test_rejected_draw(self):
        self.sub(r'(P603 SOAK CYCLE 40\b.*?UIIMGUI STATUS [^\r\n]*?)rejected=0', r'\1rejected=1'); self.rejected('cycle 40: rejected')
    def test_hold_reupload(self):
        self.sub(r'(P603 SOAK HOLDEND\b.*?UIIMGUI STATUS [^\r\n]*?uploads=)(\d+)', lambda m: m[1] + str(int(m[2]) + 1))
        self.rejected('hold: reopened/reuploaded')
    def test_hold_missing_dump(self): self.sub(r'P603 PERF SAMPLE 0 hold 5\b', 'NO SAMPLE'); self.rejected('hold CPU dumps')
    def test_hold_drift(self):
        # Double every QC UpdateView figure in the last third of the hold.
        text = self.log.read_text(errors='replace')
        hold = json.loads((self.copy / 'report.json').read_text())['hold']
        head, sep, tail = text.partition(f'P603 PERF SAMPLE 0 hold {hold - hold // 3}')
        self.assertTrue(sep)
        tail, n = re.subn(r'(\d+\.\d+)(\s+QC UpdateView)', lambda m: f'{float(m[1]) * 2:.2f}{m[2]}', tail)
        self.assertEqual(n, hold // 3); self.log.write_text(head + sep + tail); self.rejected('hold: QC UpdateView drifted')
    def test_missing_memory(self):
        def drop(r):
            mem = r['arms']['native']['memory']
            mem.remove(next(m for m in mem if m['kind'] == 'CYCLE' and m['n'] == warm(r['cycles']) + 5))
        self.report(drop); self.rejected('memory')
    def test_synthetic_leak(self):
        # A steady per-cycle leak sized to raise the floor by twice the bound across the run.
        def leak(r):
            step = 3 * PAIR_BOUND // r['cycles']
            for m in r['arms']['native']['memory']:
                if m['kind'] == 'CYCLE': m['private_bytes'] += m['n'] * step
        self.report(leak); self.rejected('native: cycle floor rises')
    def test_sawtooth_is_not_a_leak(self):
        # Teeth far taller than the bound that return to the same floor must not read as growth.
        def teeth(r):
            for arm in ('native', 'legacy'):
                for m in r['arms'][arm]['memory']: m['private_bytes'] = (300 << 20) + (m['n'] % 40) * (8 << 20)
        self.report(teeth)
        self.assertFalse([e for e in grade(self.copy)[0] if 'floor rises' in e])
    def test_leak_arm_must_fail(self):
        # A leak arm whose memory is as flat as native's proves the statistic cannot see a leak.
        def flat(r):
            if 'leak' in r['arms']: r['arms']['leak']['memory'] = r['arms']['native']['memory']
        self.report(flat)
        if 'leak' in json.loads((self.copy / 'report.json').read_text())['arms']: self.rejected('does not discriminate')


if __name__ == '__main__':
    if len(sys.argv) < 2: raise SystemExit('usage: test_p603soak_unit.py <retained soak rig>')
    SoakControls.rig = Path(sys.argv.pop(1)).resolve()
    SoakControls.out = SoakControls.rig.parent
    before = {p: p.stat().st_mtime_ns for p in SoakControls.rig.rglob('*') if p.is_file()}
    program = unittest.main(exit=False)
    after = {p: p.stat().st_mtime_ns for p in SoakControls.rig.rglob('*') if p.is_file()}
    if before != after: raise SystemExit('reader controls changed the retained rig')
    raise SystemExit(not program.result.wasSuccessful())
