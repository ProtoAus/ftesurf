#!/usr/bin/env python3
"""Exact plot acquisition allowance: real binary reads and complete-line controls."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import recplot

if os.environ.get('RECPLOT_UNDER_TEST'):
	spec = importlib.util.spec_from_file_location('control_recplot', os.environ['RECPLOT_UNDER_TEST'])
	recplot = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(recplot)

HEADER = b'FTESURF-REC 9\nmap synthetic\ntickrate 100\nbegin\n'
SAMPLE = b'0 1 2 3 300 400 0\n'


class PlotBudget(unittest.TestCase):
	def parse(self, data, limit):
		with tempfile.TemporaryDirectory() as home:
			path = Path(home) / 'synthetic.rec'; path.write_bytes(data)
			reads, acquired = [], []
			real_open = open
			class File:
				def __init__(self, fh): self.fh = fh
				def __enter__(self): return self
				def __exit__(self, *args): self.fh.close()
				def readline(self, size=-1):
					reads.append(size)
					value = self.fh.readline(size)
					acquired.append(len(value))
					return value
			with mock.patch.object(recplot, 'open', side_effect=lambda *a, **kw: File(real_open(path, 'rb')), create=True):
				out = recplot.parse(path, max_bytes=limit)
			self.assertTrue(all(0 < size <= recplot.LINE_MAX for size in reads), reads)
			self.assertLessEqual(sum(acquired), limit)
			return out, sum(acquired), reads

	def test_normal_complete_plot_acts_without_truncation(self):
		data = HEADER + SAMPLE + b'end 1 1 0 0 0 0 0 0 0 0\n'
		out, acquired, reads = self.parse(data, len(data) + 1)
		self.assertTrue(reads)
		self.assertEqual(acquired, len(data))
		self.assertTrue(out['ok'])
		self.assertFalse(out['truncated'])
		self.assertEqual((out['n'], out['spd'], out['stats']['max_speed']), (1, [500.0], 500.0))
		self.assertEqual(out['notes'], [])

	def test_zero_one_and_nonaligned_limits_never_overshoot(self):
		for limit in (0, 1, len(HEADER) - 1, len(HEADER) + 3):
			with self.subTest(limit=limit):
				out, acquired, reads = self.parse(HEADER + SAMPLE * 3, limit)
				self.assertEqual(acquired, limit)
				if limit == 0: self.assertEqual(reads, [])
				if out['ok']:
					self.assertTrue(out['truncated'])
					self.assertEqual(out['n'], 0)

	def test_at_cap_complete_line_is_conservatively_truncated_without_probe(self):
		data = HEADER + SAMPLE
		out, acquired, reads = self.parse(data, len(data))
		self.assertEqual(acquired, len(data))
		self.assertTrue(out['truncated'])
		self.assertEqual(out['n'], 1)
		self.assertIn('stopped at', ' '.join(out['notes']))

	def test_cap_inside_sample_never_interprets_valid_prefix_as_complete_row(self):
		data = HEADER + SAMPLE.rstrip(b'\n') + b' 99 99\n'
		limit = len(HEADER) + len(SAMPLE.rstrip(b'\n'))
		out, acquired, reads = self.parse(data, limit)
		self.assertEqual(acquired, limit)
		self.assertTrue(out['truncated'])
		self.assertEqual(out['n'], 0)

	def test_overlong_line_drain_is_bounded_and_recovery_still_acts(self):
		long = b'ignored ' + b'x' * (recplot.LINE_MAX * 3) + b'\n'
		data = HEADER + SAMPLE + long + SAMPLE
		out, acquired, reads = self.parse(data, len(HEADER) + len(SAMPLE) + recplot.LINE_MAX + 7)
		self.assertTrue(out['truncated'])
		self.assertEqual(out['n'], 1)
		out, acquired, reads = self.parse(data, len(data) + 1)
		self.assertFalse(out['truncated'])
		self.assertEqual(out['n'], 2)
		self.assertIn('1 line(s) over', ' '.join(out['notes']))

	def test_invalid_byte_allowances_refuse_before_opening(self):
		for value in (-1, 1.5, True, False, '100', None, float('inf')):
			with self.subTest(value=value), mock.patch.object(recplot, 'open', create=True) as opened:
				out = recplot.parse('synthetic-not-opened.rec', max_bytes=value)
				opened.assert_not_called()
				self.assertFalse(out['ok'])
				self.assertIn('parse failed', out['error'])


if __name__ == '__main__':
	unittest.main()
