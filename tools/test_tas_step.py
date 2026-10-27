#!/usr/bin/env python3
"""Compile/test P1055's actual native admission helper; not a mover/runtime proof.

python tools/test_tas_step.py --engine <checkout> --out <owned-task-root>/header-check
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

SOURCE = r'''
#include <stdio.h>
#include "sv_tas.h"
static int checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); return 1; } } while (0)
int main(void) {
    int i;
    CHECK(SV_TASClockSupported(1, .015f, 1, 0));
    CHECK(SV_TASClockSupported(1, .015f, 1, .006f));
    CHECK(!SV_TASClockSupported(0, .015f, 1, 0));
    CHECK(!SV_TASClockSupported(1, .01f, 1, 0));
    CHECK(!SV_TASClockSupported(1, .01499991f, 1, .01498999f));
    CHECK(!SV_TASClockSupported(1, .01500009f, 1, 0));
    CHECK(!SV_TASClockSupported(1, .015f, .5f, 0));
    CHECK(!SV_TASClockSupported(1, .015f, 1, -.001f));
    CHECK(!SV_TASClockSupported(1, .015f, 1, .015f));
    CHECK(!SV_TASClockSupported(1, .015f, 1, .015f-SV_TAS_EPSILON));
    CHECK(!SV_TASClockSupported(1, NAN, 1, 0));
    CHECK(!SV_TASClockSupported(1, .015f, 1, NAN));
    CHECK(!SV_TASClockSupported(1, .015f, 1, INFINITY));
    CHECK(SV_TASFresh(5, 0, 0));
    CHECK(SV_TASFresh(6, 5, 1));
    CHECK(!SV_TASFresh(5, 5, 1));
    CHECK(!SV_TASFresh(4, 5, 1));
    CHECK(SV_TASFresh(0, UINT32_MAX, 1));
    CHECK(!SV_TASFresh(UINT32_MAX, 0, 1));
    CHECK(!SV_TASFresh(UINT32_C(0x80000000), 0, 1));
    CHECK(SV_TASPlan(0,0,0,0,0,0,0,NAN,NAN)==SV_TAS_NORMAL);
    CHECK(SV_TASPlan(1,0,1,1,1,1,0,1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,0,1,1,0,1,0)==SV_TAS_CANCEL);
    CHECK(SV_TASPlan(1,1,1,1,1,1,7,1,0)==SV_TAS_CANCEL);
    CHECK(SV_TASPlan(1,1,0,1,1,1,7,1,0)==SV_TAS_CANCEL);
    CHECK(SV_TASPlan(1,1,0,1,1,0,7,1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,0,1,0,1,7,1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,0,1,1,1,0,1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,0,1,0,1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,0,0,1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,0,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,129,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,-1,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,.5f,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,NAN,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,INFINITY,0)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,1,NAN)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,1,16000000)==SV_TAS_BLOCK);
    CHECK(SV_TASPlan(1,1,1,1,1,1,0,128,15999999)==SV_TAS_BLOCK);
    for(i=1;i<=128;++i)
        CHECK(SV_TASPlan(1,1,1,1,1,1,0,(float)i,0)==SV_TAS_STEP);
    printf("%d actual-C admission checks, 0 failed\n", checks);
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--compiler', default='C:/msys64/ucrt64/bin/gcc.exe')
    a = p.parse_args()
    if not any((x / 'OWNER.md').is_file() for x in [a.out.resolve(), *a.out.resolve().parents]):
        p.error('--out needs an owned task-root ancestor')
    # A general float32 movement counter loses +1 at 2^24. The paused QC
    # packet gate must use the bounded native completed-step ACK instead.
    f32 = lambda n: struct.unpack('<f', struct.pack('<f', n))[0]
    assert f32(16777216) == f32(16777217)
    assert 16000000 < 2**24
    root = Path(__file__).resolve().parents[1]
    player = (root / 'src/server/sv_player.qc').read_text()
    assert 'if (self.run_tas_done == self.run_tas_seen)' in player
    assert 'run_tas_seen = e.run_movetick' not in player
    # Reserve distinct numeric slots, including against existing string names.
    defs = (Path(__file__).resolve().parents[1] / 'src/shared/sh_defs.qc').read_text()
    stats = re.findall(r'^#define (STAT_\w+)\s+(\d+)\b', defs, re.M)
    for name in ('TASPAUSE', 'TASPENDING', 'TASDONE', 'TASREQUEST'):
        slot = [int(n) for s, n in stats if s == 'STAT_FS_' + name]
        assert len(slot) == 1 and 32 <= slot[0] <= 255
        assert [s for s, n in stats if int(n) == slot[0]] == ['STAT_FS_' + name], name
    header = a.engine / 'engine/server/sv_tas.h'
    mover = a.engine / 'engine/common/pm_source.c'
    epsilon = re.search(r'^#define PMSRC_TICK_EPSILON\s+([\deE.+-]+)', mover.read_text(), re.M)
    own = re.search(r'^#define SV_TAS_EPSILON\s+([\deE.+-]+)', header.read_text(), re.M)
    if not epsilon or not own or float(epsilon[1]) != float(own[1]):
        raise RuntimeError('TAS and actual mover tick epsilons differ')
    a.out.mkdir(parents=True, exist_ok=False)
    source = a.out / 'admission.c'
    exe = a.out / 'admission.exe'
    source.write_text(SOURCE)
    compiler = Path(shutil.which(a.compiler) or a.compiler).resolve(strict=True)
    env = os.environ.copy()
    env['PATH'] = str(compiler.parent) + os.pathsep + env.get('PATH', '')
    subprocess.run([str(compiler), '-std=c99', '-Wall', '-Wextra', '-Werror', '-Os', '-ffp-contract=off',
                    '-I' + str(header.parent), str(source), '-o', str(exe), '-lm'], check=True, env=env)
    subprocess.run([str(exe)], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
