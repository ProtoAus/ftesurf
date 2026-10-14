#!/usr/bin/env python3
"""Source-bound process interruption immediately around REAL staged FS_Remove.

Never a power-loss/hostile-path-swap claim. Historical runners/graders immutable.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess

from test_update_native_journal import preflight_paths, sha, snapshot
from test_update_native_journal_deferred import helper_identity, pe_text
from test_update_native_journal_initial import cold_phase
from test_update_native_journal_interrupt import interrupt
from test_update_native_journal_live import retire_runtime
from test_update_native_retirement_windows import prepare, grade, semantic_phase
import test_update_native_staging_windows as staging


def bind_code(base, text_rva, code, listing, disassembly):
    removes = re.findall(r'^([0-9a-f]+) [tT] FS_Remove$', listing, re.M)
    assert len(removes) == 1, 'unique real FS_Remove symbol'
    names = re.findall(r'^([0-9a-f]+) [tT] (QKU_FSPurgeObject(?:\.part\.0)?)$', listing, re.M)
    assert names and len({n for _, n in names}) == len(names), 'unique purge symbols'
    candidates = []
    for address, name in names:
        sections = re.findall(r'^[0-9a-f]+ <' + re.escape(name) +
            r'>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)', disassembly, re.M | re.S)
        assert len(sections) == 1, 'one inspected purge body'
        calls = re.findall(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})\s+call\s+[^\n]*<FS_Remove>$', sections[0], re.M)
        for at, encoded in calls:
            candidates.append((name, int(at, 16), bytes.fromhex(encoded), sections[0]))
    assert len(candidates) == 1, 'unique actual staged removal call'
    name, pre, encoded, body = candidates[0]
    assert len(encoded) == 5 and encoded[0] == 0xe8, 'direct source-bound FS_Remove call'
    assert pre + 5 + int.from_bytes(encoded[1:], 'little', signed=True) == int(removes[0],16), 'actual call target'
    off = pre - base - text_rva
    assert 0 <= off < len(code)-len(encoded)
    assert code[off:off+5] == encoded, 'PE/disassembly call bytes'
    # Real root ABI, not a guessed Win32 DeleteFile import/API substitute.
    assert b'\xba\x03\x00\x00\x00' in code[max(0,off-24):off], 'FS_SYSTEM argument'
    assert re.search(r'mov\s+\$0x3,%edx', body), 'inspected x64 FS_SYSTEM ABI'
    post = pre + 5
    assert code[off+5] != 0xcc
    return dict(pre_rva=pre-base, post_rva=post-base, pre_byte=encoded[0],
                post_byte=code[off+5], abi='fs', cold_caller_rva=0, purge_symbol=name)


def bind(engine, symbols, nm, objdump):
    base, rva, text = pe_text(engine)
    assert pe_text(symbols) == (base, rva, text), 'immutable companion text mismatch'
    listing = subprocess.check_output([str(nm), '-n', str(symbols)], text=True)
    assembly = subprocess.check_output([str(objdump), '-d', str(symbols)], text=True)
    return bind_code(base, rva, text, listing, assembly) | dict(engine_sha256=sha(engine.read_bytes()),
        symbols_sha256=sha(symbols.read_bytes()), text_sha256=sha(text))


def first_resolved_hash(f):
    # Seed uses one corrupt pending row. All other authorized stages are valid;
    # the actual first deletion must follow row order, including preserved zone.
    return next(r['h'] for r in f['rows'] if r['p'] != f['pending'])


def content_grade(f, complete):
    expected = copy.deepcopy(f['ledger'])
    expected['files'][f['resolved']] = f['files'][f['resolved']]['hash']
    if complete:
        expected['version'] = f['version']
        expected['files'][f['pending']] = f['files'][f['pending']]['hash']
    assert json.loads((f['meta']/'state.json').read_text()) == expected, 'exact partial/complete ledger'
    assert (f['meta']/'consent').read_bytes() == f['seed']['.ftesurf-updater/consent'], 'unchanged consent'
    assert (f['meta']/'ingame/manifest.json').read_bytes() == f['signed'], 'exact signed manifest'
    for path in f['payload']:
        data = f['payload'][path] if path == f['resolved'] or (complete and path == f['pending']) else f['seed'][path]
        assert (f['dest']/path).read_bytes() == data, 'whole signed closure: '+path
    for path,data in f['sentinels'].items():
        assert (f['dest']/path).read_bytes() == data, 'protected/unmanaged identity: '+path


def interrupted_grade(f, removed, before):
    content_grade(f, False)
    stage = f['meta'] / 'ingame/staged'
    original = {Path(p).name: b for p,b in f['seed'].items()
                if p.startswith('.ftesurf-updater/ingame/staged/')}
    if removed:
        del original[first_resolved_hash(f)]
    assert {p.name:p.read_bytes() for p in stage.iterdir()} == original, 'actual removal count/other survivors'
    j = json.loads((f['meta'] / 'ingame/journal.json').read_text())
    rows = [r for r in f['rows'] if r['p'] == f['pending']] if before else f['rows']
    assert j == dict(attempts=2, version=f['version'], files=rows), 'interrupted authority/budget'
    survivors = {r['h'] for r in f['rows']} & original.keys()
    if not before:
        assert survivors <= {r['h'] for r in j['files']}, 'every surviving candidate must remain named'
    else:
        assert survivors - {r['h'] for r in j['files']}, 'before dropped resolved-authority defect must ACT'
    for path,data in f['sentinels'].items():
        assert (f['dest']/path).read_bytes() == data, 'protected interruption identity'
    assert (f['dest']/f['resolved']).read_bytes() == f['payload'][f['resolved']], 'partial install ACT'
    assert (f['dest']/f['pending']).read_bytes() == staging.OLD
    assert not (f['meta']/'installed.json').exists()
    assert (f['meta']/'ingame/manifest.json').read_bytes() == f['signed']
    assert not (f['meta']/'ingame/journal.tmp').exists(), 'published temp consumed'
    return dict(removed=int(removed), attempts=2, all_survivors_named=not before,
                authority_sha256=sha((f['meta']/'ingame/journal.json').read_bytes()),
                stage_sha256={p:sha(b) for p,b in original.items()})


def before_completed_grade(f, removed):
    content_grade(f, True)
    stage = f['meta']/'ingame/staged'
    expected = {Path(p).name:b for p,b in f['seed'].items()
                if p.startswith('.ftesurf-updater/ingame/staged/')}
    expected.pop(f['files'][f['pending']]['hash'])
    if removed: expected.pop(first_resolved_hash(f))
    assert {p.name:p.read_bytes() for p in stage.iterdir()} == expected, 'exact before completed stage map'
    assert not (f['meta']/'ingame/journal.tmp').exists(), 'before published temp consumed'
    assert not (f['meta']/'ingame/journal.json').exists()
    assert (f['meta']/'installed.json').read_bytes() == f['signed']
    assert (f['dest']/f['pending']).read_bytes() == f['payload'][f['pending']]
    named = {r['h'] for r in f['rows'] if r['p'] != f['pending']}
    survivors = {p.name:p.read_bytes() for p in stage.iterdir()}
    orphaned = named & survivors.keys()
    assert orphaned, 'before completed outside-authority orphan detector must ACT'
    for h in orphaned:
        assert survivors[h] == f['stage'][h]
    for path,data in f['sentinels'].items():assert (f['dest']/path).read_bytes()==data
    return dict(before_defect_acted=True, orphaned=sorted(orphaned))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine','symbols','helper','feed','runtime-root','evidence'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, required=True, action='append')
    ap.add_argument('--nm', type=Path, default=Path('C:/msys64/ucrt64/bin/nm.exe'))
    ap.add_argument('--objdump', type=Path, default=Path('C:/msys64/ucrt64/bin/objdump.exe'))
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine,symbols = (p.resolve(strict=True) for p in (a.engine,a.symbols))
    helper,helper_hash = helper_identity(a.helper)
    binding = bind(engine,symbols,a.nm,a.objdump)
    root,evidence = preflight_paths(a.runtime_root,a.evidence)
    signed,manifest,files,payload = staging.load_inputs(a.feed,a.objects)
    root.mkdir(parents=True);evidence.mkdir(parents=True)
    (root/'OWNER.md').write_text('Owned actual staged-removal debugger fixtures; retire only after complete receipts/export/job0.\n')
    result = dict(status='FAIL',binding=binding,helper_sha256=helper_hash,
                  harness_sha256=sha(Path(__file__).read_bytes()),feed_sha256=sha(signed),
                  expect_before=a.expect_before,cases=[])
    dest=None
    oldhash=os.environ.get('OWNED_RETIRE_HASH')
    try:
        for protected_first in (False,True):
            for mode in ('crash-before','crash-after'):
                name=('protected-first-' if protected_first else 'content-first-')+mode
                dest=root/name
                f=prepare(root,name,'unique',protected_first,signed,manifest,files,payload)
                phase=evidence/name/'interrupt'
                os.environ['OWNED_RETIRE_HASH']=first_resolved_hash(f)
                interrupt(engine,helper,binding,dest,phase,mode)
                semantic_phase(phase,lambda:interrupted_grade(f,mode=='crash-after',a.expect_before))
                # Repair immediately: the admitted interruption already bumped2;
                # subject must persist3, finish and discharge OS-confirmed missing.
                p=f['meta']/'ingame/staged'/files[f['pending']]['hash']
                p.write_bytes(payload[f['pending']])
                f['stage'][files[f['pending']]['hash']] = payload[f['pending']]
                (evidence/name/'fixture-repair.json').write_text(json.dumps(dict(
                    path=f['pending'], sha256=sha(payload[f['pending']]))))
                phase=evidence/name/'released-repaired'
                cold_phase(engine,dest,phase)
                semantic_phase(phase,lambda:before_completed_grade(f,mode=='crash-after') if a.expect_before else grade(f,True,3))
                snapshot(dest,evidence/name/'final')
                result['cases'].append(name)
                print('PASS actual removal',name,'before' if a.expect_before else 'subject',flush=True)
        assert sha(engine.read_bytes())==binding['engine_sha256']
        result['status']='PASS'
    except BaseException as error:
        result['error']=repr(error)
        raise
    finally:
        if oldhash is None:os.environ.pop('OWNED_RETIRE_HASH',None)
        else:os.environ['OWNED_RETIRE_HASH']=oldhash
        retire_runtime(root,evidence,result,dest)


if __name__=='__main__':main()
