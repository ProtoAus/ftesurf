"""Atomic peer admission/observations; real SQLite rollback and bounded reader."""
import os
import sqlite3
from types import SimpleNamespace
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('atomic_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


class AtomicFlush(unittest.TestCase):
    setUp = fixture.StoredSources.setUp
    run_source = fixture.StoredSources.run_source

    def peer_cursor(self, conn=None):
        conn = conn or self.conn
        row = conn.execute("SELECT after_id FROM sim_cursor WHERE scope='peer' AND source_id=1").fetchone()
        return row[0] if row else None

    def test_insert_abort_rolls_back_existing_cursor_and_all_new_observations(self):
        sc._advance(self.conn, 'peer', 99, 1)
        inserted = []
        self.conn.create_function('flush_probe', 1, lambda b: inserted.append(b) or 0)
        self.conn.executescript('''
            CREATE TRIGGER stop BEFORE INSERT ON sims BEGIN
                SELECT flush_probe(NEW.b_id);
                SELECT CASE WHEN NEW.b_id=3 THEN RAISE(ABORT,'synthetic rollback') END;
            END;
        ''')
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_source(max_pairs=2)
        self.assertEqual(inserted, [2, 3])  # first insertion genuinely preceded abort
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)
        self.assertFalse(self.conn.in_transaction)
        self.assertEqual(self.peer_cursor(), 99)
        with sqlite3.connect(self.db) as reopened:
            self.assertEqual(self.peer_cursor(reopened), 99)
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_cursor_write_abort_cannot_commit_observations(self):
        sc._advance(self.conn, 'peer', 99, 1)
        checkpoints = []
        self.conn.create_function('cursor_probe', 1, lambda n: checkpoints.append(n) or 0)
        self.conn.executescript('''
            CREATE TRIGGER stop_cursor BEFORE UPDATE ON sim_cursor BEGIN
                SELECT cursor_probe(NEW.after_id);
                SELECT RAISE(ABORT,'synthetic cursor fault');
            END;
        ''')
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_source(max_pairs=2)
        self.assertEqual(checkpoints, [3])
        self.assertEqual(self.peer_cursor(), 99)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)
        self.assertFalse(self.conn.in_transaction)

    def test_normal_flush_and_cursor_share_transaction_without_file_write_lock(self):
        transactions = []
        self.conn.set_trace_callback(transactions.append)
        compared = []
        def compare(a, b, **kw):
            self.assertFalse(self.conn.in_transaction)
            with sqlite3.connect(self.db) as writer:
                writer.execute('INSERT INTO probe VALUES (1)')
            verdict, metrics = fixture.rs.compare_paths(a, b, **kw)
            compared.append(metrics['compared'])
            return verdict, metrics
        self.assertEqual(self.run_source(reader=SimpleNamespace(compare_paths=compare), max_pairs=2), (2, 0, 2))
        self.assertEqual(compared, [80, 80])
        self.assertEqual(self.peer_cursor(), 3)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 2)
        self.assertEqual(sum(t.upper().startswith('BEGIN') for t in transactions), 1)
        self.assertEqual(sum(t.upper() == 'COMMIT' for t in transactions), 1)
        with sqlite3.connect(self.db) as reopened:
            self.assertEqual(self.peer_cursor(reopened), 3)
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 2)

    def test_all_failed_pairs_rotate_without_observations(self):
        attempts = []
        def fail(a, b, **kw):
            self.assertFalse(self.conn.in_transaction)
            attempts.append(b)
            raise RuntimeError('synthetic unavailable')
        self.assertEqual(self.run_source(reader=SimpleNamespace(compare_paths=fail), max_pairs=2), (0, 0, 0))
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.peer_cursor(), 3)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)

    def test_legacy_direct_call_initializes_cursor_only_on_actual_admission(self):
        self.conn.execute('DROP TABLE sim_cursor'); self.conn.commit()
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        with mock.patch.object(sc, '_recsim', return_value=(fixture.rs, '')):
            self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=0), (0, 0, 0))
            self.assertIsNone(self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='sim_cursor'").fetchone())
            self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=1), (1, 0, 1))
        self.assertEqual(self.peer_cursor(), 2)


if __name__ == '__main__':
    unittest.main()
