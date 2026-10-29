#!/usr/bin/env python3
"""P1113: map_tiers takes Momentum's tier from mapwatch's catalogue, then momtracks.tsv's,
then KSF's. Run from surfd/ with python -B."""
import json
import logging
import os
import shutil
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="maptiers-")
TSV, CAT = os.path.join(HOME, "momtracks.tsv"), os.path.join(HOME, "catalogue.json")
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, "test.db"), SURFD_MAPS=os.path.join(HOME, "maps"),
                  SURFD_MOMTRACKS=TSV, SURFD_MAPWATCH_CATALOGUE=CAT)
import surfd as S


def write(tsv_rows, cat_maps):
    with open(TSV, "w") as f:
        f.write("# map\tmapid\ttier\n" + "".join("%s\t1\t%d\n" % r for r in tsv_rows))
    with open(CAT, "w") as f:
        json.dump({"at": 0, "maps": cat_maps}, f)


class Tiers(unittest.TestCase):
    clock = 1e9

    def t(self):
        Tiers.clock += 10 * S.MOMTRACKS_TTL               # past the cache each call, and forward
        return S.map_tiers(now=Tiers.clock)

    def test_order(self):
        write([("surf_a", 3), ("surf_b", 4), ("surf_old", 2)],
              {"surf_a": {"mtier": 5, "ktier": 1},          # the catalogue's Momentum tier wins
               "surf_b": {"mtier": None, "ktier": 7},        # momtracks' beats KSF's
               "surf_anubis": {"mtier": None, "ktier": 8},   # KSF's when Momentum has none
               "surf_anubis_ksf": {"ktier": 8, "of": "surf_anubis"},
               "Surf_Caps": {"ktier": 2},
               "surf_none": {"mtier": None},
               "surf_bad": {"mtier": True, "ktier": 99}})
        t = self.t()
        self.assertEqual((t["surf_a"], t["surf_b"], t["surf_old"], t["surf_anubis"], t["surf_anubis_ksf"], t["surf_caps"]),
                         (5, 4, 2, 8, 8, 2))
        self.assertNotIn("surf_none", t)
        self.assertNotIn("surf_bad", t)

    def test_no_catalogue_is_momtracks(self):
        write([("surf_a", 3)], {})
        os.remove(CAT)
        self.assertEqual(self.t(), {"surf_a": 3})

    def test_neither_is_none(self):
        os.remove(TSV) if os.path.exists(TSV) else None
        os.remove(CAT) if os.path.exists(CAT) else None
        self.assertIsNone(self.t())


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        logging.shutdown(); shutil.rmtree(HOME)
