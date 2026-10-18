"""P804 additive installer controls; real fixture files, no live nginx writes.

Run on POSIX: python3 -m unittest test_hid_proxy_install
Only the fixed /etc destinations and nginx/systemctl processes are substituted.
"""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent
SCRIPT = (SOURCE / "setup_public.sh").read_text()
BODY = SCRIPT.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
CODE = compile(BODY, str(SOURCE / "setup_public.sh") + ":hid-only", "exec")
DESTS = ("/etc/nginx/snippets/surfd.conf", "/etc/nginx/conf.d/surfd-ratelimit.conf")
REAL_PATH = type(SOURCE)


@unittest.skipUnless(os.name == "posix", "installer uses POSIX file ownership")
class InstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = REAL_PATH(self.temp.name)
        self.paths = [self.root / p.lstrip("/") for p in DESTS]
        self.before = [b"# keep unrelated routes verbatim\nlocation = /health { return 200; }\n",
                       b"# keep unrelated limits verbatim\nlimit_req_zone $binary_remote_addr zone=existing:1m rate=1r/s;\n"]
        for p, b in zip(self.paths, self.before):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b)
            p.chmod(0o644)
        self.calls = []
        self.backup = self.root / "backup"
        self.hashes = [hashlib.sha256(b).hexdigest() for b in self.before]
        self.addCleanup(self.temp.cleanup)

    def run_install(self, *, hashes=None, failure=None, peer=None):
        def mapped(value):
            return self.paths[DESTS.index(str(value))] if str(value) in DESTS else REAL_PATH(value)

        failed = False

        def command(args, **kwargs):
            nonlocal failed
            self.calls.append(args)
            if peer:
                peer(args)
            if args == failure and not failed:
                failed = True
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0)

        with mock.patch("pathlib.Path", mapped), mock.patch("subprocess.run", command), \
                mock.patch.object(sys, "argv", ["-", str(SOURCE), str(self.backup), *(hashes or self.hashes)]), \
                contextlib.redirect_stdout(io.StringIO()):
            exec(CODE, {"__name__": "__hid_install_test__"})

    def unchanged(self):
        self.assertEqual([p.read_bytes() for p in self.paths], self.before)
        for p in self.paths:
            self.assertEqual(list(p.parent.glob("*.hid-new-*")), [])

    def test_adds_only_declared_block_and_zones(self):
        self.run_install()
        block = re.findall(r"(?ms)^location = /api/hid \{\n.*?^\}", (SOURCE / "surfd.nginx").read_text())[0]
        self.assertEqual(self.paths[0].read_bytes(), self.before[0] + b"\n" + block.encode() + b"\n")
        self.assertTrue(self.paths[1].read_bytes().startswith(self.before[1]))
        added = self.paths[1].read_text()[len(self.before[1]):]
        self.assertEqual(len(re.findall(r"(?m)^limit_(?:req|conn)_zone", added)), 3)
        self.assertEqual([p.stat().st_mode & 0o777 for p in self.paths], [0o644, 0o644])
        self.assertEqual(self.calls, [["nginx", "-t"], ["systemctl", "reload", "nginx"]])
        for p, old in zip(self.paths, self.before):
            self.assertEqual((self.backup / p.name).read_bytes(), old)
        self.assertTrue((self.backup / "receipt.json").is_file())

    def test_stale_config_does_not_write(self):
        with self.assertRaisesRegex(SystemExit, "changed"):
            self.run_install(hashes=["0" * 64, self.hashes[1]])
        self.unchanged()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.backup.exists())

    def test_nginx_test_failure_restores_without_reload(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_install(failure=["nginx", "-t"])
        self.unchanged()
        self.assertEqual(self.calls, [["nginx", "-t"]])

    def test_reload_failure_restores_then_reloads_previous(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_install(failure=["systemctl", "reload", "nginx"])
        self.unchanged()
        self.assertEqual(self.calls, [["nginx", "-t"], ["systemctl", "reload", "nginx"],
                                     ["nginx", "-t"], ["systemctl", "reload", "nginx"]])

    def test_existing_conflicting_route_is_not_replaced(self):
        self.before[0] += b"location = /api/hid {\n return 418;\n}\n"
        self.paths[0].write_bytes(self.before[0])
        self.hashes[0] = hashlib.sha256(self.before[0]).hexdigest()
        with self.assertRaisesRegex(SystemExit, "differs"):
            self.run_install()
        self.unchanged()
        self.assertEqual(self.calls, [])

    def test_peer_edit_during_test_is_preserved_without_reload(self):
        peer_bytes = b"# independently changed limits\n"

        def peer(args):
            if args == ["nginx", "-t"]:
                self.paths[1].write_bytes(peer_bytes)

        with self.assertRaisesRegex(RuntimeError, "preserved peer edits"):
            self.run_install(failure=["nginx", "-t"], peer=peer)
        self.assertEqual(self.paths[0].read_bytes(), self.before[0])
        self.assertEqual(self.paths[1].read_bytes(), peer_bytes)
        self.assertEqual(self.calls, [["nginx", "-t"]])

    def test_successful_validation_cannot_reload_peer_edits(self):
        peer_bytes = b"# peer edit during successful validation\n"

        def peer(args):
            if args == ["nginx", "-t"]:
                self.paths[1].write_bytes(peer_bytes)

        with self.assertRaisesRegex(RuntimeError, "preserved peer edits"):
            self.run_install(peer=peer)
        self.assertEqual(self.paths[0].read_bytes(), self.before[0])
        self.assertEqual(self.paths[1].read_bytes(), peer_bytes)
        self.assertEqual(self.calls, [["nginx", "-t"]])
        self.assertFalse((self.backup / "receipt.json").exists())

    def test_reload_peer_edit_cannot_get_a_success_receipt(self):
        peer_bytes = b"# peer edit during reload\n"

        def peer(args):
            if args == ["systemctl", "reload", "nginx"]:
                self.paths[1].write_bytes(peer_bytes)

        with self.assertRaisesRegex(RuntimeError, "preserved peer edits"):
            self.run_install(peer=peer)
        self.assertEqual(self.paths[0].read_bytes(), self.before[0])
        self.assertEqual(self.paths[1].read_bytes(), peer_bytes)
        self.assertEqual(self.calls, [["nginx", "-t"], ["systemctl", "reload", "nginx"]])
        self.assertFalse((self.backup / "receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
