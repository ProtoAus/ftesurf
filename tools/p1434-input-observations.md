# P1434 — stored receipt input observations

## Implemented

The existing journal reader's input-corroboration diagnostics now survive the
captured signed-byte receipt projection, its existing sweep storage and authenticated
admin detail. Fixed bounded typed fields include legacy mouse/key presses,
handle-less keyboard reports, the keyboard observer's initial availability/state,
observer changes and the reader's partial-key qualifier.

Measured zero remains zero. Missing/off/unavailable/changed keyboard observation
never becomes a whole-journal zero. Missing totals render explicitly unavailable.
Partial-key wording applies only to keyboard measurements, not mouse or identity
measurements. Uncorroborated input remains a diagnostic, not proof of cheating.

Malformed/skipped records can leave valid-looking zero or subtotal counters in a
faulted reader report. Conservatively withhold all four newly projected input
counts on any content-reader fault, while preserving the initial observer state,
existing partial qualifier, identity/join fields and original verdicts.

No new capture, raw-HID API, receipt/journal grammar, schema, history rewrite or
backfill, detector threshold, ranking, input blocking, native pin/tag or QC Build.
The existing genuine-keyboard manual check remains pending in lextest.md.

## Verified source

- Original product plus new controls: 9 snapshot, 5 signed-storage and 34 admin
  failures, after untouched baseline suites passed. The independent five-frame
  identity and real receipt signatures act in the storage controls.
- Two independent reviewers found malformed-record availability and overbroad
  partial-warning gaps. Additional raw malformed zero/subtotal/shape/time cases
  fail eight assertions before correction; signed persistence fails twice.
- Corrected Windows: 12 snapshot tests; zero failures in receipt storage/lifecycle
  and authenticated API/executed DOM programs; receipt268, HID307, recording949
  checks and the existing sweep/diagnostic programs pass.
- Required read-only corpus: 561 REC and179 VIEW, each acquired once for both
  baseline and subject. All740 per-file reports identical;351 pre-existing faults
  (346 REC /5 VIEW), zero increase. No evidence/player files changed.
- Node executes the actual extracted receipt renderer in a minimal DOM fixture;
  this is not browser or human acceptance. Storage, API and DOM use separate
  fixtures; no single persisted snapshot is claimed to traverse all three.
- An initial 120-second recording-test timeout is retained, not called a pass;
  the longer completed invocation reports949 checks, zero failures.

## Delivery status

Source/platform verification and installed delivery are distinct. Final receipts
are recorded below when completed. The actual backend is an immutable admitted
system-service generation with source-bound reader/namespace pins. A fresh guarded
candidate and privileged system-service namespace installation are required; do
not copy these files over the admitted runtime, bypass the fence or restore data.

Read-only preflight on8November2026 confirms the SSH account has no noninteractive
privilege and the system drop-in is not writable. This blocks actual backend
activation, not source work or isolated ARM qualification. No live maintenance
gate, process, reader, database, stored observation or lobby has been modified.
