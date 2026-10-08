"""Exact bounded reader bytes, never a claim about present file/authenticity."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_reader', ROOT/'tools/census/recsim.py')
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def source(n=80, newline='\n'):
    rows = ['FTESURF-REC 9', 'map synthetic', 'tickrate 100', 'begin']
    rows += ['in %d %d 0 %d 0 0 0 0 0 4' % (i, i, 100+i%7) for i in range(n)]
    return (newline.join(rows+['end %d' % n])+newline).encode()


def captured(data):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


class Sources(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.a, self.b = self.root/'a.rec', self.root/'b.rec'
        self.a.write_bytes(source()); self.b.write_bytes(source())

    def compare(self, **kw):
        return rs.compare_paths(str(self.a), str(self.b), **kw)

    def test_real_comparison_retains_metrics_and_captures_both_buffers(self):
        verdict, old = self.compare()
        self.assertEqual((verdict, old['compared'], old['match']), ('compared', 80, 1.0))
        self.assertNotIn('sources', old)  # unbounded default makes no capture promise
        verdict, d = self.compare(max_bytes=8192, max_moves=100)
        self.assertEqual(verdict, 'compared')
        self.assertEqual({k:v for k,v in d.items() if k != 'sources'}, old)
        self.assertEqual(d.get('sources'), {'version': 1, 'a': captured(source()), 'b': captured(source())})
        self.assertNotIn(str(self.root), str(d.get('sources')))

    def test_newlines_ignored_and_replacement_bytes_are_not_normalized_for_hash(self):
        hashes = set()
        for newline in ('\n', '\r\n', '\r'):
            data = b'# ignored \xff\x81\r\n' + source(newline=newline)
            self.a.write_bytes(data); self.b.write_bytes(data)
            verdict, d = self.compare(max_bytes=len(data), max_moves=80)
            self.assertEqual((verdict, d['compared'], d['match']), ('compared', 80, 1.0))
            snap = d.get('sources')
            self.assertEqual(snap, {'version':1, 'a':captured(data), 'b':captured(data)})
            if snap: hashes.add(snap['a']['sha256'])
        self.assertEqual(len(hashes), 3)

    def test_replacement_after_capture_does_not_rehash_current_path(self):
        original = rs.io.StringIO
        acted = []
        def replace(*args, **kw):
            if not acted:
                self.a.write_bytes(source(9)); acted.append(str(self.a))
            return original(*args, **kw)
        with mock.patch.object(rs.io, 'StringIO', side_effect=replace):
            verdict, d = self.compare(max_bytes=8192, max_moves=100)
        self.assertEqual(acted, [str(self.a)])
        self.assertEqual((verdict, d['compared'], d['match']), ('compared', 80, 1.0))
        self.assertEqual(self.a.read_bytes(), source(9))
        self.assertEqual(d.get('sources'), {'version':1, 'a':captured(source()), 'b':captured(source())})

    def test_caps_and_skips_never_return_partial_capture_measurement(self):
        for kw in ({'max_bytes':len(source())-1}, {'max_bytes':8192, 'max_moves':79}):
            verdict, d = self.compare(**kw)
            self.assertEqual(verdict, 'source limit')
            self.assertIsInstance(d, str)
        self.a.write_bytes(source(9))
        verdict, d = self.compare(max_bytes=8192, max_moves=100)
        self.assertEqual(verdict, 'too short')
        self.assertIsInstance(d, str)


if __name__ == '__main__': unittest.main()
