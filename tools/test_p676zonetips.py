#!/usr/bin/env python3
"""Generate/grade zone-editor hover controls in an owned runlines_smoke overlay.

Generate: python tools/test_p676zonetips.py --write-cfg ftesurf/cfg/test/p676zonetips.cfg
Fixture markers/screenshots retain development P675 labels; allocation moved to
P676 when another session published the native P675. No control changed.
Run with tools/runlines_smoke.py, then grade its retained log. --control-log
proves the same pre-patch controls were reached without zone tooltips.
Synthetic hovers do not prove physical device delivery.
"""
import argparse
import re
from pathlib import Path

MAIN = ('ze_t0', 'ze_t1', 'ze_as', 'ze_ag', 'ze_ac', 'ze_ae', 'ze_z0',
        'ze_rp', 'ze_sp', 'ze_resetspawn', 'ze_dl', 'ze_shape', 'ze_edges',
        'ze_xyz', 'ze_g1', 'ze_g8', 'ze_g16', 'ze_g32', 'ze_g64', 'ze_gs',
        'ze_sv', 'ze_rl', 'ze_fg', 'ze_settings', 'ze_look', 'ze_cl')
PROPS = ('ze_mode_surf', 'ze_mode_bhop', 'ze_ms0', 'ze_ms1', 'ze_ms2',
         'ze_msapply', 'ze_mssave', 'ze_msback')
LABELS = ('ze_msl0', 'ze_msl1', 'ze_msl2')


def cfg():
    lines = ['cfg_save_auto 0', 'cl_idlefps 0', 'cl_maxfps 100',
             'vid_width 1600', 'vid_height 900', 'vid_fullscreen 0',
             'vid_winmaximize 0', 'vid_conautoscale 1', 'con_savehistory 0',
             'con_notifytime 0', 'con_notifylines 0', 'cl_download_zonesrc ""',
             'fs_missingwarn 0', 'developer 1', 'log_developer 1',
             'log_enable 1', 'log_dir logs', 'log_name runlines_smoke',
             'set lobby_enable 0', 'set lobby_master ""', 'sv_public 0',
             'waitms 1500', 'map surf_dune', 'waitmap 60', 'waitms 5000',
             'menu_restart', 'ui_close', 'set hud_scale 2',
             'set ui_tooltip_delay 0.35', 'zone_edit', 'waitms 400',
             'echo P675 INITIAL', 'zone_edit status', 'hud_edit ui',
             'zone_edit pointer 0 0', 'waitms 150',
             'echo P675 DELAY', 'hud_edit ui hover ze_shape', 'waitms 100',
             'hud_edit ui', 'echo P675 DELAY_END']

    def hover(name, shot=False, suffix=''):
        lines.extend(['echo P675 HOVER ' + name, 'hud_edit ui hover ' + name,
                      'waitms 750', 'wait 4', 'hud_edit ui'])
        if shot:
            lines.extend(['screenshot p675_' + name + suffix + '.png', 'wait 4'])
        lines.append('echo P675 END ' + name)

    for name in MAIN:
        hover(name, name in ('ze_shape', 'ze_gs', 'ze_sv'))
    lines.extend(['echo P675 AFTER_MAIN', 'zone_edit status',
                  'zone_edit settings', 'zone_edit setting sv_maxvelocity 10000',
                  'zone_edit press ze_ms0', 'waitms 300'])
    for name in PROPS + LABELS + ('ze_value',):
        hover(name, name in ('ze_mode_bhop', 'ze_ms0'))
    lines.extend(['zone_edit pointer 1300 300', 'waitms 750',
                  'echo P675 HELD', 'hud_edit ui down mouse1', 'waitms 100',
                  'hud_edit ui', 'echo P675 HELD_END', 'hud_edit ui up mouse1',
                  'waitms 750', 'echo P675 DEPART', 'zone_edit pointer 0 0', 'waitms 100',
                  'hud_edit ui', 'echo P675 DEPART_END',
                  'hud_edit ui hover ze_ms0', 'waitms 750',
                  'echo P675 BLUR', 'hud_edit ui focus 0 0', 'waitms 100',
                  'hud_edit ui', 'echo P675 BLUR_END', 'hud_edit ui focus 1 1',
                  'waitms 750', 'echo P675 LOOK', 'zone_edit mouse',
                  'waitms 200', 'hud_edit ui', 'echo P675 LOOK_END',
                  'zone_edit mouse', 'zone_edit press ze_msback', 'waitms 300',
                  'hud_edit ui hover ze_gs', 'waitms 750',
                  'echo P675 CLOSE', 'zone_edit', 'waitms 200', 'hud_edit ui',
                  'echo P675 CLOSE_END', 'zone_edit', 'waitms 400',
                  'set hud_scale 1', 'vid_width 800', 'vid_height 600', 'vid_restart', 'waitms 2000',
                  'ui_close', 'waitms 300'])
    hover('ze_gs', True, '_small')
    lines.extend(['echo P675 FINAL', 'zone_edit status', 'zone_edit',
                  'hud_edit', 'waitms 300'])
    hover('he_round')
    lines.extend(['hud_edit', 'echo RUNLINES COMPLETE', 'quit'])
    return '\n'.join(lines) + '\n'


