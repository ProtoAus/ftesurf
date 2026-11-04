#!/usr/bin/env python3
"""Small offline ramp-wear falsifiers. No engine, replay writes or player data."""
import math
import unittest

import numpy as np

import rampwear as rw


def chart(key, start, end):
    n = (0.0, 0.8, 0.6)
    u, v = rw.frame(n)
    poly = [tuple(u[i] * x + v[i] * y for i in range(3))
            for x, y in [(start, 0), (end, 0), (end, 160), (start, 160)]]
    c = rw.Chart(('f', key), n)
    c.facets = [rw.Facet(c, n, 0.0, poly)]
    c.verts = poly
    c.vcc = [f.to2(p) for f in c.facets for p in f.poly]
    c.tris = [(0, 1, 2), (0, 2, 3)]
    c.bounds()
    return c


class RampWearTests(unittest.TestCase):
    def test_coplanar_seam_uses_identical_samples(self):
        left, right = chart(1, 3, 100), chart(2, 100, 211)
        u, v = rw.frame(left.n)

        def world(x, y):
            return tuple(u[i] * x + v[i] * y for i in range(3))

        ev = rw.Events()
        ev.add_ride(world(60, 80), world(140, 80), u)
        ev.add_board(world(80, 80), u, u, 25)
        a, b = rw.paint(left, 8.0, ev), rw.paint(right, 8.0, ev)
        self.assertGreater(a['scr'].max(), 0.5)
        self.assertGreater(b['scr'].max(), 0.5, 'boarding must continue onto the neighbour')
        # Both chart borders overlap in world space; every shared data sample must agree.
        overlap = 0
        for y in range(a['h']):
            by = round((a['v0'] - b['v0']) / 8) + y
            for x in range(a['w']):
                bx = round((a['u0'] - b['u0']) / 8) + x
                if 0 <= bx < b['w'] and 0 <= by < b['h']:
                    for field in ('ride', 'scr', 'dsum'):
                        np.testing.assert_allclose(a[field][y, x], b[field][by, bx], atol=1e-6)
                    overlap += 1
        self.assertGreater(overlap, 40)
        self.assertEqual(math.fmod(a['u0'] - b['u0'], 8), 0)

    def test_atlas_is_power_of_two_and_nonoverlapping(self):
        charts = {1: {'w': 700, 'h': 500}, 2: {'w': 700, 'h': 320}, 3: {'w': 800, 'h': 200}}
        pos, w, h = rw.pack(charts, 2048)
        self.assertEqual(h & (h - 1), 0)
        self.assertGreaterEqual(h, 700)
        for k, (x, y) in pos.items():
            self.assertLessEqual(x + charts[k]['w'], w)
            self.assertLessEqual(y + charts[k]['h'], h)
            for j, (xx, yy) in pos.items():
                if j == k:
                    continue
                self.assertTrue(x + charts[k]['w'] <= xx or xx + charts[j]['w'] <= x or
                                y + charts[k]['h'] <= yy or yy + charts[j]['h'] <= y)

    def test_boarding_strength_control(self):
        self.assertEqual(rw.board_strength(0), 0)
        self.assertEqual(rw.board_strength(25), 1)
        self.assertGreater(rw.board_length(25), rw.board_length(0))


if __name__ == '__main__':
    unittest.main()
