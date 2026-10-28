#!/usr/bin/env python3
"""Real Ed25519, account/role, nonce, bounds and preservation falsifiers."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import ed25519
import zonepub as z

SEED = bytes(range(32))
PUB = ed25519.publickey(SEED).hex()
SID = '76561198000000001'


class Coded:
    """A test client whose refusals carry their code again: since P826 a refusal answers 200
    with ok=0 and the code in the body, and these tests assert the code."""
    def __init__(self, c): self.c = c
    def post(self, *a, **kw):
        r = self.c.post(*a, **kw)
        if r.status_code == 200 and r.is_json and r.json.get('ok') == 0: r.status_code = r.json['status']
        return r


def zone():
    r = dict(points=[[0,0],[32,0],[32,32],[0,32]],bottom=0,height=64)
    return dict(formatVersion=1, tracks=dict(main=dict(zones=dict(
        segments=[dict(checkpoints=[dict(regions=[r])])], end=dict(regions=[r])))))


class Upload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store, self.main, self.game = [self.root / n for n in ('zones.db','accounts.db','csprogs.dat')]
        z.initialize(self.store)
        self.game.write_bytes(b'synthetic game whitelist fixture')
        self.code = hashlib.sha256(self.game.read_bytes()).hexdigest()
        db = sqlite3.connect(self.main)
        db.executescript('CREATE TABLE accounts(steamid TEXT PRIMARY KEY,banned_at INTEGER); CREATE TABLE keylinks(pub TEXT,steamid TEXT);')
        db.execute('INSERT INTO accounts VALUES(?,0)', (SID,)); db.execute('INSERT INTO keylinks VALUES(?,?)',(PUB,SID)); db.commit(); db.close()
        self.now = 10000
        self.app = z.create_app(self.store,self.main,[self.game],clock=lambda:self.now,verify=ed25519)
        self.c = Coded(self.app.test_client())
        self.raw = (json.dumps(zone(), indent=2)+'\n').encode()
    def grant(self):
        with z.connect(self.store) as db: db.execute('INSERT OR IGNORE INTO roles VALUES(?)',(SID,))
    def challenge(self, raw=None, name='surf_fixture'):
        r = self.c.post('/api/zones/challenge',json=dict(map=name,sha=hashlib.sha256(raw or self.raw).hexdigest()))
        self.assertEqual(r.status_code,200,r.data)
        return r.json['nonce']
    def envelope(self, nonce, raw=None, kind=-6, site=z.SITE, keyed=1, code=None, seed=SEED):
        code = code or self.code
        msg = (z.accounts.STATEMENT % (site,nonce,kind,keyed,code)).encode()
        sig = ed25519.sign(seed,msg).hex()
        return ('{"nonce":"%s","pub":"%s","sig":"%s","game":"%s","zones":' %
                (nonce,ed25519.publickey(seed).hex(),sig,code)).encode()+(raw or self.raw)+b'}'
    def upload(self, nonce, **kw): return self.c.post('/api/zones/draft',data=self.envelope(nonce,**kw),content_type='application/json')
    def drafts(self):
        with z.connect(self.store) as db: return db.execute('SELECT * FROM drafts').fetchall()
    def test_positive_large_exact_snapshot_and_no_existing_writes(self):
        self.grant(); obj=zone(); obj['note']='x'*20000; raw=(json.dumps(obj,indent=2)+'\n').encode()
        before=self.main.read_bytes(); live=self.root/'live.json'; live.write_bytes(b'predecessor zones')
        r=self.upload(self.challenge(raw),raw=raw)
        self.assertEqual(r.status_code,200,r.data); self.assertEqual(r.json['ok'],1)
        self.assertEqual(self.drafts()[0]['body'],raw)
        self.assertEqual(self.drafts()[0]['steamid'],SID)
        self.assertEqual(self.main.read_bytes(),before); self.assertEqual(live.read_bytes(),b'predecessor zones')
        self.assertNotIn(SID,r.get_data(as_text=True)); self.assertIn('no-store',r.headers['Cache-Control'])
    def test_linked_nonadmin_is_denied(self):
        self.assertEqual(self.upload(self.challenge()).status_code,403)
        self.assertFalse(self.drafts())
    def test_refusal_reaches_the_game_with_its_reason(self):
        # P826: on the wire a refusal is 200, ok=0, the reason and the code (the raw client).
        r = self.c.c.post('/api/zones/draft',data=self.envelope(self.challenge()),content_type='application/json')
        self.assertEqual((r.status_code, r.json['ok'], r.json['status']), (200, 0, 403))
        self.assertEqual(r.json['error'], 'This Steam account is not a zone admin')
        self.assertFalse(self.drafts())
    def test_banned_and_unlinked_are_denied(self):
        self.grant()
        with sqlite3.connect(self.main) as db: db.execute('UPDATE accounts SET banned_at=1')
        self.assertEqual(self.upload(self.challenge()).status_code,403)
        with sqlite3.connect(self.main) as db: db.execute('DELETE FROM keylinks')
        self.assertEqual(self.upload(self.challenge()).status_code,403)
        self.assertFalse(self.drafts())
    def test_wrong_purpose_origin_key_and_signature_are_denied(self):
        self.grant()
        for kw in (dict(kind=-2),dict(site='evil.example:443'),dict(keyed=0),dict(seed=b'x'*32)):
            self.assertEqual(self.upload(self.challenge(),**kw).status_code,403)
        self.assertFalse(self.drafts())
    def test_nonce_binding_replay_expiry_and_role_recheck(self):
        self.grant(); n=self.challenge()
        self.assertEqual(self.upload(n,raw=self.raw+b' ').status_code,409)
        self.assertEqual(self.upload(n).status_code,200)
        self.assertEqual(self.upload(n).status_code,409)
        n=self.challenge(); self.now+=181
        self.assertEqual(self.upload(n).status_code,409)
        n=self.challenge()
        with z.connect(self.store) as db: db.execute('DELETE FROM roles')
        self.assertEqual(self.upload(n).status_code,403)
        self.assertEqual(len(self.drafts()),1)
    def test_unknown_game_and_proof_attempt_budget(self):
        self.grant(); n=self.challenge()
        for _ in range(3): self.assertEqual(self.upload(n,code='f'*64).status_code,403)
        self.assertEqual(self.upload(n).status_code,409)
        self.assertFalse(self.drafts())
    def test_malformed_geometry_and_capacity_do_not_land(self):
        self.grant()
        for obj in ({'error':'not zones'},dict(formatVersion=True,tracks={}),dict(formatVersion=1,tracks={'main':{}})):
            raw=json.dumps(obj).encode(); self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,400)
        obj=zone(); obj['tracks']['main']['zones']['end']['regions'][0]['height']=-1
        raw=json.dumps(obj).encode(); self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,400)
        self.assertFalse(self.drafts())
    def test_request_bounds_names_and_missing_store(self):
        for name in ('../surf_escape','surf_x/y','bhop_x.json','SURF_Upper','surf_a;cmd'):
            self.assertEqual(self.c.post('/api/zones/challenge',json=dict(map=name,sha='a'*64)).status_code,400)
        self.assertEqual(self.c.post('/api/zones/draft',data=b'x'*(z.MAX_ZONE_BYTES+2048)).status_code,413)
        self.assertEqual(self.c.post('/api/zones/challenge',json=dict(map='surf_fixture',sha='a'*64),
                         environ_overrides={'CONTENT_LENGTH':'','wsgi.input_terminated':True}).status_code,411)
        missing=self.root/'missing.db'
        c=Coded(z.create_app(missing,self.main,[self.game]).test_client())
        self.assertEqual(c.post('/api/zones/challenge',json=dict(map='surf_ok',sha='a'*64)).status_code,503)
        self.assertFalse(missing.exists())
    def test_review_stages_only_exact_bytes_and_requires_explicit_times_policy(self):
        self.grant(); r=self.upload(self.challenge()); ident=r.json['draft']; sha=hashlib.sha256(self.raw).hexdigest()
        (self.root/'OWNER.md').write_text('Synthetic owned staging fixture')
        bsp=self.root/'surf_fixture.bsp';bsp.write_bytes(b'synthetic BSP fingerprint fixture')
        bsp_sha=hashlib.sha256(bsp.read_bytes()).hexdigest()
        before=self.main.read_bytes()
        for policy in ('hide','archive'):
            with self.assertRaises(ValueError):z.stage(self.store,ident,sha,bsp,self.root/policy,policy,bsp_sha)
        with self.assertRaises(ValueError):z.stage(self.store,ident,'f'*64,bsp,self.root/'wrong','keep',bsp_sha)
        with self.assertRaises(ValueError):z.stage(self.store,ident,sha,bsp,self.root/'wrongbsp','keep','f'*64)
        out=self.root/'review';report=z.stage(self.store,ident,sha,bsp,out,'keep',bsp_sha)
        self.assertEqual((out/'surf_fixture.json').read_bytes(),self.raw)
        self.assertEqual(report['times_policy'],'keep')
        self.assertEqual(report['bsp_sha256'],bsp_sha)
        self.assertEqual(self.main.read_bytes(),before)
        self.assertNotIn(SID,(out/'REVIEW.json').read_text())
        with self.assertRaises(ValueError):z.stage(self.store,ident,sha,bsp,out,'keep',bsp_sha)
        bsp.write_bytes(b'new synthetic revision')
        with self.assertRaises(ValueError):z.stage(self.store,ident,sha,bsp,self.root/'changed','keep',bsp_sha)
        self.assertFalse((self.root/'changed').exists())

    def test_wsgi_source_header_requires_inspected_commit(self):
        spec=importlib.util.spec_from_file_location('zonepub_wsgi_test',Path(__file__).with_name('zonepub_wsgi.py'))
        env=dict(ZONEPUB_STORE=str(self.store),ZONEPUB_ACCOUNTS=str(self.main),
                 ZONEPUB_GAMES=json.dumps([str(self.game)]),ZONEPUB_SOURCE='a'*40)
        module=importlib.util.module_from_spec(spec)
        with patch.dict('os.environ',env):spec.loader.exec_module(module)
        response=module.app.test_client().post('/api/zones/challenge',json=dict(map='surf_fixture',sha='a'*64))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['X-Zonepub-Source'],'a'*40)
        env['ZONEPUB_SOURCE']='not-an-inspected-commit'
        with patch.dict('os.environ',env):
            with self.assertRaises(ValueError):spec.loader.exec_module(importlib.util.module_from_spec(spec))

    def test_duplicate_draft_is_idempotent(self):
        self.grant(); a=self.upload(self.challenge()); b=self.upload(self.challenge())
        self.assertEqual(a.status_code,200); self.assertEqual(b.status_code,200)
        self.assertEqual(a.json['draft'],b.json['draft']); self.assertEqual(len(self.drafts()),1)

    def test_teleport_destination_fields_are_checked(self):
        self.grant()
        for bad in ([1,2], [1,'2',3], 'x', [1,2,float('nan')]):
            obj=zone(); obj['tracks']['main']['zones']['segments'][0]['checkpoints'][0]['regions'][0]['teleDestPos']=bad
            raw=json.dumps(obj).encode(); self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,400)
        obj=zone(); obj['tracks']['main']['zones']['segments'][0]['checkpoints'][0]['regions'][0]['teleDestTargetname']=7
        raw=json.dumps(obj).encode(); self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,400)
        obj=zone(); r=obj['tracks']['main']['zones']['segments'][0]['checkpoints'][0]['regions'][0]
        r.update(teleDestPos=[16,16,1], teleDestYaw=90)
        raw=json.dumps(obj).encode(); self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,200)

    def test_speed_cap_is_bounded(self):
        """P841: maxVelocity sets the lobbies' cap; the engine ignores it outside 1..100000."""
        for bad in (0.5, 100001, -1, '5000', True, 1e30):
            obj=zone(); obj['maxVelocity']=bad
            self.assertRaises(ValueError, z.validate, json.dumps(obj).encode())
        for good in (0, 1, 5000, 9999.5, 100000):
            obj=zone(); obj['maxVelocity']=good
            z.validate(json.dumps(obj).encode())
        self.grant(); obj=zone(); obj['maxVelocity']=200000; raw=json.dumps(obj).encode()
        r=self.upload(self.challenge(raw),raw=raw)
        self.assertEqual((r.status_code, r.json['error']), (400, 'maxVelocity must be 0 or 1..100000'))
        self.assertFalse(self.drafts())


