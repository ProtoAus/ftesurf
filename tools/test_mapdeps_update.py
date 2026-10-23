#!/usr/bin/env python3
"""Client-free controls for mapdeps' incremental generated-catalogue update."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mapdeps import update_mapdeps


class UpdateMapdepsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mapdeps-unit-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "mapdeps.txt"
        self.before = (b"FTESURF-MAPDEPS 1\r\n# owner annotation\r\n"
                       b"dep bhop_a steam:Other Game/game\r\n"
                       b"dep bhop_z steam:Yet Another Game/game\r\n")
        self.path.write_bytes(self.before)
        self.sha = hashlib.sha256(self.before).hexdigest()

    def test_add_preserves_unrelated_bytes_and_spaces(self):
        row = b"dep bhop_autumnal steam:Counter-Strike Global Offensive/csgo\n"
        self.assertTrue(update_mapdeps(self.path, "bhop_autumnal",
                                       ["steam:Counter-Strike Global Offensive/csgo"], self.sha))
        self.assertEqual(self.path.read_bytes().replace(row, b""), self.before)
        self.assertLess(self.path.read_bytes().index(row), self.path.read_bytes().index(b"dep bhop_z"))

    def test_replace_duplicate_rows_then_remove_only_target(self):
        oldrow = b"dep bhop_autumnal steam:Wrong/game\n"
        self.path.write_bytes(self.before + oldrow + oldrow)
        self.assertTrue(update_mapdeps(self.path, "bhop_autumnal", ["steam:Right/game"] * 2,
                                       hashlib.sha256(self.path.read_bytes()).hexdigest()))
        after = self.path.read_bytes()
        row = b"dep bhop_autumnal steam:Right/game\n"
        self.assertEqual(after.count(row), 1)
        self.assertEqual(after.replace(row, b""), self.before)
        self.assertTrue(update_mapdeps(self.path, "bhop_autumnal", [], hashlib.sha256(after).hexdigest()))
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_wrong_or_missing_predecessor_refuses_without_mutation(self):
        for sha in [None, "0" * 64]:
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                update_mapdeps(self.path, "bhop_autumnal", ["steam:Right/game"], sha)
            self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_new_catalogue_and_idempotent_existing_update(self):
        self.path.unlink()
        self.assertTrue(update_mapdeps(self.path, "bhop_autumnal", ["steam:Right/game"]))
        after = self.path.read_bytes()
        self.assertEqual(after, b"FTESURF-MAPDEPS 1\ndep bhop_autumnal steam:Right/game\n")
        self.assertFalse(update_mapdeps(self.path, "bhop_autumnal", ["steam:Right/game"],
                                       hashlib.sha256(after).hexdigest()))

    def test_invalid_header_name_and_spec_refuse(self):
        for name, specs in [("../bhop_autumnal", []), ("bhop_autumnal", ["steam:Game/game\ninjected"])]:
            with self.subTest(name=name, specs=specs), self.assertRaises(ValueError):
                update_mapdeps(self.path, name, specs, self.sha)
            self.assertEqual(self.path.read_bytes(), self.before)
        self.path.write_bytes(b"NOT-A-CATALOGUE\n")
        with self.assertRaises(ValueError):
            update_mapdeps(self.path, "bhop_autumnal", [], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(self.path.read_bytes(), b"NOT-A-CATALOGUE\n")

    def test_failed_replace_preserves_old_catalogue_and_cleans_own_temp(self):
        with patch("mapdeps.os.replace", side_effect=OSError("held destination")) as replace:
            with self.assertRaises(OSError):
                update_mapdeps(self.path, "bhop_autumnal", ["steam:Right/game"], self.sha)
            replace.assert_called_once()
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main()
