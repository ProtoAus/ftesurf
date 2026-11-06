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
- Windows has7 explicit platform skips; Linux has7 Node-dependent skips. Each
  platform therefore has300 passing,2 failing and7 skipped counted unittest cases.
  The real POSIX FIFO/ownership controls run on Linux, not silently passed on Windows.
  The first aggregate incorrectly counted6 Linux skips because it inspected skips
  only in `OK` summaries; the failed budget program also skipped one Node case.
  Corrected accounting uses both `OK` and `FAILED` terminal summaries without
  rerunning tests or altering any raw result. The original aggregate is retained.
- Existing pwsh7 NoDeploy build compiled all3VMs with0warnings. Eleven selected
  native/progs hashes across both Windows installs stayed exact; no game swap.
- Required core reader949checks/0failed. Fresh corpus548REC178VIEW remains344/7
  faulted files:716 exact old path/byte reports reused under unchanged core reader
  and support,10 newly discovered views actually parsed with0faults. The initial
  strict sweep refused the new inputs; this failure is retained, not waived or
  called a clean scan before parsing them. No volatile or changed old reports.

## Delivered - 6 Nov 2026,00:19:37UTC

The first independent round found the Linux skip undercount and stale README row
literal. Those documentation/accounting errors were corrected with unchanged
product/test bytes and no reruns. Two fresh independent whole-feature re-reviews
then cleared the complete12-path change, with the explicit suite/human limits.
Reviewed feature source3012555ce627b69443234df2ea92716d76c36f7a and engine journal
81d5af9db96184187cf0093cd6b7a2d9926fc6c3 were published by exact inspected SHA.

Actual backend-only source9150481fa48de38cdfde9cc6c605a130fcb5492a is the prior
live5bf3bda3 plus ONLYadmin.py,simcheck.py and tools/census/recsim.py. Other82runtime
files/guard/dispatcher/config/external3 origins are unchanged. The two runtime
modules belong to collectors84; the canonical census/recsim.py helper does NOT
belong to that seal. It was separately installed by exact old/new byte CAS under
the existing participating-collector resource, with old-reader beforeimage kept.
Its SHA was checked through the actual backend process's namespace, configured
tools path matched, and heldmeta stayed exact. This is not helper guard attestation.

Both real CLOSED generations passed six integrity-refusal controls and authenticated
synthetic missing-pair POST200/anonymous401/CSRF400/cross-origin403; the exact pure
projection distinguishes primary's new label from the prior label. Separately,
actual CAS-function controls prove install/restore and foreign-byte/symlink/hardlink
refusal, including the otherwise-idempotent desired-byte case. Initial controller
fixture dependency/import failures remain recorded; no production data was used.

The first promotion was interrupted by a private operations-helper variable error
in namespace(pid,manifest,...), after starting the primary; it restored the old
reader but also blocked fallback acceptance at the same check. All admissions were
closed and MOM stopped during repair. The parameter was corrected; an initial
resume's guessed alias failed before mutation. The same inspected transaction
then resumed the EXISTING acceptance/cron/MOM/audit gates with exact source hashes,
not a fresh root, skipped gate, old database restore or regraded passing launch.
Both failed launches and original logs remain retained. This is not claimed as an
uninterrupted or single-pass rollout. Lobbies/native engines/VMs were not swapped.

Accepted00:19:37UTC; read-only audit00:19:38 checked156 sealed origins, actual five
ROpins/two ROruntimes/RWdata, all44 table schemas/nonchurn counts/eight identity
hashes and unchanged environment bytes. Core26/event1 held. PrimaryOPEN, old and
fallbackCLOSED; four cron routes/MOM requester active. Backup preceded the live
gate, was retained as historical, and was NEVER restored. Same-current-data code
rollback must be coupled with the retained old reader under the same exact resource.
Collector resource was released and its persistent zero-byte single-link sidecar
was acquired/released again without unlinking. No installer reservation remains.

Live anonymous source POST401/public health200ok/directory200twelve pass. One old
pair actually re-read by the installed reader now returns unmodelled/no metrics;
its stored observation stayed unchanged. It remains a current-file diagnostic,
NOT a durable historical rewrite/backfill, model implementation or new guilt score.
P1333 owner readability is still pending; no production owner session was forged.
Required production/fallback/namespace/history roots and exact helper rollback
bytes are retained. The overall anti-cheat plan is not completed by this patch.
