#!/usr/bin/env python3
"""Mutate acting model evidence: quiet/stale/retargeted results cannot pass."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from PIL import Image
from p601model import grade, ROOT


class Controls(unittest.TestCase):
    rig = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p601-grade-',dir=ROOT/'rig')
        self.copy = Path(self.temp.name)/'rig'
        shutil.copytree(self.rig,self.copy,ignore=shutil.ignore_patterns('*.exe','*.dll','*.o'))

    def tearDown(self): self.temp.cleanup()

    def log(self,old,new,arm='scale1'):
        p=next((self.copy/arm/'ftesurf/logs').glob('input*.log'))
        text=p.read_text(); self.assertIn(old,text); p.write_text(text.replace(old,new))

    def reject(self): self.assertTrue(grade(self.copy),'false success accepted')
    def test_acting_baseline(self): self.assertEqual([],grade(self.copy))
    def test_quiet_actions(self): self.log('P601 ACTION','NO ACTION'); self.reject()
    def test_quiet_models(self): self.log('P601 MODEL','NO MODEL'); self.reject()
    def test_wrong_revision(self): self.log('value=1 revision=3','value=1 revision=2'); self.reject()
    def test_wrong_row(self): self.log('id=21 row=191','id=21 row=91'); self.reject()
    def test_offset_not_identity(self): self.log('id=11 row=91','id=1 row=91'); self.reject()
    def test_wrong_value(self): self.log('value=1 revision=4','value=2 revision=4'); self.reject()
    def test_partial_model(self): self.log('count=3 committed=1','count=2 committed=1'); self.reject()
    def test_commit_failure(self): self.log('committed=1','committed=0'); self.reject()
    def test_duplicate_action(self):
        p=next((self.copy/'scale1/ftesurf/logs').glob('input*.log'))
        text=p.read_text(); row=next(l for l in text.splitlines() if 'P601 ACTION' in l)
        p.write_text(text+'\n'+row); self.reject()
    def test_input_rejected(self): self.log('accepted=1','accepted=0'); self.reject()
    def test_quiet_legacy(self): self.log('P601 INPUT','NO INPUT','absent'); self.reject()
    def test_missing_capability(self): self.log('P601 INIT','NO INIT'); self.reject()
    def test_missing_finish(self): self.log('P601 FINISHED','NO FINISH'); self.reject()
    def test_missing_renderer_cleanup(self): self.log('renderer=1','renderer=0'); self.reject()
    def test_visible_model_unchanged(self):
        root=self.copy/'scale1/ftesurf/screenshots'
        shutil.copy2(next(root.glob('menu_initial.*')),next(root.glob('menu_changed.*'))); self.reject()
    def test_clip_state_marker(self):
        p=next((self.copy/'scale1/ftesurf/screenshots').glob('menu_initial.*'))
        im=Image.open(p).convert('RGB'); im.putpixel((600,110),(255,0,255)); im.save(p); self.reject()
    def test_no_covering_fallback(self):
        p=next((self.copy/'drawonly/ftesurf/screenshots').glob('menu_initial.*'))
        im=Image.open(p).convert('RGB'); im.putpixel((400,220),(0,0,0)); im.save(p); self.reject()
    def test_missing_screenshot(self):
        next((self.copy/'scale1/ftesurf/screenshots').glob('menu_initial.*')).unlink(); self.reject()
    def test_implicit_file(self): (self.copy/'scale1/imgui.ini').write_text('side effect'); self.reject()
    def test_wrong_exit(self):
        p=self.copy/'report.json'; report=json.loads(p.read_text()); report['arms']['scale1']['exit']=1
        p.write_text(json.dumps(report)); self.reject()


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('rig',type=Path); a=p.parse_args()
    errors=grade(a.rig)
    if errors: raise SystemExit('Non-green source rig: '+repr(errors))
    Controls.rig=a.rig
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    raise SystemExit(not result.wasSuccessful())
