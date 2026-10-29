#!/usr/bin/env python3
"""KSF profile-demand controls: real migrated DB, fake paced source, no network."""
import hashlib
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
        m = re.search(r'/players/([^/]+)/records/map/([^?]+)\?game=css&mode=(\d)$', url)
        if m:
            sid, mp, mode = m.group(1), m.group(2), int(m.group(3))
            if mp in getattr(self, 'missing', ()):
                raise K.NoSuchPlayer('HTTP 500')
            fail = getattr(self, 'fail', {}).get(mp)
            if isinstance(fail, Exception):
                raise fail
            if fail is not None:
                return json.dumps(fail)         # a reply of some other shape
            recs = [{'zoneId': z, 'record_id': 7000 + z, 'surfTime': 5.0 + z,
                     'date_set_at': '2026-10-01T00:00:%02dZ' % z, 'rank': 1}
                    for z in (0, 1, 2, 3, 31, 32)] if mode == 0 else []
            return json.dumps({'detail': 'pr', 'records': recs,
                               'basicInfo': {'steamID': getattr(self, 'who', sid)}})
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
        self.db.execute('DELETE FROM ksf_unbound'); self.db.execute('DELETE FROM ksfprofiles'); self.db.execute('DELETE FROM runs'); self.db.execute('DELETE FROM accounts'); self.db.commit()
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
        # A signed-in account's walk: a profile view's stops at VIEW_PAGES (P1117 review 4).
        self.db.execute("INSERT INTO accounts (steamid, created_at) VALUES (?, 1)", (PLAYER,)); self.db.commit()
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
        # P1117 review 3: a host refusal parks the walks (never the host), past that page.
        self.queue()
        with patch.object(K, 'fetch', side_effect=K.Refused('HTTP 429', 429)):
            self.step()
        self.assertEqual((P.status(self.db, PLAYER)['next'], self.count()), (6, 0))
        self.assertEqual(self.parks(), [P.PARK])
        with patch.object(K, 'fetch', side_effect=AssertionError('asked while parked')):
            self.assertEqual(self.step(now=1002), 0)
    def test_wrong_offset_never_exhausts_or_imports(self):
        # P1117 review 3: a bad page ends the walk ('limited', never complete), no park.
        self.queue(); self.step()
        with patch.object(K, 'fetch', return_value=json.dumps({'records': [], 'pagination': {'offset': 0, 'limit': 5}})):
            self.step()
        self.assertEqual((P.status(self.db, PLAYER)['state'], P.status(self.db, PLAYER)['next']),
                         ('refused', 6))
        self.assertEqual((self.count(), self.parks()), (5, []))

    def parks(self):
        return [n for n in ('.refused', P.PARK) if os.path.exists(os.path.join(self.cache, n))]

    def test_p1117r3_a_bad_record_is_skipped_never_parks_or_replays(self):
        good = {'mapName': 'surf_profile1', 'record_id': None, 'time': 11.0, 'date': 1790000001,
                'stage_id': None, 'zone_id': None}
        bad = [dict(good, mapName='surf_profile2', date=None), dict(good, mapName='surf_profile3', time=0),
               dict(good, mapName='../../etc'), dict(good, mapName='surf_profile4', stage_id=9)]
        page = json.dumps({'records': [good] + bad, 'pagination': {'offset': 0, 'limit': 5}})
        self.queue()
        with patch.object(K, 'fetch', return_value=page):
            self.assertEqual(self.step(), 1)
        st = P.status(self.db, PLAYER)
        self.assertEqual((self.count(), st['unavailable'], st['next'], self.parks()), (1, 4, 6, []))
        # A saved page that no longer reads is deleted and ends its walk; never replayed.
        self.db.execute('DELETE FROM ksfprofiles'); self.db.commit(); self.queue(now=5000)
        leaf = hashlib.sha256(PLAYER.encode('ascii')).hexdigest()
        fn = os.path.join(self.cache, 'profiles', leaf, '0-1.json')
        K._save(fn, {'asked': 5000, 'body': {'records': 'x'}})
        with patch.object(K, 'fetch', side_effect=AssertionError('the saved page is used')):
            self.step(now=5001)
        self.assertEqual((os.path.exists(fn), P.status(self.db, PLAYER)['state'], self.parks()),
                         (False, 'refused', []))

    def test_p1117r4_an_out_of_range_date_is_a_bad_record(self):
        page = ('{"records": [{"mapName": "surf_profile1", "record_id": null, "time": 11.0, "date": 1e400,'
                ' "stage_id": null, "zone_id": null}, {"mapName": "surf_profile2", "record_id": null,'
                ' "time": 11.0, "date": 100000000000000000000, "stage_id": null, "zone_id": null},'
                ' {"mapName": "surf_profile3", "record_id": null, "time": 12.0, "date": 1790000003,'
                ' "stage_id": null, "zone_id": null}], "pagination": {"offset": 0, "limit": 5}}')
        self.queue()
        with patch.object(K, 'fetch', return_value=page):
            self.step()
        self.assertEqual((self.count(), P.status(self.db, PLAYER)['unavailable']), (1, 2))
        # A saved page holding one heals on replay: skipped, never raised.
        self.db.execute('DELETE FROM ksfprofiles'); self.db.commit(); self.queue(now=5000)
        leaf = hashlib.sha256(PLAYER.encode('ascii')).hexdigest()
        K._save(os.path.join(self.cache, 'profiles', leaf, '0-1.json'),
                {'asked': 5000, 'body': {'records': [{'mapName': 'surf_profile4', 'time': 9.0, 'date': 10 ** 20,
                                                      'stage_id': None, 'zone_id': None}],
                                         'pagination': {'offset': 0, 'limit': 5}}})
        with patch.object(K, 'fetch', side_effect=AssertionError('the saved page is used')):
            self.step(now=5001)
        self.assertEqual(P.status(self.db, PLAYER)['unavailable'], 1)

    def test_p1117r4_a_walk_error_never_stops_the_crawl(self):
        self.queue()
        calls = []

        def fetch(url):
            calls.append(url)
            if '/api/maps/new' in url:
                return '[]'
            raise AssertionError(url)
        with patch.object(P, 'step', side_effect=OverflowError('int too large')), \
                patch.object(K, 'fetch', side_effect=fetch):
            K.watch_mode(SimpleNamespace(delay=0, max=10, go=True), self.have, self.cache)
        self.assertEqual((bool(calls), self.parks()), (True, [P.PARK]))

    def test_p1117r5_a_walk_that_raises_gives_up_its_turn(self):
        other = '76561198000000099'
        self.queue(now=100); self.queue(other, now=200)
        real = K.rec_row

        def broken(mp, zone, mode, rec):
            if rec.get('steamID') == PLAYER:
                raise ValueError('a value nothing expected')
            return real(mp, zone, mode, rec)
        with patch.object(K, 'rec_row', broken):
            with self.assertRaises(ValueError):
                self.step(now=1001)
        self.assertEqual(P.pending(self.db)[0][0], other)

    def test_p1117r4_a_view_walk_is_capped(self):
        self.src.n = 100; self.queue()
        with patch.object(P, 'VIEW_PAGES', 3):
            for i in range(6):
                self.step(now=1001 + i)
        st = P.status(self.db, PLAYER)
        self.assertEqual((st['state'], st['pages'], self.count()), ('limited', 3, 15))

    def test_p1117r3_a_walks_403_ends_it_and_never_lifts_a_park(self):
        self.queue()
        K._save(os.path.join(self.cache, P.PARK), {'at': 1, 'until': 2, 'n': 3, 'why': 'old'})
        p = K.Pacer(0, 10)
        with patch.object(K, 'fetch', side_effect=K.Refused('HTTP 403', 403)):
            P.step(K, self.cache, p, self.have, 1001, 3)
        self.assertEqual((P.status(self.db, PLAYER)['state'], p.made, p.unanswered), ('refused', 1, 1))
        self.assertEqual(K._load(os.path.join(self.cache, P.PARK))['n'], 3)

    def test_p1117r3_a_view_walks_main_records_only(self):
        self.stage_world()
        self.db.execute('DELETE FROM accounts'); self.db.commit()
        self.assertEqual(self.step(budget=10), 4)
        self.assertEqual(([c for c in self.src.calls if '/records/map/' in c],
                          P.status(self.db, PLAYER)['state']), ([], 'complete'))
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
    def stage_world(self):
        """P1117: three main completions; profile0 is staged (2 stages, 1 bonus),
        profile1 linear with no bonus, profile2's map info is not cached."""
        self.src.n = 3
        maps = Path(self.cache) / 'maps'
        maps.mkdir()
        for mp, info in (('surf_profile0', {'isLinear': False, 'cp_count': 2, 'b_count': 1}),
                         ('surf_profile1', {'isLinear': True, 'cp_count': 4, 'b_count': 0})):
            (maps / (mp + '.json')).write_text(json.dumps([dict(info, name=mp)]))
        # P1117 review 3: only a signed-in account's walk has a stage phase.
        self.db.execute("INSERT OR IGNORE INTO accounts (steamid, created_at) VALUES (?, 1)", (PLAYER,))
        self.db.commit()
        self.queue()

    def zones(self, mp='surf_profile0'):
        return self.db.execute("SELECT track, leg, millis, runid != '', replay_id FROM runs"
                               " WHERE tier='ksf' AND map=? ORDER BY track, leg", (mp,)).fetchall()

    def test_p1117_stage_phase_files_only_the_zones_the_map_has(self):
        self.stage_world()
        # A board-bound stage PB (its demo file named): the walk's equal time must keep it.
        when = P._iso('2026-10-01T00:00:01Z')
        board = dict(K.rec_row('surf_profile0', 1, 0, {
            'steamID': K.S.steam2(PLAYER), 'time': 6.0, 'date': when, 'record_id': 7001,
            'file': 'replay_css_5_0_9_%d.rec' % when}), name='p')
        K.write_rows([board])
        self.assertEqual(self.step(budget=10), 5)
        self.assertEqual(self.db.execute("SELECT runid FROM runs WHERE map='surf_profile0' AND leg=1")
                         .fetchone()[0], board['runid'])
        asked = [c for c in self.src.calls if '/records/map/' in c]
        self.assertEqual([c.split('/records/map/')[1] for c in asked], ['surf_profile0?game=css&mode=0'])
        self.assertEqual([tuple(r) for r in self.zones()],
                         [(0, 0, 10010, 0, 0), (0, 1, 6000, 1, 0), (0, 2, 7000, 1, 0), (1, 0, 36000, 1, 0)])
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'complete')

    def test_p1117_stage_phase_budget_500_and_identity(self):
        self.stage_world()
        p = K.Pacer(0, 10)          # the crawl's pacer has room; the walk's budget does not
        P.step(K, self.cache, p, self.have, 1001, 4)
        self.assertEqual((p.made, P.status(self.db, PLAYER)['mode']), (4, P.STAGE_MODE))
        self.src.missing = {'surf_profile0'}
        p = K.Pacer(0, 10)
        P.step(K, self.cache, p, self.have, 1002, 4)
        self.assertEqual((p.made, p.unanswered, len(self.zones())), (1, 1, 1))
        self.assertEqual(P.status(self.db, PLAYER)['state'], 'complete')
        self.db.execute('DELETE FROM ksfprofiles'); self.db.commit(); self.queue(now=5000)
        self.src.missing, self.src.who = set(), 'STEAM_0:0:1'
        P.step(K, self.cache, K.Pacer(0, 10), self.have, 5001, 10)    # P1117 review: skipped, not refused
        self.assertEqual((len(self.zones()), P.status(self.db, PLAYER)['state']), (1, 'complete'))

    def at_stage(self, now=3000):
        """The walk at its first stage map (profile0), the main pages done."""
        self.stage_world()
        P.step(K, self.cache, K.Pacer(0, 10), self.have, now - 1, 4)
        self.assertEqual((P.status(self.db, PLAYER)['mode'], P.status(self.db, PLAYER)['next']),
                         (P.STAGE_MODE, 0))

    def test_p1117r1_a_maps_failure_skips_it_and_never_parks(self):
        stages = lambda: (P.status(self.db, PLAYER)['mode'], P.status(self.db, PLAYER)['next'])
        for fail in (K.Refused('HTTP 404', 404),
                     K.Refused("ksf.surf's reply did not parse"),
                     {'records': [], 'basicInfo': None}, {'records': 'x', 'basicInfo': {}},
                     {'records': [{}] * (P.STAGE_RECORDS_MAX + 1),
                      'basicInfo': {'steamID': K.S.steam2(PLAYER)}}):
            with self.subTest(fail=str(fail)[:40]):
                self.db.execute('DELETE FROM ksfprofiles'); self.db.execute('DELETE FROM runs')
                self.db.commit()
                shutil.rmtree(self.cache); self.cache = tempfile.mkdtemp(dir=HOME)
                self.at_stage()
                self.src.fail = {'surf_profile0': fail}
                p = K.Pacer(0, 10)
                P.step(K, self.cache, p, self.have, 3001, 1)
                self.assertEqual((p.made, p.unanswered, P.status(self.db, PLAYER)['state']),
                                 (1, 1, 'complete'))
                self.assertEqual(len(self.zones()), 1)

    def test_p1117r1_host_refusals_park_and_no_answer_moves_on(self):
        # P1117 review 3: a host code parks the WALKS (never the host), returns rather
        # than raising, past the map and after the others.
        other = '76561198000000077'
        for n, fail in enumerate((K.Refused('HTTP 429', 429), K.Refused('HTTP 502', 502),
                                  K.Refused('no answer: timed out', transient=True))):
            with self.subTest(fail=str(fail)):
                self.db.execute('DELETE FROM ksfprofiles'); self.db.execute('DELETE FROM runs')
                self.db.commit()
                shutil.rmtree(self.cache); self.cache = tempfile.mkdtemp(dir=HOME)
                self.at_stage(now=3000 + 10 * n)
                self.db.execute("INSERT OR IGNORE INTO accounts (steamid, created_at) VALUES (?, 1)", (other,))
                self.db.commit()
                self.queue(other, now=3005 + 10 * n)
                self.src.fail = {'surf_profile0': fail}
                p = K.Pacer(0, 10)
                P.step(K, self.cache, p, self.have, 3009 + 10 * n, 1)
                st = P.status(self.db, PLAYER)
                self.assertEqual((st['mode'], st['next'], P.pending(self.db)[0][0], self.parks(),
                                  p.made == p.unanswered), (P.STAGE_MODE, 1, other, [P.PARK], True))
                self.src.fail = {}

    def test_p1117r2_a_blocked_route_ends_the_stage_phase(self):
        for code in (401, 403):
            with self.subTest(code=code):
                self.db.execute('DELETE FROM ksfprofiles'); self.db.execute('DELETE FROM runs')
                self.db.commit()
                shutil.rmtree(self.cache); self.cache = tempfile.mkdtemp(dir=HOME)
                self.at_stage()
                self.src.fail = {'surf_profile0': K.Refused('HTTP %d' % code, code)}
                p = K.Pacer(0, 10)
                K._save(os.path.join(self.cache, P.PARK), {'at': 1, 'until': 2, 'n': 4})
                P.step(K, self.cache, p, self.have, 3001, 3)
                self.assertEqual((p.made, P.status(self.db, PLAYER)['state'], len(self.zones())),
                                 (1, 'limited', 1))
                # P1117 review 3: a refusal never counts as an answer, nor resets a backoff.
                self.assertEqual((p.unanswered, K._load(os.path.join(self.cache, P.PARK))['n']), (1, 4))
                self.src.fail = {}

    def test_p1117r2_a_saved_page_is_only_what_is_filed(self):
        self.at_stage()
        junk = 'x' * 100000
        recs = [{'zoneId': 1, 'record_id': 8001, 'surfTime': 6.5, 'date_set_at': '2026-10-01T00:00:01Z',
                 'junk': junk, 'rank': {'nested': junk}}]
        self.src.fail = {'surf_profile0': {'records': recs, 'junk': junk,
                                           'basicInfo': {'steamID': K.S.steam2(PLAYER), 'junk': junk}}}
        P.step(K, self.cache, K.Pacer(0, 10), self.have, 3001, 1)
        saved = [p for p in Path(self.cache, 'profiles').rglob('*surf_profile0.json')]
        self.assertEqual(len(saved), 1)
        body = json.loads(saved[0].read_text())['body']
        self.assertEqual(body, {'basicInfo': {'steamID': K.S.steam2(PLAYER)},
                                'records': [{'zoneId': 1, 'record_id': 8001, 'surfTime': 6.5,
                                             'date_set_at': '2026-10-01T00:00:01Z'}]})
        self.assertEqual(len(self.zones()), 2)
        main = [p for p in Path(self.cache, 'profiles').rglob('0-1.json')]
        self.assertEqual(set(json.loads(main[0].read_text())['body']), {'records', 'pagination'})

    def test_p1117r2_accounts_walks_come_first(self):
        view, mine = '76561198000000201', '76561198000000202'
        self.queue(view, now=100)
        self.db.execute("INSERT INTO accounts (steamid, created_at) VALUES (?, 1)", (mine,))
        self.db.commit()
        self.queue(mine, now=200)
        self.assertEqual([r[0] for r in P.pending(self.db)], [mine, view])
        self.db.execute('DELETE FROM accounts'); self.db.commit()

    def test_p1117r1_views_cannot_fill_an_accounts_slots(self):
        for i in range(P.MAX_VIEWED):
            self.assertEqual(self.queue('765611980000%05d' % (100 + i))['state'], 'queued')
        self.assertEqual(self.queue('76561198000099999')['state'], 'busy')
        self.db.execute("INSERT INTO accounts (steamid, created_at) VALUES (?, 1)", (PLAYER,))
        self.db.commit()
        self.assertEqual(self.queue()['state'], 'queued')
        self.db.execute('DELETE FROM accounts'); self.db.commit()

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
