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
                                kwargs.get('bytes', 4096), kwargs.get('seconds', 10))

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
