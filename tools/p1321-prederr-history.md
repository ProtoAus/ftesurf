# P1321: overlapping expected-reset report context

## Problem and scope

A pending unpredicted reset was represented by one time/command/reason. Another
reset could replace that expectation before the first correction arrived.
Reporting then blamed a known requested teleport on prediction.

Retain16 requests, newest-first for matching, without widening any request's
existing time/sequence bounds. A map change clears the history. Reasons stay
associated with their own request. Context identifies the reporter revision,
server warp-op capability and request clock for future diagnosis.

This does NOT change movement, the native error counter/ring, network commands,
ranked evidence, upload consent, native pins/tag or Build number. It cannot turn
an incomplete historical upload into a complete one or prove a mover fault.

## Falsifier and verification

Synthetic example: request1 at time20/command100, request2 at20.5/130, delayed
correction110 at20.6, ping300ms and netfps66.6667. The original predicate accepts
request1 alone and rejects that correction after request2 overwrites it. The
new history accepts it under request1 and returns request1's reason, while
request2 still acts independently.

- Actual compiled QC VM, exact production helper bodies:23 checks PASS. Includes
  acting legacy negative control, unrelated/pre-request/future sequences,
  expired/future clocks, strict original bounds, zero timestamp, map clear,
  bounded count and eviction/wrap. Not a Python simulation or a live-network test.
- Required compiler is SHA256
  `c24ede65af01d6c7e20d5d1dbd2190a9295a38fb0e109843f75e52166da22f74`
  (git-7809). The known7ccb93d1 source-tree compiler's two F333 warnings are NOT
  an acceptable shipping baseline. Its preliminary outputs were rejected.
- Clean deployed-runtime baseline `dacf00d8` builds all3VM with ZERO warnings;
  CSQC SHA256 `06585861c9afaf6ae6db1ee05151814d35f9532691cf8dca2eb23ccbdd4b6b12`
  exactly matches the installed/lobby baseline.
- An initial pure-logic VM fixture could not load VBSP in its dedicated image;
  using one existing Quake1 map let the actual helper checks execute. A later
  wrong-log-path reader was corrected against the retained successful output,
  not by rerunning that completed arm. Correct-compiler requalification was a
  real dependency change and passed23/0 again. Neither infrastructure failure
  is counted as a feature pass.

## Source and delivery boundaries

Public main contains a separate TAS/native candidate. Runtime qualification uses
only this CSQC delta on the explicit deployed P1319 client cohort; do not deploy
main's whole client/menu, roll SSQC back before P1320, or replace native/assets.

Changed-program qualification: public main and the explicit runtime cohort both
build all3VM with ZERO warnings using the qualified compiler. Runtime CSQC is
`0a0cecb70a68e954ae388a7d2a76cb4a1d944cd82400c156bbd330e842027374`;
SSQC/menu are byte-identical to that runtime baseline. Main's different candidate
CSQC is NOT the runtime artifact. Committed-source proof: pending final receipt.
Windows and lobby delivery: pending. Preserve immediate `.prev` and current
SSQC/menu/native/config/data. This document is not deployment evidence.

## Limits / owner check

On a higher-latency connection, rapidly repeat a restart/stage jump and confirm
that the known corrections do not cause a report popup. Pending human check;
normal error reporting is guarded by the automated negative controls, not by
invented manual acceptance. History is bounded: excessive request spam can evict
old expectations rather than silence unknown errors. Other report causes remain
independent investigations.
