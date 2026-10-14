"""Mutations of the cold original-row and exact-stage publication oracle."""
import copy
import unittest
import os
import json
import tempfile
from unittest.mock import patch
from pathlib import Path

import test_update_native_cold_superset as cold
from test_update_native_staging_windows import journal


class ColdSupersetTests(unittest.TestCase):
    def setUp(self):
        self.files = {'first': dict(hash='a'*64, size=7, exec=False),
                      'last': dict(hash='b'*64, size=9, exec=False)}
        self.paths = list(self.files)
        self.original = journal(self.files, self.paths, '0.1.25', 2)

    def grade(self, actual, before=False):
        return cold.authority_grade(actual, self.files, self.paths, '0.1.25', 2, before, 'last')

    def test_original_rows_pass(self):
        self.assertFalse(self.grade(self.original))

    def test_reduced_candidate_refuses(self):
        with self.assertRaises(AssertionError):
            self.grade(journal(self.files, ['last'], '0.1.25', 2))

    def test_exact_before_reduction_acts(self):
        self.assertTrue(self.grade(journal(self.files, ['last'], '0.1.25', 2), True))

    def test_before_must_act_not_full(self):
        with self.assertRaises(AssertionError): self.grade(self.original, True)

    def test_each_tuple_budget_version_order_extra_mutation_refuses(self):
        mutations = []
        for key, value in [('p','wrong'), ('h','c'*64), ('s',8), ('x',1)]:
            changed = copy.deepcopy(self.original); changed['files'][0][key] = value
            mutations.append(changed)
        for key, value in [('attempts',1), ('version','0.1.24'), ('extra',True)]:
            changed = copy.deepcopy(self.original); changed[key] = value
            mutations.append(changed)
        changed = copy.deepcopy(self.original); changed['files'].reverse(); mutations.append(changed)
        changed = copy.deepcopy(self.original); changed['files'].append(changed['files'][0]); mutations.append(changed)
        for actual in mutations:
            with self.subTest(actual=actual), self.assertRaises(AssertionError): self.grade(actual)

    def test_before_wrong_reduction_refuses(self):
        for paths in ([], ['first'], ['last','last']):
            with self.subTest(paths=paths), self.assertRaises(AssertionError):
                self.grade(journal(self.files, paths, '0.1.25', 2), True)

    def test_partial_closure_ledger_consent_envelope_certificate_mutations_refuse(self):
        with tempfile.TemporaryDirectory(dir=os.environ['FTESURF_TEST_SCRATCH']) as tmp:
            dest = Path(tmp); meta = dest / 'meta'; (meta / 'ingame').mkdir(parents=True)
            expected = {'resolved':b'new', 'pending':b'old', 'protected':b'edit', 'unmanaged':b'guard'}
            ledger = dict(version='0.1.24', files={'resolved':'a', 'pending':'old'})
            seed = expected | {'meta/state.json':json.dumps(ledger).encode(),
                'meta/consent':b'1\n', 'meta/ingame/manifest.json':b'signed'}
            for p,data in seed.items(): (dest / p).write_bytes(data)
            def grade(): cold.grade_state(dest, meta, expected, ledger, b'signed', '0.1.25')
            grade()
            for p,data in seed.items():
                with self.subTest(path=p):
                    (dest / p).write_bytes(b'{}' if p.endswith('.json') else b'mutated')
                    with self.assertRaises(AssertionError): grade()
                    (dest / p).write_bytes(data)
            (meta / 'installed.json').write_bytes(b'signed')
            with self.assertRaises(AssertionError): grade()

    def test_complete_requires_exact_certificate_and_version(self):
        with tempfile.TemporaryDirectory(dir=os.environ['FTESURF_TEST_SCRATCH']) as tmp:
            dest=Path(tmp); meta=dest/'meta'; (meta/'ingame').mkdir(parents=True)
            ledger=dict(version='0.1.25', files={})
            (meta/'state.json').write_text(json.dumps(ledger))
            (meta/'consent').write_bytes(b'1\n')
            (meta/'ingame/manifest.json').write_bytes(b'signed')
            (meta/'installed.json').write_bytes(b'signed')
            cold.grade_state(dest,meta,{},ledger,b'signed','0.1.25',True)
            (meta/'installed.json').write_bytes(b'wrong')
            with self.assertRaises(AssertionError):
                cold.grade_state(dest,meta,{},ledger,b'signed','0.1.25',True)

    def test_attempt3_full_rows_and_reduced_before_are_independent(self):
        original = journal(self.files, self.paths, '0.1.25', 3)
        self.assertFalse(cold.authority_grade(original, self.files, self.paths, '0.1.25', 3, False, 'last'))
        for count in (1,2,4):
            with self.subTest(count=count), self.assertRaises(AssertionError):
                cold.authority_grade(journal(self.files,self.paths,'0.1.25',count),
                                     self.files,self.paths,'0.1.25',3,False,'last')
        reduced=journal(self.files,['last'],'0.1.25',3)
        self.assertTrue(cold.authority_grade(reduced,self.files,self.paths,'0.1.25',3,True,'last'))
        with self.assertRaises(AssertionError):
            cold.authority_grade(reduced,self.files,self.paths,'0.1.25',3,False,'last')

    def test_exhausted_refusal_rejects_authority_ledger_install_stage_and_temp_mutations(self):
        with tempfile.TemporaryDirectory(dir=os.environ['FTESURF_TEST_SCRATCH']) as tmp:
            dest=Path(tmp); meta=dest/'.ftesurf-updater'; stage=meta/'ingame/staged'; stage.mkdir(parents=True)
            expected={'resolved':b'new','pending':b'old','protected':b'edit','unmanaged':b'guard'}
            ledger=dict(version='0.1.24',files={'resolved':'a','pending':'old'})
            ledger_bytes=json.dumps(ledger).encode()
            authority=json.dumps(journal(self.files,self.paths,'0.1.25',3)).encode()
            seed=expected | {'.ftesurf-updater/state.json':ledger_bytes,
                '.ftesurf-updater/consent':b'1\n','.ftesurf-updater/ingame/manifest.json':b'signed',
                '.ftesurf-updater/ingame/journal.json':authority,
                '.ftesurf-updater/ingame/staged/pending':b'repaired',
                '.ftesurf-updater/ingame/staged/unmanaged.tmp':b'sibling'}
            for p,data in seed.items(): (dest/p).write_bytes(data)
            def grade(): cold.exhaustion_grade(dest,meta,expected,ledger,b'signed','0.1.25',
                                              authority,ledger_bytes,{'pending':b'repaired','unmanaged.tmp':b'sibling'})
            grade()
            for p,data in seed.items():
                with self.subTest(path=p):
                    (dest/p).write_bytes(b'{}' if p.endswith('.json') else b'mutated')
                    with self.assertRaises(AssertionError): grade()
                    (dest/p).write_bytes(data)
            for extra in ('ingame/journal.tmp','installed.json','ingame/staged/extra'):
                with self.subTest(extra=extra):
                    (meta/extra).write_bytes(b'new')
                    with self.assertRaises(AssertionError): grade()
                    (meta/extra).unlink()

    def test_every_stage_survivor_removal_byte_change_and_extra_refuses(self):
        expected = {'a':b'signed', 'b':b'corrupt', 'unmanaged.tmp':b'sibling'}
        with patch.object(cold, 'stage_map', return_value=expected):
            cold.stages_grade(Path('unused'), expected)
        mutants = [expected | {'extra':b'new'}]
        for name in expected:
            removed = dict(expected); del removed[name]; mutants.append(removed)
            mutants.append(expected | {name:b'mutated'})
        for actual in mutants:
            with self.subTest(actual=actual), patch.object(cold, 'stage_map', return_value=actual), self.assertRaises(AssertionError):
                cold.stages_grade(Path('unused'), expected)


if __name__ == '__main__': unittest.main()
