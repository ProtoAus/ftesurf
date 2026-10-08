#!/usr/bin/env python3
"""Copied snapshot/schema controls; not authored movement trajectories."""
import argparse
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from offramp_shape import CAP, CHECKS, DICT_CAP, compare, grade, parse
from offramp_shape_smoke import instrument
from offramp_origin_smoke import prepare as origin_prepare
import test_offramp_origin as origin_tests

ORIGIN_SNAPSHOT = origin_tests.snapshot


def fixture():
    rows = ['OFFRAMPGEOM_CHECK %i %s 1' % (i, name) for i, name in enumerate(CHECKS, 1)]
    rows += [f'OFFRAMPGEOM_SELFTEST {len(CHECKS)} 0', f'OFFRAMPGEOM_BEGIN 2 {CAP} {DICT_CAP}']
    planes = [(1,0,0,200), (-1,0,0,200), (0,1,0,200), (0,-1,0,200),
              (0,0,1,200), (0,0,-1,200), (.8,0,.6,123)]
    emitted = False
    for line in origin_tests.fixture().splitlines():
        rows.append(line)
        if not line.startswith('OFFRAMPORIGIN_CONTACT '):
            continue
        r = line.split()[1:]
        if not emitted:
            rows.append('OFFRAMPGEOM_SHAPE 1 1 7 -200 -200 -200 200 200 200')
            rows += ['OFFRAMPGEOM_PLANE 1 %i %s' % (i, ' '.join(map(str,p))) for i,p in enumerate(planes)]
            emitted = True
        rows.append(f'OFFRAMPGEOM_CONTACT {r[0]} {r[1]} 1 {r[4]} {r[5]} {r[6]} {r[7]} 0 0 0 0 0 0 1 0 1')
    rows.append('OFFRAMPGEOM_END 10 10 0 1')
    return '\n'.join(rows)+'\n'


def change(text, tag, index, value, pred=lambda r: True):
    lines = text.splitlines()
    token = f'OFFRAMPGEOM_{tag} '
    for i, line in enumerate(lines):
        if token not in line:
            continue
        prefix, tail = line.split(token, 1)
        row = tail.split()
        if not pred(row):
            continue
        row[index] = str(value)
        lines[i] = prefix+token+' '.join(row)
        return '\n'.join(lines)+'\n'
    raise AssertionError('Geometry counterfactual did not ACT')


def controls(text):
    lines = text.splitlines()
    def first(tag):
        return next(l for l in lines if f'OFFRAMPGEOM_{tag} ' in l)
    bad = [(f'missing-{tag}', '\n'.join(l for l in lines if l != first(tag)))
           for tag in ('CHECK','SELFTEST','BEGIN','SHAPE','PLANE','CONTACT','END')]
    bad += [(f'duplicate-{tag}', text+first(tag)+'\n') for tag in ('CHECK','SELFTEST','BEGIN','SHAPE','PLANE','CONTACT','END')]
    bad += [('unknown-tag', text+'OFFRAMPGEOM_UNKNOWN 1\n'),
            ('explicit-abort', text+'OFFRAMPGEOM_ABORT shape-table-cap\n'),
            ('malformed', text+'OFFRAMPGEOM_PLANE 1\n'),
            ('failed-check', text.replace('whole-brush-copy 1','whole-brush-copy 0')),
            ('selftest-failure', text.replace(f'OFFRAMPGEOM_SELFTEST {len(CHECKS)} 0',f'OFFRAMPGEOM_SELFTEST {len(CHECKS)} 1'))]
    # Select a COMPLETE shape/plane, not a capped shape, for acted mutations.
    rows = parse(text)
    pid = next(w[0] for tag,w in rows if tag == 'SHAPE' and w[1] == '1')
    for label,tag,index,value in [('version','BEGIN',0,1), ('side-cap','BEGIN',1,CAP+1),
                                ('dict-cap','BEGIN',2,DICT_CAP+1), ('payload','SHAPE',0,999999),
                                ('shape-status','SHAPE',1,4), ('negative-sides','SHAPE',2,-1),
                                ('too-few-sides','SHAPE',2,3), ('complete-over-cap','SHAPE',2,CAP+1),
                                ('cap-without-overflow','SHAPE',1,2), ('nonfinite-bounds','SHAPE',3,'nan'),
                                ('reversed-bounds','SHAPE',3,1e30), ('wrong-plane-payload','PLANE',0,999999),
                                ('plane-ordinal','PLANE',1,999), ('nonfinite-normal','PLANE',2,'nan'),
                                ('non-unit-normal','PLANE',2,99), ('nonfinite-dist','PLANE',5,'inf'),
                                ('ordinal','CONTACT',0,-1), ('tick','CONTACT',1,-1),
                                ('undefined-payload','CONTACT',2,999999), ('leaf','CONTACT',3,-1),
                                ('rootleaf','CONTACT',4,-1), ('depth','CONTACT',5,99),
                                ('contents','CONTACT',6,0), ('nonfinite-pose','CONTACT',7,'inf'),
                                ('nonfinite-scale','CONTACT',13,'nan'), ('capsule-enum','CONTACT',14,2),
                                ('native-enum','CONTACT',15,2), ('fractional-leaf','CONTACT',3,1.5),
                                ('footer-contacts','END',0,-1), ('footer-complete','END',1,-1),
                                ('footer-capped','END',2,-1), ('footer-payloads','END',3,-1)]:
        pred = (lambda r: r[0] == pid) if tag in ('SHAPE','PLANE') else (lambda r: True)
        bad.append((label,change(text,tag,index,value,pred)))
    return bad


