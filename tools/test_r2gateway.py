#!/usr/bin/env python3
"""Synthetic, offline redirect falsifiers. Requires explicit owned output root."""
import argparse
import configparser
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import r2gateway as g

ROOT = None


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / self._testMethodName
        self.root.mkdir()
        self.sources = {}
        for group in g.FORMATS:
            p = self.root / group
            p.mkdir()
            self.sources[group] = str(p)
        self.credentials = self.root / "rclone.conf"
        self.credentials.write_text("[task]\nendpoint=https://" + "a" * 32 + ".r2.cloudflarestorage.com\naccess_key_id=synthetic\nsecret_access_key=synthetic-secret\n")
        self.state = self.root / "state.sqlite"
        with contextlib.closing(sqlite3.connect(self.state)) as db:
            db.execute("CREATE TABLE assets(alias TEXT PRIMARY KEY,group_name TEXT,source TEXT,sig TEXT,sha TEXT,object_key TEXT,bytes INTEGER,state TEXT,present INTEGER)")
            db.commit()
        self.config = {"state": str(self.state), "groups": self.sources, "rclone_config": str(self.credentials), "remote": "task:synthetic-public"}
        self.app = g.Gateway(self.config, reachability=lambda key: True)
        self.seed("maps", "case_Map.bsp", b"map-body")
        self.seed("zones", "case_Map.json", b'{"Zones":[]}')
        self.seed("mapshots", "case_Map.jpg", b"synthetic-jpeg")

    def seed(self, group, leaf, body):
        p = Path(self.sources[group]) / leaf
        p.write_bytes(body)
        _, prefix, suffix = g.FORMATS[group]
        sha = hashlib.sha256(body).hexdigest()
        with contextlib.closing(sqlite3.connect(self.state)) as db:
            db.execute("INSERT OR REPLACE INTO assets VALUES(?,?,?,?,?,?,?,?,?)", (prefix + leaf, group, str(p), g.signature(p.stat()), sha, "objects/" + group + "/" + sha + suffix, len(body), "verified", 1))
            db.commit()
        return p

    def mutate(self, **kwargs):
        with contextlib.closing(sqlite3.connect(self.state)) as db:
            for k, v in kwargs.items():
                db.execute("UPDATE assets SET " + k + "=? WHERE group_name='maps'", (v,))
            db.commit()

    def call(self, path="/ftesurf/maps/case_Map.bsp", method="GET", query=""):
        got = []
        body = b"".join(self.app({"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query}, lambda s, h: got.append((s, dict(h)))))
        return got[0][0], got[0][1], body

    def test_positive_all_aliases(self):
        for path in ["/ftesurf/maps/case_Map.bsp", "/maps/case_Map.bsp", "/ftesurf/maps/zones/local/case_Map.json", "/board/shot/case_Map", "/board/shot/case_Map.jpg"]:
            status, h, _ = self.call(path)
            self.assertEqual(status, "302 Found")
            self.assertEqual(h["X-R2-Route"], "r2")
            self.assertEqual(h["Cache-Control"], "no-store")
            self.assertIn("objects/", h["Location"])
            self.assertEqual(parse_qs(urlsplit(h["Location"]).query)["X-Amz-Expires"], ["300"])

    def test_current_body_replacement_falls_back(self):
        self.assertEqual(self.call()[0], "302 Found")
        (Path(self.sources["maps"]) / "case_Map.bsp").write_bytes(b"new-body")
        self.assertEqual(self.call()[0], "409 Conflict")

    def test_same_size_replacement_falls_back(self):
        p = Path(self.sources["maps"]) / "case_Map.bsp"
        p.unlink()
        p.write_bytes(b"map-body")
        self.assertEqual(self.call()[0], "409 Conflict")

    def test_queued_or_deleted_not_routable(self):
        self.mutate(state="queued")
        self.assertEqual(self.call()[0], "409 Conflict")
        self.mutate(state="verified", present=0)
        self.assertEqual(self.call()[0], "409 Conflict")

    def test_corrupt_metadata(self):
        for fields in [{"object_key": "objects/maps/not-the-hash.bsp"}, {"object_key": "https://foreign.invalid/body"}, {"sha": "bad"}, {"sha": None}, {"bytes": None}, {"bytes": 0}, {"sig": "bad"}, {"source": str(self.root / "foreign.bsp")}, {"group_name": "zones"}]:
            self.seed("maps", "case_Map.bsp", b"map-body")
            self.mutate(**fields)
            self.assertEqual(self.call()[0], "409 Conflict", str(fields))

    def test_missing_sources_and_database(self):
        (Path(self.sources["maps"]) / "case_Map.bsp").unlink()
        self.assertEqual(self.call()[0], "409 Conflict")
        self.state.unlink()
        self.assertEqual(self.call()[0], "409 Conflict")
        self.assertFalse(self.state.exists(), "read-only connection must never create DB")

    def test_corrupt_database_fallback(self):
        self.state.write_bytes(b"not SQLite")
        self.assertEqual(self.call()[0], "409 Conflict")

    def test_private_and_traversal_paths_refused(self):
        for path in ["/data/runs/x.rec", "/api/replay/x", "/maps/", "/maps/../case_Map.bsp", "/maps/%2e%2e.bsp", "/maps/case_Map.bsp/extra", "/maps/case_Map.bsp\n", "/maps/a.demo", "/maps/case_Map.bsp?x=y"]:
            self.assertEqual(self.call(path)[0], "404 Not Found", path)
        self.assertEqual(self.call(method="POST")[0], "405 Method Not Allowed")

    def test_query_not_forwarded_and_head_signed_as_head(self):
        fixed = g.datetime.datetime(2026, 10, 15, tzinfo=g.datetime.timezone.utc)
        with mock.patch.object(g.datetime, "datetime", wraps=g.datetime.datetime) as clock:
            clock.now.return_value = fixed
            _, get, _ = self.call(query="X-Amz-Signature=attacker")
            _, head, _ = self.call(method="HEAD")
        self.assertNotEqual(get["Location"], head["Location"])
        self.assertNotIn("attacker", get["Location"])
        self.assertEqual(len(parse_qs(urlsplit(get["Location"]).query)["X-Amz-Signature"][0]), 64)

    @unittest.skipIf(sys.platform == "win32", "POSIX link creation control")
    def test_linked_source_and_state_refused(self):
        p = Path(self.sources["maps"]) / "case_Map.bsp"
        target = self.root / "body"
        p.rename(target)
        p.symlink_to(target)
        self.assertEqual(self.call()[0], "409 Conflict")
        target = self.root / "db-target"
        self.state.rename(target)
        self.state.symlink_to(target)
        self.assertEqual(self.call()[0], "409 Conflict")

    def test_r2_outage_and_recovery_act(self):
        remote = mock.Mock(return_value=False)
        self.app.reachability = remote
        self.assertEqual(self.call()[0], "409 Conflict")
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(self.call()[0], "409 Conflict")
        self.assertEqual(remote.call_count, 1, "failure must not hammer R2")
        remote.return_value = True
        self.app.probe_until = 0
        self.assertEqual(self.call()[0], "302 Found")
        self.assertEqual(remote.call_count, 2)
        self.assertEqual(self.call()[0], "302 Found")
        self.assertEqual(remote.call_count, 2, "success is cached")

    def test_r2_head_transport_failure_falls_back(self):
        self.app.reachability = self.app.head_probe
        with mock.patch.object(g.urllib.request, "urlopen", side_effect=OSError("synthetic outage")) as transport:
            self.assertEqual(self.call()[0], "409 Conflict")
            self.assertEqual(transport.call_count, 1)

    def test_inflight_head_uses_disk(self):
        self.app.probe_lock.acquire()
        try:
            self.assertEqual(self.call()[0], "409 Conflict")
        finally:
            self.app.probe_lock.release()

    def test_inflight_head_after_success_keeps_r2(self):
        self.assertEqual(self.call()[0], "302 Found")
        self.app.probe_until = 0
        self.app.probe_lock.acquire()
        try:
            self.assertEqual(self.call()[0], "302 Found", "a re-probe in flight must not send the rest to disk")
        finally:
            self.app.probe_lock.release()

    def gzseed(self, state="verified", key=None):
        gz = self.root / "gzip.sqlite"
        sha = hashlib.sha256(b"map-body").hexdigest()
        with contextlib.closing(sqlite3.connect(gz)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS gz(alias TEXT PRIMARY KEY,sha TEXT,bytes INTEGER,state TEXT,"
                       "gz_key TEXT,gz_sha TEXT,gz_bytes INTEGER,verified_at TEXT,error TEXT)")
            db.execute("INSERT OR REPLACE INTO gz VALUES(?,?,?,?,?,?,?,?,?)",
                       ("ftesurf/maps/case_Map.bsp", sha, 8, state, key or "objects/maps/" + sha + ".bsp.gz",
                        "0" * 64, 5, "", ""))
            db.commit()
        self.app = g.Gateway(dict(self.config, gzip_state=str(gz)), reachability=lambda key: True)
        self.ua = "FTE QW"
        return sha

    def gzcall(self, accept, path="/ftesurf/maps/case_Map.bsp", rng=None):
        got = []
        env = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "QUERY_STRING": "", "HTTP_ACCEPT_ENCODING": accept,
               "HTTP_USER_AGENT": self.ua}
        if rng:
            env["HTTP_RANGE"] = rng
        b"".join(self.app(env, lambda s, h: got.append((s, dict(h)))))
        return got[0][0], got[0][1]

    def test_gzip_companion_only_when_accepted(self):
        sha = self.gzseed()
        status, h = self.gzcall("gzip")
        self.assertEqual(status, "302 Found")
        self.assertIn("objects/maps/" + sha + ".bsp.gz", h["Location"])
        self.assertEqual(h.get("X-R2-Encoding"), "gzip")
        for accept in ("", "identity", "br", "gzip;q=0", "gzip;q=0.0", "gzip; q=0.000", "deflate, br",
                       "x-gzip", "*"):
            status, h = self.gzcall(accept)
            self.assertEqual(status, "302 Found")
            self.assertIn("objects/maps/" + sha + ".bsp?", h["Location"], accept)
            self.assertNotIn("X-R2-Encoding", h)
        self.assertIn(".bsp.gz", self.gzcall("gzip, deflate, br")[1]["Location"])
        self.assertIn(".bsp.gz", self.gzcall("deflate, gzip;q=0.5")[1]["Location"])

    def test_gzip_only_for_the_game_client(self):
        self.gzseed()
        self.assertIn(".bsp.gz", self.gzcall("gzip")[1]["Location"])
        for ua in ("Mozilla/5.0 (Windows NT 10.0) Chrome/130", "curl/8.4", ""):
            self.ua = ua
            self.assertNotIn(".bsp.gz", self.gzcall("gzip, deflate, br")[1]["Location"], ua)

    def test_gzip_refused_for_range_unverified_or_other_groups(self):
        sha = self.gzseed()
        self.assertNotIn(".bsp.gz", self.gzcall("gzip", rng="bytes=4-")[1]["Location"])
        self.assertNotIn(".gz", self.gzcall("gzip", path="/ftesurf/maps/zones/local/case_Map.json")[1]["Location"])
        for state, key in (("skip", None), ("error", None), ("verified", "objects/maps/other.bsp.gz")):
            self.gzseed(state, key)
            self.assertNotIn(".bsp.gz", self.gzcall("gzip")[1]["Location"], state)
        self.gzseed()
        (Path(self.sources["maps"]) / "case_Map.bsp").write_bytes(b"new-body")
        self.assertEqual(self.gzcall("gzip")[0], "409 Conflict", "a replaced body is not served at all")

    def test_no_database_writes(self):
        before = self.state.read_bytes()
        for _ in range(10):
            self.assertEqual(self.call()[0], "302 Found")
        self.assertEqual(before, self.state.read_bytes())
        self.assertFalse(Path(str(self.state) + "-journal").exists())

    def test_bad_configuration_refuses(self):
        for fields in [{"groups": {"recordings": str(self.root)}}, {"remote": "task:wrong/prefix"}]:
            with self.assertRaises(ValueError):
                g.Gateway(dict(self.config, **fields))
        self.credentials.write_text(self.credentials.read_text().replace("https://", "http://"))
        with self.assertRaises(ValueError):
            g.Gateway(self.config)


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    ROOT = a.out.absolute()
    if not any((p / "OWNER.md").is_file() for p in ROOT.parents):
        p.error("--out requires OWNER.md ancestor")
    ROOT.mkdir()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GatewayTests))
    (ROOT / "result.json").write_text(json.dumps({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}) + "\n")
    return not result.wasSuccessful()


if __name__ == "__main__":
    raise SystemExit(main())
