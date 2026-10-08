#!/usr/bin/env python3
"""Authenticated historical associations: result cap, whole-panel SQL abstention."""
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


class Associations(ObservationFixture):
	def setUp(self):
		super().setUp()
		self.pub = 'synthetic-key'
		self.player = self.c.execute('SELECT player FROM replays WHERE id=?', (self.rid,)).fetchone()[0]
		self.c.execute("INSERT INTO receipts(runid,map,pub,verdict,angles,reason,at)"
			" VALUES('synthetic-assoc','bhop_eazy',?,'VALID','OK','control',1)", (self.pub,))
		self.c.execute("UPDATE replays SET runid='synthetic-assoc' WHERE id=?", (self.rid,))
		self.c.commit()

	def seed(self, n):
		with self.c:
			self.c.executemany('INSERT INTO pubkeys(pub,player,first_at,last_at,runs) VALUES(?,?,1,2,3)',
				[(self.pub, 'synthetic-player-%05d' % i) for i in range(n)] +
				[('synthetic-key-%05d' % i, self.player) for i in range(n)])

	def history(self):
		return {t: [tuple(r) for r in self.c.execute('SELECT * FROM ' + t)]
			for t in ('pubkeys', 'receipts', 'replays', 'reviews', 'verdicts')}

	def test_positive_both_directions_and_anonymous_refusal(self):
		self.seed(2)
		before = self.history()
		value = self.detail()['receipt']
		self.assertEqual(len(value['players']), 2)
		self.assertEqual(len(value['keys']), 2)
		self.assertEqual(value.get('associations', {}).get('state'), 'ok')
		self.assertFalse(value['associations']['players_more'])
		self.assertFalse(value['associations']['keys_more'])
		self.assertEqual(value['verdict'], 'VALID')
		self.assertEqual(self.history(), before)
		self.assertEqual(self.m.app.test_client().get(self.route).status_code, 401)

	def test_acquisition_is_cap_plus_one_and_history_board_do_not_move(self):
		self.seed(1000)
		before, board = self.history(), self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json()
		seen = []
		read = simcheck._read
		def observe(conn, sql, parameters=(), read_budget=None):
			rows = read(conn, sql, parameters, read_budget)
			if 'FROM pubkeys' in sql:
				seen.append(len(rows))
			return rows
		with mock.patch.object(simcheck, '_read', side_effect=observe):
			value = self.detail()['receipt']
		limit = value.get('associations', {}).get('limit', 25)
		self.assertEqual((len(value['players']), len(value['keys'])), (limit, limit))
		self.assertTrue(seen)  # selected SQL actually acted
		self.assertEqual(seen, [limit + 1, limit + 1])
		self.assertTrue(value['associations']['players_more'])
		self.assertTrue(value['associations']['keys_more'])
		self.assertEqual(self.history(), before)
		self.assertEqual(self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json(), board)

	def test_owned_budget_interrupts_whole_association_panel_and_recovers(self):
		self.seed(100)
		before, callbacks = self.history(), []
		original = simcheck.ReadBudget.rows
		def observe(budget, *args, **kw):
			try:
				return original(budget, *args, **kw)
			finally:
				callbacks.append(budget.exhausted)
		with mock.patch.object(self.a, 'ASSOCIATION_SQL_STEPS', 1, create=True), \
			mock.patch.object(simcheck.ReadBudget, 'rows', observe):
			value = self.detail()['receipt']
		self.assertIn(True, callbacks)  # real VM allowance, not a mocked failure
		self.assertEqual(value.get('associations', {}).get('state'), 'read_limit')
		self.assertEqual((value['players'], value['keys']), ([], []))
		self.assertEqual(value['verdict'], 'VALID')
		self.assertEqual(self.detail()['receipt']['associations']['state'], 'ok')
		self.assertEqual(self.history(), before)

	def test_second_query_interruption_withholds_first_query_results(self):
		self.seed(2)
		before, first, exhausted = self.history(), [], []
		original = simcheck.ReadBudget.rows
		def second_limited(budget, sql, *args, **kw):
			if 'FROM pubkeys' not in sql:
				return original(budget, sql, *args, **kw)
			if 'SELECT pub, runs' in sql:
				budget.remaining = 1
			try:
				rows = original(budget, sql, *args, **kw)
				first.append(len(rows))
				return rows
			finally:
				exhausted.append(budget.exhausted)
		with mock.patch.object(simcheck.ReadBudget, 'rows', second_limited):
			value = self.detail()['receipt']
		self.assertEqual(first, [2])  # first association query genuinely completed
		self.assertEqual(exhausted[:2], [False, True])
		self.assertEqual(value['associations']['state'], 'read_limit')
		self.assertEqual((value['players'], value['keys']), ([], []))
		self.assertEqual(self.history(), before)

	def test_borrowed_handler_and_legacy_schema_remain_owned_read_only(self):
		self.seed(2)
		calls = []
		self.c.set_progress_handler(lambda: calls.append(1) or 0, 1)
		try:
			value = self.a.receipt_for(self.c, self.rid, 'synthetic-assoc')
			self.assertEqual(len(value['players']), 2)
			n = len(calls)
			self.c.execute('SELECT 1').fetchall()
			self.assertGreater(len(calls), n)
		finally:
			self.c.set_progress_handler(None, 0)
		self.c.execute('DROP TABLE pubkeys'); self.c.commit()
		value = self.detail()['receipt']
		self.assertEqual(value.get('associations', {}).get('state'), 'missing')
		self.assertEqual(value['verdict'], 'VALID')
		self.assertIsNone(self.c.execute("SELECT 1 FROM sqlite_master WHERE name='pubkeys'").fetchone())

	def test_actual_dom_partial_counts_are_lower_bounds_and_unavailable_is_explicit(self):
		if not shutil.which('node'): self.skipTest('Node absent')
		text = Path(self.a.__file__).with_name('templates').joinpath('admin_run.html').read_text(encoding='utf-8')
		start = text.find('function renderReceiptAssociations(')
		self.assertNotEqual(start, -1)
		block = text[start:text.index('function renderRun(', start)]
		js = r'''
const el=(tag,cls,text)=>String(text??'');const rows=[];
const result=renderReceiptAssociations(JSON.parse(process.argv[2]),(k,v)=>rows.push(k+': '+v));
console.log(JSON.stringify({rows,result}));
''' .replace('const el=', block + '\nconst el=')
		with tempfile.TemporaryDirectory() as home:
			path = Path(home) / 'render.js'; path.write_text(js, encoding='utf-8')
			self.seed(30)
			value = self.detail()['receipt']
			def render(v):
				p = subprocess.run(['node', str(path), json.dumps(v)], capture_output=True, text=True)
				self.assertEqual(p.returncode, 0, p.stderr)
				return json.loads(p.stdout)
			out = render(value)
			self.assertEqual(out['result']['playerCount'], '25+')
			self.assertEqual(out['result']['keyCount'], '25+')
			self.assertIn('showing first 25', '\n'.join(out['rows']))
			value.update(players=[], keys=[], associations={'state':'read_limit'})
			out = render(value)
			self.assertFalse(out['result']['shared'])
			self.assertFalse(out['result']['manykeys'])
			self.assertIn('unavailable', '\n'.join(out['rows']))
			self.assertIn('SQL work limit', '\n'.join(out['rows']))


if __name__ == '__main__':
	unittest.main()
