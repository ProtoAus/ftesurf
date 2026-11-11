#!/usr/bin/env python3
"""Offline native-mode projection contract for mapscan's existing Beta sidecar."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

import mapgrab
import mapscan


class BetaSidecarTests(unittest.TestCase):
    def test_cached_native_modes_project_without_private_fields(self):
        def row(name, ident, gm):
            return dict(name=name, id=ident, status=3,
                        private_fixture='must-not-project',
                        currentVersion=dict(bspHash='a' * 40, zoneHash='b' * 40,
                            downloadURL='https://cdn.momentum-mod.org/maps/12345678-abcd-1234-abcd-123456789abc.bsp'),
                        leaderboards=[dict(gamemode=gm, trackType=0, trackNum=1,
                                           style=0, tier=1)])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cache = root / '_cache'; cache.mkdir()
            approved = [dict(row('ahop_approved', 1, 2), status=0)]
            submissions = [row('ahop_approved', 1, 2), row('ahop_beta', 2, 2),
                           row('kz_hl1_beta', 3, 3), row('kz_unrelated', 4, 6),
                           row('../bad', 5, 3), row('surf_legacy', 6, 6),
                           dict(row('kz_malformed', 7, 3), leaderboards=7)]
            for i, status in enumerate([1, 2, 4, 5, 99, None, True, False, '3', 3.0, [], {}]):
                for prefix in ('kz_', 'bhop_'):
                    submissions.append(dict(row(prefix + 'blocked_%d' % i, 100 + i, 3), status=status))
            missing = row('kz_blocked_missing', 200, 3)
            del missing['status']
            submissions.append(missing)
            for kind, rows in [('approved', approved), ('submission', submissions)]:
                (cache / (kind + '_1.dat')).write_bytes(b'MSML' + b'\0' * 8 +
                    zlib.compress(json.dumps(rows).encode()))
            calls = []

            def transport(cmd, **kwargs):
                calls.append(cmd)
                return 0, ''

            with patch.object(mapgrab, 'MOMENTUM', str(root)), \
                    patch.object(mapscan, 'DATA', str(root)), \
                    patch.object(mapscan, 'sh', side_effect=transport):
                self.assertEqual(mapscan.push_beta('fixture.invalid'), 3)
            extra = (root / 'mapbeta.tsv').read_text()
            ids = (root / 'mapbetaids.tsv').read_text()
            self.assertEqual([line.split()[0] for line in extra.splitlines() if not line.startswith('#')],
                             ['ahop_beta', 'kz_hl1_beta', 'surf_legacy'])
            self.assertIn('ahop_beta ' + 'a' * 40 + ' 2 ' + 'b' * 40 + ' 2\n', ids)
            self.assertIn('kz_hl1_beta ' + 'a' * 40 + ' 3 ' + 'b' * 40 + ' 3\n', ids)
            self.assertIn('surf_legacy ' + 'a' * 40 + ' 6 ' + 'b' * 40 + '\n', ids)
            self.assertNotIn('must-not-project', extra + ids)
            self.assertNotIn('kz_unrelated', extra + ids)
            self.assertNotIn('ahop_approved', extra + ids)
            self.assertNotIn('blocked_', extra + ids)
            self.assertEqual(len(calls), 4)


if __name__ == '__main__':
    unittest.main()
