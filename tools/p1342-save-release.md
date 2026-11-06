# P1342 — short save chains and coherent hold release

## Problem / change

Only current/neighbor/first/last save rows were published, so two or three rapid
steps could not be predicted. Release then reused wop_loadvel from a previous
row. Separately, atomic cursor updates could outrun the numeric HOLDVEL stats.

Publish four more rows (+2,-2,+3,-3) through optional stat207. Its bounded D string
contains the COMPLETE original C snapshot as one quoted token plus four rows:
38outer tokens,50inner C tokens, hard1400-byte cap. New clients prefer that whole
snapshot, never a new separately arriving C plus old extra rows. Old C and numeric
stats are unchanged for older clients/servers. Extra-only row changes participate
in the serializer's signature and refresh D even when the original C is unchanged.
No new engine wire type/native build, evidence/run/save format or raw capture.
Payload is bounded to four extra rows, never a full999-save dump. The cap is
checked before publishing; oversized/malformed/missing extensions fall back without
inventing a partial row. Beyond +-3 (unless original first/last/current/neighbor
covers it), prediction remains explicitly unknown rather than guessed.

Resolve a release row through existing WarpOp_Row replay; use its coherent speed
or existing BLIND semantics if that destination/list is unknown. Preserve legacy
held-stat fallback, refused steps, queue-full/backstop and missing-ring behavior.
No threshold/quiet-period change: unknown release truthfully uses the existing
blind-operation classification; known releases remain predicted.

## Acting verification

Actual dedicated CPU-only QC VM compiles EXACT production server row selection/
serializer and client decoder/row/step/release/apply helpers with explicit synthetic
stat delivery/queue/rate stubs.43checks total:
- Window22: baseline10intended failures, subject0. Includes actual server formatter,
  legacy C50, D38/cap, both directions at2/3, wrapping/small lists, delayed D vs C,
  full-snapshot preference, malformed inner/outer data, empty/missing rows, stale
  list ack, and extra-only updates while C stays unchanged.
- Release21: baseline8intended failures, subject0. Includes full queued step/release/
  apply integration for extended2/3 chains, stale separate speed, known/unknown/
  refused/legacy/recovery/backstop/missing-ring/queue-full/free-mode controls.
Both compiler0warnings, server exit0. BOTH main/Pi-profile standard THREE-VM
NoDeploy builds0warnings.
Initial pointer-declaration and sent-cursor fixture setup failures retained; no
warning waived. Earlier smaller fixtures are retained history, not current totals.

This is source-helper/state evidence, NOT full native packet/physics or proof of
a historical report's cause. Engine stat strings support65536-byte read buffers
and existing reliable string transport; no measured bandwidth/FPS claim is made.
Reader949checks pass. Primary RUNS548/351fault-count incl views is the actual
predeployment baseline (reader exactly prework source), not a fault-free claim.
Independent reviews, native packet smoke and paired deployment remain pending.
Human acceptance in lextest.md: hold a save, step next/previous2or3times quickly
and release; compare single-step and first/last recovery. Unknown longer chains
may still arrive server-authoritatively; old-save release speed must not apply.
