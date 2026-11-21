"""Journal delivery falsifiers. All keys, receipts and journals are synthetic.
Run: python -m unittest discover -s surfd -p test_hidupload.py -v
Set FTESURF_TEST_ROOT to keep temporary fixtures under an owned task root.
"""
import hashlib
import io
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from flask import Flask, jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ed25519
import hidupload

SEED = bytes(range(32))
PUB = ed25519.publickey(SEED).hex()
NONCE = "10" * 16


def statement(blob, mapname="surf_test", runid="1234_5678", nonce=NONCE):
    return ("FTESURF-HID 1\nmap %s\nrunid %s\nnonce %s\nhid %s %d\n" % (
        mapname, runid, nonce, hashlib.sha256(blob).hexdigest(), len(blob))).encode("ascii")


def packet(blob, mapname="surf_test", runid="1234_5678", nonce=NONCE, seed=SEED):
    msg = statement(blob, mapname, runid, nonce)
    header = msg + ("pub %s\nsig %s\n" % (
        ed25519.publickey(seed).hex(), ed25519.sign(seed, msg).hex())).encode("ascii")
    return header.ljust(hidupload.HEADER_SIZE - 1, b" ") + b"\n" + blob


def receipt(root, blob, mapname="surf_test", runid="1234_5678", nonce=NONCE, ticks="1"):
    d = Path(root) / mapname
    d.mkdir(parents=True, exist_ok=True)
    msg = ("FTESURF-RCPT 1\nserver 127.0.0.1:27510\nnonce %s\nticks %s\nhid %s %d 1\nview -\n" % (
        nonce, ticks, hashlib.sha256(blob).hexdigest(), len(blob))).encode("ascii")
    p = d / (runid + ".rcpt")
    signed = "".join("signed " + line + "\n" for line in msg.decode("ascii").splitlines()[1:])
    p.write_text("FTESURF-RCPT 1\nrunid %s\npub %s\nsig %s\n%s" % (
        runid, PUB, ed25519.sign(SEED, msg).hex(), signed), encoding="ascii")
    return d / (runid + ".hid")


class UploadTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("SURFD_HID_BASE_BYTES", "SURFD_HID_BYTES_PER_TICK"):
            os.environ.pop(key, None)
        self.tmp = tempfile.TemporaryDirectory(prefix="hidupload-", dir=os.getenv("FTESURF_TEST_ROOT"))
        self.addCleanup(self.tmp.cleanup)
        self.allowed = True
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=16 * 1024)
        self.env = types.SimpleNamespace(
            evidence=lambda: self.tmp.name, rate_key=lambda: "synthetic",
            clock=lambda: 1, rate_ok=lambda *a, **k: self.allowed,
            fail=lambda message, code: (jsonify(error=message), code),
            log=logging.getLogger(__name__))
        hidupload.register(self.app, self.env)

        @self.app.post("/small")
        def small():
            # Flask 2.2 enforces this cap during form parsing, not get_data.
            # Exercise the enforcing interface on both supported generations.
            return str(len(request.form.get("payload", "")))

        self.client = self.app.test_client()
        self.blob = b"synthetic journal\n" * 2000
        self.dest = receipt(self.tmp.name, self.blob)

    def post(self, data, **kwargs):
        return self.client.post("/api/hid", data=data,
                                content_type="application/octet-stream", **kwargs)

    def assert_clean(self):
        self.assertFalse(self.dest.exists())
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])

    def test_large_finished_run_without_sibling_recording(self):
        blob = bytes(range(256)) * (5 * 4096)
        self.dest = receipt(self.tmp.name, blob)
        self.assertGreater(len(blob), 4 * 1024 * 1024)
        self.assertFalse(self.dest.with_suffix(".rec").exists())
        result = self.post(packet(blob))
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.dest.read_bytes(), blob)
        self.assertEqual(result.data, ("stored %s %d\n" % (
            hashlib.sha256(blob).hexdigest(), len(blob))).encode("ascii"))
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])

    def test_dotted_map_case_is_preserved(self):
        self.dest = receipt(self.tmp.name, self.blob, mapname="Surf.Test+v1")
        result = self.post(packet(self.blob, mapname="Surf.Test+v1"))
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.dest.read_bytes(), self.blob)

    def test_actual_error_statuses(self):
        self.assertEqual(self.post(b"x" * 2048).status_code, 400)
        self.allowed = False
        self.assertEqual(self.post(packet(self.blob)).status_code, 429)
        self.allowed = True
        self.dest.with_suffix(".rcpt").unlink()
        self.assertEqual(self.post(packet(self.blob)).status_code, 410)     # P1704: no receipt is final
        self.assert_clean()
        for p in Path(self.tmp.name).iterdir():
            for f in p.iterdir():
                f.unlink()
            p.rmdir()
        self.assertEqual(self.post(packet(self.blob)).status_code, 503)     # an empty evidence root: retryable
        (Path(self.tmp.name) / "surf_other").mkdir()
        self.assertEqual(self.post(packet(self.blob)).status_code, 410)     # maps present, this one unknown: junk

    def test_wrong_nonce_key_signature_and_receipt_commitment(self):
        bad_signature = bytearray(packet(self.blob))
        start = bad_signature.index(b"\nsig ") + 5
        bad_signature[start] = ord("0") if bad_signature[start] != ord("0") else ord("1")
        for name, data in [
                ("nonce", packet(self.blob, nonce="11" * 16)),
                ("key", packet(self.blob, seed=bytes(range(1, 33)))),
                ("signature", bytes(bad_signature)),
                ("commitment", packet(self.blob + b"changed"))]:
            with self.subTest(name=name):
                self.assertEqual(self.post(data).status_code, 403)
                self.assert_clean()

    def test_wrong_digest_and_truncation(self):
        data = packet(self.blob)
        self.assertEqual(self.post(data[:-1] + b"X").status_code, 400)
        self.assert_clean()
        # A transport-level early EOF keeps its original Content-Length.
        env = {"CONTENT_LENGTH": str(len(data)), "wsgi.input": io.BytesIO(data[:-1])}
        self.assertEqual(self.client.open("/api/hid", method="POST", environ_overrides=env,
                         content_type="application/octet-stream").status_code, 400)
        self.assert_clean()

    def test_duplicate_and_conflicting_existing_evidence(self):
        data = packet(self.blob)
        self.assertEqual(self.post(data).status_code, 200)
        self.assertEqual(self.post(data).status_code, 200)
        self.assertEqual(self.dest.read_bytes(), self.blob)
        self.dest.write_bytes(b"operator must preserve this conflict")
        self.assertEqual(self.post(data).status_code, 409)
        self.assertEqual(self.dest.read_bytes(), b"operator must preserve this conflict")
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])

    def test_path_traversal_and_wrong_run_are_refused(self):
        for mapname in ("../surf_test", ".hidden", "surf..test", "surf/test"):
            self.assertEqual(self.post(packet(self.blob, mapname=mapname)).status_code, 400)
            self.assert_clean()
        self.assertEqual(self.post(packet(self.blob, runid="different")).status_code, 410)   # P1704: final
        self.assert_clean()

    def budget_client(self, base="128", per_tick="64"):
        app = Flask(__name__)
        app.config.update(TESTING=True, MAX_CONTENT_LENGTH=16 * 1024)
        with mock.patch.dict(os.environ):
            for key, value in (("SURFD_HID_BASE_BYTES", base),
                               ("SURFD_HID_BYTES_PER_TICK", per_tick)):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            hidupload.register(app, self.env)
        return app.test_client()

    def test_run_budget_refuses_before_body_or_temporary_file(self):
        client = self.budget_client()
        blob = b"x" * 4096
        self.dest = receipt(self.tmp.name, blob, ticks="1")
        data = packet(blob)
        stream = io.BytesIO(data)
        with mock.patch.object(hidupload.tempfile, "mkstemp", wraps=tempfile.mkstemp) as create:
            result = client.open("/api/hid", method="POST", content_type="application/octet-stream",
                                 environ_overrides={"CONTENT_LENGTH": str(len(data)),
                                                    "wsgi.input": stream})
        self.assertEqual(result.status_code, 413, result.data)
        self.assertEqual(stream.tell(), hidupload.HEADER_SIZE)
        create.assert_not_called()
        self.assert_clean()

    def test_run_budget_exact_boundary_and_longer_signed_run(self):
        client = self.budget_client()
        for runid, ticks, size, expected in (("boundary", "3", 320, 200),
                                            ("excess", "3", 321, 413),
                                            ("longer", "4", 321, 200)):
            with self.subTest(runid=runid):
                blob = b"x" * size
                dest = receipt(self.tmp.name, blob, runid=runid, ticks=ticks)
                result = client.post("/api/hid", data=packet(blob, runid=runid),
                                     content_type="application/octet-stream")
                self.assertEqual(result.status_code, expected, result.data)
                self.assertEqual(dest.exists(), expected == 200)
                if expected == 200:
                    self.assertEqual(dest.read_bytes(), blob)
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])

    def test_run_budget_unknown_clock_is_unavailable_not_a_fault(self):
        client = self.budget_client()
        for ticks in ("0", "-1", "+1", "01", "1.0", "1e2", "NaN", "1_0", "999999999999"):
            with self.subTest(ticks=ticks):
                self.dest = receipt(self.tmp.name, self.blob, ticks=ticks)
                data = packet(self.blob)
                stream = io.BytesIO(data)
                with mock.patch.object(hidupload.tempfile, "mkstemp", wraps=tempfile.mkstemp) as create:
                    result = client.open("/api/hid", method="POST", content_type="application/octet-stream",
                                         environ_overrides={"CONTENT_LENGTH": str(len(data)),
                                                            "wsgi.input": stream})
                # still no verdict about the run; 403 since P1704, whose clients would re-send a 503 six times
                self.assertEqual(result.status_code, 403, result.data)
                self.assertEqual(result.json["error"], "journal run budget unavailable")
                self.assertEqual(stream.tell(), hidupload.HEADER_SIZE)
                create.assert_not_called()
                self.assert_clean()

    def test_run_budget_requires_complete_canonical_operator_configuration(self):
        maximum = str(hidupload.MAX_JOURNAL)
        for base, rate in ((None, "64"), ("128", None), ("", "64"), ("128", ""),
                           ("-1", "64"), ("128", "0"), ("1.0", "64"), ("128", "1e2"),
                           ("01", "64"), ("128", "+1"), ("1_0", "64"), ("١", "64"),
                           (str(int(maximum) + 1), "64"), ("128", str(int(maximum) + 1))):
            with self.subTest(base=base, rate=rate):
                with self.assertRaisesRegex(ValueError, "journal run budget"):
                    self.budget_client(base, rate)

    def test_run_budget_is_captured_at_registration_and_keeps_absolute_ceiling(self):
        client = self.budget_client("0", str(hidupload.MAX_JOURNAL))
        self.dest = receipt(self.tmp.name, self.blob, ticks="99999999999")
        with mock.patch.dict(os.environ, {"SURFD_HID_BASE_BYTES": "0",
                                         "SURFD_HID_BYTES_PER_TICK": "1"}):
            result = client.post("/api/hid", data=packet(self.blob),
                                 content_type="application/octet-stream")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.dest.read_bytes(), self.blob)
        self.assertEqual(hidupload._run_byte_limit((0, hidupload.MAX_JOURNAL), "99999999999"),
                         hidupload.MAX_JOURNAL)
        result = client.post("/api/hid", data=packet(self.blob), content_type="application/octet-stream",
                             environ_overrides={"CONTENT_LENGTH": str(hidupload.MAX_JOURNAL +
                                                                      hidupload.HEADER_SIZE + 1)})
        self.assertEqual(result.status_code, 413)

    def test_run_budget_uses_application_setting_loader(self):
        values = {"SURFD_HID_BASE_BYTES": "0", "SURFD_HID_BYTES_PER_TICK": "1"}
        self.env.setting = lambda name, default=None: values.get(name, default)
        client = self.budget_client(None, None)
        result = client.post("/api/hid", data=packet(self.blob), content_type="application/octet-stream")
        self.assertEqual(result.status_code, 413, result.data)
        self.assert_clean()

    def test_run_budget_preserves_already_stored_evidence(self):
        client = self.budget_client()
        original = b"existing evidence stays byte-for-byte"
        self.dest.write_bytes(original)
        result = client.post("/api/hid", data=packet(self.blob), content_type="application/octet-stream")
        self.assertEqual(result.status_code, 413, result.data)
        self.assertEqual(self.dest.read_bytes(), original)
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])

    def test_run_budget_does_not_replace_receipt_authentication(self):
        client = self.budget_client()
        for data, expected in ((packet(self.blob, nonce="11" * 16), 403),
                               (packet(self.blob, seed=bytes(range(1, 33))), 403),
                               (packet(self.blob, runid="not_published"), 410)):   # P1704: final
            with self.subTest(expected=expected):
                result = client.post("/api/hid", data=data, content_type="application/octet-stream")
                self.assertEqual(result.status_code, expected, result.data)
                self.assert_clean()

    def test_body_cap_is_scoped_and_extra_body_rejected(self):
        result = self.client.post("/small", data={"payload": "a" * 20000})
        self.assertEqual(result.status_code, 413)
        self.assertEqual(self.post(packet(self.blob) + b"extra").status_code, 400)
        self.assertEqual(self.post(packet(self.blob), environ_overrides={
            "CONTENT_LENGTH": str(hidupload.MAX_JOURNAL + hidupload.HEADER_SIZE + 1)}).status_code, 413)
        self.assertEqual(self.client.get("/api/hid").status_code, 405)
        self.assert_clean()


