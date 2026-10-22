"""Acting structural controls, not native trajectory/qualification acceptance."""
import hashlib
import os
from pathlib import Path
import re
import struct
import unittest
import heldmeta as h

GENERATION = "01" * 16


def encode(family, **values):
    tokens = [family]
    for name, kind in h.SCHEMAS[family]:
        value = values.get(name, GENERATION if kind == "G" else 0)
        if kind == "F":
            token = struct.pack(">f", value).hex()
        elif kind in ("G", "D"):
            token = value if isinstance(value, str) else bytes(value if value else h.WIDTHS[kind] // 2).hex()
        else:
            token = int(value).to_bytes(h.WIDTHS[kind] // 2, "big", signed=kind == "I").hex()
        tokens.append(token)
    return (" ".join(tokens) + "\n").encode("ascii")


def fixture(extra_held=False):
    """Synthetic sealed protocol: no server/provenance or honest-user verdict."""
    events = []
    message = execution = alias = 0

    def add(family, **kw):
        events.append((family, dict(message=message, execution=0, **kw)))

    def begin():
        nonlocal message
        message += 1
        add("hscope", kind=1, phase=1)

    def end():
        add("hpend", last_execution=execution)
        add("hscope", kind=1, phase=2)

    def move(pmtype):
        nonlocal execution, alias
        execution += 1
        add("hpre", phase=1)
        events[-1][1]["execution"] = execution
        if pmtype == 5:
            add("hmaint", site=1)
            events[-1][1]["execution"] = execution
        add("hpre", phase=2)
        events[-1][1]["execution"] = execution
        add("hmove", effective_msec=7.5, gamespeed=1, context=1,
            pmtype=pmtype, ownerkind=3 if pmtype == 5 else 1,
            ownerindex=0 if pmtype == 5 else alias)
        if pmtype != 5:
            alias += 1
        events[-1][1]["execution"] = execution
        add("hdone", ticksrun=0, carry=.0075, raw_moveticks=execution)
        events[-1][1]["execution"] = execution

    add("hctx", context=1, rules=1)
    begin()
    add("hinit", context=1)
    events[-1][1]["execution"] = 1
    move(0)
    add("hpost", phase=1)
    add("hpost", phase=2)
    end()
    begin()
    add("hscope", kind=3, phase=1)
    add("hobs", boundary=1)
    add("hentry", saved_movetype=3)
    add("hscope", kind=3, phase=2)
    move(5)
    add("hpost", phase=1)
    add("hmaint", site=2)
    add("hfreeze")
    add("hmaint", site=3)
    add("hpost", phase=2)
    if extra_held:
        move(5)
        add("hpost", phase=1)
        add("hmaint", site=2)
        add("hmaint", site=3)
        add("hpost", phase=2)
    end()
    begin()
    add("hscope", kind=3, phase=1)
    add("hrelease", restored_movetype=3)
    add("hobs", boundary=2)
    add("hscope", kind=3, phase=2)
    move(0)
    add("hpost", phase=1)
    add("hthaw")
    add("hobs", boundary=3)
    add("hpost", phase=2)
    end()
    begin()
    move(0)
    add("hpost", phase=1)
    add("hobs", boundary=4)
    add("hterminal", closekind=1)
    add("hpost", phase=2)
    end()
    counters = dict(first_execution=1, last_execution=execution, executions=execution,
                    pre_enters=4, pre_exits=4, movers=4, completions=4,
                    post_enters=4, post_exits=4, messages=4, commands=2,
                    scene_fences=25, control_events=7, effect_dispatches=0, qualification=1)
    if extra_held:
        for name in ("pre_enters", "pre_exits", "movers", "completions", "post_enters", "post_exits"):
            counters[name] += 1
        counters["scene_fences"] += 7
        counters["control_events"] += 3
    # Actual native sites: 16 pre/post +4 command +5 physical-control fences.
    # Message/completion counters are independent, not extra census increments.
    return events, counters


def seal(events, counters):
    lines = []
    ledger = hashlib.sha256(b"FTESURF-aircell1-ledger-1").digest()
    execution_ledger = hashlib.sha256(b"FTESURF-aircell1-exec-1").digest()
    mover = None
    for ordinal, (family, values) in enumerate(events, 1):
        line = encode(family, ordinal=ordinal, **values)
        record = h.parse_record(line)
        ledger = hashlib.sha256(ledger + record.canonical).digest()
        if family in ("hmove", "hordinary"):
            mover = record.canonical
        elif family == "hdone" and mover is not None:
            execution_ledger = hashlib.sha256(execution_ledger + mover + record.canonical).digest()
            mover = None
        lines.append(line)
    lines.append(encode("hseal", ordinal=len(lines) + 1, ledger=ledger,
                        execution_ledger=execution_ledger, **counters))
    return lines


def nonce_fixture(where):
    events, counters = fixture()
    ack = [("hscope", dict(message=1, execution=0, kind=4, phase=phase)) for phase in (1, 2)]
    if where == "zero":
        for _, values in events:
            if values["message"]:
                values["message"] += 1
        events[1:1] = [("hscope", dict(message=1, execution=0, kind=1, phase=1)),
                       *ack, ("hpend", dict(message=1, execution=0, last_execution=0)),
                       ("hscope", dict(message=1, execution=0, kind=1, phase=2))]
        counters["messages"] += 1
    else:
        index = next(i for i, (name, _) in enumerate(events) if name == "hinit")
        events[index + (where == "after"):index + (where == "after")] = ack
    acked = False
    for family, values in events:
        if family == "hscope" and values["kind"] == 4 and values["phase"] == 2:
            acked = True
        if ("clock_flags", "F") in h.SCHEMAS[family]:
            values["clock_flags"] = h.TF_NONCE if acked else 0
    counters["commands"] += 1
    counters["scene_fences"] += 2
    return events, counters


class HeldMetadataTest(unittest.TestCase):
    def test_actual_native_pin_schema(self):
        root = os.environ.get("FTESURF_FTEROOT")
        if not root:
            self.skipTest("set documented FTESURF_FTEROOT for paired native source check")
        engine = Path(root) / "engine"
        source = (engine / "server/sv_user.c").read_text(encoding="utf-8")
        table = source.split("const char *sv_pmpin_names[SV_PMPIN_COUNT] =", 1)[1].split("};", 1)[0]
        names = re.findall(r'"([a-z0-9_]+)"', table)
        self.assertEqual(len(h.PIN_NAMES), 70)
        self.assertEqual(names[:len(h.PIN_NAMES)], h.PIN_NAMES)
        self.assertEqual(names[len(h.PIN_NAMES):], ["momlimit", "momcool", "momslide"])
        server = (engine / "server/server.h").read_text(encoding="utf-8")
        count = re.search(r"#define\s+SV_PMPIN_COUNT\s+(\d+)", server)
        self.assertIsNotNone(count)
        self.assertEqual(int(count.group(1)), len(names))
        mover = (engine / "common/pmove.h").read_text(encoding="utf-8")
        profile = (engine / "server/sv_held_initial.h").read_text(encoding="utf-8")
        native_version = re.search(r"#define PMSRC_VERSION (\d+)", mover)
        profile_version = re.search(r"#define HELD_SOURCE_VERSION (\d+)", profile)
        self.assertIsNotNone(native_version)
        self.assertIsNotNone(profile_version)
        self.assertEqual(int(native_version.group(1)), 10)
        self.assertEqual(profile_version.group(1), native_version.group(1))
        framing = (engine / "server/sv_held_ledger.h").read_text(encoding="utf-8")
        shared = (Path(__file__).resolve().parent.parent / "src/shared/sh_defs.qc").read_text(encoding="utf-8")
        for c_name, qc_name, expected in (("HELD_BASE_REC_VERSION", "FS_REC_VERSION", h.BASE_VERSION),
                                           ("HELD_NATIVE_REC_VERSION", "FS_REC_NATIVE_VERSION", h.NATIVE_VERSION)):
            c_version = re.search(r"#define\s+%s\s+(\d+)" % c_name, framing)
            qc_version = re.search(r"#define\s+%s\s+(\d+)" % qc_name, shared)
            self.assertIsNotNone(c_version)
            self.assertIsNotNone(qc_version)
            self.assertEqual(int(c_version.group(1)), expected)
            self.assertEqual(int(qc_version.group(1)), expected)
        self.assertEqual(h.NATIVE_VERSION, h.BASE_VERSION + 1)
        # Paired ABI assertions, not proof of the zero-only predicate:
        # native kernel controls exercise each excluded nonzero input.

    def test_named_fixed_arities(self):
        self.assertEqual(len(h.CTX), 89)
        self.assertEqual(len(h.CLOCK), 36)
        self.assertEqual(len(h.PHYS), 54)
        for family, arity in h.ARITIES.items():
            with self.subTest(family=family):
                self.assertEqual(len(encode(family).split()), arity + 1)
                h.parse_record(encode(family))

    def test_canonical_byte_order(self):
        line = encode("hmove", ordinal=1, message=2, execution=3,
                      effective_msec=7.5, gamespeed=1, context=1)
        record = h.parse_record(line)
        expected = (b"hmove\0" + bytes.fromhex(GENERATION) +
                    struct.pack(">QQQffIIII", 1, 2, 3, 7.5, 1, 1, 0, 0, 0))
        self.assertEqual(record.canonical, expected)

    def test_complete_callback_fixture(self):
        events, counters = fixture()
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")

    def test_native_fence_sites_do_not_invent_message_or_mover_fences(self):
        events, counters = fixture()
        # Independently driven native C coverage gives25 for this trace.
        # Incorrectly counting messages/completions instead of callback exits
        # gives29; a rehashed witness cannot replace the native-site count.
        self.assertEqual(counters["scene_fences"], 25)
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")
        counters["scene_fences"] = 29
        with self.assertRaisesRegex(h.Malformed, "independent coverage counter"):
            h.parse_witness(seal(events, counters))

    def test_no_event_after_packet_closure(self):
        events, counters = fixture()
        index = next(i for i, (name, _) in enumerate(events) if name == "hpend")
        # The full original move remains; a new callback is inserted AFTER its close.
        events[index + 1:index + 1] = [("hpost", dict(message=1, execution=0, phase=p)) for p in (1, 2)]
        counters["post_enters"] += 1
        counters["post_exits"] += 1
        counters["scene_fences"] += 2
        with self.assertRaisesRegex(h.Malformed, "event after packet closure"):
            h.parse_witness(seal(events, counters))

    def test_no_second_seal_after_closed_witness(self):
        events, counters = fixture()
        lines = seal(events, counters)
        last = dict(h.parse_record(lines[-1]).values)
        last["ordinal"] += 1
        lines.append(encode("hseal", **last))
        with self.assertRaises(h.Malformed):
            h.parse_witness(lines)

    def test_frame_after_closed_packet_does_not_inherit_pending(self):
        events, counters = fixture()
        index = next(i for i, (name, values) in enumerate(events)
                     if name == "hscope" and values["kind"] == 1 and values["phase"] == 2)
        events[index + 1:index + 1] = [("hscope", dict(message=0, execution=0, kind=2, phase=p)) for p in (1, 2)]
        counters["scene_fences"] += 2
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")

    def test_packet_without_move_still_needs_close(self):
        events, counters = fixture()
        # Insert an entire native accepted-message envelope with no mover callback.
        index = next(i for i, (name, values) in enumerate(events)
                     if name == "hscope" and values["kind"] == 1 and
                     values["phase"] == 1 and values["message"] == 4)
        for _, values in events[index:]:
            values["message"] += 1
        empty = [("hscope", dict(message=4, execution=0, kind=1, phase=1)),
                 ("hpend", dict(message=4, execution=0, last_execution=3)),
                 ("hscope", dict(message=4, execution=0, kind=1, phase=2))]
        events[index:index] = empty
        counters["messages"] += 1
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")
        events.pop(index + 1)
        with self.assertRaises(h.Malformed):
            h.parse_witness(seal(events, counters))

    def test_nonce_ack_before_initial_horizon_same_or_zero_move_message(self):
        for where in ("before", "zero"):
            with self.subTest(where=where):
                events, counters = nonce_fixture(where)
                self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")
                self.assertNotEqual(next(i for i, (f, _) in enumerate(events, 1) if f == "hinit"), 3)

    def test_nonce_ack_after_initial_derives_only_later_flags(self):
        events, counters = nonce_fixture("after")
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")
        self.assertEqual(next(v for f, v in events if f == "hinit")["clock_flags"], 0)
        self.assertEqual(next(v for f, v in events if f == "hfreeze")["clock_flags"], h.TF_NONCE)

    def test_rehashed_nonce_flag_or_command_mutation_is_not_justified(self):
        for where in ("before", "after", "zero"):
            events, counters = nonce_fixture(where)
            for family, values in events:
                if family == "hscope" and values["kind"] == 4:
                    values["kind"] = 3
            with self.assertRaisesRegex(h.Malformed, "nonce flag"):
                h.parse_witness(seal(events, counters))
        events, counters = nonce_fixture("before")
        next(v for f, v in events if f == "hterminal")["clock_flags"] = 0
        with self.assertRaisesRegex(h.Malformed, "nonce flag"):
            h.parse_witness(seal(events, counters))

    def test_preinitial_frame_is_not_a_command(self):
        events, counters = fixture()
        events[1:1] = [("hscope", dict(message=0, execution=0, kind=2, phase=p)) for p in (1, 2)]
        counters["scene_fences"] += 2
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")
        counters["commands"] += 1
        with self.assertRaisesRegex(h.Malformed, "independent coverage counter"):
            h.parse_witness(seal(events, counters))

    def test_omission_rehashed_but_native_counter_unchanged(self):
        events, counters = fixture()
        del events[next(i for i, (name, values) in enumerate(events)
                        if name == "hmaint" and values["site"] == 3)]
        # Reject at the applicable callback, before the later census mismatch.
        with self.assertRaisesRegex(h.Malformed, "maintenance"):
            h.parse_witness(seal(events, counters))

    def test_maintenance_omissions_rehashed_and_recounted(self):
        # Native-independent counters cannot be recreated by a reader. Even a
        # mutation that rewrites them must not erase required source operations.
        for sites in ((1,), (2,), (3,), (2, 3), (1, 2, 3)):
            events, counters = fixture()
            removed = sum(name == "hmaint" and values["site"] in sites
                          for name, values in events)
            events = [(name, values) for name, values in events
                      if not (name == "hmaint" and values["site"] in sites)]
            counters["control_events"] -= removed
            counters["scene_fences"] -= removed
            with self.subTest(sites=sites):
                with self.assertRaisesRegex(h.Malformed, "maintenance|freeze accounting"):
                    h.parse_witness(seal(events, counters))

    def test_maintenance_duplicates_rehashed_and_recounted(self):
        for site in (1, 2, 3):
            events, counters = fixture()
            index = next(i for i, (name, values) in enumerate(events)
                         if name == "hmaint" and values["site"] == site)
            name, values = events[index]
            events.insert(index + 1, (name, dict(values)))
            counters["control_events"] += 1
            counters["scene_fences"] += 1
            with self.subTest(site=site):
                with self.assertRaisesRegex(h.Malformed, "maintenance"):
                    h.parse_witness(seal(events, counters))

    def test_freeze_cannot_be_deferred_to_a_later_post(self):
        events, counters = fixture(extra_held=True)
        self.assertEqual(h.parse_witness(seal(events, counters)).status, "sealed")
        index = next(i for i, (name, _) in enumerate(events) if name == "hfreeze")
        freeze = events.pop(index)
        second = [i for i, (name, v) in enumerate(events)
                  if name == "hmaint" and v["site"] == 2][1]
        for key in ("message", "execution"):
            freeze[1][key] = events[second][1][key]
        events.insert(second + 1, freeze)
        with self.assertRaisesRegex(h.Malformed, "maintenance"):
            h.parse_witness(seal(events, counters))

    def test_maintenance_order_and_freeze_fence_rehashed(self):
        for operation in ("swap-post", "repeat-post", "freeze-before-site2", "site4"):
            events, counters = fixture()
            second = next(i for i, (name, values) in enumerate(events)
                          if name == "hmaint" and values["site"] == 2)
            third = next(i for i, (name, values) in enumerate(events)
                         if name == "hmaint" and values["site"] == 3)
            if operation == "swap-post":
                events[second], events[third] = events[third], events[second]
            elif operation == "repeat-post":
                events[third][1]["site"] = 2
            elif operation == "freeze-before-site2":
                events[second], events[second + 1] = events[second + 1], events[second]
            else:
                events[third][1]["site"] = 4
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(h.Malformed, "maintenance|freeze accounting"):
                    h.parse_witness(seal(events, counters))

    def test_distinct_missing_duplicate_ordered_controls(self):
        original, counters = fixture()
        for family in ("hpre", "hmove", "hdone", "hpost", "hentry", "hrelease", "hthaw", "hpend", "hterminal"):
            index = next(i for i, (name, _) in enumerate(original) if name == family)
            for operation in ("missing", "duplicate", "reordered"):
                events = [(name, dict(values)) for name, values in original]
                if operation == "missing":
                    del events[index]
                elif operation == "duplicate":
                    events.insert(index, events[index])
                else:
                    events[index], events[index + 1] = events[index + 1], events[index]
                with self.subTest(family=family, operation=operation):
                    with self.assertRaises(h.Malformed):
                        h.parse_witness(seal(events, counters))

    def test_fractional_timing_grammar_not_a_replay_claim(self):
        record = h.parse_record(encode("hmove", effective_msec=7.8125, gamespeed=1))
        self.assertEqual(record.values["effective_msec"], 7.8125)
        for value in (-0.0, -1.0, float("inf"), float("nan")):
            with self.assertRaises(h.Malformed):
                h.parse_record(encode("hmove", effective_msec=value))

    def test_context_generation_counter_closure(self):
        for family, key, value in (("hmove", "context", 2), ("hmove", "execution", 5),
                                   ("hentry", "saved_movetype", 8), ("hterminal", "closekind", 3),
                                   ("hctx", "generation", "02" * 16)):
            events, counters = fixture()
            next(values for name, values in events if name == family)[key] = value
            with self.subTest(family=family, key=key):
                with self.assertRaises(h.Malformed):
                    h.parse_witness(seal(events, counters))

    def test_failed_finalization_has_no_detail(self):
        failure = encode("hfail", status=1)
        self.assertEqual(h.parse_witness([failure]).status, "unsupported")
        for details in ([failure, encode("hctx")], [encode("hctx"), failure]):
            with self.assertRaises(h.Malformed):
                h.parse_witness(details)
        self.assertEqual(h.parse_witness([encode("hfail", status=2)]).status, "incomplete")

    def test_exact_lexical_contract(self):
        line = encode("hmove")
        for damaged in (line[:-1], line.replace(b" ", b"  ", 1), line.replace(b"\n", b"\r\n"),
                        line.replace(b"00000000", b"0000000A", 1), line + b"x",
                        line.replace(b"hmove", b"hunknown"), line + b" ", b"hctx\xff\n"):
            with self.subTest(damaged=damaged[:30]):
                with self.assertRaises(h.Malformed):
                    h.parse_record(damaged)

    def test_bounded_input_before_append(self):
        for lines in ([], [None], [b"x" * (h.MAX_LINE + 1)],
                      (encode("hfail", status=1) for _ in range(h.MAX_EVENTS + 1))):
            with self.assertRaises(h.Malformed):
                h.parse_witness(lines)


if __name__ == "__main__":
    unittest.main()
