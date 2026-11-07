# P1363-P1365: audit of the 1%/0.1%-low work, three fixes (7 Nov 2026)

Owner request: audit Sol's lows work (P1345-P1358, the rejected GPU endpoint shader) on
surf_garden, surf_boreas, surf_demise, bhop_ceaseless and surf_tensor2, find heavier maps,
and improve rendering speed without lowering quality; test with full water/refraction and
transparencies on. Task root `C:/FTESurf-worktrees/lows2-20261107-opus` (driver scripts,
condumps, profiles, census in `artifacts/`).

## Measurement profile

Owner's Desktop play settings plus every effect on (`fullfx.cfg` in the task root):
1920x1200 window, `r_renderscale 1`, `vid_multisample 4`, `hl2_water 2` (live reflection
and refraction), `r_capturerate 60`, `hl2_refract 1` (Source refraction with framebuffer
copy; the Desktop cfg has 0), `hl2_translucent 1`, `hl2_detail 1`, sprites, lightglows,
spotlights, lasers, glare, decals, overlays, 3D sky and cubemaps on, `vbsp_sprite_skyrays
64`, uncapped, real dedicated socket, replay views. Each run echoes these cvars back.

Sol's numbers were taken at `r_renderscale 2`, `hl2_water 0` (the dev install's cfg), not the
Desktop copy the owner plays. At scale 1 Tensor2 is CPU-bound (GPU 0.28 ms of a 2.2-2.8 ms
frame), so CPU work decides its lows; Garden/Demise GPU findings at scale 2 stand as they were.

Timed comparisons are ABBA in one binary, 20 s windows (Ceaseless 14 s through the old
hitch), after one warm pass; FPS columns are `r_frametime_dump` average / 1% / 0.1% tail
means. 0.1% values rest on 7-10 frames a window and are the least certain number here.

## Findings on the earlier work

1. **Tensor2 sky rays (P1357).** P1357 skipped empty grid cells but every CSQC trace still
   walked every cell of its bounding box (about 1,860 per sky ray; 814 M cells in 20 s) and
   all 362 overflow-list entities (78 brush, 277 trigger, 7 zone probes), and traced brush
   entities whose box met the ray's box but not the ray. Sky rays 64 vs 0 at scale 1: 355 vs
   602 fps, so the test cost 1.16 ms of a 2.82 ms frame. Fixed by P1363.
2. **Ceaseless hitch (P1358).** P1358 halved each solve, but solves still ran in the frame
   that first drew a prop: worst frames stayed ~70 ms, 0.1% low 18-26 fps. Ceaseless's 151
   props are unbaked and lit by 169 worldlights; all of them solve in 340-357 ms. Fixed by P1364
   (everything solved before play).
3. **Late shader compiles (P1351).** The starter list carried none of 36 permutations these
   maps compile under full effects; a first play compiled 27 programs late on Tensor2 and 13
   on Ceaseless. P1365 halves that. The rest are programs registered after activation, which
   no list can reach (BACKLOG).
4. **GPU endpoint shader (rejected 7 Nov).** Agreed: explicit-gradient branching cost more
   than the fetches it skipped. Not the limit at the owner's play scale on Tensor2.

## P1363 (engine): CSQC point traces visit only what the ray reaches

Tensor2 replay 4729, full effects, two runs of the final gate (absolute fps vary between runs
with machine load; the ABBA inside a run is the comparison):

| run, arm | avg | 1% | 0.1% |
|---|---|---|---|
| 1: csqc_linewalk 0 (A1/A2) | 386 / 384 | 239 / 231 | 143 / 145 |
| 1: csqc_linewalk 1 (B1/B2) | 496 / 486 | 295 / 283 | 179 / 153 |
| 2: csqc_linewalk 0 (A1/A2) | 349 / 339 | 167 / 161 | 105 / 109 |
| 2: csqc_linewalk 1 (B1/B2) | 438 / 442 | 208 / 198 | 130 / 128 |

