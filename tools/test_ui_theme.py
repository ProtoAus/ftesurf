#!/usr/bin/env python3
"""Look gate: a build that says it leaves the SUI panels alone proves it.

Gallery runs (tools/ui_gallery.py, isolated rigs under --out):
  control   --control-qc, the progs the look is compared against; or
            --control-arm, one arm of a gallery that already ran
  subject   --subject-qc, the progs under test
  mutant    the subject's csprogs recompiled HERE with one theme colour moved,
            so the comparison is shown to see a change

Predictions:
  P0  every panel state is ON SCREEN in the subject: its shot differs from a
      named other shot of the same run (the plain HUD, or the state before it).
      Without this a panel that failed to open in both builds would pass P1.
  P1  every panel state is pixel-identical between control and subject. In-game
      shots compare the whole frame less the room list's ping cell; menu shots
      compare the opaque inside of their panel, clear of its rounded corners
      (the backdrop behind it is animated).
  P2  the mutant FAILS P1 where that colour is drawn, and only there.
  P3  a mouse parked on a map-picker chip raises its tooltip: the menu VM's own
      `ui_hover` line says so.
A patch that changes the look on purpose fails P1 by design: it names the shots
that moved, and `ui_gallery.py --against` pairs them for a person to read.
Exit 0 all held, 1 a prediction failed, 2 a run could not be graded -- which
includes a rig whose window took the foreground mid-run (ui_gallery.py says
INTERFERED): the owner's desktop reached it, and that is not the build's fault.
1920x1080, hud_scale 2 only: the regions below are that layout's.
(Until Patch 607 this compared the two `ui_style` values; there is one look now.)
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageChops

import ui_gallery

ROOT = Path(__file__).resolve().parents[1]
ARM = '1920x1080'
# Geometry at 1920x1080, hud_scale 2. (x0, y0, x1, y1), None = whole frame.
PING = (1540, 155, 1592, 174)           # the room list's ping text: live network time
INGAME = ('gfx_page1', 'gfx_page2', 'hudedit_list', 'hudedit_pane', 'hudedit_tip', 'saveloc',
          'scores_local', 'scores_online', 'scores_native')
# Six pixels inside each panel: its 12 px corners show the backdrop nearer the edge.
MENU = {'menu_create': (416, 142, 1504, 938), 'menu_create_hover': (416, 142, 1504, 938),
        'menu_board': (586, 206, 1334, 874), 'menu_board_empty': (586, 206, 1334, 874)}
# P0: what each shot must differ from within one run. menu_create has nothing
# static to differ from (the main menu sits on the animated backdrop), so it is
# witnessed by the panel's own fill, SUI_THEME_PANEL, covering its region.
DREW = {'gfx_page1': 'hud_plain', 'gfx_page2': 'gfx_page1', 'hudedit_list': 'hud_plain',
        'hudedit_pane': 'hudedit_list', 'hudedit_tip': 'hudedit_pane', 'saveloc': 'hud_plain',
        'scores_local': 'hud_plain', 'scores_online': 'scores_local', 'scores_native': 'scores_local',
        'menu_create_hover': 'menu_create', 'menu_board': 'menu_create', 'menu_board_empty': 'menu_board'}
PANEL_RGB = (26, 28, 38)
# Butter: the renderer menu's named modes and the board's first plate and note wear it;
# the HUD editor and the save-lock menu (with no save selected) do not.
MUTATION = ("#define SUI_THEME_WARN     '0.961 0.867 0.588'", "#define SUI_THEME_WARN     '0.961 0.867 0.688'")
MUTANT_SEES = ('gfx_page1', 'scores_local')
MUTANT_BLIND = ('hudedit_list',)


def shot(arm, name):
    paths = list((arm / 'ftesurf/screenshots').glob(name + '.*'))
    return paths[0] if len(paths) == 1 else None


def differing(a, b, region=None, mask=None):
    """Pixels that differ between two screenshots, or None when one is missing."""
    if a is None or b is None:
        return None
    with Image.open(a) as ia, Image.open(b) as ib:
        ia, ib = ia.convert('RGB'), ib.convert('RGB')
        if ia.size != ib.size:
            return None
        if mask:
            for image in (ia, ib):
                image.paste((0, 0, 0), mask)
        if region:
            ia, ib = ia.crop(region), ib.crop(region)
        diff = ImageChops.difference(ia, ib).convert('L').point(lambda v: 255 if v else 0)
        return sum(diff.histogram()[1:])


def panel_pixels(path, region):
    """Pixels of the region within 2 of the panel fill, or None when the shot is missing."""
    if path is None:
        return None
    with Image.open(path) as image:
        data = image.convert('RGB').crop(region).tobytes()
    return sum(all(abs(data[i + k] - PANEL_RGB[k]) <= 2 for k in range(3)) for i in range(0, len(data), 3))


def gallery(a, qc, tag):
    args = argparse.Namespace(engine=a.engine, server=a.server, plugins=a.engine.parent, qc_artifacts=qc,
                              library=a.library, out=a.out / tag, sizes=[(1920, 1080)],
                              hud_scale=2, renderer='gl', timeout=180)
    rig = ui_gallery.run(args)
    errors = ui_gallery.grade(rig)
    for error in errors:
        print('NOT REACHED', tag, error)
    return rig / ARM, not errors


def build_mutant(a):
    """The subject's csprogs with one theme colour moved; nothing else differs."""
    src = ROOT / 'src'
    dest = a.out / 'mutant-qc'
    dest.mkdir(parents=True, exist_ok=False)
    text = (src / 'shared/sh_ui.qc').read_text(encoding='utf-8')
    if text.count(MUTATION[0]) != 1:
        raise RuntimeError('the mutation site is not unique in sh_ui.qc')
    (dest / 'sh_ui_mutant.qc').write_text(text.replace(*MUTATION), encoding='utf-8')
    lines = (src / 'cl_progs.src').read_text(encoding='utf-8').splitlines()
    out = [os.path.relpath(dest / 'csprogs.dat', src).replace('\\', '/')]
    swapped = 0
    for line in lines[1:]:
        if line.strip() == 'shared/sh_ui.qc':
            line = os.path.relpath(dest / 'sh_ui_mutant.qc', src).replace('\\', '/')
            swapped += 1
        out.append(line)
    if swapped != 1:
        raise RuntimeError('cl_progs.src does not name shared/sh_ui.qc exactly once')
    # Old-style fteqcc wants a manifest beside the sources; an owned name, removed after.
    manifest = src / (a.out.name + '-mutant-cl_progs.src')
    if manifest.exists():
        raise RuntimeError('mutant manifest already exists')
    manifest.write_text('\n'.join(out) + '\n', encoding='utf-8')
    try:
        with (dest / 'compile.log').open('w', encoding='utf-8') as log:
            result = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', manifest.name], cwd=src,
                                    stdout=log, stderr=subprocess.STDOUT)
    finally:
        manifest.unlink()
    if result.returncode or 'Done. 0 warnings' not in (dest / 'compile.log').read_text(errors='replace'):
        raise RuntimeError('mutant compile failed: ' + str(dest / 'compile.log'))
    for name in ('qwprogs.dat', 'menu.dat'):
        shutil.copy2(a.subject_qc / name, dest / name)
    return dest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True)
    control = p.add_mutually_exclusive_group(required=True)
    control.add_argument('--control-qc', type=Path)
    control.add_argument('--control-arm', type=Path, help='an arm directory (it holds ftesurf/screenshots) of an earlier gallery')
    p.add_argument('--subject-qc', type=Path, required=True)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True, help='owned task-root output directory')
    a = p.parse_args()
    a.out = a.out.resolve()
    if not any((d / 'OWNER.md').is_file() for d in [a.out, *a.out.parents]):
        p.error('--out requires an ancestor OWNER.md')
    a.out.mkdir(parents=True, exist_ok=True)

    if a.control_arm:
        control, ok_c = a.control_arm.resolve(), (a.control_arm / 'ftesurf/screenshots').is_dir()
    else:
        control, ok_c = gallery(a, a.control_qc, 'control')
    subject, ok_s = gallery(a, a.subject_qc, 'subject')
    mutant, ok_m = gallery(a, build_mutant(a), 'mutant')
    if not (ok_c and ok_s and ok_m):
        print('CANNOT GRADE: a gallery run did not complete')
        return 2

    fails = 0
    ungraded = 0

    def check(ok, message):
        nonlocal fails
        fails += not ok
        print(('PASS ' if ok else 'FAIL ') + message)

    def compare(arm_a, arm_b, name):
        region = MENU.get(name)
        mask = None if region else PING
        return differing(shot(arm_a, name), shot(arm_b, name), region, mask)

    for name in INGAME + tuple(MENU):
        if name in DREW:
            region = MENU.get(name)
            drew = differing(shot(subject, name), shot(subject, DREW[name]), region, None if region else PING)
            want = f'differ from {DREW[name]} in the same run (want > 500)'
        else:
            drew = panel_pixels(shot(subject, name), MENU[name])
            want = 'are the panel fill (want > 100000)'
        if drew is None:
            ungraded += 1
            print('NOT REACHED P0', name, 'screenshot missing or resized')
            continue
        check(drew > (500 if name in DREW else 100000), f'P0 {name}: {drew} pixels {want}')
    for name in INGAME + tuple(MENU):
        same = compare(control, subject, name)
        if same is None:
            ungraded += 1
            print('NOT REACHED', name, 'screenshot missing or resized')
            continue
        check(same == 0, f'P1 {name}: {same} pixels differ from the control (want 0)')
    for name, sees in [(n, True) for n in MUTANT_SEES] + [(n, False) for n in MUTANT_BLIND]:
        moved = compare(subject, mutant, name)
        if moved is None:
            ungraded += 1
            print('NOT REACHED mutant', name)
            continue
        if sees:
            check(moved > 0, f'P2 mutant {name}: {moved} pixels differ from the subject (want > 0)')
        else:
            check(moved == 0, f'P2 mutant {name}: {moved} pixels differ (want 0: the colour is not drawn there)')

    logs = list((subject / 'ftesurf/logs').glob('gallery*.log'))
    lines = [line for line in logs[0].read_text(errors='replace').splitlines() if 'ui_hover:' in line] if logs else []
    # The second line is the report; the first is the park itself, before any frame drew.
    if len(lines) != 2:
        ungraded += 1
        print('NOT REACHED P3 ui_hover lines:', len(lines))
    else:
        said = lines[1].split('ui_hover:', 1)[1].strip()
        check('mouse 1' in said and said.endswith('tip 1 [cs_tier1]'), f'P3 menu tooltip: "{said}" (want mouse 1 ... tip 1 [cs_tier1])')

    if ungraded:
        print(f'CANNOT GRADE: {ungraded} comparison(s) not reached')
        return 2
    print(f'Look gate: {fails} failed; arms {control} {subject} {mutant}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
