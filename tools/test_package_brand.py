#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline package copy invariants; --source-ref grades an acting old-source control.

The explicit prose edits reconstruct the frozen baseline exactly; no arbitrary
string masking can hide a changed path, feed identity, allowlist or code branch.
No fixtures, network, credentials, release or player installation are used.
"""
import argparse
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = "e27f2c88af25cd0d6ba6827b883d35cb8d1b01bb"
SOURCE_REF = None

COPY_EDITS = {'README.md': [('# FTESurf\n', '# World of Surf\n'),
               ('**Steam games, mounted — never redistributed.** FTESurf reads',
                '**Steam games, mounted — never redistributed.** World of Surf reads'),
               ('FTESurf is not separable', 'World of Surf is not separable'),
               ('FTESurf is a mod for it', 'World of Surf is a mod for it'),
               ('**FTESurf contains no Valve', '**World of Surf contains no Valve')],
 'surfd/README.md': [('# surfd - FTESurf lobby directory',
                      '# surfd - World of Surf lobby directory')],
 'src/release/release.ps1': [('FTESurf $Ver\n', 'World of Surf $Ver\n'),
                             ('FTESurf $Ver -- install', 'World of Surf $Ver -- install'),
                             ('FTESurf $Ver -- source', 'World of Surf $Ver -- source'),
                             ('FTESurf $Ver -- third-party software',
                              'World of Surf $Ver -- third-party software'),
                             ('FTESurf $Ver for Linux x86_64 (beta)',
                              'World of Surf $Ver for Linux x86_64 (beta)'),
                             ('FTESurf $Ver for Linux (beta) -- install',
                              'World of Surf $Ver for Linux (beta) -- install'),
                             ('FTESurf ships NO Valve', 'World of Surf ships NO Valve'),
                             ('FTESurf contains no Valve or Momentum Mod code',
                              'World of Surf contains no Valve or Momentum Mod code'),
                             ('It is part of the FTESurf\nengine fork',
                              'It is part of the World of Surf\nengine fork'),
                             ('FTESurf only reads its maps', 'World of Surf only reads its maps'),
                             ('=== FTESurf $Ver released ===',
                              '=== World of Surf $Ver released ===')],
 'ftesurf.sh': [('say "FTESurf cannot write', 'say "World of Surf cannot write'),
                ('say "FTESurf stopped', 'say "World of Surf stopped')]}

UNCHANGED = (
    "src/release/bootstrap.ps1", "src/release/linux-bootstrap.sh",
    "src/release/linux-pack.sh", "ftesurf.bat", "ftesurf_debug.bat",
)


def read_source(path, ref=None):
    if ref:
        data = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)
        return data.decode("utf-8").replace(chr(13) + chr(10), chr(10))
    return (ROOT / path).read_text(encoding="utf-8")


def expected_copy(path):
    text = read_source(path, BASE)
    for old, new in COPY_EDITS[path]:
        if old not in text:
            raise ValueError(f"baseline prose missing in {path}: {old!r}")
        text = text.replace(old, new)
    return text


def machine_contract_matches(path, text):
    for old, new in reversed(COPY_EDITS[path]):
        text = text.replace(new, old)
    return text == read_source(path, BASE)


class PackageBrandTests(unittest.TestCase):
    def test_authored_package_copy(self):
        for path in COPY_EDITS:
            with self.subTest(path=path):
                self.assertEqual(read_source(path, SOURCE_REF), expected_copy(path))

    def test_unedited_bootstrap_and_entrypoints(self):
        for path in UNCHANGED:
            with self.subTest(path=path):
                self.assertEqual(read_source(path, SOURCE_REF), read_source(path, BASE))

    def test_only_explicit_prose_differs_from_base(self):
        for path in COPY_EDITS:
            with self.subTest(path=path):
                self.assertTrue(machine_contract_matches(path, read_source(path, SOURCE_REF)))

    def test_machine_contract_mutants_are_detected(self):
        text = expected_copy("src/release/release.ps1")
        for old, new in (("$LinuxTop  = 'FTESurf'", "$LinuxTop  = 'WorldofSurf'"),
                         ('"ftesurf-$Ver.7z"', '"worldofsurf-$Ver.7z"'),
                         ("https://proto.bar/ftesurf", "https://proto.bar/worldofsurf"),
                         ("'ftesurf64.exe'", "'worldofsurf64.exe'")):
            with self.subTest(token=old):
                self.assertIn(old, text)
                mutant = text.replace(old, new)
                self.assertNotEqual(mutant, text)
                self.assertFalse(machine_contract_matches("src/release/release.ps1", mutant))

    def test_legacy_history_paths_and_attribution(self):
        text = read_source("src/release/release.ps1", SOURCE_REF)
        for token in ("Upgrading from 0.1.9 or earlier", "This makes a folder called FTESurf",
                      "Discord, in the FTESurf channel", "Stock FTEQW", "GPLv2 or later",
                      "https://github.com/ProtoAus/ftesurf", "FTESURF_UPDATE_SEED_FILE"):
            with self.subTest(token=token):
                self.assertIn(token, text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ref", help="read candidate files from this Git ref instead of disk")
    args, rest = parser.parse_known_args()
    SOURCE_REF = args.source_ref
    unittest.main(argv=["test_package_brand", *rest])
