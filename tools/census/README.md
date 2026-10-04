# Map censuses

Read-only sweeps over the shipped map library, used to size anti-cheat rules
before they are written. Every number quoted in a `run_pushed` / `run_pushlift`
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
| `pushcensus.py` | `trigger_push` volumes overlapping or near a start zone |
| `pushtilt.py` | ...of those, which push UPWARD (Patch 411) |
| `sscensus.py` | `trigger_setspeed` pads that can drive `velocity_z` over 140 |
| `sscount.py` | ...counted by real overlap VOLUME and by containment |
| `ssd1.py` | horizontal-only setspeed pads in a start zone (Patch 412's open case) |
| `onjumpstart.py` | OnJump basevelocity pads vs start zones, on the live rotation (Patch 414) |
| `recsim.py` | cross-run similarity over the server-written move columns (BACKLOG item F) |

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
