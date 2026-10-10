#!/usr/bin/env python3
"""Acted private board-render controls for removing the misleading compare chip."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CFG = '''cfg_save_auto 0
name CompareChipControl
log_enable 1
log_dir logs
log_name runlines_smoke
cl_idlefps 0
cl_maxfps 100
con_notifystyle 0
con_notifytime 0
con_notifytime_error 0
con_notifylines 0
waitms 2000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
scores
scores tab imported
waitms 800
screenshot board_imported.png
scores tab online
waitms 800
screenshot board_native.png
echo RUNLINES COMPLETE
quit
'''


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Test seam must match once: {old!r}')
    return text.replace(old, new, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix='compare-chip-source-', dir=a.output_dir))
    work.rmdir()
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(work), 'HEAD'], check=True)
    shutil.copy2(ROOT/'src/fteqcc64.exe', work/'src/fteqcc64.exe')
    p = work/'src/client/cl_scores.qc'
    text = (ROOT/'src/client/cl_scores.qc').read_text()
    text = once(text, 'float(string id, vector pos, vector sz, string label, float on) Scores_Chip =',
                'var float sc_test_cmp, sc_test_imp, sc_test_refresh, sc_test_tab = -99;\n'
                'float(string id, vector pos, vector sz, string label, float on) Scores_Chip =')
    text = once(text, '\tsui_action_element(pos, sz, id, sui_noop);',
                '\tif (!strcmp(id, "sb_tmix")) sc_test_cmp = sc_test_cmp + 1;\n'
                '\tif (!strcmp(id, "sb_tref")) sc_test_refresh = sc_test_refresh + 1;\n'
                '\tsui_action_element(pos, sz, id, sui_noop);')
    # Patch 607: the source tabs are Scores_Seg's now, not chips.
    text = once(text, '\tsui_action_element(pos, sz, tab, sui_noop);',
                '\tif (!strcmp(tab, "sb_tmix")) sc_test_cmp = sc_test_cmp + 1;\n'
                '\tif (!strcmp(tab, "sb_t3")) sc_test_imp = sc_test_imp + 1;\n'
                '\tsui_action_element(pos, sz, tab, sui_noop);')
    text = once(text, '\tScores_Refresh();\n\n\tsui_begin(scr_x, scr_y);',
                '\tScores_Refresh();\n\tsc_test_cmp = sc_test_imp = sc_test_refresh = 0;\n\n\tsui_begin(scr_x, scr_y);')
    text = once(text, '\tsui_end();\n\tFont_Reset();\n\n\tif (Scores_SpecHandOff())',
                '\tsui_end();\n\tFont_Reset();\n'
                '\tif (sc_test_tab != rec_sb_tab)\n\t{\n'
                '\t\tprint(sprintf("COMPARE FRAME: tab %g tier %s compare %g imported %g refresh %g\\n", rec_sb_tab, Scores_TierOf(), sc_test_cmp, sc_test_imp, sc_test_refresh));\n'
                '\t\tsc_test_tab = rec_sb_tab;\n\t}\n\n\tif (Scores_SpecHandOff())')
    p.write_text(text)
    cfg = work/'ftesurf/cfg/test/compare_chip.cfg'
    cfg.write_text(CFG)
    subprocess.run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8', '-QuakeDir', ''], cwd=work/'src', check=True)
    result = subprocess.run([sys.executable, '-B', str(work/'tools/runlines_smoke.py'), str(cfg), '--output-dir', str(a.output_dir)], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Board control failed; retained rig paths printed above')
    rig = Path(result.stdout.strip().splitlines()[-1].removeprefix('Retained private rig: '))
    log = (rig/'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
    frames = re.findall(r'COMPARE FRAME: tab (\d+) tier (\w+) compare (\d+) imported (\d+) refresh (\d+)', log)
    assert any(tier=='imported' and cmp=='0' and int(imp)>0 and int(refresh)>0 for _,tier,cmp,imp,refresh in frames), frames
    assert any(tier=='ranked' and cmp=='0' and int(refresh)>0 for _,tier,cmp,_,refresh in frames), frames
    for name in ('board_imported.png', 'board_native.png'):
        assert list(rig.rglob(name)), name
    print('Both actual board tabs rendered; imported/ranked tiers distinct; compare absent; imported and refresh widgets acted.')
    print('Retained source:', work)
    print('Retained rig:', rig)


if __name__ == '__main__':
    main()
