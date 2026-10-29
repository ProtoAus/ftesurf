#!/usr/bin/env python3
"""P1104: /api/board?player= row filters (source=wos, only=wr|top10) and the WOS top tens.
Run from surfd/ with python -B (not -I: surfd is imported from the script's directory)."""
import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

HOME = tempfile.mkdtemp(prefix='profilefilters-')
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, 'test.db'))
import surfd as S
import ksfimport as K

ME, OTHER, IMPORTED = '76561198000000042', '76561198000000043', '76561198000000044'
# (map, tier, my millis, the other player's millis or None)
ROWS = [('surf_a', S.TIER_RANKED, 1000, 2000),      # WOS first place, contested: wr + top10
        ('surf_b', S.TIER_RANKED, 3000, 2500),      # WOS second of two: top10
        ('surf_c', S.TIER_RANKED, 4000, None),      # WOS first of one: wr, not top10
        ('surf_d', S.TIER_MOMENTUM, 1500, 1600),    # Momentum first, contested
        ('surf_e', S.TIER_KSF, 5000, 4500)]         # KSF second of two


class Filters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = S.connect()
        db.execute('DELETE FROM runs')
        sql = ("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,"
               "submitted,replay_id) VALUES (?,0,0,?,'clean',?,?,100,100,?,0,'x',?,1000,0)")
        for i, (m, tier, mine, theirs) in enumerate(ROWS):
            db.execute(sql, (m, tier, ME, 'me', mine, 'm%d' % i))
            if theirs is not None:
                db.execute(sql, (m, tier, OTHER, 'them', theirs, 'o%d' % i))
        db.execute(sql, ('surf_d', S.TIER_MOMENTUM, IMPORTED, 'imp', 1700, 'i0'))
        db.commit()
        db.close()
        S.people_reset()

    def ask(self, args='', who=ME):
        with patch.object(K, 'fetch', side_effect=AssertionError('no network')):
            with S.app.test_client() as c:
                return c.get('/api/board?player=' + S.web_handle(who) + '&limit=50' + args)

    def maps(self, args=''):
        r = self.ask(args)
        self.assertEqual(r.status_code, 200, r.data[:200])
        return sorted(row['map'] for row in r.json['rows']), r.json

    def test_no_filter_is_every_row(self):
        got, j = self.maps()
        self.assertEqual(got, ['surf_a', 'surf_b', 'surf_c', 'surf_d', 'surf_e'])
        self.assertEqual((j['total'], j['rows_source'], j['rows_only']), (5, 'all', ''))

    def test_wos_rows(self):
        got, j = self.maps('&source=wos')
        self.assertEqual(got, ['surf_a', 'surf_b', 'surf_c'])
        self.assertEqual(j['total'], 3)
        self.assertTrue(all(row['tr'] == S.TIER_RANKED for row in j['rows']))

    def test_first_places_and_top_tens(self):
        self.assertEqual(self.maps('&source=wos&only=wr')[0], ['surf_a', 'surf_c'])
        self.assertEqual(self.maps('&source=wos&only=top10')[0], ['surf_a', 'surf_b'])
        got, j = self.maps('&only=wr')
        self.assertEqual(got, ['surf_a', 'surf_c', 'surf_d'])
        self.assertEqual(len(got), j['wr'])             # the list is the figure's
        got, j = self.maps('&only=top10')
        self.assertEqual(got, ['surf_a', 'surf_b', 'surf_d', 'surf_e'])
        self.assertEqual(len(got), j['top10'])

    def test_wos_figures_have_top_tens(self):
        _, j = self.maps()
        self.assertEqual(j['wos'], {'n': 3, 'wr': 2, 'wrc': 1, 'top10': 2, 'maps': 3})
        self.assertEqual(len(self.maps('&source=wos&only=top10')[0]), j['wos']['top10'])

    def test_auto_source(self):
        got, j = self.maps('&source=auto')
        self.assertEqual((got, j['rows_source']), (['surf_a', 'surf_b', 'surf_c'], 'wos'))
        r = self.ask('&source=auto', IMPORTED)            # imported times only: every row
        self.assertEqual(r.status_code, 200, r.data[:200])
        self.assertEqual(([row['map'] for row in r.json['rows']], r.json['rows_source'], r.json['wos']['n']),
                         (['surf_d'], 'all', 0))

    def test_bad_filters_refused(self):
        for bad in ('&source=ksf', '&only=all', '&only=top11', '&source='):
            self.assertEqual(self.ask(bad).status_code, 400, bad)


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        logging.shutdown(); shutil.rmtree(HOME)
