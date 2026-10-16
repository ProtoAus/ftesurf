#!/usr/bin/env python3
"""Bounded request-worker/priority controls; synthetic DB and no CDN traffic.

Set MOMGRAB_UNDER_TEST to an inspected old momgrab.py to falsify the mid-batch
priority arm. Use an owned TEMP/TMPDIR when invoking this existing test family.
"""
import configparser
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_momrequest as F

G = F.G
if os.environ.get("MOMGRAB_UNDER_TEST"):
    spec = importlib.util.spec_from_file_location("momgrab_control", os.environ["MOMGRAB_UNDER_TEST"])
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)


class Priority(unittest.TestCase):
    def setUp(self):
        self.fixture = F.Requests()
        self.fixture.setUp()
        self.tmp = tempfile.TemporaryDirectory(prefix="priority-", dir=F.ROOT)
        self.home = Path(self.tmp.name)
        self.a = SimpleNamespace(boards=str(self.home / "boards"), state=str(self.home / "state"),
                                 demos=str(self.home / "demos"), out=str(self.home / "out"),
                                 maps=str(self.home / "maps"), top=10, max=3, delay=0, go=True,
                                 requests_only=True, watch_requests=False)
        for name in ("boards", "state", "demos", "out", "maps"):
            (self.home / name).mkdir()
        self.disk = patch.object(G.shutil, "disk_usage", return_value=SimpleNamespace(free=100e9))
        self.disk.start()

    def tearDown(self):
        self.disk.stop()
        self.fixture.tearDown()
        self.tmp.cleanup()

    def queue(self, h="c" * 40, player="76561198000000003"):
        token = self.fixture.board(h, player)
        result = self.fixture.client.post(self.fixture.url(token))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["state"], "queued")
        return token

    def state(self, value):
        G._save(str(self.home / "state/state.json"), value)

    def background(self):
        return [(0, n, "fixture", h * 40, "76561198000000001", 3000,
                 {"map": "surf_p544", "track": 0, "leg": 0, "player": "76561198000000001"})
                for n, h in enumerate(("a", "b"))]

    def run_background(self, download):
        self.a.requests_only = False
        with patch.object(G, "refresh_queue", return_value=({"boards": {}}, 0, 0)), \
             patch.object(G, "held_runs", return_value={}), \
             patch.object(G, "wanted_maps", return_value=set()), \
             patch.object(G, "pick", return_value=self.background()), \
             patch.object(G, "download", side_effect=download):
            self.assertEqual(G.run(self.a), 0)

    def test_click_during_batch_is_next(self):
        token = self.fixture.board("c" * 40, "76561198000000003")
        order = []

        def download(h, dest):
            order.append(h[0])
            if h == "a" * 40:
                result = self.fixture.client.post(self.fixture.url(token))
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.get_json()["state"], "queued")
            return "toobig"  # settle the synthetic transfer; not codec coverage

        self.run_background(download)
        self.assertEqual(order, ["a", "c", "b"])
        self.assertEqual(self.fixture.db.execute("SELECT state FROM momrequests").fetchone()[0], "failed")

    def test_invalidated_mid_batch_request_is_not_retained(self):
        order = []

        def download(h, dest):
            order.append(h[0])
            if h == "a" * 40:
                self.queue("c" * 40, "76561198000000003")
                self.queue("d" * 40, "76561198000000004")
            if h == "c" * 40:
                with self.fixture.db:
                    self.fixture.db.execute("UPDATE runs SET momdemo=?,millis=2000 WHERE momdemo=?",
                                            ("e" * 40, "d" * 40))
            return "toobig"

        self.run_background(download)
        self.assertEqual(order, ["a", "c", "b"])
        self.assertEqual(self.fixture.db.execute("SELECT state,why FROM momrequests WHERE hash=?",
                                                ("d" * 40,)).fetchone()[:], ("failed", "record changed"))

    def test_click_during_pacing_is_next(self):
        order = []
        self.a.delay = 2
        now = time.time()
        self.state({"last_request": now - 2})

        def pause(seconds):
            if not self.fixture.db.execute("SELECT 1 FROM momrequests").fetchone():
                self.queue()

        def download(h, dest):
            order.append(h[0])
            return "toobig"

        with patch.object(G.time, "time", return_value=now), patch.object(G.time, "sleep", side_effect=pause):
            self.run_background(download)
        self.assertEqual(order, ["a", "c", "b"])

    def test_persistent_inventory_discovers_new_bsp_and_rejects_wrong_build(self):
        maps = self.home / "maps"
        cache = str(self.home / "state/bsp.json")
        G._bsp.clear()
        G._bsp_names.clear()
        self.addCleanup(G._bsp.clear)
        self.addCleanup(G._bsp_names.clear)
        (maps / "a.bsp").write_bytes(b"installed A")
        self.assertIsNotNone(G.bsp_sha1("a", str(maps), cache))
        (maps / "B.bsp").write_bytes(b"installed B")
        demo = self.home / ("c" * 40 + ".mtv")
        demo.write_bytes(b"synthetic header double")
        head = dict(steam_id=76561198000000001, map="b", track_type=0, track_number=1,
                    tick_interval=.01, run_time=3, map_sha1="0" * 40)
        board = dict(map="b", track=0, leg=0, player=str(head["steam_id"]))
        with patch.object(G.momreplay, "read_header", return_value=head), \
             patch.object(G.momreimport, "convert") as convert:
            self.assertEqual(G.convert_demo(str(demo), board, 3000, str(maps), cache, self.a.out),
                             ("otherbuild", None))
        convert.assert_not_called()

    def test_service_has_no_forced_transfer_stop_deadline(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read(os.environ.get("MOMREQUESTS_UNIT_UNDER_TEST", str(F.HERE / "momrequests.service")))
        self.assertEqual(config["Service"]["TimeoutStopSec"], "infinity")

    @unittest.skipIf(os.name == "nt", "POSIX SIGTERM delivery; exercised on the NanoPi")
    def test_sigterm_finishes_a_slow_active_transfer(self):
        body = b"synthetic transfer, not a demo codec fixture\n" * 4000
        h = hashlib.sha1(body).hexdigest()
        self.queue(h)
        self.state({"last_request": time.time() - 3})
        started, release = threading.Event(), threading.Event()

        class Slow(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[:65536])
                self.wfile.flush()
                started.set()
                release.wait(10)
                self.wfile.write(body[65536:])

        server = HTTPServer(("127.0.0.1", 0), Slow)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(F.HERE)
        env["P740_CDN"] = "http://127.0.0.1:%d/" % server.server_port
        code = "import os,momgrab as G; G.CDN=os.environ['P740_CDN']; raise SystemExit(G.main())"
        args = [sys.executable, "-c", code, "--requests-only", "--watch-requests", "--go",
                "--state", self.a.state, "--demos", self.a.demos, "--out", self.a.out,
                "--maps", self.a.maps]
        proc = None
        try:
            with (self.home / "sigterm.log").open("wb") as log:
                proc = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT)
                self.assertTrue(started.wait(5), "the worker must actually start its transfer")
                proc.send_signal(signal.SIGTERM)
                with self.assertRaises(subprocess.TimeoutExpired):
                    proc.wait(timeout=.15)
                release.set()
                self.assertEqual(proc.wait(timeout=5), 0)
            dest = Path(self.a.demos) / h[:2] / (h + ".mtv")
            self.assertEqual(dest.read_bytes(), body)
            self.assertFalse(Path(str(dest) + ".part").exists())
            self.assertEqual(self.fixture.db.execute("SELECT state,why FROM momrequests WHERE hash=?",
                                                    (h,)).fetchone()[:], ("failed", "unreadable"))
        finally:
            release.set()
            if proc is not None and proc.poll() is None:
                proc.kill()  # only this test's synthetic child, never a serving worker
                proc.wait()
            server.shutdown()
            server.server_close()
            thread.join()

    def test_requested_only_never_scans_backlog(self):
        token = self.queue()
        with patch.object(G, "refresh_queue", side_effect=AssertionError("background scan")), \
             patch.object(G, "held_runs", side_effect=AssertionError("held corpus scan")), \
             patch.object(G, "wanted_maps", side_effect=AssertionError("wanted-map scan")), \
             patch.object(G, "download", return_value="toobig") as download:
            self.assertEqual(G.run(self.a), 0)
        self.assertEqual(download.call_args[0][0], token[1])
        self.assertEqual(download.call_count, 1)
        self.assertFalse(G.requests_due(self.a))

    def test_only_spendable_queued_or_stale_work_is_due(self):
        token = self.fixture.board()
        self.assertEqual(self.fixture.client.get(self.fixture.url(token)).status_code, 404)
        self.assertEqual(self.fixture.client.post(self.fixture.url((token[0], "b" * 40))).status_code, 409)
        self.assertFalse(G.requests_due(self.a))
        self.queue()
        self.assertTrue(G.requests_due(self.a))
        now = int(time.time())
        F.M.set_state(self.fixture.db, "c" * 40, "working", "fixture transfer", now=now)
        self.assertFalse(G.requests_due(self.a, now))
        self.assertTrue(G.requests_due(self.a, now + 3601))
        self.assertFalse(G.requests_due(self.a, now + F.M.TTL + 1))

    def test_host_and_file_cooldowns_are_not_reset(self):
        token = self.queue()
        now = int(time.time())
        parked = {"park": {"until": now + 3600, "n": 2, "why": "fixture refusal"}}
        self.state(parked)
        self.assertFalse(G.requests_due(self.a, now))
        self.assertEqual(G._load(str(self.home / "state/state.json")), parked)
        deferred = {"later": {token[1]: [G.STRIKES, now, "fixture transient"]}}
        self.state(deferred)
        self.assertFalse(G.requests_due(self.a, now))
        self.assertEqual(G._load(str(self.home / "state/state.json")), deferred)

    def test_busy_global_lock_does_not_start_another_worker(self):
        self.queue()
        lock = G.take_lock(self.a.state)
        self.assertIsNotNone(lock)
        try:
            self.assertFalse(G.requests_due(self.a))
        finally:
            lock.close()
        self.assertTrue(G.requests_due(self.a))

    def test_request_handoffs_share_persisted_network_pace(self):
        self.queue("c" * 40, "76561198000000003")
        self.queue("d" * 40, "76561198000000004")
        self.a.max = 1
        self.a.delay = 2
        now = time.time()
        self.state({"last_request": now - self.a.delay})
        with patch.object(G.time, "time", return_value=now), \
             patch.object(G.time, "sleep") as sleep, \
             patch.object(G, "download", return_value="toobig") as download:
            G.run(self.a)
            G.run(self.a)
        self.assertEqual(download.call_count, 2)
        sleep.assert_called_once_with(2)
        self.assertEqual(G._load(str(self.home / "state/state.json"))["last_request"], now)

    def test_legacy_handoff_and_backwards_clock_wait_at_most_one_gap(self):
        self.a.max = 1
        self.a.delay = 2
        now = time.time()
        for n, (h, state) in enumerate((("e", {}), ("f", {"last_request": now + 60})), 5):
            self.queue(h * 40, "7656119800000000" + str(n))
            self.state(state)
            with patch.object(G.time, "time", return_value=now), \
                 patch.object(G.time, "sleep") as sleep, \
                 patch.object(G, "download", return_value="toobig") as download:
                G.run(self.a)
            download.assert_called_once()
            sleep.assert_called_once_with(2)

    def test_watch_cli_caps_work_and_preserves_minimum_cdn_gap(self):
        with patch.object(G.sys, "argv", ["momgrab.py", "--watch-requests", "--requests-only",
                                          "--go", "--max", "999", "--delay", "0"]), \
             patch.object(G, "serve_requests", return_value=0) as serve:
            self.assertEqual(G.main(), 0)
        args, stop = serve.call_args[0]
        self.assertEqual(args.max, 2)
        self.assertEqual(args.delay, G.GRAB_DELAY)
        self.assertFalse(stop.is_set())

    def test_stop_during_pacing_leaves_request_queued(self):
        self.queue()
        self.a.delay = 2
        now = time.time()
        self.state({"last_request": now})
        stop = threading.Event()
        with patch.object(G.time, "time", return_value=now), \
             patch.object(G.time, "sleep", side_effect=lambda _: stop.set()), \
             patch.object(G, "download") as download:
            G.run(self.a, stop)
        download.assert_not_called()
        self.assertEqual(self.fixture.db.execute("SELECT state FROM momrequests").fetchone()[0], "queued")

    def test_foreground_worker_checks_before_its_first_poll_wait(self):
        stop = threading.Event()
        events = []
        with patch.object(G, "requests_due", return_value=True), \
             patch.object(G, "run_once", side_effect=lambda a, s: events.append("run")) as run, \
             patch.object(stop, "wait", side_effect=lambda seconds: (events.append(seconds), stop.set())):
            self.assertEqual(G.serve_requests(self.a, stop), 0)
        self.assertEqual(events, ["run", 1.0])
        run.assert_called_once_with(self.a, stop)


if __name__ == "__main__":
    unittest.main()
