"""Participating host-local collectors; real OS locks and bounded reader work."""
from contextlib import closing
import errno
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import test_simcheck_atomic_flush as fixture

sc = fixture.sc


class Ownership(unittest.TestCase):
    setUp = fixture.fixture.StoredSources.setUp
    run_source = fixture.fixture.StoredSources.run_source

    @property
    def sidecar(self):
        return Path(str(self.db) + '.simcheck.lock')

    def compared(self, a, b, **limits):
        self.assertFalse(self.conn.in_transaction)
        value = fixture.fixture.rs.compare_paths(a, b, **limits)
        self.assertEqual((value[0], value[1]['compared']), ('compared', 80))
        return value

    def positive(self):
        self.assertEqual(self.run_source(max_pairs=1), (1, 0, 1))
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0], 80)

    def step(self):
        return sc.similarity_step(self.conn, self.sf,
            tools_dir=str(fixture.fixture.ROOT / 'tools'))

    def test_participating_reverse_does_not_repeat_actual_reader_work(self):
        acted = []
        def compare(a, b, **limits):
            value = self.compared(a, b, **limits)
            acted.append(80)
            with closing(sqlite3.connect(self.db)) as other:
                other.row_factory = sqlite3.Row
                with other:
                    other.execute('INSERT INTO probe VALUES(1)')
                self.assertEqual(other.execute('SELECT COUNT(*) FROM probe').fetchone()[0], 1)
                row = other.execute('SELECT * FROM replays WHERE id=2').fetchone()
                diagnostics = {}
                reader = SimpleNamespace(compare_paths=mock.Mock(side_effect=AssertionError('duplicate read')))
                self.assertEqual(sc.compare_run(self.sf, other, row, limit_peers=1,
                    reader=reader, diagnostics=diagnostics), (0, 0, 0))
                self.assertEqual(diagnostics, {'collector_busy': 1})
                reader.compare_paths.assert_not_called()
            return value
        self.assertEqual(self.run_source(reader=SimpleNamespace(compare_paths=compare)), (1, 0, 1))
        self.assertEqual(acted, [80])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 1)
        self.assertEqual(self.sidecar.stat().st_size, 0)

    def test_busy_pass_has_no_loader_schema_or_admission_and_readers_still_work(self):
        before = tuple(self.conn.iterdump())
        with sc.collector_ownership(self.conn) as acquired:
            self.assertTrue(acquired)
            identity = self.sidecar.stat()
            with mock.patch.object(sc, '_recsim', side_effect=AssertionError('busy loader')):
                for _ in range(3):
                    out = self.step()
                    self.assertEqual(out[:2], (0, 0))
                    self.assertIn('collector busy', out[2])
                    self.assertIn('not admitted', out[2])
            self.assertEqual(tuple(self.conn.iterdump()), before)
            self.assertEqual(len(sc.pending(self.conn)), 3)
            self.assertEqual(sc.summary(self.conn)['state'], 'empty')
        after = self.sidecar.stat()
        self.assertEqual((identity.st_dev, identity.st_ino), (after.st_dev, after.st_ino))
        self.positive()

    def test_owned_pass_does_not_reacquire_at_each_source(self):
        stored, notable, note = self.step()
        self.assertEqual((stored, notable), (3, 3))
        self.assertEqual(note, 'sims +3')
        self.assertEqual([r[0] for r in self.conn.execute('SELECT compared FROM sims')], [80]*3)

    def test_disabled_invalid_read_only_and_caller_owned_paths_create_no_sidecar(self):
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('disabled loader')):
            for kw in ({'limit': 0}, {'max_pairs': 0}, {'max_seconds': 0}):
                self.assertEqual(sc.similarity_step(self.conn, self.sf, **kw), (0, 0, ''))
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        self.assertEqual(sc.compare_run(self.sf, self.conn, row, limit_peers=0), (0, 0, 0))
        with self.assertRaises(ValueError):
            sc.similarity_step(self.conn, self.sf, max_pairs=-1)
        sc.pending(self.conn); sc.summary(self.conn)
        self.conn.execute('INSERT INTO probe VALUES(7)')
        self.assertIn('active caller transaction', self.step()[2])
        with self.assertRaises(ValueError):
            sc.compare_run(self.sf, self.conn, row)
        self.assertTrue(self.conn.in_transaction)
        self.assertFalse(self.sidecar.exists())
        self.conn.rollback()  # ONLY this fixture's caller work
        self.positive()

    def test_different_disk_database_can_compare_while_first_is_owned(self):
        with closing(sqlite3.connect(self.root / 'other.db')) as other:
            self.conn.backup(other); other.row_factory = sqlite3.Row
            with sc.collector_ownership(self.conn) as acquired:
                self.assertTrue(acquired)
                row = other.execute('SELECT * FROM replays WHERE id=1').fetchone()
                self.assertEqual(sc.compare_run(self.sf, other, row, limit_peers=1,
                    reader=fixture.fixture.rs), (1, 0, 1))
                self.assertEqual(other.execute('SELECT compared FROM sims').fetchone()[0], 80)
                self.assertIn('collector busy', self.step()[2])
        self.positive()

    def test_normalized_alias_contends_with_original(self):
        alias = self.root / '..' / self.root.name / 'sample.db'
        with closing(sqlite3.connect(alias)) as other:
            with sc.collector_ownership(self.conn) as acquired:
                self.assertTrue(acquired)
                with sc.collector_ownership(other) as second:
                    self.assertFalse(second)
        self.positive()

    def unavailable_without_loader(self):
        before = tuple(self.conn.iterdump())
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('unsafe loader')):
            out = self.step()
        self.assertEqual(out[:2], (0, 0))
        self.assertIn('collector lock unavailable', out[2])
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def test_nonempty_sidecar_is_not_truncated_or_borrowed(self):
        self.sidecar.write_bytes(b'owned sentinel')
        self.unavailable_without_loader()
        self.assertEqual(self.sidecar.read_bytes(), b'owned sentinel')
        self.sidecar.rename(self.root / 'preserved-sentinel')
        self.positive()

    def test_multilink_database_abstains_until_alias_is_retired(self):
        alias = self.root / 'alias.db'
        os.link(self.db, alias)
        self.unavailable_without_loader()
        self.assertEqual(self.db.stat().st_nlink, 2)
        self.assertFalse(self.sidecar.exists())
        alias.unlink()  # exact fixture link created above, never shared data
        self.positive()

    def test_multilink_sidecar_is_not_used(self):
        self.sidecar.touch(mode=0o600)
        alias = self.root / 'alias.lock'
        os.link(self.sidecar, alias)
        self.unavailable_without_loader()
        self.assertEqual(self.sidecar.stat().st_size, 0)
        alias.unlink()
        self.positive()

    def test_symlink_sidecar_does_not_modify_target(self):
        target = self.root / 'preserved-target'
        target.write_bytes(b'owned sentinel')
        try:
            self.sidecar.symlink_to(target)
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable; Linux required')
            raise
        self.unavailable_without_loader()
        self.assertEqual(target.read_bytes(), b'owned sentinel')
        self.sidecar.unlink()  # this fixture's exact symlink, not its target
        self.positive()

    @unittest.skipUnless(os.name == 'posix', 'POSIX named pipe contract')
    def test_nonregular_fifo_abstains_without_waiting_for_a_peer(self):
        os.mkfifo(self.sidecar, 0o600)
        self.unavailable_without_loader()
        self.assertTrue(self.sidecar.exists())
        self.sidecar.unlink()  # only this fixture's unused FIFO
        self.positive()

    @unittest.skipUnless(os.name == 'posix', 'POSIX ownership/mode contract')
    def test_broadly_writable_sidecar_is_not_chmodded_or_used(self):
        self.sidecar.touch(mode=0o644)
        self.sidecar.chmod(0o644)
        self.unavailable_without_loader()
        self.assertEqual(self.sidecar.stat().st_mode & 0o777, 0o644)
        self.sidecar.chmod(0o600)  # only this fixture's mode
        self.positive()

    def test_lock_capability_failure_abstains_then_recovers(self):
        with mock.patch.object(sc, '_try_collector_lock', side_effect=OSError(errno.EIO, 'private failure')):
            self.unavailable_without_loader()
        self.positive()

    def test_replaced_name_during_acquire_is_not_an_ownership_proof(self):
        original = sc._try_collector_lock
        replacement = self.root / 'replacement.lock'
        replacement.touch(mode=0o600)
        def replace(fd):
            result = original(fd)
            os.replace(replacement, self.sidecar)
            return result
        with mock.patch.object(sc, '_try_collector_lock', side_effect=replace):
            self.unavailable_without_loader()
        if os.name == 'posix':
            self.assertFalse(replacement.exists())  # actual replaced inode, not an OS refusal
        self.positive()

    def test_exception_releases_kernel_handle_without_unlinking(self):
        with self.assertRaisesRegex(RuntimeError, 'fixture exit'):
            with sc.collector_ownership(self.conn) as acquired:
                self.assertTrue(acquired)
                identity = self.sidecar.stat()
                raise RuntimeError('fixture exit')
        self.assertEqual(self.sidecar.stat().st_ino, identity.st_ino)
        self.positive()

    def child_owner(self, inflight=False):
        code = '''import os, sqlite3, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import simcheck
c=sqlite3.connect(sys.argv[2]); c.row_factory=sqlite3.Row
with simcheck.collector_ownership(c) as held:
    assert held
    if sys.argv[3] == 'inflight':
        tools=str(Path(sys.argv[1]).parent/'tools')
        rs,why=simcheck._recsim(tools); assert rs is not None,why
        def compare(a,b,**limits):
            value=rs.compare_paths(a,b,**limits)
            assert value[0]=='compared' and value[1]['compared']==80
            assert not c.in_transaction
            print('MEASURED',flush=True)
            if sys.stdin.readline().strip()=='CRASH': os._exit(23)
            return value
        reader=SimpleNamespace(compare_paths=compare)
        simcheck._recsim=lambda *args:(reader,'fixture')
        sf=SimpleNamespace(replay_file=lambda r:(str(Path(sys.argv[2]).parent/(str(r['id'])+'.rec')),''))
        simcheck._similarity_step(c,sf,tools_dir=tools)
    else:
        print('HELD', flush=True)
        if sys.stdin.readline().strip() == 'CRASH': os._exit(23)
c.close()
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', code,
            str(Path(sc.__file__).parent), str(self.db), 'inflight' if inflight else 'lock'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if child.poll() is None:
                child.terminate(); child.wait(timeout=5)  # ONLY this spawned fixture
            child.stdin.close(); child.stdout.close(); child.stderr.close()
        self.addCleanup(cleanup)
        self.assertEqual(child.stdout.readline().strip(), 'MEASURED' if inflight else 'HELD')
        return child

    def test_crash_after_real_read_retries_unflushed_pair(self):
        child = self.child_owner(inflight=True)
        self.assertEqual(sc._cursor(self.conn, 'source'), 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 0)
        self.assertIn('collector busy', self.step()[2])
        with closing(sqlite3.connect(self.db)) as writer:
            with writer:
                writer.execute('INSERT INTO probe VALUES(1)')
        child.communicate('CRASH\n', timeout=5)
        self.assertEqual(child.returncode, 23)
        self.assertEqual(self.step()[:2], (3, 3))
        rows = self.conn.execute('SELECT a_id,b_id,compared FROM sims').fetchall()
        self.assertEqual({tuple(sorted(r[:2])) for r in rows}, {(1, 2), (1, 3), (2, 3)})
        self.assertEqual([r[2] for r in rows], [80]*3)

    def test_real_child_contention_and_abrupt_exit_recover(self):
        child = self.child_owner()
        self.assertIn('collector busy', self.step()[2])
        child.communicate('CRASH\n', timeout=5)
        self.assertEqual(child.returncode, 23)
        self.assertEqual(self.sidecar.stat().st_size, 0)
        self.positive()

    def test_lock_descriptor_is_not_inherited_by_exec(self):
        original = sc._try_collector_lock
        acted = []
        def check(fd):
            acted.append(os.get_inheritable(fd))
            return original(fd)
        with mock.patch.object(sc, '_try_collector_lock', side_effect=check):
            self.positive()
        self.assertEqual(acted, [False])


if __name__ == '__main__':
    unittest.main()
