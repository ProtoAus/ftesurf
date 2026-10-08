"""Source budgets are configuration, never invalid read-all sizes or evidence."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('limit_reader', HERE/'census/recsim.py')
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


class Limits(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.a, self.b = Path(temp.name)/'a.rec', Path(temp.name)/'b.rec'
        self.data = ('FTESURF-REC 9\nmap synthetic\ntickrate 100\nbegin\n' + ''.join(
            'in %d %d 0 %d 0 0 0 0 0 4\n' % (i, i, 100+i%7) for i in range(80))
            + 'end 80\n').encode()
        self.a.write_bytes(self.data); self.b.write_bytes(self.data)

    def test_invalid_configuration_rejected_before_any_io_or_skip(self):
        invalid = (-2, -1, True, False, 1.5, float('nan'), float('inf'), '80')
        for name in ('max_bytes', 'max_moves'):
            for value in invalid + ((sys.maxsize,) if name == 'max_bytes' else ()):
                with self.subTest(name=name, value=value):
                    before = list(rs.SKIPPED)
                    with mock.patch('builtins.open', side_effect=AssertionError('I/O acted')) as opened:
                        for strict in (False, True):
                            with self.assertRaises(ValueError):
                                rs.parse_rec(str(self.a), strict=strict, **{name:value})
                        for peer in (self.a, self.b):
                            with self.assertRaises(ValueError):
                                rs.compare_paths(str(self.a), str(peer), **{name:value})
                    opened.assert_not_called()
                    self.assertEqual(rs.SKIPPED, before)

    def test_actual_capture_reads_only_limit_plus_one(self):
        opened = open
        sizes = []
        class Capture:
            def __init__(self, fh): self.fh = fh
            def __enter__(self): return self
            def __exit__(self, *args): self.fh.close()
            def read(self, size):
                sizes.append(size)
                return self.fh.read(size)
        def traced(path, mode, **kw):
            self.assertEqual(mode, 'rb')
            return Capture(opened(path, mode, **kw))
        with mock.patch('builtins.open', side_effect=traced):
            verdict, result = rs.compare_paths(str(self.a), str(self.b),
                                               max_bytes=len(self.data), max_moves=80)
        self.assertEqual(sizes, [len(self.data)+1]*2)  # both real sources ACTED
        self.assertEqual((verdict, result['compared'], result['match']), ('compared',80,1.))
        self.assertEqual(result['sources']['a']['bytes'], len(self.data))

    def test_valid_defaults_and_exact_limits_keep_metrics(self):
        verdict, old = rs.compare_paths(str(self.a), str(self.b))
        self.assertEqual((verdict, old['compared']), ('compared',80))
        verdict, bounded = rs.compare_paths(str(self.a), str(self.b),
                                            max_bytes=len(self.data), max_moves=80)
        self.assertEqual(verdict, 'compared')
        self.assertEqual({k:v for k,v in bounded.items() if k != 'sources'}, old)
        for limits in ({'max_bytes':0}, {'max_moves':0},
                       {'max_bytes':len(self.data)-1}, {'max_moves':79}):
            verdict, result = rs.compare_paths(str(self.a), str(self.b), **limits)
            self.assertEqual(verdict, rs.SKIP_SOURCE_LIMIT)
            self.assertIsInstance(result, str)  # no prefix score/snapshot


if __name__ == '__main__': unittest.main()
