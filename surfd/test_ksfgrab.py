#!/usr/bin/env python3
"""Offline collector/index/API falsifier. --out must be inside an owned task root."""
import argparse
import io
import http.client
import sqlite3
import time
from types import SimpleNamespace
import json
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import urllib.error

p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
a, rest = p.parse_known_args()
if not any((x / 'OWNER.md').is_file() for x in [a.out, *a.out.parents]):
    p.error('--out requires an ancestor OWNER.md')
a.out.mkdir(parents=True, exist_ok=True)
os.environ.update(SURFD_HOME=str(a.out), SURFD_DB=str(a.out/'test.db'))
import surfd as S
import ksfimport as K
import ksfgrab as G


def binary(version=2):
    marks = [(0, 2, 1), (2, 3, 1), (6, 2, 99)]
    h = struct.pack('<4i', version, 99, 500, len(marks))
    if version == 3:
        h += struct.pack('<2i', 18, 0)
    for tick, touch, zone in marks:
        h += struct.pack('<3i', tick, touch, zone) + bytes(512)
    for tick in range(10):
        h += struct.pack('<i9f', 8, tick*3, 0, 40, 0, 90, 0, 200, 0, 0)
        if version == 3:
            h += struct.pack('<i7f', 1, 0, 0, 1, 0, 0, 0, 0)
    return h


def raw(**updates):
    r = dict(rank=1, playerID=7, steamID='STEAM_0:0:123', name='demo',
             time=.06, date=1700000000, record_id=111,
             file='replay_css_5_0_7_1700000000.rec')
    r.update(updates)
    return r


