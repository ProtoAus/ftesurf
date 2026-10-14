#!/usr/bin/env python3
"""Compile exact legacy batch/reload C with controlled stubs (NOT native proof).

Needs --engine-root and a NEW owned --output directory; no install/game writes.
See p690legacyorder.md for scope, predictions, and the still-open native gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fragment(text: str, signature: str) -> str:
    """Extract one complete function, ignoring braces in strings/comments."""
    need(text.count(signature) == 1, 'ambiguous source signature: ' + signature)
    start = text.index(signature)
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]',
                         text[start:], re.DOTALL)
    depth, opened = 0, False
    for token in tokens:
        if token.group() == '{':
            depth += 1
            opened = True
        elif token.group() == '}':
            depth -= 1
            if opened and depth == 0:
                return text[start:start + token.end()] + '\n'
    raise ValueError('unterminated source function: ' + signature)


PRE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef int qboolean;
#define true 1
#define false 0
#define MAX_QPATH 64
__SHADERSORT__
#define MAXRLIGHTMAPS 1
#define MAX_INDICIES 65535
#define SURF_NODRAW 1
#define SURF_PLANEBACK 2
#define SHADER_HASREFLECT 1
#define SHADER_HASREFRACT 2
#define SHADER_HASREFLECTCUBE 4
#define SUF_NONE 0
#define SUR_FORCEFALLBACK 1
#define CON_WARNING ""
#define CON_ERROR ""
#define MLS_LOADED 2
#define mod_brush 0
#define ca_connected 1
#define ca_active 2
#define VectorClear(a) memset(a,0,3*sizeof(float))
#define VectorCopy(a,b) memcpy(b,a,3*sizeof(float))
#define Vector4Copy(a,b) memcpy(b,a,4*sizeof(float))
#define VectorNegate(a,b) do { for(int vi=0;vi<3;vi++) (b)[vi]=-(a)[vi]; } while(0)
#define Vector4Compare(a,b) (!memcmp(a,b,4*sizeof(float)))
typedef float vec4_t[4];
typedef struct shader_s shader_t;
typedef struct { shader_t *s; const char *saveshaderbody; } parsestate_t;
typedef void shader_gen_t(parsestate_t *, const char *);
struct shader_s {
 int sort, uses, flags; unsigned usageflags; char name[MAX_QPATH];
 shader_gen_t *generator; const char *genargs;
 int target, parsed; /* controlled stub-only fields, NOT real layout */
};
typedef struct image_s { int unused; } image_t;
typedef struct texture_s { shader_t *shader; int alternate_anims,anim_total; } texture_t;
typedef struct { texture_t *texture; } texinfo_t;
typedef struct { int numvertexes; } mesh_t;
typedef struct { float normal[3], dist; } plane_t;
typedef struct batch_s {
 struct batch_s *next; shader_t *shader; texture_t *texture;
 int lightmap[1], firstmesh, maxmeshes; void *ent, *fog; image_t *envmap;
 void (*buildmeshes)(void); struct { struct { vec4_t plane; int ebobatch; } bmodel; } user;
} batch_t;
typedef struct {
 texinfo_t *texinfo; int flags, lightmaptexturenums[1]; plane_t *plane;
 image_t *envmap; mesh_t *mesh; void *fog; batch_t *sbatch;
} msurface_t;
typedef struct {
 int type, loadstate, numbatches, nummodelsurfaces, firstmodelsurface, fromgame;
 int memgroup; msurface_t *surfaces; batch_t *batches[SHADER_SORT_COUNT];
 struct { int mergew,mergeh,count,width,height,deluxemapping; } lightmaps;
} model_t;
static model_t models[4], *mod_known=models;
static int mod_numknown, r_worldentity;
static shader_t materials[5], *shader_slots[6], **r_shaders=shader_slots;
static unsigned int r_numshaders;
static batch_t arena[32]; static int allocated;
static struct { int state; } cls;
static struct { int backend; const char *shadernamefmt; } sh_config;
static struct { int ival; } ruleset_allow_shaders={1}, developer={0};
static const char *shader_reload_why="test";
#define TRACE(x) ((void)0)
static qboolean shader_rescan_needed, shader_reload_needed;
static int scans, generic_reloads, parse_calls, generated, scene_clears;
static void Surf_ClearSceneCache(void) { scene_clears++; }
static const char *case_name;
static void check(int ok, const char *what) {
 if(!ok) { fprintf(stderr,"FAIL %s: %s\n",case_name,what); exit(1); }
}
static void *ZG_Malloc(void *group, size_t size) {
 (void)group; check(size==sizeof(batch_t)&&allocated<32,"arena bounds");
 return &arena[allocated++];
}
static shader_t *R_RegisterShader(const char *name, int usage, const char *body) {
 (void)name;(void)usage;(void)body;check(0,"unexpected nodraw stub");return NULL;
}
static void Con_Printf(const char *format,...) { (void)format; }
static double Sys_DoubleTime(void) { return 0; }
static void Shader_ReloadGenerics(void) { generic_reloads++; }
static void Shader_FlushCache(void) { scans++; }
static void Shader_InitCallback(void) {}
static void Shader_InitCallback_Doom3(void) {}
static void COM_EnumerateFiles(const char *path, void (*callback)(void), void *param) {
 (void)path;(void)callback;(void)param;
}
static void Con_DPrintf(const char *format,...) { (void)format; }
static void R2D_ImageColours(float a,float b,float c,float d) { (void)a;(void)b;(void)c;(void)d; }
static qboolean Shader_ParseShader(parsestate_t *ps, const char *name) {
 (void)name;parse_calls++;if(!ps->s->parsed)return false;
 ps->s->sort=ps->s->target;return true;
}
static void generate(parsestate_t *ps, const char *args) {
 (void)args;generated++;ps->s->sort=ps->s->target;
}
static void Q_strncpyz(char *out, const char *in, size_t n) {
 if(n) { snprintf(out,n,"%s",in); }
}
static void Shader_Regenerate(parsestate_t *ps, const char *name) {
 (void)name;ps->s->generator(ps,ps->s->genargs);
}
#define Q_snprintfz snprintf
static void COM_StripExtension(const char *in, char *out, size_t n) { Q_strncpyz(out,in,n); }
#define lmmerge(i) ((i>=0)?i/merge:i)
'''

TESTS = r'''
static texture_t textures[2]; static texinfo_t texinfos[2];
static mesh_t meshes[3]; static msurface_t surfaces[3];
static void reset(const char *name) {
 case_name=name;memset(models,0,sizeof(models));memset(materials,0,sizeof(materials));
 memset(arena,0,sizeof(arena));memset(shader_slots,0,sizeof(shader_slots));
 allocated=0;mod_numknown=4;r_numshaders=5;cls.state=ca_active;sh_config.backend=1;
 scans=generic_reloads=parse_calls=generated=scene_clears=0;shader_rescan_needed=shader_reload_needed=false;
 for(int i=0;i<5;i++) {
  materials[i].uses=1;materials[i].sort=materials[i].target=11;
  materials[i].generator=generate;snprintf(materials[i].name,MAX_QPATH,"mat%d",i);
  r_shaders[i]=&materials[i];
 }
 models[0].type=models[1].type=models[2].type=mod_brush;
 models[0].loadstate=models[1].loadstate=MLS_LOADED;
 models[2].loadstate=1;models[3].type=1;models[3].loadstate=MLS_LOADED;
}
static void build_world(void) {
 model_t *m=&models[0];memset(textures,0,sizeof(textures));memset(surfaces,0,sizeof(surfaces));
 for(int i=0;i<2;i++){textures[i].shader=&materials[i];texinfos[i].texture=&textures[i];}
 for(int i=0;i<3;i++) {
  meshes[i].numvertexes=4;surfaces[i].texinfo=&texinfos[i%2];surfaces[i].mesh=&meshes[i];
  surfaces[i].lightmaptexturenums[0]=-1;
 }
 m->surfaces=surfaces;m->nummodelsurfaces=3;
 check(Mod_Batches_Generate(m)==1,"merge default");
 check(allocated==2,"same red texture reuses batch");
 check(surfaces[0].sbatch==surfaces[2].sbatch&&surfaces[0].sbatch->maxmeshes==2,"red faces merged");
 check(surfaces[1].sbatch->maxmeshes==1,"blue separate");
}
static void order(model_t *m, shader_t *a, shader_t *b, const char *why) {
 batch_t *head=m->batches[11];
 check(head&&head->shader==a&&head->next&&head->next->shader==b&&!head->next->next,why);
}
static void add_cached_model(void) {
 batch_t *a=ZG_Malloc(NULL,sizeof(batch_t)), *b=ZG_Malloc(NULL,sizeof(batch_t));
 a->shader=&materials[0];b->shader=&materials[1];a->next=b;models[1].batches[11]=a;
}
static void reload(void) { shader_rescan_needed=shader_reload_needed=true;Shader_DoReload(); }
int main(void) {
 reset("initial-head-insertion");build_world();order(&models[0],&materials[1],&materials[0],"blue/red");
 puts("PASS initial-head-insertion");
 reset("global-rebucket");build_world();add_cached_model();
 batch_t held[4]={{0}};held[0].shader=&materials[2];held[1].shader=&materials[2];
 held[3].shader=&materials[4];held[1].next=&held[3];
 models[2].batches[11]=&held[0];models[3].batches[11]=&held[1];models[0].batches[3]=&held[2];
 Mod_ResortShaders();order(&models[0],&materials[0],&materials[1],"unchanged world reverses");
 order(&models[1],&materials[1],&materials[0],"unrelated loaded brush reverses");
 check(models[2].batches[11]==&held[0],"loading model excluded");
 order(&models[3],&materials[4],&materials[2],"loadstate-only eligibility (no model-type guard)");
 check(models[0].batches[3]==&held[2]&&scene_clears==1,"null bucket and cache invalidation");
 Mod_ResortShaders();order(&models[0],&materials[1],&materials[0],"second reversal returns");
 check(scene_clears==2,"cache invalidation each resort");
 puts("PASS global-rebucket");
 reset("bucket-migration");build_world();materials[1].sort=12;Mod_ResortShaders();
 check(models[0].batches[12]==surfaces[1].sbatch&&!models[0].batches[12]->next,"changed band moves");
 check(models[0].batches[11]==surfaces[0].sbatch&&!models[0].batches[11]->next,"other band remains");
 puts("PASS bucket-migration");
 reset("connecting-defer");build_world();cls.state=ca_connected;materials[2].sort=5;reload();
 order(&models[0],&materials[1],&materials[0],"deferred world");
 check(shader_rescan_needed&&shader_reload_needed&&!scans&&!generic_reloads&&!parse_calls,"defer all work");
 cls.state=ca_active;Shader_DoReload();order(&models[0],&materials[0],&materials[1],"active consumes deferred change");
 check(!shader_rescan_needed&&!shader_reload_needed&&scans==1&&generic_reloads==1,"active consumes flags");
 puts("PASS connecting-defer");
 reset("equal-sort-reload");build_world();reload();
 order(&models[0],&materials[1],&materials[0],"equal sort must not rebucket");
 check(scans==1&&generic_reloads==1&&generated==5,"stubbed reload acted");
 puts("PASS equal-sort-reload");
 reset("unrelated-generated-change");build_world();add_cached_model();materials[2].sort=5;reload();
 order(&models[0],&materials[0],&materials[1],"unrelated shader changes world order");
 order(&models[1],&materials[1],&materials[0],"unrelated cached brush also reverses");
 check(materials[0].sort==11&&materials[1].sort==11&&materials[2].sort==11,"same world final bands");
 puts("PASS unrelated-generated-change");
 reset("parsed-sortcheck");build_world();materials[2].generator=NULL;
 materials[2].parsed=1;materials[2].sort=5;reload();
 check(parse_calls==5&&generated==4,"parsed route acted");
 order(&models[0],&materials[0],&materials[1],"parsed route must reach sortcheck");
 puts("PASS parsed-sortcheck");
 reset("unused-slot");build_world();materials[2].sort=5;materials[2].uses=0;r_shaders[3]=NULL;reload();
 check(materials[2].sort==5&&generated==3,"unused/null slots untouched");
 order(&models[0],&materials[1],&materials[0],"unused shader must not trigger resort");
 puts("PASS unused-slot");
 reset("world-after-rescan");materials[2].sort=5;reload();build_world();
 order(&models[0],&materials[1],&materials[0],"world built after unrelated change");
 check(materials[2].sort==11,"same unrelated final band");puts("PASS world-after-rescan");
 reset("world-not-published");build_world();models[0].loadstate=1;materials[2].sort=5;reload();
 order(&models[0],&materials[1],&materials[0],"built loading world skipped by resort");
 models[0].loadstate=MLS_LOADED;shader_reload_needed=true;Shader_DoReload();
 order(&models[0],&materials[1],&materials[0],"publication alone not a new sort change");
 check(materials[2].sort==11,"same final materials despite skipped resort");puts("PASS world-not-published");
 reset("rescan-only");build_world();shader_rescan_needed=true;Shader_DoReload();
 check(scans==1&&!shader_reload_needed,"rescan-only schedules reload and consumes");
 order(&models[0],&materials[1],&materials[0],"same-sort scan no reorder");puts("PASS rescan-only");
 return 0;
}
'''


def run(engine: Path, output: Path, cc: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    model_path = engine / 'engine/gl/gl_model.c'
    shader_path = engine / 'engine/gl/gl_shader.c'
    header_path = engine / 'engine/gl/gl_model.h'
    model, shader = model_path.read_text(), shader_path.read_text()
    shader_enum = fragment(header_path.read_text(), 'typedef enum {\n\tSHADER_SORT_NONE,').rstrip() + ' shadersort_t;\n'
    pre = PRE.replace('__SHADERSORT__', shader_enum)
    generate_c = fragment(model, 'static int Mod_Batches_Generate(model_t *mod)\n')
    resort = fragment(model, 'void Mod_ResortShaders(void)\n')
    reload_c = fragment(shader, 'void Shader_DoReload(void)\n')
    code = pre + generate_c + resort + reload_c + TESTS
    mutations = [
        ('missing-rebucket', 'Mod_ResortShaders();', '(void)resort;', 'connecting-defer', True),
        ('unconditional-reload-resort', 'if (resort)\n\t{\n\t\tMod_ResortShaders();',
         '(void)resort; if (true)\n\t{\n\t\tMod_ResortShaders();', 'equal-sort-reload', False),
        ('lost-connecting-defer', 'if (cls.state && cls.state < ca_active)', 'if (false)', 'connecting-defer', False),
        ('lost-parsed-sortcheck', 'if (Shader_ParseShader(&ps, cleanname))\n\t\t\t\tgoto sortcheck;',
         'if (Shader_ParseShader(&ps, cleanname))\n\t\t\t\tcontinue;', 'parsed-sortcheck', False),
        ('reload-unused-slot', 'if (!s || !s->uses)', 'if (!s)', 'unused-slot', False),
        ('incomplete-bucket-drain', 'while((b=oldlists[j]))', 'if((b=oldlists[j]))', 'global-rebucket', False),
    ]
    variants = [('production-fragments', code, None)]
    for name, old, new, case, only_reload in mutations:
        target = reload_c if only_reload else code
        need(target.count(old) == 1, 'ambiguous mutation: ' + name)
        mutated = (pre + generate_c + resort + reload_c.replace(old, new) + TESTS
                   if only_reload else code.replace(old, new))
        variants.append((name, mutated, case))
    results = []
    report = {'schema': 1, 'scope': 'exact C with controlled stubs; NOT native registration, pixels or scheduler proof',
              'engine_root': str(engine.resolve()), 'compiler': cc,
              'source_sha256': {str(p.relative_to(engine)): sha(p.read_bytes()) for p in (model_path, shader_path, header_path)},
              'fragment_sha256': {'shadersort_t': sha(shader_enum.encode()), 'Mod_Batches_Generate': sha(generate_c.encode()),
                                  'Mod_ResortShaders': sha(resort.encode()), 'Shader_DoReload': sha(reload_c.encode())},
              'results': results}
    for name, c, case in variants:
        for opt in ('-O0', '-O2'):
            base = output / (name + opt)
            source, binary = base.with_suffix('.c'), base.with_suffix('.exe')
            source.write_text(c, encoding='utf-8')
            command = [cc, '-std=c99', '-Wall', '-Wextra', '-Werror', opt, str(source), '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=60)
            base.with_suffix('.build.txt').write_text(json.dumps(command) + '\n' + build.stdout + build.stderr)
            need(build.returncode == 0, f'compile failed (NOT acting mutant): {name} {opt}')
            test = subprocess.run([str(binary.resolve())], capture_output=True, text=True, timeout=10)
            base.with_suffix('.run.txt').write_text(test.stdout + test.stderr)
            need(test.returncode == (1 if case else 0), f'wrong exit: {name} {opt}')
            if case:
                need(('FAIL ' + case + ':') in test.stderr, 'mutant wrong predicate: ' + name)
            else:
                cases = ['initial-head-insertion', 'global-rebucket', 'bucket-migration', 'connecting-defer',
                         'equal-sort-reload', 'unrelated-generated-change', 'parsed-sortcheck', 'unused-slot',
                         'world-after-rescan', 'world-not-published', 'rescan-only']
                need(test.stdout.splitlines() == ['PASS ' + label for label in cases] and not test.stderr,
                     'missing production cases')
            results.append({'variant': name, 'optimization': opt, 'exit': test.returncode,
                            'acting_case': case, 'c_sha256': sha(c.encode())})
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='NEW owned artifact directory')
    parser.add_argument('--cc', required=True, help='C compiler executable; no shell expansion')
    args = parser.parse_args()
    try:
        report = run(args.engine_root, args.output, args.cc)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f'Legacy order test failed: {exc}\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
