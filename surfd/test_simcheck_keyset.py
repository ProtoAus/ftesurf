"""Bounded rotating selection: exact order, real reader, no partial wrap return."""
import json
import sqlite3
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc


class KeysetSelection(fixture.StoredSources):
    def grow(self):
        self.conn.executemany(
            "INSERT INTO replays VALUES (?,'synthetic',0,0,'run','','s')",
            [(i,) for i in range(4, 50001)])
        self.conn.commit()

    def measured(self):
        row = dict(self.conn.execute('SELECT * FROM sims').fetchone())
        self.assertEqual((row['a_id'], row['b_id'], row['verdict'], row['compared'], row['match']),
                         (1, 2, 'compared', 80, 1.0))
        self.assertEqual(json.loads(row['source_capture']),
                         fixture.capture(self.data[1], self.data[2]))
        self.assertFalse(self.conn.in_transaction)

    def test_large_source_selection_default_allowance_reaches_actual_reader(self):
        self.grow()
        original = fixture.rs.compare_paths
        acted = []
        def compare(a, b, **kw):
            self.assertFalse(self.conn.in_transaction)
            with sqlite3.connect(str(self.db)) as writer:
                writer.execute('INSERT INTO probe VALUES (1)')
            value = original(a, b, **kw)
            acted.append(value[0])
            return value
        reader = type('Reader', (), {'compare_paths': staticmethod(compare)})
        with mock.patch.object(sc, '_recsim', return_value=(reader, 'actual reader')):
            out = sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=1,
                                     max_seconds=30,
                                     read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS))
        self.assertEqual(out[:2], (1, 1))
        self.assertNotIn('SQL read limit', out[2])
        self.assertEqual(acted, ['compared'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 1)
        self.measured()

    def test_large_peer_selection_default_allowance_reaches_actual_reader(self):
        self.grow()
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        with mock.patch.object(sc, '_recsim', return_value=(fixture.rs, 'actual reader')):
            self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=1,
                            read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS)), (1, 0, 1))
        self.measured()

    def varied(self):
        self.conn.executemany("INSERT INTO replays VALUES (?,'synthetic',0,0,'run','','s')",
                              [(-4,), (-2,), (4,), (7,), (9,)])
        self.conn.execute("UPDATE replays SET kind='stage' WHERE id=4")
        self.conn.execute("UPDATE replays SET map='other' WHERE id=7")
        self.conn.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at)"
                          " VALUES(2,-2,'synthetic',0,0,'compared',0)")
        self.conn.commit()

    def test_pending_order_matches_previous_single_query(self):
        self.varied()
        for after in (-100, -3, 0, 2, 5, 100):
            sc._advance(self.conn, 'source', after_id=after, source_id=0)
            self.conn.commit()
            before = list(self.conn.iterdump())
            for limit in (1, 2, 4, 20):
                with self.subTest(after=after, limit=limit):
                    old = self.conn.execute('SELECT r.* FROM replays r WHERE ' +
                        sc._PENDING_WHERE + ' ORDER BY (r.id > ?) DESC,r.id LIMIT ?',
                        (after, limit)).fetchall()
                    new = sc.pending(self.conn, limit,
                                     read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS))
                    self.assertEqual([r['id'] for r in new], [r['id'] for r in old])
            self.assertEqual(list(self.conn.iterdump()), before)

    def test_peer_order_matches_previous_single_query(self):
        self.varied()
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        sql = ("SELECT p.* FROM replays p WHERE p.map=? AND p.track=? AND p.leg=?"
               " AND p.kind='run' AND p.id!=? AND NOT EXISTS (SELECT 1 FROM sims s"
               " WHERE (s.a_id=? AND s.b_id=p.id) OR (s.a_id=p.id AND s.b_id=?))")
        for after in (-100, -3, 0, 2, 5, 100):
            sc._advance(self.conn, 'peer', after_id=after, source_id=1)
            self.conn.commit()
            for limit in (1, 2, 4, 20):
                old = self.conn.execute(sql + ' ORDER BY (p.id>?) DESC,p.id LIMIT ?',
                    ('synthetic', 0, 0, 1, 1, 1, after, limit)).fetchall()
                selected = []
                original = sc._read
                def trace(conn, query, parameters=(), read_budget=None):
                    rows = original(conn, query, parameters, read_budget)
                    if 'SELECT p.* FROM replays p' in query:
                        selected.extend(r['id'] for r in rows)
                    return rows
                with self.subTest(after=after, limit=limit), \
                     mock.patch.object(sc, '_read', side_effect=trace), \
                     mock.patch.object(sc, '_recsim', return_value=(fixture.rs, 'actual reader')), \
                     mock.patch.object(self.sf, 'replay_file', return_value=(None, 'selection only')):
                    before = list(self.conn.iterdump())
                    self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=limit,
                        read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS)), (0, 0, 0))
                    self.assertEqual(selected, [r['id'] for r in old])
                    self.assertEqual(list(self.conn.iterdump()), before)

    def test_wrap_query_interrupt_does_not_return_head_or_advance(self):
        sc._advance(self.conn, 'source', after_id=2, source_id=0)
        self.conn.commit()
        budget = sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS)
        original = sc._read
        actual_reads = []
        def interrupted_wrap(conn, query, parameters=(), read_budget=None):
            if 'SELECT r.* FROM replays r' in query:
                actual_reads.append(query)
                if 'r.id <= ?' in query:
                    budget.remaining = 1
            return original(conn, query, parameters, read_budget)
        before = list(self.conn.iterdump())
        with mock.patch.object(sc, '_read', side_effect=interrupted_wrap):
            with self.assertRaises(sc.ReadLimit):
                sc.pending(self.conn, 3, read_budget=budget)
        self.assertEqual(len(actual_reads), 2)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(sc._cursor(self.conn, 'source'), 2)
        # Same head/wrap and actual database succeed with an adequate allowance.
        self.assertEqual([r['id'] for r in sc.pending(self.conn, 3,
                         read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS))], [3, 1, 2])
        self.assertEqual(self.conn.execute('SELECT 42').fetchone()[0], 42)
        self.assertFalse(self.conn.in_transaction)

    def test_full_upper_range_does_not_read_wrap(self):
        original = sc._read
        def forbid_wrap(conn, query, parameters=(), read_budget=None):
            self.assertNotIn('r.id <= ?', query)
            return original(conn, query, parameters, read_budget)
        with mock.patch.object(sc, '_read', side_effect=forbid_wrap):
            self.assertEqual([r['id'] for r in sc.pending(self.conn, 1,
                             read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS))], [1])

    def test_legacy_read_does_not_create_cursor_or_mutate_schema(self):
        self.conn.execute('DROP TABLE sim_cursor')
        self.conn.commit()
        before = list(self.conn.iterdump())
        self.assertEqual([r['id'] for r in sc.pending(self.conn, 2,
                         read_budget=sc.ReadBudget(self.conn, sc.MAX_SQL_STEPS))], [1, 2])
        self.assertEqual(list(self.conn.iterdump()), before)


if __name__ == '__main__':
    unittest.main()
