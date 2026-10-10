#!/usr/bin/env python3
"""Patch 621: the strafe trainer keeps its last jumps. Look, and grade.

Built on tools/ui_gallery.py's rig, whose map has no floor: the body floats, so the server's
own flags say "air" for the whole run. `trainer feed` authors the rest (1 ground, 2 riding a
ramp, 3 air), and `+right`/`+left` turn at exactly cl_yawspeed, so every jump is known by the
rates of its strafes without the subject's help.

Graded on the panel's own `trainer status` lines after each mark:
  kept      three jumps of 2, 3 and 2 strafes at 300, 400 and 500 deg/s, ended by the ground,
            a ramp and the ground; a 30 ms gap in the ride and a jump with no strafe are
            counted and not kept
  paging    older, older, older (stops at the oldest), newer, newer (back to the newest)
  release   a jump kept while an old one is pinned takes the panel back
  frozen    hard strafing on the ground afterwards changes nothing about the jump on show
  open      the jump in the air is the one on show; older pins the newest kept, newer returns
  ring      ten jumps made, eight kept, the two oldest gone, older stops at number 3
  low       placed where it would run off the bottom, the panel ends on the screen's edge
  split 0   a ramp in the middle of a jump does not end it, and its strafe is not graded
  sync      a key held into a jump has no sync (it was not swapped there); one pressed with its
            flick just before the jump reads 0, timed from the key and not from the take-off
Pixels: the strip's place matches the bare HUD with the strip off, its cells are filled for the
kept jumps and no more (8, then 3), and an older jump's panel differs from the newest's. The
shots are for eyes.

--real is the other arm, with nothing fed: surf_kitsune, a hop from the spawn (the server's
ground flag ends it) and a drop onto a real ramp (the server's ramp flag does).
"""
import argparse
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_gallery as G  # noqa: E402

SHOTS = ('hud_plain', 'trn_newest', 'trn_older', 'trn_open', 'trn_full', 'trn_nostrip')
GROUND, RIDE, AIR = 1, 2, 3


def strafe(side, yaw, ms):
    move = 'moveright' if side == 'R' else 'moveleft'
    turn = 'right' if side == 'R' else 'left'
    return [f'cl_yawspeed {yaw}', f'+{move}', f'+{turn}', f'waitms {ms}', f'-{turn}', f'-{move}']


def jump(strafes, end):
    lines = [f'trainer feed {AIR}', 'waitms 60']
    for side, yaw in strafes:
        lines += strafe(side, yaw, 300)
    return lines + ['waitms 40', f'trainer feed {end}', 'waitms 150']


def mark(name):
    return ['waitms 150', 'echo P621 ' + name, 'trainer status', 'waitms 50']


