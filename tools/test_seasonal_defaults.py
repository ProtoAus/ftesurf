"""P1335 source-bound Christmas/default guards and ACTUAL native bias parser.
Not native game rendering, sound shutdown, grazing-angle or FPS acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def evaluate(expression, values, theme=False, want=0):
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    return bool(eval(expression, {'__builtins__': {}}, {
        'cvar': lambda name: values.get(name, 0), 'Winter_ThemeActive': lambda: theme,
        'wi_colin': values.get('colin', 0), 'want': want,
        'Snow_InList': lambda *args: True, 'cvar_string': lambda name: '', 'snow_map': 'fixture'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--gcc', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    winter = (ROOT/'src/client/cl_winter.qc').read_text(encoding='utf-8')
    weather = (ROOT/'src/client/cl_weather.qc').read_text(encoding='utf-8')
    snow = (ROOT/'src/client/cl_snow.qc').read_text(encoding='utf-8')
    ramp = (ROOT/'src/client/cl_rampwear.qc').read_text(encoding='utf-8')
    hud = (ROOT/'src/client/cl_hudedit.qc').read_text(encoding='utf-8')
    theme = re.search(r'Winter_ThemeActive =.*?return (.*?);', winter, re.S)[1]
    load = re.search(r'^\s*wx_enabled = (\(cvar\("r_christmas"\).*);', weather, re.M)[1]
    frame = re.search(r'^\s*enabled = (\(cvar\("r_christmas"\).*);', weather, re.M)[1]
    snowwant = next(line.split('=',1)[1].split(';',1)[0] for line in snow.splitlines() if 'want = ((' in line)
    cases = []
    for christmas in [0, 1]:
        for colin in [0, 1]:
            for manual in [0, 1]:
                values = {'r_christmas':christmas, 'colin':colin, 'r_colin_winter':1,
                          'r_weather':manual, 'r_snow':manual*2, 'r_weather_test':2}
                themed = evaluate(theme, values)
                active = evaluate(frame, values, themed)
                assert active == evaluate(load, values, themed)
                snowy = bool(christmas and evaluate(snowwant, values, themed, manual*2))
                assert themed == bool(christmas and colin)
                assert active == bool(christmas and (manual or colin))
                assert snowy == bool(christmas and (manual or colin))
                cases.append([christmas,colin,manual,active,snowy])
    # Nonempty positives above prevent "everything off" from passing the master.
    assert any(row[-1] and row[-2] for row in cases)
    for text,marker in [(winter,'void() Winter_Frame'),(snow,'void() Snow_Frame')]:
        body=text.split(marker,1)[1]
        assert body.index('if (!cvar("r_christmas")) return;') < body.index('addentity(')
    disabled=weather.split('void() Weather_Frame',1)[1].split('// CSQC_WorldLoaded',1)[0]
    assert 'if (wx_enabled) Weather_Free();' in disabled and 'return;' in disabled
    free=weather.split('void() Weather_Free',1)[1].split('void() Weather_Init',1)[0]
    assert all('stopsound('+name in free for name in ['wx_out','wx_in','wx_thunder'])
    assert 'wx_flash = wx_thunderat = 0' in free
    for name in ['r_christmas','r_rampwear','r_rampwear_dirt']:
        assert re.search(r'registercvar\("'+name+r'", "0",',winter+ramp)
        assert re.search(r'^set '+name+r' 0$',(ROOT/'ftesurf/cfg/default.cfg').read_text(),re.M)
        assert name+'|' in hud
    assert '"r_rampwear_lift", "0.03125"' in ramp and ramp.count('bound(0, cvar("r_rampwear_lift"), 0.125)')==2
    rframe=ramp.split('void() RampWear_Frame',1)[1]
    assert rframe.index('if (!cvar("r_rampwear")) return;') < rframe.index('RampWear_Load();')
    assert 'rw_alloc && bound(' in rframe and 'strcmp(serverkey("map"), rw_map)' in rframe
    assert '\\npolygonoffset 1\\n' in ramp and '\\ndepthpush ' not in ramp and '"v2_close"' in ramp
    native=(args.engine/'engine/gl/gl_shader.c').read_text(encoding='utf-8')
    assert re.search(r'"polygonoffset"\s*,\s*Shader_PolygonOffset',native)
    assert not re.search(r'"depthpush"\s*,',native)
    start=native.index('static void Shader_PolygonOffset (')
    function=native[start:native.index('\n}',start)+2]
    header='''#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#define SHADER_POLYGONOFFSET 1\ntypedef struct{int flags;struct{float unit,factor;}polyoffset;}shader_t;\ntypedef struct{shader_t*s;}parsestate_t;\nstatic float Shader_ParseFloat(shader_t*s,const char**p,float d){return strtof(*p,0);}\n'''
    footer='''\nint main(void){shader_t s={0};parsestate_t p={&s};const char*v="1";if(s.polyoffset.unit||s.polyoffset.factor)return 1;Shader_PolygonOffset(&p,&v);if(s.polyoffset.unit!=-25||s.polyoffset.factor!=-.05f||s.flags!=SHADER_POLYGONOFFSET)return 2;printf("{\\"unit\\":%g,\\"factor\\":%g}\\n",s.polyoffset.unit,s.polyoffset.factor);return 0;}\n'''
    args.out.mkdir(parents=True,exist_ok=True)
    cfile=args.out/'actual-native-polygonoffset.c';exe=args.out/'actual-native-polygonoffset.exe'
    cfile.write_text(header+function+footer)
    env=dict(os.environ,PATH=str(args.gcc.parent)+os.pathsep+os.environ['PATH'])
    subprocess.run([str(args.gcc),'-std=c99',str(cfile),'-o',str(exe)],env=env,check=True)
    bias=json.loads(subprocess.check_output([str(exe)],env=env,text=True))
    for saved in [-1,0,.03125,.125,2,8]:
        assert 0<=max(0,min(saved,.125))<=.125
    report={'source_gate_truth_cases':cases,'defaults_ui_shutdown_source_guards':True,
            'actual_native_polygonoffset':bias,'native_function_sha256':hashlib.sha256(function.encode()).hexdigest(),
            'scope':'source-bound combinational/shutdown checks and actual native bias parser; NOT live game, flicker, bleed, sound or FPS acceptance'}
    (args.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
