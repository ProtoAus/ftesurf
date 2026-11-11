# 0.1%-low survey 3 and the fixes it led to (P1481, P1482; P1477 delivered) -- ftesurf-18, 11 Nov 2026

Lex, 11 Nov: continue the frame-rate work (water fill rates), find the worst 0.1%-low offenders and fix them so the
frame rate is as flat as possible. Root `C:\FTESurf-worktrees\lows2-20261107-opus` (driver `artifacts/run_survey3.py`,
tally `artifacts/spike_causes.py`, table `artifacts/survey3_table.py`, dumps `artifacts/survey3/`).

## Method

The installed build (client exe b0349be2, patch-1476; plugin 8204a248; cs 01d9d44e), each map's best board replay
from a fresh load at Lex's settings (fullfx, MSAA 4, reflection MSAA 2, r_blendsort 2, uncapped, 1920x1200 window
behind the others), played twice: pass 1 is the first play (load and first-traversal costs), pass 2 the same 35 s
warm. `r_spikes 1` attributes the 8 slowest frames of each pass by r_budget group. The PC (i9-9900K / RTX 2080 SUPER),
shared with a peer session's rig queue. 20 of the 32 worst maps of survey 2 ran; the run was stopped by Claude Code's
low-memory reaper before agtricks, bhop_ceaseless, surf_aircontrol, surf_boreas, surf_frost, surf_garden, surf_het,
surf_kitsune, surf_monolith, surf_nova, surf_quarantine and surf_tensor2 (all 0.1% >= 190 in survey 2). surf_lovetunnel's
pass 1 ran beside an engine compile (void); tendies' and fairy's runs logged the window coming forward mid-run.

## Ranking (worst warm 0.1% first; buckets are the largest bucket of each of the 8 slowest frames)

| # | map | first play avg / 1% / 0.1% (worst ms) | warm avg / 1% / 0.1% (worst ms) | warm slowest-8 by bucket | first-play slowest-8 |
|---|---|---|---|---|---|
| 1 | surf_fairy | 247 / 83 / 58 (23.75) | 262 / 99 / 75 (16.98) | csqc 5, messages 2, blend draws 1 | csqc 4, messages 2, opaque draws 2 |
| 2 | surf_jumble | 325 / 109 / 86 (13.27) | 333 / 133 / 90 (17.31) | csqc 4, present 2, messages 2 | csqc 7, present 1 |
| 3 | surf_andromeda | 544 / 230 / 115 (19.55) | 572 / 227 / 90 (89.71) | present 4, csqc 2, messages 2 | present 6, opaque draws 1, messages 1 |
| 4 | surf_lovetunnel | 319 / 44 / 28 (41.62) | 471 / 167 / 91 (16.65) | present 3, csqc 2, script particles 1 | present 3, blend draws 1, prediction 1 |
| 5 | surf_mesa_revo | 327 / 146 / 106 (11.69) | 341 / 150 / 92 (15.37) | present 2, csqc 2, opaque draws 2 | csqc 3, messages 2, present 2 |
| 6 | surf_nuclear | 457 / 188 / 110 (?) | 417 / 163 / 112 (?) | present 4, qc collector 2, messages 2 | opaque draws 3, csqc 3, present 1 |
| 7 | surf_pantheon | 452 / 224 / 144 (12.00) | 437 / 194 / 112 (13.27) | present 6, messages 1, opaque draws 1 | present 4, messages 2, qc collector 2 |
| 8 | surf_colony | 466 / 227 / 147 (12.14) | 463 / 196 / 115 (19.96) | present 5, messages 2, opaque draws 1 | present 3, messages 2, world walk 2 |
| 9 | surf_tendies | 643 / 226 / 67 (146.88) | 467 / 180 / 122 (17.92) | csqc 3, messages 2, opaque draws 2 | opaque draws 5, messages 3 |
| 10 | surf_demise | 481 / 214 / 118 (20.11) | 498 / 217 / 122 (17.78) | present 5, csqc 2, messages 1 | present 6, blend draws 1, messages 1 |
| 11 | surf_whiteout | 549 / 240 / 115 (19.28) | 531 / 230 / 129 (14.47) | present 7, messages 1 | csqc 6, present 2 |
| 12 | bhop_emevaelx3 | 603 / 261 / 141 (13.08) | 604 / 262 / 140 (20.50) | present 5, messages 3 | present 6, messages 2 |
| 13 | surf_citypop | 681 / 316 / 144 (38.89) | 642 / 272 / 145 (14.58) | present 5, messages 3 | opaque draws 3, present 2, messages 2 |
| 14 | surf_hourglass | 472 / 213 / 121 (12.68) | 470 / 240 / 149 (12.03) | present 4, messages 3, csqc 1 | present 6, messages 1, csqc 1 |
| 15 | bhop_orgrimmar | 433 / 144 / 68 (?) | 493 / 216 / 150 (?) | csqc 4, present 2, messages 2 | csqc 3, opaque draws 2, present 2 |
| 16 | surf_bossfight | 669 / 196 / 117 (13.36) | 678 / 221 / 163 (11.12) | present 4, messages 2, blend draws 2 | present 5, opaque draws 2, blend draws 1 |
| 17 | surf_joutsenlaulu | 557 / 217 / 133 (16.07) | 549 / 260 / 176 (10.44) | present 4, messages 2, csqc 2 | present 4, csqc 2, messages 2 |
| 18 | surf_spectra | 778 / 388 / 200 (12.54) | 782 / 374 / 178 (11.95) | present 6, qc collector 1, messages 1 | present 5, messages 2, opaque draws 1 |
| 19 | surf_calzone | 715 / 311 / 157 (12.50) | 741 / 348 / 206 (12.89) | present 4, messages 2, csqc 2 | present 6, messages 2 |
| 20 | surf_original | 849 / 351 / 125 (43.57) | 875 / 418 / 241 (10.11) | present 5, messages 2, csqc 1 | opaque draws 4, present 4 |

