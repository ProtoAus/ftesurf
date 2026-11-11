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
        self.assertEqual(self.post(packet(self.blob)).status_code, 503)
        self.assert_clean()

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
        self.assertEqual(self.post(packet(self.blob, runid="different")).status_code, 503)
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
                self.assertEqual(result.status_code, 503, result.data)
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
                               (packet(self.blob, runid="not_published"), 503)):
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