class Publish(Upload):
    """P815: an accepted admin upload is queued and written when its map is quiet."""
    OLD = b'{"formatVersion":1,"old":true}'
    def setUp(self):
        super().setUp()
        self.game.write_bytes(b'synthetic P815 game: ' + z.PUBLISH_MARKER)      # the P815 upload flow
        self.code = hashlib.sha256(self.game.read_bytes()).hexdigest()
        clock = z.pub.CLOCK                     # P1081: the write's and the budget's moment
        z.pub.CLOCK = lambda: self.now
        self.addCleanup(setattr, z.pub, 'CLOCK', clock)
        self.dirs = [self.root/'game_zones', self.root/'site_zones']
        for d in self.dirs: d.mkdir()
        self.dirs[0].joinpath('surf_fixture.json').write_bytes(self.OLD)
        self.maps = set()                       # heard, and nobody on the map
        self.owed, self.swept, self.stalled = set(), self.now, False
        with z.connect(self.store) as db:       # watched long enough already
            db.execute('INSERT INTO meta VALUES(?,?)', ('watch_since', self.now - 1000))
            db.execute('INSERT INTO meta VALUES(?,?)', ('watch_last', self.now - 30))
        self.app = z.create_app(self.store,self.main,[self.game],clock=lambda:self.now,verify=ed25519,
                                publish_dirs=self.dirs,maps_fn=self.lobbies)
        self.c = Coded(self.app.test_client())
    def files(self):
        return [(d/'surf_fixture.json').read_bytes() if (d/'surf_fixture.json').exists() else None for d in self.dirs]
    def rows(self, kind=None):
        with z.connect(self.store) as db:
            q='SELECT * FROM publications'+(' WHERE kind=?' if kind else '')+' ORDER BY id'
            return db.execute(q,(kind,) if kind else ()).fetchall()
    def lobbies(self):
        if self.maps is None: return None
        ports = getattr(self, 'ports', {})
        return {'maps': self.maps, 'owed': self.owed, 'swept': self.swept, 'posted': getattr(self, 'posted', {}),
                'ports': ports, 'stamps': list(getattr(self, 'stamps', [])),
                'unresolved': dict(getattr(self, 'unresolved', {}))}
    def apply(self): return self.app.config['ZONEPUB_APPLY'](self.now)
    def wait(self, seconds):
        # The service hears the lobbies every 60 s; a longer gap restarts the watch.
        done = {}
        for _ in range(seconds // 60):
            self.now += 60
            if not self.stalled:
                self.swept = self.now      # the sweeper's own log, and its completion line
                self.stamps = getattr(self, 'stamps', []) + ['2026-01-01T%08d' % self.now]
            done.update(self.apply())
        return done
    def rollback(self, dirs=None, **kw):
        return z.pub.rollback(z.connect,self.store,dirs or self.dirs,'surf_fixture',z.valid_name,self.lobbies,
                              self.now,z.MAX_ZONE_BYTES,**kw)
    def raw2(self, h):
        obj=zone(); obj['tracks']['main']['zones']['end']['regions'][0]['height']=h
        return (json.dumps(obj)+'\n').encode()
    def test_the_marker_is_the_client_source_s(self):
        # Reword that note in cl_zonepublish.qc and every publish is refused: keep the two together.
        src = (Path(__file__).resolve().parent.parent / 'src/client/cl_zonepublish.qc').read_bytes()
        self.assertEqual(src.count(z.PUBLISH_MARKER), 1)
    def test_a_client_without_the_p815_flow_cannot_publish(self):
        self.grant(); self.game.write_bytes(b'the P729 draft client')
        self.code = hashlib.sha256(self.game.read_bytes()).hexdigest()
        self.assertEqual(self.upload(self.challenge()).status_code,403)
        self.assertEqual(self.files(),[self.OLD,None]); self.assertFalse(self.rows())
    def test_quiet_map_is_live_at_once_and_rollback_restores(self):
        self.grant(); r=self.upload(self.challenge())
        self.assertEqual(r.status_code,200,r.data); self.assertEqual(r.json['published'],1)
        self.assertEqual(self.files(),[self.raw,self.raw])
        if hasattr(os,'getuid'):
            for d in self.dirs: self.assertEqual((d/'surf_fixture.json').stat().st_mode & 0o777, 0o644)
        self.assertEqual([x.name for d in self.dirs for x in d.iterdir()],['surf_fixture.json']*2)
        row=self.rows('live')[0]; self.assertEqual((row['steamid'],row['sha']),(SID,hashlib.sha256(self.raw).hexdigest()))
        self.rollback()
        self.assertEqual(self.files(),[self.OLD,None])
        with self.assertRaises(ValueError): self.rollback()     # nothing live now
    def test_a_lobby_on_the_map_holds_it_until_quiet(self):
        self.grant(); self.maps={'surf_fixture','surf_other'}
        r=self.upload(self.challenge()); self.assertEqual(r.json['published'],0)
        self.assertIn('10 minutes',r.json['note']); self.assertEqual(self.files(),[self.OLD,None])
        self.maps={'surf_other'}; self.assertEqual(self.wait(540),{})
        self.assertEqual(self.files(),[self.OLD,None])
        self.assertEqual(self.wait(60),{'surf_fixture':'live'})
        self.assertEqual(self.files(),[self.raw,self.raw])
    def test_a_verdict_owed_or_a_stalled_sweeper_holds_it(self):
        self.grant(); self.owed={'surf_fixture'}
        self.assertEqual(self.upload(self.challenge()).json['published'],0)
        self.assertEqual(self.wait(700),{})
        self.owed=set(); self.assertEqual(self.wait(60),{'surf_fixture':'live'})
    def test_a_posted_stage_counts_as_a_sighting(self):
        self.grant(); self.posted={'surf_fixture': self.now}
        self.assertEqual(self.upload(self.challenge()).json['published'],0)
        self.assertEqual(self.wait(540),{}); self.assertEqual(self.wait(60),{'surf_fixture':'live'})
    def test_a_stalled_sweeper_holds_a_map_that_was_on_a_lobby(self):
        self.grant(); self.maps={'surf_fixture'}; self.upload(self.challenge())
        self.maps=set(); self.stalled=True; self.assertEqual(self.wait(1200),{})
        self.stalled=False; self.assertEqual(self.wait(60),{'surf_fixture':'live'})
    def test_rollback_supersedes_a_pending_publish_and_repairs_partial(self):
        self.grant(); self.upload(self.challenge())
        b=self.raw2(55); self.maps={'surf_fixture'}; self.upload(self.challenge(b),raw=b)   # waits
        self.maps=set(); self.wait(660)          # it goes live: the newest state
        b2=self.raw2(56); self.maps={'surf_fixture'}; self.upload(self.challenge(b2),raw=b2)
        self.maps=set(); self.wait(540)
        self.rollback(anyway=True)               # an operator's, while the newer upload waits
        self.assertEqual(self.files(),[self.raw,self.raw])
        self.assertEqual(self.wait(600),{})      # the pending publish was superseded
        self.assertEqual(self.files(),[self.raw,self.raw])
    def test_lobby_state_reads_surfd_like_mapwatch(self):
        db=self.root/'surfd.db'; c=sqlite3.connect(db)
        c.executescript("CREATE TABLE lobbies(node TEXT, map TEXT, last_seen INTEGER, addr TEXT);"
                        "CREATE TABLE assignments(node TEXT, map TEXT, asked_at INTEGER);"
                        "CREATE TABLE runs(map TEXT, leg INTEGER, submitted INTEGER);"
                        "CREATE TABLE replays(id INTEGER PRIMARY KEY, map TEXT, kind TEXT, checked INTEGER, submitted INTEGER, recheck_at INTEGER);"
                        "CREATE TABLE verdicts(replay_id INTEGER, verdict TEXT, at INTEGER);")
        log=self.root/'sweep.log'; log.write_text('x\n2026-10-28T05:40:05 sweep: nothing to verify\nevidence y\n'
                                                   '2026-10-28T05:45:04 sweep: nothing to verify\n')
        # P1081: surfd writes our lobbies as SURFD_PUBLIC_HOST:port (surfd.py PUBLIC_HOST); the
        # lobby cfgs name the ports; only a literal address of this machine counts otherwise.
        ours = {27510, 27520, 27530, 27540}
        state=lambda: z.pub.lobby_state(db,log,self.now,local=lambda h: h == '127.0.0.1',
                                        ours=ours, public='play.proto.bar')
        self.assertIsNone(state())                      # no lobby heard yet
        c.executemany('INSERT INTO lobbies VALUES(?,?,?,?)',[('1','Surf_A',self.now-5,'play.proto.bar:27510'),
                                                              ('2','surf_b',self.now-20,'127.0.0.1:27520'),
                                                              ('3','surf_b',self.now-2,'bad'),
                                                              ('4','surf_b',self.now-2,'203.0.113.9:27530'),   # elsewhere
                                                              ('5','surf_b',self.now-2,'play.proto.bar:28000'),
                                                              ('6','surf_b',self.now-2,'evil.example:27540')]); c.commit()
        st=state(); self.assertEqual(st['maps'],{'surf_a','surf_b'}); self.assertEqual(st['owed'],set())
        self.assertEqual(st['ports'],{'surf_a':[27510],'surf_b':[27520]})
        self.assertEqual(st['unresolved'],{'surf_b':4})   # bad, elsewhere, a port not ours, a name not ours
        self.assertEqual(st['stamps'],['2026-10-28T05:40:05','2026-10-28T05:45:04'])
        c.executemany('INSERT INTO replays VALUES(?,?,?,?,?,?)',[(1,'surf_a','run',0,1,0),(2,'surf_b','momentum',0,1,0),(3,'surf_c','evidence',1,1,0),(4,'surf_d','run',0,1,0)])
        c.executemany('INSERT INTO verdicts VALUES(?,?,?)',[(4,'ERROR',5)]*3); c.commit()
        self.assertEqual(state()['owed'],{'surf_a'})    # imported kinds, checked and spent rows are not owed
        c.executemany('INSERT INTO assignments VALUES(?,?,?)',[('1','surf_e',self.now-10),('4','surf_f',self.now-900)])
        c.executemany('INSERT INTO runs VALUES(?,?,?)',[('surf_g',1,self.now-50),('surf_g',0,self.now-5),('surf_h',0,self.now-5)]); c.commit()
        st=state(); self.assertIn('surf_e',st['maps']); self.assertNotIn('surf_f',st['maps'])   # a recent assignment only
        self.assertEqual(st['ports']['surf_e'],[27510])         # P1081: a lobby told to move is a target too
        self.assertEqual(st['posted'],{'surf_g':self.now-50})                                    # stages only
        c.execute("UPDATE lobbies SET last_seen=? WHERE node='2'",(self.now-31,)); c.commit()
        self.assertIsNone(state())                      # one silent lobby: nothing is known
        c.close()
    def test_unheard_lobbies_or_a_fresh_watch_write_nothing(self):
        self.grant(); self.maps=None
        self.assertEqual(self.upload(self.challenge()).json['published'],0)
        self.now+=5000; self.assertEqual(self.apply(),{})          # deaf for 5000 s: the watch restarts
        self.maps=set(); self.assertEqual(self.wait(540),{})
        self.assertEqual(self.wait(120),{'surf_fixture':'live'})
    def test_newer_upload_supersedes_a_pending_one(self):
        self.grant(); self.maps={'surf_fixture'}; b=self.raw2(99)
        self.upload(self.challenge()); self.upload(self.challenge(b),raw=b)
        self.maps=set(); self.wait(660)
        self.assertEqual(self.files(),[b,b]); self.assertEqual(len(self.rows('superseded')),1)
    def test_repeat_of_live_bytes_is_noop(self):
        self.grant(); self.upload(self.challenge())
        r=self.upload(self.challenge()); self.assertIn('already live',r.json['note'])
        self.assertEqual(len(self.rows('live')),1)
    def test_rate_limit(self):
        self.grant()
        for i in range(z.pub.RATE):
            b=self.raw2(64+i); self.assertEqual(self.upload(self.challenge(b),raw=b).status_code,200)
        b=self.raw2(999); self.assertEqual(self.upload(self.challenge(b),raw=b).status_code,429)
        self.now+=3601; self.assertEqual(self.upload(self.challenge(b),raw=b).status_code,200)
    def test_nonadmin_and_invalid_upload_write_nothing(self):
        before=self.files(); self.assertEqual(self.upload(self.challenge()).status_code,403)
        self.grant(); raw=json.dumps({'formatVersion':1,'tracks':{}}).encode()
        self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,400)
        self.assertEqual(self.files(),before); self.assertFalse(self.rows())
    def test_failed_second_write_restores_the_first(self):
        self.grant(); real=z.pub.write_file; calls=[]
        def flaky(path, body):
            calls.append(path)
            if len(calls)==2: raise OSError('disk full')
            real(path, body)
        with patch.object(z.pub,'write_file',flaky): r=self.upload(self.challenge())
        self.assertEqual(r.status_code,500)
        self.assertEqual(self.files(),[self.OLD,None]); self.assertEqual(len(self.rows('failed')),1)
    def test_failed_restore_is_partial(self):
        self.grant(); real=z.pub.write_file; calls=[]
        def flaky(path, body):
            calls.append(path)
            if len(calls)>=2: raise OSError('disk full')
            real(path, body)
        with patch.object(z.pub,'write_file',flaky): r=self.upload(self.challenge())
        self.assertEqual(r.status_code,500); self.assertEqual(len(self.rows('partial')),1)
        rid=self.rows('partial')[0]['id']
        with self.assertRaises(ValueError): self.rollback(to_id=rid)
        self.rollback(to_id=rid,anyway=True); self.assertEqual(self.files(),[self.OLD,None])
    def test_crash_while_applying_is_recovered(self):
        self.grant(); self.maps={'surf_fixture'}; self.upload(self.challenge())
        with z.connect(self.store) as db:
            prev=json.dumps([[z.pub.key(d), (self.OLD.hex() if i==0 else None)] for i,d in enumerate(self.dirs)])
            db.execute("UPDATE publications SET kind='applying', prev=? WHERE kind='pending'",(prev,))
        for d in self.dirs: (d/'surf_fixture.json').write_bytes(self.raw)    # the writes had landed
        self.apply(); self.assertEqual(len(self.rows('live')),1)
    def test_recovered_row_gives_way_to_a_newer_upload(self):
        self.grant(); self.maps={'surf_fixture'}; self.upload(self.challenge())
        with z.connect(self.store) as db:
            prev=json.dumps([[z.pub.key(d), (self.OLD.hex() if i==0 else None)] for i,d in enumerate(self.dirs)])
            db.execute("UPDATE publications SET kind='applying', prev=? WHERE kind='pending'",(prev,))
        b=self.raw2(77); self.upload(self.challenge(b),raw=b)      # files untouched: the crash came before any write
        self.maps=set(); self.wait(660)
        self.assertEqual(self.files(),[b,b]); self.assertEqual(len(self.rows('superseded')),1)
    def test_rollback_with_directories_reversed_and_by_id(self):
        self.grant(); self.upload(self.challenge())
        b=self.raw2(99); self.upload(self.challenge(b),raw=b)
        first=self.rows('live')[0]['id']
        with self.assertRaises(ValueError): self.rollback(dirs=self.dirs[:1])
        self.rollback(dirs=list(reversed(self.dirs)),to_id=first)
        self.assertEqual(self.files(),[self.OLD,None])
    def test_rollback_refuses_a_changed_file_and_a_busy_map(self):
        self.grant(); self.upload(self.challenge())
        (self.dirs[1]/'surf_fixture.json').write_bytes(b'someone else')
        with self.assertRaises(ValueError): self.rollback()
        (self.dirs[1]/'surf_fixture.json').write_bytes(self.raw)
        self.maps={'surf_fixture'}
        with self.assertRaises(ValueError): self.rollback()
        self.rollback(anyway=True); self.assertEqual(self.files(),[self.OLD,None])
    def test_symlinked_destination_is_refused(self):
        self.grant(); target=self.root/'elsewhere.json'; target.write_bytes(b'x')
        link=self.dirs[1]/'surf_fixture.json'
        try: link.symlink_to(target)
        except OSError: self.skipTest('no symlink privilege')
        self.assertEqual(self.upload(self.challenge()).status_code,500)
        self.assertEqual(target.read_bytes(),b'x'); self.assertEqual(self.files()[0],self.OLD)
    def test_validator_refuses_what_the_game_reads_differently(self):
        self.grant()
        r=self.raw.decode()
        bad=[r.replace('"height": 64','"height": -5, "height": 64',1),        # the engine reads the first
             r.replace('"points"','"p\\u006fints"',1),                         # escaped key
             r.replace('"bottom": 0','"bottom": 0, "x": 1e31',1)]              # number past 1e30
        deep=zone(); t=deep
        for _ in range(17): t['n']={}; t=t['n']
        t['n']=[1]
        bad.append(json.dumps(deep))
        many=zone(); many['tracks']['bonuses']=[many['tracks']['main']]*17; bad.append(json.dumps(many))
        gr=zone(); gr['globalRegions']={'cancel':{}}; bad.append(json.dumps(gr))
        bad.append(r.replace('"bottom": 0','"bottom": 0.' + '0'*40 + '1',1))   # a number longer than the engine reads
        for body in bad:
            raw=body.encode(); self.assertEqual(self.upload(self.challenge(raw),raw=raw).status_code,400,body[:80])
        self.assertEqual(self.files(),[self.OLD,None])


