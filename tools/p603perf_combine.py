#!/usr/bin/env python3
"""Explicitly combine retained cost arms, never relaunch or overwrite source evidence.

Failed source reports remain failed. Each selected arm must pass the complete final
reader. Samples are from separate processes/times, not a simultaneous benchmark.
"""
import argparse
import json
from pathlib import Path
import shutil

from p590bridge import sha
from p603perf import ARMS, grade, summary


def combine(sources, out):
    if out.exists(): raise RuntimeError('combined output must be fresh')
    if not any((p / 'OWNER.md').is_file() for p in (out.resolve(), *out.resolve().parents)):
        raise RuntimeError('combined output requires ancestor OWNER.md')
    reports = {arm: json.loads((source / 'report.json').read_text()) for arm, source in sources.items()}
    common = ('rows', 'repeats', 'samples', 'csprogs_sha256', 'engine_sha256', 'plugin_sha256')
    first = reports['native']
    for arm, report in reports.items():
        if arm not in report['arms'] or any(report.get(k) != first.get(k) for k in common):
            raise RuntimeError('selected arm absent or unequal workload/product: ' + arm)
    out.mkdir(parents=True)
    merged = {k: v for k, v in first.items() if k != 'arms'}
    merged['planned_arms'] = list(ARMS); merged['arms'] = {}
    merged['combination'] = {'limits': 'Explicit selected arms from different times/processes; no claim of simultaneous or controlled hardware load.', 'sources': {}}
    for arm in ARMS:
        source = sources[arm]
        game = out / arm / 'ftesurf'; game.mkdir(parents=True)
        for name in ('logs', 'screenshots'):
            shutil.copytree(source / arm / 'ftesurf' / name, game / name)
        shutil.copy2(source / arm / 'ftesurf/perf.cfg', game / 'perf.cfg')
        merged['arms'][arm] = reports[arm]['arms'][arm]
        merged['combination']['sources'][arm] = {'rig': str(source.resolve()),
                                               'report_sha256': sha(source / 'report.json'),
                                               'log_sha256': sha(source / arm / 'ftesurf/logs/perf.log')}
    (out / 'report.json').write_text(json.dumps(merged, indent=2) + '\n')
    errors = grade(out)
    (out / 'grade.json').write_text(json.dumps({'errors': errors}, indent=2) + '\n')
    if not errors: (out / 'summary.json').write_text(json.dumps(summary(out), indent=2) + '\n')
    for error in errors: print('FAIL', error)
    print('Combined cost evidence', out, 'failures', len(errors)); return int(bool(errors))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for arm in ARMS: p.add_argument('--' + arm, type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(combine({arm: getattr(a, arm) for arm in ARMS}, a.out))
