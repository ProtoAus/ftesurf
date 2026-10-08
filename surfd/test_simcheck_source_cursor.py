"""Durable source admission progress, not stored comparison evidence."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import simcheck
import test_simcheck_pending as fixture


class SourceCursorTests(fixture.PendingTests):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory(prefix='sim-source-cursor-')
        self.db = Path(self.temp.name) / 'sample.db'
        target = sqlite3.connect(self.db)
        self.conn.backup(target)
        self.conn.close()
        self.conn = target
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        super().tearDown()
        self.temp.cleanup()

    def restart(self):
        self.conn.close()
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row

    def cursor(self):
        if not self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='sim_cursor'").fetchone():
            return 0
        row = self.conn.execute("SELECT after_id FROM sim_cursor"
                                " WHERE scope='source' AND source_id=0").fetchone()
        return row[0] if row else 0

    def unavailable(self, row):
        self.assertFalse(self.conn.in_transaction)
        self.resolved.append(row['id'])
        return None, 'unavailable'

    def test_unavailable_sources_rotate_across_restarts_and_wrap(self):
        for i in range(1, 4):
            self.add(i)
        self.surfd.replay_file = self.unavailable
        for _ in range(4):
            self.assertEqual(self.step()[0], 0)
            self.restart()
        self.assertEqual(self.resolved, [1, 2, 3, 1])
        self.assertEqual(self.cursor(), 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_old_unresolved_source_does_not_hide_later_measurable_pair(self):
        for i in range(1, 4):
            self.add(i)
        original = self.surfd.replay_file

        def path(row):
            return self.unavailable(row) if row['id'] == 1 else original(row)

        self.surfd.replay_file = path
        self.assertEqual(self.step()[0], 0)
        self.restart()
        self.assertEqual(self.step(pairs=2)[0], 2)
        self.assertEqual(self.compared, [(2, 3)])
        self.assertEqual(self.resolved, [1, 2, 1, 3])
        # Peer1 is a stored unavailability, not a measured zero comparison.
        self.assertEqual(simcheck.summary(self.conn)['compared'], 1)

    def test_row_exception_still_rotates_without_fabricated_observation(self):
        for i in range(1, 4):
            self.add(i)
        attempted = []

        def fail(surfd, conn, row, **kwargs):
            attempted.append(row['id'])
            self.assertFalse(conn.in_transaction)
            raise RuntimeError('synthetic row error')

        with mock.patch.object(simcheck, 'compare_run', side_effect=fail):
            for _ in range(3):
                self.assertIn('1 row failed', self.step()[2])
                self.restart()
        self.assertEqual(attempted, [1, 2, 3])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_disabled_steps_do_not_import_or_advance(self):
        for i in range(1, 4):
            self.add(i)
        before = tuple(self.conn.iterdump())
        with mock.patch.object(simcheck, '_recsim', side_effect=AssertionError('disabled import')):
            for options in ({'limit': 0}, {'max_pairs': 0}, {'max_seconds': 0}):
                self.assertEqual(simcheck.similarity_step(self.conn, self.surfd, **options),
                                 (0, 0, ''))
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertEqual(self.cursor(), 0)

    def test_loader_exhausted_deadline_admits_no_source(self):
        for i in range(1, 4):
            self.add(i)
        clock = [0.]

        def load(*args):
            clock[0] = 2.
            return self.mod, 'fake'

        with mock.patch.object(simcheck.time, 'monotonic', side_effect=lambda: clock[0]), \
             mock.patch.object(simcheck, '_recsim', side_effect=load):
            out = simcheck.similarity_step(self.conn, self.surfd, max_seconds=1.)
        self.assertIn('time limit reached', out[2])
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.cursor(), 0)

    def test_read_only_old_schema_does_not_create_or_advance_state(self):
        for i in range(1, 4):
            self.add(i)
        self.seed(1, 2)
        self.conn.execute('DROP TABLE IF EXISTS sim_cursor')
        before = tuple(self.conn.iterdump())
        self.assertEqual(self.pending_ids(), [1, 2, 3])
        self.assertEqual(simcheck.summary(self.conn)['pairs'], 1)
        self.assertEqual(tuple(self.conn.iterdump()), before)
        simcheck.ensure_schema(self.conn)
        self.assertEqual(simcheck.summary(self.conn)['pairs'], 1)
        after = tuple(self.conn.iterdump())
        self.pending_ids()
        simcheck.summary(self.conn)
        self.assertEqual(tuple(self.conn.iterdump()), after)
        self.assertEqual(self.cursor(), 0)

    def test_removed_cursor_source_wraps_to_existing_eligible_rows(self):
        for i in range(1, 4):
            self.add(i)
        self.surfd.replay_file = self.unavailable
        for _ in range(3):
            self.step()
        self.conn.execute('DELETE FROM replays WHERE id=3')
        self.conn.commit()
        self.restart()
        self.step()
        self.assertEqual(self.resolved, [1, 2, 3, 1])
        self.assertEqual(self.cursor(), 1)


if __name__ == '__main__':
    unittest.main()
