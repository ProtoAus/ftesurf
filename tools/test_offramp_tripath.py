#!/usr/bin/env python3
"""Independent schema/installer units + optional ACTED native path falsifiers."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

import offramp_tripath as path
import offramp_tripath_smoke as installer

ARMS = None


class Units(unittest.TestCase):
    def test_schema_nonfinite_unknown_and_source_refuse(self):
        for text in ('OFFRAMPTRIPATH_UNKNOWN 1', 'OFFRAMPTRIPATH_END 0 0',
                     'OFFRAMPTRIPATH_END nan', 'OFFRAMPTRIPATH_END 0.5',
                     'OFFRAMPTRIPATH_BEGIN 1 0 32 44 0 '+'0'*64):
            with self.assertRaises(AssertionError): path.parse(text)

    def test_installer_collision_and_missing_late_seam_write_nothing(self):
        root = Path('unpopulated-readonly-engine')
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=True), patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'overwrite'): installer.instrument(root)
            write.assert_not_called()
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=False), patch.object(installer, 'prior_prepare', return_value={root/'engine/common/pm_source.c': 'missing late native function'}), patch.object(Path, 'write_text') as write:
            with self.assertRaises(RuntimeError): installer.instrument(root)
            write.assert_not_called()

    def test_existing_report_refuses_before_read_or_write(self):
        with patch.object(sys, 'argv', ['path', '--arms', 'absent', '--output', 'existing']), patch.object(Path, 'exists', return_value=True), patch.object(path, 'load_arms') as load, patch.object(Path, 'open') as opened:
            with self.assertRaises(SystemExit) as error: path.main()
            self.assertEqual(error.exception.code, 2); load.assert_not_called(); opened.assert_not_called()


@unittest.skipUnless(ARMS, 'Retained native arms not supplied; NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = path.load_arms(ARMS)
        cls.result = path.compare(*cls.texts)
        cls.prior = cls.result['prior_plane_set_report']['prior_pm_report']
        cls.blocks = re.findall(r'OFFRAMPBEVPM_CASE [0-9]+ .*?(?=OFFRAMPBEVPM_CASE_END)', path.pm.split(cls.texts[3])[1], re.S)

    def test_counts_real_raw_loss_clear_and_zero_fraction_clips_acted(self):
        self.assertEqual([c['attempt_count'] for c in self.result['cases']], [44, 32, 38])
        self.assertEqual([c['validation_count'] for c in self.result['cases']], [20, 32, 26])
        self.assertEqual(self.result['actual_raw_loss_first_move'], 'CAPTURED_NATIVE_AND_IDEAL_CLEAR')
        hits = [r for c in self.result['cases'] for call in c['calls'] for r in call['attempts'] if r[24] < 1]
        zeros = [r for r in hits if r[24] == 0]
        self.assertEqual(len(hits), 18); self.assertEqual(len(zeros), 14)
        self.assertTrue(all(r[5:8] == r[34:37] and r[25] > 0 for r in zeros))
        self.assertEqual(self.result['physical_exit_acceptance'], 'NOT_TESTED')
        self.assertEqual(self.result['general_native_path_acceptance'], 'ABSTAIN')

    def test_every_actual_new_capture_numeric_fault_independently_refuses(self):
        acted = 0
        for case, block in enumerate(self.blocks):
            lines = [l[l.find('OFFRAMPTRIPATH_'):] for l in block.splitlines() if 'OFFRAMPTRIPATH_' in l]
            for line in lines:
                words = line.split(); tag = words[0].removeprefix('OFFRAMPTRIPATH_')
                for column in range(1, len(words)):
                    if tag == 'BEGIN' and column == 6: continue
                    changed = words.copy(); changed[column] = str(float(words[column])+.125)
                    mutated = block.replace(line, ' '.join(changed), 1)
                    self.assertNotEqual(mutated, block)
                    with self.subTest(case=case, tag=tag, row=words[1], column=column), self.assertRaises(AssertionError):
                        path.grade_case(mutated, case, self.prior['cases'][case])
                    acted += 1
        self.assertEqual(acted, 10524)
        print(f'{acted} ACTED numeric native path refusals in independent NEW gate, 0 failed')

    def test_each_native_path_row_missing_or_duplicated_refuses(self):
        acted = 0
        for case, block in enumerate(self.blocks):
            lines = [l for l in block.splitlines() if 'OFFRAMPTRIPATH_' in l]
            for line in lines:
                for replacement in ('', line+'\n'+line):
                    bad = block.replace(line, replacement, 1)
                    self.assertNotEqual(bad, block)
                    with self.subTest(case=case, prefix=line.split()[0]), self.assertRaises(AssertionError):
                        path.grade_case(bad, case, self.prior['cases'][case])
                    acted += 1
        self.assertEqual(acted, 1008)
        print(f'{acted} ACTED path-row deletion/duplication refusals, 0 failed')

    def test_mirrored_time_mutant_passes_prior_and_repeat_then_new_gate_refuses(self):
        line = next(l[l.find('OFFRAMPTRIPATH_ATTEMPT'):] for l in self.blocks[0].splitlines() if 'OFFRAMPTRIPATH_ATTEMPT 11 ' in l)
        words = line.split(); words[5] = '.01'  # plausible residual time, not an integer/schema fault
        texts = [t.replace(line, ' '.join(words)) for t in self.texts]
        self.assertEqual(path.clip.compare(*texts), self.result['prior_plane_set_report'])
        self.assertEqual(path.parse(texts[3]), path.parse(texts[4]))
        with self.assertRaisesRegex(AssertionError, 'time-left'): path.compare(*texts)

    def test_capture_quiet_outside_envelope_overflow_unsupported_and_source_refuse(self):
        line = next(l[l.find('OFFRAMPTRIPATH_CALL'):] for l in self.blocks[0].splitlines() if 'OFFRAMPTRIPATH_CALL 0 ' in l)
        for arm in (0, 1, 2):
            texts = self.texts.copy(); texts[arm] += '\n'+line
            with self.assertRaises(AssertionError): path.compare(*texts)
        texts = self.texts.copy(); texts[3] += '\n'+line
        with self.assertRaises(AssertionError): path.compare(*texts)
        for column in (3, 4, 6, 7, 20, 21, 22, 23, 26):
            words = line.split(); words[column+1] = '1'
            with self.assertRaises(AssertionError): path.grade_case(self.blocks[0].replace(line, ' '.join(words)), 0, self.prior['cases'][0])
        begin = next(l[l.find('OFFRAMPTRIPATH_BEGIN'):] for l in self.blocks[0].splitlines() if 'OFFRAMPTRIPATH_BEGIN' in l)
        for bad in (begin.replace('44 0 ', '44 1 '), begin.replace(installer.source_digest(), '0'*64)):
            with self.assertRaises(AssertionError): path.grade_case(self.blocks[0].replace(begin, bad), 0, self.prior['cases'][0])

    def test_manifest_nonfinite_wrong_source_mode_refuse(self):
        arms = json.loads(ARMS.read_text())
        for field, value in (('tripath_source_sha256', '0'*64), ('bevpm_source_sha256', '0'*64), ('capture', True), ('oracle', 0)):
            bad = copy.deepcopy(arms); bad['on'][field] = value
            with patch.object(Path, 'read_text', return_value=json.dumps(bad)), patch.object(path.pm, 'load_arms', return_value=(self.texts, [])), self.assertRaises(AssertionError): path.load_arms(ARMS)
        line = next(l[l.find('OFFRAMPTRIPATH_ATTEMPT'):] for l in self.blocks[0].splitlines() if 'OFFRAMPTRIPATH_ATTEMPT 0 ' in l)
        for value in ('nan', 'inf', '-inf', 'nonnumeric'):
            words = line.split(); words[5] = value
            with self.assertRaises(AssertionError): path.parse(' '.join(words))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    a, rest = ap.parse_known_args(); ARMS = a.native_arms
    Native.__unittest_skip__ = not bool(ARMS)
    unittest.main(argv=[__file__, *rest])
