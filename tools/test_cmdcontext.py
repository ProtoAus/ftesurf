#!/usr/bin/env python3
"""Compile real P675 server bridge/budget/split source with downstream doubles.

No mover/VM/network is emulated as proof. The harness extracts production Q1
command prefix, context publisher, wrappers, typed lookup and PreThink scope.
Full-QC movement, log output and PreThink are doubles; dedicated fixture is the
independent production execution test. Native physics is deliberately unchanged.
"""
import argparse
import json
import pathlib
import subprocess
import os
import shlex
import re
import math

from test_predinput import between


def source_slice(path, start, end):
    return start + between(path, start, end)

HARNESS = r'''
#include "quakedef.h"
#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#undef Q2SERVER
#undef Q3SERVER
#undef PR_ExecuteProgram
#undef PR_FindGlobal
static globalptrs_t globals;
globalptrs_t *pr_global_ptrs = &globals;
static pubprogfuncs_t fakeprogs;
pubprogfuncs_t *svprogfuncs = &fakeprogs;
static pubprogfuncs_t *csqcprogs = &fakeprogs;
static client_t client;
client_t *host_client = &client;
server_t sv;
double host_frametime;
double realtime;
static usercmd_t cmd; // production sv_user.c uses the same shared recursive scratch
cvar_t sv_showpredloss;
static float words[6];
static func_t preth = 1;
static unsigned int expectedseq;
static int expectedkind, leaves, fullqc, fullcalls;
static float expectedtotal, lastend, executed, leafsum;
static float lookupvalue;
static etype_t lookuptype;
static int missing;
static int lastimpulse;
void VARGS Con_Printf(const char *fmt,...) {}
void VARGS SV_BroadcastTPrintf(int level, const char *fmt,...) {assert(!"unexpected speed drop");}
void SV_SetSSQCInputs(usercmd_t *u) {}
qboolean SV_RunFullQCMovement(client_t *c,usercmd_t *u) {fullcalls++;return fullqc;}
static void *TestFindGlobal(pubprogfuncs_t *p,const char *name,int n,etype_t *type)
{ *type=lookuptype;return missing?NULL:&lookupvalue; }
#define PR_FindGlobal TestFindGlobal
static void TestExecute(pubprogfuncs_t *p,func_t f)
{
 assert(f==1);leaves++;
 assert(words[0]==expectedkind);
 if(expectedkind) {
  assert(words[1]==(expectedseq&0xffffu));assert(words[2]==(expectedseq>>16));
  assert(words[3]==expectedtotal);assert(words[5]==lastend);
  assert(words[4]>=0 && words[4]<=50);
  lastend=words[5]+words[4];leafsum+=words[4];
 } else {for(int i=1;i<6;i++)assert(words[i]==0);}
 // A QC write to the read-only exports must not survive the scope.
 for(int i=0;i<6;i++)words[i]=-999;
}
#define PR_ExecuteProgram TestExecute
@LOOKUP@
@CLIENTLOOKUP@
@PUBLISH@
@PREFIX@
 @PRETHINK@
 executed += cmd.msec;
 if(leaves==1)assert(cmd.impulse==9);else assert(cmd.impulse==0 || offsetmsec==0);
 lastimpulse=cmd.impulse;
 for(int j=0;j<6;j++)if(j!=2 || globals.input_cmd_sequence_hi)assert(words[j]==0);
}
@WRAPPERS@
static void Reset(void)
{
 memset(&globals,0,sizeof(globals));memset(&client,0,sizeof(client));
 globals.input_cmd_kind=&words[0];globals.input_cmd_sequence_lo=&words[1];
 globals.input_cmd_sequence_hi=&words[2];globals.input_cmd_msec=&words[3];
 globals.input_cmd_piece_msec=&words[4];globals.input_cmd_offset_msec=&words[5];
 globals.PlayerPreThink=&preth;
 memset(words,0,sizeof(words));client.msecs=10000;
 leaves=fullqc=fullcalls=0;lastend=executed=leafsum=0;expectedkind=1;
}
static usercmd_t Command(unsigned int seq,float msec)
{ usercmd_t u;memset(&u,0,sizeof(u));u.sequence=seq;u.msec=msec;u.impulse=9;return u; }
int main(void)
{
 unsigned int seqs[]={0,65535,65536,16777217u,0x80000001u,0xffffffffu};
 float durations[]={0,10,50,51,101,255,50.5f,100.75f};
 for(unsigned int i=0;i<sizeof(seqs)/sizeof(seqs[0]);i++)
 for(unsigned int j=0;j<sizeof(durations)/sizeof(durations[0]);j++) {
  Reset();expectedseq=seqs[i];expectedtotal=durations[j];
  usercmd_t u=Command(expectedseq,expectedtotal);SV_RunCmdNetwork(&u,1);
  float target=expectedtotal>50?(int)expectedtotal:expectedtotal;
  assert(leaves>0 && fullcalls>0 && executed==target && leafsum==target && lastend==target);
 }
 puts("PASS exact uint32 words, decoded QW, native integer split offsets/fractional truncation acted");
 Reset();expectedkind=2;expectedtotal=255;expectedseq=0x80000001u;
 usercmd_t u=Command(expectedseq,expectedtotal);SV_RunCmdNetwork(&u,2);assert(leaves==8);
 puts("PASS timestamp-derived kind 2 distinct from original-client timing");
 Reset();expectedkind=0;u=Command(999,101);SV_RunCmd(&u,false);assert(leaves==3);
 puts("PASS synthetic/legacy wrapper unavailable and scope cleared");
 Reset();expectedkind=0;client.msecs=50;u=Command(999,51);SV_RunCmdNetwork(&u,1);
 assert(u.msec==50 && executed==50 && leaves==1);
 Reset();client.msecs=12;u=Command(999,51);SV_RunCmdNetwork(&u,1);
 assert(u.msec==50 && executed==0 && leaves==0);
 puts("PASS native budget mutation invalidates boundary rather than advertising raw duration");
 Reset();fullqc=1;u=Command(999,101);SV_RunCmdNetwork(&u,1);
 assert(fullcalls==1 && leaves==0);for(int i=0;i<6;i++)assert(words[i]==0);
 puts("PASS full-QC movement does not expose native PreThink context");
 Reset();expectedkind=0;globals.input_cmd_sequence_hi=NULL;u=Command(1,10);
 SV_RunCmdNetwork(&u,1);assert(leaves==1);
 memset(&globals,0,sizeof(globals));SV_PublishCmdContext(NULL,0,0,0);
 puts("PASS incomplete/missing optional exports are unavailable and null-safe");
 Reset();u=Command(1,10);
 float bad[]={NAN,INFINITY,-1,501};
 for(int i=0;i<4;i++){SV_PublishCmdContext(&u,1,bad[i],0);assert(words[0]==0);}
 SV_PublishCmdContext(&u,1,10,1);assert(words[0]==0);
 SV_PublishCmdContext(&u,3,10,0);assert(words[0]==0);
 SV_PublishCmdContext(NULL,1,10,0);assert(words[0]==0);
 puts("PASS invalid kind/nonfinite/out-of-piece timing abstains");
 lookuptype=ev_float;lookupvalue=999;assert(SV_FindCmdContextGlobal("x")==&lookupvalue && lookupvalue==0);
 lookuptype=ev_vector;lookupvalue=999;assert(!SV_FindCmdContextGlobal("x") && lookupvalue==999);
 lookuptype=ev_integer;assert(!SV_FindCmdContextGlobal("x"));
 lookuptype=ev_float;missing=1;assert(!SV_FindCmdContextGlobal("x"));
 missing=0;lookuptype=ev_float;lookupvalue=999;
 assert(CSQC_FindCmdContextGlobal("x")==&lookupvalue && lookupvalue==0);
 lookuptype=ev_vector;lookupvalue=999;assert(!CSQC_FindCmdContextGlobal("x") && lookupvalue==999);
 lookuptype=ev_integer;assert(!CSQC_FindCmdContextGlobal("x"));
 lookuptype=ev_float;missing=1;assert(!CSQC_FindCmdContextGlobal("x"));
 puts("PASS server/client typed discovery zeroes only valid scalar exports");
 return 0;
}
'''


