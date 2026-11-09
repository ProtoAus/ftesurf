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
        self.db.execute("DELETE FROM runs WHERE map='surf_fq' OR player IN (?, '76561198000000078')", (PLAYER,))
        self.db.commit()
        self.tracks = os.path.join(T.HOME, "momtracks-fq.tsv")
        Path(self.tracks).write_text(TSV)
        self.old_tracks, S.MOMTRACKS_PATH = S.MOMTRACKS_PATH, self.tracks
        maps = Path(S.DATA_DIR) / 'ksf' / 'maps'
        maps.mkdir(parents=True, exist_ok=True)
        self.meta = maps / 'surf_fq.json'
        self.meta.write_text(json.dumps([dict(name='surf_fq', isLinear=False, cp_count=4, b_count=3)]))
        S._rate.clear()
        self.installed = patch.object(S, 'map_index', return_value=({'surf_fq': 'surf_fq'}, set()))
        self.installed.start()
        for t in ("accounts",):
            self.db.execute("DELETE FROM %s WHERE steamid LIKE '7656119800000007%%'" % t)
        self.db.commit()

    def tearDown(self):
        self.installed.stop()
        S.MOMTRACKS_PATH = self.old_tracks
        self.meta.unlink()
        self.db.close()

    def account(self, sid):
        self.db.execute("INSERT OR IGNORE INTO accounts(steamid, created_at) VALUES (?, 1)", (sid,))
        self.db.commit()

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
        # An exhausted board's press refreshes it after REFRESH_AFTER, without adding depth.
        body, code = F.mom_enqueue(self.db, key, 103 + F.REFRESH_AFTER, self.tracks)
        self.assertEqual((code, body['state'], body['target']), (202, 'queued', 100))
        self.assertEqual(F.mom_finish(self.db, key, 100, 100, 500, False, 104), 'done')
        self.assertEqual(F.mom_finish(self.db, key, 100, 100, 500, False, 104), 'done')   # CAS: no-op
        body, _ = F.mom_enqueue(self.db, key, 105, self.tracks)                # done: 100 more
        self.assertEqual(body['target'], 200)
        self.assertEqual(F.mom_finish(self.db, key, 200, 120, 500, False, 106, progressed=False), 'done')
        body, _ = F.mom_enqueue(self.db, key, 107, self.tracks)
        self.assertEqual(F.mom_finish(self.db, key, body['target'], 0, 0, True, 108), 'unsupported')
        self.assertEqual(F.mom_enqueue(self.db, key, 109, self.tracks)[0]['state'], 'unsupported')
        target = body['target']
        body, code = F.mom_enqueue(self.db, key, 108 + F.RETRY_AFTER, self.tracks)
        self.assertEqual((code, body['target']), (202, target))               # retried, not deepened
        with patch.object(F, 'MAX_ACTIVE', 1):
            F.mom_enqueue(self.db, ('surf_fq', 0, 2), 200, self.tracks)
            self.assertEqual(F.mom_enqueue(self.db, ('surf_fq', 3, 0), 200, self.tracks), (None, 429))

    def test_http_queues_both_sources_on_a_map_with_no_rows(self):
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs WHERE map='surf_fq'").fetchone()[0], 0)
        with patch.object(K, 'fetch', side_effect=AssertionError('HTTP must not fetch')),              patch.object(S, 'FETCH_RATE', 100), \
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
            # KSF lists it, this server does not host it: nothing is queued (review round 1).
            other = self.meta.with_name('surf_notours.json')
            other.write_text(json.dumps([dict(name='surf_notours', isLinear=True, cp_count=0, b_count=0)]))
            try:
                self.assertEqual(c.post('/api/board?fetch=1&map=surf_notours').status_code, 404)
            finally:
                other.unlink()
            self.assertEqual(c.post('/api/board?fetch=1&map=surf_fq&style=segmented').status_code, 400)
            self.assertEqual(c.post('/api/board?ksfmore=1&map=surf_fq').status_code, 202)   # old clients
            # The site's button state. It shows maps with a row or an installed zoned build only.
            self.db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,"
                            "flags,node,runid,submitted,replay_id) VALUES ('surf_fq',0,0,'ranked','clean',"
                            "'76561198000000078','fx',100,100,1000,0,'n','fqr',1000,0)")
            self.db.commit()
            g = c.get('/board/api/map?map=surf_fq&track=3').json
            self.assertEqual((g['mom_topup']['state'], g['mom_topup']['eligible']), ('queued', True))
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

    def test_fetched_profile_takes_its_turn_and_the_cap_holds(self):
        now = int(time.time())
        view, fetched, acct, third = (str(int(PLAYER) + k) for k in (1, 0, 2, 3))
        P.enqueue(self.db, view, now - 10)
        P.enqueue(self.db, fetched, now)
        self.assertTrue(F.fetch_profile(self.db, fetched, now))
        self.assertEqual(P.pending(self.db)[0][0], view)                 # by turn, not ahead of views
        self.assertTrue(P.is_account(K, fetched))                        # but it walks fully
        self.assertFalse(F.fetch_profile(self.db, view, now))            # a view's walk stays a view's
        self.account(acct)
        P.enqueue(self.db, acct, now)
        with patch.object(F, 'MAX_FETCHED', 1):
            self.assertTrue(F.fetch_profile(self.db, acct, now))         # accounts are not counted
            P.enqueue(self.db, third, now)
            self.assertFalse(F.fetch_profile(self.db, third, now))       # the cap
            self.assertTrue(F.fetch_profile(self.db, fetched, now + 5))  # its own live walk, not new
        # The mark ends with the walk: a later view's walk of the same player has view limits.
        self.db.execute("UPDATE ksfprofiles SET state='complete', updated=0 WHERE player=?", (fetched,))
        self.db.commit()
        P.enqueue(self.db, fetched, now + 10)
        self.assertFalse(P.is_account(K, fetched))
        # The KSF slot is the view pool's: fetching never takes an account's slot.
        with patch.object(P, 'MAX_VIEWED', 3):
            self.assertEqual(P.enqueue(self.db, str(int(PLAYER) + 4), now)['state'], 'busy')
        self.db.execute("DROP TABLE profilefetch")                       # an older generation's DB
        self.db.commit()
        self.assertEqual(len(P.pending(self.db)), 3)
        self.assertFalse(F.fetched(self.db, fetched, now))
        F.ensure(self.db)

    def test_momentum_profile_pools(self):
        now = int(time.time())
        acct = str(int(PLAYER) + 2)
        self.account(acct)
        with patch.object(MP, 'MAX_VIEWED', 1):
            self.assertEqual(MP.enqueue(self.db, PLAYER, now, force=True)['state'], 'queued')
            self.assertEqual(MP.enqueue(self.db, str(int(PLAYER) + 1), now, force=True)['state'], 'busy')
            self.assertEqual(MP.enqueue(self.db, acct, now)['state'], 'queued')   # its own pool
        asked = []
        def get(url):
            asked.append(url)
            raise RuntimeError('stop')       # one request is all this needs to see the order
        try:
            MP.step(self.db, {}, 1, get, delay=0, now=now)
        except Exception:
            pass
        self.assertIn('steamID=' + acct, asked[0])                       # accounts first
        # A non-account walk unasked for STARVE ranks with the accounts (it cannot starve).
        self.db.execute("UPDATE momprofiles SET updated=? WHERE player=?", (now - MP.STARVE - 5, PLAYER))
        self.db.execute("UPDATE momprofiles SET updated=? WHERE player=?", (now, acct))
        self.db.commit()
        asked.clear()
        try:
            MP.step(self.db, {}, 1, get, delay=0, now=now)
        except Exception:
            pass
        self.assertIn('steamID=' + PLAYER, asked[0])

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
        self.assertEqual([c[c.index('--max') + 1] for c in cmds],
                         [str(W.TOPUP_PAGES), str(W.TOPUP_MAX - W.TOPUP_PAGES)])     # the tick's budget
        self.assertNotIn('--refresh', cmds[0])                       # never fetched: page 1 anyway
        st = dict(((r[0], r[1]) for r in self.db.execute("SELECT leg, state FROM momtopup")))
        self.assertEqual(st, {0: 'exhausted', 2: 'partial'})
        # A partial job does not ask page 1 again (once per press); a refusal rests everything
        # and sends the board to the back of the queue.
        os.utime(Path(boards, '9_g1_t12.json'), (time.time() - W.TOPUP_FRESH - 5,) * 2)
        cmds.clear()
        F.mom_enqueue(self.db, ('surf_fq', 3, 0), int(time.time()) - 5, self.tracks)   # queued earlier
        self.db.execute("UPDATE momtopup SET updated=0 WHERE leg=2")
        self.db.commit()
        with patch.object(W.subprocess, 'call', side_effect=lambda cmd: cmds.append(cmd) or 3), \
             patch.object(W, 'has_extras', return_value=True):
            self.assertEqual(W.topup_step(a), (True, 3))
        self.assertNotIn('--refresh', cmds[0])
        self.assertTrue(W.resting(a.boards))
        self.assertEqual(self.db.execute("SELECT state FROM momtopup WHERE leg=2").fetchone()[0], 'partial')
        self.assertEqual(F.mom_pending(self.db)[0][:3], ('surf_fq', 3, 0))      # the refused one went back
        with patch.object(W.subprocess, 'call', side_effect=AssertionError('rested')):
            self.assertEqual(W.topup_step(a), (False, 0))

    def test_momwatch_second_job_given_one_request_is_not_done(self):
        boards = Path(T.HOME) / 'momboards-fq-slot2'
        boards.mkdir(exist_ok=True)
        for f in boards.glob('*'):
            f.unlink()
        a = SimpleNamespace(tracks=self.tracks, boards=str(boards), take=100, delay=0, go=True, index=False)
        for k in ('9_g1_t01', '9_g1_t12'):
            Path(boards, k + '.json').write_text(json.dumps(dict(rows=[{"rank": r} for r in range(1, 101)],
                                                                 total=900)))
            os.utime(Path(boards, k + '.json'), (time.time() - W.TOPUP_FRESH - 5,) * 2)
        F.mom_enqueue(self.db, ('surf_fq', 0, 0), 100, self.tracks)
        F.mom_enqueue(self.db, ('surf_fq', 0, 2), 101, self.tracks)
        self.db.execute("UPDATE momtopup SET target=200")
        self.db.commit()
        with patch.object(W.subprocess, 'call', return_value=0), patch.object(W, 'has_extras', return_value=True):
            W.topup_step(a)
        self.assertEqual(self.db.execute("SELECT state FROM momtopup WHERE leg=0").fetchone()[0], 'done')
        # Job 2 had one request, page 1 only: it gained nothing deeper and was never asked to.
        self.assertEqual(self.db.execute("SELECT state FROM momtopup WHERE leg=2").fetchone()[0], 'partial')

    def test_momwatch_retires_a_board_that_keeps_refusing(self):
        boards = Path(T.HOME) / 'momboards-fq-strike'
        boards.mkdir(exist_ok=True)
        a = SimpleNamespace(tracks=self.tracks, boards=str(boards), take=100, delay=0, go=True, index=False)
        F.mom_enqueue(self.db, ('surf_fq', 3, 0), 100, self.tracks)
        for _ in range(F.STRIKES):
            for f in boards.glob('*'):
                f.unlink()                   # the rest file too: each try is a new tick
            with patch.object(W.subprocess, 'call', return_value=3), patch.object(W, 'has_extras', return_value=True):
                W.topup_step(a)
        self.assertEqual(self.db.execute("SELECT state, strikes FROM momtopup").fetchone()[:], ('unsupported', 3))

    def test_ksf_half_of_a_port_uses_ksfs_name(self):
        # surf_fq_ksf is a build of surf_fq; KSF lists only the suffixed name.
        port = self.meta.with_name('surf_fq_ksf.json')
        port.write_text(json.dumps([dict(name='surf_fq_ksf', isLinear=True, cp_count=0, b_count=0)]))
        try:
            with patch.object(S, 'map_index', return_value=({'surf_fq': 1, 'surf_fq_ksf': 1}, set())), \
                 patch.object(S, 'variant_base', side_effect=lambda m, now=None: 'surf_fq' if m == 'surf_fq_ksf' else None), \
                 S.app.test_client() as c:
                r = c.post('/api/board?fetch=1&map=surf_fq_ksf')
                self.assertEqual((r.status_code, r.json['ksf']['state'], r.json['momentum']['state']),
                                 (202, 'queued', 'queued'))
            self.assertEqual(self.db.execute("SELECT map FROM ksftopup").fetchall()[0][0], 'surf_fq_ksf')
            self.assertEqual(self.db.execute("SELECT map FROM momtopup").fetchall()[0][0], 'surf_fq')
        finally:
            port.unlink()

    def test_momwatch_finishes_holed_and_stalled_boards(self):
        boards = Path(T.HOME) / 'momboards-fq-holes'
        boards.mkdir(exist_ok=True)
        for f in boards.glob('*'):
            f.unlink()
        a = SimpleNamespace(tracks=self.tracks, boards=str(boards), take=100, delay=0, go=True, index=False)
        # 148 rows whose ranks reach 150 of 150: momfetch plans nothing deeper.
        holed = [{"rank": r} for r in range(1, 151) if r not in (40, 41)]
        Path(boards, '9_g1_t01.json').write_text(json.dumps(dict(rows=holed, total=150)))
        # 100 of 900, and the fetch gains nothing.
        Path(boards, '9_g1_t12.json').write_text(json.dumps(dict(rows=[{"rank": r} for r in range(1, 101)],
                                                                 total=900)))
        F.mom_enqueue(self.db, ('surf_fq', 0, 0), 100, self.tracks)
        F.mom_enqueue(self.db, ('surf_fq', 0, 2), 101, self.tracks)
        self.db.execute("UPDATE momtopup SET target=248 WHERE leg=0")
        self.db.execute("UPDATE momtopup SET target=200 WHERE leg=2")
        self.db.commit()
        with patch.object(W.subprocess, 'call', return_value=0), patch.object(W, 'has_extras', return_value=True):
            W.topup_step(a)
        st = dict(((r[0], r[1]) for r in self.db.execute("SELECT leg, state FROM momtopup")))
        self.assertEqual(st, {0: 'exhausted', 2: 'done'})

    def ksf_step(self, doc_edit, state='queued'):
        """One KSF topup_step on surf_fq's main board; -> (pages asked with their top flag, job state)."""
        cache = T.fresh_cache()
        doc = K.board_load(cache, 'surf_fq', 0, 0)
        doc_edit(doc)
        K._save(K.board_path(cache, 'surf_fq', 0, 0), doc)
        self.assertEqual(KT_enqueue(self.db, ('surf_fq', 0, 0, 'clean'))[1], 202)
        self.db.execute("UPDATE ksftopup SET state=?", (state,))
        self.db.commit()
        asked = []

        def page(cache, mp, zone, pacer, mode, **kw):
            asked.append(kw.get('top', False))
            d = K.board_load(cache, mp, zone, mode)
            d['done'] = True
            return d, []
        with patch.object(K, 'map_info', return_value={}), patch.object(K, 'zones_of', return_value={0}),              patch.object(K, 'board_page', side_effect=page),              patch.object(K, 'fetch', side_effect=AssertionError('network')):
            K.topup_step(cache, {}, K.Pacer(0, 5), [], [], [], {'surf_fq'})
        return asked, self.db.execute("SELECT state FROM ksftopup").fetchone()[0]

    def test_ksf_fetch_respects_set_aside_and_asks_page_one_once(self):
        now = int(time.time())
        stale = lambda d: d.update(top=now - K.FETCH_FRESH - 60, done=True)
        self.assertEqual(self.ksf_step(stale)[0], [True])                       # a press refreshes
        self.db.execute("DELETE FROM ksftopup"); self.db.commit()
        self.assertEqual(self.ksf_step(stale, 'partial')[0], [])                # a later visit does not
        self.db.execute("DELETE FROM ksftopup"); self.db.commit()
        asked, st = self.ksf_step(lambda d: d.update(top=0, skip=True, skip_at=now))
        self.assertEqual((asked, st), ([], 'unsupported'))                       # strike()'s set-aside holds
        self.db.execute("DELETE FROM ksftopup"); self.db.commit()
        cache = T.fresh_cache()                                                  # not installed here
        KT_enqueue(self.db, ('surf_fq', 0, 0, 'clean'))
        with patch.object(K, 'map_info', side_effect=AssertionError('asked')),              patch.object(K, 'fetch', side_effect=AssertionError('network')):
            K.topup_step(cache, {}, K.Pacer(0, 5), [], [], [], {'surf_other'})
        self.assertEqual(self.db.execute("SELECT state FROM ksftopup").fetchone()[0], 'unsupported')

    def test_momwatch_tick_runs_the_fetch_stage(self):
        boards = Path(T.HOME) / 'momboards-fq-main'
        boards.mkdir(exist_ok=True)
        for f in boards.glob('*'):
            f.unlink()
        self.db.execute("DELETE FROM lobbies")
        self.db.commit()
        F.mom_enqueue(self.db, ('surf_fq', 3, 0), 100, self.tracks)
        # A lobby on the map: a refused fetch must not cost the live maps their turn.
        self.db.execute("INSERT INTO lobbies(node,map,players,maxplayers,addr,name,last_seen)"
                        " VALUES ('fqnode','surf_fq',1,8,'a','n',?)", (int(time.time()),))
        self.db.commit()
        cmds = []
        argv = ['momwatch.py', '--tracks', self.tracks, '--boards', str(boards), '--go', '--delay', '0']
        try:
            with patch.object(W.sys, 'argv', argv), patch.object(W, 'has_extras', return_value=True), \
                 patch.object(W.subprocess, 'call', side_effect=lambda cmd: cmds.append(cmd) or (3 if '--board' in cmd else 0)):
                W.main()
        finally:
            self.db.execute("DELETE FROM lobbies")
            self.db.commit()
        self.assertEqual([c[c.index('--board') + 1] for c in cmds if '--board' in c], ['9_g1_t23'])
        self.assertTrue(any('--map' in c and 'surf_fq' in c for c in cmds))


def KT_enqueue(db, key):
    import ksftopup
    return ksftopup.enqueue(db, key, int(time.time()), os.path.join(S.DATA_DIR, 'ksf', 'maps'))


def KT_recent(db):
    import ksftopup
    return ksftopup.recent(db, int(time.time()))


if __name__ == '__main__':
    unittest.main(verbosity=1)
