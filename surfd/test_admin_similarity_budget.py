#!/usr/bin/env python3
"""Owned panel SQL budget: real interruption, recovery and unchanged history."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

import simcheck
from test_admin_metric_bounds import ObservationFixture


class SimilarityBudget(ObservationFixture):
    def prepare(self):
        self.pair(50000, compared=80)
        self.c.executemany("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at)"
                           " VALUES(?,?,'bhop_eazy',0,0,'skip',1)",
                           ((self.rid, 20000 + i) for i in range(10000)))
        self.c.commit()
        return [tuple(r) for r in self.c.execute('SELECT * FROM sims')]

    def test_actual_api_interrupts_recovers_and_clears_owned_handler(self):
        before = self.prepare()
        traced, callbacks, slots, after = [], [], [], []
        connect = sqlite3.connect

        class Connection(sqlite3.Connection):
            def set_progress_handler(self, handler, interval):
                slots.append((handler is not None, interval))
                if handler is not None:
                    def tick():
                        value = handler()
                        callbacks.append(value)
                        return value
                    return super().set_progress_handler(tick, interval)
                return super().set_progress_handler(None, interval)

            def close(self):
                # Actual SQL on the still-open owned handle proves callback teardown.
                after.append(self.execute('SELECT SUM(id) FROM sims').fetchone()[0])
                super().close()

        def tracked(*a, **kw):
            conn = connect(*a, **dict(kw, factory=Connection))
            conn.set_trace_callback(traced.append)
            return conn

        with mock.patch.object(self.a, 'SIM_SQL_STEPS', 3000, create=True), \
                mock.patch.object(sqlite3, 'connect', side_effect=tracked):
            limited = self.detail()
        s = limited['similarity']
        self.assertTrue(any('FROM sims WHERE a_id=' in sql for sql in traced), traced)
        self.assertIn(1, callbacks)  # real SQLite VM interruption, not a mocked exception
        self.assertEqual(slots[-1], (False, 0))
        self.assertEqual(len(after), 1)
        self.assertEqual(s['state'], 'read_limit')
        self.assertFalse(s['available'])
        self.assertEqual(s['pairs'], [])
        self.assertFalse(s['more'])
        self.assertEqual(limited['run']['id'], self.rid)
        self.assertIn('verdicts', limited)
        recovered = self.detail()['similarity']
        self.assertEqual(recovered['state'], 'ok')
        self.assertTrue(recovered['available'])
        self.assertEqual(recovered['pairs'][0]['metrics']['compared'], 80)
        self.assertEqual([tuple(r) for r in self.c.execute('SELECT * FROM sims')], before)
        self.assertEqual(self.m.app.test_client().get(self.route).status_code, 401)

    def test_borrowed_callback_stays_installed_and_owner_opt_in_acts(self):
        before = self.prepare()
        calls = []
        self.c.set_progress_handler(lambda: calls.append(1) or 0, 1)
        try:
            value = self.a.similarity_for(self.c, self.rid)
            self.assertEqual(value['pairs'][0]['metrics']['compared'], 80)
            count = len(calls)
            self.c.execute('SELECT SUM(id) FROM sims').fetchone()
            self.assertGreater(len(calls), count)
        finally:
            self.c.set_progress_handler(None, 0)
        limited = self.a.similarity_for(self.c, self.rid, own_read_budget=True, max_sql_steps=1)
        self.assertEqual(limited['state'], 'read_limit')
        self.assertEqual(limited['pairs'], [])
        self.assertEqual([tuple(r) for r in self.c.execute('SELECT * FROM sims')], before)
        self.assertEqual(self.a.similarity_for(self.c, self.rid, own_read_budget=True)['pairs'][0]['metrics']['compared'], 80)

    def test_missing_panel_and_storage_errors_do_not_masquerade_as_limits(self):
        self.c.execute('DROP TABLE sims');self.c.commit()
        s = self.detail()['similarity']
        self.assertEqual(s['state'], 'missing')
        self.assertFalse(s['available'])
        self.assertEqual(s['pairs'], [])
        simcheck.ensure_schema(self.c)
        with mock.patch.object(simcheck.ReadBudget, 'rows', side_effect=sqlite3.OperationalError('synthetic I/O control')):
            self.assertEqual(self.client.get(self.route).status_code, 500)

    def render_dom(self, value):
        if not shutil.which('node'):
            self.skipTest('Node absent; actual DOM must be tested on Windows')
        text = Path(self.a.__file__).with_name('templates').joinpath('admin_run.html').read_text(encoding='utf-8')
        block = text[text.index('function renderSimilarity(value) {'):text.index('function renderKey(j) {')]
        js = r'''
class E {constructor(tag, cls, text){this.text=String(text??'');this.children=[];}
append(...nodes){this.children.push(...nodes);} replaceChildren(){this.children=[];}
set innerHTML(v){throw Error('HTML sink');}}
const box=new E();const document={getElementById:()=>box};const el=(t,c,s)=>new E(t,c,s);
''' + block + r'''
renderSimilarity(JSON.parse(process.argv[2]));
const flat=n=>typeof n==='string'?n:n.text+n.children.map(flat).join('');
console.log(JSON.stringify({text:flat(box)}));
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'render.js'
            path.write_text(js, encoding='utf-8')
            result = subprocess.run(['node', str(path), json.dumps(value)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_actual_dom_distinguishes_limited_from_missing(self):
        value = {'available': False, 'state': 'read_limit', 'pairs': []}
        self.assertIn('SQL work limit', self.render_dom(value)['text'])
        self.assertNotIn('table not present', self.render_dom(value)['text'])
        self.assertIn('table not present', self.render_dom({'available': False, 'state': 'missing'})['text'])


if __name__ == '__main__':
    unittest.main()
