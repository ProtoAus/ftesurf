"""Real publisher-to-content-epoch seam, private files only."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import tascontent as content
import mapwatch
import zonepub_publish as publisher


class Settings(unittest.TestCase):
    def test_present_empty_disables_writer_hook_without_reading_env_file(self):
        with patch.dict(os.environ, {'SURFD_TAS_CONTENT_LEASE': ''}), \
             patch.object(publisher, 'env_value', side_effect=AssertionError('empty was collapsed')):
            with publisher.content_publication() as lease:
                self.assertIsNone(lease)
            with mapwatch.content_publication() as lease:
                self.assertIsNone(lease)

    def test_configured_writer_path_is_env_first_then_named_env_file(self):
        token = object()
        with patch.dict(os.environ, {'SURFD_TAS_CONTENT_LEASE': '/private/test.epoch'}), \
             patch.object(publisher, 'env_value', side_effect=AssertionError('env not first')), \
             patch.object(content, 'publication', return_value=token) as acquire:
            self.assertIs(publisher.content_publication(), token)
            acquire.assert_called_once_with('/private/test.epoch')
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(publisher, 'env_value', return_value='/private/from-file.epoch') as read, \
             patch.object(content, 'publication', return_value=token) as acquire:
            self.assertIs(publisher.content_publication(), token)
            read.assert_called_once_with('SURFD_TAS_CONTENT_LEASE', os.path.join('/srv/nvme/surfd', 'surfd.env'))
            acquire.assert_called_once_with('/private/from-file.epoch')


@unittest.skipUnless(os.name == 'posix', 'real POSIX content publication required')
class Publication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tas-publisher-', dir=os.environ.get('TAS_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.epoch = self.root / 'epoch'
        self.before = content.initialize(self.epoch)
        self.paths = [self.root / 'first.json', self.root / 'second.json']
        for path in self.paths:
            path.write_bytes(b'old')
        self.config = patch.dict(os.environ, {'SURFD_TAS_CONTENT_LEASE': str(self.epoch)})
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_actual_put_writes_both_inside_one_odd_epoch(self):
        real = publisher.write_file
        calls = []

        def observed(path, body):
            calls.append((path, self.epoch.read_bytes()))
            real(path, body)

        with patch.object(publisher, 'write_file', side_effect=observed):
            publisher.put(self.paths, [b'new-first', b'new-second'], 100)
        self.assertEqual([p.read_bytes() for p in self.paths], [b'new-first', b'new-second'])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(raw.endswith(b'00000000000000000001\n') for _, raw in calls))
        with content.snapshot(self.epoch) as lease:
            self.assertEqual(lease.stamp, content.Stamp(self.before.incarnation, 2))

    def test_actual_rollback_stays_in_same_lease_and_dirty_aborts_before_write(self):
        real = publisher.write_file
        calls = []

        def failure(path, body):
            calls.append(self.epoch.read_bytes())
            if len(calls) == 2:
                raise OSError('synthetic disk full')
            real(path, body)

        with patch.object(publisher, 'write_file', side_effect=failure):
            with self.assertRaisesRegex(OSError, 'synthetic disk full'):
                publisher.put(self.paths, [b'changed', b'changed'], 100)
        self.assertEqual([p.read_bytes() for p in self.paths], [b'old', b'old'])
        self.assertEqual(len(calls), 3)  # first ACTED, second failed, first restored
        self.assertTrue(all(raw.endswith(b'00000000000000000001\n') for raw in calls))
        with content.snapshot(self.epoch) as lease:
            self.assertEqual(lease.stamp.epoch, 2)
        self.epoch.write_bytes(self.epoch.read_bytes().replace(b'00000000000000000002', b'00000000000000000003'))
        with patch.object(publisher, 'write_file', side_effect=AssertionError('dirty writer ran')):
            with self.assertRaisesRegex(content.Unavailable, 'DIRTY'):
                publisher.put(self.paths, [b'wrong', b'wrong'], 100)
        self.assertEqual([p.read_bytes() for p in self.paths], [b'old', b'old'])

    def test_mapwatch_actual_fresh_and_replacement_share_outer_epoch(self):
        real = mapwatch._publish
        calls = []
        fresh = self.root / 'fresh.bsp'
        parts = [self.root / 'fresh.part', self.root / 'replacement.part']
        parts[0].write_bytes(b'new-map')
        parts[1].write_bytes(b'new-zone')

        def observed(part, final, isfresh):
            calls.append(self.epoch.read_bytes())
            return real(part, final, isfresh)

        with patch.object(mapwatch, '_publish', side_effect=observed):
            with mapwatch.content_publication():
                self.assertTrue(mapwatch.publish(str(parts[0]), str(fresh), True))
                self.assertTrue(mapwatch.publish(str(parts[1]), str(self.paths[0]), False))
        self.assertEqual(fresh.read_bytes(), b'new-map')
        self.assertEqual(self.paths[0].read_bytes(), b'new-zone')
        self.assertTrue(all(not p.exists() for p in parts))
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(raw.endswith(b'00000000000000000001\n') for raw in calls))
        with content.snapshot(self.epoch) as lease:
            self.assertEqual(lease.stamp.epoch, 2)

    def test_mapwatch_dirty_state_never_calls_mutator(self):
        self.epoch.write_bytes(self.epoch.read_bytes().replace(b'00000000000000000000', b'00000000000000000001'))
        part = self.root / 'unchanged.part'
        part.write_bytes(b'new')
        with patch.object(mapwatch, '_publish', side_effect=AssertionError('dirty writer ran')):
            with self.assertRaisesRegex(content.Unavailable, 'DIRTY'):
                mapwatch.publish(str(part), str(self.paths[0]), False)
        self.assertEqual(part.read_bytes(), b'new')
        self.assertEqual(self.paths[0].read_bytes(), b'old')


if __name__ == '__main__':
    unittest.main()
