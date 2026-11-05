"""P1319: production snow GLSL pixels + real IQM/front-face and PCM controls.
Uses the existing small hidden WGL helper, NOT a game/placement/FPS acceptance.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave
import numpy as np
from PIL import Image
from test_soundsky_sky_pixels import GL
UINT=C.c_uint
FLOAT=C.c_float

ROOT=Path(__file__).resolve().parents[1]

def mesh(path):
    data=path.read_bytes();h=struct.unpack_from('<27I',data,16);arrays={}
    for i in range(h[7]):
        kind,flags,fmt,size,off=struct.unpack_from('<5I',data,h[9]+i*20)
        if kind not in (0,2):continue
        assert fmt==7 and size==3
        arrays[kind]=np.frombuffer(data,dtype='<f4',count=h[8]*size,offset=off).reshape(-1,size)
    t=np.frombuffer(data,dtype='<u4',count=h[10]*3,offset=h[11]).reshape(-1,3)
    p=arrays[0][t];n=arrays[2][t].sum(1)
    facing=np.einsum('ij,ij->i',np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),n)
    text=data[h[4]:h[4]+h[3]];material=struct.unpack_from('<6I',data,h[6])[1]
    return facing,text[material:text.index(bytes([0]),material)].decode()

def sources(path,grass):
    body='\n'.join(l for l in path.read_text().splitlines() if not l.startswith('!!') and not l.startswith('#include'))
    defs='#version 110\n#define ZBASE -100.0\n#define ZRANGE 200.0\n'+('#define GRASS 1\n' if grass else '')
    common='uniform vec4 e_colourident,e_colour;uniform vec3 e_eyepos;uniform float e_time;\n'
    vs=defs+'#define VERTEX_SHADER\n#define v_position gl_Vertex\n#define v_texcoord gl_MultiTexCoord0.st\n#define v_normal gl_Normal\n#define v_colour gl_Color\n#define ftetransform ftransform\n'+common+body
    fs=defs+'#define FRAGMENT_SHADER\nuniform sampler2D s_roof,s_grain,s_snow,s_bolt,s_cloud;\n'+common+body
    return vs,fs

def program(g,path,grass):
    vs,fs=sources(path,grass);v=g.shader(0x8B31,vs);f=g.shader(0x8B30,fs)
    create=g.fn('glCreateProgram',UINT);attach=g.fn('glAttachShader',None,UINT,UINT)
    p=create();attach(p,v);attach(p,f);g.fn('glLinkProgram',None,UINT)(p)
    ok=C.c_int();g.fn('glGetProgramiv',None,UINT,UINT,C.POINTER(C.c_int))(p,0x8B82,C.byref(ok));assert ok.value,'production program link failed'
    g.fn('glUseProgram',None,UINT)(p)
    loc=g.fn('glGetUniformLocation',C.c_int,UINT,C.c_char_p)
    for name,index in [('s_roof',0),('s_grain',1),('s_snow',1),('s_bolt',0),('s_cloud',1)]:g.fn('glUniform1i',None,C.c_int,C.c_int)(loc(p,name.encode()),index)
    g.fn('glUniform4f',None,C.c_int,FLOAT,FLOAT,FLOAT,FLOAT)(loc(p,b'e_colourident'),1,1,1,1)
    g.fn('glUniform4f',None,C.c_int,FLOAT,FLOAT,FLOAT,FLOAT)(loc(p,b'e_colour'),1,1,1,1)
    g.fn('glDeleteShader',None,UINT)(v);g.fn('glDeleteShader',None,UINT)(f)
    return p

def render(g,p,roof,cw=True,light=1.0,albedo=.5):
    n=32;g.fn('glViewport',None,C.c_int,C.c_int,C.c_int,C.c_int)(0,0,n,n)
    g.fn('glClearColor',None,FLOAT,FLOAT,FLOAT,FLOAT)(0,0,0,0);g.fn('glClear',None,UINT)(0x4000)
    g.fn('glUseProgram',None,UINT)(p);textures=(UINT*2)()
    g.fn('glGenTextures',None,C.c_int,C.c_void_p)(2,textures)
    for unit,value in [(0,[roof,0,0,1]),(1,[albedo,albedo,albedo,1])]:
        g.fn('glActiveTexture',None,UINT)(0x84C0+unit)
        g.fn('glBindTexture',None,UINT,UINT)(0x0DE1,textures[unit])
        for prop in [0x2800,0x2801]:g.fn('glTexParameteri',None,UINT,UINT,C.c_int)(0x0DE1,prop,0x2600)
        pixel=np.asarray(value,dtype=np.float32)
        g.fn('glTexImage2D',None,UINT,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,UINT,UINT,C.c_void_p)(0x0DE1,0,0x8814,1,1,0,0x1908,0x1406,pixel.ctypes.data)
    mode=g.fn('glMatrixMode',None,UINT);identity=g.fn('glLoadIdentity',None)
    mode(0x1701);identity();g.fn('glOrtho',None,*([C.c_double]*6))(-1,1,-1,1,-10,10);mode(0x1700);identity()
    g.fn('glEnable',None,UINT)(0x0B44);g.fn('glCullFace',None,UINT)(0x0404)
    g.fn('glFrontFace',None,UINT)(0x0901) # FTE alias front: clockwise, cull CCW
    begin=g.fn('glBegin',None,UINT);end=g.fn('glEnd',None)
    normal=g.fn('glNormal3f',None,FLOAT,FLOAT,FLOAT);texcoord=g.fn('glTexCoord2f',None,FLOAT,FLOAT)
    vertex=g.fn('glVertex3f',None,FLOAT,FLOAT,FLOAT);error=g.fn('glGetError',UINT)
    setup_error=error();assert setup_error==0,('setup',hex(setup_error))
    g.fn('glColor4f',None,FLOAT,FLOAT,FLOAT,FLOAT)(light,light,light,1)
    begin(0x0004);normal(0,0,1)
    positions=[(-.9,-.9),(-.9,.9),(.9,-.9)]
    if not cw:positions.reverse()
    for x,y in positions:
        texcoord(.5,.5);vertex(x,y,0)
    end();draw_error=error();assert draw_error==0,('draw',hex(draw_error));pixels=np.zeros((n,n,4),dtype=np.float32)
    g.fn('glReadPixels',None,C.c_int,C.c_int,C.c_int,C.c_int,UINT,UINT,C.c_void_p)(0,0,n,n,0x1908,0x1406,pixels.ctypes.data)
    g.fn('glDisable',None,UINT)(0x0B44);g.fn('glDeleteTextures',None,C.c_int,C.c_void_p)(2,textures)
    final_error=error();assert final_error==0,('readback',hex(final_error))
    return pixels

def main():
    a=argparse.ArgumentParser();a.add_argument('--bake',type=Path,required=True);a.add_argument('--original-bake',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    results={'claims':'GPU/compiler/mesh/data controls ONLY; game look/placement/ride/FPS pending'}
    qc=(ROOT/'src/client/cl_winter.qc').read_text();surface=qc.split(' Winter_Surface =',1)[1].split('void() Winter_Load',1)[0]
    assert surface.index('shaderforname(')<surface.index('precache_model(')
    assert 'ftesurf_colin_snow_v2_' in surface
    for group in ['grass','caps']:
        rel=Path('models/gibs/winterweather')/('surf_colin_blaster_69000-'+group+'.iqm');new,mat=mesh(args.bake/rel);old,_=mesh(args.original_bake/rel)
        assert len(new)>0 and np.all(new<-.0001);assert np.any(old>.0001)
        assert mat=='ftesurf_colin_snow_'+group and 'v2_' not in mat
        results[group]={'corrected_CW':len(new),'old_wrong_CCW':int((old>.0001).sum()),'old_degenerate':int((np.abs(old)<=.0001).sum()),'default_runtime_names_distinct':True}
    step_hashes=[]
    for i in range(1,5):
        path=args.bake/'sound/winter'/f'snow{i}.wav'
        with wave.open(str(path),'rb') as f:
            assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,22050)
            values=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float)/32768
        assert .1<len(values)/22050<.5 and .005<np.sqrt(np.mean(values**2))<.3 and np.max(np.abs(values))<.65
        step_hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert len(set(step_hashes))==4;results['original_quiet_snow_PCM_distinct']=4
    source=(ROOT/'src/client/cl_snow.qc').read_text();emit=(ROOT/'src/client/cl_emit.qc').read_text();mainqc=(ROOT/'src/client/cl_main.qc').read_text()
    assert 'snow_active = FALSE;' in source and source.index('addentity(snow_ent);')<source.index('snow_active = TRUE;')
    assert 'if (Snow_ReplacementActive()) { pr_nact = 0; pr_sacc = 0; return; }' in emit
    draw=mainqc.split('Snow_Frame();',1)[1];assert draw.index('Emit_Frame();')<draw.index('Winter_Frame();')
    audio=(ROOT/'src/client/cl_gameaudio.qc').read_text();assert 'if (onlysnow) return FALSE;' in audio and 'volume <= 0)' in audio
    rwm=(ROOT/'src/client/cl_rampwear.qc').read_text();assert '"r_rampwear_lift", "2"' in rwm and '* rw_lift;' in rwm and 'rw_rad[s] = stof(argv(4)) + rw_lift;' in rwm
    g=GL()
    try:
        # This driver accepted BOTH original shader branches: falsify the initial
        # reserved-keyword suspicion rather than claim it caused the owner's pink.
        for grass in [True,False]:
            old=program(g,ROOT/'ftesurf/glsl/ftesurf_snowcover_v1.glsl',grass);g.fn('glDeleteProgram',None,UINT)(old)
        results['original_packed_compile_failure_hypothesis']='FALSIFIED on actual driver'
        for label,grass,roof,visible,cw in [('grass',True,.9,True,True),('caps-open',False,.5,True,True),('caps-roofed',False,.9,False,True),('wrong-winding',True,.9,False,False)]:
            p=program(g,ROOT/'ftesurf/glsl/ftesurf_snowcover_v2.glsl',grass);pixels=render(g,p,roof,cw);g.fn('glDeleteProgram',None,UINT)(p)
            count=int(np.count_nonzero(pixels[:,:,3]>.5));assert (count>100)==visible,(label,count)
            if visible:
                rgb=pixels[:,:,:3][pixels[:,:,3]>.5];assert np.min(rgb)>.7 and np.all(rgb[:,2]>=rgb[:,0]) # white/blue snow, not purple
            results[label+'_visible_pixels']=count;Image.fromarray(np.uint8(np.clip(pixels,0,1)*255)).save(args.out.with_name(args.out.stem+'-'+label+'.png'))
    finally:g.close()
    args.out.write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))

if __name__=='__main__':main()
