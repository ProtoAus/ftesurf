# P954 — per-player practice slow motion

Status: implemented and locally verified; independent re-review and deployment
pending. This is ordinary development work, not a release or Build-number bump.

## Behaviour and boundaries

While connected, `host_timescale` queries the server-owned value. Set
`host_timescale 0.5` for half speed, or choose 0.1..1. Movement and the counted
run timer share scaled outgoing command duration; native physics ticks, world
and audio clocks, and other players are not slowed. Restoring1 does not clear
an active attempt's practice status. Connection/map initialization returns to1.

Slow practice uses existing `cl_predict_extrapolate 0`, not native partial mode1.
A bare slow request selects this compatibility mode before forwarding; the
runtime keeps it while slow. The previous setting is restored after the last
observed slow local seat returns to1, or VM shutdown, if still owned. An unobserved
pending/refused slow request conservatively retains the mode until observed or
shutdown. Direct low-level `cmd` users must also use this supported prediction
mode. Local-seat requests/queries preserve their `pN` owner and fractional carry.

No native API/producer/counter, stored clock/evidence field, schema, reader,
tolerance or collection change. Native pin/tag remain P953. Slow visual/body
samples are spaced by at least one physics tick of truthful simulated time;
full input/frozen-input/event rows remain intact. Restored prefix spacing is
conservatively re-anchored without adding saved-state columns.

## Local verification

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
