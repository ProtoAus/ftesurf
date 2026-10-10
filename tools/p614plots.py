#!/usr/bin/env python3
"""Patch 614: the run-graph panel's plots through the ui_imgui plugin (ImPlot). Look, and grade.

Built on tools/ui_gallery.py's rig and tools/p610ui.py's three synthetic runs. One rig per arm:

  native     the engine and plugin under test: the plots are the plugin's. Graded on the panel's own
             `linegraph status` lines (the plugin drew, its series and points, the view it reports,
             the time under the cursor) through a zoom request, a wheel notch each way, a pan, the
             right button, a box, a chip that hides a run and one that picks it out, a replay's
             marker, and `linegraph probe`'s hostile transactions; and on PIXELS: each run's colour
             inside the plots' rectangle, there when drawn and gone when hidden.
             Then one step for each defect the patch's review found (grade_review): a range
             outside the run, notches faster than frames, the wheel and the mouse together, a
             button held when another panel takes the mouse, the owner lost twice and three
             times running, the plugin given up mid-open, and the panel opened by the board's
             chip in a frame the board's native table drew.
             Where the plots' rectangle is under the plugin's 160x120 px the QC plots are wanted
             instead, and read as the other arms' are.
  off        the same binaries with ui_native_graphs 0: the QC plots, the plugin never opened.
             This and the three arms below are graded on the QC plots' own pixels.
  absent     no plugin beside the engine.
  oldplugin  the engine under test with a plugin from before the patch (no plot service).
  oldengine  the plugin under test under an engine from before the patch (no plot builtins).
  cost       frames drawn in fixed windows with the panel up, the two routes alternating, uncapped.

Readings are related to each other, never to a pixel-to-time mapping assumed here: two hovers give
the plot's own scale, and every later step is predicted from that. --renderer and --sizes move the
native arm to d3d11 or vk and to other windows.
"""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_gallery as G  # noqa: E402
import p610ui as P  # noqa: E402

ARMS = ('native', 'off', 'absent', 'oldplugin', 'oldengine', 'cost')
LONGEST = max(r[2] for r in P.RUNS)
# Plot_Series 1..3 (cl_plot.qc), as the screenshot holds them.
COLOURS = {1: (140, 196, 248), 2: (248, 191, 152), 3: (155, 227, 181)}
WHEEL_IN, WHEEL_OUT = 1.25 / 1.5, 1.25      # ImPlot's zoom at the plugin's ZoomRate 0.25
# What each of `linegraph probe`'s cases must print: begin, series, rows, commit, view (-1 not called).
PROBE = {
    'stale-revision': (0, -1, -1, -1, -1), 'seventeen-series': (0, -1, -1, -1, -1),
    'fractional-count': (0, -1, -1, -1, -1), 'unknown-flag': (1, 0, -1, 0, -1),
    'zero-gap': (1, 0, -1, -1, -1), 'colour-out-of-range': (1, 0, -1, -1, -1),
    'no-rows': (1, 1, 0, 0, -1), 'too-many-rows': (1, 1, 0, -1, -1), 'null-time': (1, 1, 0, -1, -1),
    'beyond-vm-memory': (1, 1, 0, -1, -1), 'second-value-not-declared': (1, 1, 0, -1, -1),
    'second-value-missing': (1, 1, 0, -1, -1), 'time-backwards': (1, 1, 0, -1, -1),
    'infinite-value': (1, 1, 0, -1, -1), 'series-missing': (1, 1, 1, 0, -1), 'rows-twice': (1, 1, 0, 0, -1),
    'hidden-mask-too-wide': (-1, -1, -1, -1, 0), 'caption-size-zero': (-1, -1, -1, -1, 0),
    'infinite-mark': (-1, -1, -1, -1, 0), 'value-past-a-billion': (1, 1, 0, -1, -1),
}


def seed(game):
    G_SEED(game)
    (game / 'cfg/test').mkdir(parents=True, exist_ok=True)
    for slot, (owner, sd, total, retry) in enumerate(P.RUNS, 1):
        (game / f'cfg/test/uig_run{slot}.rec').write_text(P.synth_run(owner, sd, total, retry))


