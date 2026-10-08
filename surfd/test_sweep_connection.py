"""main owns/closes its connection on all exits; step APIs borrow theirs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ConnectionLifetime(unittest.TestCase):
    def test_actual_main_exits_and_borrowed_step_control(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home, SURFD_DB=str(Path(home)/'test.db'),
                       SURFD_ENV=str(Path(home)/'empty.env'), SURFD_GAME=home,
                       SURFD_RUNS=str(Path(home)/'runs'))
            program = r'''
from contextlib import ExitStack, redirect_stdout
from io import StringIO
import importlib.util, os, sqlite3, unittest
from unittest import mock
import surfd, sweep
if os.environ.get('SWEEP_UNDER_TEST'):
    spec=importlib.util.spec_from_file_location('control_sweep',os.environ['SWEEP_UNDER_TEST'])
    sweep=importlib.util.module_from_spec(spec);spec.loader.exec_module(sweep)

class Owned(sqlite3.Connection):
    closed=0
    def close(self):
        self.closed+=1
        return super().close()

class Exits(unittest.TestCase):
    def act(self, mode):
        conn=sqlite3.connect(':memory:',factory=Owned);conn.row_factory=sqlite3.Row
        self.addCleanup(conn.close)
        conn.execute('CREATE TABLE acted(n)')
        conn.execute('INSERT INTO acted VALUES(7)');conn.commit()
        retained=[]
        def fail(*a,**k):
            self.assertEqual(conn.execute('SELECT n FROM acted').fetchone()[0],7)
            raise KeyboardInterrupt('acted') if mode=='interrupt' else RuntimeError('acted')
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(surfd,'connect',return_value=conn))
            stack.enter_context(mock.patch.object(sweep,'evidence_step',side_effect=fail if mode in ('error','interrupt') else None,return_value=(0,0)))
            stack.enter_context(mock.patch.object(sweep,'receipt_step',return_value=(0,0)))
            stack.enter_context(mock.patch.object(sweep,'similarity_step',return_value=(0,0,'')))
            stack.enter_context(mock.patch.object(sweep,'sweep',return_value={}))
            stack.enter_context(mock.patch.object(sweep,'disk_note',return_value=''))
            stack.enter_context(mock.patch.object(sweep,'pending',return_value=[]))
            stack.enter_context(mock.patch.object(surfd,'index_evidence',return_value=(0,0)))
            if mode=='schema': stack.enter_context(mock.patch.object(sweep,'ensure_schema',side_effect=fail))
            with redirect_stdout(StringIO()):
                try: result=sweep.main(['--dry-run'] if mode=='dry' else ['--sims','0'])
                except (RuntimeError,KeyboardInterrupt) as exc: retained.append(exc)
                else:
                    self.assertIn(mode,('normal','dry'));self.assertEqual(result,0)
        if mode in ('schema','error','interrupt'):
            self.assertEqual(len(retained),1)
            self.assertIsNotNone(retained[0].__traceback__)
        self.assertEqual(conn.closed,1)
        with self.assertRaises(sqlite3.ProgrammingError):conn.execute('SELECT 1')
    def test_normal(self):self.act('normal')
    def test_dry(self):self.act('dry')
    def test_schema(self):self.act('schema')
    def test_error(self):self.act('error')
    def test_interrupt(self):self.act('interrupt')
    def test_borrowed_step(self):
        conn=sqlite3.connect(':memory:',factory=Owned);self.addCleanup(conn.close)
        self.assertEqual(sweep.similarity_step(conn,limit=0),(0,0,''))
        self.assertEqual(conn.closed,0)
        self.assertEqual(conn.execute('SELECT 42').fetchone()[0],42)

unittest.main()
'''
            result = subprocess.run([sys.executable,'-W','error','-c',program],cwd=here,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('Ran 6 tests',result.stderr)
            self.assertIn('OK',result.stderr)


if __name__ == '__main__': unittest.main()