def clean(text):
    return '\n'.join(l for l in text.splitlines() if 'OFFRAMPGEOM_' not in l and
                     'OFFRAMPORIGIN_' not in l and
                     ('OFFRAMPBUF_' not in l or 'OFFRAMPBUF_COMPLETE' in l))+'\n'


class Tests(unittest.TestCase):
    def test_positive(self):
        r = grade(fixture(),'unit')
        self.assertEqual(r['winning_brush_snapshot_gates'],'PASS')
        self.assertEqual(r['shape_contact_statuses'],{'copied-world-brush-plane-bound':10})
        self.assertEqual(r['shape_payload_count'],1)
        self.assertEqual(r['physical_exit_acceptance'],'NOT_TESTED')
        self.assertEqual(r['winning_brush_movement_geometry_acceptance'],'NOT_TESTED')
        self.assertEqual(r['losses'][0]['winning_brush_snapshot']['numeric_halfspaces']['matching_runtime_side_indices'],[6])

    def test_counterfactuals(self):
        for name,text in controls(fixture()):
            with self.subTest(name=name),self.assertRaises(AssertionError):
                grade(text,'unit')

    def test_unsupported_valid_metadata_abstains(self):
        for index,value,reason in [(7,1,'transformed-instance-unsupported'), (10,10,'transformed-instance-unsupported'),
                                   (13,2,'instance-scale-unsupported'), (14,1,'capsule-hull-unsupported'),
                                   (15,0,'native-callback-unsupported')]:
            with self.subTest(reason=reason):
                r=grade(change(fixture(),'CONTACT',index,value),'unit')
                self.assertEqual(r['shape_contact_statuses'][reason],1)
                self.assertEqual(r['physical_exit_acceptance'],'NOT_TESTED')
        # A consistently unmatched accepted plane is unknown, not a larger
        # tolerance or a physical departure. All instances share this payload.
        text=change(fixture(),'PLANE',5,124,lambda r:r[1]=='6')
        r=grade(text,'unit')
        self.assertEqual(r['winning_brush_snapshot_gates'],'ABSTAIN')
        self.assertEqual(r['shape_contact_statuses'],{'accepted-plane-unmatched':10})
        # The raw scale0 world convention is explicitly supported; no guessed 1.
        self.assertEqual(grade(change(fixture(),'CONTACT',13,0),'unit')['winning_brush_snapshot_gates'],'PASS')

    def test_whole_shape_cap_abstention(self):
        text=fixture()
        text=change(change(text,'SHAPE',1,2),'SHAPE',2,CAP+1)
        text='\n'.join(l for l in text.splitlines() if 'OFFRAMPGEOM_PLANE' not in l)+'\n'
        text=change(change(text,'END',1,0),'END',2,10)
        r=grade(text,'unit')
        self.assertEqual(r['shape_contact_statuses'],{'whole-shape-cap-abstention':10})
        self.assertEqual(r['winning_brush_snapshot_gates'],'ABSTAIN')
        self.assertFalse(any('numeric_halfspaces' in l['winning_brush_snapshot'] for l in r['losses']))

    def test_static_leaf_inconsistent_copy_refused(self):
        # Two legal complete payloads for the SAME static leaf cannot disagree.
        text=fixture()
        block=['OFFRAMPGEOM_SHAPE 2 1 7 -200 -200 -200 200 200 200']
        for tag,words in parse(text):
            if tag=='PLANE':
                words=words.copy(); words[0]='2'
                if words[1]=='0': words[5]='201'
                block.append('OFFRAMPGEOM_PLANE '+' '.join(words))
        lines=text.splitlines()
        at=next(i for i,l in enumerate(lines) if l.startswith('OFFRAMPGEOM_CONTACT 1 '))
        words=lines[at].split(); words[3]='2'; lines[at]=' '.join(words)
        lines[at:at]=block
        changed=change('\n'.join(lines)+'\n','END',3,2)
        with self.assertRaisesRegex(AssertionError,'static runtime leaf changed'):
            grade(changed,'unit')

    def test_quiet_repeat_and_changed_valid_snapshot(self):
        text=fixture(); quiet=clean(text)
        self.assertEqual(compare(quiet,quiet,text,text,'unit')['repeat_shape_equality'],'PASS')
        changed=change(text,'PLANE',5,201,lambda r:r[1]=='0')
        self.assertEqual(grade(changed,'unit')['winning_brush_snapshot_gates'],'PASS')
        with self.assertRaisesRegex(AssertionError,'repeated winning brush snapshot'):
            compare(quiet,quiet,text,changed,'unit')
        with self.assertRaises(AssertionError):
            compare(quiet+'OFFRAMPGEOM_BEGIN 2 64 32768\n',quiet,text,text,'unit')

    def test_nonbrush_stale_payload_refused(self):
        for index,val in ((3,2),(6,1)):
            text=origin_tests.change(fixture(),index,val)
            if index==3:
                with self.assertRaisesRegex(AssertionError,'non-brush origin promoted'):
                    grade(text,'unit')
            else:
                # Embedded origin with a coherent snapshot remains unsupported.
                text=change(text,'CONTACT',5,1)
                self.assertEqual(grade(text,'unit')['shape_contact_statuses']['embedded-model-unsupported'],1)


