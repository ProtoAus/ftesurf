# Patch 1557 — whole-angle diagnostic states the evidence limit

## Problem

The standalone journal checker correctly kept a whole-angle discontinuity
unresolved, but then said the recording's warp rows could tell a server angle
set from a whole-view rewrite. Those rows establish server body events; the
current formats do not uniquely bind one to a client view mutation. The same
note also implied every teleport changes angles, although some preserve them.

## Change

Correct only that diagnostic and the existing whole-angle fixture's explanation.
Four added assertions require body-event corroboration and the attribution
limit, and reject the obsolete resolution and universal-teleport claims.
All arithmetic, counters, tolerances, fault and BLIND decisions stay unchanged.
No new evidence fields, recording, consent, retention, detector or enforcement
rule. This does not retrospectively resolve any existing recording.

## Verified

- Existing whole-angle fixture ACTED: five whole-angle/unresolved observations,
  no fault, both per-axis counters retained. Against the old diagnostic only
  the four new assertions failed (8 checks/4 failures); corrected message8/0.
- Full `python tools/test_hidcheck.py`:1627 checks/0 failed.
- Required `python tools/test_reccheck.py`:949 checks/0 failed.
- Existing recording corpus swept with the supported checker entrypoint before
  and after: identical output and fault count, not a claim that old faults pass.
- An existing protected original input sample retains identical metrics and
  faults, including unresolved state. Only this one explanatory note changes;
  no original bytes, old verdict or historical metadata are rewritten.

## Delivery scope

Python diagnostic/tooling change: no VM/native build, native commit/tag or
qcbuild change. The production receipt consumer derives its journal outcome
from `info`/`faults`, not this standalone diagnostic note; no lobby or backend
runtime output/ship set changes here. Source publication and any local working
copy are distinct from a live service deployment. No release or new detection
coverage is claimed.
