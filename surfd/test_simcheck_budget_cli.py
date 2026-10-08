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
