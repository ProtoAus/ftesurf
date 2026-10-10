#!/usr/bin/env python3
"""Patch 620: the runner's name on each ticked line in the world. Look, and grade.

Built on tools/ui_gallery.py's rig. Three straight synthetic runs cross the view 360 to 480 u ahead
of the spawn, 9 u a sample, so each one's nearest point to the eye is dead ahead and on screen.
Their owners are the kinds of name the boards really hold: Cyrillic, kana and Hanzi, symbols with a
^ colour escape and an emoji, and one longer than the label shows.

Graded on the panel's own `linegraph status` lines after each of four eye positions (setpos):
  - a label is drawn for every run, and its point on the line is the CLOSEST point of that line to
    the printed eye, to half a unit. The lines and eyes are authored here, so the answer is known
    without the subject: (run's x, eye's y, run's z). The eyes sit between samples on purpose, and
    far inside one coarse step of the old search (54 u), so a label that snaps to a sample fails;
  - the text is the slot number and the name, the long one cut after 18 CHARACTERS (it is 22, and
    42 bytes) with nothing left of a half character, and the ^ still a ^.
  - then three eyes ON run 1's line looking along it, which is how a line is ridden. The nearest
    point of that line is under the camera, where no text can be read, so its label must sit
    where the line comes onto the screen: at the middle of the bottom edge of the label area
    (86% of the height). Every label must be inside that area and on its line, and its distance
    ahead of the eye must be the same at all three eyes: it slides, it does not hop. The first
    cut of this patch put all four off screen here.
  - a console face of the player's own that begins with the shipped one is still theirs after
    the next Font_Init.
What a name looks like (the face, a glyph the first face lacks) is for eyes: names_world,
names_along, names_panel and names_console are the shots.
"""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_gallery as G  # noqa: E402

# (owner, x of the line, z of the line). Written to the .rec as UTF-8, as surfd serves them.
RUNS = (('Привет мир', 360.0, 130.0),
        ('日本語カタカナ 柊', 420.0, 150.0),
        ('★ ^3star ♥ \U0001f600', 480.0, 170.0))
LONG = ('Ελληνικά-очень-длинное', 540.0, 190.0)
ALL = RUNS + (LONG,)
# The player's origin. The first is 10 u from run 1's line at its height, midway between two of
# the samples the first search tries (54 u apart): neither is on screen, the line is.
EYES = ((350.0, 21.0, 66.0), (0.0, 0.0, 128.0), (0.0, 7.3, 128.0), (0.0, 21.7, 128.0), (0.0, 40.1, 128.0))
ALONG = (0.0, 7.3, 21.7)         # y of the origin, on run 1's x, yaw 90: looking along the lines
SPEED, TICK, SECONDS = 600.0, 0.015, 20.0
CHOSEN = 'gfx/fonts/GoogleMed.ttf,msyh.ttc'


def synth(owner, x, z):
    n = round(SECONDS / TICK)
    head = ['FTESURF-REC 4', 'map ' + G.MAP + '.map', 'track 0', 'leg 0', 'startseg 0', 'tickrate 0.015',
            'movetickrate 0.015', 'owner ' + owner, 'flags 0', 'pmpin gravity=800', 'begin']
    for i in range(n + 1):
        t = i * TICK
        y = -SPEED * SECONDS / 2 + SPEED * t
        head.append('%.4f %.3f %.3f %.3f 0.0 %.1f 0.0 0 90.0 0 0 0 0 0 0 0 0' % (t, x, y, z, SPEED))
    head.append('end %d %d 0 0' % (n, n + 1))
    return '\n'.join(head) + '\n'


def seed(game):
    G_SEED(game)
    (game / 'cfg/test').mkdir(parents=True, exist_ok=True)
    for slot, (owner, x, z) in enumerate(ALL, 1):
        (game / f'cfg/test/p620_run{slot}.rec').write_bytes(synth(owner, x, z).encode('utf-8'))