def config(a, size, port, http_port, native):
    def shot(name):
        return ['waitms 300', 'screenshot ' + name, 'waitms 250']

    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0', 'cl_maxfps 250',
             'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0', 'r_fullbright 1', 'vid_srgb 0',
             'v_gamma 1', 'v_contrast 1', 'v_brightness 0', 'set ui_bootcheck 0', 'set rec_terms 4',
             'set run_resume 0', 'set run_prestrafe 0', f'set lobby_dir "http://127.0.0.1:{http_port}"',
             'name GalleryUser', 'waitms 1500', 'menu_restart', 'waitms 1200', 'ui_close', 'waitms 300',
             f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
             f'set hud_scale {a.hud_scale}', 'set rec_terms 4', 'set hud_mapinfo_timeleft 0',
             'set ui_native_scores 0', 'set hud_linegraph 0', 'seta hud_trainer_x 0.28',
             'seta hud_trainer_y 0.27', 'set hud_trainer_size 0', 'set hud_trainer_rows 6',
             'set hud_trainer_trace 1', 'set hud_trainer_jumps 1', 'set hud_trainer_split 1',
             'hud_trainer 0']
    lines += shot('hud_plain')
    # Speed first, unmeasured; then the body is "on the ground" before the panel is on.
    lines += strafe('R', 330, 1500) + ['waitms 200', f'trainer feed {GROUND}', 'hud_trainer 1',
                                       'developer 1', 'log_developer 1', 'waitms 400']
    lines += mark('empty')
    lines += jump((('R', 300), ('L', 300)), GROUND)
    lines += jump((('R', 400), ('L', 400), ('R', 400)), RIDE)
    # The ride loses contact for two ticks with a key held, and finds it again.
    lines += ['waitms 300', 'cl_yawspeed 500', '+moveright', '+right', 'waitms 100',
              f'trainer feed {AIR}', 'waitms 30', f'trainer feed {RIDE}', 'waitms 100',
              '-right', '-moveright', 'waitms 200']
    lines += jump((('L', 500), ('R', 500)), GROUND)
    lines += [f'trainer feed {AIR}', 'waitms 400', f'trainer feed {GROUND}', 'waitms 150']    # no strafe in it
    lines += mark('kept') + shot('trn_newest')
    lines += ['trainer older'] + mark('older1') + shot('trn_older')
    lines += ['trainer older'] + mark('older2') + ['trainer older'] + mark('older3')
    lines += ['trainer newer'] + mark('newer1') + ['trainer newer'] + mark('newer2')
    lines += ['trainer older', 'trainer older'] + mark('pinned')
    lines += jump((('R', 350),), GROUND) + mark('released')
    # On the ground, and moving hard: the jump on show must not change.
    lines += strafe('L', 450, 600) + mark('frozen')
    # In the air with a strafe held: the open jump is the one on show.
    lines += [f'trainer feed {AIR}', 'waitms 60', 'cl_yawspeed 320', '+moveright', '+right', 'waitms 400']
    lines += mark('open') + shot('trn_open')
    lines += ['trainer older'] + mark('open-older') + ['trainer newer'] + mark('open-newer')
    lines += ['-right', '-moveright', 'waitms 40', f'trainer feed {GROUND}', 'waitms 150']
    for k in range(5):
        lines += jump((('R', 600 + 10 * k),), GROUND)
    lines += mark('ring') + shot('trn_full')
    lines += ['trainer older'] * 9 + mark('ring-oldest') + ['trainer live']
    # Placed where it would run off the bottom, it rises to stay on the screen.
    lines += ['set hud_trainer_y 0.95'] + mark('low') + ['set hud_trainer_y 0.27', 'waitms 100']
    # hud_trainer_split is read twice a second of the trainer's own clock.
    lines += ['set hud_trainer_split 0', 'waitms 800', f'trainer feed {AIR}', 'waitms 60']
    lines += strafe('R', 300, 300) + [f'trainer feed {RIDE}'] + strafe('L', 300, 300)
    lines += [f'trainer feed {AIR}'] + strafe('R', 300, 300)
    lines += ['waitms 40', f'trainer feed {GROUND}', 'waitms 150'] + mark('split0')
    lines += ['set hud_trainer_split 1', 'waitms 800', 'set hud_trainer_jumps 0'] + mark('nostrip') + shot('trn_nostrip')
    lines += ['set hud_trainer_jumps 1', 'waitms 200']
    # A key held on the ground for 400 ms, then the flick and the take-off together: the jump
    # opens a strafe for it, and that is not a swap. The next strafe is one, in the air.
    lines += ['echo P621 held', 'cl_yawspeed 300', '+moveright', '+left', 'waitms 400',
              '-left', '+right', f'trainer feed {AIR}', 'waitms 300', '-right', '-moveright']
    lines += strafe('L', 300, 300) + ['waitms 40', f'trainer feed {GROUND}', 'waitms 200', 'echo P621 held-done']
    # The key and the flick together on the ground, the take-off 45 ms later: timed from the key.
    lines += ['echo P621 tapped', 'cl_yawspeed 300', '+left', 'waitms 300', '+moveright', '-left', '+right',
              'waitms 45', f'trainer feed {AIR}', 'waitms 300', '-right', '-moveright', 'waitms 40',
              f'trainer feed {GROUND}', 'waitms 200', 'echo P621 tapped-done']
    lines += ['developer 0', 'log_developer 0', 'trainer feed 0', 'hud_trainer 0',
              'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


REAL_MAP = 'surf_kitsune'
# 126 u above a ramp 5500 u long, off a ride in one of the owner's runs (plane -0.76 -0.14 0.64).
REAL_DROP = '-15212.4 14484.6 10766.4'


def config_real(a, size, port, http_port, native):
    """No feed: the server's own ground flag and ramp flag end the jumps."""
    lines = config(a, size, port, http_port, native).split('\n')
    lines = lines[:lines.index('hud_trainer 0')]
    lines[lines.index('waitms 7000')] = 'waitms 14000'
    lines += ['hud_trainer 1', 'developer 1', 'log_developer 1', 'waitms 600'] + mark('spawn')
    lines += ['cl_yawspeed 200', '+moveright', '+right', '+jump', 'waitms 80', '-jump', 'waitms 320',
              '-right', '-moveright', 'waitms 900'] + mark('hop')
    lines += ['+moveright', f'setpos {REAL_DROP} 0 -104 0', 'waitms 900'] + mark('ramp')
    lines += ['waitms 200', 'screenshot real_ramp', 'waitms 250', '-moveright', 'waitms 2500'] + mark('after')
    lines += ['developer 0', 'log_developer 0', 'hud_trainer 0', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def grade_real(rig):
    errors = G.grade(rig)
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        logs = list((rig / arm / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')

        def bad(msg):
            errors.append(f'{arm}: {msg}')

        if 'trainer: feed' in text:
            bad('the real arm fed a state')
        s = {name: status(text, name) for name in ('spawn', 'hop', 'ramp', 'after')}
        if any(v is None for v in s.values()):
            bad(f'no trainer status after {[k for k, v in s.items() if v is None]}')
            continue
        ends = {num: j['end'] for num, j in s['after']['jumps'].items()}
        print(f'{arm}: states spawn {s["spawn"]["state"]} hop {s["hop"]["state"]} ramp {s["ramp"]["state"]} '
              f'after {s["after"]["state"]}; kept jumps and what ended them (1 ground, 2 ramp): {ends}; '
              f'not kept: short {s["after"]["short"]} empty {s["after"]["empty"]}')
        if s['spawn']['state'] != GROUND or s['spawn']['kept']:
            bad(f'spawn: wanted the body on the ground with nothing kept, read state {s["spawn"]["state"]} kept {s["spawn"]["kept"]}')
        j = s['hop']['jumps'].get(1)
        if not j or j['end'] != GROUND or not 550 <= j['air'] <= 900 or [r[0] for r in j['rates']] != ['R']:
            bad(f'hop: wanted jump 1, one R strafe, about 755 ms of air, ended by the ground; read {j and j["line"]}')
        j = s['ramp']['jumps'].get(2)
        if not j or j['end'] != RIDE or not 350 <= j['air'] <= 800:
            bad(f'ramp: wanted jump 2 ended by the ramp after about 560 ms of air; read {j and j["line"]}')
        if s['ramp']['state'] != RIDE:
            bad(f'ramp: the body was not riding at the mark (state {s["ramp"]["state"]})')
    return errors


def status(text, name):
    """The `trainer status` block printed after one mark, parsed."""
    m = re.search(r'P621 %s\r?\n(.*?)(?=P621 |UIGALLERY FINISHED|$)' % re.escape(name), text, re.S)
    if not m:
        return None
    body = m.group(1)
    head = re.search(r'trainer: state (\d+) open (\d+) strafes (\d+) kept (\d+) newest (\d+) pin (\d+) show (-?\d+)', body)
    lost = re.search(r'trainer: not kept short (\d+) empty (\d+) split (\d+)', body)
    show = re.search(r'trainer: show span (-?\d+)ms v (-?[\d.]+)->(-?[\d.]+) strafes (\d+) trace (\d+)', body)
    box = re.search(r'trainer: panel (-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+) u ([\d.]+) strip (\d+)', body)
    if not (head and lost and show and box):
        return None
    jumps = {}
    for num, end, kept, made, air, v0, v1, trace, q, rates in re.findall(
            r'trainer: jump (\d+) end (\d+) strafes (\d+) of (\d+) air (\d+)ms v (-?[\d.]+)->(-?[\d.]+) trace (\d+) q (-?[\d.]+) rates((?: [LR][\d.]+)*)', body):
        jumps[int(num)] = {'end': int(end), 'kept': int(kept), 'made': int(made), 'air': int(air),
                           'v': (float(v0), float(v1)), 'trace': int(trace), 'q': float(q),
                           'rates': [(r[0], float(r[1:])) for r in rates.split()],
                           'line': (num, end, kept, made, air, v0, v1, trace, q, rates)}
    keys = ('state', 'open', 'strafes', 'kept', 'newest', 'pin', 'show')
    out = dict(zip(keys, (int(v) for v in head.groups())))
    out.update(short=int(lost.group(1)), empty=int(lost.group(2)), split=int(lost.group(3)),
               span=int(show.group(1)), v=(show.group(2), show.group(3)), shown=int(show.group(4)),
               box=[float(v) for v in box.groups()], jumps=jumps)
    return out


def differing(root, a, b, box):
    ia = Image.open(root / f'ftesurf/screenshots/{a}.png').convert('RGB').crop(box)
    ib = Image.open(root / f'ftesurf/screenshots/{b}.png').convert('RGB').crop(box)
    diff = ImageChops.difference(ia, ib).convert('L').point(lambda v: 255 if v > 24 else 0)
    return diff.histogram()[255]


CHIP = (36, 39, 53)             # SUI_THEME_CHIP, which only a kept jump's cell is filled with


def chip_pixels(root, name, box):
    im = Image.open(root / f'ftesurf/screenshots/{name}.png').convert('RGB').crop(box)
    return sum(n for n, c in im.getcolors(maxcolors=1 << 20) if max(abs(c[i] - CHIP[i]) for i in range(3)) <= 4)


def grade(rig):
    errors = G.grade(rig)
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        root = rig / arm
        logs = list((root / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')

        def bad(msg):
            errors.append(f'{arm}: {msg}')

        s = {name: status(text, name) for name in (
            'empty', 'kept', 'older1', 'older2', 'older3', 'newer1', 'newer2', 'pinned', 'released',
            'frozen', 'open', 'open-older', 'open-newer', 'ring', 'ring-oldest', 'low', 'split0', 'nostrip')}
        missing = [k for k, v in s.items() if v is None]
        if missing:
            bad(f'no trainer status after {missing} (the drive did not act, or the build has no history)')
            continue

        def want(name, **fields):
            got = {k: s[name][k] for k in fields}
            if got != fields:
                bad(f'{name}: wanted {fields}, read {got}')

        def rates(name, num, wanted, end):
            j = s[name]['jumps'].get(num)
            if not j:
                bad(f'{name}: jump {num} is not kept: {sorted(s[name]["jumps"])}')
                return
            got = j['rates']
            ok = len(got) == len(wanted) and j['end'] == end
            for (side, rate), (wside, wrate) in zip(got, wanted):
                # A strafe's first tick is partial, so a rate reads a few percent low.
                if side != wside or not 0.90 * wrate <= rate <= 1.02 * wrate:
                    ok = False
            if not ok:
                bad(f'{name}: jump {num} read end {j["end"]} rates {got}, authored end {end} rates {wanted}')

        want('empty', kept=0, newest=0, pin=0, show=-1, state=GROUND)
        want('kept', kept=3, newest=3, pin=0, show=3, short=1, empty=1, state=GROUND)
        rates('kept', 1, [('R', 300), ('L', 300)], GROUND)
        rates('kept', 2, [('R', 400), ('L', 400), ('R', 400)], RIDE)
        rates('kept', 3, [('L', 500), ('R', 500)], GROUND)
        for num in (1, 2, 3):
            j = s['kept']['jumps'].get(num)
            if j and not (j['trace'] >= 30 and 550 <= j['air'] <= 1300 and j['kept'] == j['made']):
                bad(f'kept: jump {num} holds {j["trace"]} trace ticks over {j["air"]} ms, {j["kept"]} of {j["made"]} strafes')
        n = len(re.findall(r'trainer: kept jump \d+ strafes', text))
        print(f'{arm}: kept {s["kept"]["kept"]} of 5 jumps made by the first mark (1 short, 1 empty wanted: '
              f'{s["kept"]["short"]}, {s["kept"]["empty"]}); {n} keeps reported over the run')

        want('older1', pin=2, show=2, shown=3)
        want('older2', pin=1, show=1, shown=2)
        want('older3', pin=1, show=1)
        want('newer1', pin=2, show=2)
        want('newer2', pin=0, show=3)
        want('pinned', pin=1, show=1)
        want('released', kept=4, newest=4, pin=0, show=4)
        rates('released', 4, [('R', 350)], GROUND)
        a, b = s['released'], s['frozen']
        ja, jb = a['jumps'].get(4), b['jumps'].get(4)
        if not ja or not jb:
            bad(f'frozen: jump 4 is not kept: {sorted(a["jumps"])}, {sorted(b["jumps"])}')
        elif (a['span'], a['v'], ja['line']) != (b['span'], b['v'], jb['line']) or b['show'] != 4:
            bad(f'frozen: the jump on show changed on the ground: span {a["span"]}->{b["span"]} v {a["v"]}->{b["v"]}')
        want('open', state=AIR, open=1, strafes=1, pin=0, show=0, shown=1, kept=4)
        if not 300 <= s['open']['span'] <= 700:
            bad(f'open: the open jump spans {s["open"]["span"]} ms, about 460 authored')
        want('open-older', pin=4, show=4)
        want('open-newer', pin=0, show=0)
        want('ring', kept=8, newest=10, pin=0, show=10)
        if sorted(s['ring']['jumps']) != list(range(3, 11)):
            bad(f'ring: kept jumps {sorted(s["ring"]["jumps"])}, wanted 3..10')
        rates('ring', 3, [('L', 500), ('R', 500)], GROUND)
        rates('ring', 5, [('R', 320)], GROUND)
        for k in range(5):
            rates('ring', 6 + k, [('R', 600 + 10 * k)], GROUND)
        want('ring-oldest', pin=3, show=3)
        height = int(arm.split('x')[1])
        x, y, w, h, u, strip = s['low']['box']
        if abs(y + h - height) > 0.5 or y >= 0.95 * height - 1:
            bad(f'low: at hud_trainer_y 0.95 the panel is {y:g}..{y + h:g} of {height}, wanted its bottom on the edge')
        want('split0', kept=8, newest=11, show=11, split=0)
        j = s['split0']['jumps'].get(11)
        if not j or [r[0] for r in j['rates']] != ['R', 'L', 'R'] or j['rates'][1][1] != 0 \
                or not all(270 <= j['rates'][i][1] <= 306 for i in (0, 2)) or j['end'] != GROUND:
            bad(f'split0: wanted one jump of R300 L0 R300 ended by the ground, read {j and (j["end"], j["rates"])}')
        if s['kept']['short'] != s['split0']['short'] or s['split0']['empty'] != s['kept']['empty']:
            bad(f'jumps were dropped after the first mark: short {s["split0"]["short"]} empty {s["split0"]["empty"]}')
        want('nostrip', split=1)

        # The strafes' own reports between two marks: side and sync, None for no number.
        def syncs(name):
            m = re.search(r'P621 %s\r?\n(.*?)P621 %s-done' % (name, name), text, re.S)
            return [(side, None if v == 'none' else int(v[:-2])) for side, v in re.findall(
                r'trainer: ([LR]) dur \d+ms graded \d+ms q [\d.-]+ rate [\d.]+ ideal [\d.]+ sync (none|[+-]\d+ms)',
                m.group(1) if m else '')]

        held, tapped = syncs('held'), syncs('tapped')
        print(f'{arm}: a key held 400 ms into a jump, then a swap in the air: {held}; a key pressed with its flick '
              f'45 ms before the jump: {tapped}')
        if len(held) != 2 or held[0] != ('R', None) or held[1][0] != 'L' or held[1][1] is None or abs(held[1][1]) > 30:
            bad(f'held: wanted no sync for the held key and about 0 for the swap after it, read {held}')
        if len(tapped) != 1 or tapped[0][0] != 'R' or tapped[0][1] is None or abs(tapped[0][1]) > 20:
            bad(f'tapped: wanted about 0 ms, timed from the key and not from the take-off, read {tapped}')

        # Pixels. The panel's own rectangle says where to look; the pixels say what is there.
        # Both marks below show jump 11, so the two panels differ by the strip alone.
        x, y, w, h, u, strip = s['split0']['box']
        if strip != 32 or s['nostrip']['box'][5] != 0 or s['nostrip']['box'][3] != h - 32 * u:
            bad(f'the strip is not 32 units of the panel: {s["split0"]["box"]} with, {s["nostrip"]["box"]} without')
            continue
        gone = tuple(int(v) for v in (x, y + h - 32 * u, x + w, y + h))
        off = differing(root, 'hud_plain', 'trn_nostrip', gone)
        x, y, w, h, u, strip = s['ring']['box']
        box = tuple(int(v) for v in (x, y + h - 32 * u, x + w, y + h))
        on = differing(root, 'hud_plain', 'trn_full', box)
        full = chip_pixels(root, 'trn_full', box)
        x, y, w, h, u, strip = s['kept']['box']
        three = chip_pixels(root, 'trn_newest', tuple(int(v) for v in (x, y + h - 32 * u, x + w, y + h)))
        x, y, w, h, u, strip = s['older1']['box']
        moved = differing(root, 'trn_newest', 'trn_older', tuple(int(v) for v in (x, y, x + w, y + h)))
        cell = 16 * u * 18 * u
        print(f'{arm}: strip place {box}: {on} px differ from the bare HUD with it, {off} px of {gone} without; '
              f'cell fill {full} px with 8 kept and {three} with 3 (a cell is {cell:.0f}); '
              f'older against newest {moved} px')
        # A cell's fill less its two strings and its corners: more than half is left.
        if not 8 * 0.5 * cell <= full <= 8 * cell:
            bad(f'8 kept jumps filled {full} px of cells, wanted {4 * cell:.0f} to {8 * cell:.0f}')
        if not 3 * 0.5 * cell <= three <= 3 * cell:
            bad(f'3 kept jumps filled {three} px of cells, wanted {1.5 * cell:.0f} to {3 * cell:.0f}')
        if off:
            bad(f'{off} px of the place the strip had still differ from the bare HUD with hud_trainer_jumps 0')
        if moved < 2000:
            bad(f'an older panel differs from the newest by {moved} px, wanted 2000+')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True)
    p.add_argument('--qc-artifacts', type=Path, required=True)
    p.add_argument('--library', type=Path)
    p.add_argument('--out', type=Path, required=True, help='owned task-root output directory')
    p.add_argument('--sizes', nargs='+', type=G.size_arg, default=[(1920, 1080)], metavar='WxH')
    p.add_argument('--hud-scale', type=float, default=2)
    p.add_argument('--renderer', choices=('gl', 'd3d11', 'vk'), default='gl')
    p.add_argument('--timeout', type=int, default=150)
    p.add_argument('--real', action='store_true',
                   help=f'the other arm: {REAL_MAP} from --library, a real hop and a real ramp, nothing fed')
    a = p.parse_args()
    a.plugins = Path('nonexistent-no-plugin')
    G.config = config_real if a.real else config
    G.SHOTS = ('real_ramp',) if a.real else SHOTS
    G.SHOTS_1080 = ()
    if a.real:
        # A Source map: hl2's loader beside both exes (default.cfg loads it), from the engine's folder.
        G.SERVER_CFG = f'sv_cheats 1\nlog_enable 1\nlog_dir logs\nlog_name server\nmap {REAL_MAP}\n'
        G.EXTRA_PLUGINS = (a.engine.resolve().parent / 'fteplug_hl2_x64.dll',)
    rig = G.run(a)
    errors = grade_real(rig) if a.real else grade(rig)
    for error in errors:
        print('FAIL', error)
    print('Trainer rig', rig)
    print('Trainer failures:', len(errors))
    raise SystemExit(bool(errors))
