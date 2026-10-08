"""Owned-connection SQLite VM budgets: source selection, not elapsed/coverage."""
import inspect
import os
import sqlite3
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('budget_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


class TrackedConnection(sqlite3.Connection):
    def set_progress_handler(self, callback, quantum):
        self.handlers.append((callback is not None, quantum))
        return super().set_progress_handler(callback, quantum)


def budget(conn, steps):
    cls = getattr(sc, 'ReadBudget', None)
    return cls(conn, steps) if cls else None


def options(fn, obj):
    return {'read_budget': obj} if 'read_budget' in inspect.signature(fn).parameters else {}


class SqlSources(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def step(self, steps):
        obj = budget(self.conn, steps)
        return sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'),
                                 max_seconds=30, **options(sc.similarity_step, obj))

    def grow(self, n=250):
        self.conn.executemany("INSERT INTO replays VALUES (?,'synthetic',0,0,'run','','s')",
                              [(i,) for i in range(4,n+1)])
        self.conn.commit()

    def test_pending_limit_is_unavailable_without_partial_rows_or_admission(self):
        self.grow()
        resolved = []
        self.sf.replay_file = lambda row: (resolved.append(row['id']) or (None, 'unavailable'))
        before = tuple(self.conn.iterdump())
        result = self.step(200)
        self.assertEqual(result[:2], (0,0))
        self.assertIn('SQL read limit', result[2])
        self.assertIn('coverage not measured', result[2])
        self.assertEqual(resolved, [])
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertFalse(self.conn.in_transaction)
        # A fresh high allowance must actually resolve native sources.
        result = self.step(10000000)
        self.assertIn('source unavailable', result[2])
        self.assertGreater(len(resolved), 0)

    def test_positive_real_comparison_is_unchanged_and_unguarded(self):
        active = []
        old = self.sf.replay_file
        def resolve(row):
            calls = []
            self.conn.set_progress_handler(lambda: calls.append(1) or 0, 1)
            self.conn.execute('SELECT 1').fetchall()
            self.conn.set_progress_handler(None, 0)
            self.assertTrue(calls)  # proves query helper released its slot before files
            active.append(row['id'])
            return old(row)
        self.sf.replay_file = resolve
        stored, notable, note = self.step(1000000)
        self.assertEqual((stored,notable),(3,3))
        self.assertEqual([r[0] for r in self.conn.execute('SELECT compared FROM sims')], [80]*3)
        self.assertGreater(len(active),0)
        self.assertNotIn('SQL read limit',note)

    def test_guard_closes_callback_on_success_interrupt_and_query_error(self):
        conn = sqlite3.connect(':memory:', factory=TrackedConnection)
        self.addCleanup(conn.close); conn.handlers=[]
        obj = budget(conn, 100)
        if obj is None:
            self.fail('bounded read support unavailable')
        self.assertEqual(obj.rows('SELECT 42'), [(42,)])
        self.assertEqual(conn.handlers[-1], (False,0))
        with self.assertRaises(getattr(sc,'ReadLimit',AssertionError)):
            obj.rows('WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<10000) SELECT sum(x) FROM n')
        self.assertEqual(conn.handlers[-1], (False,0))
        self.assertEqual(conn.execute('SELECT 43').fetchone()[0],43)
        obj = budget(conn,1000)
        with self.assertRaises(sqlite3.OperationalError): obj.rows('SELECT absent FROM absent')
        self.assertEqual(conn.handlers[-1], (False,0))

    def test_quantum_reservation_bounds_many_small_reads_and_rejects_reuse(self):
        obj = budget(self.conn, 30)
        if obj is None: self.fail('bounded read support unavailable')
        self.assertEqual(obj.rows('SELECT 1')[0][0],1)
        with self.assertRaises(sc.ReadLimit): obj.rows('SELECT 2')
        self.assertTrue(obj.exhausted)
        self.assertEqual(self.conn.execute('SELECT 3').fetchone()[0],3)
        for invalid in (0,-1,True,1.5):
            with self.assertRaises(ValueError): sc.ReadBudget(self.conn,invalid)

    def test_no_budget_preserves_external_callback_and_legacy_read(self):
        calls=[]
        self.conn.set_progress_handler(lambda: calls.append(1) or 0,1)
        rows=sc.pending(self.conn,1)
        self.assertEqual(len(rows),1); self.assertGreater(len(calls),0)
        before=len(calls); self.conn.execute('SELECT 1').fetchall()
        self.assertGreater(len(calls),before)
        self.conn.set_progress_handler(None,0)

    def test_foreign_connection_budget_is_rejected_before_query(self):
        obj=budget(self.conn,100000)
        other=sqlite3.connect(':memory:'); self.addCleanup(other.close)
        if obj is None: self.fail('bounded read support unavailable')
        with self.assertRaises(ValueError): sc.pending(other,1,**options(sc.pending,obj))

if __name__=='__main__': unittest.main()
