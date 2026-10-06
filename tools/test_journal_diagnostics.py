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
        text = mouse_journal([(2, 0)] * 6)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("v "):
                fields = line.split()
                fields[6] = str(float(fields[6]) + 0.5)
                lines[i] = " ".join(fields)
                break
        self.assertEqual(receipt_for("\n".join(lines) + "\n").journal, "FAULT")
        r = run(Journal(mfilter=1).end())
        self.assertNotIn("identity_mouse_frames", r.info)


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

    def test_verbose_contains_continuity(self):
        r = run(unresolved_journal((3, 4)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hidcheck.emit(r, True)
        self.assertIn("identity_unresolved_runs", out.getvalue())
        self.assertIn("identity_unresolved_longest", out.getvalue())


if __name__ == "__main__":
    unittest.main()
