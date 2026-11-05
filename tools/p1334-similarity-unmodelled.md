# P1334 - an unmodelled recording is not malformed input

## Scope

The similarity reader already abstains for recording clock models it does not
support. Those refusals previously shared the malformed-input category. A typed
`UnmodelledRec` now reaches the fixed `unmodelled recording` comparison result,
`unmodelled` stored skip category, and `recording clock model unavailable` private
review explanation. Both standalone pair and corpus diagnostics distinguish it.

The refusal remains: no new clock model, compared rows, similarity score, source
capture, player verdict, badge, threshold or enforcement is manufactured. The
common parser-refusal superclass and default parse-or-None behavior remain.
Existing limits, unreadability, short streams, true malformed input, supported
native metadata, numeric conversions and comparison math retain their contracts.
A new fixed reason in the existing skip-code column is not a new captured field.
No schema, format, native code/pin/tag, qcbuild or consent/identity policy change.

## History and current files

Old stored observations are historical. They are NOT rewritten, reclassified,
backfilled, deleted or automatically retried, even if their old reason was an
unsupported model. Ordinary authenticated reads do no comparison-file IO. This
patch does not supply durable historical-refresh scheduling or new observations
for old skipped pairs. P1333's optional current-file check remains a different
operation and cannot make an old unbound observation retroactively bound.

## Controls so far

- Unchanged baseline:14 reader cases and5 collector/review cases pass.
- The new unsupported-format falsifier fails four subcases against the old
  implementation; the actual collector/projection falsifier also fails.
- The fixed supported-native structural control compares three retained rows,
  same metrics and exact-buffer capture. Changing a real metadata seal still
  refuses as malformed. This is parser structure, not native replay acceptance.
- Seven collector/review cases pass, including unmodelled/no metrics/no capture,
  genuine malformed input, measured zero, source unreadability and no rows. An
  old malformed observation is byte-for-byte unchanged by an authenticated GET
  while the comparison loader is armed to fail if called.
- Initial native negative fixture failures are retained: the first mutation used
  absent hclose, then an assertion expected absent hseed. Inspection of the actual
  schema selected hseal; presence and changed bytes are now asserted. Product
  parsing did not change to satisfy those invalid fixtures.

## Qualification and limits

- Windows and actual Linux focused reader30/0 and collector/history7/0 pass.
- Each platform has309 counted unittest cases across34 related invocations.
  One of those invocations is a standalone custom-check program; its checks are
  not folded into that unit-case count.
  Two single-assertion failures remain: the owned-budget/probe fixtures expect
  one database close but observe two. Exact pristine prefeature94ce7bb9 whole-
  source controls reproduce BOTH on Windows and Linux. No changed budget or
  unrelated connection code was used to obtain a pass. These are not clean
  full-suite results; attribution work is recorded in BACKLOG.md.
- Windows has7 explicit platform skips; Linux has6 Node-dependent skips. The
  real POSIX FIFO/ownership controls run on Linux, not silently passed on Windows.
- Existing pwsh7 NoDeploy build compiled all3VMs with0warnings. Eleven selected
  native/progs hashes across both Windows installs stayed exact; no game swap.
- Required core reader949checks/0failed. Fresh corpus548REC178VIEW remains344/7
  faulted files:716 exact old path/byte reports reused under unchanged core reader
  and support,10 newly discovered views actually parsed with0faults. The initial
  strict sweep refused the new inputs; this failure is retained, not waived or
  called a clean scan before parsing them. No volatile or changed old reports.

Two fresh whole-feature reviews and actual guarded backend/tool delivery remain
pending at this source checkpoint. The two runtime modules belong to collectors84;
the canonical census/recsim.py helper does NOT belong to that guard's sealed origins.
It needs its own exact source/installed-hash binding, short collector coordination
and rollback. Do not claim an unsealed helper is guard-qualified, or implementation
is deployment. Historical observations and default-read behavior stay unchanged.
