#!/usr/bin/env python3
"""Bake every real Story/Event map, preserving per-map coverage and failures.

Input lists contain paths and belong in a private task root. Output reports are
aggregates only. This does not download replays, alter a board or verify native
runs. Use --baker to pin an inspected snapshot during a long batch.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def maps_from_story(path):
    mode, maps = '', set()
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        words = line.split('//', 1)[0].split()
        if words and words[0] == 'list':
            mode = words[1]
        if len(words) > 1 and words[0] == 'level' and mode in ('story', 'events') and words[1] != 'soon':
            if not re.fullmatch(r'[a-z0-9_-]{1,64}', words[1]):
                raise ValueError('unsafe map in roster')
            maps.add(words[1])
    if not maps:
        raise ValueError('empty Story/Event roster')
    return sorted(maps)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--story', type=Path, required=True)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--gamedir', type=Path, required=True)
    p.add_argument('--reports', type=Path, required=True)
    p.add_argument('--baker', type=Path, default=Path(__file__).with_name('rampwear.py'))
    p.add_argument('--only-maps', type=Path, help='JSON subset to refresh after a changed input/reader dependency')
    p.add_argument('--workers', type=int, default=2, choices=range(1, 9))
    p.add_argument('--timeout', type=int, default=3600)
    a = p.parse_args()
    allmaps = maps_from_story(a.story)
    maps = allmaps
    if a.only_maps:
        subset = json.loads(a.only_maps.read_text(encoding='utf-8'))
        if not isinstance(subset, list) or not all(isinstance(m, str) for m in subset) or not set(subset) <= set(allmaps):
            p.error('--only-maps must be a subset of the actual Story/Event roster')
        maps = sorted(set(subset))
    missing_inputs = [name for name in maps if not (a.inputs/(name+'.inputs.json')).is_file()]
    if missing_inputs:
        p.error('missing frozen replay-list(s) in --inputs: '+', '.join(missing_inputs))
    a.reports.mkdir(parents=True, exist_ok=True)
    a.gamedir.mkdir(parents=True, exist_ok=True)
    plan = {'story_sha256': hashlib.sha256(a.story.read_bytes()).hexdigest(),
            'baker_sha256': hashlib.sha256(a.baker.read_bytes()).hexdigest(),
            'maps': maps, 'full_roster_maps': allmaps, 'workers': a.workers, 'raw_provenance_NOTincluded': True}
    with (a.reports/'batch-plan.json').open('x') as f:
        json.dump(plan, f, indent=2)

    def one(name):
        report = a.reports/(name+'.json')
        log = a.reports/(name+'.log')
        if report.exists() or log.exists():
            raise ValueError('refusing to overwrite existing bake evidence: '+name)
        command = [sys.executable, '-B', str(a.baker), '--map', name,
                   '--gamedir', str(a.gamedir), '--report', str(report)]
        inputs = a.inputs/(name+'.inputs.json')
        if inputs.is_file():
            command += ['--replay-list', str(inputs)]
        start = time.monotonic()
        with log.open('xb') as f:
            try:
                result = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, timeout=a.timeout)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = -1
        if code or not report.is_file():
            text = log.read_text(encoding='utf-8', errors='replace')
            status = ('no_replays' if 'no replays for ' in text else
                      'no_placed_contacts' if 'nothing to draw' in text else
                      'execution_limit' if code == -1 else 'bake_failed')
            row = {'map': name, 'status': status, 'exit_code': code,
                   'elapsed_seconds': round(time.monotonic()-start, 3)}
            # Preserve a report emitted before a failure; never rewrite it into a pass.
            if not report.exists():
                report.write_text(json.dumps(row, indent=2)+'\n', encoding='utf-8')
            else:
                row = json.loads(report.read_text(encoding='utf-8'))
                if row.get('status') == 'ready':
                    row = dict(row, status='bake_failed', actual_report_preserved=True)
                row['exit_code'] = code
                row['elapsed_seconds'] = round(time.monotonic()-start, 3)
        else:
            row = json.loads(report.read_text(encoding='utf-8'))
            row['elapsed_seconds'] = round(time.monotonic()-start, 3)
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(one, name): name for name in maps}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print('%d/%d %s: %s; inputs=%d unique-recordings=%d placed=%d' %
                  (len(rows), len(maps), row['map'], row['status'], row.get('input_files', 0),
                   row.get('unique_sources', 0), row.get('counts', {}).get('placed', 0)), flush=True)
    rows.sort(key=lambda row: row['map'])
    summary = dict(plan, results=rows, ready=sum(row['status']=='ready' for row in rows),
                   incomplete=[row['map'] for row in rows if row['status']!='ready'])
    with (a.reports/'batch-complete.json').open('x') as f:
        json.dump(summary, f, indent=2)
    print('READY %d/%d; %d explicit gaps (not fabricated coverage)' %
          (summary['ready'], len(maps), len(summary['incomplete'])), flush=True)
    return 0 if not summary['incomplete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
