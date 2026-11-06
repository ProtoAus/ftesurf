"""Required input numbers use native spelling, not Python-only numeral syntax."""
import argparse
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest

import test_reccheck as grammar
from test_held_readers import recording as native_recording
from test_recsim_parsing import recording, rs

TOOLS = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get("RECCHECK", TOOLS / "reccheck.py"))
spec = importlib.util.spec_from_file_location("numeric_spelling_checker", SOURCE)
rc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rc
spec.loader.exec_module(rc)
FULLWIDTH = str.maketrans("0123456789", "０１２３４５６７８９")


def mutate(lines, position, column, spelling, tag="in"):
    changed = list(lines)
    index = [i for i, line in enumerate(changed) if line.split()[:1] == [tag]][position]
    fields = changed[index].split()
    fields[column] = spelling(fields[column])
    changed[index] = " ".join(fields)
    return "\n".join(changed) + "\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="input-numeric-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.cleanup)
        self.a = self.root / "a.rec"
        self.b = self.root / "b.rec"
        self.b.write_text(recording(), encoding="utf-8")

    def cleanup(self):
        self.tmp.cleanup()
        self.assertFalse(self.root.exists())

    def pair(self, max_bytes=65536, min_len=50):
        before = self.a.read_bytes(), self.b.read_bytes()
        result = rs.compare_paths(str(self.a), str(self.b), min_len=min_len,
                                  max_bytes=max_bytes, max_moves=100)
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), before)
        return result

    def assert_unavailable(self, text, max_bytes):
        self.a.write_text(text, encoding="utf-8")
        verdict, detail = self.pair(max_bytes)
        self.assertEqual((verdict, detail),
                         ("malformed input", "malformed required move-stream input"))
        with self.assertRaises(rs.MalformedRec):
            rs.parse_rec(str(self.a), strict=True, max_bytes=max_bytes, max_moves=100)
        self.assertIsNone(rs.parse_rec(str(self.a), max_bytes=max_bytes, max_moves=100))


class Similarity(Fixture):
    def test_normal_and_unequal_controls_act(self):
        for cap in (None, 65536):
            with self.subTest(cap=cap):
                self.a.write_text(recording(), encoding="utf-8")
                verdict, detail = self.pair(cap)
                self.assertEqual((verdict, detail["match"], detail["compared"]),
                                 ("compared", 1.0, 80))
                self.a.write_text(recording(other=True), encoding="utf-8")
                verdict, detail = self.pair(cap)
                self.assertEqual((verdict, detail["match"]), ("compared", 0.0))
                self.assertGreater(detail["compared"], 0)

    def test_required_tokens_abstain_whole_in_both_read_modes(self):
        for position in (0, 40, 79):
            for column in (2, 4, 5, 6, 10):
                for spelling in (lambda s: "0_" + s, lambda s: s.translate(FULLWIDTH)):
                    for cap in (None, 65536):
                        with self.subTest(position=position, column=column,
                                          spelling=spelling("123"), cap=cap):
                            self.assert_unavailable(mutate(recording().splitlines(),
                                                           position, column, spelling), cap)

    def test_fraction_sign_and_exponent_compatibility(self):
        text = mutate(recording().splitlines(), 0, 2, lambda _: "+0.9")
        for column, token in ((4, "-2.9e0"), (5, "+3.9"), (6, "4.9E0"), (10, "+1.9e0")):
            text = mutate(text.splitlines(), 0, column, lambda _, token=token: token)
        for column, token in ((4, "-2"), (5, "3"), (6, "4"), (10, "1")):
            peer = self.b.read_text(encoding="utf-8")
            self.b.write_text(mutate(peer.splitlines(), 0, column,
                                     lambda _, token=token: token), encoding="utf-8")
        self.a.write_text(text, encoding="utf-8")
        for cap in (None, 65536):
            with self.subTest(cap=cap):
                parsed = rs.parse_rec(str(self.a), strict=True, max_bytes=cap, max_moves=100)
                self.assertEqual((parsed.mt[0], parsed.moves[0], parsed.btns[0]),
                                 (0, (-2, 3, 4), 1))
                verdict, detail = self.pair(cap)
                self.assertEqual((verdict, detail["match"], detail["compared"]),
                                 ("compared", 1.0, 80))

    def test_release_keyword_and_future_clock_keep_their_meaning(self):
        base = recording().replace("FTESURF-REC 9", "FTESURF-REC 11")
        row = base.splitlines()[44]
        base = base.replace(row, "fzin\t" + row[3:])
        self.a.write_text(base, encoding="utf-8")
        verdict, detail = self.pair()
        self.assertEqual((verdict, detail["match"], detail["compared"]),
                         ("compared", 1.0, 80))
        self.assert_unavailable(mutate(base.splitlines(), 0, 4,
                                       lambda s: "0_" + s, tag="fzin"), 65536)
        self.a.write_text(base.replace("FTESURF-REC 11", "FTESURF-REC 14"), encoding="utf-8")
        self.assertEqual(self.pair(),
                         ("unmodelled recording", "recording clock model unavailable"))

    def test_real_collector_keeps_malformed_input_unjudgeable(self):
        path = Path(os.environ.get("SIMCHECK_SOURCE", TOOLS.parent / "surfd/simcheck.py"))
        spec = importlib.util.spec_from_file_location("numeric_spelling_collector", path)
        sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sc)
        bad = mutate(recording().splitlines(), 40, 4, lambda s: "0_" + s)
        for text, verdict, code, compared, notable in (
                (recording(), "compared", "", 80, 1),
                (recording(other=True), "compared", "", None, 0),
                (bad, "skip", "malformed", 0, 0)):
            with self.subTest(verdict=verdict, code=code, notable=notable):
                self.a.write_text(text, encoding="utf-8")
                with contextlib.closing(sqlite3.connect(":memory:")) as conn:
                    conn.row_factory = sqlite3.Row
                    sc.ensure_schema(conn)
                    conn.execute("CREATE TABLE replays (id INTEGER PRIMARY KEY,map TEXT,"
                                 "track INTEGER,leg INTEGER,kind TEXT,tier TEXT,player TEXT)")
                    for i in (1, 2):
                        conn.execute("INSERT INTO replays VALUES (?, 'synthetic',0,0,"
                                     "'run','ranked','synthetic')", (i,))
                    conn.commit()
                    looked = []
                    def replay_file(row):
                        looked.append(row["id"])
                        return str(self.a if row["id"] == 1 else self.b), ""
                    result = sc.similarity_step(conn, SimpleNamespace(replay_file=replay_file),
                                                tools_dir=str(Path(rs.__file__).parents[1]))
                    self.assertEqual(set(looked), {1, 2})
                    self.assertEqual(result[:2], (1, notable))
                    row = conn.execute("SELECT * FROM sims").fetchone()
                    self.assertEqual((row["verdict"], row["skip_code"]), (verdict, code))
                    if compared is None:
                        self.assertGreater(row["compared"], 0)
                        self.assertEqual(row["match"], 0.0)
                    else:
                        self.assertEqual(row["compared"], compared)
                    self.assertNotIn(str(self.root), row["reason"])
                    if code:
                        summary = sc.summary(conn)
                        self.assertEqual((summary["compared"], summary["skipped"],
                                          summary["notable"], summary["skip_codes"]),
                                         (0, 1, 0, {"malformed": 1}))

    def test_pair_cli_withholds_metrics(self):
        self.a.write_text(mutate(recording().splitlines(), 40, 4,
                                 lambda s: "0_" + s), encoding="utf-8")
        output = io.StringIO()
        args = argparse.Namespace(a=str(self.a), b=str(self.b), min_len=50)
        with contextlib.redirect_stdout(output):
            result = rs.cmd_one(args)
        self.assertEqual(result, 1)
        self.assertIn("not compared: malformed required move-stream input", output.getvalue())
        self.assertNotIn("match   ", output.getvalue())


