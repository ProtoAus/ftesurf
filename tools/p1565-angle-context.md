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
The subsequent clean-build and delivery evidence below does not turn this
controlled component into a naturally signed finish.

## Delivered component — 15 November 2026

The compatible backend reader cohort was admitted and independently read back
at 01:19–01:23 UTC, before new native writers were enabled. The producer changes
were subsequently inherited by published P1568 native source
`cc56219a3c7e2a99128cc8ff02285d57a25e422b` (`patch-1568`), rather than installing
an older P1565 build over that newer work.

- Clean-tagged Windows client, dedicated server and all five plugins built;
  Windows and ARM each passed 1831 native selfchecks, with zero new warnings
  against their matched controls.
- Both Windows installs received the supported ship set. Independent readback
  confirmed all 22 native/VM destinations and the saved 20540-file protected
  before/after inventory. The original copy invocation failed while writing its
  receipt after copying; that failure remains failed. Product acceptance comes
  from the separate readback, not a rerun or a relabelled producer result.
- All 12 beta lobbies restarted onto the new native image at 04:38 UTC. Normal
  postflight at 04:42 UTC verified their new process/image/plugin pairs, the
  backend's actual selected native image, and recorder/resume/config preservation.
  Later independent observation confirmed all 12 running native images matched.
- Independent source review confirmed the P1565 metadata functions, builtin
  slots, callback state and wire grammar were retained. The server metadata
  callback module is also unchanged in the published Windows QC build. Existing
  Pi program bytes were preserved, not attributed to an unrelated QC build.

This establishes delivery of the P1565 component, not blanket qualification of
other P1568 features. Earlier numerical receipts remain bound to their original
images, programs and worlds; they are not renamed as P1568 runs. No new natural
opt-in recording or physical-input calibration was collected. Historical gaps
stay inconclusive; capture choice/defaults, retention, enforcement and ranking
remain unchanged. There is no release or qcbuild bump.

## Delivery order / rollback

Compatible readers must precede new writers; the dated delivery above followed
that order. Future swaps must preserve source namespaces, default-entrypoint and
current actor/dependency checks, recorder/resume data and rollback provenance.
Ordinary lobby swaps retain `.prev`, but once a new writer has been exposed an
older reader/native image is not an automatic rollback target. Use only a
verified current-data-compatible recovery. Do not overwrite a newer peer cohort
or publish another session's uncommitted work.
