"""Journal delivery falsifiers. All keys, receipts and journals are synthetic.
Run: python -m unittest discover -s surfd -p test_hidupload.py -v
Set FTESURF_TEST_ROOT to keep temporary fixtures under an owned task root.
"""
import hashlib
import io
import logging
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

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


def receipt(root, blob, mapname="surf_test", runid="1234_5678", nonce=NONCE):
    d = Path(root) / mapname
    d.mkdir(parents=True, exist_ok=True)
    msg = ("FTESURF-RCPT 1\nserver 127.0.0.1:27510\nnonce %s\nticks 1\nhid %s %d 1\nview -\n" % (
        nonce, hashlib.sha256(blob).hexdigest(), len(blob))).encode("ascii")
    p = d / (runid + ".rcpt")
    signed = "".join("signed " + line + "\n" for line in msg.decode("ascii").splitlines()[1:])
    p.write_text("FTESURF-RCPT 1\nrunid %s\npub %s\nsig %s\n%s" % (
        runid, PUB, ed25519.sign(SEED, msg).hex(), signed), encoding="ascii")
    return d / (runid + ".hid")


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hidupload-", dir=os.getenv("FTESURF_TEST_ROOT"))
        self.addCleanup(self.tmp.cleanup)
        self.allowed = True
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=16 * 1024)
        hidupload.register(self.app, types.SimpleNamespace(
            evidence=lambda: self.tmp.name, rate_key=lambda: "synthetic",
            clock=lambda: 1, rate_ok=lambda *a, **k: self.allowed,
            fail=lambda message, code: (jsonify(error=message), code),
            log=logging.getLogger(__name__)))

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

    def test_body_cap_is_scoped_and_extra_body_rejected(self):
        result = self.client.post("/small", data={"payload": "a" * 20000})
        self.assertEqual(result.status_code, 413)
        self.assertEqual(self.post(packet(self.blob) + b"extra").status_code, 400)
        self.assertEqual(self.post(packet(self.blob), environ_overrides={
            "CONTENT_LENGTH": str(hidupload.MAX_JOURNAL + hidupload.HEADER_SIZE + 1)}).status_code, 413)
        self.assertEqual(self.client.get("/api/hid").status_code, 405)
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
