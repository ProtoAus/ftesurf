#!/usr/bin/env python3
"""Native-rendered layout/synthetic-input falsifiers; NOT physical F2 verification.

Use test_update_corner.py for Windows native F2/binding dispatch controls.
Synthetic friends are NOT account authority.

Run with an owned --out, a NoDeploy --qc-artifacts and --library install gamedir.
Reuses the isolated gallery rig; never writes install configs/data or controls the
owner's clients. Two sizes exercise the sidebar and narrow modal drawer.
"""
import argparse
import json
from pathlib import Path
import re
import ui_gallery as gallery

SHOTS = ('main', 'updates', 'large', 'filters', 'filtered', 'collapsed', 'compact',
         'scrolled', 'friends_disconnected', 'friends_connected', 'friends_bottom', 'friends_stale')


def config(a, size, port, http, native):
    def click(name):
        return [f'ui_hover @{name}', 'ui_mouse down', 'waitms 100',
                f'ui_hover @{name}', 'ui_mouse up', 'waitms 300']

    def shot(name):
        return ['ui_hover 2 2', 'waitms 300', f'screenshot {name}', 'waitms 500']

    lines = ['cfg_save_auto 0', 'cl_idlefps 0', 'cl_maxfps 100',
             'vid_conautoscale 1', 'vid_conwidth 0', 'vid_conheight 0',
             'ui_native_scores 0', 'ui_bootcheck 0', 'milk_panels 0', 'milk_enable 0',
             'update_consent 0', 'lobby_dir ""', 'ui_maps_filters 0',
             'ui_maps_large 1', 'ui_maps_friends 0', 'ui_maps_modes 127',
             f'ui_mapdl_url "http://127.0.0.1:{http}/maps"',
             'name MenuFixture', 'log_dir logs', 'log_name gallery', 'log_enable 1',
             'waitms 1200', 'menu_restart', 'waitms 2000', 'ui_updates', 'ui_key escape', 'waitms 300']
    lines += shot('main')
    lines += ['bind F2', 'ui_key f2', 'waitms 300', 'ui_update_probe'] + shot('updates')
    lines += ['ui_key escape', 'waitms 300'] + click('mm_play') + ['waitms 900']
    lines += ['echo MENU_LARGE', 'ui_menu_probe'] + shot('large')
    lines += click('cs_filters') + ['echo MENU_FILTERS', 'ui_menu_probe'] + shot('filters')
    lines += click('cs_tier3') + ['echo MENU_FILTERED', 'ui_menu_probe'] + shot('filtered')
    lines += click('cs_filters') + ['echo MENU_COLLAPSED', 'ui_menu_probe'] + shot('collapsed')
    lines += click('cs_size') + ['echo MENU_COMPACT', 'ui_menu_probe'] + shot('compact')
    lines += ['ui_hover @cs_list'] + ['ui_key mwheeldown', 'waitms 100'] * 12
    lines += ['echo MENU_SCROLLED', 'ui_menu_probe'] + shot('scrolled')
    lines += click('cs_friends') + shot('friends_disconnected')
    lines += ['ui_key escape', 'ui_close', f'connect 127.0.0.1:{port}', 'waitms 6500',
              'friend_begin']
    for i in range(128):
        # Pending rows intentionally carry dummy location: UI must not show it.
        rel = 1 if i == 1 else 3
        online = 1 if i != 2 else 0
        lines += [f'friend_row {i+1:08x} {rel} {online} Friend%20{i+1:03d} Lobby%20One surf_fixture']
    lines += ['friend_end', 'friends_status', 'ui_updates', 'waitms 200', 'ui_key escape', 'waitms 200']
    lines += click('mm_play') + click('cs_friends')
    lines += ['echo MENU_FRIENDS', 'ui_menu_probe'] + shot('friends_connected')
    lines += click('mf_join00000001')
    # Pending/offline IDs cannot arm another join, even via the console adapter.
    lines += ['friends_menu_join 00000002', 'friends_menu_join 00000003']
    lines += ['ui_hover @mf_list'] + ['ui_key mwheeldown', 'waitms 30'] * 160
    lines += shot('friends_bottom')
    lines += ['friend_begin', 'friend_row 00000001 3 1 Partial Other Hidden',
              'echo MENU_PARTIAL', 'ui_menu_probe', 'waitms 17000',
              'echo MENU_STALE', 'ui_menu_probe'] + shot('friends_stale')
    lines += ['friend_clear', 'waitms 300', 'echo MENU_CLEARED', 'ui_menu_probe',
              'disconnect', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def grade(rig):
    errors = gallery.grade(rig)
    report = json.loads((rig / 'report.json').read_text())
    for arm in report['arms']:
        logs = list((rig / arm / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')
        states = {}
        for name, data in re.findall(r'MENU_(LARGE|FILTERS|FILTERED|COLLAPSED|COMPACT|SCROLLED)[\s\S]*?ui_menu_probe: ([^\r\n]+)', text):
            states[name] = {k: float(v) for k, v in re.findall(r'(\w+)=(-?[\d.]+)', data)}
        checks = {
            'QC F2 handler opens updater': bool(re.search(r'ui_update_probe: .*screen=7', text)),
            'F2 binding text exists (not dispatch proof)': 'ui_updates' in text and '"F2"' in text,
            'all layout actors': len(states) == 6,
            '128 completed friends': 'friends: ready 1 rows 128 loading 0' in text,
            'menu sees connected snapshot': bool(re.search(r'ui_menu_probe: friends_count=128 client=2 screen=1', text)),
            'one authorised join path': text.count('Friends: asking lobby to join friend') == 1,
            'partial snapshot not published': bool(re.search(r'MENU_PARTIAL[\s\S]*?friends_count=128', text)),
            'stale is unavailable, not offline': bool(re.search(r'MENU_STALE[\s\S]*?friends_draw=-1', text)),
            'clear invalidates snapshot': bool(re.search(r'MENU_CLEARED[\s\S]*?friends_count=-1', text)),
        }
        if len(states) == 6:
            checks.update({
                'large default': states['LARGE']['large'] == 1 and states['LARGE']['rows'] > 0,
                'filters expand': states['FILTERS']['filters'] == 1,
                'collapse gains height': states['COLLAPSED']['rows'] > states['FILTERED']['rows'],
                'collapse preserves tier/results': states['COLLAPSED']['tier'] == 3 and
                    states['FILTERED']['maps'] == states['COLLAPSED']['maps'] > 0,
                'compact gains rows': states['COMPACT']['rows'] > states['COLLAPSED']['rows'],
                'map wheel acts': states['SCROLLED']['scroll'] > 0,
            })
        for name, passed in checks.items():
            if not passed:
                errors.append(f'{arm}: {name}')
        # Pixel controls supplement runtime state: a no-op toggle cannot pass.
        from PIL import Image, ImageChops
        shots = rig / arm / 'ftesurf/screenshots'
        for left, right in [('large', 'filters'), ('filtered', 'collapsed'),
                            ('collapsed', 'compact'), ('friends_connected', 'friends_bottom')]:
            a = next(shots.glob(left + '.*'), None)
            b = next(shots.glob(right + '.*'), None)
            if a and b and not ImageChops.difference(Image.open(a).convert('RGB'), Image.open(b).convert('RGB')).getbbox():
                errors.append(f'{arm}: pixels did not change {left}/{right}')
    (rig / 'verdict.json').write_text(json.dumps({'passed': not errors, 'errors': errors}, indent=2) + '\n')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True)
    p.add_argument('--qc-artifacts', type=Path, required=True)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.sizes = [(1280, 720), (800, 600)]
    a.hud_scale, a.renderer, a.timeout = 1, 'gl', 150
    a.plugins = Path('nonexistent-no-optional-plugin')
    gallery.SHOTS, gallery.SHOTS_1080 = SHOTS, ()
    gallery.config = config
    rig = gallery.run(a)
    errors = grade(rig)
    print('Menu refresh rig:', rig)
    print('Failures:', json.dumps(errors))
    raise SystemExit(bool(errors))
