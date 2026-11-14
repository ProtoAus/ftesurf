# P1565 — optional server angle-operation context

## Contract

This adds future context, not an explanation retrofitted onto old recordings.
Movement, capture defaults/choice, retention, ranking, enforcement and thresholds
are unchanged. The context identifies software operations; it is not physical
input or personal/hardware attestation.

The first supported subset is ordinary seat-zero QW ABS on a fresh live unfrozen
recorder. REC14 advertises `anglecause1`; opt-in HID advertises `anglecause 1`.
A server `angleop` carries the actual run nonce, operation ID, opaque basis and
canonical encoded wire bytes. Native client observations carry their actual
application disposition and pre/post float bits. Sparse `anglebaseline` and
`angleend` delimit the measured input interval; ordinal zero does not license a
neighboring interval. Unsupported prediction, consumed or interleaved operations
remain inconclusive. Existing versions/files are not upgraded or rewritten.

Authority is an exact nonce/operation/basis/format/bytes match, never a target or
nearest-time lookup. The signed client receipt does not authenticate server
custody. Receipt processing must first satisfy the existing signature, immutable
file observations, digests, recording grammar and nonce joins. Only then may the
model substitute the proven starting pose; the rest of the input still has to
match. Malformed or ambiguous observations never supply usable operations or
invent a zero count. Later duplicate declarations cannot downgrade an unsupported
version into a supported one. Missing/pruned/mismatched context stays BLIND.

The normal delayed-HID path obtains only an optional isolated REC observation
when a supported nontrivial unresolved operation needs it. A fresh/full read
reuses already captured REC bytes, including when no VIEW/tick analysis produced
a recording report. Only journal result/detail/metrics transfer back; previous
receipt faults, signer identity, pub comparisons and unavailable ticks do not.
Legacy, no-feature and no-op cases retain their existing fast paths.

Native callback state uses GC-visible reserved-register snapshots, appended ABI5
interfaces and a complete native/plugin rebuild. `build.ps1 -Full` also removes
precompiled headers. qcbuild89 is unchanged; this is not a release.

## Qualification so far

- Three QC VMs: zero warnings.
- Full Windows native client, dedicated server and five plugins: successful;
  pre-existing unrelated compiler warnings are retained, not repaired here.
- Strict codec execution and actual native consumer compilation pass.
- Seventeen new reader test methods include three ABS widths, genuinely
  authority-dependent positives, removed/wrong authority, remaining bad input,
  declaration ambiguity and canonical physical-line controls.
- Existing signed receipt/scheduler fixtures exercise delayed arrival,
  full/fresh captured-byte reuse, unavailable/wrong REC, old FAULT retention,
  pub-change deferral and no-op/legacy fast paths. Scoped independent reviews
  clear native repairs, reader admission and caller integration.
- Actual bounded VM collector controls exercise reserved words, string contents,
  argc, callback reuse/refusal/flush and real allocator relocation with packed
  and Windows mirror collection. Independent review accepts that dependency
  proof only; it does not imply release optimization or live-recorder coverage.
- The existing run corpus retains identical output/faults, and an existing
  journal retains identical measured information. No historical regrading.

The real dedicated-socket/headless component also passes with current product QC:
a complete actual REC has zero strict-reader faults and one canonical operation.
Its actual native DIRECT application closes onto an existing sparse HID view row.
Checked source authority accounts one operation/frame with no unresolved source
frame; removing authority or changing only its exact lookup key leaves that
same frame unbound. The first actor staged an old DAT with the already-corrected
oversized formatter; its malformed bytes remain failed history, not a current
source defect or a pass. Rebuilt current QC matches the successful Full inputs.

This is a manual-journal, virtual-input, practice component, not automatic CSQC,
a naturally signed finish/receipt or hardware attestation. The normal signed
caller and unchanged human-observed lifecycle remain separately qualified.
Clean-commit qualification and deployment remain pending.

## Delivery order / rollback

Not deployed yet. Qualify and promote the backend reader/native generation
before enabling new writers: an old strict native reader cannot understand the
new typed rows. Preserve immutable source namespace and default-entrypoint
checks, current actor/dependency observations, recorder/resume data and rollback.
Only then deploy the inspected clean cohort to both Windows installs and the
beta lobbies, checking destination hashes and live behaviour. Ordinary lobby
swaps retain `.prev`; record actual UTC provenance rather than implying delivery
from a successful build. Do not publish another session's uncommitted work.
