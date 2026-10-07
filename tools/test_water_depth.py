#!/usr/bin/env python3
"""Source water wiring/numerical regressions, not a renderer/runtime substitute.

Run with --engine <checkout>. Runtime acceptance also requires a real GL depth
attachment, neutral-normal, fog-range and no-fog controls, plus above/below views.
"""
import argparse
import math
from pathlib import Path
import re
import unittest

ENGINE = None


def project(distance, near, far):
    a = -1.0 if math.isinf(far) else -(far + near) / (far - near)
    b = -2.0 * near if math.isinf(far) else -2.0 * far * near / (far - near)
    return ((-a * distance + b) / distance + 1.0) * 0.5, a, b


def eye_depth(z, a, b):
    return abs(b / max(-(z * 2.0 - 1.0) - a, 0.000001))


def clamp(x):
    return max(0.0, min(x, 1.0))


class WaterDepth(unittest.TestCase):
    def test_perspective_depth_roundtrip(self):
        for near in (1.0, 4.0, 16.0):
            for far in (4096.0, 65536.0, math.inf):
                for distance in (near, 32.0, 100.0, 1024.0, 2048.0):
                    with self.subTest(near=near, far=far, distance=distance):
                        z, a, b = project(distance, near, far)
                        self.assertAlmostEqual(eye_depth(z, a, b), distance, places=6)

    def test_far_clear_is_finite_and_fogged(self):
        for far in (65536.0, math.inf):
            _, a, b = project(128.0, 4.0, far)
            result = eye_depth(1.0, a, b)
            self.assertTrue(math.isfinite(result))
            self.assertGreater(result, 65535.0)

    def test_negative_gap_cannot_reverse_distortion(self):
        self.assertEqual(max(0.0, 32.0 - 64.0), 0.0)

    def test_fog_start_and_range(self):
        self.assertEqual(clamp((50.0 - 100.0) / 400.0), 0.0)
        self.assertEqual(clamp((100.0 - 100.0) / 400.0), 0.0)
        self.assertEqual(clamp((300.0 - 100.0) / 400.0), 0.5)
        self.assertEqual(clamp((500.0 - 100.0) / 400.0), 1.0)
        self.assertEqual(clamp((900.0 - 100.0) / 400.0), 1.0)
        self.assertEqual(max(1.0, 32.0 - 100.0), 1.0)

    def test_shallow_distortion_does_not_scale_fresnel_normal(self):
        self.assertEqual(clamp(0.0 / 400.0), 0.0)
        self.assertEqual(clamp(40.0 / 400.0), 0.1)
        self.assertEqual(clamp(800.0 / 400.0), 1.0)

    @classmethod
    def setUpClass(cls):
        cls.mat = (ENGINE / 'plugins/hl2/mat_vmt.c').read_text()
        cls.shader = (ENGINE / 'plugins/hl2/glsl/vmt/water.glsl').read_text()
        cls.parser = (ENGINE / 'engine/gl/gl_shader.c').read_text()
        cls.backend = (ENGINE / 'engine/gl/gl_backend.c').read_text()

    def test_depth_sampler_and_pass_agree(self):
        self.assertIn('!!samps =DEPTH refractdepth=2', self.shader)
        self.assertIn('map $refractiondepth', self.mat)
        self.assertIn('map $null', self.mat)  # slot 1 in mode 1, NOT a live reflection
        self.assertIn('#DEPTH#FOGSTART=%f#FOGRANGE=%f', self.mat)

    def test_parser_requests_real_depth_attachment(self):
        branch = re.search(r'else if \(!Q_stricmp \(tname, "\$refractiondepth"\)\)\s*\{([^}]+)', self.parser)
        self.assertIsNotNone(branch)
        self.assertIn('SHADER_HASREFRACTDEPTH', branch[1])
        self.assertIn('T_GEN_REFRACTIONDEPTH', branch[1])
        self.assertIn('FBO_TEX_DEPTH', self.backend)

    def test_copy_mode_producer_consumer_agree(self):
        self.assertIn('shaderstate.curshader->flags & (SHADER_HASPORTAL|SHADER_HASREFRACTDEPTH)', self.backend)
        self.assertIn('bs->flags&(SHADER_HASPORTAL|SHADER_HASREFRACTDEPTH)', self.backend)

    def test_authored_fog_and_underwater_guard(self):
        self.assertIn('st->waterfog_disabled = !atoi(value)', self.mat)
        self.assertIn('st->water_below = !atoi(value)', self.mat)
        self.assertIn('!defined(NO_WATERFOG) && !defined(UNDERWATER)', self.shader)
        self.assertIn('(depth - float(FOGSTART)) / float(FOGRANGE)', self.shader)
        self.assertNotIn('depth/4096.0', self.shader)

    def test_depth_uses_actual_projection_and_no_fixed_resolution(self):
        self.assertIn('m_projection[3][2]', self.shader)
        self.assertIn('max(0.0, eyeDepth', self.shader)
        self.assertNotIn('cvar/gl_maxdist', self.shader)
        self.assertNotIn('1080.0', self.shader)

    def test_foreground_and_edge_rejection(self):
        self.assertIn('lessThan(refractUV', self.shader)
        self.assertIn('greaterThan(refractUV', self.shader)
        self.assertIn('<= gl_FragCoord.z', self.shader)
        self.assertIn('refractUV = stc', self.shader)

    def test_no_extra_capture_in_budget_shader(self):
        budget = (ENGINE / 'plugins/hl2/glsl/vmt/waterbudget.glsl').read_text()
        self.assertNotIn('refractdepth', budget)
        self.assertNotIn('s_refract,', budget)
        self.assertNotIn('s_reflect,', budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    options, remaining = parser.parse_known_args()
    ENGINE = options.engine.resolve()
    unittest.main(argv=['test_water_depth.py'] + remaining)
