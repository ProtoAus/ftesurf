#!/usr/bin/env python3
"""Fail-closed demo navigation grader controls; copies private probes/logs only."""
import argparse
import contextlib
import io
from pathlib import Path
import shutil
import tempfile

from watch_navigation_smoke import grade


def field(gd, label, index, value):
    p = gd/'cfg/test'/f'watch_nav_{label}.txt'
    words = p.read_text().split()
    words[index] = str(value)
    if index == 4:
        words[5] = str(float(value)*100-11500)
    p.write_text(' '.join(words)+'\n')


def log_change(gd, old, new):
    p = gd/'logs/runlines_smoke.log'
    text = p.read_text()
    assert text.count(old) == 1
    p.write_text(text.replace(old, new))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    gd = a.rig/'ftesurf'
    with contextlib.redirect_stdout(io.StringIO()):
        grade(gd)
    print('PASS positive retained demo navigation')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='watch-nav-negatives-', dir=a.output_dir))
    cases = [
        ('missing-probe', lambda g: (g/'cfg/test/watch_nav_left1.txt').unlink()),
        ('unacted-probe', lambda g: log_change(g, 'WATCH NAV PROBE left1\n', 'ABSENT PROBE left1\n')),
        ('duplicate-probe', lambda g: log_change(g, 'WATCH NAV PROBE left1\n', 'WATCH NAV PROBE left1\nWATCH NAV PROBE left1\n')),
        ('runtime-error', lambda g: log_change(g, 'WATCH NAV PROBE left1\n', 'QC VM error\nWATCH NAV PROBE left1\n')),
        ('bad-open-state', lambda g: field(g, 'left1', 2, 0)),
        ('not-paused', lambda g: field(g, 'left1', 3, 0)),
        ('nonfinite-clock', lambda g: field(g, 'left1', 4, 'nan')),
        ('wrong-pose', lambda g: field(g, 'left1', 5, 99999)),
        ('wrong-velocity', lambda g: field(g, 'left1', 8, 0)),
        ('preopen-restart', lambda g: field(g, 'preopen', 4, 19)),
        ('no-held-scrub', lambda g: shutil.copy2(g/'cfg/test/watch_nav_preopen.txt', g/'cfg/test/watch_nav_left1.txt')),
        ('repeat-restart', lambda g: shutil.copy2(g/'cfg/test/watch_nav_left1.txt', g/'cfg/test/watch_nav_left2.txt')),
        ('chat-stop-drift', lambda g: field(g, 'chat_end', 4, 19)),
        ('ordinary-release-drift', lambda g: field(g, 'right_end', 4, 19)),
        ('wrong-tap', lambda g: field(g, 'tap', 4, 20)),
        ('opposed-drift', lambda g: field(g, 'oppose_end', 4, 19)),
        ('remaining-key-lost', lambda g: shutil.copy2(g/'cfg/test/watch_nav_oppose_end.txt', g/'cfg/test/watch_nav_oppose_release.txt')),
        ('same-key-lost', lambda g: shutil.copy2(g/'cfg/test/watch_nav_same_left.txt', g/'cfg/test/watch_nav_same_remaining.txt')),
        ('chat-preheld-restart', lambda g: field(g, 'chat_preheld', 4, 19)),
        ('rebind-release-drift', lambda g: field(g, 'rebind_end', 4, 19)),
        ('reopen-restart', lambda g: field(g, 'reopened', 4, 19)),
        ('console-release-drift', lambda g: field(g, 'console_end', 4, 19)),
        ('menu-drift', lambda g: field(g, 'menu_end', 4, 19)),
        ('focus-drift', lambda g: field(g, 'focus_end', 4, 19)),
        ('wrong-arrow', lambda g: field(g, 'arrow_left', 4, 14)),
        ('wrong-window-clamp', lambda g: field(g, 'clamp_end', 4, 41)),
        ('play-stays-paused', lambda g: field(g, 'play', 3, 1)),
        ('native-body-missing', lambda g: (g/'cfg/test/watch_body_last.txt').unlink()),
        ('native-body-drift', lambda g: (g/'cfg/test/watch_body_last.txt').write_text('body 1 0 0 0 0 0 0\n')),
        ('unacted-chain', lambda g: log_change(g, 'WATCH NAV EVENT focus 0 0\n', 'ABSENT EVENT focus 0 0\n')),
    ]
    for name, change in cases:
        dst = root/name/'ftesurf'
        for rel in ('cfg/test', 'logs'):
            shutil.copytree(gd/rel, dst/rel)
        change(dst)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                grade(dst)
        except (AssertionError, ValueError, IndexError, FileNotFoundError):
            print('PASS rejects', name)
        else:
            raise AssertionError(f'grader accepted {name}; artifacts {dst}')
    print(f'{len(cases)+1} counterfactual checks, 0 failed')
    print('Retained private controls:', root)


if __name__ == '__main__':
    main()
