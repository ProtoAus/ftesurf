"""Native structural reader controls; no native replay or hardware claim."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import heldmeta as h
import reccheck
import rcptcheck
import test_heldmeta as metadata
import test_rcptcheck as snapshots
import test_reccheck as grammar

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("held_census", HERE / "census/recsim.py")
census = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census)


def recording(*, events=None, counters=None, suffix=None, fzin=False, version=None):
    lines = grammar.v12_fixture(packets=3)
    version = h.NATIVE_VERSION if version is None else version
    lines[0] = "FTESURF-REC %d" % version
    if version == h.NATIVE_VERSION:
        lines = [line + " 0" if line.startswith("end ") else line for line in lines]
    if fzin:
        row = [i for i, line in enumerate(lines) if line.startswith("in ")][1]
        lines[row] = "fzin " + lines[row][3:]
    if suffix is None:
        if events is None:
            events, counters = metadata.fixture()
        if fzin:
            events = copy.deepcopy(events)
            [v for family, v in events if family == "hmove" and v["ownerkind"] == 1][1]["ownerkind"] = 2
        suffix = b"".join(metadata.seal(events, counters))
    return ("\n".join(lines) + "\n").encode() + suffix


class Framing(unittest.TestCase):
    def test_acting_seal_and_zero_based_combined_alias_control(self):
        for release in (False, True):
            with self.subTest(fzin=release):
                data = recording(fzin=release)
                framed = h.parse_recording(data)
                self.assertEqual(framed.witness.status, "sealed")
                aliases = [r.values for r in framed.witness.records
                           if r.family == "hmove" and r.values["ownerkind"] != 3]
                self.assertEqual([r["ownerindex"] for r in aliases], [0, 1, 2])
                self.assertEqual([r["ownerkind"] for r in aliases], [1, 2 if release else 1, 1])
                report = reccheck.check_rec("synthetic.rec", data=data)
                self.assertEqual(report.faults, [])
                self.assertEqual(report.info["version"], h.NATIVE_VERSION)
                self.assertEqual(report.info["held_status"], "sealed")
                self.assertTrue(any("not NativePASS" in note for note in report.notes))
                # Four executions, only THREE retained ordinary input payloads.
                self.assertEqual(len(aliases), 3)
                self.assertEqual(len([r for r in framed.witness.records if r.family == "hmove"]), 4)

    def test_relative_mc_versions_preserve_legacy_and_require_zero_origin(self):
        for version in (12, 13, 14, 15):
            if version in h.NATIVE_VERSIONS:
                data = recording(version=version)
            else:
                lines = grammar.v12_fixture(packets=3)
                lines[0] = "FTESURF-REC %d" % version
                if version == 14:
                    lines = [line + " 0" if line.startswith("end ") else line for line in lines]
                data = ("\n".join(lines) + "\n").encode()
            row = next(line for line in data.splitlines(keepends=True) if line.startswith(b"in "))
            packet = row.split()[1]
            for values, valid_new in ((b"0 0 0 0 0", True), (b"4 8 4 8 2", False),
                                      (b"0 0 0 0 1048576", False)):
                with self.subTest(version=version, values=values):
                    counts = b"mc " + packet + b" 0 " + values + b"\n"
                    report = reccheck.check_rec("counts.rec", data=data.replace(row, row + counts, 1))
                    self.assertEqual(report.ok, valid_new if version in (14, 15) else True, report.faults)
                    if report.ok:
                        self.assertEqual(report.info["mcs"], 1)
                        self.assertIn("recording-relative" if version in (14, 15) else "legacy", report.info["mc_scope"])

    def test_relative_mc_advance_and_reject_wrap_are_structural_not_native_proof(self):
        base = recording()
        rows = [line for line in base.splitlines(keepends=True) if line.startswith(b"in ")]
        first = b"mc " + rows[0].split()[1] + b" 0 0 0 0 0 0\n"
        second = b"mc " + rows[1].split()[1] + b" 1 2 1048575.5 2 1048575.5 3\n"
        data = base.replace(rows[0], rows[0] + first, 1).replace(rows[1], rows[1] + second, 1)
        report = reccheck.check_rec("counts.rec", data=data)
        self.assertTrue(report.ok, report.faults)
        self.assertEqual(report.info["mcs"], 2)
        self.assertTrue(any("not NativePASS" in note for note in report.notes))
        bad = data.replace(second, second.replace(b" 3\n", b" 1048576\n"), 1)
        self.assertTrue(any("relative 'mc' rejects" in fault for fault in reccheck.check_rec("counts.rec", data=bad).faults))

    def test_rehashed_alias_mismatches_cannot_hide_in_valid_ledger(self):
        events, counts = metadata.fixture()
        movers = [i for i, (family, v) in enumerate(events)
                  if family == "hmove" and v["ownerkind"] != 3]
        for field, value in (("ownerindex", 30), ("ownerkind", 2)):
            changed = copy.deepcopy(events)
            changed[movers[1]][1][field] = value
            suffix = b"".join(metadata.seal(changed, counts))
            self.assertEqual(h.parse_witness(suffix.splitlines(keepends=True)).status, "sealed")
            with self.assertRaisesRegex(h.Malformed, "alias"):
                h.parse_recording(recording(suffix=suffix))
        base = recording()
        ordinary = base[:base.index(b"hctx ")]
        row = next(line for line in ordinary.splitlines(keepends=True) if line.startswith(b"in "))
        for changed in (base.replace(row, b"", 1), base.replace(row, row + row, 1)):
            with self.assertRaisesRegex(h.Malformed, "alias|unowned"):
                h.parse_recording(changed)

    def test_framing_and_lexical_damage_are_not_normalized_away(self):
        base = recording()
        start = base.index(b"hctx ")
        suffix = base[start:]
        variants = [base[:start], base[:-1], base[:start] + suffix.replace(b"\n", b"\r\n"),
                    base + b"split 1 2\n", base + b"in 0 0 0 0 0 0 0 0 0 0 0\n",
                    base.replace(b"hctx ", b"hunknown ", 1),
                    base.replace(b"\nbegin\n", b"\nbegin\n" + suffix, 1)]
        for changed in variants:
            with self.subTest(case=variants.index(changed)):
                report = reccheck.check_rec("synthetic.rec", data=changed)
                self.assertFalse(report.ok)
                self.assertIsNone(report.held)
                self.assertIsNone(report.angles)

    def test_generic_failures_cannot_keep_detail(self):
        for status, word in ((1, "unsupported"), (2, "incomplete")):
            failure = metadata.encode("hfail", status=status)
            data = recording(suffix=failure)
            report = reccheck.check_rec("synthetic.rec", data=data)
            self.assertEqual(report.faults, [])
            self.assertEqual(report.info["held_status"], word)
            with self.assertRaises(h.Malformed):
                h.parse_recording(data + metadata.encode("hobs"))

    def test_generic_failure_does_not_apply_sealed_alias_cap_to_legacy_body(self):
        data = recording(suffix=metadata.encode("hfail", status=2))
        row = next(line for line in data.splitlines(keepends=True) if line.startswith(b"in "))
        long_recording = data.replace(row, row * (h.MAX_PIECES + 2), 1)
        self.assertEqual(h.parse_recording(long_recording).witness.status, "incomplete")
        with self.assertRaisesRegex(h.Malformed, "alias bound"):
            h.parse_recording(recording().replace(row, row * (h.MAX_PIECES + 2), 1))

    def test_initial_neutral_carrier_floor_is_observation_not_carrier_history(self):
        base = recording()
        first = next(line for line in base.splitlines(keepends=True) if line.startswith(b"in "))
        packet, mover = first.split()[1:3]
        floor = b"ride " + packet + b" " + mover + b" arm 0 -0 0\n"
        good = base.replace(first, floor + first, 1)
        self.assertEqual(h.parse_recording(good).witness.status, "sealed")
        self.assertEqual(h._neutral_ride_floor(floor), (int(packet), int(mover)))
        variants = [floor.replace(b"arm", b"pay"), floor.replace(b"0 -0 0", b"1 0 0"),
                    floor.replace(b"0 -0 0", b"1e-9999 0 0"), floor.replace(b"0 -0 0", b"0.0 0 0"),
                    floor[:-2] + b"\n", floor[:-1] + b" extra\n",
                    b"ride +" + packet + b" " + mover + b" arm 0 0 0\n",
                    b"ride 0" + packet + b" " + mover + b" arm 0 0 0\n",
                    b"ride " + str(int(packet) + 1).encode() + b" " + mover + b" arm 0 0 0\n",
                    b"ride " + packet + b" " + str(int(mover) + 1).encode() + b" arm 0 0 0\n"]
        for bad in variants:
            with self.subTest(floor=bad):
                with self.assertRaisesRegex(h.Malformed, "incompatible ordinary history"):
                    h.parse_recording(base.replace(first, bad + first, 1))
        for bad in (base.replace(first, floor + floor + first, 1),
                    base.replace(first, first + floor, 1),
                    base.replace(b"\nbegin\n", b"\nbegin\n" + floor, 1),
                    base.replace(first, floor + first.replace(b"in ", b"fzin ", 1), 1)):
            with self.assertRaisesRegex(h.Malformed, "incompatible ordinary history"):
                h.parse_recording(bad)
        # A refused profile still frames legacy carrier activity; it does not
        # retain any rejected detailed witness or pretend a carrier was modeled.
        generic = recording(suffix=metadata.encode("hfail", status=1))
        for bad in variants:
            self.assertEqual(h.parse_recording(generic.replace(first, bad + first, 1)).witness.status,
                             "unsupported")

    def test_native_metadata_cannot_be_downgraded_to_legacy(self):
        changed = recording().replace(("FTESURF-REC %d\n" % h.NATIVE_VERSION).encode(),
                                      ("FTESURF-REC %d\n" % h.BASE_VERSION).encode(), 1)
        report = reccheck.check_rec("synthetic.rec", data=changed)
        self.assertTrue(any("held metadata" in fault and "header framing" in fault for fault in report.faults))

    def test_public13_and_relative14_park_clocks_are_not_native_frames(self):
        for version in (13, 14):
            for gap in (None, 0, 5, 86401):
                with self.subTest(version=version, gap=gap):
                    lines = grammar.v13_fixture(gap)
                    lines[0] = "FTESURF-REC %d" % version
                    data = ("\n".join(lines) + "\n").encode()
                    self.assertFalse(h.is_native_recording(data))
                    report = reccheck.check_rec("park.rec", data=data)
                    self.assertEqual(report.faults, [])
                    self.assertIsNone(report.held)
                    self.assertEqual(report.info["park_edges"], int(gap is not None))
                    if gap is not None:
                        self.assertIn("offline gap: physical continuation not modelled", report.angle_epoch)
                    bad = data.replace(b"parkclock 5 5", b"parkclock 5 4")
                    if bad != data:
                        self.assertTrue(reccheck.check_rec("bad.rec", data=bad).faults)

    def test_native_version_and_namespace_cannot_fall_back_to_ordinary13(self):
        for version in h.NATIVE_VERSIONS:
            data = recording(version=version)
            self.assertTrue(h.is_native_recording(data))
            for changed in (data.replace(b"hctx ", b"hunknown ", 1), data.replace(b"\n", b"\r\n")):
                self.assertTrue(h.is_native_recording(changed))
                self.assertFalse(reccheck.check_rec("bad.rec", data=changed).ok)
        stripped = recording().split(b"hctx ", 1)[0]
        self.assertTrue(h.is_native_recording(stripped))
        self.assertFalse(reccheck.check_rec("stripped.rec", data=stripped).ok)
        historical = recording(version=13).split(b"hctx ", 1)[0]
        self.assertFalse(h.is_native_recording(historical))
        self.assertFalse(reccheck.check_rec("stripped13.rec", data=historical).ok)
        # Public13's park-count field is mandatory; old private13 stays old12-body.
        public = ("\n".join(grammar.v13_fixture()) + "\n").encode()
        self.assertTrue(reccheck.check_rec("public.rec", data=public).ok)

    def test_unknown_rule_is_not_an_admitted_profile(self):
        events, counts = metadata.fixture()
        events[0][1]["rules"] = 2
        with self.assertRaisesRegex(h.Malformed, "unsupported rules"):
            h.parse_recording(recording(events=events, counters=counts))


class Captures(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "data/evidence/testmap/fixture.rec"
        self.path.parent.mkdir(parents=True)

    def test_census_validates_profile_in_both_capture_modes(self):
        for version in h.NATIVE_VERSIONS:
            data = recording(fzin=True, version=version)
            for limits in ({}, {"max_bytes": len(data), "max_moves": 3}):
                with self.subTest(version=version, limits=limits):
                    self.path.write_bytes(data)
                    got = census.parse_rec(str(self.path), strict=True, **limits)
                    self.assertEqual((got.ver, len(got.moves)), (version, 3))
                    changed = data.replace(b"hctx ", b"hunknown ", 1)
                    self.path.write_bytes(changed)
                    self.assertIsNone(census.parse_rec(str(self.path), **limits))
                    self.path.write_bytes(data[:data.index(b"hctx ")] + data[data.index(b"hctx "):].replace(b"\n", b"\r\n"))
                    self.assertIsNone(census.parse_rec(str(self.path), **limits))
            self.path.write_bytes(data.replace(("FTESURF-REC %d" % version).encode(),
                                              ("FTESURF-REC %d" % (version - 1)).encode(), 1))
            self.assertIsNone(census.parse_rec(str(self.path)))

    def receipt(self):
        r = rcptcheck.Receipt("synthetic.rcpt")
        r.head.update(runid="fixture", map="testmap")
        r.signed = [("ticks", "1")]
        return r

    def test_receipt_uses_original_bytes_after_acting_close_time_replacement(self):
        data = recording().replace(b"\nbegin\n", b"\nrunid fixture\nbegin\n", 1)
        start = data.index(b"hctx ")
        changed = data[:start] + data[start:].replace(b"\n", b"\r\n")
        self.path.write_bytes(data)
        with mock.patch.object(rcptcheck, "GAME", str(self.root)):
            r = self.receipt()
            with snapshots.swap_after_close(str(self.path), changed) as state:
                rcptcheck.join_rec(r)
            self.assertEqual(state, {"reads": 1, "swaps": 1})
            self.assertEqual(r.recdata, data)
            self.assertTrue(rcptcheck.recording_report(r).ok)
            self.assertIs(rcptcheck.recording_report(r), r.rec_report)
            later = self.receipt()
            rcptcheck.join_rec(later)
            self.assertEqual(later.recdata, changed)
            self.assertFalse(rcptcheck.recording_report(later).ok)

    def test_legacy_cr_only_header_discovery_still_uses_exact_bytes(self):
        lines = grammar.v11_fixture(packets=3)
        data = ("\n".join(lines) + "\n").encode().replace(b"\nbegin\n", b"\nrunid fixture\nbegin\n", 1)
        for newline in (b"\n", b"\r\n", b"\r"):
            original = data.replace(b"\n", newline)
            self.path.write_bytes(original)
            with mock.patch.object(rcptcheck, "GAME", str(self.root)):
                r = self.receipt()
                rcptcheck.join_rec(r)
                self.assertEqual(r.recdata, original)
                self.assertTrue(rcptcheck.recording_report(r).ok)


if __name__ == "__main__":
    unittest.main()
