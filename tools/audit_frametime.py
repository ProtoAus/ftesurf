#!/usr/bin/env python3
"""Audit actual r_frametime sampler C with a deterministic clock (no GPU/client).

Diagnostic, not a game benchmark or a copied implementation. Extracts the static
sampler/statistics from an explicitly selected engine source and records its hash.
Known defects may disappear after a fix; observations, not their presence, are the
output. See frametime-smoothness-audit.md for scope and interpretation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

PREAMBLE = r'''
#include <stdio.h>
#include <string.h>
typedef int qboolean;
typedef float vec3_t[3];
#define true 1
#define false 0
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define bound(a,b,c) min(max(a,b),c)
#define VectorCopy(a,b) memcpy((b),(a),sizeof(vec3_t))
typedef struct { float value; int ival; } cvar_t;
static cvar_t r_frametime = {1,1}, r_frametime_seconds = {10,10}, r_frametime_window = {30,30}, idlefps = {0,0};
static struct {int activeapp;} vid = {true};
static struct {vec3_t vieworg,viewangles;} r_refdef;
static double clock_now;
static double Sys_DoubleTime(void) { return clock_now; }
static cvar_t *Cvar_FindVar(const char *name) { (void)name; return &idlefps; }
'''

CASES = r'''
static void sample_at(double t) { clock_now = t; R_FrameTime_Sample(); }
static void reset_at(double t, float seconds) {
    r_frametime_window.value = seconds;
    ft.on = false;
    sample_at(t);
}
int main(void) {
    int i;
    double t;
    reset_at(0, 1);
    sample_at(.6); sample_at(1.0); sample_at(1.61);
    R_FrameTime_Stats();
    printf("{\"expiry\":{\"count\":%d,\"actual\":[%.6f,%.6f],\"cache\":[%.6f,%.6f,%.6f],\"overflow_rank1\":%.6f},",
        ft.count, ft.ms[(ft.head-ft.count)&(FT_RING-1)], ft.ms[(ft.head-1)&(FT_RING-1)],
        ft.bad[0].ms, ft.bad[1].ms, ft.bad[2].ms, R_FrameTime_Over(1));
    reset_at(0, 120);
    t = .9; sample_at(t);
    for (i=0; i<FT_RING; ++i) { t += .0005; sample_at(t); }
    R_FrameTime_Stats();
    printf("\"capacity\":{\"count\":%d,\"retained_first\":%.6f,\"retained_last\":%.6f,\"reported_worst\":%.6f},",
        ft.count, ft.ms[(ft.head-ft.count)&(FT_RING-1)], ft.ms[(ft.head-1)&(FT_RING-1)], ft.worst);
    reset_at(0, 120);
    sample_at(.01); sample_at(1.511); sample_at(1.521);
    R_FrameTime_Stats();
    printf("\"longstall\":{\"count\":%d,\"samples_ms\":%.6f,\"elapsed_ms\":1521,\"worst\":%.6f},", ft.count,ft.sum,ft.worst);
    reset_at(0, 120);
    t = 0;
    for (i=0; i<999; ++i) { t+=.01; sample_at(t); }
    t+=.1; sample_at(t); R_FrameTime_Stats();
    printf("\"semantics\":{\"count\":%d,\"low1_fps\":%.6f,\"low01_fps\":%.6f,\"median_ms\":%.6f},",
        ft.count,1000/ft.low1,1000/ft.low01,ft.median);
    reset_at(0, 120);
    sample_at(1); sample_at(2.001); sample_at(2.011); R_FrameTime_Stats();
    printf("\"cutoff\":{\"count\":%d,\"samples_ms\":%.6f,\"worst\":%.6f}}\n",ft.count,ft.sum,ft.worst);
    return 0;
}
'''


def audit(source, out, cc):
    source = source.resolve(strict=True)
    out = out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in (out, *out.parents)):
        raise ValueError('--out must be under an owned task root with OWNER.md')
    text = source.read_text(encoding='utf-8')
    start = text.index('#define FT_RING ')
    end = text.index('\nstatic void R_FrameTime_Draw', start)
    body = text[start:end]
    for anchor in ('R_FrameTime_Sample(void)', 'R_FrameTime_Stats(void)',
                   'R_FrameTime_Over(int fromtop)', 'ft.ms[ft.head]'):
        if anchor not in body:
            raise ValueError('unsupported sampler layout: missing ' + anchor)
    out.mkdir(parents=True, exist_ok=True)
    cpath = out / 'frametime_actual.c'
    binary = out / ('frametime_actual.exe' if os.name == 'nt' else 'frametime_actual')
    cpath.write_text(PREAMBLE + body + CASES, encoding='utf-8')
    command = [cc, '-std=c99', '-O2', '-Wall', '-Wextra', str(cpath), '-o', str(binary)]
    env = os.environ.copy()
    # Match build.ps1's MSYS2 UCRT compiler environment; cc1 needs its DLLs too.
    env['PATH'] = str(Path(cc).resolve().parent) + os.pathsep + env.get('PATH', '')
    build = subprocess.run(command, capture_output=True, text=True, env=env)
    (out / 'build.log').write_text(build.stdout + build.stderr, encoding='utf-8')
    if build.returncode:
        raise RuntimeError(f'compiler exit {build.returncode}; see {out / "build.log"}')
    run = subprocess.run([str(binary)], capture_output=True, text=True, env=env, check=True)
    observed = json.loads(run.stdout)
    # Positive witnesses: prove the clock drove real accepted/expired/evicted samples.
    if observed['expiry']['count'] != 2 or observed['expiry']['actual'] != [400, 610]:
        raise RuntimeError('expiry stimulus did not act: ' + run.stdout)
    if observed['capacity']['count'] != 65536 or observed['capacity']['retained_first'] != .5 or observed['capacity']['retained_last'] != .5:
        raise RuntimeError('capacity stimulus did not act: ' + run.stdout)
    if observed['semantics']['count'] != 1000:
        raise RuntimeError('tail sample-count stimulus did not act: ' + run.stdout)
    result = {
        'source': str(source),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'extracted_body_sha256': hashlib.sha256(body.encode()).hexdigest(),
        'scope': 'literal sampler/statistics C; stub clock/cvars/view metadata; no GPU/runtime performance claim',
        'build_command': command,
        'build_diagnostics': build.stdout + build.stderr,
        'observed': observed,
        'findings': {
            'duplicate_after_expiry': observed['expiry']['cache'][:2] == [610, 610],
            'overflow_rank_mismatch': observed['expiry']['overflow_rank1'] != 400,
            'stale_capacity_worst': observed['capacity']['reported_worst'] != .5,
            'longstall_excluded': observed['longstall']['count'] == 2 and observed['longstall']['samples_ms'] == 20,
        },
        'tail1_exact_reference_fps': 1000 / ((100 + 9 * 10) / 10),
        'tail01_exact_reference_fps': 10,
    }
    (out / 'audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='inspected engine/client/cl_screen.c')
    parser.add_argument('--out', required=True, type=Path, help='output under an owned task root')
    parser.add_argument('--cc', help='GCC-compatible C compiler; defaults to clang, gcc, then cc on PATH')
    args = parser.parse_args()
    cc = args.cc or next((path for name in ('clang', 'gcc', 'cc') if (path := shutil.which(name))), None)
    if not cc:
        parser.error('no C compiler found; use the existing supported build toolchain with --cc')
    print(json.dumps(audit(args.source, args.out, cc), indent=2))


if __name__ == '__main__':
    main()
