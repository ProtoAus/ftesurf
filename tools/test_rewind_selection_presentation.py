#!/usr/bin/env python3
"""Counterfactual copies of actual draw/clock probes; retain private artifacts."""
import argparse
import contextlib
import io
from pathlib import Path
import shutil
from rewind_selection_presentation import grade


def row(gd, label, field, column, value):
    p = gd / f'cfg/test/resume_ui_{label}.txt'
    lines = p.read_text().splitlines()
    found = [i for i, s in enumerate(lines) if s.startswith(field + ' ')]
    assert len(found) == 1
    words = lines[found[0]].split()
    words[column + 1] = str(value)
    lines[found[0]] = ' '.join(words)
    p.write_text('\n'.join(lines) + '\n')


def replace(gd, rel, old, new):
    p = gd / rel
    text = p.read_text()
    assert old in text
    p.write_text(text.replace(old, new, 1))


def caption(gd, label, text):
    p = gd / f'cfg/test/resume_ui_{label}.txt'
    lines = p.read_text().splitlines()
    assert lines[-1].startswith('text ')
    lines[-1] = 'text ' + text
    p.write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    cases = [
        ('positive', None),
        ('missing-caption', lambda g: caption(g, 'warm1_cursor', 'REWIND resume here')),
        ('wrong-request', lambda g: caption(g, 'warm1_cursor', 'sampled request 0:00.000 -- nearest recorded position')),
        ('sample-display-collapsed', lambda g: row(g, 'warm1_cursor', 'cursor', 1, 0)),
        ('display-clock', lambda g: row(g, 'warm1_cursor', 'panel', 0, 0)),
        ('pending-unacted', lambda g: row(g, 'warm1_pending', 'phase', 1, 0)),
        ('pending-native-claim', lambda g: caption(g, 'warm1_pending', 'native resume 0:00.000 -- requested 0:00.000')),
        ('pending-request', lambda g: caption(g, 'warm1_pending', 'requested 0:00.000 -- waiting for native snapshot')),
        ('held-unacted', lambda g: row(g, 'warm1_hold1', 'phase', 2, 0)),
        ('practice-native-claim', lambda g: row(g, 'warm1_hold1', 'phase', 4, 1)),
        ('untimed-native-claim', lambda g: row(g, 'warm1_hold1', 'ack', 0, -1)),
        ('uncorrelated-native-claim', lambda g: row(g, 'warm1_hold1', 'ack', 1, 0)),
        ('unfrozen', lambda g: row(g, 'warm1_hold1', 'ack', 6, 0)),
        ('timer-not-native', lambda g: row(g, 'warm1_hold1', 'panel', 0, 0)),
        ('native-caption', lambda g: caption(g, 'warm1_hold1', 'native resume 0:00.000 -- requested 0:00.000 (+0.000s)')),
        ('delta-caption', lambda g: replace(g, 'cfg/test/resume_ui_warm1_hold1.txt', 's)', 'x)')),
        ('held-caption-creep', lambda g: caption(g, 'warm1_hold2', 'native resume 0:59.000 -- requested 0:00.000 (+0.000s)')),
        ('stale-after-close', lambda g: caption(g, 'warm1_release', 'native resume 0:00.000')),
        ('missing-probe', lambda g: (g / 'cfg/test/resume_ui_cold3_hold2.txt').unlink()),
        ('nonfinite', lambda g: row(g, 'warm1_hold1', 'panel', 1, 'nan')),
        ('short-field', lambda g: replace(g, 'cfg/test/resume_ui_warm1_hold1.txt', 'panel ', 'other ')),
        ('probe-unacted', lambda g: replace(g, 'logs/runlines_smoke.log', 'RESUMEUI PROBE warm1_hold1', 'NO PROBE warm1_hold1')),
        ('probe-duplicate', lambda g: replace(g, 'logs/runlines_smoke.log', 'RESUMEUI PROBE warm1_hold1', 'RESUMEUI PROBE warm1_hold1\nRESUMEUI PROBE warm1_hold1')),
        ('tie-unit-failed', lambda g: replace(g, 'logs/runlines_server.log', 'RESUMEUI TIES 5 0', 'RESUMEUI TIES 5 1')),
        ('presentation-unit-failed', lambda g: replace(g, 'logs/runlines_smoke.log', 'RESUMEUI UIUNITS 9 0', 'RESUMEUI UIUNITS 9 1')),
    ]
    for name, mutate in cases:
        gd = a.output_dir / name / 'ftesurf'
        shutil.copytree(a.rig / 'ftesurf/cfg/test', gd / 'cfg/test')
        shutil.copytree(a.rig / 'ftesurf/logs', gd / 'logs')
        if mutate:
            mutate(gd)
        accepted = True
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                grade(gd)
            except (AssertionError, ValueError, IndexError, FileNotFoundError):
                accepted = False
        assert accepted == (mutate is None), ('grader outcome', name, gd)
        print('PASS', name)
    print(f'{len(cases)} presentation counterfactual controls, 0 failed; retained {a.output_dir}')


if __name__ == '__main__':
    main()
