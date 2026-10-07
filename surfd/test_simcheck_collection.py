"""Collector diagnostics controls: temporary SQLite only, no player data."""
import importlib.util
from pathlib import Path
import sqlite3
import unittest

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


if __name__ == '__main__':
    unittest.main()
