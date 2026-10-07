"""Bound Python summary results without changing stored sample semantics."""
import sqlite3
import unittest

import simcheck


class TrackingCursor(sqlite3.Cursor):
    def fetchall(self):
        rows = super().fetchall()
        if getattr(self, 'sample_query', False):
            self.connection.sample_results.append(len(rows))
        return rows


class TrackingConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        cur = self.cursor(factory=TrackingCursor)
        cur.sample_query = 'FROM SIMS' in sql.upper()
        return cur.execute(sql, parameters)


def reference(rows):
    """Predecessor's read-only sample contract, not a second file reader."""
    out = {'state': 'available' if rows else 'empty', 'pairs': len(rows),
           'compared': 0, 'skipped': 0, 'notable': 0, 'same_n': 0,
           'cross_n': 0, 'unknown_n': 0, 'same_max': None,
           'cross_max': None, 'unknown_max': None, 'skip_codes': {}}
    for verdict, match, same, a, b, code in rows:
        if verdict != 'compared':
            out['skipped'] += 1
            code = ((code if code in simcheck.KNOWN_SKIP_CODES else 'unknown')
                    if code else 'legacy_unknown')
            out['skip_codes'][code] = out['skip_codes'].get(code, 0) + 1
            continue
        out['compared'] += 1
        out['notable'] += match >= simcheck.NOTABLE
        bucket = ('same' if same else 'cross') if a and b else 'unknown'
        out[bucket + '_n'] += 1
        old = out[bucket + '_max']
        out[bucket + '_max'] = match if old is None else max(old, match)
    return out


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:', factory=TrackingConnection)
        self.conn.row_factory = sqlite3.Row
        self.conn.sample_results = []
        simcheck.ensure_schema(self.conn)
        self.rows = []

    def tearDown(self):
        self.conn.close()

    def add(self, verdict='compared', match=0.5, same=0, a='a', b='b', code=''):
        i = len(self.rows) + 1
        self.conn.execute('INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at,'
                          'match,same_who,who_a,who_b,skip_code)'
                          " VALUES(?,?, 'm',0,0,?,0,?,?,?,?,?)",
                          (i, i + 10000, verdict, match, same, a, b, code))
        self.rows.append((verdict, match, same, a, b, code))

    def check_reference(self):
        self.conn.commit()
        self.assertEqual(simcheck.summary(self.conn), reference(self.rows))

    def test_large_sample_aggregates_into_fixed_result_bound(self):
        codes = sorted(simcheck.KNOWN_SKIP_CODES) + ['', 'unsafe source path']
        for i in range(1200):
            self.add(match=(i % 101) / 100., same=i % 2,
                     a='' if i % 3 == 0 else '0', b='0' if i % 2 else 'b')
            self.add('skip', match=1., code=codes[i % len(codes)])
        self.check_reference()
        self.assertEqual(len(self.conn.sample_results), 1)  # one sample snapshot
        self.assertLessEqual(self.conn.sample_results[0],
                             len(simcheck.KNOWN_SKIP_CODES) + 1 + 3)
        self.assertEqual(simcheck.summary(self.conn)['pairs'], 2400)  # ACTED count
        self.assertNotIn('unsafe source path', simcheck.summary_line(self.conn))

    def test_identity_and_notable_boundary_parity(self):
        for match in (0., 0.949999, simcheck.NOTABLE, 1.):
            self.add(match=match, same=1, a='0', b='0')
            self.add(match=match, same=0, a='0', b='a')
            self.add(match=match, same=1, a='', b='a')
            self.add(match=match, same=0, a='a', b='')
        self.add('skip', match=1., same=1, a='0', b='0', code='too_short')
        self.check_reference()
        out = simcheck.summary(self.conn)
        self.assertEqual((out['same_n'], out['cross_n'], out['unknown_n']), (4, 4, 8))
        self.assertEqual(out['notable'], 8)  # skips are not notable zero scores

    def test_arbitrary_unknown_codes_collapse_without_prose_projection(self):
        for i in range(500):
            self.add('skip', code='private detail %d' % i)
        self.check_reference()
        self.assertEqual(simcheck.summary(self.conn)['skip_codes'], {'unknown': 500})
        self.assertNotIn('private detail', simcheck.summary_line(self.conn))
        self.assertEqual(self.conn.sample_results, [1, 1, 1])

    def test_old_schema_stays_legacy_without_read_migration(self):
        self.add('skip', code='too_short')
        self.add(match=1., same=1)
        self.conn.execute('ALTER TABLE sims DROP COLUMN skip_code')
        self.rows[0] = (*self.rows[0][:-1], '')
        before = tuple(self.conn.iterdump())
        self.check_reference()
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertEqual(simcheck.summary(self.conn)['skip_codes'], {'legacy_unknown': 1})

    def test_query_denial_is_unavailable_not_zero(self):
        self.add(match=1.)
        self.conn.commit()
        denied = []

        def authorize(action, table, column, *rest):
            if action == sqlite3.SQLITE_READ and table == 'sims':
                denied.append(column)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.conn.set_authorizer(authorize)
        out = simcheck.summary(self.conn)
        self.assertTrue(denied)  # real query refusal ACTED
        self.assertEqual(out['state'], 'error')
        self.assertIsNone(out['pairs'])
        self.assertEqual(simcheck.summary_line(self.conn), 'sims: unavailable (query error)')
        self.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        self.check_reference()
        self.assertEqual(simcheck.summary(self.conn)['notable'], 1)

    def test_missing_and_empty_stay_distinct_and_read_only(self):
        before = tuple(self.conn.iterdump())
        self.check_reference()
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertEqual(simcheck.summary_line(self.conn), 'sims: no pairs stored yet')
        self.conn.execute('DROP TABLE sims')
        before = tuple(self.conn.iterdump())
        out = simcheck.summary(self.conn)
        self.assertEqual(out['state'], 'missing')
        self.assertIsNone(out['pairs'])
        self.assertEqual(tuple(self.conn.iterdump()), before)


if __name__ == '__main__':
    unittest.main()
