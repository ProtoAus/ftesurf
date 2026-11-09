#!/usr/bin/env python3
"""P1448 falsifiers: the Fetch button queues, the crons spend. No network."""
import json
import os
import subprocess
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_ksfimport as T
import fetchq as F
import ksfprofile as P
import momprofile as MP
import momwatch as W
S, K = T.S, T.K

PLAYER = '76561198000000077'
TSV = ("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n"
       "surf_fq\t9\t3\t1\t0\t1\n"
       "surf_fq\t9\t3\t2\t0\t1\n"          # a bhop board on a surf map: not ours
       "surf_fq\t9\t3\t1\t1\t2\n"          # stage 2
       "surf_fq\t9\t3\t1\t2\t3\n")         # bonus 3


class Fetch(unittest.TestCase):
    def setUp(self):
        self.db = S.connect()
        F.ensure(self.db)
        for t in ("momtopup", "profilefetch", "ksftopup", "ksfprofiles", "momprofiles", "mapwant"):
            self.db.execute("DELETE FROM %s" % t)
        self.db.execute("DELETE FROM runs WHERE map='surf_fq' OR player=?", (PLAYER,))
        self.db.commit()
        self.tracks = os.path.join(T.HOME, "momtracks-fq.tsv")
        Path(self.tracks).write_text(TSV)
        self.old_tracks, S.MOMTRACKS_PATH = S.MOMTRACKS_PATH, self.tracks
        maps = Path(S.DATA_DIR) / 'ksf' / 'maps'
        maps.mkdir(parents=True, exist_ok=True)
        self.meta = maps / 'surf_fq.json'
        self.meta.write_text(json.dumps([dict(name='surf_fq', isLinear=False, cp_count=4, b_count=3)]))
        S._rate.clear()

    def tearDown(self):
        S.MOMTRACKS_PATH = self.old_tracks
        self.meta.unlink()
        self.db.close()

    def test_mom_board_is_the_maps_own_gamemode_per_leg(self):
        self.assertEqual(F.mom_board(self.tracks, 'surf_fq', 0, 0), (9, 1, 0, 1))
        self.assertEqual(F.mom_board(self.tracks, 'SURF_FQ', 0, 2), (9, 1, 1, 2))
        self.assertEqual(F.mom_board(self.tracks, 'surf_fq', 3, 0), (9, 1, 2, 3))
        self.assertIsNone(F.mom_board(self.tracks, 'surf_fq', 0, 3))
        self.assertIsNone(F.mom_board(self.tracks, 'surf_other', 0, 0))
        self.assertIsNone(F.mom_board(self.tracks + '.absent', 'surf_fq', 0, 0))
        self.assertEqual(F.board_key((9, 1, 2, 3)), '9_g1_t23')

    def test_mom_queue_rules(self):
        key = ('surf_fq', 0, 0)
        self.assertEqual(F.mom_enqueue(self.db, ('surf_fq', 0, 3), 100, self.tracks), (None, 404))
        body, code = F.mom_enqueue(self.db, key, 100, self.tracks)
        self.assertEqual((code, body['state'], body['target']), (202, 'queued', 100))
        body, code = F.mom_enqueue(self.db, key, 101, self.tracks)     # coalesced, not stacked
        self.assertEqual((code, body['target']), (202, 100))
        self.assertEqual(F.mom_finish(self.db, key, 100, 40, 40, False, 102), 'exhausted')
        self.assertEqual(F.mom_enqueue(self.db, key, 103, self.tracks)[0]['state'], 'exhausted')
        body, code = F.mom_enqueue(self.db, key, 103 + F.RETRY_AFTER, self.tracks)
        self.assertEqual((code, body['state']), (202, 'queued'))
        self.assertEqual(F.mom_finish(self.db, key, 100, 100, 500, False, 104), 'done')
        self.assertEqual(F.mom_finish(self.db, key, 100, 100, 500, False, 104), 'done')   # CAS: no-op
        with patch.object(F, 'MAX_ACTIVE', 1):
            F.mom_enqueue(self.db, ('surf_fq', 0, 2), 200, self.tracks)
            self.assertEqual(F.mom_enqueue(self.db, ('surf_fq', 3, 0), 200, self.tracks), (None, 429))

    def test_http_queues_both_sources_on_a_map_with_no_rows(self):
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs WHERE map='surf_fq'").fetchone()[0], 0)
        with patch.object(K, 'fetch', side_effect=AssertionError('HTTP must not fetch')), \
             S.app.test_client() as c:
            r = c.post('/api/board?fetch=1&map=surf_fq')
            self.assertEqual(r.status_code, 202)
            self.assertEqual((r.json['ksf']['state'], r.json['momentum']['state']), ('queued', 'queued'))
            r = c.post('/board/api/map?fetch=1&map=surf_fq&track=3')        # the site's path
            self.assertEqual((r.status_code, r.json['momentum']['state']), (202, 'queued'))
            r = c.post('/api/board?fetch=1&map=surf_fq&leg=2&style=sw')     # no Momentum styles
            self.assertEqual((r.json['ksf']['state'], r.json['momentum']['state']), ('queued', 'unknown'))
            r = c.post('/api/board?fetch=1&map=surf_fq&leg=3')              # KSF has 4 stages
            self.assertEqual((r.status_code, r.json['momentum']['state']), (202, 'unknown'))
            self.assertEqual(c.post('/api/board?fetch=1&map=surf_nowhere').status_code, 404)
            self.assertEqual(c.post('/api/board?fetch=1&map=surf_fq&style=segmented').status_code, 400)
            self.assertEqual(c.post('/api/board?ksfmore=1&map=surf_fq').status_code, 202)   # old clients
        self.assertEqual(self.db.execute("SELECT map FROM mapwant").fetchall()[0][0], 'surf_fq')
        self.assertEqual(KT_recent(self.db), {('surf_fq', 0, 0, 'clean'), ('surf_fq', 3, 0, 'clean'),
                                              ('surf_fq', 0, 2, 'sw'), ('surf_fq', 0, 3, 'clean')})

    def test_http_rate_limit(self):
        with S.app.test_client() as c:
            codes = [c.post('/api/board?fetch=1&map=surf_fq').status_code for _ in range(S.FETCH_RATE + 1)]
        self.assertEqual(codes[-1], 429)

    def test_profile_fetch_queues_both_full_walks(self):
        self.db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,"
                        "node,runid,submitted,replay_id) VALUES ('surf_fq',0,0,'ksf','clean',?,'fx',100,100,"
                        "1000,0,'ksf','fq',1000,0)", (PLAYER,))
        self.db.commit()
        S.people_reset()
        h = S.web_handle(PLAYER)
        with patch.object(K, 'fetch', side_effect=AssertionError('HTTP must not fetch')), \
             S.app.test_client() as c:
            r = c.post('/board/api/map?fetch=1&player=' + h)
            self.assertEqual(r.status_code, 202)
            self.assertEqual((r.json['ksf_sync']['state'], r.json['mom_sync']['state'], r.json['full']),
                             ('queued', 'queued', True))
            self.assertEqual(c.post('/api/board?fetch=1&player=aaaaaaaaaaaa').status_code, 404)
            self.assertEqual(c.post('/api/board?fetch=1&player=zz').status_code, 400)
            self.assertIn('mom_sync', c.get('/api/board?player=' + h).json)
        self.assertTrue(P.is_account(K, PLAYER))          # walks past a view's limits
        now = int(time.time())
        # FORCE_TTL: a press re-walks after an hour, a view does not within a day.
        self.db.execute("UPDATE ksfprofiles SET state='complete', updated=?", (now - 2 * P.FORCE_TTL,))
        self.db.execute("UPDATE momprofiles SET state='complete', updated=?", (now - 2 * MP.FORCE_TTL,))
        self.db.commit()
        self.assertEqual(P.enqueue(self.db, PLAYER, now)['state'], 'complete')
        self.assertEqual(P.enqueue(self.db, PLAYER, now, force=True)['state'], 'queued')
        self.assertEqual(MP.enqueue(self.db, PLAYER, now)['state'], 'complete')
        self.assertEqual(MP.enqueue(self.db, PLAYER, now, force=True)['state'], 'queued')

    def test_fetched_profile_walks_ahead_of_views_and_caps(self):
        now = int(time.time())
        view, fetched = str(int(PLAYER) + 1), PLAYER
        P.enqueue(self.db, view, now - 10)
        P.enqueue(self.db, fetched, now)
        self.assertEqual(P.pending(self.db)[0][0], view)
        self.assertTrue(F.fetch_profile(self.db, fetched, now))
        self.assertEqual(P.pending(self.db)[0][0], fetched)
        with patch.object(F, 'MAX_FETCHED', 1):
            self.assertFalse(F.fetch_profile(self.db, view, now))
            self.assertTrue(F.fetch_profile(self.db, fetched, now))      # a re-press is not new
        self.db.execute("DROP TABLE profilefetch")                       # an older generation's DB
        self.db.commit()
        self.assertEqual(len(P.pending(self.db)), 2)
        self.assertFalse(F.fetched(self.db, fetched, now))
        F.ensure(self.db)

    def test_momwatch_spends_the_queue_first(self):
        boards = Path(T.HOME) / 'momboards-fq'
        boards.mkdir(exist_ok=True)
        for f in boards.glob('*'):
            f.unlink()
        a = SimpleNamespace(tracks=self.tracks, boards=str(boards), take=100, delay=0, go=True, index=False)
        F.mom_enqueue(self.db, ('surf_fq', 0, 0), 100, self.tracks)
        F.mom_enqueue(self.db, ('surf_fq', 0, 2), 101, self.tracks)
        self.db.execute("UPDATE momtopup SET target=200 WHERE leg=2")
        self.db.commit()
        cmds = []

        def call(cmd):
            cmds.append(cmd)
            key = cmd[cmd.index('--board') + 1]
            rows = [{"rank": i + 1} for i in range(120 if key == '9_g1_t01' else 100)]
            Path(boards, key + '.json').write_text(json.dumps(dict(rows=rows, total=len(rows) if key == '9_g1_t01' else 900)))
            return 0
        with patch.object(W.subprocess, 'call', side_effect=call), patch.object(W, 'has_extras', return_value=True), \
             patch.object(W.momfetch, 'load_board', side_effect=lambda p: json.loads(Path(p).read_text())
                          if Path(p).exists() else None):
            self.assertEqual(W.topup_step(a), (True, 0))
        self.assertEqual([c[c.index('--board') + 1] for c in cmds], ['9_g1_t01', '9_g1_t12'])
        self.assertEqual([c[c.index('--depth') + 1] for c in cmds], ['100', '200'])
        self.assertEqual([c[c.index('--max') + 1] for c in cmds], [str(W.TOPUP_PAGES)] * 2)
        self.assertNotIn('--refresh', cmds[0])                       # never fetched: page 1 anyway
        st = dict(((r[0], r[1]) for r in self.db.execute("SELECT leg, state FROM momtopup")))
        self.assertEqual(st, {0: 'exhausted', 2: 'partial'})
        # A board fetched over TOPUP_FRESH ago is refreshed; a refusal rests everything.
        os.utime(Path(boards, '9_g1_t12.json'), (time.time() - W.TOPUP_FRESH - 5,) * 2)
        cmds.clear()
        with patch.object(W.subprocess, 'call', side_effect=lambda cmd: cmds.append(cmd) or 3), \
             patch.object(W, 'has_extras', return_value=True):
            self.assertEqual(W.topup_step(a), (True, 3))
        self.assertIn('--refresh', cmds[0])
        self.assertTrue(W.resting(a.boards))
        self.assertEqual(self.db.execute("SELECT state FROM momtopup WHERE leg=2").fetchone()[0], 'partial')
        with patch.object(W.subprocess, 'call', side_effect=AssertionError('rested')):
            self.assertEqual(W.topup_step(a), (False, 0))

    def test_momwatch_tick_runs_the_fetch_stage(self):
        boards = Path(T.HOME) / 'momboards-fq-main'
        boards.mkdir(exist_ok=True)
        for f in boards.glob('*'):
            f.unlink()
        self.db.execute("DELETE FROM lobbies")
        self.db.commit()
        F.mom_enqueue(self.db, ('surf_fq', 3, 0), 100, self.tracks)
        cmds = []
        argv = ['momwatch.py', '--tracks', self.tracks, '--boards', str(boards), '--go', '--delay', '0']
        with patch.object(W.sys, 'argv', argv), patch.object(W, 'has_extras', return_value=True), \
             patch.object(W.subprocess, 'call', side_effect=lambda cmd: cmds.append(cmd) or 0):
            self.assertEqual(W.main(), 0)
        self.assertEqual([c[c.index('--board') + 1] for c in cmds if '--board' in c], ['9_g1_t23'])


def KT_recent(db):
    import ksftopup
    return ksftopup.recent(db, int(time.time()))


if __name__ == '__main__':
    unittest.main(verbosity=1)
