#!/usr/bin/env python3
"""Mutate acting runtime evidence; a quiet native/legacy arm must never pass."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from PIL import Image
from p600input import grade, ROOT


class Controls(unittest.TestCase):
    rig = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p599-grade-',dir=ROOT/'rig')
        self.copy = Path(self.temp.name)/'rig'
        shutil.copytree(self.rig,self.copy,ignore=shutil.ignore_patterns('*.exe','*.dll','*.o'))

    def tearDown(self):
        self.temp.cleanup()

    def log(self, old, new, arm='scale1'):
        p = next((self.copy/arm/'ftesurf/logs').glob('input*.log'))
        text = p.read_text(); self.assertIn(old,text); p.write_text(text.replace(old,new))

    def reject(self):
        self.assertTrue(grade(self.copy),'false success accepted')

    def test_baseline(self): self.assertEqual([],grade(self.copy))
    def test_actions_absent(self): self.log('P599 ACTION','MISSING ACTION'); self.reject()
    def test_wrong_value(self): self.log('value=2','value=9'); self.reject()
    def test_zero_generation(self):
        import re
        p = next((self.copy/'scale1/ftesurf/logs').glob('input*.log'))
        p.write_text(re.sub(r'generation=\d+','generation=0',p.read_text())); self.reject()
    def test_duplicate_action(self):
        p = next((self.copy/'scale1/ftesurf/logs').glob('input*.log'))
        text = p.read_text(); action = next(l for l in text.splitlines() if 'P599 ACTION' in l)
        p.write_text(text+'\n'+action); self.reject()
    def test_input_rejected(self): self.log('accepted=1','accepted=0'); self.reject()
    def test_legacy_no_activity(self): self.log('P599 INPUT','NO INPUT',arm='absent'); self.reject()
    def test_missing_capability_witness(self): self.log('P599 INIT','NO INIT'); self.reject()
    def test_finish_absent(self): self.log('P599 FINISHED','NO FINISH'); self.reject()
    def test_resource_leak(self):
        p = next((self.copy/'scale1/ftesurf/logs').glob('input*.log'))
        lines = p.read_text().splitlines(); n = [i for i,l in enumerate(lines) if 'UIIMGUI STATUS' in l][-1]
        lines[n] = lines[n].replace('live=0','live=1'); p.write_text('\n'.join(lines)); self.reject()
    def test_missing_renderer_cleanup(self): self.log('renderer=1','renderer=0'); self.reject()
    def test_visible_state_unchanged(self):
        root = self.copy/'scale1/ftesurf/screenshots'
        shutil.copy2(next(root.glob('menu_initial.*')),next(root.glob('menu_changed.*'))); self.reject()
    def test_clip_state_marker(self):
        p = next((self.copy/'scale1/ftesurf/screenshots').glob('menu_initial.*'))
        im = Image.open(p).convert('RGB'); im.putpixel((600,110),(255,0,255)); im.save(p); self.reject()
    def test_no_covering_fallback(self):
        p = next((self.copy/'drawonly/ftesurf/screenshots').glob('menu_initial.*'))
        im = Image.open(p).convert('RGB'); im.putpixel((400,220),(0,0,0)); im.save(p); self.reject()
    def test_missing_shot(self):
        next((self.copy/'scale1/ftesurf/screenshots').glob('menu_initial.*')).unlink(); self.reject()
    def test_side_effect_file(self): (self.copy/'scale1/imgui.ini').write_text('side effect'); self.reject()
    def test_wrong_exit(self):
        p = self.copy/'report.json'; report = json.loads(p.read_text()); report['arms']['scale1']['exit']=1
        p.write_text(json.dumps(report)); self.reject()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('rig',type=Path); a=p.parse_args()
    errors = grade(a.rig)
    if errors: raise SystemExit('Non-green source rig: '+repr(errors))
    Controls.rig = a.rig
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    raise SystemExit(not result.wasSuccessful())
