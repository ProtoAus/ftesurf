#!/usr/bin/env python3
"""Fail-closed grader controls; copies only private probes/logs, never game data."""
import argparse
from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import tempfile

from rewind_navigation_smoke import grade


def change_row(rig, label, column, value, row=0):
    path = rig / f'ftesurf/cfg/test/rewind_nav_{label}.txt'
    lines = path.read_text().splitlines()
    fields = lines[row].split()
    fields[column] = str(value)
    lines[row] = ' '.join(fields)
    path.write_text('\n'.join(lines) + '\n')


def change_log(rig, old, new, last=False):
    path = rig / 'ftesurf/logs/runlines_smoke.log'
    text = path.read_text()
    assert old in text
    path.write_text(new.join(text.rsplit(old, 1)) if last else text.replace(old, new, 1))


def change_body(rig, column, value):
    path = rig / 'ftesurf/cfg/test/rewind_body_last.txt'
    fields = path.read_text().split()
    fields[column] = str(value)
    path.write_text(' '.join(fields) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    grade(a.rig)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    cases = [
        ('missing-probe', lambda g: (g / 'ftesurf/cfg/test/rewind_nav_oppose.txt').unlink()),
        ('duplicate-probe', lambda g: change_log(g, 'REWIND NAV PROBE oppose\n', 'REWIND NAV PROBE oppose\nREWIND NAV PROBE oppose\n')),
        ('input-unacted', lambda g: change_log(g, 'REWIND NAV EVENT 0 103 0 1\n', '')),
        ('run-unacted', lambda g: change_log(g, 'practice 0  recording 1', 'practice 0  recording 0')),
        ('runtime-error', lambda g: change_log(g, 'RUNLINES COMPLETE', 'QC VM error\nRUNLINES COMPLETE')),
        ('missing-completion', lambda g: change_log(g, 'RUNLINES COMPLETE', '')),
        ('nonfinite-cursor', lambda g: change_row(g, 'oppose', 4, 'nan')),
        ('nonfinite-native', lambda g: change_row(g, 'oppose', 2, 'nan', 1)),
        ('native-retimed', lambda g: change_row(g, 'oppose', 1, 99999, 1)),
        ('not-browsing', lambda g: change_row(g, 'oppose', 2, 0)),
        ('cancel-direction', lambda g: change_row(g, 'oppose', 5, 1)),
        ('cancel-motion', lambda g: change_row(g, 'oppose_end', 4, 100)),
        ('reverse-cancel', lambda g: change_row(g, 'reverse', 5, -1)),
        ('remaining-right', lambda g: change_row(g, 'remaining_right', 5, 0)),
        ('remaining-left', lambda g: change_row(g, 'remaining_left', 5, 0)),
        ('same-side-release', lambda g: change_row(g, 'same_remaining', 5, 0)),
        ('release-stuck', lambda g: change_row(g, 'stopped_end', 5, -1)),
        ('panel-release-stuck', lambda g: change_row(g, 'chat_end', 5, -1)),
        ('preopen-adopted', lambda g: change_row(g, 'preopen_end', 4, 100)),
        ('rebind-stuck', lambda g: change_row(g, 'rebind_end', 5, -1)),
        ('rebind-new-direction', lambda g: change_row(g, 'rebind_new', 5, -1)),
        ('pending-navigation', lambda g: change_row(g, 'pending_end', 4, 100)),
        ('pending-hud', lambda g: change_row(g, 'pending_end', 7, 1)),
        ('not-closed', lambda g: change_row(g, 'closed', 2, 1)),
        ('body-moved', lambda g: change_body(g, 2, 99999)),
        ('clock-moved', lambda g: change_body(g, 8, 99999)),
        ('velocity-leak', lambda g: change_body(g, 5, 1)),
        ('focus-unacted', lambda g: change_log(g, 'REWIND NAV EVENT 5 -1 0 0\n', '')),
        ('chat-unacted', lambda g: change_row(g, 'chat_focus_stop', 1, 0, 3)),
        ('console-unacted', lambda g: change_row(g, 'console_focus_stop', 3, 0, 3)),
        ('menu-unacted', lambda g: change_row(g, 'menu_focus_stop', 3, 0, 3)),
        ('focus-nonfinite', lambda g: change_row(g, 'menu_focus_stop', 3, 'nan', 3)),
        ('chat-cancel-direction', lambda g: change_row(g, 'chat_focus_end', 5, -1)),
        ('console-cancel-motion', lambda g: change_row(g, 'console_focus_end', 4, 100)),
        ('menu-cancel-motion', lambda g: change_row(g, 'menu_focus_end', 4, 100)),
        ('keyboard-cancel-motion', lambda g: change_row(g, 'keyboard_focus_end', 4, 100)),
        ('arrow-cancel-motion', lambda g: change_row(g, 'arrow_focus_end', 4, 100)),
        ('focus-repeat-restart', lambda g: change_row(g, 'chat_focus_repeat', 5, -1)),
        ('focus-return-restart', lambda g: change_row(g, 'chat_focus_return', 4, 100)),
        ('fresh-press-lost', lambda g: change_row(g, 'keyboard_focus_fresh', 5, 0)),
        ('mouse-only-cancel', lambda g: change_row(g, 'mouse_after', 5, 0)),
        ('opposed-release-restart', lambda g: change_row(g, 'opposed_focus_return', 4, 100)),
        ('opposed-repeat-restart', lambda g: change_row(g, 'opposed_focus_repeat', 5, 1)),
        ('closed-ownership-lost', lambda g: change_log(g, 'REWIND NAV EVENT 1 103 0 1\n', 'REWIND NAV EVENT 1 103 0 0\n', last=True)),
        ('cancel-hud-creep', lambda g: change_row(g, 'chat_focus_end', 6, 99999)),
        ('late-cancel', lambda g: change_row(g, 'chat_focus_stop', 5, -1)),
    ]
    for name, mutate in cases:
        dst = Path(tempfile.mkdtemp(prefix=name + '-', dir=a.output_dir))
        (dst / 'ftesurf/cfg/test').mkdir(parents=True)
        shutil.copytree(a.rig / 'ftesurf/logs', dst / 'ftesurf/logs')
        for p in (a.rig / 'ftesurf/cfg/test').glob('rewind_*.txt'):
            shutil.copy2(p, dst / 'ftesurf/cfg/test' / p.name)
        mutate(dst)
        try:
            with redirect_stdout(io.StringIO()):
                grade(dst)
        except (AssertionError, ValueError, IndexError, FileNotFoundError):
            continue
        raise AssertionError(f'grader accepted {name}; artifacts {dst}')
    print(f'{len(cases)+1} grader controls, 0 failed; retained under {a.output_dir}')


if __name__ == '__main__':
    main()
