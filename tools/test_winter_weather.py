#!/usr/bin/env python3
"""Small offline weather controls; NOT native visual/audio/FPS acceptance."""
import unittest

from PIL import Image
from winter_weather import kind, roof_data


class WeatherBakeTests(unittest.TestCase):
    def test_surface_positive_and_negative_controls(self):
        up, down = (0, 0, 1), (0, 0, -1)
        self.assertEqual(kind(4 | 8, 'water/test', up), 'sky')
        self.assertEqual(kind(8, 'nature/blue', up), 'water')
        self.assertEqual(kind(0, 'liquids/lava', up), 'lava')
        self.assertIsNone(kind(0, 'brick/clean', up))
        self.assertIsNone(kind(8, 'water/test', down))
        self.assertIsNone(kind(4 | 128, 'sky/test', up))

    def test_roof_pair_really_distinguishes_exposure(self):
        image = Image.new('RGB', (2, 1))
        image.putdata([(0, 0, 0), (255, 255, 0)])
        dims, height = roof_data('snowmask 1 fixture 0 0 128 2 1 -32 160', image)
        self.assertEqual(dims, (0, 0, 128, 2, 1))
        self.assertEqual(height.dtype.str, '<f4')
        self.assertEqual(list(height.flat), [-32, 128])
        outside = [min(1, max(0, (32 - float(h) + 32) / 64)) for h in height.flat]
        self.assertEqual(outside, [1, 0])

    def test_roof_rejects_size_and_schema_faults(self):
        image = Image.new('RGB', (2, 1))
        for bad in ['snowmask 2 fixture 0 0 128 2 1 -32 160',
                    'snowmask 1 fixture 0 0 128 512 1 -32 160',
                    'snowmask 1 fixture 0 0 0 2 1 -32 160',
                    'snowmask 1 fixture nan 0 128 2 1 -32 160']:
            with self.assertRaises(ValueError):
                roof_data(bad, image)
        with self.assertRaises(ValueError):
            roof_data('snowmask 1 fixture 0 0 128 1 1 -32 160', image)


if __name__ == '__main__':
    unittest.main()
