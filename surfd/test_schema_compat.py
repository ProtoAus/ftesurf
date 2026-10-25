#!/usr/bin/env python3
"""Fresh-process schema compatibility controls; all DBs are synthetic/private.

Run with --work-root beneath an owned test root. --source selects an unchanged
control application without checking out or editing a running install.
"""
import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

AP = argparse.ArgumentParser(description=__doc__)
AP.add_argument('--work-root', type=Path, required=True)
AP.add_argument('--source', type=Path, default=Path(__file__).with_name('surfd.py'))
ARGS = AP.parse_args()
ROOT = ARGS.work_root.resolve()
SOURCE = ARGS.source.resolve()
HELPERS = Path(__file__).resolve().parent
TOOLS = HELPERS.parent / 'tools'
assert any((p / 'OWNER.md').is_file() for p in [ROOT, *ROOT.parents]), 'owned test root required'
ROOT.mkdir(parents=True, exist_ok=True)

CHILD = r'''
import hashlib, importlib.util, os, pathlib, subprocess, sys
source=pathlib.Path(sys.argv[1]);mode=sys.argv[2]
spec=importlib.util.spec_from_file_location('surfd',source)
m=importlib.util.module_from_spec(spec);sys.modules['surfd']=m
raced=[]
def durable():
    result={}
    for suffix in ['', '-wal']:
        p=pathlib.Path(m.DB_PATH+suffix)
        result[suffix]=(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mode&0o777) if p.is_file() else None
    return result
try:
    if mode in ['connect','connect-race']:
        text=source.read_text();anchor='\nmigrate()\n';assert text.count(anchor)==1
        exec(compile(text[:text.index(anchor)],str(source),'exec'),m.__dict__)
        if mode=='connect-race':
            original=m.sqlite3.connect
            def opening(path,*a,**kw):
                if str(path)==m.DB_PATH and not kw.get('uri') and not raced:
                    creator="import sqlite3,os,sys;d=sqlite3.connect(sys.argv[1]);d.execute('PRAGMA wal_autocheckpoint=0');d.execute('INSERT INTO operator_fixture VALUES (?)',(b'between checks',));d.execute('PRAGMA user_version=%d'%int(sys.argv[2]));d.commit();os._exit(0)"
                    r=subprocess.run([sys.executable,'-c',creator,m.DB_PATH,str(m.SCHEMA_VERSION+1)],capture_output=True,timeout=30)
                    assert r.returncode==0,r.stderr
                    raced.append(durable());assert raced[0]['-wal'] is not None
                return original(path,*a,**kw)
            m.sqlite3.connect=opening
        db=m.connect();db.close()
    else:
        spec.loader.exec_module(m)
except RuntimeError as e:
    assert mode!='normal' and 'newer than this surfd' in str(e),str(e)
    if mode=='connect-race':
        assert len(raced)==1 and durable()==raced[0],'RW recheck checkpointed ahead WAL'
    print('ACTED newer-schema refusal',flush=True)
else:
    assert mode=='normal','ahead database accepted'
    print('ACTED supported startup',flush=True)
'''


