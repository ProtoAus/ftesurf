# P1507: stable sprite draw lists (0.1%-low continuation)

## Scope and source

Continuation of `tools/lows-handoff-20261112.md`. QC base `f4a0a1a5`, subsequently
fast-forwarded to `3f3d8671` (two documentation changes only). Native measurement
control is the installed P1505 client, `git-8692-patch-1505-0-g08c5cc387`,
SHA256 `5be0c6a5e571f30258a44f523465c49b103623740cd268f63ed0b48e0effcf1d`;
HL2 plugin SHA256 `d21e12b22a9afd9d0cab48cf242d54fec14892ec9ad8a00773406456c86ff448`.
These are the retained A/B input hashes; the first report revision transcribed
the native/plugin identifiers incorrectly. The raw inputs and measurements did
not change. This is QC-only: no native code, pin/tag, mover, evidence
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
  then exercised that gate eight times. Subsequent correctly mapped Kitsune
  diagnostics exercised it again, with two passes advancing to about 35.6s.
  The sampled large frames did not reproduce the earlier large game-code spike;
  presentation/profiling-overlay costs dominated the largest samples. This is
  attribution only, not FPS evidence or a causal fix. Coverage stops before the
  end of the historical survey's 1.5..36.5s window; the remaining interval and the
  rest of the 151s replay are not cleared.
  A12Nov read-only full-tail preflight bound the correct25800cache:10,347samples,
  -3.840..151.351s (filename151.365is not the last sample). Existing diagnostic
  feature strings and historical named-builtin output were bound, not newly
  executed. The retained frame-specific output calls `r_frametime_dump`, which
  unconditionally writes the global clipboard; no console-only argument exists.
  No coordinated clipboard interval was available within the no-overwrite scope,
  so no five-minute arm was launched and no replacement harness/build invented.
  **New coverage: none; tail remains untested**, not a fixed/absent QC spike or
  GPU conclusion. An exact owner stall location or coordinated attribution is
  needed before another safe code change is justified.
- Native read-only review found a possible monotonic plane-side early exit in
  `GLBE_BlendPlaneSide`. Not implemented or measured by P1507. Subsequent P1511
  implements it with unchanged logical sort-work accounting and qualified
  dual-client delivery; see tools/p1511-plane-side.md. Its native FPS benefit
  remains unmeasured, separate from this sprite result. No safe immediate
  pantheon/bossfight change established; do not disable effects, alter
  transparency or broaden P1490 reuse.

## Survey-5 follow-up

The three queued maps were actually measured, then a validated alternate cached
Utopia replay filled one older missing result. The four new rows use the P1505
native/plugin identifiers above and CSQC `44b32b4e`; actual map/clock/reset/advance
reader gates passed. First/second pass are the retained survey passes, not A/B.

| Map | Replay | First-pass 0.1% FPS | Second-pass 0.1% FPS |
|---|---:|---:|---:|
| surf_whiteout | 39189 | 254 | 265 |
| surf_zae | 39233 | 406 | 387 |
| surf_zoomathon | 24797 | 352 | 274 |
| surf_utopia | 6 | 294 | 462 |

`tools/lows-survey5-followup-20261112.tsv` preserves the original 57 rows, adds
the three continuation rows and the alternate Utopia row: 61 observations over
60 map names, 59 with numeric second-pass results. This is a mixed native/QC/
replay cohort for investigation, **not** a uniform current-fleet benchmark or a
controlled improvement comparison. Historical rows were not retroactively
requalified with the new reader gate. Original Utopia replay26310's missing row
is retained; replay6 is explicitly an alternate, not a replacement claim.
Dragon CSS remains unmeasured: no exact-map cached replay long enough for the
35-second active window was found; no alias or successful result was invented.

## Delivery

Source feature commit: `7a81a67a50d0d0309b5e06399d83633ae2657dc8` (published).
Windows paired-program delivery was independently read back at
**2026-11-11 15:14:57 UTC** in both `C:/FTESurf` and `C:/FTEQuake`: eight generated
targets verified, 19,586 captured protected rows unchanged, zero failures.
Installed CSQC SHA256 starts `44b32b4e`; SSQC starts `de63efd3`. The original
caller timed out during postflight; its failure was retained and the healthy
swap was **not** repeated. This was a separate read-only acceptance.

Installed/hashed is not owner visual acceptance: that check remains pending.

Pi paired-program activation completed at **2026-11-11 23:01:57 UTC** after the
standard chat warning and actual 10-second countdown. Both qualified progs and
`.prev` hashes verified; all12lobbies restarted, zero skips. All58,462captured
protected files remained exact, with zero new files at postflight. Complete
onbox and independently rehashed offbox progs/recorder/resume preimages preceded
canonical staging. The fresh capture bound the actually changed P1508 native
actors/backend launcher rather than reusing old PIDs or redating old evidence.
The earlier never-activated capture and its qualified rollback archives remain.

Separate read-only full payload/metadata postflight at **23:02:42 UTC** verified
all9original part files and207resume files unchanged, all12new actor epochs,
strict13declared actor FD closure, and native/plugin/menu/config/backend
preservation. This is the explicitly scoped recorder/resume actor check, not a
general system file-writer audit. No backend generation or native binary swap.
Real cold-client acceptance subsequently passed on the deployed endpoint. Only
owned local CS/matching cache files were parked and exactly restored. The client
actually downloaded `csprogsvers/dfb59cb7.dat`, **5,317,642 bytes**, SHA25644b32...
(the complete frozen hash above), then logged CSQC loaded and positive execution
of `CSQC_WorldLoaded`, `CSQC_Ent_Update`, `CSQC_Input_Frame` and `CSQC_UpdateView`.
This is wire/VM evidence, not merely server advertisement or process start. The
spectator-intent client sent no movement/start/warp/RCON commands and disconnected;
its session is not independently claimed to cause zero remote metadata writes.
Owned fixture/cache restoration was byte-verified. Numerical FPS and owner visual
acceptance are not inferred from this functional tandem check. No release or
QCBuild bump.
