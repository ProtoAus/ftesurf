#!/usr/bin/env python3
"""P1702 tools/publish_board.py: its Pi program run locally against a fake live generation and board folder; the
UI-only rule against real game history. python3 -B tools/test_publish_board.py"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish_board as pb

ROOT = Path(__file__).resolve().parents[1]
RUN = [sys.executable, '-I', '-B']
P1700 = '091ad1e9'          # board.html/js + tasupd.py (not a surfd member): UI-only
P1699 = '3697175c'          # board.js + surfd.py: rides a generation
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = self.d = Path(self.tmp.name)
        self.paths = dict(board=str(d / 'board'), runsh=str(d / 'run.sh'), snippet=str(d / 'ftesurf.conf'))
        self.generation('a' * 40, pb.git('rev-parse', P1700 + '^').decode().strip())

    def tearDown(self): self.tmp.cleanup()

    def generation(self, gen, source_ref, tweak=b''):
        root = self.d / ('gen-' + gen[:6]); home = root / 'runtime'; state = root / 'state'
        (home / 'web').mkdir(parents=True, exist_ok=True); state.mkdir(exist_ok=True)
        hashes = {}
        for f in pb.FILES:
            raw = pb.git('show', '%s:surfd/web/%s' % (source_ref, f)) + tweak
            (home / 'web' / f).write_bytes(raw); hashes['web/' + f] = sha(raw)
        (home / 'surfd.py').write_bytes(pb.git('show', source_ref + ':surfd/surfd.py'))
        hashes['surfd.py'] = sha((home / 'surfd.py').read_bytes()); hashes['admin.py'] = '0' * 64
        (state / 'manifest.json').write_text(json.dumps({'generation': gen, 'source_home': str(home), 'hashes': hashes}))
        (root / 'generation-identity.json').write_text(json.dumps({'source_ref': source_ref}))
        Path(self.paths['runsh']).write_text('#!/bin/sh\nexec /usr/bin/python3.11 -I -B guard.py --state-dir %s --timeout 240 '
                                             'launch --generation %s --route server\n' % (state, gen))
        return home

    def publish(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return pb.main(list(argv), runner=RUN, paths=self.paths)

    def current(self): return Path(self.paths['board']) / 'current'

    def test_live_publishes_the_live_bytes_and_keeps_two(self):
        out = self.publish('--live')
        self.assertEqual(os.readlink(self.current()), 'releases/live-aaaaaaaaaaaa')
        home = self.d / 'gen-aaaaaa' / 'runtime'
        for f in pb.FILES: self.assertEqual((self.current() / f).read_bytes(), (home / 'web' / f).read_bytes())
        self.assertEqual(self.publish('--live')['current'], out['current'])           # idempotent
        for i, g in enumerate(('b' * 40, 'c' * 40)):
            self.generation(g, pb.git('rev-parse', P1700 + '^').decode().strip(), tweak=b'\n/* %d */' % i)
            out = self.publish('--live')
        self.assertEqual(sorted(os.listdir(Path(self.paths['board']) / 'releases')), ['live-bbbbbbbbbbbb', 'live-cccccccccccc'])
        self.assertEqual(out['removed'], ['live-aaaaaaaaaaaa'])

    def test_live_refuses_bytes_the_manifest_does_not_pin(self):
        (self.d / 'gen-aaaaaa' / 'runtime' / 'web' / 'board.js').write_bytes(b'tampered')
        with self.assertRaisesRegex(SystemExit, 'does not match the live manifest'): self.publish('--live')
        self.assertFalse(os.path.lexists(self.current()))

    def test_dry_run_writes_nothing(self):
        out = self.publish('--live', '--dry-run')
        self.assertTrue(out['dry_run']); self.assertFalse(os.path.exists(self.paths['board']))

    def test_commit_ui_only_rule(self):
        out = self.publish('--commit', P1700)
        self.assertEqual(out['current'], 'commit-' + pb.git('rev-parse', P1700).decode()[:12])
        self.assertEqual((self.current() / 'board.html').read_bytes(), pb.git('show', P1700 + ':surfd/web/board.html'))
        # P1699's board change comes with surfd.py: refused while the live source_ref predates it.
        self.generation('d' * 40, pb.git('rev-parse', P1699 + '^').decode().strip())
        with self.assertRaisesRegex(SystemExit, 'ride a generation'): self.publish('--commit', P1699)
        # a REF the live generation is not an ancestor of
        self.generation('e' * 40, pb.git('rev-parse', P1700).decode().strip())
        with self.assertRaisesRegex(SystemExit, 'not an ancestor'): self.publish('--commit', P1699 + '^')

    def test_the_repo_snippet_carries_surfds_csp_and_a_wrong_one_refuses(self):
        snippet = (ROOT / 'src/release/ftesurf.nginx').read_text()
        Path(self.paths['snippet']).write_text(snippet)
        self.assertEqual(self.publish('--live', '--dry-run')['snippet'], 'snippet CSP matches')
        # The repo's snippet must carry HEAD's surfd.py CSP exactly (a CSP change needs ftesurf.nginx + install.sh).
        csp, watch = pb.csp_of((ROOT / 'surfd/surfd.py').read_bytes())
        self.assertEqual(snippet.count('"%s" always;' % csp), 14); self.assertEqual(snippet.count('"%s" always;' % watch), 2)
        Path(self.paths['snippet']).write_text(snippet.replace("img-src 'self'", "img-src *", 1))
        with self.assertRaisesRegex(SystemExit, 'different CSP'): self.publish('--live')
        Path(self.paths['snippet']).write_text('location / {}\n')
        self.assertIn('not installed', self.publish('--live', '--dry-run')['snippet'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
