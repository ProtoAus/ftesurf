"""Actual sweep wrapper and CLI budget controls, isolated HOME and run tree."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class BudgetCLI(unittest.TestCase):
    def test_actual_wrapper_and_zero_disable(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home,
                       SURFD_DB=str(Path(home)/'test.db'), SURFD_ENV=str(Path(home)/'empty.env'),
                       SURFD_RUNS=str(Path(home)/'runs'), SURFD_GAME=home,
                       SURFD_TOOLS=str(HERE.parent/'tools'), SURFD_VERIFIER=str(Path(home)/'noengine'))
            Path(env['SURFD_ENV']).write_text('SURFD_KEY=synthetic\n')
            program = r'''
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock
import surfd, sweep, simcheck
conn = surfd.connect()
for i in range(1,4):
    leaf = '0000800_synthetic-%08x_run.rec' % i
    folder = Path(surfd.RUNS_DIR)/'synthetic'/'main'
    folder.mkdir(parents=True, exist_ok=True)
    rows = ['FTESURF-REC 9','map synthetic','track 0','leg 0','tickrate 100','begin']
    rows += ['in %d %d 0 %d 0 0 0 0 0 4' % (j,j,100+j%7) for j in range(80)]
    rows += ['end 80']
    (folder/leaf).write_text('\n'.join(rows)+'\n')
    conn.execute("INSERT INTO replays (map,map_dir,track,leg,leaf,tier,style,player,name,ticks,tickrate,millis,flags,node,submitted,kind) VALUES ('synthetic','synthetic',0,0,?,'ranked','normal','synthetic','synthetic',80,100,800,0,'1',1,'run')", (leaf,))
conn.commit()
with mock.patch.object(sweep, '_simcheck', side_effect=AssertionError('disabled loader called')):
    assert sweep.similarity_step(conn, limit=3, max_pairs=0) == (0,0,'')
    assert sweep.similarity_step(conn, limit=3, max_seconds=0) == (0,0,'')
    assert sweep.similarity_step(conn, limit=3, max_sql_steps=0) == (0,0,'')
stored, notable, note = sweep.similarity_step(conn, limit=3, max_pairs=1)
assert (stored,notable) == (1,1), (stored,notable,note)
assert 'pair limit reached' in note, note
assert conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0] == 1
assert conn.execute('SELECT compared FROM sims').fetchone()[0] == 80
# Actual CLI consumer: the two already-observed sources still have unobserved
# pairs with the third. A count of three is not "no pair stored yet".
before = [tuple(r) for r in conn.execute('SELECT * FROM sims ORDER BY id')]
output = StringIO()
with redirect_stdout(output):
    assert sweep.main(['--dry-run']) == 0
assert '3 run(s) with unobserved eligible pairs' in output.getvalue(), output.getvalue()
assert 'no pair stored yet' not in output.getvalue(), output.getvalue()
assert before == [tuple(r) for r in conn.execute('SELECT * FROM sims ORDER BY id')]
output = StringIO()
with redirect_stdout(output):
    assert sweep.main(['--dry-run', '--sims-sql-steps', '1']) == 0
assert 'sims pending: unavailable (SQL read limit; coverage not measured)' in output.getvalue(), output.getvalue()
assert 'sims: unavailable (SQL read limit; sample not measured)' in output.getvalue(), output.getvalue()
output = StringIO()
with redirect_stdout(output):
    assert sweep.main(['--dry-run', '--sims-sql-steps', '0']) == 0
assert 'SQL reads disabled' in output.getvalue(), output.getvalue()
assert 'no pairs stored' not in output.getvalue(), output.getvalue()
assert before == [tuple(r) for r in conn.execute('SELECT * FROM sims ORDER BY id')]
print('DRY_RUN_ACTED')
with mock.patch.object(simcheck, 'similarity_step', return_value=(0,0,'')) as target:
    sweep.similarity_step(conn, limit=3, max_pairs=2, max_seconds=0.25)
    assert target.call_args.kwargs['max_seconds'] == 0.25
# CLI forwards the scalar and rejects invalid budgets before its connect call.
with mock.patch.object(surfd, 'connect', side_effect=AssertionError('parser connected')):
    for value in ('-1','1.5','nan'):
        try:
            sweep.main(['--sims-sql-steps='+value])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError('invalid SQL read budget accepted')
    for value in ('-1','nan','inf','-inf'):
        try:
            sweep.main(['--sims-seconds='+value])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError('invalid elapsed budget accepted')
with mock.patch.object(sweep, 'similarity_step', return_value=(0,0,'')) as target:
    sweep.main(['--limit','0','--sims','0','--sims-seconds','0.25','--sims-sql-steps','1234'])
    assert target.call_args.kwargs['max_seconds'] == 0.25
    assert target.call_args.kwargs['max_sql_steps'] == 1234
    assert target.call_args.kwargs['hard_process'] is True
print('WRAPPER_ACTED')
'''
            result = subprocess.run([sys.executable, '-c', program], cwd=HERE, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('WRAPPER_ACTED', result.stdout)
            self.assertIn('DRY_RUN_ACTED', result.stdout)
            result = subprocess.run([sys.executable, str(HERE/'sweep.py'), '--limit','0',
                                     '--sims','3','--sims-pairs','0'], cwd=HERE, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('sweep: nothing to verify', result.stdout)
            self.assertNotIn('sims ', result.stdout)

    def test_peer_window_uses_remaining_pair_allowance(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, SURFD_HOME=home,
                       SURFD_DB=str(Path(home)/'test.db'), SURFD_ENV=str(Path(home)/'empty.env'),
                       SURFD_RUNS=str(Path(home)/'runs'), SURFD_GAME=home,
                       SURFD_TOOLS=str(HERE.parent/'tools'), SURFD_VERIFIER=str(Path(home)/'noengine'))
            Path(env['SURFD_ENV']).write_text('SURFD_KEY=synthetic\n')
            program = r'''
from pathlib import Path
import surfd, sweep, simcheck
conn = surfd.connect()
folder = Path(surfd.RUNS_DIR)/'synthetic'/'main'
folder.mkdir(parents=True)
record = ['FTESURF-REC 9','map synthetic','track 0','leg 0','tickrate 100','begin']
record += ['in %d %d 0 %d 0 0 0 0 0 4' % (j,j,100+j%7) for j in range(80)]
record += ['end 80']
for i in range(1,202):
    leaf = '0000800_synthetic-%08x_run.rec' % i
    (folder/leaf).write_text('\n'.join(record)+'\n')
    conn.execute("INSERT INTO replays (map,map_dir,track,leg,leaf,tier,style,player,name,ticks,tickrate,millis,flags,node,submitted,kind) VALUES ('synthetic','synthetic',0,0,?,'ranked','normal','synthetic','synthetic',80,100,800,0,'1',1,'run')", (leaf,))
conn.commit()
conn.execute('PRAGMA busy_timeout=617')
queries = []
conn.set_trace_callback(lambda sql: queries.append(sql) if sql.startswith('SELECT p.* FROM replays') else None)
# Without the shared remainder, the old 200-peer prefetch spends this SQL
# allowance before its first comparison; the real reader is never substituted.
stored, notable, note = sweep.similarity_step(conn, limit=1, max_pairs=1,
    max_sql_steps=20000, max_seconds=60, max_lock_ms=5)
assert (stored,notable) == (1,1), (stored,notable,note)
assert 'pair limit reached' in note and 'SQL read limit reached' not in note, note
row = conn.execute('SELECT a_id,b_id,verdict,compared,match,source_capture FROM sims').fetchone()
assert tuple(row)[:5] == (1,2,'compared',80,1.0), tuple(row)
assert row['source_capture'] and queries and all(q.endswith('LIMIT 1') for q in queries)
assert not conn.in_transaction and conn.execute('PRAGMA busy_timeout').fetchone()[0] == 617
assert conn.execute('SELECT COUNT(*) FROM replays').fetchone()[0] == 201
# Later healthy passes still advance, rather than repeatedly selecting the pair
# already measured. Windows are bounded; this is not exhaustive/fair coverage.
for _ in range(3):
    result = sweep.similarity_step(conn, limit=1, max_pairs=1, max_seconds=60)
    assert result[:2] == (1,1), result
assert conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0] == 4
assert conn.execute('SELECT MAX(MAX(a_id,b_id)) FROM sims').fetchone()[0] >= 4
# Generic direct callers retain their existing window, including late-overlap
# lookahead. An exhausted budget still admits/stores nothing.
queries.clear()
source = conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
assert simcheck.compare_run(surfd, conn, source, budget=simcheck._PairBudget(0,60),
                           tools_dir=sweep.TOOLS) == (0,0,0)
queries.clear()
result = simcheck.compare_run(surfd, conn, source, limit_peers=2, tools_dir=sweep.TOOLS)
assert result == (2,0,2), result
assert queries and all(q.endswith('LIMIT 2') for q in queries)
assert not conn.in_transaction and conn.execute('PRAGMA busy_timeout').fetchone()[0] == 617
assert conn.execute('SELECT COUNT(*) FROM sims WHERE verdict=? AND compared=80 AND match=1', ('compared',)).fetchone()[0] == 6
print('REMAINING_PEER_WINDOW_ACTED')
conn.close()
'''
            result = subprocess.run([sys.executable, '-B', '-c', program], cwd=HERE, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('REMAINING_PEER_WINDOW_ACTED', result.stdout)

    def test_cli_rejects_invalid_elapsed_budget(self):
        with tempfile.TemporaryDirectory() as home:
            for value in ('-1','nan','inf','-inf'):
                result = subprocess.run([sys.executable, str(HERE/'sweep.py'), '--sims-seconds='+value],
                                        cwd=HERE, env=dict(os.environ, SURFD_HOME=home,
                                        SURFD_DB=str(Path(home)/'test.db'), SURFD_ENV=str(Path(home)/'empty.env')),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn('--sims-seconds must be finite and nonnegative', result.stderr)

    def test_cli_rejects_negative_pair_budget(self):
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run([sys.executable, str(HERE/'sweep.py'), '--sims-pairs','-1'],
                                    cwd=HERE, env=dict(os.environ, SURFD_HOME=home,
                                    SURFD_DB=str(Path(home)/'test.db'), SURFD_ENV=str(Path(home)/'empty.env')),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('--sims-pairs must be nonnegative', result.stderr)


if __name__ == '__main__':
    unittest.main()
