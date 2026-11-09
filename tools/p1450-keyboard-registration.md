# P1450 — keyboard enumeration is not proof of registration

## Problem and change

`rawkbds` records keyboards enumerated/bound into the Windows input device table.
It does not prove that Windows accepted raw-keyboard registration. The reader
previously used that count to explain why the keyboard observer was off, promise
coverage from another counter, and identify otherwise-unclaimed key device IDs.
Those conclusions were stronger than the recorded evidence.

`hidcheck.py` now states the registration/coverage limitation explicitly. An
unclaimed nonzero key device ID is still noted, without asserting raw provenance.
Legacy device ID0 remains a constant, not a proven raw-key identity, even beside
a positive enumeration count. Unavailable stays unavailable rather than measured
zero. Existing whole/partial observations, counters, `info`, faults and flags are
unchanged. This does not establish human-generated input.

No new capture/grammar/privacy field, input blocking, threshold, ranking, native
binary/pin/tag, QC Build, historical reread/backfill or schema change.

## Controls and results — 9 November 2026

- Same strengthened HID suite: untouched reader fails6 assertions out of314;
  corrected reader passes314/0. Existing acting controls cover API parsing,
  observed zero/nonzero, unavailable, partial and faulted journals. The initial
  devid0 fixture also claimed0 in its device table; it was strengthened to claim
  only1 BEFORE changing production code. Both control results are retained.
- Receipt268/0, captured journal snapshots12/0 and recording949/0.
- Canonical runs corpus acquired read-only; each captured buffer was supplied to
  baseline and subject parsers. All765 reports remain identical:561REC/179VIEW/
  25HID, faults346/5/0 before AND after. These are pre-existing faults, not a clean
  corpus or newly validated recordings. No file writes or reclassification.
- Python LSP reports no diagnostics; this is not a native build/runtime proof.

## Native remainder — OPEN, not fixed by this patch

Independent lifecycle review blocked the initial count-to-success-latch proposal:
observation pairing belongs to the input/window thread, while registration can
be initiated elsewhere. Ordinary resets/fallback on that other thread are not
safe. Failed registration replacement/removal can retain the previous Windows
binding, so mode and raw dispatch cannot simply be inferred from enumeration or
from an unsuccessful API call.

No native source was changed. Before implementing that follow-up, qualify thread-
owned transitions, refused replacement/removal, opt-in/observer transitions and
shutdown/reinit with acting event-interleaving controls. Prove exactly-once game
input and honest availability, without changing input policy. See BACKLOG.md.
The existing genuine-keyboard manual check in lextest.md is still pending.

## Delivery boundary

Source is published as `b2159d6d` (engine documentation only: `ca9c3a475`).
At05:11:30UTC on9November2026, that exact reader was installed in both Windows
`tools/` directories with guarded predecessor/paired-reader hashes and exact
`.pre-p1450-b2159d6d` rollback copies. Fourteen protected native/progs/config files
and the other three reader modules stayed unchanged. At05:12:41UTC each ACTUAL
installed reader passed314HID checks and12snapshot tests. The first verification
caller lacked the installed tools import prefix and stopped before tests; that
failure is retained, the caller path was corrected, and verification finished
without recopying either installed reader. Both final source/evidence reviews
were CLEAR-with-limits. No engine/progs/lobby restart was needed.

The backend's admitted reader closure must
not be overwritten or repinned in place: this patch is NOT a claim that a fresh
source-bound backend generation has been qualified or activated. The previously
completed P1434 deployment stays healthy and must not be replayed for this patch.