Exactness: `csqc_linewalk 2` ran both walks on every eligible trace and compared every
trace_t field: 392,134 Tensor2 traces on the final gate and 1,275,353 on earlier builds
(Tensor2 and Jumble), 0 differed. The guard that stands the fast path aside when engine code
leaves a solid entity's link out of date read 0 in every run that had it (Tensor2, Voyager,
Tripportals with 279 listened proximity brushes). Remaining
sky cost with the fix: rays 64 vs 0 = 445-458 vs 593-599 fps (~0.5 ms, mostly the world BIH
trace). surf_jumble (594 lightglows): +4.5% avg, +6% 1% low; its cost is the world BIH trace itself.

## P1364 (hl2 plugin): static-prop lighting before first sight

Ceaseless replay 77, a fresh launch per arm (on, off, off, on), first traversal, full effects:

| arm | props solved mid-route | avg | 1% | 0.1% |
|---|---|---|---|---|
| hl2_lt_prewarm 3000 | 0 | 575 | 261 | 240 |
| hl2_lt_prewarm 0 | 103 (321 ms) | 548 | 135 | 26 |
| hl2_lt_prewarm 0 | 103 (322 ms) | 547 | 136 | 26 |
| hl2_lt_prewarm 3000 | 0 | 560 | 264 | 231 |

The pass solves all 151 props in 355-357 ms, once, in the first world frame after the
loading plaque, after waiting for every prop model. Other maps: Demise 2350 props in 23 ms,
Boreas 1587 in 21, Garden 429 in 12, Jumble 819 in 3, surf_dragon_css 3133 in 15 (baked
props skip the worldlight traces).

## P1365 (data): starter shader list

36 permutations added to `ftesurf/glsl/warmseed.txt`. Fresh fixture, empty learned list,
14 s of first play (late compiles via `r_mapready_info`): Tensor2 27/27 -> 14/14, Ceaseless
13/13 -> 5/5. Milliseconds are small on this PC because its driver cache is warm; on a
first-time machine each late compile is a 20-40 ms frame (P1351 measured 37/30/20 ms).

## Heavier maps (census of 2,204 BSPs, `artifacts/census.json`)

Sprite/beam sets above Tensor2's 465: bhop_rpg (877 sprites), surf_vestige (381 glows +
362 spotlights), surf_fairy, surf_jumble (594 glows), bhop_exordium (565 spotlights),
surf_s_t_a_t_i_o_n, bhop_canals, bhop_treason_speedrun. Unbaked props x worldlights like
Ceaseless but larger: candidates among surf_kitsune2_css (1455 x 7898), surf_lt_omnific_css,
surf_clavius_css, surf_palm_css; surf_dragon_css turned out baked (3133 props in 15 ms).

## Delivery status

Engine `e7912dd9b` (tag `patch-1364`) and this report pushed 7 Nov. Installed 7 Nov 12:00Z
on the owner's go into C:\FTESurf and C:\FTEQuake: a clean `-Engine -Full -NoDeploy` build of
the tag (3.2 min, stamp `patch-1364-0-ge7912dd9b`; its only warnings in touched files are on
upstream lines), 7 natives + glsl/warmseed.txt per install, predecessors as .prev and archived
(task root artifacts/delivery-p1364), 18,959 cfg/progs/data files hashed unchanged. Smoke on
those exact files, full effects: Tensor2 r4729 ABBA 362/364 -> 458/461 avg, 1% 203/211 ->
250/250, 0.1% 128/126 -> 149/151; csqc_linewalk 2 compared 196,073 traces, 0 differed.
Ceaseless r77 fresh launch: prewarm on 151 props in 341 ms at load, 0 in play, 0.1% low 200
fps; off 103 props (323 ms) in play, 0.1% low 26. The Desktop release copy (0.1.41,
patch-1348) gets it with the next release.

## Review

Three independent review rounds, two lenses each in rounds 1-2 (exactness/control flow;
consequences for what the player sees). They found box traces, BODY-less masks, off-grid
rows, engine-side stale links and the proximity listener's false stale flag on the trace
side, and on the prewarm side re-runs on cvar presses, mid-run model arrivals, a reload
into the same model slot, a dangling pointer and the wait eating the budget. All are fixed
or excluded. Round 3's fixes were measured (above) but not reviewed again.

## Next levers (BACKLOG)

World BIH trace for long rays (30% of surf_jumble's frame, ~10 us a ray); the CSQC
interpreter (14-18%); programs registered after activation; 3D sky and transparent passes at
`r_renderscale 2`.
