#!/usr/bin/env python3
"""Quiet/inert/retargeted scoreboard routes cannot pass the local runtime grader."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

from p603scores import grade


class EvidenceControls(unittest.TestCase):
    rig = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p603-reader-')
        self.copy = Path(self.temp.name) / 'rig'
        shutil.copytree(self.rig, self.copy, ignore=shutil.ignore_patterns(
            '*.exe', '*.dll', '*.pfx', 'data', 'downloads', 'models', 'gfx', 'glsl', 'scripts', 'particles'))
        self.addCleanup(self.temp.cleanup)

    def log(self, old, new, arm='native1'):
        path = next((self.copy / arm / 'ftesurf/logs').glob('scores*.log'))
        text = path.read_text(errors='replace')
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def field(self, kind, name, field, new):
        path = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))
        text = path.read_text(errors='replace')
        pattern = rf'(P603 {kind} {name} [^\r\n]*?\b{field}=)(-?[0-9]+(?:\.[0-9]+)?)'
        text, count = re.subn(pattern, lambda m: m[1] + str(new), text)
        self.assertEqual(count, 1)
        path.write_text(text)

    def rejected(self):
        self.assertTrue(grade(self.copy))

    def test_acting_control(self): self.assertEqual(grade(self.copy), [])
    def test_quiet(self):
        path = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))
        path.write_text('P603 FINISHED\n'); self.rejected()
    def test_no_arms(self):
        path = self.copy / 'report.json'; report = json.loads(path.read_text())
        report['arms'] = {}; path.write_text(json.dumps(report)); self.rejected()
    def test_missing_planned_arm(self):
        path = self.copy / 'report.json'; report = json.loads(path.read_text())
        del report['arms']['native2']; path.write_text(json.dumps(report)); self.rejected()
    def test_missing_finish(self): self.log('P603 FINISHED', 'not finished'); self.rejected()
    def test_duplicate_probe(self): self.log('P603 STATE pinned', 'P603 STATE pinned h=0\nP603 STATE pinned'); self.rejected()
    def test_missing_field(self): self.log('h=', 'missing='); self.rejected()
    def test_runtime_error(self): self.log('P603 FINISHED', 'QC runtime error\nP603 FINISHED'); self.rejected()
    def test_gpu_device_lost(self): self.log('P603 FINISHED', 'ERROR: vkQueueSubmit: VK_ERROR_DEVICE_LOST\nP603 FINISHED'); self.rejected()
    def test_wrong_renderer(self):
        path = self.copy / 'report.json'; report = json.loads(path.read_text())
        report['renderer'] = 'vk'; path.write_text(json.dumps(report)); self.rejected()
    def test_no_native_act(self): self.field('STATE', 'pinned', 'painted', 0); self.rejected()
    def test_no_pin(self): self.field('OWNER', 'pinned', 'pin', 0); self.rejected()
    def test_passive_capture(self): self.field('OWNER', 'passive_click', 'cursor', 2); self.rejected()
    def test_no_line_build(self): self.field('LINE', 'line_control', 'ready', 0); self.rejected()
    def test_empty_line(self): self.field('LINE', 'line_control', 'samples', 0); self.rejected()
    def test_no_watch(self): self.field('ACTIVE', 'watch_control', 'watch', 0); self.rejected()
    def test_wrong_line_identity(self):
        self.log('scores: line 1 on: l:data/runs/p603scores.map/main/0000100_p6030_pb.rec',
                 'scores: line 1 on: l:data/runs/p603scores.map/main/0000101_p6031_pb.rec'); self.rejected()
    def test_wrong_watch_identity(self):
        self.log('replay: data/runs/p603scores.map/main/0000100_p6030_pb.rec  P603 Row0  0:01.500  20 samples',
                 'replay: data/runs/p603scores.map/main/0000101_p6031_pb.rec  P603 Row1  0:01.515  20 samples'); self.rejected()
    def test_no_page_act(self): self.field('STATE', 'next', 'page', 0); self.rejected()
    def test_inert_rescan(self): self.field('STATE', 'stale_rescan', 'revision', 1); self.rejected()
    def test_stale_activation(self): self.field('ACTIVE', 'stale_rescan', 'watch', 1); self.rejected()
    def test_focus_not_released(self): self.field('STATE', 'keyboard_lost', 'h', 1); self.rejected()
    def test_console_not_acted(self): self.field('OWNER', 'console', 'focus', 1); self.rejected()
    def test_stuck_button(self): self.field('OWNER', 'closed2', 'down', 1); self.rejected()
    def test_extra_closed_work(self):
        path = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))
        text = path.read_text(errors='replace')
        matches = list(re.finditer(r'UIIMGUI STATUS [^\r\n]*?frames=(\d+)', text))
        self.assertGreaterEqual(len(matches), 3)
        last = matches[-1]
        text = text[:last.start(1)] + str(int(last[1]) + 1) + text[last.end(1):]
        path.write_text(text); self.rejected()
    def test_bad_exit(self):
        path = self.copy / 'report.json'; report = json.loads(path.read_text())
        report['arms']['native1']['returncode'] = 1; path.write_text(json.dumps(report)); self.rejected()
    def test_missing_screenshot(self):
        for p in (self.copy / 'native1/ftesurf/screenshots').glob('pinned.*'): p.unlink()
        self.rejected()


if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('usage: test_p603scores_unit.py <runtime-rig>')
    EvidenceControls.rig = Path(sys.argv.pop()).resolve()
    unittest.main()
