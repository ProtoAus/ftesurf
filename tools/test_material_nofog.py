#!/usr/bin/env python3
"""Compile actual fog gates + narrow VMT policy statements; not a render test.

Requires an explicit fresh output directory under the caller's owned workspace.
No game, renderer, install, service or player data is opened by the C fixtures.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


GL = "engine/gl/gl_backend.c"
VMT = "plugins/hl2/mat_vmt.c"
SHADER = "engine/gl/gl_shader.c"
BASELINE = "3a7a48a833a45961b76a97895e18469d865942a0"


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n}", start) + 2]


def statements(backend, vmt):
    start = backend.index("\tif (r_refdef.globalfog.density && !shaderstate.force2d")
    perm = backend[start:backend.index("perm |= PERMUTATION_FOG;", start) + len("perm |= PERMUTATION_FOG;")]
    start = vmt.index('else if (!Q_strcasecmp(key, "$nofog"))')
    assignment = vmt[start:].splitlines()[1].strip()
    start = vmt.rindex("\tif (st->wireframe)")
    emit = vmt[start:vmt.index("\n\tif (*st->fullbrightmap)", start)]
    assert "st->nofog = 1;" in vmt[vmt.index('if (!Q_strcasecmp(st->type, "Wireframe")'):][:350]
    return perm, assignment, emit


C = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int qboolean;
enum { false, true, SHADER_SKY=8, PERMUTATION_FOG=32,
       GL_FOG_COLOR, GL_FOG_MODE, GL_LINEAR, GL_FOG_START, GL_FOG_END,
       GL_EXP2, GL_EXP, GL_FOG_DENSITY, GL_FOG };
typedef struct { int ival; } cvar_t;
typedef struct { void *prog; unsigned flags; qboolean materialnofog; } shader_t;
typedef struct { shader_t *s; } parsestate_t;
static shader_t material;
static struct { int force2d; shader_t *curshader; } shaderstate;
static struct { struct { float density, alpha, depthbias, colour[3]; } globalfog; } r_refdef;
cvar_t r_fog_progless, r_fog_linear, r_fog_exp2;
static int calls, enabled, checks;
#define VectorCopy(a,b) memcpy((b),(a),3*sizeof(float))
static void Con_DPrintf(const char *fmt, ...) { (void)fmt; }
static void fogi(int k, int v) { (void)k; (void)v; calls++; }
static void fogf(int k, float v) { (void)k; (void)v; calls++; }
static void fogfv(int k, const float *v) { assert(k==GL_FOG_COLOR && v[3]==1); calls++; }
static void enable(int k) { assert(k==GL_FOG); enabled=1; calls++; }
static void disable(int k) { assert(k==GL_FOG && enabled); enabled=0; }
static void (*qglFogi)(int,int)=fogi;
static void (*qglFogf)(int,float)=fogf;
static void (*qglFogfv)(int,const float *)=fogfv;
static void (*qglEnable)(int)=enable;
static void (*qglDisable)(int)=disable;
@FOG_BEGIN@
@FOG_END@
static int permutation(void) {
	int perm=0;
@PERM@
	return perm;
}
#if SUBJECT
@SETTER@
#endif
static void reset(void) {
    memset(&material,0,sizeof(material));
    memset(&r_refdef,0,sizeof(r_refdef));
    shaderstate.force2d=0; shaderstate.curshader=&material;
    r_refdef.globalfog.density=128; r_refdef.globalfog.alpha=1;
    r_fog_progless.ival=1; r_fog_linear.ival=0; r_fog_exp2.ival=0;
    calls=enabled=0; qglFogi=fogi; qglFogf=fogf; qglFogfv=fogfv;
}
static void check(int expected) {
    int got=BE_ProglessFogBegin(); assert(got==expected);
    assert((calls>0)==expected && enabled==expected);
    BE_ProglessFogEnd(got); assert(!enabled); checks++;
}
static void Q_strlcatfz(char *dst, size_t *offset, size_t cap, const char *fmt, ...) {
    va_list ap; int n; va_start(ap,fmt); n=vsnprintf(dst+*offset,cap-*offset,fmt,ap); va_end(ap);
    assert(n>=0 && (size_t)n<cap-*offset); *offset+=(size_t)n;
}
static int emit_policy(const char *value, int forced_wireframe) {
    struct { int nofog, wireframe; } state={0}, *st=&state;
    char script[128]={0}; size_t offset=0;
    @ASSIGNMENT@
    if (forced_wireframe) { st->nofog=1; st->wireframe=1; }
    @EMIT@
    assert((strstr(script,"fte_wireframe")!=NULL)==forced_wireframe);
    return strstr(script,"fte_materialnofog")!=NULL;
}
int main(void) {
    int linear, exp2;
    for (linear=0;linear<2;linear++) for (exp2=0;exp2<2;exp2++) {
        reset(); r_fog_linear.ival=linear; r_fog_exp2.ival=exp2; check(1);
        assert(permutation()==PERMUTATION_FOG); checks++;
        material.materialnofog=1; calls=0; check(!SUBJECT);
        assert(permutation()==(SUBJECT?0:PERMUTATION_FOG)); checks++;
    }
    reset(); shaderstate.force2d=1; check(0); assert(!permutation()); checks++;
    reset(); material.prog=&material; check(0);
    reset(); material.flags=SHADER_SKY; check(0);
    reset(); r_refdef.globalfog.density=0; check(0); assert(!permutation()); checks++;
    reset(); r_fog_progless.ival=0; check(0);
    reset(); qglFogi=NULL; check(0);
    reset(); qglFogf=NULL; check(0);
    reset(); qglFogfv=NULL; check(0);
    reset(); r_refdef.globalfog.alpha=0.5f; check(0);
    reset(); r_refdef.globalfog.depthbias=1; check(0);
    reset(); r_fog_linear.ival=1; r_refdef.globalfog.depthbias=1; check(1);
#if SUBJECT
    { parsestate_t ps={&material}; Shader_MaterialNoFog(&ps,NULL); assert(material.materialnofog); checks++; }
#endif
    assert(emit_policy("0",0)==0); checks++;
    assert(emit_policy("1",0)==SUBJECT); checks++;
    assert(emit_policy("1",1)==SUBJECT); checks++;
    printf("%s PASS checks=%d ordinary-fog-acted authored-nofog=%s\n",
           SUBJECT?"subject":"baseline",checks,SUBJECT?"refused":"incorrectly-fogged");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--cc", default=shutil.which("gcc") or "gcc")
    args = parser.parse_args()
    engine = args.engine.resolve()
    out = args.out.resolve()
    if out.exists() or not out.parent.is_dir():
        parser.error("--out must be fresh, with an existing owned parent")
    subject = {p: (engine / p).read_text(encoding="utf-8") for p in (GL, VMT, SHADER)}
    baseline = {p: subprocess.check_output(["git", "-C", str(engine), "show", f"{args.baseline}:{p}"], text=True, encoding="utf-8") for p in (GL, VMT)}
    header = (engine / "engine/gl/shader.h").read_text(encoding="utf-8")
    assert header.index("qboolean materialnofog;") > header.index("qboolean reflectnoents;")
    reset = function(subject[SHADER], "static void Shader_Reset(parsestate_t *ps)")
    assert "memset(s, 0, sizeof(*s));" in reset
    assert '{"materialnofog",' in subject[SHADER] and 'Shader_MaterialNoFog' in subject[SHADER]
    assert '{"nofog",\t\t\t\tNULL,' in subject[SHADER], "legacy ignored directive changed"
    out.mkdir()
    compiler = Path(shutil.which(args.cc) or args.cc).resolve()
    env = os.environ.copy()
    env["PATH"] = str(compiler.parent) + os.pathsep + env["PATH"]
    env["TMP"] = env["TEMP"] = str(out)
    for name, sources, is_subject in (("baseline", baseline, 0), ("subject", subject, 1)):
        perm, assignment, emit = statements(sources[GL], sources[VMT])
        values = {"FOG_BEGIN": function(sources[GL], "static qboolean BE_ProglessFogBegin(void)"),
                  "FOG_END": function(sources[GL], "static void BE_ProglessFogEnd(qboolean fogging)"),
                  "PERM": perm, "ASSIGNMENT": assignment, "EMIT": emit,
                  "SETTER": function(subject[SHADER], "static void Shader_MaterialNoFog") if is_subject else ""}
        code = C
        for key, value in values.items():
            code = code.replace(f"@{key}@", value)
        assert "@" not in code
        src = out / f"{name}.c"
        exe = out / (name + (".exe" if os.name == "nt" else ""))
        src.write_text(code, encoding="utf-8")
        command = [str(compiler), "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", f"-DSUBJECT={is_subject}", str(src), "-o", str(exe)]
        result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8")
        (out / f"{name}-compile.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{name} compile failed rc={result.returncode}; retained {out / (name+'-compile.log')}")
        result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, encoding="utf-8")
        (out / f"{name}-run.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        result.check_returncode()
        print(result.stdout.strip())
    print("Source contracts PASS; visual/real-window/material-reload acceptance remains separate.")


if __name__ == "__main__":
    main()
