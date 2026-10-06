"""Production occlusion helper tests and optional real hl2_lightprobe log grading.

python tools/p509lighting.py --engine C:/msys64/home/Lex/fteqw [--log <log>]
The log must contain same-point hl2_lt_occlusion 1/0 arms with direct light on.
No game deployment, no player data changes, no Source screenshot parity claim.
"""
import argparse
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def extract(source, name):
    m = re.search(r'static (?:void|qboolean) ' + name + r'\s*\(', source)
    assert m, name
    brace = source.index('{', m.start())
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[m.start():end]


def unit(engine):
    source = (engine/'plugins/hl2/mod_vbsp.c').read_text(encoding='utf-8')
    # Stub only the allocator and BIH interface. The selection, lifetime wiring,
    # endpoint offset, trace mask and all acceptance rules are production code.
    code = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdarg.h>
typedef float vec3_t[3];
typedef int qboolean;
typedef unsigned int index_t;
#define true 1
#define false 0
#define NULLFRAMESTATE NULL
#define FTECONTENTS_SOLID 1
#define VWL_SURFACE 0
#define DISPSURF_NORAY_COLL 8
#define BIH_BRUSH 1
#define BIH_TRIANGLE 2
#define VectorCopy(a,b) memcpy((b),(a),sizeof(vec3_t))
#define VectorMA(a,s,b,c) do {int vi;for(vi=0;vi<3;vi++)(c)[vi]=(a)[vi]+(s)*(b)[vi];}while(0)
#define AddPointToBounds(p,a,b) do {int vi;for(vi=0;vi<3;vi++){if((p)[vi]<(a)[vi])(a)[vi]=(p)[vi];if((p)[vi]>(b)[vi])(b)[vi]=(p)[vi];}}while(0)
typedef struct {float fraction; int startsolid,allsolid;} trace_t;
struct bihnode_s {int unused;};
typedef struct model_s model_t;
typedef int (*tracefn)(model_t*,int,void*,const vec3_t*,const vec3_t,const vec3_t,const vec3_t,const vec3_t,int,unsigned int,trace_t*);
struct model_s {void *meshinfo; int memgroup; struct bihnode_s *cnodes; struct {tracefn NativeTrace;} funcs; vec3_t mins,maxs; char *name;};
typedef struct {vec3_t absmins,absmaxs; int contents;} q2cbrush_t;
typedef struct {int firstbrush,num_brushes;} cmodel_t;
typedef struct {int lightopaque; unsigned int collflags; size_t numindexes; index_t *cidx; vec3_t *xyz;} dispinfo_t;
typedef struct {cmodel_t *cmodels; size_t numworldlights,numdisplacements; dispinfo_t *displacements; q2cbrush_t *brushes; int *brushlightopaque; model_t *wl_trace_model;} vbspinfo_t;
struct vworldlight_s {vec3_t origin,normal; int type;};
struct bihleaf_s {int type; struct {q2cbrush_t *brush;struct {vec3_t *xyz;index_t *indexes;} tri;unsigned int contents;} data;vec3_t mins,maxs;};
static struct {int ival;} occ={1};
static void *hl2_lt_occlusion=&occ; /* replaced below with typed pointer */
static int calls,mode,checks;static vec3_t laststart,lastend;
static unsigned int lastmask;
static int Trace(model_t*m,int hull,void*frame,const vec3_t*axis,const vec3_t start,const vec3_t end,const vec3_t mins,const vec3_t maxs,int capsule,unsigned int mask,trace_t*out) {
    (void)m;(void)hull;(void)frame;(void)axis;(void)mins;(void)maxs;(void)capsule;
    calls++;VectorCopy(start,laststart);VectorCopy(end,lastend);lastmask=mask;
    out->fraction=mode==1?.5f:1;out->startsolid=mode==2;out->allsolid=mode==3;return 1;
}
static void *Alloc(int*group,size_t n) {(void)group;return calloc(1,n);}
static struct {void *(*GMalloc)(int*,size_t);void *(*Malloc)(size_t);void(*Free)(void*);} plugs={Alloc,malloc,free},*plugfuncs=&plugs;
static struct bihnode_s lightnodes;
static size_t built;
static struct bihleaf_s captured[16];
static void Build(model_t*m,struct bihleaf_s*l,size_t n) {built=n;memcpy(captured,l,n*sizeof(*l));m->cnodes=&lightnodes;m->funcs.NativeTrace=Trace;}
static struct {void(*BIH_Build)(model_t*,struct bihleaf_s*,size_t);} mods={Build},*modfuncs=&mods;
static void Con_DPrintf(const char *fmt,...) {(void)fmt;}
#define REQUIRE(x) do{checks++;if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);return 1;}}while(0)
'''
    code = code.replace('static struct {int ival;} occ={1};\nstatic void *hl2_lt_occlusion=&occ; /* replaced below with typed pointer */',
                        'typedef struct {int ival;} cvar_t; static cvar_t occ={1},*hl2_lt_occlusion=&occ;')
    code += extract(source, 'VBSP_BuildLightBIH') + '\n' + extract(source, 'VBSP_WorldLightVisible')
    code += r'''
