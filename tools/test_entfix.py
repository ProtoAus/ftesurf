#!/usr/bin/env python3
"""Patch 890: the engine's entity-fix applier (gl_model.c Mod_EntFix), compiled out of the engine
source against small shims and driven case by case -- filter, add, modify (replace / delete /
insert), wildcards, the 0x1b output separator, comments, a block that matches nothing, a
malformed file.

  python tools/test_entfix.py [path/to/engine/gl/gl_model.c]

Needs gcc (msys2 ucrt64).  Exits 1 on any failed case.
"""
import os, pathlib, re, subprocess, sys, tempfile

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r'C:\msys64\home\Lex\fteqw\engine\gl\gl_model.c')
GCC = os.environ.get('GCC', r'C:\msys64\ucrt64\bin\gcc.exe')

SHIMS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef int qboolean;
#define true 1
#define false 0
#define MAX_QPATH 64
#define BZ_Realloc realloc
#define BZ_Malloc malloc
#define BZ_Free free
#define Z_Free free
#define Z_StrDup strdup
#define Z_Malloc malloc
#define Q_strncasecmp strncasecmp
#define Q_strcasecmp strcasecmp
#define CON_WARNING "W: "
#define CON_ERROR "E: "
#define Con_Printf printf
typedef struct { const char *name; } model_t;
static struct { int ival; } sv_entfix = {1};
static char *test_fix;
static void COM_FileBase(const char *in, char *out, int len)
{
	const char *s = strrchr(in, '/'), *e;
	s = s ? s + 1 : in;
	e = strrchr(s, '.');
	if (!e) e = s + strlen(s);
	snprintf(out, len, "%.*s", (int)(e - s), s);
}
#define Q_snprintfz snprintf
static char vabuf[256];
static const char *va(const char *f, int n) { snprintf(vabuf, sizeof(vabuf), f, n); return vabuf; }
static char *EF_LoadTrusted(const char *path) { (void)path; return test_fix ? strdup(test_fix) : NULL; }
typedef struct { int unused; } hashfunc_t;
static hashfunc_t hash_sha1;
static unsigned int CalcHashInt(const hashfunc_t *h, const void *data, size_t n)
{	//FNV-1a: the identity cases test which bytes are hashed and the 24-bit fold, not the engine's sha1
	const unsigned char *p = data; unsigned int x = 2166136261u;
	(void)h;
	while (n--) x = (x ^ *p++) * 16777619u;
	return x;
}
'''

MAIN = r'''
static char *slurp(const char *p)
{
	FILE *f = fopen(p, "rb"); long n; char *b;
	if (!f) return NULL;
	fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
	b = malloc(n + 1); fread(b, 1, n, f); b[n] = 0; fclose(f);
	return b;
}
int main(int argc, char **argv)
{
	model_t m = {"maps/testmap.bsp"};
	char *lump = slurp(argv[1]), *out;
	test_fix = slurp(argv[2]);
	unsigned int fixhash = 0;
	out = Mod_EntFix(&m, lump, &fixhash);
	printf("fixhash %u\n=====\n%s", fixhash, out ? out : "(null)\n");
	return 0;
}
'''

def extract(text):
    a = text.index('FTESurf Patch 890: per-map entity fixes')
    a = text.rindex('/*', 0, a)
    b = text.index("//P841's rule for map-load rulesets", a)
    c = text.index('static char *Mod_EntFix(model_t *mod, const char *ents, unsigned int *fixhash)', b)
    d = text.index('\ndone:', c)
    e = text.index('\n}', d) + 2
    return text[a:b] + text[c:e]

LUMP = '''{
"classname" "worldspawn"
}
{
"classname" "trigger_teleport"
"model" "*3"
"target" "seperation1"
"filtername" "t_filter"
}
{
"classname" "trigger_teleport"
"model" "*5"
"target" "SEPERATION1"
}
{
"classname" "trigger_teleport"
"model" "*9"
"target" "fall2"
}
{
"classname" "logic_timer"
"targetname" "spawn_timer"
"OnTimer" "jail\x1bEnable\x1b\x1b0\x1b-1"
"OnTimer" "spawn,Disable,,0,-1"
"OnTimer" "spawn_timer,Disable,,1,-1"
}
{
"classname" "func_brush"
"model" "*13"
"targetname" "''' + 'a' * 40 + '''"
}
'''

CASES = [
    ('modify replace, case-insensitive values, two hits',
     '''// comment
modify:
{
	match:
	{
		"classname" "trigger_teleport"
		"target" "seperation1"
	}
	replace:
	{
		"target" "entfix_start"
	}
}''',
     ['0 removed, 0 added, 2 modified'],
     lambda o: o.count('"target" "entfix_start"') == 2 and '"target" "fall2"' in o),
    ('match needs every pair',
     '''modify:
{
	match: { "classname" "trigger_teleport" "filtername" "t_filter" }
	replace: { "target" "x" }
}''',
     ['1 modified'], lambda o: o.count('"target" "x"') == 1),
    ('filter removes; add appends last',
     '''filter:
{
	"model" "*9"
}
add:
{
	"classname" "info_teleport_destination"
	"targetname" "entfix_start"
	"origin" "1 2 3"
}''',
     ['1 removed, 1 added, 0 modified'],
     lambda o: '"*9"' not in o and o.rstrip().endswith('"origin" "1 2 3"\n}'.rstrip())),
    ('delete by wildcard, the 0x1b separator as a comma; insert',
     '''; semicolon comment
