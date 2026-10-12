#!/usr/bin/env python3
"""Exercise the actual VTF mip/frame loop with deterministic synthetic payloads.

No game/assets needed. --workdir must be an existing owned scratch directory.
Extracts the production loop, not a Python reproduction of its indexing.
"""
import argparse
import os
from pathlib import Path
import subprocess

PREFIX = r'''
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned char qbyte;
#define countof(x) (sizeof(x)/sizeof(*(x)))
#define PTI_2D_ARRAY 1
#define CON_ERROR ""
#define Con_Printf(...) fprintf(stderr, __VA_ARGS__)
struct mip { unsigned width,height,depth; size_t datasize; qbyte *data; };
struct pendingtextureinfo { int type; unsigned mipcount; struct mip mip[72]; };
struct api { void (*Free)(void*); } api = {free}, *plugfuncs = &api;
static struct pendingtextureinfo *walk(qbyte *filedata, size_t size,
    unsigned framecount, unsigned mipcount, unsigned faces, unsigned storedfaces,
    int array)
{
    struct header { unsigned mipmapcount,numframes,width,height; } header =
        {mipcount,framecount,1u<<(mipcount-1),1u<<(mipcount-1)}, *vtf=&header;
    struct pendingtextureinfo *mips=calloc(1,sizeof(*mips));
    qbyte *end=filedata+size, *axcraw=NULL;
    const char *fname="synthetic";
    unsigned frames=array?framecount:1, miplevels=mipcount;
    unsigned bw=1,bh=1,bd=1,bb=1,w,h,d=1,miplevel,frame,img;
    size_t datasize;
    mips->type=array?PTI_2D_ARRAY:0;
    (void)axcraw; (void)fname;
'''
SUFFIX = r'''
    return mips;
}
int main(void)
{
    unsigned cases[][4]={{331,8,1,1},{1,8,1,1},{80,8,6,7},{331,8,1,1}};
    for (unsigned c=0;c<4;c++) {
        unsigned nf=cases[c][0],nm=cases[c][1],faces=cases[c][2],stored=cases[c][3];
        size_t length=0;
        for(unsigned m=0;m<nm;m++){ size_t w=1u<<(nm-1-m); length+=w*w*nf*stored; }
        qbyte *payload=malloc(length),*p=payload;
        size_t expected[16];
        for(unsigned m=nm;m-->0;) {
            size_t w=1u<<(nm-1-m), bytes=w*w; expected[m]=p-payload;
            for(unsigned f=0;f<nf;f++) {
                memset(p,(m*17+f)%251,bytes*stored);p+=bytes*stored;
            }
        }
        struct pendingtextureinfo *out=walk(payload,length,nf,nm,faces,stored,c==3);
        if(!out){ fprintf(stderr,"unexpected reject case %u\n",c);return 1; }
        for(unsigned m=0;m<nm;m++) {
            size_t w=1u<<(nm-1-m), bytes=w*w;
            if(out->mip[m].data!=payload+expected[m] ||
               out->mip[m].datasize!=bytes*faces*(c==3?nf:1)) {
                fprintf(stderr,"wrong frame-zero offset/size case %u mip %u\n",c,m);return 2;
            }
            if(out->mip[m].data[0]!=(m*17)%251){fprintf(stderr,"wrong frame pixels\n");return 3;}
        }
        free(out);
        if(c!=2) {
            out=walk(payload,length-1,nf,nm,faces,stored,c==3);
            if(out){fprintf(stderr,"truncated input accepted\n");return 4;}
        }
        free(payload);
    }
    puts("PASS VTF: single-frame, 331-frame 2D, legacy cubemap, array, truncation");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    args = parser.parse_args()
    if not args.workdir.is_dir():
        parser.error('--workdir must already exist under your owned task root')
    source = (args.engine / 'plugins/hl2/img_vtf.c').read_text(encoding='utf-8')
    start = source.index('\t\tfor (miplevel = vtf->mipmapcount; miplevel-- > 0;)')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    code = args.workdir / 'vtf-frame-loop.c'
    exe = args.workdir / 'vtf-frame-loop.exe'
    code.write_text(PREFIX + source[start:end] + SUFFIX, encoding='utf-8')
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join((str(Path(args.cc).parent), env['PATH']))
    subprocess.run([args.cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(code), '-o', str(exe)], check=True, env=env)
    subprocess.run([str(exe.resolve())], check=True, env=env)


if __name__ == '__main__':
    main()
