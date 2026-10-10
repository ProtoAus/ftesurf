#!/usr/bin/env python3
"""Patch 622: the player's own run on the run graphs, as it happens. Look, and grade.

Built on tools/ui_gallery.py's rig: its map has no floor (the body drifts at whatever speed it
was left with) and a start box, so a run can be started and left to coast. Two authored runs of
6 s are ticked; the live one is set against them.

Graded on `linegraph status`, whose `timer` line is the server's own stats and whose `live` line
is what the graph made of them:
  idle      nothing live before a run
  run       out of the start box: the live run is on the graph from the run's start, its head a
            few ticks behind the timer's clock, coasting at one speed, every sample folded
  off       hud_linegraph_live 0 takes it off, and the plot's white ink with it
  stretch   past the ticked runs' 6 s the span has grown by quarters of it and still holds the head
  up        put 400 u higher its energy leaves the energy axis, which the HUD is not drawing:
            the curves are cut again once for it, not once a frame
  kept      back in the start box the run is over: its curve stays and stops growing
  again     the next run starts a new curve from zero
  many      with eight ticked runs a rebuild of the bins takes more than one frame: ticking
            them blanks the graph ("building...", counted), and a rebuild for the live run
            alone does not, because the ticked runs' drawn bins stay up meanwhile
--staged is the other arm: a track of two stages and one ticked run of stage 2. In stage 1 the
live run is not drawn and says why; with a stage 1 run ticked too it is, from the run's start.
Put in the box of stage 2, as a map's teleporter does, that line is still stage 1's and has
stopped (the timer's stats are stage 2's a frame before the trail ends the line); in stage 2
the new line is drawn from the clock the server started the stage at, on the way out of its
box; with a whole run ticked instead, from the run's start.
--plugins is the third: the comparison panel opened over a run in progress with the plugin's
plots. The live rows are one more series, republished as they grow, nothing refused, and past
the ticked runs' end the view is still the whole run (no `fit` chip); then the same panel on
the QC plots.
Pixels: the live curve is the only white ink in the plot, it ends at the head's column, and
there is none with the switch off. The shots are for eyes.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_gallery as G  # noqa: E402

TICK, SECONDS = 0.015, 6.0
START = '-350 -350 40 0 45 0'       # inside the rig's start box
STAGE2 = (0, 100)                   # the second stage's box, x and y from 0 to 100 (--staged)


def synth(owner, base, leg):
    n = round(SECONDS / TICK)
    head = ['FTESURF-REC 4', 'map ' + G.MAP + '.map', 'track 0', f'leg {leg}', f'startseg {max(0, leg - 1)}',
            'tickrate 0.015', 'movetickrate 0.015', 'owner ' + owner, 'flags 0', 'pmpin gravity=800', 'begin']
    for i in range(n + 1):
        t = i * TICK
        v = base + 40 * math.sin(t * 2)
        head.append('%.4f 3000.000 %.3f 500.000 0.0 %.1f 0.0 0 90.0 0 0 0 0 0 0 0 0' % (t, -900 + 300 * t, v))
    head.append('end %d %d 0 0' % (n, n + 1))
    return '\n'.join(head) + '\n'


def seed(game, staged):
    G_SEED(game)
    (game / 'cfg/test').mkdir(parents=True, exist_ok=True)
    (game / 'cfg/test/p622_a.rec').write_text(synth('Ticked One', 260, 0))
    (game / 'cfg/test/p622_b.rec').write_text(synth('Ticked Two', 180, 0))
    (game / 'cfg/test/p622_s1.rec').write_text(synth('Stage One', 240, 1))
    (game / 'cfg/test/p622_s2.rec').write_text(synth('Stage Two', 220, 2))
    if staged:
        lo, hi = STAGE2
        box = {'points': [[lo, lo], [hi, lo], [hi, hi], [lo, hi]], 'bottom': 0, 'height': 100}
        for name in (G.MAP, G.MAP + '.map'):
            path = game / f'maps/zones/local/{name}.json'
            zones = json.loads(path.read_text())
            zones['tracks']['main']['zones']['segments'].append({'checkpoints': [{'regions': [box]}]})
            path.write_text(json.dumps(zones))


def mark(name):
    return ['waitms 150', 'echo P622 ' + name, 'linegraph status', 'waitms 50']


def shot(name):
    return ['waitms 200', 'screenshot ' + name, 'waitms 250']


def leave():
    """Out of the start box under the body's own power: a strafe, then coasting."""
    return ['cl_yawspeed 240', '+moveright', '+right', 'waitms 1200', '-right', '-moveright']


