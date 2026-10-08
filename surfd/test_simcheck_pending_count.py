"""Scalar pending diagnostics: capped predicate parity, payload avoidance, abstention."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('count_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


def count(conn, limit=1000000, read_budget=None):
    fn = getattr(sc, 'pending_count', None)
    return fn(conn, limit, read_budget=read_budget) if fn else len(sc.pending(conn, limit, read_budget=read_budget))


class PendingCount(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def test_scalar_projection_never_fetches_wide_replay_rows(self):
        self.conn.execute('UPDATE replays SET player=?', ('irrelevant' * 100000,))
        self.conn.commit()
        calls = []
        original = sc._read
        def read(conn, sql, *args, **kw):
            rows = original(conn, sql, *args, **kw)
            calls.append((sql, len(rows), len(rows[0]) if rows else 0))
            return rows
        before = self.conn.total_changes
        with mock.patch.object(sc, '_read', side_effect=read):
            self.assertEqual(count(self.conn), 3)
        self.assertEqual(len(calls), 1)
        self.assertIn('COUNT(*)', calls[0][0])
        self.assertNotIn('r.*', calls[0][0])
        self.assertEqual(calls[0][1:], (1, 1))
        self.assertEqual(self.conn.total_changes, before)
        self.assertFalse(self.conn.in_transaction)

    def test_capped_parity_exclusions_orientations_skips_and_source_cursor(self):
        for row in ((4,'synthetic',0,0,'save','','s'),(5,'other',0,0,'run','','s'),
                    (6,'synthetic',1,0,'run','','s'),(7,'synthetic',0,1,'run','','s')):
            self.conn.execute('INSERT INTO replays VALUES (?,?,?,?,?,?,?)', row)
        self.conn.commit()
        sc._advance(self.conn, 'source', 2)
        for cap in (0, 1, 2, 10):
            self.assertEqual(count(self.conn, cap), len(sc.pending(self.conn, cap)))
        self.assertEqual(count(self.conn), 3)
        self.paths[1].write_bytes(fixture.source(9))  # two real short/unjudgeable skips ACT
        self.assertEqual(fixture.StoredSources.run_source(self, 1, max_pairs=2), (2, 2, 0))
        self.assertEqual(count(self.conn), 2)
        self.conn.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,reason,match,compared,at) VALUES(3,2,'synthetic',0,0,'skip','synthetic',0,0,1)")
        self.conn.commit()
        before = tuple(self.conn.iterdump())
        self.assertEqual(count(self.conn), 0)
        self.assertEqual(sc.pending(self.conn, 10), [])
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def test_actual_vm_interruption_is_unavailable_not_zero_and_recovers(self):
        with self.assertRaises(sc.ReadLimit): count(self.conn, read_budget=sc.ReadBudget(self.conn, 1))
        self.assertEqual(self.conn.execute('SELECT 42').fetchone()[0], 42)
        self.assertEqual(count(self.conn, read_budget=sc.ReadBudget(self.conn, 100000)), 3)
        queries=[];self.conn.set_trace_callback(queries.append)
        for value in (-1, True, 1.5, 1 << 63):
            with self.assertRaises(ValueError): count(self.conn, value)
        self.assertEqual(count(self.conn, 0), 0)
        self.assertEqual(queries, [])

    def test_actual_cli_does_not_call_row_materializer_and_reports_capped_count(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home, SURFD_DB=str(Path(home)/'test.db'),
                       SURFD_ENV=str(Path(home)/'empty.env'), SURFD_GAME=home,
                       SURFD_RUNS=str(Path(home)/'runs'))
            program = r'''
from contextlib import redirect_stdout
from io import StringIO
import importlib.util, os
from unittest import mock
import surfd, sweep, simcheck
if os.environ.get('SWEEP_UNDER_TEST'):
    spec=importlib.util.spec_from_file_location('control_sweep',os.environ['SWEEP_UNDER_TEST'])
    sweep=importlib.util.module_from_spec(spec);spec.loader.exec_module(sweep)
conn=surfd.connect();simcheck.ensure_schema(conn)
for i in (1,2,3):
    conn.execute("INSERT INTO replays(map,map_dir,track,leg,leaf,tier,style,player,name,ticks,tickrate,millis,flags,node,submitted,kind) VALUES('synthetic','synthetic',0,0,?,'ranked','normal','s','s',80,100,800,0,'1',1,'run')",('synthetic-%d.rec'%i,))
conn.commit();conn.close()
with mock.patch.object(simcheck,'pending',side_effect=AssertionError('row materializer acted')):
    output=StringIO()
    with redirect_stdout(output):assert sweep.main(['--dry-run'])==0
    assert 'sims pending: 3 run(s) with unobserved eligible pairs' in output.getvalue(),output.getvalue()
    output=StringIO()
    with redirect_stdout(output):assert sweep.main(['--dry-run','--sims-sql-steps','1'])==0
    assert 'unavailable (SQL read limit; coverage not measured)' in output.getvalue(),output.getvalue()
if hasattr(simcheck,'pending_count'):
    with mock.patch.object(simcheck,'pending_count',return_value=1000000):
        output=StringIO()
        with redirect_stdout(output):assert sweep.main(['--dry-run'])==0
        assert 'sims pending: at least 1000000 run(s)' in output.getvalue(),output.getvalue()
else:raise AssertionError('scalar consumer unavailable')
print('SCALAR_CLI_ACTED')
'''
            result = subprocess.run([sys.executable,'-c',program],cwd=here,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('SCALAR_CLI_ACTED',result.stdout)


if __name__ == '__main__': unittest.main()
