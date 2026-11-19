#!/usr/bin/env python3
"""runcompare: a run against itself loses nothing; a slower copy loses exactly its delay."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runcompare as rc  # noqa: E402
from test_tasplaus import RATE, simulate, text  # noqa: E402


class RunCompare(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        rows, fin = simulate()
        self.ref = os.path.join(self.dir.name, "ref.rec")
        with open(self.ref, "w") as f:
            f.write(text(rows, fin))
        # the same line, 5 ticks late from t=0.3 on (stands still for 5 ticks first)
        k = next(i for i, r in enumerate(rows) if r[0] >= 0.3)
        slow = rows[:k] + [(round(rows[k][0] + j * RATE, 6), rows[k][1], [0.0, 0.0, 0.0]) for j in range(5)] \
            + [(round(t + 5 * RATE, 6), o, v) for t, o, v in rows[k:]]
        self.slow = os.path.join(self.dir.name, "slow.rec")
        with open(self.slow, "w") as f:
            f.write(text(slow, fin + 5))

    def tearDown(self):
        self.dir.cleanup()

    def test_self_and_delay(self):
        names, res = rc.compare(rc.load(self.ref), [rc.load(self.ref), rc.load(self.slow)])
        ref, same, slow = res
        self.assertEqual(len(names), len(ref["splits"]))
        for a, b in zip(ref["splits"], same["splits"]):
            self.assertAlmostEqual(a, b, places=6)
        self.assertAlmostEqual(sum(slow["splits"]) - sum(ref["splits"]), 5 * RATE, places=3)
        self.assertAlmostEqual(slow["marks"][-1] - ref["marks"][-1], 5 * RATE, places=6)
        self.assertIsNotNone(ref["metrics"]["jump_t"])


if __name__ == "__main__":
    unittest.main()