def config(a, size, port, http_port, native):
    def mark(name, wait=500):
        return [f'waitms {wait}', 'echo P620 ' + name, 'linegraph status']

    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0', 'cl_maxfps 250',
             'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0', 'r_fullbright 1', 'vid_srgb 0',
             'v_gamma 1', 'v_contrast 1', 'v_brightness 0', 'set ui_bootcheck 0', 'set rec_terms 4',
             'set run_resume 0', 'set run_prestrafe 0', f'set lobby_dir "http://127.0.0.1:{http_port}"',
             'name GalleryUser', 'waitms 1500', 'menu_restart', 'waitms 1200', 'ui_close', 'waitms 300',
             f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
             f'set hud_scale {a.hud_scale}', 'set rec_terms 4', 'set hud_mapinfo_timeleft 0',
             'set ui_native_scores 0', 'set ui_native_graphs 0', 'set hud_linegraph 1', 'set hud_lines_board 1',
             'set hud_linegraph_labels 1', 'hud_trainer 0', 'echo P620 font', 'con_textfont']
    for slot in range(1, len(ALL) + 1):
        lines += [f'scores lineat {slot} cfg/test/p620_run{slot}.rec']
    lines += ['waitms 4000', 'scores lines']
    for k, (x, y, z) in enumerate(EYES):
        lines += [f'setpos {x} {y} {z} 0 0 0'] + mark(f'eye{k}')
    lines += ['waitms 300', 'screenshot names_world', 'waitms 300']
    for k, y in enumerate(ALONG):
        lines += [f'setpos {RUNS[0][1]} {y} 128 0 90 0'] + mark(f'along{k}')
    lines += ['waitms 300', 'screenshot names_along', 'waitms 300']
    lines += ['linegraph', 'waitms 1200', 'linegraph cursor 5 5', 'waitms 300', 'screenshot names_panel', 'waitms 300',
              'linegraph close', 'waitms 300']
    # The console holds the status lines above, names included.
    lines += ['scr_consize 0.9', 'toggleconsole', 'waitms 900', 'screenshot names_console', 'waitms 300', 'toggleconsole']
    # A list of the player's own that begins with the shipped face, then Font_Init again
    # (menu_restart runs the menu's): the first cut moved it back to the default list.
    lines += [f'con_textfont "{CHOSEN}"', 'waitms 300', 'menu_restart', 'waitms 1500', 'ui_close',
              'waitms 300', 'echo P620 chosen', 'con_textfont', 'waitms 100']
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def grade(rig):
    errors = [e for e in G.grade(rig) if 'missing screenshot scores_native' not in e]
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        logs = list((rig / arm / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_bytes().decode('utf-8', errors='replace')

        def bad(msg):
            errors.append(f'{arm}: {msg}')

        m = re.search(r'P620 font\b.*?"con_textfont" is "([^"]*)"', text, re.S)
        print(f'{arm}: console font {m.group(1) if m else None}')
        if not m or not m.group(1).startswith('gfx/fonts/GoogleMed.ttf,'):
            bad(f'the console font has no fallback faces: {m and m.group(1)}')
        m = re.search(r'P620 chosen\b.*?"con_textfont" is "([^"]*)"', text, re.S)
        print(f'{arm}: a chosen console face after the next Font_Init: {m.group(1) if m else None}')
        if not m or m.group(1) != CHOSEN:
            bad(f'the player\'s console face {CHOSEN} became {m and m.group(1)}')
        worst, graded = 0.0, 0
        for k, (ex, ey, ez) in enumerate(EYES):
            body = re.search(r'P620 eye%d\b(.*?)(?=P620 |UIGALLERY FINISHED|$)' % k, text, re.S)
            eye = body and re.search(r'linegraph: eye (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', body.group(1))
            if not eye:
                bad(f'eye {k}: no status after the move')
                continue
            e = [float(v) for v in eye.groups()]
            if abs(e[0] - ex) > 0.5 or abs(e[1] - ey) > 0.5:
                bad(f'eye {k}: setpos to {ex} {ey} left the eye at {e[:2]}')
                continue
            labels = {int(s): ([float(v) for v in (x, y, z)], t) for s, x, y, z, t in re.findall(
                r'linegraph: label (\d+) at (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) screen -?[\d.]+ -?[\d.]+ text \[(.*?)\]\r?\n', body.group(1))}
            for slot, (owner, x, z) in enumerate(ALL, 1):
                if slot not in labels:
                    bad(f'eye {k}: no label drawn for run {slot}')
                    continue
                at, shown = labels[slot]
                off = max(abs(at[0] - x), abs(at[1] - e[1]), abs(at[2] - z))
                worst = max(worst, off)
                graded += 1
                if off > 0.5:
                    bad(f'eye {k} run {slot}: the label sits at {at}, the line\'s closest point to the eye is ({x}, {e[1]:.3f}, {z})')
                want = f'{slot} ' + (owner if len(owner) <= 18 else owner[:18] + '..')
                if shown.replace('^^', '^') != want:
                    bad(f'eye {k} run {slot}: label text {shown!r}, wanted {want!r}')
        # Looking along the lines.
        width, height = (int(v) for v in arm.split('x'))
        ahead = {}
        for k, ey in enumerate(ALONG):
            body = re.search(r'P620 along%d\b(.*?)(?=P620 |UIGALLERY FINISHED|$)' % k, text, re.S)
            eye = body and re.search(r'linegraph: eye (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', body.group(1))
            if not eye:
                bad(f'along {k}: no status after the move')
                continue
            e = [float(v) for v in eye.groups()]
            if abs(e[0] - RUNS[0][1]) > 0.5 or abs(e[1] - ey) > 0.5:
                bad(f'along {k}: setpos left the eye at {e[:2]}')
                continue
            rows = {int(s): [float(v) for v in rest] for s, *rest in re.findall(
                r'linegraph: label (\d+) at (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) screen (-?[\d.]+) (-?[\d.]+) text', body.group(1))}
            for slot, (owner, x, z) in enumerate(ALL, 1):
                if slot not in rows:
                    bad(f'along {k}: no label drawn for run {slot}')
                    continue
                wx, wy, wz, sx, sy = rows[slot]
                if abs(wx - x) > 0.5 or abs(wz - z) > 0.5:
                    bad(f'along {k} run {slot}: the label at ({wx}, {wy}, {wz}) is not on its line (x {x}, z {z})')
                if not (0.02 * width - 1 <= sx <= 0.98 * width + 1 and 0.06 * height <= sy <= 0.86 * height + 1):
                    bad(f'along {k} run {slot}: the label is at {sx:g}, {sy:g} on a {width}x{height} screen, outside the label area')
                if wy <= e[1]:
                    bad(f'along {k} run {slot}: the label is {e[1] - wy:.1f} u behind the eye')
                ahead.setdefault(slot, []).append(wy - e[1])
                if slot == 1 and (abs(sx - width / 2) > 3 or not 0.86 * height - 3 <= sy <= 0.86 * height + 1):
                    bad(f'along {k}: the line under the eye is labelled at {sx:g}, {sy:g}, wanted {width / 2:g}, {0.86 * height:g}')
        spread = {slot: max(v) - min(v) for slot, v in ahead.items() if len(v) == len(ALONG)}
        print(f'{arm}: looking along the lines, {len(spread)} of {len(ALL)} labels at all {len(ALONG)} eyes; '
              f'distance ahead of the eye {({k: round(min(v), 1) for k, v in ahead.items()})}, '
              f'its spread across the eyes {({k: round(v, 2) for k, v in spread.items()})} u')
        if len(spread) != len(ALL):
            bad(f'{len(spread)} labels were on screen at every eye along the lines, {len(ALL)} wanted')
        for slot, v in spread.items():
            if v > 1.5:
                bad(f'along: run {slot}\'s label moved {v:.2f} u against the eye between eyes: it hopped')
        print(f'{arm}: {graded} labels graded of {len(EYES)} eye positions x {len(ALL)} runs; '
              f'worst distance from the true closest point {worst:.3f} u')
        if graded != len(EYES) * len(ALL):
            bad(f'{graded} labels were graded, {len(EYES) * len(ALL)} were wanted')
    return errors


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')    # names, on any console
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
    G.SHOTS = ('names_world', 'names_along', 'names_panel', 'names_console')
    G.SHOTS_1080 = ()
    rig = G.run(a)
    errors = grade(rig)
    for error in errors:
        print('FAIL', error)
    print('Names rig', rig)
    print('Names failures:', len(errors))
    raise SystemExit(bool(errors))
