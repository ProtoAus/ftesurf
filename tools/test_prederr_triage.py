#!/usr/bin/env python3
"""Identity-free report-reader controls; --output must be a new owned directory."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

TRIAGE = None
OUTPUT = None


def native(seq, time, error=0, extra=None):
    row = dict.fromkeys(TRIAGE.RING_COLS, 0)
    row.update(t=time, seq=seq, sx=error, msec=15)
    values = [row[k] for k in TRIAGE.RING_COLS]
    return ' '.join(map(str, values + (extra or [])))


def server(seq, piece=15, kind=1, time=1):
    row = dict.fromkeys(TRIAGE.SV_COLS, 0)
    row.update(t=time, rt=time, kind=kind, seq=seq, msec=piece, piece=piece)
    return ' '.join(str(row[k]) for k in TRIAGE.SV_COLS)


class ReportReader(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT / self._testMethodName
        self.root.mkdir()

    def report(self, *, version=1, rows=None, sv='', marker=False, context=''):
        if rows is None:
            rows = [native(10, 0), native(11, .015), native(12, .03), native(13, .33, 9)]
        identity = '# command_identity ack-seat-tag-v1\n' if marker else ''
        text = ('FTESURF-PREDREPORT 1\nmap synthetic\n'
                'utc 2026-01-01 00:00:00\n'
                'player Fixture slot 1 account PRIVATE_ACCOUNT_SENTINEL ping 1\n'
                'server PRIVATE_ADDRESS_SENTINEL\n'
                '== context\nFTESURF-PREDCTX 6\nreporter P1321 fs_wop "1" expected 0 of 16\n'
                + context + '\n== ring\nFTESURF-PREDRING %d\n' % version
                + '# engine FTE git-8383-patch-1318-0-g3a64ae7476\n' + identity
                + '\n'.join(rows) + '\n' + sv + '\n== end\n')
        path = self.root / 'synthetic.txt'
        path.write_text(text, encoding='utf8')
        return path

    def run_report(self, path):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = TRIAGE.triage(path, 1, 2, 4)
        text = out.getvalue()
        (self.root / 'triage.stdout').write_text(text, encoding='utf8')
        return result, text

    def test_legacy_error_and_rows_preserved(self):
        path = self.report()
        _, _, rows, _ = TRIAGE.load(path)
        self.assertEqual(len(rows), 4)
        self.assertEqual(TRIAGE.err(rows[-1]), 9)
        _, text = self.run_report(path)
        self.assertIn('seq 13 off by 9.0', text)

    def test_comparison_gap_is_not_packet_history(self):
        _, text = self.run_report(self.report())
        self.assertIn('COMPARISON GAP:', text)
        self.assertIn('packet receipt/ACK history unknown', text)
        self.assertNotIn('no server packet', text)
        self.assertNotIn('never acked', text)

    def test_absent_server_is_unknown_not_old_version(self):
        _, text = self.run_report(self.report())
        self.assertIn('command receipt/execution unknown', text)
        self.assertNotIn('before P1238', text)

    def test_bounded_missing_identity_is_not_nonexecution(self):
        sv = '== server\nmark seq 13 at 1\n' + server(9) + '\n' + server(14)
        _, text = self.run_report(self.report(sv=sv))
        self.assertIn('captured SV tagged bounds: 9..14', text)
        self.assertIn('no matching tagged SV row captured: 13', text)
        self.assertIn('absence is not proof of nonexecution', text)
        self.assertNotIn('NEVER RAN', text)

    def test_piece_duration_is_not_simulated_time(self):
        rows = [native(10, 0), native(12, .015), native(14, .03, 9)]
        sv = '== server\nmark seq 14 at 1\n' + '\n'.join([server(13, 1), server(13, 17), server(14, 15)])
        _, text = self.run_report(self.report(rows=rows, sv=sv))
        self.assertIn('33.0 ms logged input-piece duration', text)
        self.assertIn('simulated duration unknown', text)
        self.assertNotIn('ms simulated', text)
        self.assertNotIn('ms predicted', text)

    def test_default_header_does_not_echo_private_identifiers(self):
        _, text = self.run_report(self.report())
        self.assertNotIn('PRIVATE_ACCOUNT_SENTINEL', text)
        self.assertNotIn('PRIVATE_ADDRESS_SENTINEL', text)
        self.assertIn('map synthetic', text)

    def test_old_build_provenance_and_binding_warning(self):
        _, text = self.run_report(self.report())
        self.assertIn('# engine FTE git-8383-patch-1318', text)
        self.assertIn('reporter P1321', text)
        self.assertIn('pre-P1326 command identity not qualified', text)
        self.assertIn('inputs(unqualified)', text)

    def test_v2_event_provenance_and_mode_boundary(self):
        extra = [1, 1, 0, 12, .014, 1, 2, 2]
        rows = [native(12, 0, extra=extra), native(13, .015, 9, extra)]
        # Authoritative mode2 differs from captured predicted mode0.
        values = rows[-1].split()
        values[TRIAGE.RING_COLS.index('pmtype')] = '2'
        rows[-1] = ' '.join(values)
        result, text = self.run_report(self.report(version=2, rows=rows, marker=True))
        self.assertTrue(result)
        self.assertIn('saved prediction: pm 0, seed seq 12 carry 14.000000 ms, phase hit 1, parts 2 ticks 2', text)
        self.assertIn('movement-mode boundary observed; not automatically expected or excused', text)
        self.assertIn('declared acknowledged move/local seat', text)

    def test_v2_unknown_prediction_not_fabricated(self):
        extra = [0, 0, 0, 0, 0, 0, 0, 0]
        result, text = self.run_report(self.report(version=2, rows=[native(13, 0, 9, extra)], marker=True))
        self.assertTrue(result)
        self.assertIn('seq 13 off by 9.0', text)
        self.assertIn('inputs(unqualified)', text)
        self.assertNotIn('saved prediction:', text)

    def test_unknown_schema_not_silently_graded(self):
        result, text = self.run_report(self.report(version=73))
        self.assertFalse(result)
        self.assertIn('unsupported ring schema 73', text)
        self.assertIn('report not graded', text)
        self.assertNotIn('worst: seq', text)

    def test_missing_file_makes_cli_fail(self):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', ['prederr_triage', str(self.root / 'absent.txt')]), contextlib.redirect_stdout(out):
            self.assertEqual(TRIAGE.main(), 1)

    def test_failed_fetch_with_old_local_rows_is_failure(self):
        path = self.report()
        fetch = self.root / 'fetch'
        existing = fetch / Path(TRIAGE.PI_DIR.rstrip('/')).name
        existing.mkdir(parents=True)
        (existing / 'old.txt').write_bytes(path.read_bytes())
        result = subprocess.CompletedProcess([], 1, '', 'synthetic fetch failure')
        with mock.patch.object(TRIAGE.subprocess, 'run', return_value=result), mock.patch.object(sys, 'argv', ['prederr_triage', '--fetch', str(fetch)]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(TRIAGE.main(), 1)

    def test_quiet_comparisons_do_not_invent_gap(self):
        _, text = self.run_report(self.report(rows=[native(10, 0), native(11, .015, 9)]))
        self.assertNotIn('COMPARISON GAP:', text)
        self.assertNotIn('GAP: no server packet', text)

    def test_kind_zero_and_delayed_mode_are_qualified(self):
        sv = '== server\nfixture SV header\nmark seq 13 at 1\npacket stalls 63 credited 5\n' + server(12) + '\n' + server(13) + '\n' + server(0, kind=0)
        _, text = self.run_report(self.report(sv=sv))
        self.assertIn('loss-fill/special input cannot be distinguished', text)
        self.assertIn('SV body/mode sampled at next PreThink', text)
        self.assertIn('server counters (not window-local): packet stalls 63', text)

    def test_clean_local_v2_snapshot_keeps_valid_metadata_without_error_claim(self):
        path = self.root / 'manual.txt'
        extra = [1, 1, 0, 12, .014, 1, 2, 2]
        values = native(13, .015, extra=extra).split()
        values[TRIAGE.RING_COLS.index('fwd')] = '120'
        path.write_text('FTESURF-PREDRING 2\n# command_identity ack-seat-tag-v1\n'
                        + ' '.join(values) + '\n', encoding='utf8')
        result, text = self.run_report(path)
        self.assertTrue(result)
        self.assertIn('no disagreement above eps 1 in retained ring', text)
        self.assertIn('errors outside these retained position comparisons are unknown', text)
        self.assertIn('inputs move 120 0 0', text)
        self.assertIn('saved prediction: pm 0, seed seq 12 carry 14.000000 ms', text)
        self.assertNotIn('disagreement starts', text)
        self.assertNotIn('worst:', text)

    def test_sub_epsilon_snapshot_is_not_reported_as_a_disagreement(self):
        result, text = self.run_report(self.report(rows=[native(12, 0, .5), native(13, .015, .9)]))
        self.assertTrue(result)
        self.assertIn('no disagreement above eps 1 in retained ring', text)
        self.assertIn('largest 0.900 units', text)
        self.assertNotIn('disagreement starts', text)
        self.assertNotIn('worst:', text)

    def test_exact_epsilon_snapshot_is_not_reported_as_a_disagreement(self):
        result, text = self.run_report(self.report(rows=[native(12, 0), native(13, .015, 1)]))
        self.assertTrue(result)
        self.assertIn('no disagreement above eps 1 in retained ring', text)
        self.assertIn('largest 1.000 units', text)
        self.assertNotIn('disagreement starts', text)

    def test_clean_unknown_prediction_does_not_fabricate_metadata(self):
        extra = [0] * 8
        result, text = self.run_report(self.report(version=2, rows=[native(13, 0, extra=extra)], marker=True))
        self.assertTrue(result)
        self.assertIn('no disagreement above eps 1 in retained ring', text)
        self.assertIn('inputs(unqualified)', text)
        self.assertNotIn('saved prediction:', text)

    def test_just_above_epsilon_still_reports_the_disagreement(self):
        result, text = self.run_report(self.report(rows=[native(12, 0), native(13, .015, 1.001)]))
        self.assertTrue(result)
        self.assertIn('disagreement starts at seq 13', text)
        self.assertIn('worst: seq 13', text)
        self.assertNotIn('no disagreement above eps', text)

    def test_named_clean_row_cannot_hide_another_retained_error(self):
        path = self.report(rows=[native(12, 0), native(13, .015, 9)], context='worst 0 at seq 12')
        result, text = self.run_report(path)
        self.assertTrue(result)
        self.assertIn('worst: seq 13 off by 9.0', text)
        self.assertIn('disagreement starts at seq 13', text)
        self.assertNotIn('no disagreement above eps', text)

    def test_local_ring_and_context_pair_still_read(self):
        path = self.root / 'local.txt'
        path.write_text('FTESURF-PREDRING 1\n' + native(12, 0) + '\n' + native(13, .015, 9), encoding='utf8')
        path.with_name('local_ctx.txt').write_text('FTESURF-PREDCTX 6\nreporter synthetic\n', encoding='utf8')
        _, ctx, rows, _ = TRIAGE.load(path)
        self.assertEqual(len(rows), 2)
        self.assertIn('reporter synthetic', ctx)
        _, text = self.run_report(path)
        self.assertIn('seq 13 off by 9.0', text)


def main():
    global TRIAGE, OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, default=Path(__file__).with_name('prederr_triage.py'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true', help='accept a discriminating legacy failure, never a candidate pass')
    args = parser.parse_args()
    OUTPUT = args.output
    OUTPUT.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('prederr_triage_test_subject', args.module)
    TRIAGE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(TRIAGE)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReportReader))
    receipt = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), baseline=args.baseline)
    (OUTPUT / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf8')
    return 0 if (not result.wasSuccessful() if args.baseline else result.wasSuccessful()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
