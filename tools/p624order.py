#!/usr/bin/env python3
"""Patch 624: a ticked board line is shown in run order from where the viewer is. Look, and grade.

Built on tools/ui_gallery.py's rig. One authored run passes the same place twice: pass A along +y
at x 300 (0 to 10 s), a wide loop away, then pass B back along -y at x 200 (21.2 to 36.2 s), each
600 u/s and a sample a tick. Standing on A, B is 100 u to the left and 20 s later.

Graded on `lines order` (the cursor) and on the draw's own trace (`replay marktrace`: lnd is the
window a slot was drawn with, lnd2 the samples it drew), at six eyes:
  replay name   before any line is ticked: the open replay's own name is on its line near the
                viewer (the board loop has never run, and its windows must not be read as one)
  on A          the cursor is A's sample under the eye, though B is as near; the draw is the 2 s
                behind it and the 8 s ahead, which is none of B
  along A       1000 u on: the cursor followed; no look at the whole line moved it
  far down B    where only B is: a look at the whole line moved the cursor, and it is B's
  between       back between the passes: B, the stretch nearest in time to where the cursor was
  restart       from far down B, the timer armed in the start box, then between the passes: A, the
                earliest (the stats of a restart can lead the view by a frame, and a forget spent
                there takes B and keeps it)
  order 0       no window: the whole line, as before the patch
  names         with the names on (hud_linegraph_labels), standing ON one pass while the cursor is
                on the other, 100 u aside: the name is on the cursor's pass, which is the one drawn.
                The pass under the eye is the nearer by far and is not drawn, so a name put on the
                nearest sample of the whole line is on it both times (the first cut of this step
                stood between the passes, and passed with the fix taken out)
A second authored run at a real pace, 2000 u/s for 162 s (the look's 512 samples are 660 u apart):
  fast new      ticked with the eye already on pass A, where pass B has one of those 512 beside
                the eye and A's are 300 u up and down the line: the earliest stretch is A's. The
                fixture checks itself: a look at the 512 alone takes B
  fast stop     where that run stands still for 6 s: the cursor is the stop's LAST sample, so the
                8 s drawn ahead are the run after it
  fast cross    over to pass C, 500 u from the stretch being followed: the cursor is C's
Pixels, at the first eye: with the order on, the place B crosses holds exactly what it holds with
board lines off; with it off (hud_lines_order 0) B is there. The shots are for eyes.
"""
import argparse
import math
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_gallery as G  # noqa: E402

TICK, SPEED = 0.015, 600.0
XA, XB, Z = 300.0, 200.0, 130.0
TB0 = 10 + 5 + 1 + (3300 - XB) / SPEED          # the clock at which pass B begins, at y 3600
END = TB0 + 9000 / SPEED
START = '-350 -350 40 0 90 0'                   # the rig's start box
AHEAD = 8.0


def at(t):
    """Position and velocity of the authored run at clock t."""
    if t <= 10:
        return (XA, -3000 + SPEED * t), (0.0, SPEED)
    if t <= 15:
        return (XA + SPEED * (t - 10), 3000.0), (SPEED, 0.0)
    if t <= 16:
        return (3300.0, 3000 + SPEED * (t - 15)), (0.0, SPEED)
    if t <= TB0:
        return (3300 - SPEED * (t - 16), 3600.0), (-SPEED, 0.0)
    return (XB, 3600 - SPEED * (t - TB0)), (0.0, -SPEED)


def t_a(y):
    return (y + 3000) / SPEED


def t_b(y):
    return TB0 + (3600 - y) / SPEED


SPEED2, FAR, XC, YE = 2000.0, 150100.0, -200.0, 480.0
STOP = 6.0                      # seconds the fast run stands still at (XA, -1500)


def fast_legs():
    """Up A with a stop, a long way out, back down B 100 u aside, then up C 500 u from A."""
    pts = [(XA, -3000.0), (XA, -1500.0), (XA, -1500.0), (XA, FAR), (XB, FAR), (XB, -3000.0), (XC, -3000.0), (XC, 3000.0)]
    legs, t = [], 0.0
    for a, b in zip(pts, pts[1:]):
        dur = STOP if a == b else math.dist(a, b) / SPEED2
        legs.append((t, t + dur, a, b))
        t += dur
    return legs


