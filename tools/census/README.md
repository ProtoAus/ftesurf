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