def read(path):
    return re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '',
                  path.read_text(encoding='utf-8', errors='replace'), flags=re.M)


def chunks(text, name):
    return re.findall(r'P675 HOVER ' + re.escape(name) + r'\n(.*?)P675 END ' +
                      re.escape(name) + r'\n', text, re.S)


def tip_ok(block, name):
    visible = re.search(r'sui_probe round \S+ asset \S+ tip 1 lines ([1-9]\d*)', block)
    tip = re.search(r'sui_tip \[' + re.escape(name) + r'\] ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)', block)
    screen = re.search(r'sui_work .* screen ([\d.]+) ([\d.]+)', block)
    widths = re.findall(r'sui_tip_line \d+ width ([\d.]+) limit ([\d.]+)', block)
    if not (visible and tip and screen and widths):
        return False
    x, y, w, h = map(float, tip.groups())
    sx, sy = map(float, screen.groups())
    return (x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= sx+0.1 and y+h <= sy+0.1
            and len(widths) == int(visible[1])
            and all(float(a) <= float(b)+0.1 for a, b in widths))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log', type=Path, nargs='?')
    ap.add_argument('--control-log', type=Path)
    ap.add_argument('--write-cfg', type=Path)
    a = ap.parse_args()
    if a.write_cfg:
        a.write_cfg.write_text(cfg(), encoding='utf-8')
        return 0
    if not a.log:
        ap.error('log or --write-cfg required')
    text = read(a.log)
    checks = []

    def check(label, ok):
        checks.append(bool(ok))
        print(('ok   ' if ok else 'FAIL ') + label)

    def section(start, end):
        found = re.search(re.escape('P675 ' + start) + r'\n(.*?)' + re.escape('P675 ' + end) + r'\n', text, re.S)
        return found[1] if found else ''

    check('completed without VM/command errors', 'RUNLINES COMPLETE' in text and
          not re.search(r'Unknown command|boundcheck failed|Host_EndGame|QC VM error|Stack Overflow|sui_probe: no control', text))
    for name in MAIN + PROPS + LABELS + ('ze_value',):
        blocks = chunks(text, name)
        check('hover acted and wrapped tip inside screen: ' + name, blocks and
              all('sui_hover [' + name + ']' in b and tip_ok(b, name) for b in blocks))
    check('initial delay hides tooltip', re.search(r'sui_probe .* tip 0 ', section('DELAY', 'DELAY_END')))
    check('held mouse press reaches editor', re.search(r'sui_event down mouse1 took 1', section('HELD', 'HELD_END')))
    for phase in ('HELD', 'DEPART', 'BLUR', 'LOOK', 'CLOSE'):
        check(phase.lower() + ' dismisses tooltip', re.search(r'sui_probe .* tip 0 ', section(phase, phase + '_END')))
    states = re.findall(r'^zone_edit: state \d+ map \S+ zones (\d+) points (\d+) dirty (\d+) crc (\S+)', text, re.M)
    check('hovering never changes the zone table', len(states) >= 3 and len(set(states)) == 1)
    game = a.log.resolve().parent.parent
    check('hovering writes no local zones or properties', not list((game / 'data/maps').rglob('*.json'))
          and not list((game / 'data/maps').rglob('*.cfg')))
    check('small-window Surface tooltip reached', len(chunks(text, 'ze_gs')) == 2)
    check('HUD-editor tooltip survives inactive zone editor',
          any(tip_ok(b, 'he_round') for b in chunks(text, 'he_round')))
    for name in ('ze_shape', 'ze_gs', 'ze_sv', 'ze_mode_bhop', 'ze_ms0', 'ze_gs_small'):
        shot = game / 'screenshots' / ('p675_' + name + '.png')
        check('screenshot exists: ' + name, shot.is_file() and shot.stat().st_size > 1000)
    if a.control_log:
        control = read(a.control_log)
        check('control completed and reached all pre-existing controls', 'RUNLINES COMPLETE' in control and
              all(any('sui_hover [' + name + ']' in b for b in chunks(control, name))
                  for name in MAIN + PROPS + ('ze_value',)))
        check('control has no zone tooltip despite acting hovers',
              not re.search(r'sui_tip \[ze_', control))
    print('P676: %d passed, %d failed, of %d' % (sum(checks), len(checks)-sum(checks), len(checks)))
    return 0 if all(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
