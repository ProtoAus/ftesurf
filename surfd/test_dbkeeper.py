#!/usr/bin/env python3
"""P1175: surfd keeps the WAL sidecars, so a reader that cannot create files (the zone
service under ProtectSystem=strict) can open the DB read-only. POSIX, non-root: a 0555
directory stands in for the read-only mount."""
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HOME = Path(tempfile.mkdtemp(prefix="surfd-keeper-"))
(HOME / "surfd.env").write_text("SURFD_KEY=testkey\n")
DBDIR = HOME / "db"
DBDIR.mkdir()
DB = DBDIR / "surfd.db"
os.environ.update(SURFD_HOME=str(HOME), SURFD_DB=str(DB), SURFD_ENV=str(HOME / "surfd.env"))
import surfd as S


def sidecar(tail):
    return Path(str(DB) + tail)


READER = """import sqlite3, sys
c = sqlite3.connect(sys.argv[1] + "?mode=ro", uri=True, timeout=0.25)
print(c.execute("SELECT count(*) FROM sqlite_master").fetchone()[0])
"""


def sandboxed_read():
    """mode=ro from another process (sqlite shares one shm mapping per process) while neither
    the directory nor the sidecars take writes, like the zone service's read-only mount."""
    files = [p for p in (DB, sidecar("-wal"), sidecar("-shm")) if p.exists()]
    for p in files:
        os.chmod(p, 0o400)
    os.chmod(DBDIR, 0o555)
    try:
        out = subprocess.run([sys.executable, "-I", "-c", READER, DB.as_uri()],
                             capture_output=True, text=True, timeout=30)
    finally:
        os.chmod(DBDIR, 0o755)
        for p in files:
            os.chmod(p, 0o600)
    if out.returncode:
        raise sqlite3.OperationalError(out.stderr.strip().splitlines()[-1])
    return int(out.stdout)


@unittest.skipUnless(os.name == "posix" and os.geteuid() != 0, "needs POSIX and a non-root uid")
class Keeper(unittest.TestCase):
    def setUp(self):
        self.reset()

    def tearDown(self):
        self.reset()

    def reset(self):
        if S._KEEPER["conn"] is not None:
            S._KEEPER["conn"].close()
        S._KEEPER.update(key=None, conn=None)

    def request(self):
        with S.app.app_context():
            return S.get_db().execute("SELECT count(*) FROM sqlite_master").fetchone()[0]

    def test_read_only_reader_opens_after_a_request(self):
        tables = self.request()
        self.assertTrue(sidecar("-shm").exists())
        self.assertEqual(sandboxed_read(), tables)
        self.assertFalse(S._KEEPER["conn"].in_transaction)

    def test_control_without_the_keeper_the_same_read_fails(self):
        with mock.patch.object(S, "_keep_sidecars", lambda: None):
            self.request()      # the last rw close checkpoints and unlinks the sidecars
        self.assertFalse(sidecar("-shm").exists())
        with self.assertRaises(sqlite3.OperationalError):
            sandboxed_read()

    def test_idle_keeper_does_not_hold_back_a_checkpoint(self):
        self.request()
        w = sqlite3.connect(str(DB))
        try:
            w.execute("CREATE TABLE IF NOT EXISTS p1175(x)")
            w.executemany("INSERT INTO p1175 VALUES(?)", [(b"x" * 4000,)] * 200)
            w.commit()
            # Control: a reader inside a transaction does hold it back, so the check can fail.
            r = sqlite3.connect(str(DB))
            r.execute("BEGIN")
            r.execute("SELECT count(*) FROM p1175").fetchone()
            w.execute("INSERT INTO p1175 VALUES(1)")
            w.commit()
            self.assertEqual(w.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 1)
            r.close()
            self.assertEqual(w.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0)
            self.assertEqual(sidecar("-wal").stat().st_size, 0)
        finally:
            w.execute("DROP TABLE IF EXISTS p1175")
            w.commit()
            w.close()

    def test_a_different_path_moves_the_keeper(self):
        self.request()
        first = S._KEEPER["conn"]
        other = DBDIR / "other.db"
        with mock.patch.object(S, "DB_PATH", str(other)):
            self.request()
            self.assertEqual(S._KEEPER["key"], (os.getpid(), str(other)))
        self.assertIsNot(S._KEEPER["conn"], first)
        with self.assertRaises(sqlite3.ProgrammingError):
            first.execute("SELECT 1")       # closed, not leaked


def tearDownModule():
    if S._KEEPER["conn"] is not None:
        S._KEEPER["conn"].close()
    logging.shutdown()          # surfd's log handler holds logs/surfd.log open (Windows)
    shutil.rmtree(HOME)


if __name__ == "__main__":
    unittest.main()
