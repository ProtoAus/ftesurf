#!/usr/bin/env python3
"""Patch 610: the strafe trainer, the run graphs and the list thumb. Look, and grade.

Built on tools/ui_gallery.py's rig (same isolation: nothing launched from an
install, no owner config or player data). One arm per window size. Each arm:

  thumb     the map picker's list, the longest there is: its thumb's rectangle
            (`ui_cursor`) at rest, held and dragged 120 px, and dragged past
            the end.
  trainer   a driven jump in zero gravity. `+right`/`+left` turn at exactly
            cl_yawspeed, so every strafe has an authored rate and the
            trainer's own `trainer:` lines are graded against it
            (cfg/test/p462trn.cfg is the full measuring arm).
  graphs    three synthetic runs of a made-up map (46-53 s, ramps, one with a
            retry) loaded into board line slots with `scores lineat`: the HUD
            graph, the comparison panel, its cursor, its zoom, a replay's
            playhead, and a real click on each of the three switches that take
            the HUD graph off screen.

--legacy sends only what a pre-610 csprogs knows, for a "before" rig; the same
arm without it must FAIL on such a build. --perf prints QC time per frame from
profile_csqc windows instead. Shots are evidence of the look, at hud_scale's
size and at text sizes 20 and 12; the grade reads what the subject printed.
"""
import argparse
import math
from pathlib import Path
import random
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_gallery as G  # noqa: E402

RUNS = (('Lex', 11, 46.2, None), ('kitsune', 23, 48.9, None), ('moonwalk', 37, 53.4, 21.0))
SHOTS = ('thumb_top', 'hud_plain', 'trainer', 'trainer_compact', 'graph_hud', 'graph_panel', 'graph_hover')
# Text sizes off hud_scale's own: 20 px is what the owner runs the trainer at.
SIZED = ('trainer_20', 'trainer_12', 'graph_hud_20', 'graph_hud_12')
NEW_SHOTS = ('thumb_drag', 'thumb_end', 'graph_zoom', 'graph_one', 'graph_hud_both', 'board_graphs',
             'graph_hud_off', 'hudedit_graph', 'graph_replay', 'graph_replay_panel', 'graph_replay_panel2')
THUMB_DRAG = 120                # pixels the thumb is dragged down, and must follow


def synth_run(owner, seed, total, retry_at):
    """A plausible surf run as FTESURF-REC 4 text: speed builds ramp by ramp."""
    rnd = random.Random(seed)
    tick, g = 0.015, 800.0
    n = round(total / tick)
    joins = [0.0, 0.07, 0.16, 0.25, 0.37, 0.48, 0.60, 0.71, 0.82, 0.92, 1.0]
    gain = [rnd.uniform(140, 330) for _ in joins]
    loss = [rnd.uniform(0.04, 0.13) for _ in joins]
    head = ['FTESURF-REC 4', 'map ' + G.MAP + '.map', 'track 0', 'leg 0', 'startseg 0', 'tickrate 0.015',
            'movetickrate 0.015', 'owner ' + owner, 'flags 0', 'pmpin gravity=800', 'begin']
    speed, energy = 290.0, 4200.0
    x = y = 0.0
    heading = 0.0
    k = 0
    zprev = None
    for i in range(n + 1):
        t = i * tick
        u = i / n
        while k + 1 < len(joins) - 1 and u >= joins[k + 1]:
            k += 1
            was = speed
            speed *= 1 - loss[k]                                # the landing on the next ramp
            energy -= (was * was - speed * speed) / (2 * g)     # height is continuous across it
        span = (joins[k + 1] - joins[k]) * total
        # Most of a ramp's gain comes early; a strafe wobble rides on it.
        speed += gain[k] * tick / span * (1.6 - 1.2 * (u - joins[k]) / (joins[k + 1] - joins[k]))
        energy += 14 * tick
        shown = speed + 3 * math.sin(t * 13.0 + seed) + 1.5 * math.sin(t * 31.0)
        z = energy - speed * speed / (2 * g)
        vz = 0.0 if zprev is None else (z - zprev) / tick
        zprev = z
        heading += 0.35 * math.sin(t * 0.9 + seed) * tick
        vx, vy = shown * math.cos(heading), shown * math.sin(heading)
        x += vx * tick
        y += vy * tick
        if retry_at is not None and abs(t - retry_at) < tick / 2:
            head.append('retry %d 1' % i)
        head.append('%.4f %.3f %.3f %.3f %.1f %.1f %.1f 0 %.1f 0 0 0 0 0 0 0 0'
                    % (t, x, y, z, vx, vy, vz, math.degrees(heading)))
    head.append('end %d %d 0 0' % (n, n + 1))
    return '\n'.join(head) + '\n'