FAST = fast_legs()
LEG_A, LEG_STOP, LEG_C = 2, 1, 6


def fast_at(t):
    for t0, t1, a, b in FAST:
        if t <= t1:
            break
    f = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
    v = (0.0, 0.0) if a == b else ((b[0] - a[0]) / (t1 - t0), (b[1] - a[1]) / (t1 - t0))
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), v


def fast_t(leg, y):
    t0, t1, a, b = FAST[leg]
    return t0 + (y - a[1]) / (b[1] - a[1]) * (t1 - t0)


def synth_fast():
    n = int(FAST[-1][1] / TICK)
    head = ['FTESURF-REC 4', 'map ' + G.MAP + '.map', 'track 0', 'leg 0', 'startseg 0', 'tickrate 0.015',
            'movetickrate 0.015', 'owner Fast Past', 'flags 0', 'pmpin gravity=800', 'begin']
    pos = []
    for i in range(n + 1):
        t = i * TICK
        (x, y), (vx, vy) = fast_at(t)
        pos.append((x, y))
        yaw = math.degrees(math.atan2(vy, vx)) if (vx or vy) else 90.0
        head.append('%.4f %.3f %.3f %.3f %.1f %.1f 0.0 0 %.1f 0 0 0 0 0 0 0 0' % (t, x, y, Z, vx, vy, yaw))
    head.append('end %d %d 0 0' % (n, n + 1))
    return '\n'.join(head) + '\n', pos


def coarse_pick(pos, eye):
    """What a look at every ceil(n/512)-th sample ALONE takes with no cursor: the first of them
    within max(1.5 best, best + 128) of the eye. `fast new` is worth running only while that is
    not the stretch under the eye."""
    stride = max(1, math.ceil(len(pos) / 512))
    d = [(math.dist((x, y, Z), eye), i) for i, (x, y) in list(enumerate(pos))[::stride]]
    best = min(d)[0]
    tol = max(best * 1.5, best + 128)
    return next(i for dist, i in d if dist <= tol)


def synth():
    n = int(END / TICK)
    head = ['FTESURF-REC 4', 'map ' + G.MAP + '.map', 'track 0', 'leg 0', 'startseg 0', 'tickrate 0.015',
            'movetickrate 0.015', 'owner Twice Past', 'flags 0', 'pmpin gravity=800', 'begin']
    for i in range(n + 1):
        t = i * TICK
        (x, y), (vx, vy) = at(t)
        yaw = math.degrees(math.atan2(vy, vx))
        head.append('%.4f %.3f %.3f %.3f %.1f %.1f 0.0 0 %.1f 0 0 0 0 0 0 0 0' % (t, x, y, Z, vx, vy, yaw))
    head.append('end %d %d 0 0' % (n, n + 1))
    return '\n'.join(head) + '\n', n + 1


def seed(game):
    G_SEED(game)
    (game / 'cfg/test').mkdir(parents=True, exist_ok=True)
    (game / 'cfg/test/p624_twice.rec').write_text(synth()[0])
    text, pos = synth_fast()
    if pos[coarse_pick(pos, (XA, YE, Z + 64))][0] != XB:
        raise SystemExit('the fast fixture no longer fools a look at 512 samples: `fast new` would show nothing')
    (game / 'cfg/test/p624_fast.rec').write_text(text)


def mark(name):
    return ['waitms 400', 'echo P624 ' + name, 'lines order', 'replay marktrace 1', 'waitms 200']


def named(name):
    return ['waitms 500', 'echo P624 ' + name, 'lines order', 'linegraph status', 'waitms 200']


def shot(name):
    return ['waitms 200', 'screenshot ' + name, 'waitms 250']


