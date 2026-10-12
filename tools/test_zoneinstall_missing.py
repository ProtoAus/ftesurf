#!/usr/bin/env python3
"""Missing-only zone import controls; no installed maps or zones are modified."""
import contextlib
import io
import ntpath
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import zoneinstall as subject


class MissingZones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zoneinstall-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / "game"
        self.dest = self.game / "maps/zones/local"
        self.dest.mkdir(parents=True)
        self.source = self.root / "source.json"
        self.source.write_bytes(b'{"tracks": {"main": {}}}\n')
        self.existing = self.dest / "surf_owned.json"
        self.existing.write_bytes(b'owner edit\n')
        self.manifest = self.dest.parent / "manifest.txt"
        self.manifest.write_text("surf_owned mirror self unchanged-hash -\n")
        self.mirrors = [("surf_owned", str(self.source), "self"),
                        ("surf_new", str(self.source), "self")]
        self.donations = [("surf_variant", str(self.source), "surf_new", "FIT", "fits")]

    def run_tool(self, *args, plan=None):
        argv = ["zoneinstall.py", "--gamedir", str(self.game), *args]
        capture = io.StringIO()
        with patch.object(sys, "argv", argv), \
             patch.object(subject, "MOMMAPS", str(self.root)), \
             patch.object(subject, "plan", plan or (lambda _: (self.mirrors, self.donations, []))), \
             patch.object(subject, "DEST", subject.DEST), \
             patch.object(subject, "MANIFEST", subject.MANIFEST), \
             patch.object(subject.zonefit, "GAMEMAPS", subject.zonefit.GAMEMAPS), \
             contextlib.redirect_stdout(capture):
            rc = subject.main()
        return rc, capture.getvalue()

    def test_dry_run_and_missing_only(self):
        original = self.manifest.read_bytes()
        rc, log = self.run_tool("--only-missing")
        self.assertEqual(rc, 0)
        self.assertIn("write 2 file(s)", log)
        self.assertFalse((self.dest / "surf_new.json").exists())
        self.assertEqual(self.manifest.read_bytes(), original)
        rc, log = self.run_tool("--only-missing", "--go")
        self.assertEqual(rc, 0)
        self.assertIn("wrote 2", log)  # acted: both a mirror and verified donation landed
        self.assertEqual((self.dest / "surf_new.json").read_bytes(), self.source.read_bytes())
        self.assertEqual((self.dest / "surf_variant.json").read_bytes(), self.source.read_bytes())
        self.assertEqual(self.existing.read_bytes(), b"owner edit\n")
        self.assertIn("surf_owned mirror self unchanged-hash -", self.manifest.read_text())
        self.assertIn("surf_variant donation surf_new", self.manifest.read_text())
        after = self.manifest.read_bytes()
        rc, log = self.run_tool("--only-missing", "--go")
        self.assertEqual(rc, 0)
        self.assertIn("wrote 0", log)
        self.assertEqual(self.manifest.read_bytes(), after)

    def test_cross_drive_diagnostics(self):
        target = "D:/zones/maps/zones/local"
        with patch.object(subject, "ROOT", "C:/checkout"), \
             patch.object(subject.os.path, "relpath", ntpath.relpath), \
             patch.object(subject.os.path, "abspath", ntpath.abspath):
            self.assertEqual(subject.display_path(target), ntpath.abspath(target))
            self.assertEqual(subject.display_path("C:/checkout/maps"), "maps")

    def test_force_is_incompatible(self):
        before = self.manifest.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            self.run_tool("--only-missing", "--force", "--go")
        self.assertEqual(exc.exception.code, 2)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_file_appears_after_plan(self):
        # The file becomes owned after filtering the plan but before the final
        # copy. Exclusive creation must keep it, not truncate it.
        target = self.dest / "surf_new.json"
        real_open = open

        def raced_open(path, mode="r", *args, **kwargs):
            if os.fspath(path) == str(target) and mode == "xb":
                target.write_bytes(b"arrived during import\n")
            return real_open(path, mode, *args, **kwargs)

        with patch("builtins.open", raced_open):
            rc, log = self.run_tool("--only-missing", "--go")
        self.assertEqual(rc, 0)
        self.assertIn("keeping existing surf_new.json", log)
        self.assertEqual(target.read_bytes(), b"arrived during import\n")
        self.assertNotIn("surf_new mirror", self.manifest.read_text())
        self.assertTrue((self.dest / "surf_variant.json").exists())


if __name__ == "__main__":
    unittest.main()
