#!/usr/bin/env python3
"""Publisher controls; pass an owned --work-root (never a player installation)."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import ed25519
import updatefeed as feed

# RFC 8032 public test vector, NOT the production update credential.
SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
KEY = ed25519.publickey(SEED).hex()
WORK = None


def stage(root, platform='win64'):
    paths = ['default.fmf', 'ftesurf/menu.dat', 'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat',
             'ftesurf64.exe' if platform == 'win64' else 'ftesurf64']
    for p in paths:
        dest = root / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((p + '\n').encode())
    return root


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='publisher-', dir=WORK)
        self.root = Path(self.temp.name)
        self.win = stage(self.root / 'win')

    def tearDown(self):
        self.temp.cleanup()

    def build(self, name='feed', **kwargs):
        return feed.build({'win64': self.win}, self.root / name, kwargs.pop('version', '0.1.25'),
                          ['https://dl.proto.bar/ftesurf/update'], SEED, KEY, **kwargs)

    def test_signed_roundtrip_objects_and_hashes(self):
        receipt = self.build()
        self.assertEqual(receipt['files'], 5)
        m = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        for f in m['files']:
            obj = self.root / 'feed/objects' / f['hash'][:2] / f['hash']
            self.assertEqual(hashlib.blake2b(obj.read_bytes(), digest_size=32).hexdigest(), f['hash'])
            self.assertEqual(obj.stat().st_size, f['size'])

    def test_mutation_and_wrong_key_fail(self):
        self.build()
        e = json.loads((self.root / 'feed/update.json').read_bytes())
        e['payload'] = e['payload'].replace('0.1.25', '0.1.26')
        with self.assertRaises(ValueError): feed.verify(json.dumps(e).encode(), KEY)
        with self.assertRaises(ValueError): feed.envelope({'x': 1}, SEED)

    def test_explicit_empty_prior_refuses_before_feed(self):
        for name, previous in [('empty-bytes', b''), ('signed-empty-object', feed.envelope({}, SEED, KEY))]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.build(name=name, previous=previous)
                self.assertFalse((self.root / name / 'update.json').exists())
                self.assertFalse((self.root / name / 'objects.txt').exists())

    def test_signed_non_object_payload_is_not_absent_prior(self):
        for i, value in enumerate((None, [], False, 0, '')):
            with self.subTest(payload=value):
                previous = feed.envelope(value, SEED, KEY)
                with self.assertRaisesRegex(ValueError, 'must be an object'):
                    self.build(name=f'non-object-{i}', previous=previous)
                self.assertFalse((self.root / f'non-object-{i}' / 'update.json').exists())

    def test_player_owned_stage_file_is_fatal(self):
        p = self.win / 'ftesurf/data/consent.txt'
        p.parent.mkdir(parents=True)
        p.write_text('player sentinel')
        with self.assertRaisesRegex(ValueError, 'unmanaged'): self.build()

    def test_policy_protects_mounted_assets_and_settings(self):
        for p in ['ftesurf/ftesurf.cfg', 'qkey', 'hl2/pak01_dir.vpk', 'ftesurf/maps/a.bsp',
                  'ftesurf/data/consent.txt', 'ftesurf/cfg/settings.cfg', '../LICENSE',
                  'ftesurf/maps/tiers-other.txt', 'ftesurf/maps/tiers.txt/extra', 'ftesurf/maps/TIERS.txt',
                  'ftesurf/gfx/../../data/consent.txt', 'ftesurf/gfx/x.']:
            self.assertFalse(feed.managed(p), p)
        for p in ['ftesurf/maps/zones/local/surf_a.json', 'ftesurf/cfg/maps/map_surf_a.cfg',
                  'ftesurf/data/mapwr.txt', 'ftesurf/menu.dat', 'ftesurf/maps/tiers.txt']:
            self.assertTrue(feed.managed(p), p)

    def test_tier_catalogue_signed_roundtrip(self):
        p = self.win / 'ftesurf/maps/tiers.txt'
        p.parent.mkdir(parents=True)
        p.write_bytes(b'tiers surf_fixture "0,0,4,approved,6"\n')
        self.build()
        payload = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        row = next(f for f in payload['files'] if f['path'] == 'ftesurf/maps/tiers.txt')
        self.assertEqual(feed.object_bytes(self.root / 'feed/objects', row['hash'], row['size']), p.read_bytes())

    def test_launcher_is_bootstrap_not_self_replaced(self):
        (self.win / 'WOS-Launcher.exe').write_bytes(b'bootstrap')
        self.assertEqual(self.build()['omitted'], ['WOS-Launcher.exe'])

    def test_missing_required_game_file_fails(self):
        (self.win / 'ftesurf/menu.dat').unlink()
        with self.assertRaisesRegex(ValueError, 'required'): self.build()

    def test_windows_only_release_preserves_linux_entries(self):
        linux = stage(self.root / 'linux', 'linux64')
        feed.build({'win64': self.win, 'linux64': linux}, self.root / 'both', '0.1.24',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        previous = (self.root / 'both/update.json').read_bytes()
        self.build(previous=previous, previous_objects=self.root / 'both/objects')
        m = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        # P1294: what Linux installs is its own entries and the shared "all" ones
        self.assertEqual(len([f for f in m['files'] if f['platform'] in ('linux64', 'all')]), 5)
        self.assertEqual(m['exec_by_platform']['linux64']['cmd'], 'ftesurf64')
        objects = feed.verify_objects(self.root / 'feed/objects', m)
        self.assertEqual(len((self.root / 'feed/objects.txt').read_text().splitlines()), len(objects))
        linux_exe = next(f for f in m['files'] if f['path'] == 'ftesurf64')
        self.assertEqual(feed.object_bytes(self.root / 'feed/objects', linux_exe['hash'], linux_exe['size']), b'ftesurf64\n')

    def both(self, name='both'):
        linux = stage(self.root / 'linux', 'linux64')
        feed.build({'win64': self.win, 'linux64': linux}, self.root / name, '0.1.24',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        return feed.verify((self.root / name / 'update.json').read_bytes(), KEY), linux

    def test_shared_files_listed_once_as_all(self):
        # P1294: identical bytes and exec flag on both platforms -> one "all" entry; the executables stay native
        m, _ = self.both()
        by = {(f['path'], f['platform']) for f in m['files']}
        for shared in ('default.fmf', 'ftesurf/menu.dat', 'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat'):
            self.assertIn((shared, 'all'), by)
            self.assertNotIn((shared, 'win64'), by)
            self.assertNotIn((shared, 'linux64'), by)
        self.assertIn(('ftesurf64.exe', 'win64'), by)
        self.assertIn(('ftesurf64', 'linux64'), by)
        self.assertEqual(len(m['files']), 6)
        for platform in ('win64', 'linux64'):
            self.assertEqual(len([f for f in m['files'] if f['platform'] in (platform, 'all')]), 5)
        self.assertEqual(feed.platforms(m), {'win64', 'linux64'})

    def test_differing_bytes_or_exec_stay_native(self):
        linux = stage(self.root / 'linux', 'linux64')
        (linux / 'ftesurf/menu.dat').write_bytes(b'linux menu\n')        # same path, other bytes
        (self.win / 'ftesurf.sh').write_bytes(b'#!/bin/sh\n')            # same bytes, exec only on Linux
        (linux / 'ftesurf.sh').write_bytes(b'#!/bin/sh\n')
        feed.build({'win64': self.win, 'linux64': linux}, self.root / 'diff', '0.1.24',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        m = feed.verify((self.root / 'diff/update.json').read_bytes(), KEY)
        by = {(f['path'], f['platform']): f for f in m['files']}
        self.assertIn(('ftesurf/menu.dat', 'win64'), by)
        self.assertIn(('ftesurf/menu.dat', 'linux64'), by)
        self.assertNotIn(('ftesurf/menu.dat', 'all'), by)
        self.assertFalse(by[('ftesurf.sh', 'win64')]['exec'])
        self.assertTrue(by[('ftesurf.sh', 'linux64')]['exec'])
        self.assertNotIn(('ftesurf.sh', 'all'), by)

    def test_all_overlapping_a_native_entry_is_refused(self):
        # the launcher's "overlapping platform entries": an "all" and a native entry would install two versions
        m, _ = self.both()
        shared = next(f for f in m['files'] if f['platform'] == 'all')
        for bad in (dict(m, files=m['files'] + [dict(shared, platform='win64')]),
                    dict(m, files=m['files'] + [dict(shared, platform='all', path='ftesurf/gfx/x.png'),
                                                dict(shared, platform='all', path='ftesurf/gfx/X.png')])):
            with self.assertRaisesRegex(ValueError, 'duplicate update path'):
                feed.validate(bad)

    def test_all_only_feed_is_refused(self):
        m, _ = self.both()
        only = dict(m, files=[dict(f, platform='all') for f in m['files'] if f['path'] != 'ftesurf64'])
        with self.assertRaises(ValueError):
            feed.validate(only)

    def test_windows_only_release_after_a_merged_feed(self):
        # a retained Linux keeps its copies of the old "all" entries; nothing overlaps
        m, _ = self.both()
        self.build(previous=(self.root / 'both/update.json').read_bytes(), previous_objects=self.root / 'both/objects')
        n = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        feed.validate(n)
        for platform in ('win64', 'linux64'):
            got = sorted(f['path'] for f in n['files'] if f['platform'] in (platform, 'all'))
            self.assertEqual(len(got), 5, platform)
        self.assertEqual(feed.platforms(n), {'win64', 'linux64'})

    def test_shared_bytes_count_once_toward_the_limit(self):
        m, _ = self.both()
        listed = sum(f['size'] for f in m['files'])
        per_platform = sum(f['size'] for f in m['files'] if f['platform'] in ('win64', 'all')) + \
            sum(f['size'] for f in m['files'] if f['platform'] in ('linux64', 'all'))
        self.assertLess(listed, per_platform)

    def test_missing_or_corrupt_retained_objects_fail_before_feed(self):
        linux = stage(self.root / 'linux', 'linux64')
        feed.build({'win64': self.win, 'linux64': linux}, self.root / 'both', '0.1.24',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        previous = (self.root / 'both/update.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'retained object cache'):
            self.build(name='missing-cache', previous=previous)
        m = feed.verify(previous, KEY)
        f = next(f for f in m['files'] if f['path'] == 'ftesurf64')
        obj = self.root / 'both/objects' / f['hash'][:2] / f['hash']
        obj.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'corrupt referenced object'):
            self.build(name='corrupt-cache', previous=previous, previous_objects=self.root / 'both/objects')
        obj.unlink()
        with self.assertRaisesRegex(ValueError, 'missing referenced object'):
            self.build(name='missing-object', previous=previous, previous_objects=self.root / 'both/objects')
        for name in ('missing-cache', 'corrupt-cache', 'missing-object'):
            self.assertFalse((self.root / name / 'update.json').exists())

    def test_descriptor_paths_and_sizes_refuse_before_object_access(self):
        self.build()
        m = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        for field, bad in [('hash', '../bad'), ('path', 'ftesurf/data/consent.txt'), ('size', True)]:
            changed = json.loads(json.dumps(m))
            changed['files'][0][field] = bad
            with self.assertRaisesRegex(ValueError, 'descriptor'):
                feed.validate(changed)

    def test_refuses_signed_rollback_and_output_reuse(self):
        self.build(version='0.1.25')
        previous = (self.root / 'feed/update.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'rollback'): self.build(name='older', version='0.1.24', previous=previous)
        with self.assertRaisesRegex(ValueError, 'same-version'): self.build(name='same', version='0.1.25', previous=previous)
        with self.assertRaisesRegex(ValueError, 'empty'): self.build()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-root', type=Path, required=True)
    args, rest = parser.parse_known_args()
    WORK = args.work_root
    WORK.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=['test_updatefeed', *rest])
