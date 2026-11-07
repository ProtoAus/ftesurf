# P1357: empty CSQC grid-call overhead

## Scope

Native client-only broadphase optimization. The exact CSQC world checks each
live cell's forward-list sentinel before calling the unchanged collision
routine. Empty calls have no state effects; all occupied cells/entities retain
original x-major/y-minor/insertion order. Sequence increment, jumbo-first,
portal/network handling, collision filters and every trace result remain on
their original paths. No occupancy/visibility cache, reduced ray budget, quality
setting, header/ABI, movement formula, evidence or QC Build change.

`csqc_emptygrid` defaults1;0 is the nonarchived diagnostic/control fallback.
Dedicated-server code retains the original traversal.

Engine source: `00b5400e478093741b23b788b0a077f7a45b8904`, tag `patch-1357`.
Paired QC baseline: published `e189de0a`, with this patch's metadata/notes only.
The earlier five-map baseline in `map-lows-water-diagnosis.md` stays unchanged.
Do not subtract new numbers from that P1351 source and call it a matched gain.

## Verified prototype and source controls

- Native selected-query probe on published engine55f024c4f: about81% of collision
  time was the client broadphase,17% world BSP and1% result publication.
- Two all-edict emptiness/relevance proof candidates were rejected: neither had
  a positive selected-query skip witness. Do not count those source tests as a
  delivered optimization.
- Actual C traversal/insertion/unlink extraction passes, with8 runtime-killed
  mutants. Tests preserve occupied-cell/raw-node order, disabled/other-world
  behavior, sequence, shared cells, first/final heads, native upper-boundary
  jumbo behavior, portal/jumbo/link/unlink transitions and exact forward
  sentinel behavior. Adapter results are not a claim of runtime trace_t tests.
- Independent review confirms the native callee has only local declarations
  before its forward-node loop, so an empty call has no trace/state/callback or
  synchronization effect. Occupied processing remains unchanged.
- Instrumented prototype: same native exe, normal64 rays, unchanged scale2,
  moving replay4729 from0.25s,12s warmed ABBA0/1/1/0; profiling OFF during FPS
  windows. Original394/395avg,249/258 1% low; candidate433/433avg,284/286 1% low.
  Separate100fps diagnostic witness skipped54,319,301/60,271,690 cell calls.
  .1% tails of these short windows are small-sample diagnostics, not guarantees.
- Boreas/Garden scoped mean timings were largely neutral. Demise/Ceaseless had
  zero selected tracelines: their strict acting-witness controllers refuse;
  retained moving/FPS windows are non-target/noise controls, NOT acting passes.
- Initial native RAM admission refusals were preserved; the owner freed RAM.
  Reader-only staging/path fixes reused the successful native evidence rather
  than repeat it. Qualification does not lower the4096MiB/60quiet-second gate.

## Clean committed source qualification

Built the exact committed/tagged engine above through the existing
`src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <clean engine>` entrypoint.
All three VMs compile with zero warnings. Native control and subject each have
74 existing compiler warnings, with identical normalized filename/message
multisets: zero new signatures or increased counts. Actual-C controls and all
8 runtime-killed mutants pass against the clean product source.

The isolated delivery tree contains only this guard, registration, extracted-C
test and patch documentation. Temporary native trace/frame/substage probes and
unselected shader sample-reuse candidates are excluded. Engine commit and tag
were pushed7Nov2026UTC. Full-build native client SHA256:
`61565f9ac3f89088e3269c3735ccc0295ddd89fdd449900b5b0313263b9a18ff`.

### Matched five-map comparisons

Same clean native executable, `csqc_emptygrid`0/1/1/0 ABBA, normal64 rays,
1920x1200 window, unchanged render scale2, unlimited frame cap. Each map's route
was warmed once at100fps before comparisons; each arm seeks to0.25s, settles5s,
then plays at1x. Profiling/spike logging and in-window file logging are OFF.
The ordinary budget collector is identical in both arms. Runtime VMs are the
frozen published `b8b0cda6599aeedbb5c8eb6ab6926661954b0856` pair, NOT a claim
that the latest independently advanced installed programs were benchmarked.
Two off and two on windows per map, with positive replay-motion and native
control/version witnesses. Columns give the two-window ranges, not confidence
intervals; lows are reciprocal mean times of the slowest1%/0.1% frames.

| Map / retained seconds per arm | Average off -> on | 1% low off -> on | 0.1% low off -> on |
| --- | --- | --- | --- |
| Tensor2 /60 |383-384 ->410 |255 ->273-276 |166-167 ->179-181 |
| Boreas /38 |488-499 ->490-494 |243-251 ->252 |206-215 ->213-219 |
| Demise /35.5 |383-391 ->385-387 |229-234 ->233-234 |185-191 ->203-205 |
| Garden /85.5 |516-532 ->522-528 |258-268 ->265-267 |208-216 ->214-217 |
| Ceaseless /40.5 |747-748 ->748 |410-421 ->425-440 |264-275 ->309-341 |

Tensor2 reproduces about7% average and8% 1%-low improvement in these longer
windows. Other maps have no consistent attributable gain: early/late drift is
visible, and Demise/Ceaseless lack the selected query workload. Do not attribute
their tail fluctuations to this optimization. Tensor2 retains only60s of its
much longer replay, not whole-map coverage. The0.1% estimates use only about
14-46 frames per window across the maps and remain sensitive to outliers.
These warmed runs do not measure loading or first-traversal hitch removal.
Saved source-bound summaries and untouched native captures are retained under
the owned lowsfix task root; the historical five-map report remains unchanged.

## Delivery boundary

Actual dual-Windows activation/hash/rollback verification is PENDING at this
source checkpoint. Promotion must retain actual installed VMs, configs, aliases
and player data unchanged; do not ship the older timing-control programs or the
newly compiled latest-main programs merely to deliver a client-native change.
The guard is compiled out of dedicated-server behavior; no NanoPi lobby restart,
backend change, release or QC Build bump is required for this client-only fix.

No first-use or GPU improvement is claimed here. Ceaseless's separate249ms
frame was245.682ms in VBSP PrepareFrame and is still being localized.