def snapshot(engine):
    result=ORIGIN_SNAPSHOT(engine)
    for name in ('offramp_shape_types.h','offramp_shape_native.inc','offramp_shape_selftest.inc'):
        p=engine/'engine/common'/name
        import hashlib
        result[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return result


def installer_controls(engine,primary):
    before = snapshot(engine)
    for name in ('offramp_shape_types.h','offramp_shape_native.inc','offramp_shape_selftest.inc'):
        target = engine/'engine/common'/name
        target.write_text('owned untracked shape collision sentinel\n')
        sentinel = snapshot(engine)
        try:
            try: instrument(engine)
            except RuntimeError: assert snapshot(engine) == sentinel
            else: raise AssertionError('Shape installer overwrote include')
        finally: target.unlink()
        assert snapshot(engine) == before
        print('PASS shape include refusal:',name)
    prepared = origin_prepare(engine)
    path = engine/'engine/common/offramp_buffer_native.inc'
    prepared[path] = prepared[path].replace('OFFRAMPBUF_END','DELIBERATELY_MISSING_GENERATED_ANCHOR')
    with patch('offramp_shape_smoke.origin_prepare',return_value=prepared):
        try: instrument(engine)
        except RuntimeError: assert snapshot(engine) == before
        else: raise AssertionError('Shape installer accepted missing generated seam')
    print('PASS shape late generated-anchor refusal, no files changed')
    with patch('test_offramp_origin.snapshot',side_effect=snapshot), patch('test_offramp_origin.instrument',side_effect=instrument):
        origin_tests.installer_controls(engine,primary)


def acted_controls(arms):
    a=json.loads(arms.read_text())
    texts={k:Path(v['log']).read_text(errors='replace') for k,v in a.items()}
    result=compare(*(texts[k] for k in ('clean','off','on','repeat')),a['on']['map'])
    assert result['winning_brush_snapshot_gates']=='PASS'
    bad=controls(texts['on'])
    for name,copy in bad:
        try:grade(copy,a['on']['map'])
        except AssertionError:continue
        raise AssertionError(f'Acted shape counterfactual accepted: {name}')
    print(f'{len(bad)+1} acted shape reader controls, zero failed; four-arm shape equality PASS')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms',type=Path)
    ap.add_argument('--installer-engine',type=Path)
    ap.add_argument('--primary-engine',type=Path)
    a=ap.parse_args()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not r.wasSuccessful():raise SystemExit(1)
    if a.installer_engine:
        if not a.primary_engine:ap.error('--installer-engine requires --primary-engine')
        installer_controls(a.installer_engine,a.primary_engine)
    if a.arms:acted_controls(a.arms)


if __name__=='__main__':main()
