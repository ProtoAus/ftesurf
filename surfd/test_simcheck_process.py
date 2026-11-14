"""Similarity process containment, not real-assist calibration.

python surfd/test_simcheck_process.py
Linux acting arms use Debian's existing /usr/bin/prlimit, isolated fixture DATA,
and the real sweep.py entrypoint. Unsupported systems still test abstention.
"""
import contextlib
import importlib
import io
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
LINUX = sys.platform == "linux" and os.access("/usr/bin/prlimit", os.X_OK)


class ProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("SURFD_TEST_TMP"))
        cls.home = Path(cls.tmp.name)
        (cls.home / "surfd.env").write_text("SURFD_KEY=testkey\n")
        cls.runs = cls.home / "runs"
        cls.runs.mkdir()
        os.environ.update(SURFD_HOME=str(cls.home), SURFD_ENV=str(cls.home / "surfd.env"),
                          SURFD_RUNS=str(cls.runs), SURFD_GAME=str(cls.home),
                          SURFD_DB=str(cls.home / "initial.db"),
                          SURFD_TOOLS=str(REPO / "tools"))
        for key in ("SURFD_EVIDENCE", "SURFD_KEEP"):
            os.environ.pop(key, None)
        cls.app = importlib.import_module("surfd")
        cls.sweep = importlib.import_module("sweep")
        cls.simcheck = importlib.import_module("simcheck")
        # Fixture-only fault, surrounding the unchanged real comparison.
        cls.tools = cls.home / "fixture-tools"
        (cls.tools / "census").mkdir(parents=True)
        real = str(REPO / "tools/census/recsim.py")
        (cls.tools / "census/recsim.py").write_text(
            "import importlib.util, os, time\n"
            "s=importlib.util.spec_from_file_location('fixture_real', %r)\n" % real
            + "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
            "globals().update({k:v for k,v in vars(m).items() if not k.startswith('__')})\n"
            "def compare_paths(*a, **kw):\n"
            "    with open(os.environ['_SIMTEST_MARKER'], 'w') as f: f.write(str(os.getpid()))\n"
            "    if os.environ.get('_SIMTEST_BEHAVIOR') == 'sleep': time.sleep(8)\n"
            "    if os.environ.get('_SIMTEST_BEHAVIOR') == 'memory': b=bytearray(1<<30)\n"
            "    if os.environ.get('_SIMTEST_BEHAVIOR') == 'lease':\n"
            "        import json\n"
            "        from pathlib import Path\n"
            "        def identity(fd):\n"
            "            try: st=os.fstat(fd)\n"
            "            except OSError: return None\n"
            "            return [st.st_dev, st.st_ino]\n"
            "        fd=int(os.environ['_SIMTEST_LEASE_FD'])\n"
            "        witness={'lease': identity(fd),\n"
            "                 'private': identity(int(os.environ['_SIMTEST_PRIVATE_FD']))}\n"
            "        witness['inheritable']=os.get_inheritable(fd) if witness['lease'] else False\n"
            "        ready=Path(os.environ['_SIMTEST_LEASE_READY'])\n"
            "        ready.with_suffix('.json').write_text(json.dumps(witness))\n"
            "        ready.touch()\n"
            "        release=Path(os.environ['_SIMTEST_LEASE_RELEASE'])\n"
            "        deadline=time.monotonic()+10\n"
            "        while not release.exists():\n"
            "            if time.monotonic()>deadline: raise RuntimeError('lease fixture not released')\n"
            "            time.sleep(.01)\n"
            "    return m.compare_paths(*a, **kw)\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()
        cls.tmp.cleanup()

    def setUp(self):
        self.app.DB_PATH = str(self.home / (self._testMethodName + ".db"))
        os.environ["SURFD_DB"] = self.app.DB_PATH
        self.app.migrate()
        self.conn = self.app.connect()
        self.addCleanup(self.conn.close)
        self.sweep.ensure_schema(self.conn)
        self.marker = self.home / (self._testMethodName + ".acted")
        os.environ["_SIMTEST_MARKER"] = str(self.marker)
        os.environ.pop("_SIMTEST_BEHAVIOR", None)
        self.sweep.TOOLS = str(REPO / "tools")
        os.environ["SURFD_TOOLS"] = self.sweep.TOOLS
        d = self.runs / "surf_control/main"
        d.mkdir(parents=True, exist_ok=True)
        for index, who in enumerate(("control-abcdef12", "control-12345678"), 1):
            leaf = "%07d_pb.rec" % index
            body = ["FTESURF-REC 9", "map surf_control", "track 0", "leg 0",
                    "tickrate 0.015", "who " + who, "begin"]
            body += ["in %d %d 0 %d %d 0 0 0 0 0 1" %
                     (i, i, (i * 7) % 451, (i * 3) % 451) for i in range(400)]
            body += ["end 400 0 0 0 0 0 0 0 0 0 0 0"]
            (d / leaf).write_text("\n".join(body) + "\n", encoding="utf-8")
            self.conn.execute(
                "INSERT INTO replays (map,map_dir,track,leg,leaf,tier,style,player,name,"
                "ticks,tickrate,millis,flags,node,submitted,kind) "
                "VALUES ('surf_control','surf_control',0,0,?,'ranked','normal',?,'control',"
                "400,66.6667,6000,0,'1',1,'run')", (leaf, who))
        self.conn.commit()

    def step(self, **kw):
        return self.sweep.similarity_step(self.conn, hard_process=True, **kw)

    def test_disabled_does_not_load_or_spawn(self):
        with mock.patch.object(self.sweep, "_simcheck", side_effect=AssertionError("loaded")):
            self.assertEqual(self.step(limit=0), (0, 0, ""))
            self.assertEqual(self.step(max_pairs=0), (0, 0, ""))
            self.assertEqual(self.step(max_seconds=0), (0, 0, ""))

    def test_unsupported_abstains_without_fallback(self):
        with mock.patch.object(self.simcheck.sys, "platform", "unsupported"), \
                mock.patch.object(self.simcheck.subprocess, "Popen", side_effect=AssertionError("spawned")):
            result = self.step()
        self.assertEqual(result[:2], (0, 0))
        self.assertIn("no unbounded fallback", result[2])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sims").fetchone()[0], 0)

    def test_transaction_is_not_committed_or_launched(self):
        self.conn.execute("UPDATE replays SET name='owned control' WHERE id=1")
        self.assertIn("active caller transaction", self.step()[2])
        self.assertTrue(self.conn.in_transaction)
        self.conn.rollback()

    def test_hard_process_flag_is_typed(self):
        with self.assertRaises(ValueError):
            self.sweep.similarity_step(self.conn, hard_process=1)

    def test_existing_only_never_creates_a_missing_database(self):
        self.app.DB_PATH = str(self.home / "missing-database.db")
        with self.assertRaises(sqlite3.OperationalError):
            self.app.connect(existing_only=True)
        self.assertFalse(Path(self.app.DB_PATH).exists())

    def test_existing_only_refuses_older_schema_without_migrating(self):
        self.conn.execute("PRAGMA user_version=%d" % (self.app.SCHEMA_VERSION - 1))
        self.conn.commit()
        with self.assertRaises(RuntimeError):
            self.app.connect(existing_only=True)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0],
                         self.app.SCHEMA_VERSION - 1)
        self.assertEqual([r[0] for r in self.conn.execute("SELECT tier FROM replays")],
                         ["ranked", "ranked"])

    def test_connect_preserves_default_and_sets_exact_native_wait(self):
        for kw, expected in (({}, 5000), ({"busy_timeout_ms": 7}, 7)):
            with self.subTest(kw=kw):
                conn = self.app.connect(existing_only=True, **kw)
                try:
                    self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], expected)
                finally:
                    conn.close()

    def test_bad_native_wait_refuses_before_sqlite_open(self):
        with mock.patch.object(self.app.sqlite3, "connect", side_effect=AssertionError("opened")):
            for value in (None, True, -1, 2147483648, 1.5, "7"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.app.connect(existing_only=True, busy_timeout_ms=value)

    def test_native_wait_covers_the_initial_readonly_schema_probe(self):
        self.conn.close()
        owner = sqlite3.connect(self.app.DB_PATH, timeout=0)
        try:
            self.assertEqual(owner.execute("PRAGMA journal_mode=DELETE").fetchone()[0], "delete")
            owner.execute("BEGIN EXCLUSIVE")
            self.assertTrue(owner.in_transaction, "lock control did not act")
            started = time.monotonic()
            with self.assertRaises(sqlite3.OperationalError):
                self.app.connect(existing_only=True, busy_timeout_ms=1)
            # A broad startup regression ceiling, NOT a one-ms wall-time claim.
            self.assertLess(time.monotonic() - started, 1.0)
        finally:
            owner.rollback()
            owner.close()

    def test_worker_forwards_native_wait_and_closes_its_connection(self):
        request = {"version": 1, "db": os.path.realpath(self.app.DB_PATH),
                   "limits": [1, 2, 0.1, 1234, 7]}
        called = []

        def step(conn, **kwargs):
            called.append(conn)
            self.assertEqual(kwargs["max_lock_ms"], 7)
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 7)
            return 0, 0, ""

        with mock.patch.object(self.simcheck, "process_limits_present", return_value=True), \
                mock.patch.object(self.simcheck.sys, "stdin") as source, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            source.buffer = io.BytesIO(json.dumps(request).encode("utf-8"))
            self.assertEqual(self.simcheck.process_worker(self.app, step), 0)
        self.assertEqual(json.loads(output.getvalue())["stored"], 0)
        self.assertEqual(len(called), 1, "forwarding control did not act")
        with self.assertRaises(sqlite3.ProgrammingError):
            called[0].execute("SELECT 1")

    def test_memory_database_cannot_dispatch_to_another_database(self):
        memory = sqlite3.connect(":memory:")
        try:
            with mock.patch.object(self.simcheck.sys, "platform", "linux"), \
                    mock.patch.object(self.simcheck.os, "access", return_value=True), \
                    mock.patch.object(self.simcheck.subprocess, "Popen", side_effect=AssertionError("spawned")):
                result = self.sweep.similarity_step(memory, hard_process=True)
            self.assertIn("configured on-disk database", result[2])
        finally:
            memory.close()

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_actual_worker_compares_and_preserves_ranked_rows(self):
        result = self.step()
        self.assertEqual(result[0], 1, result)
        row = self.conn.execute('SELECT verdict,"match" FROM sims').fetchone()
        self.assertEqual(tuple(row), ("compared", 1.0))
        self.assertEqual([r[0] for r in self.conn.execute("SELECT tier FROM replays")],
                         ["ranked", "ranked"])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM verdicts").fetchone()[0], 0)

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_worker_retains_explicit_lease_but_not_private_descriptor(self):
        self._assert_inherited_lease(self.step)

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_native_verifier_retains_explicit_lease_but_not_private_descriptor(self):
        engine = self.home / "lease-engine"
        engine.write_text(
            "#!" + sys.executable + "\n"
            "import importlib.util, sys\n"
            "s=importlib.util.spec_from_file_location('lease_reader', %r)\n" %
            str(self.tools / "census/recsim.py")
            + "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
            "verdict, data=m.compare_paths(%r, %r, max_bytes=1048576, max_moves=1000)\n" %
            tuple(str(self.runs / "surf_control/main" / ("%07d_pb.rec" % i))
                  for i in (1, 2))
            + "assert verdict == 'compared' and data['compared'] > 0\n"
            "index=sys.argv.index('+pm_verify'); path, challenge=sys.argv[index+1:index+3]\n"
            "print('VERIFY-INPUT '+path+' SHA256 '+('a'*64)+' CHALLENGE '+challenge)\n"
            "print('VERIFY '+path+' PASS ticks 400 rows 400')\n",
            encoding="utf-8")
        engine.chmod(0o700)

        def run():
            path = "data/runs/surf_control/main/0000001_pb.rec"
            with mock.patch.object(self.sweep, "ENGINE", str(engine)), \
                    mock.patch.object(self.sweep, "GAME", str(self.home)):
                result = self.sweep.run_verifier("surf_control", [path])
            self.assertEqual(result, ["VERIFY-SOURCE " + path + " SHA256 " + "a" * 64,
                                      "VERIFY " + path + " PASS ticks 400 rows 400"])
            return 1, 0, ""

        self._assert_inherited_lease(run)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sims").fetchone()[0], 0)
        self.assertEqual([r[0] for r in self.conn.execute("SELECT tier FROM replays")],
                         ["ranked", "ranked"])

    def _assert_inherited_lease(self, run):
        import fcntl

        prefix = self._testMethodName
        lease_path = self.home / (prefix + ".lifetime.lock")
        private_path = self.home / (prefix + ".private-fd")
        lease_path.touch()
        private_path.touch()
        lease = os.open(lease_path, os.O_RDONLY)
        private = os.open(private_path, os.O_RDONLY)
        self.assertFalse(os.get_inheritable(private))
        expected = [os.fstat(lease).st_dev, os.fstat(lease).st_ino]
        private_identity = [os.fstat(private).st_dev, os.fstat(private).st_ino]
        fcntl.flock(lease, fcntl.LOCK_SH | fcntl.LOCK_NB)
        os.set_inheritable(lease, True)
        ready = self.home / (prefix + ".lease.ready")
        release = self.home / (prefix + ".lease.release")
        lease_open = [True]
        observations = []
        errors = []

        def probe():
            try:
                deadline = time.monotonic() + 5
                while not ready.exists():
                    if time.monotonic() > deadline:
                        raise RuntimeError("lease comparison never acted")
                    time.sleep(.01)
                os.close(lease)
                lease_open[0] = False
                with lease_path.open("rb") as independent:
                    try:
                        fcntl.flock(independent, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        observations.append("child still holds lease")
                    else:
                        observations.append("premature drain")
            except Exception as exc:
                errors.append(repr(exc))
            finally:
                release.touch()

        controller = threading.Thread(target=probe)
        self.sweep.TOOLS = str(self.tools)
        try:
            with mock.patch.dict(os.environ, {
                    "_SIMTEST_BEHAVIOR": "lease", "_SIMTEST_LEASE_FD": str(lease),
                    "_SIMTEST_PRIVATE_FD": str(private),
                    "_SIMTEST_LEASE_READY": str(ready),
                    "_SIMTEST_LEASE_RELEASE": str(release)}):
                controller.start()
                result = run()
        finally:
            release.touch()
            if controller.ident is not None:
                controller.join(7)
            if lease_open[0]:
                os.close(lease)
            os.close(private)
        self.assertFalse(controller.is_alive(), "own lease probe did not stop")
        self.assertEqual(errors, [])
        self.assertTrue(self.marker.exists(), "comparison never acted")
        self.assertEqual(result[0], 1, result)
        self.assertEqual(observations, ["child still holds lease"])
        witness = json.loads(ready.with_suffix(".json").read_text())
        self.assertEqual(witness["lease"], expected)
        self.assertTrue(witness["inheritable"])
        self.assertNotEqual(witness["private"], private_identity)
        with lease_path.open("rb") as independent:
            fcntl.flock(independent, fcntl.LOCK_EX | fcntl.LOCK_NB)

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_missing_prlimit_abstains(self):
        with mock.patch.object(self.simcheck, "PRLIMIT", str(self.home / "missing-prlimit")):
            result = self.step()
        self.assertIn("containment unavailable", result[2])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sims").fetchone()[0], 0)

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_direct_worker_without_os_limits_refuses(self):
        result = subprocess.run([sys.executable, str(HERE / "sweep.py"), "--similarity-worker"],
                                input="{}", text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual([r[0] for r in self.conn.execute("SELECT tier FROM replays")],
                         ["ranked", "ranked"])

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_timeout_reaps_acted_worker_then_badge_phase_runs(self):
        self.sweep.TOOLS = str(self.tools)
        os.environ["_SIMTEST_BEHAVIOR"] = "sleep"
        badge = []
        started = time.monotonic()
        with mock.patch.object(self.simcheck, "PROCESS_SECONDS", 3.0), \
                mock.patch.object(self.sweep, "receipt_step", return_value=(0, 0)), \
                mock.patch.object(self.sweep, "sweep", side_effect=lambda *a: badge.append(True) or {}), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.sweep.main(["--limit", "0"]), 0)
        self.assertTrue(self.marker.exists(), "comparison never acted")
        pid = int(self.marker.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(badge, [True])
        self.assertIn("timed out; outcome unavailable", output.getvalue())
        self.assertLess(time.monotonic() - started, 7)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sims").fetchone()[0], 0)

    @unittest.skipUnless(LINUX, "actual Linux containment required")
    def test_memory_cap_yields_no_numeric_measurement(self):
        self.sweep.TOOLS = str(self.tools)
        os.environ["_SIMTEST_BEHAVIOR"] = "memory"
        result = self.step()
        self.assertTrue(self.marker.exists(), "allocation arm never acted")
        self.assertEqual(self.conn.execute(
            'SELECT count(*) FROM sims WHERE "match" IS NOT NULL').fetchone()[0], 0)
        self.assertFalse(self.conn.in_transaction)
        self.assertTrue(result[2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
