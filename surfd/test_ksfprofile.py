#!/usr/bin/env python3
"""KSF profile-demand controls: real migrated DB, fake paced source, no network."""
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HOME = tempfile.mkdtemp(prefix='ksfprofile-')
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, 'test.db'))
import surfd as S
import ksfimport as K
import ksfprofile as P

PLAYER = '76561198000000042'


class Source:
    def __init__(self, n=8):
        self.n, self.calls = n, []
    def __call__(self, url):
        self.calls.append(url)
        m = re.search(r'/bestrecords/(\d+)\?game=css&mode=(\d)$', url)
        start, mode = map(int, m.groups())
        n = self.n if mode == 0 else 0
        rows = [{'mapName': 'surf_profile%d' % i, 'record_id': None, 'time': 10.01+i,
                 'date': 1790000000+i, 'stage_id': None, 'zone_id': None}
                for i in range(start-1, min(start-1+5, n))]
        return json.dumps({'records': rows, 'pagination': {'offset': start-1, 'limit': 5}, 'total': 1})


class Profiles(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp(dir=HOME)
        self.db = S.connect()
        self.db.execute('DELETE FROM ksf_unbound'); self.db.execute('DELETE FROM ksfprofiles'); self.db.execute('DELETE FROM runs'); self.db.commit()
        self.src = Source(); self.have = {'surf_profile%d' % i for i in range(1100)}
        self.network = patch.object(K, 'fetch', self.src); self.network.start()
    def tearDown(self):
        self.network.stop(); self.db.close(); shutil.rmtree(self.cache)
    def step(self, budget=1, now=1001):
        p = K.Pacer(0, budget)
        P.step(K, self.cache, p, self.have, now, budget)
        return p.made
    def queue(self, player=PLAYER, now=1000):
        return P.enqueue(self.db, player, now)
    def count(self):
        return self.db.execute("SELECT count(*) FROM runs WHERE tier='ksf'").fetchone()[0]
    def test_solo_profile_uses_full_bounded_allowance(self):
        self.src.n = 25; self.queue()
        self.assertEqual(self.step(budget=3), 3)
        self.assertEqual(self.count(), 15)
        self.assertEqual(P.status(self.db, PLAYER)['next'], 16)

    def test_locked_queue_does_not_block_browsing(self):
        import time
        other = S.connect(); other.execute('BEGIN IMMEDIATE')
        try:
            t = time.monotonic()
            self.assertEqual(self.queue()['state'], 'busy')
            self.assertLess(time.monotonic() - t, .3)
        finally:
            other.rollback(); other.close()
        self.assertEqual(self.db.execute('PRAGMA busy_timeout').fetchone()[0], 5000)
        self.assertEqual(self.queue()['state'], 'queued')

    def test_correct_start_and_resume_not_position25(self):
        self.assertEqual(self.queue()['next'], 1)
        self.assertEqual(self.step(), 1); self.assertEqual(self.count(), 5)
        self.assertEqual(P.status(self.db, PLAYER)['next'], 6)
        self.step(); self.assertEqual(self.count(), 8)
        self.assertIn('/bestrecords/6?', self.src.calls[1])
        self.assertEqual(P.status(self.db, PLAYER)['mode'], 1)
        for _ in range(3): self.step()
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'complete')
    def test_walk_beyond1000(self):
        self.src.n = 1005; self.queue()
        for i in range(210): self.step(now=1001+i)
        self.assertEqual(self.count(), 1005)
        self.assertTrue(any('/bestrecords/1001?' in x for x in self.src.calls))
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'complete')
    def test_real_source_null_ids_keep_completions_without_demo_authority(self):
        self.queue(); self.step()
        self.assertEqual(self.count(), 5)
        self.assertEqual(self.db.execute("SELECT count(*) FROM runs WHERE runid='' AND replay_id=0").fetchone()[0], 5)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ksf_unbound').fetchone()[0], 5)

    def test_refusal_keeps_cursor(self):
        self.queue()
        with patch.object(K, 'fetch', side_effect=K.Refused('HTTP 429', 429)):
            with self.assertRaises(K.Refused): self.step()
        self.assertEqual(P.status(self.db, PLAYER)['next'], 1)
        self.assertEqual(self.count(), 0)
    def test_wrong_offset_never_exhausts_or_imports(self):
        self.queue(); self.step()
        with patch.object(K, 'fetch', return_value=json.dumps({'records': [], 'pagination': {'offset': 0, 'limit': 5}})):
            with self.assertRaises(K.Refused): self.step()
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'partial')
        self.assertEqual(P.status(self.db, PLAYER)['next'], 6)
    def test_crash_after_durable_import_replays_cache_without_network(self):
        self.queue(); real = K.write_rows
        def crash(rows):
            real(rows); raise sqlite3.OperationalError('simulated crash before cursor')
        with patch.object(K, 'write_rows', side_effect=crash):
            with self.assertRaises(sqlite3.OperationalError): self.step()
        self.assertEqual(self.count(), 5); self.assertEqual(P.status(self.db, PLAYER)['next'], 1)
        with patch.object(K, 'fetch', side_effect=AssertionError('must use durable page')):
            self.step(budget=0) # no work without allowance
            self.step()
        self.assertEqual(self.count(), 5); self.assertEqual(P.status(self.db, PLAYER)['next'], 6)
    def test_view_coalescing_and_refresh_expiry(self):
        self.queue(); self.queue(now=1100); self.assertEqual(P.pending(self.db)[0][3], 1000)
        for _ in range(5): self.step()
        self.assertEqual(self.queue(now=2000)['state'], 'complete')
        self.assertEqual(self.queue(now=1001+P.TTL)['state'], 'queued')
        self.assertEqual(P.pending(self.db)[0][3], 1001+P.TTL)
        self.step(now=1002+P.TTL)
        self.assertEqual(len(self.src.calls), 6) # old cached page must not satisfy refresh
    def test_active_cap_and_invalid_identity(self):
        self.assertEqual(self.queue('private-guid')['state'], 'ineligible')
        self.assertEqual(self.queue('11111111111111111')['state'], 'ineligible')
        for i in range(P.MAX_ACTIVE): self.queue(str(int(PLAYER)+i))
        self.assertEqual(self.queue(str(int(PLAYER)+99))['state'], 'busy')
        self.assertEqual(len(P.pending(self.db)), 3)
    def test_unavailable_maps_counted_not_claimed_playable(self):
        self.have = set(); self.queue(); self.step()
        self.assertEqual(self.count(), 0)
        self.assertEqual(P.status(self.db, PLAYER)['unavailable'], 5)
    def test_styles_and_limited_are_not_complete(self):
        self.src.n = 5; self.queue()
        with patch.object(P, 'MAX_POSITION', 6): self.step()
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'limited')
        self.db.execute('DELETE FROM ksfprofiles'); self.db.commit(); self.queue()
        self.db.execute('UPDATE ksfprofiles SET mode=2'); self.db.commit()
        with patch.object(K, 'fetch', return_value=Source(1)('https://fake/bestrecords/1?game=css&mode=0')):
            self.step()
        self.assertEqual(self.db.execute("SELECT count(*) FROM runs WHERE style='hsw'").fetchone()[0], 1)
    def test_profile_http_only_queues_resolved_known_identity(self):
        self.db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) VALUES ('surf_profile0',0,0,'ksf','clean',?,'fixture',100,100,1000,0,'ksf','x',1000,0)", (PLAYER,)); self.db.commit()
        S.people_reset()
        with patch.object(K, 'fetch', side_effect=AssertionError('HTTP must not fetch KSF')):
            with S.app.test_client() as c:
                r = c.get('/api/board?player=' + S.web_handle(PLAYER))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json['ksf_sync']['state'], 'queued')
                self.assertEqual(c.get('/api/board?player=aaaaaaaaaaaa').status_code, 404)
        self.assertEqual(len(P.pending(self.db)), 1)

    # P747: KSF answers 500 for a player it does not know; that parked the host.
    def test_unknown_player_retires_walk_one_per_tick(self):
        other = str(int(PLAYER) + 1)
        self.queue(); self.queue(other, now=1001)
        with patch.object(K, 'fetch', side_effect=K.NoSuchPlayer('HTTP 500')) as f:
            self.assertEqual(self.step(budget=3), 1)
            self.assertEqual(f.call_count, 1)
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'unknown')
        self.assertEqual(P.status(self.db, other)['state'], 'queued')
        self.assertEqual(self.queue(now=2000)['state'], 'unknown')
        self.assertEqual(self.queue(now=1002 + P.TTL)['state'], 'queued')
    def test_partial_walk_500_is_limited_not_complete(self):
        self.src.n = 25; self.queue(); self.step()
        with patch.object(K, 'fetch', side_effect=K.NoSuchPlayer('HTTP 500')):
            self.step()
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'limited')
        self.assertEqual(self.count(), 5)
    def test_watch_tick_survives_unknown_profile_and_keeps_crawling(self):
        self.queue()
        calls = []
        def fetch(url):
            calls.append(url)
            if '/bestrecords/' in url:
                raise K.NoSuchPlayer('HTTP 500')
            if '/api/maps/new' in url:
                return '[]'
            raise AssertionError(url)
        with patch.object(K, 'fetch', side_effect=fetch):
            K.watch_mode(SimpleNamespace(delay=0, max=10, go=True), self.have, self.cache)
        self.assertEqual(len(calls), 2)
        self.assertIn('/api/maps/new', calls[1])
        self.assertFalse(os.path.exists(os.path.join(self.cache, '.refused')))
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'unknown')
    def test_swallowed_500_does_not_lift_an_expired_park(self):
        self.queue()
        now = int(time.time())
        K._save(os.path.join(self.cache, 'catalog.json'),
                {'names': [], 'offset': 0, 'done': True, 'at': now, 'full_at': now})
        park = {'at': 1, 'until': 2, 'n': 3, 'why': 'HTTP 500'}
        K._save(os.path.join(self.cache, '.refused'), park)
        with patch.object(K, 'fetch', side_effect=K.NoSuchPlayer('HTTP 500')) as f:
            K.watch_mode(SimpleNamespace(delay=0, max=10, go=True), self.have, self.cache)
            self.assertEqual(f.call_count, 1)
        self.assertEqual(K._load(os.path.join(self.cache, '.refused')), park)
    def test_migrate18_to20_adds_scoped_marker_without_rewriting_runs(self):
        self.queue(); self.step()
        row = list(self.db.execute('SELECT * FROM runs ORDER BY map LIMIT 1').fetchone())
        row[0], row[3], row[12] = 'surf_native', 'community', ''
        self.db.execute('INSERT INTO runs VALUES ('+','.join('?' for _ in row)+')', row)
        row[0], row[3], row[12] = 'surf_identified', 'ksf', 'identified-record'
        self.db.execute('INSERT INTO runs VALUES ('+','.join('?' for _ in row)+')', row)
        self.db.commit()
        before = [tuple(r) for r in self.db.execute('SELECT * FROM runs ORDER BY map')]
        self.db.executescript('DROP TABLE ksf_unbound; PRAGMA user_version=18;')
        S.migrate()
        self.assertEqual(self.db.execute('PRAGMA user_version').fetchone()[0], 20)
        columns = self.db.execute('PRAGMA table_info(ksf_unbound)').fetchall()
        self.assertEqual([(r[1], r[2], r[3], r[5]) for r in columns],
                         [('map','TEXT',1,1), ('track','INTEGER',1,2), ('leg','INTEGER',1,3),
                          ('style','TEXT',1,4), ('player','TEXT',1,5), ('seconds','REAL',0,0),
                          ('millis','INTEGER',1,0), ('submitted','INTEGER',1,0)])
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM runs ORDER BY map')], before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ksf_unbound WHERE seconds IS NULL').fetchone()[0], 5)
        S.migrate()
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM runs ORDER BY map')], before)

    def test_pre18_legacy_rows_remain_marker_free_on_upgrade(self):
        self.queue(); self.step()
        before = [tuple(r) for r in self.db.execute('SELECT * FROM runs ORDER BY map')]
        self.db.executescript('DROP TABLE ksf_unbound; DROP TABLE ksfprofiles; PRAGMA user_version=17;')
        S.migrate()
        self.assertEqual(self.db.execute('PRAGMA user_version').fetchone()[0], 20)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ksf_unbound').fetchone()[0], 0)
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM runs ORDER BY map')], before)

    def test_migrate20_idempotent_and_no_existing_run_changes(self):
        self.assertEqual(self.db.execute('PRAGMA user_version').fetchone()[0], 20)
        S.migrate(); self.assertEqual(self.count(), 0)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        logging.shutdown(); shutil.rmtree(HOME)