def config(a, size, port, http_port, native):
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0', 'cl_maxfps 250',
             'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0', 'r_fullbright 1', 'vid_srgb 0',
             'v_gamma 1', 'v_contrast 1', 'v_brightness 0', 'set ui_bootcheck 0', 'set rec_terms 4',
             'set run_resume 0', 'set run_prestrafe 0', f'set lobby_dir "http://127.0.0.1:{http_port}"',
             'name GalleryUser', 'waitms 1500', 'menu_restart', 'waitms 1200', 'ui_close', 'waitms 300',
             f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
             f'set hud_scale {a.hud_scale}', 'set rec_terms 4', 'set hud_mapinfo_timeleft 0',
             'set ui_native_scores 0', 'set hud_linegraph 0', 'set hud_linegraph_labels 0',
             'set hud_lines_board 1', 'set hud_trail 0', 'set hud_watch_path_far 6000',
             f'set hud_lines_order {AHEAD:g}', 'hud_trainer 0']
    # Before any line is ticked, so the board loop has never run: the open replay's own name.
    lines += ['set hud_watch_path 1', 'set hud_watch_path_ahead 1', 'set hud_linegraph_labels 1',
              'replay cfg/test/p624_twice.rec', 'waitms 3000', 'replay pause', 'replay seek 3', 'waitms 800',
              'echo P624 replay-name', 'linegraph status', 'waitms 200'] + shot('replay_name')
    lines += ['replay stop', 'waitms 500', 'set hud_linegraph_labels 0',
              'scores lineat 1 cfg/test/p624_twice.rec', 'waitms 4000', 'scores lines']
    lines += [f'setpos {XA} -2000 {Z} 0 90 0'] + mark('on-a') + shot('order_on')
    lines += ['set hud_lines_order 0'] + mark('order-0') + shot('order_off')
    lines += ['set hud_lines_board 0'] + shot('lines_off') + ['set hud_lines_board 1', f'set hud_lines_order {AHEAD:g}']
    lines += [f'setpos {XA} -1000 {Z} 0 90 0'] + mark('along-a')
    lines += [f'setpos {XB} -5000 {Z} 0 90 0'] + mark('far-b')
    lines += [f'setpos 250 0 {Z} 0 90 0'] + mark('between') + shot('between')
    # A restart from far down B, where only B is.
    lines += [f'setpos {XB} -5000 {Z} 0 90 0', 'waitms 600', f'setpos {START}', 'waitms 600',
              f'setpos 250 0 {Z} 0 90 0'] + mark('restart')
    # The cursor is on A (the restart). Over to B's line: it follows A, 119 u away.
    lines += ['set hud_linegraph_labels 1', f'setpos {XB} 0 {Z} 0 90 0'] + named('name-a') + shot('name_a')
    # Down B and back onto A's line: the cursor is B's, the nearest in time to where it was.
    lines += [f'setpos {XB} -5000 {Z} 0 90 0', 'waitms 600', f'setpos {XA} 0 {Z} 0 90 0'] + named('name-b') + shot('name_b')
    lines += ['set hud_linegraph_labels 0', 'scores lines clear', 'waitms 400']
    # The fast run, ticked with the eye already in place: its first look has no cursor.
    lines += [f'setpos {XA} {YE} {Z} 0 90 0', 'waitms 400', 'scores lineat 1 cfg/test/p624_fast.rec', 'waitms 9000']
    lines += mark('fast-new')
    lines += [f'setpos {XA} -1500 {Z} 0 90 0', 'waitms 300'] + mark('fast-stop')
    lines += [f'setpos {XC} {YE} {Z} 0 90 0', 'waitms 500'] + mark('fast-cross')
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def read(text, name):
    m = re.search(r'P624 %s\r?\n(.*?)(?=P624 |UIGALLERY FINISHED|$)' % re.escape(name), text, re.S)
    if not m:
        return None
    body = m.group(1)
    st = re.search(r'lines: order slot 1 cursor (\d+) t (-?[\d.]+) at ([\d.]+) u searches (\d+)(?: moved (\d+))? window (-?[\d.]+) (-?[\d.]+)', body)
    lnd = re.search(r'lnd 1 [\d.]+ (\d) (-?[\d.]+) (-?[\d.]+)', body)
    lnd2 = re.search(r'lnd2 1 (\d+) (\d+) (\d+) (\d+) (\d+)', body)
    if not (st and lnd and lnd2):
        return None
    return {'t': float(st.group(2)), 'd': float(st.group(3)), 'searches': int(st.group(4)),
            'moved': None if st.group(5) is None else int(st.group(5)),
            'win': (float(st.group(6)), float(st.group(7))), 'winon': int(lnd.group(1)),
            'drawn': (float(lnd.group(2)), float(lnd.group(3))), 'ia': int(lnd2.group(1)),
            'ib': int(lnd2.group(2)), 'points': int(lnd2.group(3))}


