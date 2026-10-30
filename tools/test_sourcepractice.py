#!/usr/bin/env python3
"""Exercise the exact native slow-practice pose-ring functions and math primitives.

Core arithmetic/bounds only; not collision, network, adapter or deployment proof.
The native full build and actual socket on/off capture cover those separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

TEST = r'''
static void near(float a,float b) {assert(fabsf(a-b)<.0001f);}
int main(int argc,char **argv) {
 sourcepracticelerp_t s={0},saved;
 vec3_t p={0,0,0},v={100,0,0},out={-999,-999,-999};
 int i;float t;
 if(argc>1 && !strcmp(argv[1],"idle-resume")) {
  assert(CL_SourcePracticePush(&s,1,p,v,.15f));p[0]=10;
  assert(CL_SourcePracticePush(&s,1.15f,p,vec3_origin,.15f));
  assert(CL_SourcePracticePush(&s,1.4f,p,vec3_origin,.15f));p[0]=20;
  assert(CL_SourcePracticePush(&s,1.45f,p,v,.15f));
  assert(CL_SourcePracticeSample(&s,1.285f,out));
  if(fabsf(out[0]-10)>.0001f) {printf("FAIL idle resumes by moving backward: x=%g expected10\\n",out[0]);return 2;}
  assert(CL_SourcePracticeSample(&s,1.1f,out));near(out[0],10*(.1f/.15f));
  puts("PASS motion-stop-idle-resume preserves earlier segment and stationary endpoint");return 0;
 }
 if(argc>1 && !strcmp(argv[1],"teleport")) {
  vec3_t diagonal={100,100,0},edge={128,0,0},beyond={129,0,0};
  if(!native_jump_guard(diagonal)) {puts("FAIL diagonal teleport100,100 is not spherical128 snap");return 2;}
  assert(!native_jump_guard(edge));assert(native_jump_guard(beyond));
  puts("PASS actual native adapter uses the existing spherical128 teleport boundary");return 0;
 }
 if(argc>1 && !strcmp(argv[1],"stair-view")) {
  float classic=native_stair_view(16,-16,-15,false);
  float active=native_stair_view(16,-16,-15,true);
  near(classic,65);
  if(active<64) {printf("FAIL delayed step combines current stair correction: viewZ=%g expected>=64\\n",active);return 2;}
  near(active,64);
  puts("PASS actual view integration does not apply a future stair correction to delayed feet");return 0;
 }
 if(argc>1 && !strcmp(argv[1],"stair-entry")) {
#if HAS_PRACTICE_ENTRY
  vec3_t feet={0,0,16},gravity={0,0,-1},anchor;
  CL_SourcePracticeEntry(feet,gravity,-15,anchor);near(anchor[2],1);
  near(native_stair_view(16,anchor[2]-16,-15,true),native_stair_view(16,0,-15,false));
  puts("PASS entering interpolation preserves the already-presented stair height");return 0;
#else
  puts("UNAVAILABLE entry helper in retained revision; not a runtime counterexample");return 77;
#endif
 }
 if(argc>1 && !strcmp(argv[1],"save-epoch")) {
#if HAS_SAVE_EPOCH
  assert(!CL_SourcePracticeSaveEpochChanged(9,1,10,1));
  assert(!CL_SourcePracticeSaveEpochChanged(10,1,10,1));
  assert(!CL_SourcePracticeSaveEpochChanged(10,2,11,1));
  assert(CL_SourcePracticeSaveEpochChanged(10,1,11,2));
  assert(CL_SourcePracticeSaveEpochChanged(11,2,12,3));
  assert(CL_SourcePracticeSaveEpochChanged(12,3,13,4));
  assert(CL_SourcePracticeSaveEpochChanged(10,1,10,2));
  puts("PASS save metadata preserves camera history; load/retry/resume and late op changes reset it");return 0;
#else
  puts("UNAVAILABLE epoch helper in retained revision; not a runtime counterexample");return 77;
#endif
 }
 if(argc>1 && !strcmp(argv[1],"roof-view")) {
#if HAS_VIEW_ROOF
  vec3_t feet={-20,0,0},gravity={0,0,-1};
  fixture_fraction=.5f;fixture_hit[0]=-20;fixture_hit[1]=0;fixture_hit[2]=63;
  near(V_SourcePracticeEye(feet,gravity,64),51);
  near(fixture_from[0],-20);near(fixture_from[2],32);near(fixture_to[2],76);
  fixture_hit[0]=0;
  near(native_stair_view(0,0,0,true),51);
  near(native_stair_view(0,0,0,false),64);
  fixture_fraction=1;near(V_SourcePracticeEye(feet,gravity,64),64);
  near(V_SourcePracticeEye(feet,gravity,0),0);
  puts("PASS literal rendered-eye helper/call bounds the delayed location using a controlled trace hit; not a native geometry test");return 0;
#else
  puts("UNAVAILABLE rendered-eye helper in retained revision; not a runtime counterexample");return 77;
#endif
 }
 if(argc>1 && !strcmp(argv[1],"packet-delay")) {
  float delay=native_delay(.015f,.75f),first,second;
  p[0]=0;v[0]=100;assert(CL_SourcePracticePush(&s,0,p,v,.02f));
  p[0]=3;assert(CL_SourcePracticePush(&s,.03f,p,v,.02f));
  assert(CL_SourcePracticeSample(&s,.055f-delay,out));first=out[0];
  assert(CL_SourcePracticeSample(&s,.059f-delay,out));second=out[0];
  if(second<=first) {printf("FAIL packet-quantized gap freezes at newest pose: delay=%g first=%g second=%g\\n",delay,first,second);return 2;}
  near(delay,.035f);near(first,2);near(second,2.4f);
  puts("PASS actual target delay covers real packet quantization without extrapolating");return 0;
 }
 assert(argc==1);
 assert(!CL_SourcePracticeSample(&s,0,out));near(out[0],-999);
 assert(CL_SourcePracticePush(&s,0,p,v,.03f));
 p[0]=3;assert(CL_SourcePracticePush(&s,.03f,p,v,.03f));
 assert(CL_SourcePracticePush(&s,.045f,p,v,.03f));assert(s.count==2);
 p[0]=6;assert(CL_SourcePracticePush(&s,.06f,p,v,.03f));
 for(i=0;i<=60;i++) {
  t=i*.001f;assert(CL_SourcePracticeSample(&s,t,out));near(out[0],t*100);
  near(out[1],0);near(out[2],0);
 }
 puts("PASS completed-tick interpolation rejects moving duplicate packet holds");
 assert(CL_SourcePracticeSample(&s,-1,out));near(out[0],0);
 assert(CL_SourcePracticeSample(&s,100,out));near(out[0],6);
 puts("PASS endpoints clamp; no future movement extrapolation");
 memset(&s,0,sizeof(s));p[0]=0;
 assert(CL_SourcePracticePush(&s,0,p,vec3_origin,.03f));
 assert(CL_SourcePracticePush(&s,9,p,vec3_origin,.03f));assert(s.count==1);
 p[0]=3;assert(CL_SourcePracticePush(&s,10,p,v,.03f));
 assert(CL_SourcePracticeSample(&s,9.9f,out));near(out[0],0);
 assert(CL_SourcePracticeSample(&s,9.985f,out));near(out[0],1.5f);
 puts("PASS long stationary interval does not become a slow idle glide");
 memset(&s,0,sizeof(s));p[0]=12;
 assert(CL_SourcePracticePush(&s,-.03f,p,v,.03f));p[0]=15;
 assert(CL_SourcePracticePush(&s,.015f,p,v,.03f));
 assert(CL_SourcePracticeSample(&s,-.03f,out));near(out[0],12);
 puts("PASS first presented anchor is continuous, including initial negative lookback");
 saved=s;p[0]=NAN;assert(!CL_SourcePracticePush(&s,.03f,p,v,.03f));
 assert(!memcmp(&s,&saved,sizeof(s)));p[0]=INFINITY;
 assert(!CL_SourcePracticePush(&s,.03f,p,v,.03f));p[0]=20;
 assert(!CL_SourcePracticePush(&s,NAN,p,v,.03f));
 assert(!CL_SourcePracticePush(&s,INFINITY,p,v,.03f));
 assert(!CL_SourcePracticePush(&s,.03f,p,v,0));
 assert(!CL_SourcePracticePush(&s,-.05f,p,v,.03f));
 assert(!CL_SourcePracticePush(&s,.015f,p,v,.03f));
 assert(!CL_SourcePracticeSample(&s,NAN,out));
 assert(!memcmp(&s,&saved,sizeof(s)));
 puts("PASS nonfinite/backward/equal changed stamps fail without corrupting history");
 memset(&s,0,sizeof(s));
 for(i=0;i<1000;i++) {p[0]=i;assert(CL_SourcePracticePush(&s,i*.03f,p,v,.03f));}
 assert(s.count==SOURCE_PRACTICE_POSES&&s.next==1000%SOURCE_PRACTICE_POSES);
 assert(CL_SourcePracticeSample(&s,-100,out));near(out[0],1000-SOURCE_PRACTICE_POSES);
 assert(CL_SourcePracticeSample(&s,1000,out));near(out[0],999);
 for(i=969;i<999;i++) {
  assert(CL_SourcePracticeSample(&s,(i+.5f)*.03f,out));
  assert(out[0]>=i&&out[0]<=i+1);
 }
 puts("PASS fixed ring wraps, retains ordered endpoints and cannot overshoot a segment");
 return 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--source', type=Path, help='Exact retained native source for a negative control; math remains the unchanged native implementation')
    ap.add_argument('--view-source', type=Path, help='Exact retained view source for the independent stair integration control')
    a = ap.parse_args()
    native = a.engine/'engine'
    source_file = a.source or native/'client/cl_pred.c'
    source = source_file.read_text()
    start = '#define SOURCE_PRACTICE_POSES 32'
    end = 'static qboolean CL_SourcePracticeContext'
    assert source.count(start) == source.count(end) == 1
    core = start + source.split(start, 1)[1].split(end, 1)[0]
    declaration = 'static sourcepracticelerp_t sourcepractice[MAX_SPLITS];'
    assert core.count(declaration) == 1
    core = core.replace(declaration, '')
    anchor = '\t\tVectorSubtract(ent->origin, s->pose[(s->next + SOURCE_PRACTICE_POSES - 1) % SOURCE_PRACTICE_POSES].origin, delta);'
    assert source.count(anchor) == 1, 'Native discontinuity source drift'
    guard = source.split(anchor,1)[1].split('\n\t}',1)[0]
    assert guard.count('goto discontinuity;') == 1
    guard = '\nstatic qboolean native_jump_guard(const vec3_t delta) { int i=0;(void)i;'+guard+'\nreturn false; discontinuity:return true;}\n'
    target_lines=[line for line in source.splitlines() if 'target = cl.servertime - ' in line]
    assert len(target_lines)==1,'Actual native target expression drifted'
    delay_control='''\nstatic float native_delay(float tick,float scale) {\n struct {double servertime;} cl={0};\n float interval=tick/scale,target;(void)interval;\n'''+target_lines[0]+'''\n return -target;\n}\n'''
    view_file = a.view_source or native/'client/view.c'
    view = view_file.read_text()
    begin = '// refresh position from simulated origin'
    end_view = '\n\tr_refdef.useperspective = true;'
    assert view.count(begin) == 1
    view = view.split(begin,1)[1]
    assert view.count(end_view) == 1, 'Scope delimiter after simulated-origin refresh drifted'
    view = view.split(end_view,1)[0]
    height_source = view_file.read_text()
    height_lines = [line for line in height_source.splitlines() if 'viewheight +=' in line and 'crouch' in line]
    assert len(height_lines) == 1, 'Native stair-height source drift'
    height_tail = height_source.split(height_lines[0],1)[1].split('\n\tVectorMA(r_refdef.vieworg, -viewheight, pv->gravitydir, r_refdef.vieworg);',1)[0]
    assert len(height_tail) < 512, 'Eye placement scope drifted'
    roof = re.search(r'static float V_SourcePracticeEye\(.*?\n\}',height_source,re.S)
    roof_control = ''
    if roof:
        pm_source = (native/'common/pm_source.c').read_text()
        clip = re.search(r'float PMSrc_ClipRenderEye\s*\([^}]*\n\}',pm_source)
        assert clip, 'Actual Source eye bound drifted'
        macros = [line.strip() for line in (native/'client/quakedef.h').read_text().splitlines() if re.match(r'\s*#define (min|max)\(',line)]
        assert len(macros)==2
        roof_control = '\n'.join(macros)+'\n'+r'''
static float fixture_fraction=1;
static vec3_t fixture_hit,fixture_from,fixture_to;
static float CL_TraceLineProps(vec3_t from,vec3_t to,vec3_t hit,vec3_t normal,int *ent) {
 (void)normal;(void)ent;VectorCopy(from,fixture_from);VectorCopy(to,fixture_to);
 VectorCopy(fixture_hit,hit);return fixture_fraction;
}
'''+clip.group(0)+'\n'+roof.group(0)+'\n'
    view_control = r'''
struct {vec3_t vieworg;} r_refdef;
static qboolean view_active;
static float view_delta;
static qboolean CL_GetSourcePracticeViewOffset(const void *pv,vec3_t out) {
 (void)pv;out[0]=out[1]=0;out[2]=view_delta;return view_active;
}
static float native_stair_view(float raw,float delta,float crouch,qboolean active) {
 struct {vec3_t simorg,gravitydir;float crouch;} body={{0,0,0},{0,0,-1},0},*pv=&body;
 vec3_t practiceoffset;float viewheight=64;qboolean practiceview=false;
 (void)practiceview;body.simorg[2]=raw;body.crouch=crouch;view_active=active;view_delta=delta;
'''+view+'\n'+height_lines[0]+height_tail+r'''
 return r_refdef.vieworg[2]+viewheight;
}
'''
    math = (native/'common/mathlib.c').read_text()
    compare = re.search(r'\nint\s+VectorCompare\s*\([^)]*\)\s*\{.*?\n\}', math, re.S)
    assert compare, 'Native VectorCompare source drift'
    preface = '#include <assert.h>\n#include <math.h>\n#include <stdio.h>\n#include <string.h>\n#include <stdbool.h>\ntypedef int qboolean;typedef unsigned char qbyte;\n#define FTE_ALIGN(x)\n#define QDECL\n#define VARGS\n'
    preface += '#include "'+(native/'common/mathlib.h').as_posix()+'"\nvec3_t vec3_origin={0,0,0};\n'
    preface += '#define HAS_PRACTICE_ENTRY '+str(int(core.count('static void CL_SourcePracticeEntry(')==1))+'\n'
    preface += '#define HAS_SAVE_EPOCH '+str(int(core.count('static qboolean CL_SourcePracticeSaveEpochChanged(')==1))+'\n'
    preface += '#define HAS_VIEW_ROOF '+str(int(bool(roof)))+'\n'
    a.out.mkdir(exist_ok=True, parents=True)
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    view_digest = hashlib.sha256(view_file.read_bytes()).hexdigest()
    script_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    digest = hashlib.sha256((source_digest+view_digest+script_digest).encode()).hexdigest()
    file = a.out/('sourcepractice-core-'+digest[:12]+'.c')
    file.write_text(preface+compare.group(0)+'\n'+core+guard+delay_control+roof_control+view_control+TEST)
    gcc = Path('C:/msys64/ucrt64/bin/gcc.exe')
    exe = file.with_suffix('.exe')
    env = dict(os.environ)
    env['PATH'] = str(gcc.parent)+os.pathsep+env.get('PATH','')
    compile = subprocess.run([str(gcc),'-O2','-fno-strict-aliasing','-Wall','-Wextra','-Werror',str(file),'-o',str(exe)],capture_output=True,text=True,env=env)
    if compile.returncode:
        print('COMPILE_FAILURE (not a product counterexample)',compile.stdout+compile.stderr)
        (a.out/('compile-failure-'+digest[:12]+'.json')).write_text(json.dumps({'source':str(source_file),'viewSource':str(view_file),'scriptSha256':script_digest,'exit':compile.returncode,'stdout':compile.stdout,'stderr':compile.stderr},indent=2)+'\n')
        raise SystemExit(3)
    results = []
    for case in ['core','idle-resume','teleport','stair-view','stair-entry','save-epoch','roof-view','packet-delay']:
        run = subprocess.run([str(exe)]+([] if case=='core' else [case]),capture_output=True,text=True,env=env)
        print(case,'exit',run.returncode,run.stdout+run.stderr,flush=True)
        results.append({'case':case,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
    (a.out/('receipt-'+digest[:12]+'.json')).write_text(json.dumps({'source':str(source_file),'sourceSha256':source_digest,'viewSource':str(view_file),'viewSha256':view_digest,'scriptSha256':script_digest,'compileExit':0,'generatedC':str(file),'limits':'Exact source snippets with controlled trace response; no native stair/roof collision-world scene runtime claim','results':results},indent=2)+'\n')
    raise SystemExit(int(any(row['exit'] for row in results)))


if __name__ == '__main__':
    main()
