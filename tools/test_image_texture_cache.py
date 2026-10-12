#!/usr/bin/env python3
"""Compile the production Image_FindTexture and test its cache identity policy.

Hashing/upload are stubbed; lookup logic and flag/type values come from the engine.
--workdir must be an existing owned scratch directory. No game assets required.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess

PREFIX = r'''
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <stddef.h>
#define NULL_IMAGE ((image_t *)0)
typedef struct image_s {
    unsigned flags;
    const char *ident, *subpath;
    int regsequence;
    struct image_s *next;
} image_t;
static image_t *imagetable;
static int r_regsequence = 42;
static struct { int ival; } r_ignoremapprefixes;
static int Q_strcasecmp(const char *a, const char *b)
{
    while (*a && tolower((unsigned char)*a) == tolower((unsigned char)*b)) { a++; b++; }
    return tolower((unsigned char)*a) - tolower((unsigned char)*b);
}
static image_t *Hash_GetNextInsensitive(image_t **table, const char *name, image_t *prev)
{
    image_t *p = prev ? prev->next : *table;
    for (; p; p = p->next) if (!Q_strcasecmp(name, p->ident)) return p;
    return NULL_IMAGE;
}
static image_t *Hash_GetInsensitive(image_t **table, const char *name)
{
    return Hash_GetNextInsensitive(table, name, NULL_IMAGE);
}
'''
SUFFIX = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)
int main(void)
{
    image_t first = {0,"Smoke",NULL,0,NULL}, second = {0,"smoke",NULL,0,NULL};
    unsigned types[] = {IF_TEXTYPE_2D, IF_TEXTYPE_2D_ARRAY, IF_TEXTYPE_CUBE,
                        IF_TEXTYPE_3D, IF_TEXTYPE_CUBE_ARRAY};
    for (unsigned i=0;i<sizeof(types)/sizeof(types[0]);i++) {
        for (unsigned j=0;j<sizeof(types)/sizeof(types[0]);j++) {
            if (i==j) continue;
            first.flags=types[i]; first.next=NULL_IMAGE; imagetable=&first;
            CHECK(Image_FindTexture("sMoKe",NULL,types[j])==NULL_IMAGE);
            second.flags=types[j]; first.next=&second;
            CHECK(Image_FindTexture("SMOKE",NULL,types[i])==&first);
            CHECK(Image_FindTexture("smoke",NULL,types[j])==&second);
            CHECK(second.regsequence==r_regsequence);
            // ANY is resolved on upload; subsequent previews must reuse it.
            first.next=NULL_IMAGE;
            for (unsigned repeat=0;repeat<10;repeat++)
                CHECK(Image_FindTexture("smoke",NULL,IF_TEXTYPE_ANY)==&first);
        }
    }
    first.flags=IF_TEXTYPE_ANY; first.next=NULL_IMAGE;
    CHECK(Image_FindTexture("smoke",NULL,IF_TEXTYPE_ANY)==&first);
    for (unsigned i=0;i<sizeof(types)/sizeof(types[0]);i++)
        CHECK(Image_FindTexture("smoke",NULL,types[i])==NULL_IMAGE);
    first.flags=IF_TEXTYPE_2D;
    unsigned identity[] = {IF_CLAMP,IF_PALETTIZE,IF_PREMULTIPLYALPHA};
    for (unsigned i=0;i<sizeof(identity)/sizeof(identity[0]);i++) {
        CHECK(Image_FindTexture("smoke",NULL,identity[i])==NULL_IMAGE);
        first.flags=identity[i];
        CHECK(Image_FindTexture("smoke",NULL,identity[i])==&first);
        CHECK(Image_FindTexture("smoke",NULL,0)==NULL_IMAGE);
        first.flags=0;
    }
    first.subpath="map-a";
    CHECK(Image_FindTexture("smoke","MAP-A",0)==&first);
    CHECK(Image_FindTexture("smoke","map-b",0)==NULL_IMAGE);
    CHECK(Image_FindTexture("smoke",NULL,0)==NULL_IMAGE);
    CHECK(Image_FindTexture("smoke","map-b",IF_INEXACT)==&first);
    first.flags=IF_INEXACT;
    CHECK(Image_FindTexture("smoke","map-b",0)==&first);
    first.flags=0; r_ignoremapprefixes.ival=1;
    CHECK(Image_FindTexture("smoke","map-b",0)==&first);
    puts("PASS texture cache: type matrix/order, same-type reuse, ANY lifecycle, identity flags, subpaths");
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
    source = (args.engine / 'engine/client/image.c').read_text(encoding='utf-8')
    start = source.index('image_t *Image_FindTexture(')
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    merged = (args.engine / 'engine/client/merged.h').read_text(encoding='utf-8')
    enum = re.search(r'enum imgtype_e\s*\{(.+?)\}\s*type;', merged, re.S).group(1)
    render = (args.engine / 'engine/client/render.h').read_text(encoding='utf-8')
    flags = ['IF_CLAMP','IF_PALETTIZE','IF_PREMULTIPLYALPHA','IF_INEXACT','IF_TEXTYPEMASK']
    definitions = 'enum imgtype_e {' + enum + '};\n'
    for flag in flags:
        value = re.search(r'\b' + flag + r'\s*=\s*([^,]+),', render).group(1)
        definitions += '#define ' + flag + ' (' + value + ')\n'
    definitions += '\n'.join(re.findall(r'^#define IF_TEXTYPE\w+[^\n]*', render, re.M)) + '\n'
    code, exe = args.workdir / 'image-cache-lookup.c', args.workdir / 'image-cache-lookup.exe'
    code.write_text(PREFIX + definitions + source[start:end] + SUFFIX, encoding='utf-8')
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join((str(Path(args.cc).parent), env['PATH']))
    subprocess.run([args.cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(code), '-o', str(exe)], check=True, env=env)
    subprocess.run([str(exe.resolve())], check=True, env=env)


if __name__ == '__main__':
    main()
