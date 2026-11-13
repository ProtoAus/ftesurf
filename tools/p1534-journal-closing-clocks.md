# P1534 — closing clocks must cover their recorded prefix

Implemented/source-qualified, not independently reviewed or deployed. This is
measurement integrity, not physical input authenticity or detector calibration.

## Closing chronology and measured availability

A marked partial journal could close at a time earlier than its recorded prefix
and still be accepted. A full-file finite absolute/end-delta mismatch already
faulted, but the unsupported duration remained a measurement. The cap's absolute
time was not checked against its recorded relative delta; the special cap parser
also bypassed ordinary post-close checks and accepted another cap marker.

Use the existing TIME_EPS print budget, not a new detector threshold. A finite cap
timestamp must agree with the recorded relative prefix; a whole closing time
must not precede it. Omit unsupported cap/duration values, not zero or a subtotal.
Keep cap existence separate from its timestamp: a malformed time does not turn a
known partial capture into a complete one. Preserve independently finite prefix
rates/angle/raw comparisons and valid whole counters ahead of a capped prefix.
Reject a second cap marker or one after end, retaining supported prefix facts.
Existing nonfinite/unusable-clock behavior is unchanged.

No new native/writer/capture/recording field, rank, badge, signature, threshold or
QC Build; no deferred native/compiler/filewriter audit resumed. Primitive native
timestamp formatting is only a consistency contract, not trusted physical truth.

## Acting verification

- Same final fixture on parent P1533: **1285 assertions,15 failures**. Subject:
  **1285 assertions, zero failures**, with **41 new checks**.
- Actual ordinary CLI formerly accepted the backwards-close fixture, now exits1.
  The same valid control remains0. Recorded prefix/whole values are not invented.
- Finite full and partial time contradictions omit unsupported duration while
  finite captured-prefix rates and19angle/count joins still ACT. Bad cap times
  lose only that timestamp; cap existence, ahead counter2 and independent whole
  duration/prefix comparisons remain. Reject duplicate/post-end cap markers.
- Valid zero origin remains measured0, not unknown. Existing print budget1us
  controls, exact/full controls, equal/ahead partial closes and native counter/
  backend sentinel controls all survive. No new exact2us binary-rounding claim.
- **949REC checks/800receipt checks/32structured diagnostics**, all zero failures.
- Supported normal isolated **NoDeploy three VMs, zero warnings**. Native code
  unchanged: existing native qualification reused, not claimed as new proof.
- **134journal hashes and all fault/info/note reports identical** (3oldfaulty).
  This mixed capture/fixture cohort is not physical/genuine-device labels.
- **568REC183VIEW**, all751 input hashes/per-file reports identical,356existing
  faults unchanged. No historical record or stored receipt/snapshot regraded.

## Retained failed premises and delivery limits

The initial zero-clock fixture accidentally replaced frame sequence field3, not
absolute-time field2; original14failures retained. Read existing Journal.frame,
corrected fixture before product edit; zero control retained and passing in the
final parent run. The matched15-failure run also includes the single-marker/
before-end controls. A targeted edit's stale old note text was refused atomically;
source reread and exact edit corrected, not a failed build or evidence rewrite.
A duplicate freeze preflight refused already-protected P1533 snapshot names before
mutation; exact original snapshots were checked against published Git blobs.

Independent verifier review still required before deployment. No self-clear,
old report reuse, silent external provider or live swap. Native code/pins/tag and
Build89 held. Original genuine-data, world/HFR, trust/privacy/policy and postponed
physical-test gates remain. This patch cannot establish completed anti-cheat.
