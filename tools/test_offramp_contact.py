#!/usr/bin/env python3
"""Acted positive + counterfactual refusals for private off-ramp stage grading."""
import argparse
from pathlib import Path

from offramp_contact import grade_text


def drop(text, tag, pred=lambda row: True):
    return '\n'.join(line for line in text.splitlines() if not (
        f'OFFRAMP_{tag} ' in line and pred(line.split(f'OFFRAMP_{tag} ', 1)[1].split()))) + '\n'


def change(text, tag, index, value, pred=lambda row: True):
    out = []
    changed = False
    for line in text.splitlines():
        token = f'OFFRAMP_{tag} '
        if token in line and not changed:
            prefix, tail = line.split(token, 1)
            row = tail.split()
            if pred(row):
                row[index] = str(value)
                line = prefix + token + ' '.join(row)
                changed = True
        out.append(line)
    assert changed, f'Control {tag} did not ACT'
    return '\n'.join(out) + '\n'


def first(text, tag):
    return next(line for line in text.splitlines() if f'OFFRAMP_{tag} ' in line) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rig', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path)
    a = ap.parse_args()
    gd = a.rig / 'ftesurf' if (a.rig / 'ftesurf/logs').is_dir() else a.rig
    server = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    client = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    result = grade_text(server, client)
    assert result['fix_acceptance'] == 'NOT_TESTED'
    print('PASS acted positive (native/sample/mark/actual-render stages; NOT fix acceptance)')
    leave = lambda r: r[2] == '2' and r[3] == '9'
    controls = [
        ('missing-native', drop(server, 'NATIVE'), client),
        ('client-fake-native-authority', server, client + first(server, 'NATIVE')),
        ('server-fake-sample-authority', server + first(client, 'SAMPLE'), client),
        ('unacted-native-ride', '\n'.join(
            (' '.join(line.split()[:]) if 'OFFRAMP_NATIVE ' not in line else
             line.split('OFFRAMP_NATIVE ', 1)[0] + 'OFFRAMP_NATIVE ' +
             ' '.join(['0' if i == 2 else v for i, v in enumerate(line.split('OFFRAMP_NATIVE ', 1)[1].split())]))
            for line in server.splitlines()) + '\n', client),
        ('duplicate-native', server + first(server, 'NATIVE'), client),
        ('invalid-native-plane', change(server, 'NATIVE', 12, 0, lambda r: r[2] == '1'), client),
        ('native-contact-fake', change(server, 'PACKET', 5, 0, lambda r: r[5] == '1' and r[3] == '2'), client),
        ('missing-anchor', drop(server, 'ANCHOR'), client),
        ('clock-anchor-fake', change(server, 'ANCHOR', 1, 999999, lambda r: float(r[1]) > 0), client),
        ('missing-samples', server, drop(client, 'SAMPLE')),
        ('duplicate-sample', server, client + first(client, 'SAMPLE')),
        ('nonfinite-body', server, change(client, 'BODY', 2, 'nan')),
        ('missing-body', server, drop(client, 'BODY')),
        ('held-kind-fake', server, change(client, 'SAMPLE', 6, 0, lambda r: r[6] == '2')),
        ('held-state-fake', server, change(client, 'SAMPLE', 7, 0, lambda r: r[7] == '1')),
        ('last-contact-fake', server, change(client, 'BODY', 8, -123)),
        ('break-stamp-not-cleared', server, change(client, 'SAMPLE', 9, 1,
             lambda r: not (int(r[5]) & 16) and r[7] == '0' and r[9] == '0')),
        ('command-clock-reversed', server, change(client, 'SAMPLE', 4, 999999)),
        ('missing-leave', server, drop(client, 'EVENT', leave)),
        ('leave-ordinal-fake', server, change(client, 'EVENT', 1, 999999, leave)),
        ('mark-position-fake', server, change(client, 'EVENT', 5, 999999, leave)),
        ('missing-render', server, drop(client, 'RENDER')),
        ('render-position-fake', server, change(client, 'RENDER', 5, 999999, lambda r: r[2] == '2')),
        ('render-time-fake', server, change(client, 'RENDER', 3, 999999, lambda r: r[2] == '2')),
        ('missing-held-view', server, drop(client, 'HELD')),
        ('held-selection-fake', server, change(client, 'HELD', 0, -123)),
        ('missing-completion', server, client.replace('RUNLINES COMPLETE', 'UNACTED')),
        ('unknown-trace', server, client + 'OFFRAMP_MYSTERY 1\n'),
        ('malformed-sample', server, client + 'OFFRAMP_SAMPLE 1\n'),
        ('runtime-fault', server, client + 'QC VM error\n'),
    ]
    failed = 0
    for label, s, c in controls:
        if a.output_dir:
            out = a.output_dir / label
            out.mkdir(parents=True, exist_ok=True)
            (out / 'server.log').write_text(s)
            (out / 'client.log').write_text(c)
        try:
            grade_text(s, c)
        except AssertionError as e:
            print(f'PASS {label}: refused ({e})')
        else:
            print(f'FAIL {label}: malformed/unacted copy was accepted')
            failed += 1
    print(f'{len(controls)+1} controls, {failed} failed')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
