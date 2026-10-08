"""Typed contention is unavailable, never a measured zero or a fake skip."""
import os
import sqlite3
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('contention_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc

NOTE = 'sims unavailable: database busy (coverage not measured)'


def require_codes(test):
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute('SELECT missing')
    except sqlite3.Error as exc:
        if not hasattr(exc, 'sqlite_errorcode'):
            test.skipTest('Python SQLite lacks result-code attributes; no prose inference')
    finally:
        conn.close()


class Contention(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def blocker(self):
        self.conn.execute('PRAGMA busy_timeout=0')
        blocker = sqlite3.connect(self.db); self.addCleanup(blocker.close)
        return blocker

    def test_schema_lock_is_fixed_unavailable_then_native_recovery_acts(self):
        require_codes(self)
        blocker = self.blocker(); blocker.execute('BEGIN EXCLUSIVE')
        result = sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))
        self.assertEqual(result, (0, 0, NOTE))
        self.assertFalse(self.conn.in_transaction)
        blocker.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)
        self.assertEqual(sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))[:2], (3, 3))
        self.assertEqual([r[0] for r in self.conn.execute('SELECT compared FROM sims')], [80]*3)

    def test_summary_lock_has_all_unknown_counters_and_exact_recovery(self):
        require_codes(self)
        self.assertEqual(sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))[:2], (3, 3))
        before = sc.summary(self.conn)
        blocker = self.blocker(); blocker.execute('BEGIN EXCLUSIVE')
        result = sc.summary(self.conn)
        self.assertEqual(result['state'], 'busy')
        self.assertTrue(all(v is None for k,v in result.items() if k != 'state'))
        self.assertEqual(sc.summary_line(self.conn), 'sims: unavailable (database busy; sample not measured)')
        blocker.rollback()
        self.assertEqual(sc.summary(self.conn), before)

    def test_later_row_contention_stops_admission_and_keeps_committed_first_row(self):
        require_codes(self)
        blocker = self.blocker()
        resolved = []
        original = self.sf.replay_file
        def resolve(row):
            resolved.append(row['id'])
            if resolved == [1, 2, 2]:
                blocker.execute('BEGIN EXCLUSIVE')
            return original(row)
        self.sf.replay_file = resolve
        original_compare = sc.compare_run
        def one_peer(*args, **kw):
            return original_compare(*args, limit_peers=1, **kw)
        with mock.patch.object(sc, 'compare_run', side_effect=one_peer):
            result = sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))
        self.assertEqual(result[:2], (1, 1))
        self.assertIn(NOTE, result[2])
        self.assertNotIn('row failed', result[2])
        self.assertNotIn('pair failed', result[2])
        self.assertEqual(resolved, [1, 2, 2])
        self.assertFalse(self.conn.in_transaction)
        blocker.rollback()
        self.assertEqual([tuple(r) for r in self.conn.execute('SELECT a_id,b_id,compared FROM sims')], [(1,2,80)])
        self.assertEqual(sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))[:2], (2, 2))
        self.assertEqual(sc.summary(self.conn)['compared'], 3)

    def test_busy_code_and_real_locked_code_classify_without_message_parsing(self):
        require_codes(self)
        classify = getattr(sc, '_database_busy', lambda exc: False)
        cursor = self.conn.execute('SELECT * FROM replays')
        try:
            with self.assertRaises(sqlite3.OperationalError) as caught:
                self.conn.execute('DROP TABLE replays')
            self.assertEqual(caught.exception.sqlite_errorcode & 255, sqlite3.SQLITE_LOCKED)
            self.assertTrue(classify(caught.exception))
        finally:
            cursor.close()
        for code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_BUSY | (7 << 8)):
            exc = sqlite3.OperationalError('unrelated synthetic prose')
            exc.sqlite_errorcode = code
            self.assertTrue(classify(exc))
        for exc in (sqlite3.OperationalError('database is locked'), RuntimeError('database is locked')):
            self.assertFalse(classify(exc))
        exc = sqlite3.OperationalError('database is locked'); exc.sqlite_errorcode = sqlite3.SQLITE_ERROR
        self.assertFalse(classify(exc))

    def test_other_query_and_storage_faults_remain_failures_not_busy(self):
        self.conn.execute('DROP TABLE replays'); self.conn.commit()
        result = sc.similarity_step(self.conn, self.sf, tools_dir=str(fixture.ROOT/'tools'))
        self.assertIn('similarity step failed', result[2])
        self.assertNotIn('database busy', result[2])
        denied = []
        def guard(action, table, *args):
            if action == sqlite3.SQLITE_READ and table == 'sims':
                denied.append(1)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.conn.set_authorizer(guard)
        self.assertEqual(sc.summary(self.conn)['state'], 'error')
        self.assertTrue(denied)
        self.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)


if __name__ == '__main__':
    unittest.main()