def compile_and_run(root, out):
    root = root.resolve()
    out.mkdir(parents=True, exist_ok=True)
    user = root / 'engine/server/sv_user.c'
    prefix = source_slice(user, 'static void SV_RunCmdPart (', '\n\tVALGRIND_MAKE_MEM_UNDEFINED')
    scope = source_slice(user, '\t\t\tif (pr_global_ptrs->PlayerPreThink)', '\n\n\t\tif (progstype')
    if 'SV_PublishCmdContext(NULL, 0, 0, 0);' not in scope:
        raise ValueError('PreThink clear source anchor drift')
    source = HARNESS.replace('@LOOKUP@', source_slice(root / 'engine/server/pr_cmds.c',
        'static pvec_t *SV_FindCmdContextGlobal(', '\nvoid PR_LoadGlabalStruct'))
    source = source.replace('@CLIENTLOOKUP@', source_slice(root / 'engine/client/pr_csqc.c',
        'static float *CSQC_FindCmdContextGlobal(', '\nstatic void CSQC_FindGlobals'))
    source = source.replace('@PUBLISH@', source_slice(user, 'static void SV_PublishCmdContext(', '\nstatic void SV_RunCmdPart'))
    source = source.replace('@PREFIX@', prefix).replace('@PRETHINK@', scope)
    source = source.replace('@WRAPPERS@', source_slice(user, 'void SV_RunCmd(usercmd_t *', '\nvoid SV_PostRunCmd'))
    db = json.loads((root / 'compile_commands.json').read_text())
    entry = next(x for x in db if x['file'].endswith('/sv_user.c'))
    flags = entry.get('arguments') or shlex.split(entry['command'])
    flags = flags[:flags.index('-c')]
    oi = flags.index('-o')
    del flags[oi:oi+2]
    env = dict(os.environ)
    env['PATH'] = str(pathlib.Path(flags[0]).parent) + os.pathsep + env.get('PATH', '')
    cfile = out / 'cmdcontext_native_test.c'
    exe = out / 'cmdcontext_native_test.exe'
    cfile.write_text(source)
    subprocess.run(flags + ['-O1', '-Werror', '-Wno-unused-function', '-Wno-unused-variable', str(cfile), '-o', str(exe)], cwd=entry['directory'], env=env, check=True)
    subprocess.run([str(exe)], env=env, check=True)
    print('PASS production server source compiled with native m-rel flags; downstream doubles only')


