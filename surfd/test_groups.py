#!/usr/bin/env python3
"""P1590: Groups (G1-G6 off an imported board) and one-map-per-family completion.
Synthetic database only. Run from surfd/ with python -B."""
import json
import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

HOME = tempfile.mkdtemp(prefix='groups-')
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, 'test.db'), SURFD_MAPS=os.path.join(HOME, 'maps'))
os.makedirs(os.path.join(HOME, 'maps'))
import surfd as S
import ksfimport as K

ME = '76561198000000042'
SQL = ("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,"
       "submitted,replay_id) VALUES (?,?,?,?,?,?,?,100,100,?,0,'x',?,?,0)")


def put(db, rows):
    for i, (m, track, leg, tier, style, who, ms) in enumerate(rows):
        db.execute(SQL, (m, track, leg, tier, style, who, who[:12], ms, 'r%s%d' % (who, i), 1000 + i))


class Ladder(unittest.TestCase):
    def test_screenshots(self):
        # Lex's calculator, 16 Nov: Top 10, then G1..G6's last ranks.
        self.assertEqual(S.group_ranks(50000), [10, 1010, 2035, 4098, 8256, 16630, 33500])
        self.assertEqual(S.group_ranks(150), [10, 15, 22, 32, 47, 69, 101])
        self.assertEqual(S.group_ranks(50), [10, 15, 20, 25, 31, 39, 50])

    def test_small_boards(self):
        self.assertIsNone(S.group_ranks(10))
        self.assertEqual(S.group_ranks(12), [10, 12, 12, 12, 12, 12, 12])   # empty groups repeat
        for x in range(11, 3000, 7):
            r = S.group_ranks(x)
            self.assertEqual(r, sorted(r))
            self.assertLessEqual(r[-1], x)

    def test_group_of(self):
        cuts = [100, 200, 300, 300, 400, 500, 600]
        self.assertEqual([S.group_of(ms, cuts) for ms in (50, 100, 101, 300, 301, 600, 601)],
                         [0, 0, 1, 2, 4, 6, 7])


class Groups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = S.connect()
        db.execute('DELETE FROM runs')
        rows = []
        # surf_g main: 150 Momentum times 10000..10149 ms, 40 KSF; stage 1 KSF only (50).
        rows += [('surf_g', 0, 0, S.TIER_MOMENTUM, 'clean', 'm%03d' % i, 10000 + i) for i in range(150)]
        rows += [('surf_g', 0, 0, S.TIER_KSF, 'clean', 'k%03d' % i, 9000 + i) for i in range(40)]
        rows += [('surf_g', 0, 1, S.TIER_KSF, 'clean', 'k%03d' % i, 5000 + i * 10) for i in range(50)]
        rows += [('surf_g', 0, 0, S.TIER_KSF, 'sw', 'k%03d' % i, 20000 + i) for i in range(30)]
        # ME: main 10030 (rank 31 of the Momentum board: G3 ends at 32), stage 1 slower than all of KSF.
        rows += [('surf_g_css', 0, 0, S.TIER_RANKED, 'clean', ME, 10100)]     # rank 101: G6
        rows += [('surf_g', 0, 0, S.TIER_RANKED, 'clean', ME, 10030),
                 ('surf_g', 0, 1, S.TIER_RANKED, 'clean', ME, 99999),
                 ('surf_g', 0, 0, S.TIER_RANKED, 'segmented', ME, 9000)]
        put(db, rows)
        db.commit()
        db.close()
        os.makedirs(os.path.join(S.DATA_DIR, 'mapwatch'), exist_ok=True)
        with open(os.path.join(S.DATA_DIR, 'mapwatch', 'catalogue.json'), 'w') as fh:
            json.dump({'maps': {'surf_g': {}, 'surf_g_css': {'of': 'surf_g'}}}, fh)
        S._variants['at'] = None
        S.people_reset()
        S.groups_forget()

    def ask(self, args, mapname='surf_g'):
        with patch.object(K, 'fetch', side_effect=AssertionError('no network')):
            with S.app.test_client() as c:
                r = c.get('/api/board?groups=' + mapname + args)
        self.assertEqual(r.status_code, 200, r.data[:200])
        return r.json

    def test_cuts_are_the_reference_times(self):
        legs = {(l['track'], l['leg']): l for l in self.ask('&style=clean')['legs']}
        main = legs[(0, 0)]
        self.assertEqual((main['src'], main['x']), ('momentum', 150))   # the bigger board, not KSF's 40
        self.assertEqual(main['ms'], [10000 + r - 1 for r in S.group_ranks(150)])
        st = legs[(0, 1)]
        self.assertEqual((st['src'], st['x']), ('ksf', 50))
        self.assertEqual(st['ms'], [5000 + (r - 1) * 10 for r in S.group_ranks(50)])
        self.assertNotIn('mine', main)                     # nobody asked

    def test_my_group(self):
        j = self.ask('&style=clean&me=' + S.web_handle(ME))
        self.assertTrue(j['player_known'])
        legs = {(l['track'], l['leg']): l for l in j['legs']}
        self.assertEqual((legs[(0, 0)]['mine'], legs[(0, 0)]['g']), (10030, 3))   # rank 31: G3 is 23..32
        self.assertEqual(legs[(0, 1)]['g'], 7)                                  # past every cut: ungrouped

    def test_second_build_ladders_on_its_base(self):
        j = self.ask('&style=clean&me=' + S.web_handle(ME), 'surf_g_css')
        main = {(l['track'], l['leg']): l for l in j['legs']}[(0, 0)]
        self.assertEqual((main['src'], main['x']), ('momentum', 150))
        self.assertEqual((main['mine'], main['g']), (10100, 6))     # its own build's time, rank 101

    def test_directions_ladder_on_ksf_and_segmented_has_none(self):
        sw = self.ask('&style=sw')['legs']
        self.assertEqual([(l['src'], l['x']) for l in sw], [('ksf', 30)])
        self.assertEqual(self.ask('&style=segmented&me=' + S.web_handle(ME))['legs'], [])

    def test_refusals(self):
        with S.app.test_client() as c:
            self.assertEqual(c.get('/api/board?groups=surf_g&style=nope').status_code, 400)
            self.assertEqual(c.get('/api/board?groups=surf_g&me=XYZ').status_code, 400)
            self.assertEqual(c.get('/api/board?groups=').status_code, 400)


