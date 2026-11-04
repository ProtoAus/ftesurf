#!/usr/bin/env python3
"""Bounded content/geometry controls; rendering/timing still needs a real client."""
import math
import struct
import unittest

import holiday_assets as H
import winter_placements as W


def mesh(data):
    assert data[:16] == b'INTERQUAKEMODEL\0'
    h = struct.unpack_from('<27I', data, 16)
    assert h[0] == 2 and h[1] == len(data)
    arrays = [struct.unpack_from('<5I', data, h[9] + 20 * i) for i in range(h[7])]
    triangles = [struct.unpack_from('<3I', data, h[11] + 12 * i) for i in range(h[10])]
    return h, arrays, triangles


class HolidayTests(unittest.TestCase):
    def test_iqm_controls_and_bounds(self):
        v = [((0, 0, 0), (0, 0), (0, 0, 1)),
             ((1, 0, 0), (1, 0), (0, 0, 1)),
             ((0, 1, 0), (0, 1), (0, 0, 1))]
        h, arrays, tri = mesh(H.iqm('test', v, [(0, 1, 2)]))
        self.assertEqual((h[5], h[7], h[8], h[10]), (1, 3, 3, 1))
        self.assertEqual([a[0] for a in arrays], [0, 1, 2])
        self.assertTrue(all(a[2] == 7 for a in arrays))
        self.assertEqual(tri, [(0, 1, 2)])
        for a in arrays:
            self.assertLessEqual(a[4] + a[3] * 4 * h[8], len(H.iqm('test', v, tri)))

    def test_obj_rotation_does_not_invert_winding(self):
        src = '\n'.join(['v 0 0 0', 'v 1 0 0', 'v 0 1 0',
                         'vt 0 0', 'vt 1 0', 'vt 0 1', 'vn 0 0 1',
                         'f 1/1/1 2/2/1 3/3/1'])
        v, tri = H.convert_obj(src, 1)
        self.assertEqual(tri, [(0, 1, 2)])
        p, q, r = [x[0] for x in v]
        a, b = [q[i] - p[i] for i in range(3)], [r[i] - p[i] for i in range(3)]
        cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        self.assertGreater(sum(x*y for x, y in zip(cross, v[0][2])), 0)
        with self.assertRaises(ValueError):
            H.convert_obj(src.replace('v 1 0 0', 'v nan 0 0'))

    def test_mist_has_exact_hard_geometry_cap(self):
        data = H.mist_field()
        h, arrays, tri = mesh(data)
        self.assertEqual((h[8], h[10]), (38, 12))
        self.assertEqual(data, H.mist_field())
        self.assertTrue(all(max(t) < 36 for t in tri), 'bounds-only vertices must not draw')
        off = arrays[0][4]
        points = [struct.unpack_from('<3f', data, off + i * 12) for i in range(38)]
        self.assertEqual(points[-2:], [(-1, -1, -1), (1, 1, 1)])
        self.assertTrue(all(abs(x) <= 0.55 for p in points[:-2] for x in p))

    def test_manifest_caps_and_empty_control(self):
        entities = [dict(classname='info_player_start', origin='0 0 64')]
        entities += [dict(classname='light', origin=f'{i*350} 100 128') for i in range(1, 30)]
        props, mist = W.records(entities)
        self.assertEqual(len(props), 6)
        self.assertEqual(len(mist), 12)
        self.assertTrue(all(len(row.split()) == 11 for row in mist))
        self.assertTrue(all(24 <= float(row.split()[4]) <= 64 for row in mist))
        p, m = W.records(entities[:1])
        self.assertEqual(len(p), 6); self.assertEqual(m, [])
        with self.assertRaises(ValueError):
            W.records([])

    def test_area_guard_caps_even_dense_input(self):
        area, fields = 0, 0
        for radius, distance in [(48, 400)] * 1000:
            score = 4 * (radius / distance) ** 2
            if fields < 4 and area + score <= 0.12:
                fields += 1; area += score
        self.assertEqual(fields, 2)
        self.assertLessEqual(area, 0.12)
        # This tests the exact conservative arithmetic, NOT GPU frame time.


if __name__ == '__main__':
    unittest.main()