def seed(game):
    G_seed(game)
    (game / 'cfg/test').mkdir(parents=True, exist_ok=True)
    for slot, (owner, sd, total, retry) in enumerate(RUNS, 1):
        (game / f'cfg/test/uig_run{slot}.rec').write_text(synth_run(owner, sd, total, retry))


def strafe(side, yaw, ms):
    """One strafe: the key and the turn together, at an authored rate."""
    move = 'moveright' if side == 'R' else 'moveleft'
    turn = 'right' if side == 'R' else 'left'
    return [f'cl_yawspeed {yaw}', f'+{move}', f'+{turn}', f'waitms {ms}', f'-{turn}', f'-{move}']


def click(control):
    """A mouse click on a sui control of whichever cursor panel is up."""
    return [f'hud_edit ui hover {control}', 'hud_edit ui down mouse1', 'waitms 120',
            f'hud_edit ui hover {control}', 'hud_edit ui up mouse1', 'waitms 250']


def config(a, size, port, http_port, native):
    def shot(name, wait=500):
        return [f'waitms {wait}', 'screenshot ' + name, 'waitms 250']

    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             'cl_maxfps 250', 'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0', 'r_fullbright 1',
             f'set pr_enable_profiling {int(a.perf)}',
             'vid_srgb 0', 'v_gamma 1', 'v_contrast 1', 'v_brightness 0',
             'set ui_bootcheck 0', 'set rec_terms 4', 'set run_resume 0', 'set run_prestrafe 0',
             f'set lobby_dir "http://127.0.0.1:{http_port}"', 'name GalleryUser',
             'waitms 1500', 'menu_restart', 'waitms 1200']
    # ---- the list thumb, on the longest list there is: the map picker's.
    lines += ['ui_strip_test screen create', 'waitms 4500', 'echo UIG thumb-top', 'ui_cursor']
    lines += shot('thumb_top', 300)
    if not a.legacy:
        # Held in its middle and moved: it must stay under the cursor, then stop at the end.
        lines += ['ui_hover @cs_listvbar', 'ui_mouse down', 'waitms 150', f'ui_hover @cs_listvbar 0 {THUMB_DRAG}',
                  'waitms 300', 'echo UIG thumb-drag', 'ui_cursor'] + shot('thumb_drag', 200)
        lines += ['ui_hover @cs_listvbar 0 5000', 'waitms 300', 'echo UIG thumb-end', 'ui_cursor']
        lines += shot('thumb_end', 200) + ['ui_mouse up', 'waitms 200']
    lines += ['echo UIG thumb-done', 'ui_close', 'waitms 300',
             f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
             f'set hud_scale {a.hud_scale}', 'set rec_terms 4', 'set hud_mapinfo_timeleft 0',
             'set ui_native_scores 0', 'set hud_linegraph 1', 'set hud_lines_board 1',
             'seta hud_trainer_x 0.28', 'seta hud_trainer_y 0.27']
    lines += shot('hud_plain', 800)

    # ---- the trainer: speed first (unmeasured), then a jump's worth of strafes.
    lines += ['hud_trainer 0'] + strafe('R', 330, 1500) + ['waitms 200', 'hud_trainer_trace 1',
              'hud_trainer_rows 6', 'hud_trainer 1', 'waitms 250', 'developer 1', 'log_developer 1']
    lines += strafe('L', 330, 300) + strafe('R', 300, 280) + strafe('L', 420, 260)
    # The flick 60 ms before the key swap: the next strafe reads late.
    lines += ['cl_yawspeed 300', '+moveright', '+right', 'waitms 260', '-right', '+left', 'waitms 60',
              '-moveright', '+moveleft', 'waitms 280', '-left', '-moveleft']
    lines += strafe('R', 180, 300) + strafe('L', 290, 320)
    lines += ['developer 0', 'log_developer 0'] + shot('trainer', 150)
    if a.perf:
        return '\n'.join(lines + perf_tail(a)) + '\n'
    if not a.legacy:
        lines += ['set hud_trainer_size 20'] + shot('trainer_20', 300)
        lines += ['set hud_trainer_size 12'] + shot('trainer_12', 300) + ['set hud_trainer_size 0']
    lines += ['hud_trainer_trace 0', 'hud_trainer_rows 0'] + shot('trainer_compact', 300)
    lines += ['hud_trainer 0', 'hud_trainer_trace 1', 'hud_trainer_rows 6', 'waitms 200']

    # ---- the graphs.
    for slot in range(1, len(RUNS) + 1):
        lines += [f'scores lineat {slot} cfg/test/uig_run{slot}.rec']
    lines += ['waitms 4000', 'scores lines', 'echo UIG hud', 'linegraph status'] + shot('graph_hud', 600)
    lines += ['linegraph', 'waitms 800', 'linegraph cursor 5 5'] + shot('graph_panel', 500)
    lines += ['linegraph cursorat 21.5', 'waitms 200', 'echo UIG hover', 'linegraph status'] + shot('graph_hover', 300)
    if a.legacy:
        lines += ['linegraph close', 'waitms 200']
    else:
        # The view: 18-30 s of 53.4. The cursor's time must follow it.
        lines += ['linegraph zoom 18 30', 'waitms 400', 'linegraph cursorat 24', 'waitms 200',
                  'echo UIG zoom', 'linegraph status'] + shot('graph_zoom', 300)
        lines += ['linegraph zoom', 'waitms 300', 'echo UIG fit', 'linegraph status']
        # One run's chip off: its curves go, the others stay.
        lines += click('lg_slot2') + ['linegraph cursorat 21.5'] + shot('graph_one', 300)
        lines += click('lg_slot2')
        # Switch 1 of 3, the panel's chip: off, and back.
        lines += click('lg_hud') + ['echo UIG chip-off', 'hud_linegraph'] + click('lg_hud')
        lines += ['echo UIG chip-on', 'hud_linegraph'] + click('lg_close')
        lines += ['set hud_linegraph_plots 3', 'waitms 300', 'echo UIG both', 'linegraph status']
        lines += shot('graph_hud_both', 400)
        lines += ['set hud_linegraph_size 20'] + shot('graph_hud_20', 400)
        lines += ['set hud_linegraph_size 12'] + shot('graph_hud_12', 400)
        lines += ['set hud_linegraph_size 0', 'set hud_linegraph_plots 1']
        # Switch 2, the board's chip, beside the LINE boxes that raise the graph.
        lines += ['scores tab local', 'scores open'] + shot('board_graphs', 1200)
        lines += click('sb_hudgraph') + ['echo UIG board-off', 'hud_linegraph', 'scores close', 'waitms 400',
                  'linegraph status'] + shot('graph_hud_off', 300)
        # Switch 3, the HUD editor's row: back on, with its options open.
        lines += ['set hud_edit_panel_x 0.05', 'set hud_edit_panel_y 0.08', 'hud_edit on', 'waitms 700']
        lines += click('he_on_graph') + ['echo UIG edit-on', 'hud_linegraph'] + click('he_sel_graph')
        # Off the name chip, or its tooltip covers the pane it opened.
        lines += ['hud_edit ui hover he_done'] + shot('hudedit_graph', 600) + ['hud_edit off', 'waitms 300']
        # A replay beside the board lines: slot 0, and its playhead on the HUD graph.
        lines += ['set hud_watch_path 1', 'replay cfg/test/uig_run1.rec', 'waitms 3000', 'replay pause',
                  'replay seek 20', 'waitms 800', 'echo UIG replay', 'linegraph status']
        lines += shot('graph_replay', 300)
        # The playhead as ink: the panel's opaque plots at two replay clocks.
        lines += ['linegraph', 'waitms 900', 'linegraph cursor 5 5', 'echo UIG replay-panel', 'linegraph status']
        lines += shot('graph_replay_panel', 300) + ['replay seek 35'] + shot('graph_replay_panel2', 900)
        lines += ['linegraph close', 'replay stop', 'waitms 400']
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def perf_tail(a):
    """QC time per function over fixed windows: the trainer, the HUD graph, the panel."""
    def window(mark, ms=5000):
        return ['profile_csqc', f'waitms {ms}', f'echo UIG prof-{mark}', 'profile_csqc', 'echo UIG prof-end']

    lines = window('trainer') + ['hud_trainer 0', 'waitms 200'] + window('plain')
    for slot in range(1, len(RUNS) + 1):
        lines += [f'scores lineat {slot} cfg/test/uig_run{slot}.rec']
    lines += ['waitms 4000', 'scores lines'] + window('hud')
    if not a.legacy:
        lines += ['set hud_linegraph_plots 3', 'waitms 300'] + window('hudboth') + ['set hud_linegraph_plots 1']
    lines += ['linegraph', 'waitms 800', 'linegraph cursorat 21.5', 'waitms 200'] + window('panel')
    return lines + ['linegraph close', 'scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']


