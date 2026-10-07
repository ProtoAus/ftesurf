"""Bounded comparison sources: synthetic files/SQLite only, no fleet writes."""
import importlib.util
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

rs = load('bounded_reader', ROOT/'tools/census/recsim.py')
sc = load('bounded_collector', ROOT/'surfd/simcheck.py')

def source(n=80, newline='\n'):
    rows = ['FTESURF-REC 9', 'map synthetic', 'tickrate 100', 'begin']
    rows += ['in %d %d 0 %d 0 0 0 0 0 4' % (j, j, 100+j%7) for j in range(n)]
    return (newline.join(rows+['end %d' % n])+newline).encode()

class Ingestion(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.a, self.b = self.root/'a.rec', self.root/'b.rec'
        self.a.write_bytes(source())
        self.b.write_bytes(source())

    def compare(self, **limits):
        # Predecessor performs the comparison; red is behavioral, not TypeError.
        kw = limits if 'max_bytes' in inspect.signature(rs.compare_paths).parameters else {}
        return rs.compare_paths(str(self.a), str(self.b), **kw)

    def test_bytes_limit_counts_ignored_data_and_abstains(self):
        self.a.write_bytes(b'# ignored\n'*500+source())
        self.assertEqual(self.compare(max_bytes=4096, max_moves=100)[0], 'source limit')
        self.assertEqual(self.compare()[0], 'compared')  # old optional API retains scope

    def test_move_limit_abstains_instead_of_comparing_a_prefix(self):
        self.assertEqual(self.compare(max_bytes=8192, max_moves=79)[0], 'source limit')
        verdict, d = self.compare(max_bytes=8192, max_moves=80)
        self.assertEqual(verdict, 'compared')
        self.assertEqual((d['match'], d['compared'], d['moves_a']), (1.0,80,80))

    def test_capture_reads_only_cap_plus_one_even_for_growth(self):
        original = open
        reads = []
        def opening(path, *args, **kwargs):
            fh = original(path, *args, **kwargs)
            if args and args[0] == 'rb':
                with original(path, 'ab') as growing:
                    growing.write(b'# trailing\n'*1000)
                wrapped = mock.MagicMock(wraps=fh)
                wrapped.__enter__.return_value = wrapped
                wrapped.__exit__.side_effect = lambda *a: fh.close()
                def read(n=-1):
                    reads.append(n)
                    return fh.read(n)
                wrapped.read.side_effect = read
                return wrapped
            return fh
        self.a.write_bytes(source())
        with mock.patch('builtins.open', side_effect=opening):
            verdict, detail = self.compare(max_bytes=3000, max_moves=100)
        self.assertEqual(verdict, 'source limit')
        self.assertEqual(reads, [3001])  # no stat-size trust, bounded actual read
        self.assertNotIn(str(self.root), detail)

    def test_exact_byte_boundary_and_universal_newlines(self):
        for newline in ('\n','\r\n','\r'):
            data = source(newline=newline)
            self.a.write_bytes(data); self.b.write_bytes(data)
            verdict, d = self.compare(max_bytes=len(data), max_moves=80)
            self.assertEqual(verdict, 'compared')
            self.assertEqual((d['match'],d['compared']), (1.0,80))

    def test_collector_stores_limit_as_unjudgeable_not_a_measurement(self):
        conn = sqlite3.connect(':memory:');conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        sc.ensure_schema(conn)
        conn.execute('CREATE TABLE replays (id INTEGER PRIMARY KEY, map TEXT, track INTEGER, leg INTEGER, kind TEXT, tier TEXT, player TEXT)')
        for i in (1,2):
            conn.execute("INSERT INTO replays VALUES (?, 'synthetic',0,0,'run','ranked','synthetic')",(i,))
        conn.commit()
        sf = mock.Mock()
        sf.replay_file.side_effect = lambda row: (str(self.a if row['id']==1 else self.b),'')
        with mock.patch.object(sc, 'MAX_SOURCE_MOVES', 79, create=True):
            stored, notable, note = sc.similarity_step(conn, sf, tools_dir=str(ROOT/'tools'))
        self.assertEqual((stored,notable), (1,0))
        row = conn.execute('SELECT verdict, compared, reason FROM sims').fetchone()
        self.assertEqual((row['verdict'],row['compared']), ('skip',0))
        self.assertIn('limit', row['reason'])
        self.assertIn('unjudgeable', note)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM replays').fetchone()[0], 2)

    def test_old_reader_capability_is_unavailable_not_unbounded(self):
        tools = self.root/'tools';(tools/'census').mkdir(parents=True)
        (tools/'census/recsim.py').write_text("def compare_paths(a,b):\n    return 'compared', {}\n")
        mod, why = sc._recsim(str(tools))
        self.assertIsNone(mod)
        self.assertIn('bounded', why)

if __name__ == '__main__':
    unittest.main()
