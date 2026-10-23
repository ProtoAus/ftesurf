# P954 — per-player practice slow motion

Status: R3 source corrections in progress; clean native/VM build, three-lens
re-review and deployment pending. Prior local measurements below are r1/r2 only. This is ordinary development work, not a release or Build-number bump.

## Behaviour and boundaries

While connected, `host_timescale` queries the server-owned value. Set
`host_timescale 0.5` for half speed, or choose 0.1..1. Movement and the counted
run timer share scaled outgoing command duration; native physics ticks, world
and audio clocks, and other players are not slowed. Restoring1 does not clear
practice eligibility for this map connection. New map/reconnect returns to1 and
clears old client commands; queued slow inputs cannot enter a newly clean run.

Slow practice uses existing `cl_nopred 1` (server-authoritative movement), since
native partial prediction can run even at extrapolate0 with low netfps or gaps.
A bare slow request selects it before forwarding; runtime keeps it while slow.
Restore the exact previous cvar STRING after the last observed slow local seat
returns to1, removed seats are reconciled, or VM shutdown, only while still owned.
Unobserved pending/refused requests retain it until observed or shutdown. Direct
low-level `cmd` users must also select this mode. Local-seat requests/queries
preserve their `pN` owner and fractional carry.

No new native input API/producer/counter, stored clock/evidence field, schema,
grammar, detector/tolerance or collection change. Native pin/tag move to P954:
legacy replay event order now uses existing packet ordinals rather than visual
sample presence, and paired restarts inherit their relocation's phase. Slow visual/body
samples are spaced by at least one physics tick of truthful simulated time;
full input/frozen-input/event rows remain intact. Restored prefix spacing is
conservatively re-anchored without adding saved-state columns.

## Prior r1/r2 local verification (R3 requires fresh acceptance)

- Three production VMs build with zero warnings. QC LSP records no diagnostics;
  that is not a QC compiler claim.
- Real dedicated socket, unchanged native P952 images, known bhop_eazy BSP and
  owned thin fixture: normal versus0.5 counted-time ratio0.506 and moving-body
  ratio0.517; fixed15ms tick. At0.1, 30/300 frame caps each count22 ticks over
  3.235 wall seconds (factor0.102); nonzero movement and whole-hull start exit.
- Separate real player remains scalar1, untainted and moving/counting normally.
  Invalid ranges/NaN/argument count preserve authority; immediate taint, armed
  latch and restoring1 during an active run pass. Class0/watch1 running clean
  control versus slow practice, formerly clean save load and restore pass.
- Review found a real writer defect: completed original normal66.465 samples/s
  faults0 versus half-speed133.234/s faults1. Revised completed1/.5/.1 captures
  yield65.449/54.859/64.417 samples/s, zero reader faults each. Reader unchanged.
- Runtime ghost0.1 clock factor0.095 (ordinary slow0.103); preference1->0->1.
  An ACTUALLY admitted second local player accepts bare p2 set/query; p1 stays1,
  p2 moves/counts at factor0.510. A split-disabled p2 merely wrapped to p1 and
  was rejected as a fixture failure, not counted as a pass.
- Existing reader suite864 checks, zero failed. Canonical corpus BEFORE baseline
  is430REC/126pairedVIEW/294faulty files: a regression baseline, NOT a clean
  corpus claim. Revised suite/sweep and destination/live provenance pending.

Earlier fixture, observer, compiler and first-review failures are retained in
private evidence, not repackaged as passes. Owner feel/visual acceptance is
pending; no numerical performance or human-acceptance claim is made.
