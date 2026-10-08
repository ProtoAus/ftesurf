#!/usr/bin/env python3
"""Mutate the actual acting gallery evidence; refuse a non-green input rig."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from PIL import Image
from p598imgui import grade, ROOT


class Mutations(unittest.TestCase):
    rig = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p595-grader-',dir=ROOT/'rig')
        self.copy = Path(self.temp.name)/'rig'
        shutil.copytree(self.rig,self.copy,ignore=shutil.ignore_patterns('*.exe','*.dll','*.o'))

    def tearDown(self):
        self.temp.cleanup()

    def mutate_log(self, old, new):
        p = next((self.copy/'scale1/ftesurf/logs').glob('imgui*.log'))
        text = p.read_text(errors='replace')
        self.assertIn(old,text)
        p.write_text(text.replace(old,new))

    def pixel(self, xy, color):
        p = next((self.copy/'scale1/ftesurf/screenshots').glob('menu.*'))
        im = Image.open(p).convert('RGB'); im.putpixel(xy,color); im.save(p)

    def reject(self):
        self.assertTrue(grade(self.copy),'mutant was incorrectly accepted')

    def test_baseline(self): self.assertEqual([],grade(self.copy))
    def test_native_not_acted(self): self.mutate_log('native=1','native=0'); self.reject()
    def test_finish_absent(self): self.mutate_log('P595 FINISHED','REMOVED'); self.reject()
    def test_lost_after(self): self.pixel((230,180),(0,255,0)); self.reject()
    def test_inherited_clip(self): self.pixel((575,100),(0,255,0)); self.reject()
    def test_state_leak(self): self.pixel((600,110),(255,0,255)); self.reject()
    def test_missing_glyphs(self):
        p = next((self.copy/'scale1/ftesurf/screenshots').glob('menu.*'))
        im = Image.open(p).convert('RGB'); im.paste((30,20,20),(62,78,410,91)); im.save(p); self.reject()
    def test_no_rounding(self): self.pixel((197,95),(44,68,108)); self.reject()
    def test_scale_mismatch(self): self.pixel((80,350),(255,255,255)); self.reject()
    def test_wrong_exit(self):
        p=self.copy/'report.json'; report=json.loads(p.read_text()); report['arms']['scale1']['exit']=1
        p.write_text(json.dumps(report)); self.reject()
    def test_context_witness_absent(self): self.mutate_log('live=2','live=1'); self.reject()
    def test_renderer_cleanup_absent(self): self.mutate_log('renderer=1','renderer=0'); self.reject()
    def test_closed_work(self):
        p=next((self.copy/'scale1/ftesurf/logs').glob('imgui*.log')); lines=p.read_text().splitlines()
        n=[i for i,l in enumerate(lines) if 'UIIMGUI STATUS' in l][-1]
        lines[n]=lines[n].replace('live=0','live=1'); p.write_text('\n'.join(lines)); self.reject()
    def test_file_leak(self): (self.copy/'scale1/imgui.ini').write_text('leaked'); self.reject()
    def test_missing_screenshot(self):
        next((self.copy/'scale1/ftesurf/screenshots').glob('menu.*')).unlink(); self.reject()
    def test_submission_rejected(self): self.mutate_log('rejected=0','rejected=1'); self.reject()


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('rig',type=Path); a=p.parse_args()
    errors=grade(a.rig)
    if errors: raise SystemExit('Input rig is not green: '+repr(errors))
    Mutations.rig=a.rig
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Mutations))
    raise SystemExit(not result.wasSuccessful())
