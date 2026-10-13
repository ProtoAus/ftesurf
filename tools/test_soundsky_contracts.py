#!/usr/bin/env python3
"""Static lifecycle/sampler regressions; not a substitute for runtime pixels/audio."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def check(audio, sky, material):
    body = audio.split('void() Milk_Audio =', 1)[1].split('void(', 1)[0]
    assert body.count('snd_visimage(MILK_SPEC, MILK_SPECBANDS);') == 1
    upload = body.index('snd_visimage(MILK_SPEC, MILK_SPECBANDS);')
    availability = body.index('snd_getvis(milk_vis, 16) >= 14')
    assert upload < availability, 'unavailable source must upload blank native image too'
    assert re.search(r'if \(milk_hasvis\)\s+snd_visimage', body)
    frame = sky.split('void() MilkSky_Frame =', 1)[1]
    assert re.search(r'if \(strcmp\(serverkey\("map"\), ms_thumb_map\)\)\s*\{\s*MilkSky_Thumbnail\(\);', frame)
    assert 'ms_thumb_map = want;' in sky and 'want = strzone(serverkey("map"));' in sky
    assert 'ms_thumb_map = "";' in sky
    metadata = sky.split('void(float now) MilkSky_Metadata =', 1)[1].split('void()', 1)[0]
    assert 'if (now < ms_thumb_next) return;' in metadata and 'MilkSky_Thumbnail();' in metadata
    assert '#define MILK_META_ROWS 64' in sky
    assert 'i < MILK_META_ROWS' in metadata, 'metadata must not scan the whole file per frame'
    assert 'MilkSky_Index(argv(6))' in metadata and 'MilkSky_Index(argv(7))' in metadata
    assert 'if not (ln)' in metadata, 'blank lines must not be treated as null EOF'
    opened = sky.split('void() MilkSky_Thumbnail =', 1)[1].split('void(float page', 1)[0]
    failed = opened.split('if (ms_thumb_file < 0)', 1)[1]
    assert 'ms_thumb_page = ms_thumb_cell = -1;' in failed and 'ms_palette_next = 0;' in failed
    assert 'MilkSky_ThumbnailClose();' in frame.split('now = gettime(0);', 1)[0]
    material = re.sub(r'//[^\n]*', '', material)
    assert re.search(r'surfaceparm sky\s*\{\s*program milk_sky[^{}]*map \$rt:ms_out\s*map \$rt:ms_palette', material), 'program must precede both maps INSIDE the pass'


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = (ROOT / 'src/milk_sys.qc').read_text(encoding='utf-8')
        cls.sky = (ROOT / 'src/client/cl_milk.qc').read_text(encoding='utf-8')
        cls.material = (ROOT / 'ftesurf/scripts/milk.shader').read_text(encoding='utf-8')

    def test_production(self):
        check(self.audio, self.sky, self.material)

    def test_missing_blank_upload_mutant(self):
        mutant = self.audio.replace('snd_visimage(MILK_SPEC, MILK_SPECBANDS);', '', 1)
        self.assertNotEqual(mutant, self.audio)
        with self.assertRaises(AssertionError):
            check(mutant, self.sky, self.material)

    def test_initial_only_thumbnail_mutant(self):
        mutant = self.sky.replace('if (strcmp(serverkey("map"), ms_thumb_map))', 'if (FALSE)', 1)
        self.assertNotEqual(mutant, self.sky)
        with self.assertRaises(AssertionError):
            check(self.audio, mutant, self.material)

    def test_no_retry_mutant(self):
        mutant = self.sky.replace('if (now < ms_thumb_next) return;', 'return;', 1)
        self.assertNotEqual(mutant, self.sky)
        with self.assertRaises(AssertionError):
            check(self.audio, mutant, self.material)

    def test_unbounded_scan_mutant(self):
        mutant = self.sky.replace('i < MILK_META_ROWS', 'i < 1000000', 1)
        self.assertNotEqual(mutant, self.sky)
        with self.assertRaises(AssertionError):
            check(self.audio, mutant, self.material)

    def test_blank_is_eof_mutant(self):
        mutant = self.sky.replace('if not (ln)', 'if (!ln)', 1)
        self.assertNotEqual(mutant, self.sky)
        with self.assertRaises(AssertionError):
            check(self.audio, mutant, self.material)

    def test_failed_open_keeps_stale_mutant(self):
        stale = 'if (ms_thumb_file < 0)\n\t{\n\t\tms_thumb_page = ms_thumb_cell = -1;'
        mutant = self.sky.replace(stale, 'if (ms_thumb_file < 0)\n\t{', 1)
        self.assertNotEqual(mutant, self.sky)
        with self.assertRaises(AssertionError):
            check(self.audio, mutant, self.material)

    def test_shader_level_program_mutant(self):
        mutant = self.material.replace('surfaceparm sky\n\t{\n\t\tprogram milk_sky', 'surfaceparm sky\n\tprogram milk_sky\n\t{', 1)
        self.assertNotEqual(mutant, self.material)
        with self.assertRaises(AssertionError):
            check(self.audio, self.sky, mutant)


if __name__ == '__main__':
    unittest.main()