int main(void) {
    struct bihnode_s original;
    cmodel_t sub={0,3}; q2cbrush_t brushes[3]={0};int opaque[3]={1,0,1};
    vec3_t xyz[3]={{0,0,0},{1,0,0},{0,1,0}};index_t indices[3]={0,1,2};
    dispinfo_t disp[3]={{1,4,3,indices,xyz},{1,8,3,indices,xyz},{0,0,3,indices,xyz}};
    vbspinfo_t prv={&sub,1,3,disp,brushes,opaque,NULL};
    model_t map={0};vec3_t point={4,5,6};struct vworldlight_s wl={{9,10,11},{0,0,1},0};
    map.meshinfo=&prv;map.cnodes=&original;map.funcs.NativeTrace=Trace;map.name="test";
    VBSP_BuildLightBIH(&map);
    REQUIRE(map.cnodes==&original);
    REQUIRE(prv.wl_trace_model && prv.wl_trace_model->cnodes==&lightnodes);
    REQUIRE(built==3); /* two opaque brushes + NOHULL ray-collidable displacement */
    REQUIRE(captured[0].data.brush==&brushes[0] && captured[1].data.brush==&brushes[2]);
    REQUIRE(captured[2].type==BIH_TRIANGLE && captured[2].data.tri.indexes==indices);
    REQUIRE(captured[0].data.contents==FTECONTENTS_SOLID && brushes[0].contents==0);
    REQUIRE(map.funcs.NativeTrace==Trace);
    REQUIRE(VBSP_WorldLightVisible(&map,point,&wl));
    REQUIRE(calls==1 && lastmask==FTECONTENTS_SOLID);
    REQUIRE(!memcmp(laststart,point,sizeof(point)));
    REQUIRE(fabsf(lastend[2]-11.125f)<.00001f);
    wl.type=1;REQUIRE(VBSP_WorldLightVisible(&map,point,&wl));
    REQUIRE(!memcmp(lastend,wl.origin,sizeof(lastend)));
    mode=1;REQUIRE(!VBSP_WorldLightVisible(&map,point,&wl));
    mode=2;REQUIRE(!VBSP_WorldLightVisible(&map,point,&wl));
    mode=3;REQUIRE(!VBSP_WorldLightVisible(&map,point,&wl));
    prv.wl_trace_model->funcs.NativeTrace=NULL;REQUIRE(!VBSP_WorldLightVisible(&map,point,&wl));
    free(prv.wl_trace_model);prv.wl_trace_model=NULL;REQUIRE(!VBSP_WorldLightVisible(&map,point,&wl));
    occ.ival=0;calls=0;REQUIRE(VBSP_WorldLightVisible(&map,point,&wl));REQUIRE(calls==0);
    prv.numworldlights=0;VBSP_BuildLightBIH(&map);REQUIRE(prv.wl_trace_model==NULL && map.cnodes==&original);
    printf("PASS production world-occlusion helpers: %d checks, 0 failed\n",checks);return 0;
}
'''
    gcc = shutil.which('gcc') or 'C:/msys64/ucrt64/bin/gcc.exe'
    with tempfile.TemporaryDirectory(prefix='p509lighting-') as tmp:
        src, exe = Path(tmp)/'light.c', Path(tmp)/'light.exe'
        src.write_text(code, encoding='utf-8')
        env = dict(os.environ)
        env['PATH'] = str(Path(gcc).resolve().parent) + os.pathsep + env.get('PATH', '')
        env['TEMP'] = env['TMP'] = tmp
        subprocess.run([gcc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(exe), '-lm'], check=True, env=env)
        subprocess.run([str(exe)], check=True, env=env)
    assert 'wantocclusion != occlusion_live' in source
    print('PASS occlusion is part of the prop cache key')


def parse_probes(path):
    probes, current = [], None
    for line in path.read_text(errors='replace').splitlines():
        if '[lightprobe] ' not in line:
            continue
        fields = line.split('[lightprobe] ', 1)[1].split()
        if fields[0] == 'point':
            current = {'point': tuple(map(float, fields[1:4])), 'occlusion': int(fields[5]), 'lights': {}, 'faces': {}}
            probes.append(current)
        elif fields[0] == 'light':
            current['lights'][int(fields[1])] = (fields[2], list(map(float, fields[4:7])), list(map(float, fields[8:11])))
        elif fields[0] == 'face':
            current['faces'][int(fields[1])] = list(map(float, fields[2:5]))
    return probes


def grade_log(path):
    probes = parse_probes(path)
    assert probes, 'no acted-on probes'
    blocked, visible, compared = 0, 0, 0
    for p in probes:
        expected = [[0., 0., 0.] for _ in range(6)]
        for status, rgb, direction in p['lights'].values():
            if status == 'blocked':
                blocked += 1
                continue
            assert status == 'visible'
            visible += 1
            for face in range(6):
                weight = max(0., direction[face//2] * (1 if face%2 == 0 else -1))
                for c in range(3):
                    expected[face][c] += weight*rgb[c]
        assert len(p['faces']) == 6
        assert all(math.isclose(expected[f][c], p['faces'][f][c], abs_tol=2e-5) for f in range(6) for c in range(3)), p
        if not p['occlusion']:
            assert all(row[0] == 'visible' for row in p['lights'].values())
            for on in probes:
                if on['occlusion'] and on['point'] == p['point']:
                    assert on['lights'].keys() == p['lights'].keys()
                    assert all(on['lights'][i][1:] == p['lights'][i][1:] for i in p['lights'])
                    compared += 1
    assert blocked > 0 and visible > 0 and compared > 0, 'both blocked and visible controls plus PVS-only arms must ACT'
    print(f'PASS runtime: {len(probes)} cubes reconstruct from visible lights ONLY; {blocked} blocked, {visible} visible, {compared} matched arms')
    for p in probes:
        if p['occlusion']:
            lum = [sum(v*w for v,w in zip(p['faces'][f],(.299,.587,.114))) for f in range(6)]
            print('sample',p['point'],'direct luminance +/-XYZ',*[round(x,6) for x in lum])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, default=Path('C:/msys64/home/Lex/fteqw'))
    ap.add_argument('--log', type=Path)
    args = ap.parse_args()
    unit(args.engine)
    if args.log:
        grade_log(args.log)


if __name__ == '__main__':
    main()