class SchemaCompatibility(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='schema-', dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.db = self.home / 'schema.db'
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith('SURFD_') and k not in ['PYTHONHOME', 'PYTHONPATH']}
        (self.home / 'fixture.env').write_text('SURFD_KEY=synthetic-schema-test\n')
        (self.home / 'csprogs.dat').write_bytes(b'synthetic schema test code\n')
        self.env.update(SURFD_HOME=str(self.home), SURFD_DB=str(self.db),
            SURFD_ENV=str(self.home / 'fixture.env'), SURFD_TOOLS=str(TOOLS),
            SURFD_GAME_CODE=str(self.home / 'csprogs.dat'), PYTHONDONTWRITEBYTECODE='1',
            PYTHONNOUSERSITE='1', PYTHONPATH=os.pathsep.join([str(HELPERS), str(TOOLS)]))

    def child(self, mode):
        r = subprocess.run([sys.executable, '-c', CHILD, str(SOURCE), mode],
                           cwd=self.home, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('ACTED ', r.stdout)

    def seed(self, ahead):
        self.child('normal')
        with closing(sqlite3.connect(self.db)) as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            db.execute('CREATE TABLE operator_fixture (value BLOB NOT NULL)')
            db.execute('INSERT INTO operator_fixture VALUES (?)', (b'preserve this value',))
            if ahead:
                db.execute('PRAGMA user_version=%d' % (version + 1))
            db.commit()
            self.assertEqual(db.execute('PRAGMA journal_mode=DELETE').fetchone()[0], 'delete')
        self.db.chmod(0o640)
        return version

    def fingerprint(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest(), self.db.stat().st_mode & 0o777

    def test_ahead_full_startup_refuses_before_writes(self):
        version = self.seed(True)
        before = self.fingerprint()
        self.child('ahead')
        self.assertEqual(self.fingerprint(), before)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version + 1)
            self.assertEqual(db.execute('SELECT value FROM operator_fixture').fetchone()[0], b'preserve this value')

    def test_ahead_direct_connection_refuses_before_writes(self):
        self.seed(True)
        before = self.fingerprint()
        self.child('connect')
        self.assertEqual(self.fingerprint(), before)

    def durable_fingerprint(self):
        result = {}
        for suffix in ['', '-wal']:
            path = Path(str(self.db) + suffix)
            result[suffix] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mode & 0o777) if path.is_file() else None
        return result

    def test_ahead_committed_wal_is_not_checkpointed(self):
        version = self.seed(False)
        creator = "import sqlite3,os,sys;d=sqlite3.connect(sys.argv[1]);d.execute('PRAGMA journal_mode=WAL');d.execute('PRAGMA wal_autocheckpoint=0');d.execute('INSERT INTO operator_fixture VALUES (?)',(b'committed WAL',));d.execute('PRAGMA user_version=%d'%int(sys.argv[2]));d.commit();os._exit(0)"
        r = subprocess.run([sys.executable, '-c', creator, str(self.db), str(version + 1)],
                           env=self.env, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(int.from_bytes(self.db.read_bytes()[60:64], 'big'), version)
        before = self.durable_fingerprint()
        self.assertIsNotNone(before['-wal'])
        self.child('connect')
        self.assertEqual(self.durable_fingerprint(), before)
        # SHM read marks are coordination metadata, not durable pages/logs.
        with closing(sqlite3.connect(self.db.as_uri() + '?mode=ro', uri=True)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version + 1)
            self.assertEqual(db.execute('SELECT count(*) FROM operator_fixture WHERE value=?',
                                       (b'committed WAL',)).fetchone()[0], 1)

    def test_ahead_cold_wal_only_creates_empty_coordination_files(self):
        version = self.seed(False)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA user_version=%d' % (version + 1))
            db.commit()
        wal = Path(str(self.db) + '-wal')
        self.assertFalse(wal.exists())
        before = self.fingerprint()
        self.child('connect')
        self.assertEqual(self.fingerprint(), before)
        # SQLite mode=ro may create an empty WAL and its SHM coordination cache.
        if wal.exists():
            self.assertEqual(wal.stat().st_size, 0)

    def test_upgrade_between_checks_keeps_committed_wal(self):
        self.seed(False)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
        self.child('connect-race')
        with closing(sqlite3.connect(self.db.as_uri() + '?mode=ro', uri=True)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM operator_fixture WHERE value=?',
                                       (b'between checks',)).fetchone()[0], 1)

    def test_current_version_still_starts(self):
        version = self.seed(False)
        self.child('normal')
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version)
            self.assertEqual(db.execute('SELECT value FROM operator_fixture').fetchone()[0], b'preserve this value')

    def test_fresh_database_still_initializes(self):
        self.child('normal')
        with closing(sqlite3.connect(self.db)) as db:
            self.assertGreater(db.execute('PRAGMA user_version').fetchone()[0], 0)
            self.assertIn('last_used', [r[1] for r in db.execute('PRAGMA table_info(lobbies)')])


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
