#!/usr/bin/env python3
"""Non-enforcing journal diagnostics, from grammar-built synthetic input.

Run with python tools/test_journal_diagnostics.py. No player files are written.
"""
import contextlib
import hashlib
import io
import os
import tempfile
import unittest

import hidcheck
import rcptcheck
from test_hidcheck import Journal, run


def receipt_for(text):
    """Exercise the real digest/content join, not signature verification."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "sample.rcpt")
        data = text.encode("utf-8")
        with open(os.path.splitext(path)[0] + ".hid", "wb") as fh:
            fh.write(data)
        r = rcptcheck.Receipt(path)
        r.signed = [("hid", "%s %d 1" % (hashlib.sha256(data).hexdigest(), len(data)))]
        rcptcheck.join_journal(r)
        return r


def mouse_journal(counts, flags=None):
    j = Journal()
    yaw, pitch = 90.0, 10.0
    for i, (dx, dy) in enumerate(counts):
        flag = flags[i] if flags else 0
        j.frame(3000 + i)
        if dx or dy:
            j.mouse(dx, dy)
        if not flag & (hidcheck.VF_STRAFE_X | hidcheck.VF_FREE):
            yaw += j.k * dx
        if not flag & (hidcheck.VF_STRAFE_Y | hidcheck.VF_FREE):
            pitch += j.kp * dy
        j.view(dx, dy, pitch, yaw, flags=flag)
    return j.end()


def fault_journal(text=None):
    lines = (text or mouse_journal([(2, 0)] * 6)).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("v "):
            fields = line.split()
            fields[6] = str(float(fields[6]) + 0.5)
            lines[i] = " ".join(fields)
            break
    return "\n".join(lines) + "\n"


class MouseCoverage(unittest.TestCase):
    def test_active_control_and_verbose_output(self):
        text = mouse_journal([(2, 0)] * 6)
        r = run(text)
        self.assertTrue(r.ok, r.faults)
        self.assertEqual(r.info["identity_judged"], 5)
        self.assertEqual(r.info["identity_mouse_frames"], 5)
        self.assertEqual(r.info["identity_mouse_pct"], 100.0)
        self.assertEqual(r.info["identity_no_mouse_longest"], 0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hidcheck.emit(r, True)
        self.assertIn("identity_mouse_frames", out.getvalue())
        receipt = receipt_for(text)
        self.assertEqual(receipt.journal, "OK")
        self.assertIn("mouse counts on 5/5 judged frames (100.00%)", receipt.journal_detail)

    def test_no_mouse_and_sparse_input_are_measurements(self):
        for counts, expected, verdict in (([(0, 0)] * 6, (0, 5, 5), "BLIND"),
                                          ([(0, 0), (1, 0)] + [(0, 0)] * 4,
                                           (1, 4, 4), "OK")):
            text = mouse_journal(counts)
            r = run(text)
            self.assertTrue(r.ok, r.faults)
            self.assertEqual(tuple(r.info[k] for k in ("identity_mouse_frames",
                             "identity_no_mouse_frames", "identity_no_mouse_longest")), expected)
            self.assertEqual(r.info["identity_mouse_pct"], expected[0] * 20.0)
            self.assertEqual(receipt_for(text).journal, verdict)

    def test_pitch_counts_and_excluded_axis(self):
        self.assertEqual(run(mouse_journal([(0, 2)] * 6)).info["identity_mouse_frames"], 5)
        r = run(mouse_journal([(0, 2)] * 6, [hidcheck.VF_STRAFE_Y] * 6))
        self.assertTrue(r.ok, r.faults)
        self.assertEqual(r.info["identity_judged"], 5)
        self.assertEqual(r.info["identity_mouse_frames"], 0)
        # Existing verdict policy is unchanged even for an excluded-axis count.
        self.assertEqual(receipt_for(mouse_journal([(0, 2)] * 6,
                         [hidcheck.VF_STRAFE_Y] * 6)).journal, "OK")

    def test_unjudged_frame_breaks_gap(self):
        text = mouse_journal([(0, 0)] * 8, [0, 0, 0, hidcheck.VF_FREE, 0, 0, 0, 0])
        r = run(text)
        self.assertTrue(r.ok, r.faults)
        self.assertEqual(r.info["identity_judged"], 6)
        self.assertEqual(r.info["identity_no_mouse_longest"], 4)

    def test_fault_precedence_and_absent_metric(self):
        text = fault_journal()
        h = run(text)
        self.assertGreaterEqual(len(h.faults[0]), 300)
        receipt = receipt_for(text)
        self.assertEqual(receipt.journal, "FAULT")
        self.assertIn("YAW IDENTITY BROKEN", receipt.journal_detail[:300])
        self.assertIn("mouse counts on 5/5", receipt.journal_detail[:300])
        self.assertIn(h.faults[0][:300], " ".join(receipt.notes))
        r = run(Journal(mfilter=1).end())
        self.assertNotIn("identity_mouse_frames", r.info)


class AxisCoverage(unittest.TestCase):
    def metrics(self, r, axis):
        return tuple(r.info["identity_%s_%s" % (axis, key)] for key in
                     ("judged", "mouse_frames", "no_mouse_frames", "mouse_pct", "no_mouse_longest"))

    def test_each_active_axis_and_union(self):
        for counts, yaw, pitch in (([(2, 0)] * 6, 5, 0),
                                   ([(0, 2)] * 6, 0, 5),
                                   ([(2, 2)] * 6, 5, 5)):
            text = mouse_journal(counts)
            r = run(text)
            self.assertTrue(r.ok, r.faults)
            self.assertEqual(self.metrics(r, "yaw"), (5, yaw, 5-yaw, yaw*20.0, 5-yaw))
            self.assertEqual(self.metrics(r, "pitch"), (5, pitch, 5-pitch, pitch*20.0, 5-pitch))
            self.assertEqual(r.info["identity_mouse_frames"], 5)
            self.assertEqual(receipt_for(text).journal, "OK")

    def test_seed_and_excluded_pitch(self):
        # Counts on the seed establish a predecessor, not a comparison.
        r = run(mouse_journal([(2, 2)] + [(0, 0)] * 5))
        self.assertEqual(self.metrics(r, "yaw"), (5, 0, 5, 0.0, 5))
        text = mouse_journal([(0, 2)] * 6, [hidcheck.VF_STRAFE_Y] * 6)
        r = run(text)
        self.assertTrue(r.ok, r.faults)
        self.assertEqual(self.metrics(r, "yaw"), (5, 0, 5, 0.0, 5))
        self.assertEqual(self.metrics(r, "pitch"), (0, 0, 0, 0.0, 0))
        self.assertEqual(receipt_for(text).journal, "OK")  # existing policy

    def test_mode_and_profile_break_axis_gaps(self):
        text = mouse_journal([(0, 0)] * 8, [0, 0, 0, hidcheck.VF_FREE, 0, 0, 0, 0])
        r = run(text)
        for axis in ("yaw", "pitch"):
            self.assertEqual(self.metrics(r, axis), (6, 0, 6, 0.0, 4))
        j = Journal()
        for i in range(8):
            j.frame(3000+i)
            if i in (3, 4):
                j.cvarchange("m_filter", "1" if i == 3 else "0")
            j.view(0, 0, 10.0, 90.0)
        r = run(j.end())
        self.assertTrue(r.ok, r.faults)
        for axis in ("yaw", "pitch"):
            self.assertEqual(self.metrics(r, axis), (6, 0, 6, 0.0, 4))

    def test_global_abstention_has_no_invented_axis_coverage(self):
        j = Journal(mfilter=1)
        for i in range(5):
            j.frame(3000+i)
            j.mouse(2, 0)
            j.view(2, 0, 10.0, 90.0)
        r = run(j.end())
        self.assertTrue(r.ok, r.faults)
        self.assertNotIn("identity_yaw_judged", r.info)
        self.assertNotIn("identity_pitch_judged", r.info)

    def test_verbose_reports_both_axes(self):
        r = run(mouse_journal([(2, 0)] * 6))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hidcheck.emit(r, True)
        for axis in ("yaw", "pitch"):
            self.assertIn("identity_%s_mouse_frames" % axis, out.getvalue())
            self.assertIn("identity_%s_judged" % axis, out.getvalue())


def unresolved_journal(changed, excluded=()):
    j = Journal()
    yaw, pitch = 90.0, 10.0
    for i in range(10):
        j.frame(3000 + i)
        j.mouse(2, 2)
        yaw += j.k * 2
        pitch += j.kp * 2
        if i in changed:
            yaw += 0.5
            pitch += 0.5
        j.view(2, 2, pitch, yaw, flags=hidcheck.VF_FREE if i in excluded else 0)
    return j.end()


class UnresolvedContinuity(unittest.TestCase):
    def test_control_and_adjacent_frames(self):
        for changed, want in (((), (0, 0, 0)), ((3,), (1, 1, 1)),
                              ((3, 4, 5), (3, 1, 3)), ((2, 5, 8), (3, 3, 1))):
            text = unresolved_journal(changed)
            r = run(text)
            self.assertTrue(r.ok, r.faults)
            self.assertEqual(tuple(r.info[k] for k in ("identity_unresolved",
                             "identity_unresolved_runs", "identity_unresolved_longest")), want)
            receipt = receipt_for(text)
            self.assertEqual(receipt.journal, "BLIND" if changed else "OK")
            if changed:
                self.assertIn("unresolved spans %d, longest %d frames" % want[1:],
                              receipt.journal_detail[:300])
                self.assertIn("mouse counts on 9/9", receipt.journal_detail[:300])

    def test_excluded_frame_breaks_continuity(self):
        text = unresolved_journal((3, 4, 5, 6), excluded=(4,))
        r = run(text)
        self.assertTrue(r.ok, r.faults)
        self.assertEqual(r.info["identity_unresolved"], 3)
        self.assertEqual(r.info["identity_unresolved_runs"], 2)
        self.assertEqual(r.info["identity_unresolved_longest"], 2)

    def test_long_fault_retains_continuity(self):
        receipt = receipt_for(fault_journal(unresolved_journal((3, 4))))
        self.assertEqual(receipt.journal, "FAULT")
        self.assertIn("unresolved spans 1, longest 2 frames", receipt.journal_detail[:300])
        self.assertIn("mouse counts on 9/9", receipt.journal_detail[:300])

    def test_verbose_contains_continuity(self):
        r = run(unresolved_journal((3, 4)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hidcheck.emit(r, True)
        self.assertIn("identity_unresolved_runs", out.getvalue())
        self.assertIn("identity_unresolved_longest", out.getvalue())


class AbstentionReasons(unittest.TestCase):
    def assert_blind(self, text, why):
        r = run(text)
        self.assertTrue(r.ok, r.faults)
        self.assertEqual(r.info.get("identity_blind"), why)
        receipt = receipt_for(text)
        self.assertEqual(receipt.journal, "BLIND")
        self.assertIn(why, receipt.journal_detail[:300])
        self.assertFalse(receipt.faults, receipt.faults)

    def test_no_view_and_legacy(self):
        for legacy in (False, True):
            j = Journal(p293=not legacy)
            for i in range(5):
                j.frame(3000 + i)
                j.mouse(2, 1)
            why = "pre-293 journal: no recorded angle identity" if legacy else "no view records to judge"
            self.assert_blind(j.end(), why)

    def test_nonlinear_and_zero_yaw(self):
        for args, why in (({"mfilter": 1}, "no plain-linear frames (m_filter/m_accel or unusable constants)"),
                          ({"maccel": 1}, "no plain-linear frames (m_filter/m_accel or unusable constants)"),
                          ({"myaw": 0}, "zero yaw scale on all plain-linear frames")):
            j = Journal(**args)
            for i in range(5):
                j.frame(3000 + i)
                j.mouse(2, 0)
                j.view(2, 0, 10.0, 90.0)
            self.assert_blind(j.end(), why)

    def test_excluded_modes_and_one_frame(self):
        self.assert_blind(mouse_journal([(2, 0)] * 5, [hidcheck.VF_FREE] * 5),
                          "fewer than two frames in a governed view mode")
        self.assert_blind(mouse_journal([(2, 0)]),
                          "fewer than two frames in a governed view mode")

    def test_per_frame_override_leaves_no_judged_transition(self):
        j = Journal()
        for i in range(5):
            j.frame(3000 + i)
            if i == 1:
                j.cvarchange("m_filter", "1")
            j.mouse(2, 0)
            j.view(2, 0, 10.0, 90.0)
        self.assert_blind(j.end(), "no transition judgeable with recorded scales and pitch limits")

    def test_fault_precedence_and_active_control(self):
        r = run(mouse_journal([(2, 0)] * 6))
        self.assertTrue(r.ok, r.faults)
        self.assertNotIn("identity_blind", r.info)
        self.assertEqual(receipt_for(mouse_journal([(2, 0)] * 6)).journal, "OK")
        text = mouse_journal([(2, 0)] * 6).replace("sensitivity 0.3", "sensitivity BAD")
        self.assertEqual(receipt_for(text).journal, "FAULT")


if __name__ == "__main__":
    unittest.main()
