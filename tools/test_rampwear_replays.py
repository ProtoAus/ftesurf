#!/usr/bin/env python3
"""Cosmetic readers only: full KSF inputs, binding, clip coverage, no evidence writes."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import rampwear_replays as R


class CosmeticReplayTests(unittest.TestCase):
    def raw(self, root, version=3):
        data=struct.pack('<4i',version,1,4,0)
        if version==3:data+=struct.pack('<2i',11,0)
        for i in range(4):
            data+=struct.pack('<i5fi3f',4 if i==1 else 0,float(i),2.,3.,0.,0.,0,100.,0.,-100.)
            if version==3:data+=struct.pack('<i',1 if i==3 else 0)
        path=root/'original.rec';path.write_bytes(data)
        binding={'map':'surf_fixture','game':'css66','sha256':hashlib.sha256(data).hexdigest()}
        path.with_suffix('.binding.json').write_text(json.dumps(binding))
        return path,binding

    def clip(self,root,digest,name='clip.rec',x=0):
        p=root/name;p.write_text('FTESURF-REC 5\nmap surf_fixture\nforeign ksf '+digest+'\ntick 0.015\nbegin\n0 '+str(x)+' 0 0 100 0 -100 0 0 0\nend 1 1 0 0\n')
        return p

    def test_both_raw_versions_keep_all_frames_and_never_recorded_contacts(self):
        for version in [2,3]:
            with self.subTest(version=version),tempfile.TemporaryDirectory() as tmp:
                p,b=self.raw(Path(tmp),version);data,identity,kind=R.capture(p,'surf_fixture');r=R.decode(p,data,kind)
                self.assertEqual(identity,('ksf',b['sha256']))
                self.assertEqual(len(r['ticks']),4)
                self.assertEqual([t.tick for t in r['ticks']],[0,1,2,3])
                self.assertEqual(r['tick_interval'],0.015)
                self.assertFalse(r['recorded_contacts'])
                self.assertEqual(r['ticks'][1].flags&2,2)
                self.assertEqual(r['ticks'][3].flags&1,1 if version==3 else 0)

    def test_map_game_and_bytes_binding_all_act(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,b=self.raw(Path(tmp));R.capture(p,'surf_fixture')
            for field,value in [('map','surf_other'),('game','css100'),('sha256','0'*64)]:
                p.with_suffix('.binding.json').write_text(json.dumps(dict(b,**{field:value})))
                with self.subTest(field=field),self.assertRaises(ValueError):R.capture(p,'surf_fixture')
            p.with_suffix('.binding.json').unlink()
            with self.assertRaises(OSError):R.capture(p,'surf_fixture')

    def test_only_valid_full_original_supersedes_partial_clips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw,b=self.raw(root);a=self.clip(root,b['sha256']);z=self.clip(root,b['sha256'],'later.rec',42)
            self.assertEqual(R.prefer_originals([a,z],'surf_fixture'),[a,z])
            self.assertNotEqual(R.capture(a,'surf_fixture')[1],R.capture(z,'surf_fixture')[1])
            self.assertEqual(R.prefer_originals([a,z,raw],'surf_fixture'),[raw])
            # Same advertised name/bytes hash, but an invalid body cannot hide clips.
            raw.write_bytes(raw.read_bytes()[:-1]);b['sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
            raw.with_suffix('.binding.json').write_text(json.dumps(b));a=self.clip(root,b['sha256'])
            self.assertEqual(R.prefer_originals([a,raw],'surf_fixture'),[a,raw])
            missing=root/'missing.rec'
            self.assertEqual(R.prefer_originals([missing],'surf_fixture'),[missing])


if __name__=='__main__':unittest.main()