## What the slowest frames were

- **swap/present 5-15 ms (once 87 ms)**: the largest bucket in most maps' slowest frames, in clusters, often with
  WM_PAINT in the same moments. The rig window sits windowed behind other windows; nothing in the engine is running
  in those frames. Whether a fullscreen client sees them is unknown -- the owner check in lextest asks.
- **WM_PAINT dispatch 3.7-5.1 ms** ("input, console"): found by P1482's split. Handling WM_PAINT in the window
  procedure did not change it, so it is outside the engine (driver/compositor hooks); windowed only, likely.
- **QC tempstring collector 1-6 ms main-thread phases** (every map; replays grow CSQC's slot table to 2.09M slots):
  fixed by **P1481** -- phases now 0.23-0.49 ms. surf_nuclear's 0.1% low did not move (on that quiet run the
  collector frames sat in the 1% tail); a slower PC is where they reach the 0.1%.
- **csqc 5-9 ms frames on surf_fairy and surf_jumble**: QC self time small (r_spikes 2: top functions 0.07-0.3 ms),
  so the time is in engine builtins called from QC (glare traces on fairy, P1456; jumble unknown). Next lead.
- **First-play opaque-draw hitches 20-147 ms** with no late compile or image upload: surf_tendies (the same spot,
  setpos -1021 10388 3962, 44 ms and 77 ms in two launches; 147 ms at -8804 5122 7549), bhop_orgrimmar (40-48 ms),
  surf_original (44 ms), surf_citypop (39 ms). Driver-side first use (state-dependent program recompiles or buffer
  placement); not yet identified. Next lead.

## GL debug output (diagnostic build only, not shipped)

- `GL_LazyBind` enables/disables texture targets on the compatibility path, including 2D-array and cube-array
  targets, which are not enable caps: GL_INVALID_ENUM many times a second. Harmless but wasted; BACKLOG.
- The instancing ring (1 MB, GL_STREAM_DRAW) is orphaned every few frames; normal, low priority.

## Delivered (both installs, 11 Nov 20:18Z): client exe 7930cc92

`git-8660-patch-1484-1482-0-g52f4f0ce9` = engine main 52f4f0ce9: P1477 (forced water captures staggered, rate floor
10), P1481 (collector write watch), P1482 (r_spikes input split), with pi.dev's installed P1479/P1480/P1484 journal
fixes. Server exes and the hl2 plugin unchanged. An interim install at 20:05Z of tag patch-1482 alone (exe ae0e53d8,
patch-1476 base) replaced pi.dev's installed patch-1484 build (006d65ac) for 13 minutes, because the live hash was not
re-checked right before installing; the combined build restored it and `.prev` is 006d65ac again. Records:
`artifacts/delivery-p1482/`, `artifacts/delivery-p1484-1482/`.