def preamble(a, port, http_port):
    return ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
            'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0', 'cl_maxfps 250',
            'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0', 'r_fullbright 1', 'vid_srgb 0',
            'v_gamma 1', 'v_contrast 1', 'v_brightness 0', 'set ui_bootcheck 0', 'set rec_terms 4',
            'set run_resume 0', 'set run_prestrafe 0', f'set lobby_dir "http://127.0.0.1:{http_port}"',
            'name GalleryUser', 'waitms 1500', 'menu_restart', 'waitms 1200', 'ui_close', 'waitms 300',
            f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
            f'set hud_scale {a.hud_scale}', 'set rec_terms 4', 'set hud_mapinfo_timeleft 0',
            'set ui_native_scores 0', 'set hud_linegraph 1', 'set hud_lines_board 1',
            'set hud_linegraph_live 1', 'set hud_linegraph_plots 1', 'set hud_trail 1', 'hud_trainer 0']


def config(a, size, port, http_port, native):
    lines = preamble(a, port, http_port)
    lines += ['scores lineat 1 cfg/test/p622_a.rec', 'scores lineat 2 cfg/test/p622_b.rec', 'waitms 4000', 'scores lines']
    lines += mark('idle')
    lines += [f'setpos {START}', 'waitms 1000'] + mark('armed')
    lines += leave() + ['waitms 1000'] + mark('run1a') + ['waitms 2000'] + mark('run1b') + shot('hud_live')
    lines += ['set hud_linegraph_live 0', 'waitms 300'] + mark('off') + shot('hud_off')
    lines += ['set hud_linegraph_live 1', 'waitms 3200'] + mark('run1c') + shot('hud_stretch')
    # Clear of both boxes, 400 u up: the trail breaks and goes on, its energy 400 higher. No
    # status until the mark: the status reads both axes, and an axis just read is not stale.
    lines += ['setpos 200 -200 440 0 45 0', 'waitms 1500'] + mark('up')
    lines += [f'setpos {START}', 'waitms 1200'] + mark('back') + ['waitms 1000'] + mark('back2')
    lines += leave() + ['waitms 1000'] + mark('run2') + shot('hud_again')
    # Eight ticked runs: 3200 samples and the live run's, over the 2048 a frame is given.
    lines += [f'scores lineat {k} cfg/test/p622_a.rec' for k in range(3, 9)] + ['waitms 7000'] + mark('many0')
    lines += ['set hud_linegraph_live 0', 'waitms 400', 'set hud_linegraph_live 1', 'waitms 600'] + mark('many1')
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def config_staged(a, size, port, http_port, native):
    lines = preamble(a, port, http_port)
    lines += ['scores lineat 1 cfg/test/p622_s2.rec', 'waitms 3000', 'scores lines']
    lines += [f'setpos {START}', 'waitms 1000'] + leave() + ['waitms 1200'] + mark('stage1')
    lines += ['scores lineat 2 cfg/test/p622_s1.rec', 'waitms 2500'] + mark('stage1b')
    mid = (STAGE2[0] + STAGE2[1]) / 2
    # Into stage 2's box as a map's teleporter puts you there: the trail stops in the box and a
    # new one opens on the way out, which is when the server starts the stage's clock.
    lines += [f'setpos {mid} {mid} 40 0 45 0', 'waitms 700'] + mark('box2') + ['waitms 400'] + mark('box2b')
    lines += leave() + ['waitms 800'] + mark('stage2') + ['waitms 2000'] + mark('stage2b')
    lines += shot('hud_stage')
    lines += ['scores lines clear', 'waitms 300', 'scores lineat 1 cfg/test/p622_a.rec', 'waitms 3000'] + mark('whole')
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def config_native(a, size, port, http_port, native):
    """The panel open over a run in progress, its plots the plugin's: the live rows are one more
    series, republished as they grow."""
    lines = preamble(a, port, http_port) + ['plug_load ui_imgui', 'waitms 500', 'set ui_native_graphs 1']
    lines += ['scores lineat 1 cfg/test/p622_a.rec', 'scores lineat 2 cfg/test/p622_b.rec', 'waitms 4000', 'scores lines']
    lines += [f'setpos {START}', 'waitms 1000'] + leave() + ['waitms 600']
    lines += ['linegraph', 'waitms 1500', 'linegraph cursor 5 5'] + mark('panel1') + shot('panel_native')
    lines += ['waitms 2000'] + mark('panel2') + ['waitms 2200'] + mark('panel3') + ['linegraph close', 'waitms 300']
    lines += ['set ui_native_graphs 0', 'waitms 300', 'linegraph', 'waitms 1500', 'linegraph cursor 5 5']
    lines += mark('panelqc') + shot('panel_qc') + ['linegraph close', 'waitms 300']
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def grade_native(rig):
    errors = [e for e in G.grade(rig) if 'missing screenshot scores_native' not in e]

    def bad_of(arm):
        return lambda msg: errors.append(f'{arm}: {msg}')

    for arm in sorted(q.name for q in rig.iterdir() if (q / 'ftesurf/logs').is_dir()):
        root = rig / arm
        logs = list((root / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')
        bad = bad_of(arm)
        got = {}
        for name in ('panel1', 'panel2', 'panel3', 'panelqc'):
            m = re.search(r'P622 %s\r?\n(.*?)(?=P622 |UIGALLERY FINISHED|$)' % name, text, re.S)
            body = m.group(1) if m else ''
            nat = re.search(r'linegraph: native drew (\d) refused (\d) revision (\d+) series (\d+)', body)
            px = re.search(r'linegraph: plots pixels (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', body)
            st = status(text, name)
            if not (nat and px and st):
                bad(f'{name}: no status (the drive did not act)')
                got = None
                break
            got[name] = (st, [int(v) for v in nat.groups()], [float(v) for v in px.groups()])
        if not got:
            continue
        (s1, n1, px1), (s2, n2, _), (s3, n3, px3) = got['panel1'], got['panel2'], got['panelqc']
        # Past the ticked runs' 6 s the span is rounded on ahead of the head; the plugin's whole
        # view ends where its rows do. It is still the whole run: no `fit` chip.
        past = got['panel3'][0]
        print(f'{arm}: past the ticked runs: head {past.get("head")} span {past.get("span")} '
              f'plugin view to {past.get("view1")} of rows to {past.get("extent")}, zoomed {past.get("zoomed")}')
        if past['slot'] < 9 or past.get('zoomed') is None:
            bad('panel3: no live run, or the build does not print where the plugin\'s rows end')
        elif past['head'] <= SECONDS or past['span'] <= past['head'] or past['zoomed'] != 0 \
                or not -0.01 <= past['head'] - past['extent'] <= 0.6 or abs(past['view1'] - past['extent']) > 0.6:
            bad(f'panel3: wanted the whole run in view past {SECONDS:g} s: head {past["head"]} span {past["span"]} '
                f'view to {past["view1"]} rows to {past["extent"]} zoomed {past["zoomed"]}')
        if s1.get('zoomed') != 0 or s2.get('zoomed') != 0:
            bad(f'the whole run was in view and the panel says zoomed {s1.get("zoomed")} then {s2.get("zoomed")}')
        print(f'{arm}: plugin plots: drew {n1[0]} refused {n1[1]} series {n1[3]}, revision {n1[2]} then {n2[2]} '
              f'as the live head went {s1.get("head")} to {s2.get("head")}; QC plots after: drew {n3[0]}')
        if s1['slot'] < 9 or s2['slot'] < 9 or s3['slot'] < 9:
            bad('the live run was not on the graph with the panel open')
            continue
        if n1[:2] != [1, 0] or n2[:2] != [1, 0] or n1[3] != 3 or n2[3] != 3:
            bad(f'wanted the plugin drawing three series and refusing nothing, read {n1} then {n2}')
        if n2[2] <= n1[2] or s2['head'] - s1['head'] < 1.5:
            bad(f'wanted new revisions as the run grew: revision {n1[2]} then {n2[2]}, head {s1["head"]} then {s2["head"]}')
        if n3[0] != 0:
            bad(f'with ui_native_graphs 0 the plugin still drew: {n3}')
        for name, (x, y, w, h) in (('panel_native', px1), ('panel_qc', px3)):
            cols, count = white(root, name, tuple(int(v) for v in (x, y, x + w, y + h)))
            # The live curve is one unbroken stretch of columns from the left; a label is not.
            best = run = 0
            for i, c in enumerate(cols):
                run = run + 1 if i and c == cols[i - 1] + 1 else 1
                best = max(best, run)
            print(f'{arm}: {name}: {count} white px in the plots; the longest unbroken stretch of '
                  f'columns holding any is {best} of {w:.0f}')
            if best < 0.2 * w:
                bad(f'{name}: no white curve across the plots: the longest stretch is {best} columns of {w:.0f}')
    return errors


def status(text, name):
    m = re.search(r'P622 %s\r?\n(.*?)(?=P622 |UIGALLERY FINISHED|$)' % re.escape(name), text, re.S)
    if not m:
        return None
    body = m.group(1)
    live = re.search(r'linegraph: live (-?\d+) why (\d+)(?: start (-?[\d.]+) leg (\d+) samples (\d+) folded (\d+) head (-?[\d.]+)'
                     r' speed (-?[\d.]+) energy (-?[\d.]+) span (-?[\d.]+) gen (\d+))?', body)
    timer = re.search(r'linegraph: timer state (\d+) seg (\d+) of (\d+) track (\d+) clock (-?[\d.]+) base (-?[\d.]+)', body)
    plot = re.search(r'linegraph: hud plot (-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+) drawn (\d)', body)
    ops = re.search(r'linegraph: liveops rebuilds (\d+) blanks (\d+) curves (\d+) pending (\d)', body)
    view = re.search(r'linegraph: native view (-?[\d.]+) (-?[\d.]+)', body)
    ext = re.search(r'linegraph: native extent (-?[\d.]+) zoomed (\d)', body)
    if not (live and timer and plot):
        return None
    out = {'slot': int(live.group(1)), 'why': int(live.group(2)), 'state': int(timer.group(1)),
           'seg': int(timer.group(2)), 'segs': int(timer.group(3)), 'clock': float(timer.group(5)),
           'base': float(timer.group(6)), 'plot': [float(v) for v in plot.groups()[:4]], 'drawn': int(plot.group(5))}
    if live.group(3) is not None:
        keys = ('start', 'leg', 'samples', 'folded', 'head', 'speed', 'energy', 'span', 'gen')
        out.update(zip(keys, (float(v) for v in live.groups()[2:])))
    if ops:
        out.update(zip(('rebuilds', 'blanks', 'curves', 'pending'), (int(v) for v in ops.groups())))
    if view and ext:
        out.update(view1=float(view.group(2)), extent=float(ext.group(1)), zoomed=int(ext.group(2)))
    return out


def white(root, name, box):
    """Columns of the box holding near-white ink, and how many such pixels."""
    im = Image.open(root / f'ftesurf/screenshots/{name}.png').convert('RGB').crop(box)
    px = im.load()
    cols, count = [], 0
    for x in range(im.size[0]):
        n = sum(1 for y in range(im.size[1]) if min(px[x, y]) >= 215)
        if n:
            cols.append(x)
            count += n
    return cols, count


def marks(rig, names, bad_of):
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        root = rig / arm
        logs = list((root / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')
        bad = bad_of(arm)
        s = {name: status(text, name) for name in names}
        missing = [k for k, v in s.items() if v is None]
        if missing:
            bad(f'no linegraph status after {missing} (the drive did not act, or the build has no live line)')
            continue
        yield arm, root, s, bad


def grade(rig):
    errors = G.grade(rig)

    def bad_of(arm):
        return lambda msg: errors.append(f'{arm}: {msg}')

    names = ('idle', 'armed', 'run1a', 'run1b', 'off', 'run1c', 'up', 'back', 'back2', 'run2', 'many0', 'many1')
    for arm, root, s, bad in marks(rig, names, bad_of):
        if s['idle']['slot'] != -1 or s['idle']['why'] != 2:
            bad(f'idle: wanted no live run (why 2), read slot {s["idle"]["slot"]} why {s["idle"]["why"]}')
        for name in ('run1a', 'run1b', 'run1c', 'run2'):
            r = s[name]
            if r['slot'] < 9 or r['why'] != 0 or r['state'] != 2:
                bad(f'{name}: wanted the live run on the graph with the timer running, read slot {r["slot"]} why {r["why"]} state {r["state"]}')
        if any(s[n]['slot'] < 9 for n in ('run1a', 'run1b', 'run1c', 'back', 'back2', 'run2')):
            bad('the live run was not on the graph at every mark that wants it')
            continue
        a, b, c = s['run1a'], s['run1b'], s['run1c']
        print(f'{arm}: run 1 head {a["head"]:.3f} / {b["head"]:.3f} / {c["head"]:.3f} s against the timer\'s '
              f'{a["clock"]:.3f} / {b["clock"]:.3f} / {c["clock"]:.3f}; speed {a["speed"]:.2f} / {b["speed"]:.2f} / {c["speed"]:.2f}; '
              f'folded {b["folded"]:.0f} of {b["samples"]:.0f}; span {a["span"]:g} then {c["span"]:g}')
        for name, r in (('run1a', a), ('run1b', b), ('run1c', c)):
            if r['start'] != 0 or r['leg'] != 0:
                bad(f'{name}: wanted the run\'s own start (0, leg 0), read start {r["start"]} leg {r["leg"]}')
            # The line is a round trip behind the stat: a tick or two on loopback. Six is the
            # limit, under the sixteen the trail's own shown range may lag by.
            if not -0.02 <= r['clock'] - r['head'] <= 0.09:
                bad(f'{name}: the head is at {r["head"]:.3f} s and the timer at {r["clock"]:.3f}')
            if r['samples'] - r['folded'] > 3:
                bad(f'{name}: {r["folded"]:.0f} of {r["samples"]:.0f} samples are in the drawn bins')
        if not 1.9 <= b['head'] - a['head'] <= 2.7:
            bad(f'run1b: the head moved {b["head"] - a["head"]:.3f} s in about 2.2 s of waiting')
        if abs(a['speed'] - b['speed']) > 1 or abs(b['speed'] - c['speed']) > 1 or a['speed'] < 20:
            bad(f'the body was left to coast and its curve reads {a["speed"]}, {b["speed"]}, {c["speed"]} u/s')
        if a['span'] != SECONDS or b['span'] != SECONDS:
            bad(f'inside the ticked runs the span is theirs ({SECONDS:g} s): read {a["span"]}, {b["span"]}')
        q = SECONDS * 0.25
        if c['head'] <= SECONDS or c['span'] < c['head'] or abs(c['span'] / q - round(c['span'] / q)) > 1e-3 \
                or c['span'] - c['head'] > q + 0.01:
            bad(f'stretch: head {c["head"]:.3f} s, span {c["span"]:g} s; wanted the next quarter of {SECONDS:g} s past the head')
        if s['off']['slot'] != -1 or s['off']['why'] != 1:
            bad(f'off: wanted hud_linegraph_live 0 to take it off (why 1), read slot {s["off"]["slot"]} why {s["off"]["why"]}')
        # The review's two costs, on the subject's own counters. The ticked runs stay up while
        # the bins are rebuilt for the live run alone; and the energy axis, which this HUD does
        # not draw, is not a reason to cut every curve again a frame once the energy leaves it.
        if any('blanks' not in s[n] for n in names):
            bad('the build does not print `liveops` (rebuilds, blank frames, the generation of the curves)')
            continue
        up = s['up']
        seq = [s[n]['rebuilds'] for n in ('armed', 'run1b', 'run1c', 'back', 'run2')]
        m0, m1 = s['many0'], s['many1']
        print(f'{arm}: rebuilds for the live run alone {seq}; put 400 u up: energy {c["energy"]:.1f} then '
              f'{up.get("energy", 0):.1f}, curves cut afresh {up["curves"] - c["curves"]} times in 1.7 s; '
              f'eight ticked runs: blank frames {s["run2"]["blanks"]} then {m0["blanks"]} after ticking six more, '
              f'{m1["blanks"]} after {m1["rebuilds"] - m0["rebuilds"]} rebuilds for the live run alone')
        if not (seq[0] < seq[1] < seq[2] and seq[3] < seq[4]):
            bad(f'wanted a rebuild for the live run at each run start and at the stretch: {seq}')
        # Ticking runs must blank it here, or a rebuild still fits in a frame and the next
        # line measures nothing.
        if m0['blanks'] <= s['run2']['blanks']:
            bad(f'many0: six more ticked runs and the graph was never blank ({m0["blanks"]} frames): '
                f'a rebuild still fits in one frame, so the live rebuilds below show nothing')
        elif m1['rebuilds'] - m0['rebuilds'] < 2 or m1['slot'] < 9:
            bad(f'many1: wanted the live run taken off and put back (two rebuilds of its own): '
                f'{m0["rebuilds"]} then {m1["rebuilds"]}, slot {m1["slot"]}')
        elif m1['blanks'] != m0['blanks']:
            bad(f'many1: the HUD graph went blank for {m1["blanks"] - m0["blanks"]} frames while only the live run changed')
        if up['slot'] < 9 or up['energy'] - c['energy'] < 300:
            bad(f'up: wanted the same run 400 u higher, read slot {up["slot"]} energy {c["energy"]} then {up.get("energy")}')
        elif not 1 <= up['curves'] - c['curves'] <= 12:
            bad(f'up: the curves were cut afresh {up["curves"] - c["curves"]} times in 1.7 s; wanted once or a few')
        k, k2 = s['back'], s['back2']
        if k['state'] == 2 or k['head'] != k2['head'] or k['why'] != 0 or k['gen'] != c['gen']:
            bad(f'kept: back in the start box wanted the same run, still drawn and not growing: '
                f'state {k["state"]} head {k["head"]} then {k2["head"]} gen {k["gen"]} (was {c["gen"]})')
        n = s['run2']
        if n['gen'] != c['gen'] + 1 or not 0.3 <= n['head'] <= 3 or n['start'] != 0:
            bad(f'again: wanted a new run from zero, read gen {n["gen"]} (was {c["gen"]}) head {n["head"]} start {n["start"]}')

        # Pixels: the plot's own rectangle says where, the pixels say what.
        x, y, w, h = b['plot']
        if not b['drawn'] or w < 50:
            bad(f'the HUD graph was not drawn at run1b: {b["plot"]}')
            continue
        box = tuple(int(v) for v in (x, y, x + w, y + h))
        cols, count = white(root, 'hud_live', box)
        offcols, offcount = white(root, 'hud_off', box)
        lo, hi = b['head'] / b['span'] * w, (b['head'] + 1.2) / b['span'] * w
        print(f'{arm}: plot {box}: live white ink {count} px in columns {cols[:1]}..{cols[-1:]} '
              f'(head wanted at {lo:.0f} to {hi:.0f}); with the switch off {offcount} px')
        if count < 150 or not cols or cols[0] > 6 or not lo - 4 <= cols[-1] <= hi + 6:
            bad(f'the live curve\'s ink: {count} px over columns {cols[:1]}..{cols[-1:]}, wanted 150+ from the left edge to {lo:.0f}..{hi:.0f}')
        if offcount:
            bad(f'{offcount} white px in the plot with hud_linegraph_live 0')
    return errors


def grade_staged(rig):
    errors = G.grade(rig)

    def bad_of(arm):
        return lambda msg: errors.append(f'{arm}: {msg}')

    for arm, root, s, bad in marks(rig, ('stage1', 'stage1b', 'box2', 'box2b', 'stage2', 'stage2b', 'whole'), bad_of):
        one, box, two, twob, whole = s['stage1'], s['box2'], s['stage2'], s['stage2b'], s['whole']
        oneb, boxb = s['stage1b'], s['box2b']
        print(f'{arm}: stage 1: seg {one["seg"]} of {one["segs"]}, live {one["slot"]} why {one["why"]}; '
              f'in the box of stage 2: seg {box["seg"]} base {box["base"]:.3f}; out of it: live {two["slot"]} '
              f'start {two.get("start")} leg {two.get("leg")} head {two.get("head")} against base {two["base"]:.3f} '
              f'clock {two["clock"]:.3f}; whole: start {whole.get("start")} leg {whole.get("leg")} head {whole.get("head")}')
        if one['segs'] != 2 or one['seg'] != 0 or one['state'] != 2:
            bad(f'stage1: wanted a run in stage 1 of 2, read seg {one["seg"]} of {one["segs"]} state {one["state"]}')
        if one['slot'] != -1 or one['why'] != 4:
            bad(f'stage1: only a stage 2 run is ticked, so nothing live (why 4): read slot {one["slot"]} why {one["why"]}')
        if box['seg'] != 1:
            bad(f'box2: the body was put in the box of stage 2 and the timer says seg {box["seg"]}')
        # With a stage 1 run ticked the live run is stage 1's, from the run's start. In the box
        # of stage 2 the timer's stats are stage 2's, and that line is still stage 1's: the
        # same line, the same zero, every sample it had, and no longer growing.
        print(f'{arm}: stage 1 ticked too: live {oneb["slot"]} leg {oneb.get("leg")} start {oneb.get("start")} '
              f'samples {oneb.get("samples")} gen {oneb.get("gen")}; in the box of stage 2: live {box["slot"]} '
              f'leg {box.get("leg")} start {box.get("start")} samples {box.get("samples")} gen {box.get("gen")} '
              f'energy {box.get("energy")}, head {box.get("head")} then {boxb.get("head")}')
        if oneb['slot'] < 9 or oneb.get('leg') != 1 or oneb.get('start') != oneb['base']:
            bad(f'stage1b: with a stage 1 run ticked wanted the live run as stage 1 from its base, read slot {oneb["slot"]} '
                f'leg {oneb.get("leg")} start {oneb.get("start")}')
        elif box['slot'] < 9 or box.get('leg') != 1 or box.get('start') != oneb['start'] or box.get('gen') != oneb['gen'] \
                or box['samples'] < oneb['samples'] or abs(box['energy'] - oneb['energy']) > 0.5:
            bad(f'box2: the line the teleport ended is stage 1 and was given away: slot {box["slot"]} '
                f'leg {box.get("leg")} start {box.get("start")} samples {box.get("samples")} (had {oneb["samples"]}) '
                f'gen {box.get("gen")} (was {oneb["gen"]}) energy {box.get("energy")} (was {oneb["energy"]})')
        elif boxb.get('head') != box['head'] or boxb.get('leg') != 1:
            bad(f'box2b: wanted the stopped line unchanged, read head {box["head"]} then {boxb.get("head")} leg {boxb.get("leg")}')
        if two['seg'] != 1 or two['slot'] < 9 or two.get('leg') != 2:
            bad(f'stage2: wanted the live run on the graph as stage 2, read seg {two["seg"]} slot {two["slot"]} leg {two.get("leg")}')
            continue
        # The stage's clock starts on the way out of its box: the server's base moves there,
        # and that is the zero a ticked stage run has.
        if two['base'] <= box['base'] or two['start'] != two['base']:
            bad(f'stage2: the base was {box["base"]:.3f} in the box and {two["base"]:.3f} out of it; the live zero is {two["start"]}')
        if not 0.3 <= two['head'] <= 2.5 or not -0.02 <= two['clock'] - two['start'] - two['head'] <= 0.09:
            bad(f'stage2: head {two["head"]:.3f} s from a zero at {two["start"]:.3f}, the timer at {two["clock"]:.3f}')
        if twob['start'] != two['start'] or not 1.9 <= twob['head'] - two['head'] <= 2.7:
            bad(f'stage2b: start {two["start"]} then {twob["start"]}, head {two["head"]:.3f} then {twob["head"]:.3f}')
        late = whole['clock'] - whole.get('head', -99)
        if whole['slot'] < 9 or whole.get('leg') != 0 or whole.get('start') != 0 or not -0.02 <= late <= 0.09:
            bad(f'whole: with a whole run ticked wanted the start of the run, read leg {whole.get("leg")} '
                f'start {whole.get("start")} head {whole.get("head")} clock {whole["clock"]:.3f}')
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
    p.add_argument('--staged', action='store_true', help='the other arm: two stages, a ticked run of stage 2')
    p.add_argument('--plugins', type=Path, help='a folder holding fteplug_ui_imgui_x64.dll: the third arm, the panel on its plots')
    a = p.parse_args()
    native = bool(a.plugins)
    if not native:
        a.plugins = Path('nonexistent-no-plugin')
    G_SEED = G.seed_runs
    G.seed_runs = lambda game: seed(game, a.staged)
    G.config = config_native if native else config_staged if a.staged else config
    G.SHOTS = ('panel_native', 'panel_qc') if native else ('hud_stage',) if a.staged \
        else ('hud_live', 'hud_off', 'hud_stretch', 'hud_again')
    G.SHOTS_1080 = ()
    rig = G.run(a)
    errors = grade_native(rig) if native else grade_staged(rig) if a.staged else grade(rig)
    for error in errors:
        print('FAIL', error)
    print('Live rig', rig)
    print('Live failures:', len(errors))
    raise SystemExit(bool(errors))
