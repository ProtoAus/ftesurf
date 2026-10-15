#!/usr/bin/env python3
"""Offline installer refusal/rollback controls; no root or live config access."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = None
spec = importlib.util.spec_from_file_location("r2install", Path(__file__).with_name("r2gateway-install.py"))
i = importlib.util.module_from_spec(spec)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / self._testMethodName
        self.root.mkdir()
        self.runtime = self.root / "r2gateway-test"
        self.runtime.mkdir()
        self.snippet = self.root / "ftesurf-maps.conf"
        self.snippet.write_bytes(b"old nginx\n")
        self.unit = self.root / "unit.service"
        self.bundle = {"runtime": str(self.runtime), "nginx_before_sha256": i.sha(self.snippet), "files": {}, "port": 19000, "probe_path": "/ftesurf/maps/probe.bsp"}
        for n in i.FILES:
            p = self.runtime / n
            p.write_bytes(("synthetic " + n + "\n").encode())
            self.bundle["files"][n] = i.sha(p)
        self.save()
        self.patches = [mock.patch.object(i, "RUNTIME_PARENT", self.root), mock.patch.object(i, "SNIPPET", self.snippet), mock.patch.object(i, "UNIT", self.unit), mock.patch.object(i, "LOCK", self.root / "lock"), mock.patch.object(i, "probe", return_value=True)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.commands = []

    def save(self):
        (self.runtime / "bundle.json").write_text(json.dumps(self.bundle))

    def command(self, *argv):
        self.commands.append(argv)

    def test_positive_installs_and_preserves_backup(self):
        with mock.patch.object(i, "run", side_effect=self.command):
            b, r = i.checked(self.runtime / "bundle.json")
            i.apply(b, r)
        self.assertEqual(self.snippet.read_bytes(), (self.runtime / "ftesurf-maps.conf").read_bytes())
        self.assertEqual(list(self.root.glob("ftesurf-maps.conf.pre-r2-*"))[0].read_bytes(), b"old nginx\n")
        self.assertIn(("/usr/bin/systemctl", "reload", "nginx"), self.commands)
        self.assertIn(("/usr/bin/systemctl", "enable", i.SERVICE), self.commands)

    def test_changed_predecessor_refuses(self):
        self.snippet.write_bytes(b"peer nginx\n")
        with self.assertRaises(ValueError):
            i.checked(self.runtime / "bundle.json")
        self.assertFalse(self.unit.exists())

    def test_existing_unit_refuses(self):
        self.unit.write_bytes(b"peer service")
        with self.assertRaises(ValueError):
            i.checked(self.runtime / "bundle.json")
        self.assertEqual(self.unit.read_bytes(), b"peer service")

    def test_bundle_tamper_refuses(self):
        (self.runtime / "r2gateway.py").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            i.checked(self.runtime / "bundle.json")
        self.assertEqual(self.snippet.read_bytes(), b"old nginx\n")

    def test_start_failure_leaves_original_and_stops_own_service(self):
        def run(*argv):
            self.command(*argv)
            if argv[1:2] == ("start",):
                raise RuntimeError("synthetic start failure")
        with mock.patch.object(i, "run", side_effect=run):
            with self.assertRaises(RuntimeError):
                i.apply(self.bundle, self.runtime)
        self.assertEqual(self.snippet.read_bytes(), b"old nginx\n")
        self.assertIn(("/usr/bin/systemctl", "disable", "--now", i.SERVICE), self.commands)
        self.assertNotIn(("/usr/bin/systemctl", "reload", "nginx"), self.commands)

    def test_new_nginx_syntax_failure_restores_original(self):
        def run(*argv):
            self.command(*argv)
            if argv[0].endswith("nginx") and self.snippet.read_bytes() != b"old nginx\n":
                raise RuntimeError("synthetic bad nginx")
        with mock.patch.object(i, "run", side_effect=run):
            with self.assertRaises(RuntimeError):
                i.apply(self.bundle, self.runtime)
        self.assertEqual(self.snippet.read_bytes(), b"old nginx\n")
        self.assertIn(("/usr/bin/systemctl", "reload", "nginx"), self.commands)
        self.assertIn(("/usr/bin/systemctl", "disable", "--now", i.SERVICE), self.commands)

    def test_reload_failure_restores_original(self):
        failed = False
        def run(*argv):
            nonlocal failed
            self.command(*argv)
            if argv[1:3] == ("reload", "nginx") and not failed:
                failed = True
                raise RuntimeError("synthetic reload failure")
        with mock.patch.object(i, "run", side_effect=run):
            with self.assertRaises(RuntimeError):
                i.apply(self.bundle, self.runtime)
        self.assertTrue(failed)
        self.assertEqual(self.snippet.read_bytes(), b"old nginx\n")
        self.assertEqual(self.commands.count(("/usr/bin/systemctl", "reload", "nginx")), 2)

    def test_peer_edit_during_reload_not_overwritten(self):
        def run(*argv):
            self.command(*argv)
            if argv[1:3] == ("reload", "nginx"):
                self.snippet.write_bytes(b"peer changed while installing")
                raise RuntimeError("synthetic concurrent replacement")
        with mock.patch.object(i, "run", side_effect=run):
            with self.assertRaisesRegex(RuntimeError, "Concurrent nginx replacement"):
                i.apply(self.bundle, self.runtime)
        self.assertEqual(self.snippet.read_bytes(), b"peer changed while installing")

    def test_peer_edit_before_swap_not_overwritten(self):
        def run(*argv):
            self.command(*argv)
            if argv[1:2] == ("start",):
                self.snippet.write_bytes(b"peer edit before swap")
        with mock.patch.object(i, "run", side_effect=run):
            with self.assertRaisesRegex(RuntimeError, "predecessor changed"):
                i.apply(self.bundle, self.runtime)
        self.assertEqual(self.snippet.read_bytes(), b"peer edit before swap")

    def test_backup_collision_refuses_without_mutation(self):
        with mock.patch.object(i.time, "strftime", return_value="synthetic"):
            backup = self.root / "ftesurf-maps.conf.pre-r2-synthetic"
            backup.write_bytes(b"preexisting recovery")
            with mock.patch.object(i, "run", side_effect=self.command):
                with self.assertRaises(FileExistsError):
                    i.apply(self.bundle, self.runtime)
        self.assertEqual(backup.read_bytes(), b"preexisting recovery")
        self.assertFalse(self.unit.exists())


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    ROOT = a.out.absolute()
    if sys.platform != "linux" or not any((d / "OWNER.md").is_file() for d in ROOT.parents):
        p.error("Linux and owned --out ancestor required")
    ROOT.mkdir()
    spec.loader.exec_module(i)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstallTests))
    (ROOT / "result.json").write_text(json.dumps({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)}) + "\n")
    return not result.wasSuccessful()


if __name__ == "__main__":
    raise SystemExit(main())
