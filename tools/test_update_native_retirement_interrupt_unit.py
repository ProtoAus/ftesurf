import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from test_update_native_retirement_interrupt import (bind_code, interrupted_grade,
    before_completed_grade, first_resolved_hash)
from test_update_native_retirement_windows import prepare, byte_hash
from test_update_native_journal_interrupt import grade_events


class Binding(unittest.TestCase):
    def fixture(self):
        base, rva = 0x100000, 0x1000
        pre, target = base+rva+20, base+rva+100
        call = b'\xe8'+(target-pre-5).to_bytes(4,'little',signed=True)
        code=bytearray(128)
        code[10:15]=b'\xba\x03\x00\x00\x00';code[20:25]=call;code[25]=0x85
        listing=f'{base+rva:x} t QKU_FSPurgeObject.part.0\n{target:x} T FS_Remove\n'
        assembly=(f'{base+rva:x} <QKU_FSPurgeObject.part.0>:\n'
            f' {base+rva+10:x}: ba 03 00 00 00 mov $0x3,%edx\n'
            f' {pre:x}: '+call.hex(' ')+f' call {target:x} <FS_Remove>\n')
        return [base,rva,bytes(code),listing,assembly]

    def test_exact_call_and_root(self):
        b=bind_code(*self.fixture())
        self.assertEqual((b['pre_rva'],b['post_rva'],b['abi']),(0x1014,0x1019,'fs'))

    def test_bad_call_bytes(self):
        a=self.fixture();c=bytearray(a[2]);c[21]^=1;a[2]=bytes(c)
        with self.assertRaisesRegex(AssertionError,'PE/disassembly'):bind_code(*a)

    def test_wrong_target(self):
        a=self.fixture();a[3]=a[3].replace('101064 T','101065 T')
        with self.assertRaisesRegex(AssertionError,'actual call target'):bind_code(*a)

    def test_wrong_system_root(self):
        a=self.fixture();a[2]=a[2][:11]+b'\x04'+a[2][12:]
        with self.assertRaisesRegex(AssertionError,'FS_SYSTEM argument'):bind_code(*a)

    def test_duplicate_call(self):
        a=self.fixture();a[4]+=a[4].splitlines(True)[-1]
        with self.assertRaisesRegex(AssertionError,'unique actual'):bind_code(*a)

    def test_missing_purge(self):
        a=self.fixture();a[3]=a[3].replace('QKU_FSPurgeObject.part.0','QKU_Other')
        with self.assertRaisesRegex(AssertionError,'unique purge'):bind_code(*a)

    def test_missing_remove(self):
        a=self.fixture();a[3]=a[3].replace(' FS_Remove',' FS_Other')
        with self.assertRaisesRegex(AssertionError,'unique real'):bind_code(*a)

    def test_receipt_requires_real_result_and_order(self):
        b=bind_code(*self.fixture())
        events=[dict(event='child',pid=7),dict(event='before',rva=b['pre_rva'],thread=8,paths_verified=True),
            dict(event='after',rva=b['post_rva'],thread=8,native_result=1,leaf_absent=True,journal_present=True),
            dict(event='interrupt',code=86,hits=2),dict(event='exit',pid=7,code=86,hits=2)]
        self.assertEqual(grade_events(events,b,'crash-after'),(7,86))
        for index,key,value in [(2,'native_result',0),(2,'thread',9),(0,'pid',6)]:
            bad=copy.deepcopy(events);bad[index][key]=value
            with self.assertRaises(AssertionError):grade_events(bad,b,'crash-after')


