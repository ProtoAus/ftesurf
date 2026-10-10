#!/usr/bin/env python3
"""Lifecycle evidence falsifiers, exclusively beneath a caller-owned output dir."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from p603scores import grade


class LifecycleEvidence(unittest.TestCase):
    rig = out = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='life-reader-', dir=self.out)
        self.addCleanup(self.temp.cleanup)
        self.copy = Path(self.temp.name)
        shutil.copy2(self.rig / 'report.json', self.copy / 'report.json')
        report = json.loads((self.copy / 'report.json').read_text())
        for arm in report['planned_arms']:
            for folder in ('logs', 'screenshots'):
                shutil.copytree(self.rig / arm / 'ftesurf' / folder, self.copy / arm / 'ftesurf' / folder)
            http = self.rig / arm / 'http.jsonl'
            if http.exists(): shutil.copy2(http, self.copy / arm / 'http.jsonl')
        self.log = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))

    def field(self, kind, name, field, value):
        prefix = 'life_' if kind in ('STATE', 'OWNER', 'ACTIVE') else ''
        pattern = rf'(P603 {kind} {prefix}{name} [^\r\n]*?\b{field}=)(-?[0-9]+(?:\.[0-9]+)?)'
        text, count = re.subn(pattern, lambda m: m[1] + str(value), self.log.read_text(errors='replace'))
        self.assertEqual(count, 1)
        self.log.write_text(text)

    def rejected(self): self.assertTrue(grade(self.copy))
    def test_acting_control(self): self.assertEqual(grade(self.copy), [])
    def test_quiet(self):
        self.log.write_text('P603 FINISHED\nP603 LIFE FINISHED\n'); self.rejected()
    def test_duplicate_probe(self):
        text = self.log.read_text(errors='replace')
        self.assertEqual(text.count('P603 LIFE control '), 1)
        self.log.write_text(text.replace('P603 LIFE control ', 'P603 LIFE control chat=0\nP603 LIFE control '))
        self.rejected()
    def test_duplicate_field(self):
        text = self.log.read_text(errors='replace')
        self.assertEqual(text.count('P603 LIFE control chat='), 1)
        self.log.write_text(text.replace('P603 LIFE control chat=', 'P603 LIFE control chat=0 chat='))
        self.rejected()
    def test_missing_field(self):
        text = self.log.read_text(errors='replace')
        self.log.write_text(text.replace('P603 LIFE control chat=', 'P603 LIFE control missing=')); self.rejected()
    def test_inert_native(self): self.field('STATE', 'control', 'painted', 0); self.rejected()
    def test_inert_focus(self): self.field('LIFE', 'mouse_lost', 'mouse', 1); self.rejected()
    def test_coupled_focus(self): self.field('LIFE', 'mouse_lost', 'keyboard', 0); self.rejected()
    def test_stale_focus_watch(self): self.field('ACTIVE', 'mouse_back', 'watch', 1); self.rejected()
    def test_stuck_down(self): self.field('OWNER', 'filter', 'down', 1); self.rejected()
    def test_stuck_taken(self): self.field('OWNER', 'plugin_back', 'taken', 1); self.rejected()
    def test_inert_chat(self): self.field('LIFE', 'chat', 'chat', 0); self.rejected()
    def test_inert_editor(self): self.field('LIFE', 'editor', 'editor', 0); self.rejected()
    def test_inert_menu(self): self.field('OWNER', 'menu', 'focus', 1); self.rejected()
    def test_retained_focus_owner(self): self.field('STATE', 'mouse_lost', 'h', 1); self.rejected()
    def test_inert_source(self): self.field('LIFE', 'source', 'tab', 2); self.rejected()
    def test_inert_filter(self): self.field('LIFE', 'filter', 'filter', 0); self.rejected()
    def test_inert_shell(self): self.field('LIFE', 'shell', 'filter', 0); self.rejected()
    def test_retained_unloaded_owner(self): self.field('STATE', 'plugin_off', 'h', 1); self.rejected()
    def test_failed_recovery(self): self.field('STATE', 'restart_back', 'painted', 0); self.rejected()
    def test_draw_retry_spam(self): self.field('LIFEFALL', 'draw_latched', 'draw', 2); self.rejected()
    def test_model_retry_spam(self): self.field('LIFEFALL', 'model_latched', 'model', 2); self.rejected()
    def test_missing_failure_latch(self): self.field('STATE', 'draw_fail', 'failed', 0); self.rejected()
    def test_no_failure_legacy_cover(self): self.field('ACTIVE', 'model_fallback', 'watch', 0); self.rejected()
    def test_stuck_close(self): self.field('OWNER', 'closed2', 'cursor', 1); self.rejected()
    def test_cache_stale_label(self): self.field('CACHE', 'changed', 'ok', 0); self.rejected()
    def test_cache_stale_raw(self): self.field('CACHE', 'equivalent', 'raw', 0); self.rejected()
    def test_cache_inert_revision(self):
        text = self.log.read_text(errors='replace')
        revision = re.search(r'P603 CACHE equivalent [^\r\n]*revision=(\d+)', text)[1]
        self.field('CACHE', 'changed', 'revision', revision); self.rejected()
    def test_dock_overlap(self):
        text = self.log.read_text(errors='replace'); self.assertIn('P603 DOCK clipped=1 gap=1 hover=0', text)
        self.log.write_text(text.replace('P603 DOCK clipped=1 gap=1 hover=0', 'P603 DOCK clipped=0 gap=0 hover=0', 1)); self.rejected()
    def test_dock_watch(self): self.field('ACTIVE', 'dock', 'watch', 1); self.rejected()
    def test_disable_owner_retained(self): self.field('STATE', 'disabled', 'h', 1); self.rejected()
    def test_disable_route_retained(self): self.field('STATE', 'disabled', 'painted', 1); self.rejected()
    def test_disable_closed_pin(self): self.field('OWNER', 'disabled', 'pin', 0); self.rejected()
    def test_enable_failed(self): self.field('STATE', 'enabled', 'painted', 0); self.rejected()
    def test_disable_extra_work(self):
        text = self.log.read_text(errors='replace')
        match = re.search(r'P603 DISABLED BEGIN(.*?)P603 DISABLED END', text, re.S)
        self.assertIsNotNone(match)
        stats = re.findall(r'UIIMGUI STATUS [^\r\n]+', match[1])
        self.assertEqual(len(stats), 2)
        changed = stats[1].replace('live=0', 'live=1')
        self.log.write_text(text[:match.start(1)] + match[1].replace(stats[1], changed, 1) + text[match.end(1):])
        self.rejected()
    def test_vm_not_unloaded(self):
        text = self.log.read_text(errors='replace')
        text, count = re.subn(r'(P603 VM BEGIN.*?UIIMGUI STATUS [^\r\n]*?)live=0', r'\1live=1', text, flags=re.S)
        self.assertEqual(count, 1); self.log.write_text(text); self.rejected()
    def test_vm_not_reloaded(self):
        text = self.log.read_text(errors='replace')
        self.assertEqual(text.count('FTESurf CSQC loaded'), 2)
        self.log.write_text(text.replace('FTESurf CSQC loaded', 'Missing reload', 1)); self.rejected()
    def test_vm_stale_watch(self): self.field('ACTIVE', 'vm_back', 'watch', 1); self.rejected()
    def test_missing_screenshot(self):
        files = list((self.copy / 'native1/ftesurf/screenshots').glob('life_draw_fail.*'))
        self.assertEqual(len(files), 1); files[0].unlink(); self.rejected()


if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('usage: test_p603life_unit.py <lifecycle-rig> <owned-output-dir>')
    LifecycleEvidence.rig, LifecycleEvidence.out = (Path(p).resolve() for p in sys.argv[1:])
    if not LifecycleEvidence.out.is_dir(): raise SystemExit('owned output dir must already exist')
    del sys.argv[1:]
    unittest.main()
