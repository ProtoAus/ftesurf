#!/usr/bin/env python3
"""Explicit KSF demand falsifiers: no network, real queue/import/HTTP paths."""
import os
import struct
import time
import unittest
import sqlite3
import tempfile
from pathlib import Path

import test_ksfimport as T
import ksftopup as Q
import zonefit
S, K = T.S, T.K


class Topup(unittest.TestCase):
    def setUp(self):
        self.db = S.connect()
        self.db.execute("DELETE FROM ksftopup")
        self.db.execute("DELETE FROM runs WHERE map='surf_topup'")
        self.db.commit()
        self.cache = T.fresh_cache()
        self.fake = T.FakeKSF({'surf_topup': dict(T.LINEAR)},  {('surf_topup', 0): 247,
                                                             ('surf_topup', 0, 1): 13})
        K.fetch = self.fake
        self.info, _, _ = K.sweep_maps(['surf_topup'], self.cache, 120, K.Pacer(0, 20))
        self.file()
        self.key = ('surf_topup', 0, 0, 'clean')
        S._rate.clear()
        self.client = S.app.test_client()

    def tearDown(self):
        self.db.close()
        K.fetch = T.REAL_FETCH

    def file(self):
        rows, _, _ = K.map_rows(self.cache, self.info, sorted(K.KSF_MODES))
        K.write_rows(rows)

    def step(self, pages=5):
        done, fetched = [], []
        K.topup_step(self.cache, {}, K.Pacer(0, pages), done, fetched)
        return done

    def test_positive_topup_and_restart(self):
        self.assertEqual(Q.count(self.db, self.key), 120)
        before = list(self.fake.asked)
        self.assertEqual(self.step(), [])  # control: no demand, no fetch
        self.assertEqual(self.fake.asked, before)
        body, code = Q.enqueue(self.db, self.key, 100)
        self.assertEqual((code, body['target']), (202, 220))
        again, _ = Q.enqueue(self.db, self.key, 101)
        self.assertEqual(again['target'], 220)  # coalesced, not +100 per click
        self.fake.asked.clear()
        done = self.step(2)
        self.assertEqual(len(T.pages(self.fake)), 2)
        self.assertEqual(Q.count(self.db, self.key), 120)  # fetched != filed
        self.assertEqual(Q.status(self.db, self.key)['state'], 'queued')
        # Interrupted before write/ack: a new step continues cached cursor.
        done = self.step(5)
        self.file()
        K.finish_topups(done)
        self.assertEqual(Q.count(self.db, self.key), 220)
        self.assertEqual(Q.status(self.db, self.key)['state'], 'done')
        Q.enqueue(self.db, self.key, 200)
        done = self.step(5)
        self.file(); K.finish_topups(done)
        self.assertEqual((Q.count(self.db, self.key), Q.status(self.db, self.key)['state']),
                         (247, 'exhausted'))
        self.assertEqual(Q.enqueue(self.db, self.key, int(time.time()))[0]['state'], 'exhausted')

    def test_whole_watch_worker_files_before_acknowledgement(self):
        maps = tempfile.mkdtemp(prefix='topup-maps-', dir=T.HOME)
        Path(maps, 'surf_topup.bsp').touch()
        Q.enqueue(self.db, self.key, 100)
        write = K.write_rows
        def fail_write(rows):
            raise sqlite3.OperationalError('owned forced filing failure')
        K.write_rows = fail_write
        try:
            self.assertEqual(T.tick(self.cache, maps, 12), 1)
        finally:
            K.write_rows = write
        self.assertEqual(Q.count(self.db, self.key), 120)
        self.assertEqual(Q.status(self.db, self.key)['state'], 'queued')
        self.assertTrue(K.owed_boards(self.cache))
        self.assertEqual(T.tick(self.cache, maps, 12), 0)
        # The ordinary crawl shares the tick and finishes this small board.
        self.assertEqual(Q.count(self.db, self.key), 247)
        self.assertEqual(Q.status(self.db, self.key)['state'], 'done')

    def test_http_and_style_isolation(self):
        url = '/api/board?ksfmore=1&map=surf_topup&style=sw'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(len(Q.pending(self.db)), 0)  # GET/prefetch is harmless
        r = self.client.post(url, json={})
        self.assertEqual((r.status_code, r.json['target']), (202, 100))
        self.assertEqual(r.headers['Cache-Control'], 'no-store')
        done = self.step()
        self.file(); K.finish_topups(done)
        self.assertEqual(Q.count(self.db, ('surf_topup', 0, 0, 'sw')), 13)
        self.assertEqual(Q.count(self.db, self.key), 120)
        for style, n in [('clean', 120), ('sw', 13), ('hsw', 0), ('bw', 0)]:
            r = self.client.get('/api/board?map=surf_topup&tier=ksf&style=' + style + '&limit=200')
            self.assertEqual(len(r.json['rows']), n)
        self.assertEqual(self.client.post('/board/api/map?ksfmore=1&map=surf_topup&style=bw').status_code, 202)
        self.assertEqual(self.client.post('/api/board?ksfmore=1&map=surf_unknown').status_code, 404)
        self.assertEqual(self.client.post('/api/board?ksfmore=1&map=surf_topup&track=2').status_code, 404)
        self.assertEqual(self.client.post('/api/board?ksfmore=1&map=surf_topup&style=segmented').status_code, 400)
        self.assertEqual(self.client.post('/api/board?map=surf_topup').status_code, 400)

    def test_bonus_four_and_linked_build(self):
        self.fake.maps['surf_topup']['b_count'] = 4
        self.fake.boards[('surf_topup', 34)] = 8
        self.fake.boards[('surf_topup', 34, 2)] = 37
        # Refresh cached metadata, then the ordinary import makes the leg known.
        K._save(os.path.join(self.cache, 'maps', 'surf_topup.json'), self.fake.maps['surf_topup'])
        self.info, _, _ = K.sweep_maps(['surf_topup'], self.cache, 120, K.Pacer(0, 30))
        self.file()
        key = ('surf_topup', 4, 0, 'hsw')
        old = S.variant_base
        S.variant_base = lambda name: 'surf_topup' if name == 'surf_topup_ksf' else None
        try:
            r = self.client.post('/api/board?ksfmore=1&map=surf_topup_ksf&track=4&leg=0&style=hsw')
            self.assertEqual(r.status_code, 202)
        finally:
            S.variant_base = old
        self.assertEqual(Q.pending(self.db)[0][:4], key)
        self.fake.asked.clear()
        done = self.step()
        self.file(); K.finish_topups(done)
        self.assertEqual(Q.count(self.db, key), 37)
        self.assertEqual(Q.count(self.db, self.key), 120)
        self.assertTrue(all(z == 34 and mode == 2 for _, z, _, mode in T.pages(self.fake, modes=True)))
        self.assertEqual(Q.status(self.db, key)['state'], 'exhausted')

    def test_cap_lock_and_refusal(self):
        old = Q.MAX_ACTIVE
        Q.MAX_ACTIVE = 0
        try:
            self.assertEqual(Q.enqueue(self.db, self.key, 100), (None, 429))
        finally:
            Q.MAX_ACTIVE = old
        hold = S.connect()
        try:
            hold.execute('BEGIN IMMEDIATE')
            at = time.monotonic()
            r = self.client.post('/api/board?ksfmore=1&map=surf_topup')
            self.assertEqual(r.status_code, 503)
            self.assertLess(time.monotonic() - at, 1)
        finally:
            hold.rollback(); hold.close()
        Q.enqueue(self.db, self.key, 100)
        self.fake.refuse_after = 0
        self.fake.asked.clear()
        with self.assertRaises(K.Refused):
            self.step()
        self.assertEqual(len(self.fake.asked), 1)
        self.assertEqual(Q.status(self.db, self.key)['state'], 'queued')


