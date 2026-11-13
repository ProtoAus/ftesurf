# P1532 — native loss declarations cannot cancel into a false zero

Implemented and source-qualified; independent verifier review and deployment
remain pending. The owner-postponed physical test was not needed or invented.

## Problem and correction

The producer declares loss counters as unsigned int and writes them with `%u`
(`IN_Journal_Frame`/`IN_JournalEnd_f` in native `client/in_generic.c`). The reader
accepted negative/out-of-native-range values. Invalid declarations could cancel
reported loss and produce a successful format report with dropped0 and no loss
warning. Rejected records could leave zero or a subtotal as a whole measurement.

Validate the existing native unsigned32-bit loss domain without wrapping invalid
values into another quantity. Reject unusable marker/closing declarations and
withhold the drop measurement. Known positive loss remains disclosed, not a claim
of human admissibility. Independently finite clocks, angle comparisons and raw
count joins remain active. A clock overflow does not discard a finite counter
payload, and signed-1 sentinels on different backend fields retain their meaning.
There is no native, capture, writer, recording-field, signature, ranking,
threshold, evidence-identity or QC Build change. Native pin/tag stay held.

## Acting verification

- Same final fixture: untouched reader **1150 checks,24 failures**; corrected
  reader **1150 checks, zero failures**, including **60 new assertions**.
- Actual ordinary `python tools/hidcheck.py --verbose <owned-fixture>` accepts
  the valid control. The same CLI formerly accepted the malformed cancellation;
  it now exits1/refuses it. No player files were edited.
- Zero, positive1, nativeMAX and legitimate closing totals ahead of emitted
  markers remain exact. Every malformed-loss fixture still exercises19finite
  angle/count intervals, not an untested blanket suppression.
- `test_reccheck.py`: **949/0**; `test_rcptcheck.py`: **800/0**;
  `test_journal_diagnostics.py`: **32 tests/0**.
- Normal isolated `src/build.ps1 -NoDeploy -Jobs 8 -FteRoot <owned-engine>`:
  **three QC VMs, zero warnings**. Native code is unchanged; its earlier
  qualification is not repeated or represented as a new native test.
- Actual supported Windows compiler reports `__SIZEOF_INT__ 4`; supported
  producer uses unsigned-int counters. This is field-domain validation, not a
  new statistical threshold or a claim about hardware input truth.
- **134 retained journal byte hashes and every fault/info/note** match the
  parent; **three existing faulty files** stay faulty. These retained fixtures
  and captures are not independent human labels or calibration.
- **568REC +183VIEW**: all751 hashes and every paired per-file report identical;
  **356 existing faults** unchanged. No old recording or stored verdict regraded.

## Limits and preserved execution failures

The first optional compiler-ABI probe, after tests/build passed, failed outside
the documented compiler PATH; its stderr was not captured and the exact cause is
not asserted. The bounded repeat used the documented UCRT+MSYS environment,
retained stdout/stderr and confirmed the supported ABI. No product edit or passed
feature test was changed/repeated to hide that probe failure. An initial exact
text edit found a different comment and made no mutation; the real source block
was reread and the same targeted edit applied.

Source publication is not independent review, live rollout or human/device
acceptance. Required verifier review remains before deployment; no stale report,
supervisor self-clear or silent provider/CLI fallback. Other unsigned closing
fields and truncated counter-direction checks are not claimed by this bounded
loss correction. The deferred native/compiler/filewriter audit stays deferred.
