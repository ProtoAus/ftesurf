#!/usr/bin/env python3
"""Stored similarity: authenticated bounded reads and actual text-only DOM."""
import importlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import unittest

import admin
import test_admin as at
import test_sweep as suite


class Similarity(unittest.TestCase):
    def setUp(self):
        self.first_home=len(at.HOMES);self.handlers=[];self.addCleanup(self.cleanup_home)
        self.m=at.fresh(SURFD_ADMIN_HASH=admin.hash_password('test password only',n=2**10),
                        SURFD_ADMIN_SECRET='temporary-test-secret-not-a-real-secret',
                        SURFD_ADMIN_INSECURE_COOKIE='1')
        self.handlers=self.m.log.handlers[:]
        self.a=importlib.import_module('admin');self.c=self.m.connect();self.addCleanup(self.c.close)
        self.rid=suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy','0000100_run.rec')
        self.client=self.m.app.test_client();self.route='/admin/api/run/%d'%self.rid
        self.assertEqual(at.login(self.client,'test password only').status_code,302)

    def cleanup_home(self):
        logger=logging.getLogger('surfd')
        for home in at.HOMES[self.first_home:]:
            for h in set(self.handlers+logger.handlers[:]):
                if getattr(h,'baseFilename','').startswith(os.path.abspath(home)+os.sep):logger.removeHandler(h);h.close()
            if os.path.exists(home):shutil.rmtree(home)
            self.assertFalse(os.path.exists(home))

    def pair(self,peer,identity='same',verdict='compared',at_time=10,compared=80,reason=''):
        wa='synthetic-owner';wb=wa if identity=='same' else 'synthetic-other' if identity=='cross' else ''
        self.c.execute("INSERT INTO sims(a_id,b_id,map,track,leg,who_a,who_b,same_who,verdict,reason,"
                       "match,cover,prefix,offset,compared,moves_a,moves_b,tick_a,tick_b,at)"
                       " VALUES(?,?,'bhop_eazy',0,0,?,?,?,?,?,0.75,0.2,16,-2,?,80,90,100,125,?)",
                       (self.rid,peer,wa,wb,int(identity=='same'),verdict,reason,compared,at_time))
        self.c.commit()

    def detail(self,rid=None):
        reply=self.client.get('/admin/api/run/%d'%(rid or self.rid))
        self.assertEqual(reply.status_code,200)
        return reply.get_json()

    def test_authenticated_identity_split_both_endpoints_no_mutation(self):
        peers=[suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy','%07d_run.rec'%(i+101)) for i in range(4)]
        for peer,identity,verdict in zip(peers,['same','cross','unknown','same'],['compared']*3+['skip']):
            self.pair(peer,identity,verdict,reason='<img> & <script>literal</script>' if verdict=='skip' else '')
        anon=self.m.app.test_client()
        self.assertEqual(anon.get(self.route).status_code,401)
        self.assertEqual(anon.get('/admin/run/%d'%self.rid).status_code,302)
        self.assertEqual(self.client.get('/admin/run/%d'%self.rid).status_code,200)
        board=anon.get('/api/board?map=bhop_eazy').get_json()
        tables=('sims','verdicts','reviews','replays','runs')
        before={t:[tuple(r) for r in self.c.execute('SELECT * FROM '+t)] for t in tables}
        j=self.detail();s=j['similarity']
        self.assertTrue(s['available']);self.assertFalse(s['source_binding']);self.assertEqual(len(s['pairs']),4)
        self.assertEqual({r['identity'] for r in s['pairs']},{'same','cross','unknown'})
        for p in s['pairs']:
            self.assertNotIn('current',p);self.assertNotIn('who_a',p);self.assertNotIn('who_b',p)
            if p['verdict']=='skip':self.assertIsNone(p['metrics'])
            else:self.assertEqual((p['metrics']['compared'],p['metrics']['moves_a'],p['metrics']['moves_b']), (80,80,90))
        self.assertNotIn('synthetic-owner',json.dumps(s));self.assertNotIn('synthetic-other',json.dumps(s))
        self.assertEqual(self.detail(peers[0])['similarity']['pairs'][0]['a_id'],self.rid)
        self.assertEqual(anon.get('/api/board?map=bhop_eazy').get_json(),board)
        self.assertNotIn('similarity',json.dumps(board))
        self.assertEqual({t:[tuple(r) for r in self.c.execute('SELECT * FROM '+t)] for t in tables},before)
        self.assertNotIn('sims',self.m.VER_SQL)

    def test_bounded_order(self):
        for i in range(30):self.pair(100+i,at_time=i//2)
        rows=self.detail()['similarity']
        self.assertTrue(rows['more']);self.assertEqual(len(rows['pairs']),25);self.assertEqual(rows['limit'],25)
        order=[(r['at'],r['id']) for r in rows['pairs']]
        self.assertEqual(order,sorted(order,reverse=True))

    def test_empty_missing_and_unmeasured_are_not_zero_scores(self):
        s=self.detail()['similarity'];self.assertTrue(s['available']);self.assertEqual(s['pairs'],[])
        self.pair(100,verdict='skip',compared=0)
        self.pair(101,compared=0)
        self.c.execute('UPDATE sims SET match=? WHERE b_id=100',(float('inf'),));self.c.commit()
        self.assertTrue(all(r['metrics'] is None for r in self.detail()['similarity']['pairs']))
        self.c.execute('DROP TABLE sims');self.c.commit()
        s=self.detail()['similarity'];self.assertFalse(s['available']);self.assertEqual(s['pairs'],[])
        self.assertIsNone(self.c.execute("SELECT 1 FROM sqlite_master WHERE name='sims'").fetchone())

    def test_real_collector_skip_prose_is_projected_without_history_change(self):
        # Synthetic marker filenames, never actual player identifiers.
        leaves=['0000100_unit-11111111_run.rec','0000101_other-22222222_run.rec']
        self.c.execute('UPDATE replays SET leaf=? WHERE id=?',(leaves[0],self.rid));self.c.commit()
        peer=suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy',leaves[1])
        rows=['FTESURF-REC 9','map bhop_eazy','track 0','leg 0','tickrate 100','begin']
        rows += ['in %d %d 0 100 0 0 0 0 0 1'%(i,i) for i in range(9)]
        rows += ['end 9']
        for leaf in leaves:
            p=os.path.join(self.m.RUNS_DIR,'bhop_eazy','main',leaf)
            with open(p,'w',encoding='utf-8') as f:f.write('\n'.join(rows)+'\n')
        import simcheck
        source=self.c.execute('SELECT * FROM replays WHERE id=?',(self.rid,)).fetchone()
        tools=os.path.join(os.path.dirname(os.path.dirname(__file__)),'tools')
        stored,skipped,notable=simcheck.compare_run(self.m,self.c,source,now=50,tools_dir=tools)
        self.assertEqual((stored,skipped,notable),(1,1,0))  # collector actually acted
        before=[tuple(r) for r in self.c.execute('SELECT * FROM sims')]
        self.assertIn(leaves[0],self.c.execute('SELECT reason FROM sims').fetchone()[0])
        value=self.detail()['similarity'];encoded=json.dumps(value)
        for protected in (*leaves,'11111111','22222222','unit-','other-'):
            self.assertNotIn(protected,encoded)
        self.assertEqual(value['pairs'][0]['reason'],'too short to compare (9 moves; minimum 50)')
        self.assertIsNone(value['pairs'][0]['metrics'])
        self.assertEqual([tuple(r) for r in self.c.execute('SELECT * FROM sims')],before)
        self.assertEqual(self.a.similarity_reason('skip','private/path: unknown detail'),'unjudgeable (legacy detail withheld)')
        self.assertEqual(self.a.similarity_reason('skip','private.rec has no `in` rows'),'no sample rows')
        self.assertEqual(self.a.similarity_reason('skip','peer unresolved: private path'),'peer unresolved')
        if shutil.which('node'):
            rendered=self.render_dom(value)
            for protected in (*leaves,'11111111','22222222','unit-','other-'):
                self.assertNotIn(protected,rendered['text'])
            self.assertIn('too short to compare (9 moves; minimum 50)',rendered['text'])

    def render_dom(self,value):
        if not shutil.which('node'):self.skipTest('Node absent; DOM tested on Windows')
        text=open(os.path.join(os.path.dirname(__file__),'templates','admin_run.html'),encoding='utf-8').read()
        block=text[text.index('function renderSimilarity(value) {'):text.index('function renderKey(j) {')]
        js=r'''
class E {constructor(tag,cls,text){this.text=String(text??'');this.children=[];this.tag=tag;}
append(...nodes){this.children.push(...nodes);} replaceChildren(){this.children=[];}
set innerHTML(v){throw Error('HTML sink');}}
const box=new E('div');const document={getElementById:()=>box};
const el=(t,c,s)=>new E(t,c,s),fmtDate=n=>'date '+n;
'''+block+r'''
renderSimilarity(JSON.parse(process.argv[2]));
const flat=n=>typeof n==='string'?n:n.text+n.children.map(flat).join('');
const links=n=>typeof n==='string'?[]:[...(n.tag==='a'?[n.href]:[]),...n.children.flatMap(links)];
console.log(JSON.stringify({text:flat(box),links:links(box)}));
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=os.path.join(tmp,'render.js');open(p,'w',encoding='utf-8').write(js)
            r=subprocess.run(['node',p,json.dumps(value)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            return json.loads(r.stdout)

    def test_actual_dom(self):
        if not shutil.which('node'):self.skipTest('Node absent; DOM tested on Windows')
        self.pair(100,'unknown','skip',reason='<img> & <script>literal</script>')
        self.pair(101,'cross','compared')
        s=self.detail()['similarity']
        self.assertNotIn('<img>',json.dumps(s))  # legacy API prose is withheld
        # Challenge the actual text sink separately from the safe API projection.
        for pair in s['pairs']:
            if pair['verdict']=='skip':pair['reason']='<img> & <script>literal</script>'
        for value,phrase in ((None,'stored similarity unavailable'),
                             ({'available':True,'pairs':[]},'no stored pairs'),
                             (s,'rows compared80')):
            out=self.render_dom(value)
            self.assertIn(phrase,out['text'])
            if value==s:
                self.assertIn('identity unknown',out['text']);self.assertIn('cross identity',out['text'])
                self.assertIn('<img> & <script>literal</script>',out['text'])
                self.assertIn('measurement unavailable',out['text'])
                self.assertIn('/admin/run/100',out['links']);self.assertIn('/admin/run/101',out['links'])
                self.assertIn('alignment offset (rows)-2',out['text'])


if __name__=='__main__':unittest.main()
