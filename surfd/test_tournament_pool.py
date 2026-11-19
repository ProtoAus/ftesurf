"""Synthetic exact-build qualifications only; no native or production assets."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import mapmanifest
import tournament_pool as P
import tournament_rules as R


class Pool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tournament-pool-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute(mapmanifest.DDL)
        self.names = ['surf_Exact', 'surf_Exact_css', 'bhop_test', 'kz_native', 'surf_unknown', 'surf_high']
        self.bsp = {n.lower(): n for n in self.names}
        self.timed = set(self.bsp)
        self.tiers = {n.lower(): 1 for n in self.names[:4]} | {'surf_high': 4}
        self.listed = self.root / 'mapdl.txt'
        self.listed.write_text('FTESURF-MAPDL 1\n' + ''.join(
            'dl %s %s m 0 1 2026-01-01 0 %d 2\n' %
            (n, 'bhop' if n.startswith(('bhop_', 'kz_')) else 'surf', self.tiers.get(n.lower(), 0))
            for n in self.names))
        self.registry = self.root / 'qualifications.json'
        self.records = {}
        for name in self.names:
            path = self.root / (name + '.bsp')
            path.write_bytes(b'SYNTHETIC fixture ' + name.encode())
            st = path.stat()
            pin = dict(approved=1, mapcrc='12345678', zonepin='b'*64, sha256='c'*64,
                       gamemode='bhop' if name.startswith(('bhop_', 'kz_')) else 'surf',
                       map_stamp=[st.st_size, st.st_mtime_ns, st.st_ctime_ns])
            self.records[name] = {'default': pin}
        self.save()
        self.env = {'SURFD_TOURNAMENT_QUALIFICATIONS': str(self.registry)}
        self.d = SimpleNamespace(setting=lambda k, v='': self.env.get(k, v),
                                 map_tiers=lambda: self.tiers, map_index=lambda: (self.bsp, self.timed),
                                 zone_file_index=lambda: set(self.bsp), maps_root=str(self.root))
        self.list_patch = patch.object(mapmanifest, 'LIST_PATH', str(self.listed))
        self.list_patch.start()
        self.addCleanup(self.list_patch.stop)
        mapmanifest._listed = (None, {})

    def save(self):
        self.registry.write_text(json.dumps(dict(v=1, maps=self.records)))

    def settings(self, **fields):
        return R.settings(dict(kind='surf', tiers='7', profile='default', pool='-') | fields)

    def pool(self, **fields):
        return P.catalogue(self.db, self.d, self.settings(**fields))

    def test_defaults_filters_exact_builds_and_provenance(self):
        self.assertEqual(R.settings({}, legacy=True), dict(kind='surf', tiers=7, profile='default', tick_us=15000, pool=None))
        rows, unqualified = self.pool()
        self.assertEqual(list(rows), ['surf_Exact', 'surf_Exact_css'])
        self.assertEqual(unqualified, 0)
        self.assertEqual((rows['surf_Exact']['tier'], rows['surf_Exact']['mt'], rows['surf_Exact']['kt']), (1, 1, 2))
        self.assertEqual(list(self.pool(kind='bhop')[0]), ['bhop_test', 'kz_native'])
        self.assertEqual(list(self.pool(tiers=str(1 << 20))[0]), ['surf_unknown'])
        self.assertEqual(list(self.pool(tiers='8')[0]), ['surf_high'])
        # Actual tier is canonical map_tiers, not MAPDL's independent raw provenance.
        self.tiers['surf_exact_css'] = 5
        self.assertEqual(list(self.pool()[0]), ['surf_Exact'])

    def test_manual_empty_exact_names_and_no_silent_fill(self):
        self.assertEqual(P.selected(self.db, self.d, self.settings(pool='_')), {})
        selected = P.selected(self.db, self.d, self.settings(pool='surf_Exact_css'))
        self.assertEqual(list(selected), ['surf_Exact_css'])
        for raw in ('surf_exact', 'surf_Exact,surf_Exact', 'surf_Exact,', '../surf_Exact', '/surf_Exact', 'surf/Exact', 'a'*65, '', 'é'):
            with self.assertRaises(R.Refusal, msg=raw):
                P.selected(self.db, self.d, self.settings(pool=raw))
        self.db.execute('INSERT INTO map_pool VALUES(?,?,?)', ('surf_exact_css', 0, 0))
        with self.assertRaises(R.Refusal):
            P.selected(self.db, self.d, self.settings(pool='surf_Exact_css'))
        self.assertEqual(list(self.pool()[0]), ['surf_Exact'])

    def test_unset_missing_unapproved_stale_and_profile_never_infer(self):
        for path in ('', str(self.root / 'missing')):
            self.env['SURFD_TOURNAMENT_QUALIFICATIONS'] = path
            rows, count = self.pool()
            self.assertEqual((rows, count), ({}, 2))
        self.env['SURFD_TOURNAMENT_QUALIFICATIONS'] = str(self.registry)
        self.assertEqual(self.pool(profile='hl2-pre'), ({}, 2))
        self.records['surf_Exact']['default']['approved'] = 0
        self.save()
        self.assertEqual(list(self.pool()[0]), ['surf_Exact_css'])
        (self.root / 'surf_Exact_css.bsp').write_bytes(b'changed')
        self.assertEqual(self.pool(), ({}, 2))

    def test_catalogue_none_not_empty_and_registry_strict(self):
        self.tiers = None
        with self.assertRaisesRegex(R.Refusal, 'difficulty catalogue unavailable'):
            self.pool()
        self.tiers = {}
        self.assertEqual(self.pool()[0], {})
        self.listed.unlink()
        with self.assertRaisesRegex(R.Refusal, 'map catalogue unavailable'):
            self.pool()
        for raw in ('{}', '{"v":1,"v":1,"maps":{}}', '{"v":true,"maps":{}}', '[1]', '{', 'x'*(P.MAX_BYTES+1)):
            self.registry.write_text(raw)
            with self.assertRaises(R.Refusal, msg=raw[:50]):
                P.registry(self.registry)
        for key, value in (('mapcrc','00000000'), ('mapcrc','ABCDEF12'), ('zonepin','b'*8),
                           ('sha256','c'*40), ('map_stamp',[1,2]), ('approved',True), ('gamemode','race')):
            records = copy.deepcopy(self.records)
            records['surf_Exact']['default'][key] = value
            self.registry.write_text(json.dumps(dict(v=1, maps=records)))
            with self.assertRaises(R.Refusal, msg=key):
                P.registry(self.registry)

    def test_settings_malformed_and_profile_matrix(self):
        for fields in ({}, dict(kind='race'), dict(tiers='07'), dict(tiers='0'), dict(tiers='2097152'),
                       dict(tiers='1.0'), dict(profile='ag'), dict(pool=','.join('map%d'%n for n in range(25)))):
            with self.assertRaises(R.Refusal):
                R.settings(fields) if not fields else self.settings(**fields)
        self.assertEqual(list(R.PROFILES), ['default','hl2-pre','hl2-post','ag-100','ag-250','ag-1000','cs16'])
        self.assertEqual([p['tick_us'] for p in R.PROFILES.values()], [15000,15000,15000,10000,4000,1000,10000])
        self.assertEqual([p['unranked'] for p in R.PROFILES.values()], [0,1,1,1,1,1,1])

    def test_frozen_selected_records_revalidated_not_unselected_additions(self):
        rows, _ = self.pool()
        m = dict(settings=self.settings(), schedule=['surf_Exact'], reserve='surf_Exact_css',
                 _pins={n: c['pin'] for n,c in rows.items()})
        P.revalidate(self.db, self.d, m)
        # A newly rated but unselected map does not change the frozen event.
        self.tiers['surf_unknown'] = 2
        P.revalidate(self.db, self.d, m)
        self.records['surf_Exact_css']['default']['zonepin'] = 'd'*64
        self.save()
        with self.assertRaisesRegex(R.Refusal, 'qualification changed'):
            P.revalidate(self.db, self.d, m)


if __name__ == '__main__':
    unittest.main()
