"""Execute FTE's actual map/clampmap parser functions with texture-I/O stubs.
P1332: parser slot control + source-bound colour/timing checks, NOT gameplay.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def native_function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]


def expression(source, prefix):
    line = next(line.strip() for line in source.splitlines() if line.strip().startswith(prefix))
    return line.split('=', 1)[1].split(';', 1)[0].strip()


def arithmetic(expression, noise):
    expression = re.sub(r'Weather_Noise\([^)]*\)', str(noise), expression)
    expression = expression.replace('wx_flash', '0').replace('time', '0')
    assert re.fullmatch(r'[0-9.eE+*/() \-]+', expression), expression
    return eval(expression, {'__builtins__': {}}, {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--gcc', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    native = (args.engine / 'engine/gl/gl_shader.c').read_text(encoding='utf-8')
    backend = (args.engine / 'engine/gl/gl_backend.c').read_text(encoding='utf-8')
    snippets = '\n'.join(native_function(native, signature) for signature in [
        'shaderpass_t *Shaderpass_DefineMap(', 'static void Shaderpass_Map (',
        'static void Shaderpass_ClampMap ('])
    # The only stubs are texture loading/tokenization, unrelated to slot selection.
    header = r'''
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef int qboolean;
#define true 1
#define false 0
#define SHADER_PASS_MAX 8
#define SHADER_TMU_MAX 8
#define CON_WARNING ""
#define TC_GEN_UNSPECIFIED 0
#define TC_GEN_BASE 1
#define T_GEN_SINGLEMAP 1
#define IF_CLAMP 1
#define IF_TEXTYPEMASK 0
#define IF_TEXTYPE_2D 0
#define TEXVALID(x) ((x)!=0)
#define Con_DPrintf(...) ((void)0)
#define stricmp _stricmp
#define Q_strncpyz(d,s,n) snprintf(d,n,"%s",s)
static int r_nulltex=0, missing_texture=-1;
typedef struct {void *prog;int numMergedPasses,anim_frames[8],tcgen,texgen;} shaderpass_t;
typedef struct {char mapname[128];} defaults_t;
typedef struct {char name[128];int numpasses;shaderpass_t passes[8];defaults_t *defaulttextures;} shader_t;
typedef struct {shader_t *s;shaderpass_t *pass;int droppass;} parsestate_t;
static char *Shader_ParseSensString(const char **p){return (char*)*p;}
static int Shader_SetImageFlags(parsestate_t *p,shaderpass_t *s,char **n,int f){return f;}
static int Shaderpass_MapGen(parsestate_t *p,shaderpass_t *s,char *n){return 0;}
static int Shader_FindImage(parsestate_t *p,char *n,int f){return strstr(n,"roof")?7:11;}
'''
    footer = r'''
int main(void){
 defaults_t defs={{0}};shader_t s={0};parsestate_t p={&s,&s.passes[0],0};
 const char *roof="roof",*snow="snow";int oldslots,oldroof,oldsnow;
 s.defaulttextures=&defs;s.numpasses=1;p.pass->prog=(void*)1;
 Shaderpass_ClampMap(&p,&roof);Shaderpass_Map(&p,&snow);
 oldslots=p.pass->numMergedPasses;oldroof=s.passes[0].anim_frames[0];oldsnow=s.passes[1].anim_frames[0];
 if(oldslots!=1||oldroof!=11||oldsnow!=0)return 1;
 memset(s.passes,0,sizeof(s.passes));s.numpasses=1;p.pass->prog=(void*)1;
 Shaderpass_Map(&p,&roof);Shaderpass_Map(&p,&snow);
 if(p.pass->numMergedPasses!=2||s.passes[0].anim_frames[0]!=7||s.passes[1].anim_frames[0]!=11)return 2;
 printf("{\"old_slots\":%d,\"old_slot1_unbound\":true,\"fixed_slots\":2,\"roof0_snow1\":true}\n",oldslots);
 return 0;
}
'''
    args.out.mkdir(parents=True, exist_ok=True)
    cfile = args.out / 'actual-native-sampler-control.c'
    exe = args.out / 'actual-native-sampler-control.exe'
    cfile.write_text(header + snippets + footer)
    env = dict(os.environ, PATH=str(args.gcc.parent) + os.pathsep + os.environ['PATH'])
    subprocess.run([str(args.gcc), '-std=c99', '-O2', str(cfile), '-o', str(exe)], env=env, check=True)
    sampler = json.loads(subprocess.check_output([str(exe)], env=env, text=True))
    winter = (ROOT / 'src/client/cl_winter.qc').read_text()
    surface = winter.split(' Winter_Surface =', 1)[1].split('void() Winter_Load', 1)[0]
    assert '#usemods#' in surface and 'rgbgen exactvertex' in surface and 'alphagen vertex' in surface
    definition = surface.split('definition = sprintf', 1)[1].split('e = spawn()', 1)[0]
    assert 'clampmap ' not in definition and 'map $clamp:$nosrgb:$nearest:' in definition
    assert definition.index('gfx/snowmask/') < definition.index('map %s')
    assert 'ftesurf_colin_snow_v4_' in surface and 'EF_FULLBRIGHT' not in surface
    assert 'prog->calcgens = false;' in native and '"usemods", 7))\n\t\t\tprog->calcgens = true;' in native
    binding = backend.split('shaderstate.pendingcolourflatvalid = false;', 1)[1]
    assert binding.index('if (p->calcgens)') < binding.index('GenerateColourMods(pass);') < binding.index('BE_Program_Set_Attributes(')
    assert 'pass->rgbgen == RGB_GEN_VERTEX_EXACT) && pass->alphagen == ALPHA_GEN_VERTEX' in backend
    weather = (ROOT / 'src/client/cl_weather.qc').read_text()
    old = subprocess.check_output(['git', '-C', str(ROOT), 'show', '446fe4ee:src/client/cl_weather.qc'], text=True)
    for prefix in ['duration = ', 'wx_nextflash = wx_flash + ', 'pulse = bound']:
        # Pulse uses a bound(), so verify its proportional denominator separately.
        if prefix.startswith('pulse'):
            assert '(wx_flash - time) / 0.04' in weather and '(wx_flash - time) / 0.12' in old
            continue
        for noise in [0, .1, .5, .999999]:
            assert abs(3 * arithmetic(expression(weather, prefix), noise) - arithmetic(expression(old, prefix), noise)) < 1e-10
    assert expression(weather, 'wx_thunderat = wx_flash + ') == expression(old, 'wx_thunderat = wx_flash + ')
    assert '3 + floor(Weather_Noise(time + wx_burstid * 13) * 4)' in weather
    report = {'sampler_actual_C': sampler, 'colour_native_source_gate': True,
              'pulse_gap_fade_3x_same_brightness': True, 'thunder_delay_and_3to6_strokes_unchanged': True,
              'native_parser_snippets_sha256': hashlib.sha256(snippets.encode()).hexdigest(),
              'scope': 'actual native parser functions with image-I/O stubs; colour/timing source controls; NOT native game pixels/clock/FPS'}
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
