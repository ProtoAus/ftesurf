"""Synthetic grammar/error tests; fake VM/BSP bytes are NOT world qualification."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tasvfs as v

WORLD = 'maps/bhop_eazy.bsp'


def hx(value):
    return value.encode().hex() if value else '-'


def fixture(extra=None, omit=(), lie_missing=(), duplicate=False, version=10, lower_order=False, purpose='component'):
    bodies = {'qwprogs.dat': b'not a parsed VM', WORLD: b'not a parsed map',
              'models/deep/actor.txt': b'native reader grammar control'}
    bodies.update(extra or {})
    entries = [v.Entry(0, False, 0, name) for name in v.queries(WORLD, version) if name not in omit]
    parents = set()
    for name, body in bodies.items():
        entries.append(v.Entry(1, False, len(body), name))
        parts = name.split('/')
        parents.update('/'.join(parts[:i]) + '/' for i in range(1, len(parts)))
    entries.extend(v.Entry(1, True, 0, name) for name in parents)
    if duplicate:
        entries.append(v.Entry(1, False, len(bodies['qwprogs.dat']), 'qwprogs.dat'))
    entries.sort(key=lambda e: (e.name.lower() if lower_order else e.name.upper(), e.name, e.source))
    rows = ['TASVFSEXPORT %s %s 1 1 0 0 0 %s' % (version, purpose, hx(WORLD)),
            'ROOT 1 2 ' + hx('/fixture/g'), 'ROOT 2 3 ' + hx('/fixture/exe'),
            'SOURCE 1 0 1 1 1 1 0 ' + hx('/fixture/g') + ' ' + hx('/fixture/g'),
            'PATH 1 ' + hx('/fixture/g'), 'PUREPATH 1 -']
    seen, files, missing, total = set(), 0, 0, 0
    for e in entries:
        rows.append('ENTRY %s %s %s %s' % (e.source, int(e.directory), e.size, hx(e.name)))
        if e.directory or e.name in seen:
            continue
        seen.add(e.name)
        if e.name in bodies and e.name not in lie_missing:
            body = bodies[e.name]
            rows.append('FILE 1 %s %s %s' % (len(body), hashlib.sha256(body).hexdigest(), hx(e.name)))
            files += 1
            total += len(body)
        else:
            rows.append('MISSING ' + hx(e.name))
            missing += 1
    rows += ['INPUT 1 3 1 1 1 3 1 0 1 0 ' + hx('/fixture/exe'),
             'END %s %s %s %s %s' % (purpose, files, missing, len(entries), total)]
    return ('\n'.join(rows) + '\n').encode(), bodies


def parse(raw):
    return v.parse_component(raw, hashlib.sha256(raw).hexdigest(), WORLD)


class GrammarTests(unittest.TestCase):
    def test_exact_component_not_authority(self):
        raw, bodies = fixture()
        result = parse(raw)
        self.assertEqual(result.world, WORLD)
        self.assertEqual(result.version, 10)
        self.assertFalse(result.preparation)
        self.assertEqual(len(v.queries(WORLD)), 91)
        self.assertEqual(sum(bool(r.source) for r in result.resolved), len(bodies))
        self.assertEqual({e.name for e in result.entries if e.source == 0}, set(v.queries(WORLD)))
        with self.assertRaises(AttributeError):
            result.epoch = 3

    def test_preparation_role_is_explicit_and_not_a_component(self):
        raw, _ = fixture(purpose='profileprep')
        digest = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(v.Invalid, 'HEADER'):
            parse(raw)
        result = v.parse_preparation(raw, digest, WORLD)
        self.assertTrue(result.preparation)
        with self.assertRaises(AttributeError):
            result.preparation = False
        regular, _ = fixture()
        with self.assertRaisesRegex(v.Invalid, 'HEADER'):
            v.parse_preparation(regular, hashlib.sha256(regular).hexdigest(), WORLD)

    def test_preparation_is_current_schema_and_exact_complete_frame(self):
        raw, _ = fixture(purpose='profileprep')
        legacy, _ = fixture(version=9, purpose='profileprep')
        variants = [legacy, raw.replace(b'END profileprep ', b'END component '), raw + raw,
                    raw.replace(b'TASVFSEXPORT 10 profileprep', b'TASVFSMEASURE 1 diagnostic-length view10')]
        for value in variants:
            with self.assertRaises(v.Invalid):
                v.parse_preparation(value, hashlib.sha256(value).hexdigest(), WORLD)
        with self.assertRaisesRegex(v.Invalid, 'MANIFEST_SHA'):
            v.parse_preparation(raw, '0' * 64, WORLD)

    def test_preparation_caps_do_not_change_ordinary_limits(self):
        regular, _ = fixture()
        prepared, _ = fixture(purpose='profileprep')
        read_prepared = lambda: v.parse_preparation(prepared, hashlib.sha256(prepared).hexdigest(), WORLD)
        self.assertEqual((v.MAX_FILES, v.MAX_TOTAL), (8000, 2 * 1024 ** 3))
        self.assertEqual((v.PREP_MAX_FILES, v.PREP_MAX_TOTAL), (131072, 8 * 1024 ** 3))
        for name in ('MAX_FILES', 'MAX_TOTAL'):
            with patch.object(v, name, 1):
                with self.assertRaisesRegex(v.Invalid, 'COUNTS'):
                    parse(regular)
                self.assertTrue(read_prepared().preparation)
        for name in ('PREP_MAX_FILES', 'PREP_MAX_TOTAL'):
            with patch.object(v, name, 1), self.assertRaisesRegex(v.Invalid, 'COUNTS'):
                read_prepared()

    def test_native_ascii_upper_order_not_python_lower_order(self):
        extra = {'models/a.txt': b'a', 'models/_actor.txt': b'underscore'}
        for version in (1, 10):
            raw, _ = fixture(extra=extra, version=version)
            names = [e.name for e in parse(raw).entries]
            self.assertLess(names.index('models/a.txt'), names.index('models/_actor.txt'))
            invalid, _ = fixture(extra=extra, version=version, lower_order=True)
            with self.assertRaisesRegex(v.Invalid, 'ENTRY_ORDER'):
                parse(invalid)

    def test_ack_digest_world_and_scope_are_exact(self):
        raw, _ = fixture()
        for sha, world in [('0' * 64, WORLD), (hashlib.sha256(raw).hexdigest(), 'maps/other.bsp')]:
            with self.assertRaises(v.Invalid):
                v.parse_component(raw, sha, world)
        for prefix in (b'TASVFSEXPORT 10 canonical', b'TASVFSMEASURE 1 diagnostic-length view10'):
            with self.assertRaises(v.Invalid):
                parse(raw.replace(b'TASVFSEXPORT 10 component', prefix, 1))

    def test_legacy_is_explicit_archived_component_not_upgraded(self):
        raw, _ = fixture(version=1)
        result = parse(raw)
        self.assertEqual(result.version, 1)
        self.assertEqual(len(v.queries(WORLD, 1)), 35)
        self.assertNotIn('bhop_eazy', {e.name for e in result.entries})

    def test_control_contract_does_not_drop_maps_prefixed_controls(self):
        controls = set(v.control_queries(WORLD))
        self.assertEqual(len(controls), 57)
        for path in ('impfiltr.cfg', 'gibfiltr.cfg', 'mod.gam', 'fteadd.dat', 'hlbsp.dat', 'q2bsp.lno',
                     'fte_bimap.txt', 'maps/tiers.txt', 'data/maps/tiers.txt',
                     'maps/settings/local/bhop_eazy.cfg', 'maps/zones/online/bhop_eazy.json'):
            self.assertIn(path, controls)
        self.assertNotIn(WORLD, controls)
        for name in v.WORLD_DATA_QUERIES:
            self.assertNotIn(name, controls)
            self.assertIn(name, v.queries(WORLD))
        self.assertTrue(controls.isdisjoint(v.negative_probes(WORLD)))

    def test_schema2_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=2)
        result = parse(raw)
        self.assertEqual(result.version, 2)
        self.assertEqual(len(v.queries(WORLD, 2)), 45)
        self.assertNotIn('maps/zones/online/bhop_eazy.json', {e.name for e in result.entries})

    def test_native_and_qc_control_fallbacks_are_bound(self):
        names = set(v.queries(WORLD))
        for path in ('maplist.txt', 'data/maps/tiers.txt', 'maps/tiers.txt',
                     'qwprogs.lno', 'csprogs.lno', 'menu.lno', 'progs.lno', 'csqcprogs.lno',
                     'qwprogs.qvm', 'vm/qagame.qvm', 'vm/cgame.qvm', 'vm/ui.qvm',
                     'data/mapdeps.net.txt', 'mapdeps.net.txt',
                     'data/maps/settings/local/bhop_eazy.cfg', 'maps/settings/local/bhop_eazy.cfg',
                     'data/maps/zones/online/bhop_eazy.json', 'maps/zones/online/bhop_eazy.json',
                     'data/maps/zones/dl/bhop_eazy.json', 'maps/zones/dl/bhop_eazy.json'):
            with self.subTest(path=path):
                self.assertIn(path, names)

    def test_schema3_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=3)
        result = parse(raw)
        self.assertEqual(result.version, 3)
        self.assertEqual(len(v.queries(WORLD, 3)), 57)
        self.assertNotIn('qwprogs.so', {e.name for e in result.entries})

    def test_schema4_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=4)
        result = parse(raw)
        self.assertEqual(result.version, 4)
        self.assertEqual(len(v.queries(WORLD, 4)), 58)
        self.assertNotIn('maplist.txt', {e.name for e in result.entries})

    def test_schema5_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=5)
        result = parse(raw)
        self.assertEqual(result.version, 5)
        self.assertEqual(len(v.queries(WORLD, 5)), 66)
        self.assertNotIn('common.default.po', {e.name for e in result.entries})

    def test_schema6_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=6)
        result = parse(raw)
        self.assertEqual(result.version, 6)
        self.assertEqual(len(v.queries(WORLD, 6)), 72)
        self.assertNotIn('fte_bimap.txt', {e.name for e in result.entries})

    def test_schema7_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=7)
        result = parse(raw)
        self.assertEqual(result.version, 7)
        self.assertEqual(len(v.queries(WORLD, 7)), 73)
        self.assertNotIn('mod.gam', {e.name for e in result.entries})

    def test_schema8_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=8)
        result = parse(raw)
        self.assertEqual(result.version, 8)
        self.assertEqual(len(v.queries(WORLD, 8)), 89)
        self.assertNotIn('gibfiltr.cfg', {e.name for e in result.entries})

    def test_schema9_is_archived_not_silently_upgraded(self):
        raw, _ = fixture(version=9)
        result = parse(raw)
        self.assertEqual(result.version, 9)
        self.assertEqual(len(v.queries(WORLD, 9)), 90)
        self.assertNotIn('impfiltr.cfg', {e.name for e in result.entries})

    def test_native_map_probes_are_negative_only(self):
        for name in v.negative_probes(WORLD):
            raw, _ = fixture({name: b'must not become an alternate readable world'})
            with self.subTest(name=name), self.assertRaisesRegex(v.Invalid, 'PROBE_PRESENT'):
                parse(raw)

    def test_truncation_unknown_rows_counts_and_extra_frames(self):
        raw, _ = fixture()
        variants = [raw[:-1], raw[:raw.rfind(b'END ')], raw + raw,
                    raw.replace(b'END component 3 ', b'END component 4 '),
                    raw.replace(b'INPUT 1 ', b'UNKNOWN 1 ')]
        for value in variants:
            with self.subTest(value=len(value)), self.assertRaises(v.Invalid):
                parse(value)

    def test_queries_and_resolution_cannot_be_silently_dropped(self):
        raw, _ = fixture(omit=['menu.dat'])
        with self.assertRaisesRegex(v.Invalid, 'QUERY_SET'):
            parse(raw)
        raw, _ = fixture(lie_missing=['qwprogs.dat'])
        with self.assertRaisesRegex(v.Invalid, 'RESOLUTION_COVERAGE'):
            parse(raw)

    def test_provider_identity_parent_and_selected_id(self):
        raw, _ = fixture()
        variants = [raw.replace(b'SOURCE 1 0 1 1 1 1 0 ', b'SOURCE 1 0 1 0 1 1 0 '),
                    raw.replace(b'SOURCE 1 0 1 1 1 1 0 ', b'SOURCE 1 0 1 1 1 1 99 '),
                    raw.replace(b'FILE 1 ', b'FILE 2 ', 1)]
        for value in variants:
            with self.assertRaises(v.Invalid):
                parse(value)

    def test_provider_ancestry_follows_native_construction_not_search_order(self):
        for purpose, reader in [('component', v.parse_component), ('profileprep', v.parse_preparation)]:
            raw, _ = fixture(purpose=purpose)
            # Child (origin2) is first in search order; its directory parent is second.
            child = 'SOURCE 1 0 3 1 1 2 1 ' + hx('/fixture/g/pak0.pk3') + ' -'
            parent = ('SOURCE 2 0 1 1 1 1 0 ' + hx('/fixture/g') + ' ' + hx('/fixture/g') +
                      '\nPATH 2 ' + hx('/fixture/g') + '\nPUREPATH 2 -\n')
            rows = raw.decode().splitlines()
            rows[0] = rows[0].replace(' 1 1 0 0 0 ', ' 1 2 0 0 0 ')
            source = next(i for i, row in enumerate(rows) if row.startswith('SOURCE '))
            rows[source] = child
            rows.insert(source + 3, parent.rstrip())
            valid = ('\n'.join(rows) + '\n').encode()
            def read(value):
                return reader(value, hashlib.sha256(value).hexdigest(), WORLD)
            with self.subTest(purpose=purpose, graph='valid child-first'):
                self.assertEqual([p.origin for p in read(valid).providers], [2, 1])
            malformed = [valid.replace(b'SOURCE 1 0 3 1 1 2 1 ', b'SOURCE 1 0 3 1 1 2 0 '),
                         valid.replace(b'SOURCE 2 0 1 1 1 1 0 ', b'SOURCE 2 0 3 1 1 1 2 ')]
            for value in malformed:
                with self.subTest(purpose=purpose, graph=value[:140]), self.assertRaisesRegex(v.Invalid, 'ORIGIN_PARENT'):
                    read(value)

    def test_parent_case_and_nonadjacent_file_directory_aliases(self):
        cases = [{'models/Parent/one.txt': b'a', 'models/parent/two.txt': b'b'},
                 {'models/a': b'a', 'models/a.ext': b'b', 'models/a/child': b'c'}]
        for extra in cases:
            raw, _ = fixture(extra)
            with self.assertRaisesRegex(v.Invalid, 'CASE_ALIAS|FILE_DIRECTORY_ALIAS'):
                parse(raw)

    def test_duplicate_entry_and_noncanonical_number(self):
        raw, _ = fixture(duplicate=True)
        with self.assertRaises(v.Invalid):
            parse(raw)
        raw, _ = fixture()
        for number in [b'01', b'-1', b'9' * 10000]:
            with self.assertRaises(v.Invalid):
                parse(raw.replace(b'INPUT 1 3 1 ', b'INPUT 1 3 ' + number + b' '))

    def test_name_traversal_and_hex_aliases(self):
        for name in ['models/../escape', 'models//escape', 'models/with\\slash', 'models/nonascii\u00e9']:
            raw, _ = fixture({name: b'body'})
            with self.assertRaises(v.Invalid):
                parse(raw)
        raw, _ = fixture()
        with self.assertRaises(v.Invalid):
            parse(raw.replace(hx(WORLD).encode(), hx(WORLD).upper().encode(), 1))


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow flat reader')
class FlatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tasvfs-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'flat'
        self.root.mkdir()
        raw, self.bodies = fixture()
        self.component = parse(raw)
        (self.root / 'index.txt').write_bytes(raw)
        for name, body in self.bodies.items():
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)

    def test_exact_flat_then_same_size_body_drift(self):
        v.validate_flat(self.component, str(self.root))
        target = self.root / 'models/deep/actor.txt'
        target.write_bytes(b'x' * target.stat().st_size)
        with self.assertRaisesRegex(v.Invalid, 'FLAT_BYTES'):
            v.validate_flat(self.component, str(self.root))

    def test_extra_file_and_directory(self):
        for name, directory in [('extra.txt', False), ('empty-extra', True)]:
            target = self.root / name
            target.mkdir() if directory else target.write_bytes(b'extra')
            with self.assertRaises(v.Invalid):
                v.validate_flat(self.component, str(self.root))
            target.rmdir() if directory else target.unlink()

    def test_links_never_followed_or_accepted(self):
        target = self.root / 'models/deep/actor.txt'
        outside = Path(self.tmp.name) / 'outside.txt'
        outside.write_bytes(target.read_bytes())
        target.unlink()
        for hard in [False, True]:
            os.link(outside, target) if hard else target.symlink_to(outside)
            with self.assertRaises(v.Invalid):
                v.validate_flat(self.component, str(self.root))
            target.unlink()
        self.assertEqual(outside.read_bytes(), self.bodies['models/deep/actor.txt'])


if __name__ == '__main__':
    unittest.main()