def grade_runtime(server, client, kind):
    for marker in ('FTESurf CSQC loaded', 'CMDCONTEXT CLIENT COMPLETE', 'RUNLINES COMPLETE'):
        if marker not in client:
            raise ValueError('client control did not act: ' + marker)
    for bad in ('Unknown command', 'QC VM error', 'Cannot call', 'stack overflow', 'CMDCONTEXT STALE'):
        if bad in server or bad in client:
            raise ValueError('runtime fault: ' + bad)
    if 'CMDCONTEXT FRAME CLEARED original-hooks-acted' not in server:
        raise ValueError('outside-command control did not act')
    rows = re.findall(r'CMDCONTEXT PRE kind=(\S+) lo=(\S+) hi=(\S+) total=(\S+) piece=(\S+) off=(\S+)', server)
    if len(rows) != server.count('CMDCONTEXT PRE '):
        raise ValueError('malformed or truncated PreThink observation')
    unavailable = available = split = complete = 0
    current = None
    end = 0
    for row in rows:
        k, lo, hi, total, piece, offset = map(float, row)
        if not all(map(math.isfinite, (k, lo, hi, total, piece, offset))):
            raise ValueError('nonfinite runtime metadata')
        if k == 0:
            if any((lo, hi, total, piece, offset)):
                raise ValueError('unavailable boundary retained data')
            unavailable += 1
            continue
        if k != kind or kind == 0:
            raise ValueError('unexpected protocol provenance')
        if lo != int(lo) or hi != int(hi) or not 0 <= lo <= 65535 or not 0 <= hi <= 65535:
            raise ValueError('sequence words are not exact 16-bit integers')
        if not 0 <= piece <= 50 or not 0 <= offset <= total <= 500 or offset + piece > total:
            raise ValueError('invalid timing metadata')
        identity = (k, lo, hi, total)
        if offset == 0:
            current = identity
            end = 0
        if current != identity or abs(offset - end) > .001:
            raise ValueError('noncontiguous native split budget')
        end = offset + piece
        available += 1
        split += offset > 0
        # Existing server behavior truncates >50ms to integer before splitting.
        target = math.floor(total) if total > 50 else total
        complete += abs(end - target) < .001
    if kind == 0:
        if unavailable < 10 or available:
            raise ValueError('old-engine optional-global control did not act')
    elif available < 10 or split < 2 or complete < 2:
        raise ValueError('decoded/split controls did not act')
    return f'PASS runtime kind={kind}: decoded={available} split={split} complete={complete} unavailable={unavailable}; frame scope cleared'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=pathlib.Path)
    p.add_argument('--out', type=pathlib.Path)
    p.add_argument('--log', type=pathlib.Path, help='grade retained server fixture log')
    p.add_argument('--client-log', type=pathlib.Path, help='acting/completed client log, required with --log')
    p.add_argument('--kind', type=int, choices=(0, 1, 2), default=1, help='0 is the old-engine compatibility control')
    a = p.parse_args()
    if a.log:
        if not a.client_log:
            p.error('--log requires --client-log')
        server = a.log.read_text(errors='replace')
        client = a.client_log.read_text(errors='replace')
        print(grade_runtime(server, client, a.kind))
        for marker in ('CMDCONTEXT PRE', 'CMDCONTEXT FRAME CLEARED original-hooks-acted'):
            try:
                grade_runtime(server.replace(marker, 'REMOVED'), client, a.kind)
            except ValueError:
                continue
            raise ValueError('negative grader accepted missing arm: ' + marker)
        try:
            grade_runtime(server + '\nCMDCONTEXT STALE', client, a.kind)
        except ValueError:
            pass
        else:
            raise ValueError('negative grader accepted stale scope')
        print('PASS negative graders reject missing PreThink/frame controls and stale scope')
    elif a.engine and a.out:
        compile_and_run(a.engine, a.out)
    else:
        p.error('supply --log + --client-log, or --engine + --out')


if __name__ == '__main__':
    main()