class EmbeddedZones(unittest.TestCase):
    def test_public_proxy_opens_only_selected_map_post(self):
        cfg = (Path(__file__).resolve().parents[1] / 'src/release/ftesurf.nginx').read_text()
        exact = cfg.split('location = /ftesurf/board/api/map {', 1)[1].split('\n}', 1)[0]
        rest = cfg.split('location ^~ /ftesurf/board/ {', 1)[1].split('\n}', 1)[0]
        self.assertIn('limit_except GET POST { deny all; }', exact)
        self.assertIn('proxy_pass            http://127.0.0.1:8084/board/api/map;', exact)
        self.assertIn('limit_except GET { deny all; }', rest)

    def bsp(self, name, ents, model_count=3):
        path = Path(T.HOME) / (name + '.bsp')
        header = bytearray(zonefit.HDRSZ)
        header[:8] = b'VBSP' + struct.pack('<i', 20)
        body = ents.encode()
        models = (struct.pack('<6f', -100, -100, -100, 100, 100, 100) + bytes(24)) * model_count
        struct.pack_into('<ii', header, 8, len(header), len(body))
        struct.pack_into('<ii', header, 8 + 14 * 16, len(header) + len(body), len(models))
        path.write_bytes(header + body + models)
        return str(path)

    def test_both_brush_timers_required_and_cache_invalidates(self):
        start = '{"classname" "trigger_momentum_timer_start" "model" "*1"}'
        stop = '{"classname" "trigger_momentum_timer_stop" "model" "*2"}'
        p = self.bsp('timer', start + stop)
        self.assertTrue(zonefit.has_timer(p))
        self.assertFalse(zonefit.has_timer(self.bsp('startonly', start)))
        self.assertFalse(zonefit.has_timer(self.bsp('badmodel', start + stop.replace('*2', '*99'))))
        self.assertFalse(zonefit.has_timer(self.bsp('point', start + stop.replace('"*2"', '""'))))
        self.bsp('timer', start)
        self.assertFalse(zonefit.has_timer(p))
        old_maps, old_online, old_local = S.MAPS_DIR, S.ZONES_DIR, S.ZONES_LOCAL_DIR
        try:
            S.MAPS_DIR = T.HOME; S.ZONES_DIR = S.ZONES_LOCAL_DIR = T.HOME + '/absent'
            self.bsp('complete', start + stop)
            bsp, zones = S._scan_maps()
            self.assertIn('complete', zones)
            self.assertNotIn('startonly', zones)
        finally:
            S.MAPS_DIR, S.ZONES_DIR, S.ZONES_LOCAL_DIR = old_maps, old_online, old_local


if __name__ == '__main__':
    unittest.main()
