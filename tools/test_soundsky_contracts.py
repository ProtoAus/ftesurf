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

    def test_shader_level_program_mutant(self):
        mutant = self.material.replace('surfaceparm sky\n\t{\n\t\tprogram milk_sky', 'surfaceparm sky\n\tprogram milk_sky\n\t{', 1)
        self.assertNotEqual(mutant, self.material)
        with self.assertRaises(AssertionError):
            check(self.audio, self.sky, mutant)


if __name__ == '__main__':
    unittest.main()
