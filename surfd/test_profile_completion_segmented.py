#!/usr/bin/env python3
"""P1297: a segmented finish is not a completion. The profile's maps finished (completion, completion_wos, ct=a1/a0)
leave it out; the maps with a time (ct=p) and the board rows keep it.
Run from surfd/ with python -B (not -I: surfd is imported from the script's directory)."""
import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

HOME = tempfile.mkdtemp(prefix='profileseg-')
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, 'test.db'), SURFD_MAPS=os.path.join(HOME, 'maps'))
os.makedirs(os.path.join(HOME, 'maps'))
import surfd as S
import ksfimport as K

ME = '76561198000000042'
# (map, tier, style, millis): surf_a clean, surf_both clean and segmented, the two seg maps segmented only
ROWS = [('surf_a', S.TIER_RANKED, 'clean', 1000), ('surf_both', S.TIER_RANKED, 'clean', 2000),
        ('surf_both', S.TIER_RANKED, 'segmented', 1500), ('surf_seg', S.TIER_RANKED, 'segmented', 1200),
        ('surf_ksfseg', S.TIER_KSF, 'segmented_sw', 3000)]
MAPS = {'surf_a', 'surf_both', 'surf_seg', 'surf_ksfseg'}


class Segmented(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = S.connect()
        db.execute('DELETE FROM runs')
        sql = ("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,"
               "submitted,replay_id) VALUES (?,0,0,?,?,?,'me',100,100,?,0,'x',?,1000,0)")
        for i, (m, tier, style, ms) in enumerate(ROWS):
            db.execute(sql, (m, tier, style, ME, ms, 'r%d' % i))
        db.commit()
        db.close()
        S.people_reset()

    def ask(self, args=''):
        with patch.object(K, 'fetch', side_effect=AssertionError('no network')), \
                patch.object(S, 'map_tiers', return_value={m: 1 for m in MAPS}):
            with S.app.test_client() as c:
                r = c.get('/api/board?player=' + S.web_handle(ME) + '&limit=50' + args)
        self.assertEqual(r.status_code, 200, r.data[:200])
        return r.json

    def test_finished_lists_leave_segmented_out(self):
        self.assertEqual(sorted(m['map'] for m in self.ask('&ct=a1')['maps']), ['surf_a', 'surf_both'])
        self.assertEqual(sorted(m['map'] for m in self.ask('&ct=a0')['maps']), ['surf_ksfseg', 'surf_seg'])
        both = next(m for m in self.ask('&ct=a1')['maps'] if m['map'] == 'surf_both')
        self.assertEqual((both['ms'], both['s']), (2000, 'clean'))     # the clean time, not the faster segmented one

    def test_completion_counts_leave_segmented_out(self):
        j = self.ask()
        self.assertEqual(j['completion']['done'], 2)
        self.assertEqual(j['completion_wos']['done'], 2)

    def test_maps_with_a_time_and_rows_keep_them(self):
        p = self.ask('&ct=p')
        self.assertEqual(sorted(m['map'] for m in p['maps']), sorted(MAPS))
        self.assertEqual(p['done'], 2)      # the header's "N of M finished"; surf_both's best shown is segmented
        both = next(m for m in p['maps'] if m['map'] == 'surf_both')
        self.assertEqual((both['ms'], both['s']), (1500, 'segmented'))
        self.assertEqual(self.ask()['total'], len(ROWS))

    def test_site_map_lists_leave_segmented_out(self):
        with patch.object(S, 'map_tiers', return_value={m: 1 for m in MAPS}):
            with S.app.test_client() as c:
                r = c.get('/board/api/player/' + S.web_handle(ME) + '/maps')
        self.assertEqual(r.status_code, 200, r.data[:200])
        t1 = r.json['tiers'][0]
        self.assertEqual((t1['tier'], t1['done']), (1, 2))
        self.assertEqual(sorted(m['map'] for m in t1['maps'] if 'ms' in m), ['surf_a', 'surf_both'])


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        logging.shutdown(); shutil.rmtree(HOME)
