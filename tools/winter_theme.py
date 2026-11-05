#!/usr/bin/env python3
"""P1317 map-specific, pre-baked Christmas terrain/props. No BSP/material edits.
Reuses the native-matching roof and weather bakers. Grass becomes an opaque snow
surface; exposed caps use the SAME fine32 roof mask as falling snow. Two bounded
static cosmetic meshes, no runtime traces. Not P1287's world-shader workstream.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import numpy as np
import wave
from PIL import Image, ImageFilter
from rampwear import Bsp
from holiday_assets import iqm
from snow_lighting import FaceLights
from winter_weather import MOM_MAPS, meshes as weather_meshes, roof_header
from winter_placements import records

MAP = 'surf_colin_blaster_69000'
ASSETS = ('snowman-hat','tree-decorated-snow','present-a-cube','tree-snow-a','snowman','present-b-rectangle')
ASSET_IDS = (2, 3, 5, 4, 1, 6)


def world_faces(b):
    faces,fv=b.lump(7); vertices,_=b.lump(3); edges,ev=b.lump(12); se,_=b.lump(13)
    tex,_=b.lump(6); td,_=b.lump(2); st,_=b.lump(44); ss,_=b.lump(43); pl,_=b.lump(1); models,_=b.lump(14)
    es,ef=(8,'<2I') if ev>=1 else (4,'<2H'); fs,ff=(72,'<IBBxxiiii') if fv>=2 else (56,'<HBBiHHH')
    first,count=struct.unpack_from('<ii',models,40)
    for face in range(first,first+count):
        plane,side,on,start,n,ti,disp=struct.unpack_from(ff,faces,face*fs)
        if ti<0 or ti==65535 or n<3: continue
        flags,di=struct.unpack_from('<ii',tex,ti*72+64)
        sid=struct.unpack_from('<i',td,di*32+12)[0]; off=struct.unpack_from('<i',st,sid*4)[0]
        material=ss[off:ss.index(b'\0',off)].decode('latin1').lower()
        normal=np.array(struct.unpack_from('<3f',pl,plane*20))*(-1 if side else 1)
        poly=[]
        for j in range(n):
            edge=struct.unpack_from('<i',se,(start+j)*4)[0]; pair=struct.unpack_from(ef,edges,abs(edge)*es)
            poly.append(np.array(struct.unpack_from('<3f',vertices,pair[0 if edge>=0 else 1]*12)))
        yield face,flags,material,normal,poly,(-1 if disp==65535 else disp)


def displacement(b, poly, index):
    info,ver=b.lump(26); verts,_=b.lump(33); stride=232 if ver>=1 else 176
    if len(poly)!=4 or not (0<=index<len(info)//stride): raise ValueError('invalid displacement quad/index')
    pos=np.array(struct.unpack_from('<3f',info,index*stride)); start=struct.unpack_from('<i',info,index*stride+12)[0]; power=struct.unpack_from('<i',info,index*stride+20)[0]
    if not 2<=power<=4: raise ValueError('displacement power outside native range')
    n=1<<power
    if start<0 or (start+(n+1)**2)*20>len(verts): raise ValueError('displacement vertex range')
    primary=min(range(4),key=lambda k:float(np.dot(poly[k]-pos,poly[k]-pos)))
    corners=[poly[(primary+k)&3] for k in range(4)]; grid=[]
    for y in range(n+1):
        for x in range(n+1):
            fx,fy=x/n,y/n
            base=(1-fx)*(1-fy)*corners[0]+(1-fx)*fy*corners[1]+fx*fy*corners[2]+fx*(1-fy)*corners[3]
            v=struct.unpack_from('<4f',verts,(start+y*(n+1)+x)*20)
            grid.append(base+np.array(v[:3])*v[3])
    for y in range(n):
        for x in range(n):
            a=x+y*(n+1); c=a+n+2
            pairs=((a,a+n+1,c),(a,c,a+1)) if not((x+y)&1) else ((a+n+1,c,a+1),(a+n+1,a+1,a))
            for indices in pairs: yield [grid[k] for k in indices]


def area(poly):
    return sum(np.linalg.norm(np.cross(poly[i]-poly[0],poly[i+1]-poly[0]))*.5 for i in range(1,len(poly)-1))


def clockwise_triangles(vertices, triangles):
    """Match FTE's IQM front faces AFTER float32 storage, not OBJ conventions."""
    p=np.asarray([v[0] for v in vertices],dtype=np.float32)
    n=np.asarray([v[2] for v in vertices],dtype=np.float32)
    result=[]
    for a,b,c in triangles:
        facing=float(np.dot(np.cross(p[b]-p[a],p[c]-p[a]),n[a]+n[b]+n[c]))
        if abs(facing)<=0.0001: continue
        result.append((a,c,b) if facing>0 else (a,b,c))
    return result


