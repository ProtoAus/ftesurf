#!/usr/bin/env python3
"""Small native codec/storage falsifier; no Valve assets or game processes."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--engine', required=True, type=Path)
p.add_argument('--work-root', required=True, type=Path)
p.add_argument('--compiler', default='C:/msys64/ucrt64/bin/gcc.exe')
a = p.parse_args()
if a.work_root.exists() or not any((q / 'OWNER.md').is_file() for q in a.work_root.parents):
    p.error('fresh work-root under an existing owned task root required')
a.work_root.mkdir(parents=True)
(a.work_root / 'OWNER.md').write_text('Owned P952 synthetic frame-codec checks. No licensed model data. Retain source/logs; executable disposable.\n', encoding='utf-8')
main = (a.engine / 'plugins/hl2/mod_hl2.c').read_text(encoding='utf-8')
header = (a.engine / 'plugins/hl2/mod_hl2_weapon.h').read_text(encoding='utf-8')
span_start = main.index('static qboolean HL2_EventSpan(')
span = main[span_start:main.index('\n}', span_start) + 2]
half_start = main.index('static float HalfToFloat(')
half = main[half_start:main.index('static void Mod_HL2_ReadPose(', half_start)]
codec = header[header.index('static qboolean HL2_WeaponQuat('):header.index('static qboolean HL2_WeaponPose(')]
prefix = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char qbyte;
typedef int qboolean;
typedef float vec3_t[3], vec4_t[4];
#define true 1
#define false 0
#define max(a,b) ((a)>(b)?(a):(b))
typedef struct { vec3_t pos; vec4_t quat; } hl2mdlbone_t;
static void matrix(const float *p, const float *q, const float *s, float *out)
{ unsigned i; (void)s; for(i=0;i<12;i++)out[i]=0; memcpy(out,p,12); memcpy(out+3,q,16); }
static struct { void (*GenMatrixPosQuat4Scale)(const float*,const float*,const float*,float*); } api={matrix}, *modfuncs=&api;
'''
tests = r'''
int main(void)
{
    unsigned char data[256]={0}; unsigned h[6]={28,40,12,0,0,0};
    float constant[3]={1,2,3}, varying[6]={4,5,6,7,8,9}, out[12];
    hl2mdlbone_t bone={{10,20,30},{0,0,0,1}};
    unsigned short packed[3]={16384,16384,16384}; float q[4];
    float baked[61*40*12]={0}; void *opaque=baked;
    float *first=HL2_WeaponFrameBase(opaque,0,40), *next=HL2_WeaponFrameBase(opaque,1,40);
    float *last=HL2_WeaponFrameBase(opaque,60,40);
    assert(first==baked && next==baked+480 && last==baked+60*480);
    first[479]=11; next[0]=22; last[479]=33;
    assert(baked[479]==11 && baked[480]==22 && baked[61*40*12-1]==33);
    assert(HL2_WeaponQuat((qbyte*)packed,1,q) && q[3]==1);
    packed[2]|=32768; assert(HL2_WeaponQuat((qbyte*)packed,1,q) && q[3]==-1);
    packed[0]=packed[1]=packed[2]=32767; assert(!HL2_WeaponQuat((qbyte*)packed,1,q));
    memcpy(data,h,sizeof(h)); data[24]=32|16; memcpy(data+28,constant,12); memcpy(data+40,varying,24);
    assert(HL2_WeaponFrame(data,64,0,&bone,1,0,out) && out[0]==4 && out[1]==5 && out[6]==1);
    assert(HL2_WeaponFrame(data,64,0,&bone,1,1,out) && out[0]==7 && out[2]==9);
    assert(!HL2_WeaponFrame(data,63,0,&bone,1,1,out));
    assert(!HL2_WeaponFrame(data,64,0,&bone,0,0,out));
    assert(!HL2_WeaponFrame(data,64,0,&bone,257,0,out));
    assert(!HL2_WeaponFrame(data,64,0,&bone,1,4096,out));
    assert(!HL2_WeaponFrame(data,12,0,&bone,1,0,out));
    h[2]=11; memcpy(data,h,sizeof(h)); assert(!HL2_WeaponFrame(data,64,0,&bone,1,0,out));
    h[2]=12; h[0]=UINT32_MAX; memcpy(data,h,sizeof(h)); assert(!HL2_WeaponFrame(data,64,0,&bone,1,0,out));
    h[0]=28; memcpy(data,h,sizeof(h)); data[24]=3; assert(!HL2_WeaponFrame(data,64,0,&bone,1,0,out));
    data[24]=0; assert(HL2_WeaponFrame(data,64,0,&bone,1,0,out) && out[0]==10 && out[6]==1);
    data[24]=16; varying[0]=INFINITY; memcpy(data+40,varying,24); assert(!HL2_WeaponFrame(data,64,0,&bone,1,0,out));
    // CS:GO Legacy: actual frame records have 12 bytes reserved after the
    // first three words. Do not silently apply another reader's 12-byte layout.
    memset(data,0,sizeof(data)); h[0]=28; h[1]=h[2]=0;
    memcpy(data,h,sizeof(h)); data[24]=32; memcpy(data+28,constant,12);
    assert(HL2_WeaponFrame(data,40,0,&bone,1,0,out) && out[0]==1 && out[1]==2 && out[2]==3);
    memset(data,0,sizeof(data)); h[0]=16; memcpy(data,h,12); data[12]=32; memcpy(data+16,constant,12);
    assert(!HL2_WeaponFrame(data,28,0,&bone,1,0,out));
    puts("PASS native frame/quaternion and multi-frame storage controls (opaque stride, non-overlap, Legacy format, bounds, finite, bind pose)");
    return 0;
}
'''
source = a.work_root / 'frame-codec.c'
exe = a.work_root / 'frame-codec.exe'
source.write_text(prefix + span + half + codec + tests, encoding='utf-8')
env = os.environ.copy()
env['PATH'] = str(Path(a.compiler).parent) + os.pathsep + env.get('PATH', '')
build = subprocess.run([a.compiler, '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-lm', '-o', str(exe)], env=env, capture_output=True, text=True)
(a.work_root / 'build.log').write_text(build.stdout + build.stderr, encoding='utf-8')
if build.returncode:
    sys.exit('native test compile failed; see ' + str(a.work_root / 'build.log'))
result = subprocess.run([str(exe)], capture_output=True, text=True)
(a.work_root / 'result.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
print(result.stdout, end='')
if result.returncode:
    sys.exit(result.stderr or f'native test failed ({result.returncode}); see result.txt')
