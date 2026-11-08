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

Source/platform verification and installed delivery are distinct. Product source
is published as QC8e4978c4; the engine's documentation-only entry is81695faef.
Both independent re-reviews are CLEAR after correcting their findings.

The actual backend is an immutable admitted
system-service generation with source-bound reader/namespace pins. A fresh guarded
candidate and privileged system-service namespace installation are required; do
not copy these files over the admitted runtime, bypass the fence or restore data.

Read-only preflight on8November2026 confirms the SSH account has no noninteractive
privilege and the system drop-in is not writable. This blocks actual backend
activation, not source work or isolated ARM qualification. No live maintenance
gate, process, backend reader, database, stored observation or lobby has been modified.

### ARM qualification and Windows reader delivery — 8 November 2026

- Isolated ARM Python3.11.2 qualification completed17:12:10UTC using an archive
  of the clean published source (SHA256b9e9085f06e1b8b828453573b3a7be62f11a15431c492550a4c9f2120fd67489).
  Snapshot12 tests, signed storage/lifecycle and authenticated API, receipt268 and
  HID307 checks pass. Node is absent on ARM: its DOM check explicitly SKIPS;
  the actual renderer execution passed on Windows, not ARM or a live browser.
- At17:13:00UTC both Windows installs' four reader modules match exact inspected
  commit blobs; the second install retains three replaced-file rollback copies
  with suffix.pre-p1434-8e4978c4. The already exact crypto module was unchanged.
  Each installed reader cohort then passed all12 snapshot controls, including
  signed-byte/digest, malformed-record, measured-zero, unavailable and partial
  cases. This qualifies installed local readers, not native keyboard hardware.
- No engine executable, plugin, progs, owner config, game process or player data
  changed. No historical record is reinterpreted automatically or old row backfilled.
- The authenticated web feature is NOT deployed. It remains blocked on privileged
  source-bound backend-generation/reader namespace installation. The old primary
  remains active; no gate was acquired or left closed and no restart attempted.
