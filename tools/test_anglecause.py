#!/usr/bin/env python3
"""Controlled v1 angle-cause reader tests. No native/hardware/capture claim.

Positive input must actually need its bound server operation; removing authority
or adding an unrelated rewrite must not become clean. Reuses the existing HID
fixture, encoded wire bytes, and REC reader, without a new runner or deployment
framework. All identities below are synthetic public test values.
"""
import struct
import unittest

import hidcheck
import reccheck
from test_hidcheck import Journal
from test_reccheck import build as rec_fixture

NONCE = "0" * 32


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bits(pose):
    return " ".join(struct.pack(">f", value).hex() for value in pose)


def wire(fmt="qwabs4n", pose=(30.0, 80.0, 0.0)):
    if fmt == "qwabs4n":
        payload = struct.pack("<fff", *pose)
    elif fmt == "qwabs1n":
        payload = struct.pack("<bbb", 21, 56, 0)
    else:
        payload = struct.pack("<hhh", 5000, 9000, 0)
    return "0a" + payload.hex()


def server(fmt, raw, opid=1):
    return hidcheck.angle_server_row(
        ("angleop 0 0 0 %s %d 7 %s %s" % (NONCE, opid, fmt, raw)).split())


def fixture(fmt="qwabs4n", disposition="direct", rewrite=0.0, with_op=True,
            serial=2, close_zero=False, wrong_input=False, no_op=False):
    raw = wire(fmt, pose=(0, 0, 0)) if no_op else wire(fmt)
    target = hidcheck.angle_wire(fmt, raw)
    j = Journal(p293=True)
    j.lines.insert(1, "anglecause 1")
    j.view(0, 0, 0, 0)
    j.lines += ["anglebaseline 0 1 " + bits((0, 0, 0)),
                "angleend 0 1 " + bits((0, 0, 0)) + " 1"]
    if with_op:
        j.lines.append("angleop 0 %s 1 7 %s %s %s %s %s %d" % (
            NONCE, fmt, raw, disposition, bits((0, 0, 0)), bits(target), serial))
    base = (target[0] + rewrite, target[1] + rewrite, 0.0)
    if close_zero:
        j.lines += ["anglebaseline 0 %d %s" % (serial, bits(base)),
                    "angleend 0 %d %s 0" % (serial, bits(base))]
        serial += 1
    sign = -1 if wrong_input else 1
    output = (f32(base[0] - sign * j.k * 20),
              f32(base[1] + sign * j.k * 10), 0.0)
    j.frame(1)  # an acting nonempty drain precedes its raw mouse event
    j.mouse(10, 20)
    j.view(10, 20, output[0], output[1])
    j.lines += ["anglebaseline 0 %d %s" % (serial, bits(base)),
                "angleend 0 %d %s 2" % (serial, bits(output))]
    scope = {"nonce": NONCE, "operations": {(NONCE, 1): server(fmt, raw)}}
    return j.end(), scope


def read(text, scope=None):
    return hidcheck.check_hid("_anglecause_synthetic.hid", data=text.encode(),
                              angle_authority=scope)


def rec_bytes():
    lines = rec_fixture(ver=10)
    index = lines.index("begin")
    lines[index:index] = ["nonce " + NONCE, "anglecause 1"]
    index = next(i for i, line in enumerate(lines) if line.startswith("seed ")) + 1
    row = "angleop 0 0 0 %s 1 7 qwabs4n %s" % (NONCE, wire())
    lines.insert(index, row)
    return ("\n".join(lines) + "\n").encode(), row


