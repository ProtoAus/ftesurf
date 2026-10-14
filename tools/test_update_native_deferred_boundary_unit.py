"""Source-named raw deferred boundary mutations; no native process launch."""
from pathlib import Path
import unittest

import test_update_native_deferred_boundary as gate
import test_update_native_journal_initial_unit as initial_units


class DeferredBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.binding = initial_units.InitialTests().bind()
        self.dest = Path('C:/owned/runtime')

    def events(self, mode):
        b = self.binding
        meta = self.dest / '.ftesurf-updater/ingame'
        events = [dict(event='child', pid=1234),
            dict(event='writer', ordinal=1, rva=b['entry_rva'], thread=8, caller_rva=b['initial_caller_rva']),
            dict(event='writer', ordinal=2, rva=b['entry_rva'], thread=8, caller_rva=b['deferred_caller_rva']),
            dict(event='before', rva=b['pre_rva'], thread=8, paths_verified=True, authority_absent=False),
            dict(event='boundary', ordinal=2, thread=8, commit_caller_rva=b['commit_caller_rva'], flags=1,
                source=(meta / 'journal.tmp').as_posix(), destination=(meta / 'journal.json').as_posix())]
        if mode == 'source-lock':
            events.append(dict(event='source-lock', rename_error=32, write_allowed=True))
        events += [dict(event='after', rva=b['post_rva'], thread=8, native_result=0 if mode == 'source-lock' else 1, ordinal=2),
                   dict(event='exit', pid=1234, code=0, hits=3, calls=2)]
        return events

    def grade(self, events, mode='source-lock'):
        return gate.grade_events(events, self.binding, mode, self.dest)

    def test_acting_failure_and_success_raw_returns(self):
        for mode in ('none', 'source-lock'):
            self.assertEqual(self.grade(self.events(mode), mode), (1234, 0))

    def test_paths_flags_commit_caller_refuse(self):
        for key, value in [('source', 'C:/wrong/journal.tmp'), ('destination', 'C:/wrong/journal.json'),
                           ('flags', 3), ('ordinal', 1), ('commit_caller_rva', 0), ('thread', 9)]:
            events = self.events('source-lock')
            events[4][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.grade(events)

    def test_missing_or_reordered_raw_boundary_refuses(self):
        for index in range(len(self.events('source-lock'))):
            events = self.events('source-lock')
            del events[index]
            with self.subTest(index=index), self.assertRaises((AssertionError, ValueError)):
                self.grade(events)
        events = self.events('source-lock')
        events[4], events[5] = events[5], events[4]
        with self.assertRaises(AssertionError):
            self.grade(events)

    def test_return_not_inferred_from_probe(self):
        for mode, result in [('source-lock', 1), ('none', 0), ('none', -1), ('none', True), ('source-lock', '0')]:
            events = self.events(mode)
            events[-2]['native_result'] = result
            with self.subTest(mode=mode, result=result), self.assertRaises(AssertionError):
                self.grade(events, mode)

    def test_same_thread_caller_ordinal_and_exit_required(self):
        for index, key, value in [(1, 'ordinal', 2), (2, 'ordinal', 1), (2, 'thread', 9),
                                  (2, 'caller_rva', 0), (3, 'paths_verified', False),
                                  (3, 'authority_absent', True), (-2, 'rva', 0), (-2, 'ordinal', 1),
                                  (-1, 'code', 86), (-1, 'hits', 2), (-1, 'calls', 1)]:
            events = self.events('source-lock')
            events[index][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(AssertionError):
                self.grade(events)

    def test_writable_open_and_independent_probe_required(self):
        for key, value in [('rename_error', 0), ('write_allowed', False)]:
            events = self.events('source-lock')
            events[5][key] = value
            with self.assertRaises(AssertionError):
                self.grade(events)

    def test_native_byte_import_direct_call_and_stack_mutations(self):
        fixture = initial_units.InitialTests()
        for offset in (0, 2, 15, 0x40, 0x42, 0x46, 0x200, 0x521, 0x561):
            code, listing, assembly = fixture.fixture()
            code[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(AssertionError):
                fixture.bind(code=code, listing=listing, assembly=assembly)


if __name__ == '__main__':
    unittest.main()
