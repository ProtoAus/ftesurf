#!/usr/bin/env python3
"""Compile literal selected cl_screen.c sampler; deterministic sorted-ring oracle.
No copied sampler, native client, GPU or performance claim. Outputs retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

DUMP_STUBS = r'''
#include <stdarg.h>
#define countof(x) ((int)(sizeof(x)/sizeof((x)[0])))
#define CBT_CLIPBOARD 0
static char clipboard[4096];
static struct model_stub { const char *name; } model={"deterministic"};
static struct { struct model_stub *worldmodel; } cl={&model};
static const char *version_string(void) { return "source-bound test"; }
static char *va(const char *format, ...) {
    static char out[4096]; va_list args;
    va_start(args,format); vsnprintf(out,sizeof(out),format,args); va_end(args);
    return out;
}
static void Q_strncatz(char *out,const char *s,size_t n) {
    strncat(out,s,n-strlen(out)-1);
}
static char console_last[4096];
static void Con_Printf(const char *format,...) {
    va_list args; va_start(args,format); vsnprintf(console_last,sizeof(console_last),format,args); va_end(args);
    clock_now+=.001;
}
static void Sys_SaveClipboard(int type,const char *s) { (void)type; strcpy(clipboard,s); clock_now+=.2; }
static void R_FrameTime_AfterDump(void) { rebase_calls++; ft.last=Sys_DoubleTime(); }
'''

CASES = r'''
#include <stdlib.h>
#include <math.h>
static int failures, checks;
static float sorted[FT_RING];
static vec3_t orgs[FT_RING], angs[FT_RING];
static int known_count;
static void check(int ok, const char *name) {
    checks++;
    if (!ok) { failures++; printf("FAIL %s\n", name); }
}
static int compare(const void *a, const void *b) {
    float x=*(const float *)a, y=*(const float *)b;
    return (x<y)-(x>y);
}
static void sample(double t, int id) {
    int slot=ft.head, j;
    clock_now=t;
    for (j=0;j<3;j++) {
        r_refdef.vieworg[j]=(float)(id*4+j+64);
        r_refdef.viewangles[j]=(float)(id*4+j);
    }
    R_FrameTime_Sample();
    if (ft.head != slot) {
        VectorCopy(r_refdef.vieworg,orgs[slot]); orgs[slot][2]-=FT_EYE;
        VectorCopy(r_refdef.viewangles,angs[slot]);
    }
}
static void reset(float window) {
    ft.on=false; vid.activeapp=true; idlefps.value=0;
    r_frametime_window.value=window; sample(0,0);
}
static void oracle(const char *name) {
    int i,j,k,n,nb; double total=0, sum=0, residual=0;
    float expected;
    R_FrameTime_Stats();
    for (i=0;i<ft.count;i++) {
        k=(ft.head-ft.count+i)&(FT_RING-1);
        sorted[i]=ft.ms[k]; total+=ft.ms[k];
    }
    qsort(sorted,ft.count,sizeof(sorted[0]),compare);
    check(fabs(ft.sum-total)<.02,name);
    check(fabs(ft.worst-sorted[0])<.001,name);
    known_count=0;
    for (i=0;i<FT_KEEP && i<ft.count;i++) {
        check(fabs(ft.bad[i].ms-sorted[i])<.001,name);
#ifdef FIXED
        k=ft.bad[i].slot;
        check(((ft.head-1-k)&(FT_RING-1))<ft.count,"cache slot retained");
        for (j=0;j<i;j++) check(k!=ft.bad[j].slot,"unique cache identity");
        check(ft.bad[i].ms==ft.ms[k] && ft.bad[i].at==ft.at[k],"cache value identity");
        if (ft.bad[i].known) {
            known_count++;
            check(!memcmp(ft.bad[i].org,orgs[k],sizeof(vec3_t)),"camera origin identity");
            check(!memcmp(ft.bad[i].ang,angs[k],sizeof(vec3_t)),"camera angle identity");
        }
#else
        (void)j;
#endif
    }
    /* Oracle uses sorted raw ring, with documented histogram quantization and
       the overflow residual mean after exact top64, not a copied cache. */
    for (nb=0;nb<ft.count && sorted[nb]>=(FT_BINS-1)*FT_BINMS;nb++) ;
    for (i=FT_KEEP;i<nb;i++) residual+=sorted[i];
    for (j=0;j<2;j++) {
        n=max(1,ft.count/(j?1000:100)); sum=0;
        for (i=0;i<n;i++) {
            if (sorted[i]>=(FT_BINS-1)*FT_BINMS)
                sum+=i<FT_KEEP?sorted[i]:residual/(nb-FT_KEEP);
            else
                sum+=((int)(sorted[i]/FT_BINMS)+.5)*FT_BINMS;
        }
        expected=sum/n;
        check(fabs((j?ft.low01:ft.low1)-expected)<.002,"tail sorted oracle");
    }
    printf("CASE %s count=%d worst=%.6f tails=%.6f/%.6f known=%d\n",name,ft.count,ft.worst,ft.low1,ft.low01,known_count);
}
int main(void) {
    int i, before; double t;
    reset(1); sample(.6,1);sample(1,2);sample(1.61,3);
    check(ft.count==2 && fabs(ft.sum-1010)<.001,"expiry stimulus acted");
    oracle("expiry"); check(fabs(R_FrameTime_Over(1)-400)<.001,"expiry overflow rank1");
#ifdef FIXED
    check(ft.bad[0].known && ft.bad[0].slot==((ft.head-1)&(FT_RING-1)),"newest camera after rebuild");
#endif
    reset(120);ft.base=-16777216; t=.9;sample(t,1);
    for(i=0;i<FT_RING;i++){t+=.0005;sample(t,i+2);}
    check(ft.count==FT_RING && fabs(ft.ms[(ft.head-ft.count)&(FT_RING-1)]-.5)<.001,"capacity stimulus acted");
    oracle("capacity");
    before=rebuild_calls;
    for(i=0;i<256;i++){t+=.0005;sample(t,i+FT_RING+2);}
    check(ft.count==FT_RING,"equal capacity eviction acted");
    check(rebuild_calls-before<=1,"equal capacity bounded rebuilds");
    printf("REBUILDS equal capacity %d over 256 evictions\n",rebuild_calls-before);
    oracle("capacity steady");
    reset(1);t=0;before=rebuild_calls;
    for(i=0;i<4000;i++){t+=.001;sample(t,i+1);}
    check(ft.count>=999 && ft.count<=1001,"equal expiry acted");
    check(rebuild_calls-before<=1,"equal expiry bounded rebuilds");
    printf("REBUILDS equal expiry %d over 4000 samples\n",rebuild_calls-before);
    oracle("expiry steady");
    reset(120);sample(.01,1);sample(1.511,2);sample(1.521,3);
    check(ft.count==3 && fabs(ft.sum-1521)<.001,"1501ms stall accepted");oracle("long stall");
    reset(120);t=0;
    for(i=0;i<1000;i++){t+=(i%37==0)?.091:.007;sample(t,i+1);}
    check(ft.count==1000,"ordinary stimulus acted");oracle("ordinary");
    /* >64 overflow frames: exercise both exact cache and residual approximation. */
    reset(120);t=0;
    for(i=0;i<10000;i++){t+=i<100?(.21+i*.0001):.0005;sample(t,i+1);}
    check(ft.count==10000 && ft.bins[FT_BINS-1]==100,"overflow stimulus acted");oracle("overflow residual");
    r_frametime_window.value=1;sample(t+.3,10001);oracle("mass expiry");
    reset(120);sample(.01,1);vid.activeapp=false;idlefps.value=10;
    sample(.51,2);sample(1.01,3);vid.activeapp=true;sample(1.02,4);
    check(ft.count==2 && fabs(ft.sum-20)<.001,"focus idle gating acted");
#ifdef FIXED
    check(ft.excluded==2 && fabs(ft.excludedms-1000)<.001,"focus excluded count/time");
#endif
    vid.activeapp=false;idlefps.value=0;sample(2.52,5);
    check(ft.count==3 && fabs(ft.sum-1520)<.001,"unfocused unthrottled stall accepted");
    oracle("focus");
    R_FrameTime_Dump_f();
#ifdef FIXED
    check(strstr(clipboard,"sampled 1.520 s")!=NULL,"dump sample duration acted");
    check(strstr(clipboard,"2 intervals, 1.000 s")!=NULL,"dump focus exclusions acted");
    check(strstr(clipboard,"1% tail mean")!=NULL,"dump tail label acted");
#endif
    printf("DUMP %s",clipboard);
    i=ft.count;sample(2.52,6);check(ft.count==i,"zero clock unchanged");
    sample(2.51,7);check(ft.count==i,"negative clock unchanged");
    printf("RESULT checks=%d failures=%d\n",checks,failures);
    return failures?1:0;
}
'''

TRACKING = r'''
#include <stdlib.h>
static int allocation_calls, free_calls, sort_calls, live_allocations, fail_allocation, rebase_calls;
static size_t largest_allocation;
static void *tracked_malloc(size_t size) {
    void *p; allocation_calls++; clock_now+=.1;
    if (size>largest_allocation) largest_allocation=size;
    if (fail_allocation) return NULL;
    p=malloc(size); if (p) live_allocations++; return p;
}
static void tracked_free(void *p) {
    if (p) { free_calls++; live_allocations--; } free(p);
}
static void tracked_qsort(void *p,size_t n,size_t size,int (*cmp)(const void *,const void *)) {
    sort_calls++; clock_now+=.3; qsort(p,n,size,cmp);
}
#define malloc tracked_malloc
#define free tracked_free
#define qsort tracked_qsort
'''

EXACT_CASES = r'''
static void exact_dump_oracle(const char *name) {
    int i,j,n,rank,ns=0,got_stutters=-1,matched;
    const int numerators[4]={500,900,990,999};
    const char *row;
    double avg,tail1,tail01,x=0,a,b,c,threshold,median,sum=0,s1=0,s01=0;
    int alloc_before=allocation_calls, free_before=free_calls, sort_before=sort_calls, rebase_before=rebase_calls;
    for(i=0;i<ft.count;i++) sorted[i]=ft.ms[(ft.head-ft.count+i)&(FT_RING-1)];
    qsort(sorted,ft.count,sizeof(sorted[0]),compare);
    for(i=0;i<ft.count;i++) sum+=sorted[i];
    n=max(1,ft.count/100);for(i=0;i<n;i++) s1+=sorted[i]; tail1=s1/n;
    n=max(1,ft.count/1000);for(i=0;i<n;i++) s01+=sorted[i]; tail01=s01/n;
    avg=sum/ft.count;
    R_FrameTime_Dump_f();
    row=strstr(clipboard,"  avg ");
    matched=row?sscanf(row,"  avg %lf ms (%lf fps)  1%% tail mean %lf ms (%lf fps)  0.1%% tail mean %lf ms",&a,&b,&c,&x,&threshold):0;
    check(matched==5,"dump numeric rows acted");
    if(matched==5) {
        check(fabs(a-avg)<.0051,"exact raw average");
        check(fabs(c-tail1)<.0051,"exact raw 1% tail");
        check(fabs(threshold-tail01)<.0051,"exact raw 0.1% tail");
    }
    for(j=0;j<4;j++) {
        /* Independent rank oracle: first rank whose cumulative integer fraction meets p. */
        for(rank=1;rank*1000<ft.count*numerators[j];rank++) ;
        row=strstr(clipboard,va("  p%g",numerators[j]/10.0));
        matched=row?sscanf(row," p%lf %lf ms",&a,&b):0;
        check(matched==2,"percentile row acted");
        if(matched==2) check(fabs(b-sorted[ft.count-rank])<.0051,"raw nearest-rank percentile");
    }
    for(rank=1;rank*2<ft.count;rank++) ;
    median=sorted[ft.count-rank];threshold=median*2.5;
    for(i=0;i<ft.count;i++) if(sorted[i]>threshold) ns++;
    row=strstr(clipboard,"  stutters ");
    matched=row?sscanf(row,"  stutters (over %lfx the median, %lf ms): %d",&a,&b,&got_stutters):0;
    check(matched==3 && got_stutters==ns,"raw median-threshold stutters");
    check(matched==3 && fabs(b-threshold)<.0051,"nearest-rank median threshold");
    check(strstr(clipboard,"exact raw samples")!=NULL,"exact raw label acted");
    check(strstr(clipboard,"nearest rank")!=NULL,"median rank convention disclosed");
    check(allocation_calls==alloc_before+1 && sort_calls==sort_before+1,"one explicit dump allocation/sort");
    check(free_calls==free_before+1 && live_allocations==0,"successful dump freed buffer");
    check(rebase_calls==rebase_before+1 && ft.last==clock_now,"successful dump rebased after work");
    printf("EXACT %s count=%d expected tails=%.6f/%.6f stutters=%d allocation=%lu\n",name,ft.count,tail1,tail01,ns,(unsigned long)largest_allocation);
    printf("%s",clipboard);
}
int main(void) {
    int i,alloc_before,sort_before,free_before,rebase_before;
    double t;
    (void)tracked_malloc; (void)tracked_free; (void)tracked_qsort;
    /* The original source-bound 13992 checks still run unchanged. */
    legacy_main();
    reset(120);t=0;alloc_before=allocation_calls;sort_before=sort_calls;
    for(i=0;i<FT_RING;i++){t+=.0005;sample(t,i+1);}
    R_FrameTime_Stats();
    check(ft.count==FT_RING,"65536 half-ms samples acted");
    check(allocation_calls==alloc_before && sort_calls==sort_before,"no sampler/stats heap or sort");
    exact_dump_oracle("half ms at capacity");
    reset(120);t=0;
    for(i=0;i<998;i++){t+=.0005;sample(t,i+1);}
    t+=.01;sample(t,999);t+=.1;sample(t,1000);
    check(ft.count==1000 && ft.bad[0].ms>99,"p99.9 boundary stimulus acted");
    exact_dump_oracle("N1000 p99.9 is rank999 not1000");
    reset(120);sample(.01,1);sample(.03501,2); /* lower p50=10, threshold25, one >25 */
    check(ft.count==2,"even median stimulus acted");
    exact_dump_oracle("even median threshold");
    reset(120);t=0;
    for(i=0;i<10000;i++){t+=i<500?.2+i*.00001:.0005;sample(t,i+1);}
    check(ft.count==10000 && ft.bins[FT_BINS-1]==500,"overflow raw tail stimulus acted");
    exact_dump_oracle("overflow tail beyond top64");
    reset(120);sample(.0005,1);
    exact_dump_oracle("singleton");
    strcpy(clipboard,"previous report sentinel");console_last[0]=0;
    fail_allocation=1;alloc_before=allocation_calls;sort_before=sort_calls;free_before=free_calls;rebase_before=rebase_calls;
    R_FrameTime_Dump_f();
    check(allocation_calls==alloc_before+1,"OOM allocation acted");
    check(!strcmp(clipboard,"previous report sentinel"),"OOM no misleading new clipboard");
    check(strstr(console_last,"out of memory; no new report")!=NULL,"OOM explicit failure acted");
    check(sort_calls==sort_before && free_calls==free_before && live_allocations==0,"OOM no sort or leak");
    check(rebase_calls==rebase_before+1 && ft.last==clock_now,"OOM rebased after failure work");
    fail_allocation=0;sample(clock_now+.0005,2);
    check(fabs(ft.ms[(ft.head-1)&(FT_RING-1)]-.5)<.001,"dump overhead excluded from next sample");
    ft.on=false;alloc_before=allocation_calls;
    R_FrameTime_Dump_f();
    check(allocation_calls==alloc_before,"no sample dump remains allocation-free");
    check(largest_allocation<=256*1024 && live_allocations==0,"256KiB maximum/no leaks");
    printf("EXACT RESULT checks=%d failures=%d alloc=%d free=%d sort=%d\n",checks,failures,allocation_calls,free_calls,sort_calls);
    return failures?1:0;
}
'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--audit-tool',type=Path,default=Path(__file__).with_name('audit_frametime.py'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--fixed',action='store_true',help='exercise slot identity, exclusion reporting and explicit tail labels')
    p.add_argument('--cc',help='GCC-compatible compiler; default uses the supported UCRT compiler on Windows, else gcc/cc')
    a=p.parse_args()
    a.out=a.out.resolve()
    if not any((parent/'OWNER.md').is_file() for parent in (a.out,*a.out.parents)):
        p.error('--out must be below an owned task root with OWNER.md')
    a.out.mkdir(parents=True,exist_ok=True)
    text=a.source.read_text(encoding='utf-8')
    body=text[text.index('#define FT_RING '):text.index('\nstatic void R_FrameTime_Draw')]
    preamble=runpy.run_path(str(a.audit_tool))['PREAMBLE']
    c=a.out/'actual_sampler.c'; exe=a.out/'actual_sampler.exe'
    instrumented=body.replace('static void R_FrameTime_Rebuild(void)\n{', 'static void R_FrameTime_Rebuild(void)\n{\n    rebuild_calls++;')
    assert instrumented != body
    dump_start=text.index('static int R_FrameTime_RawCompare(') if 'static int R_FrameTime_RawCompare(' in text else text.index('static void R_FrameTime_Dump_f(void)')
    dump_function=text.index('static void R_FrameTime_Dump_f(void)')
    dump=text[dump_start:text.index('\n}\n',dump_function)+3]
    c.write_text(preamble+TRACKING+'\nstatic int rebuild_calls;\n'+instrumented+DUMP_STUBS+dump+'\n#undef malloc\n#undef free\n#undef qsort\n'+CASES.replace('int main(void)', 'static int legacy_main(void)')+EXACT_CASES)
    cc=a.cc or ('C:/msys64/ucrt64/bin/gcc.exe' if os.name=='nt' else shutil.which('gcc') or shutil.which('cc'))
    if not cc:
        p.error('C compiler missing; select the existing toolchain with --cc')
    env=os.environ.copy()
    env['PATH']=str(Path(cc).resolve().parent)+os.pathsep+'C:/msys64/usr/bin'+os.pathsep+env.get('PATH','')
    cmd=[cc,'-std=c99','-O2','-Wall','-Wextra','-Werror']+(['-DFIXED'] if a.fixed else [])+[str(c),'-o',str(exe)]
    build=subprocess.run(cmd,env=env,capture_output=True,text=True)
    (a.out/'build.log').write_text(build.stdout+build.stderr)
    run=None
    if build.returncode==0:
        run=subprocess.run([str(exe.resolve())],env=env,capture_output=True,text=True)
        (a.out/'run.log').write_text(run.stdout+run.stderr)
        print(run.stdout,end='')
    # Dump/label contract is checked in source; not a claim of rendered pixels.
    contract=not a.fixed or all(x in text for x in ['focus-idle excluded since reset:','sampled %.3f s','1%% tail mean','0.1%% tail mean'])
    result=dict(source=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),dump_sha256=hashlib.sha256(dump.encode()).hexdigest(),body_sha256=hashlib.sha256(body.encode()).hexdigest(),command=cmd,build_exit=build.returncode,run_exit=None if run is None else run.returncode,report_contract=contract)
    (a.out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    if build.returncode: print(build.stdout+build.stderr)
    raise SystemExit(build.returncode or (run.returncode if run else 1) or (not contract))
if __name__=='__main__': main()