class AngleCauseTests(unittest.TestCase):
    def assert_unbound(self, report):
        self.assertEqual(report.info.get("identity_unresolved"), 1, report.info)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 0)
        self.assertEqual(report.info.get("anglecause_unbound_frames"), 1)

    def test_float_word_endianness(self):
        self.assertEqual(hidcheck._angle_pose("3f800000 c0000000 00000000".split()),
                         (1.0, -2.0, 0.0))

    def test_supported_wire_and_acting_controls(self):
        for fmt in ("qwabs1n", "qwabs2n", "qwabs4n"):
            with self.subTest(fmt=fmt):
                text, scope = fixture(fmt)
                report = read(text, scope)
                self.assertFalse(report.faults, report.faults)
                self.assertEqual(report.info.get("identity_judged"), 1)
                self.assertEqual(report.info.get("identity_unresolved"), 0)
                self.assertEqual(report.info.get("anglecause_accounted_operations"), 1)
                self.assertEqual(report.info.get("anglecause_accounted_frames"), 1)
                self.assert_unbound(read(text))
                old = "\n".join(line for line in text.splitlines()
                                if not line.startswith("angle")) + "\n"
                control = read(old)
                self.assertEqual(control.info.get("identity_unresolved"), 1,
                                 "the reset must ACT, not just add harmless annotations")
                self.assertNotIn("anglecause_accounted_operations", control.info)

    def test_wrong_authority_never_licenses(self):
        text, scope = fixture()
        for changed in ({}, {"nonce": "1" * 32, "operations": scope["operations"]},
                        {"nonce": NONCE, "operations": {(NONCE, 2): server("qwabs4n", wire())}},
                        {"nonce": NONCE, "operations": {(NONCE, 1): server(
                            "qwabs4n", wire(pose=(31, 80, 0)))}}):
            with self.subTest(scope=changed):
                self.assert_unbound(read(text, changed))

    def test_non_direct_dispositions_abstain(self):
        for disposition in ("predicted", "consumed", "interleaved"):
            text, scope = fixture(disposition=disposition)
            report = read(text, scope)
            self.assertFalse(report.faults, report.faults)
            self.assert_unbound(report)

    def test_unrelated_whole_rewrite_is_not_excused(self):
        for with_op in (True, False):
            text, scope = fixture(rewrite=1.0, with_op=with_op)
            self.assert_unbound(read(text, scope))

    def test_bound_operation_is_not_a_blanket_input_exemption(self):
        text, scope = fixture(wrong_input=True)
        report = read(text, scope)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 1)
        self.assertEqual(report.info.get("anglecause_unbound_frames"), 0)
        self.assertEqual(report.info.get("identity_unresolved"), 1)

    def test_target_coincidence_without_operation_is_not_authority(self):
        text, scope = fixture(with_op=False)
        self.assert_unbound(read(text, scope))

    def test_no_v_closure_cannot_license_next_v(self):
        text, scope = fixture(close_zero=True)
        report = read(text, scope)
        self.assertFalse(report.faults, report.faults)
        self.assert_unbound(report)

    def test_interval_ids_may_have_gaps(self):
        text, scope = fixture(serial=100)
        report = read(text, scope)
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 1)

    def test_malformed_annotations_withhold_totals(self):
        text, scope = fixture()
        op = next(line for line in text.splitlines() if line.startswith("angleop "))
        baseline = next(line for line in text.splitlines() if line.startswith("anglebaseline 0 2 "))
        end = next(line for line in text.splitlines() if line.startswith("angleend 0 2 "))
        for bad in (text.replace(op, op + "\n" + op),
                    text.replace(op, op.replace("angleop 0 ", "angleop 1 ")),
                    text.replace(baseline, baseline + "\n" + baseline),
                    text.replace(end, end[:-1] + "1"),
                    text.replace(baseline, baseline.replace(bits((30, 80, 0)),
                                                          "7fc00000 42a00000 00000000")),
                    text + end + "\n"):
            with self.subTest(bad=bad[-150:]):
                report = read(bad, scope)
                self.assertTrue(report.faults)
                self.assertFalse(report.info.get("anglecause_observations_complete"))
                self.assertIsNone(report.info.get("anglecause_accounted_operations"))
                self.assertIsNone(report.info.get("anglecause_unbound_frames"))

    def test_missing_baseline_or_end_is_malformed(self):
        text, scope = fixture()
        for prefix in ("anglebaseline 0 2 ", "angleend 0 2 "):
            bad = "\n".join(s for s in text.splitlines() if not s.startswith(prefix)) + "\n"
            self.assertTrue(read(bad, scope).faults)

    def test_pending_operation_cannot_silently_lose_its_recorded_input_closure(self):
        text, scope = fixture(no_op=True)
        positive = read(text, scope)
        self.assertFalse(positive.faults, positive.faults)
        self.assertEqual(positive.info.get("identity_unresolved"), 0)
        bad = "\n".join(s for s in text.splitlines()
                        if not s.startswith(("anglebaseline 0 2 ", "angleend 0 2 "))) + "\n"
        report = read(bad, scope)
        self.assertTrue(report.faults, "known pending metadata cannot silently disappear")
        self.assertIsNone(report.info.get("anglecause_operations"))

    def test_future_schema_is_unavailable_not_legacy_clean(self):
        text, scope = fixture()
        report = read(text.replace("anglecause 1", "anglecause 2"), scope)
        self.assertEqual(report.info.get("identity_blind"), "unsupported anglecause schema")
        self.assertNotIn("anglecause_accounted_operations", report.info)

    def test_server_schema_is_canonical(self):
        row = "angleop 0 0 0 %s 1 7 qwabs4n %s" % (NONCE, wire())
        self.assertEqual(server("qwabs4n", wire())["opid"], 1)
        variants = [row + " extra", row.replace(" 1 7 ", " 0 7 "),
                    row.replace(" 1 7 ", " 01 7 "),
                    row.replace(" 1 7 ", " 18446744073709551616 7 "),
                    row.replace(" 1 7 ", " 1 4294967296 "),
                    row.replace("angleop 0 ", "angleop -1 "),
                    row.replace("qwabs4n", "qwabs4b"),
                    row.replace("0a", "0b", 1),
                    row.replace(wire(), "0a0000c07f0000a04200000000")]
        for bad in variants:
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, hidcheck.angle_server_row, bad.split())

    def test_duplicate_capabilities_never_select_supported_last_value(self):
        text, scope = fixture()
        data, _ = rec_bytes()
        for declarations in ("anglecause 1\nanglecause 1", "anglecause 2\nanglecause 1",
                             "anglecause 1\nanglecause 2", "anglecause  1", "anglecause\t1",
                             " anglecause 1", "anglecause 1 "):
            with self.subTest(declarations=declarations):
                h = read(text.replace("anglecause 1", declarations), scope)
                self.assertTrue(h.faults)
                self.assertIsNone(h.info.get("anglecause_accounted_operations"))
                r = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(
                    b"anglecause 1", declarations.encode()))
                self.assertTrue(r.faults)
                self.assertFalse(getattr(r, "angle_ops", {}))

    def test_known_rec_row_preserves_canonical_physical_spelling(self):
        data, row = rec_bytes()
        for newline in (b"\n", b"\r\n"):
            positive = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(b"\n", newline))
            self.assertFalse(positive.faults, positive.faults)
            self.assertEqual(positive.info.get("anglecause_operations"), 1)
        for changed in (row + " ", " " + row, row.replace(" ", "  ", 1),
                        row.replace(" ", "\t", 1)):
            with self.subTest(changed=changed):
                r = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(
                    row.encode(), changed.encode()))
                self.assertTrue(r.faults)
                self.assertFalse(getattr(r, "angle_ops", {}))
                self.assertIsNone(r.info.get("anglecause_operations"))

    def test_rec_reader_declares_and_binds_active_nonce(self):
        data, row = rec_bytes()
        report = reccheck.check_rec("_anglecause_synthetic.rec", data=data)
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_operations"), 1)
        self.assertIn((NONCE, 1), report.angle_ops)
        for bad in (data.replace(b"anglecause 1\n", b""),
                    data.replace(row.encode(), (row + "\n" + row).encode()),
                    data.replace(row.encode(), row.replace(NONCE, "1" * 32).encode())):
            self.assertTrue(reccheck.check_rec("_anglecause_synthetic.rec", data=bad).faults)


if __name__ == "__main__":
    unittest.main(verbosity=2)
