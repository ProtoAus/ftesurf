#!/usr/bin/env python3
"""Offline falsifier: held PB -> bounded queue -> momgrab -> replay route.

Run: python surfd/test_momrequest.py. No credentials, live DB or CDN traffic.
The converter is an explicit test double; player/hash/size checks and the real
filing/linker/delivery path are separate controls, not claims of codec coverage.
"""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix="momrequest-"))
os.environ["SURFD_DB"] = str(ROOT / "db.sqlite")
os.environ["SURFD_RUNS"] = str(ROOT / "runs")
os.environ["SURFD_MOMENTUM"] = str(ROOT / "momentum")
sys.path.insert(0, str(HERE))
import surfd as S
import momboards as B
import momgrab as G
import momrequest as M


class Reply(io.BytesIO):
    status = 200
    headers = {}


class Requests(unittest.TestCase):
    def setUp(self):
        S.migrate()
        self.db = S.connect()
        with self.db:
            for table in ("momrequests", "runs", "replays"):
                self.db.execute("DELETE FROM " + table)
        S._rate.clear()
        self.client = S.app.test_client()

    def tearDown(self):
        self.db.close()

    def board(self, h="a" * 40, player="76561198000000001", ms=3000):
        B.flush(self.db, [("surf_p544", 0, 0, player, "Test", ms, 1000, ms, 1, h)])
        r = self.db.execute("SELECT rowid, * FROM runs WHERE player=?", (player,)).fetchone()
        return r["rowid"], h

    def url(self, token):
        return "/api/momentum/%d/%s" % token

    def test_click_poll_and_dedup(self):
        token = self.board()
        page = self.client.get("/api/board?map=surf_p544&tier=momentum").get_json()
        self.assertEqual(page["rows"][0]["get"], "%d/%s" % token)
        self.assertEqual(page["rows"][0]["rep"], 0)
        self.assertEqual(self.client.get(self.url(token)).status_code, 404)
        self.assertEqual(self.client.post(self.url(token)).get_json()["state"], "queued")
        self.assertEqual(self.client.post(self.url(token)).get_json()["state"], "queued")
        self.assertEqual(self.db.execute("SELECT count(*) FROM momrequests").fetchone()[0], 1)
        self.assertEqual(self.client.get(self.url(token)).get_json()["state"], "queued")
        M.set_state(self.db, token[1], "working", "downloading", 100)
        self.assertEqual(self.client.get(self.url(token)).get_json()["state"], "working")
        M.set_state(self.db, token[1], "failed", "gone", 100)
        self.assertEqual(self.client.get(self.url(token)).get_json()["why"], "gone")

    def test_stale_and_unspendable(self):
        token = self.board()
        self.assertEqual(self.client.post(self.url((token[0], "b" * 40))).status_code, 409)
        self.assertEqual(self.client.post(self.url((token[0], "bad"))).status_code, 400)
        B.flush(self.db, [("surf_p544", 0, 0, "76561198000000001", "Test", 2000, 1000, 2000, 2, "b" * 40)])
        self.assertEqual(self.client.post(self.url(token)).status_code, 409)
        self.assertEqual(self.db.execute("SELECT count(*) FROM momrequests").fetchone()[0], 0)
        with self.db:
            self.db.execute("UPDATE runs SET tier='ranked'")
        self.assertEqual(self.client.post(self.url((token[0], "b" * 40))).status_code, 409)

    def test_equal_time_backfill_not_slower_hash(self):
        token = self.board("")
        self.board("a" * 40)
        self.assertEqual(self.db.execute("SELECT momdemo FROM runs").fetchone()[0], "a" * 40)
        self.board("b" * 40, ms=4000)
        self.assertEqual(self.db.execute("SELECT momdemo,millis FROM runs").fetchone()[:], ("a" * 40, 3000))

    def test_capacity_recovery_expiry(self):
        now = 100000
        for i in range(M.CAP):
            rid, h = self.board("%040x" % (i + 1), str(i + 1))
            self.assertEqual(M.reply(self.db, rid, h, now, True)[0], 200)
        rid, h = self.board("f" * 40, "999")
        self.assertEqual(M.reply(self.db, rid, h, now, True)[0], 429)
        M.set_state(self.db, "%040x" % 1, "working", "", now - 3601)
        self.assertEqual(len(M.pending(self.db, now)), M.CAP)
        self.assertEqual(self.db.execute("SELECT state FROM momrequests WHERE hash=?", ("%040x" % 1,)).fetchone()[0], "queued")
        self.assertEqual(len(M.pending(self.db, now + M.TTL + 1)), 0)
        self.assertEqual(M.reply(self.db, rid, h, now + M.TTL + 1, True)[0], 200)

    def test_oversized_handle_and_nontext_metadata(self):
        token = self.board()
        self.assertEqual(self.client.post(self.url((10**30, token[1]))).status_code, 400)
        with self.db:
            self.db.execute("UPDATE runs SET momdemo=?", (b"not text",))
        page = self.client.get("/api/board?map=surf_p544&tier=momentum").get_json()
        self.assertNotIn("get", page["rows"][0])

    def test_endpoint_post_rate_limit(self):
        token = self.board()
        for i in range(10):
            self.assertEqual(self.client.post(self.url(token)).status_code, 200)
        self.assertEqual(self.client.post(self.url(token)).status_code, 429)
        self.assertEqual(self.client.get(self.url(token)).status_code, 200)

    def test_hash_and_size_download_controls(self):
        data = b"MMTV" + b"x" * 64
        h = hashlib.sha1(data).hexdigest()
        dest = ROOT / "download.mtv"
        with patch.object(G.urllib.request, "urlopen", return_value=Reply(data)):
            self.assertEqual(G.download(h, str(dest)), "ok")
        self.assertEqual(dest.read_bytes(), data)
        with patch.object(G.urllib.request, "urlopen", return_value=Reply(data)):
            self.assertEqual(G.download("0" * 40, str(dest)), "badhash")
        with patch.object(G, "MAX_BYTES", 8), patch.object(G.urllib.request, "urlopen", return_value=Reply(data)):
            self.assertEqual(G.download(h, str(dest)), "toobig")
        self.assertFalse(Path(str(dest) + ".part").exists())

    def test_requested_worker_files_links_and_serves(self):
        data = b"MMTV" + b"explicit not automatic top ten"
        h = hashlib.sha1(data).hexdigest()
        token = self.board(h)
        self.client.post(self.url(token))
        self.assertEqual(G.request_picks({}, {}, int(__import__('time').time()), True)[0][3], h)
        dest = ROOT / "momentum" / "surf_p544" / "main" / "0000300_abcdef01_run.rec"
        dest.parent.mkdir(parents=True, exist_ok=True)
        rec = ("FTESURF-REC 4\nmap surf_p544\ntrack 0\nleg 0\nstartseg 0\n"
               "tickrate 0.01\nmovetickrate 0.01\nclock sampled\nowner Test\n"
               "foreign momentum %s 0 0 1 76561198000000001\nflags 0\nbegin\n"
               "0.0000 0 0 100 300 400 0 0 0 0 0 0 0 0 0 0 0\n"
               "0.0100 3 4 100 300 400 0 0 0 0 0 0 0 0 0 0 0\n"
               "end 300 2 0 0\n") % h
        dest.write_text(rec)
        work = ROOT / "worker"
        args = ["momgrab.py", "--boards", str(work / "boards"), "--demos", str(work / "demos"),
                "--out", str(ROOT / "momentum"), "--state", str(work / "state"), "--max", "1", "--go"]
        work.mkdir(exist_ok=True)
        with patch.object(sys, "argv", args), patch.object(G, "convert_demo", return_value=("ok", str(dest))) as convert, patch.object(G.urllib.request, "urlopen", return_value=Reply(data)):
            G.main()
        self.assertEqual(convert.call_count, 1)
        result = self.client.get(self.url(token))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["state"], "ready")
        rep = result.get_json()["rep"]
        self.assertGreater(rep, 0)
        response = self.client.get("/api/replay/%d" % rep)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"foreign momentum " + h.encode(), response.data)
        self.assertNotIn(b"pmpin", response.data)
        response.close()
        # Ready polls follow the live link, not a stale queue state.
        with self.db:
            self.db.execute("UPDATE runs SET replay_id=0")
        self.assertEqual(self.client.get(self.url(token)).status_code, 404)

    def test_conversion_refuses_different_player(self):
        source = ROOT / "badplayer.mtv"
        source.write_bytes(b"MMTV")
        with patch.object(G.momreplay, "read_header", return_value={"steam_id": 999}):
            status, path = G.convert_demo(str(source), {"player": "123"}, 3000, str(ROOT), str(ROOT / "bsp.json"), str(ROOT))
        self.assertEqual((status, path), ("otherplayer", None))


if __name__ == "__main__":
    unittest.main()
