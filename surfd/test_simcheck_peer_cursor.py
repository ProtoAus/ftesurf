"""Per-source peer admission survives faults/restarts without inventing evidence."""
import sqlite3
import unittest
from unittest import mock

import simcheck
import test_simcheck_source_cursor as fixture


class PeerCursorTests(fixture.SourceCursorTests):
    def setUp(self):
        super().setUp()
        self.attempted = []

    def faulty_compare(self, a, b, **limits):
        self.assertFalse(self.conn.in_transaction)
        self.attempted.append((a, b))
        if b == 2:
            raise RuntimeError('synthetic peer exception')
        return self.compare(a, b, **limits)

    def peer_cursor(self, source=1):
        row = self.conn.execute("SELECT after_id FROM sim_cursor"
                                " WHERE scope='peer' AND source_id=?", (source,)).fetchone()
        return row[0] if row else 0

    def direct(self, source=1, peers=200, budget=None):
        row = self.conn.execute('SELECT * FROM replays WHERE id=?', (source,)).fetchone()
        if budget is None:
            budget = simcheck._PairBudget(1, 1.)
        with mock.patch.object(simcheck, '_recsim', return_value=(self.mod, 'fake')):
            try:
                return simcheck.compare_run(self.surfd, self.conn, row,
                                            limit_peers=peers, budget=budget)[0]
            except RuntimeError:
                return 0  # inspect progress/evidence independently of later fault isolation

    def add_four(self):
        for i in range(1, 5):
            self.add(i)
        self.mod.compare_paths = self.faulty_compare

    def test_failed_first_peer_rotates_past_one_candidate_window_and_wraps(self):
        self.add_four()
        stored = []
        for _ in range(4):
            stored.append(self.direct(peers=1))
            self.restart()
        self.assertEqual(stored, [0, 1, 1, 0])
        self.assertEqual(self.attempted, [(1, 2), (1, 3), (1, 4), (1, 2)])
        self.assertEqual(self.peer_cursor(), 2)
        self.assertEqual(self.cursor(), 0)  # direct peers don't advance global sources
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 2)
        self.assertIsNone(self.conn.execute('SELECT id FROM sims WHERE a_id=1 AND b_id=2').fetchone())

    def test_fault_admission_consumes_one_attempt_and_checkpoints_once(self):
        self.add_four()
        budget = simcheck._PairBudget(1, 1.)
        self.assertEqual(self.direct(budget=budget), 0)
        self.assertEqual((budget.attempted, budget.remaining), (1, 0))
        self.assertEqual(self.attempted, [(1, 2)])
        self.assertEqual(self.peer_cursor(), 2)
        self.assertFalse(self.conn.in_transaction)
        self.assertEqual(self.direct(), 1)
        self.assertEqual(self.attempted[-1], (1, 3))  # positive next peer ACTED

    def test_peer_cursors_are_independent_for_each_source(self):
        self.add_four()
        self.direct(1)
        self.assertEqual(self.direct(2), 1)
        self.assertEqual((self.peer_cursor(1), self.peer_cursor(2)), (2, 1))
        self.assertEqual(self.direct(1), 1)
        self.assertEqual(self.attempted[-1], (1, 3))

    def test_zero_expired_and_missing_primary_do_not_advance_peer_cursor(self):
        self.add_four()
        self.assertEqual(self.direct(budget=simcheck._PairBudget(0, 1.)), 0)
        self.assertEqual(self.direct(budget=simcheck._PairBudget(1, 0.)), 0)
        self.assertEqual(self.attempted, [])
        self.assertEqual(self.peer_cursor(), 0)
        self.direct()
        self.assertEqual(self.peer_cursor(), 2)
        self.surfd.replay_file = self.unavailable
        self.assertEqual(self.direct(), 0)
        self.assertEqual(self.peer_cursor(), 2)
        self.assertEqual(self.attempted, [(1, 2)])

    def test_completed_source_does_not_resolve_or_advance(self):
        self.add_four()
        self.direct()
        for i in range(2, 5):
            self.seed(1, i, 'skip')
        self.resolved.clear()
        self.assertEqual(self.direct(), 0)
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.peer_cursor(), 2)

    def test_one_checkpoint_after_multiple_comparisons_with_writer_control(self):
        self.add_four()
        self.conn.execute('CREATE TABLE writer_probe(n INTEGER)')
        self.conn.commit()
        statements = []
        self.conn.set_trace_callback(statements.append)

        def compare(a, b, **limits):
            self.assertFalse(self.conn.in_transaction)
            other = sqlite3.connect(self.db, timeout=0.2)
            try:
                other.execute('INSERT INTO writer_probe VALUES(?)', (b,))
                other.commit()  # an independent writer ACTS during comparison
            finally:
                other.close()
            return self.compare(a, b, **limits)

        self.mod.compare_paths = compare
        self.assertEqual(self.direct(budget=simcheck._PairBudget(3, 1.)), 3)
        self.assertEqual(len(self.compared), 3)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM writer_probe').fetchone()[0], 3)
        self.assertEqual(sum('INSERT INTO sim_cursor' in sql for sql in statements), 1)
        self.assertEqual(self.peer_cursor(), 4)

    def test_historical_direct_caller_initializes_state_only_after_admission(self):
        self.add_four()
        self.conn.execute('DROP TABLE sim_cursor')

        def compare(a, b, **limits):
            self.assertIsNone(self.conn.execute(
                "SELECT name FROM sqlite_master WHERE name='sim_cursor'").fetchone())
            return self.compare(a, b, **limits)

        self.mod.compare_paths = compare
        self.assertEqual(self.direct(budget=simcheck._PairBudget(0, 1.)), 0)
        self.assertIsNone(self.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='sim_cursor'").fetchone())
        self.assertEqual(self.direct(), 1)
        self.assertEqual(self.compared, [(1, 2)])
        self.assertEqual(self.peer_cursor(), 2)
        self.assertEqual(self.cursor(), 0)

    def test_late_stored_pair_recheck_costs_no_admission_or_cursor(self):
        self.add_four()
        original = self.surfd.replay_file

        def path(row):
            if row['id'] == 1:
                self.seed(1, 2, 'skip')  # ACT after candidate selection
            return original(row)

        self.surfd.replay_file = path
        budget = simcheck._PairBudget(1, 1.)
        self.assertEqual(self.direct(budget=budget), 1)
        self.assertEqual(self.attempted, [(1, 3)])
        self.assertEqual(budget.attempted, 1)
        self.assertEqual(self.peer_cursor(), 3)


if __name__ == '__main__':
    unittest.main()
