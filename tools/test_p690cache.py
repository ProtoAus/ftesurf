"""Acted positive/negative controls for the offline P690 cache evidence grader.

All PNGs and receipts here are SYNTHETIC detector tests, never native evidence.
Output must be a fresh operator-owned directory (no implicit temp/install writes).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest

import numpy as np
from PIL import Image

import p690cache as g

OUTPUT = None


class CacheGradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = OUTPUT
        cls.root.mkdir(parents=True, exist_ok=False)
        cls.receipts = []
        cls.pictures = {}
        opaque = np.zeros((720, 960, 3), dtype=np.uint8)
        opaque[:100, :100] = [255, 0, 0]
        opaque[300:420, 440:560] = [0, 0, 255]
        red_over_blue = np.zeros_like(opaque)
        red_over_blue[300:420, 440:560] = [127, 0, 64]
        blue_over_red = np.zeros_like(opaque)
        blue_over_red[300:420, 440:560] = [64, 0, 127]
        for name, a in (("opaque.png", opaque), ("red-over-blue.png", red_over_blue),
                        ("blue-over-red.png", blue_over_red)):
            Image.fromarray(a).save(cls.root / name)
            cls.pictures[name] = a
        cls.base = dict(schema=1, restored=True,
                        fixtures={n: hashlib.sha256(b).hexdigest() for n, b in g.fixture_payloads().items()},
                        bundles={a: dict(stamp=g.STAMPS[a], hashes=g.HASHES[a], staged=g.HASHES[a],
                                         version="SYNTHETIC " + g.STAMPS[a]) for a in g.ARMS}, shots=[])
        for arm in g.ARMS:
            for kind in g.KINDS:
                for mode in (1, 2):
                    for phase in g.PHASES:
                        for rep in ("a", "b"):
                            name = "opaque.png" if kind == "opaque" else (
                                "blue-over-red.png" if phase == "cached" or (mode == 2 and arm in ("merged", "probe"))
                                else "red-over-blue.png")
                            counter = 1000 if rep == "a" else 1200
                            actor = dict(ticket=1 if rep == "a" else 2,
                                         ordinary=0 if g.CACHE[phase] else counter,
                                         cached=counter if g.CACHE[phase] else 0,
                                         world=f"maps/mv12_cache_{kind}.bsp", fromgame=0, flags="0x0",
                                         requested=g.CACHE[phase], inuse=g.CACHE[phase],
                                         eye="0.062,0.062,64.062", angles="0.000,0.000,0.000", mode=mode)
                            cls.base["shots"].append(dict(arm=arm, kind=kind, mode=mode, phase=phase, rep=rep,
                                cache=g.CACHE[phase], path=name, sha256=g.sha(cls.root / name), stamp=g.STAMPS[arm],
                                world=actor["world"], body="0,0,0", aim="0,0,0", velocity="0,0,0",
                                actor=actor if arm == "probe" else None))

    @classmethod
    def tearDownClass(cls):
        (cls.root / "negative-results.json").write_text(json.dumps(cls.receipts, indent=2) + "\n")

    def evidence(self, data):
        (self.root / "capture.json").write_text(json.dumps(data) + "\n")
        return g.grade(self.root)

    def reject(self, name, mutate, reason):
        data = copy.deepcopy(self.base)
        mutate(data)
        with self.assertRaisesRegex(g.GateError, reason) as caught:
            self.evidence(data)
        self.receipts.append(dict(control=name, status="REJECTED_AS_EXPECTED", error=str(caught.exception)))

    @staticmethod
    def probe(data, phase="cached", rep="b"):
        return next(s for s in data["shots"] if (s["arm"], s["kind"], s["mode"], s["phase"], s["rep"])
                    == ("probe", "opaque", 1, phase, rep))

    def replace_image(self, data, select, pixels, name):
        path = self.root / name
        Image.fromarray(pixels).save(path)
        for row in data["shots"]:
            if select(row):
                row["path"] = name
                row["sha256"] = g.sha(path)

    def test_positive(self):
        result = self.evidence(copy.deepcopy(self.base))
        self.assertTrue(result["opaque"].startswith("PASS"))
        self.assertEqual(len(result["actors"]), 12)
        self.assertEqual(result["legacy_unstable"], [])
        self.assertTrue(all(p["status"] == "PASS" for p in result["alpha"]))

    def test_acted_counter_negatives(self):
        cases = (
            ("frozen-cached", "cached", 1000, "cache branch NOT REACHED"),
            ("mixed-ordinary", "ordinary", 20, "cache branch NOT REACHED"),
            ("wrong-world", "world", "maps/surf_kitsune.bsp", "not supported Q1"),
            ("Source-not-supported", "fromgame", 4, "not supported Q1"),
            ("request-did-not-act", "requested", 0, "settings did not act"),
            ("effective-forced-off", "inuse", 0, "settings did not act"),
            ("wrong-render-mode", "mode", 2, "settings did not act"),
            ("wrong-rendered-eye", "eye", "0.062,0.062,22", "wrong rendered camera"),
            ("wrong-rendered-angle", "angles", "0,1,0", "wrong rendered camera"),
            ("frozen-ticket", "ticket", 1, "ticket did not advance"),
        )
        for name, field, value, reason in cases:
            with self.subTest(name=name):
                self.reject(name, lambda d, f=field, v=value: self.probe(d)["actor"].update({f: v}), reason)
        self.reject("ordinary-path-frozen", lambda d: self.probe(d, "initial")["actor"].update(ordinary=1000),
                    "cache branch NOT REACHED")
        def stale_age(d):
            row = self.probe(d)
            row["actor"]["cached"] = 1000
            row["waterinfo"] = 'wanted 1, in use 1; MarkLeaves last ran 20 seconds ago'
        self.reject("cvar-and-stale-age-not-actor", stale_age, "cache branch NOT REACHED")

    def test_acted_metadata_negatives(self):
        self.reject("missing-row", lambda d: d["shots"].pop(), "missing evidence rows")
        self.reject("duplicate-row", lambda d: d["shots"].append(copy.deepcopy(d["shots"][0])), "duplicate shot")
        self.reject("unrestored", lambda d: d.update(restored=False), "restoration not verified")
        self.reject("wrong-fixture-bytes", lambda d: d["fixtures"].update({"mv12_cache_opaque.bsp": "0" * 64}),
                    "wrong/unbound fixture")
        self.reject("wrong-runtime-stamp", lambda d: d["bundles"]["merged"].update(stamp=g.STAMPS["p688"]),
                    "wrong runtime stamp")
        self.reject("missing-runtime-observation", lambda d: d["bundles"]["merged"].update(version="version command sent"),
                    "version not observed")
        self.reject("unstaged-native", lambda d: d["bundles"]["merged"]["staged"].update({g.FILES[0]: "0" * 64}),
                    "wrong/unstaged exact bundle")
        def same_wrong_hash(d):
            for field in ("hashes", "staged"):
                d["bundles"]["merged"][field][g.FILES[0]] = "0" * 64
        self.reject("self-consistent-wrong-binary", same_wrong_hash, "wrong/unstaged exact bundle")
        self.reject("wrong-shot-world", lambda d: d["shots"][0].update(world="maps/nope.bsp"), "wrong shot world")
        self.reject("moved-body", lambda d: d["shots"][0].update(body="0,0,1"), "camera/body/velocity moved")
        self.reject("moved-velocity", lambda d: d["shots"][0].update(velocity="0,0,1"), "camera/body/velocity moved")
        self.reject("wrong-phase", lambda d: d["shots"][0].update(cache=1), "wrong phase/cache")
        self.reject("tampered-PNG", lambda d: d["shots"][0].update(sha256="0" * 64), "changed screenshot")
        self.reject("outside-PNG", lambda d: d["shots"][0].update(path="../opaque.png"), "relative to evidence")

    def test_acted_pixel_negatives(self):
        black = np.zeros((720, 960, 3), dtype=np.uint8)
        self.reject("empty-opaque", lambda d: self.replace_image(d, lambda r: r["kind"] == "opaque", black, "empty.png"),
                    "no authored colours")
        wrong_depth = self.pictures["opaque.png"].copy()
        wrong_depth[360, 480] = [255, 0, 0]
        self.reject("wrong-opaque-depth", lambda d: self.replace_image(d, lambda r: r["kind"] == "opaque", wrong_depth, "depth.png"),
                    "nearest-depth witness lost")
        lost = self.pictures["opaque.png"].copy()
        lost[50, 50] = [0, 0, 0]
        self.reject("cache-lost-geometry", lambda d: self.replace_image(d, lambda r: r["arm"] == "merged"
                    and r["kind"] == "opaque" and r["phase"] == "cached", lost, "lost.png"), "pixel mismatch")
        self.reject("diagnostic-production-mismatch", lambda d: self.replace_image(d, lambda r: r["arm"] == "probe"
                    and r["kind"] == "opaque", lost, "probe-lost.png"), "pixel mismatch")
        self.reject("return-did-not-restore", lambda d: self.replace_image(d, lambda r: r["arm"] == "merged"
                    and r["kind"] == "opaque" and r["phase"] == "return", lost, "return-lost.png"), "pixel mismatch")
        self.reject("unstable-repeat", lambda d: self.replace_image(d, lambda r: r["arm"] == "merged"
                    and r["kind"] == "opaque" and r["phase"] == "initial" and r["rep"] == "b", lost, "unstable.png"), "pixel mismatch")
        self.reject("sorter-never-acted", lambda d: self.replace_image(d, lambda r: r["kind"] == "alpha"
                    and r["arm"] in ("merged", "probe") and r["mode"] == 2 and r["phase"] != "cached",
                    self.pictures["red-over-blue.png"], "no-sort.png"), "mode2 did not act")

    def test_legacy_instability_is_not_parity_acceptance(self):
        d = copy.deepcopy(self.base)
        self.replace_image(d, lambda r: r["arm"] == "p688-return" and r["kind"] == "alpha" and r["mode"] == 1,
                           self.pictures["blue-over-red.png"], "legacy-return.png")
        result = self.evidence(d)
        self.assertEqual(len(result["legacy_unstable"]), 2)  # cached already had blue-over-red
        self.assertEqual(sum(p["status"] == "UNSTABLE_LEGACY_NOT_ACCEPTED" for p in result["alpha"]), 2)
        self.assertTrue(result["opaque"].startswith("PASS"))

    def test_cli_complete_incomplete_refusal_and_optimized(self):
        self.evidence(copy.deepcopy(self.base))
        script = Path(g.__file__)
        def cli(name):
            return subprocess.run([sys.executable, "-B", "-O", str(script), "grade",
                                   "--evidence", str(self.root), "--result", str(self.root / name)],
                                  capture_output=True, text=True)
        complete = cli("cli-complete.json")
        self.assertEqual(complete.returncode, 0, complete.stderr)
        self.assertEqual(json.loads((self.root / "cli-complete.json").read_text())["verdict"], "PASS bounded matrix")
        digest = g.sha(self.root / "cli-complete.json")
        self.assertNotEqual(cli("cli-complete.json").returncode, 0)
        self.assertEqual(g.sha(self.root / "cli-complete.json"), digest)
        d = copy.deepcopy(self.base)
        self.replace_image(d, lambda r: r["arm"] == "p688-return" and r["kind"] == "alpha" and r["mode"] == 1,
                           self.pictures["blue-over-red.png"], "legacy-cli.png")
        (self.root / "capture.json").write_text(json.dumps(d) + "\n")
        incomplete = cli("cli-incomplete.json")
        self.assertNotEqual(incomplete.returncode, 0)
        self.assertIn("INCOMPLETE", incomplete.stderr)
        self.assertEqual(json.loads((self.root / "cli-incomplete.json").read_text())["verdict"],
                         "INCOMPLETE alpha legacy parity")
        d = copy.deepcopy(self.base)
        self.probe(d)["actor"]["cached"] = 1000
        (self.root / "capture.json").write_text(json.dumps(d) + "\n")
        broken = cli("cli-rejected.json")
        self.assertNotEqual(broken.returncode, 0)
        self.assertIn("NOT REACHED", broken.stderr)
        self.assertFalse((self.root / "cli-rejected.json").exists())
        (self.root / "capture.json").write_text("null\n")
        self.assertNotEqual(cli("cli-malformed.json").returncode, 0)
        self.assertFalse((self.root / "cli-malformed.json").exists())

    def test_fixtures_are_deterministic_and_do_not_overwrite(self):
        out = self.root / "fixtures"
        manifest = g.create_fixtures(out)
        self.assertEqual(manifest, self.base["fixtures"])
        self.assertEqual(struct.unpack_from("<i", (out / "mv12_cache_opaque.bsp").read_bytes())[0], 29)
        with self.assertRaises(FileExistsError):
            g.create_fixtures(out)
        self.assertNotEqual(g.fixture_bytes("opaque"), g.fixture_bytes("alpha"))
        with self.assertRaises(g.GateError):
            g.parse_actor('wanted 1, in use 1; MarkLeaves last ran 20 seconds ago')


def main():
    global OUTPUT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    OUTPUT = a.output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CacheGradeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
