#!/usr/bin/env python3
"""Offline controls for the public map/leg rating importer (no player data)."""
import csv
import io
import pathlib
import unittest

import shipguard

import maptiers as mt
import mapmeta


def lb(kind=0, num=1, tier=3, gm=1, style=0):
    return dict(trackType=kind, trackNum=num, tier=tier, gamemode=gm, style=style)


def maprow(status=0, rows=None, suggestions=None):
    return dict(name="surf_test", status=status, leaderboards=rows or [],
                submission=dict(suggestions=suggestions or []))


def sheet(*rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerows([["Tiers:", "", "", "Unit Bonuses", "", "", "", "Strafe Bonuses"],
                 ["IMPORTANT:"], ["Editors:"], *rows])
    return out.getvalue()


class Ratings(unittest.TestCase):
    def test_ranked_map_stage_bonus_independent(self):
        table = {}
        mt.momentum(table, [maprow(rows=[lb(tier=4), lb(1, 2, 2), lb(2, 3, 7),
                                                lb(1, 4, None), lb(2, 5, 0)])])
        self.assertEqual(table["surf_test", 0, 0][:2], ["4", "rank"])
        self.assertEqual(table["surf_test", 0, 2][:2], ["2", "rank"])
        self.assertEqual(table["surf_test", 3, 0][:2], ["7", "rank"])
        self.assertNotIn(("surf_test", 0, 4), table)
        self.assertNotIn(("surf_test", 5, 0), table)
        self.assertNotIn(("surf_test_css", 0, 0), table)

    def test_suggestions_only_for_public_submissions(self):
        for status in (2, 3, 4):
            table = {}
            mt.momentum(table, [maprow(status, [lb(tier=10)],
                                     [lb(tier=5), lb(1, 1, 2), lb(2, 1, 8)])])
            self.assertEqual(table["surf_test", 0, 0][:2], ["5", "sugg"])
            self.assertEqual(table["surf_test", 0, 1][:2], ["2", "sugg"])
            self.assertEqual(table["surf_test", 1, 0][:2], ["8", "sugg"])
        table = {}
        mt.momentum(table, [maprow(rows=[lb(tier=3)], suggestions=[lb(tier=8)])])
        self.assertEqual(table["surf_test", 0, 0][:2], ["3", "rank"])

    def test_private_and_disabled_never_published(self):
        for status in (1, 5, None, 99):
            table = {}
            mt.momentum(table, [maprow(status, [lb()], [lb(2, 1, 6)])])
            self.assertEqual(table, {})

    def test_mode_and_style_filters_act(self):
        table = {}
        mt.momentum(table, [maprow(rows=[lb(), lb(1, 1, 7, style=2),
                                                lb(1, 2, 6, gm=2), lb(2, 1, 4)])])
        self.assertNotIn(("surf_test", 0, 1), table)
        self.assertNotIn(("surf_test", 0, 2), table)
        self.assertEqual(table["surf_test", 1, 0][0], "4")

    def test_pro_fallback_not_mixed(self):
        table = {}
        mt.momentum(table, [maprow(rows=[lb(style=mapmeta.ST_PRO), lb(2, 1, 6, style=mapmeta.ST_PRO),
                                                lb(2, 2, 9, style=0)])])
        self.assertEqual(table["surf_test", 1, 0][0], "6")
        self.assertNotIn(("surf_test", 2, 0), table)

    def test_main_numeric_ksf_not_mom(self):
        table = {}
        mt.ksf_main(table, "Map name,Tier,Type\nsurf_test,6,Staged\nsurf_unknown,0,Linear\n")
        self.assertEqual(table["surf_test", 0, 0], ["-", "-", "6", "-", "-"])
        mt.momentum(table, [maprow(rows=[lb(tier=3)])])
        self.assertEqual(table["surf_test", 0, 0][:3], ["3", "rank", "6"])
        self.assertNotIn(("surf_unknown", 0, 0), table)

    def test_maplist_fills_by_exact_name(self):
        table = {}
        mt.ksf_main(table, "Map name,Tier\nsurf_test,4\nsurf_old,6\n")
        text = ("FTESURF-MAPDL 1\n# comment\n"
                "dl surf_test_css surf k 1 300 2026-10-11 0 0 2 surf_test 1 1\n"
                "dl surf_test surf km 1 300 2026-10-11 0 1 4 - 1 1\n"
                "dl surf_old surf km 1 300 2026-10-11 0 1 7 - 1 1\n"
                "dl surf_none surf m 1 300 2026-10-11 0 1 0 - 1 1\n"
                "dl surf_port surf m 1 300 2026-10-11 0 0 3 - 1 1\n"
                "dl ../bad surf k 1 300 2026-10-11 0 0 3 - 1 1\n")
        filled, moved = mt.ksf_maplist(table, text)
        self.assertEqual(filled, ["surf_test_css", "surf_port"])
        self.assertEqual(table["surf_port", 0, 0], ["-", "-", "3", "-", "-"])
        self.assertEqual(moved, ["surf_old 6->7"])
        self.assertEqual(table["surf_test_css", 0, 0], ["-", "-", "2", "-", "-"])
        self.assertEqual(table["surf_test", 0, 0][2], "4")
        self.assertNotIn(("surf_none", 0, 0), table)
        with self.assertRaises(ValueError):
            mt.ksf_maplist({}, "not a map list\n")

    def test_first_ratings_share_note_rows(self):
        table = {}
        text = sheet(["", "", "", "tail b3", "G Tier"])
        rows = list(csv.reader(io.StringIO(text)))
        rows[1] = ["IMPORTANT:", "", "", "first b1", "X Tier"]
        rows[2] = ["Editors:", "", "", "second b2", "S Tier"]
        out = io.StringIO()
        csv.writer(out).writerows(rows)
        mt.ksf_bonus(table, out.getvalue())
        self.assertEqual(table["surf_first", 1, 0][3], "X")
        self.assertEqual(table["surf_second", 2, 0][3], "S")
        self.assertEqual(len(table), 3)

    def test_bonus_split_and_pending(self):
        table = {}
        counts = mt.ksf_bonus(table, sheet(
            ["", "", "", "pls b4 (1/2)", "Y Tier", "", "", "pls b4 (2/2)", "S Tier", "", "", "new b1", "Unit"],
            ["", "", "", "surf_other b2", "? Tier"]))
        self.assertEqual(table["surf_pls", 4, 0], ["-", "-", "-", "Y", "S"])
        self.assertEqual(table["surf_other", 2, 0][3], "?")
        self.assertNotIn(("surf_new", 1, 0), table)
        self.assertEqual(counts[3], 2)
        self.assertEqual(counts[4], 1)

    def test_duplicates_fail_not_last_writer_wins(self):
        with self.assertRaisesRegex(ValueError, "conflicting MOM"):
            mt.momentum({}, [maprow(rows=[lb(), lb(tier=9)])])
        with self.assertRaisesRegex(ValueError, "conflicting KSF main"):
            mt.ksf_main({}, "Map,Tier\nsurf_test,2\nsurf_test,8\n")
        with self.assertRaisesRegex(ValueError, "conflicting KSF bonus"):
            mt.ksf_bonus({}, sheet(["", "", "", "test b1", "X Tier"],
                                   ["", "", "", "test b1", "D Tier"]))

    def test_sheet_change_fails_closed(self):
        with self.assertRaises(ValueError):
            mt.ksf_bonus({}, "not,the,sheet\n")
        with self.assertRaises(ValueError):
            mt.ksf_bonus({}, sheet(["", "", "", "test b1", "7 Tier"]))
        with self.assertRaises(ValueError):
            mt.ksf_bonus({}, sheet())

    def test_payload_exact_and_bounded(self):
        table = {}
        mt.momentum(table, [maprow(rows=[lb(tier=4), lb(1, 2, 2)])])
        mt.ksf_main(table, "Map name,Tier\nsurf_test,6\n")
        text = mt.render(table)
        self.assertIn('tiers surf_test "v1;surf_test;0,0,4,rank,6,-,-;0,2,2,rank,-,-,-;"', text)
        self.assertNotIn("surf_test_css", text)
        for n in range(1, 100):
            mt.slot(table, "surf_test", 0, n)[:2] = ["10", "sugg"]
            mt.slot(table, "surf_test", n, 0)[:2] = ["10", "sugg"]
        with self.assertRaisesRegex(ValueError, "too long"):
            mt.render(table)

    def test_disagreeing_public_caches_fail_closed(self):
        table = {}
        mt.momentum(table, [maprow(rows=[lb()])])
        with self.assertRaisesRegex(ValueError, "conflicting MOM cache"):
            mt.momentum(table, [maprow(2, suggestions=[lb(tier=4)])])

    def test_release_ships_catalogue_and_omission_is_detected(self):
        release = (mt.ROOT / "src/release/release.ps1").read_text(encoding="utf8")
        files = set(shipguard.ps_strings(shipguard.ps_array(release, "ShipGameFiles")))
        self.assertIn("ftesurf/maps/tiers.txt", files)
        asset = mt.ROOT / "ftesurf/maps/tiers.txt"
        self.assertTrue(asset.is_file())
        # Judge the real QC fopen literal against the real release allowlist.
        with_asset = {p.removeprefix("ftesurf/") for p in files}
        good = shipguard.classify("maps/tiers.txt", "fopen", with_asset, set(), ", FILE_READ")
        bad = shipguard.classify("maps/tiers.txt", "fopen", with_asset - {"maps/tiers.txt"}, set(), ", FILE_READ")
        self.assertEqual(good[0], "SHIPPED")
        self.assertEqual(bad[0], "MISS")

    def test_bad_names_and_numeric_values(self):
        with self.assertRaises(ValueError):
            mt.slot({}, "../surf_test")
        for v in (None, 0, 11, 1.0, True, "4"):
            self.assertIsNone(mt.tier(v))
        self.assertEqual(mt.tier(10), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
