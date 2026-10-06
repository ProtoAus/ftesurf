# Map censuses

Read-only sweeps over the shipped map library, used to size movement rules
and rendering coverage before they are written. Every number quoted in a `run_pushed` / `run_pushlift`
comment comes from one of these, and the point of committing them is that the
number stays checkable after the session that produced it.

Maps come from the Momentum install; override the default with

    MOMENTUM_DIR="/path/to/momentum" python sscount.py

Start zones come from the shipped zone JSON (`maps/zones/online/<map>.json`,
`segments[0].checkpoints[0]`) where one exists, else from the map's own
`trigger_momentum_timer_start` brushes.

| script | question |
|---|---|
| `bsplib.py` | minimal VBSP reader: entity lump + models lump, LZMA-aware |
| `particlecoverage.py` | Source particle entities vs embedded PCFs, registered bakes and translator support |
| `pushcensus.py` | `trigger_push` volumes overlapping or near a start zone |
| `pushtilt.py` | ...of those, which push UPWARD (Patch 411) |
| `sscensus.py` | `trigger_setspeed` pads that can drive `velocity_z` over 140 |
| `sscount.py` | ...counted by real overlap VOLUME and by containment |
| `ssd1.py` | horizontal-only setspeed pads in a start zone (Patch 412's open case) |
| `onjumpstart.py` | OnJump basevelocity pads vs start zones, on the live rotation (Patch 414) |
| `recsim.py` | cross-run similarity over the server-written move columns (BACKLOG item F) |
| `assist.py` | the timing-assist statistics, and which of them the corpus can support (BACKLOG item G) |

## Source particle coverage

From the repository root:

```sh
python tools/census/test_particlecoverage.py
python tools/census/particlecoverage.py --json <report.json>
```

`--mapsdir`, `--index` and `--cfgdir` override the inputs. `MOMENTUM_DIR` points
at the game directory containing `maps/`, not at `maps/` itself. The tool does
not generate effects or change the index/player data. Only the optional JSON
output is written. Exit 2 means an incomplete census: every failed library is
reported, while its map/entities and other readable libraries remain counted.

Measured 2026-10-06: 1,349 BSPs, 144 maps with 8,000 particle-system entities,
96 maps with embedded PCFs, two with registered bakes, 94 embedded-library maps
without bakes, and 23 maps with multiple PCFs. Both existing tensor2/boreas cfgs
reproduce exactly with the current translator. Ten PCFs use unsupported DMX
binary v5; two more fail their ZIP CRC, so the full translation census is NOT
complete (exit 2). A translatable system is not a fidelity/runtime pass: unknown
operators and rejected systems are reported separately, and game-pack libraries
are not scanned. Maps without embedded PCFs do not necessarily lack a library.

## The fleet corpus, and how to get it

`recsim.py` and `assist.py` both answer a question about a CORPUS, and the corpus
on this workstation is the wrong one: `ftesurf/data/` is harness output, so its
multi-run groups are one scripted route driven twice rather than two performances.
The runs real players posted live on the Pi.  **Neither tool defaults to it and no
number in this README was measured on it before 2026-10-05** -- the sections below
say which corpus each figure came from, and a figure from the wrong one is not a
weaker version of the right one, it is an answer to a different question.

Read-only fetch (79 MB, 64 `.rec` at the time of writing; nothing is written on
the host):

    ssh proto@192.168.1.102 'cd /srv/nvme/ftesurf-server/game/ftesurf &&
        tar -cf - $(find data/runs -name "*.rec")' > fleet.tar
    mkdir fleetruns && tar -xf fleet.tar -C fleetruns
    python tools/census/recsim.py --root fleetruns/data/runs pairs
    python tools/census/assist.py --root fleetruns/data   census
    python tools/census/assist.py --root fleetruns/data   control

Note the two roots are DIFFERENT: `recsim` wants `data/runs`, `assist` wants
`data` (it classifies by the `/momentum/` vs `/data/runs/` path segment).

**THESE ARE PLAYER RUNS AND THEY DO NOT GO IN THE REPO.**  The filenames carry a
name and a guid digest.  Fetch them to a scratch directory outside the tree,
quote the numbers, and never commit the files -- `ftesurf/data/**` is gitignored
precisely so this stays true.  The detailed write-up lives in the private
`cheatanalysis/FINDINGS.md`, not here.

**AND THE CORPUS'S COMPOSITION IS PART OF THE MEASUREMENT.**  A run's identity is
the 8-hex `FS_GuidId` in its filename, which is sha256 of the install's `qkey` --
so it survives a rename and it does NOT distinguish two netnames on one install.
At the time of writing the fleet holds **four identities and 53 of its 64 files
are one of them** (`proto-`, `kap-`, `1proto-` and `player-26c95e00` are one
machine).  `recsim.py pairs` prints the same-identity / cross-identity /
unknown split for exactly that reason: a similarity gate's hardest honest case is
ONE PLAYER replaying ONE MAP, and a corpus that is mostly one identity measures
that case while appearing to measure the general one.

### What the fleet corpus moved (2026-10-05)

Both tools had recorded themselves as blocked on it.  Measured, not expected:

| | local `ftesurf/data` | fleet `data/runs` |
|---|---|---|
| `recsim` negative pairs | 7, of which 3 agree on EVERY row (harness output) | **20**, none above **0.5866** |
| `recsim` separation | unmeasurable -- the corpus cannot calibrate | **positive min 1.0000 vs negative max 0.5866, CLEAN, margin 1.70x** |
| `recsim` identity split | 3 same, 4 unknown, **0 cross** | **12 same (max 0.5866), 8 cross (max 0.2146)** |
| `assist` files with a ramp-contact tick (`fl` bit 16) | 101 of 5571, every one native | **54 of 64** |
| `assist` `land(bit16)` judgeable runs | 90 | **27, and every one reads 0.0000** |
| `assist` `null` runs reading exactly 1.0000 | 364 of 4237 (8.59%) | **4 of 57 (7.02%)** |
| `assist` hop-interval cv floor | 0.5487 | **0.6023** |

The two findings that matter:

- **`recsim`'s discriminator now separates on real runs, and the worst case is a
  same-player one.**  0.5866 is `surf_utopia` 0004216 vs 0004224, one install,
  two runs 8 ticks apart in length, cover 0.0000 and prefix 0 -- they agree on 59%
  of compared rows and share no contiguous opening at all.  The cross-identity max
  is 0.2146.  A gate at `match >= 0.95` sits 1.62x above the worst same-player
  pair and 4.4x above the worst cross-player one.  **That is still not a shipped
  threshold**: 20 pairs is a small sample and only 8 of them are cross-identity.
- **`assist`'s coverage problem INVERTS on the fleet.**  The local corpus's
  obstacle was that bit 16 is written only by our server, so the 5281 Momentum
  imports have none of it and 101 files in the whole tree did.  The fleet is all
  native: 54 of 64 files carry ramp ticks and 27 runs are judgeable.  **Every one
  of the 27 reads a frame-perfect-landing rate of 0.0000**, and `control` on a
  fleet run (`surf_4am`, 19132 ticks) proves the statistic is live rather than
  dead: **146 ramp-contact opportunities, 0.0000 as recorded, 1.0000 rewritten
  assist-shaped.**  So on this game's own runs, not one honest landing out of
  thousands was frame-perfect.  `null` is still unusable as a sole gate -- 7.02%
  of honest fleet runs read exactly 1.0000, matching the local 8.59%.

## READ THIS BEFORE QUOTING A NUMBER

**An entity box from the models lump is where a brush CAN be, not where it IS.**
This has been wrong by a wide margin three times:

- surf_666's `trigger_push` brush is far narrower in x than its AABB;
- surf_polygon's is inert throughout a 2048 x 2048 x 4096 AABB — 45 probe points
  across it moved the player nowhere (`cfg/test/p411push.cfg`);
- Patch 411's "4 upward pads on 3 maps" was a `gap == 0` figure, which counts a
  zero-width plane contact as an overlap. Two of its three maps were unreachable.

So the figures are graded, and only the last is safe to lean on:

1. `gap == 0` — touching, including zero-width. Nearly meaningless on its own.
2. positive overlap volume — the boxes genuinely interpenetrate.
3. **containment** — the pad's whole box lies inside the start zone. Wherever the
   brush sits within that box it is still inside the zone, so this survives the
   AABB problem. It still does not prove you can *touch* the brush.

Nothing here beats a live check. `cmd viewpos` after a `setpos` reads the player's
actual position back, and a `.rec` `warp`/`ride` row is a real touch by a real
player — `p369/surf_deoa.rec` is what established that setspeed pads are reachable
at all, its recorded origins sitting one hull-radius outside the pad's box in x.


## `recsim.py` — a census whose own output says it cannot calibrate

This one is different from the rest of the table, and the difference is the point.
Every other script here answers a question about map geometry and its answer is a
number you can quote. `recsim.py` answers a question about a corpus, and **on this
workstation the corpus is the wrong one**, so the tool prints that instead of a
threshold.

It measures whether two recordings can be told to be the same performance from
columns the SERVER wrote (`<fwd side up>` and `<bt>` out of the `in` rows) — the
strongest position in the evidence chain, because no client-side artifact is
involved and there is nothing on the attacker's side to forge.

**The finding that survived is which statistic separates, and it is the opposite
of the intuitive one.** `match` (agreement over compared rows) separates an exact
replay at 1.0000 from 376 pairs of genuinely different runs whose maximum is
0.5242 — a margin of 1.91x. `cover` (the exact contiguous prefix) separates
*further* on an exact replay and looks better, but it fails on the two attacks
that matter: it is brittle (one perturbed move at 1% of a run drops it from 1.0000
to 0.0098) and it misses the trimmed playback — submitting the first half of
someone else's recording — which reads 0.4998 while `match` still reads 1.0000
correctly. The first cut of the tool reported `cover` as the headline and would
have shipped a gate that a partial playback walks past.

**Why there is no threshold:** the local corpus holds no two genuinely independent
runs of one map. Every multi-run group is harness output, and finding that took
three passes at the fixture filter, each of which let a class through — reccheck's
own mutants in `data/p369/`, harness arms sitting inside the *real* directory
`data/runs/bhop_eazy/main/`, the `p371` harness's three runs under the player name
`anna-ab9ae4aa`, one file stored twice under two names, and 45 pairs of 7–13-move
stubs that agree perfectly because nine quaternions of input is not enough to
identify anything. `MIN_LEN` exists for the last of those, and a pair below it is
not compared at all rather than being reported as a low score.

So: run `recsim.py pairs` on a **fleet** `data/runs/` before believing any number
here, and read the caveat it prints when it fires. Full measurement and the
synthetic-positive table are in BACKLOG.md's item F.

## `assist.py` — a census that measured its own premise and lost it

BACKLOG item G asked whether a timing assist (`Edgebug assist`, `Jumpbug assist`,
`null strafe`, `AutoBounce`, `Perf-Hop`) can be told from a human using a kept
`.rec` alone, and proposed reading a success rate per opportunity off "`fl` bit 1
... ground contact per tick". **That premise does not survive the corpus**, and
the tool exists to show the measurement rather than the intention:

| obstacle | measured |
|---|---|
| `fl` bit 1 is not contact on a surf run — Source sets FL_ONGROUND only on walkable ground, and sliding a ramp leaves it clear | 5369 of 5414 files with rows hold fewer than `MIN_OPP` fresh-press landings; 45 are judgeable |
| a landing is not a jump opportunity | of 9855 such landings, 9122 (92.6%) see no press within 40 ticks |
| bit 16 (`run_rampcontact`) is the signal that would work, and only our server writes it | 101 of 5571 files have one ramp tick, all native; 90 hold such a landing; 16 delays total |
| `keys` is derived from the move signs by BOTH writers, so an overlap check is vacuous | `fl` bit 4 and `keys` FSI_JUMP agree on every row of all 5571 files — one fact, not two witnesses |
| the null observable that does exist does not separate | clean-switch rate: median 0.9038, and **364 of 4237 runs (8.59%) read exactly 1.0000** |

The one statistic with coverage is the **jump impulse**, which needs no ground bit:
`steps` histograms every upward `vz` step and finds a sharp spike at 275–300 u/s
(16,428 of 255,592 steps in that one bucket) sitting in a valley — `pm_jumpvelocity`
added in a single tick, against a ramp's gradual climb. That measured band is what
`HOP_MIN`/`HOP_MAX` are, and the interval regularity over it reads min 0.5487 on
204 judgeable human runs against 0.0000 for a synthetic periodic chain. Wide-looking,
but it bounds separation from **one side only**: no real assist sample exists in this
tree, and a timer-driven assist still reacts to terrain.

**A falsified explanation is in the tool's docstring and stays there.** The 73 of
733 presses that arrive within 2 ticks are too fast for a reaction (~150–250 ms), so
I predicted jump mashing. `delays` buckets runs by the fraction of ticks jump is
held, and the prediction is backwards: 32.9% fast in the 0–5% bucket against 0.68%
in the 75–100% one. What survives is either a selection artifact of excluding
held-jump landings, or a *predicted* press timed to a visible landing — which is
legitimate play. Neither is tested, and both say the same thing: a small delay
cannot accuse.

Run `control` before believing any zero in the output: it rewrites a real run into
an assist-shaped one and asserts each statistic reaches 1.0000 (and the periodic
chain reaches cv 0), so a low count reads as coverage and not as a broken statistic.
