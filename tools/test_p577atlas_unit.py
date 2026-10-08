#!/usr/bin/env python3
"""Portable mutation controls for the plugin atlas grader, not engine tests."""
from pathlib import Path
import json
import tempfile
import unittest

from PIL import Image, ImageDraw

from p577atlas import grade, PHASES, PIXELS


class AtlasGradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p577-grade-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        report = {'arms':{x:{'exit':0} for x in ('control','subject','disabled','none')}}
        (self.root/'report.json').write_text(json.dumps(report))
        for arm in ('control','subject','disabled'):
            game = self.root/arm/'ftesurf'
            (game/'screenshots').mkdir(parents=True)
            log = []
            if arm == 'disabled':
                log = ['Unknown command "p577_open"']
            else:
                log += ['P577 INIT wrong_size_rejected=1','P577 OPEN subject=1 focus=1']
                for i,frame in enumerate((100,260,470,630)):
                    handle = 36 if arm == 'subject' else 0
                    size = 'size=1 w=2 h=2' if handle else 'size=-1 w=0 h=0'
                    log += [f'P577 STATUS phase={int(i != 0)} frames={frame} videoevents={1 if i < 2 else 4} uploads={min(i+1,3)} atlas={handle} {size} video=1 vw=640 vh=480 pw=640 ph=480']
                log += ['P577 REPLACE reached=1','P577 VIDEO restart=1']
                if arm == 'subject':
                    log += ['P577 INVALID begin=1','P577 INVALID end=1 rejected=7 ids=12 unloads=4',
                            'P577 LIFETIME begin=1 temp=31 size=1 w=2 h=2',
                            'P577 LIFETIME end=1 released_size=-1 released_image=0 released_quad=0 reload=31 size=1 w=2 h=2']
            (game/'p577.log').write_text('\n'.join(log)+'\n')
            for i,phase in enumerate(PHASES):
                im = Image.new('RGB',(640,480))
                if arm != 'disabled':
                    paint = ImageDraw.Draw(im)
                    paint.rectangle((16,16,39,39),fill=(255,0,255))
                    patch = Image.new('RGB',(128,128))
                    p = ImageDraw.Draw(patch)
                    colors = PIXELS if i == 0 else PIXELS[2:]+PIXELS[:2]
                    for box,color in zip(((0,0,63,63),(64,0,127,63),(0,64,63,127),(64,64,127,127)),colors):
                        p.rectangle(box,fill=color)
                    im.paste(patch,(256,64))
                    im.paste(patch,(448,64))
                    if arm == 'subject':
                        im.paste(patch,(64,64))
                        if phase == 'lifetime':
                            im.paste(patch,(64,256))
                im.save(game/'screenshots'/(phase+'.png'))
        (self.root/'none').mkdir()
        (self.root/'none'/'p577-none.txt').write_text('P577 NONE begin=1 video=0\nP577 NONE end=1 loaded=0\n')

    def reject(self, text):
        errors = grade(self.root)
        self.assertTrue(any(text in x for x in errors),errors)

    def log_replace(self, arm, old, new):
        path = self.root/arm/'ftesurf'/'p577.log'
        self.assertIn(old,path.read_text())
        path.write_text(path.read_text().replace(old,new))

    def clear(self, arm, phase, box):
        path = self.root/arm/'ftesurf'/'screenshots'/(phase+'.png')
        with Image.open(path) as source:
            im = source.convert('RGB')
        im.paste((0,0,0),box)
        im.save(path)

    def test_valid(self):
        self.assertEqual(grade(self.root),[])

    def test_forged_handle_without_pixels(self):
        self.clear('subject','initial',(64,64,192,192))
        self.reject('returned handle did not draw')

    def test_no_reloaded_pixels(self):
        self.clear('subject','lifetime',(64,256,192,384))
        self.reject('reloaded temporary image')

    def test_missing_sentinel(self):
        self.clear('subject','initial',(16,16,40,40))
        self.reject('sentinel')

    def test_memory_upload_silent(self):
        self.clear('control','initial',(448,64,576,192))
        self.reject('memory upload/lookup')

    def test_disk_control_silent(self):
        self.clear('control','initial',(256,64,384,192))
        self.reject('disk decoder/alpha')

    def test_unchanged_replacement(self):
        game = self.root/'subject'/'ftesurf'/'screenshots'
        (game/'replacement.png').write_bytes((game/'initial.png').read_bytes())
        self.reject('replacement control')

    def test_bad_alpha_even_when_all_crops_match(self):
        path = self.root/'subject'/'ftesurf'/'screenshots'/'initial.png'
        with Image.open(path) as source:
            im = source.convert('RGB')
        paint = ImageDraw.Draw(im)
        for left in (64,256,448):
            paint.rectangle((left+64,128,left+127,191),fill=(255,255,255))
        im.save(path)
        self.reject('alpha')

    def test_bad_physical_dimensions(self):
        path = self.root/'subject'/'ftesurf'/'screenshots'/'initial.png'
        with Image.open(path) as im:
            im.resize((1280,960)).save(path)
        self.reject('physical capture dimensions')

    def test_bad_virtual_dimensions(self):
        self.log_replace('subject','vw=640','vw=1280')
        self.reject('dimensions/phase')

    def test_no_frames(self):
        self.log_replace('subject','frames=100','frames=0')
        self.reject('frame')

    def test_frozen_frames(self):
        self.log_replace('subject','frames=260','frames=100')
        self.reject('did not advance')

    def test_bad_size(self):
        self.log_replace('subject','w=2 h=2','w=1 h=2')
        self.reject('handle/size')

    def test_short_abi_accepted(self):
        self.log_replace('subject','wrong_size_rejected=1','wrong_size_rejected=0')
        self.reject('ABI witness')

    def test_lost_focus(self):
        self.log_replace('subject','focus=1','focus=0')
        self.reject('focus witness')

    def test_missing_status(self):
        self.log_replace('subject','P577 STATUS phase=0','IGNORED phase=0')
        self.reject('four rendered')

    def test_restart_not_acted(self):
        self.log_replace('subject','videoevents=4','videoevents=1')
        self.reject('restart did not act')

    def test_wrong_upload_count(self):
        self.log_replace('subject','uploads=3','uploads=2')
        self.reject('upload witness')

    def test_missing_replacement_marker(self):
        self.log_replace('subject','P577 REPLACE','IGNORED')
        self.reject('replacement/restart witness')

    def test_invalid_probe_incomplete(self):
        self.log_replace('subject','rejected=7','rejected=6')
        self.reject('invalid input/handle')

    def test_bad_handle_probes(self):
        self.log_replace('subject','ids=12','ids=11')
        self.reject('invalid input/handle')

    def test_nonlive_handle_accepted(self):
        self.log_replace('subject','released_size=-1','released_size=1')
        self.reject('released-slot')

    def test_reload_not_acted(self):
        self.log_replace('subject','reload=31','reload=0')
        self.reject('reload probes')

    def test_no_renderer_marker_missing(self):
        path = self.root/'none'/'p577-none.txt'
        path.write_text('P577 NONE begin=1 video=0\n')
        self.reject('no-renderer')

    def test_no_renderer_was_graphics(self):
        path = self.root/'none'/'p577-none.txt'
        path.write_text(path.read_text().replace('video=0','video=1'))
        self.reject('no-renderer')

    def test_no_renderer_shutdown_fault_not_accepted(self):
        path = self.root/'report.json'
        report = json.loads(path.read_text())
        report['arms']['none']['exit'] = 3221225477
        path.write_text(json.dumps(report))
        self.reject('no-renderer')

    def test_disabled_plugin_active(self):
        path = self.root/'disabled'/'ftesurf'/'p577.log'
        path.write_text(path.read_text()+'P577 INIT wrong_size_rejected=1\n')
        self.reject('unexpectedly active')

    def test_disabled_arm_not_reached(self):
        self.log_replace('disabled','Unknown command "p577_open"','')
        self.reject('command-rejection')

    def test_unknown_command_in_subject(self):
        path = self.root/'subject'/'ftesurf'/'p577.log'
        path.write_text(path.read_text()+'Unknown command "p577_lifetime"\n')
        self.reject('command/runtime')

    def test_control_must_reproduce(self):
        self.log_replace('control','atlas=0','atlas=36')
        self.reject('control defect')


if __name__ == '__main__':
    unittest.main()
