#!/usr/bin/env python3
"""Client-free process-cut falsifiers for an UNIMPLEMENTED retirement proposal."""
import copy
from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

from update_retirement_protocol import (Event, Journal, MAX_ROWS, Protocol, Refusal, Row, digest)


class RetirementProtocolTests(unittest.TestCase):
    def fixture(self, pending=True, shared=False, first=False, attempts=1):
        one = b'resolved signed ordinary bytes'
        two = one if shared else b'pending signed ordinary bytes'
        zone = b'signed zone baseline'
        payload = {'ftesurf/one': one, 'ftesurf/two': two, 'ftesurf/zones/local/owned.json': zone}
        rows = {p: Row.for_bytes(p, data) for p, data in payload.items()}
        order = list(rows.values())
        if first:
            order.reverse()
        destinations = dict(payload)
        destinations['ftesurf/zones/local/owned.json'] = b'intervening local zone edit'
        if pending:
            destinations['ftesurf/two'] = b'old ordinary bytes'
        unrelated = {digest(b'unmanaged valid'): b'unmanaged valid',
                     digest(b'not actually stored'): b'unmanaged corrupt'}
        stage = {row.hash: payload[row.path] for row in rows.values()}
        stage.update(unrelated)
        stage['unmanaged.part'] = b'partial transfer'
        stage['unmanaged.install'] = b'install sibling'
        model = Protocol('new', rows, Journal('new', attempts, tuple(order)), destinations, stage,
                         preserved=['ftesurf/zones/local/owned.json'])
        return model, payload, rows, unrelated

    def assert_safe(self, model, original, unrelated):
        # Independent oracle: no outside identity may disappear; every surviving
        # candidate must retain a committed row, even after partial retirement.
        for name, data in unrelated.items():
            self.assertEqual(model.staged[name], data)
        self.assertEqual(model.staged['unmanaged.part'], b'partial transfer')
        self.assertEqual(model.staged['unmanaged.install'], b'install sibling')
        named = set() if model.journal is None else {row.hash for row in model.journal.rows}
        for row in original:
            if row.hash in model.staged:
                self.assertIn(row.hash, named, 'surviving candidate lost authority')
        pending_hashes = set()
        for row in original:
            data = model.destinations.get(row.path)
            readable_match = (data is not None and len(data) == row.size and
                              hashlib.blake2b(data, digest_size=32).hexdigest() == row.hash)
            if (row.path in model.unreadable_destinations or
                    (row.path not in model.preserved and not readable_match)):
                pending_hashes.add(row.hash)
        for name in model.removed:
            self.assertIn(name, {row.hash for row in original})
            self.assertNotIn(name, pending_hashes, 'shared pending deletion')

    def test_partial_publication_retains_full_superset_and_shared_guard_acts(self):
        for shared in (False, True):
            for first in (False, True):
                m, payload, rows, unrelated = self.fixture(shared=shared, first=first)
                original = m.journal.rows
                events = list(m.pass_events())
                self.assertEqual(m.journal, Journal('new', 2, original))
                self.assertIn(Event('published'), events)
                self.assertIn(Event('removed', rows['ftesurf/zones/local/owned.json'].hash), events)
                self.assertEqual(rows['ftesurf/one'].hash in m.staged, shared)
                self.assertIn(rows['ftesurf/two'].hash, m.staged)
                self.assertEqual(m.ledger_version, 'old')
                self.assertIsNone(m.certificate)
                self.assert_safe(m, original, unrelated)
                m.destinations['ftesurf/two'] = payload['ftesurf/two']  # independent repair actor
                list(m.pass_events())
                self.assertIsNone(m.journal)
                self.assertEqual(m.ledger_version, 'new')
                self.assertEqual(m.certificate, 'new')
                self.assert_safe(m, original, unrelated)

    def test_every_process_cut_retains_authority_then_repaired_restart_finishes(self):
        cuts = 0
        for pending in (False, True):
            for shared in (False, True):
                for first in (False, True):
                    full, _, _, _ = self.fixture(pending, shared, first)
                    count = len(list(full.pass_events()))
                    for stop in range(count + 1):
                        m, payload, _, unrelated = self.fixture(pending, shared, first)
                        original = m.journal.rows
                        iterator = m.pass_events()
                        for _ in range(stop):
                            next(iterator)
                        iterator.close()  # lose volatile continuation, not persistent state
                        self.assert_safe(m, original, unrelated)
                        m.destinations['ftesurf/two'] = payload['ftesurf/two']
                        list(m.pass_events())
                        self.assertIsNone(m.journal)
                        self.assert_safe(m, original, unrelated)
                        cuts += 1
        self.assertEqual(cuts, 44)  # shared hashes collapse one destructive event

    def test_blocked_or_missing_candidate_at_every_cut_can_resume_after_repair(self):
        def configure(m, rows, kind):
            name = rows['ftesurf/zones/local/owned.json'].hash
            if kind == 'held':
                m.held_objects.add(name)
            elif kind == 'corrupt':
                m.staged[name] = b'corrupt candidate bytes'
            elif kind == 'unreadable':
                m.unreadable_objects.add(name)
            else:
                del m.staged[name]
        cuts = 0
        for kind in ('held', 'corrupt', 'unreadable', 'missing'):
            for pending in (False, True):
                for first in (False, True):
                    full, _, rows, _ = self.fixture(pending, first=first)
                    configure(full, rows, kind)
                    count = len(list(full.pass_events()))
                    for stop in range(count + 1):
                        m, payload, rows, unrelated = self.fixture(pending, first=first)
                        original = m.journal.rows
                        configure(m, rows, kind)
                        iterator = m.pass_events()
                        for _ in range(stop):
                            next(iterator)
                        iterator.close()
                        self.assert_safe(m, original, unrelated)
                        m.destinations['ftesurf/two'] = payload['ftesurf/two']
                        m.held_objects.clear()
                        m.unreadable_objects.clear()
                        name = rows['ftesurf/zones/local/owned.json'].hash
                        if name in m.staged:
                            m.staged[name] = payload['ftesurf/zones/local/owned.json']
                        list(m.pass_events())
                        self.assertIsNone(m.journal)
                        self.assert_safe(m, original, unrelated)
                        cuts += 1
        self.assertEqual(cuts, 92)

    def test_admitted_completion_at_every_cut_preserves_increment_and_candidates(self):
        cuts = 0
        for held in (False, True):
            for first in (False, True):
                full, _, rows, _ = self.fixture(False, first=first)
                if held:
                    full.held_objects.add(rows['ftesurf/one'].hash)
                count = len(list(full.pass_events(content_admitted=True)))
                for stop in range(count + 1):
                    m, _, rows, unrelated = self.fixture(False, first=first)
                    original = m.journal.rows
                    if held:
                        m.held_objects.add(rows['ftesurf/one'].hash)
                    iterator = m.pass_events(content_admitted=True)
                    for _ in range(stop):
                        next(iterator)
                    iterator.close()
                    self.assert_safe(m, original, unrelated)
                    if stop >= 2 and m.journal is not None:
                        self.assertEqual(m.journal.attempts, 2)
                    m.held_objects.clear()
                    list(m.pass_events())  # already-complete replay is cleanup, not admission
                    self.assertIsNone(m.journal)
                    self.assert_safe(m, original, unrelated)
                    cuts += 1
        self.assertEqual(cuts, 32)

    def test_failed_publication_keeps_authority_and_every_staged_byte(self):
        m, _, _, _ = self.fixture()
        prior, stage = m.journal, dict(m.staged)
        events = m.pass_events(fail_publication=True)
        self.assertEqual(next(events), Event('temp-written'))
        with self.assertRaisesRegex(Refusal, 'replacement failed'):
            next(events)
        self.assertEqual(m.journal, prior)
        self.assertEqual(m.staged, stage)
        self.assertEqual(m.temp, Journal('new', 2, prior.rows))
        self.assertEqual(m.removed, [])

    def test_completed_held_object_retains_candidates_without_spending_budget(self):
        m, _, rows, unrelated = self.fixture(pending=False, attempts=3)
        original = m.journal
        held = rows['ftesurf/one'].hash
        m.held_objects.add(held)
        for _ in range(4):
            events = list(m.pass_events())
            self.assertIn(Event('retained', held), events)
            self.assertEqual(m.journal, original)
            self.assertEqual(m.certificate, 'new')
            self.assertFalse(m.new_apply_allowed())
            self.assert_safe(m, original.rows, unrelated)
        m.held_objects.clear()
        list(m.pass_events())
        self.assertIsNone(m.journal)
        self.assertTrue(m.new_apply_allowed())

    def test_failed_final_authority_unlink_is_nonfatal_and_idempotent(self):
        m, _, _, unrelated = self.fixture(False, attempts=3)
        original = m.journal
        events = list(m.pass_events(fail_drop=True))
        self.assertEqual(events[-1], Event('authority-drop-failed'))
        self.assertEqual(m.journal, original)
        self.assert_safe(m, original.rows, unrelated)
        self.assertFalse(m.new_apply_allowed())
        list(m.pass_events())
        self.assertIsNone(m.journal)
        self.assertEqual(m.certificate, 'new')

    def test_admitted_content_completion_persists_increment_before_held_retirement(self):
        m, _, rows, _ = self.fixture(False)
        original = m.journal.rows
        held = rows['ftesurf/one'].hash
        m.held_objects.add(held)
        events = list(m.pass_events(content_admitted=True))
        self.assertEqual(events[:3], [Event('temp-written'), Event('published'), Event('content-complete')])
        self.assertEqual(m.journal, Journal('new', 2, original))
        self.assertIn(held, m.staged)
        list(m.pass_events())
        self.assertEqual(m.journal.attempts, 2, 'cleanup must not spend another content attempt')
        m.held_objects.clear()
        list(m.pass_events())
        self.assertIsNone(m.journal)
        m, _, _, _ = self.fixture(False)
        prior, stage = m.journal, dict(m.staged)
        with self.assertRaisesRegex(Refusal, 'replacement failed'):
            list(m.pass_events(content_admitted=True, fail_publication=True))
        self.assertEqual(m.journal, prior)
        self.assertEqual(m.staged, stage)
        self.assertIsNone(m.certificate)

    def test_same_size_wrong_hash_wrong_size_and_unreadable_remain_named(self):
        for kind in ('same-size', 'wrong-size', 'unreadable'):
            for first in (False, True):
                m, payload, rows, unrelated = self.fixture(False, first=first)
                original = m.journal.rows
                row = rows['ftesurf/zones/local/owned.json']
                if kind == 'same-size':
                    body = payload[row.path]
                    m.staged[row.hash] = bytes([body[0] ^ 1]) + body[1:]
                    self.assertEqual(len(m.staged[row.hash]), row.size)
                    self.assertNotEqual(digest(m.staged[row.hash]), row.hash)
                elif kind == 'wrong-size':
                    m.staged[row.hash] = b'wrong length'
                    self.assertNotEqual(len(m.staged[row.hash]), row.size)
                else:
                    m.unreadable_objects.add(row.hash)
                before = m.staged[row.hash]
                events = list(m.pass_events())
                self.assertIn(Event('removed', rows['ftesurf/one'].hash), events)
                self.assertIn(Event('retained', row.hash), events)
                self.assertEqual(m.staged[row.hash], before)
                self.assert_safe(m, original, unrelated)
                self.assertIsNotNone(m.journal)
                m.unreadable_objects.clear()
                m.staged[row.hash] = payload[row.path]
                list(m.pass_events())
                self.assertIsNone(m.journal)

    def test_unresolved_content_at_exhaustion_refuses_before_any_mutation(self):
        m, payload, rows, _ = self.fixture(attempts=3)
        before = copy.deepcopy(m.__dict__)
        with self.assertRaisesRegex(Refusal, 'budget exhausted'):
            list(m.pass_events())
        self.assertEqual(m.__dict__, before)
        # Correcting STAGED input is not resolution of its still-old destination.
        m.staged[rows['ftesurf/two'].hash] = payload['ftesurf/two']
        with self.assertRaisesRegex(Refusal, 'budget exhausted'):
            list(m.pass_events())

    def test_partial_restarts_spend_content_budget_without_reset(self):
        m, _, _, _ = self.fixture()
        list(m.pass_events())
        self.assertEqual(m.journal.attempts, 2)
        list(m.pass_events())
        self.assertEqual(m.journal.attempts, 3)
        stage = dict(m.staged)
        with self.assertRaisesRegex(Refusal, 'budget exhausted'):
            list(m.pass_events())
        self.assertEqual(m.journal.attempts, 3)
        self.assertEqual(m.staged, stage)

    def test_missing_candidate_is_idempotent_but_failed_read_is_not_absence(self):
        m, _, rows, _ = self.fixture(False)
        del m.staged[rows['ftesurf/one'].hash]
        list(m.pass_events())
        self.assertIsNone(m.journal)
        m, _, rows, _ = self.fixture(False)
        m.unreadable_objects.add(rows['ftesurf/one'].hash)
        list(m.pass_events())
        self.assertIsNotNone(m.journal)
        self.assertIn(rows['ftesurf/one'].hash, m.staged)

    def test_full_signed_closure_is_required_before_completion_or_retirement(self):
        m, _, _, _ = self.fixture(False)
        outside = Row.for_bytes('ftesurf/outside-journal', b'signed outside content')
        m.signed_rows[outside.path] = outside
        before = copy.deepcopy(m.__dict__)
        with self.assertRaisesRegex(Refusal, 'installation incomplete'):
            list(m.pass_events())
        self.assertEqual(m.__dict__, before)

    def test_reduced_authority_unreadable_full_closure_refuses_before_completion(self):
        for path in ('ftesurf/one', 'ftesurf/zones/local/owned.json'):
            for admitted in (False, True):
                m, _, rows, _ = self.fixture(False)
                m.journal = Journal('new', 1, (rows['ftesurf/two'],))
                m.unreadable_destinations.add(path)
                before = copy.deepcopy(m.__dict__)
                with self.assertRaisesRegex(Refusal, 'unreadable full signed installation'):
                    list(m.pass_events(content_admitted=admitted))
                self.assertEqual(m.__dict__, before)

    def test_shared_hash_oracle_does_not_trust_implementation_pending_predicate(self):
        m, _, rows, unrelated = self.fixture(shared=True)
        original = m.journal.rows
        name = rows['ftesurf/one'].hash
        del m.staged[name]  # independent actor simulating an unsafe shared removal
        m.removed.append(name)
        with patch.object(m, 'pending', return_value=()):
            with self.assertRaisesRegex(AssertionError, 'shared pending deletion'):
                self.assert_safe(m, original, unrelated)

    def test_no_authority_and_legacy_reduced_authority_cannot_adopt_outside_orphans(self):
        for authority in ('absent', 'reduced'):
            m, _, rows, unrelated = self.fixture(False)
            outside = rows['ftesurf/one'].hash
            original_bytes = m.staged[outside]
            m.journal = None if authority == 'absent' else Journal('new', 1, (rows['ftesurf/two'],))
            list(m.pass_events())
            self.assertEqual(m.staged[outside], original_bytes)
            for name, data in unrelated.items():
                self.assertEqual(m.staged[name], data)

    def test_failed_temp_is_never_a_candidate_or_recovery_authority(self):
        m, _, _, _ = self.fixture(False)
        temp = Journal('untrusted-temp', 3, ())
        m.temp = temp
        list(m.pass_events())
        self.assertEqual(m.temp, temp)
        self.assertIsNone(m.journal)
        m.journal = None
        stage = dict(m.staged)
        list(m.pass_events())
        self.assertEqual(m.staged, stage)
        self.assertEqual(m.temp, temp)

    def test_tuple_exec_size_hash_path_duplicates_bounds_and_generation_refuse(self):
        for field, value in [('hash', '0' * 64), ('size', 0), ('executable', True), ('path', 'outside')]:
            m, _, _, _ = self.fixture()
            m.journal = replace(m.journal, rows=(replace(m.journal.rows[0], **{field: value}),))
            before = copy.deepcopy(m.__dict__)
            with self.assertRaisesRegex(Refusal, 'unsigned candidate'):
                list(m.pass_events())
            self.assertEqual(m.__dict__, before)
        for mutate in (lambda j: replace(j, rows=j.rows + (j.rows[0],)),
                       lambda j: replace(j, rows=j.rows * (MAX_ROWS + 1)),
                       lambda j: replace(j, rows=()), lambda j: replace(j, attempts=0),
                       lambda j: replace(j, attempts=True), lambda j: replace(j, attempts=4),
                       lambda j: replace(j, version='older')):
            m, _, _, _ = self.fixture()
            m.journal = mutate(m.journal)
            with self.assertRaises(Refusal):
                list(m.pass_events())

    def test_linked_candidate_and_unreadable_destination_refuse_whole_batch(self):
        for kind in ('linked', 'unreadable'):
            m, _, rows, _ = self.fixture(False)
            if kind == 'linked':
                m.linked_objects.add(rows['ftesurf/one'].hash)
            else:
                m.unreadable_destinations.add('ftesurf/one')
            before = copy.deepcopy(m.__dict__)
            with self.assertRaises(Refusal):
                list(m.pass_events())
            self.assertEqual(m.__dict__, before)

    def test_destructive_seam_rechecks_shared_pending_reference(self):
        m, _, rows, _ = self.fixture(False, shared=True)
        iterator = m.pass_events()
        self.assertEqual(next(iterator), Event('content-complete'))
        m.destinations['ftesurf/two'] = b'old bytes'
        list(iterator)
        self.assertIn(rows['ftesurf/one'].hash, m.staged)
        self.assertIsNotNone(m.journal)
        self.assertEqual(m.removed, [rows['ftesurf/zones/local/owned.json'].hash])

    def test_oracle_discriminates_legacy_reduction_and_unlink_before_purge(self):
        m, _, rows, unrelated = self.fixture()
        original = m.journal.rows
        # Independent source-shaped old actors, NOT protocol implementation modes.
        m.journal = Journal('new', 2, (rows['ftesurf/two'],))
        with self.assertRaisesRegex(AssertionError, 'lost authority'):
            self.assert_safe(m, original, unrelated)
        m, _, _, unrelated = self.fixture(False)
        original = m.journal.rows
        m.journal = None  # interrupted completion unlink before any purge
        with self.assertRaisesRegex(AssertionError, 'lost authority'):
            self.assert_safe(m, original, unrelated)


if __name__ == '__main__':
    unittest.main()