class Tests(unittest.TestCase):
    def setUp(self):
        self.cache = str(a.out / self._testMethodName)
        Path(self.cache).mkdir(exist_ok=True)
        for name in ('.refused', 'demos.json'):
            (Path(self.cache) / name).unlink(missing_ok=True)
        self.conn = S.connect()
        self.conn.execute('DELETE FROM runs')
        self.conn.execute('DELETE FROM replays')
        self.conn.commit()
        self.r = raw()
        self.job = G.candidate('surf_test', 0, 0, self.r)
        K.write_rows([K.rec_row('surf_test', 0, 0, self.r)])

    def tearDown(self):
        self.conn.close()

    def board(self, rows):
        K._save(K.board_path(self.cache, 'surf_test', 0), dict(rows=rows, done=True))

    def test_advertised_only_and_exact_context(self):
        self.assertIsNotNone(self.job)
        for change in [dict(file=None), dict(file='../../x.rec'), dict(file='https://bad/x'),
                       dict(playerID=8), dict(record_id=None), dict(date=0),
                       dict(file='replay_css_5_1_7_1700000000.rec')]:
            self.assertIsNone(G.candidate('surf_test', 0, 0, raw(**change)))
        self.assertIsNone(G.candidate('surf_test', 2, 0, self.r))
        self.assertIsNone(G.candidate('../surf_test', 0, 0, self.r))
        self.board([self.r, raw(playerID=8, file=None)])
        state = {}
        G.discover(self.cache, state, self.conn)
        self.assertEqual(len(state['jobs']), 1)

    def test_install_api_idempotent_no_native_promotion(self):
        # Real SQLite schema/API, not a stubbed index or reader.
        rid = G.install(self.conn, self.job, binary())
        self.assertGreater(rid, 0)
        self.assertEqual(G.install(self.conn, self.job, binary()), rid)
        row = self.conn.execute('SELECT * FROM replays WHERE id=?', (rid,)).fetchone()
        self.assertEqual((row['kind'], row['tier']), ('ksf', S.TIER_KSF))
        path, why = S.replay_file(row)
        self.assertEqual(why, '')
        text = Path(path).read_text()
        self.assertIn('foreign ksf ', text)
        self.assertIn('mapbuild unknown', text)
        self.assertNotIn('integrity ', text)
        with S.app.test_client() as cl:
            reply = cl.get('/api/replay/%d' % rid)
            self.assertEqual(reply.status_code, 200)
            self.assertIn(b'FTESURF-REC 5', reply.data)
            reply.close()
        self.assertEqual(self.conn.execute('SELECT millis,replay_id FROM runs').fetchone()[:], (60, rid))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM runs WHERE tier<>'ksf'").fetchone()[0], 0)
        self.assertTrue(list((Path(S.KSF_DIR)/'.originals').glob('*.rec')))

    def test_faster_sub_millisecond_invalidates_and_old_job_refuses(self):
        rid = G.install(self.conn, self.job, binary())
        faster = raw(time=.0599, record_id=112, date=1699999999,
                     file='replay_css_5_0_7_1699999999.rec')
        K.write_rows([K.rec_row('surf_test', 0, 0, faster)])
        self.assertEqual(self.conn.execute('SELECT millis,replay_id FROM runs').fetchone()[:], (60, 0))
        self.assertIsNone(G.install(self.conn, self.job, binary()))
        # Old slower PB, despite its newer date and identical rounded millis,
        # cannot restore the old row or link.
        K.write_rows([K.rec_row('surf_test', 0, 0, self.r)])
        self.assertEqual(self.conn.execute('SELECT runid FROM runs').fetchone()[0], K.record_key(faster))
        self.assertIsNotNone(self.conn.execute('SELECT id FROM replays WHERE id=?', (rid,)).fetchone())

    def test_same_record_refresh_and_file_withdrawal(self):
        rid = G.install(self.conn, self.job, binary())
        K.write_rows([K.rec_row('surf_test', 0, 0, self.r)])
        self.assertEqual(self.conn.execute('SELECT replay_id FROM runs').fetchone()[0], rid)
        doc = {'rows': [self.r]}
        K.merge_page(doc, [raw(file=None)])
        self.assertIsNone(doc['rows'][0]['file'])
        K.write_rows([K.rec_row('surf_test', 0, 0, doc['rows'][0])])
        self.assertEqual(self.conn.execute('SELECT replay_id FROM runs').fetchone()[0], 0)

    def test_wrong_time_player_style_and_bad_binary(self):
        for changes in [dict(map='surf_other'), dict(track=4), dict(style='sw'),
                        dict(player='other'), dict(runid='different'), dict(millis=61)]:
            j = dict(self.job, **changes)
            self.assertIsNone(G.install(self.conn, j, binary()))
        with self.assertRaises(ValueError): G.install(self.conn, self.job, b'bad')
        self.assertIsNone(G.install(self.conn, dict(self.job, seconds=2), binary()))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM replays').fetchone()[0], 0)

    def test_refusal_shared_cooldown_and_recovery(self):
        self.board([self.r])
        calls = []
        def refused(file):
            calls.append(file)
            raise urllib.error.HTTPError('public', 429, 'refused', {}, io.BytesIO())
        with patch.object(G.time, 'sleep') as sleep:
            self.assertEqual(G.tick(self.cache, download=refused), (1, 0))
            sleep.assert_called_once_with(3.0)
            self.assertEqual(G.tick(self.cache, download=refused), (0, 0))
        self.assertEqual(len(calls), 1)
        K._save(os.path.join(self.cache, '.refused'), dict(until=0))
        with patch.object(G.time, 'sleep'), patch.object(G.time, 'time', return_value=time.time()+K.COOLDOWN+1):
            self.assertEqual(G.tick(self.cache, download=lambda f: binary()), (1, 1))
            self.assertEqual(G.tick(self.cache, download=lambda f: self.fail('warm download')), (0, 0))

    def test_fixed_origin_ua_and_body_failures_park_entire_host(self):
        other = raw(playerID=8, steamID='STEAM_0:0:124', record_id=112,
                    file='replay_css_5_0_8_1700000000.rec')
        K.write_rows([K.rec_row('surf_test', 0, 0, other)])
        self.board([self.r, other])
        errors = [ConnectionResetError('body reset'), http.client.IncompleteRead(b'part', 8)]
        for error in errors:
            for name in ('.refused', 'demos.json'):
                (Path(self.cache)/name).unlink(missing_ok=True)
            class Body:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read1(self, count):
                    self_count.append(count)
                    raise error
            self_count = []
            with patch.object(G.urllib.request, 'build_opener') as build, patch.object(G.time, 'sleep'):
                opener = build.return_value
                opener.open.return_value = Body()
                self.assertEqual(G.tick(self.cache), (1, 0))
                self.assertEqual(opener.open.call_count, 1)
                req = opener.open.call_args.args[0]
                self.assertEqual(req.full_url, K.KSF_BASE+'/api/replays/'+self.r['file']+'?game=66t')
                self.assertEqual(req.get_header('User-agent'), K.UA)
                self.assertEqual(self_count, [64<<10])
            self.assertGreater(K._load(os.path.join(self.cache, '.refused'))['until'], time.time())
            self.assertEqual(len(K._load(os.path.join(self.cache, 'demos.json'))['jobs']), 2)
        with self.assertRaises(ValueError): G.fetch('../file.rec')

    def test_streaming_byte_cap_and_body_deadline_act_before_decode(self):
        class Body:
            def __init__(self): self.reads=0
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read1(self,count):
                self.reads+=1
                return b'x'*count
        with patch.object(G.urllib.request,'build_opener') as build:
            body=Body();build.return_value.open.return_value=body
            with self.assertRaises(ValueError): G.fetch(self.r['file'])
            self.assertEqual(body.reads,(G.MAX_BYTES//(64<<10))+1)
            body=Body();build.return_value.open.return_value=body
            with patch.object(G.time,'monotonic',side_effect=[0,0,31]):
                with self.assertRaises(urllib.error.URLError): G.transport(G.fetch,self.r['file'])
            self.assertEqual(body.reads,1)
            body=Body();body.headers={'Content-Length':'10'}
            body.read1=lambda count: b''
            build.return_value.open.return_value=body
            with self.assertRaises(urllib.error.URLError): G.transport(G.fetch,self.r['file'])

    def test_seed_keeps_raw_seconds_and_cannot_erase_known_binding(self):
        self.conn.execute('DELETE FROM runs'); self.conn.commit()
        exact = raw(time=.0601)
        K.write_rows([K.rec_row('surf_test', 0, 0, exact)])
        job = G.candidate('surf_test', 0, 0, exact)
        rid = G.install(self.conn, job, binary())
        sid = int(job['player'])
        for seconds in (.0604, .0601):
            rec = dict(mapName='surf_test', time=seconds, date=1700000001, record_id=113)
            with patch.object(K, 'records', return_value=({'records':[rec]}, False)):
                rows, _ = K.seed_mode(SimpleNamespace(max=1), {sid:'seed'}, {'surf_test'}, self.cache)
            self.assertEqual(rows[0]['seconds'], seconds)
            K.write_rows(rows)
            got = self.conn.execute('SELECT runid,replay_id FROM runs').fetchone()
            self.assertEqual(got[:], (job['runid'], rid))
        rec = dict(mapName='surf_test', time=.0599, date=1700000001, record_id=114)
        with patch.object(K, 'records', return_value=({'records':[rec]}, False)):
            rows, _ = K.seed_mode(SimpleNamespace(max=1), {sid:'seed'}, {'surf_test'}, self.cache)
        K.write_rows(rows)
        got = self.conn.execute('SELECT runid,replay_id FROM runs').fetchone()
        self.assertEqual(K.record_seconds(got['runid']), .0599)
        self.assertEqual(got['replay_id'], 0)
        rounded = dict(rows[0]); rounded.pop('seconds'); rounded['runid']=''; rounded['when']+=1
        K.write_rows([rounded])
        self.assertEqual(self.conn.execute('SELECT runid FROM runs').fetchone()[0], got['runid'])

    def test_budget_reservation_and_shared_lock_in_main_path(self):
        seen = []
        def watch(args, have, cache):
            seen.append(('boards', args.max))
            return [], []
        def demos(cache, maximum, delay):
            self.assertIsNone(K.take_lock(cache))  # The real main lock still acts.
            seen.append(('demos', maximum))
        argv = ['ksfimport.py','--watch','--go','--demos','--cache',self.cache,'--max','6']
        with patch.object(sys, 'argv', argv), patch.object(K, 'playable_maps', return_value={'surf_test'}), \
             patch.object(K, 'watch_mode', side_effect=watch), patch.object(G, 'tick', side_effect=demos):
            self.assertEqual(K.main(), 0)
        self.assertEqual(seen, [('boards',4), ('demos',2)])
        held = K.take_lock(self.cache)
        self.assertIsNotNone(held)
        held.close()

    def test_scan_rotation_and_queue_cap_and_obsolete_progress(self):
        records = []
        for i in range(36):
            mp = 'surf_q%02d'%i
            r = raw(record_id=200+i)
            records.append(K.rec_row(mp, 0, 0, r))
            K._save(K.board_path(self.cache, mp, 0), dict(rows=[r], done=True))
        K.write_rows(records)
        state = {}
        G.discover(self.cache, state, self.conn)
        self.assertEqual(len(state['jobs']), G.SCAN)
        G.discover(self.cache, state, self.conn)
        self.assertEqual(len(state['jobs']), 36)
        many = [raw(playerID=100+i, steamID='STEAM_0:0:%d'%(1000+i), record_id=1000+i,
                    file='replay_css_5_0_%d_1700000000.rec'%(100+i)) for i in range(260)]
        K.write_rows([K.rec_row('surf_queue',0,0,r) for r in many])
        K._save(K.board_path(self.cache,'surf_queue',0), dict(rows=many,done=True))
        state = {'cursor':'surf_q35/z0.json'}
        G.discover(self.cache,state,self.conn)
        self.assertEqual(len(state['jobs']), G.MAX_QUEUE)
        K._save(os.path.join(self.cache,'demos.json'),state)
        self.conn.execute('DELETE FROM runs');self.conn.commit()
        r=raw(record_id=9000)
        K.write_rows([K.rec_row('surf_zlater',0,0,r)])
        K._save(K.board_path(self.cache,'surf_zlater',0),dict(rows=[r],done=True))
        self.assertEqual(G.tick(self.cache,maximum=0), (0,0))
        jobs=K._load(os.path.join(self.cache,'demos.json'))['jobs']
        self.assertEqual([j['map'] for j in jobs.values()], ['surf_zlater'])

    def test_256_warm_rows_do_not_starve_cold_row_and_removals_are_durable(self):
        rows=[raw(playerID=2000+i, steamID='STEAM_0:0:%d'%(2000+i), record_id=30000+i,
                  file='replay_css_5_0_%d_1700000000.rec'%(2000+i)) for i in range(257)]
        K.write_rows([K.rec_row('surf_warm',0,0,r) for r in rows])
        K._save(K.board_path(self.cache,'surf_warm',0),dict(rows=rows,done=True))
        jobs={}
        for r in rows[:256]:
            j=G.candidate('surf_warm',0,0,r)
            self.assertGreater(G.install(self.conn,j,binary()),0)
            self.assertTrue(G.ready(self.conn,j))
            key='surf_warm|0|0|'+j['runid']
            jobs[key]=dict(j,status='queued',retry=0)
        K._save(os.path.join(self.cache,'demos.json'),dict(jobs=jobs,cursor=''))
        calls=[]
        def download(file): calls.append(file);return binary()
        with patch.object(G.time,'sleep'):
            self.assertEqual(G.tick(self.cache,maximum=1,download=download),(1,1))
            self.assertEqual(G.tick(self.cache,maximum=1,download=download),(0,0))
        self.assertEqual(calls,[rows[-1]['file']])
        self.assertEqual(K._load(os.path.join(self.cache,'demos.json'))['jobs'],{})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM runs WHERE map='surf_warm' AND replay_id>0").fetchone()[0],257)

    def test_warm_missing_file_requeues_and_recovers_same_index(self):
        self.board([self.r])
        rid=G.install(self.conn,self.job,binary())
        row=self.conn.execute('SELECT * FROM replays WHERE id=?',(rid,)).fetchone()
        path,_=S.replay_file(row)
        self.assertTrue(G.ready(self.conn,self.job))
        Path(path).unlink()  # This case's own synthetic normalized fixture only.
        self.assertFalse(G.ready(self.conn,self.job))
        with patch.object(G.time,'sleep'):
            self.assertEqual(G.tick(self.cache,maximum=1,download=lambda file:binary()),(1,1))
        self.assertTrue(G.ready(self.conn,self.job))
        self.assertEqual(self.conn.execute('SELECT replay_id FROM runs').fetchone()[0],rid)
        self.assertEqual(K._load(os.path.join(self.cache,'demos.json'))['jobs'],{})

    def test_interrupted_index_retries_after_files_without_native_mutation(self):
        self.board([self.r])
        original_install=G.install
        class FailIndex:
            def __enter__(self): self.entered=self_conn.__enter__();return self
            def __exit__(self,*args): return self_conn.__exit__(*args)
            def execute(self,sql,*args):
                if sql.startswith('INSERT INTO replays'): raise sqlite3.OperationalError('acted index failure')
                return self_conn.execute(sql,*args)
        self_conn=self.conn
        def interrupted(conn,job,data): return original_install(FailIndex(),job,data)
        with patch.object(G.time,'sleep'), patch.object(G,'install',side_effect=interrupted):
            with self.assertRaises(sqlite3.OperationalError): G.tick(self.cache,download=lambda f:binary())
        self.assertEqual(self.conn.execute('SELECT replay_id FROM runs').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM replays').fetchone()[0],0)
        self.assertEqual(len(K._load(os.path.join(self.cache,'demos.json'))['jobs']),1)
        self.assertTrue(list((Path(S.KSF_DIR)/'surf_test/main').glob('*_run.rec')))
        with patch.object(G.time,'sleep'):
            self.assertEqual(G.tick(self.cache,download=lambda f:binary()),(1,1))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM replays').fetchone()[0],1)

    def test_local_archive_error_is_not_a_host_refusal_and_three_strikes_retire(self):
        self.board([self.r])
        base=time.time()
        for i in range(3):
            with patch.object(G.time,'sleep'), patch.object(G.time,'time',return_value=base+i*86401), \
                 patch.object(G,'install',side_effect=OSError('acted disk failure')):
                self.assertEqual(G.tick(self.cache,download=lambda f:binary()),(1,0))
            self.assertFalse((Path(self.cache)/'.refused').exists())
        state=K._load(os.path.join(self.cache,'demos.json'))
        self.assertEqual(state['jobs'],{})
        self.assertEqual(len(state['failed']),1)

    def test_variant_board_times_survive_without_unplayable_watch(self):
        rid=G.install(self.conn,self.job,binary())
        path=Path(S.DATA_DIR)/'mapwatch/catalogue.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'maps':{'surf_test_css':{'of':'surf_test'}}}))
        S._variants['at']=None
        with S.app.test_client() as cl:
            base=cl.get('/api/board?map=surf_test&tier=ksf').get_json()
            variant=cl.get('/api/board?map=surf_test_css&tier=ksf').get_json()
        self.assertEqual(base['rows'][0]['rep'],rid)
        self.assertEqual(variant['rows'][0]['rep'],0)
        self.assertEqual(base['rows'][0]['ms'],variant['rows'][0]['ms'])

    def test_path_kind_and_escape_refusal(self):
        rid = G.install(self.conn, self.job, binary())
        row = dict(self.conn.execute('SELECT * FROM replays WHERE id=?', (rid,)).fetchone())
        for k, value in [('kind', 'nonsense'), ('leaf', '../x.rec'), ('map_dir', '../')]:
            r = dict(row); r[k] = value
            self.assertEqual(S.replay_file(r)[1], 'name')


unittest.main(argv=[sys.argv[0], *rest])
