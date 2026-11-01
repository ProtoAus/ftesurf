"""Private real-kernel content-lease falsifiers; never touch a live epoch."""
from pathlib import Path
import os
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import tascontent as content


@unittest.skipUnless(os.name == 'posix', 'real POSIX flock required')
class ContentLease(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tas-content-', dir=os.environ.get('TAS_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'assets.epoch'
        self.first = content.initialize(self.path)

    def child(self, script, pass_fds=()):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(content.__file__).parent)
        proc = subprocess.Popen([sys.executable, '-B', '-c', script, str(self.path), str(self.root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, pass_fds=pass_fds)
        self.addCleanup(self.stop_child, proc)
        return proc

    @staticmethod
    def stop_child(proc):
        if proc.poll() is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        proc.wait(5)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()

    def line(self, proc):
        ready, _, _ = select.select([proc.stdout], [], [], 5)
        self.assertTrue(ready, 'owned actor did not signal')
        return proc.stdout.readline().strip()

    def test_real_reader_blocks_acting_writer_then_allows_same_actor(self):
        script = '''import sys
from pathlib import Path
import tascontent as c
p=Path(sys.argv[1]); root=Path(sys.argv[2])
print('READY',flush=True)
sys.stdin.readline()
try:
 with c.publication(p,timeout=0):print('WRONG_ENTERED',flush=True)
except c.Unavailable as e:print(str(e),flush=True)
sys.stdin.readline()
with c.publication(p,timeout=1):
 (root/'changed').write_text('writer ACTED')
 print('ENTERED',flush=True)
'''
        with content.snapshot(self.path) as reader:
            self.assertEqual(reader.stamp, self.first)
            proc = self.child(script)
            self.assertEqual(self.line(proc), 'READY')
            proc.stdin.write('attempt\n'); proc.stdin.flush()
            self.assertEqual(self.line(proc), 'CONTENT_LEASE_BUSY')
            self.assertFalse((self.root / 'changed').exists())
        proc.stdin.write('again\n'); proc.stdin.flush()
        self.assertEqual(self.line(proc), 'ENTERED')
        self.assertEqual(proc.wait(5), 0)
        self.assertEqual((self.root / 'changed').read_text(), 'writer ACTED')
        with content.snapshot(self.path) as after:
            self.assertEqual(after.stamp, content.Stamp(self.first.incarnation, 2))

    def test_nested_publication_is_one_pair_and_upgrade_is_refused(self):
        with content.publication(self.path) as writer:
            self.assertEqual(writer.stamp.epoch, 1)
            with content.publication(self.path) as nested:
                self.assertEqual(nested, writer)
            with self.assertRaisesRegex(content.Unavailable, 'LOCK_ORDER'):
                with content.snapshot(self.path):
                    self.fail('read of in-progress writer was admitted')
        with content.snapshot(self.path) as reader:
            self.assertEqual(reader.stamp.epoch, 2)
            with content.snapshot(self.path) as nested:
                self.assertEqual(nested, reader)
            with self.assertRaisesRegex(content.Unavailable, 'LOCK_ORDER'):
                with content.publication(self.path):
                    self.fail('upgrade was admitted')

    def test_exception_advances_epoch_and_new_file_never_reuses_incarnation(self):
        with self.assertRaisesRegex(RuntimeError, 'partial'):
            with content.publication(self.path):
                (self.root / 'changed').write_text('partial mutation ACTED')
                raise RuntimeError('partial')
        with content.snapshot(self.path) as after:
            self.assertNotEqual(after.stamp, self.first)
            self.assertEqual(after.stamp.epoch, 2)
        replacement = content.initialize(self.root / 'new.epoch')
        self.assertEqual(replacement.epoch, 0)
        self.assertNotEqual(replacement.incarnation, self.first.incarnation)
        with self.assertRaises(FileExistsError):
            content.initialize(self.path)

    def test_killed_real_writer_leaves_dirty_not_automatic_repair(self):
        script = '''import sys
from pathlib import Path
import tascontent as c
with c.publication(Path(sys.argv[1])):
 (Path(sys.argv[2])/'changed').write_text('killed writer ACTED')
 print('ODD',flush=True)
 sys.stdin.readline()
'''
        proc = self.child(script)
        self.assertEqual(self.line(proc), 'ODD')
        self.assertEqual((self.root / 'changed').read_text(), 'killed writer ACTED')
        proc.kill(); proc.wait(5)
        for acquire in (content.snapshot, content.publication):
            with self.subTest(acquire=acquire.__name__), self.assertRaisesRegex(content.Unavailable, 'DIRTY'):
                with acquire(self.path):
                    self.fail('dirty generation admitted')
        self.assertTrue(self.path.read_bytes().endswith(b'00000000000000000001\n'))

    def test_inherited_reader_survives_parent_context_close(self):
        with content.snapshot(self.path) as reader:
            script = '''import os,sys
print('INHERITED',flush=True)
sys.stdin.readline()
os.close(%d)
''' % reader.fd
            proc = self.child(script, pass_fds=(reader.fd,))
            self.assertEqual(self.line(proc), 'INHERITED')
        with self.assertRaisesRegex(content.Unavailable, 'BUSY'):
            with content.publication(self.path, timeout=0):
                self.fail('inherited shared lease was dropped')
        proc.stdin.write('close\n'); proc.stdin.flush()
        self.assertEqual(proc.wait(5), 0)
        with content.publication(self.path):
            (self.root / 'changed').write_text('after descendant')
        with content.snapshot(self.path) as after:
            self.assertEqual(after.stamp.epoch, 2)

    def test_initial_admission_checks_named_identity_before_mutation(self):
        original = self.path.read_bytes()
        named = list(os.stat(self.path, follow_symlinks=False))
        named[1] += 1
        foreign = os.stat_result(named)
        for acquire in (content.snapshot, content.publication):
            with self.subTest(acquire=acquire.__name__), \
                 patch.object(content.os, 'stat', return_value=foreign), \
                 self.assertRaisesRegex(content.Unavailable, 'REPLACED'):
                with acquire(self.path):
                    self.fail('unbound initial lease admitted')
            self.assertEqual(self.path.read_bytes(), original)

    def test_nested_scopes_validate_named_identity(self):
        for acquire in (content.snapshot, content.publication):
            with self.subTest(acquire=acquire.__name__), acquire(self.path):
                named = list(os.stat(self.path, follow_symlinks=False))
                named[1] += 1
                with patch.object(content.os, 'stat', return_value=os.stat_result(named)), \
                     self.assertRaisesRegex(content.Unavailable, 'REPLACED'):
                    with acquire(self.path):
                        self.fail('unbound nested lease admitted')

    def test_read_completion_rejects_changed_record(self):
        original = self.path.read_bytes()
        valid = content._record(content.Stamp('f' * 32, 4))
        self.assertEqual(len(valid), content.SIZE)
        for changed in (b'unexpected fixture record\n', valid):
            with self.subTest(same_length=len(changed) == content.SIZE):
                self.path.write_bytes(original)
                with self.assertRaisesRegex(content.Unavailable, 'CHANGED'):
                    with content.snapshot(self.path):
                        self.path.write_bytes(changed)
                self.assertEqual(self.path.read_bytes(), changed)

    def test_writer_never_repairs_changed_record_on_exit(self):
        original = self.path.read_bytes()
        valid = content._record(content.Stamp('f' * 32, 4))
        self.assertEqual(len(valid), content.SIZE)
        for changed in (b'unexpected fixture record\n', valid):
            with self.subTest(same_length=len(changed) == content.SIZE):
                self.path.write_bytes(original)
                with self.assertRaisesRegex(content.Unavailable, 'CHANGED'):
                    with content.publication(self.path):
                        self.path.write_bytes(changed)
                self.assertEqual(self.path.read_bytes(), changed)

    def test_bad_records_links_permissions_missing_and_overflow_refuse(self):
        original = self.path.read_bytes()
        for raw in (b'', b'wrong', original[:-1], original + b'junk',
                    original.replace(b'00000000000000000000', b'99999999999999999999')):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(content.Unavailable, 'RECORD'):
                    with content.snapshot(self.path):
                        self.fail('invalid record admitted')
        self.path.write_bytes(original)
        link = self.root / 'hardlink'; os.link(self.path, link)
        with self.assertRaisesRegex(content.Unavailable, 'IDENTITY'):
            with content.snapshot(self.path):
                self.fail('linked file admitted')
        link.unlink()
        alias = self.root / 'symlink'; alias.symlink_to(self.path)
        with self.assertRaises((OSError, content.Unavailable)):
            with content.snapshot(alias):
                self.fail('symlink admitted')
        self.path.chmod(0o604)
        with self.assertRaisesRegex(content.Unavailable, 'IDENTITY'):
            with content.snapshot(self.path):
                self.fail('insecure file admitted')
        self.path.chmod(0o600)
        with self.assertRaises(FileNotFoundError):
            with content.snapshot(self.root / 'missing'):
                self.fail('missing file auto-created')
        self.path.write_bytes(original.replace(b'00000000000000000000', b'18446744073709551614'))
        with content.snapshot(self.path) as last:
            self.assertEqual(last.stamp.epoch, content.MAX_EPOCH - 1)
        with self.assertRaisesRegex(content.Unavailable, 'EXHAUSTED'):
            with content.publication(self.path):
                self.fail('counter wrapped')
        self.path.write_bytes(original)
        with content.snapshot(self.path) as positive:
            self.assertEqual(positive.stamp, self.first)  # every refusal retained an acting positive


@unittest.skipIf(os.name == 'posix', 'POSIX lease available')
class UnsupportedLease(unittest.TestCase):
    def test_non_posix_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(content.Unavailable, 'UNSUPPORTED'):
            content.initialize('/not-used/assets.epoch')


if __name__ == '__main__':
    unittest.main()
