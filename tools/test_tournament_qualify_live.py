#!/usr/bin/env python3
"""Falsifier for tools/tournament_qualify_live.py (synthetic data; the native arm is opt-in).

Native arm: TQLIVE_LIVE=<fake live basedir> TQLIVE_BINARY=<fteqw-sv> TQLIVE_OBSERVER=<observer qwprogs>
TQLIVE_CANDIDATES=<json> runs `run` once and checks the registry against tournament_pool.registry().
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'surfd'))
import tournament_qualify_live as Q  # noqa: E402
import tournament_pool as P          # noqa: E402
import tournament_rules as R         # noqa: E402
import mapmanifest                   # noqa: E402

GOOD = 'TQQUAL|surf_A|ad801abe|' + 'b' * 64 + '|default|15000|15000|surf|8|1'


class Candidates(unittest.TestCase):
    def test_filters_zoned_enabled_surf_bhop_tier_1_10(self):
        text = ('FTESURF-MAPDL 1\n# header\n'
                'dl surf_A surf m 3 10 2026-01-01 0 3 0 - 1 1\n'
                'dl surf_B surf m 3 10 2026-01-01 0 3 0 - 0 1\n'      # not zoned
                'dl surf_C surf m 3 10 2026-01-01 0 3 0 - 1 0\n'      # disabled
                'dl surf_D surf m 0 10 2026-01-01 0 0 0 - 1 1\n'      # untiered
                'dl kz_E kz m 2 10 2026-01-01 0 2 0 - 1 1\n'          # not surf/bhop
                'dl Bhop_F bhop km 11 10 2026-01-01 0 11 0 - 1 1\n'   # tier 11
                'dl bhop_G bhop km 10 10 2026-01-01 0 10 0 surf_A surf_A 1 1\n'
                'dl surf_a surf m 3 10 2026-01-01 0 3 0 - 1 1\n')     # case duplicate
        rows = Q.candidates_from_mapdl(text)
        self.assertEqual([(r['name'], r['mode'], r['tier']) for r in rows], [('surf_A', 'surf', 3), ('bhop_G', 'bhop', 10)])
        with self.assertRaises(ValueError):
            Q.candidates_from_mapdl('nope\n')


class Observation(unittest.TestCase):
    def test_valid_line(self):
        o = Q.parse_observation(GOOD, 'surf_a', 'default', 'surf')
        self.assertEqual((o['mapcrc'], o['gamemode'], o['zone_generation']), ('ad801abe', 'surf', 8))

    def test_each_field_refuses(self):
        bad = {
            'zero crc': GOOD.replace('ad801abe', '00000000'),
            'short crc': GOOD.replace('ad801abe', 'ad801ab'),
            'no zone pin': GOOD.replace('b' * 64, ''),
            'movement': GOOD.replace('|default|', '|unqualified|'),
            'tick': GOOD.replace('|15000|15000|', '|15000|10000|'),
            'gamemode vs list': GOOD.replace('|surf|8|', '|bhop|8|'),
            'generation': GOOD.replace('|surf|8|', '|surf|0|'),
            'invalid course': GOOD[:-1] + '0',
            'other map': GOOD.replace('surf_A', 'surf_B'),
            'truncated': GOOD.rsplit('|', 1)[0],
        }
        for label, line in bad.items():
            with self.assertRaises(ValueError, msg=label):
                Q.parse_observation(line, 'surf_A', 'default', 'surf')
        with self.assertRaises(ValueError):
            Q.parse_observation(GOOD, 'surf_A', 'hl2-post', 'surf')     # profile movement differs


class Base(unittest.TestCase):
    def test_symlinks_dirs_and_plugins_only_and_manifest_without_disablehomedir(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            live = t / 'live'
            for d in ('ftesurf', 'momentum', 'tools'):
                (live / d).mkdir(parents=True)
            for f in ('fteplug_hl2_arm64.so', 'fteplug_hl2_arm64.so.pre1604-x', 'crash.log', 'installed.lst', 'fteqw-svarm64'):
                (live / f).write_text('x')
            linked = Q.build_base(str(live), t / 'base', 'FTEMANIFEST 1\nGAME "FTESurf"\nDISABLEHOMEDIR 1\n  disablehomedir 1\n')
            self.assertEqual(linked, ['fteplug_hl2_arm64.so', 'ftesurf', 'momentum'])
            self.assertTrue(all((t / 'base' / n).is_symlink() for n in linked))
            self.assertFalse((t / 'base' / 'crash.log').exists())
            self.assertNotIn('disablehomedir', (t / 'base/default.fmf').read_text().lower())

    def test_work_root_must_be_owned_private_and_outside_live(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / 'live/sub').mkdir(parents=True)
            (t / 'work').mkdir(mode=0o700)
            self.assertEqual(Q.owned_work(t / 'work', t / 'live'), (t / 'work').resolve())
            os.chmod(t / 'live/sub', 0o700)
            for bad in (t / 'live/sub', t / 'live'):
                with self.assertRaises(ValueError):
                    Q.owned_work(bad, t / 'live')
            os.chmod(t / 'work', 0o755)
            with self.assertRaises(ValueError):
                Q.owned_work(t / 'work', t / 'live')


class Incremental(unittest.TestCase):
    def test_reuse_only_when_stamp_and_zones_unchanged(self):
        stamp, zones = [10, 1, 2], [['/z/online/surf_A.json', 5, 7]]
        state = {'surf_A': dict(map_stamp=stamp, zones=zones)}
        reg = {'surf_A': {'default': dict(map_stamp=stamp)}}
        self.assertTrue(Q.reusable(state, reg, 'surf_A', 'default', stamp, zones))
        self.assertFalse(Q.reusable(state, reg, 'surf_A', 'default', [10, 1, 3], zones))          # file touched
        self.assertFalse(Q.reusable(state, reg, 'surf_A', 'default', stamp, [['/z/online/surf_A.json', 5, 8]]))
        self.assertFalse(Q.reusable(state, reg, 'surf_A', 'hl2-post', stamp, zones))              # other profile
        self.assertFalse(Q.reusable({}, reg, 'surf_A', 'default', stamp, zones))

    def test_zone_stats_sees_every_precedence_directory(self):
        with tempfile.TemporaryDirectory() as t:
            dirs = [os.path.join(t, d) for d in ('a', 'b', 'c')]
            for d in dirs:
                os.mkdir(d)
            Path(dirs[0], 'Surf_X.json').write_text('{}')
            Path(dirs[2], 'surf_x.json').write_text('{}')
            got = [os.path.relpath(p, t) for p, _, _ in Q.zone_stats(dirs, 'Surf_X')]
            self.assertEqual(got, [os.path.join('a', 'Surf_X.json'), os.path.join('c', 'surf_x.json')])


class RegistryAcceptance(unittest.TestCase):
    """The tool's record() output must be what tournament_pool.registry()/catalogue() accept."""
    def test_pool_counts_recorded_maps(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            maps = {'surf_A': 'surf', 'Bhop_B': 'bhop', 'surf_C': 'surf'}
            records = {}
            for name, mode in maps.items():
                p = t / (name + '.bsp')
                p.write_bytes(b'VBSP' + name.encode())
                o = Q.parse_observation(GOOD.replace('surf_A', name).replace('|surf|8|', '|%s|8|' % mode), name, 'default', mode)
                records[name] = {'default': Q.record(o, Q.sha256_file(p), Q.stamp(p))}
            reg = t / 'q.json'
            reg.write_text(json.dumps(dict(v=1, maps=records), separators=(',', ':')))
            self.assertEqual(set(P.registry(str(reg))), set(maps))
            listed = t / 'mapdl.txt'
            listed.write_text('FTESURF-MAPDL 1\n' + ''.join('dl %s %s m 1 1 2026-01-01 0 1 0\n' % (n, m) for n, m in maps.items()))
            bsp = {n.lower(): n for n in maps}
            d = SimpleNamespace(setting=lambda k, v='': str(reg) if k == 'SURFD_TOURNAMENT_QUALIFICATIONS' else v,
                                map_tiers=lambda: {k: 1 for k in bsp}, map_index=lambda: (bsp, set(bsp)),
                                zone_file_index=lambda: set(bsp), maps_root=str(t))
            db = sqlite3.connect(':memory:')
            db.execute(mapmanifest.DDL)
            with patch.object(mapmanifest, 'LIST_PATH', str(listed)):
                mapmanifest._listed = (None, {})
                surf, unq = P.catalogue(db, d, R.settings(dict(kind='surf', tiers='1', profile='default', pool='-')))
                self.assertEqual((sorted(surf), unq), (['surf_A', 'surf_C'], 0))
                self.assertEqual(sorted(P.catalogue(db, d, R.settings(dict(kind='bhop', tiers='1', profile='default', pool='-')))[0]), ['Bhop_B'])
                (t / 'surf_C.bsp').write_bytes(b'VBSP changed after qualification')   # stamp drift unqualifies
                surf, unq = P.catalogue(db, d, R.settings(dict(kind='surf', tiers='1', profile='default', pool='-')))
                self.assertEqual((sorted(surf), unq), (['surf_A'], 1))


@unittest.skipUnless(os.environ.get('TQLIVE_LIVE'), 'native arm: set TQLIVE_LIVE/BINARY/OBSERVER/CANDIDATES')
class Native(unittest.TestCase):
    def test_run_against_fake_live(self):
        env = os.environ
        with tempfile.TemporaryDirectory() as t:
            os.chmod(t, 0o700)
            rc = Q.main(['run', '--work', t, '--live', env['TQLIVE_LIVE'], '--binary', env['TQLIVE_BINARY'],
                         '--observer', env['TQLIVE_OBSERVER'], '--candidates', env['TQLIVE_CANDIDATES'], '--timeout', '60'])
            self.assertEqual(rc, 0)
            run = next(Path(t).glob('run-*'))
            receipt = json.loads((run / 'receipt.json').read_text())
            self.assertGreater(receipt['counts']['valid'], 0)
            self.assertTrue(set(P.registry(str(run / 'qualifications.json'))))
            # a second run reuses every unchanged valid map without starting a server
            rc = Q.main(['run', '--work', t, '--live', env['TQLIVE_LIVE'], '--binary', env['TQLIVE_BINARY'],
                         '--observer', env['TQLIVE_OBSERVER'], '--candidates', env['TQLIVE_CANDIDATES'],
                         '--previous', str(run / 'qualifications.json'), '--previous-state', str(run / 'state.json')])
            again = json.loads((sorted(Path(t).glob('run-*'))[-1] / 'receipt.json').read_text())
            self.assertEqual(again['counts']['reused'], receipt['counts']['valid'])
            self.assertFalse(any(m.get('server_started') for m in again['maps']))


if __name__ == '__main__':
    unittest.main()
