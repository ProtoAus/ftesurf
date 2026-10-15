"""SYNTHETIC transcripts only: parser checks, never native/no-overlay evidence."""
import unittest

import p721cache_readback as contract


def synthetic_records(overlays=False, cache=0):
    """Invent complete records, including informational defaults; no native input."""
    required = dict(contract.OBSERVED_REQUIRED, r_temporalscenecache=str(cache))
    if overlays:
        required.update(contract.OVERLAY_REQUIRED)
    records = {name: f'"{name}" is "{value}"\nDefault: "{value}"'
               for name, value in required.items()}
    records.update({name: f'Unknown command "{name}"'
                    for name in sorted(contract.EXPECTED_ABSENT)})
    return records


def transcript(records):
    return '\n'.join(records.values())


class P721CacheReadbackTests(unittest.TestCase):
    def reject(self, records, message, overlays=False, cache=0):
        reader = contract.proposed_settings if overlays else contract.audit_preserved_settings
        with self.assertRaises(contract.ContractError) as caught:
            reader(transcript(records), cache)
        self.assertEqual(str(caught.exception), message)

    def test_synthetic_complete_36_and_49_settings_only_not_no_overlay(self):
        for cache in (0, 1):
            with self.subTest(cache=cache):
                base = transcript(synthetic_records(cache=cache))
                self.assertEqual(len(contract.audit_preserved_settings(base, cache)), 36)
                future = transcript(synthetic_records(True, cache))
                values = contract.proposed_settings(future, cache)
                self.assertEqual(len(values), 49)
                self.assertEqual(values['r_temporalscenecache'], str(cache))
                self.assertEqual(values['hud_timer'], '0')
        # Even 49 synthetic observations certify neither pixels nor modal/idle state.

    def test_remove_all_36_complete_records_requires_exact_named_membership(self):
        for name in (*contract.OBSERVED_REQUIRED, 'r_temporalscenecache'):
            with self.subTest(name=name):
                records = synthetic_records()
                del records[name]  # Also removes Default, not an orphan-record control.
                self.reject(records, 'missing mandatory cvar: ' + name)

    def test_remove_all_13_overlay_records_requires_exact_named_membership(self):
        self.assertEqual(len(contract.OVERLAY_REQUIRED), 13)
        for name in contract.OVERLAY_REQUIRED:
            with self.subTest(name=name):
                records = synthetic_records(True)
                del records[name]
                self.reject(records, 'missing mandatory cvar: ' + name, True)

    def test_base_cannot_supply_missing_overlay_records(self):
        missing = ','.join(sorted(contract.OVERLAY_REQUIRED))
        self.reject(synthetic_records(), 'missing mandatory cvar: ' + missing, True)

    def test_nonzero_every_real_zero_control_requested_and_effective(self):
        for name, value in dict(contract.OBSERVED_REQUIRED, **contract.OVERLAY_REQUIRED).items():
            if value != '0':
                continue
            for effective in (False, True):
                with self.subTest(name=name, effective=effective):
                    records = synthetic_records(True)
                    records[name] = (f'"{name}" is "0"\nEffective value is "1"'
                                     if effective else f'"{name}" is "1"') + '\nDefault: "0"'
                    self.reject(records, 'wrong effective ' + name, True)

    def test_exact_six_unknown_membership(self):
        self.assertEqual(contract.EXPECTED_ABSENT, {
            'hud_timers', 'hud_pb', 'hud_spectators', 'hud_statusbar',
            'hud_lobby', 'hud_surfinfo'})
        for name in contract.EXPECTED_ABSENT:
            with self.subTest(name=name):
                records = synthetic_records()
                del records[name]
                self.reject(records, 'missing expected-absent observation: ' + name)
                records = synthetic_records()
                records[name] += '\n' + records[name]
                self.reject(records, 'duplicate unknown: ' + name)
            for value in ('0', '1'):
                with self.subTest(name=name, value=value):
                    records = synthetic_records()
                    records[name] = f'"{name}" is "{value}"\nDefault: "0"'
                    self.reject(records, 'expected absent reappeared: ' + name)

    def test_unexpected_unknown_is_not_a_prefix_exception(self):
        for name in ('hud_timers_extra', 'hud_timer', 'r_novis', 'invented'):
            with self.subTest(name=name):
                records = synthetic_records()
                records['extra'] = f'Unknown command "{name}"'
                self.reject(records, 'unexpected unknown: ' + name)

    def test_effective_overrides_requested_but_default_never_does(self):
        records = synthetic_records()
        records['r_novis'] = '"r_novis" is "1"\nEffective value is "0"\nDefault: "1"'
        self.assertEqual(contract.audit_preserved_settings(transcript(records))['r_novis'], '0')
        records['r_novis'] = '"r_novis" is "1"\nDefault: "0"'
        self.reject(records, 'wrong effective r_novis')
        records['r_novis'] = '"r_novis" is "0"\nEffective value is "1"\nDefault: "0"'
        self.reject(records, 'wrong effective r_novis')

    def test_orphan_duplicate_and_latch_records_fail_closed(self):
        cases = (
            ('Default: "0"', 'orphan default value'),
            ('Effective value is "0"', 'orphan effective value'),
            ('"r_novis" is "0"\nEffective value is "0"\nEffective value is "0"',
             'duplicate effective value: r_novis'),
            ('"r_novis" is "0"\nDefault: "0"\nEffective value is "0"',
             'orphan effective value'),
            ('Will be changed to "0" on vid_restart',
             'unrecognized readback line: Will be changed to "0" on vid_restart'),
        )
        for record, message in cases:
            with self.subTest(record=record):
                records = synthetic_records()
                records['r_novis'] = record
                self.reject(records, message)
        records = synthetic_records()
        records['extra'] = '"r_novis" is "0"'
        self.reject(records, 'duplicate cvar: r_novis')
        records['extra'] = '"invented" is "0"'
        self.reject(records, 'unexpected cvar: invented')

    def test_nonfinite_full_requested_and_effective_records(self):
        for value in ('NaN', 'Infinity', '-Infinity', 'bad'):
            for effective in (False, True):
                with self.subTest(value=value, effective=effective):
                    records = synthetic_records()
                    records['r_novis'] = (f'"r_novis" is "0"\nEffective value is "{value}"'
                                          if effective else f'"r_novis" is "{value}"') + '\nDefault: "0"'
                    self.reject(records, 'wrong effective r_novis')

    def test_engine_divergent_numeric_spellings_full_records_rejected(self):
        cases = (('r_blendsort', '+1'), ('cl_maxfps', '1e2'), ('cl_maxfps', '1E2'),
                 ('cl_maxfps', '1_0_0'), ('cl_maxfps', ' 100'), ('cl_maxfps', '100 '),
                 ('cl_maxfps', '\t100'), ('cl_maxfps', '１００'),
                 ('cl_maxfps', '١٠٠'), ('r_novis', '-0'))
        for name, value in cases:
            wanted = contract.OBSERVED_REQUIRED[name]
            for effective in (False, True):
                with self.subTest(name=name, value=value, effective=effective):
                    records = synthetic_records()
                    records[name] = (f'"{name}" is "{wanted}"\nEffective value is "{value}"'
                                     if effective else f'"{name}" is "{value}"') + f'\nDefault: "{wanted}"'
                    self.reject(records, 'wrong effective ' + name)

    def test_source_compatible_ascii_decimal_requested_and_effective(self):
        for name, value in (('r_blendsort', '001.000'), ('cl_maxfps', '0100.00'),
                            ('r_novis', '00.000'), ('cl_predict_timenudge', '00.500')):
            for effective in (False, True):
                with self.subTest(name=name, effective=effective):
                    records = synthetic_records()
                    records[name] = (f'"{name}" is "999"\nEffective value is "{value}"'
                                     if effective else f'"{name}" is "{value}"') + '\nDefault: "999"'
                    self.assertEqual(contract.audit_preserved_settings(transcript(records))[name], value)

    def test_branch_mode_cache_phase_and_renderer_mandatory(self):
        for name, value in (('r_blendsort', '0'), ('r_blendsort', '2'),
                            ('r_temporalscenecache', '1'), ('vid_renderer', 'vk'),
                            ('vid_renderer', 'GL')):
            with self.subTest(name=name, value=value):
                records = synthetic_records()
                records[name] = f'"{name}" is "{value}"'
                self.reject(records, 'wrong effective ' + name)
        for cache in (-1, 2, True, False, '0', 0.0, None):
            for reader in (contract.audit_preserved_settings, contract.proposed_settings):
                with self.subTest(cache=cache, reader=reader.__name__):
                    with self.assertRaises(contract.ContractError) as caught:
                        reader(transcript(synthetic_records(True)), cache)
                    self.assertEqual(str(caught.exception), 'invalid cache phase')

    def test_explicit_parse_membership_and_malformed_output(self):
        for required, absent, message in (({}, set(), 'empty required membership'),
                                          ({'x': '0'}, {'x'}, 'overlapping membership')):
            with self.subTest(message=message):
                with self.assertRaises(contract.ContractError) as caught:
                    contract.parse_readback('', required, absent)
                self.assertEqual(str(caught.exception), message)
        for line in ('Unknown command hud_timer', '"r_novis" is currently "0"', 'diagnostic'):
            records = synthetic_records()
            records['extra'] = line
            self.reject(records, 'unrecognized readback line: ' + line)


if __name__ == '__main__':
    unittest.main(verbosity=2)