class Families(unittest.TestCase):
    """surf_x and its CS:S build surf_x_css are one map to finish."""
    @classmethod
    def setUpClass(cls):
        db = S.connect()
        db.execute('DELETE FROM runs')
        put(db, [('surf_w', 0, 0, S.TIER_MOMENTUM, 'clean', ME, 900),         # disabled in the pool
                 ('surf_w_css', 0, 0, S.TIER_RANKED, 'clean', 'someone', 950),
                 ('surf_x', 0, 0, S.TIER_RANKED, 'clean', ME, 1000),
                 ('surf_x_css', 0, 0, S.TIER_RANKED, 'clean', 'someone', 1100),
                 ('surf_y', 0, 0, S.TIER_RANKED, 'clean', 'someone', 1200),
                 ('surf_y_css', 0, 0, S.TIER_RANKED, 'clean', ME, 1300),
                 ('surf_z', 0, 0, S.TIER_RANKED, 'clean', 'someone', 1400)])
        db.execute("INSERT INTO map_pool VALUES('surf_w',0,1)")
        db.commit()
        db.close()
        os.makedirs(os.path.join(S.DATA_DIR, 'mapwatch'), exist_ok=True)
        with open(os.path.join(S.DATA_DIR, 'mapwatch', 'catalogue.json'), 'w') as fh:
            json.dump({'maps': {'surf_w': {}, 'surf_w_css': {'of': 'surf_w'},
                                'surf_x': {}, 'surf_x_css': {'of': 'surf_x'}, 'surf_y': {},
                                'surf_y_css': {'of': 'surf_y'}, 'surf_z': {}}}, fh)
        S._variants['at'] = None
        S.people_reset()

    def ask(self, args=''):
        tiers = {'surf_w': 5, 'surf_w_css': 5, 'surf_x': 2, 'surf_x_css': 1, 'surf_y': 3,
                 'surf_y_css': 3, 'surf_z': 4}
        with patch.object(K, 'fetch', side_effect=AssertionError('no network')), \
                patch.object(S, 'map_tiers', return_value=tiers):
            with S.app.test_client() as c:
                r = c.get('/api/board?player=' + S.web_handle(ME) + '&limit=50' + args)
        self.assertEqual(r.status_code, 200, r.data[:200])
        return r.json

    def test_totals_count_a_family_once(self):
        comp = self.ask()['completion']
        # w (its base finished, the base out of the pool), x, y (its css); z not
        self.assertEqual((comp['done'], comp['of']), (3, 4))
        self.assertEqual({t['tier']: (t['done'], t['of']) for t in comp['tiers']},
                         {2: (1, 1), 3: (1, 1), 4: (0, 1), 5: (1, 1)})   # the base's tier, not the easier build's
        wos = self.ask()['completion_wos']
        self.assertEqual((wos['done'], wos['of']), (2, 4))         # w's finish is Momentum's

    def test_lists_count_a_family_once(self):
        done = self.ask('&ct=a1')
        self.assertEqual(sorted(m['map'] for m in done['maps']), ['surf_w_css', 'surf_x', 'surf_y_css'])
        self.assertEqual(done['total'], 3)
        w = next(m for m in done['maps'] if m['map'] == 'surf_w_css')
        self.assertEqual(w['ms'], 900)                              # the base's finish, shown on the build held
        self.assertEqual([m['map'] for m in self.ask('&ct=a0')['maps']], ['surf_z'])


def tearDownModule():
    logging.shutdown()                  # surfd's log handler holds logs/surfd.log open (Windows)
    try:
        shutil.rmtree(HOME)
    except OSError as exc:
        print('test_groups: scratch home %s not removed: %s' % (HOME, exc))


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    unittest.main()
