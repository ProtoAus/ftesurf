#!/usr/bin/env python3
"""Act the TAS carried-state publication and actual QC go/board functions.

Synthetic restore/arrival values; not a mover, socket, session or REC replay test.
Requires the sibling engine source and the existing standalone qclib qcvm.
Artifacts must be fresh and below an agent-owned task root. Original native and
QC sources each must fail independently, proving that both seams are needed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from test_jargon_cem import extract

ROOT = Path(__file__).resolve().parents[1]
NATIVE = 'engine/server/sv_tas_rewind.inc'
PLAYER = 'src/server/sv_player.qc'
TIMER = 'src/server/sv_timer.qc'

C_FIXTURE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);return 1;} } while(0)
typedef struct {float boardcount, msec_carry; int other;} pmsourcestate_t;
typedef struct {int unused;} edict_t;
typedef union {float _float;} eval_t;
static struct {pmsourcestate_t pmsrc; int jump_held, pmepoch; double movetickcount;} client, *cl=&client;
static struct {pmsourcestate_t source; int jumpheld, input, planinput, planmode, planyaw; float planamount, pitchfollow;} state, *s=&state;
static struct {int lastinput, planinput, lastplaninput, planmode, lastplanmode, planyaw, planepoch; double lastmove;
 float planamount, lastplanamount, lastpitchfollow;} pool_data, *pool=&pool_data;
static eval_t fields[3];
static int missing;
#define ev_float 1
static void SV_TASInputCancel(edict_t *e) {(void)e;}
static eval_t *SV_TASRewindField(edict_t *e, const char *name, int type) {
 (void)e;(void)type;
 int n=!strcmp(name,"run_tas_pitchfollow")?0:(!strcmp(name,"run_movecarry")?1:2);
 return (missing & (1<<n)) ? NULL : &fields[n];
}
static void capture(void) {__CAPTURE__}
static void apply(edict_t *e) {eval_t *f; __RESTORE__}
int main(void) {
 edict_t e={0};
 for(int absent=0;absent<8;absent++) for(int count=0;count<5;count+=2) {
  memset(&client,0,sizeof(client));memset(&state,0,sizeof(state));memset(&pool_data,0,sizeof(pool_data));
  cl->pmsrc.boardcount=count;cl->pmsrc.msec_carry=.005f;cl->pmsrc.other=47;cl->jump_held=1;
  capture();s->input=7;s->planinput=8;s->planamount=.75f;s->pitchfollow=1;s->planmode=4;s->planyaw=32768;
  cl->pmsrc.boardcount=9;cl->pmsrc.msec_carry=.009f;cl->pmsrc.other=99;cl->jump_held=0;
  cl->movetickcount=1234;cl->pmepoch=17;missing=absent;
  for(int j=0;j<3;j++)fields[j]._float=99;
  apply(&e);
  CHECK(cl->pmsrc.boardcount==count && cl->pmsrc.msec_carry==.005f && cl->pmsrc.other==47 && cl->jump_held==1);
  CHECK(fields[2]._float==((absent&4)?99:count));
  CHECK(fields[1]._float==((absent&2)?99:.005f));
  CHECK(fields[0]._float==((absent&1)?99:1));
  CHECK(cl->movetickcount==1234 && pool->lastmove==1234 && cl->pmepoch==17 && pool->planepoch==17);
  CHECK(pool->lastinput==7 && pool->planinput==8 && pool->lastplaninput==8 && pool->planyaw==32768);
 }
 puts("PASS native capture/restore block: 24 carried-count/optional-field arms, unchanged connection tick/epoch and plan rebind");return 0;
}
'''

QC_FIXTURE = r'''
// Required by the recognized system prefix, unused in this standalone test.
void() StartFrame = {}; void() PlayerPreThink = {}; void() PlayerPostThink = {};
void() ClientKill = {}; void() ClientConnect = {}; void() PutClientInServer = {};
void() ClientDisconnect = {}; void() SetNewParms = {}; void() SetChangeParms = {};
void(string s) puts = #1;
string(float f) ftos = #2;
entity() spawn = #3;
#define TRUE 1
#define FALSE 0
#define SLOP_LOADED 1
#define PRINT_HIGH 2
.float rec_sl_slop,rec_sl_hold,run_tas_paused,run_tas_pending,run_tas_seen,run_tas_done,run_tas_rwcap;
.float run_boardcount,rec_rec_lastbc,vbsp_bhop_since;
.vector run_boardnormal,run_boardvelocity;
.entity vbsp_bhop_on;
float loaded,restored,nativecalls,headcalls,headbc,rows,lastrow,live,checks,failures;
float(float s) FS_SlopOp = {return s;};
void(entity e) SV_SaveLocGo = {e.rec_sl_slop=loaded;e.rec_sl_hold=loaded;};
void(entity e) SV_SaveLocRelease = {e.rec_sl_hold=0;};
void(entity e) SV_TASMark = {};
float(entity e,float slot,float token,float op) tas_rewind = {
 nativecalls=nativecalls+1;
 if (restored) e.run_boardcount=2;
 return restored;
};
void(entity e,float p,string s) sprint = {};
void(entity e) SV_TimerFreezeFrame = {};
void(entity e) SV_RewindTASHead = {headcalls=headcalls+1;headbc=e.rec_rec_lastbc;};
void(entity e) SV_TASProjectTouch = {};
float(entity e) SV_RecLive = {return live;};
string(string fmt,...) sprintf = {return fmt;};
string(string a,string b) strcat = {return a;};
void(entity e,string row) SV_RecPut = {rows=rows+1;lastrow=e.run_boardcount;};
__FUNCTIONS__
void(float ok,string name) check = {
 checks=checks+1;
 if (!ok) {puts("FAIL ");puts(name);puts("\n");failures=failures+1;}
};
void() main = {
 local entity e;
 local float initial,ok;
 e=spawn();loaded=1;restored=1;live=1;
 for(initial=0;initial<=4;initial=initial+2) {
  nativecalls=0;headcalls=0;rows=0;
  e.run_boardcount=3;e.rec_rec_lastbc=initial;e.run_boardnormal='0.6 0 0.8';
  e.run_boardvelocity='100 0 -200';e.run_tas_done=17;e.run_tas_pending=8;
  ok=SV_TASGo(e,7,11);
  check(ok,"restore succeeds");check(nativecalls==1 && headcalls==1,"one restore and one head");
  check(e.run_boardcount==2 && e.rec_rec_lastbc==2 && headbc==2,"restored counter/latch before capture");
  check(e.run_tas_pending==0 && e.run_tas_seen==17 && e.run_tas_paused==1,"existing pause/counter policy");
  SV_RecBoard(e,5.49);check(rows==0,"no duplicate arrival on resumed non-arrival");
  e.run_boardcount=3;SV_RecBoard(e,5.505);check(rows==1 && lastrow==3,"first resumed true arrival retained");
  SV_RecBoard(e,5.52);check(rows==1,"one row per observed change");
 }
 // First-board head and a skipped counter: restored publication is synthetic,
 // while the production recorder still decides whether to write each row.
 e.run_boardcount=0;e.rec_rec_lastbc=0;rows=0;SV_RecBoard(e,0);check(rows==0,"no-board head");
 e.run_boardcount=1;SV_RecBoard(e,.015);check(rows==1 && lastrow==1,"first genuine board after zero");
 e.run_boardcount=4;SV_RecBoard(e,.03);check(rows==2 && lastrow==4,"multiple arrivals may skip counters");
 e.run_boardcount=5;e.run_boardnormal='0 0 0';SV_RecBoard(e,.045);check(rows==2 && e.rec_rec_lastbc==5,"zero-normal reset unchanged");
 live=0;e.run_boardcount=6;SV_RecBoard(e,.06);check(rows==2 && e.rec_rec_lastbc==5,"closed recorder unchanged");live=1;
 restored=0;headcalls=0;e.rec_rec_lastbc=9;e.run_boardcount=8;e.run_tas_rwcap=1;
 ok=SV_TASGo(e,7,11);check(!ok && e.run_tas_rwcap==0,"native refusal fails closed");
 check(e.rec_rec_lastbc==9 && headcalls==0,"refused native restore does not rebase or capture");
 loaded=0;nativecalls=0;e.rec_rec_lastbc=7;
 ok=SV_TASGo(e,7,11);check(!ok && nativecalls==0 && e.rec_rec_lastbc==7,"placement refusal does not restore or rebase");
 if(failures) puts("FAIL QC board restore\n");
 else {puts("PASS QC board restore checks=");puts(ftos(checks));puts("\n");}
};
'''


def old(repo, ref, path):
    return subprocess.check_output(['git', '-C', str(repo), 'show', ref + ':' + path], text=True, encoding='utf-8')


def native_fixture(text):
    # The exact production restore slice, not a second implementation. Admission,
    # full body/notification, physics and world side effects are outside this test.
    first = text.index('\tSV_TASInputCancel(e); // a placement')
    last = text.index('\tVectorCopy(s->origin, e->v->origin);', first)
    capture = 's->source = cl->pmsrc;'
    jump = 's->jumpheld = cl->jump_held;'
    assert text.count(capture) == 1 and text.count(jump) == 1
    return C_FIXTURE.replace('__CAPTURE__', capture + jump).replace('__RESTORE__', text[first:last])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--qcvm', type=Path, required=True)
    ap.add_argument('--qcc', type=Path, default=Path('C:/FTESurf/src/fteqcc64.exe'))
    ap.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    ap.add_argument('--qc-base', default='152051670b0ee830c815cf6fb4569a6331bac595')
    ap.add_argument('--engine-base', default='47998d6e3129978559d123e3334406cb95b0526b')
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists() or not any((p / 'OWNER.md').is_file() for p in out.parents):
        ap.error('--out must be fresh and under an owned task root')
    out.mkdir(parents=True)
    sysdefs_path = ROOT / 'src/defs/sv_defs.qc'
    sysdefs = sysdefs_path.read_text()
    # Keep the actual recognized system prefix, before custom fixture fields.
    # This standalone VM needs no engine builtin declarations from the suffix.
    sysdefs = sysdefs[sysdefs.index('entity self;'):sysdefs.index('void end_sys_fields;') + len('void end_sys_fields;')]
    paths = [a.engine / NATIVE, ROOT / PLAYER, ROOT / TIMER, sysdefs_path, Path(__file__), a.qcvm, a.qcc, a.cc]
    manifest = {'sha256': {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                'native_base': a.engine_base, 'qc_base': a.qc_base,
                'scope': 'Exact native carry-restore block and full QC go/board functions; synthetic API/world/arrival stubs. '
                         'No movement, socket, full restore admission, session/cold-stream or complete recording verification.'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    env = dict(os.environ)
    env['PATH'] = 'C:/msys64/ucrt64/bin' + os.pathsep + env.get('PATH', '')
    for control in (True, False):
        label = 'original' if control else 'subject'
        folder = out / label
        folder.mkdir()
        native = old(a.engine, a.engine_base, NATIVE) if control else (a.engine / NATIVE).read_text()
        c = folder / 'native.c'
        c.write_text(native_fixture(native))
        cc = subprocess.run([str(a.cc), '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(folder / 'native.exe')],
                            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (folder / 'native-compiler.log').write_text(cc.stdout)
        if cc.returncode:
            raise RuntimeError('native fixture compile failed: ' + str(folder))
        result = subprocess.run([str(folder / 'native.exe')], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (folder / 'native.log').write_text(result.stdout)
        assert (result.returncode != 0) == control, 'native original must fail and subject must pass'
        native_ok = 'PASS native capture/restore block' in result.stdout
        if control:
            assert 'FAIL line ' in result.stdout and 'fields[2]._float==' in result.stdout, 'original must expose stale publication'
        else:
            assert native_ok, 'subject must reach the native assertions'
        player = old(ROOT, a.qc_base, PLAYER) if control else (ROOT / PLAYER).read_text()
        timer = (ROOT / TIMER).read_text()
        functions = extract(player, 'SV_TASGo') + extract(timer, 'SV_RecBoard')
        (folder / 'unit.qc').write_text(sysdefs + '\n' + QC_FIXTURE.replace('__FUNCTIONS__', functions))
        (folder / 'progs.src').write_text('progs.dat\nunit.qc\n')
        cc = subprocess.run([str(a.qcc), '-srcfile', 'progs.src'], cwd=folder, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (folder / 'qc-compiler.log').write_text(cc.stdout)
        if cc.returncode or '0 warnings' not in cc.stdout:
            raise RuntimeError('QC fixture compile failed or warnings present: ' + str(folder))
        result = subprocess.run([str(a.qcvm), 'progs.dat'], cwd=folder, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (folder / 'qc.log').write_text(result.stdout)
        bad = result.returncode != 0 or 'FAIL ' in result.stdout or 'PASS QC board restore' not in result.stdout
        assert bad == control, 'QC original must fail and subject must pass'
        if control:
            assert 'FAIL restored counter/latch before capture' in result.stdout, 'original must expose stale recorder latch'
        print(label, 'native:', 'expected fail' if control else 'pass', 'QC:', 'expected fail' if control else 'pass')
    print('PASS acting original native/QC failures and fixed subject. Evidence:', out)


if __name__ == '__main__':
    main()
