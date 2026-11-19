#!/usr/bin/env python3
"""Offline controls for checksum reuse and the marked disposable qualifier.

No engine, service, download, installed asset or owner profile is used here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import tournament_qualify as Q
import tournament_playtest as P

WORK = None


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qualification-unit-', dir=WORK)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'OWNER.md').write_text('Owned synthetic qualification unit fixture.\n')

    def line(self, profile='default', **changes):
        spec = Q.PROFILES[profile]
        parts = ['TQQUAL', 'surf_Exact_css', '1234abcd', 'a' * 64,
                 spec['movement'], str(spec['tick_us']), str(spec['tick_us']), 'surf', '1', '1']
        fields = ('tag', 'name', 'mapcrc', 'zonepin', 'movement', 'tick', 'clock', 'mode', 'generation', 'valid')
        for key, value in changes.items():
            parts[fields.index(key)] = value
        return '|'.join(parts)

    def test_rfc1320_md4_vectors_and_independent_fold(self):
        vectors = [(b'', '31d6cfe0d16ae931b73c59d7e0c089c0'),
                   (b'a', 'bde52cb31de33e46245e05fbdbd6fb24'),
                   (b'abc', 'a448017aaf21d8525fc10ae87aa6729d'),
                   (b'message digest', 'd9130a8164549fe818874806e1c7014b'),
                   (b'abcdefghijklmnopqrstuvwxyz', 'd79e1c308aa5bbcdeea8ed63df412da9')]
        for data, expected in vectors:
            digest = Q.md4(data)
            self.assertEqual(digest.hex(), expected)
            folded = bytes(digest[i] ^ digest[i+4] ^ digest[i+8] ^ digest[i+12] for i in range(4))
            self.assertEqual(Q.fold_md4(digest), int.from_bytes(folded, 'little'))

    def test_native_observation_requires_exact_identity_clock_and_real_course(self):
        positive = Q.parse_observation(self.line(), 'surf_Exact_css', 'default', '1234abcd')
        self.assertEqual((positive['name'], positive['tick_us'], positive['clock_us']), ('surf_Exact_css',15000,15000))
        for change in (dict(name='surf_Exact'), dict(mapcrc='00000000'), dict(mapcrc='1234abce'),
                       dict(zonepin='a'*32), dict(zonepin='A'*64), dict(movement='unqualified'),
                       dict(tick='10000'), dict(clock='10000'), dict(mode='other'),
                       dict(generation='0'), dict(valid='0')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                Q.parse_observation(self.line(**change), 'surf_Exact_css', 'default', '1234abcd')
        with self.assertRaises(ValueError):
            Q.parse_observation(self.line() + '|extra', 'surf_Exact_css', 'default', '1234abcd')

    def test_every_supported_native_version_is_explicit_not_selector_echo(self):
        for profile, spec in Q.PROFILES.items():
            out = Q.parse_observation(self.line(profile), 'surf_Exact_css', profile, '1234abcd')
            self.assertEqual(out['movement'], spec['movement'])
            if profile != 'default':
                with self.assertRaises(ValueError):
                    Q.parse_observation(self.line(profile, movement=profile), 'surf_Exact_css', profile, '1234abcd')

    def test_approval_is_never_implied_by_a_native_observation(self):
        observation = Q.parse_observation(self.line(), 'surf_Exact_css', 'default', '1234abcd')
        asset = dict(sha256='b'*64, map_stamp=[8,9,10])
        proposal = Q.registry_record(observation, asset)
        self.assertEqual(type(proposal['approved']), int)
        self.assertEqual(proposal['approved'], 0)
        self.assertEqual(Q.registry_record(observation, asset, True)['approved'], 1)
        self.assertEqual(set(proposal), {'approved','mapcrc','zonepin','gamemode','sha256','map_stamp'})

    def test_marked_nonfixture_and_played_rigs_refuse_before_native(self):
        for test_only, played in ((False,False), (True,True)):
            rig = self.root / ('rig-' + str(test_only))
            rig.mkdir()
            (rig / 'manifest.json').write_text(json.dumps(dict(test_only=test_only)))
            if played:
                (rig / 'backend').mkdir()
            with mock.patch.object(P, 'Native') as native:
                with self.assertRaisesRegex(ValueError, 'pristine test-only'):
                    Q.qualify_prepared(rig, Path(sys.executable), fixture_approve=True)
                native.assert_not_called()
            self.assertFalse((rig / 'qualification').exists())

    def test_compiler_uses_real_server_source_list_and_stops_before_native_on_failure(self):
        rig = self.root/'prepared'
        for relative in ('src/server','bin','ftesurf','server/ftesurf'):
            (rig/relative).mkdir(parents=True, exist_ok=True)
        compiler = rig/'bin/fteqcc64'
        compiler.write_bytes(b'owned mock compiler')
        (rig/'ftesurf/qwprogs.dat').write_bytes(b'owned mock VM')
        (rig/'src/server/sv_tournament.qc').write_text('// mock input\n')
        (rig/'src/server/sv_main.qc').write_text('void() Frame = { Tour_Frame(); };\n')
        (rig/'src/sv_progs.src').write_text('../ftesurf/qwprogs.dat\n')
        sources = {str(p.relative_to(rig)):Q.digest(p) for p in (rig/'src').rglob('*') if p.is_file()}
        manifest = dict(test_only=True, maps=['surf_Exact_css'], source_files=sources,
                        native={'fteqcc64':Q.digest(compiler)},
                        vms={'qwprogs.dat':Q.digest(rig/'ftesurf/qwprogs.dat')})
        (rig/'manifest.json').write_text(json.dumps(manifest))
        with mock.patch.object(Q.subprocess, 'run', side_effect=RuntimeError('bounded mock compiler failure')) as compile_call, \
                mock.patch.object(P, 'Native') as native:
            with self.assertRaisesRegex(RuntimeError, 'bounded mock compiler'):
                Q.qualify_prepared(rig, compiler)
            self.assertEqual(compile_call.call_args.args[0][-2:], ['-srcfile','sv_progs.src'])
            self.assertEqual(compile_call.call_args.kwargs['cwd'], rig/'qualification/src')
            native.assert_not_called()
        self.assertFalse(json.loads((rig/'qualification/receipt.json').read_text())['ok'])
        self.assertFalse((rig/'fixture-qualifications.json').exists())

    def test_held_asset_records_separate_native_checksum_and_sha(self):
        path = self.root / 'surf_Exact_css.bsp'
        data = b'VBSP' + bytes(range(64))
        path.write_bytes(data)
        out = Q.held_asset(path)
        self.assertEqual(out['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(out['mapcrc'], f'{Q.fold_md4(Q.md4(data)):08x}')
        self.assertEqual(out['map_stamp'], Q.stamp(path))
        with mock.patch.object(Q, 'stamp', side_effect=([len(data),1,1], [len(data),2,1])):
            with self.assertRaisesRegex(ValueError, 'changed'):
                Q.held_asset(path)

    def test_loose_overrides_refuse_without_modification(self):
        for filename in ('surf_Exact_css.ent', 'surf_Exact_css.lmp', 'surf_Exact_css_l_0.lmp'):
            path = self.root / filename
            path.write_bytes(b'owned synthetic override')
            with self.assertRaisesRegex(ValueError, 'Loose map override'):
                Q.reject_sidecars(self.root, 'surf_Exact_css')
            self.assertEqual(path.read_bytes(), b'owned synthetic override')
            path.unlink()
        Q.reject_sidecars(self.root, 'surf_Exact_css')

    def test_seeder_cli_preserves_existing_hashes_and_pending_downloads(self):
        source = self.root / 'csprogs.dat'
        source.write_bytes(b'abc')
        cache = self.root / 'downloads/csprogsvers'
        cache.mkdir(parents=True)
        names = ('other.dat', 'pending.tmp', 'pending.dcl')
        for name in names:
            (cache / name).write_bytes(b'preserve ' + name.encode())
        seeder = Path(Q.__file__).parent / 'seed_csprogs.py'
        result = subprocess.run([sys.executable, '-B', str(seeder), str(source)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout)
        key = '%x' % Q.fold_md4(Q.md4(b'abc'))
        self.assertEqual((cache / (key + '.dat')).read_bytes(), b'abc')
        for name in names:
            self.assertEqual((cache / name).read_bytes(), b'preserve ' + name.encode())

    def test_seeder_import_never_opens_argv_or_seeds_a_cache(self):
        seeder = Path(Q.__file__).parent / 'seed_csprogs.py'
        # Keep module path separate: argv is deliberately an absent input file.
        program = ('import importlib.util,sys; path=sys.argv[1]; '
                   'sys.argv=["seed",sys.argv[2]]; '
                   's=importlib.util.spec_from_file_location("seed",path); '
                   'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); print("IMPORT_ONLY")')
        result = subprocess.run([sys.executable, '-B', '-c', program, str(seeder), str(self.root / 'absent.dat')],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        self.assertEqual((result.returncode, result.stdout.strip()), (0,'IMPORT_ONLY'))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['OWNER.md'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args, rest = parser.parse_known_args()
    WORK = P.owned_root(args.work_root)
    unittest.main(argv=[sys.argv[0], *rest])
