#!/usr/bin/env python3
"""Per-attempt counts observations: synthetic verifier stdout + API/actual DOM."""
import importlib
import json
import logging
import os
import shutil
import subprocess
import sqlite3
import sys
import threading
import tempfile
import unittest
from unittest import mock

import admin
import test_admin as at
import test_sweep as suite


def section(path, diagnostic=None, verdict='PASS ticks 100 rows 80'):
    out = ['^5pm_recsim^7  '+path]
    if diagnostic is not None:out.append('  counts    '+diagnostic)
    out.extend(['^5ARM 1^7 synthetic control', 'VERIFY '+path+' '+verdict])
    return out


class Counts(unittest.TestCase):
    def setUp(self):
        self.first_home = len(at.HOMES)
        self.handlers = []
        self.addCleanup(self.cleanup_home)
        self.m = at.fresh(SURFD_ADMIN_HASH=admin.hash_password('test password only', n=2**10),
                          SURFD_ADMIN_SECRET='temporary-test-secret-not-a-real-secret',
                          SURFD_ADMIN_INSECURE_COOKIE='1')
        self.handlers = self.m.log.handlers[:]
        sys.modules.pop('sweep', None)
        self.sw = importlib.import_module('sweep')
        self.sw.GAME = self.m.BASE_DIR
        self.m.RUNS_DIR = os.path.join(self.m.BASE_DIR, 'ftesurf', 'data', 'runs')
        os.makedirs(self.m.RUNS_DIR, exist_ok=True)
        self.c = self.m.connect()
        self.addCleanup(self.c.close)

    def cleanup_home(self):
        logger = logging.getLogger('surfd')
        for home in at.HOMES[self.first_home:]:
            for h in set(self.handlers + logger.handlers[:]):
                if getattr(h,'baseFilename','').startswith(os.path.abspath(home)+os.sep):
                    logger.removeHandler(h);h.close()
            if os.path.exists(home):shutil.rmtree(home)
            self.assertFalse(os.path.exists(home))

    def test_sections_and_original_parser(self):
        lines = section('a', '12 record(s): what the input ring delivered is what the view read')
        lines += section('b', '^12 of 8 record(s) disagree^7, first at row 5 (read - ring 1 -2)', 'HOLD state: control')
        lines += section('c', 'none -- the client predates Patch 376')
        lines += ['VERIFY d REFUSE early control', '^5pm_recsim^7 e', 'counts truncated', 'VERIFY e HOLD control']
        got=self.sw.parse_counts(lines)
        self.assertEqual(got, {'a':{'version':1,'state':'measured','records':12,'disagree':0},
                              'b':{'version':1,'state':'measured','records':8,'disagree':2,'first_row':5},
                              'c':{'version':1,'state':'no_records','records':0},'d':None,'e':None})
        self.assertEqual(self.sw.parse(lines)['b'], ('HOLD','state: control',-1))
        self.assertEqual(self.sw.parse(lines)['a'], ('PASS','ticks 100 rows 80',100))

    def test_ambiguous_missing_and_reordered_are_unavailable(self):
        good='counts    5 record(s): what the input ring delivered is what the view read'
        for lines in ([good,'VERIFY a PASS ticks 100'],
                      ['pm_recsim a',good,'VERIFY b REFUSE early'],
                      ['pm_recsim a',good,good,'VERIFY a PASS ticks 100'],
                      ['pm_recsim a','VERIFY a PASS ticks 100',good,'VERIFY b HOLD control'],
                      ['pm_recsim a',good,'pm_recsim b','VERIFY b REFUSE early'],
                      ['pm_recsim a','counts    '+ '9'*5000 +' record(s): what the input ring delivered is what the view read','VERIFY a HOLD control'],
                      ['pm_recsim a','counts    3 of 2 record(s) disagree, first at row 0 (read - ring 1 0)','VERIFY a HOLD control']):
            self.assertTrue(all(v is None for v in self.sw.parse_counts(lines).values()), lines[:1])
        self.assertEqual(self.sw.parse_counts(['pm_recsim a',good]), {})

    def test_sweep_persists_only_matching_attempt(self):
        ids=[suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy','%07d_run.rec'%(100+i)) for i in range(4)]
        observed=[]
        def runner(map_dir,paths):
            observed.extend(paths)
            return (section(paths[0],'9 record(s): what the input ring delivered is what the view read', 'PASS ticks 662 rows 80')+
                    section(paths[1],None,'HOLD control')+['VERIFY '+paths[2]+' REFUSE early control']+
                    ['pm_recsim '+paths[3], 'counts    none -- the client predates Patch 376'])
        result=self.sw.sweep(self.c,50,runner=runner,now=9999999999)
        self.assertEqual(len(observed),4)  # positive: runner really acted
        self.assertEqual(result,{'PASS':1,'HOLD':1,'REFUSE':1,'ERROR':1})
        rows=[dict(r) for r in self.c.execute('SELECT * FROM verdicts ORDER BY replay_id')]
        self.assertEqual(json.loads(rows[0]['counts_metrics']),{'version':1,'state':'measured','records':9,'disagree':0})
        self.assertEqual([r['counts_metrics'] for r in rows[1:]],['','',''])
        self.assertEqual([(r['verdict'],r['reason'],r['ticks']) for r in rows],
                         [('PASS','ticks 662 rows 80',662),('HOLD','control',-1),('REFUSE','early control',-1),('ERROR','no VERIFY line',-1)])
        self.assertEqual([r[0] for r in self.c.execute('SELECT checked FROM replays ORDER BY id')],[1,1,1,0])

    def test_migration_no_backfill_and_authenticated_api(self):
        rid=suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy','0000100_run.rec')
        self.sw.record(self.c,rid,'PASS','ticks 100 rows 80',100,'e','p',1)
        self.c.commit()
        self.c.execute('ALTER TABLE verdicts DROP COLUMN counts_metrics');self.c.commit()
        before=dict(self.c.execute('SELECT * FROM verdicts').fetchone())
        for _ in range(2):
            self.m.verdict_metrics(self.c);self.c.commit()
            self.assertEqual(dict(self.c.execute('SELECT * FROM verdicts').fetchone()),dict(before,counts_metrics=''))
        client=self.m.app.test_client();route='/admin/api/run/%d'%rid
        self.assertEqual(client.get(route).status_code,401)
        self.assertEqual(at.login(client,'test password only').status_code,302)
        board=client.get('/api/board?map=bhop_eazy').get_json()
        snap={'version':1,'state':'measured','records':8,'disagree':2,'first_row':0}
        for raw,expected in (('',None),(json.dumps(snap),snap),('{bad',None),
                             ('{"version":1,"state":"measured","records":true,"disagree":0}',None),
                             ('{"version":1,"state":"measured","records":1,"disagree":2}',None),
                             ('{"version":2,"state":"no_records","records":0}',None)):
            self.c.execute('UPDATE verdicts SET counts_metrics=?',(raw,));self.c.commit()
            reply=client.get(route)
            self.assertEqual(reply.status_code,200)
            self.assertEqual(reply.get_json()['verdicts'][0]['counts_metrics'],expected)
            self.assertEqual(reply.get_json()['verdicts'][0]['verdict'],'PASS')
        self.assertEqual(client.get('/api/board?map=bhop_eazy').get_json(),board)
        self.c.execute('ALTER TABLE verdicts DROP COLUMN counts_metrics');self.c.commit()
        self.assertIsNone(client.get(route).get_json()['verdicts'][0]['counts_metrics'])

    def test_concurrent_additive_migration(self):
        rid=suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy','0000100_run.rec')
        self.sw.record(self.c,rid,'PASS','historic control',100,'e','p',1);self.c.commit()
        self.c.execute('ALTER TABLE verdicts DROP COLUMN counts_metrics');self.c.commit()
        before = [tuple(r) for r in self.c.execute('SELECT * FROM verdicts')]
        self.assertEqual(len(before),1)
        barrier, errors, checked = threading.Barrier(2), [], []
        m = self.m

        def run():
            c = sqlite3.connect(m.DB_PATH, timeout=10)
            try:
                class PausedCheck:
                    first = True
                    def execute(self, sql):
                        if sql.startswith('PRAGMA') and self.first:
                            rows = c.execute(sql).fetchall()
                            self.first = False
                            checked.append('counts_metrics' not in {r[1] for r in rows})
                            barrier.wait(timeout=5)
                            return rows
                        return c.execute(sql)
                m.verdict_metrics(PausedCheck());c.commit()
            except Exception as e:errors.append(e)
            finally:c.close()

        workers=[threading.Thread(target=run) for _ in range(2)]
        for w in workers:w.start()
        for w in workers:w.join(timeout=15)
        self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(checked,[True,True])  # both saw absence before either ALTER
        self.assertEqual(errors,[])
        self.assertIn('counts_metrics',{r[1] for r in self.c.execute('PRAGMA table_info(verdicts)')})
        self.assertEqual([tuple(r)[:-1] for r in self.c.execute('SELECT * FROM verdicts')],before)
        class IOFailure:
            def execute(self, sql):
                if sql.startswith('PRAGMA'):return [(0,'verdict')]
                raise sqlite3.OperationalError('synthetic disk I/O error')
        with self.assertRaisesRegex(sqlite3.OperationalError,'disk I/O'):m.verdict_metrics(IOFailure())

    def test_actual_dom(self):
        if not shutil.which('node'):self.skipTest('Node absent; DOM must be tested on Windows')
        text=open(os.path.join(os.path.dirname(__file__),'templates','admin_run.html'),encoding='utf-8').read()
        block=text[text.index('  const tb = document.querySelector("#verdicts tbody");'):text.index('  const RCPT_CLS')]
        helper=text[text.index('function renderVerdictSummary('):text.index('function renderRun(')]
        js=r'''
const j={verdicts:[JSON.parse(process.argv[2])]};
class E {constructor(tag,cls,text){this.text=String(text??'');this.children=[];}
append(...items){this.children.push(...items);} appendChild(n){this.children.push(n);}
replaceChildren(){this.children=[];} set innerHTML(v){throw Error('HTML sink');}}
const table=new E();const document={querySelector:()=>table};
const el=(t,c,s)=>new E(t,c,s),pill=(s)=>el('span','',s),fmtDate=()=> 'date';
const VERDICT_CLS={};let summary;const summarise=(id,bad)=>{summary=bad;};
'''+helper+block+r'''
const flat=n=>typeof n==='string'?n:n.text+n.children.map(flat).join('');
console.log(JSON.stringify({text:flat(tb),summary}));
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=os.path.join(tmp,'render.js');open(p,'w',encoding='utf-8').write(js)
            for snap,phrase in ((None,'counts unavailable'),
                                ({'version':1,'state':'no_records','records':0},'agreement unmeasured'),
                                ({'version':1,'state':'measured','records':8,'disagree':0},'8 records, 0 disagree'),
                                ({'version':1,'state':'measured','records':8,'disagree':2,'first_row':0},'first at row 0')):
                v=dict(id=1,verdict='PASS',current=True,engine='e',progs='p',at=1,ticks=100,
                       reason='<img> & <script>literal</script>',counts_metrics=snap)
                r=subprocess.run(['node',p,json.dumps(v)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
                rendered=json.loads(r.stdout)
                self.assertIn(phrase,rendered['text']);self.assertIn(v['reason'],rendered['text'])
                self.assertFalse(rendered['summary'])


class StartupCleanup(unittest.TestCase):
    def test_initial_import_failure_cleans_owned_home(self):
        first=len(at.HOMES)
        case=Counts('test_sections_and_original_parser')
        real=at.importlib.import_module
        def fail(name,*args,**kw):
            if name=='surfd':raise RuntimeError('synthetic initial import failure')
            return real(name,*args,**kw)
        try:
            with mock.patch.object(at.importlib,'import_module',side_effect=fail):
                with self.assertRaisesRegex(RuntimeError,'initial import'):case.setUp()
        finally:case.doCleanups()
        self.assertTrue(at.HOMES[first:])
        self.assertTrue(all(not os.path.exists(h) for h in at.HOMES[first:]))


if __name__=='__main__':unittest.main()
