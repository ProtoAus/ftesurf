#!/usr/bin/env python3
"""Mutation controls for the HTTP scoreboard gate, using an owned evidence copy."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

from p603scores import grade


class HttpEvidenceControls(unittest.TestCase):
    rig = out = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='http-reader-', dir=self.out)
        self.addCleanup(self.temp.cleanup)
        self.copy = Path(self.temp.name)
        shutil.copy2(self.rig / 'report.json', self.copy / 'report.json')
        report = json.loads((self.copy / 'report.json').read_text())
        for arm in report['planned_arms']:
            for folder in ('logs', 'screenshots'):
                shutil.copytree(self.rig / arm / 'ftesurf' / folder, self.copy / arm / 'ftesurf' / folder)
            shutil.copy2(self.rig / arm / 'http.jsonl', self.copy / arm / 'http.jsonl')

    def field(self, kind, name, field, value):
        path = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))
        text = path.read_text(errors='replace')
        pattern = rf'(P603 {kind} {name} [^\r\n]*?\b{field}=)(-?[0-9]+(?:\.[0-9]+)?)'
        text, count = re.subn(pattern, lambda m: m[1] + str(value), text)
        self.assertEqual(count, 1)
        path.write_text(text)

    def replace(self, old, new):
        path = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))
        text = path.read_text(errors='replace')
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new))

    def rejected(self): self.assertTrue(grade(self.copy))
    def test_acting_control(self): self.assertEqual(grade(self.copy), [])
    def test_quiet(self):
        path = next((self.copy / 'native1/ftesurf/logs').glob('scores*.log'))
        path.write_text('P603 FINISHED\nP603 HTTP FINISHED\n'); self.rejected()
    def test_duplicate_probe(self):
        self.replace('P603 HTTP ready ', 'P603 HTTP ready state=2\nP603 HTTP ready '); self.rejected()
    def test_missing_field(self):
        self.replace('P603 HTTP ready state=', 'P603 HTTP ready missing='); self.rejected()
    def test_no_mine(self): self.field('HTTP', 'ready', 'mine', -1); self.rejected()
    def test_wrong_identity(self):
        self.replace('P603 PHASH ready: ', 'P603 PHASH ready: other-'); self.rejected()
    def test_same_epoch(self): self.field('HTTP', 'identical', 'epoch', 0); self.rejected()
    def test_same_revision(self): self.field('HTTP', 'identical', 'revision', 1); self.rejected()
    def test_stale_watch(self): self.field('ROUTE', 'identical', 'watch', 1); self.rejected()
    def test_page_reset(self): self.field('HTTP', 'page_refresh', 'page', 0); self.rejected()
    def test_inert_line(self): self.field('ROUTE', 'line', 'ready', 0); self.rejected()
    def test_inert_watch(self): self.field('ROUTE', 'watch', 'watch', 0); self.rejected()
    def test_missing_replay_watch(self): self.field('ROUTE', 'missing', 'watch', 1); self.rejected()
    def test_inert_queue(self): self.field('ROUTE', 'demo_queued', 'lines', 0); self.rejected()
    def test_error_claimed_queued(self): self.field('ROUTE', 'demo_error', 'lines', 6); self.rejected()
    def test_bad_rate_delta(self):
        self.replace('P603 CELL ready 16: +0:00.100', 'P603 CELL ready 16: +0:00.900'); self.rejected()
    def test_missing_cold_download(self):
        path = self.copy / 'native1/http.jsonl'
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        before = len(entries)
        entries = [e for e in entries if '/api/replay/' not in e['path']]
        self.assertLess(len(entries), before)
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries)); self.rejected()
    def test_nonidentical_refresh(self):
        path = self.copy / 'native1/http.jsonl'
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        changed = False
        for entry in entries:
            if entry['path'].startswith('/normal/api/board'):
                entry['sha256'] = '0' * 64; changed = True; break
        self.assertTrue(changed)
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries)); self.rejected()
    def test_missing_http(self):
        (self.copy / 'native1/http.jsonl').unlink(); self.rejected()
    def test_missing_post(self):
        path = self.copy / 'native1/http.jsonl'
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        before = len(entries)
        entries = [e for e in entries if e['method'] != 'POST']
        self.assertLess(len(entries), before)
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries)); self.rejected()
    def test_denied_allocates(self): self.field('ROUTE', 'noterms', 'handle', 1); self.rejected()
    def test_denied_subject_inert(self): self.field('HTTP', 'noterms', 'state', 2); self.rejected()
    def test_unconfigured_subject_inert(self): self.field('HTTP', 'nodir', 'state', 2); self.rejected()
    def test_no_terms_recovery(self): self.field('ROUTE', 'terms_back', 'painted', 0); self.rejected()
    def test_failed_refresh_loses_rows(self): self.field('HTTP', 'http404', 'rows', 0); self.rejected()
    def test_verified_claim_truncated(self):
        self.replace('P603 CELL verified_get 9: Get demo (verified)', 'P603 CELL verified_get 9: Get demo'); self.rejected()
    def test_denied_network_disclosure(self):
        path = self.copy / 'native1/http.jsonl'
        with path.open('a') as stream:
            stream.write(json.dumps({'method': 'GET', 'path': '/noterms/api/board', 'code': 200}) + '\n')
        self.rejected()
    def test_missing_404(self):
        path = self.copy / 'native1/http.jsonl'
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertTrue(any(e['code'] == 404 for e in entries))
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries if e['code'] != 404)); self.rejected()
    def test_missing_screenshot(self):
        paths = list((self.copy / 'native1/ftesurf/screenshots').glob('http_identical.*'))
        self.assertEqual(len(paths), 1)
        paths[0].unlink(); self.rejected()


if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('usage: test_p603http_unit.py <runtime-rig> <owned-output-directory>')
    HttpEvidenceControls.rig = Path(sys.argv[1]).resolve()
    HttpEvidenceControls.out = Path(sys.argv[2]).resolve()
    if not HttpEvidenceControls.out.is_dir(): raise SystemExit('owned output directory must already exist')
    del sys.argv[1:]
    unittest.main()
