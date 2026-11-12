# P1526 — journal clock quality

## Problem and correction

Non-finite base/frame/end clocks and a NaN truncation marker could retain journal
content OK: NaN evades ordinary difference comparisons. Closing deltas also
bypassed the body's nonnegative rule. An unrepresentable delta could raise an
exception, while a malformed body timestamp could drop a pointer row and then
produce a false counts-join finding about that missing row.

Validate finite clocks before storing/comparing them, and validate closing clock
arithmetic before committing trailer state. Refuse unrepresentable body timing
without dropping otherwise finite payloads. A skipped pointer with an unusable
timestamp cannot support a complete counts comparison. Unusable timing metrics
stay absent, not healthy duration/rate zeroes. These are evidence-quality errors,
not angle/count/player accusations; independently usable comparisons stay separate.

The fixed clock tolerance is unchanged. No native code, recorded field, codec,
version, cutoff, ranking/policy, historical regrading, engine pin/tag or QC Build
change. This is not a redesign of clock provenance or a complete parser audit.

## Acting evidence

- A finite 20-event/20-view journal actually judges 19 angle transitions. The
  untouched reader also accepted base/frame/end NaN and a NaN truncation marker,
  plus an inconsistent negative closing delta, as content OK.
- Eighteen malformed-clock cases cover base/frame/end/truncation non-finite
  values, negative/unrepresentable closing deltas and unusable body deltas.
  Untouched P1525 executes 71 checks and fails 32, including two overflow cases;
  corrected source passes all 77 checks. Finite duration/rate, bounded rounding
  and genuine finite clock-contradiction controls still act.
- The first body-pointer probe hit the correctly seed-exempt join and did NOT
  reproduce the counts finding. That failed prediction is retained. The governed
  second-window subject then produced the actual false counts finding; the
  correction withholds the unavailable join instead of making that accusation.
- Windows suites: **1001 HID**, **800 receipt**, **949 recording-reader** checks,
  all passing. Actual captured digest/no second open, quality versus signature
  status, withheld input totals and independent finite comparisons are asserted.
- Current captured corpus: **134 HID, 3 faulty**, identical baseline/subject
  fault lists; **568 REC with paired VIEW, 356 faulty**, no increase. All 751
  current paired input hashes remain stable during the sweep. These are known
  existing faults, not a claim that the corpus is clean. Earlier P1525 snapshot
  drift remains recorded; absent prior files were not restored or marked passed.
- Supported direct `src/build.ps1 -NoDeploy -Jobs 8`: three VMs, zero warnings,
  exit 0. The later Python-only body guard does not alter compiled QC/menu inputs;
  that still-valid build evidence is reused, not redated. Native code/pins and
  QC Build 89 held.

## Limits and delivery state

Source qualification is not hardware provenance, genuine calibration, complete
clock/mapping attestation, independent review or deployment. The native/compiler/
file-writer vulnerability audit remains deferred. No live install/service, owner
process, player data, policy or maintenance gate was changed. Mandatory independent
source reviews and subsequent normal guarded rollout remain pending.
