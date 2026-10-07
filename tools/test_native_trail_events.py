#!/usr/bin/env python3
"""Fail-closed grader controls on a retained PRIVATE native-events rig.

python tools/test_native_trail_events.py --rig <private rig> --output-dir <private dir>
Copies only probe/log/screenshot artifacts; originals are never changed.
"""
import argparse
import contextlib
import io
from pathlib import Path
import shutil
import tempfile

from native_trail_events import grade


def field(gd, name, label, index, value):
    p = gd / 'cfg/test' / name
    rows = p.read_text().splitlines()
    matches = [i for i, line in enumerate(rows) if line.split()[0] == label]
    assert len(matches) == 1, (name, label)
    i = matches[0]
    words = rows[i].split()
    words[index] = str(value)
    rows[i] = ' '.join(words)
    p.write_text('\n'.join(rows)+'\n')


def log_change(gd, old, new):
    p = gd / 'logs/runlines_server.log'
    text = p.read_text()
    assert text.count(old) == 1
    p.write_text(text.replace(old, new))


def malformed(gd, name, kind):
    p = gd / 'cfg/test' / name
    rows = p.read_text().splitlines()
    if kind == 'empty':
        rows = []
    elif kind == 'duplicate':
        rows.append(rows[-1])
    else:
        rows[-1] = ' '.join(rows[-1].split()[:-1])
    p.write_text('\n'.join(rows)+'\n')


def raw_break(gd):
    p = gd / 'cfg/test/stitch_live_end.txt'
    rows = p.read_text().splitlines()
    for i in range(2, len(rows)):
        w = rows[i].split()
        if float(w[8]):
            w[8] = '0'
            rows[i] = ' '.join(w)
            p.write_text('\n'.join(rows)+'\n')
            return
    raise AssertionError('positive fixture had no break')


def quarter(gd, column, value):
    p = gd / 'cfg/test/visual_native1_cursor.txt'
    rows = p.read_text().splitlines()
    w = rows[2].split()
    w[column] = str(value)
    rows[2] = ' '.join(w)
    p.write_text('\n'.join(rows)+'\n')


def missing_quarter(gd):
    p = gd / 'cfg/test/visual_native1_cursor.txt'
    rows = p.read_text().splitlines()
    del rows[2]
    p.write_text('\n'.join(rows)+'\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    gd = a.rig / 'ftesurf'
    with contextlib.redirect_stdout(io.StringIO()):
        grade(gd)
    print('PASS positive retained native fixture')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='native-event-negatives-', dir=a.output_dir))
    cases = [
        ('missing-touch', lambda g: (g/'cfg/test/native_touch_keep.txt').unlink()),
        ('no-acted-touch', lambda g: log_change(g, 'NATIVE EVENT TOUCH keep', 'NATIVE EVENT ABSENT keep')),
        ('duplicate-touch', lambda g: log_change(g, 'NATIVE EVENT TOUCH keep', 'NATIVE EVENT TOUCH keep\nNATIVE EVENT TOUCH keep')),
        ('runtime-error', lambda g: log_change(g, 'NATIVE EVENT TOUCH keep', 'QC VM error\nNATIVE EVENT TOUCH keep')),
        ('wrong-native-state', lambda g: field(g, 'native_touch_keep.txt', 'before', 2, 1)),
        ('missing-recorder', lambda g: field(g, 'native_touch_keep.txt', 'after', 3, 0)),
        ('native-clock-reset', lambda g: field(g, 'native_touch_keep.txt', 'after', 1, 1)),
        ('keep-velocity-changed', lambda g: field(g, 'native_touch_keep.txt', 'after', 8, 1234)),
        ('zero-velocity-kept', lambda g: field(g, 'native_touch_zero.txt', 'after', 8, 1234)),
        ('wrong-destination', lambda g: field(g, 'native_touch_zero.txt', 'after', 4, 1234)),
        ('wrong-yaw', lambda g: field(g, 'native_touch_keep.txt', 'after', 11, 90)),
        ('nonfinite-touch', lambda g: field(g, 'native_touch_keep.txt', 'after', 4, 'nan')),
        ('truncated-touch', lambda g: malformed(g, 'native_touch_keep.txt', 'truncate')),
        ('duplicate-touch-row', lambda g: malformed(g, 'native_touch_keep.txt', 'duplicate')),
        ('raw-missing-break', raw_break),
        ('paused-native-clock', lambda g: field(g, 'native_pose_pause_end.txt', 'pose', 1, 0)),
        ('held-pause', lambda g: field(g, 'native_pose_pause_end.txt', 'pose', 4, 1)),
        ('native-pause-drift', lambda g: field(g, 'native_pose_pause_end.txt', 'pose', 5, 0)),
        ('native-pause-speed', lambda g: field(g, 'native_pose_pause_end.txt', 'pose', 8, 10)),
        ('pin-clock-drift', lambda g: field(g, 'native_pose_freeze_second.txt', 'pose', 1, 99999)),
        ('unfrozen-pin', lambda g: field(g, 'native_pose_freeze_second.txt', 'pose', 4, 0)),
        ('cursor-clock-drift', lambda g: field(g, 'native_cursor_second.txt', 'cursor', 5, 10)),
        ('cursor-body-drift', lambda g: field(g, 'native_cursor_second.txt', 'cursor', 7, 10)),
        ('missing-cursor', lambda g: malformed(g, 'native_cursor_first.txt', 'empty')),
        ('truncated-cursor', lambda g: malformed(g, 'native_cursor_first.txt', 'truncate')),
        ('duplicate-cursor', lambda g: malformed(g, 'native_cursor_first.txt', 'duplicate')),
        ('nonfinite-cursor', lambda g: field(g, 'native_cursor_first.txt', 'cursor', 5, 'inf')),
        ('wrong-render-mode', lambda g: field(g, 'native_view_chase.txt', 'view', 1, 0)),
        ('wrong-render-pose', lambda g: field(g, 'native_view_first.txt', 'view', 4, 1e6)),
        ('wrong-render-yaw', lambda g: field(g, 'native_view_chase.txt', 'view', 8, 45)),
        ('missing-return-view', lambda g: (g/'cfg/test/native_view_return.txt').unlink()),
        ('wrong-return-view', lambda g: field(g, 'native_view_return.txt', 'view', 4, 1e6)),
        ('aliased-camera-pixels', lambda g: shutil.copy2(g/'screenshots/native_events_first.png', g/'screenshots/native_events_chase.png')),
        ('wrong-return-pixels', lambda g: shutil.copy2(g/'screenshots/native_events_chase.png', g/'screenshots/native_events_return.png')),
        ('missing-return-image', lambda g: (g/'screenshots/native_events_return.png').unlink()),
        ('missing-quarter', missing_quarter),
        ('nonfinite-camera', lambda g: quarter(g, 15, 'nan')),
        ('wrong-visual-position', lambda g: quarter(g, 6, 1e6)),
        ('wrong-visual-velocity', lambda g: quarter(g, 9, 1e6)),
        ('wrong-raw-view', lambda g: quarter(g, 13, 45)),
        ('wrong-first-camera', lambda g: quarter(g, 15, 1e6)),
        ('wrong-chase-tangent', lambda g: quarter(g, 25, 12345)),
        ('compiled-failure', lambda g: field(g, 'visual_units.txt', 'units', 2, 1)),
    ]
    for name, change in cases:
        dst = root / name / 'ftesurf'
        for rel in ('cfg/test', 'logs', 'screenshots'):
            shutil.copytree(gd / rel, dst / rel)
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
