#!/usr/bin/env python3
"""Cost evidence needs acting rows, exact CPU samples, images, identities and counters."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

from p603perf import grade


class CostControls(unittest.TestCase):
    rig = out = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='perf-reader-', dir=self.out)
        self.addCleanup(self.tmp.cleanup); self.copy = Path(self.tmp.name)
        shutil.copy2(self.rig / 'report.json', self.copy / 'report.json')
        report = json.loads((self.copy / 'report.json').read_text())
        for arm in report['arms']:
            game = self.copy / arm / 'ftesurf'; game.mkdir(parents=True)
            for name in ('logs', 'screenshots'):
                shutil.copytree(self.rig / arm / 'ftesurf' / name, game / name)
            shutil.copy2(self.rig / arm / 'ftesurf/perf.cfg', game / 'perf.cfg')
        self.log = self.copy / 'native/ftesurf/logs/perf.log'

    def rejected(self): self.assertTrue(grade(self.copy))
    def replace(self, old, new):
        text = self.log.read_text(errors='replace'); self.assertIn(old, text)
        self.log.write_text(text.replace(old, new, 1))
    def report(self, fn):
        p = self.copy / 'report.json'; r = json.loads(p.read_text()); fn(r); p.write_text(json.dumps(r))

    def test_acting(self): self.assertEqual(grade(self.copy), [])
    def test_quiet(self): self.log.write_text('P603 PERF FINISHED\n'); self.rejected()
    def test_missing_sample(self): self.replace('P603 PERF SAMPLE 0 open 0', 'NO SAMPLE'); self.rejected()
    def test_duplicate_sample(self): self.replace('P603 PERF SAMPLE 0 open 0', 'P603 PERF SAMPLE 0 closed 0'); self.rejected()
    def test_missing_dump(self): self.replace('---- end r_speeds_dump ----', 'NO END'); self.rejected()
    def test_wrong_average(self): self.replace('100-frame average', '1-frame average'); self.rejected()
    def test_missing_cpu(self): self.replace('QC UpdateView', 'missing CPU'); self.rejected()
    def test_empty_cpu(self):
        text, n = re.subn(r'\d+\.\d+\s+QC UpdateView', '0.00 QC UpdateView', self.log.read_text(errors='replace'), count=1)
        self.assertEqual(n, 1); self.log.write_text(text); self.rejected()
    def test_wrong_rows(self): self.report(lambda r: r.update(rows=r['rows']+1)); self.rejected()
    def test_instrumented(self): self.replace('P603 PERF FINISHED', 'P603 CAP model=1\nP603 PERF FINISHED'); self.rejected()
    def test_wrong_backend(self): self.replace('OpenGL renderer initialized', 'automatic fallback'); self.rejected()
    def test_missing_arm(self): self.report(lambda r: r['arms'].pop('absent')); self.rejected()
    def test_missing_memory(self): self.report(lambda r: r['arms']['native']['memory'].pop()); self.rejected()
    def test_empty_memory(self): self.report(lambda r: r['arms']['native']['memory'][0].update(private_bytes=0)); self.rejected()
    def test_unequal_qc(self): self.report(lambda r: r['arms']['native'].update(csprogs_sha256='different')); self.rejected()
    def test_unequal_engine(self): self.report(lambda r: r['arms']['native'].update(engine_sha256='different')); self.rejected()
    def test_failed_exit(self): self.report(lambda r: r['arms']['native'].update(returncode=1)); self.rejected()
    def test_profile_config(self):
        p = self.copy / 'native/ftesurf/perf.cfg'; p.write_text(p.read_text().replace('pr_enable_profiling 0','pr_enable_profiling 1')); self.rejected()
    def test_closed_work(self):
        text, n = re.subn(r'(P603 PERF BEGIN 0 closed\b.*?UIIMGUI STATUS [^\r\n]*?)frames=0', r'\1frames=1', self.log.read_text(errors='replace'), count=1, flags=re.S)
        self.assertEqual(n, 1); self.log.write_text(text); self.rejected()
    def test_native_inert(self):
        self.log.write_text(self.log.read_text(errors='replace').replace('live=1','live=0')); self.rejected()
    def test_missing_screenshot(self):
        next((self.copy / 'native/ftesurf/screenshots').glob('perf_0_open.*')).unlink(); self.rejected()
    def test_quiet_legacy_image(self):
        game = self.copy / 'legacy/ftesurf/screenshots'; shutil.copy2(game / 'perf_0_closed.png', game / 'perf_0_open.png'); self.rejected()
    def test_swapped_route(self):
        dest = self.copy / 'native/ftesurf/screenshots/perf_0_open.png'
        shutil.copy2(self.copy / 'legacy/ftesurf/screenshots/perf_0_open.png', dest); self.rejected()


if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('usage: test_p603perf_unit.py <rig> <owned-output-dir>')
    CostControls.out = Path(sys.argv.pop()).resolve(); CostControls.rig = Path(sys.argv.pop()).resolve()
    if not CostControls.out.is_dir(): raise SystemExit('owned output dir must exist')
    unittest.main()
