"""Bounded orphan scheduling-state retirement; stored evidence is never GC'd."""
import os
import sqlite3
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('retirement_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


class CursorRetirement(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def step(self, **kw):
        with mock.patch.object(sc, '_recsim', return_value=(fixture.rs, 'fixture')):
            return sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=1, **kw)

    def peers(self):
        return dict(self.conn.execute("SELECT source_id,after_id FROM sim_cursor"
                                      " WHERE scope='peer'"))

    def orphan(self, *ids):
        with self.conn:
            self.conn.executemany("INSERT INTO sim_cursor VALUES('peer',?,17)",
                                  [(i,) for i in ids])

    def reopen(self):
        self.conn.close()
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def test_step_retires_orphan_while_real_comparison_acts(self):
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=1,
                                       reader=fixture.rs), (1, 0, 1))
        old = tuple(self.conn.execute('SELECT * FROM sims WHERE id=1').fetchone())
        replays = list(self.conn.execute('SELECT * FROM replays ORDER BY id'))
        self.orphan(999)
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.conn.execute('SELECT compared FROM sims ORDER BY id DESC LIMIT 1').fetchone()[0], 80)
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=1').fetchone()), old)
        self.assertEqual(list(self.conn.execute('SELECT * FROM replays ORDER BY id')), replays)
        self.assertNotIn(999, self.peers())
        self.assertIn(1, self.peers())

    def test_step_retirement_is_bounded_and_progresses_across_reopen(self):
        self.orphan(*range(100, 340))
        admitted = 0
        for _ in range(6):
            before = set(self.peers()) & set(range(100, 340))
            admitted += self.step()[0]
            after = set(self.peers()) & set(range(100, 340))
            self.assertLessEqual(len(before - after), 64)
            self.reopen()
        self.assertEqual(admitted, 3)
        self.assertEqual([r[0] for r in self.conn.execute('SELECT compared FROM sims')], [80] * 3)
        self.assertFalse(set(self.peers()) & set(range(100, 340)))

    def test_step_passes_live_window_without_erasing_live_positions(self):
        with self.conn:
            self.conn.executemany("INSERT INTO replays VALUES(?,'other',0,0,'tool','imported','synthetic')",
                                  [(i,) for i in range(100, 228)])
            self.conn.executemany("INSERT INTO sim_cursor VALUES('peer',?,77)",
                                  [(i,) for i in range(100, 228)])
        self.orphan(900)
        for _ in range(4):
            self.step()
            self.reopen()
        self.assertNotIn(900, self.peers())
        self.assertEqual({i: self.peers()[i] for i in range(100, 228)},
                         dict.fromkeys(range(100, 228), 77))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 3)

    def test_zero_negative_and_late_lower_ids_are_visited(self):
        self.orphan(-1, 0, 999)
        self.assertEqual(sc._retire_peer_cursors(self.conn, limit=2), 2)
        self.assertEqual(sc._retire_peer_cursors(self.conn, limit=2), 1)
        self.assertEqual(self.peers(), {})
        self.orphan(-10)
        self.assertEqual(sc._retire_peer_cursors(self.conn), 1)
        self.assertEqual(self.peers(), {})

    def test_scope_and_live_ineligible_source_positions_are_preserved(self):
        with self.conn:
            self.conn.execute("INSERT INTO replays VALUES(99,'other',0,0,'tool','imported','synthetic')")
            self.conn.executescript("INSERT INTO sim_cursor VALUES('source',0,123);"
                                    "INSERT INTO sim_cursor VALUES('source',1,456);"
                                    "INSERT INTO sim_cursor VALUES('peer',99,789);")
        old_replays = list(self.conn.execute('SELECT * FROM replays ORDER BY id'))
        self.orphan(999)
        self.assertEqual(sc._retire_peer_cursors(self.conn), 1)
        self.assertEqual(self.peers(), {99: 789})
        self.assertEqual(sc._cursor(self.conn, 'source'), 123)
        self.assertEqual(sc._cursor(self.conn, 'source', 1), 456)
        self.assertEqual(list(self.conn.execute('SELECT * FROM replays ORDER BY id')), old_replays)

    def test_default_cap_cannot_be_raised_by_internal_caller(self):
        self.orphan(*range(100, 300))
        self.assertEqual(sc._retire_peer_cursors(self.conn, limit=100000), 64)
        self.assertEqual(len(self.peers()), 136)

    def test_disabled_and_borrowed_step_never_retires_state(self):
        self.orphan(999)
        before = tuple(self.conn.iterdump())
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('disabled import')):
            for kw in ({'limit': 0}, {'max_pairs': 0}, {'max_seconds': 0}):
                self.assertEqual(sc.similarity_step(self.conn, self.sf, **kw), (0, 0, ''))
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.conn.execute('INSERT INTO probe VALUES(9)')
        self.assertIn('active caller transaction', self.step()[2])
        self.assertTrue(self.conn.in_transaction)
        with self.assertRaises(ValueError):
            sc._retire_peer_cursors(self.conn)
        self.conn.rollback()
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def test_zero_limit_and_empty_selection_create_no_position(self):
        before = tuple(self.conn.iterdump())
        self.assertEqual(sc._retire_peer_cursors(self.conn), 0)
        self.orphan(999)
        with_orphan = tuple(self.conn.iterdump())
        self.assertEqual(sc._retire_peer_cursors(self.conn, limit=0), 0)
        self.assertEqual(tuple(self.conn.iterdump()), with_orphan)
        self.conn.execute("DELETE FROM sim_cursor WHERE scope='peer'")
        self.conn.commit()
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def traced_step(self, now, loader=None, retirement=None):
        statements, entries = [], []
        original = sc._pending_sources
        def pending(*args, **kwargs):
            entries.append(now[0])
            return original(*args, **kwargs)
        if loader is None:
            loader = lambda *args: (fixture.rs, 'fixture')
        if retirement is None:
            retirement = sc._retire_peer_cursors
        self.conn.set_trace_callback(statements.append)
        try:
            with mock.patch.object(sc.time, 'monotonic', side_effect=lambda: now[0]), \
                    mock.patch.object(sc, '_recsim', side_effect=loader), \
                    mock.patch.object(sc, '_retire_peer_cursors', side_effect=retirement), \
                    mock.patch.object(sc, '_pending_sources', side_effect=pending):
                out = sc.similarity_step(self.conn, self.sf, limit=1,
                                         max_pairs=1, max_seconds=1)
        finally:
            self.conn.set_trace_callback(None)
        selects = [s for s in statements if s.startswith('SELECT r.* FROM replays r')]
        return out, entries, selects

    def test_fresh_preparation_selects_and_compares_before_deadline(self):
        out, entries, selects = self.traced_step([100.0])
        self.assertEqual(entries, [100.0])  # deadline is 101
        self.assertTrue(selects)
        self.assertEqual(out[:2], (1, 1))
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0], 80)
        self.assertNotIn('time limit', out[2])
        self.assertEqual({i: p.read_bytes() for i, p in self.paths.items()}, self.data)

    def test_expired_loader_cannot_admit_cleanup(self):
        self.orphan(999)
        before = tuple(self.conn.iterdump())
        now = [100.0]
        def loader(*args):
            now[0] = 102.0
            return fixture.rs, 'fixture'
        out, entries, selects = self.traced_step(now, loader=loader)
        self.assertEqual(out[:2], (0, 0))
        self.assertIn('time limit reached (cooperative; 0 attempted; coverage not measured)', out[2])
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertEqual((entries, selects), ([], []))
        now[0] = 100.0
        fresh, entries, selects = self.traced_step(now)
        self.assertEqual(fresh[:2], (1, 1))
        self.assertEqual(entries, [100.0])
        self.assertTrue(selects)
        self.assertNotIn(999, self.peers())
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0], 80)
        self.assertEqual({i: p.read_bytes() for i, p in self.paths.items()}, self.data)

    def test_expiry_during_admitted_retirement_preserves_cleanup_and_recovery(self):
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=1,
                                       reader=fixture.rs), (1, 0, 1))
        old = tuple(self.conn.execute('SELECT * FROM sims').fetchone())
        sc._source_admit(self.conn, 1)
        positions = [tuple(r) for r in self.conn.execute(
            "SELECT * FROM sim_cursor ORDER BY scope,source_id")]
        replays = [tuple(r) for r in self.conn.execute('SELECT * FROM replays ORDER BY id')]
        self.orphan(999)
        now, retired = [100.0], []
        original = sc._retire_peer_cursors
        def retirement(*args, **kwargs):
            count = original(*args, **kwargs)
            retired.append(count)
            self.assertFalse(self.conn.in_transaction)
            now[0] = 102.0
            return count
        out, entries, selects = self.traced_step(now, retirement=retirement)
        self.assertEqual(retired, [1])
        self.assertEqual(out[:2], (0, 0))
        self.assertIn('sims retired 1 orphan peer cursors', out[2])
        self.assertIn('time limit reached (cooperative; 0 attempted; coverage not measured)', out[2])
        self.reopen()  # deletion and maintenance checkpoint actually committed
        self.assertNotIn(999, self.peers())
        self.assertEqual(sc._cursor(self.conn, 'source', sc._SOURCE_CURSOR_RETIRE), 999)
        self.assertEqual([tuple(r) for r in self.conn.execute(
            "SELECT * FROM sim_cursor WHERE NOT(scope='source' AND source_id=2)"
            " ORDER BY scope,source_id")], positions)
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims').fetchone()), old)
        self.assertEqual([tuple(r) for r in self.conn.execute('SELECT * FROM replays ORDER BY id')], replays)
        self.assertEqual((entries, selects), ([], []))
        now[0] = 100.0
        fresh, entries, selects = self.traced_step(now)
        self.assertEqual(fresh[:2], (1, 1))
        self.assertEqual(entries, [100.0])
        self.assertTrue(selects)
        self.assertEqual([tuple(r) for r in self.conn.execute(
            'SELECT a_id,b_id,compared FROM sims ORDER BY id')], [(1, 2, 80), (1, 3, 80)])
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=1').fetchone()), old)
        self.assertIsNone(self.conn.execute("SELECT after_id FROM sim_cursor"
                                            " WHERE scope='source' AND source_id=1").fetchone())
        self.assertEqual({i: p.read_bytes() for i, p in self.paths.items()}, self.data)

    def test_real_sql_read_interrupt_keeps_whole_window_unchanged(self):
        self.orphan(*range(100, 200))
        before = tuple(self.conn.iterdump())
        budget = sc.ReadBudget(self.conn, 1)
        with self.assertRaises(sc.ReadLimit):
            sc._retire_peer_cursors(self.conn, read_budget=budget)
        self.assertTrue(budget.exhausted)
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM replays').fetchone()[0], 3)

    def test_unbudgeted_cleanup_preserves_callers_progress_callback(self):
        self.orphan(999)
        calls = []
        self.conn.set_progress_handler(lambda: calls.append(1) or 0, 1)
        try:
            self.assertEqual(sc._retire_peer_cursors(self.conn), 1)
            before = len(calls)
            self.conn.execute('SELECT COUNT(*) FROM replays').fetchone()
            self.assertGreater(len(calls), before)
        finally:
            self.conn.set_progress_handler(None, 0)

    def test_readonly_failure_never_advances_or_deletes(self):
        self.orphan(999)
        before = tuple(self.conn.iterdump())
        ro = sqlite3.connect(self.db.as_uri() + '?mode=ro', uri=True)
        self.addCleanup(ro.close)
        with self.assertRaises(sqlite3.OperationalError):
            sc._retire_peer_cursors(ro)
        self.assertFalse(ro.in_transaction)
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def test_autocommit_delete_and_position_rollback_as_one_unit(self):
        self.conn.isolation_level = None
        self.orphan(999, 1000)
        acted = []
        def checkpoint_probe(n):
            count = self.conn.execute("SELECT COUNT(*) FROM sim_cursor WHERE scope='peer'").fetchone()[0]
            acted.append((n, count))
            return 0
        self.conn.create_function('retire_probe', 1, checkpoint_probe)
        self.conn.executescript("""CREATE TRIGGER stop_retire BEFORE INSERT ON sim_cursor
            WHEN NEW.scope='source' AND NEW.source_id=2 BEGIN
                SELECT retire_probe(NEW.after_id);
                SELECT RAISE(ABORT,'owned retirement rollback'); END;""")
        before = tuple(self.conn.iterdump())
        self.assertIn('similarity step failed', self.step()[2])
        self.assertEqual(acted, [(1000, 0)])  # DELETE really acted before failed position
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertFalse(self.conn.in_transaction)
        self.conn.execute('DROP TRIGGER stop_retire')
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.peers(), {1: 2})
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0], 80)

    def test_late_source_resurrection_retains_its_old_peer_position(self):
        self.orphan(999)
        original = sc._rotated_rows
        acted = []
        def selected(*args, **kwargs):
            rows = original(*args, **kwargs)
            with sqlite3.connect(self.db) as writer:
                writer.execute("INSERT INTO replays VALUES(999,'other',0,0,'tool','imported','synthetic')")
            acted.append([r[0] for r in rows])
            return rows
        with mock.patch.object(sc, '_rotated_rows', side_effect=selected):
            self.assertEqual(sc._retire_peer_cursors(self.conn), 0)
        self.assertEqual(acted, [[999]])
        self.assertEqual(self.peers(), {999: 17})
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM replays WHERE id=999').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
