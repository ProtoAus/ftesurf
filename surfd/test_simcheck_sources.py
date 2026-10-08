"""Historical compared-buffer provenance: real parser and temporary SQLite only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


rs = load('captured_reader', ROOT/'tools/census/recsim.py')
sc = load('captured_collector', ROOT/'surfd/simcheck.py')


def source(n=80, tag=b''):
    rows = ['FTESURF-REC 9', 'map synthetic', 'tickrate 100', 'begin']
    rows += ['in %d %d 0 %d 0 0 0 0 0 4' % (i, i, 100+i%7) for i in range(n)]
    return tag + ('\n'.join(rows+['end %d' % n])+'\n').encode()


def capture(a, b):
    def one(data): return {'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data)}
    return {'version':1, 'a':one(a), 'b':one(b)}


class StoredSources(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); self.db = self.root/'sample.db'
        self.conn = sqlite3.connect(str(self.db)); self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        sc.ensure_schema(self.conn)
        self.conn.executescript('''CREATE TABLE replays
            (id INTEGER PRIMARY KEY, map TEXT, track INTEGER, leg INTEGER, kind TEXT, tier TEXT, player TEXT);
            CREATE TABLE probe (n INTEGER);
            INSERT INTO replays VALUES (1,'synthetic',0,0,'run','ranked','synthetic');
            INSERT INTO replays VALUES (2,'synthetic',0,0,'run','ranked','synthetic');
            INSERT INTO replays VALUES (3,'synthetic',0,0,'run','ranked','synthetic');''')
        self.data = {i:source(tag=('# source%d\n' % i).encode()) for i in (1,2,3)}
        self.paths = {i:self.root/('%d.rec' % i) for i in (1,2,3)}
        for i in self.paths: self.paths[i].write_bytes(self.data[i])
        self.sf = SimpleNamespace(replay_file=lambda row:(str(self.paths[row['id']]), ''))

    def run_source(self, rid=1, reader=rs, max_pairs=1):
        row = self.conn.execute('SELECT * FROM replays WHERE id=?',(rid,)).fetchone()
        with mock.patch.object(sc, '_recsim', return_value=(reader,'')):
            return sc.compare_run(self.sf, self.conn, row, limit_peers=max_pairs)

    def snap(self, row):
        return json.loads(row['source_capture']) if 'source_capture' in row.keys() and row['source_capture'] else None

    def test_real_capture_survives_post_compare_replacement_and_reopen(self):
        acted = []
        def compare(a, b, **kw):
            self.assertFalse(self.conn.in_transaction)
            with sqlite3.connect(str(self.db)) as writer:
                writer.execute('INSERT INTO probe VALUES (1)')  # writer ACTS during reader
            verdict, d = rs.compare_paths(a,b,**kw)
            self.paths[1].write_bytes(source(9)); self.paths[2].write_bytes(source(9))
            acted.append((verdict,d['compared']))
            return verdict,d
        self.assertEqual(self.run_source(reader=SimpleNamespace(compare_paths=compare)),(1,0,1))
        self.assertEqual(acted,[('compared',80)])
        row = self.conn.execute('SELECT * FROM sims').fetchone()
        self.assertEqual((row['verdict'],row['match'],row['compared']),('compared',1.0,80))
        self.assertEqual(self.snap(row),capture(self.data[1],self.data[2]))
        self.assertEqual(self.paths[1].read_bytes(),source(9))
        with sqlite3.connect(str(self.db)) as reopened:
            reopened.row_factory = sqlite3.Row
            self.assertEqual(self.snap(reopened.execute('SELECT * FROM sims').fetchone()),capture(self.data[1],self.data[2]))
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM probe').fetchone()[0],1)
        before = tuple(row)
        self.assertEqual(self.run_source(),(1,1,0))  # peer3 now skip; first pair is never refreshed
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=?',(row['id'],)).fetchone()),before)

    def test_stored_orientation_preserves_a_and_b(self):
        self.assertEqual(self.run_source(2),(1,0,1))
        row = self.conn.execute('SELECT * FROM sims').fetchone()
        self.assertEqual((row['a_id'],row['b_id']),(2,1))
        self.assertEqual(self.snap(row),capture(self.data[2],self.data[1]))

    def test_skip_never_invents_two_captures(self):
        self.paths[1].write_bytes(source(9))
        self.assertEqual(self.run_source(),(1,1,0))
        row = self.conn.execute('SELECT * FROM sims').fetchone()
        self.assertEqual((row['verdict'],row['compared']),('skip',0))
        self.assertIsNone(self.snap(row))

    def test_legacy_additive_migration_is_idempotent_and_not_backfilled(self):
        old = sqlite3.connect(':memory:'); self.addCleanup(old.close); old.row_factory=sqlite3.Row
        old.executescript(sc.SIMS_SQL.replace("    source_capture TEXT NOT NULL DEFAULT '',\n",''))
        old.execute("INSERT INTO sims (a_id,b_id,map,track,leg,verdict,reason,match,compared,at) VALUES (7,8,'synthetic',0,0,'compared','historical',0.5,80,1)")
        old.commit()
        before = dict(old.execute('SELECT * FROM sims').fetchone())
        sc.ensure_schema(old); sc.ensure_schema(old)
        after = dict(old.execute('SELECT * FROM sims').fetchone())
        self.assertEqual({k:after[k] for k in before},before)
        self.assertEqual(after.get('source_capture'), '')

    def test_atomic_insert_fault_does_not_keep_measurement_or_capture(self):
        self.conn.execute("CREATE TRIGGER stop BEFORE INSERT ON sims WHEN new.b_id=3 BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError): self.run_source(max_pairs=2)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0],0)

    def test_invalid_reader_capture_stays_unbound_without_losing_measurement(self):
        def compare(a,b,**kw):
            verdict,d=rs.compare_paths(a,b,**kw)
            d['sources']={'version':99,'a':{'path':'private'},'b':{}}
            return verdict,d
        self.assertEqual(self.run_source(reader=SimpleNamespace(compare_paths=compare)),(1,0,1))
        row=self.conn.execute('SELECT * FROM sims').fetchone()
        self.assertEqual((row['verdict'],row['compared']),('compared',80))
        self.assertIsNone(self.snap(row))

    def test_old_bounded_only_reader_is_unavailable(self):
        tools=self.root/'tools';(tools/'census').mkdir(parents=True)
        (tools/'census/recsim.py').write_text('BOUNDED_INPUT_VERSION=1\ndef compare_paths(a,b,**kw):\n    return "compared", {}\n')
        mod,why=sc._recsim(str(tools))
        self.assertIsNone(mod); self.assertIn('capture',why)

    def test_snapshot_validator_is_narrow_bounded_and_versioned(self):
        project=getattr(sc,'source_snapshot',lambda raw:None)
        good=capture(self.data[1],self.data[2])
        self.assertEqual(project(json.dumps(good)),good)
        bad=[]
        for mutate in (lambda x:x.update(version=True), lambda x:x.update(version=2),
                       lambda x:x.update(path='not allowed'), lambda x:x['a'].update(bytes=True),
                       lambda x:x['a'].update(bytes=0), lambda x:x['a'].update(bytes=17<<20),
                       lambda x:x['a'].update(sha256='F'*64),lambda x:x['a'].update(sha256='<img>')):
            value=json.loads(json.dumps(good));mutate(value);bad.append(json.dumps(value))
        bad += ['', '{', '['*500, json.dumps(good)+' '*1000,
                json.dumps(good).replace('"version": 1','"version": 99, "version": 1')]
        for raw in bad:
            with self.subTest(raw=raw[:40]):self.assertIsNone(project(raw))


if __name__=='__main__':unittest.main()
