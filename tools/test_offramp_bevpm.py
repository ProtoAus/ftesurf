#!/usr/bin/env python3
"""Independent bevel PM algebra + optional ACTED native-derived falsifiers."""
import argparse
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import offramp_bevpm as pm
import offramp_bevpm_smoke as installer
from offramp_motion import joint_overlap
from offramp_triangle import sweep
from test_offramp_triangle import prism_halfspaces

NATIVE_ARMS = None


class Units(unittest.TestCase):
    def test_hand_derived_standing_edge_interval_and_bias(self):
        g = pm.entry_check(pm.VERTICES, [-8, 64, -60], [-8, 64, -68], .5-1/32/4.8, [0, .8, .6], 0, .5)
        self.assertAlmostEqual(g['enter'], .5, places=6)
        self.assertEqual(len(g['entry_planes']), 1)
        self.assertTrue(pm.close(g['entry_planes'][0], [0, .8, .6, 0], 1e-6))

    def test_independent_joint_before_after_and_partial_edge(self):
        planes = prism_halfspaces(pm.VERTICES, 4)
        for p, want in (([-8, 64, -63.9], False), ([-8, 64, -64.1], True), ([-19, 64, -64.1], False)):
            sat = sweep(pm.VERTICES, p, p, pm.MINS, pm.MAXS)['intersects']
            joint = joint_overlap(planes, [x+a for x, a in zip(p, pm.MINS)], [x+a for x, a in zip(p, pm.MAXS)])
            self.assertEqual(sat, want); self.assertEqual(joint, want)

    def test_wrong_fraction_plane_and_winding_cannot_pass(self):
        for fraction, normal, dist in ((.4, [0, .8, .6], 0), (.5, [0, 0, 1], 0), (.5, [0, .8, .6], 1)):
            with self.assertRaises(AssertionError):
                pm.entry_check(pm.VERTICES, [-8, 64, -60], [-8, 64, -68], fraction, normal, dist)
        with self.assertRaises(AssertionError):
            pm.entry_check(pm.VERTICES[::-1], [-8, 64, -60], [-8, 64, -68], .5, [0, .8, .6], 0)

    def test_fixture_and_seed_are_exact_and_nonfinite_refuse(self):
        f = list(map(str, [0, 0, 1, 2, *(x for v in pm.VERTICES for x in v)]))
        s = list(map(str, [0, *pm.SEED]))
        pm.fixture(f, 0); pm.seed(s, 0)
        for words, fn in ((f, pm.fixture), (s, pm.seed)):
            for value in ('nan', 'inf', '-inf', 'nonnumeric'):
                bad = words.copy(); bad[5] = value
                with self.assertRaises(AssertionError): fn(bad, 0)

    def test_installer_prepares_before_writes_and_refuses_collision(self):
        engine = Path('unpopulated-readonly-test-engine')
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=True), patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'overwrite'): installer.instrument(engine)
            write.assert_not_called()
        prepared = {engine/'engine/common/pm_source.c': 'static void OfframpMotion_f(void);\nMISSING_REQUIRED_LATE_INIT_ANCHOR'}
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=False), patch.object(installer, 'bevel_prepare', return_value=prepared), patch.object(Path, 'write_text') as write:
            with self.assertRaises(RuntimeError): installer.instrument(engine)
            write.assert_not_called()

    def test_envelope_unknown_rows_and_missing_refuse(self):
        for text in ('', 'OFFRAMPBEVPM_UNKNOWN 1', 'OFFRAMPBEVPM_BEGIN 1 1 1 3 32\n',
                     'OFFRAMPBEVPM_BEGIN 1 1 1 3 32\nOFFRAMPBEVPM_END 3\nOFFRAMPBEVPM_END 3'):
            with self.assertRaises(AssertionError): pm.split(text)


