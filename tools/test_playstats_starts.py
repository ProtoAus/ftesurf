#!/usr/bin/env python3
"""Execute literal QC dedup/reset bodies and the explicit-retry branch in C.

Entity/vector access is adapted to C; zone membership and counter storage are
bounded stubs. This is a helper/integration-hook control, NOT a QC VM playtest.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:brace], text[brace:end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--weak', action='store_true')
    args = parser.parse_args()
    stats = (ROOT / 'src/server/sv_playstats.qc').read_text()
    timer = (ROOT / 'src/server/sv_timer.qc').read_text()
    _, reset = block(stats, 'void(entity e) PlayStats_StageReset =')
    _, stage = block(stats, 'void(entity e, float track, float leg) PlayStats_Stage =')
    _, restart = block(timer, 'void(entity e) SV_TimerRestartSeg =')
    condition, failure = block(restart, 'if (!SV_ZoneInBox(')
    if failure.count('PlayStats_StageReset(e);') != 1:
        raise ValueError('Explicit retry reset anchor drift')
    if args.weak:
        failure = failure.replace('PlayStats_StageReset(e);', '')
    body = (condition + failure).replace('e.', 'e->').replace("'0 0 0'", '0')
    source = r'''
#include <stdio.h>
#include <stdlib.h>
#define TRUE 1
#define FALSE 0
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
typedef struct {int ps_stage_begun,run_st_fails,lobby_sty_fails,run_leg_zone,origin;} state;
typedef state *entity;
static int counts[12][24],outside;
static void PlayStats_Attempt(entity e,float t,float l) {(void)e;counts[(int)t][(int)l]++;}
static int SV_ZoneInBox(int z,int p,int a,int b){(void)z;(void)p;(void)a;(void)b;return !outside;}
static void PlayStats_StageReset(entity e) __RESET__
static void PlayStats_Stage(entity e,float track,float leg) __STAGE__
static void retry(entity e) { __RETRY__ }
int main(void) {
 state value={0};entity e=&value;
 PlayStats_Stage(e,0,2);CHECK(counts[0][2]==1); /* forward crossing */
 PlayStats_Stage(e,0,2);CHECK(counts[0][2]==1); /* ordinary departure/rebase */
 outside=1;retry(e);CHECK(e->run_st_fails==1); /* !r outside */
 outside=0;retry(e);retry(e);CHECK(e->run_st_fails==1); /* in-box repeats preserve pending start */
 PlayStats_Stage(e,0,2);CHECK(counts[0][2]==2); /* retry departure */
 retry(e);PlayStats_Stage(e,0,2);CHECK(counts[0][2]==2); /* same-box reset is not a new attempt */
 PlayStats_StageReset(e);PlayStats_Stage(e,0,2);CHECK(counts[0][2]==3); /* walk-back failure */
 PlayStats_StageReset(e);PlayStats_Stage(e,1,3);CHECK(counts[1][3]==1); /* another track/stage */
 CHECK(counts[0][2]==3);
 puts("PASS literal stage helpers + explicit-retry branch: forward/rebase once, outside retry, repeated in-box retry, walk-back, track separation");
 return 0;
}
'''
    source = source.replace('__RESET__', reset.replace('e.', 'e->'))
    source = source.replace('__STAGE__', stage.replace('e.', 'e->')).replace('__RETRY__', body)
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='stage-starts-', dir=args.out) as folder:
        folder = Path(folder)
        cfile, exe = folder / 'check.c', folder / 'check.exe'
        cfile.write_text(source)
        subprocess.run([args.cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(cfile), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
