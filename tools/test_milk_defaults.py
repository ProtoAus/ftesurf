#!/usr/bin/env python3
"""Check shipped visualizer defaults and optionally the isolated runtime control log.

python tools/test_milk_defaults.py [<runlines_smoke.log>]
The runtime cfg is cfg/test/milk_defaults.cfg. Music choice is intentionally not
copied from a user's profile; saved visual preferences must survive menu_restart.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED = {
    'milk_menu': '1', 'milk_quality': '4', 'milk_trails': '1', 'milk_react': '1',
    'milk_sky': '0', 'milk_lowpass': '1', 'milk_world': 'lattice',
    'milk_panels': '0', 'milk_sfx': '1', 'milk_grade': '0', 'milk_streaks': '2',
    'milk_res': '1', 'milk_fsr': '0', 'milk_checker': '0', 'milk_cone': '0',
    'milk_sky_parallax': '1', 'milk_sky_palette': '1',
}
OLD = {'milk_quality': '2', 'milk_world': 'monolith', 'milk_panels': '1',
       'milk_grade': '1', 'milk_streaks': '1', 'milk_res': '0'}


def runtime(text):
    text = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', text, flags=re.M)
    sections = re.split(r'^MILK DEFAULTS (boot|old|preserved|restored)\s*$', text, flags=re.M)
    found = {}
    for i in range(1, len(sections) - 1, 2):
        found[sections[i]] = dict(re.findall(r'^"(milk_\w+)" is "([^"]*)"', sections[i + 1], re.M))
    for section, expected in [('boot', EXPECTED), ('old', OLD), ('preserved', OLD), ('restored', EXPECTED)]:
        values = found.get(section, {})
        bad = {n: values.get(n) for n, v in expected.items() if values.get(n) != v}
        if bad:
            raise AssertionError(f'{section}: missing/wrong values {bad}')
    assert 'RUNLINES COMPLETE' in text, 'runtime did not finish'
    assert not any(x in text for x in ('Unknown command', 'QC VM error', 'Cannot call', 'stack overflow'))
    return len(EXPECTED) * 2 + len(OLD) * 2


def main():
    qc = (ROOT / 'src/menu/m_milk.qc').read_text(encoding='utf-8')
    cfg = (ROOT / 'ftesurf/cfg/default.cfg').read_text(encoding='utf-8')
    registrations = dict(re.findall(r'registercvar\("(milk_\w+)",\s*"([^"]*)"', qc))
    values = dict(re.findall(r'^set\s+(milk_\w+)\s+(\S+)', cfg, re.M))
    for name, value in EXPECTED.items():
        assert registrations.get(name) == value, f'{name}: QC default {registrations.get(name)!r}'
        assert values.get(name) == value, f'{name}: cfg default {values.get(name)!r}'
    for source in (ROOT / 'src').rglob('*.qc'):
        if 'defs' in source.parts:
            continue
        for name, value in re.findall(r'registercvar\("(milk_\w+)",\s*"([^"]*)"', source.read_text(encoding='utf-8')):
            if name in EXPECTED:
                assert value == EXPECTED[name], f'{source}: conflicting {name} default {value!r}'
    assert registrations['milk_menumusic'] == 'auto'
    assert not re.search(r'^seta?\s+(?:milk_menumusic|snd_vis_source)\b', cfg, re.M)
    print(f'PASS: {len(EXPECTED)} visual defaults agree in menu and default.cfg; music auto; capture opt-in')
    if len(sys.argv) > 1:
        text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
        count = runtime(text)
        mutant = text.replace('"milk_quality" is "4"', '"milk_quality" is "2"', 1)
        assert mutant != text, 'mutant did not act'
        try:
            runtime(mutant)
        except AssertionError:
            pass
        else:
            raise AssertionError('wrong-default mutant incorrectly passed')
        print(f'PASS: {count} runtime readbacks; saved overrides preserved; acted wrong-default mutant rejected')


if __name__ == '__main__':
    main()
