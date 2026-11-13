# P1516 — do not infer identity constants from clipped journal text

## Problem

The legacy writer can map different effective cvars to identical captured text.
At the real64-byte header and128-byte change buffers, a whole zero value and a
long zero prefix ending in1 can have the same observed token, while literal
native `Q_atoi`/`Q_atof` return different effective values. Quoting fixes cannot
reconstruct the suffix. Both false angle accusations and unsupported journal-OK
results were possible.

## Bounded change

The reader retains each token's encoded span internally. At the legacy boundary,
an unfinished numeric prefix is unavailable, not an inferred constant. This
covers header `leftisright` and changes to sensitivity, yaw/pitch scales, filter,
acceleration and `leftisright`. Other header scales already have typed effective
scalar fields; a clipped redundant text table does not invalidate those scalars.

An ambiguous capture produces an explicit data-quality fault and unknown constant
until a valid replacement. It cannot cause a stale-sign/scale angle accusation
or become journal OK. An observed terminator or character that already determines
the native effective value keeps comparisons active. Known non-linear profiles
retain their existing exclusions; this does not invent an acceleration model.

No native producer, journal grammar/field, capture policy, calibrated threshold,
movement, receipt-signature verdict, ranking rule or Build change. HID content
status remains independent from signed receipt validity, exactly as before.

## Actual evidence

- Literal native encoder + `Q_atoi`: **20 matching rows**,64/128-byte buffers;
  literal encoder + `Q_atof`: **5 matching rows**,128-byte change buffer. Actual
  different effective values share captured tokens. Compiler exit0/zero warnings;
  float probe uses `-ffp-contract=off`. A malformed printf fixture was retained
  and fixed at the formatting seam, not worked around with another compiler.
- Corrected final fixture on exact published P1515 parent: **535 checks,92 fail**.
- Subject HID suite on Windows AND ARM Python: **535 checks,0 fail**, including
  **157 new assertions** beyond P1515. Real mouse comparisons act; valid updates
  restore the exact expected windows. Complete-prefix wrong-angle controls still
  fault. Synthetic profiles are not genuine human/native filtered movement.
- Earlier float fixture used the opposite yaw sign; its failing output is retained,
  not interpreted as a product defect. Final fixtures use native signed yaw.
- Receipt suite: **388/0**, including120 new captured-byte consumer assertions:
  real digest checked, content status FAULT rather than journal OK, no angle
  accusation from unavailable data, input totals withheld, signature state not
  invented or changed. These joins do not claim to validate a new signature.
- Recording suite: **949/0**. Existing136HID files still have3faulty/unchanged
  fault lists;568REC183VIEW have identical hashes/results, existing349/7faulty.
- Actual CLI and supported QC NoDeploy metadata build are retained separately.
  Source qualification is not independent review, deployment or field calibration.

## Remaining

This refuses insufficient legacy capture; it does not recover missing text or
make all original observations complete. Non-default console encoding remains
unrecorded/unmodelled. A future producer-side completeness/effective-value design
must preserve capture consent, signed byte identity, bounds and old evidence;
no new recorded field or historical regrading is implied here.

The installed shared reader has peer changes and was not overwritten. Native
commit/tag pins and QC Build remain unchanged. Independent final-source reviews
and normal guarded deployment remain pending, separately from source publication
and continued work on other actual anti-cheat backlog items.