## Addendum, 11 Nov ~10:00-11:00 local: quiet machine, and P1488

- With the peer's benchmark paused, surf_pantheon and surf_colony had no swap/present stalls among their slowest
  frames and warm 0.1% lows of 200-239 (survey: 112-115); r_renderscale 0.5 changed little (+10-20). The survey's
  present and WM_PAINT stalls were contention from other work on the machine. Its ranking of the CSQC-heavy maps held.
- surf_fairy / surf_jumble: a diagnostic build that times each CSQC builtin under r_spikes 2 (engine branch
  diag-builtins) put their slowest frames in traceline -- 66-98 calls a frame at ~100 us on fairy, 60-78 at ~40 us on
  jumble -- from Sprite_Glare and Sprite_SkyTick. Halving both ray budgets: fairy 0.1% 82 -> 110.
- P1488 (delivered): engine gettime(2) (seconds into the frame, 0.1 ms steps) and a shared per-frame trace time budget
  in QC, vbsp_sprite_tracems 1. surf_fairy warm, two alternating rounds at 0 / 1.5 / 1 ms: 0.1% 86 / 114 / 125,
  1% 105 / 137 / 148, avg 296 / 310 / 324, stutters ~830 / ~100 / ~40. surf_jumble 0 / 1: 0.1% 183 / 252.

## Quiet re-ranking on the installed build (11 Nov ~11:20 local; exe 79c0cd4c, cs e8700c05)

Warm pass, avg / 1% / 0.1%: surf_fairy 326 / 149 / 126, surf_mesa_revo 419 / 264 / 218, surf_pantheon 464 / 267 /
218, surf_andromeda 594 / 304 / 235, surf_jumble 434 / 278 / 253, surf_lovetunnel 583 / 363 / 287, surf_nuclear
637 / 364 / 308 (colony, tendies, demise not re-run). fairy is still the worst: its slowest frames (~8 ms) sit at one
place ~30 s into the replay, transparent draws 3.0-3.5 ms + csqc 2.2 + one water view -- r_blendsort 2's cost there
(P1457/P1463/P1465's ground); next: a paused-view probe at that spot.

## First-play hitches (surf_tendies probe, GL debug output on)

Every pass-1 hitch (29-70 ms) came with new STATIC_DRAW vertex/index buffer pairs created mid-play, 3-4 pairs a hitch
~5 ms apart: models finishing their load and building their mesh VBOs on the main thread at first sight
(com_mesh.c Mod_GenerateMeshVBO and the skin/vector work around it). A second launch minutes later had none (pass-1
0.1% 321, worst 5.2 ms) and built no model in play -- so it depends on whether the activation warm-up got to those
models (r_mapready_budget 6 s, cold vs warm file cache). Next: print r_mapready_info after a cold first load, and
load what the warm-up misses off the main thread or before play. Diagnostic branches (not shipped): diag-builtins
(r_spikes 2 per-builtin time), diag-firstplay (gl_debugperf filtered, r_spikes 3 slow-frame stamps, meshvbo names).

## P1489 and the next leads (11 Nov afternoon)

- Lex's fullscreen fairy dump: no present stalls; his worst frames were first-play -- 77 + 51 ms csqc right after
  spawn, a 53 ms frame with a late shader compile. A spawn probe (r_spikes 2 from launch, per-builtin times) named
  the csqc frames: the sprite/emitter/decal/portal loaders ran in the first frames after spawn because
  serverkey("map") is "" in CSQC_WorldLoaded on a connect. P1489 (delivered) runs them there, keyed by the loaded
  world: fairy's post-spawn frame 547 -> 108 ms (profiled); zones remain.
- Traces: a ray costs fairy 40-56 us in the world BIH (entities < 3 us); see BACKLOG.
- Fairy's worst spot (replay t=33.2): r_blendsort 2's sort fails every frame with no certificate, ~1.2 ms of
  transparent + ~1 ms GPU; see BACKLOG.
