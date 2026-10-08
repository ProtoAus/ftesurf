"""Explicit owner-scoped busy handler: real contention, restoration and recovery."""
from contextlib import nullcontext
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('wait_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


def policy(conn, milliseconds):
    fn = getattr(sc, 'lock_wait', None)
    return fn(conn, milliseconds) if fn else nullcontext()


class LockWait(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def timeout(self):
        return self.conn.execute('PRAGMA busy_timeout').fetchone()[0]

    def test_actual_exclusive_lock_has_short_wait_then_restores_and_recovers(self):
        self.conn.execute('PRAGMA busy_timeout=500')
        blocker = sqlite3.connect(self.db); self.addCleanup(blocker.close)
        blocker.execute('BEGIN EXCLUSIVE')
        started = time.monotonic()
        with policy(self.conn, 20):
            during = self.timeout()
            result = sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))
        elapsed = time.monotonic()-started
        self.assertEqual(result[:2], (0, 0))
        self.assertTrue(result[2])
        self.assertEqual(during, 20)
        self.assertLess(elapsed, 0.4)  # broad tolerance, not precision timing
        self.assertEqual(self.timeout(), 500)
        self.assertFalse(self.conn.in_transaction)
        blocker.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)
        with policy(self.conn, 20):
            self.assertEqual(sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))[:2], (3, 3))
        self.assertEqual([r[0] for r in self.conn.execute('SELECT compared FROM sims')], [80]*3)
        self.assertEqual(self.timeout(), 500)

    def test_real_busy_operation_acts_and_zero_wait_restores_after_error(self):
        self.conn.execute('PRAGMA busy_timeout=777')
        blocker = sqlite3.connect(self.db); self.addCleanup(blocker.close)
        blocker.execute('BEGIN EXCLUSIVE')
        with self.assertRaises(sqlite3.OperationalError) as caught:
            with policy(self.conn, 0):
                during = self.timeout()
                self.conn.execute('SELECT * FROM replays').fetchall()
        code = getattr(caught.exception, 'sqlite_errorcode', None)
        if code is not None:
            self.assertEqual(code & 255, sqlite3.SQLITE_BUSY)
        self.assertEqual(during, 0)
        self.assertEqual(self.timeout(), 777)
        blocker.rollback()
        self.assertEqual(len(self.conn.execute('SELECT * FROM replays').fetchall()), 3)

    def test_success_exception_interrupt_and_nested_numeric_policy_restore(self):
        self.conn.execute('PRAGMA busy_timeout=4321')
        for exception in (None, RuntimeError, KeyboardInterrupt):
            try:
                with policy(self.conn, 9):
                    self.assertEqual(self.timeout(), 9)
                    with policy(self.conn, 0):
                        self.assertEqual(self.timeout(), 0)
                    self.assertEqual(self.timeout(), 9)
                    if exception: raise exception('synthetic interruption')
            except (RuntimeError, KeyboardInterrupt):
                pass
            self.assertEqual(self.timeout(), 4321)

    def test_invalid_policy_rejects_before_changing_connection(self):
        fn = getattr(sc, 'lock_wait', None)
        if fn is None: self.fail('owner lock wait support unavailable')
        before = self.timeout()
        for value in (-1, True, 1.5, 2147483648):
            with self.assertRaises(ValueError):
                with fn(self.conn, value): pass
            self.assertEqual(self.timeout(), before)

    def test_unopted_direct_collection_preserves_numeric_timeout(self):
        self.conn.execute('PRAGMA busy_timeout=333')
        self.assertEqual(sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))[:2], (3, 3))
        self.assertEqual(self.timeout(), 333)


class WrapperCLI(unittest.TestCase):
    def test_actual_wrapper_scope_disabled_paths_cli_validation_and_forwarding(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home, SURFD_DB=str(Path(home)/'test.db'),
                       SURFD_ENV=str(Path(home)/'empty.env'), SURFD_RUNS=str(Path(home)/'runs'),
                       SURFD_GAME=home, SURFD_TOOLS=str(here.parent/'tools'),
                       SURFD_VERIFIER=str(Path(home)/'noengine'))
            Path(env['SURFD_ENV']).write_text('SURFD_KEY=synthetic\n')
            program = r'''
from unittest import mock
import surfd, sweep, simcheck
conn = surfd.connect()
conn.execute('PRAGMA busy_timeout=876')
acted=[]
def collect(conn, *args, **kw):
    acted.append(conn.execute('PRAGMA busy_timeout').fetchone()[0])
    return (0,0,'synthetic acted')
with mock.patch.object(simcheck,'similarity_step',side_effect=collect):
    assert sweep.similarity_step(conn, max_lock_ms=17)==(0,0,'synthetic acted')
assert acted==[17],acted
assert conn.execute('PRAGMA busy_timeout').fetchone()[0]==876
with mock.patch.object(simcheck,'lock_wait',side_effect=AssertionError('disabled wait called')):
    for options in ({'limit':0},{'max_pairs':0},{'max_seconds':0},{'max_sql_steps':0}):
        assert sweep.similarity_step(conn,**options)==(0,0,'')
with mock.patch.object(surfd,'connect',side_effect=AssertionError('parser connected')):
    for value in ('-1','1.5','nan','2147483648'):
        try: sweep.main(['--sims-lock-ms='+value])
        except SystemExit as exc: assert exc.code==2
        else: raise AssertionError('invalid lock allowance accepted')
with mock.patch.object(sweep,'similarity_step',return_value=(0,0,'')) as target:
    sweep.main(['--limit','0','--sims','0','--sims-lock-ms','0'])
    assert target.call_args.kwargs['max_lock_ms']==0
print('LOCK_WRAPPER_ACTED')
'''
            result = subprocess.run([sys.executable,'-c',program],cwd=here,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('LOCK_WRAPPER_ACTED',result.stdout)


if __name__ == '__main__':
    unittest.main()