def name_at(text, name):
    """The cursor's clock and where slot 1's name was drawn (world), after `echo P624 <name>`."""
    m = re.search(r'P624 %s\r?\n(.*?)(?=P624 |UIGALLERY FINISHED|$)' % re.escape(name), text, re.S)
    body = m.group(1) if m else ''
    st = re.search(r'lines: order slot 1 cursor (\d+) t (-?[\d.]+)', body)
    lab = re.search(r'linegraph: label 1 at (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) screen (-?[\d.]+) (-?[\d.]+)', body)
    return (float(st.group(2)) if st else None, [float(v) for v in lab.groups()] if lab else None)


def differing(root, a, b, box):
    ia = Image.open(root / f'ftesurf/screenshots/{a}.png').convert('RGB').crop(box)
    ib = Image.open(root / f'ftesurf/screenshots/{b}.png').convert('RGB').crop(box)
    return ImageChops.difference(ia, ib).convert('L').point(lambda v: 255 if v > 24 else 0).histogram()[255]


def grade(rig):
    errors = G.grade(rig)
    samples = synth()[1]
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        root = rig / arm
        logs = list((root / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')

        def bad(msg):
            errors.append(f'{arm}: {msg}')

        s = {name: read(text, name) for name in ('on-a', 'order-0', 'along-a', 'far-b', 'between', 'restart')}
        missing = [k for k, v in s.items() if v is None]
        if missing:
            bad(f'no cursor and draw trace after {missing} (the drive did not act, or the build has no run order)')
            continue
        want = {'on-a': t_a(-2000), 'along-a': t_a(-1000), 'far-b': t_b(-5000), 'between': t_b(0), 'restart': t_a(0)}
        print(f'{arm}: cursor clock at each eye ' + ', '.join(f'{k} {s[k]["t"]:.3f} (wanted {v:.3f})' for k, v in want.items())
              + f'; looks at the whole line {[s[k]["searches"] for k in want]}, of which moved it {[s[k]["moved"] for k in want]}')
        for name, t in want.items():
            r = s[name]
            if abs(r['t'] - t) > 0.03:
                bad(f'{name}: the cursor is at {r["t"]:.3f} s of the run, {r["d"]:.0f} u from the eye; wanted {t:.3f} s')
                continue
            wa, wb = t - AHEAD * 0.25, t + AHEAD
            if r['winon'] != 1 or abs(r['drawn'][0] - wa) > 0.03 or abs(r['drawn'][1] - wb) > 0.03 or r['win'] != r['drawn']:
                bad(f'{name}: drawn with window {r["winon"]} {r["drawn"]} (status {r["win"]}), wanted {wa:.3f} to {wb:.3f}')
            ia = max(0, math.ceil(wa / TICK - 1e-6))
            ib = min(samples - 1, math.floor(wb / TICK + 1e-6))
            if abs(r['ia'] - ia) > 1 or abs(r['ib'] - ib) > 1 or r['points'] < 2:
                bad(f'{name}: drew samples {r["ia"]}..{r["ib"]} ({r["points"]} points), the window is {ia}..{ib}')
        if s['on-a']['moved'] is None:
            bad('the build does not print how many looks moved the cursor (`moved`): along-a and far-b not graded')
        else:
            if s['along-a']['moved'] != s['on-a']['moved']:
                bad(f'along-a: 1000 u along the same pass and a look at the whole line moved the cursor '
                    f'{s["along-a"]["moved"] - s["on-a"]["moved"]} times; wanted it followed')
            if s['far-b']['moved'] <= s['along-a']['moved']:
                bad('far-b: the cursor reached the other pass 4000 u away without a look moving it')

        # The open replay's name, before any line was ticked.
        m = re.search(r'P624 replay-name\r?\n(.*?)(?=P624 |UIGALLERY FINISHED|$)', text, re.S)
        eye = m and re.search(r'linegraph: eye (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', m.group(1))
        lab = m and re.search(r'linegraph: label 0 at (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', m.group(1))
        if not eye:
            bad('replay-name: no status (the drive did not act)')
        else:
            e = [float(v) for v in eye.groups()]
            p = [float(v) for v in lab.groups()] if lab else None
            print(f'{arm}: replay-name: eye {e}, the replay\'s name at {p}')
            if p is None:
                bad('replay-name: the open replay has no name on its line, with no board line ever ticked')
            elif math.dist(p, e) > 1500:      # the run's first point, where the lost name sat, is 1800 u back
                bad(f'replay-name: the name is at {p}, {math.dist(p, e):.0f} u from the eye at {e}; wanted it on the line near the viewer')

        # The fast run: the look's 512 samples are 660 u apart.
        fast = {name: read(text, name) for name in ('fast-new', 'fast-stop', 'fast-cross')}
        wantf = {'fast-new': fast_t(LEG_A, YE), 'fast-stop': FAST[LEG_STOP][1], 'fast-cross': fast_t(LEG_C, YE)}
        why = {'fast-new': 'the stretch under the eye, the earliest; pass B has the coarse sample',
               'fast-stop': 'the last sample of the 6 s stop, so the run after it is what is drawn ahead',
               'fast-cross': 'pass C under the eye, 500 u from the stretch that was being followed'}
        print(f'{arm}: fast run: ' + ', '.join(
            f'{k} {fast[k]["t"]:.3f} (wanted {v:.3f})' if fast[k] else f'{k} no status' for k, v in wantf.items()))
        for name, t in wantf.items():
            r = fast[name]
            if r is None:
                bad(f'{name}: no cursor and draw trace (the drive did not act, or the line did not build)')
            elif abs(r['t'] - t) > 0.03:
                bad(f'{name}: the cursor is at {r["t"]:.3f} s, {r["d"]:.0f} u from the eye; wanted {t:.3f} s ({why[name]})')
        z = s['order-0']
        if z['winon'] != 0 or z['ia'] != 0 or z['ib'] != samples - 1:
            bad(f'order-0: wanted no window and samples 0..{samples - 1}, read window {z["winon"]} samples {z["ia"]}..{z["ib"]}')

        # The names, with the eye on the OTHER pass: on the cursor's pass, inside what was drawn.
        for name, x, t, other in (('name-a', XA, t_a(0), 'B'), ('name-b', XB, t_b(0), 'A')):
            cur, lab = name_at(text, name)
            print(f'{arm}: {name}: cursor at {cur} s (wanted {t:.3f}), the name at {lab[:3] if lab else None}')
            if cur is None or abs(cur - t) > 0.03:
                bad(f'{name}: the cursor is at {cur} s, wanted {t:.3f} (the drive did not put it on that pass)')
            elif lab is None:
                bad(f'{name}: no name was drawn on the line')
            elif abs(lab[0] - x) > 5:
                bad(f'{name}: the name is at x {lab[0]:.0f}, on pass {other} under the eye, which is not drawn; '
                    f'the cursor\'s pass is at x {x:.0f}')
            elif not 0 < lab[1] < 4800:
                bad(f'{name}: the name is at y {lab[1]:.0f}, outside the stretch that is drawn ahead of the eye')

        # Pixels, at the first eye: B crosses the lower left of the view, A runs up the middle.
        w, h = (int(v) for v in arm.split('x'))
        left = (int(0.10 * w), int(0.56 * h), int(0.42 * w), h)
        mid = (int(0.46 * w), int(0.52 * h), int(0.54 * w), h)
        b_on = differing(root, 'order_on', 'lines_off', left)
        b_off = differing(root, 'order_off', 'lines_off', left)
        a_on = differing(root, 'order_on', 'lines_off', mid)
        print(f'{arm}: where pass B crosses the view {left}: {b_on} px of line with the order on, {b_off} with it off; '
              f'pass A up the middle: {a_on} px')
        if b_on:
            bad(f'{b_on} px of a line where the later pass crosses the view, with the order on')
        if b_off < 300:
            bad(f'with hud_lines_order 0 the later pass drew {b_off} px there, wanted 300+ (the control shows nothing)')
        if a_on < 300:
            bad(f'the pass the eye is on drew {a_on} px, wanted 300+')
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
    a = p.parse_args()
    a.plugins = Path('nonexistent-no-plugin')
    G_SEED = G.seed_runs
    G.seed_runs = seed
    G.config = config
    G.SHOTS = ('replay_name', 'order_on', 'order_off', 'lines_off', 'between', 'name_a', 'name_b')
    G.SHOTS_1080 = ()
    rig = G.run(a)
    errors = grade(rig)
    for error in errors:
        print('FAIL', error)
    print('Order rig', rig)
    print('Order failures:', len(errors))
    raise SystemExit(bool(errors))
