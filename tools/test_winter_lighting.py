"""P1327: actual production GLSL light/roof/flash pixels, stored IQM and audio.
Not an in-game placement/sound/FPS acceptance. Reuse the owned small WGL seam.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import numpy as np
from test_winter_repair_pixels import GL,UINT,FLOAT,program,render,mesh
from snow_lighting import FaceLights
from rampwear import Bsp

ROOT=Path(__file__).resolve().parents[1]

def colours(path):
    data=path.read_bytes();h=struct.unpack_from('<27I',data,16)
    for i in range(h[7]):
        kind,flags,fmt,size,off=struct.unpack_from('<5I',data,h[9]+i*20)
        if kind==6:
            assert (fmt,size)==(1,4)
            return np.frombuffer(data,np.uint8,count=h[8]*4,offset=off).reshape(-1,4)
    raise AssertionError('actual IQM must carry normalized vertex light')

def mean_visible(image):
    valid=image[:,:,3]>.5;assert np.count_nonzero(valid)>100
    return float(image[:,:,:3][valid].mean())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bake',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--ffmpeg',type=Path,required=True);ap.add_argument('--ffprobe',type=Path,required=True);a=ap.parse_args();result={'scope':'actual shader/data controls, not native appearance/audio/FPS'}
    report=json.loads((a.bake/'theme-report.json').read_text());assert report['counts']['cap_boundary_skirts']>0 and report['lighting']['sampled']>8000
    for group in ['grass','caps']:
        path=a.bake/'models/gibs/winterweather'/f'surf_colin_blaster_69000-{group}-lit.iqm';facing,material=mesh(path);assert len(facing)>0 and np.all(facing<-.0001)
        c=colours(path);assert np.all(c[:,3]==255) and int(c[:,:3].min())<100 and int(c[:,:3].max())>200
        result[group]={'CW_triangles':len(facing),'RGB_range':[int(c[:,:3].min()),int(c[:,:3].max())]}
    # Independent fixture of the actual RGBExp32 reader, including bilinear sample
    # and a missing-face ambient control. The native map itself supplies the IQM.
    class Fixture:
        version=20
        def __init__(self):
            f=bytearray(56);struct.pack_into('<h',f,10,0);f[16:20]=bytes([0,255,255,255]);struct.pack_into('<i',f,20,0);struct.pack_into('<2i',f,36,1,1)
            t=bytearray(72);struct.pack_into('<8f',t,32,1,0,0,0,0,1,0,0)
            self.lumps={7:bytes(f),6:bytes(t),8:bytes([64,64,64,0,128,128,128,0,192,192,192,0,255,255,255,0]),53:b''}
        def lump(self,n):return self.lumps.get(n,b''),0
    f=Fixture();lights=FaceLights(f);assert np.allclose(lights.sample(0,[.5,.5,0]),(64+128+192+255)/(4*255))
    f.lumps[7]=f.lumps[7][:20]+struct.pack('<i',-1)+f.lumps[7][24:];assert np.allclose(FaceLights(f).sample(0,[0,0,0]),.28)
    audio=[]
    for name in ['rainloop','snowloop','thunder']:
        path=ROOT/'ftesurf/sound/winter'/(name+'.ogg');probe=json.loads(subprocess.check_output([str(a.ffprobe),'-v','error','-show_entries','stream=codec_name,channels,sample_rate,bit_rate,duration','-of','json',str(path)],text=True))['streams'][0]
        assert probe['codec_name']=='vorbis' and probe['channels']==1 and int(probe['bit_rate'])==64000
        pcm=subprocess.check_output([str(a.ffmpeg),'-nostdin','-v','error','-i',str(path),'-f','f32le','-acodec','pcm_f32le','-']);values=np.frombuffer(pcm,'<f4');assert np.isfinite(values).all() and .001<float(np.sqrt(np.mean(values**2)))<.9 and float(np.max(np.abs(values)))<1.01
        audio.append({'name':name,'bytes':path.stat().st_size,'duration':float(probe['duration']),'decoded_peak':float(np.max(np.abs(values)))})
    result['owner_Vorbis']=audio
    qc=(ROOT/'src/client/cl_weather.qc').read_text();winter=(ROOT/'src/client/cl_winter.qc').read_text();release=(ROOT/'src/release/release.ps1').read_text()
    assert '3 + floor(Weather_Noise(time + wx_burstid * 13) * 4)' in qc
    assert 'wx_thunderat = wx_flash + 0.8 +' in qc and 'wx_flashesleft = wx_flashesleft - 1;' in qc
    assert 'preview >= 2' in qc and 'missing audio must not stall later visual bursts' in qc
    assert 'lightstyle(' not in qc.split('void() Weather_StartBurst =',1)[1] # no hot lightmap writes
    assert 'EF_NOSHADOW; e.colormod' in winter and 'player/footsteps/snow%g.wav' in winter and 'for (i = 1; i <= 6;' in winter
    assert "@{ Path = 'ftesurf/sound/winter';   Filter = '*.ogg' }" in release
    result['timeline_guards']='source-structural ONLY; native preview/counters remain manual'
    g=GL()
    try:
        for version in [2,3]:
            p=program(g,ROOT/'ftesurf/glsl'/f'ftesurf_snowcover_v{version}.glsl',True)
            bright=mean_visible(render(g,p,.5,light=1,albedo=.9));dark=mean_visible(render(g,p,.5,light=.2,albedo=.9));g.fn('glDeleteProgram',None,UINT)(p)
            if version==2:assert abs(bright-dark)<.0001 # acted old fullbright control
            else:assert bright>.8 and .15<dark/bright<.25
            result[f'v{version}_actual_bright_dark']=[bright,dark]
        p=program(g,ROOT/'ftesurf/glsl/ftesurf_snowcover_v3.glsl',False)
        opened=render(g,p,.5,light=.8,albedo=.9);roofed=render(g,p,.9,light=.8,albedo=.9);wrong=render(g,p,.5,cw=False,light=.8,albedo=.9)
        assert np.count_nonzero(opened[:,:,3]>.5)>100 and not np.count_nonzero(roofed[:,:,3]) and not np.count_nonzero(wrong[:,:,3]);g.fn('glDeleteProgram',None,UINT)(p)
        p=program(g,ROOT/'ftesurf/glsl/ftesurf_weather_sky_v3.glsl',False);loc=g.fn('glGetUniformLocation',C.c_int,UINT,C.c_char_p)
        g.fn('glUniform3f',None,C.c_int,FLOAT,FLOAT,FLOAT)(loc(p,b'e_eyepos'),-10,0,-5)
        g.fn('glUniform4f',None,C.c_int,FLOAT,FLOAT,FLOAT,FLOAT)(loc(p,b'e_colour'),1,.5,.5,.65);base=mean_visible(render(g,p,.5))
        g.fn('glUniform4f',None,C.c_int,FLOAT,FLOAT,FLOAT,FLOAT)(loc(p,b'e_colour'),1,.5,.5,1);flash=mean_visible(render(g,p,.5));assert flash>base+.2
        result['sky_actual_base_flash']=[base,flash];g.fn('glDeleteProgram',None,UINT)(p)
    finally:g.close()
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
