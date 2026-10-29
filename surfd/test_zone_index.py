#!/usr/bin/env python3
"""P1109: zone_file_index reads all three zone folders the lobbies read.
Run from surfd/ with python -B."""
import logging
import os
import shutil
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix='zoneindex-')
DIRS = {k: os.path.join(HOME, k) for k in ('online', 'local', 'momlocal')}
for d in DIRS.values():
    os.makedirs(d)
os.environ.update(SURFD_HOME=HOME, SURFD_DB=os.path.join(HOME, 'test.db'), SURFD_MAPS=os.path.join(HOME, 'maps'),
                  SURFD_ZONES=DIRS['online'],
                  SURFD_ZONES_LOCAL=DIRS['local'], SURFD_ZONES_MOMLOCAL=DIRS['momlocal'])
import surfd as S


class ZoneIndex(unittest.TestCase):
    def test_three_folders(self):
        for k, name in (('online', 'surf_a'), ('local', 'surf_b'), ('momlocal', 'Surf_C')):
            open(os.path.join(DIRS[k], name + '.json'), 'w').write('{}')
        open(os.path.join(DIRS['momlocal'], 'notes.txt'), 'w').write('x')
        self.assertEqual(S.zone_file_index(now=0.0), {'surf_a', 'surf_b', 'surf_c'})


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        logging.shutdown(); shutil.rmtree(HOME)
