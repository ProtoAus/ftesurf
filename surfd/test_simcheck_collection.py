"""Collector diagnostics controls: temporary SQLite only, no player data."""
import importlib.util
from pathlib import Path
import sqlite3
import inspect
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('collector_subject', Path(__file__).with_name('simcheck.py'))
simcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simcheck)


class SummaryAvailability(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def test_missing_is_unavailable_not_empty(self):
        result = simcheck.summary(self.conn)
        self.assertEqual(result.get('state'), 'missing')
        self.assertIsNone(result['pairs'])
        self.assertIn('unavailable', simcheck.summary_line(self.conn))
        self.assertIn('missing', simcheck.summary_line(self.conn))
        self.assertFalse(self.conn.execute("SELECT name FROM sqlite_master WHERE name='sims'").fetchone())

    def test_empty_is_measured_zero_and_printed(self):
        simcheck.ensure_schema(self.conn)
        result = simcheck.summary(self.conn)
        self.assertEqual(result.get('state'), 'empty')
        self.assertEqual(result['pairs'], 0)
        self.assertEqual(simcheck.summary_line(self.conn), 'sims: no pairs stored yet')

    def test_query_error_is_unavailable_not_zero(self):
        simcheck.ensure_schema(self.conn)
        denied = []
        def guard(action, table, column, db, source):
            if action == sqlite3.SQLITE_READ and table == 'sims':
                denied.append(column)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.conn.set_authorizer(guard)
        result = simcheck.summary(self.conn)
        self.assertTrue(denied)  # refusal ACTED; not a dormant error stub
        self.assertEqual(result.get('state'), 'error')
        self.assertIsNone(result['pairs'])
        self.assertEqual(simcheck.summary_line(self.conn), 'sims: unavailable (query error)')
        self.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_nonempty_control_preserves_identity_split(self):
        simcheck.ensure_schema(self.conn)
        for a, b, verdict, match, same, wa, wb in (
                (1,2,'compared',1.0,1,'a','a'),
                (1,3,'compared',0.2,0,'a','b'),
                (1,4,'compared',0.0,0,'',''),
                (1,5,'skip',0.0,0,'','')):
            self.conn.execute('INSERT INTO sims (a_id,b_id,map,track,leg,verdict,match,same_who,who_a,who_b,at) VALUES (?,?,\'synthetic\',0,0,?,?,?,?,?,1)',
                              (a,b,verdict,match,same,wa,wb))
        self.conn.commit()
        result = simcheck.summary(self.conn)
        self.assertEqual(result.get('state'), 'available')
        self.assertEqual((result['pairs'],result['compared'],result['skipped'],result['notable']), (4,3,1,1))
        self.assertEqual((result['same_n'],result['cross_n'],result['unknown_n']), (1,1,1))
        self.assertEqual((result['same_max'],result['cross_max'],result['unknown_max']), (1.0,0.2,0.0))
        self.assertIn('4 pairs, 3 compared, 1 unjudgeable', simcheck.summary_line(self.conn))


class CollectorAvailability(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        simcheck.ensure_schema(self.conn)
        self.conn.execute('CREATE TABLE replays (id INTEGER PRIMARY KEY, map TEXT, track INTEGER, leg INTEGER, kind TEXT, tier TEXT, player TEXT)')
        for i in range(1, 4):
            self.conn.execute("INSERT INTO replays VALUES (?, 'synthetic', 0, 0, 'run', 'ranked', 'synthetic')", (i,))
        self.conn.commit()
        self.resolved = []
        self.compared = []
        self.surfd = mock.Mock()
        self.surfd.replay_file.side_effect = self.resolve
        self.reader = mock.Mock()
        self.reader.compare_paths.side_effect = self.compare
        patcher = mock.patch.object(simcheck, '_recsim', return_value=(self.reader, 'synthetic'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def resolve(self, row):
        self.resolved.append(row['id'])
        return str(row['id']), ''

    def compare(self, a, b, **kw):
        self.assertFalse(self.conn.in_transaction)
        self.compared.append((a, b))
        return 'compared', dict(match=1.0, cover=1.0, prefix=80, offset=0,
                                compared=80, moves_a=80, moves_b=80,
                                tickrate_a=100.0, tickrate_b=100.0,
                                who_a='', who_b='', same_who=False)

    def test_unresolved_primary_is_counted_without_fake_pairs(self):
        self.surfd.replay_file.side_effect = lambda row: (self.resolved.append(row['id']) or None, 'private path not exposed')
        stored, notable, note = simcheck.similarity_step(self.conn, self.surfd)
        self.assertEqual(self.resolved, [1,2,3])
        self.assertEqual((stored, notable, self.compared), (0,0,[]))
        self.assertIn('3 source unavailable', note)
        self.assertNotIn('private', note)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_row_failure_is_counted_and_later_rows_act(self):
        def failing(a, b, **kw):
            if a == '1':
                self.compared.append((a, b))
                raise RuntimeError('synthetic failure')
            return self.compare(a, b)
        self.reader.compare_paths.side_effect = failing
        stored, notable, note = simcheck.similarity_step(self.conn, self.surfd)
        self.assertIn(('1', '2'), self.compared)
        self.assertGreater(stored, 0)
        self.assertGreater(notable, 0)
        self.assertIn('1 row failed', note)
        self.assertNotIn('synthetic failure', note)
        self.assertEqual(self.conn.execute("SELECT MIN(compared) FROM sims WHERE verdict='compared'").fetchone()[0], 80)

    def test_all_row_failures_still_report_when_nothing_stored(self):
        def failing(a, b, **kw):
            self.compared.append((a, b))
            raise RuntimeError('synthetic failure')
        self.reader.compare_paths.side_effect = failing
        stored, notable, note = simcheck.similarity_step(self.conn, self.surfd)
        self.assertEqual(len(self.compared), 3)
        self.assertEqual((stored, notable), (0,0))
        self.assertIn('3 row failed', note)

    def test_normal_control_has_no_unavailable_note(self):
        stored, notable, note = simcheck.similarity_step(self.conn, self.surfd)
        self.assertEqual((stored, notable, len(self.compared)), (3,3,3))
        self.assertEqual(note, 'sims +3')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 3)


class PairBudget(CollectorAvailability):
    def step(self, budget, limit=50):
        # The same work ACTS on the predecessor; its absent budget API does not
        # turn the falsifier into just an unexpected-keyword test.
        kw = {'max_pairs': budget} if 'max_pairs' in inspect.signature(simcheck.similarity_step).parameters else {}
        return simcheck.similarity_step(self.conn, self.surfd, limit=limit, **kw)

    def test_aggregate_cap_flushes_then_second_pass_acts(self):
        stored, notable, note = self.step(1)
        self.assertEqual((stored, notable, len(self.compared)), (1,1,1))
        self.assertEqual([(r['a_id'],r['b_id']) for r in self.conn.execute('SELECT * FROM sims')], [(1,2)])
        self.assertIn('pair limit reached', note)
        self.compared.clear()
        stored, notable, note = self.step(1)
        self.assertEqual((stored, notable, len(self.compared)), (1,1,1))
        self.assertEqual(self.compared, [('2','3')])  # next source's admission turn
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 2)
        # No complete-pair scheduling claim: current pending semantics remain.

    def test_unresolved_peer_consumes_attempt(self):
        def resolve(row):
            self.resolved.append(row['id'])
            return (None,'unresolved') if row['id'] == 2 else (str(row['id']),'')
        self.surfd.replay_file.side_effect = resolve
        stored, notable, note = self.step(1)
        self.assertEqual((stored, notable, self.compared), (1,0,[]))
        self.assertEqual(self.resolved, [1,2])
        self.assertEqual(self.conn.execute('SELECT verdict FROM sims').fetchone()[0], 'skip')
        self.assertIn('pair limit reached', note)

    def test_exception_consumes_attempt_and_cannot_overrun(self):
        def failing(a,b, **kw):
            self.compared.append((a,b))
            raise RuntimeError('synthetic failure')
        self.reader.compare_paths.side_effect = failing
        stored, notable, note = self.step(1)
        self.assertEqual((stored, notable, len(self.compared)), (0,0,1))
        self.assertIn('1 row failed', note)
        self.assertIn('pair limit reached', note)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_zero_budget_is_import_free_and_quiet(self):
        with mock.patch.object(simcheck, '_recsim', return_value=(self.reader, 'synthetic')) as loader:
            self.assertEqual(self.step(0), (0,0,''))
        loader.assert_not_called()
        self.assertEqual(self.resolved, [])

    def test_under_budget_real_comparison_retains_metrics(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for i in range(1,4):
            rows = ['FTESURF-REC 9','map synthetic','track 0','leg 0','tickrate 100','begin']
            rows += ['in %d %d 0 %d 0 0 0 0 0 4' % (j,j,100+j%7) for j in range(80)]
            rows += ['end 80']
            (root/('%d.rec'%i)).write_text('\n'.join(rows)+'\n')
        spec = importlib.util.spec_from_file_location('budget_reader', Path(__file__).resolve().parents[1]/'tools'/'census'/'recsim.py')
        rs = importlib.util.module_from_spec(spec);spec.loader.exec_module(rs)
        calls = []
        def real(a,b, **kw):
            calls.append((a,b))
            self.assertFalse(self.conn.in_transaction)
            return rs.compare_paths(a,b, **kw)
        self.reader.compare_paths.side_effect = real
        self.surfd.replay_file.side_effect = lambda row: (str(root/('%d.rec'%row['id'])), '')
        stored, notable, note = self.step(4)
        self.assertEqual((stored, notable, len(calls)), (3,3,3))
        self.assertEqual(note, 'sims +3')
        self.assertEqual([tuple(r) for r in self.conn.execute('SELECT match,compared FROM sims')], [(1.0,80)]*3)


if __name__ == '__main__':
    unittest.main()