class Oracle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('FTESURF_TEST_SCRATCH'))
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.count=0
        self.payload={'ftesurf/gfx/crosshairs/xhair1.png':b'new one',
            'ftesurf/gfx/crosshairs/xhair2.png':b'new two',
            'ftesurf/maps/zones/local/owned.json':b'new managed zone',
            'ftesurf/gfx/untouched.png':b'untouched signed bytes'}
        self.files={p:dict(hash=byte_hash(b),size=len(b),exec=False) for p,b in self.payload.items()}

    def actor(self, removed=False, before=False, complete=False):
        self.count+=1
        f=prepare(self.root,str(self.count),'unique',False,b'unit unsigned envelope',
                  dict(version='0.1.25'),self.files,self.payload)
        state=copy.deepcopy(f['ledger']);state['files'][f['resolved']]=self.files[f['resolved']]['hash']
        (f['dest']/f['resolved']).write_bytes(self.payload[f['resolved']])
        if complete:
            state['version']=f['version'];state['files'][f['pending']]=self.files[f['pending']]['hash']
            (f['dest']/f['pending']).write_bytes(self.payload[f['pending']])
            (f['meta']/'installed.json').write_bytes(f['signed'])
            (f['meta']/'ingame/journal.json').unlink()
            (f['meta']/'ingame/staged'/self.files[f['pending']]['hash']).unlink()
        else:
            rows=[r for r in f['rows'] if r['p']==f['pending']] if before else f['rows']
            (f['meta']/'ingame/journal.json').write_text(json.dumps(dict(attempts=2,version=f['version'],files=rows)))
        (f['meta']/'state.json').write_text(json.dumps(state))
        (f['meta']/'ingame/journal.tmp').unlink()
        if removed:(f['meta']/'ingame/staged'/first_resolved_hash(f)).unlink()
        return f

    def test_interrupted_exact_partial_content_both_boundaries(self):
        for before in (False,True):
            for removed in (False,True):interrupted_grade(self.actor(removed,before),removed,before)

    def test_interrupted_ledger_version_and_hash_mutants(self):
        for field in ('version','hash'):
            f=self.actor();p=f['meta']/'state.json';state=json.loads(p.read_text())
            if field=='version':state['version']=f['version']
            else:state['files'][f['zone']]='f'*64
            p.write_text(json.dumps(state))
            with self.assertRaisesRegex(AssertionError,'ledger'):interrupted_grade(f,False,False)

    def test_interrupted_consent_mutant(self):
        f=self.actor();(f['meta']/'consent').write_bytes(b'1\n')
        with self.assertRaisesRegex(AssertionError,'consent'):interrupted_grade(f,False,False)

    def test_interrupted_unrelated_signed_content_mutant(self):
        f=self.actor();(f['dest']/'ftesurf/gfx/untouched.png').write_bytes(b'silent wrong bytes')
        with self.assertRaisesRegex(AssertionError,'whole signed closure'):interrupted_grade(f,False,False)

    def test_before_completion_exact_orphans_both_boundaries(self):
        for removed in (False,True):before_completed_grade(self.actor(removed,True,True),removed)

    def test_before_completion_ledger_mutant(self):
        f=self.actor(False,True,True);p=f['meta']/'state.json';state=json.loads(p.read_text())
        state['files'][f['zone']]='e'*64;p.write_text(json.dumps(state))
        with self.assertRaisesRegex(AssertionError,'ledger'):before_completed_grade(f,False)

    def test_before_completion_consent_and_closure_mutants(self):
        for field in ('consent','closure'):
            f=self.actor(False,True,True)
            p=f['meta']/'consent' if field=='consent' else f['dest']/'ftesurf/gfx/untouched.png'
            p.write_bytes(b'wrong')
            with self.assertRaises(AssertionError):before_completed_grade(f,False)

    def test_before_completion_exact_stage_bytes_and_membership(self):
        for field in ('extra','bytes','absent'):
            f=self.actor(False,True,True);stage=f['meta']/'ingame/staged'
            p=stage/first_resolved_hash(f)
            if field=='extra':(stage/('e'*64)).write_bytes(b'extra')
            elif field=='bytes':p.write_bytes(b'wrong')
            else:p.unlink()
            with self.assertRaisesRegex(AssertionError,'exact before completed stage'):before_completed_grade(f,False)


if __name__=='__main__':unittest.main()
