"""Compare actual native buf_loadfile implementations, not a Python re-spelling.

Extract the control/candidate builtin and VFS_GETS from engine source. Compile
with a short-read-capable memory VFS and compare every appended string, including
legacy 8191-byte splitting, embedded NULs and the untrimmed CR at EOF. An optional
private recording stays in memory; neither its rows nor its name are printed.
All generated files must live in an explicitly owned --work directory.
"""
import argparse
import os
from pathlib import Path
import random
import re
import subprocess


def function(text, name):
    match = re.search(r"^(?:void QCBUILTIN |char \*)" + name + r"\s*\([^\n]*\).*?^}",
                      text, re.M | re.S)
    if not match:
        raise ValueError(f"Cannot extract {name}")
    return match.group(0)


STUB = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef struct {int unused;} pubprogfuncs_t;
struct globalvars_s {float v[3];};
typedef struct {const unsigned char *data; size_t size, pos, calls, cap;} vfsfile_t;
static vfsfile_t input;
static struct {pubprogfuncs_t *prinst;} strbuflist[1];
static size_t strbufmax = 1;
static char **rows;
static size_t count;
enum {false=0, true=1, BUFSTRBASE=1, FS_GAME=1, OFS_PARM0=0, OFS_PARM1=1, OFS_RETURN=2};
#define QCBUILTIN
#define G_FLOAT(n) (pr_globals->v[n])
#define PR_GetStringOfs(p,n) ("primary")
#define Con_Printf(...) ((void)0)
static int QC_FixFileName(const char *n, const char **out, const char **fallback)
{*out=n; *fallback=NULL; return 1;}
static vfsfile_t *FS_OpenVFS(const char *n, const char *m, int root)
{(void)n; (void)m; (void)root; return &input;}
static int VFS_READ(vfsfile_t *f, void *dst, size_t n)
{
    f->calls++;
    if (n > f->size-f->pos) n=f->size-f->pos;
    if (f->cap && n > f->cap) n=f->cap;
    memcpy(dst,f->data+f->pos,n); f->pos+=n; return (int)n;
}
static void VFS_CLOSE(vfsfile_t *f) {(void)f;}
static size_t PF_bufstr_add_internal(int b, const char *s, int append)
{
    size_t n=strlen(s)+1;
    if (b || !append) abort();
    rows=realloc(rows,(count+1)*sizeof(*rows));
    if (!rows) abort();
    rows[count]=malloc(n); if (!rows[count]) abort();
    memcpy(rows[count],s,n); return count++;
}
static void prefix(void)
{
    rows=NULL; count=0;
    PF_bufstr_add_internal(0,"existing prefix",1);
    rows=realloc(rows,2*sizeof(*rows)); if (!rows) abort();
    rows[count++]=NULL; /* Existing hole must stay; loads append. */
}
'''

MAIN = r'''
int main(int argc,char **argv)
{
    FILE *f;
    long size;
    unsigned char *data;
    char **old;
    size_t i, oldcount, oldcalls, newcalls;
    pubprogfuncs_t vm={0};
    struct globalvars_s g={{0,1,0}};
    if (argc!=3) return 2;
    f=fopen(argv[1],"rb"); if (!f) return 3;
    if (fseek(f,0,SEEK_END) || (size=ftell(f))<0 || fseek(f,0,SEEK_SET)) return 4;
    data=malloc((size_t)size+1); if (!data) return 5;
    if (fread(data,1,(size_t)size,f)!=(size_t)size) return 6;
    fclose(f);
    input.data=data; input.size=(size_t)size; input.cap=(size_t)strtoul(argv[2],NULL,10);
    strbuflist[0].prinst=&vm;
    prefix(); PF_buf_loadfile_old(&vm,&g);
    if (g.v[OFS_RETURN]!=1) return 7;
    old=rows; oldcount=count; oldcalls=input.calls;
    input.pos=input.calls=0;
    prefix(); PF_buf_loadfile(&vm,&g);
    if (g.v[OFS_RETURN]!=1 || count!=oldcount) return 8;
    newcalls=input.calls;
    for (i=0;i<count;i++)
    {
        if ((!old[i]) != (!rows[i])) return 9;
        if (old[i] && strcmp(old[i],rows[i]))
        {fprintf(stderr,"row mismatch at %zu\n",i); return 10;}
        free(old[i]); free(rows[i]);
    }
    if (size>100000 && !input.cap && newcalls*100>=oldcalls) return 11;
    printf("rows %zu; backend reads %zu -> %zu\n",count-2,oldcalls,newcalls);
    free(old); free(rows); free(data); return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--baseline', default='f76bd37bf')
    p.add_argument('--cc', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--recording', type=Path)
    a = p.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    rel = 'engine/common/pr_bgcmd.c'
    old = subprocess.check_output(['git', '-C', str(a.engine), 'show', f'{a.baseline}:{rel}'],
                                  text=True, encoding='utf-8')
    current = (a.engine / rel).read_text(encoding='utf-8')
    vfs = (a.engine / 'engine/common/fs.c').read_text(encoding='utf-8')
    source = (STUB + '\n' + function(vfs, 'VFS_GETS') + '\n' +
              re.sub(r'\bPF_buf_loadfile\b', 'PF_buf_loadfile_old', function(old, 'PF_buf_loadfile'), count=1) + '\n' +
              function(current, 'PF_buf_loadfile') + '\n' + MAIN)
    c = a.work / 'bufload-check.c'
    exe = a.work / ('bufload-check.exe' if os.name == 'nt' else 'bufload-check')
    c.write_text(source, encoding='utf-8')
    env = os.environ.copy()
    if os.name == 'nt':
        # Match build.ps1: cc1's DLLs and a native, writable compiler temp path.
        msys_bin = a.cc.parent.parent.parent / 'usr/bin'
        env['PATH'] = os.pathsep.join([str(a.cc.parent), str(msys_bin), env.get('PATH', '')])
    for key in ['TMP', 'TEMP', 'TMPDIR']:
        env[key] = str(a.work.resolve())
    subprocess.run([str(a.cc), '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(c), '-o', str(exe)], check=True, env=env)
    fixtures = [b'', b'\n', b'\r\n', b'a', b'a\r', b'a\r\n', b'a\r\nb\nc\r',
                b'a\0b\n\0c\r\n', bytes(range(256)) * 80]
    for n in [8189, 8190, 8191, 8192, 8193, 16382, 65534, 65535, 65536, 65537]:
        fixtures += [b'x'*n+b'\nend', b'x'*n+b'\r\n\n', b'x'*n+b'\r']
    rng = random.Random(935)
    fixtures.append(bytes(rng.choice([0, 10, 13, 65, 255]) for _ in range(200000)))
    cases = 0
    for i, data in enumerate(fixtures):
        f = a.work / f'case-{i}.bin'
        f.write_bytes(data)
        for cap in [0, 1, 7, 8191]:
            subprocess.run([str(exe), str(f), str(cap)], check=True, stdout=subprocess.DEVNULL)
            cases += 1
    print(f'PASS {cases} native control/candidate edge and short-read cases')
    if a.recording:
        result = subprocess.check_output([str(exe), str(a.recording), '0'], text=True).strip()
        print('PASS intact private recording:', result)


if __name__ == '__main__':
    main()