def element_after(text, mark, name):
    """[x, y, w, h] of a sui control as `ui_cursor` printed it after `echo UIG <mark>`."""
    m = re.search(r'UIG ' + re.escape(mark) + r'\b(.*?)UIG ', text, re.S)
    r = m and re.search(r'ui_element \d+ \[' + re.escape(name) + r'\] ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)', m.group(1))
    return r and [float(v) for v in r.groups()]


PROFILED = ('CSQC_UpdateView', 'LineGraph_Draw', 'LineGraph_Plot', 'LineGraph_Curves', 'LineGraph_Simplify',
            'LineGraph_Prepare', 'Trn_Draw', 'Trn_Timeline', '_sui_round_draw', 'Line_Emit')


def profile(rig):
    """Per-frame QC time in each `--perf` window, from profile_csqc's table.

    The table has ops and seconds, not calls. Rewind_Waiting and
    Online_ReplayState are each one op called once a frame, so their ops are the
    window's frames; when the two disagree the window is not counted. The
    times are the profiler's, inflated: they compare builds, they are not a cost.
    """
    errors = []
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        text = next((rig / arm / 'ftesurf/logs').glob('gallery*.log')).read_text(errors='replace')
        windows = re.findall(r'UIG prof-(\S+)(.*?)UIG prof-end', text, re.S)
        if not windows:
            errors.append(f'{arm}: no profile window in the log')
        for mark, body in windows:
            rows = {m.group(4): (int(m.group(1)), float(m.group(2)), float(m.group(3)))
                    for m in re.finditer(r'(\d+)\s+([\d.]+)\s+([\d.]+): (\S+)\s*$', body, re.M)}
            frames = rows.get('Rewind_Waiting', (0,))[0]
            if not frames or frames != rows.get('Online_ReplayState', (0,))[0]:
                errors.append(f'{arm} {mark}: the two frame counters disagree, window not counted')
                continue
            print(f'{arm} {mark}: {frames} frames')
            for name in PROFILED:
                if name in rows:
                    ops, own, total = rows[name]
                    print(f'   {name:20s} {total / frames * 1e6:8.1f} us/frame   self {own / frames * 1e6:8.1f}'
                          f'   {ops / frames:8.0f} ops/frame')
    return errors


