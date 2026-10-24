#!/usr/bin/env python3
"""Offline r2gzip falsifiers with a fake transport. Requires an owned --out root."""
import argparse
import contextlib
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import unittest

import r2gzip as z
import r2mirror as m

ROOT = None


class Fake:
    def __init__(self):
        self.objects = {}
        self.puts = 0

    def put_gzip(self, source, key, sha):
        self.puts += 1
        self.objects[key] = Path(source).read_bytes()

    def digest_both(self, key):
        b = self.objects[key]
        plain = gzip.decompress(b)
        return ((hashlib.sha256(b).hexdigest(), len(b)), (hashlib.sha256(plain).hexdigest(), len(plain)))


class GzipTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / self._testMethodName
        self.root.mkdir()
        self.maps = self.root / "maps"
        self.maps.mkdir()
        self.work = self.root / "work"
        self.work.mkdir()
        self.state = self.root / "state.sqlite"
        with contextlib.closing(m.connect(self.state)) as db:
            pass
        self.db = z.connect(self.work / "gzip.sqlite")

    def tearDown(self):
        self.db.close()

    def seed(self, leaf, body, state="verified"):
        p = self.maps / leaf
        p.write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        with contextlib.closing(sqlite3.connect(self.state)) as db:
            db.execute("INSERT OR REPLACE INTO assets (alias,group_name,source,sig,bytes,present,state,sha,object_key) "
                       "VALUES (?,?,?,?,?,1,?,?,?)", ("ftesurf/maps/" + leaf, "maps", str(p), m.signature(p.stat()),
                                                      len(body), state, sha, "objects/maps/" + sha + ".bsp"))
            db.commit()
        return p, sha

    def test_compressible_map_gets_a_verified_companion(self):
        _, sha = self.seed("surf_a.bsp", b"VBSP" + b"\0" * 20000 + b"lump" * 3000)
        t = Fake()
        attempted, failed = z.run(self.db, self.state, self.work, t, 0.10)
        self.assertEqual((attempted, failed), (1, 0))
        row = self.db.execute("SELECT * FROM gz").fetchone()
        self.assertEqual(row["state"], "verified")
        self.assertEqual(row["gz_key"], "objects/maps/" + sha + ".bsp.gz")
        self.assertEqual(hashlib.sha256(gzip.decompress(t.objects[row["gz_key"]])).hexdigest(), sha)
        self.assertLess(row["gz_bytes"], row["bytes"] * 0.9)
        # deterministic bytes: same body, same companion
        p2, _ = z.compress(self.maps / "surf_a.bsp", self.work), None
        self.assertEqual(p2[1], row["gz_sha"])
        p2[0].unlink()

    def test_incompressible_map_is_skipped_not_uploaded(self):
        self.seed("surf_lzma.bsp", os.urandom(50000))
        t = Fake()
        z.run(self.db, self.state, self.work, t, 0.10)
        self.assertEqual(t.puts, 0)
        self.assertEqual(self.db.execute("SELECT state FROM gz").fetchone()["state"], "skip")

    def test_second_pass_is_idempotent(self):
        self.seed("surf_a.bsp", b"\0" * 30000)
        self.seed("surf_b.bsp", os.urandom(30000))
        t = Fake()
        z.run(self.db, self.state, self.work, t, 0.10)
        puts = t.puts
        self.assertEqual(z.run(self.db, self.state, self.work, t, 0.10), (0, 0))
        self.assertEqual(t.puts, puts)

    def test_changed_source_or_unverified_row_is_not_compressed(self):
        p, _ = self.seed("surf_a.bsp", b"\0" * 30000)
        p.write_bytes(b"\1" * 30000)          # changed after r2mirror verified it
        self.seed("surf_q.bsp", b"\0" * 30000, state="pending")
        t = Fake()
        attempted, failed = z.run(self.db, self.state, self.work, t, 0.10)
        self.assertEqual((attempted, failed), (1, 1))
        self.assertEqual(t.puts, 0)
        self.assertEqual(self.db.execute("SELECT state FROM gz WHERE alias LIKE '%surf_a.bsp'").fetchone()["state"], "error")

    def test_remote_mismatch_is_an_error(self):
        self.seed("surf_a.bsp", b"\0" * 30000)

        class Corrupt(Fake):
            def put_gzip(self, source, key, sha):
                super().put_gzip(source, key, sha)
                self.objects[key] = gzip.compress(b"\2" * 30000)
        t = Corrupt()
        self.assertEqual(z.run(self.db, self.state, self.work, t, 0.10), (1, 1))
        self.assertEqual(self.db.execute("SELECT state FROM gz").fetchone()["state"], "error")

    def test_state_is_not_wal(self):
        self.assertEqual(self.db.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_main_state_is_only_read(self):
        self.seed("surf_a.bsp", b"\0" * 30000)
        before = self.state.read_bytes()
        z.run(self.db, self.state, self.work, Fake(), 0.10)
        self.assertEqual(before, self.state.read_bytes())


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    ROOT = a.out.absolute()
    if not any((q / "OWNER.md").is_file() for q in ROOT.parents):
        p.error("--out requires OWNER.md ancestor")
    ROOT.mkdir()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GzipTests))
    (ROOT / "result.json").write_text(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
                                                  "errors": len(result.errors)}) + "\n")
    return not result.wasSuccessful()


if __name__ == "__main__":
    raise SystemExit(main())