def config(a, size, port, http_port, native):
    def shot(name, wait=400):
        return [f'waitms {wait}', 'screenshot ' + name, 'waitms 250']

    def mark(name, wait=350):
        return [f'waitms {wait}', 'echo P614 ' + name, 'linegraph status']

    def at(fx, fy=0.30):
        return [f'linegraph cursorfrac {fx} {fy}']

    arm = a.arm
    loaded = native and arm != 'absent'

    def pmark(name, wait=350):          # ...with the plugin's own counters beside the panel's
        return mark(name, wait) + (['ui_imgui_status'] if loaded else [])
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             f'cl_maxfps {0 if arm == "cost" else 250}', 'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0',
             'r_fullbright 1', 'vid_srgb 0', 'v_gamma 1', 'v_contrast 1', 'v_brightness 0',
             'set ui_bootcheck 0', 'set rec_terms 4', 'set run_resume 0', 'set run_prestrafe 0',
             f'set lobby_dir "http://127.0.0.1:{http_port}"', 'name GalleryUser',
             'waitms 1500', 'menu_restart', 'waitms 1200', 'ui_close', 'waitms 300']
    if loaded:
        lines += ['plug_load ui_imgui']
    lines += [f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
              f'set hud_scale {a.hud_scale}', 'set rec_terms 4', 'set hud_mapinfo_timeleft 0',
              'set ui_native_scores 0', 'set hud_linegraph 1', 'set hud_lines_board 1', 'hud_trainer 0',
              f'set ui_native_graphs {0 if arm == "off" else 1}']
    for slot in range(1, len(P.RUNS) + 1):
        lines += [f'scores lineat {slot} cfg/test/uig_run{slot}.rec']
    lines += ['waitms 4000', 'scores lines', 'linegraph', 'waitms 1200', 'linegraph cursor 5 5']
    lines += mark('open') + (['ui_imgui_status'] if loaded else []) + shot('plots_open')

    if arm == 'cost':
        for i in range(2):
            for route in (1, 0):
                lines += [f'set ui_native_graphs {route}', 'waitms 1500', 'linegraph frames', 'waitms 6000',
                          f'echo P614 cost-{"native" if route else "qc"}-{i}', 'linegraph frames']
        lines += ['set ui_native_graphs 1', 'waitms 1500'] + at(0.5) + ['waitms 500', 'linegraph frames', 'waitms 6000',
                  'echo P614 cost-native-hover', 'linegraph frames']
        lines += ['set ui_native_graphs 0', 'waitms 1500', 'linegraph cursorat 26', 'waitms 500', 'linegraph frames',
                  'waitms 6000', 'echo P614 cost-qc-hover', 'linegraph frames']
        # No curve at all: what each route costs before its first point.
        lines += ['linegraph cursor 5 5', 'linegraph toggle 1', 'linegraph toggle 2', 'linegraph toggle 3']
        for route in (1, 0):
            lines += [f'set ui_native_graphs {route}', 'waitms 1500', 'linegraph frames', 'waitms 6000',
                      f'echo P614 cost-{"native" if route else "qc"}-empty', 'linegraph frames']
    elif arm == 'native':
        # A second with nothing changing: nothing is cut afresh, every frame is the plugin's.
        lines += mark('idle', 800)
        # Two hovers: the plot's own scale, which every later step is predicted from. A third
        # must sit on it.
        lines += at(0.30) + mark('hoverA') + at(0.60) + mark('hoverB') + shot('plots_hover') + at(0.45) + mark('hoverC')
        lines += ['linegraph zoom 18 30'] + at(0.30) + mark('zoom') + shot('plots_zoom')
        lines += at(0.60) + mark('wheel0') + ['linegraph wheel 1'] + mark('wheel-in')
        lines += ['linegraph wheel -1'] + mark('wheel-out')
        # A pan: the time the button went down on must end up under the cursor.
        lines += at(0.60) + mark('pan0') + ['linegraph button 1 down', 'waitms 120'] + at(0.40)
        lines += ['waitms 200', 'linegraph button 1 up'] + mark('pan1')
        # The right button without a drag is the whole run; with one, a box.
        lines += ['linegraph button 2 down', 'waitms 120', 'linegraph button 2 up'] + mark('rmb')
        lines += at(0.30) + ['waitms 150', 'linegraph button 2 down', 'waitms 120'] + at(0.50, 0.60)
        lines += ['waitms 200', 'linegraph button 2 up'] + mark('box') + shot('plots_box')
        lines += ['linegraph zoom', 'linegraph cursor 5 5'] + mark('fit')
        # A chip hides a run (a real click), another picks one out (the cursor resting on it).
        lines += P.click('lg_slot2') + mark('hidden') + shot('plots_hidden') + P.click('lg_slot2') + mark('shown')
        lines += ['hud_edit ui hover lg_slot1'] + mark('loud') + shot('plots_loud') + ['hud_edit ui hover lg_close']
        lines += ['linegraph probe', 'waitms 1500'] + mark('probed') + ['ui_imgui_status'] + shot('plots_probed')
        # ---- one step for each defect the review found (grade_review) ----
        # Each from a fresh open: a refusal lasts an open, and on the build before the fixes
        # one step's would otherwise leave the next with nothing to measure.
        fresh = ['linegraph close', 'waitms 300', 'linegraph', 'waitms 1200', 'linegraph cursor 5 5']
        # A range that is not in the run: its report made the engine drop the owner, every frame.
        lines += pmark('far0') + ['linegraph zoom 5000000 6000000'] + pmark('far1', 700)
        # Twelve notches in one frame: ten are kept, and each is a step of its own.
        lines += fresh + ['linegraph zoom 18 30', 'waitms 300'] + at(0.60) + mark('burst0')
        lines += ['linegraph wheel 1'] * 12 + mark('burst1', 900)
        # The wheel and the mouse together, three of each at a time: one event a frame, and
        # nothing left queued in the plugin.
        lines += fresh + ['linegraph zoom 18 30', 'waitms 300'] + at(0.60) + mark('storm0')
        for i in range(240):
            lines += at(round(0.55 + 0.002 * (i % 40), 3)) + [f'linegraph wheel {1 if i % 2 == 0 else -1}']
            lines += ['waitms 8'] if i % 3 == 2 else []
        lines += mark('storm1', 700)
        # A button held in the plots when another panel takes the mouse: its release never comes.
        lines += fresh + ['linegraph zoom 18 30', 'waitms 300'] + at(0.60) + ['waitms 200', 'linegraph button 1 down']
        lines += mark('held', 250)
        lines += ['hud_player open'] + mark('claimed', 600) + ['hud_player close', 'waitms 400'] + at(0.40)
        lines += mark('bare', 400) + ['linegraph zoom', 'linegraph cursor 5 5', 'waitms 300']
        # The owner closed behind the panel: twice running it is replaced, a third and it is given up.
        lines += fresh + pmark('lose0') + ['linegraph lose 2'] + pmark('lose2', 500) + ['linegraph lose 3'] + pmark('lose3', 500)
        lines += ['linegraph close', 'waitms 300', 'linegraph', 'waitms 1200', 'linegraph cursor 5 5']
        # The plugin given up mid-open: the QC plots take over, with no frame between.
        lines += mark('refuse0') + ['linegraph refuse'] + mark('refused', 500) + shot('plots_refused')
        lines += ['linegraph close', 'waitms 300', 'linegraph', 'waitms 1200', 'linegraph cursor 5 5'] + mark('reopened')
        # Opened by the board's chip, in a frame the board's native table has drawn.
        lines += ['linegraph close', 'waitms 300', 'set ui_native_scores 1', 'scores tab local', 'scores open',
                  'waitms 1500', 'echo P614 board', 'ui_imgui_status'] + P.click('sb_graph') + ['linegraph cursor 5 5']
        lines += pmark('fromboard', 900) + shot('plots_fromboard') + ['set ui_native_scores 0']
        # A replay is run 0, and its clock is the marker.
        lines += ['linegraph close', 'waitms 300', 'echo P614 closed', 'ui_imgui_status', 'set hud_watch_path 1',
                  'replay cfg/test/uig_run1.rec', 'waitms 3000', 'replay pause', 'replay seek 20', 'waitms 800',
                  'linegraph', 'waitms 1200', 'linegraph cursor 5 5'] + mark('replay20') + shot('plots_replay20')
        lines += ['replay seek 35'] + mark('replay35', 900) + shot('plots_replay35')
        lines += ['linegraph close', 'replay stop', 'waitms 400']
        # A renderer restart takes the plugin's owner away: the panel must get a new one.
        lines += ['linegraph', 'waitms 1200'] + mark('before-restart') + ['vid_restart', 'waitms 4000']
        lines += mark('after-restart') + ['ui_imgui_status'] + shot('plots_restart')
    lines += ['linegraph close', 'waitms 300', 'echo P614 end'] + (['ui_imgui_status'] if loaded else [])
    lines += ['scores lines clear', 'waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def status(text, name):
    """The `linegraph status` printed after `echo P614 <name>`, as a dict of float lists."""
    m = re.search(r'P614 ' + re.escape(name) + r'\b(.*?)(?=P614 |UIGALLERY FINISHED)', text, re.S)
    if not m:
        return None
    body = m.group(1)
    num = r'(-?[\d.]+(?:e[+-]?\d+)?)'
    pats = {'open': r'linegraph: open (\d) cursor ' + num + ' duration ' + num,
            'native': r'linegraph: native drew (\d) refused (\d) revision (\d+) series (\d+) points ' + num + r' rebuilt (\d)(?: cut ' + num + ')?',
            'input': r'linegraph: native input in (\d) down (\d) wheel (-?\d+) lost (\d+) nodraw (\d+) ever ' + num + ' events ' + num,
            'routes': r'linegraph: routes panel ' + num + ' native ' + num + ' qc ' + num,
            'qcpixels': r'linegraph: plots pixels ' + ' '.join([num] * 4),
            'view': r'linegraph: native view ' + num + ' ' + num + r' hover (\d) ' + num,
            'pixels': r'linegraph: native pixels ' + ' '.join([num] * 4),
            'playhead': r'linegraph: playhead ' + num + r' runs (\d+)',
            'qcview': r'linegraph: view ' + num + ' ' + num + r' fit (\d) drawn ' + num + ' ' + num + r' ok (\d)'}
    out = {}
    for key, pat in pats.items():
        r = re.search(pat, body)
        out[key] = r and [None if v is None else float(v) for v in r.groups()]
    r = re.search(r'UIIMGUI STATUS (.*)', body)
    out['plugin'] = r and dict(kv.split('=', 1) for kv in r.group(1).split())
    return out


def count(shot, rect, colour, tol=14):
    """Pixels inside `rect` (x, y, w, h) within `tol` of `colour` on every channel."""
    from PIL import Image
    im = Image.open(shot).convert('RGB').crop((int(rect[0]), int(rect[1]), int(rect[0] + rect[2]), int(rect[1] + rect[3])))
    px, (w, h) = im.load(), im.size
    return sum(1 for y in range(h) for x in range(w) if all(abs(px[x, y][i] - colour[i]) <= tol for i in range(3)))


def changed_columns(a, b, rect):
    """Screenshot columns (absolute x) inside `rect` where two shots differ at all."""
    from PIL import Image, ImageChops
    box = (int(rect[0]), int(rect[1]), int(rect[0] + rect[2]), int(rect[1] + rect[3]))
    d = ImageChops.difference(Image.open(a).convert('RGB').crop(box), Image.open(b).convert('RGB').crop(box)).convert('L')
    w, h = d.size
    px = d.load()
    return [box[0] + x for x in range(w) if sum(1 for y in range(h) if px[x, y] > 24) >= 12]


def ink_floor(rect):
    """Pixels of one run's colour a drawn plot pair must hold: measured 1900-3000 at 1056 px wide."""
    return max(80, 0.57 * rect[2])


def grade_qc(label, root, s, bad, name='plots_open'):
    """The QC plots are what is on screen: their own status line, and each run's colour as ink."""
    if not s['qcview'] or s['qcview'][5] != 1 or abs(s['qcview'][1] - LONGEST) > 0.06:
        bad(f'the QC plots are not drawn over the whole run: {s["qcview"]}')
    rect = s.get('qcpixels')
    found = list((root / 'ftesurf/screenshots').glob(name + '.*'))
    if not rect or not found:
        bad(f'{name}: no QC plots rectangle or no screenshot to read ({rect}, {found})')
        return
    ink = {k: count(found[0], rect, c) for k, c in COLOURS.items()}
    print(f'{label}: {name}: QC plots {rect[2]:.0f}x{rect[3]:.0f} px; pixels of each run\'s colour {ink}')
    for k, n in ink.items():
        if n < ink_floor(rect):
            bad(f'{name}: run {k}\'s colour covers {n} pixels of the QC plots, wanted {ink_floor(rect):.0f}+')


def grade_review(arm, root, text, bad, base, shot):
    """One step for each defect the review of Patch 614 found. Each fails on the build before its fix."""
    def need(name, *keys):
        s = status(text, name)
        missing = [k for k in keys if not s or s.get(k) is None]
        if missing:
            bad(f'{name}: status lines missing: {missing}')
            return None
        return s

    def span(s):
        return s['view'][1] - s['view'][0]

    # A range that is not in the run. Before: the plugin's report of it ran past what the
    # engine accepts, the owner was dropped at the poll, and the panel opened another every frame.
    f0, f1 = need('far0', 'plugin'), need('far1', 'native', 'view', 'input', 'plugin')
    if f0 and f1:
        opens = [int(x['plugin'].get('opens', -1)) for x in (f0, f1)]
        print(f'{arm}: range 5000000..6000000: the plugin opened {opens[1] - opens[0]} more times, shows {f1["view"][:2]}')
        if f1['native'][:2] != [1, 0] or f1['input'][3] != 0:
            bad(f'far range: wanted the plugin drawing with no owner lost, read {f1["native"]} lost {f1["input"][3]}')
        if opens[0] < 1 or opens[1] != opens[0]:
            bad(f'far range: the plugin\'s owner was opened {opens[1] - opens[0]} more times (opens {opens})')
        if abs(f1['view'][0]) > 0.02 or abs(f1['view'][1] - LONGEST) > 0.06:
            bad(f'far range: none of it is in the run, wanted the whole run, the plugin reports {f1["view"][:2]}')

    # Twelve notches before one frame: ten are kept (lgn_wheel's bound) and each is a zoom step.
    b0, b1 = need('burst0', 'view'), need('burst1', 'native', 'view', 'input')
    if b0 and b1:
        ratio, want = span(b1) / span(b0), WHEEL_IN ** 10
        print(f'{arm}: twelve notches at once: span {span(b0):.3f} -> {span(b1):.3f} s, x{ratio:.4f} (ten steps are x{want:.4f})')
        if b1['native'][:2] != [1, 0] or b1['input'][2] != 0:
            bad(f'notch burst: wanted the plugin drawing and no notch waiting, read {b1["native"]} wheel {b1["input"][2]}')
        if abs(ratio / want - 1) > 0.06:
            bad(f'notch burst: span x{ratio:.4f}, ten steps are x{want:.4f}')

    # The wheel and the mouse together. Before: a position ahead of every notch, which ImGui
    # takes a frame apart, so its queue grew until an event was refused (refusal 6).
    # (A notch in and one out do not cancel in ImPlot, x1.0417 the pair, so the span is
    # printed and not graded; what was SENT is.)
    s0, s1 = need('storm0', 'view', 'input', 'routes'), need('storm1', 'native', 'view', 'input', 'routes')
    if s0 and s1:
        sent, frames = s1['input'][6] - s0['input'][6], s1['routes'][0] - s0['routes'][0]
        print(f'{arm}: 240 notches with the mouse moving: {sent:.0f} events sent in {frames:.0f} frames, now {s1["native"][:2]}, '
              f'span x{span(s1) / span(s0):.3f}, waiting {s1["input"][2]:.0f}')
        if s1['native'][:2] != [1, 0]:
            bad(f'wheel with the mouse: wanted the plugin still drawing, read drew/refused {s1["native"][:2]}')
        if s1['input'][2] != 0:
            bad(f'wheel with the mouse: {s1["input"][2]} notches never sent')
        if sent < 60 or sent > frames:
            bad(f'wheel with the mouse: {sent:.0f} events in {frames:.0f} frames; wanted 60+ and never two a frame')

    # A button held when another panel takes the mouse. Before: it stayed held, so the plots
    # panned under a bare cursor afterwards.
    h, c, b = need('held', 'view', 'input'), need('claimed', 'input'), need('bare', 'native', 'view', 'input')
    if h and c and b:
        print(f'{arm}: button held, another panel opened: down {h["input"][1]:.0f} -> {c["input"][1]:.0f}; '
              f'view {h["view"][:2]} -> {b["view"][:2]} after a bare move')
        if h['input'][1] != 1:
            bad(f'held button: the press inside the plots was not taken (down {h["input"][1]}), so nothing is shown')
        if c['input'][1] != 0:
            bad('held button: another panel has the mouse and the plots still hold the button')
        if b['native'][:2] != [1, 0] or b['view'][2] != 1:
            bad(f'held button: afterwards wanted the plugin drawing with the cursor read, got {b["native"]} {b["view"]}')
        elif abs(b['view'][0] - h['view'][0]) > 0.05 or abs(b['view'][1] - h['view'][1]) > 0.05:
            bad(f'held button: the plots panned under a bare cursor: {h["view"][:2]} -> {b["view"][:2]}')

    # The owner closed behind the panel (a renderer restart does it once). Twice running it
    # is opened again; lost on a third frame running the panel stops asking, which is what
    # ends a loop like the far range's whatever starts it.
    l0, l2, l3 = need('lose0', 'plugin'), need('lose2', 'native', 'input', 'plugin'), need('lose3', 'native', 'qcview', 'plugin')
    if l0 and l2 and l3:
        opens = [int(x['plugin'].get('opens', -1)) for x in (l0, l2, l3)]
        print(f'{arm}: owner closed behind the panel twice, then three times: opens {opens}, {l2["native"][:2]} then {l3["native"][:2]}')
        if opens[1] != opens[0] + 2 or l2['native'][:2] != [1, 0] or l2['input'][3] != 0:
            bad(f'owner lost twice: wanted two more opens and the plugin drawing, read opens {opens[:2]} {l2["native"]}')
        if opens[2] != opens[1] + 3 or l3['native'][:2] != [0, 7] or l3['qcview'][5] != 1:
            bad(f'owner lost three frames running: wanted three more opens, refused 7 and the QC plots, read opens {opens[1:]} {l3["native"]}')

    # The plugin given up mid-open. Every panel frame must be one route or the other, QC's
    # from that frame on, and the QC plots must be ink.
    r0, r1 = need('refuse0', 'native', 'routes'), need('refused', 'native', 'routes', 'qcview', 'qcpixels')
    if r0 and r1:
        dp, dn, dq = (r1['routes'][i] - r0['routes'][i] for i in range(3))
        print(f'{arm}: plugin refused mid-open: {dp:.0f} panel frames = {dn:.0f} the plugin\'s + {dq:.0f} QC\'s; now {r1["native"][:2]}')
        if r0['native'][:2] != [1, 0]:
            bad(f'refusal: the plugin was not drawing before it: {r0["native"]}')
        if r1['native'][:2] != [0, 9]:
            bad(f'refusal: wanted drew 0 refused 9, read {r1["native"][:2]}')
        if dp < 20 or dp != dn + dq or dq < 10:
            bad(f'refusal: {dp:.0f} panel frames against {dn:.0f} + {dq:.0f}: a frame with no plots, or too few to say')
        grade_qc(arm, root, r1, bad, 'plots_refused')
    r2 = need('reopened', 'native', 'input')
    if r2 and r2['native'][:2] != [1, 0]:
        bad(f'refusal: it must last one open; the next read {r2["native"]}')

    # Opened by the board's chip. Before: the board's native table had drawn that frame, the
    # panel's own draw was refused (one owner a VM a frame), and that was read as the plugin failing.
    bd, fb = status(text, 'board'), need('fromboard', 'open', 'native', 'input', 'pixels', 'plugin')
    if not bd or bd['plugin'] is None or bd['plugin'].get('live') != '1':
        bad(f'from the board: its native table was not up before the chip: {bd and bd["plugin"]}')
    elif fb and r2:
        refusals = fb['input'][5] - r2['input'][5]
        print(f'{arm}: opened from the board: {refusals:.0f} draw refused on the way, now {fb["native"][:2]}')
        if fb['open'][0] != 1:
            bad('from the board: the chip did not open the panel')
        elif refusals < 1:
            bad('from the board: no draw was refused, so the frame this step exists for did not happen')
        if fb['native'][:2] != [1, 0] or fb['native'][3] != len(P.RUNS):
            bad(f'from the board: wanted the plugin drawing {len(P.RUNS)} series, read {fb["native"]}')
        elif shot('plots_fromboard'):
            ink = {k: count(shot('plots_fromboard'), fb['pixels'], col) for k, col in COLOURS.items()}
            if any(ink[k] < base[k] * 0.7 for k in COLOURS):
                bad(f'from the board: the curves are not all on screen: {ink} against {base}')


def grade_native(arm, root, text, bad):
    shots = root / 'ftesurf/screenshots'

    def shot(name):
        found = list(shots.glob(name + '.*'))
        return found[0] if found else None

    s = status(text, 'open')
    if not s or not s['native'] or not s['view'] or not s['pixels']:
        bad(f'no native status after the panel opened: {s}')
        return
    drew, refused, rev0, series, points0, rebuilt, cut0 = s['native']
    if [drew, refused, series] != [1, 0, len(P.RUNS)] or rev0 < 1 or points0 < 60:
        bad(f'open: wanted the plugin drawing {len(P.RUNS)} series from a revision, 60+ points; read {s["native"]}')
        return
    # A view that is only being read is drawn from kept strips: nothing is cut afresh.
    if rebuilt != 0:
        bad(f'open: {rebuilt:.0f} of the two plots were cut afresh on a frame where nothing had changed')
    if abs(s['view'][0]) > 0.02 or abs(s['view'][1] - LONGEST) > 0.06:
        bad(f'open: the view {s["view"][:2]} is not the whole {LONGEST} s')
    rect = s['pixels']
    base = {k: count(shot('plots_open'), rect, c) for k, c in COLOURS.items()}
    print(f'{arm}: plots {rect[2]:.0f}x{rect[3]:.0f} px, {points0:.0f} points; pixels of each run\'s colour {base}')
    for k, n in base.items():
        if n < ink_floor(rect):
            bad(f'run {k}\'s colour covers {n} pixels of the plots, wanted {ink_floor(rect):.0f}+ (curves not on screen)')
    if s['plugin'] is None or s['plugin'].get('live') != '1' or s['plugin'].get('rejected') != '0':
        bad(f'plugin status with the panel open: {s["plugin"]}')
    # A second later with nothing touched: the strips were kept, and no frame was QC's.
    idle = status(text, 'idle')
    if not idle or not idle['native'] or not idle['routes'] or not s['routes'] or cut0 is None:
        bad('idle: a status is missing')
    elif s['input'] and idle['input'] and (s['input'][6] != 0 or idle['input'][6] != 0):
        # The harness has parked its cursor off the plots and sent nothing: any event the panel
        # forwarded came from the real mouse over the rig's window. No focus line marks that.
        bad(f'INTERFERED -- {idle["input"][6]:.0f} mouse events reached the plots before the harness moved its cursor '
            '(the real mouse over the rig window); rerun it')
        return
    else:
        dp, dn, dq = (idle['routes'][i] - s['routes'][i] for i in range(3))
        print(f'{arm}: a second idle: {dp:.0f} panel frames, {dn:.0f} the plugin\'s, {dq:.0f} QC\'s; plots cut afresh {idle["native"][6] - cut0:.0f}')
        if idle['native'][6] != cut0:
            bad(f'idle: {idle["native"][6] - cut0:.0f} plots were cut afresh with nothing changed')
        if dp < 20 or dn != dp or dq != 0:
            bad(f'idle: {dp:.0f} panel frames, {dn:.0f} drawn by the plugin and {dq:.0f} by QC')

    # The plot's own scale from two hovers: t = (fx - f0) * k.
    a, b = status(text, 'hoverA'), status(text, 'hoverB')
    if not a or not b or not a['view'] or not b['view'] or a['view'][2] != 1 or b['view'][2] != 1:
        bad(f'hover: no time under the cursor at 0.30 / 0.60 of the plots: {a and a["view"]} {b and b["view"]}')
        return
    ta, tb = a['view'][3], b['view'][3]
    k = (tb - ta) / 0.30
    f0 = 0.30 - ta / k if k > 0 else -1
    f1 = f0 + LONGEST / k if k > 0 else -1
    print(f'{arm}: hover reads {ta:.3f} s at 0.30 and {tb:.3f} s at 0.60: the plot spans {f0:.3f}..{f1:.3f} of its rectangle')
    if not (k > 0 and 0.0 < f0 < 0.2 and 0.9 < f1 <= 1.001):
        bad(f'hover: 0.30 -> {ta}, 0.60 -> {tb} is not a time axis inside the rectangle')
        return
    # A third reading the first two did not make: half way between them, to a pixel or so.
    c = status(text, 'hoverC')
    if not c or not c['view'] or c['view'][2] != 1 or abs(c['view'][3] - (ta + tb) / 2) > 0.08:
        bad(f'hover at 0.45 read {c and c["view"]}; half way between the other two is {(ta + tb) / 2:.3f} s')

    def frac(t, view):                      # where a time sits, as a fraction of the rectangle
        return f0 + (t - view[0]) / (view[1] - view[0]) * (f1 - f0)

    def time_at(fx, view):
        return view[0] + (fx - f0) / (f1 - f0) * (view[1] - view[0])

    z = status(text, 'zoom')
    if not z or not z['view'] or abs(z['view'][0] - 18) > 0.02 or abs(z['view'][1] - 30) > 0.02:
        bad(f'zoom 18 30: the plugin reports {z and z["view"]}')
        return
    if z['view'][2] != 1 or abs(z['view'][3] - time_at(0.30, z['view'])) > 0.1:
        bad(f'zoomed: hover at 0.30 read {z["view"][3]}, the scale says {time_at(0.30, z["view"]):.3f}')
    # A view that moved is cut afresh, once: the count that stood still while idle rises here.
    if cut0 is None or z['native'][6] is None or not z['native'][6] > b['native'][6]:
        bad(f'zoomed: no plot was cut afresh for a new view (cut {b["native"][6]} -> {z["native"][6]})')
    else:
        print(f'{arm}: plots cut afresh: {cut0:.0f} at open, {b["native"][6]:.0f} after two hovers, {z["native"][6]:.0f} after the zoom')

    w0, wi, wo = status(text, 'wheel0'), status(text, 'wheel-in'), status(text, 'wheel-out')
    if not (w0 and wi and wo and w0['view'] and wi['view'] and wo['view']):
        bad('wheel: a status is missing')
        return
    span0, span1, span2 = (v['view'][1] - v['view'][0] for v in (w0, wi, wo))
    if abs(span1 / span0 - WHEEL_IN) > 0.02:
        bad(f'wheel in: span {span0:.3f} -> {span1:.3f}, wanted x{WHEEL_IN:.3f}')
    if abs(span2 / span1 - WHEEL_OUT) > 0.02:
        bad(f'wheel out: span {span1:.3f} -> {span2:.3f}, wanted x{WHEEL_OUT:.3f}')
    if abs(wi['view'][3] - w0['view'][3]) > 0.08:
        bad(f'wheel in moved the time under the cursor: {w0["view"][3]} -> {wi["view"][3]}')

    p0, p1 = status(text, 'pan0'), status(text, 'pan1')
    if not (p0 and p1 and p0['view'] and p1['view']):
        bad('pan: a status is missing')
        return
    if p1['view'][2] != 1 or abs(p1['view'][3] - p0['view'][3]) > 0.12:
        bad(f'pan: {p0["view"][3]:.3f} s was grabbed at 0.60 and {p1["view"][3]:.3f} s is under the cursor at 0.40')
    if not p1['view'][0] > p0['view'][0] + 0.5:
        bad(f'pan: the view did not move: {p0["view"][:2]} -> {p1["view"][:2]}')

    r = status(text, 'rmb')
    if not r or not r['view'] or abs(r['view'][0]) > 0.02 or abs(r['view'][1] - LONGEST) > 0.06:
        bad(f'right button: wanted the whole run, the plugin reports {r and r["view"]}')
    bx = status(text, 'box')
    whole = [0, LONGEST]
    want = [time_at(0.30, whole), time_at(0.50, whole)]
    if not bx or not bx['view'] or abs(bx['view'][0] - want[0]) > 0.4 or abs(bx['view'][1] - want[1]) > 0.4:
        bad(f'box from 0.30 to 0.50: wanted about {want[0]:.2f}..{want[1]:.2f}, the plugin reports {bx and bx["view"]}')
    ft = status(text, 'fit')
    if not ft or not ft['view'] or abs(ft['view'][0]) > 0.02 or abs(ft['view'][1] - LONGEST) > 0.06:
        bad(f'bare zoom: wanted the whole run, the plugin reports {ft and ft["view"]}')

    h, sh = status(text, 'hidden'), status(text, 'shown')
    if not (h and sh and h['native'] and sh['native']):
        bad('hide: a status is missing')
        return
    hid = {k: count(shot('plots_hidden'), rect, c) for k, c in COLOURS.items()}
    print(f'{arm}: run 2 hidden: points {points0:.0f} -> {h["native"][4]:.0f} -> {sh["native"][4]:.0f}, pixels {hid}')
    if not h['native'][4] < points0 * 0.85:
        bad(f'hide: points {points0} -> {h["native"][4]}: nothing left the plots')
    if hid[2] > 60 or hid[1] < base[1] * 0.7 or hid[3] < base[3] * 0.7:
        bad(f'hide: pixels {hid} against {base}: run 2 must be gone and the others must stay')
    if abs(sh['native'][4] - points0) > points0 * 0.1:
        bad(f'show again: points {sh["native"][4]} against {points0}')
    loud = {k: count(shot('plots_loud'), rect, c) for k, c in COLOURS.items()}
    print(f'{arm}: run 1 picked out: pixels {loud}')
    if loud[1] < base[1] * 0.7 or loud[2] > base[2] * 0.4 or loud[3] > base[3] * 0.4:
        bad(f'emphasis: pixels {loud} against {base}: run 1 must stay and the others dim')

    lines = re.findall(r'linegraph: probe (\d+) (\S+) begin (-?\d+) series (-?\d+) rows (-?\d+) commit (-?\d+) view (-?\d+)', text)
    seen = {name: tuple(int(v) for v in rest) for _, name, *rest in lines}
    for name, want in PROBE.items():
        if seen.get(name) != want:
            bad(f'probe {name}: wanted {want}, the builtins returned {seen.get(name)}')
    if 'linegraph: probe done handle 1' not in text:
        bad('probe: the run never reached its end with a live owner')
    pr = status(text, 'probed')
    if not pr or not pr['native'] or pr['native'][0] != 1 or pr['native'][1] != 0 or not pr['native'][2] > rev0:
        bad(f'after the probe: wanted the plugin drawing a newer revision than {rev0}, read {pr and pr["native"]}')
    elif pr['plugin'] is None or pr['plugin'].get('rejected') != '0' or pr['plugin'].get('failed') != '0':
        bad(f'after the probe: plugin status {pr["plugin"]}')
    if pr and pr['native'] and shot('plots_probed'):
        after = {k: count(shot('plots_probed'), rect, c) for k, c in COLOURS.items()}
        if any(after[k] < base[k] * 0.7 for k in COLOURS):
            bad(f'after the probe the curves are not all on screen: {after} against {base}')

    grade_review(arm, root, text, bad, base, shot)

    c = status(text, 'closed')
    if not c or c['plugin'] is None or c['plugin'].get('live') != '0':
        bad(f'closing the panel left the plugin\'s owner open: {c and c["plugin"]}')
    b4, af = status(text, 'before-restart'), status(text, 'after-restart')
    if not (b4 and af and b4['native'] and af['native']) or b4['native'][0] != 1:
        bad(f'renderer restart: no native plots before it: {b4 and b4["native"]}')
    elif af['native'][0] != 1 or af['native'][1] != 0 or af['native'][3] != len(P.RUNS):
        bad(f'renderer restart: wanted the plugin drawing again, read {af["native"]}')
    elif af['plugin'] is None or af['plugin'].get('renderer') != '1' or af['plugin'].get('live') != '1':
        bad(f'renderer restart: the plugin did not lose and regain an owner: {af["plugin"]}')
    elif shot('plots_restart'):
        again = {k: count(shot('plots_restart'), af['pixels'], c) for k, c in COLOURS.items()}
        print(f'{arm}: after vid_restart: revision {b4["native"][2]:.0f} -> {af["native"][2]:.0f}, pixels {again}')
        if any(again[k] < base[k] * 0.7 for k in COLOURS):
            bad(f'renderer restart: the curves are not all back: {again} against {base}')
    r20, r35 = status(text, 'replay20'), status(text, 'replay35')
    if not (r20 and r35 and r20['native'] and r35['native'] and r20['playhead'] and r35['playhead']):
        bad('replay: a status is missing')
        return
    if r20['native'][0] != 1 or r20['native'][3] != len(P.RUNS) + 1:
        bad(f'replay: wanted the plugin drawing {len(P.RUNS) + 1} series, read {r20["native"]}')
    if abs(r20['playhead'][0] - 20) > 0.1 or abs(r35['playhead'][0] - 35) > 0.1:
        bad(f'replay clock: {r20["playhead"]} then {r35["playhead"]}')
    # The marker is ink: between the two shots only two thin bands may differ, one at each clock.
    rect2 = r20['pixels']
    cols = changed_columns(shot('plots_replay20'), shot('plots_replay35'), rect2)
    want_x = [rect2[0] + frac(t, whole) * rect2[2] for t in (20, 35)]
    near = [sum(1 for x in cols if abs(x - wx) <= 8) for wx in want_x]
    stray = [x for x in cols if all(abs(x - wx) > 8 for wx in want_x)]
    print(f'{arm}: replay marker: {len(cols)} changed columns, {near} of them at x {want_x[0]:.0f} and {want_x[1]:.0f}, {len(stray)} elsewhere')
    if min(near) < 1 or len(stray) > 4:
        bad(f'replay marker: changed columns {cols[:12]}... are not two bands at {want_x}')


def grade(rig, a):
    # The gallery's own shot of the native scoreboard is not taken by these arms, and its
    # focus check is the whole log's: here only the graded stretch counts (below).
    errors = [e for e in G.grade(rig) if 'missing screenshot scores_native' not in e and 'INTERFERED' not in e]
    for arm in sorted(p.name for p in rig.iterdir() if (p / 'ftesurf/logs').is_dir()):
        logs = list((rig / arm / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            continue
        text = logs[0].read_text(errors='replace')
        label = f'{a.arm} {arm}'

        def bad(msg):
            errors.append(f'{label}: {msg}')

        for slot in range(1, len(P.RUNS) + 1):
            if f'line {slot} drawn' not in text:
                bad(f'board line {slot} never built')
        # Any focus message while the panel is being driven drops a parked hover or lets
        # real input in. One before the panel opens is the window settling, and the two
        # around the arm's own vid_restart are the restart.
        driven = text.split('P614 open', 1)[-1].split('P614 before-restart', 1)[0]
        if '[focus]' in driven:
            bad('INTERFERED -- a focus message reached the rig window while the panel was driven; rerun it')
        s = status(text, 'open')
        if not s or not s['open'] or s['open'][0] != 1 or not s['native']:
            bad(f'the panel is not open with a native status line: {s}')
            continue
        if a.arm == 'native':
            # The rectangle asked of the plugin, drawn or not. With room in it (LGN_MINW x
            # LGN_MINH, cl_linegraph.qc) the plugin must draw; under that the QC plots must.
            px = s['pixels']
            if px is None or px[2] <= 0:
                bad(f'no rectangle printed for the plugin: {px}')
            elif s['native'][0] == 1:
                grade_native(label, rig / arm, text, bad)
            elif px[2] >= 160 and px[3] >= 120:
                bad(f'the plugin did not draw a {px[2]:.0f}x{px[3]:.0f} px rectangle it has room in: {s["native"]}')
            else:
                print(f'{label}: the plots\' rectangle is {px[2]:.0f}x{px[3]:.0f} px, under the plugin\'s 160x120: QC\'s are wanted')
                if s['native'][1] != 0:
                    bad(f'too small is not a refusal: {s["native"]}')
                grade_qc(label, rig / arm, s, bad)
        elif a.arm == 'cost':
            for kind in ('native-0', 'qc-0', 'native-1', 'qc-1', 'native-hover', 'qc-hover', 'native-empty', 'qc-empty'):
                m = re.search(r'P614 cost-' + kind + r'\b.*?linegraph: frames (\d+) seconds ([\d.]+) native (\d)', text, re.S)
                if not m or int(m.group(1)) < 50:
                    bad(f'cost window {kind} did not count: {m and m.groups()}')
                    continue
                frames, seconds, nat = int(m.group(1)), float(m.group(2)), int(m.group(3))
                if nat != (1 if kind.startswith('native') else 0):
                    bad(f'cost window {kind} was drawn by the wrong route (native {nat})')
                print(f'{label}: {kind:13s} {frames:6d} frames in {seconds:.3f} s = {seconds / frames * 1000:.3f} ms a frame')
        else:
            # Every other arm: the QC plots, no refusal, and the plugin (where loaded) never opened.
            if s['native'][0] != 0 or s['native'][1] != 0:
                bad(f'wanted the QC plots with nothing refused, read native {s["native"]}')
            grade_qc(label, rig / arm, s, bad)
            e = status(text, 'end')
            if a.arm in ('off', 'oldplugin', 'oldengine'):
                if not e or e['plugin'] is None:
                    bad('the plugin did not answer ui_imgui_status (not loaded?)')
                elif e['plugin'].get('opens') != '0':
                    bad(f'the plugin was opened: {e["plugin"]}')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, help='the engine under test')
    p.add_argument('--server', type=Path)
    p.add_argument('--plugin', type=Path, help='the fteplug_ui_imgui_x64.dll under test')
    p.add_argument('--old-engine', type=Path, help='an engine from before the patch (oldengine arm)')
    p.add_argument('--old-plugin', type=Path, help='a plugin DLL from before the patch (oldplugin arm)')
    p.add_argument('--qc-artifacts', type=Path)
    p.add_argument('--library', type=Path)
    p.add_argument('--out', type=Path, help='owned task-root output directory')
    p.add_argument('--arms', nargs='+', choices=ARMS, default=['native'])
    p.add_argument('--sizes', nargs='+', type=G.size_arg, default=[(1920, 1080)], metavar='WxH')
    p.add_argument('--hud-scale', type=float, default=2)
    p.add_argument('--renderer', choices=('gl', 'd3d11', 'vk'), default='gl')
    p.add_argument('--timeout', type=int, default=300)
    a = p.parse_args()
    for need in ('engine', 'server', 'plugin', 'qc_artifacts', 'out'):
        if getattr(a, need) is None:
            p.error('--' + need.replace('_', '-') + ' is required')
    G_SEED = G.seed_runs
    G.seed_runs = seed
    G.config = config
    G.SHOTS_1080 = ()
    under_test = a.engine
    failures = []
    for arm in a.arms:
        a.arm = arm
        a.engine = under_test
        a.plugins = a.plugin.parent
        G.SHOTS = ('plots_open',)
        if arm == 'native':
            G.SHOTS += ('plots_hover', 'plots_zoom', 'plots_box', 'plots_hidden', 'plots_loud', 'plots_probed',
                        'plots_refused', 'plots_fromboard', 'plots_replay20', 'plots_replay35', 'plots_restart')
        elif arm == 'absent':
            a.plugins = Path('nonexistent-no-plugin')
        elif arm == 'oldplugin':
            if a.old_plugin is None:
                p.error('--old-plugin is required for the oldplugin arm')
            a.plugins = a.old_plugin.parent
        elif arm == 'oldengine':
            if a.old_engine is None:
                p.error('--old-engine is required for the oldengine arm')
            a.engine = a.old_engine
        rig = G.run(a)
        errors = grade(rig, a)
        for error in errors:
            print('FAIL', error)
        print(f'Plots rig ({arm})', rig)
        failures += errors
    print('Plots failures:', len(failures))
    raise SystemExit(bool(failures))
