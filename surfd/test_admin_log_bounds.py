#!/usr/bin/env python3
"""Real-file log tails: bounded acquisition, rotation/growth and redaction."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import admin

if os.environ.get('ADMIN_UNDER_TEST'):
	spec = importlib.util.spec_from_file_location('control_admin', os.environ['ADMIN_UNDER_TEST'])
	admin = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(admin)


class LogBounds(unittest.TestCase):
	def tail(self, data, *, growth=b'', replacement=None):
		with tempfile.TemporaryDirectory() as home:
			path = Path(home) / 'synthetic.log'
			path.write_bytes(data)
			other = Path(home) / 'rotated.log'
			if replacement is not None:
				other.write_bytes(replacement)
			reads, acquired = [], []
			real_open = open
			class File:
				def __init__(self, fh): self.fh, self.grown = fh, False
				def __getattr__(self, name): return getattr(self.fh, name)
				def __enter__(self): return self
				def __exit__(self, *args): self.fh.close()
				def acquire(self, method, size):
					if growth and not self.grown:
						self.grown = True
						with real_open(path, 'ab') as writer: writer.write(growth)
					reads.append((method, size))
					value = getattr(self.fh, method)(size)
					acquired.append(len(value))
					return value
				def read(self, size=-1): return self.acquire('read', size)
				def readline(self, size=-1): return self.acquire('readline', size)
			with mock.patch.object(admin, 'open', side_effect=lambda *a, **kw:
					File(real_open(other if replacement is not None else path, 'rb')), create=True):
				value = admin.tail_file(path, lines=5)
			self.assertTrue(reads)  # actual acquisition, not an early unavailable return
			self.assertTrue(all(0 <= size <= admin.LOG_TAIL_BYTES for _, size in reads), reads)
			self.assertLessEqual(sum(acquired), admin.LOG_TAIL_BYTES)
			return value, sum(acquired)

	def test_small_multiline_tail_acts_and_redacts(self):
		value, size = self.tail(b'old\naddress 192.0.2.7:27510\nlast\n')
		self.assertIn('last', value)
		self.assertNotIn('192.0.2.7', value)
		self.assertEqual(size, len(b'old\naddress 192.0.2.7:27510\nlast\n'))

	def test_newline_free_window_is_bounded_and_explicitly_incomplete(self):
		value, size = self.tail(b'x' * (admin.LOG_TAIL_BYTES * 3))
		self.assertEqual(size, admin.LOG_TAIL_BYTES)
		self.assertIn('byte window', value)
		self.assertNotIn('x' * 100, value)

	def test_growth_after_positioning_cannot_expand_acquisition(self):
		value, size = self.tail(b'initial\n', growth=b'late\n' * admin.LOG_TAIL_BYTES)
		self.assertEqual(size, len(b'initial\n'))
		self.assertEqual(value, 'initial')

	def test_opened_rotated_file_owns_size_and_position(self):
		value, size = self.tail(b'old\n' * admin.LOG_TAIL_BYTES, replacement=b'rotated control\n')
		self.assertEqual(value, 'rotated control')
		self.assertEqual(size, len(b'rotated control\n'))

	def test_large_multiline_window_keeps_complete_recent_lines(self):
		value, size = self.tail(b'old\n' * admin.LOG_TAIL_BYTES + b'new one\nnew two\n')
		self.assertEqual(size, admin.LOG_TAIL_BYTES)
		self.assertIn('new one\nnew two', value)
		self.assertIn('byte window', value)

	def test_unreadable_is_not_empty_measured_tail(self):
		with tempfile.TemporaryDirectory() as home:
			self.assertIn('cannot read', admin.tail_file(Path(home) / 'absent.log'))


if __name__ == '__main__':
	unittest.main()