def view_packet(blob, mapname="surf_test", runid="1234_5678", nonce=NONCE, seed=SEED, server="127.0.0.1:27510"):
    """P1704: a run's view sidecar, posted to /api/view with its own statement."""
    msg = ("FTESURF-VIEW 1\nserver %s\nmap %s\nrunid %s\nnonce %s\nview %s %d\n" % (
        server, mapname, runid, nonce, hashlib.sha256(blob).hexdigest(), len(blob))).encode("ascii")
    header = msg + ("pub %s\nsig %s\n" % (
        ed25519.publickey(seed).hex(), ed25519.sign(seed, msg).hex())).encode("ascii")
    return header.ljust(hidupload.HEADER_SIZE - 1, b" ") + b"\n" + blob


def view_receipt(root, view, mapname="surf_test", runid="1234_5678", nonce=NONCE, ticks="100", digest=None,
                 server="127.0.0.1:27510"):
    d = Path(root) / mapname
    d.mkdir(parents=True, exist_ok=True)
    digest = digest or hashlib.sha256(view).hexdigest()
    msg = ("FTESURF-RCPT 1\nserver %s\nnonce %s\nticks %s\nhid - 0 0\nview %s\n" % (
        server, nonce, ticks, digest)).encode("ascii")
    p = d / (runid + ".rcpt")
    signed = "".join("signed " + line + "\n" for line in msg.decode("ascii").splitlines()[1:])
    p.write_text("FTESURF-RCPT 1\nrunid %s\npub %s\nsig %s\n%s" % (
        runid, PUB, ed25519.sign(SEED, msg).hex(), signed), encoding="ascii")
    return d / (runid + ".view")