class Checker(unittest.TestCase):
    def report(self, text):
        return rc.check_rec("synthetic.rec", data=text.encode("utf-8"))

    def test_clean_sign_and_float_exponent_controls(self):
        base = grammar.build(packets=80)
        text = "\n".join(base) + "\n"
        report = self.report(text)
        self.assertEqual((report.faults, report.info["inputs"]), ([], 80))
        for column in range(1, 12):
            with self.subTest(column=column):
                text = mutate(base, 40, column, lambda s: "+" + s)
                report = self.report(text)
                self.assertEqual((report.faults, report.info["inputs"]), ([], 80))
        for column in (3, 7, 8, 9):
            with self.subTest(exponent_column=column):
                text = mutate(base, 40, column, lambda s: "%.6e" % float(s))
                report = self.report(text)
                self.assertEqual(report.info["inputs"], 80)
                if column == 3:  # The carry's %.9g may legitimately use exponents.
                    self.assertEqual(report.faults, [])
                else:
                    self.assertEqual(len(report.faults), 1)
                    self.assertIn("exponent form", report.faults[0])
        for version in (6, 8):
            text = mutate(grammar.build(ver=version, packets=80), 40, 4, lambda _: "-2.9")
            with self.subTest(version=version):
                self.assertEqual(self.report(text).faults, [])

    def test_numeric_payload_lexemes_do_not_become_clean_rows(self):
        base = grammar.build(packets=80)
        for position in (0, 40, 79):
            for column in range(1, 12):
                for spelling in (lambda s: "0_" + s, lambda s: s.translate(FULLWIDTH)):
                    with self.subTest(position=position, column=column,
                                      spelling=spelling("123")):
                        report = self.report(mutate(base, position, column, spelling))
                        self.assertTrue(any("non-numeric field" in fault for fault in report.faults),
                                        report.faults)
                        self.assertEqual(report.info["inputs"], 79)


class Native(Fixture):
    def test_supported_contexts_and_release_aliases(self):
        for version in (13, 15):
            for release in (False, True):
                with self.subTest(version=version, release=release):
                    data = native_recording(version=version, fzin=release)
                    self.a.write_bytes(data)
                    self.b.write_bytes(data)
                    verdict, detail = self.pair(min_len=1)
                    self.assertEqual((verdict, detail["match"], detail["compared"]),
                                     ("compared", 1.0, 3))
                    report = rc.check_rec(str(self.a), data=data)
                    self.assertEqual(report.faults, [])
                    self.assertEqual(report.info["held_status"], "sealed")
                    tag = "fzin" if release else "in"
                    changed = mutate(data.decode("utf-8").splitlines(), 0, 4,
                                     lambda s: "0_" + s, tag=tag)
                    self.a.write_text(changed, encoding="utf-8")
                    self.assertEqual(self.pair(min_len=1),
                                     ("malformed input", "malformed required move-stream input"))
                    report = rc.check_rec(str(self.a), data=self.a.read_bytes())
                    # Native framing can already reject before the body checker.
                    self.assertFalse(report.ok)
                    self.assertTrue(report.faults)


if __name__ == "__main__":
    unittest.main()