# hash comment
modify:
{
	match: { "targetname" "spawn_timer" }
	delete: { "OnTimer" "/jail,enable*/" }
	delete: { "OnTimer" "/spawn,*/" }
	insert: { "OnTimer" "keep,Trigger,,0,-1" }
}''',
     ['1 modified'],
     lambda o: 'jail' not in o and '"spawn,Disable' not in o and 'spawn_timer,Disable' in o
               and '"OnTimer" "keep,Trigger,,0,-1"' in o),
    ('a block that matches nothing is reported, the rest applies',
     '''modify:
{
	match: { "targetname" "no_such" }
	replace: { "target" "y" }
}
filter:
{
	"model" "*5"
}''',
     ['modify block 1 matched nothing', '1 removed', '1 block(s) matched nothing'],
     lambda o: '"*5"' not in o),
    ('a malformed file is not applied',
     '''modify:
{
	match: { "targetname" "spawn_timer" }
	replace: { "target" "y"
}''',
     ['malformed'], lambda o: o.strip() == '(null)'),
    ('a match block is required',
     '''modify:
{
	replace: { "target" "y" }
}''',
     ['malformed'], lambda o: o.strip() == '(null)'),
    ('a value is exact unless /wrapped/: "*3" is not "*13"',
     '''filter:
{
	"model" "*3"
}''',
     ['1 removed'], lambda o: '"*3"' not in o and '"*13"' in o),
    ('a long value is kept whole',
     '''modify:
{
	match: { "model" "*9" }
	insert: { "message" "''' + 'x' * 12000 + '''" }
}''',
     ['1 modified'], lambda o: ('"message" "' + 'x' * 12000 + '"') in o),
    ('many stars do not blow up',
     '''modify:
{
	match: { "targetname" "/*a*a*a*a*a*a*a*a*a*a*a*a*a*a*a*a*a*a*a*a*b/" }
	replace: { "target" "z" }
}''',
     ['matched nothing'], lambda o: '(null)' not in o),
    ('no fix file, no change',
     None, ['fixhash 0'], lambda o: o.strip() == '(null)'),
    ('identity a',
     '''modify:
{
	match: { "target" "fall2" }
	replace: { "target" "start" }
}''', ['1 modified'], lambda o: True),
    ('identity c: identity a with CRLF',
     '''modify:\r
{\r
	match: { "target" "fall2" }\r
	replace: { "target" "start" }\r
}''', ['1 modified'], lambda o: True),
    ('identity b: a comment more',
     '''// a comment changes the file, so the identity
modify:
{
	match: { "target" "fall2" }
	replace: { "target" "start" }
}''', ['1 modified'], lambda o: True),
]

def main():
    text = SRC.read_text(encoding='latin1').replace('\r\n', '\n')
    code = SHIMS + extract(text) + MAIN
    with tempfile.TemporaryDirectory(prefix='entfix-') as d:
        d = pathlib.Path(d)
        (d / 't.c').write_text(code, encoding='latin1')
        exe = d / 't.exe'
        r = subprocess.run([GCC, '-O1', '-Wall', '-Wno-unused-function', '-o', str(exe), str(d / 't.c')],
                           capture_output=True, text=True, env=dict(os.environ, PATH=os.path.dirname(GCC) + os.pathsep + os.environ['PATH']))
        if r.returncode:
            print(r.stdout + r.stderr)
            return 1
        if r.stderr.strip():
            print('compiler said:\n' + r.stderr)
        (d / 'lump.txt').write_text(LUMP, encoding='latin1', newline='\n')
        fails = 0
        hashes = {}
        for name, fix, want, check in CASES:
            fp = d / 'fix.cfg'
            if fix is None:
                if fp.exists():
                    fp.unlink()
            else:
                fp.write_text(fix, encoding='latin1', newline='\n')
            out = subprocess.run([str(exe), str(d / 'lump.txt'), str(fp)], capture_output=True, text=True, timeout=20,
                                 encoding='latin1', env=dict(os.environ, PATH=os.path.dirname(GCC) + os.pathsep + os.environ['PATH'])).stdout
            log, _, body = out.partition('=====\n')
            hashes[name] = int(log.split('fixhash ')[1].split()[0]) if 'fixhash ' in log else -1
            ok = all(w in log for w in want) and check(body)
            fails += not ok
            print('%s  %s' % ('ok  ' if ok else 'FAIL', name))
            if not ok:
                print('   log: %r\n   out: %r' % (log, body[:400]))
        # The fix's identity (*entfile) is its bytes: 24 bits, set when applied, changed by any byte.
        ha, hb = hashes['identity a'], hashes['identity b: a comment more']
        hc = hashes['identity c: identity a with CRLF']
        ok = 0 < ha <= 0xffffff and 0 < hb <= 0xffffff and ha != hb and hc == ha
        fails += not ok
        print('%s  identity: 24 bits, differs with the bytes, CRLF as LF (%d, %d, %d)'
              % ('ok  ' if ok else 'FAIL', ha, hb, hc))
    print('%d case(s), %d failed' % (len(CASES) + 1, fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
