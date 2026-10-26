#!/usr/bin/env python3
"""Synthetic filtered seeks and shared WOS/Everything completion contract."""
import logging
from pathlib import Path
import shutil
import unittest
import test_admin as A


class HomeCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = S = A.fresh()
        for folder in (S.MAPS_DIR, S.ZONES_DIR, S.ZONES_LOCAL_DIR):
            Path(folder).mkdir(exist_ok=True)
        names = ['surf_native', 'surf_import', 'surf_both', 'surf_stage', 'surf_next', 'bhop_import']
        for name in names:
            (Path(S.MAPS_DIR) / (name + '.bsp')).write_bytes(b'fixture only')
            (Path(S.ZONES_DIR) / (name + '.json')).write_text('{}')
        tracks = Path(S.DATA_DIR) / 'momtracks.tsv'
        tracks.write_text(''.join(f'{n}\t1\t2\t1\t0\t1\n' for n in names))
        S.MOMTRACKS_PATH = str(tracks)
        S._mt['at'] = -1e9
        S.maps_reset()
        db = S.connect()
        def add(name, tier, player='fixture-self', ms=1000, leg=0, style='clean', label='Fixture Self'):
            db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) VALUES(?,0,?,?,?,?,?,100,100,?,0,'fixture','',1,0)",
                       (name, leg, tier, style, player, label, ms))
        add('surf_native', 'ranked')
        add('surf_import', 'momentum')
        add('surf_both', 'ranked', ms=2000)
        add('surf_both', 'ksf')
        add('surf_stage', 'ranked', leg=1)
        add('bhop_import', 'ksf')
        for i in range(1205):
            add('surf_import', 'ksf', f'fixture-{i:04}', 1000 + i, label=f'Other {i}')
        add('surf_import', 'ksf', ms=5000)
        db.commit(); db.close()
        S.people_reset()
        cls.c = S.app.test_client()
        cls.who = S.web_handle('fixture-self')

    def get(self, path, **query):
        r = self.c.get(path, query_string=query)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        return r.get_json()

    def test_completion_summary_and_population(self):
        game = self.get('/api/board', player=self.who)
        web = self.get('/board/api/player/' + self.who)
        self.assertEqual(game['completion'], web['completion'])
        self.assertEqual(game['completion_wos'], web['completion_wos'])
        self.assertEqual((game['completion']['done'], game['completion_wos']['done']), (4, 2))
        self.assertEqual(game['completion']['of'], 6)
        self.assertEqual(game['completion_wos']['of'], 6)
        self.assertEqual(game['completion_wos']['modes']['bhop']['done'], 0)
        self.assertEqual(game['completion']['modes']['bhop']['done'], 1)
        self.assertEqual(game['wos']['n'], 3)  # native stage is a time, not a completed map
        for source, count in [('wos', 2), ('all', 4)]:
            gm = self.get('/api/board', player=self.who, ct='2', completion_source=source)
            wm = self.get('/board/api/player/' + self.who + '/maps', completion_source=source)
            self.assertEqual(gm['total'], 6)
            self.assertEqual(gm['done'], count)
            self.assertEqual(sum(t['done'] for t in wm['tiers']), count)
            self.assertEqual(sum('ms' in m for m in gm['maps']), count)
            if source == 'wos':
                self.assertTrue(all(m['tr'] == 'ranked' for m in gm['maps'] if 'ms' in m))
        for path, params in [('/api/board', dict(player=self.who, ct='2')),
                             ('/board/api/player/' + self.who + '/maps', {})]:
            self.assertEqual(self.c.get(path, query_string=dict(params, completion_source='bogus')).status_code, 400)

    def test_seek_acts_beyond_first_thousand(self):
        q = dict(map='surf_import', tier='ksf', near=self.who, limit=40)
        body = self.get('/api/board', **q)
        self.assertTrue(body['near']['found'])
        self.assertGreater(body['offset'], 1000)
        own = [r for r in body['rows'] if r['player'] == 'fixture-self']
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]['r'], 1206)
        self.S.RANKED_LINKED = True
        try:
            marked = self.get('/api/board', **dict(q, near=self.who[:8]))
            self.assertTrue(marked['near']['found'])
            self.assertEqual(marked['offset'], body['offset'])
        finally:
            self.S.RANKED_LINKED = False
        self.assertLessEqual(len(body['rows']), 40)
        # Existing pager can continue from the absolute seek offset.
        nxt = self.get('/api/board', map='surf_import', tier='ksf', offset=body['offset'] + len(body['rows']))
        self.assertEqual(nxt['rows'], [])
        for change in [dict(tier='ranked'), dict(style='sw'), dict(leg=1), dict(name='Other')]:
            miss = self.get('/api/board', **dict(q, **change))
            self.assertFalse(miss['near']['found'])
        filtered = self.get('/api/board', **dict(q, name='Fixture Self'))
        self.assertTrue(filtered['near']['found'])
        self.assertEqual(filtered['offset'], 0)
        self.assertEqual(len(filtered['rows']), 1)
        self.assertEqual(filtered['rows'][0]['r'], 1206)  # displayed rank stays global
        merged = self.get('/api/board', **dict(q, map='surf_both', tier='combined'))
        self.assertEqual((merged['near']['tier'], merged['near']['ms']), ('ranked', 2000))
        self.assertEqual(merged['rows'][0]['tr'], 'ksf')  # imported record is faster, but own WOS is preferred
        self.assertEqual(self.c.get('/api/board', query_string=dict(q, near='not-a-player')).status_code, 400)

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()
        for home in A.HOMES:
            shutil.rmtree(home)


if __name__ == '__main__':
    unittest.main()