def status_after(text, mark):
    """The three `linegraph status` lines printed after `echo UIG <mark>`."""
    m = re.search(r'UIG ' + re.escape(mark) + r'\b(.*?)(?=UIG |UIGALLERY FINISHED)', text, re.S)
    if not m:
        return None
    body = m.group(1)
    a = re.search(r'linegraph: open (\d) cursor ([\d.]+) duration ([\d.]+) build (\d+)', body)
    b = re.search(r'linegraph: view ([\d.-]+) ([\d.-]+) fit (\d) drawn ([\d.-]+) ([\d.-]+) ok (\d) hud (\d)', body)
    c = re.search(r'linegraph: speed ([\d.e+-]+) ([\d.e+-]+) valid (\d) energy ([\d.e+-]+) ([\d.e+-]+) valid (\d)', body)
    d = re.search(r'linegraph: playhead ([\d.-]+) runs (\d+)', body)
    v = re.search(r'linegraph: vertices (\d+) (\d+)', body)
    r = re.search(r'linegraph: plots ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)', body)
    cv = re.search(r'"hud_linegraph" is "(\d)"', body)
    return {'a': a and [float(x) for x in a.groups()], 'b': b and [float(x) for x in b.groups()],
            'c': c and [float(x) for x in c.groups()], 'd': d and [float(x) for x in d.groups()],
            'v': v and [int(x) for x in v.groups()], 'r': r and [float(x) for x in r.groups()],
            'cvar': cv and int(cv.group(1))}


