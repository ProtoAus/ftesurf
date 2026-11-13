#!/usr/bin/env python3
"""Run extracted production CEM functions in qclib's standalone qcvm.

Requires an already-built qcvm (engine/qclib/Makefile target qcvm). Scores are
synthetic; this does not test movement, warm starts, or the batch dispatcher.
The output must be fresh and below an agent-owned task root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def extract(text, name):
    match = re.search(r'^(?:float|void)\([^\n]*\) ' + name + r' =\s*\{', text, re.M)
    if not match:
        raise ValueError(f'production function not found: {name}')
    pos, depth = match.end(), 1
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    return text[match.start():pos] + ';\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--qcvm', type=Path, required=True)
    ap.add_argument('--qcc', type=Path, default=Path('C:/FTESurf/src/fteqcc64.exe'))
    ap.add_argument('--baseline', default='2416c68920614fef89f33caac92b5c578cbb77ae')
    ap.add_argument('--mutate-nonnegative', action='store_true',
                    help='negative regression control; deliberately wrong validity gate, expected failure')
    args = ap.parse_args()
    out = args.out.resolve()
    if not any((parent / 'OWNER.md').is_file() for parent in out.parents):
        ap.error('--out must be below an owned task root')
    if out.exists():
        ap.error('--out must be fresh; preserve previous evidence')
    qcc, vm = args.qcc.resolve(strict=True), args.qcvm.resolve(strict=True)
    source = ROOT / 'src/server/sv_tasoptimize.qc'
    fixture = ROOT / 'tools/fixtures/jargon_cem.qc'
    tick_source = ROOT / 'src/shared/sh_defs.qc'
    text = source.read_text(encoding='utf-8')
    names = ['SV_TASOptSig0', 'SV_TASOptMod', 'SV_TASOptRand',
             'SV_TASOptCurveReset', 'SV_TASOptCurveNext', 'SV_TASOptCurveResult']
    parts = {name: extract(text, name) for name in names}
    if args.mutate_nonnegative:
        before = 'topt_kval[i] != -1'
        if parts['SV_TASOptCurveResult'].count(before) != 1:
            ap.error('negative control cannot identify the validity gate')
        parts['SV_TASOptCurveResult'] = parts['SV_TASOptCurveResult'].replace(before, 'topt_kval[i] >= 0')
    baseline_sha = subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', args.baseline + '^{commit}'], text=True, encoding='utf-8').strip()
    baseline = subprocess.check_output(
        ['git', '-C', str(ROOT), 'show', baseline_sha + ':src/server/sv_tasoptimize.qc'], text=True, encoding='utf-8')
    old = '\n'.join(extract(baseline, name).replace(name + ' =', alias + ' =')
                    for name, alias in [('SV_TASOptCurveNext', 'BaselineNext'),
                                        ('SV_TASOptCurveResult', 'BaselineResult')])
    defs = '\n'.join(re.findall(r'^#define TOPT_\w+[^\n]*', text, re.M))
    tick = re.search(r'^#define PM_TICK[^\n]*', tick_source.read_text(encoding='utf-8'), re.M).group(0)
    defs += '\n' + tick
    bodies = '\n'.join(parts.values()) + old
    fields = sorted(set(re.findall(r'e\.(topt_\w+)', bodies)))
    pre = '''void(string s) puts = #1;
string(float f) ftos = #2;
entity() spawn = #3;
float(float f) sqrt = #13;
float(float f) floor = #14;
float(float a,float b) min = { return a < b ? a : b; };
float(float a,float b) max = { return a > b ? a : b; };
float(float a,float b,float c) bound = { return max(a,min(b,c)); };
float(float a) fabs = { return a < 0 ? -a : a; };
float(string s) cvar = { return 0; };
string(string fmt, ...) sprintf = { return fmt; };
string(string a,string b) strcat = { return a; };
void(entity e,float p,string s) sprint = {};
float(float f) gettime = { return 0; };
void(entity e,float v) SV_TASOptArcKeep = {};
void(entity e,float v) SV_TASOptStatsSend = {};
void(entity e) SV_TASOptMemKeep = {};
float(entity e,float v) SV_TASOptEnergyShow = { return v; };
float(entity e,float j) SV_TASOptKnotTick = { return j; };
float held;
float(entity e) SV_TASOptBatchHeld = { return held; };
#define PRINT_HIGH 2
#define TRUE 1
#define FALSE 0
float topt_r1,topt_r2,topt_r3,topt_wmapn;
'''
    arrays = ['topt_kcur', 'topt_kbest', 'topt_kmean', 'topt_ksig', 'topt_kpop',
              'topt_kval', 'topt_kel', 'topt_bat_kcur', 'topt_wseed', 'topt_mempar',
              'topt_sprior', 'topt_kseed', 'topt_wmap', 'topt_dmap', 'topt_byaw',
              'topt_fyaw', 'topt_bside', 'topt_fside', 'topt_wvy', 'topt_fvy', 'topt_wvs', 'topt_fvs']
    generated = (defs + '\n' + pre + '\n'.join('.float ' + field + ';' for field in fields)
                 + '\n.float end_sys_fields;\n'
                 + '\n'.join('float ' + array + '[640];' for array in arrays)
                 + '\n' + bodies + fixture.read_text(encoding='utf-8'))
    out.mkdir(parents=True)
    (out / 'unit.qc').write_text(generated, encoding='utf-8')
    (out / 'progs.src').write_text('progs.dat\nunit.qc\n', encoding='utf-8')
    manifest = {
        'source_sha256': sha(source), 'fixture_sha256': sha(fixture),
        'tick_source_sha256': sha(tick_source),
        'driver_sha256': sha(Path(__file__)), 'qcc_sha256': sha(qcc), 'qcvm_sha256': sha(vm),
        'baseline_commit': baseline_sha, 'mutate_nonnegative': args.mutate_nonnegative,
        'functions': {name: hashlib.sha256(body.encode()).hexdigest() for name, body in parts.items()},
        'limits': 'Synthetic scores, no movement/scoring/game. Side effects stubbed; BatchHeld selected externally; '
                  'KnotTick=j with catch/flick disabled. No warm/demo/memory grid or main-dispatcher claim.'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    env = dict(os.environ)
    env['PATH'] = str(vm.parent) + os.pathsep + 'C:/msys64/ucrt64/bin' + os.pathsep + env.get('PATH', '')
    commands = [('compiler', [str(qcc), '-srcfile', 'progs.src']), ('stdout', [str(vm), 'progs.dat'])]
    for label, command in commands:
        result = subprocess.run(command, cwd=out, env=env, text=True, encoding='utf-8', stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=30)
        (out / (label + '.log')).write_text(result.stdout, encoding='utf-8')
        if result.returncode or (label == 'stdout' and ('PASS CEM checks=' not in result.stdout or 'FAIL ' in result.stdout)):
            print(result.stdout)
            raise SystemExit(f'FAIL {label} exit={result.returncode}; retained {out}')
    print((out / 'stdout.log').read_text(encoding='utf-8'), end='')
    print(f'Actual-QC CEM checks passed; synthetic-score unit scope only. Evidence: {out}')


if __name__ == '__main__':
    main()
