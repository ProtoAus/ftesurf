# P1441 -- glsl/warmseed.txt re-seeded from all 60 survey maps

**What:** the release's starter shader list (`glsl/warmseed.txt`, read beside each PC's own
`data/glslwarm.txt` -- gl_shader.c GLSLWARM_SEED, P1282) grows from 269 to 768 permutations (471 programs).
Every old entry is kept. Data only: it rides the next release; lobbies cannot deliver it.

**Why:** a permutation that is not warmed at map activation compiles the first time it is drawn. On a PC whose
NVIDIA driver has not cached it (a new install, or any driver update) that costs 10-15 ms on the PC
(i9-9900K, RTX 2080 SUPER) -- one hitch per permutation, mid-run. The old seed came from a patch-1284 exe and 41 of
today's maps never ran into it.

## Collection

`artifacts/run_warmseed.py survey-all.txt warmseed-collect-defaults.txt 26 defaults`, one map per rig.lock hold:
the fixture's `data/glslwarm.txt` deleted (only the shipped seed warms), the map loaded at cfg/default.cfg
(passed at launch), its best board replay at 3x for 45 s, then what the client wrote to `data/glslwarm.txt`
merged. 60/60 maps.

- 28 maps (tensor2 ... aweles, the first chunk) were collected while the settings were exec'd after the load,
  which voids the activation warm-up (`mapready: invalidated`) -- their late-compile COUNTS were inflated, and
  their entries may include permutations drawn under the fixture's previous settings for the first frames. Extra
  entries cost load time on a cold cache, not correctness; the cold test below includes two of those maps.
- surf_dragon_css and surf_utopia never opened a replay: their entries come from the spawn view only.

## Cold-cache test

`artifacts/run_coldwarm.py`: each run starts a renamed copy of the exe. The NVIDIA GL cache keeps one
`<hash>.bin/.toc` pair per exe name inside `%LOCALAPPDATA%/NVIDIA/GLCache/<driver>/<gpu>/` (measured: a renamed exe
created a new pair at its first compile; nothing else had created one since 6 Nov), so every run is a first launch
and the owner's cache is untouched. The new pair and the exe copy are removed after each run (cache folder back to
60 files after every run). Default settings, best board replay at 1x, frame times over 40 s from 1.5 s after play.

| map | list, budget | warm-up s (compiled/pending) | late compiles (ms) | avg / 1% / 0.1% fps | worst ms |
|---|---|---|---|---|---|
| fairy | shipped 269, 2s | 0.510 (53/0) | 31 (354) | 297 / 100 / 62 | 20.4 |
| fairy | new 768, 2s | 1.149 (121/0) | 8 (60) | 305 / 111 / 85 | 16.9 |
| fairy | new 768, 6s | 1.160 (121/0) | 8 (59) | 302 / 110 / 85 | 16.4 |
| quarantine | shipped 269, 2s | 0.831 (87/0) | 39 (490) | 620 / 229 / 49 | 98.8 |
| quarantine | new 768, 2s | 1.958 (199/0) | 8 (37) | 621 / 320 / 137 | 24.9 |
| quarantine | new 768, 6s | 1.947 (199/0) | 8 (40) | 631 / 338 / 142 | 24.8 |
| nuclear | shipped 269, 2s | 0.488 / 0.492 (52/0) | 36 / 36 (491 / 502) | 599 / 287 / 78; 588 / 263 / 72 | 33.4 / 33.1 |
| nuclear | new 768, 2s | 1.211 / 1.135 (117/0) | 3 / 3 (18 / 17) | 489 / 207 / 96; 562 / 296 / 135 | 24.8 / 17.6 |
| original | shipped 269, 2s | 0.622 (65/0) | 16 (169) | 776 / 380 / 157 | 20.8 |
| original | new 768, 2s | 1.370 (139/0) | 6 (27) | 801 / 415 / 205 | 11.5 |
| pantheon | shipped 269, 2s | 0.501 (53/0) | 37 (411) | 435 / 227 / 119 | 29.4 |
| pantheon | new 768, 2s | 1.243 (129/0) | 6 (23) | 435 / 244 / 169 | 9.7 |
| tendies | shipped 269, 2s | 0.576 (57/0) | 64 (775) | 674 / 249 / 58 | 71.0 |
| tendies | new 768, 2s | 1.544 (157/0) | 4 (21) | 660 / 305 / 139 | 16.8 |
| quarantine | new 768, 1s | 1.019 (106/93) hit | 32 (350) | 617 / 244 / 60 | 53.7 |

- nuclear ran twice per list: the first new-list run's avg (489) was run-to-run noise -- its repeat read 562.
- The cost: the first load of a map on a cold cache warms 0.6-1.1 s longer here. On a warm driver cache a
  permutation links in ~0.5 ms (quarantine, 175 eligible, 0.080 s).
- The 1 s row stands in for a CPU half this fast under today's 2 s budget: 93 permutations left pending, most of
  the gain lost. That is P1442's subject.
- A later quarantine run with `scr_loadtimes 1` hit the 2 s budget (196/3, avg 442 -- the machine was busier):
  `shader reload` 638 ms + `shader warm list` 2001 ms, back to back in CL_MakeActive's frame.

Rows: `artifacts/coldwarm-results.tsv`; collection: `artifacts/warmseed-collect-defaults.txt(.log)`.