def snow_audio(out):
    """Original quiet procedural snow crunch, no sampled/licensed third-party PCM."""
    out.mkdir(parents=True,exist_ok=True)
    rate=22050;rng=np.random.default_rng(1319)
    for i in range(1,5):
        size=int(rate*(0.27+0.025*i));t=np.arange(size)/rate
        noise=rng.normal(size=size)
        soft=np.convolve(noise,np.ones(5)/5,mode='same')
        grains=np.maximum(0,np.sin(t*(125+13*i))+rng.normal(0,.5,size))
        signal=(soft*.7+noise*.3)*(.3+.7*grains)*(1-np.exp(-t*200))*np.exp(-t*(13+i))
        signal*=np.minimum((size/rate-t)*100,1);signal-=signal.mean()
        signal*=.6/max(float(np.abs(signal).max()),1e-9)
        with wave.open(str(out/f'snow{i}.wav'),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
            f.writeframes((signal*32767).astype('<i2').tobytes())


def conservative_roof(heights, block=16):
    h,w=heights.shape
    if h%block or w%block: raise ValueError('roof reduction must preserve the full exact domain')
    return heights.reshape(h//block,block,w//block,block).max(axis=(1,3))


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--map',default=MAP,choices=[MAP]); ap.add_argument('--gamedir',type=Path,required=True); ap.add_argument('--mapdir',type=Path,default=MOM_MAPS)
    a=ap.parse_args(); out=a.gamedir; source=a.mapdir/(a.map+'.bsp'); b=Bsp(source)
    roof=out/'gfx/weather'/f'{a.map}.roof'
    if not roof.exists():
        subprocess.run([sys.executable,str(Path(__file__).with_name('winter_weather.py')),'--maps',a.map,'--mapdir',str(a.mapdir),'--gamedir',str(out)],check=True,timeout=120)
    oldreport=out/'theme-report.json'
    reuse=oldreport.exists() and json.loads(oldreport.read_text()).get('bsp_sha256')==hashlib.sha256(source.read_bytes()).hexdigest()
    if not reuse:
        subprocess.run([sys.executable,str(Path(__file__).with_name('snowmask.py')),'--map',a.map,'--bsp',str(source),'--cell','32','--gamedir',str(out)],check=True,timeout=120)
    prefix=out/'gfx/snowmask'/a.map; meta=prefix.with_suffix('.txt').read_text().split(); x0,y0,cell,w,h,z0,zr=map(float,meta[3:10]); w,h=int(w),int(h)
    if cell!=32 or len(meta)!=10 or meta[:3]!=['snowmask','1',a.map]: raise ValueError('requires actual fine32 map mask')
    rgb=np.array(Image.open(prefix.with_suffix('.png')).convert('RGB'),dtype=np.uint16)
    heights=z0+((rgb[:,:,0].astype(np.uint32)<<8)|rgb[:,:,1])*zr/65535
    # The huge Strata map needs512-unit audio cells. Reduce actual fine32 heights
    # by MAX, not coarse centre sampling: thin real roofs cannot disappear.
    # This is intentionally conservative near roof edges; visuals still use fine32.
    reduced=conservative_roof(heights)
    _, weather_triangles=weather_meshes(b)
    header=roof_header(a.map,x0,y0,cell*16,reduced.shape[1],reduced.shape[0],
                       len(weather_triangles['sky']),len(weather_triangles['ice']))
    roof.write_bytes(header.encode('ascii')+reduced.astype('<f4').tobytes())
    def exposed(p):
        ix,iy=int((p[0]-x0)//cell),int((p[1]-y0)//cell)
        return 0<=ix<w and 0<=iy<h and p[2]+3>=heights[iy,ix]
    vertices={'grass':[],'caps':[]}; triangles={'grass':[],'caps':[]}; colours={'grass':[],'caps':[]}; edges=collections.defaultdict(list); counts=collections.Counter(); candidates=[]; lighting=FaceLights(b)
    for face,flags,material,normal,poly,disp in world_faces(b):
        if flags&(2|4|128|512) or any(x in material for x in ('tools/','water','lava','grate','glass','ice2')): continue
        grass='grass' in material
        if grass: counts['grass_faces']+=1
        if not grass and normal[2]<.85: continue
        polygons=list(displacement(b,poly,disp)) if disp>=0 else [poly]
        for polygon in polygons:
            n=normal.copy()
            if disp>=0:
                n=np.cross(polygon[1]-polygon[0],polygon[2]-polygon[0]); norm=np.linalg.norm(n)
                if norm<.0001: continue
                n=n/norm
                if np.dot(n,normal)<0:n=-n
            if not grass and n[2]<.85: counts['steep_rejected']+=1;continue
            centre=sum(polygon)/len(polygon)
            if not grass and not any(exposed(p) for p in [centre,*polygon]): counts['roofed_rejected']+=1;continue
            group='grass' if grass else 'caps'; base=len(vertices[group]); counts[group+'_polys']+=1
            for p in polygon:
                depth=.75 if grass else 3.5+1.5*math.sin(p[0]*.012+p[1]*.014)
                q=p+n*depth
                vertices[group].append((tuple(q),((q[0]-x0)/(w*cell),(q[1]-y0)/(h*cell)),tuple(n)))
                colours[group].append(lighting.sample(face,p))
            for i in range(1,len(polygon)-1):triangles[group].append((base,base+i+1,base+i))
            if not grass:
                for i in range(len(polygon)):
                    j=(i+1)%len(polygon);key=tuple(sorted(tuple(round(float(v),3) for v in p) for p in (polygon[i],polygon[j])))
                    edges[key].append((base+i,base+j,polygon[i],polygon[j],centre,n))
        if grass and normal[2]>.97 and area(poly)>4096:
            centre=sum(poly)/len(poly)
            for corner in poly:
                p=corner*.6+centre*.4
                edge_clear=min(np.linalg.norm(np.cross(np.r_[poly[(j+1)%len(poly)][:2]-poly[j][:2],0],np.r_[p[:2]-poly[j][:2],0]))/max(.001,np.linalg.norm(poly[(j+1)%len(poly)][:2]-poly[j][:2])) for j in range(len(poly)))
                if edge_clear>=40 and exposed(p): candidates.append(tuple(p))
    for candidates_at_edge in edges.values():
        if len(candidates_at_edge)!=1:continue # no doubled internal skirts
        ia,ib,a0,b0,centre,n=candidates_at_edge[0];d=b0-a0;side=np.array([d[1],-d[0],0.0]);length=float(np.linalg.norm(side))
        if length<.01:continue
        side/=length
        if np.dot(side,(a0+b0)*.5-centre)<0:side=-side
        base=len(vertices['caps'])
        for old,p,top in [(ia,a0,True),(ib,b0,True),(ib,b0,False),(ia,a0,False)]:
            q=vertices['caps'][old][0] if top else tuple(p+n*.25)
            vertices['caps'].append((q,((q[0]-x0)/(w*cell),(q[1]-y0)/(h*cell)),tuple(side)))
            colours['caps'].append(colours['caps'][old]*.72)
        triangles['caps'].extend([(base,base+1,base+2),(base,base+2,base+3)]);counts['cap_boundary_skirts']+=1
    if counts['grass_faces']!=103: raise ValueError('inspected map changed or real grass not processed')
    for group,cap in [('grass',2048),('caps',18000)]:
        triangles[group]=clockwise_triangles(vertices[group],triangles[group])
        if not 0<len(triangles[group])<=cap:raise ValueError(f'{group} geometry budget: {len(triangles[group])}/{cap}')
        p=out/'models/gibs/winterweather'/f'{a.map}-{group}-lit.iqm';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(iqm(a.map+'-'+group,vertices[group],triangles[group],'ftesurf_colin_snow_'+group,colours[group]))
    entities=b.lump(0)[0].decode('latin1');spawn=[]
    for block in re.findall(r'\{[^{}]*\}',entities):
        e=dict(re.findall(r'"([^"\n]*)"\s*"([^"\n]*)"',block))
        if e.get('classname','').startswith('info_player_'):
            try:spawn.append(np.array(list(map(float,e['origin'].split()))))
            except (ValueError,KeyError):continue
    if not spawn or not candidates:raise ValueError('no valid visible decorations/real spawn')
    candidates=[np.array(p) for p in candidates if all(np.linalg.norm(np.array(p)-s)>160 for s in spawn)]
    selected=[]
    while candidates and len(selected)<16:
        chosen=min(candidates,key=lambda p:min(np.linalg.norm(p-s) for s in spawn)) if not selected else max(candidates,key=lambda p:min(np.linalg.norm(p-s) for s in selected))
        if selected and min(np.linalg.norm(chosen-s) for s in selected)<256:break
        selected.append(chosen);candidates=[p for p in candidates if not np.array_equal(p,chosen)]
    existing=(Path(__file__).resolve().parents[1]/'ftesurf/gfx/winter'/f'{a.map}.txt')
    lines=['winter 1 '+a.map,'// Map-specific snow material replacement, exposed caps, provisional safe grass-edge props.']
    for group in ('grass','caps'):lines.append(f'surface {group} models/gibs/winterweather/{a.map}-{group}-lit.iqm {z0:g} {zr:g}')
    for i,p in enumerate(selected):
        scale=.9 if ASSETS[i%len(ASSETS)].startswith('tree') else 1
        lines.append('prop %s %g %g %g %g %g'%(ASSET_IDS[i%len(ASSET_IDS)],p[0],p[1],p[2]+.5,(i*137)%360,scale))
    # Existing light selection already has strict record/trace/visible caps.
    _, light_records=records([dict(re.findall(r'"([^"\n]*)"\s*"([^"\n]*)"',block)) for block in re.findall(r'\{[^{}]*\}',entities)])
    lines.extend(light_records)
    existing.parent.mkdir(parents=True,exist_ok=True);existing.write_text('\n'.join(lines)+'\n',encoding='ascii')
    weather=out/'gfx/weather';weather.mkdir(parents=True,exist_ok=True)
    gen=Path(__file__).resolve().parents[1]/'ftesurf/gfx/weather/snow-grain.png';gen.parent.mkdir(parents=True,exist_ok=True)
    noise=np.random.default_rng(1316).integers(210,256,(128,128),dtype=np.uint8);Image.fromarray(noise).filter(ImageFilter.GaussianBlur(.35)).save(gen)
    report={'map':a.map,'bsp_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'fine_mask_cell':cell,'audio_roof':'conservative512 max of exactfine32','mask_dimensions':[w,h],'counts':dict(counts),'triangles':{k:len(v) for k,v in triangles.items()},'props':len(selected),'prop_positions':[list(p) for p in selected],'collision_changes':False,'steep_ride_surfaces_excluded':True,'lighting':{'source':lighting.source,'sampled':lighting.sampled,'ambient_fallback':lighting.ambient,'linear_RGB_percentiles':np.percentile(np.asarray(colours['grass']+colours['caps']),[0,50,100],axis=0).tolist()},'cap_depth_units':[2,5],'native_appearance_fps':'PENDING'}
    (out/'theme-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
