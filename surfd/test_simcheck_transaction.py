"""Idle-connection precondition: caller owns pending DML, never the collector."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('transaction_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


class Transactions(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def pending_write(self):
        self.conn.execute('INSERT INTO probe VALUES (42)')
        self.assertTrue(self.conn.in_transaction)

    def assert_owned(self):
        self.assertTrue(self.conn.in_transaction)
        self.assertEqual(self.conn.execute('SELECT n FROM probe').fetchall()[0][0], 42)
        with sqlite3.connect(str(self.db)) as observer:
            self.assertEqual(observer.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 0)
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 0)

    def test_enabled_step_abstains_before_loading_and_keeps_caller_write(self):
        self.pending_write()
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('loader acted')):
            result = sc.similarity_step(self.conn, self.sf)
        self.assertEqual(result[:2], (0, 0))
        self.assertIn('active caller transaction', result[2])
        self.assertIn('coverage not measured', result[2])
        self.assert_owned()

    def test_direct_comparison_rejects_before_files_and_keeps_caller_write(self):
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        self.pending_write()
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('loader acted')):
            with self.assertRaisesRegex(ValueError, 'idle connection'):
                sc.compare_run(self.sf, self.conn, row)
        self.assert_owned()

    def test_schema_and_cursor_writers_reject_without_implicit_commit(self):
        for act in (lambda: sc.ensure_schema(self.conn), lambda: sc._advance(self.conn, 'source', 2)):
            self.pending_write()
            with self.assertRaisesRegex(ValueError, 'idle connection'): act()
            self.assert_owned()

    def test_disabled_and_read_only_apis_leave_transaction_under_caller_control(self):
        self.pending_write()
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('disabled loaded')):
            self.assertEqual(sc.similarity_step(self.conn, self.sf, limit=0), (0, 0, ''))
            row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
            self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=0), (0, 0, 0))
        self.assertEqual(len(sc.pending(self.conn, 1)), 1)
        self.assertEqual(sc.summary(self.conn)['state'], 'empty')
        self.assert_owned()

    def test_wrapper_abstains_before_loading_or_changing_handler_slots(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home, SURFD_DB=str(Path(home)/'test.db'),
                       SURFD_ENV=str(Path(home)/'empty.env'), SURFD_GAME=home)
            program = r'''
import importlib.util, os
from unittest import mock
import surfd, sweep
if os.environ.get('SWEEP_UNDER_TEST'):
    spec=importlib.util.spec_from_file_location('control_sweep',os.environ['SWEEP_UNDER_TEST'])
    sweep=importlib.util.module_from_spec(spec);spec.loader.exec_module(sweep)
conn=surfd.connect()
conn.execute('CREATE TABLE probe (n INTEGER)')
conn.execute('INSERT INTO probe VALUES (42)')
conn.execute('PRAGMA busy_timeout=73')
progress=[]
conn.set_progress_handler(lambda: progress.append(1) or 0,1)
with mock.patch.object(sweep,'_simcheck',side_effect=AssertionError('wrapper loaded')):
    result=sweep.similarity_step(conn,limit=1,max_lock_ms=1)
assert result[:2]==(0,0) and 'active caller transaction' in result[2],result
assert conn.in_transaction
assert conn.execute('PRAGMA busy_timeout').fetchone()[0]==73
before=len(progress);conn.execute('SELECT 1').fetchall();assert len(progress)>before
conn.rollback();assert conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0]==0
conn.close()
print('OWNERSHIP_WRAPPER_ACTED')
'''
            result = subprocess.run([sys.executable,'-c',program],cwd=here,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('OWNERSHIP_WRAPPER_ACTED',result.stdout)

    def test_idle_control_stores_sample_and_independent_writer_acts_during_files(self):
        acted = []
        def compare(a, b, **kw):
            self.assertFalse(self.conn.in_transaction)
            with sqlite3.connect(str(self.db)) as writer:
                writer.execute('INSERT INTO probe VALUES (7)')
            acted.append(1)
            return fixture.rs.compare_paths(a, b, **kw)
        reader = type('Reader', (), {'compare_paths': staticmethod(compare)})
        with mock.patch.object(sc, '_recsim', return_value=(reader, '')):
            result = sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=1)
        self.assertEqual(result[:2], (1, 1))
        self.assertEqual(acted, [1])
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0], 80)
        self.assertEqual(self.conn.execute('SELECT n FROM probe').fetchone()[0], 7)
        self.assertFalse(self.conn.in_transaction)


if __name__ == '__main__': unittest.main()
