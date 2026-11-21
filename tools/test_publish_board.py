#!/usr/bin/env python3
"""P1702 tools/publish_board.py + tools/board_publish_pi.py: the Pi program run locally against fake live trees; the
byte rule against synthetic git histories and real game commits. python3 -B tools/test_publish_board.py"""
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish_board as pb

ROOT = Path(__file__).resolve().parents[1]
RUN = [sys.executable, '-I', '-B']
P1700 = '091ad1e9'          # board.html/js + tasupd.py (not a member): UI-only
P1699 = '3697175c'          # board.js + surfd.py
sha = lambda raw: hashlib.sha256(raw).hexdigest()
FILES = pb.FILES


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


class Live(unittest.TestCase):
    """A fake Pi: run.sh -> state/manifest.json -> runtime/{web/*, surfd.py}; board/ and a snippet."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = self.d = Path(self.tmp.name)
        self.paths = dict(board=str(d / 'board'), runsh=str(d / 'run.sh'), snippet=str(d / 'ftesurf.conf'))
        Path(self.paths['snippet']).write_text((ROOT / 'src/release/ftesurf.nginx').read_text())
        self.base = pb.git('rev-parse', P1700 + '^').decode().strip()
        self.generation('a' * 40, self.base)

    def tearDown(self):
        os.chmod(self.d, 0o700); self.tmp.cleanup()

    def generation(self, gen, source_ref, tweak=b''):
        root = self.d / ('gen-' + gen[:6]); home = root / 'runtime'; state = root / 'state'
        (home / 'web').mkdir(parents=True, exist_ok=True); state.mkdir(exist_ok=True)
        hashes = {'admin.py': '0' * 64, 'tools/ksfconvert.py': '1' * 64, 'test_board.py': '2' * 64}
        for f in FILES:
            raw = pb.git('show', '%s:surfd/web/%s' % (source_ref, f)) + tweak
            (home / 'web' / f).write_bytes(raw); hashes['web/' + f] = sha(raw)
        (home / 'surfd.py').write_bytes(pb.git('show', source_ref + ':surfd/surfd.py'))
        hashes['surfd.py'] = sha((home / 'surfd.py').read_bytes())
        (state / 'manifest.json').write_text(json.dumps({'generation': gen, 'source_home': str(home), 'hashes': hashes,
                                                         'external_python': {'momimport': {'origin': '/x/momimport.py'}}}))
        (root / 'generation-identity.json').write_text(json.dumps({'source_ref': source_ref}))
        Path(self.paths['runsh']).write_text('#!/bin/sh\nexec /usr/bin/python3.11 -I -B guard.py --state-dir %s --timeout 240 '
                                             'launch --generation %s --route server\n' % (state, gen))
        return home

    def publish(self, *argv):
        return quiet(pb.main, list(argv), runner=RUN, paths=self.paths)

    def pi(self, **payload):
        done = subprocess.run(RUN + [str(pb.PI_PROGRAM)], input=(json.dumps(dict(dict(paths=self.paths, keep=2), **payload)) + '\n').encode(),
                              capture_output=True)
        return json.loads(done.stdout.decode().strip().splitlines()[-1])

    def current(self): return Path(self.paths['board']) / 'current'
    def releases(self): return sorted(os.listdir(Path(self.paths['board']) / 'releases'))


class Publish(Live):
    def test_live_publishes_the_live_bytes_and_keeps_two_by_when_made_current(self):
        self.publish('--live')
        self.assertEqual(os.readlink(self.current()), 'releases/live-aaaaaaaaaaaa')
        for f in FILES: self.assertEqual((self.current() / f).read_bytes(), (self.d / 'gen-aaaaaa/runtime/web' / f).read_bytes())
        self.assertEqual(self.publish('--live')['current'], 'live-aaaaaaaaaaaa')                        # idempotent
        self.generation('b' * 40, self.base, b'\n/*b*/'); self.publish('--live')
        self.generation('a' * 40, self.base); self.publish('--live')                                    # roll back to A
        self.generation('c' * 40, self.base, b'\n/*c*/'); out = self.publish('--live')
        self.assertEqual(self.releases(), ['live-aaaaaaaaaaaa', 'live-cccccccccccc'])                   # B goes, not A
        self.assertEqual(out['removed'], ['live-bbbbbbbbbbbb'])
        for d in [Path(self.paths['board']), Path(self.paths['board']) / 'releases']:
            self.assertEqual(d.stat().st_mode & 0o777, 0o755)

    def test_live_refuses_bytes_the_manifest_does_not_pin(self):
        (self.d / 'gen-aaaaaa/runtime/web/board.js').write_bytes(b'tampered')
        with self.assertRaisesRegex(SystemExit, 'does not match the live manifest'): self.publish('--live')
        self.assertFalse(os.path.lexists(self.current()))
        self.generation('a' * 40, self.base)
        (self.d / 'gen-aaaaaa/runtime/surfd.py').write_bytes(b'WEB_CSP = "x"\nWEB_CSP_WATCH = "y"\n')
        with self.assertRaisesRegex(SystemExit, 'surfd.py does not match'): self.publish('--live')

    def test_dry_runs_write_nothing(self):
        self.assertTrue(self.publish('--live', '--dry-run')['dry_run'])
        self.assertTrue(self.publish('--commit', P1700, '--dry-run')['dry_run'])
        self.assertFalse(os.path.exists(self.paths['board']))

    def test_commit_on_real_history(self):
        out = self.publish('--commit', P1700)
        self.assertEqual(out['current'], 'commit-' + pb.git('rev-parse', P1700).decode()[:12])
        self.assertEqual((self.current() / 'board.html').read_bytes(), pb.git('show', P1700 + ':surfd/web/board.html'))
        self.generation('d' * 40, pb.git('rev-parse', P1699 + '^').decode().strip())
        with self.assertRaisesRegex(SystemExit, r'server code changed.*surfd/surfd.py'): self.publish('--commit', P1699)

    def test_the_snippet_csp_is_checked_per_location(self):
        self.assertEqual(self.publish('--live', '--dry-run')['snippet'], 'snippet CSP matches')
        csp, watch = pb.csp_of((ROOT / 'surfd/surfd.py').read_bytes())
        snip = Path(self.paths['snippet']).read_text()
        self.assertEqual(snip.count('"%s" always;' % csp), 14); self.assertEqual(snip.count('"%s" always;' % watch), 2)
        # watch.html and watch.js swap CSPs: the counts stay right, the per-location check refuses
        a, b = snip.index('location = /ftesurf/board/watch.html'), snip.index('location = /ftesurf/board/watch.js')
        swapped = snip[:a] + snip[a:b].replace(watch, '@W@') + snip[b:]
        i = swapped.index('location = /ftesurf/board/watch.js'); j = swapped.index('\n}', i)
        swapped = swapped[:i] + swapped[i:j].replace(csp, watch) + swapped[j:]
        Path(self.paths['snippet']).write_text(swapped.replace('@W@', csp))
        with self.assertRaisesRegex(SystemExit, 'watch'): self.publish('--live')
        i = snip.index('location = /worldofsurf/board/board.css'); j = snip.index('\n}', i)
        Path(self.paths['snippet']).write_text(snip[:i] + snip[i:j].replace("img-src 'self'", 'img-src *') + snip[j:])
        with self.assertRaisesRegex(SystemExit, '/worldofsurf/board/board.css'): self.publish('--live')
        extra = snip[:j] + '\n    add_header Content-Security-Policy "x" always;' + snip[j:]
        Path(self.paths['snippet']).write_text(extra)
        with self.assertRaisesRegex(SystemExit, '/worldofsurf/board/board.css'): self.publish('--live')
        Path(self.paths['snippet']).write_text(snip)
        os.chmod(self.paths['snippet'], 0)
        if os.geteuid() != 0:
            with self.assertRaisesRegex(SystemExit, 'cannot read the installed nginx snippet'): self.publish('--live')
        os.chmod(self.paths['snippet'], 0o644)
        Path(self.paths['snippet']).write_text('location / {}\n')
        self.assertIn('not installed', self.publish('--live', '--dry-run')['snippet'])
        os.unlink(self.paths['snippet'])                       # a box with no snippet yet: install.sh needs a publish first
        self.assertIn('no nginx snippet', self.publish('--live', '--dry-run')['snippet'])


class PiGuards(Live):
    def payload(self, **over):
        files = {f: pb.git('show', '%s:surfd/web/%s' % (self.base, f)) for f in FILES}
        import base64
        p = dict(mode='commit', commit='c' * 40, live_generation='a' * 40,
                 files={f: base64.b64encode(raw).decode() for f, raw in files.items()},
                 expect={f: sha(raw) for f, raw in files.items()}, csp=list(pb.csp_of((self.d / 'gen-aaaaaa/runtime/surfd.py').read_bytes())))
        p.update(over); return p

    def test_commit_csp_must_be_the_live_surfds(self):
        self.assertIn('differs from the live surfd.py', self.pi(**self.payload(csp=['a', 'b']))['error'])

    def test_commit_payload_guards(self):
        self.assertIn('changed since planning', self.pi(**self.payload(live_generation='b' * 40))['error'])
        bad = self.payload(); bad['expect']['board.js'] = '0' * 64
        self.assertIn('payload file set', self.pi(**bad)['error'])
        (Path(self.paths['board']) / 'releases' / ('commit-' + 'c' * 12)).mkdir(parents=True)
        (Path(self.paths['board']) / 'releases' / ('commit-' + 'c' * 12) / 'board.js').write_bytes(b'other')
        self.assertIn('exists with other bytes', self.pi(**self.payload())['error'])

    def test_keep_never_takes_current_and_modes_ignore_umask(self):
        old = os.umask(0o077)
        try: out = self.pi(mode='live', keep=0)
        finally: os.umask(old)
        self.assertEqual(out['removed'], []); self.assertTrue(os.path.isdir(self.current()))
        for d in [Path(self.paths['board']), Path(self.paths['board']) / 'releases', self.current()]:
            self.assertEqual(d.stat().st_mode & 0o777, 0o755, d)
        self.assertEqual((self.current() / 'board.js').stat().st_mode & 0o777, 0o644)


class Follow(Live):
    def test_follow_checks_the_snippet_every_tick_and_is_quiet_when_idle(self):
        self.pi(mode='follow')
        code = ('import json, runpy, sys; ns = runpy.run_path(sys.argv[1], run_name="pi_main"); '
                'ns["PATHS"].update(json.loads(sys.argv[2])); sys.exit(ns["main"](["--follow"]))')
        done = subprocess.run(RUN + ['-c', code, str(pb.PI_PROGRAM), json.dumps(self.paths)], capture_output=True)
        self.assertEqual((done.returncode, done.stdout), (0, b''))                     # the --follow entry, idle: silent
        snip = Path(self.paths['snippet']).read_text()
        Path(self.paths['snippet']).write_text(snip.replace("img-src 'self'", 'img-src *'))
        self.assertIn('carries another CSP', self.pi(mode='follow')['error'])


    def test_follow_publishes_once_per_generation_and_holds_a_commit(self):
        self.assertEqual(self.pi(mode='follow')['action'], 'published')
        self.assertEqual(self.pi(mode='follow')['action'], 'none')
        self.publish('--commit', P1700)                                                 # a UI fix ahead of a generation
        self.assertEqual(self.pi(mode='follow')['action'], 'none')
        self.assertTrue(os.readlink(self.current()).startswith('releases/commit-'))
        self.generation('e' * 40, self.base, b'\n/*e*/')                                # a swap (or a rollback)
        out = self.pi(mode='follow')
        self.assertEqual((out['action'], out['current']), ('published', 'live-eeeeeeeeeeee'))
        self.assertEqual(json.loads((Path(self.paths['board']) / 'state.json').read_text())['generation'], 'e' * 40)

    def test_a_busy_lock_and_a_crashed_write(self):
        self.pi(mode='follow')
        (Path(self.paths['board']) / 'releases' / '.live-ffffffffffff-x1').mkdir()
        lock = os.open(Path(self.paths['board']) / '.publish.lock', os.O_RDWR)
        fcntl.flock(lock, fcntl.LOCK_EX)
        self.generation('f' * 40, self.base, b'\n/*f*/')
        self.assertEqual(self.pi(mode='follow'), {'action': 'none', 'busy': True, 'ok': True})
        with self.assertRaisesRegex(SystemExit, 'another board publish is running'): self.publish('--live')
        os.close(lock)
        self.assertEqual(self.pi(mode='follow')['action'], 'published')
        self.assertNotIn('.live-ffffffffffff-x1', os.listdir(Path(self.paths['board']) / 'releases'))


class ByteRule(unittest.TestCase):
    """Synthetic histories: each would ship a board built against server code that is not live."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.repo = Path(self.tmp.name)
        self.g('init', '-q', '-b', 'main'); self.g('config', 'user.email', 't@t'); self.g('config', 'user.name', 't')
        for f in FILES: self.write('surfd/web/' + f, f)
        for f in ('surfd/surfd.py', 'surfd/recplot.py', 'surfd/templates/admin.html', 'tools/ksfconvert.py', 'tools/momimport.py',
                  'tools/momfetch.py'):
            self.write(f, f)
        self.base = self.commit('base')

    def tearDown(self): self.tmp.cleanup()
    def g(self, *a): return subprocess.run(['git', '-C', str(self.repo)] + list(a), check=True, capture_output=True).stdout.decode().strip()
    def write(self, path, text):
        p = self.repo / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text + '\n')
    def commit(self, msg): self.g('add', '-A'); self.g('commit', '-q', '-m', msg); return self.g('rev-parse', 'HEAD')

    def info(self, **over):
        hashes = {'web/' + f: sha(pb.git('show', '%s:surfd/web/%s' % (self.base, f), root=self.repo)) for f in FILES}
        hashes.update({'surfd.py': '0' * 64, 'recplot.py': '0' * 64, 'templates/admin.html': '0' * 64,
                       'tools/ksfconvert.py': '0' * 64, 'test_board.py': '0' * 64, 'momfetch.py': '0' * 64})
        hashes['recplot.py'] = sha(pb.git('show', '%s:surfd/recplot.py' % self.base, root=self.repo))
        conv = sha(pb.git('show', '%s:tools/momimport.py' % self.base, root=self.repo))
        return dict(dict(source_ref=self.base, hashes=hashes, external_python={'momimport': conv}), **over)

    def refused(self, ref, why, **over):
        with self.assertRaisesRegex(SystemExit, why): pb.ui_only(self.info(**over), ref, self.repo)

    def test_a_board_only_change_passes(self):
        self.write('surfd/web/board.css', 'new css'); self.write('surfd/test_board.py', 'tests may move')
        pb.ui_only(self.info(), self.commit('css'), self.repo)

    def test_a_split_change_is_refused(self):
        self.write('surfd/surfd.py', 'new api'); self.commit('server only')
        self.write('surfd/web/board.js', 'uses it'); self.refused(self.commit('board only'), 'surfd/surfd.py')

    def test_tools_members_templates_converters_and_renames_count(self):
        for path in ('tools/ksfconvert.py', 'surfd/templates/admin.html', 'tools/momimport.py'):
            self.write(path, 'changed ' + path); ref = self.commit(path)
            self.refused(ref, path.replace('.', r'\.'))
            self.g('reset', '-q', '--hard', self.base)
        self.g('mv', 'surfd/recplot.py', 'surfd/recplot2.py'); self.refused(self.commit('rename'), r'surfd/recplot\.py')

    def test_tools_sourced_mapping_unknown_members_and_held(self):
        self.write('tools/momfetch.py', 'changed'); self.refused(self.commit('momfetch'), r'tools/momfetch\.py')
        self.g('reset', '-q', '--hard', self.base)
        self.write('surfd/web/board.css', 'css'); ref = self.commit('css')
        info = self.info(); info['hashes']['ghost.py'] = '0' * 64
        with self.assertRaisesRegex(SystemExit, 'no git source'): pb.ui_only(info, ref, self.repo)
        held = pb.ui_only(self.info(), ref, self.repo)
        self.assertIn('surfd/surfd.py', held); self.assertNotIn('surfd/recplot.py', held); self.assertNotIn('tools/momimport.py', held)
        with self.assertRaisesRegex(SystemExit, 'no dry run'): quiet(pb.main, ['--install-follow', '--dry-run'])
        script = pb.follow_script()                       # refuse a non-lingering user before anything is written
        self.assertLess(script.index('-p Linger --value'), script.index('mkdir -p'))
        self.assertLess(script.index('enable --now'), script.index('is-active'))
        self.assertLess(script.index('is-active'), script.index('--follow\n'))

    def test_a_reverted_server_change_passes(self):
        self.write('surfd/surfd.py', 'tried'); self.commit('try')
        self.write('surfd/surfd.py', 'surfd/surfd.py'); self.write('surfd/web/board.js', 'fix'); pb.ui_only(self.info(), self.commit('revert + fix'), self.repo)

    def test_the_live_generation_must_carry_its_source_refs_board(self):
        self.write('surfd/web/board.css', 'x'); ref = self.commit('css')
        info = self.info(); info['hashes']['web/board.js'] = '9' * 64
        with self.assertRaisesRegex(SystemExit, r'does not carry its source_ref\'s web/board\.js'): pb.ui_only(info, ref, self.repo)
        self.refused(ref, 'no full source_ref', source_ref='HEAD')
        self.refused(self.base, 'not an ancestor', source_ref=ref)


if __name__ == '__main__':
    unittest.main(verbosity=2)
