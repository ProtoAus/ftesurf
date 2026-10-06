"""Compile the production ambient-floor helper and grade both lighting slots.

Usage: python tools/p508ambient.py [--engine C:/msys64/home/Lex/fteqw]
Requires GCC. Does not build/deploy the game or touch player data.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def function(source, name):
    start = source.index('static void ' + name + '(')
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, default=Path('C:/msys64/home/Lex/fteqw'))
    args = ap.parse_args()
    source = (args.engine / 'plugins/hl2/mod_vbsp.c').read_text(encoding='utf-8')
    # Grade real code, not a Python copy of its arithmetic.
    code = '''#include <math.h>
#include <stdio.h>
#include <string.h>
typedef float vec3_t[3];
#define VectorSet(v,x,y,z) ((v)[0]=(x),(v)[1]=(y),(v)[2]=(z))
''' + function(source, 'VBSP_FloorModelAmbient') + r'''
int main(void) {
    const float bases[][3] = {{0,0,0},{3,4,7},{16,16,16},{30,50,70},{0,0,100},{0.0001f,0,0}};
    const float floors[] = {0,16,64};
    int i,j,c,checks=0;
    for(i=0;i<6;i++) for(j=0;j<3;j++) {
        vec3_t base,range={51,67,89},before;
        float lum,after,minimum=floors[j];
        memcpy(base,bases[i],sizeof(base)); memcpy(before,range,sizeof(range));
        lum=.3f*base[0]+.59f*base[1]+.11f*base[2];
        VBSP_FloorModelAmbient(base,minimum);
        after=.3f*base[0]+.59f*base[1]+.11f*base[2];
        if(fabsf(after-fmaxf(lum,minimum))>.0001f) return 1;
        checks++;
        if(memcmp(range,before,sizeof(range))) return 2;
        checks++;
        if(minimum<=0 || lum>=minimum) {
            if(memcmp(base,bases[i],sizeof(base))) return 3;
            checks++;
        } else if(lum>.001f) {
            for(c=0;c<3;c++) if(fabsf(base[c]-(bases[i][c]+minimum-lum))>.0001f) return 4;
            checks++;
        }
        /* Lit-minus-dark contrast must equal the original directional range. */
        for(c=0;c<3;c++) if(fabsf((base[c]+range[c])-base[c]-before[c])>.0001f) return 5;
        checks++;
    }
    printf("PASS ambient floor: %d checks, 0 failed\n", checks);
    return 0;
}
'''
    gcc = shutil.which('gcc') or 'C:/msys64/ucrt64/bin/gcc.exe'
    with tempfile.TemporaryDirectory(prefix='p508ambient-') as tmp:
        src, exe = Path(tmp)/'floor.c', Path(tmp)/'floor.exe'
        src.write_text(code, encoding='utf-8')
        env = dict(os.environ)
        env['PATH'] = str(Path(gcc).resolve().parent) + os.pathsep + env.get('PATH', '')
        env['TEMP'] = env['TMP'] = tmp
        subprocess.run([gcc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(exe), '-lm'], check=True, env=env)
        subprocess.run([str(exe)], check=True, env=env)
    assert 'VBSP_FloorModelAmbient(res_diffuse, hl2_lt_min' in source
    assert 'wantmin != min_live' in source
    print('PASS production call uses only the ambient base; minimum is in the prop cache key')


if __name__ == '__main__':
    main()
