# P1507: stable sprite draw lists (0.1%-low continuation)

## Scope and source

Continuation of `tools/lows-handoff-20261112.md`. QC base `f4a0a1a5`, subsequently
fast-forwarded to `3f3d8671` (two documentation changes only). Native measurement
control is the installed P1505 client, `git-8692-patch-1505-0-g08c5cc387`,
SHA256 `5be7f2fa7f6bc258a1eab409342fce40e460c802a35375db0ae605f373fe8c348`;
HL2 plugin `70b9810f`. This is QC-only: no native code, pin/tag, mover, evidence
format, sort-certificate or QCBuild change.

## Problem / change

`Sprite_Draw` scanned all N sprite slots once per material, then all N again for
light glows. Its material mismatch `|| spr_hide[i]` is eager in QC. Fairy has
460 slots, 38 beams, two materials and 107 light glows: 1,380 slot visits per
frame before geometry/culling, of which only 460 can belong to their pass.

Build stable, ascending-slot index chains per material plus a separate glow
chain. Rebuild lazily after every successful ordinary/glow add and map-table
reload, including template-slot reuse with an unchanged high-water count. Keep
indices, material-major order, glow order, visibility/fade scheduling, pulse
phases and geometry unchanged. Allocate even on an FX-only cold first frame;
use separate pointer declarations because QC does not use C's combined-pointer
declarator semantics. Snapshot the live orientation mode once per frame.

## Verification

- `src/build.ps1 -Jobs 8 -NoDeploy -PassThru`: all three QC programs, zero warnings.
- `tools/test_sprite_drawlists.py`: **12,824 checks, zero failures**, exact
  production helper compiled and run in a dedicated-server QC VM. Controls cover
  empty/full tables, one/all materials, glows, mixed membership, same-count slot
  reuse/material-to-glow changes, shrink, empty reload and append. Source guards
  tie invalidation and both render traversals to the tested helper. This is
  synthetic ordering/lifetime evidence, not a pixel or performance test.
- Independent review found a combined-pointer declaration mistake before the
  first build; fixed. Final correctness re-check: no blockers.
- Old/new screenshots at replay time 15.000 show no obvious visual difference.
  Not pixel-identical acceptance or owner confirmation: moving effects and the
  frametime overlay differ. Owner visual check remains pending in `lextest.md`.

Native helper invocation (caller supplies a NEW output under its owned root):

```
python -B tools/test_sprite_drawlists.py --out <owned-root>/artifacts/drawlist-unit --compiler C:/FTESurf/src/fteqcc64.exe --server C:/FTEQuake/fteqwsv64.exe --pak C:/FTEQuake/id1/pak0.pak
```

## Measured warm A/B, not a fleet benchmark

Own task root: `C:/FTESurf-worktrees/lows3-20261111-sol01a1cae9`.
Raw evidence: `artifacts/surf_fairy-drawlists-ab/` (all eight dumps, four complete
logs, input hashes, old/new screenshots). Script: `artifacts/ab_sprites.py`.
Full public main replay 33811, 42.735 seconds; 1920x1200, full effects,
MSAA4/reflections2, uncapped, same P1505 executable/plugin. No other FTE game
or build ran in the shared quiet-rig interval. Each fresh session warmed the
whole replay, then measured two complete passes. Order: old, new, new, old.
`r_budget_csqc` and VM profiling were off; normal r_budget/frametime collection
remained enabled in both arms. Live `replay status` proved the correct map,
seek-to-zero state and clock advancement for every measured pass.

| Arm | Avg FPS, passes 1/2 | 1% FPS | 0.1% FPS | 0.1% tail mean ms |
|---|---:|---:|---:|---:|
| old 0 | 307 / 305 | 131 / 137 | 90 / 111 | 11.14 / 8.99 |
| new 1 | 307 / 311 | 141 / 144 | 96 / 116 | 10.40 / 8.60 |
| new 2 | 304 / 304 | 128 / 144 | 86 / 124 | 11.56 / 8.09 |
| old 3 | 273 / 250 | 121 / 113 | 82 / 93 | 12.17 / 10.80 |

All four nearest paired 0.1% comparisons favor the candidate. The first pair's
warm second pass is 111 -> 116 FPS (+4.5%); its first pass is 90 -> 96 (+6.7%).
**Do not claim a stable pooled percentage:** the final control slowed broadly
(average 305 -> 250 FPS across old sessions), so the reverse pair's larger
apparent gain is confounded by run-to-run drift. Current-frame CSQC budget in
the first pair's second dump was 1.27 -> 1.21 ms; that is not a replay average.
This supports a small bounded improvement, not resolution of fairy's remaining
transparent-sort/draw cost, nor a promised gain on every map/machine.

## Other leads and failed evidence

- First kitsune diagnostic accidentally used global replay 4188 (surf_ruse),
  not kitsune_css's cached main 25800. Both supposed measured passes were static
  spawn. Retained `artifacts/surf_kitsune_css-diag.txt` is INVALID replay evidence.
- A corrected-ID startup reached the right map/time0 but its acceptance parser
  incorrectly read conbridge's marker-only send response. Retained log
  `bridge_lows3_20261112T013638_cl.log`; no timing pass accepted. Fixed the reusable
  seam to read actual client-log status after the marker barrier. Actual status
  plus wrong-map/inactive/non-advancing refusal controls passed; the fairy A/B
  then exercised that gate eight times. Kitsune attribution is still pending.
- Native read-only review found a possible monotonic plane-side early exit in
  `GLBE_BlendPlaneSide`. Not implemented or measured by P1507. Preserve logical
  sort-work accounting if pursued. No safe immediate pantheon/bossfight change
  established; do not disable effects, alter transparency or broaden P1490 reuse.
- The last three survey-5 maps were still absent when checked after this A/B;
  their retained session queue is not treated as completed.

## Delivery

Source/build verified; commit/push and both-install/lobby deployment pending at
this document's first commit. Append actual UTC/hash/live verification after
execution, never infer it from this benchmark or a successful build.