class ViewUploadTests(unittest.TestCase):
    def setUp(self):
        UploadTests.setUp(self)
        self.view = b"FTESURF-VIEW synthetic frames\n" * 3000          # 90 KB: inside 256 KiB + 100 ticks * 4 KiB
        self.vdest = view_receipt(self.tmp.name, self.view, runid="9999_0001")

    def post(self, data, path="/api/view"):
        return self.client.post(path, data=data, content_type="application/octet-stream")

    def test_view_is_stored_against_the_receipt(self):
        with self.assertLogs(level="INFO") as logs:
            r = self.post(view_packet(self.view, runid="9999_0001"))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.vdest.read_bytes(), self.view)
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])
        self.assertTrue(any("stored view for surf_test/9999_0001" in m for m in logs.output), logs.output)

    def test_routes_take_only_their_own_kind(self):
        self.assertEqual(self.post(view_packet(self.view, runid="9999_0001"), "/api/hid").status_code, 400)
        self.assertEqual(self.post(packet(self.blob)).status_code, 400)
        self.assertFalse(self.vdest.exists())
        self.assertFalse(self.dest.exists())

    def test_a_receipt_without_a_view_takes_none(self):
        # the default receipt commits to a journal and `view -`
        r = self.post(view_packet(self.blob))
        self.assertEqual(r.status_code, 403, r.data)
        self.assertFalse(self.dest.with_suffix(".view").exists())

    def test_a_mismatched_view_is_refused_and_logged(self):
        other = b"another sidecar\n" * 100
        with self.assertLogs(level="WARNING") as logs:
            r = self.post(view_packet(other, runid="9999_0001"))
        self.assertEqual(r.status_code, 403, r.data)
        self.assertFalse(self.vdest.exists())
        self.assertTrue(any("view does not match its receipt" in m and "9999_0001" in m for m in logs.output),
                        logs.output)
        marker = self.vdest.with_suffix(".viewrefused")
        self.assertIn("offered %s %d" % (hashlib.sha256(other).hexdigest(), len(other)), marker.read_text())
        before = marker.read_bytes()
        self.post(view_packet(b"a third\n", runid="9999_0001"))
        self.assertEqual(marker.read_bytes(), before)                       # the first offer is kept

    def test_a_statement_from_another_server_is_refused(self):
        with self.assertLogs(level="WARNING") as logs:
            r = self.post(view_packet(self.view, runid="9999_0001", server="10.0.0.9:27500"))
        self.assertEqual(r.status_code, 410, r.data)
        self.assertFalse(self.vdest.exists())
        self.assertTrue(any("names another server" in m for m in logs.output), logs.output)
        self.assertEqual(self.post(view_packet(self.view, runid="9999_0001", server="bad server")).status_code, 400)

    def test_a_scheme_server_name_is_accepted(self):
        # DTLS/TLS/WebSocket clients sign the server with its scheme (rcptcheck SERVER_SCHEMES)
        dest = view_receipt(self.tmp.name, self.view, runid="9999_0005", server="dtls://203.0.113.7:27510")
        r = self.post(view_packet(self.view, runid="9999_0005", server="dtls://203.0.113.7:27510"))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(dest.read_bytes(), self.view)

    def test_no_receipt_is_final_for_a_view(self):
        r = self.post(view_packet(self.view, runid="9999_0404"))
        self.assertEqual(r.status_code, 410, r.data)          # final; the client counts it as junk

    def test_an_unfinished_run_takes_no_view(self):
        for ticks in ("0", "-1"):
            dest = view_receipt(self.tmp.name, self.view, runid="9999_000" + ticks[-1], ticks=ticks)
            r = self.post(view_packet(self.view, runid="9999_000" + ticks[-1]))
            self.assertEqual(r.status_code, 403, (ticks, r.data))
            self.assertFalse(dest.exists())

    def test_view_budget_follows_the_run_clock(self):
        big = b"0.1234 100 10 1.00 2.00 0\n" * 12000                 # 312 KB > 256 KiB + 4 KiB
        dest = view_receipt(self.tmp.name, big, runid="9999_0003", ticks="1")
        r = self.post(view_packet(big, runid="9999_0003"))
        self.assertEqual(r.status_code, 413, r.data)
        self.assertFalse(dest.exists())
        self.assertEqual(list(Path(self.tmp.name).rglob("*.part")), [])

    def test_existing_view_is_preserved(self):
        self.assertEqual(self.post(view_packet(self.view, runid="9999_0001")).status_code, 200)
        self.assertEqual(self.post(view_packet(self.view, runid="9999_0001")).status_code, 200)
        self.vdest.write_bytes(b"kept")
        self.assertEqual(self.post(view_packet(self.view, runid="9999_0001")).status_code, 409)
        self.assertEqual(self.vdest.read_bytes(), b"kept")

    def test_view_size_cap(self):
        big = b"v" * (hidupload.MAX_VIEW + 1)
        view_receipt(self.tmp.name, big, runid="9999_0002", ticks="100000")
        r = self.post(view_packet(big, runid="9999_0002"))
        self.assertEqual(r.status_code, 413, r.data)

    def test_each_route_counts_every_request_in_its_own_bucket(self):
        seen = []
        self.env.rate_ok = lambda *a, **k: seen.append((k.get("bucket"), k.get("cap"))) or True
        self.post(view_packet(self.view, runid="9999_0001"))
        self.post(b"x" * 2048)                                        # malformed: still counted
        self.post(packet(self.blob), "/api/hid")
        self.assertEqual(seen, [("view", hidupload.VIEW_RATE_MAX), ("view", hidupload.VIEW_RATE_MAX),
                                ("hid", hidupload.RATE_MAX)])


