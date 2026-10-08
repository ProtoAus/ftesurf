"""Collector LIMIT contracts: reject before loading/querying, positive controls act."""
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
    sc = fixture.load('limits_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc

INVALID = (-1, True, 1.5, '3', (1 << 63), None)


class Limits(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def test_source_and_pair_limits_reject_before_loader_or_database(self):
        before = tuple(self.conn.iterdump())
        for name in ('limit', 'max_pairs'):
            for value in INVALID:
                with self.subTest(name=name, value=value):
                    with mock.patch.object(sc, '_recsim', side_effect=AssertionError('loader acted')):
                        with self.assertRaises(ValueError):
                            sc.similarity_step(self.conn, self.sf, **{name: value})
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def test_peer_limits_reject_before_loader_and_zero_never_loads(self):
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        for value in INVALID:
            with self.subTest(value=value):
                with mock.patch.object(sc, '_recsim', side_effect=AssertionError('loader acted')):
                    with self.assertRaises(ValueError):
                        sc.compare_run(self.sf, self.conn, row, limit_peers=value)
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('zero loaded')):
            self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=0), (0, 0, 0))

    def test_pending_rejects_before_any_query_and_zero_returns_empty(self):
        queries = []
        self.conn.set_trace_callback(queries.append)
        for value in INVALID:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): sc.pending(self.conn, value)
        self.assertEqual(queries, [])
        self.assertEqual(sc.pending(self.conn, 0), [])
        self.assertEqual(queries, [])
        self.assertEqual(len(sc.pending(self.conn, 1)), 1)
        self.assertTrue(any('FROM replays' in q for q in queries))

    def test_positive_collection_and_zero_controls(self):
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('zero loaded')):
            for options in ({'limit': 0}, {'max_pairs': 0}):
                self.assertEqual(sc.similarity_step(self.conn, self.sf, **options), (0, 0, ''))
        result = sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=1,
                                    tools_dir=str(fixture.ROOT/'tools'))
        self.assertEqual(result[:2], (1, 1))
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0], 80)

    def test_actual_wrapper_and_cli_validate_before_optional_load_or_main_connect(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home, SURFD_DB=str(Path(home)/'test.db'),
                       SURFD_ENV=str(Path(home)/'empty.env'), SURFD_GAME=home,
                       SURFD_RUNS=str(Path(home)/'runs'), SURFD_TOOLS=str(here.parent/'tools'))
            Path(env['SURFD_ENV']).write_text('SURFD_KEY=synthetic\n')
            program = r'''
import importlib.util, os
from unittest import mock
import surfd, sweep
if os.environ.get('SWEEP_UNDER_TEST'):
    spec=importlib.util.spec_from_file_location('control_sweep',os.environ['SWEEP_UNDER_TEST'])
    sweep=importlib.util.module_from_spec(spec);spec.loader.exec_module(sweep)
conn=surfd.connect()
with mock.patch.object(sweep,'_simcheck',side_effect=AssertionError('wrapper loaded')):
    for name in ('limit','max_pairs'):
        for value in (-1,True,1.5,'3',1<<63,None):
            try: sweep.similarity_step(conn,**{name:value})
            except ValueError: pass
            else: raise AssertionError('invalid wrapper limit accepted')
with mock.patch.object(surfd,'connect',side_effect=AssertionError('main connected')):
    for flag in ('--sims','--sims-pairs'):
        for value in ('-1','1.5','9223372036854775808'):
            try: sweep.main([flag+'='+value])
            except SystemExit as exc: assert exc.code==2
            else: raise AssertionError('invalid CLI limit accepted')
print('LIMIT_CONSUMERS_ACTED')
conn.close()
'''
            result = subprocess.run([sys.executable,'-c',program],cwd=here,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('LIMIT_CONSUMERS_ACTED',result.stdout)


if __name__ == '__main__': unittest.main()
