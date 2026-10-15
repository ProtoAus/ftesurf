#!/usr/bin/env python3
"""Real Ed25519, account/role, nonce, bounds and preservation falsifiers."""
import hashlib
import importlib.util
import json
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
        self.c = self.app.test_client()
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
        missing=self.root/'missing.db'
        c=z.create_app(missing,self.main,[self.game]).test_client()
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


if __name__ == '__main__': unittest.main()
