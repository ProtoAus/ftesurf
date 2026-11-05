"""Report inserted observations, not comparisons lost to same-key overlap."""
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import unittest

import test_simcheck_atomic_flush as fixture

sc = fixture.sc


class Overlap(fixture.AtomicFlush):
    def overlap(self, peers, skip=False):
        acted = []
        def compare(a, b, **limits):
            self.assertFalse(self.conn.in_transaction)
            peer = int(Path(b).stem)
            verdict, metrics = fixture.fixture.rs.compare_paths(a, b, **limits)
            self.assertEqual((verdict, metrics['compared']), ('compared',80))
            if peer in peers:
                with closing(sqlite3.connect(self.db)) as writer:
                    with writer:
                        writer.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at)"
                                       " VALUES(1,?,'synthetic',0,0,'skip',123)", (peer,))
                    self.assertEqual(writer.execute('SELECT at FROM sims WHERE b_id=?',
                                                    (peer,)).fetchone()[0], 123)
                acted.append(peer)
            if skip and peer in peers:
                return 'too short', 'synthetic skip'
            return verdict, metrics
        out = self.run_source(reader=SimpleNamespace(compare_paths=compare), max_pairs=2)
        self.assertEqual(acted, list(peers))
        self.assertEqual(self.peer_cursor(), 3)
        self.assertFalse(self.conn.in_transaction)
        with closing(sqlite3.connect(self.db)) as reopened:
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 2)
            for peer in peers:
                self.assertEqual(reopened.execute('SELECT verdict,at FROM sims WHERE b_id=?',
                                                  (peer,)).fetchone(), ('skip',123))
        return out

    def test_competing_notable_comparison_is_not_a_new_addition(self):
        self.assertEqual(self.overlap((2,)), (1,0,1))

    def test_ignored_skip_is_not_counted_as_new_unjudgeable(self):
        self.assertEqual(self.overlap((2,), skip=True), (1,0,1))

    def test_all_ignored_still_checkpoint_admission_but_add_zero(self):
        self.assertEqual(self.overlap((2,3)), (0,0,0))

    def reverse_overlap(self, peers, skip=False):
        acted = []
        winners = {}
        def compare(a, b, **limits):
            self.assertFalse(self.conn.in_transaction)
            peer = int(Path(b).stem)
            verdict, metrics = fixture.fixture.rs.compare_paths(a, b, **limits)
            self.assertEqual((verdict, metrics['compared']), ('compared', 80))
            if peer in peers:
                if skip:
                    self.paths[peer].write_bytes(fixture.fixture.source(9))
                with closing(sqlite3.connect(self.db)) as writer:
                    writer.row_factory = sqlite3.Row
                    def reverse_compare(a, b, **limits):
                        self.assertFalse(writer.in_transaction)
                        value = fixture.fixture.rs.compare_paths(a, b, **limits)
                        if skip:
                            self.assertEqual(value[0], 'too short')
                        else:
                            self.assertEqual((value[0], value[1]['compared']),
                                             ('compared', 80))
                        return value
                    row = writer.execute('SELECT * FROM replays WHERE id=?',
                                         (peer,)).fetchone()
                    result = sc.compare_run(self.sf, writer, row, limit_peers=1,
                        reader=SimpleNamespace(compare_paths=reverse_compare))
                    self.assertEqual(result, (1, 1, 0) if skip else (1, 0, 1))
                    winners[peer] = dict(writer.execute(
                        'SELECT * FROM sims WHERE a_id=? AND b_id=1',
                        (peer,)).fetchone())
                    self.assertFalse(writer.in_transaction)
                acted.append(peer)
            return verdict, metrics
        out = self.run_source(reader=SimpleNamespace(compare_paths=compare), max_pairs=2)
        self.assertEqual(acted, list(peers))
        self.assertEqual(self.peer_cursor(), 3)
        self.assertFalse(self.conn.in_transaction)
        with closing(sqlite3.connect(self.db)) as reopened:
            reopened.row_factory = sqlite3.Row
            rows = reopened.execute('SELECT * FROM sims').fetchall()
            self.assertEqual(len(rows), 2,
                {'result': out, 'orientations': [(r['a_id'], r['b_id']) for r in rows]})
            for peer, winner in winners.items():
                self.assertEqual(dict(reopened.execute(
                    'SELECT * FROM sims WHERE a_id=? AND b_id=1',
                    (peer,)).fetchone()), winner)
                self.assertIsNone(reopened.execute(
                    'SELECT 1 FROM sims WHERE a_id=1 AND b_id=?',
                    (peer,)).fetchone())
        return out

    def test_reverse_collector_wins_without_duplicate_observation(self):
        self.assertEqual(self.reverse_overlap((2,)), (1, 0, 1))

    def test_reverse_skip_is_not_overwritten_or_counted_as_own_skip(self):
        self.assertEqual(self.reverse_overlap((2,), skip=True), (1, 0, 1))

    def test_all_reverse_winners_checkpoint_but_add_nothing(self):
        self.assertEqual(self.reverse_overlap((2, 3)), (0, 0, 0))

    def test_legacy_reverse_duplicates_are_not_rewritten_or_deduplicated(self):
        with self.conn:
            for a, b in [(1, 2), (2, 1)]:
                self.conn.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,reason,at)"
                                  " VALUES(?,?,'synthetic',0,0,'skip','historical',123)",
                                  (a, b))
        before = [dict(row) for row in self.conn.execute('SELECT * FROM sims ORDER BY id')]
        self.assertEqual(self.run_source(max_pairs=2), (1, 0, 1))
        self.assertEqual([dict(row) for row in self.conn.execute(
            'SELECT * FROM sims ORDER BY id LIMIT 2')], before)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 3)

    def test_autocommit_connection_still_rolls_back_the_whole_flush(self):
        self.conn.isolation_level = None
        self.test_insert_abort_rolls_back_existing_cursor_and_all_new_observations()

    def test_autocommit_connection_owns_one_short_flush_transaction(self):
        self.conn.isolation_level = None
        self.test_normal_flush_and_cursor_share_transaction_without_file_write_lock()

    def test_reader_opened_caller_transaction_is_not_borrowed_or_committed(self):
        sc._advance(self.conn, 'peer', 99, 1)
        acted = []
        def compare(a, b, **limits):
            self.assertFalse(self.conn.in_transaction)
            value = fixture.fixture.rs.compare_paths(a, b, **limits)
            self.assertEqual((value[0], value[1]['compared']), ('compared', 80))
            self.conn.execute('INSERT INTO probe VALUES(7)')
            acted.append(True)
            return value
        try:
            with self.assertRaises(ValueError):
                self.run_source(reader=SimpleNamespace(compare_paths=compare), max_pairs=1)
            self.assertEqual(acted, [True])
            self.assertTrue(self.conn.in_transaction)
            self.assertEqual(self.conn.execute('SELECT n FROM probe').fetchall()[0][0], 7)
            self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)
            self.assertEqual(self.peer_cursor(), 99)
        finally:
            self.conn.rollback()  # ONLY this fixture's caller-owned work

    def test_configured_write_isolation_is_preserved(self):
        for mode in ('IMMEDIATE', 'EXCLUSIVE'):
            with self.subTest(mode=mode):
                self.conn.isolation_level = mode
                statements = []
                self.conn.set_trace_callback(statements.append)
                self.assertEqual(self.run_source(max_pairs=1), (1, 0, 1))
                self.assertEqual([s.strip().upper() for s in statements
                                  if s.upper().startswith('BEGIN')], ['BEGIN ' + mode])
                self.assertFalse(self.conn.in_transaction)
        self.conn.set_trace_callback(None)

    def test_trigger_changes_do_not_inflate_insert_count(self):
        self.conn.executescript('''CREATE TRIGGER count_noise AFTER INSERT ON sims BEGIN
            INSERT INTO probe VALUES(1); INSERT INTO probe VALUES(2); END;''')
        self.assertEqual(self.run_source(max_pairs=2), (2,0,2))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 4)
        self.assertEqual(self.peer_cursor(), 3)


if __name__ == '__main__': unittest.main()
