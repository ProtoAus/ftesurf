#!/usr/bin/env python3
"""Small P1317 geometry/parser controls. No native appearance/FPS claim."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
import numpy as np
from PIL import Image
from winter_theme import conservative_roof
from winter_weather import roof_header

ROOT=Path(__file__).resolve().parents[1]

def fixture(path, wide=False, cyclic=False):
    lumps={}; versions={}
    lumps[0]=b'{"classname" "worldspawn"}\0'
    planes=[(1,0,0,64,0),(-1,0,0,64,0),(0,1,0,64,1),(0,-1,0,64,1),(0,0,1,0,2),(0,0,-1,8,2)]
    lumps[1]=b''.join(struct.pack('<4fi',*p) for p in planes)
    nodesize=48 if wide else 32; node=bytearray(nodesize)
    struct.pack_into('<iii',node,0,0,0 if cyclic else -1,-2); lumps[5]=bytes(node);versions[5]=int(wide)
    lumps[6]=bytes(72)
    lumps[2]=bytes(32);lumps[43]=b'concrete\0';lumps[44]=bytes(4)
    leafsize=56 if wide else 32; leaves=[]
    for _ in range(2):
        leaf=bytearray(leafsize)
        struct.pack_into('<II' if wide else '<HH',leaf,44 if wide else 24,0,1);leaves.append(bytes(leaf))
    lumps[10]=b''.join(leaves);versions[10]=2 if wide else 1
    model=bytearray(48);struct.pack_into('<6f',model,0,-64,-64,-8,64,64,16);struct.pack_into('<i',model,36,0);lumps[14]=bytes(model)
    lumps[17]=struct.pack('<I' if wide else '<H',0);versions[17]=int(wide)
    lumps[18]=struct.pack('<iii',0,6,1)
    lumps[19]=b''.join(struct.pack('<IiiBBxx',i,0,-1,0,0) if wide else struct.pack('<Hhhh',i,0,-1,0) for i in range(6));versions[19]=int(wide)
    data=bytearray(1036);struct.pack_into('<4si',data,0,b'VBSP',25 if wide else 20)
    for i,blob in lumps.items():
        struct.pack_into('<iiii',data,8+i*16,len(data),len(blob),versions.get(i,0),0);data.extend(blob)
    path.write_bytes(data)

class WinterThemeTests(unittest.TestCase):
    def test_roof_header_matches_current_weather_reader(self):
        header=roof_header('surf_colin_blaster_69000',-57504,-34416,512,256,128,1542,270)
        self.assertEqual(header.split(),['weather','1','surf_colin_blaster_69000',
                         '-57504','-34416','512','256','128','1542','270'])
        self.assertTrue(header.endswith('\n'))
        # The original producer output really fails the actual reader's gate.
        old='wxroof 1 surf_colin_blaster_69000 -57504 -34416 512 256 128'
        self.assertNotEqual(len(old.split()),10)
        qc=(ROOT/'src/client/cl_weather.qc').read_text()
        self.assertIn('if (n != 10)',qc)
        self.assertIn('strcmp(argv(0), "weather")',qc)

    def test_thin_roof_survives_bounded_audio_reduction(self):
        h=np.full((32,32),-1024.);h[1,1]=128
        r=conservative_roof(h)
        self.assertEqual(r.shape,(2,2));self.assertEqual(r[0,0],128)
        self.assertEqual(h[8,8],-1024) # old centre sample really misses the roof
        with self.assertRaises(ValueError):conservative_roof(np.zeros((17,32)))

    def test_theme_is_map_scoped_reversible_and_bounded(self):
        qc=(ROOT/'src/client/cl_winter.qc').read_text()
        self.assertIn('wi_colin = !strcmp(mname, "surf_colin_blaster_69000")',qc)
        self.assertIn('return (wi_colin && cvar("r_colin_winter") != 0)',qc)
        self.assertIn('#define WI_PROPS 16',qc)
        self.assertIn('if (Winter_ThemeActive())',qc)
        self.assertNotIn('cvar_set("r_snow"',qc);self.assertNotIn('cvar_set("r_weather"',qc)
        frame=qc.split('void() Winter_Frame =',1)[1].split('float(string command)',1)[0]
        self.assertNotIn('traceline(',frame);self.assertNotIn('fopen(',frame)
        self.assertIn('r_colin_winter',(ROOT/'ftesurf/cfg/default.cfg').read_text())
        self.assertIn('r_colin_winter|Colin Christmas theme',(ROOT/'src/client/cl_hudedit.qc').read_text())
        self.assertIn('Missing media must not opt older clients into unclipped automatic snow',qc)
        lost=(ROOT/'src/client/cl_milk.qc').read_text().split('CSQC_RendererRestarted =',1)[1].split('// P1235:',1)[0]
        self.assertIn('Winter_Load();',lost);self.assertIn('Weather_Load();',lost)

    def test_actual_legacy_and_strata_collision_domains_and_cycle_refusal(self):
        folder=os.environ.get('WINTER_TEST_ROOT')
        if not folder:self.skipTest('set explicit owned WINTER_TEST_ROOT, never create ad-hoc temp overlay')
        root=Path(folder);root.mkdir(parents=True,exist_ok=True)
        for wide in (False,True):
            p=root/('strata.bsp' if wide else 'legacy.bsp');fixture(p,wide)
            out=root/('strata' if wide else 'legacy');out.mkdir(exist_ok=True)
            result=subprocess.run([sys.executable,str(ROOT/'tools/snowmask.py'),'--map','fixture','--bsp',str(p),'--cell','32','--gamedir',str(out)],capture_output=True,text=True,timeout=20)
            (out/'result.log').write_text(result.stdout+result.stderr)
            self.assertEqual(result.returncode,0,result.stderr)
            # This concrete-only fixture intentionally has no sky brushes.
            # Production Colin bake supplies the positive sky/roof domain; do not
            # invent a PNG pass or grow a second map generator for the negative.
            self.assertIn('no sky brushes, no mask written',result.stdout)
            self.assertFalse((out/'gfx/snowmask/fixture.png').exists())
        p=root/'cyclic.bsp';fixture(p,True,True)
        result=subprocess.run([sys.executable,str(ROOT/'tools/snowmask.py'),'--map','fixture','--bsp',str(p),'--cell','32','--gamedir',str(root/'cyclic')],capture_output=True,text=True,timeout=20)
        (root/'cyclic-refusal.log').write_text(result.stdout+result.stderr)
        self.assertNotEqual(result.returncode,0);self.assertIn('cyclic/out-of-range',result.stderr)

if __name__=='__main__':unittest.main()
