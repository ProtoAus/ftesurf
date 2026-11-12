# P1525 — native quoted-byte numeric values

## Problem and correction

Native `Q_atof` reads a quoted character as one `char` byte. The reader used a
Unicode codepoint. These are not interchangeable, and the journal does not
identify native char signedness or the original byte-encoding profile. A valid
native numeric setting could therefore produce a false angle-identity finding.

The reader now refuses unavailable non-ASCII quoted numeric coefficients. Its
existing preflight withholds the whole identity, including after a late change;
it does not publish partial healthy comparisons or angle/count accusations.
Known nonzero flip/filter/acceleration paths remain known, as do ASCII literals,
hexadecimal and numeric-prefix values. No native code, capture/codec/version,
wire, cutoff, ranking/policy, historical regrading, engine pin/tag or Build change.

## Acting evidence

- Literal current native `Q_atof`/`Q_atoi`: seven rows under each char mode on
  Windows, zero compiler warnings. This establishes byte/Unicode disagreement
  and the independent known-nonzero boolean control, not an actual ARM run.
- Seven native-consistent journals, including a late setting change: untouched
  reader fails 28 of the 46 added checks; corrected reader passes all 46. Actual
  20-record consumption, whole unavailable partitions, finite counts joins,
  known finite settings and real finite contradictions are asserted.
- Windows: HID **924/0**, receipts **667/0**, recording reader **949/0**. Cached
  signed digest, no second open, content/signature separation and unavailable
  totals propagate through the real receipt consumer.
- Current corpus: **134 HID, 3 faulty**, identical baseline/subject fault lists;
  **568 REC with automatic paired VIEW, 356 faulty**, no increase. These are
  unchanged known faults, NOT a clean corpus. All 751 current paired input hashes
  remain stable during the sweep. Two prior staged HIDs were absent and two
  REC/VIEW inputs differed from the earlier task snapshot; absence is not a pass,
  no stale hash was redated and no shared data was restored or relabelled.
- Supported `src/build.ps1 -NoDeploy -Jobs 8`: all three VMs, zero warnings and
  exit 0, using direct PowerShell argv. Native code/pins and QC Build 89 held.

Initial local failures are retained privately: compiler environment, inline
reservation quoting/historical heading suffix, UTF-8 fixture encoding, mistakenly
bound baseline, an inline PowerShell wrapper failure after successful compiles,
corpus drift, Windows argv length and a missing reader import path. The corrected
routes use the existing compiler, actual frozen control, explicit UTF-8 fixtures,
normal build script and supported reader `main`; none waive a product guard.

## Limits

This is source/parser fidelity, not hardware provenance, genuine calibration,
complete cvar capture, support for an unrecorded codec, a new native/compiler/
file-writer vulnerability audit, independent review or deployment. The two prior
absent inputs were not rechecked. Required independent reviews and subsequent
normal guarded rollout remain pending; no live install/service was changed.
