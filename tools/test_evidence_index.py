"""Small POSIX controls for the read-only off-box copy index, not run verdicts.

Set EVIDENCE_TEST_ROOT to an owned task directory; never uses system temp or a
canonical gamedir. Run through unittest on the actual source host.
"""
import hashlib
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evidence_index as subject


@unittest.skipUnless(os.name == 'posix', 'source index requires POSIX openat/nofollow')
class EvidenceIndexTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get('EVIDENCE_TEST_ROOT')
        if not parent:
            raise RuntimeError('EVIDENCE_TEST_ROOT must name the owned task fixture')
        self.temporary = tempfile.TemporaryDirectory(prefix='index-', dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ('runs', 'evidence'):
            (self.root / name).mkdir()
        self.data = b'opaque existing evidence\x00\xff\n' * 4
        (self.root / 'runs/a.rec').write_bytes(self.data)
        (self.root / 'evidence/empty.part').write_bytes(b'')

    def run_index(self, **kwargs):
        return subject.snapshot(self.root, kwargs.get('files', 100),
                                kwargs.get('bytes', 4096), kwargs.get('seconds', 10),
                                kwargs.get('stage_store'))

    def test_real_read_exact_and_no_source_byte_or_identity_change(self):
        before = {p: subject._identity(p.stat()) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(subject.os, 'read', wraps=os.read) as acted:
            result = self.run_index()
        self.assertGreater(acted.call_count, 0)
        self.assertEqual(result['deferred'], [])
        rows = {row['rel']: row for row in result['files']}
        self.assertEqual(rows['runs/a.rec']['sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(rows['evidence/empty.part']['sha256'], hashlib.sha256(b'').hexdigest())
        self.assertEqual(result['read_bytes'], len(self.data))
        self.assertEqual(before, {p: subject._identity(p.stat()) for p in before})

    def test_same_size_edit_with_restored_mtime_has_new_digest(self):
        first = self.run_index()
        path = self.root / 'runs/a.rec'
        before = path.stat()
        path.write_bytes(b'X' * len(self.data))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        second = self.run_index()
        a = next(x for x in first['files'] if x['rel'] == 'runs/a.rec')
        b = next(x for x in second['files'] if x['rel'] == 'runs/a.rec')
        self.assertEqual(a['mtime_ns'], b['mtime_ns'])
        self.assertNotEqual(a['sha256'], b['sha256'])

    def test_symlink_directory_and_file_and_hardlink_are_explicitly_deferred(self):
        (self.root / 'runs/link.rec').symlink_to(self.root / 'runs/a.rec')
        (self.root / 'runs/linked-directory').symlink_to(self.root / 'evidence', target_is_directory=True)
        os.link(self.root / 'runs/a.rec', self.root / 'evidence/hard.rec')
        result = self.run_index()
        self.assertEqual({x['rel'] for x in result['files']}, {'evidence/empty.part'})
        self.assertEqual({x['rel'] for x in result['deferred']},
                         {'runs/link.rec', 'runs/linked-directory', 'runs/a.rec', 'evidence/hard.rec'})

    def test_fifo_is_not_read_or_blocked_and_control_file_acts(self):
        os.mkfifo(self.root / 'evidence/pipe.rec')
        result = self.run_index()
        self.assertIn('runs/a.rec', {x['rel'] for x in result['files']})
        self.assertIn('evidence/pipe.rec', {x['rel'] for x in result['deferred']})

    def test_edit_during_real_read_is_deferred_not_green(self):
        original = os.read
        changed = False

        def read(fd, count):
            nonlocal changed
            data = original(fd, count)
            if data and not changed:
                changed = True
                with (self.root / 'runs/a.rec').open('ab') as stream:
                    stream.write(b'late')
            return data

        with patch.object(subject.os, 'read', side_effect=read):
            result = self.run_index()
        self.assertTrue(changed)
        self.assertEqual({x['rel'] for x in result['files']}, {'evidence/empty.part'})
        self.assertEqual(result['deferred'], [dict(rel='runs/a.rec', reason='changed-during-read')])

    def test_unreadable_subtree_is_not_silently_complete(self):
        path = self.root / 'runs/private'
        path.mkdir()
        (path / 'a.rec').write_bytes(b'not readable')
        path.chmod(0)
        try:
            if os.geteuid() == 0:
                self.skipTest('root bypasses fixture permissions')
            with self.assertRaises(PermissionError):
                self.run_index()
        finally:
            path.chmod(0o700)

    def test_exact_byte_budget_and_exhaustion_and_entry_bound(self):
        self.assertEqual(self.run_index(bytes=len(self.data))['read_bytes'], len(self.data))
        with self.assertRaises(RuntimeError):
            self.run_index(bytes=len(self.data) - 1)
        with self.assertRaises(RuntimeError):
            self.run_index(files=1)

    def test_invalid_budgets_and_deadline_do_not_read(self):
        for seconds in (0, -1, True, math.inf, math.nan):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.run_index(seconds=seconds)
        with patch.object(subject.os, 'read', wraps=os.read) as read:
            with patch.object(subject.time, 'monotonic', side_effect=[100, 102]):
                with self.assertRaises(RuntimeError):
                    self.run_index(seconds=1)
            self.assertEqual(read.call_count, 0)

    def stage_pair(self, scope='evidence'):
        temporary = tempfile.TemporaryDirectory(prefix='stage-store-', dir=os.environ['EVIDENCE_TEST_ROOT'])
        self.addCleanup(temporary.cleanup)
        store = Path(temporary.name) / 'evidence'
        (store / 'map').mkdir(parents=True)
        (self.root / scope / 'map').mkdir()
        source = self.root / scope / 'map/stage.rec'
        source.write_bytes(self.data)
        kept = store / 'map/stage.rec'
        os.link(source, kept)
        return store, source, kept

    def test_known_stage_pair_reads_exact_bytes_only_with_explicit_store(self):
        store, source, kept = self.stage_pair()
        before = subject._identity(source.stat())
        default = self.run_index()
        self.assertIn('evidence/map/stage.rec', {x['rel'] for x in default['deferred']})
        with patch.object(subject.os, 'read', wraps=os.read) as acted:
            result = self.run_index(stage_store=store)
        self.assertGreater(acted.call_count, 0)
        self.assertEqual(result['deferred'], [])
        row = next(x for x in result['files'] if x['rel'] == 'evidence/map/stage.rec')
        self.assertTrue(row['known_stage_link'])
        self.assertEqual(row['sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(before, subject._identity(source.stat()))
        self.assertEqual(before, subject._identity(kept.stat()))

    def test_known_stage_store_wrong_inode_is_not_an_explained_link(self):
        store, source, kept = self.stage_pair()
        kept.unlink()
        kept.write_bytes(self.data)
        os.link(source, store.parent / 'unknown-alias')
        result = self.run_index(stage_store=store)
        self.assertIn('runs/a.rec', {x['rel'] for x in result['files']})
        self.assertIn(dict(rel='evidence/map/stage.rec', reason='unbound-stage-link'), result['deferred'])
        kept.unlink()
        missing = self.run_index(stage_store=store)
        self.assertIn(dict(rel='evidence/map/stage.rec', reason='FileNotFoundError'), missing['deferred'])
        self.assertIn('runs/a.rec', {x['rel'] for x in missing['files']})

    def test_stage_third_link_remains_deferred(self):
        store, source, _kept = self.stage_pair()
        os.link(source, store.parent / 'third-link')
        result = self.run_index(stage_store=store)
        self.assertEqual(source.stat().st_nlink, 3)
        self.assertIn('evidence/map/stage.rec', {x['rel'] for x in result['deferred']})
        self.assertIn('runs/a.rec', {x['rel'] for x in result['files']})

    def test_stage_exception_does_not_admit_runs_aliases(self):
        store, _source, _kept = self.stage_pair('runs')
        result = self.run_index(stage_store=store)
        self.assertIn('runs/map/stage.rec', {x['rel'] for x in result['deferred']})
        self.assertIn('runs/a.rec', {x['rel'] for x in result['files']})

    def test_stage_store_root_and_component_aliases_refused(self):
        store, source, kept = self.stage_pair()
        for bad in (self.root / 'evidence', self.root):
            with self.assertRaises(ValueError):
                self.run_index(stage_store=bad)
        alias_parent = store.parent / 'alias-root'
        alias_parent.mkdir()
        alias = alias_parent / 'evidence'
        alias.symlink_to(store, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_index(stage_store=alias)
        directory = store / 'map'
        directory.rename(store / 'elsewhere')
        directory.symlink_to(store / 'elsewhere', target_is_directory=True)
        result = self.run_index(stage_store=store)
        self.assertIn('evidence/map/stage.rec', {x['rel'] for x in result['deferred']})
        self.assertEqual(source.read_bytes(), self.data)

    def test_mutation_through_known_stage_alias_acts_and_defers(self):
        store, source, kept = self.stage_pair()
        original = os.read
        inode = source.stat().st_ino
        changed = False

        def read(fd, count):
            nonlocal changed
            data = original(fd, count)
            if data and os.fstat(fd).st_ino == inode and not changed:
                changed = True
                with kept.open('ab') as stream:
                    stream.write(b'late')
            return data

        with patch.object(subject.os, 'read', side_effect=read):
            result = self.run_index(stage_store=store)
        self.assertTrue(changed)
        self.assertIn(dict(rel='evidence/map/stage.rec', reason='changed-during-read'), result['deferred'])
        self.assertIn('runs/a.rec', {x['rel'] for x in result['files']})

    def test_alias_root_and_parent_escape_are_refused(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            subject.snapshot(alias, 100, 4096, 10)
        for relative in ('runs/../outside', '/runs/a.rec', 'keys/private'):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                subject._open_relative(self.root, relative)


if __name__ == '__main__':
    unittest.main()
