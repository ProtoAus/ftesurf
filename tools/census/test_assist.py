#!/usr/bin/env python3
"""Offline census safety controls; no real assist or catch-rate claim.

Run: python tools/census/test_assist.py
ASSIST_MODULE can select the unchanged predecessor for the acting control.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(os.environ.get("ASSIST_MODULE", Path(__file__).with_name("assist.py")))
SPEC = importlib.util.spec_from_file_location("assist_under_test", SOURCE)
assist = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assist)


def sample(t, side=-450, vz=0, flags=0, keys=0):
    return "%s 0 0 0 0 0 %s 0 0 %s %s 0 %s 0 0 0 0\n" % (
        t, vz, flags, keys, side)


class AssistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("ASSIST_TEST_ROOT"))
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "control.rec"

    def parse(self, body, tick="0.015"):
        header = "FTESURF-REC 5\nmap control\n"
        if tick is not None:
            header += "tickrate %s\n" % tick
        self.path.write_text(header + "begin\n" + body, encoding="utf-8")
        return assist.parse(str(self.path))

    def test_contiguous_statistics_act(self):
        body = "".join(sample("%.4f" % (i * 0.015),
                              side=450 if i % 2 else -450,
                              vz=289 if i % 2 else 0,
                              flags=21 if i % 2 else 0,
                              keys=16 if i % 2 else 0) for i in range(80))
        rows = self.parse(body)
        stats = assist.run_stats(rows)
        self.assertEqual((rows.nrows, len(rows.segs)), (80, 1))
        self.assertEqual((stats["null_opp"], stats["null_clean"]), (79, 79))
        self.assertEqual((stats["landg_opp"], stats["landg_d0"]), (40, 40))
        self.assertEqual((stats["landr_opp"], stats["landr_d0"]), (40, 40))
        self.assertEqual(stats["hop"], 40)
        self.assertAlmostEqual(stats["cvs"][0], 0)

    def test_time_boundaries_do_not_invent_opportunities(self):
        for boundary in ("0.015", "0.014", "-0.015", "0.060"):
            with self.subTest(boundary=boundary):
                rows = self.parse(sample("0.000") + sample("0.015")
                                  + sample(boundary, 450, 289, 21, 16)
                                  + sample("%.4f" % (float(boundary) + 0.015),
                                           450, 289, 21, 16))
                stats = assist.run_stats(rows)
                self.assertEqual([len(seg) for seg in rows.segs], [2, 2])
                for name in ("null_opp", "landg_opp", "landr_opp", "hop"):
                    self.assertEqual(stats[name], 0, name)

    def test_negative_preroll_rounding_and_event_rows_remain_supported(self):
        rows = self.parse(sample("-0.0300") + "in 0 1 0 0 0 0 0 0 0 0\n"
                          + sample("-0.0150") + "cp 0 0\n"
                          + sample("0.0000") + sample("0.0151"))
        self.assertEqual((rows.nrows, len(rows.segs)), (4, 1))

    def test_legacy_header_without_tick_keeps_default(self):
        rows = self.parse(sample("0") + sample("0.015"), tick=None)
        self.assertEqual((rows.tick, len(rows.segs)), (0.015, 1))

    def test_nonfinite_or_nonpositive_tick_is_not_a_measurement(self):
        for tick in ("nan", "inf", "-inf", "0", "-0.015", "nonsense", ""):
            with self.subTest(tick=tick), self.assertRaises(ValueError):
                self.parse(sample("0") + sample("0.015"), tick=tick)

    def test_invalid_sample_numbers_refuse_instead_of_bridging(self):
        for column in (0, 1, 4, 6, 9, 10, 12):
            for value in ("nan", "inf", "-inf", "1e999"):
                with self.subTest(column=column, value=value):
                    fields = sample("0.015").split()
                    fields[column] = value
                    with self.assertRaises(ValueError):
                        self.parse(sample("0.000") + " ".join(fields) + "\n"
                                   + sample("0.030", 450, 289, 21, 16))

    def test_fractional_flag_masks_do_not_become_integer_evidence(self):
        for column in (9, 10):
            fields = sample("0.015").split()
            fields[column] = "1.5"
            with self.subTest(column=column), self.assertRaises(ValueError):
                self.parse(sample("0") + " ".join(fields) + "\n")

    def test_broken_numeric_row_does_not_disappear(self):
        for broken in ("0.015 0 0\n", sample("0.015", side="broken")):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                self.parse(sample("0") + broken + sample("0.015", 450))

    def test_cli_refuses_invalid_evidence_without_traceback_or_score(self):
        self.path.write_text("FTESURF-REC 5\ntickrate nan\nbegin\n"
                             + sample("0") + sample("0.015"), encoding="utf-8")
        for command in (("one", str(self.path)),
                        ("control", str(self.path)),
                        ("--root", self.tmp.name, "census"),
                        ("--root", self.tmp.name, "steps"),
                        ("--root", self.tmp.name, "delays")):
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, str(SOURCE), *command],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot measure", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("rate  min", result.stdout)
                self.assertNotIn("hop interval cv", result.stdout)

    def test_valid_one_cli_reports_acting_control(self):
        self.parse("".join(sample("%.4f" % (i * 0.015),
                                  side=450 if i % 2 else -450)
                           for i in range(80)))
        result = subprocess.run([sys.executable, str(SOURCE), "one", str(self.path)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("79 opportunities", result.stdout)
        self.assertIn("1.0000", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
