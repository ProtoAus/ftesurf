#!/usr/bin/env python3
"""Offline presentation candidate contracts, not layout/runtime acceptance.

Run in a Git checkout. --source-ref grades the real pre-rebrand source control.
Comparison admits only explicit display edits; signed/wire/data/path strings and
QC code tokens must remain the frozen compatibility baseline. No game starts.
"""
import argparse
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = "e27f2c88af25cd0d6ba6827b883d35cb8d1b01bb"
SOURCE_REF = None
LEX = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"')
QC = (
    "menu/m_board.qc", "menu/m_lobby.qc", "menu/m_main.qc",
    "menu/m_milk.qc", "menu/m_update.qc", "client/cl_hud.qc",
    "client/cl_profile.qc", "client/cl_scores.qc",
    "client/cl_scores_native.qc", "server/sv_account.qc", "server/sv_lobby.qc",
    "server/sv_main.qc", "server/sv_player.qc", "shared/sh_font.qc",
)
NEW_PREFIX_BRANCH = '''	pl = strlen(LB_NAME_PREFIX_WOS);
	if (n > pl)
		if (!strcmp(strtolower(substring(s, 0, pl)), LB_NAME_PREFIX_WOS))
			return substring(s, pl, n - pl);

'''


def source(path, ref=None):
    if ref:
        return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT).decode("utf-8")
    return (ROOT / path).read_text(encoding="utf-8")


def code(text):
    # Remove comments without treating // inside a URL/string as a comment.
    text = LEX.sub(lambda m: m[0] if m[0].startswith('"') else " ", text)
    return re.findall(r'"(?:\\.|[^"\\])*"|[^\s]', text)


def expected_qc(path):
    text = source("src/" + path, BASE)
    if path == "menu/m_lobby.qc":
        text = text.replace('#define LB_NAME_PREFIX "ftesurf -- "',
                            '#define LB_NAME_PREFIX "ftesurf -- "\n#define LB_NAME_PREFIX_WOS "world of surf -- "')
        text = text.replace('\tpl = strlen(LB_NAME_PREFIX);', NEW_PREFIX_BRANCH + '\tpl = strlen(LB_NAME_PREFIX);')
        return text.replace('strtolower(substring(s, 0, pl)) == LB_NAME_PREFIX',
                            '!strcmp(strtolower(substring(s, 0, pl)), LB_NAME_PREFIX)')
    if path == "menu/m_milk.qc":
        text = text.replace("#define MM_TITLE_SZ '80 80 0'", "#define MM_TITLE_SZ '48 48 0'\n#define MM_TITLE \"WORLD OF SURF\"")
        return text.replace('"FTESURF"', 'MM_TITLE')

    def display(m):
        value = m[0]
        if not value.startswith('"'):
            return value
        if path in ("client/cl_scores.qc", "client/cl_scores_native.qc"):
            return value.replace("FTESurf", "WOS")
        if path == "client/cl_profile.qc":
            return value.replace('"FTE"', '"WOS"')
        if path == "menu/m_board.qc" and value == '"FTESurf"':
            return '"WOS"'
        if path == "server/sv_account.qc":
            return value.replace("An FTESurf from before ", "An install from before ")
        value = value.replace("an FTESurf lobby", "a World of Surf lobby")
        if path == "menu/m_main.qc":
            value = value.replace("^2FTESurf: menu.dat", "^2World of Surf: menu.dat")
        return value.replace("FTESurf:", "WOS:").replace("FTESurf", "World of Surf")
    return LEX.sub(display, text)


class ProductBrandTests(unittest.TestCase):
    def test_manifest_display_only(self):
        before = source("default.fmf", BASE)
        self.assertIn('NAME "FTESurf"', before)
        self.assertEqual(source("default.fmf", SOURCE_REF), before.replace('NAME "FTESurf"', 'NAME "World of Surf"'))
        # GAME, BASEGAME, downloads and icon/gamedir legacy identity are unchanged.

    def test_qc_copy_and_code_contract(self):
        for path in QC:
            with self.subTest(path=path):
                self.assertEqual(code(source("src/" + path, SOURCE_REF)), code(expected_qc(path)))

    def test_lobby_hostnames_only(self):
        for n in range(13):
            path = "ftesurf/cfg/lobby/lobby" + (str(n) if n else "") + ".cfg"
            before = source(path, BASE)
            expected = before.replace("FTESurf -- ", "World of Surf -- ") if n else before.replace('"FTESurf lobby (patch 270)"', '"World of Surf lobby"')
            with self.subTest(path=path):
                self.assertEqual(source(path, SOURCE_REF), expected)

    def test_machine_mutants_rejected(self):
        for path, old, new in (
            ("menu/m_main.qc", "FTESURF-CONSENT", "WOS-CONSENT"),
            ("menu/m_board.qc", 's == "ftesurf"', 's == "wos"'),
            ("client/cl_scores.qc", 'argv(2) == "ftesurf"', 'argv(2) == "wos"'),
            ("menu/m_lobby.qc", "FTESURF-MAPDL", "WOS-MAPDL"),
        ):
            expected = expected_qc(path)
            with self.subTest(path=path):
                self.assertIn(old, expected)
                self.assertNotEqual(code(expected.replace(old, new)), code(expected))

    def test_shared_title_all_draw_passes(self):
        text = source("src/menu/m_milk.qc", SOURCE_REF)
        self.assertIn('#define MM_TITLE "WORLD OF SURF"', text)
        self.assertEqual(len(re.findall(r'\bMM_TITLE\b', text)), 4)
        self.assertIn('#define MM_TITLE_SZ \'48 48 0\'', text)
        self.assertIn('"24 32 40 48 64 80"', source("src/shared/sh_font.qc", SOURCE_REF))
        # A supported native font rung, not a claim about rendered clipping.

    def test_no_unplanned_qc_edits(self):
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "src"], cwd=ROOT).decode().splitlines()
        for path in paths:
            if path.endswith(".qc") and path not in {"src/" + p for p in QC}:
                with self.subTest(path=path):
                    self.assertEqual(source(path, SOURCE_REF), source(path, BASE))
        # The CSQC boot line is a machine-consumed acting-control marker, not
        # a free-form display label. Preserve its producer and existing readers.
        self.assertIn('print("FTESurf CSQC loaded\\n");', source("src/client/cl_main.qc", SOURCE_REF))
        for path in ("src/sv_progs.src", "src/cl_progs.src", "src/m_progs.src", "src/client/cl_account.qc"):
            with self.subTest(path=path):
                self.assertEqual(source(path, SOURCE_REF), source(path, BASE))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ref", help="grade this Git ref instead of disk")
    args, rest = parser.parse_known_args()
    SOURCE_REF = args.source_ref
    unittest.main(argv=["test_product_brand", *rest])