class PublishNow(Publish):
    """P1081: the admin's "reload now": warn the map's lobbies (status as the ack), write once
    two sweeps completed after the grace and nothing is owed, then changelevel each lobby still
    on it until its status shows a load after the write. Every Publish test runs here too."""
    def setUp(self):
        super().setUp()
        self.game.write_bytes(b'synthetic P1081 game: ' + z.PUBLISH_MARKER + b' ' + z.NOW_MARKER)
        self.code = hashlib.sha256(self.game.read_bytes()).hexdigest()
        self.sent, self.silent, self.stuck = [], set(), set()
        self.ports = {'surf_fixture': [27530, 27510], 'surf_other': [27520]}
        # the fake fleet: port -> (map, when it loaded)
        self.fleet = {27510: ('surf_fixture', self.now - 500), 27530: ('surf_fixture', self.now - 500),
                      27520: ('surf_other', self.now - 500)}
        self.app = z.create_app(self.store,self.main,[self.game],clock=lambda:self.now,verify=ed25519,
                                publish_dirs=self.dirs,maps_fn=self.lobbies,rcon_fn=self.rcon,
                                official_fn=lambda server: server == 'play.proto.bar:27510')
        self.c = Coded(self.app.test_client())
    def rcon(self, port, argv, reply=False):
        self.sent.append((port,) + tuple(argv))
        if port in self.silent: return ''
        if argv[0] == 'changelevel' and port not in self.stuck:
            self.fleet[port] = (argv[1], self.now + 1)          # a load takes a moment
        if argv[0] == 'status':
            m, at = self.fleet[port]
            return 'current map      : %s ^7(x)\nmap uptime       : %ds\n' % (m, max(0, self.now - at))
        return ''
    def challenge_now(self, raw=None, name='surf_fixture', server=None):
        body = dict(map=name,sha=hashlib.sha256(raw or self.raw).hexdigest())
        if server: body['server'] = server
        r = self.c.post('/api/zones/challenge',json=body)
        self.assertEqual(r.status_code,200,r.data)
        return r.json['nonce'], r.json['nonce_now']
    def words(self, verb): return [s[0] for s in self.sent if s[1] == verb]
    def row(self):
        with z.connect(self.store) as db: return db.execute('SELECT * FROM publications ORDER BY id DESC').fetchone()
    def test_now_marker_is_the_client_source_s(self):
        src = (Path(__file__).resolve().parent.parent / 'src/client/cl_zonepublish.qc').read_bytes()
        self.assertEqual(src.count(z.NOW_MARKER), 1)
    def test_reload_now_warns_then_writes_and_reloads_only_that_maps_lobbies(self):
        self.grant(); self.maps={'surf_fixture','surf_other'}
        quiet, now = self.challenge_now(); self.assertNotEqual(quiet, now); self.assertEqual(len(now), 32)
        r=self.upload(now); self.assertEqual(r.status_code,200,r.data)
        self.assertEqual((r.json['published'], r.json['now']), (0, 1)); self.assertIn('warned', r.json['note'])
        say=z.pub.notice_text('surf_fixture')
        self.assertEqual(self.sent,[(27510,'say',say),(27510,'status'),(27530,'say',say),(27530,'status')])
        self.assertEqual(self.files(),[self.OLD,None])                       # warned, not written
        self.assertEqual(self.wait(120),{})                                  # grace, then one sweep
        self.assertEqual(self.wait(60),{'surf_fixture':'live'})              # the second sweep: ready
        self.assertEqual(self.files(),[self.raw,self.raw])
        self.assertEqual(self.words('changelevel'),[27510,27530])            # surf_other's lobby: never
        self.assertEqual(self.row()['live'], self.now)                       # the write's own moment
        self.wait(60)
        row=self.row(); self.assertEqual((row['kind'],row['force'],row['todo']),('live',1,'{}'))
        self.assertIn('warn 27510:ok 27530:ok', row['reload'])
        self.assertIn('reload 27510:changelevel 27530:changelevel', row['reload'])
        self.assertIn('reload 27510:done 27530:done', row['reload'])
        self.assertEqual(self.words('changelevel'),[27510,27530])            # confirmed: not sent again
        self.maps=set(); self.wait(660); self.rollback()                     # prior bytes kept
        self.assertEqual(self.files(),[self.OLD,None])
    def test_the_write_is_stamped_after_put_not_at_the_tick(self):
        self.grant(); self.maps={'surf_fixture'}; self.upload(self.challenge_now()[1]); self.wait(120)
        late = [0]; real_put = z.pub.put
        def slow(paths, bodies, limit): real_put(paths, bodies, limit); late[0] = 9
        z.pub.CLOCK = lambda: self.now + late[0]
        with patch.object(z.pub, 'put', slow): self.wait(60)
        self.assertEqual(self.row()['live'], self.now + 9)
    def test_production_addresses_and_an_unknown_lobby_hold_it(self):
        self.grant(); self.maps={'surf_fixture'}; self.unresolved={'surf_fixture': 1}
        self.upload(self.challenge_now()[1])
        self.assertEqual(self.wait(600),{}); self.assertEqual(self.sent,[])  # nobody told, nothing written
        self.assertIn('not ours by address and port', self.row()['hold'])
        self.assertEqual(self.files(),[self.OLD,None])
        self.unresolved={}; self.wait(60); self.assertEqual(self.words('say'),[27510,27530])
        self.assertEqual(self.wait(180),{'surf_fixture':'live'})
    def test_lobbies_on_the_map_with_no_port_of_ours_never_count_as_told(self):
        self.grant(); self.maps={'surf_fixture'}; self.ports={}                # on it, none resolved
        self.upload(self.challenge_now()[1]); self.assertEqual(self.wait(900),{})
        self.assertIsNone(self.row()['notice']); self.assertEqual(self.files(),[self.OLD,None])
    def test_an_unanswered_warning_is_retried_and_holds_the_write(self):
        self.grant(); self.maps={'surf_fixture'}; self.silent={27530}
        self.upload(self.challenge_now()[1])
        self.assertEqual(self.wait(600),{}); self.assertEqual(self.files(),[self.OLD,None])
        self.assertIsNone(self.row()['notice']); self.assertIn('27530', self.row()['hold'])
        self.assertEqual(self.words('changelevel'),[])
        self.silent=set(); self.wait(60); self.assertIsNotNone(self.row()['notice'])
        self.assertEqual(self.wait(180),{'surf_fixture':'live'})
    def test_a_warning_nobody_answers_expires_with_nothing_installed(self):
        self.grant(); self.maps={'surf_fixture'}; self.silent={27510,27530}
        self.upload(self.challenge_now()[1]); self.wait(z.pub.WARN_EXPIRE + 120)
        row=self.row(); self.assertEqual(row['kind'],'expired'); self.assertIn('nothing installed', row['reload'])
        self.silent=set(); self.wait(600)
        self.assertEqual(self.files(),[self.OLD,None]); self.assertEqual(self.words('changelevel'),[])
    def test_reload_now_never_passes_an_owed_verdict(self):
        self.grant(); self.maps={'surf_fixture'}; self.owed={'surf_fixture'}
        self.upload(self.challenge_now()[1])
        self.assertEqual(self.wait(1800),{}); self.assertEqual(self.files(),[self.OLD,None])
        self.assertEqual(self.words('changelevel'),[]); self.assertIn('owed', self.row()['hold'])
        self.owed=set(); self.assertEqual(self.wait(60),{})                   # a stale warning is given again
        self.assertEqual(len(self.words('say')),4)
        self.assertEqual(self.wait(60),{'surf_fixture':'live'})               # a minute after the new one
    def test_a_sweep_must_start_after_the_grace(self):
        self.grant(); self.maps={'surf_fixture'}; self.stalled=True
        self.upload(self.challenge_now()[1])
        self.assertEqual(self.wait(1200),{})                                  # no sweep completes
        self.stalled=False; self.assertEqual(self.wait(60),{})               # one: it may have started earlier
        n=len(self.words('say'))
        self.assertEqual(self.wait(60),{})                                    # two: ready, but warned 20 min ago:
        self.assertEqual(len(self.words('say')),n+2)                          #   warned again first
        self.assertEqual(self.wait(60),{'surf_fixture':'live'})
    def test_a_lobby_moving_onto_the_map_is_warned_before_the_write(self):
        self.grant(); self.maps={'surf_fixture'}; self.ports={'surf_fixture':[27510]}
        self.upload(self.challenge_now()[1]); self.wait(120)
        self.ports={'surf_fixture':[27510,27530]}                             # moved on after the warning
        self.assertEqual(self.wait(60),{})                                    # ready, but 27530 was never told
        self.assertEqual(self.words('say'),[27510,27530]); self.assertEqual(self.words('changelevel'),[])
        self.assertEqual(self.wait(60),{'surf_fixture':'live'})               # a minute after its warning
        self.assertEqual(self.words('changelevel'),[27510,27530])
    def test_a_lobby_that_does_not_reload_ends_live_partial_and_can_be_rearmed(self):
        self.grant(); self.maps={'surf_fixture'}; self.stuck={27530}
        self.upload(self.challenge_now()[1]); self.wait(180)                  # written, round 1
        n = len(self.sent)
        for _ in range(4): self.apply()                                       # every upload calls apply() too:
        self.assertEqual(len(self.sent), n)                                   #   no extra round in one tick
        self.wait(60 * z.pub.RELOAD_TRIES)
        self.assertEqual(self.words('changelevel').count(27530), z.pub.RELOAD_TRIES)
        self.assertEqual(self.words('changelevel').count(27510), 1)
        row=self.row(); self.assertEqual((row['kind'],row['todo'],row['partial']),('live-partial','{}','[27530]'))
        self.assertIn('27530:GAVE UP', row['reload'])
        self.stuck=set(); z.pub.rearm(z.connect, self.store, 'surf_fixture'); self.wait(120)
        row=self.row(); self.assertEqual((row['kind'],row['todo']),('live','{}'))
        self.assertEqual(self.words('changelevel').count(27530), z.pub.RELOAD_TRIES + 1)
        self.maps=set(); self.wait(660); self.rollback()                      # live-partial rolls back too
        self.assertEqual(self.files(),[self.OLD,None])
    def test_silent_rounds_spend_no_tries_and_end_at_the_expiry(self):
        self.grant(); self.maps={'surf_fixture'}
        self.upload(self.challenge_now()[1]); self.wait(120)
        self.silent={27530}; self.wait(60)                                    # written; 27530 stops answering
        self.wait(600); self.assertEqual(self.row()['kind'],'live')           # silent: still waiting, no try spent
        self.assertNotIn(27530, self.words('changelevel'))
        self.wait(z.pub.RELOAD_EXPIRE)
        row=self.row(); self.assertEqual((row['kind'],row['partial']),('live-partial','[27530]'))
    def test_a_reload_lost_after_the_write_is_started_again(self):
        self.grant(); self.maps={'surf_fixture'}; self.stuck={27510,27530}
        self.upload(self.challenge_now()[1]); self.wait(180)                  # written; the reload went nowhere
        with z.connect(self.store) as db: db.execute("UPDATE publications SET todo=NULL, round=NULL")   # as a crash
        self.stuck=set(); n=len(self.words('changelevel')); self.wait(60)
        self.assertEqual(self.words('changelevel')[n:],[27510,27530])
        self.wait(60); self.assertEqual(self.row()['todo'],'{}')
    def test_a_crash_while_writing_recovers_and_reloads(self):
        self.grant(); self.maps={'surf_fixture'}
        self.upload(self.challenge_now()[1]); self.wait(120)
        real_put = z.pub.put
        def crash(paths, bodies, limit): real_put(paths, bodies, limit); raise SystemExit('power cut')
        with patch.object(z.pub, 'put', crash):
            with self.assertRaises(SystemExit): self.wait(60)
        self.assertEqual(self.row()['kind'],'applying'); self.assertEqual(self.words('changelevel'),[])
        self.now += 10 ** 5                                                   # recovered a day later: still reloads
        self.apply()
        self.assertEqual(self.row()['kind'],'live'); self.assertEqual(self.words('changelevel'),[27510,27530])
    def test_reload_now_of_live_bytes_reloads_only_lobbies_that_loaded_before_them(self):
        self.grant(); self.ports={}; self.upload(self.challenge())            # quiet: live at once
        written=self.now
        self.ports={'surf_fixture':[27510,27530]}; self.maps={'surf_fixture'}
        self.fleet[27510]=('surf_fixture', written + 30)                      # loaded these zones
        self.fleet[27530]=('surf_fixture', written - 30)                      # loaded before them
        self.now += 60; self.upload(self.challenge_now()[1]); self.wait(240)
        self.assertEqual(self.row()['kind'],'noop'); self.assertEqual(self.words('changelevel'),[27530])
    def test_reload_now_with_nobody_on_the_map_reloads_nothing(self):
        self.grant(); self.ports={'surf_other':[27520]}; self.upload(self.challenge_now()[1])
        self.assertEqual(self.wait(180),{'surf_fixture':'live'}); self.assertEqual(self.words('changelevel'),[])
        self.assertEqual(self.words('say'),[]); self.assertIn('warn nobody on it', self.row()['reload'])
    def test_quiet_nonce_never_forces(self):
        self.grant(); self.maps={'surf_fixture'}
        self.assertEqual(self.upload(self.challenge_now()[0]).json['published'],0)
        self.assertEqual(self.wait(1200),{}); self.assertEqual(self.sent,[])
        self.assertEqual(self.rows('pending')[0]['force'],0)
    def test_reload_now_needs_the_p1081_client(self):
        self.grant(); self.game.write_bytes(b'synthetic P815 game: ' + z.PUBLISH_MARKER)
        self.code = hashlib.sha256(self.game.read_bytes()).hexdigest()
        quiet, now = self.challenge_now()
        self.assertEqual(self.upload(now).status_code,403); self.assertFalse(self.rows())
        self.assertEqual(self.upload(quiet).status_code,200)                  # its own path still works
    def test_one_challenge_is_one_publish_whichever_nonce(self):
        self.grant(); self.maps={'surf_fixture'}; quiet, now = self.challenge_now()
        self.assertEqual(self.upload(now).status_code,200); self.assertEqual(self.upload(quiet).status_code,409)
        self.assertEqual(len(self.rows()),1)
    def test_reload_now_refuses_a_nonadmin_and_changed_bytes(self):
        self.maps={'surf_fixture'}
        self.assertEqual(self.upload(self.challenge_now()[1]).status_code,403)        # no role
        self.grant(); b=self.raw2(77)
        self.assertEqual(self.upload(self.challenge_now()[1],raw=b).status_code,409)  # nonce names other bytes
        self.wait(600); self.assertEqual(self.sent,[]); self.assertFalse(self.rows())
        self.assertEqual(self.files(),[self.OLD,None])
    def test_off_host_publishing_only_from_our_lobbies(self):
        self.grant()
        self.challenge_now(server='play.proto.bar:27510')                     # official_fn says ours
        for where in ('203.0.113.9:27510', 'unknown', 'x' * 81):
            r=self.c.post('/api/zones/challenge',json=dict(map='surf_fixture',server=where,
                                                           sha=hashlib.sha256(self.raw).hexdigest()))
            self.assertIn(r.status_code,(400,403),where)
        self.challenge_now(server='host'); self.challenge_now()                # hosted, and the P815 client
    def test_the_rate_limit_comes_before_the_lobby_check(self):
        seen=[]
        self.app = z.create_app(self.store,self.main,[self.game],clock=lambda:self.now,verify=ed25519,
                                publish_dirs=self.dirs,maps_fn=self.lobbies,rcon_fn=self.rcon,
                                official_fn=lambda server: seen.append(server) or False)
        c = Coded(self.app.test_client())
        body = dict(map='surf_fixture',server='203.0.113.9:27510',sha=hashlib.sha256(self.raw).hexdigest())
        with z.connect(self.store) as db:                                     # the service is at its limit
            for i in range(256): db.execute("INSERT INTO challenges(nonce,map,sha,peer,created) VALUES(?,?,?,?,?)",
                                            ('n%d' % i,'m','s','p%d' % (i % 64),self.now))
        r = c.post('/api/zones/challenge',json=body)
        self.assertEqual(r.status_code,429); self.assertEqual(seen,[])        # refused before any lobby check
    def test_official_is_a_lobby_port_at_our_public_name(self):
        ours={27510,27520}; names=('play.proto.bar',); resolve=lambda: {'93.184.216.34'}
        off=lambda s: z.official(s, ours, names, resolve)
        self.assertTrue(off('play.proto.bar:27510')); self.assertTrue(off('93.184.216.34:27520'))
        for bad in ('127.0.0.1:27510', '[::1]:27510', '0.0.0.0:27510', '[::]:27510',   # the client's own machine
                    '192.168.1.102:27510', '10.0.0.5:27510', '169.254.1.1:27510',      # nobody's network but its
                    '93.184.216.34:27530', 'play.proto.bar:27530',                      # not a lobby port of ours
                    '203.0.113.9:27510', '27510', 'host', 'unknown'):
            self.assertFalse(off(bad), bad)
        def deaf(): raise OSError('no DNS')
        self.assertFalse(z.official('93.184.216.34:27510', ours, names, deaf))
        # split-horizon DNS may give our name a LAN address: still nobody's lobby to a remote client
        self.assertFalse(z.official('192.168.1.102:27510', ours, names, lambda: {'192.168.1.102'}))
        with patch.object(z.socket, 'getaddrinfo', side_effect=AssertionError('looked up a client name')):
            self.assertFalse(z.official('evil.example:27510', ours, names, z.resolve_public))
    def test_notice_fits_rcon_for_any_map_name(self):
        import rcon
        for n in ('surf_a', 'surf_' + 'x' * 59):
            self.assertLessEqual(len(z.pub.notice_text(n)), 128); rcon.check_arg(z.pub.notice_text(n))
    def test_rcon_budget_is_shared_bounded_and_keeps_newer_entries(self):
        t = [5000]
        z.pub.CLOCK = lambda: t[0]
        self.assertEqual([z.pub.budget_take(self.store, 27510) for _ in range(4)], [True]*3 + [False])
        self.assertTrue(z.pub.budget_take(self.store, 27520))
        t[0] = 5031; self.assertTrue(z.pub.budget_take(self.store, 27510))
        t[0] = 6010; self.assertTrue(z.pub.budget_take(self.store, 27530))    # another process, a later moment
        t[0] = 6000                                                           # this one's moment is older
        self.assertEqual([z.pub.budget_take(self.store, 27530) for _ in range(3)], [True, True, False])
    def test_a_p815_store_is_migrated_and_old_inserts_still_work(self):
        import re
        old=self.root/'old.db'; c=sqlite3.connect(old)
        c.executescript(re.sub(r', force INTEGER.*?reload TEXT', '', z.SQL.replace(',\n nonce_now TEXT',''), flags=re.S))
        self.assertNotIn('force',{r[1] for r in c.execute('PRAGMA table_info(publications)')}); c.close()
        z.create_app(old,self.main,[self.game],publish_dirs=self.dirs,maps_fn=self.lobbies)
        c=sqlite3.connect(old)
        self.assertIn('nonce_now',{r[1] for r in c.execute('PRAGMA table_info(challenges)')})
        self.assertTrue({c for c, _ in z.pub.COLUMNS} <= {r[1] for r in c.execute('PRAGMA table_info(publications)')})
        c.execute("INSERT INTO publications(map,sha,steamid,at,kind,body) VALUES('m','s','x',1,'pending',x'00')")
        c.execute("INSERT INTO challenges(nonce,map,sha,peer,created) VALUES('n','m','s','p',1)"); c.commit(); c.close()


class RconReplies(unittest.TestCase):
    """P1081 review: rcon.py's socket is connected, so only the lobby's own address can answer."""
    def test_a_reply_from_another_local_socket_is_ignored(self):
        import socket, threading, time as _t
        import rcon
        rcon.budget_reset()
        lobby = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); lobby.bind(('127.0.0.1', 0))
        spoof = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); spoof.bind(('127.0.0.1', 0))
        self.addCleanup(lobby.close); self.addCleanup(spoof.close)
        def serve():
            _, addr = lobby.recvfrom(4096)
            spoof.sendto(b'\xff\xff\xff\xffnforged\x00', addr)               # somebody else answers first
            _t.sleep(0.05)
            lobby.sendto(b'\xff\xff\xff\xffngenuine\x00', addr)
        t = threading.Thread(target=serve); t.start()
        reply = rcon.Rcon('127.0.0.1', lobby.getsockname()[1], 'pw', timeout=1.0, collect_for=0.2).execute(['status'])
        t.join(); self.assertEqual(reply, 'genuine')


if __name__ == '__main__': unittest.main()
