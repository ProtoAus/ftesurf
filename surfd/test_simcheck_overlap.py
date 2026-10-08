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

    def test_trigger_changes_do_not_inflate_insert_count(self):
        self.conn.executescript('''CREATE TRIGGER count_noise AFTER INSERT ON sims BEGIN
            INSERT INTO probe VALUES(1); INSERT INTO probe VALUES(2); END;''')
        self.assertEqual(self.run_source(max_pairs=2), (2,0,2))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 4)
        self.assertEqual(self.peer_cursor(), 3)


if __name__ == '__main__': unittest.main()
