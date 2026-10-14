#!/usr/bin/env python3
import struct
import unittest
import ksfreplay_info as K


class Replay(unittest.TestCase):
    def data(self, version=3):
        prefix = struct.pack('<i5fi3f', 1, 1, 2, 3, 4, 5, 0, 6, 7, 8)
        header = struct.pack('<4i', version, 2, 2, 1)
        if version == 3:
            header += struct.pack('<2i', 18, 40) + bytes(160)
            prefix += bytes(32)
        return header + struct.pack('<3i', 0, 2, 1) + bytes(512) + prefix * 2

    def test_positive_both_versions(self):
        for version in (2, 3):
            r = K.inspect(self.data(version))
            self.assertEqual((r['version'], r['frames'], r['bounds']),
                             (version, 2, [[1, 2, 3], [1, 2, 3]]))
            self.assertFalse(r['native_verified'])
            self.assertEqual(r['timed_interval'], 'not inferred')
            self.assertEqual(r['bookmarks'][0]['zone'], 1)

    def test_malformed_rejects(self):
        data = self.data()
        for b in (b'', b'<html>' * 100, data[:-1], data[:24],
                  struct.pack('<i', 99) + data[4:],
                  data[:16] + struct.pack('<i', -1) + data[20:],
                  data[:20] + struct.pack('<i', 99999999) + data[24:]):
            with self.assertRaises(ValueError): K.inspect(b)
        off = 24 + 160 + 524
        bad = bytearray(data)
        struct.pack_into('<f', bad, off + 4, float('nan'))
        with self.assertRaises(ValueError): K.inspect(bad)
        bad = bytearray(data)
        struct.pack_into('<i', bad, 24 + 160, 999999)
        with self.assertRaises(ValueError): K.inspect(bad)


if __name__ == '__main__': unittest.main()
