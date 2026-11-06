"""Interrupted source recovery: real reader/SQLite/OS ownership, synthetic files."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('reservation_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


class SourceReservation(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def step(self, reader=None, **kw):
        if reader is None:
            reader = fixture.rs
        with mock.patch.object(sc, '_recsim', return_value=(reader, 'fixture')):
            return sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=1, **kw)

    def reserved(self):
        row = self.conn.execute("SELECT after_id FROM sim_cursor"
                                " WHERE scope='source' AND source_id=1").fetchone()
        return row[0] if row else None

    def pairs(self):
        return [tuple(r) for r in self.conn.execute(
            'SELECT a_id,b_id,compared FROM sims ORDER BY id')]

    def schema(self):
        return tuple(self.conn.execute('SELECT type,name,sql FROM sqlite_master'
                                       ' WHERE name NOT LIKE \'sqlite_%\' ORDER BY type,name'))

    def interrupt(self):
        acted = []
        def compare(a, b, **limits):
            self.assertFalse(self.conn.in_transaction)
            result = fixture.rs.compare_paths(a, b, **limits)
            self.assertEqual((result[0], result[1]['compared']), ('compared', 80))
            acted.append(80)
            raise KeyboardInterrupt('owned fixture interrupt after actual read')
        with self.assertRaises(KeyboardInterrupt):
            self.step(SimpleNamespace(compare_paths=compare))
        self.assertEqual(acted, [80])
        self.assertFalse(self.conn.in_transaction)

    def child(self):
        code = '''import importlib.util, os, sqlite3, sys
from pathlib import Path
from types import SimpleNamespace
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('child_collector',p)
sc=importlib.util.module_from_spec(s);s.loader.exec_module(sc)
c=sqlite3.connect(sys.argv[2]);c.row_factory=sqlite3.Row
rs,why=sc._recsim(sys.argv[3]);assert rs is not None,why
sf=SimpleNamespace(replay_file=lambda row:(str(Path(sys.argv[2]).parent/(str(row['id'])+'.rec')),''))
def compare(a,b,**limits):
    result=rs.compare_paths(a,b,**limits)
    assert result[0]=='compared' and result[1]['compared']==80
    assert not c.in_transaction
    print('MEASURED',flush=True)
    if sys.stdin.readline().strip()=='CRASH':os._exit(23)
    return result
sc._recsim=lambda *args:(SimpleNamespace(compare_paths=compare),'fixture')
sc.similarity_step(c,sf,limit=1,max_pairs=1)
c.close()
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', code,
            str(Path(sc.__file__).resolve()), str(self.db), str(fixture.ROOT/'tools')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)  # ONLY this spawned synthetic child
            child.stdin.close(); child.stdout.close(); child.stderr.close()
        self.addCleanup(cleanup)
        self.assertEqual(child.stdout.readline().strip(), 'MEASURED')
        return child

    def crash(self, child):
        child.communicate('CRASH'+chr(10), timeout=5)
        self.assertEqual(child.returncode, 23)

    def test_actual_child_crash_prioritizes_unfinished_source_under_one_row_cap(self):
        before_schema = self.schema()
        child = self.child()
        self.assertEqual(sc._cursor(self.conn, 'source'), 1)
        self.assertEqual(self.pairs(), [])
        snapshot = tuple(self.conn.iterdump())
        self.assertIn('collector busy', self.step()[2])
        self.assertEqual(tuple(self.conn.iterdump()), snapshot)
        with closing(sqlite3.connect(self.db)) as writer:
            with writer:
                writer.execute('INSERT INTO probe VALUES(1)')
        self.crash(child)
        self.conn.close()
        self.conn = sqlite3.connect(self.db); self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        recovered = [r['id'] for r in sc.pending(self.conn, 1)]
        out = self.step()
        self.assertEqual(out[:2], (1, 1))
        self.assertEqual(self.pairs(), [(1, 2, 80)])
        self.assertEqual(recovered, [1])
        self.assertIsNone(self.reserved())
        self.assertEqual(self.schema(), before_schema)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 1)

    def test_keyboard_interrupt_reopen_recovers_real_unflushed_comparison(self):
        self.interrupt()
        self.assertEqual(self.pairs(), [])
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(1, 2, 80)])
        self.assertIsNone(self.reserved())

    def test_existing_observation_and_capture_not_repeated_or_rewritten_on_recovery(self):
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=1,
                                       reader=fixture.rs), (1, 0, 1))
        old = tuple(self.conn.execute('SELECT * FROM sims').fetchone())
        self.interrupt()  # source1 now has only peer3 unobserved
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(1, 2, 80), (1, 3, 80)])
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=1').fetchone()), old)

    def test_handled_row_failure_rotates_without_fake_observation_or_reservation(self):
        attempted = []
        def fail(*args, **kw):
            attempted.append(args[2]['id'])
            raise RuntimeError('owned handled comparison failure')
        with mock.patch.object(sc, '_compare_run', side_effect=fail):
            self.assertIn('1 row failed', self.step()[2])
        self.assertEqual(attempted, [1])
        self.assertEqual(self.pairs(), [])
        self.assertIsNone(self.reserved())
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(2, 1, 80)])

    def test_readlimit_is_handled_attempt_not_a_permanent_recovery_monopoly(self):
        acted = []
        def limit(*args, **kw):
            acted.append(args[2]['id'])
            raise sc.ReadLimit('owned selected read limit')
        with mock.patch.object(sc, '_compare_run', side_effect=limit):
            self.assertEqual(self.step()[:2], (0, 0))
        self.assertEqual(acted, [1])
        self.assertIsNone(self.reserved())
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(2, 1, 80)])

    def test_admission_reservation_abort_is_atomic_even_on_autocommit(self):
        self.conn.isolation_level = None
        sc._advance(self.conn, 'source', 77)
        acted = []
        self.conn.create_function('reserve_probe', 1, lambda n: acted.append(n) or 0)
        self.conn.executescript('''CREATE TRIGGER stop_reserve BEFORE INSERT ON sim_cursor
            WHEN NEW.scope='source' AND NEW.source_id=1 BEGIN
                SELECT reserve_probe(NEW.after_id);
                SELECT RAISE(ABORT,'owned admission rollback'); END;''')
        self.step()
        self.assertEqual(acted, [1])
        self.assertEqual(sc._cursor(self.conn, 'source'), 77)
        self.assertIsNone(self.reserved())
        self.assertEqual(self.pairs(), [])
        self.assertFalse(self.conn.in_transaction)
        self.conn.execute('DROP TRIGGER stop_reserve')
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(1, 2, 80)])

    def test_failed_completion_keeps_marker_but_committed_observation_counts(self):
        acted = []
        self.conn.create_function('done_probe', 1, lambda n: acted.append(n) or 0)
        self.conn.executescript('''CREATE TRIGGER stop_done BEFORE DELETE ON sim_cursor
            WHEN OLD.scope='source' AND OLD.source_id=1 BEGIN
                SELECT done_probe(OLD.after_id);
                SELECT RAISE(ABORT,'owned completion failure'); END;''')
        out = self.step()
        self.assertEqual(out[:2], (1, 1))
        self.assertEqual(acted, [1])
        self.assertEqual(self.pairs(), [(1, 2, 80)])
        self.assertEqual(self.reserved(), 1)
        old = tuple(self.conn.execute('SELECT * FROM sims').fetchone())
        self.conn.execute('DROP TRIGGER stop_done'); self.conn.commit()
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(1, 2, 80), (1, 3, 80)])
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=1').fetchone()), old)
        self.assertIsNone(self.reserved())

    def test_removed_reserved_source_does_not_hide_later_real_work(self):
        self.interrupt()
        self.conn.execute('DELETE FROM replays WHERE id=1'); self.conn.commit()
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(2, 3, 80)])
        self.assertIsNone(self.reserved())

    def test_all_work_completed_elsewhere_clears_only_stale_marker(self):
        self.interrupt()
        for rid in (1, 2):
            row = self.conn.execute('SELECT * FROM replays WHERE id=?', (rid,)).fetchone()
            sc.compare_run(self.sf, self.conn, row, limit_peers=3, reader=fixture.rs)
        self.assertEqual(len(self.pairs()), 3)
        old = list(self.conn.execute('SELECT * FROM sims ORDER BY id'))
        self.assertEqual(self.step(), (0, 0, ''))
        self.assertEqual(list(self.conn.execute('SELECT * FROM sims ORDER BY id')), old)
        self.assertIsNone(self.reserved())

    def test_zero_replay_id_is_not_an_absence_sentinel(self):
        self.conn.execute("INSERT INTO replays VALUES(0,'synthetic',0,0,'run','ranked','synthetic')")
        self.conn.commit()
        self.paths[0] = self.root/'0.rec'
        self.paths[0].write_bytes(fixture.source(tag=b'# zero source'+bytes([10])))
        sc._advance(self.conn, 'source', 99)  # force the ordinary ascending wrap
        self.interrupt()
        self.assertEqual([r['id'] for r in sc.pending(self.conn, 1)], [0])
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(0, 1, 80)])
        self.assertIsNone(self.reserved())

    def test_disabled_and_borrowed_calls_preserve_interrupted_marker(self):
        self.interrupt()
        before = tuple(self.conn.iterdump())
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('disabled loader')):
            for kw in ({'limit': 0}, {'max_pairs': 0}, {'max_seconds': 0}):
                self.assertEqual(sc.similarity_step(self.conn, self.sf, **kw), (0, 0, ''))
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.assertEqual([r['id'] for r in sc.pending(self.conn, 1)], [1])
        self.assertEqual(tuple(self.conn.iterdump()), before)
        self.conn.execute('INSERT INTO probe VALUES(9)')
        self.assertIn('active caller transaction', self.step()[2])
        self.assertTrue(self.conn.in_transaction)
        with closing(sqlite3.connect(self.db)) as other:
            self.assertEqual(other.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 0)
        self.conn.rollback()  # only owned fixture caller DML
        self.assertEqual(self.step()[:2], (1, 1))
        self.assertEqual(self.pairs(), [(1, 2, 80)])


if __name__ == '__main__':
    unittest.main()
