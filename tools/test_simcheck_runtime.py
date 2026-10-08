#!/usr/bin/env python3
"""Frozen narrow installer controls; only temporary Git/packages/tools/recordings."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import simcheck_runtime as runtime

HERE=Path(__file__).resolve().parent
SOURCE=(HERE/'census'/'recsim.py').read_bytes()
INSTALLER=Path(runtime.__file__).read_bytes()


def rec(path,n):
    rows=['FTESURF-REC 9','map synthetic','track 0','leg 0','tickrate 100','begin']
    for i in range(n):rows.append('in %d %d 0 %d 0 0 0 0 0 %d'%(i,i,100+i%7,i%3))
    rows.append('end %d'%n);path.write_text('\n'.join(rows)+'\n')


class Runtime(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.pkg=self.root/'package';self.pkg.mkdir()
        self.tools=self.root/'tools';self.tools.mkdir()
        (self.pkg/'recsim.py').write_bytes(SOURCE)
        (self.pkg/'simcheck_runtime.py').write_bytes(INSTALLER)
        self.m={'version':1,'commit':'1'*40,'recsim_sha256':runtime.digest(SOURCE),
                'installer_sha256':runtime.digest(INSTALLER),'paired_sha256':{}}
        for name in runtime.PAIRED:
            data=('synthetic paired '+name).encode();(self.tools/name).write_bytes(data)
            self.m['paired_sha256'][name]=runtime.digest(data)
        self.manifest()

    def manifest(self):
        (self.pkg/'manifest.json').write_text(json.dumps(self.m),encoding='utf-8')

    def call(self,previous='absent',apply=False):
        return runtime.install(self.pkg,self.tools,previous,apply)

    def test_dry_run_absence_and_active_install(self):
        self.assertEqual(self.call()['state'],'planned')
        self.assertFalse((self.tools/'census').exists())
        result=self.call(apply=True);self.assertEqual(result['state'],'installed')
        target=self.tools/'census'/'recsim.py'
        self.assertEqual(target.read_bytes(),SOURCE)
        mod=runtime.probe(target)
        self.assertEqual(Path(mod.__file__).resolve(),target.resolve())
        a,b=self.root/'a.rec',self.root/'b.rec';rec(a,80);rec(b,80)
        verdict,data=mod.compare_paths(str(a),str(b))
        self.assertEqual(verdict,'compared');self.assertEqual(data['match'],1.0)
        self.assertEqual(data['compared'],80)  # positive comparison acted
        rec(a,9);rec(b,9)
        verdict,why=mod.compare_paths(str(a),str(b))
        self.assertNotEqual(verdict,'compared');self.assertIn('floor',why)
        before=sorted(p.name for p in target.parent.iterdir())
        self.assertEqual(self.call(runtime.digest(SOURCE),True)['state'],'unchanged')
        self.assertEqual(sorted(p.name for p in target.parent.iterdir()),before)

    def test_existing_predecessor_and_rollback_bytes(self):
        parent=self.tools/'census';parent.mkdir();target=parent/'recsim.py';target.write_bytes(b'old frozen source')
        with self.assertRaisesRegex(ValueError,'predecessor'):self.call(apply=True)
        self.assertEqual(target.read_bytes(),b'old frozen source')
        result=self.call(runtime.digest(target.read_bytes()),True)
        self.assertEqual(Path(result['backup']).read_bytes(),b'old frozen source')
        if os.name=='posix':self.assertEqual(Path(result['backup']).stat().st_mode & 0o777,0o600)
        self.assertEqual(target.read_bytes(),SOURCE)

    def test_paired_reader_drift_blocks_without_mutation(self):
        (self.tools/'hidcheck.py').write_bytes(b'non-owned edit')
        with self.assertRaisesRegex(ValueError,'paired runtime'):self.call(apply=True)
        self.assertFalse((self.tools/'census').exists())
        self.assertEqual((self.tools/'hidcheck.py').read_bytes(),b'non-owned edit')

    def test_package_and_invoked_installer_hashes(self):
        (self.pkg/'recsim.py').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError,'package bytes'):self.call(apply=True)
        (self.pkg/'recsim.py').write_bytes(SOURCE)
        (self.pkg/'simcheck_runtime.py').write_bytes(b'other helper')
        self.m['installer_sha256']=runtime.digest(b'other helper');self.manifest()
        with self.assertRaisesRegex(ValueError,'invoked installer'):self.call(apply=True)
        self.assertFalse((self.tools/'census').exists())

    def test_missing_capability_blocks_before_mutation(self):
        bad=b'other = 1\n';(self.pkg/'recsim.py').write_bytes(bad)
        self.m['recsim_sha256']=runtime.digest(bad);self.manifest()
        with self.assertRaisesRegex(ValueError,'capability'):self.call(apply=True)
        self.assertFalse((self.tools/'census').exists())

    def test_required_version_markers_block_before_existing_target_mutation(self):
        parent=self.tools/'census';parent.mkdir();target=parent/'recsim.py'
        target.write_bytes(b'prior');before=sorted(p.name for p in parent.iterdir())
        mode=target.stat().st_mode
        for marker in ('BOUNDED_INPUT_VERSION','SOURCE_CAPTURE_VERSION'):
            for replacement in ('',marker+' = False',marker+' = True',marker+' = 2'):
                bad=SOURCE.replace((marker+' = 1').encode(),replacement.encode())
                (self.pkg/'recsim.py').write_bytes(bad)
                self.m['recsim_sha256']=runtime.digest(bad);self.manifest()
                for apply in (False,True):
                    with self.subTest(marker=marker,replacement=replacement,apply=apply):
                        with self.assertRaisesRegex(ValueError,'capability'):
                            self.call(runtime.digest(b'prior'),apply)
                        self.assertEqual(target.read_bytes(),b'prior')
                        self.assertEqual(target.stat().st_mode,mode)
                        self.assertEqual(sorted(p.name for p in parent.iterdir()),before)

    def test_hash_valid_reader_that_ignores_a_limit_is_refused(self):
        for name in ('max_bytes','max_moves'):
            bad=SOURCE+('''\n_probe_original = compare_paths
def compare_paths(a, b, **kw):
    if kw.get('%s') == %s:
        kw['%s'] = None
    return _probe_original(a, b, **kw)
''' % (name, 'os.path.getsize(a)-1' if name=='max_bytes' else '79', name)).encode()
            (self.pkg/'recsim.py').write_bytes(bad)
            self.m['recsim_sha256']=runtime.digest(bad);self.manifest()
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError,'self-check'):
                    self.call(apply=True)
                self.assertFalse((self.tools/'census').exists())

    def test_captured_hash_must_describe_positive_probe_bytes(self):
        bad=SOURCE+b'''\n_probe_original = compare_paths
def compare_paths(a, b, **kw):
    verdict, data = _probe_original(a, b, **kw)
    if verdict == 'compared': data['sources']['a']['sha256'] = '0'*64
    return verdict, data
'''
        (self.pkg/'recsim.py').write_bytes(bad)
        self.m['recsim_sha256']=runtime.digest(bad);self.manifest()
        with self.assertRaisesRegex(ValueError,'self-check'):self.call(apply=True)
        self.assertFalse((self.tools/'census').exists())

    def test_reject_unknown_manifest_and_relative_destination(self):
        self.m['version']=2;self.manifest()
        with self.assertRaisesRegex(ValueError,'manifest'):self.call()
        self.m['version']=1;self.manifest()
        with self.assertRaisesRegex(ValueError,'absolute'):runtime.install(self.pkg,'tools','absent')

    def test_racing_predecessor_never_overwritten(self):
        parent=self.tools/'census';parent.mkdir();target=parent/'recsim.py';target.write_bytes(b'prior')
        real=runtime.tempfile.NamedTemporaryFile
        def raced(*args,**kw):
            target.write_bytes(b'peer raced');return real(*args,**kw)
        with mock.patch.object(runtime.tempfile,'NamedTemporaryFile',side_effect=raced):
            with self.assertRaisesRegex(ValueError,'raced'):self.call(runtime.digest(b'prior'),True)
        self.assertEqual(target.read_bytes(),b'peer raced')
        self.assertFalse(list(parent.glob('recsim-owned-*')))

    def test_symlink_rejected(self):
        other=self.root/'other';other.mkdir()
        try:(self.tools/'census').symlink_to(other,target_is_directory=True)
        except OSError:self.skipTest('symlink creation unavailable')
        with self.assertRaisesRegex(ValueError,'symlink'):self.call(apply=True)
        self.assertFalse(list(other.iterdir()))

    def test_prepare_exact_commit_not_head_or_loose_files(self):
        repo=self.root/'repo';repo.mkdir()
        def git(*a):return subprocess.check_output(['git','-C',str(repo),*a],stderr=subprocess.DEVNULL)
        git('init','-q');git('config','user.name','Synthetic test');git('config','user.email','synthetic@example.invalid')
        paths={'tools/census/recsim.py':SOURCE,'tools/simcheck_runtime.py':INSTALLER}
        paths.update({'tools/'+p:('synthetic paired '+p).encode() for p in runtime.PAIRED})
        for p,data in paths.items():
            dest=repo/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        git('add','--',*paths);git('commit','-qm','synthetic pinned package')
        first=git('rev-parse','HEAD').decode().strip()
        (repo/'marker.txt').write_text('later clean HEAD')
        git('add','--','marker.txt');git('commit','-qm','synthetic later HEAD')
        out=self.root/'prepared';m=runtime.prepare(repo,first,out)
        self.assertEqual(m['commit'],first);self.assertEqual((out/'recsim.py').read_bytes(),SOURCE)
        self.assertNotEqual(first,git('rev-parse','HEAD').decode().strip())
        (repo/'tools/census/recsim.py').write_bytes(b'loose peer work')
        with self.assertRaisesRegex(ValueError,'clean'):runtime.prepare(repo,first,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
        with self.assertRaisesRegex(ValueError,'exact'):runtime.prepare(repo,'HEAD',self.root/'bad2')
        self.assertFalse((self.root/'bad2').exists())


if __name__=='__main__':unittest.main()
