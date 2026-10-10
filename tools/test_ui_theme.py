#!/usr/bin/env python3
"""Patch 606 gate: ui_style 0 must not move a pixel, ui_style 1 must act.

Three gallery runs (tools/ui_gallery.py, isolated rigs under --out):
  control   --control-qc, the progs built from the commit before the theme
  subject   --subject-qc, the progs under test
            (one ImGui provider for both: its colours do not follow the style)
  mutant    the subject's csprogs recompiled HERE with one classic colour
            changed, so the comparison is shown to see a classic change

Predictions:
  P1  every classic (ui_style 0) panel is pixel-identical between control and
      subject. In-game shots compare the whole frame less the room list's ping
      cell; menu shots compare the opaque inside of their panel (the backdrop
      behind it is animated).
  P2  every panel differs between the subject's two styles (the theme acts).
  P3  the mutant FAILS P1 on the HUD editor (the comparison discriminates).
  P4  a mouse parked on a map-picker chip raises its tooltip at ui_style 1 and
      nothing at ui_style 0: the menu VM's own `ui_hover` line says which.
Exit 0 all held, 1 a prediction failed, 2 a run could not be graded.
1920x1080, hud_scale 2 only: the regions below are that layout's.
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
# Classic geometry at 1920x1080, hud_scale 2. (x0, y0, x1, y1), None = whole frame.
PING = (1560, 296, 1612, 324)           # the room list's ping text: live network time
INGAME = ('gfx_page1', 'gfx_page2', 'hudedit_list', 'hudedit_pane', 'hudedit_tip', 'saveloc',
          'scores_local', 'scores_online', 'scores_native')
MENU = {'menu_create': (412, 138, 1508, 942), 'menu_create_hover': (412, 138, 1508, 942),
        'menu_board': (582, 202, 1338, 878), 'menu_board_empty': (582, 202, 1338, 878)}
MUTATION = ("#define SUI_CLASSIC_CHIP '0.12 0.13 0.16'", "#define SUI_CLASSIC_CHIP '0.12 0.13 0.19'")


def shot(rig, style, name):
    paths = list((rig / f'style{style}/ftesurf/screenshots').glob(name + '.*'))
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


def gallery(a, qc, styles, tag):
    args = argparse.Namespace(engine=a.engine, server=a.server, plugins=a.engine.parent, qc_artifacts=qc,
                              library=a.library, out=a.out / tag, styles=styles, width=1920, height=1080,
                              hud_scale=2, renderer='gl', timeout=180)
    rig = ui_gallery.run(args)
    errors = ui_gallery.grade(rig)
    for error in errors:
        print('NOT REACHED', tag, error)
    return rig, not errors


def build_mutant(a):
    """The subject's csprogs with one classic colour moved; nothing else differs."""
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
    p.add_argument('--control-qc', type=Path, required=True)
    p.add_argument('--subject-qc', type=Path, required=True)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True, help='owned task-root output directory')
    a = p.parse_args()
    a.out = a.out.resolve()
    if not any((d / 'OWNER.md').is_file() for d in [a.out, *a.out.parents]):
        p.error('--out requires an ancestor OWNER.md')
    a.out.mkdir(parents=True, exist_ok=True)

    control, ok_c = gallery(a, a.control_qc, [0], 'control')
    subject, ok_s = gallery(a, a.subject_qc, [0, 1], 'subject')
    mutant, ok_m = gallery(a, build_mutant(a), [0], 'mutant')
    if not (ok_c and ok_s and ok_m):
        print('CANNOT GRADE: a gallery run did not complete')
        return 2

    fails = 0
    ungraded = 0

    def check(ok, message):
        nonlocal fails
        fails += not ok
        print(('PASS ' if ok else 'FAIL ') + message)

    def compare(rig_a, style_a, rig_b, style_b, name):
        region = MENU.get(name)
        mask = None if region else PING
        return differing(shot(rig_a, style_a, name), shot(rig_b, style_b, name), region, mask)

    for name in INGAME + tuple(MENU):
        same = compare(control, 0, subject, 0, name)
        acts = compare(subject, 0, subject, 1, name)
        if same is None or acts is None:
            ungraded += 1
            print('NOT REACHED', name, 'screenshot missing or resized')
            continue
        check(same == 0, f'P1 classic {name}: {same} pixels differ from the control (want 0)')
        check(acts > 2000, f'P2 modern {name}: {acts} pixels differ from classic (want > 2000)')
    caught = []
    for name in ('hudedit_list', 'hudedit_pane', 'hudedit_tip'):
        moved = compare(control, 0, mutant, 0, name)
        if moved is None:
            ungraded += 1
            print('NOT REACHED mutant', name)
            continue
        caught.append(moved)
        check(moved > 0, f'P3 mutant {name}: {moved} pixels differ from the control (want > 0)')
    # ...and only where the mutation can reach: the HUD-stack menus never read that colour.
    still = compare(control, 0, mutant, 0, 'saveloc')
    check(still == 0, f'P3 mutant saveloc: {still} pixels differ (want 0: the mutation is not drawn there)')

    for style, want in ((1, 'tip 1 [cs_tier1]'), (0, 'tip 0 []')):
        logs = list((subject / f'style{style}/ftesurf/logs').glob('gallery*.log'))
        lines = [line for line in logs[0].read_text(errors='replace').splitlines() if 'ui_hover:' in line] if logs else []
        # The second line is the report; the first is the park itself, before any frame drew.
        if len(lines) != 2:
            ungraded += 1
            print('NOT REACHED P4 style', style, 'ui_hover lines:', len(lines))
            continue
        said = lines[1].split('ui_hover:', 1)[1].strip()
        check('mouse 1' in said and said.endswith(want), f'P4 style {style} menu tooltip: "{said}" (want mouse 1 ... {want})')

    if ungraded:
        print(f'CANNOT GRADE: {ungraded} comparison(s) not reached')
        return 2
    print(f'Theme gate: {fails} failed; rigs {control.name} {subject.name} {mutant.name}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
