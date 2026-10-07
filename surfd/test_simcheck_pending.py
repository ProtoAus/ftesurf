"""Stored pairs suppress only themselves, not unobserved peers (SQLite only)."""
import sqlite3
import unittest
from types import SimpleNamespace
from unittest import mock

import simcheck


class PendingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            CREATE TABLE replays(id INTEGER PRIMARY KEY, kind TEXT, map TEXT,
                                 track INTEGER, leg INTEGER, leaf TEXT,
                                 tier TEXT, player TEXT);
        ''')
        simcheck.ensure_schema(self.conn)
        self.mod = SimpleNamespace(BOUNDED_INPUT_VERSION=1,
                                   compare_paths=self.compare)
        self.surfd = SimpleNamespace(replay_file=self.path)
        self.resolved = []
        self.compared = []

    def tearDown(self):
        self.conn.close()

    def add(self, i, kind='run', map_name='m', track=0, leg=0):
        self.conn.execute('INSERT INTO replays VALUES(?,?,?,?,?,?,?,?)',
                          (i, kind, map_name, track, leg, str(i), '', 'p'))
        self.conn.commit()

    def seed(self, a, b, verdict='compared'):
        a, b = sorted((a, b))
        self.conn.execute('INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at)'
                          ' VALUES(?,?,?,0,0,?,0)', (a, b, 'm', verdict))
        self.conn.commit()

    def path(self, row):
        self.resolved.append(row['id'])
        return row['id'], ''

    def compare(self, a, b, **limits):
        self.compared.append((a, b))
        return 'compared', {'compared': 1, 'match': 1., 'cover': 1.,
                            'prefix': 1, 'offset': 0, 'moves_a': 80,
                            'moves_b': 80, 'tickrate_a': 100, 'tickrate_b': 100,
                            'who_a': 'a', 'who_b': 'b', 'same_who': False}

    def pending_ids(self, limit=50):
        return [r['id'] for r in simcheck.pending(self.conn, limit)]

    def step(self, pairs=1):
        with mock.patch.object(simcheck, '_recsim', return_value=(self.mod, 'fake')):
            return simcheck.similarity_step(self.conn, self.surfd, limit=1,
                                           max_pairs=pairs, max_seconds=0.5)

    def test_budgeted_passes_finish_all_six_pairs(self):
        for i in range(1, 5):
            self.add(i)
        stored = [self.step()[0] for _ in range(6)]
        self.assertEqual(stored, [1] * 6)
        self.assertEqual(set(self.compared),
                         {(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)})
        self.assertEqual(len(self.resolved), 12)  # both paths ACTED each pass
        self.assertEqual(self.pending_ids(), [])
        self.assertEqual(self.step(), (0, 0, ''))
        self.assertEqual(len(self.resolved), 12)  # completed sample stays idle

    def test_partial_primary_remains_pending_oldest_first(self):
        for i in range(1, 4):
            self.add(i)
        self.seed(1, 2)
        self.assertEqual(self.pending_ids(1), [1])
        self.assertEqual(self.pending_ids(), [1, 2, 3])

    def test_complete_primary_is_not_pending_but_peers_are(self):
        for i in range(1, 4):
            self.add(i)
        self.seed(1, 2)
        self.seed(1, 3)
        self.assertEqual(self.pending_ids(), [2, 3])

    def test_skip_suppresses_only_that_pair(self):
        for i in range(1, 4):
            self.add(i)
        self.seed(1, 2, 'skip')
        self.assertEqual(self.pending_ids(1), [1])
        self.assertEqual(self.step()[0], 1)
        self.assertEqual(self.compared, [(1, 3)])
        self.assertEqual(self.conn.execute(
            'SELECT verdict FROM sims WHERE a_id=1 AND b_id=2').fetchone()[0], 'skip')

    def test_mismatched_and_non_run_peers_do_not_make_primary_pending(self):
        self.add(1)
        self.add(2, kind='momentum')
        self.add(3, map_name='other')
        self.add(4, track=1)
        self.add(5, leg=1)
        self.assertEqual(self.pending_ids(), [])
        self.assertEqual(self.step(), (0, 0, ''))
        self.assertEqual(self.resolved, [])
        self.add(6)
        self.assertEqual(self.step()[0], 1)
        self.assertEqual(self.compared, [(1, 6)])  # positive native control ACTED
        self.assertEqual(self.pending_ids(), [])

    def test_pending_requires_schema_as_before(self):
        self.conn.execute('DROP TABLE sims')
        with self.assertRaises(sqlite3.OperationalError):
            self.pending_ids()
        self.assertIsNone(self.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='sims'").fetchone())


if __name__ == '__main__':
    unittest.main()
