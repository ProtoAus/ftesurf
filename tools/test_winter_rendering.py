#!/usr/bin/env python3
"""P1315 small source/math controls, NOT native appearance/FPS acceptance."""
import math
import unittest
from pathlib import Path
from holiday_assets import convert_obj

ROOT = Path(__file__).resolve().parents[1]

class WinterRenderingTests(unittest.TestCase):
    def test_obj_outward_normals_keep_uv_but_reverse_iqm_front(self):
        obj = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nvn 0 0 1\nf 1/1/1 2/2/1 3/3/1\n'
        v, t = convert_obj(obj, 1)
        self.assertEqual(t, [(0, 2, 1)])
        self.assertEqual(v[0][1], (0, 1))
        a, b, c = [v[i][0] for i in t[0]]
        d, e = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        cross = (d[1]*e[2]-d[2]*e[1], d[2]*e[0]-d[0]*e[2], d[0]*e[1]-d[1]*e[0])
        dot = sum(cross[i]*v[0][2][i] for i in range(3))
        self.assertLess(dot, 0) # old indices give positive: detector really distinguishes

    def test_close_mist_is_continuous_and_projected_area_bounded(self):
        def scale(dist):
            score = 4*(48/max(32, dist))**2
            return 48*math.sqrt(min(score, .12/4)/score)
        for boundary in [32, 160, 192, 277, 280, 554.256]:
            self.assertLess(abs(scale(boundary-.001)-scale(boundary+.001)), .001)
        for d in [0, 16, 32, 64, 128, 192, 277, 550, 900]:
            self.assertGreater(scale(d), 0)
            self.assertLessEqual(4*4*(scale(d)/max(32,d))**2, .120001)
        qc=(ROOT/'src/client/cl_winter.qc').read_text()
        self.assertNotIn('dist < 192', qc)
        self.assertNotIn('wi_area + score >', qc)
        self.assertIn('e.scale = e.wi_radius * sqrt(share /', qc)

    def test_geometry_lift_not_only_driver_depth_bias(self):
        qc=(ROOT/'src/client/cl_rampwear.qc').read_text()
        self.assertIn('rw_pos[t * 3 + j] + normalize(rw_nrm[t]) * 0.75', qc)
        for n in [(0,0,1),(.8,0,.6),(0,-.6,.8)]:
            lifted=tuple(x*.75 for x in n)
            self.assertAlmostEqual(sum(x*y for x,y in zip(n,lifted)), .75)

    def test_weather_has_late_identity_retry_and_persistent_sky(self):
        qc=(ROOT/'src/client/cl_weather.qc').read_text()
        self.assertIn('wx_pending = TRUE; wx_retry = time + 0.25;',qc)
        self.assertIn('if (time >= wx_retry) Weather_Load();',qc)
        self.assertIn('addentity(wx_sky); // persistent',qc)
        self.assertIn('lightstyle(0, wx_style, wx_stylecolour)',qc)
        self.assertIn('if (!strcmp(wx_map, serverkey("map")))',qc)
        self.assertIn('registercommand("weather_info")',qc)
        self.assertIn('r_weather_test 1',qc)

if __name__=='__main__': unittest.main()
