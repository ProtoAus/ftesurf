# P1342 — short save chains and coherent hold release

## Problem / change

Only current/neighbor/first/last save rows were published, so two or three rapid
steps could not be predicted. Release reused a previous load speed; independent
HOLDVEL stats could be older than a cursor update. Independent review then found
that even a coherent cursor is NOT proof of the held row: a failed state-file
load advances the cursor while the authoritative hold remains on the old row.

Optional stat207 contains COMPLETE quoted C50, actual-held validity/velocity,
and four extra rows (+2,-2,+3,-3):42outer tokens, hard1400-byte cap. Clients select
that WHOLE snapshot, never combine a newer C with an older D. Old C/numeric
interfaces remain. Extra-only and held-only changes participate in refresh even
when C is unchanged. Existing decimal/float32-finite codec validates EVERY numeric
outer/embedded component; wrong structure, invalid hold flag, junk/NaN/infinity/
overflow or an oversize extension rejects D, retaining legacy rows but no extras.
No truncation/partial-row guess and never a full999-save dump.

Pending non-rate-refused loads/steps use existing virtual-row replay (and can
still be corrected if the server refuses validation). Once answered, release uses
ACTUAL held speed from the same D snapshot, NOT the selected cursor. A C-only
settled hold or missing/unproven held state is BLIND; numeric-only legacy fallback
remains. Rate-refused pending ops do not retarget the hold. Queue-full/backstop,
missing-ring, unknown rows and already-free replay behavior remain.

No native engine/wire type, evidence/run/save format, authoritative load/release
semantics, threshold/quiet-period, raw capture, backend, Build or release change.
Beyond+-3 remains unknown unless an original current/neighbor/first/last covers it.

## Acting verification

Actual dedicated CPU-only QC VM, exact production helpers and explicit synthetic
stat/queue/rate/validation dependencies:
- Metadata31/0: production formatter/decoder, legacy C50, complete D42/cap,
  bidirectional2/3, wrapping/small lists, C/D ordering, extra-only AND held-only
  refresh, no-hold transition, stale list ack, malformed structure and same-shape
  junk/NaN/infinity/overflow/inner numeric/invalid flag refusal.
- Release29/0: full queued step/release/apply, known/unknown/refused/legacy/recovery,
  backstop/ring/full/free controls; production server step and release execute.
  A validation callback explicitly refuses/accepts (NOT full state-file IO):
  cursor advances while old hold persists, then acknowledged release matches
  actual server600 rather than cursor700. Accepted retarget/thaw also act.
- Relative24/0 remains byte-identical helper coverage (P1343), total84/0.

The17 added review checks expose12failures in the ORIGINAL67-check candidate:
metadata31/8 and release29/4 before correction, both0 after; compiler0warnings,
server exit0. Original43 baseline18failures and relative24 baseline7 are retained
historical controls, not added together across different baselines. Original
candidate/reviews/fixtures/failures retained; no regrading or warning waiver.

Both post-fix standard THREE-VM NoDeploy builds have0warnings. Renewed independent
review, paired deployment and native served-code/render smoke remain pending. Reader949passed; primary RUNS548/351fault
count incl paired views is the real predeployment baseline, reader exactly prework
source, NOT fault-free. Final count must not increase. This is helper/state evidence,
not full packet/collision/PVS/feel or a historical report's proven cause. No
measured bandwidth/FPS claim. Human acceptance in lextest.md: hold a save, step
next/previous2or3times quickly and release; compare single-step/first/last recovery.
Do not damage/delete real saves to manufacture a validation failure.
