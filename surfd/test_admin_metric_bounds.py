#!/usr/bin/env python3
"""Actual authenticated metric consumers: bounded SQL fetch, no history writes."""
import json
import sqlite3
import unittest
from unittest import mock

import test_admin_similarity as fixture


class ObservationFixture(unittest.TestCase):
    cleanup_home = fixture.Similarity.cleanup_home
    detail = fixture.Similarity.detail
    pair = fixture.Similarity.pair
    render_dom = fixture.Similarity.render_dom

    def setUp(self):
        add_replay = fixture.suite.add_replay
        with mock.patch.object(fixture.suite, 'add_replay',
                               side_effect=lambda *a, **kw: add_replay(*a, **dict(kw, make_file=False))):
            fixture.Similarity.setUp(self)


class MetricBounds(ObservationFixture):
    def setUp(self):
        super().setUp()
        self.c.execute("INSERT INTO receipts(runid,map,pub,verdict,angles,reason,at)"
                       " VALUES('synthetic-bound','bhop_eazy','','VALID','OK','control',1)")
        self.c.execute("UPDATE replays SET runid='synthetic-bound' WHERE id=?", (self.rid,))
        self.c.execute("INSERT INTO verdicts(replay_id,verdict,reason,ticks,engine,progs,at)"
                       " VALUES(?,'PASS','control',100,'e','p',1)", (self.rid,))
        self.c.commit()

    def fetch(self):
        seen = []
        connect = sqlite3.connect

        class Cursor:
            def __init__(self, cursor, column):
                self.cursor, self.column = cursor, column

            def __getattr__(self, key):
                return getattr(self.cursor, key)

            def observe(self, row):
                if row is not None and self.column:
                    value = row[self.column]
                    size = len(value.encode('utf-8')) if isinstance(value, str) else len(value)
                    seen.append((self.column, size))
                return row

            def fetchone(self):
                return self.observe(self.cursor.fetchone())

            def fetchall(self):
                return [self.observe(row) for row in self.cursor.fetchall()]

            def __iter__(self):
                return (self.observe(row) for row in self.cursor)

        class Connection:
            def __init__(self, conn):
                object.__setattr__(self, 'conn', conn)

            def __getattr__(self, key):
                return getattr(self.conn, key)

            def __setattr__(self, key, value):
                setattr(self.conn, key, value)

            def execute(self, sql, args=()):
                column = ('journal_metrics' if 'journal_metrics' in sql and 'FROM receipts' in sql
                          else 'counts_metrics' if 'counts_metrics' in sql and 'FROM verdicts' in sql
                          else None)
                return Cursor(self.conn.execute(sql, args), column)

        with mock.patch.object(sqlite3, 'connect', side_effect=lambda *a, **kw: Connection(connect(*a, **kw))):
            reply = self.client.get(self.route)
        self.assertEqual(reply.status_code, 200)
        self.assertEqual({name for name, size in seen}, {'journal_metrics', 'counts_metrics'})
        self.assertTrue(all(size <= (8193 if name == 'journal_metrics' else 513)
                            for name, size in seen), seen)
        return reply.get_json(), seen

    def put(self, journal, counts):
        self.c.execute('UPDATE receipts SET journal_metrics=?', (journal,))
        self.c.execute('UPDATE verdicts SET counts_metrics=?', (counts,))
        self.c.commit()

    def stored(self):
        return ([tuple(r) for r in self.c.execute('SELECT * FROM receipts')],
                [tuple(r) for r in self.c.execute('SELECT * FROM verdicts')])

    def test_measured_empty_and_legacy_controls(self):
        journal = {'version': 1, 'metrics': {'identity_judged': 80, 'join_checked': 10}}
        counts = {'version': 1, 'state': 'measured', 'records': 80, 'disagree': 0}
        for j, c, expected_j, expected_c in (
                (json.dumps(journal), json.dumps(counts), journal, counts),
                (json.dumps(journal).encode(), json.dumps(counts).encode(), journal, counts),
                ('', '', None, None)):
            self.put(j, c)
            before = self.stored()
            out, seen = self.fetch()
            self.assertEqual(out['receipt']['journal_metrics'], expected_j)
            self.assertEqual(out['verdicts'][0]['counts_metrics'], expected_c)
            self.assertEqual(out['verdicts'][0]['verdict'], 'PASS')
            self.assertEqual(self.stored(), before)
        for table, column in (('receipts', 'journal_metrics'), ('verdicts', 'counts_metrics')):
            self.c.execute('ALTER TABLE %s DROP COLUMN %s' % (table, column))
        self.c.commit()
        out = self.detail()
        self.assertIsNone(out['receipt']['journal_metrics'])
        self.assertIsNone(out['verdicts'][0]['counts_metrics'])

    def test_large_nul_and_invalid_utf8_abstain_without_materializing_suffix(self):
        for journal, counts in (
                (' ' * 1000000, ' ' * 1000000),
                (b'{}\0' + b'x' * 1000000, b'{}\0' + b'x' * 1000000),
                (b'\xff', b'\xff'), ('{bad', '{bad'),
                ('{"version":1,"metrics":{}}\0', '{"version":1,"state":"no_records","records":0}\0')):
            self.put(journal, counts)
            before = self.stored()
            out, seen = self.fetch()
            self.assertIsNone(out['receipt']['journal_metrics'])
            self.assertIsNone(out['verdicts'][0]['counts_metrics'])
            self.assertEqual(self.stored(), before)
        self.assertEqual(self.m.app.test_client().get(self.route).status_code, 401)

    def test_exact_byte_cap_and_unicode_are_not_truncated_into_valid_json(self):
        j = json.dumps({'version': 1, 'metrics': {'identity_judged': 80}})
        c = json.dumps({'version': 1, 'state': 'measured', 'records': 80, 'disagree': 0})
        for extra in (0, 1):
            self.put(j + ' ' * (8192 - len(j) + extra), c + ' ' * (512 - len(c) + extra))
            out, seen = self.fetch()
            self.assertEqual(out['receipt']['journal_metrics'], json.loads(j) if not extra else None)
            self.assertEqual(out['verdicts'][0]['counts_metrics'], json.loads(c) if not extra else None)
        self.put('é' * 8192, 'é' * 512)
        out, seen = self.fetch()
        self.assertEqual(dict(seen), {'journal_metrics': 8193, 'counts_metrics': 513})
        self.assertIsNone(out['receipt']['journal_metrics'])
        self.assertIsNone(out['verdicts'][0]['counts_metrics'])


if __name__ == '__main__':
    unittest.main()
