#!/usr/bin/env python3
"""Portable anti-silence/mutation checks for the native-only mesh grader."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import p589mesh as subject


class MeshGrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rig = Path(self.tmp.name)
        report = {'arms':{arm:{'exit':0} for arm in subject.ARMS}}
        (self.rig/'report.json').write_text(json.dumps(report))
        for arm in subject.ARMS:
            root = self.rig/arm
            shots = root/'ftesurf/screenshots'
            shots.mkdir(parents=True)
            if arm == 'none':
                (root/'none.txt').write_text('P589 NONE video=0 texture=0 submit=0\n')
                continue
            active = arm != 'disabled'
            mesh = arm.startswith('subject')
            lines = []
            if active:
                lines += [f'P589 INIT available={int(mesh)} short=1 long=1 version=1',
                          f'P589 OPEN focus=1 available={int(mesh)}']
                if mesh:
                    lines += ['P589 INVALID begin=1','P589 INVALID end=1 rejected=25 life=7 budget=61']*2
                    lines += ['P589 FOREIGN token=1 rejected=2','P589 LEAK created=32','P589 LEAK created=32',
                              'P589 RELOAD previous=0 rejected=0','P589 RELOAD previous=9 rejected=1',
                              'P589 VIDEO restart=1 stale=2']
                for i in range(4):
                    vw,vh = (320,240) if arm == 'subject2' else (640,480)
                    frames = 100*(i+1)
                    lines += [f'P589 STATUS frames={frames} submitted={frames*3 if mesh else 0} video=1 vw={vw} vh={vh} pw=640 ph=480 uploads={2 if i == 2 else 1} restarts={1 if i == 2 else 0} invalid={25 if mesh else 0} stale={2 if i == 2 else 0}']
            else:
                lines += ['Unknown command "p589_open"']
            (root/'ftesurf/p589.log').write_text('\n'.join(lines)+'\n')
            im = Image.new('RGB',(640,480))
            if active:
                for p,c in {(28,28):(255,0,255),(270,270):(0,255,0),(410,80):(255,0,0),
                            (440,104):(255,0,0),(480,144):(255,0,0)}.items():
                    im.putpixel(p,c)
            if mesh:
                for p,c in {(92,92):(255,0,0),(164,92):(0,255,0),(92,164):(0,0,128),
                            (164,164):(128,128,128),(440,104):(127,0,128),(510,260):(0,255,0),
                            (90,280):(0,255,255)}.items():
                    im.putpixel(p,c)
            for phase in subject.PHASES:
                im.save(shots/(phase+'.png'))

    def mutate(self,old,new,arm='subject1'):
        p = self.rig/arm/'ftesurf/p589.log'
        text = p.read_text()
        self.assertIn(old,text)
        p.write_text(text.replace(old,new))
        self.assertTrue(subject.grade(self.rig))

    def pixel(self,p,c,arm='subject1',phase='initial'):
        path = self.rig/arm/'ftesurf/screenshots'/(phase+'.png')
        im = Image.open(path).convert('RGB')
        im.putpixel(p,c)
        im.save(path)
        self.assertTrue(subject.grade(self.rig))

    def test_positive(self): self.assertEqual([],subject.grade(self.rig))
    def test_api_missing(self): self.mutate('available=1','available=0')
    def test_short_accepted(self): self.mutate('short=1','short=0')
    def test_long_accepted(self): self.mutate('long=1','long=0')
    def test_version_accepted(self): self.mutate('version=1','version=0')
    def test_no_frames(self): self.mutate('frames=100','frames=0')
    def test_no_submission(self): self.mutate('submitted=300','submitted=0')
    def test_no_video(self): self.mutate('video=1','video=0')
    def test_wrong_physical(self): self.mutate('pw=640','pw=320')
    def test_wrong_virtual(self): self.mutate('vw=320','vw=640','subject2')
    def test_no_focus(self): self.mutate('focus=1','focus=0')
    def test_invalid_not_rejected(self): self.mutate('rejected=25','rejected=24')
    def test_no_lifetime(self): self.mutate('life=7','life=6')
    def test_no_budget(self): self.mutate('budget=61','budget=60')
    def test_foreign_silent(self): self.mutate('token=1','token=0')
    def test_foreign_submit_accepted(self): self.mutate('rejected=2','rejected=1')
    def test_unload_leak(self): self.mutate('created=32','created=31')
    def test_restart_stale(self): self.mutate('stale=2','stale=0')
    def test_reload_stale(self): self.mutate('previous=9 rejected=1','previous=9 rejected=0')
    def test_missing_none(self):
        (self.rig/'none/none.txt').write_text('')
        self.assertTrue(subject.grade(self.rig))
    def test_none_texture_accepted(self):
        (self.rig/'none/none.txt').write_text('P589 NONE video=0 texture=1 submit=0\n')
        self.assertTrue(subject.grade(self.rig))
    def test_disabled_active(self): self.pixel((28,28),(255,0,255),'disabled')
    def test_missing_before(self): self.pixel((28,28),(0,0,0))
    def test_color_not_restored(self): self.pixel((270,270),(255,255,255))
    def test_bad_alpha(self): self.pixel((92,164),(0,0,255))
    def test_bad_vertex_tint(self): self.pixel((440,104),(255,0,0))
    def test_wrong_winding(self): self.pixel((510,260),(0,0,0))
    def test_clip_escaped(self): self.pixel((79,100),(255,0,0))
    def test_invalid_partial_draw(self): self.pixel((250,80),(255,255,255))
    def test_chunk_missing(self): self.pixel((90,280),(0,0,0))
    def test_repeat_changed(self): self.pixel((600,400),(255,255,255),phase='repeat')
    def test_scale_changed(self): self.pixel((600,400),(255,255,255),'subject2')
    def test_abnormal_exit(self):
        p=self.rig/'report.json'; r=json.loads(p.read_text()); r['arms']['subject1']['exit']=1
        p.write_text(json.dumps(r)); self.assertTrue(subject.grade(self.rig))


if __name__ == '__main__': unittest.main()
