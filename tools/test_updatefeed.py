#!/usr/bin/env python3
"""Publisher controls; pass an owned --work-root (never a player installation)."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

import ed25519
import updatefeed as feed

# RFC 8032 public test vector, NOT the production update credential.
SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
KEY = ed25519.publickey(SEED).hex()
WORK = None


# what the launcher's move needs of a worldofsurf default.fmf (feed.WOS_MAINCONFIG)
WOS_TAIL = 'DISABLEHOMEDIR 1\nMAINCONFIG ftesurf\n'


def manifest_text(game):
    tail = WOS_TAIL if game == 'worldofsurf' else ''
    return f'FTEMANIFEST 1\nGAME "{feed.MANIFEST_GAME[game]}"\nBASEGAME "{game}"\n{tail}'


def stage(root, platform='win64', game='ftesurf'):
    gamedir, exes = feed.IDENTITIES[game]
    paths = ['default.fmf', *(gamedir + leaf for leaf in feed.REQUIRED), exes[platform]]
    for p in paths:
        dest = root / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((manifest_text(game) if p == 'default.fmf' else p + '\n').encode())
    return root


def pe(tail=b''):
    """The smallest header launcher_kind accepts as a PE x86-64 image."""
    return b'MZ' + bytes(58) + (64).to_bytes(4, 'little') + b'PE\0\0\x64\x86' + tail


def elf(tail=b''):
    return b'\x7fELF\x02\x01' + bytes(12) + b'\x3e\x00' + tail


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

    def test_generated_map_tables_signed_roundtrip(self):
        for name in ('matcolours', 'unshipped', 'wadcolours'):
            p = self.win / f'ftesurf/scripts/{name}.txt'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f'synthetic {name} fixture\n'.encode())
        self.build()
        payload = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        for name in ('matcolours', 'unshipped', 'wadcolours'):
            path = f'ftesurf/scripts/{name}.txt'
            row = next(f for f in payload['files'] if f['path'] == path)
            self.assertEqual(feed.object_bytes(self.root / 'feed/objects', row['hash'], row['size']),
                             (self.win / path).read_bytes())

    def test_p1668_linux_imgui_rides_files_ext(self):
        """Still never a "files" path (every reader before launcher 0.1.7 and every engine would refuse the whole feed);
        a Linux stage's plugin goes to "files_ext", which only launcher 0.1.7+ reads."""
        name = 'fteplug_ui_imgui_amd64.so'
        for game in feed.IDENTITIES:
            self.assertFalse(feed.managed(name, game), game)
        self.assertTrue(feed.managed('fteplug_ui_imgui_x64.dll') and feed.managed('fteplug_hl2_amd64.so'))
        linux = stage(self.root / 'linux', 'linux64')
        (linux / name).write_bytes(b'synthetic plugin\n')
        feed.build({'win64': self.win, 'linux64': linux}, self.root / 'feed', '0.1.25',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        m = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        self.assertNotIn(name, {f['path'] for f in m['files']})
        h = hashlib.blake2b(b'synthetic plugin\n', digest_size=32).hexdigest()
        self.assertEqual(m['files_ext'], [{'path': name, 'hash': h, 'size': 17, 'platform': 'linux64', 'exec': False}])
        objects = feed.verify_objects(self.root / 'feed/objects', m)
        self.assertIn(h, objects)
        self.assertIn(f'{h[:2]}/{h}', (self.root / 'feed/objects.txt').read_text().splitlines())
        # a Windows stage holding the Linux plugin is still a publishing mistake
        (self.win / name).write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'unmanaged file: ' + name):
            self.build(name='winfeed')
        (self.win / name).unlink()
        # a Windows-only release keeps the Linux plugin entry
        self.build(name='winonly', version='0.1.26', previous=(self.root / 'feed/update.json').read_bytes(),
                   previous_objects=self.root / 'feed/objects')
        w = feed.verify((self.root / 'winonly/update.json').read_bytes(), KEY)
        self.assertEqual(w['files_ext'], m['files_ext'])
        feed.verify_objects(self.root / 'winonly/objects', w)
        # malformed or misplaced entries refuse
        e = m['files_ext'][0]
        for bad in ([dict(e, platform='win64')], [dict(e, platform='all')], [dict(e, path='ftesurf/data/consent.txt')],
                    [dict(e, exec=True)], [dict(e, extra=1)], [dict(e, hash=e['hash'].upper())], [dict(e, size=-1)], e):
            with self.assertRaisesRegex(ValueError, 'descriptor|file set', msg=repr(bad)):
                feed.validate(dict(m, files_ext=bad))
        with self.assertRaisesRegex(ValueError, 'duplicate update path'):
            feed.validate(dict(m, files_ext=[e, e]))
        # review: duplicates are refused even for a platform with no "files" of its own, which is refused anyway
        w2 = dict(m, files=[f for f in m['files'] if f['platform'] != 'linux64'],
                  exec_by_platform={'win64': m['exec_by_platform']['win64']})
        with self.assertRaisesRegex(ValueError, 'duplicate update path|file set'):
            feed.validate(dict(w2, files_ext=[e, e]))
        with self.assertRaisesRegex(ValueError, 'file set'):
            feed.validate(dict(w2, files_ext=[e]))
        # review: a later release restaging Linux without the plugin is refused (nothing would delete the old one)
        (linux / name).unlink()
        with self.assertRaisesRegex(ValueError, 'drops a files_ext path'):
            feed.build({'win64': self.win, 'linux64': linux}, self.root / 'dropped', '0.1.27',
                       ['https://dl.proto.bar/ftesurf/update'], SEED, KEY,
                       previous=(self.root / 'feed/update.json').read_bytes(), previous_objects=self.root / 'feed/objects')
        with self.assertRaisesRegex(ValueError, 'invalid update file descriptor'):
            feed.validate(dict(m, files=m['files'] + [dict(e, platform='linux64')]))

    def test_generated_map_tables_use_existing_asset_namespace(self):
        for name in ('matcolours', 'unshipped', 'wadcolours'):
            path = f'ftesurf/scripts/{name}.txt'
            self.assertTrue(feed.managed(path), path)
            for bad in (path.upper(), path + '.', path + ' ', path + ':stream',
                        f'ftesurf/scripts/../data/{name}.txt', f'ftesurf/data/{name}.txt'):
                self.assertFalse(feed.managed(bad), bad)
        for bad in ('ftesurf/data/consent.txt', 'ftesurf/data/player.txt', 'ftesurf/data/settings.txt'):
            self.assertFalse(feed.managed(bad), bad)

    def test_launcher_is_bootstrap_not_self_replaced(self):
        (self.win / 'WOS-Launcher.exe').write_bytes(pe(b'bootstrap'))
        self.assertEqual(self.build()['omitted'], ['WOS-Launcher.exe'])

    def test_p1666_launcher_descriptor_names_the_staged_launcher(self):
        """Old readers ignore "launcher"; the engine installs it. Never a "files" entry."""
        (self.win / 'WOS-Launcher.exe').write_bytes(pe(b'bootstrap win'))
        linux = stage(self.root / 'linux', 'linux64')
        (linux / 'WOS-Launcher').write_bytes(elf(b'bootstrap linux'))
        feed.build({'win64': self.win, 'linux64': linux}, self.root / 'feed', '0.1.25',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        m = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        self.assertNotIn('WOS-Launcher.exe', {f['path'] for f in m['files']})
        self.assertEqual(set(m['launcher']), {'win64', 'linux64'})
        for platform, body in (('win64', pe(b'bootstrap win')), ('linux64', elf(b'bootstrap linux'))):
            d = m['launcher'][platform]
            self.assertEqual(d, {'path': feed.LAUNCHER[platform], 'size': len(body),
                                 'hash': hashlib.blake2b(body, digest_size=32).hexdigest()})
            self.assertEqual(feed.object_bytes(self.root / 'feed/objects', d['hash'], d['size']), body)
        objects = feed.verify_objects(self.root / 'feed/objects', m)
        inventory = (self.root / 'feed/objects.txt').read_text().splitlines()
        self.assertEqual(len(inventory), len(objects))
        self.assertIn(f"{m['launcher']['win64']['hash'][:2]}/{m['launcher']['win64']['hash']}", inventory)
        # the closure check covers the launcher object too
        d = m['launcher']['linux64']
        (self.root / 'feed/objects' / d['hash'][:2] / d['hash']).unlink()
        with self.assertRaisesRegex(ValueError, 'missing referenced object'):
            feed.verify_objects(self.root / 'feed/objects', m)

    def test_p1666_no_staged_launcher_no_descriptor(self):
        self.build()
        self.assertNotIn('launcher', feed.verify((self.root / 'feed/update.json').read_bytes(), KEY))

    def test_p1666_windows_only_release_keeps_the_linux_launcher(self):
        linux = stage(self.root / 'linux', 'linux64')
        (linux / 'WOS-Launcher').write_bytes(elf(b'bootstrap linux'))
        (self.win / 'WOS-Launcher.exe').write_bytes(pe(b'old win'))
        feed.build({'win64': self.win, 'linux64': linux}, self.root / 'both', '0.1.24',
                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY)
        old = feed.verify((self.root / 'both/update.json').read_bytes(), KEY)
        (self.win / 'WOS-Launcher.exe').write_bytes(pe(b'new win'))
        self.build(previous=(self.root / 'both/update.json').read_bytes(), previous_objects=self.root / 'both/objects')
        m = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        self.assertEqual(m['launcher']['linux64'], old['launcher']['linux64'])
        self.assertEqual(m['launcher']['win64']['hash'], hashlib.blake2b(pe(b'new win'), digest_size=32).hexdigest())
        feed.verify_objects(self.root / 'feed/objects', m)

    def test_p1666_bad_launcher_descriptors_are_refused(self):
        (self.win / 'WOS-Launcher.exe').write_bytes(pe(b'bootstrap win'))
        self.build()
        good = feed.verify((self.root / 'feed/update.json').read_bytes(), KEY)
        d = good['launcher']['win64']
        bad = [{'win64': dict(d, path='ftesurf-launcher.exe')}, {'win64': dict(d, path='WOS-Launcher')},
               {'linux64': dict(d, path='WOS-Launcher.exe')}, {'macos64': d}, {'win64': dict(d, extra=1)},
               {'win64': {k: v for k, v in d.items() if k != 'size'}}, {'win64': dict(d, size=0)},
               {'win64': dict(d, size=32 * 1024 * 1024 + 1)}, {'win64': dict(d, size=True)},
               {'win64': dict(d, hash=d['hash'].upper())}, {'win64': dict(d, hash=d['hash'][:63])},
               {'win64': [d]}, [d], 'WOS-Launcher.exe']
        for launcher in bad:
            with self.assertRaisesRegex(ValueError, 'launcher descriptor|object size', msg=repr(launcher)):
                feed.validate(dict(good, launcher=launcher))
        # one hash, two sizes: a file and the launcher may share bytes, never disagree on their length
        f = good['files'][0]
        with self.assertRaisesRegex(ValueError, 'inconsistent object size'):
            feed.validate(dict(good, launcher={'win64': dict(d, hash=f['hash'], size=f['size'] + 1)}))
        feed.validate(dict(good, launcher={'win64': dict(d, hash=f['hash'], size=f['size'])}))

    def test_p1666_launcher_must_be_this_platforms_executable(self):
        for platform, body in (('win64', elf(b'x')), ('win64', b'MZ' + bytes(70)), ('win64', pe()[:-1]),
                               ('linux64', pe(b'x')), ('linux64', b'\x7fELF\x01\x01' + bytes(14)), ('linux64', elf()[:-2] + b'\xb7\x00')):
            self.assertFalse(feed.launcher_kind(platform, body), (platform, body[:24]))
        self.assertTrue(feed.launcher_kind('win64', pe()) and feed.launcher_kind('linux64', elf()))
        (self.win / 'WOS-Launcher.exe').write_bytes(elf(b'a linux build staged as the windows launcher'))
        with self.assertRaisesRegex(ValueError, 'not a win64 x86-64 executable'):
            self.build()
        # and the object closure check refuses a signed descriptor whose bytes are the wrong kind
        (self.win / 'WOS-Launcher.exe').write_bytes(pe(b'good'))
        self.build(name='good')
        m = feed.verify((self.root / 'good/update.json').read_bytes(), KEY)
        d = m['launcher']['win64']
        bad = elf(b'wrong kind')
        h = hashlib.blake2b(bad, digest_size=32).hexdigest()
        (self.root / 'good/objects' / h[:2]).mkdir(exist_ok=True)
        (self.root / 'good/objects' / h[:2] / h).write_bytes(bad)
        with self.assertRaisesRegex(ValueError, 'not a win64 x86-64 executable'):
            feed.verify_objects(self.root / 'good/objects', dict(m, launcher={'win64': dict(d, hash=h, size=len(bad))}))

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


SOURCE = Path(feed.__file__).read_text()
# P1593 controls: each mutant is a plausible wrong cut -> (needle, replacement, the checks it must break).
MUTANTS = {
    'union-paths': ('    if p in old_exe.values() or p.startswith(old_dir):\n        return None\n', '',
                    {'new-feed-with-legacy-gamedir-file', 'new-feed-with-legacy-exe', 'legacy-gamedir-under-new',
                     'new-stage-with-legacy-file'}),
    'feed-picks-identity': ('    if feed_game not in IDENTITIES or (game is not None and feed_game != game):\n',
                            '    if feed_game not in IDENTITIES:\n',
                            {'new-feed-for-legacy-install', 'legacy-feed-for-new-install',
                             'legacy-build-over-new-predecessor', 'publication-over-legacy-predecessor'}),
    'exec-unchecked': ('.get(platform) != {"cmd": exe, "args"',
                       '.get(platform) != {"cmd": payload["exec_by_platform"].get(platform, {}).get("cmd"), "args"',
                       {'new-feed-with-legacy-exec'}),
    'length-on-legacy-spelling': ('    if not isinstance(p, str) or len(p) >= 240:\n', '    if not isinstance(p, str):\n',
                                  {'new-path-240'}),
    'legacy-build-any-predecessor': ('        validate(old, None if game == WORLDOFSURF else game)', '        validate(old)',
                                     {'legacy-build-over-new-predecessor'}),
    'publication-predecessor-any-identity': ('        validate(old, payload["game"])', '        validate(old)',
                                             {'publication-over-legacy-predecessor'}),
    'new-feed-own-numbering': ('    if game == WORLDOFSURF and old is None:\n', '    if False:\n',
                               {'new-build-without-predecessor'}),
    'carry-across-identities': ('    same = old is not None and old["game"] == game\n', '    same = old is not None\n',
                                {'new-win64-over-legacy-carries-nothing'}),
    # build's own verify_objects pass is what refuses a stage's default.fmf
    'fmf-unchecked': ('            check_manifest(object_bytes(root, f["hash"], f["size"]), payload["game"])\n', '            pass\n',
                      {'objects-fmf-legacy-basegame', 'stage-fmf-legacy-basegame', 'stage-fmf-legacy-game',
                       'stage-fmf-without-disablehomedir'}),
    'duplicate-keys-allowed': ('json.loads(text, object_pairs_hook=unique_keys, parse_constant=constant)',
                               'json.loads(text, parse_constant=constant)',
                               {'duplicate-game-key', 'dotted-key'}),
    'del-allowed': ('any(ord(c) >= 0x7f for c in p)', 'not p.isascii()', {'path-with-del'}),
    'removed-unchecked': ('\n            or payload.get("removed") != []):', '):', {'removed-missing', 'removed-nonempty'}),
    'dots-allowed': (' or any("." in k for k in keys)', '', {'dotted-key'}),
    'envelope-extra-keys': (' or set(signed) != {"payload", "signature"} or ', ' or ', {'envelope-extra-key'}),
    'envelope-escapes-allowed': (' or escaped_key(raw):', ':', {'escaped-envelope-key'}),
    'fmf-controls-allowed': ('    if any((ord(c) < 32 and c not in "\\n\\t") or c == "\\x7f" for c in text) or "/*" in text:\n',
                             '    if "/*" in text:\n', {'fmf-cr'}),
    'fmf-block-comment-allowed': (' or "/*" in text:\n', ':\n', {'fmf-block-comment'}),
    'fmf-star-allowed': ('        if tokens and tokens[0].startswith("*"):\n', '        if False:\n', {'fmf-star-keyword'}),
    'fmf-repeat-allowed': ('            if tokens[0].lower() in found or ', '            if ',
                           {'fmf-two-game-lines', 'fmf-two-mainconfig-lines'}),
    # P1593 stage 2: what the launcher's move refuses, the feed refuses
    'fmf-homedir-unchecked': ('found.get("disablehomedir") != "1" or ', '',
                              {'fmf-no-disablehomedir', 'fmf-disablehomedir-0', 'stage-fmf-without-disablehomedir'}),
    'fmf-mainconfig-unchecked': (' or found.get("mainconfig") not in WOS_MAINCONFIG', '',
                                 {'fmf-no-mainconfig', 'fmf-mainconfig-other'}),
    'fmf-extra-words-allowed': (' or (game == WORLDOFSURF and len(tokens) != 2)', '', {'fmf-mainconfig-extra-word'}),
    'fmf-backslash-allowed': ('    if "\\\\" in text or \'""\' in text:', '    if \'""\' in text:', {'fmf-backslash-on-game-line'}),
    'fmf-empty-quotes-allowed': (' or \'""\' in text:', ':', {'fmf-empty-string'}),
    'fmf-odd-quotes-allowed': ('        if quoted:\n            raise ValueError("default.fmf holds an unpaired quote")\n', '',
                               {'fmf-unclosed-quote-earlier'}),
    'fmf-glued-opening-allowed': ('if line[i - 1:i] not in ("", " ", "\\t") if not quoted else ', 'if False if not quoted else ',
                                  {'fmf-glued-game-value', 'fmf-glued-basegame-value'}),
    'fmf-glued-closing-allowed': (' else line[i + 1:i + 2] not in ("", " ", "\\t"):', ' else False:', {'fmf-glued-closing-quote'}),
    'escaped-keys-allowed': ('    if escaped_key(text):\n', '    if False:\n', {'escaped-payload-key'}),
    'bytes-sniffed': ('    raw = feed_text(data)\n', '    raw = data.decode(json.detect_encoding(data))\n', {'feed-bom', 'feed-utf16'}),
    'constants-allowed': (', parse_constant=constant)', ')', {'nan-constant'}),
    'deeper-nesting': ('        if depth == 32:', '        if depth == 40:', {'payload-33-levels'}),
    'surrogates-allowed': (' or any(0xD800 <= ord(c) <= 0xDFFF for c in value)', '', {'lone-surrogate'}),
    'nul-allowed': ('if "\\0" in value or any(', 'if any(', {'nul-in-string'}),
    'signature-escape-allowed': (' or raw_member(raw, "signature") != sig', '', {'escaped-signature'}),
    'mirrors-unchecked': ('    if not isinstance(mirrors, list) or not mirrors or not all(mirror_ok(m) for m in mirrors):\n'
                          '        raise ValueError("invalid object mirror")\n', '',
                          {'mirror-http', 'mirror-userinfo', 'mirror-query', 'mirror-empty'}),
    'mirror-http-allowed': ('(u.scheme == "https" or loopback)', '(u.scheme in ("https", "http") or loopback)', {'mirror-http'}),
    'signature-case-allowed': ('re.fullmatch(r"[0-9a-f]{128}", sig)', 're.fullmatch(r"[0-9a-fA-F]{128}", sig)',
                               {'upper-case-signature'}),
}


def variant(name):
    """updatefeed with one mutant applied, as its own module (the subject is never patched in place)."""
    needle, replacement, _ = MUTANTS[name]
    assert SOURCE.count(needle) == 1, name
    module = types.ModuleType('updatefeed_' + name.replace('-', '_'))
    module.__file__ = feed.__file__
    exec(compile(SOURCE.replace(needle, replacement), feed.__file__, 'exec'), module.__dict__)
    return module


def signed_text(text):
    """An envelope around exact payload text (feed.envelope reserializes, so it cannot repeat a key)."""
    return json.dumps({'payload': text, 'signature': ed25519.sign(SEED, text.encode()).hex()}).encode()


class IdentityTests(unittest.TestCase):
    """P1593: exactly two identities, never mixed within one feed, one version line across both."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='identity-', dir=WORK)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, f, game, name, version, platforms=('win64', 'linux64'), **kwargs):
        base = self.root / f.__name__ / name
        stages = {p: stage(base / p, p, game) for p in platforms}
        f.build(stages, base / 'feed', version, ['https://dl.proto.bar/ftesurf/update'], SEED, KEY, game=game, **kwargs)
        return base / 'feed/update.json'

    def checks(self, f):
        """case -> True when module f behaves as P1593 requires (almost all are refusals)."""
        legacy_path = self.build(f, 'ftesurf', 'ftesurf', '0.1.24')
        new_path = self.build(f, 'worldofsurf', 'worldofsurf', '0.1.25', previous=legacy_path.read_bytes())
        legacy, new = f.verify(legacy_path.read_bytes(), KEY), f.verify(new_path.read_bytes(), KEY)
        menu = next(x for x in new['files'] if x['path'] == 'worldofsurf/menu.dat')
        exe = next(x for x in new['files'] if x['path'] == 'WorldofSurf.exe')

        def refused(call, *args, **kwargs):
            try:
                call(*args, **kwargs)
            except ValueError:
                return True
            return False

        def plus(payload, row, path):
            return dict(payload, files=payload['files'] + [dict(row, path=path)])

        def stage_with(name, game, extra=None, fmf=None):
            s = stage(self.root / f.__name__ / name, 'win64', game)
            for rel, data in (extra or {}).items():
                (s / rel).parent.mkdir(parents=True, exist_ok=True)
                (s / rel).write_bytes(data)
            if fmf:
                (s / 'default.fmf').write_bytes(fmf)
            return lambda: f.build({'win64': s}, self.root / f.__name__ / (name + '-out'), '0.1.26',
                                   ['https://dl.proto.bar/ftesurf/update'], SEED, KEY, game=game,
                                   previous=legacy_path.read_bytes())

        def carries_nothing():
            try:
                path = self.build(f, 'worldofsurf', 'win-only', '0.1.26', ('win64',), previous=legacy_path.read_bytes())
            except ValueError:
                return False
            m = f.verify(path.read_bytes(), KEY)
            return f.platforms(m) == {'win64'} and not any(x['path'].startswith('ftesurf') for x in m['files'])

        def objects_fmf_refused():
            # the worldofsurf feed's default.fmf object swapped for a legacy-identity manifest
            objects = self.root / f.__name__ / 'worldofsurf/feed/objects'
            data = manifest_text('ftesurf').encode()
            h = hashlib.blake2b(data, digest_size=32).hexdigest()
            (objects / h[:2]).mkdir(exist_ok=True)
            (objects / h[:2] / h).write_bytes(data)
            files = [dict(x, hash=h, size=len(data)) if x['path'] == 'default.fmf' else x for x in new['files']]
            return refused(f.verify_objects, objects, dict(new, files=files))

        # the last "game" is the one json.loads keeps: a legacy feed that also says worldofsurf
        text = json.dumps(legacy, separators=(',', ':'), sort_keys=True)
        duplicate = '{"game":"worldofsurf",' + text[1:]
        prior, receipt = self.root / f.__name__ / 'prior.json', self.root / f.__name__ / 'receipt.json'
        prior.write_bytes(legacy_path.read_bytes())
        receipt.write_text(json.dumps({'version': '0.1.25', 'feed_sha256': hashlib.sha256(new_path.read_bytes()).hexdigest(),
                                       'objects': len(f.validate(new)), 'verification': 'r2-roundtrip-blake2b-256'}))
        relabel = dict(new, game='ftesurf')
        execs = json.loads(json.dumps(new))
        execs['exec_by_platform']['win64']['cmd'] = 'ftesurf64.exe'
        removed = dict(legacy)
        del removed['removed']
        envelope = json.loads(legacy_path.read_bytes())
        tail = WOS_TAIL.encode()
        good = b'GAME "WorldofSurf"\nBASEGAME "worldofsurf"\n' + tail
        return {
            'new-feed-for-legacy-install': refused(f.validate, new, 'ftesurf'),
            'legacy-feed-for-new-install': refused(f.validate, legacy, 'worldofsurf'),
            'new-feed-relabelled-legacy': refused(f.validate, relabel) and refused(f.validate, relabel, 'ftesurf'),
            'legacy-feed-with-new-gamedir-file': refused(f.validate, plus(legacy, menu, 'worldofsurf/gfx/x.png')),
            'new-feed-with-legacy-gamedir-file': refused(f.validate, plus(new, menu, 'ftesurf/gfx/x.png')),
            'new-feed-with-legacy-exe': refused(f.validate, plus(new, exe, 'ftesurf64.exe')),
            'new-feed-with-legacy-exec': refused(f.validate, execs),
            'new-feed-outside-gamedir': refused(f.validate, plus(new, menu, 'worldofsurf/data/consent.txt')),
            'legacy-gamedir-under-new': not f.managed('ftesurf/menu.dat', 'worldofsurf'),
            'new-stage-with-legacy-file': refused(stage_with('mixed', 'worldofsurf', {'ftesurf/gfx/x.png': b'legacy'})),
            'new-path-240': not f.managed('worldofsurf/gfx/' + 'a' * 220 + '.png', 'worldofsurf'),
            'unknown-identity': refused(f.validate, dict(new, game='WorldofSurf')),
            'legacy-build-over-new-predecessor': refused(self.build, f, 'ftesurf', 'legacy-after-new', '0.1.26',
                                                         previous=new_path.read_bytes()),
            'publication-over-legacy-predecessor': refused(f.check_publication, new_path, receipt, '0.1.25', prior,
                                                           hashlib.sha256(prior.read_bytes()).hexdigest(), KEY),
            'new-build-without-predecessor': refused(self.build, f, 'worldofsurf', 'no-previous', '0.1.26'),
            'new-build-not-above-legacy': refused(self.build, f, 'worldofsurf', 'same-version', '0.1.24',
                                                  previous=legacy_path.read_bytes()),
            'new-win64-over-legacy-carries-nothing': carries_nothing(),
            'stage-fmf-legacy-basegame': refused(stage_with('fmf-basegame', 'worldofsurf',
                                                            fmf=b'FTEMANIFEST 1\nGAME "WorldofSurf"\nBASEGAME "ftesurf"\n')),
            'stage-fmf-legacy-game': refused(stage_with('fmf-game', 'worldofsurf',
                                                        fmf=b'FTEMANIFEST 1\nGAME "FTESurf"\nBASEGAME "worldofsurf"\n')),
            'objects-fmf-legacy-basegame': objects_fmf_refused(),
            'duplicate-game-key': refused(f.verify, signed_text(duplicate), KEY),
            'path-with-del': not f.managed('worldofsurf/gfx/a\x7f.png', 'worldofsurf'),
            'removed-missing': refused(f.validate, removed),
            'removed-nonempty': refused(f.validate, dict(legacy, removed=['ftesurf/gfx/old.png'])),
            'dotted-key': refused(f.verify, signed_text('{"game.":"worldofsurf",' + text[1:]), KEY),
            'envelope-extra-key': refused(f.verify, json.dumps(dict(envelope, note='x')).encode(), KEY),
            'fmf-cr': refused(f.check_manifest, good + b'set x 1\r\n', 'worldofsurf'),
            'escaped-envelope-key': refused(f.verify, legacy_path.read_bytes().replace(b'"payload"', b'"pay\\u006coad"', 1), KEY),
            # review 5: strict UTF-8 text, then what the engine's QKU_JSONStrict refuses, then mirrors
            'feed-bom': refused(f.verify, b'\xef\xbb\xbf' + legacy_path.read_bytes(), KEY),
            'feed-utf16': refused(f.verify, legacy_path.read_bytes().decode().encode('utf-16'), KEY),
            'feed-invalid-utf8': refused(f.verify, legacy_path.read_bytes() + b' \xff', KEY),
            'nan-constant': refused(f.verify, signed_text(text.replace('"schema":2', '"schema":NaN', 1)), KEY),
            'payload-33-levels': refused(f.verify, signed_text(text[:-1] + ',"deep":' + '[' * 32 + ']' * 32 + '}'), KEY),
            'payload-32-levels-accepted': not refused(f.verify, signed_text(text[:-1] + ',"deep":' + '[' * 31 + ']' * 31 + '}'), KEY),
            'lone-surrogate': refused(f.verify, signed_text(text.replace('"stable"', '"st\\udc00able"', 1)), KEY),
            'nul-in-string': refused(f.verify, signed_text(text.replace('"stable"', '"st\\u0000able"', 1)), KEY),
            'escaped-signature': refused(f.verify, legacy_path.read_bytes().replace(
                envelope['signature'].encode(), ('\\u00%02x' % ord(envelope['signature'][0]) + envelope['signature'][1:]).encode()), KEY),
            'mirror-http': refused(f.validate, dict(legacy, mirrors=['http://dl.proto.bar/u'])),
            'mirror-userinfo': refused(f.validate, dict(legacy, mirrors=['https://u:p@dl.proto.bar/u'])),
            'mirror-query': refused(f.validate, dict(legacy, mirrors=['https://dl.proto.bar/u?x=1'])),
            'mirror-empty': refused(f.validate, dict(legacy, mirrors=[])),
            'mirror-loopback-accepted': not refused(f.validate, dict(legacy, mirrors=['http://127.0.0.1:8000/u'])),
            'fmf-block-comment': refused(f.check_manifest, b'/* note */\n' + good, 'worldofsurf'),
            'fmf-star-keyword': refused(f.check_manifest, b'*basegame ftesurf\n' + good, 'worldofsurf'),
            'fmf-two-game-lines': refused(f.check_manifest, b'GAME "FTESurf"\n' + good, 'worldofsurf'),
            'fmf-backslash-on-game-line': refused(f.check_manifest, good.replace(b'"WorldofSurf"', b'"WorldofSurf" // \\x'),
                                                  'worldofsurf'),
            # the round-3 reviewer's inputs
            'fmf-escaped-quote-line': refused(f.check_manifest, good + b'\\"basegame ftesurf"\n', 'worldofsurf'),
            'fmf-empty-quotes': refused(f.check_manifest, b'GAME "FTESurf"\nBASEGAME "ftesurf"' b'""\n', 'ftesurf'),
            'fmf-unclosed-quote-earlier': refused(f.check_manifest, b'set x "abc\n' + good, 'worldofsurf'),
            'fmf-empty-string': refused(f.check_manifest, good + b'set x ""\n', 'worldofsurf'),
            # the round-4 reviewer's inputs (the third is refused by both glued-quote rules)
            'fmf-glued-game-value': refused(f.check_manifest, b'GAME FTESurf"x"\nBASEGAME "ftesurf"\n', 'ftesurf'),
            'fmf-glued-basegame-value': refused(f.check_manifest, b'GAME "FTESurf"\nBASEGAME ftesurf"x"\n', 'ftesurf'),
            'fmf-glued-quote-above': refused(f.check_manifest, b'GAME "WorldofSurf"\nx"y "z\nBASEGAME "worldofsurf"\n' + tail, 'worldofsurf'),
            'fmf-glued-closing-quote': refused(f.check_manifest, b'GAME "FTESurf"x\nBASEGAME "ftesurf"\n', 'ftesurf'),
            'fmf-glued-worldofsurf-values': all(refused(f.check_manifest, fmf + tail, 'worldofsurf') for fmf in (
                b'GAME WorldofSurf"x"\nBASEGAME "worldofsurf"\n', b'GAME "WorldofSurf"\nBASEGAME worldofsurf"x"\n',
                b'GAME "WorldofSurf"x\nBASEGAME "worldofsurf"\n')),
            'escaped-payload-key': refused(f.verify, signed_text(text.replace('"schema"', '"sch\\u0065ma"', 1)), KEY),
            'upper-case-signature': refused(f.verify, json.dumps(dict(envelope, signature=envelope['signature'].upper())).encode(), KEY),
            # P1593 stage 2: the launcher's move needs DISABLEHOMEDIR 1 and a known MAINCONFIG, one value each
            'fmf-no-disablehomedir': refused(f.check_manifest, good.replace(b'DISABLEHOMEDIR 1\n', b''), 'worldofsurf'),
            'fmf-disablehomedir-0': refused(f.check_manifest, good.replace(b'DISABLEHOMEDIR 1', b'DISABLEHOMEDIR 0'),
                                            'worldofsurf'),
            'fmf-no-mainconfig': refused(f.check_manifest, good.replace(b'MAINCONFIG ftesurf\n', b''), 'worldofsurf'),
            'fmf-mainconfig-other': refused(f.check_manifest, good.replace(b'MAINCONFIG ftesurf', b'MAINCONFIG fte'),
                                            'worldofsurf'),
            'fmf-two-mainconfig-lines': refused(f.check_manifest, good + b'MAINCONFIG worldofsurf\n', 'worldofsurf'),
            'fmf-mainconfig-extra-word': refused(f.check_manifest, good.replace(b'MAINCONFIG ftesurf', b'MAINCONFIG ftesurf x'),
                                                 'worldofsurf'),
            'fmf-mainconfig-worldofsurf-accepted': not refused(
                f.check_manifest, good.replace(b'MAINCONFIG ftesurf', b'MAINCONFIG "worldofsurf"'), 'worldofsurf'),
            'legacy-fmf-unchanged': not refused(f.check_manifest, b'GAME "FTESurf"\nBASEGAME "ftesurf" x\n', 'ftesurf'),
            'stage-fmf-without-disablehomedir': refused(stage_with(
                'fmf-home', 'worldofsurf', fmf=b'FTEMANIFEST 1\nGAME "WorldofSurf"\nBASEGAME "worldofsurf"\nMAINCONFIG ftesurf\n')),
        }

    def test_each_identity_accepts_its_own_feed(self):
        legacy_path = self.build(feed, 'ftesurf', 'ftesurf', '0.1.24')
        paths = {'ftesurf': legacy_path,
                 'worldofsurf': self.build(feed, 'worldofsurf', 'worldofsurf', '0.1.25', previous=legacy_path.read_bytes())}
        for game, path in paths.items():
            with self.subTest(game=game):
                payload = feed.verify(path.read_bytes(), KEY)
                gamedir, exes = feed.IDENTITIES[game]
                self.assertEqual(payload['game'], game)
                feed.validate(payload, game)
                feed.verify_objects(path.parent / 'objects', payload)
                self.assertEqual(payload['exec'], {'cmd': exes['win64'], 'args': ['-manifest', 'default.fmf']})
                self.assertEqual(feed.platforms(payload), {'win64', 'linux64'})
                for platform in ('win64', 'linux64'):
                    self.assertEqual(payload['exec_by_platform'][platform]['cmd'], exes[platform])
                    self.assertEqual(sorted(f['path'] for f in payload['files'] if f['platform'] in ('all', platform)),
                                     sorted([exes[platform], 'default.fmf', *(gamedir + leaf for leaf in feed.REQUIRED)]))
                self.assertTrue(next(f for f in payload['files'] if f['path'] == exes['linux64'])['exec'])

    def test_cross_mixed_and_outside_feeds_are_refused(self):
        for case, ok in self.checks(feed).items():
            with self.subTest(case):
                self.assertTrue(ok)

    def test_manifest_reader_matches_the_shipped_fmf(self):
        feed.check_manifest((Path(feed.__file__).parents[1] / 'default.fmf').read_bytes(), 'ftesurf')
        feed.check_manifest(b'// x\ngame WorldofSurf // trailing\n\tbasegame "worldofsurf"\n' + WOS_TAIL.encode(), 'worldofsurf')
        for bad in (b'GAME "WorldofSurf"\n', b'BASEGAME "worldofsurf"\n', b'// GAME "WorldofSurf"\nBASEGAME "worldofsurf"\n',
                    b'GAME "WorldofSurf"\nBASEGAME "worldofsurf"\nBASEGAME "ftesurf"\n',
                    b'GAME "worldofsurf"\nBASEGAME "worldofsurf"\n', b'GAME "WorldofSurf"\nBASEGAME "*worldofsurf"\n'):
            with self.subTest(bad):
                with self.assertRaisesRegex(ValueError, 'default.fmf'):
                    feed.check_manifest(bad, 'worldofsurf')

    def test_new_allowlist_is_the_legacy_one_with_the_gamedir_swapped(self):
        probes = ['ftesurf/menu.dat', 'ftesurf/maps/tiers.txt', 'ftesurf/maps/zones/local/a.json',
                  'ftesurf/maps/zones/local/x/a.json', 'ftesurf/cfg/maps/a.cfg', 'ftesurf/cfg/settings.cfg',
                  'ftesurf/cfg/test/a.cfg', 'ftesurf/data/mapwr.txt', 'ftesurf/data/consent.txt', 'ftesurf/gfx/a.png',
                  'ftesurf/gfx/../../x', 'ftesurf/maps/a.bsp', 'ftesurf/ftesurf.cfg', 'ftesurf/textures/no_texture.png',
                  'ftesurf/fs_addons.txt', 'ftesurf/MENU.DAT', 'ftesurf/menu.dat.', 'ftesurf/gfx/a\x7f.png',
                  'ftesurf/gfx/' + 'a' * 216 + '.png']
        for p in probes:
            swapped = 'worldofsurf/' + p[len('ftesurf/'):]
            with self.subTest(p):
                self.assertEqual(feed.managed(swapped, 'worldofsurf'), feed.managed(p, 'ftesurf'))
                self.assertFalse(feed.managed(p, 'worldofsurf'))
                self.assertFalse(feed.managed(swapped, 'ftesurf'))
        for p in ('default.fmf', 'LICENSE', 'notices/a.txt', 'ftesurf.sh', 'fteplug_hl2_x64.dll'):
            self.assertTrue(feed.managed(p, 'worldofsurf') and feed.managed(p, 'ftesurf'), p)
        for legacy, new in (('ftesurf64.exe', 'WorldofSurf.exe'), ('ftesurf64', 'worldofsurf64')):
            self.assertTrue(feed.managed(legacy, 'ftesurf') and feed.managed(new, 'worldofsurf'))
            self.assertFalse(feed.managed(new, 'ftesurf') or feed.managed(legacy, 'worldofsurf'))
        for p in ('worldofsurf', 'worldofsurf.exe', 'WORLDOFSURF/menu.dat', 'WorldofSurf/menu.dat', 'quakers/menu.dat'):
            self.assertFalse(feed.managed(p, 'worldofsurf'), p)
        # The 240 limit is on the real path: the longer gamedir never buys a longer on-disk path.
        self.assertTrue(feed.managed('worldofsurf/gfx/' + 'a' * 219 + '.png', 'worldofsurf'))
        self.assertTrue(feed.managed('ftesurf/gfx/' + 'a' * 220 + '.png', 'ftesurf'))

    def test_mutants_are_caught(self):
        """Control: each wrong cut breaks exactly the checks that guard against it."""
        for name, (_, _, expected) in MUTANTS.items():
            with self.subTest(name):
                got = {case for case, ok in self.checks(variant(name)).items() if not ok}
                self.assertEqual(got, expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-root', type=Path, required=True)
    args, rest = parser.parse_known_args()
    WORK = args.work_root
    WORK.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=['test_updatefeed', *rest])