def differing(root, a, b, box=None, threshold=24):
    """(pixels, columns) of two shots that differ by more than `threshold`, inside `box`
    (x0, y0, x1, y1). A column counts from 12 such pixels; its x is the screenshot's."""
    from PIL import Image, ImageChops
    shots = [next((root / 'ftesurf/screenshots').glob(n + '.*')) for n in (a, b)]
    ims = [Image.open(s).convert('RGB') for s in shots]
    box = tuple(int(v) for v in box) if box else (0, 0) + ims[0].size
    d = ImageChops.difference(ims[0].crop(box), ims[1].crop(box)).convert('L')
    px, (w, h) = d.load(), d.size
    cols = [sum(1 for y in range(h) if px[x, y] > threshold) for x in range(w)]
    return sum(cols), [box[0] + x for x, n in enumerate(cols) if n >= 12]


def grade(rig, legacy):
    errors = G.grade(rig)
    longest = max(r[2] for r in RUNS)
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        logs = list((rig / arm / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')

        def bad(msg):
            errors.append(f'{arm}: {msg}')

        # The subject's own lines: the strafes it closed and the lines it built.
        strafes = re.findall(r'trainer: ([LR]) dur (\d+)ms graded (\d+)ms q ([\d.-]+) rate ([\d.]+)', text)
        if len(strafes) < 6:
            bad(f'{len(strafes)} trainer reports, wanted 6+ (the drive did not act)')
        elif not any(float(s[3]) >= 0.9 for s in strafes) or not any(0 <= float(s[3]) < 0.84 for s in strafes):
            bad(f'the driven strafes do not span good and poor grades: {[s[3] for s in strafes]}')
        for slot in range(1, len(RUNS) + 1):
            if f'line {slot} drawn' not in text:
                bad(f'board line {slot} never built')

        # The map list's thumb. In proportion it is a few pixels (the legacy rig
        # prints that); it now keeps four gutter widths and tracks a drag 1:1.
        bar, box = element_after(text, 'thumb-top', 'cs_listvbar'), element_after(text, 'thumb-top', 'cs_list')
        if not bar or not box:
            bad(f'the map list or its thumb was not on screen: {box} {bar}')
        elif box[3] < bar[2] * 2:
            # 640x480: the picker's filters and lobby cards leave the list no height
            # at all. Nothing to hold, so nothing to grade -- and not a pass either.
            print(f'{arm}: NOT GRADED thumb: the map list is {box[3]:.0f} px tall at this window size')
        elif legacy:
            print(f'{arm}: thumb before the patch: {bar[3]:.1f} px of a {box[3]:.0f} px list')
        else:
            floor_px = min(box[3] * 0.5, bar[2] * 4)
            if abs(bar[3] - floor_px) > 0.5 or abs(bar[1] - box[1]) > 0.5:
                bad(f'thumb at the top: wanted {floor_px} px tall at y {box[1]}, read {bar}')
            # It ends up where the cursor took it, as far as its travel goes. (Read 300 ms
            # on: the drag corrects by cursor minus grabbed point each frame, so this
            # cannot tell the right gain from a near one. It tells following from not.)
            want = min(THUMB_DRAG, box[3] - bar[3])
            drag = element_after(text, 'thumb-drag', 'cs_listvbar')
            if not drag or abs(drag[1] - bar[1] - want) > 1.5:
                bad(f'thumb dragged {THUMB_DRAG} px moved {drag and drag[1] - bar[1]}, wanted {want}')
            end = element_after(text, 'thumb-end', 'cs_listvbar')
            if not end or abs(end[1] + end[3] - box[1] - box[3]) > 1:
                bad(f'thumb dragged past the end stops at {end}, list bottom {box[1] + box[3]}')
        if legacy:
            continue

        s = status_after(text, 'hud')
        if not s or not s['b'] or not s['c']:
            bad('no status after the HUD graph came up')
            continue
        if s['b'][5:] != [1, 1] or s['b'][2] != 1:
            bad(f'HUD graph: wanted fit 1 ok 1 hud 1, got {s["b"]}')
        # `hud` and `ok` are set before a curve is emitted; the vertices are what was drawn.
        if not s['v'] or s['v'][0] < 30 or s['v'][1] != 0:
            bad(f'HUD graph: wanted 30+ speed vertices and no energy plot, drew {s["v"]}')
        if abs(s['b'][1] - longest) > 0.05 or s['b'][0] != 0:
            bad(f'HUD graph view {s["b"][:2]} is not the whole {longest}s run')
        if s['c'][2] != 1 or not (s['c'][0] <= 290 and s['c'][1] >= 1500):
            bad(f'speed range {s["c"][:3]} does not hold the runs (about 290 to 1900 u/s)')
        if s['c'][5] != 1:
            bad('energy range invalid with three recorded-gravity runs')

        s = status_after(text, 'hover')
        if not s or not s['a'] or abs(s['a'][1] - 21.5) > 0.2:
            bad(f'cursor at 21.5 s read {s and s["a"]}')
        if not s or not s['v'] or min(s['v']) < 60:
            bad(f'panel: wanted 60+ vertices on each plot, drew {s and s["v"]}')
        plots = s and s['r']
        s = status_after(text, 'zoom')
        if not s or not s['b']:
            bad('no status after zoom')
        else:
            if [round(v, 2) for v in s['b'][:2]] != [18.0, 30.0] or s['b'][2] != 0:
                bad(f'zoom 18 30 gave view {s["b"][:3]}')
            if [round(v, 2) for v in s['b'][3:5]] != [18.0, 30.0] or s['b'][5] != 1:
                bad(f'the drawn buffer is not of the zoomed view: {s["b"][3:6]}')
            if abs(s['a'][1] - 24) > 0.1:
                bad(f'cursor at 24 s in the zoomed view read {s["a"][1]}')
            if not s['v'] or min(s['v']) < 30:
                bad(f'zoomed panel: wanted 30+ vertices on each plot, drew {s["v"]}')
            # A 12 s window cannot span what the whole run spans.
            full = status_after(text, 'hud')['c']
            if not (s['c'][1] - s['c'][0] < full[1] - full[0]):
                bad(f'zoomed speed range {s["c"][:2]} is no narrower than the whole run {full[:2]}')
        s = status_after(text, 'fit')
        if not s or not s['b'] or s['b'][2] != 1 or abs(s['b'][1] - longest) > 0.05:
            bad(f'bare zoom did not return the whole run: {s and s["b"]}')
        for mark, want in (('chip-off', 0), ('chip-on', 1), ('board-off', 0), ('edit-on', 1)):
            s = status_after(text, mark)
            if not s or s['cvar'] != want:
                bad(f'{mark}: hud_linegraph wanted {want}, read {s and s["cvar"]}')
        s = status_after(text, 'both')
        if not s or not s['b'] or s['b'][6] != 1:
            bad('HUD graph not drawn with both plots asked for')
        elif not s['v'] or min(s['v']) < 30:
            bad(f'HUD graph with both plots: wanted 30+ vertices on each, drew {s["v"]}')
        s = status_after(text, 'board-off')
        if not s or not s['b'] or s['b'][6] != 0:
            bad(f'HUD graph still drawn (or no status) after the board chip switched it off: {s and s["b"]}')
        s = status_after(text, 'hud')
        if not s['d'] or s['d'] != [-1, len(RUNS)]:
            bad(f'before any replay: wanted playhead -1 and {len(RUNS)} runs, read {s["d"]}')
        s = status_after(text, 'replay')
        if not s or not s['d'] or abs(s['d'][0] - 20) > 0.1 or s['d'][1] != len(RUNS) + 1:
            bad(f'replay paused at 20 s beside the lines: read {s and s["d"]}')
        elif s['b'][6] != 1:
            bad('HUD graph not drawn while the replay is open')

        # INK, at the one size these rectangles were measured for. A status line says a
        # function was reached; these say something was drawn where it should be.
        if arm == '1920x1080' and plots:
            root = rig / arm
            x0, y0, pw, ph = plots

            def x_at(t):
                return x0 + t / longest * pw

            # The trainer's panel, against the HUD before it was switched on.
            n, _ = differing(root, 'hud_plain', 'trainer', (382, 292, 694, 600))
            if n < 50000:
                bad(f'trainer: {n} pixels of its 312x308 px place differ from the bare HUD, wanted 50000+')
            # The cursor: its line at 21.5 s and the card beside it.
            n, cols = differing(root, 'graph_panel', 'graph_hover', (x0, y0, x0 + pw, y0 + ph))
            if n < 2500 or not any(abs(c - x_at(21.5)) <= 3 for c in cols):
                bad(f'cursor ink: {n} pixels changed, columns {cols[:6]}..., wanted 2500+ and one at x {x_at(21.5):.0f}')
            # The replay's playhead: between its clock at 20 s and at 35 s two thin bands move.
            n, cols = differing(root, 'graph_replay_panel', 'graph_replay_panel2', (x0, y0, x0 + pw, y0 + ph))
            near = [sum(1 for c in cols if abs(c - x_at(t)) <= 8) for t in (20, 35)]
            stray = [c for c in cols if min(abs(c - x_at(20)), abs(c - x_at(35))) > 8]
            print(f'{arm}: playhead ink: {len(cols)} changed columns, {near} at x {x_at(20):.0f} and {x_at(35):.0f}, {len(stray)} elsewhere')
            if min(near) < 1 or len(stray) > 4:
                bad(f'playhead ink: changed columns {cols[:12]} are not two bands at {x_at(20):.0f} and {x_at(35):.0f}')
            s = status_after(text, 'replay-panel')
            if not s or not s['d'] or abs(s['d'][0] - 20) > 0.1 or not s['a'] or s['a'][0] != 1:
                bad(f'replay with the panel open: {s and (s["a"], s["d"])}')

        # The trainer's own measurement, against the rates the drive authored
        # (cfg/test/p462trn.cfg is the full arm). A strafe's first tick is partial,
        # so a rate reads a few percent low.
        for i, yaw in ((0, 330), (1, 300), (2, 420), (5, 180)):
            if i < len(strafes) and not 0.90 * yaw <= float(strafes[i][4]) <= 1.02 * yaw:
                bad(f'strafe {i + 1}: rate {strafes[i][4]} against the authored {yaw}')
        late = re.findall(r'trainer: L dur \d+ms graded \d+ms q [\d.-]+ rate [\d.]+ ideal [\d.]+ sync \+(\d+)ms', text)
        if not any(45 <= int(v) <= 90 for v in late):
            bad(f'the flick-first strafe did not read 45-90 ms late: {late}')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path)
    p.add_argument('--server', type=Path)
    p.add_argument('--plugins', type=Path)
    p.add_argument('--qc-artifacts', type=Path)
    p.add_argument('--library', type=Path, help='an install gamedir to COPY map tables from (optional)')
    p.add_argument('--out', type=Path, help='owned task-root output directory')
    p.add_argument('--sizes', nargs='+', type=G.size_arg, default=[(1920, 1080)], metavar='WxH')
    p.add_argument('--against', type=Path, help='another rig (or one arm of one) to pair every shot with')
    p.add_argument('--hud-scale', type=float, default=2)
    p.add_argument('--renderer', choices=('gl', 'd3d11', 'vk'), default='gl')
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--legacy', action='store_true', help='only the commands a pre-patch csprogs has')
    p.add_argument('--perf', action='store_true', help='profile_csqc windows instead of the shots: QC time per frame')
    p.add_argument('--grade', type=Path)
    a = p.parse_args()
    G_seed = G.seed_runs
    G.seed_runs = seed
    G.config = config
    G.SHOTS = SHOTS + (() if a.legacy else NEW_SHOTS + SIZED)
    if a.perf:
        G.SHOTS = ('thumb_top', 'hud_plain', 'trainer')
    G.SHOTS_1080 = ()
    if not a.grade:
        for need in ('engine', 'server', 'qc_artifacts', 'out'):
            if getattr(a, need) is None:
                p.error('--' + need.replace('_', '-') + ' is required for a run')
        if a.plugins is None:
            a.plugins = Path('nonexistent-no-plugin')
    rig = a.grade or G.run(a)
    errors = G.grade(rig) + profile(rig) if a.perf else grade(rig, a.legacy)
    if a.against:
        G.sheet(rig, a.against)
    for error in errors:
        print('FAIL', error)
    print('Graphs rig', rig)
    print('Graphs failures:', len(errors))
    raise SystemExit(bool(errors))
