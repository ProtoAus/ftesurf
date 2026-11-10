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
