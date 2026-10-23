#!/usr/bin/env python3
"""Release-path classification and acted mutation controls in an owned fixture root."""
import argparse
import contextlib
import glob
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import shipguard
import updatefeed


RUNTIME_LITERALS = {
    'maps/%s.bsp', 'data/mapdl.net.txt', 'data/mapdl.net.tmp',
    'data/mapbuild.txt', 'maps/settings/local/',
}


def scan(files, dirs):
    rows = []
    for path in sorted(glob.glob(str(Path(shipguard.SRCDIR) / '**/*.qc'), recursive=True)):
        for line, literal, prefix, suffix in shipguard.qc_literals(path):
            for candidate in shipguard.candidates(literal):
                verdict, reason = shipguard.classify(
                    candidate, shipguard.enclosing_call(prefix), files, dirs, suffix)
                rows.append((candidate, verdict, reason, path, line))
    return rows


class ShipGuardTests(unittest.TestCase):
    root: Path

    @classmethod
    def setUpClass(cls):
        cls.files, cls.dirs, cls.globs = shipguard.resolve_shipset()
        cls.rows = scan(cls.files, cls.dirs)

    def test_release_disk_policy_accepts_current_declared_paths(self):
        output = io.StringIO()
        with patch('sys.argv', ['shipguard.py', '--release-policy']), contextlib.redirect_stdout(output):
            code = shipguard.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn('signed-update disk policy', output.getvalue())

    def test_prechange_tier_policy_is_caught_before_staging(self):
        output = io.StringIO()
        with patch.object(updatefeed, 'GAME', updatefeed.GAME - {'ftesurf/maps/tiers.txt'}), \
                patch('sys.argv', ['shipguard.py', '--release-policy']), contextlib.redirect_stdout(output):
            code = shipguard.main()
        self.assertEqual(code, 1, output.getvalue())
        self.assertIn('UNMANAGED release path: ftesurf/maps/tiers.txt', output.getvalue())

    def test_runtime_paths_are_narrowly_explained(self):
        hits = [row for row in self.rows if row[0] in RUNTIME_LITERALS and row[1] != 'RUNTIME']
        self.assertEqual(len(hits), 6, hits)
        for literal, verdict, reason, path, line in hits:
            with self.subTest(literal=literal, path=path, line=line):
                self.assertEqual(verdict, 'DENIED', reason)
                self.assertTrue(reason)

    def test_current_source_has_no_unexplained_miss(self):
        self.assertEqual([row for row in self.rows if row[1] == 'MISS'], [])

    def test_neighboring_required_paths_still_miss(self):
        for literal in ('data/mapdl.new.txt', 'data/mapbuild-baseline.txt',
                        'maps/settings/shipped/', 'maps/zones/local/',
                        'maps/required.bsp', 'maps/%s.png'):
            with self.subTest(literal=literal):
                self.assertEqual(shipguard.classify(literal, 'fopen', set(), set(), ', FILE_READ);')[0], 'MISS')

    def test_mounted_source_assets_are_exact_and_not_redistributed(self):
        mounted = {
            'scripts/game_sounds_manifest.txt', 'scripts/game_sounds_player.txt',
            'scripts/game_sounds_physics.txt', 'scripts/surfaceproperties_manifest.txt',
            'scripts/surfaceproperties.txt', 'scripts/surfaceproperties_cs.txt',
            'scripts/game_sounds_weapons.txt', 'models/weapons/v_knife_t.mdl',
            'models/weapons/v_pist_usp.mdl', 'models/weapons/v_snip_scout.mdl',
            'models/weapons/v_pist_glock18.mdl',
        }
        # GM_LoadCSS also probes physics definitions; grade the actual loads,
        # without relabelling search_begin as a read/redistribution demand.
        hits = [row for row in self.rows if row[0] in mounted and row[1] != 'RUNTIME']
        self.assertEqual({row[0] for row in hits}, mounted)
        for literal, verdict, reason, path, line in hits:
            self.assertEqual(verdict, 'DENIED', (path, line, reason))
            self.assertIn('Steam', reason)
            self.assertNotIn(literal, self.files)
        with patch.dict(shipguard.DENY_EXACT, clear=False):
            for literal in mounted:
                del shipguard.DENY_EXACT[literal]
            missing = {row[0] for row in scan(self.files, self.dirs) if row[1] == 'MISS'}
            self.assertEqual(missing, mounted)

    def test_mounted_source_exceptions_do_not_hide_owned_neighbors(self):
        for literal in ('scripts/game_sounds_ftesurf.txt',
                        'scripts/surfaceproperties_ftesurf.txt',
                        'models/weapons/v_ftesurf.mdl', 'models/required.mdl'):
            self.assertEqual(shipguard.classify(literal, 'fopen', set(), set(),
                                               ', FILE_READ);')[0], 'MISS')

    def test_local_settings_subtree_only(self):
        for literal in ('maps/settings/local/', 'maps/settings/local/surf_fixture.cfg'):
            self.assertEqual(shipguard.classify(literal, 'strcat', set(), set())[0], 'DENIED')
        self.assertEqual(shipguard.classify('maps/settings/local-other/map.cfg', 'fopen', set(), set())[0], 'MISS')

    def test_curated_zone_cache_is_narrow_and_runtime_only(self):
        hits = [row for row in self.rows if row[0] == 'maps/zones/curated/']
        self.assertEqual(len(hits), 3, hits)
        for literal, verdict, reason, path, line in hits:
            self.assertEqual(verdict, 'DENIED', (path, line, reason))
            self.assertIn('runtime zone cache', reason)
        self.assertEqual(shipguard.classify('maps/zones/curated/surf_fixture.json',
                                           'fopen', set(), set(), ', FILE_READ);')[0], 'DENIED')
        for literal in ('maps/zones/curated-other/surf_fixture.json',
                        'maps/zones/curated.json', 'maps/zones/local/'):
            self.assertEqual(shipguard.classify(literal, 'fopen', set(), set(), ', FILE_READ);')[0], 'MISS')
        self.assertFalse(any(path.removeprefix('ftesurf/').startswith('maps/zones/curated/')
                             for path in self.files))
        with patch.dict(shipguard.DENY_PREFIX, clear=False):
            del shipguard.DENY_PREFIX['maps/zones/curated/']
            self.assertEqual(len([row for row in scan(self.files, self.dirs)
                                  if row[0] == 'maps/zones/curated/' and row[1] == 'MISS']), 3)

    def test_fopen_read_remains_a_load(self):
        self.assertEqual(shipguard.classify('data/mapdl.txt', 'fopen', set(), set(), ', FILE_READ);')[0], 'MISS')
        self.assertEqual(shipguard.classify('data/mapdl.txt', 'fopen', self.files, self.dirs, ', FILE_READ);')[0], 'SHIPPED')
        for mode in ('FILE_WRITE', 'FILE_APPEND'):
            self.assertEqual(shipguard.classify('data/new-output.txt', 'fopen', set(), set(), ', ' + mode + ');')[0], 'RUNTIME')

    def test_all_five_shipped_menu_snapshots_are_required(self):
        for literal in ('data/mapdl.txt', 'data/mapmeta.txt', 'data/mapdeps.txt',
                        'data/mapwr.txt', 'data/mapparticles.txt'):
            with self.subTest(literal=literal):
                self.assertIn(literal, self.files)
                hidden = self.files - {literal, 'ftesurf/' + literal}
                flips = [(row, shipguard.classify(row[0], 'fopen', hidden, self.dirs, ', FILE_READ);')[0])
                         for row in self.rows if row[0] == literal and row[1] == 'SHIPPED']
                self.assertTrue(flips, 'no acted source reader for ' + literal)
                self.assertTrue(any(verdict == 'MISS' for row, verdict in flips), flips)

    def test_historical_glob_omissions_are_caught(self):
        for directory, literal in (('ftesurf/gfx/thumbnails', 'gfx/thumbnails/speaking_off'),
                                   ('ftesurf/maps/zones/local', 'maps/zones/local/')):
            with self.subTest(directory=directory):
                index = next(i for i, entry in enumerate(self.globs) if entry['path'] == directory)
                hidden, hdirs, _ = shipguard.resolve_shipset(hidden=index)
                self.assertTrue(self.files - hidden, 'glob did not contribute files')
                self.assertEqual(shipguard.classify(literal, 'drawpic', self.files, self.dirs)[0], 'SHIPPED')
                self.assertEqual(shipguard.classify(literal, 'drawpic', hidden, hdirs)[0], 'MISS')
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    # The current roster no longer names the old voice icons.
                    # Keep their actual historical load as an explicit fixture.
                    if not any(row[0] == literal and row[1] == 'SHIPPED' for row in self.rows):
                        fixture = self.root / ('historical-' + str(index) + '.qc')
                        fixture.write_text('void() Fixture = { drawpic("' + literal + '"); };\n')
                        stack.enter_context(patch('shipguard.glob.glob', return_value=[str(fixture)]))
                    stack.enter_context(contextlib.redirect_stdout(output))
                    code = shipguard.mutate(index)
                self.assertEqual(code, 0, output.getvalue())
                self.assertIn(literal, output.getvalue())

    def test_mutation_does_not_credit_an_existing_miss(self):
        fixture = self.root / 'already-missing.qc'
        fixture.write_text('void() Fixture = { fopen("data/required-missing.txt", FILE_READ); };\n')
        # cfg contributes real files but this fixture has no dependency on that glob.
        index = next(i for i, entry in enumerate(self.globs) if entry['path'] == 'ftesurf/cfg')
        output = io.StringIO()
        with patch('shipguard.glob.glob', return_value=[str(fixture)]), contextlib.redirect_stdout(output):
            code = shipguard.mutate(index)
        self.assertEqual(code, 2, output.getvalue())
        self.assertIn('NOT CAUGHT', output.getvalue())

    def test_invalid_mutation_index_is_refused(self):
        for index in (-1, len(self.globs)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = shipguard.mutate(index)
            self.assertEqual(code, 2, output.getvalue())
            self.assertIn('out of range', output.getvalue())

    def test_runtime_files_are_not_in_the_shipset(self):
        for path in self.files:
            short = path.removeprefix('ftesurf/')
            self.assertNotIn(short, RUNTIME_LITERALS)
            self.assertFalse(short.startswith('maps/settings/local/'), path)
            self.assertFalse(short.endswith('.bsp'), path)

    def test_font_backups_are_excluded_without_losing_fonts_or_notices(self):
        for name in ('Roboto.ttf', 'GoogleMed.ttf', 'BebasNeueRegular.ttf', 'FONTS.md', 'OFL.txt'):
            self.assertIn('gfx/fonts/' + name.lower(), self.files)
        self.assertFalse(any(path.endswith('.prev') for path in self.files))

    def test_stage_and_archive_tripwire_refuses_runtime_files(self):
        release = Path(shipguard.RELEASE).read_text(encoding='utf-8-sig')
        patterns = shipguard.ps_strings(shipguard.ps_array(release, 'DenyPatterns'))
        for path in ('ftesurf/data/mapdl.net.txt', 'ftesurf/data/mapdl.net.tmp',
                     'ftesurf/data/mapbuild.txt', 'ftesurf/maps/settings/local/surf_fixture.cfg',
                     'ftesurf/data/maps/settings/local/surf_fixture.cfg'):
            with self.subTest(path=path):
                self.assertTrue(any(re.search(pattern, path, re.I) for pattern in patterns), path)
        for path in ('ftesurf/data/mapdl.txt', 'ftesurf/maps/zones/local/surf_fixture.json',
                     'ftesurf/cfg/maps/map_fixture.cfg', 'ftesurf/particles/ftesurf.cfg'):
            self.assertFalse(any(re.search(pattern, path, re.I) for pattern in patterns), path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    if args.work_root.exists():
        parser.error('use a fresh owned test root')
    args.work_root.mkdir(parents=True)
    (args.work_root / 'OWNER.md').write_text('Shipguard unit/mutation fixtures; retained updater task evidence.\n')
    ShipGuardTests.root = args.work_root.resolve()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ShipGuardTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (args.work_root / 'result.json').write_text(json.dumps({
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'source_rows': getattr(ShipGuardTests, 'rows', []),
    }, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