@unittest.skipUnless(NATIVE_ARMS, 'No actual retained native arms; skips are NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = pm.load_arms(NATIVE_ARMS)
        cls.result = pm.compare(*cls.texts)
        cls.splits = [pm.split(t) for t in cls.texts]
        cls.report = pm.grade(cls.splits[3][1])
        cls.blocks = re.findall(r'OFFRAMPBEVPM_CASE [0-9]+ .*?(?=OFFRAMPBEVPM_CASE_END)', cls.splits[3][1], re.S)

    def test_actual_actor_removal_off_ghosts_and_repeat(self):
        self.assertEqual(self.result['ramp_ticks'], [list(range(10, 22)), [], list(range(6, 12))])
        self.assertEqual(self.result['raw_loss_ticks'], [22])
        self.assertEqual([len(c['accepted']) for c in self.result['cases']], [12, 0, 6])
        self.assertEqual(self.result['general_triangle_support'], 'ABSTAIN')
        self.assertTrue(all(not sweep(pm.VERTICES, [s+r['contact'][4]*(e-s) for s,e in zip(r['contact'][9:12],r['contact'][12:15])],
                                     [s+r['contact'][4]*(e-s) for s,e in zip(r['contact'][9:12],r['contact'][12:15])], pm.MINS, pm.MAXS)['intersects']
                            for r in self.result['cases'][2]['accepted']))

    def test_actual_copied_contact_stationary_joint_independently_agrees(self):
        checked = 0
        for c in (0, 2):
            for r in self.result['cases'][c]['accepted']:
                vertices, trace = r['copied_winner']['vertices'], r['contact']
                planes = prism_halfspaces(vertices, 4)
                for t in (0, trace[4], *(r['ideal_prism']['enter']+d for d in (-.001, .001) if r['ideal_prism']['enter'] is not None)):
                    p = [s+t*(e-s) for s,e in zip(trace[9:12], trace[12:15])]
                    sat = sweep(vertices, p, p, pm.MINS, pm.MAXS)['intersects']
                    joint = joint_overlap(planes, [x+a for x,a in zip(p, pm.MINS)], [x+a for x,a in zip(p, pm.MAXS)])
                    self.assertEqual(sat, joint)
                    checked += 1
        self.assertEqual(checked, 62)

    def test_every_actual_query_and_fixture_numeric_fault_acts(self):
        acted = 0
        for c, block in enumerate(self.blocks):
            rows = pm.parse(block)
            for tag, fn in (('FIXTURE', pm.fixture), ('SEED', pm.seed)):
                words = next(w for t,w in rows if t == tag)
                for j in range(len(words)):
                    bad = words.copy(); bad[j] = str(float(words[j])+.125)
                    with self.subTest(case=c, kind=tag, column=j), self.assertRaises(AssertionError): fn(bad, c)
                    acted += 1
            qs = [w for t,w in rows if t == 'QUERY']
            for k, words in enumerate(qs):
                i, q = divmod(k, 3); tick = self.report['cases'][c]['ticks'][i]
                for j in range(len(words)):
                    if j == 2: continue  # nonnumeric query label, separately schema-gated
                    bad = words.copy(); bad[j] = str(float(words[j])+.125)
                    with self.subTest(case=c, tick=i, q=q, column=j), self.assertRaises(AssertionError): pm.query(bad, tick, c, i, q)
                    acted += 1
        self.assertEqual(acted, 5262)
        print(f'{acted} ACTED native PM bevel query/fixture/seed numeric refusals, 0 failed')

    def test_every_actual_accepted_contact_and_winning_copy_numeric_fault_acts(self):
        acted = 0
        for c, block in enumerate(self.blocks):
            ticks = self.report['cases'][c]['ticks']
            for prefix in ('OFFRAMPBUF_CONTACT', 'OFFRAMPTRICOPY_CONTACT'):
                lines = [l[l.find(prefix):] for l in block.splitlines() if prefix+' ' in l]
                for line in lines:
                    words = line.split()
                    for j in range(1, len(words)):
                        bad = words.copy(); bad[j] = str(float(words[j])+.125)
                        with self.subTest(case=c, prefix=prefix, contact=words[1], column=j), self.assertRaises(AssertionError):
                            pm.capture(block.replace(line, ' '.join(bad)), ticks, c)
                        acted += 1
        self.assertEqual(acted, 756)
        print(f'{acted} ACTED native PM accepted-contact/winning-copy numeric refusals, 0 failed')

    def test_mirrored_plausible_fraction_passes_prior_parity_then_refuses(self):
        line = next(l[l.find('OFFRAMPBEVPM_QUERY'):] for l in self.texts[3].splitlines() if 'OFFRAMPBEVPM_QUERY 0 10 down2 ' in l)
        words = line.split(); words[10] = '.01'  # plausible biased fraction, all enabled arms identical
        texts = [t.replace(line, ' '.join(words)) for t in self.texts]
        self.assertEqual(pm.prior_compare(*(pm.split(t)[0] for t in texts)), self.result['original_twenty_case_report'])
        qs = [[r for r in pm.parse(pm.split(t)[1]) if r[0] == 'QUERY'] for t in texts[1:]]
        self.assertTrue(all(q == qs[0] for q in qs))
        with self.assertRaises(AssertionError): pm.compare(*texts)

    def test_schema_quiet_outside_capture_setup_and_repeat_refuse(self):
        block = self.splits[3][1]
        lines = block.splitlines()
        tests = [block+'\nOFFRAMPBEVPM_UNKNOWN 1', block+'\nOFFRAMPBEVPM_END 3',
                 block.replace('BEGIN 1 1 1 3 32', 'BEGIN 2 1 1 3 32'),
                 block.replace('SOURCE '+pm.source_digest(), 'SOURCE '+'0'*64)]
        for prefix in ('OFFRAMPBEVPM_TICK 0 10 ', 'OFFRAMPBEVPM_QUERY 0 10 down2 ',
                       'OFFRAMPTRICOPY_CHECK 1 ', 'OFFRAMPORIGIN_CONTACT 0 '):
            line = next(l for l in lines if prefix in l)
            missing = block.replace(line, '', 1)  # retained native logs may preserve CRLF
            self.assertNotEqual(missing, block)
            self.assertEqual(missing.count(prefix), block.count(prefix)-1)
            tests += [missing, block+'\n'+line]
        for text in tests:
            with self.assertRaises(AssertionError): pm.grade(text)
        # Capture outside a case, including the quiet global envelope, is forbidden.
        quiet = self.splits[2][1]
        insertion = '\nOFFRAMPBUF_BEGIN 1 32768\n'
        with self.assertRaises(AssertionError): pm.grade(quiet.replace('OFFRAMPBEVPM_SOURCE', insertion+'OFFRAMPBEVPM_SOURCE'))
        changed = self.texts.copy(); changed[4] = changed[4].replace('OFFRAMPBEVPM_QUERY 0 10 down2', 'OFFRAMPBEVPM_QUERY 0 10 unknown')
        with self.assertRaises(AssertionError): pm.compare(*changed)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    a, rest = ap.parse_known_args(); NATIVE_ARMS = a.native_arms
    Native.__unittest_skip__ = not bool(NATIVE_ARMS)
    unittest.main(argv=[__file__, *rest])
