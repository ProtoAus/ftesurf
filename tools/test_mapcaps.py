#!/usr/bin/env python3
"""Offline controls for tools/mapcaps.py: source precedence, merging into existing files, reruns."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapcaps  # noqa: E402

LUMP = ("// %s -- per-map ruleset, generated from the map's own entity lump.\n"
        "// WHAT THE MAP SAYS:\n//   logic_auto OnMapSpawn x,Command,sv_maxvelocity %s,0,-1\n\nset sv_maxvelocity %s\n")


def slurp(p):
    with open(p) as f:
        return f.read()


def spit(p, text):
    with open(p, "w") as f:
        f.write(text)


class Caps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.zones, self.cfg = os.path.join(d, "zones"), os.path.join(d, "maps")
        os.mkdir(self.zones)
        os.mkdir(self.cfg)
        self.cat = os.path.join(d, "cat.json")
        self.ksf = os.path.join(d, "ksf.tsv")
        self.lst = os.path.join(d, "mapdl.txt")
        self.mom = {}       # Momentum catalogue name -> zone maxVelocity (None: no zone file)
        self.k = {}
        self.rows = []      # (name, of)

    def tearDown(self):
        self.tmp.cleanup()

    def lump(self, name, v, extra=""):
        with open(os.path.join(self.cfg, "map_%s.cfg" % name), "w") as f:
            f.write(LUMP % (name, v, v) + extra)

    def run_tool(self, write=True):
        spit(self.cat, json.dumps({n: {"id": 1} for n in self.mom}))
        for n in os.listdir(self.zones):
            os.remove(os.path.join(self.zones, n))
        for n, v in self.mom.items():
            if v is not None:
                body = {"formatVersion": 1, "tracks": {}}
                if v != "absent":
                    body["maxVelocity"] = v
                spit(os.path.join(self.zones, n + ".json"), json.dumps(body))
        with open(self.ksf, "w") as f:
            f.writelines("%s\t%s\t1\n" % kv for kv in self.k.items())
        with open(self.lst, "w") as f:
            f.write("FTESURF-MAPDL 1\n")
            for n, of in self.rows:
                f.write("dl %s surf m 1 1 2026-11-20 0 1 0 %s 1 1\n" % (n, of or "-"))
        tsv = os.path.join(self.tmp.name, "out.tsv")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mapcaps.main(["--list", self.lst, "--catalogue", self.cat, "--zones", self.zones, "--ksf", self.ksf,
                          "--cfgdir", self.cfg, "--tsv", tsv] + (["--write"] if write else []))
        rows = [ln.rstrip("\n").split("\t") for ln in slurp(tsv).splitlines()][1:]
        return {r[0]: dict(src=r[2], want=r[3], action=r[6]) for r in rows}, out.getvalue()

    def cap(self, name):
        p = os.path.join(self.cfg, "map_%s.cfg" % name)
        if not os.path.exists(p):
            return None
        text = slurp(p)
        v = [ln.split()[-1] for ln in text.splitlines() if mapcaps.SETLINE.match(ln)]
        self.assertEqual(len(v), 1, text)
        return v[0]

    def test_precedence(self):
        self.mom = {"surf_m": 10000, "surf_m0": 0, "surf_mabs": "absent", "surf_unk": None, "surf_p": 5000,
                    "surf_q": 0, "surf_eq": 3500}
        self.k = {"surf_m": 5000, "surf_m0": 9999, "surf_mabs": 4000, "surf_unk": 7500, "surf_k": 4500,
                  "surf_k0": 0, "surf_p": 4000}
        self.rows = [("surf_m", None), ("surf_m0", None), ("surf_mabs", None), ("surf_unk", None),
                     ("surf_p_css", "surf_p"), ("surf_q_css", "surf_q"), ("surf_q_fix", "surf_q"),
                     ("surf_k", None), ("surf_k0", None), ("surf_none", None), ("surf_eq", None)]
        self.lump("surf_m", 4500)           # Momentum's zone beats the map's own lump
        self.lump("surf_m0", 6000)          # zone 0: the lump, not KSF
        self.lump("surf_q", 8000)           # plain map zone 0: its lump for the second build
        self.lump("surf_q_fix", 9000)       # ...unless the build has its own
        self.lump("surf_k0", 5000)          # KSF 0: the lump
        got, _ = self.run_tool()
        want = {"surf_m": ("mom", "10000"), "surf_m0": ("lump", "6000"), "surf_mabs": ("-", None),
                "surf_unk": ("ksf", "7500"), "surf_p_css": ("mom:surf_p", "5000"),
                "surf_q_css": ("lump:surf_q", "8000"), "surf_q_fix": ("lump", "9000"),
                "surf_k": ("ksf", "4500"), "surf_k0": ("lump", "5000"), "surf_none": ("-", None),
                "surf_eq": ("mom", None)}
        for n, (src, cap) in want.items():
            self.assertEqual(got[n]["src"], src, n)
            self.assertEqual(self.cap(n), cap, n)
        self.assertIn("// mapcaps src=mom lump=4500", slurp(os.path.join(self.cfg, "map_surf_m.cfg")))
        self.assertIn("WHAT THE MAP SAYS", slurp(os.path.join(self.cfg, "map_surf_m.cfg")))

    def test_lower_and_other_lines_kept(self):
        self.mom = {"surf_v": 3500}
        self.rows = [("surf_v", None)]
        self.lump("surf_v", 10000, "\n// hands-off map\nset run_startjitter 0\n")
        got, out = self.run_tool()
        self.assertEqual(self.cap("surf_v"), "3500")
        text = slurp(os.path.join(self.cfg, "map_surf_v.cfg"))
        self.assertIn("set run_startjitter 0", text)
        self.assertIn("lower 1", out)

    def test_rerun_is_stable_and_restores_the_lump(self):
        self.mom = {"surf_a": 10000, "surf_b": 5000}
        self.rows = [("surf_a", None), ("surf_b", None)]
        self.lump("surf_a", 6000)
        self.run_tool()
        first = {n: slurp(os.path.join(self.cfg, n)) for n in os.listdir(self.cfg)}
        got, _ = self.run_tool()
        self.assertEqual({r["action"] for r in got.values()}, {"same"})
        self.assertEqual({n: slurp(os.path.join(self.cfg, n)) for n in os.listdir(self.cfg)}, first)
        self.mom = {"surf_a": 0, "surf_b": 0}       # both catalogues drop their caps
        got, _ = self.run_tool()
        self.assertEqual(got["surf_a"]["action"], "restore")
        self.assertEqual(self.cap("surf_a"), "6000")
        self.assertNotIn("mapcaps", slurp(os.path.join(self.cfg, "map_surf_a.cfg")))
        self.assertEqual(got["surf_b"]["action"], "remove")
        self.assertIsNone(self.cap("surf_b"))

    def test_unreadable_file_skipped_and_report_only_writes_nothing(self):
        self.mom = {"surf_x": 10000, "surf_y": 10000}
        self.rows = [("surf_x", None), ("surf_y", None)]
        p = os.path.join(self.cfg, "map_surf_x.cfg")
        spit(p, "set sv_maxvelocity 4000\nset sv_maxvelocity 5000\n")
        got, out = self.run_tool(write=False)
        self.assertEqual(got["surf_x"]["action"], "skip")
        self.assertIn("SKIP", out)
        self.assertEqual(sorted(os.listdir(self.cfg)), ["map_surf_x.cfg"])
        self.run_tool()
        self.assertEqual(slurp(p), "set sv_maxvelocity 4000\nset sv_maxvelocity 5000\n")
        self.assertEqual(self.cap("surf_y"), "10000")

    def test_path_names_refused(self):
        self.mom = {"surf_ok": 10000}
        self.rows = [("surf_ok", None), ("../evil", None)]
        with contextlib.redirect_stderr(io.StringIO()):
            got, _ = self.run_tool()
        self.assertNotIn("../evil", got)
        self.assertEqual(sorted(os.listdir(self.cfg)), ["map_surf_ok.cfg"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