class ApplicationBudgetTests(unittest.TestCase):
    def test_actual_application_file_setting_and_environment_precedence(self):
        source = Path(__file__).resolve().parent
        script = """
import sys
sys.path.insert(0, sys.argv[1])
import surfd
from test_hidupload import packet, receipt
blob = b'x' * 321
path = receipt(surfd.EVIDENCE_DIR, blob, ticks='3')
result = surfd.app.test_client().post('/api/hid', data=packet(blob),
                                     content_type='application/octet-stream')
expected = int(sys.argv[2])
assert result.status_code == expected, (result.status_code, result.data)
assert path.exists() == (expected == 200)
if expected == 200:
    assert path.read_bytes() == blob
print('Actual app budget route acted:', expected)
"""
        for override, expected in ((None, 413), ("512", 200)):
            with self.subTest(override=override), tempfile.TemporaryDirectory(
                    prefix="hidupload-app-", dir=os.getenv("FTESURF_TEST_ROOT")) as temporary:
                home = Path(temporary)
                config = home / "surfd.env"
                config.write_text("SURFD_HID_BASE_BYTES=128\nSURFD_HID_BYTES_PER_TICK=64\n",
                                  encoding="ascii")
                env = os.environ.copy()
                for key in ("SURFD_HID_BASE_BYTES", "SURFD_HID_BYTES_PER_TICK"):
                    env.pop(key, None)
                env.update(PYTHONDONTWRITEBYTECODE="1", SURFD_HOME=str(home),
                           SURFD_ENV=str(config), SURFD_DB=str(home / "app.db"),
                           SURFD_GAME=str(home / "game"), SURFD_RUNS=str(home / "runs"),
                           SURFD_EVIDENCE=str(home / "evidence"), SURFD_KEEP=str(home / "keep"),
                           SURFD_TOOLS=str(source.parent / "tools"), SURFD__SIMCHECK_CHILD="0",
                           SURFD_ADMIN_HASH="")
                if override is not None:
                    env["SURFD_HID_BASE_BYTES"] = override
                result = subprocess.run([sys.executable, "-B", "-c", script, str(source), str(expected)],
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Actual app budget route acted: " + str(expected), result.stdout)


if __name__ == "__main__":
    unittest.main()
