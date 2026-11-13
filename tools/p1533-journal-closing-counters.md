# P1533 — closing counters must agree with the captured prefix

Implemented/source-qualified, not independently reviewed or deployed. Human test
remains postponed; no human/device/authenticity/calibration result is claimed.

## Two closing-counter gaps

A truncated journal could close with hidden0 despite a hidden event already
present in its body. The reader preserved full-file equality but skipped the
necessary truncated lower bound. Other closing fields could accept impossible
unsigned quantities, retain contradictory totals as measurements, or lose finite
clock data merely because a counter token was nonnumeric.

Reuse the producer's native unsigned32-bit domain for events/frames/drop/hidden
closing counters. Preserve the different signed-1 backend sentinels. A normal
file must agree exactly with its observed counts; a truncated prefix allows
whole totals ahead, never behind. Unsupported or contradictory totals are omitted,
not changed to zero or substituted with a prefix subtotal. Independently finite
body-prefix rates/clocks and angle/raw-count comparisons remain measurable.

No native/writer/capture/recording-field, signature, badge, ranking, detector
threshold or QC Build change. This does not authenticate the journal, establish
physical input, or treat arithmetic consistency as human admissibility.

## Acting evidence

- Final matched fixture on P1532 reader: **1244 checks,36 failures**. Corrected
  reader: **1244 checks, zero failures**, including **94 new assertions**.
- Actual ordinary `python tools/hidcheck.py --verbose <owned-fixture>` formerly
  accepts truncated hidden0/body1. It now refuses that same fixture, while the
  equal hidden1 control remains accepted. No player data was modified.
- Full and truncated invalid-negative/overflow/nonnumeric/fractional fields refuse
  without invented closing totals. Finite clocks/prefix rates and19angle/raw-join
  intervals still act. Exact, legitimate ahead and nativeMAX controls survive.
- Valid-domain contradictory event/frame/hidden/drop totals are unavailable, not
  reported as complete0/other unsupported values. Known loss remains separately
  disclosed; its domain and backend sentinels still pass P1532 controls.
- REC reader **949/0**, receipts **800/0**, structured diagnostics **32/0**.
- Supported normal isolated QC NoDeploy: **three VMs, zero warnings**. Native code
  unchanged: previous native qualification reused, not rerun/claimed as new.
- **134 retained journal hashes and every fault/info/note identical**, including
  three existing faulty files. These captures/fixtures are not genuine labels.
- **568REC183VIEW**, all751 input hashes/per-file reports identical;356existing
  faults unchanged. No stored receipt/snapshot or historical recording regraded.

## Preserved fixture correction and limits

The first fixture assumed that invalid closing counts also invalidated rates.
Source inspection shows those rates use observed body counts and first..last
frame times, not closing totals. The original37-failure run is retained, and the
fixture corrected before product edits to REQUIRE preservation of finite prefix
rates. The final matched run includes contradictory-total omission controls.
An initial ad-hoc probe treated the existing Journal.hidden method as a numeric
counter and failed before reading; using its existing method corrected that
fixture, not product code. No failed receipt was promoted or evidence redated.

Independent verifier review remains before deployment; no self-clear, old report
reuse, silent external-provider fallback or live action. Source-only ledger does
not move native code pins/tag or Build89. Postponed physical checks and other
original genuine-data/world/HFR/privacy/trust/policy acceptance gates remain. The
deferred native/compiler/filewriter audit was not resumed.
