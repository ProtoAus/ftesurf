# P1309 — optional winter weather preview

## Implemented, not native-accepted

`r_weather 0` is the default. On supported provisional maps the opt-in preview
adds original outside/sheltered wind, a crossfade from a baked roof-height lookup,
rare sky-only flash/bolt and delayed outside/muffled thunder. A static upward
world-liquid mesh adds a thin frost coat, tiled cracks and a view-dependent shine.
No liquid contents, collision, movement or damage changes: lava remains dangerous.
No full-world relight, reflection/scene/depth capture, raymarch, runtime BSP walk,
roof trace or per-frame allocation. Existing soundscape selection/volume/channels,
Milk sky and map/default sky are untouched. Disabling weather removes only its
entities/table and explicitly stops its owned channels. Audio-only off also stops
its own wind/thunder, not the map's existing ambience.

The roof cache is at most256x256 float32 values in memalloc (262144bytes), loaded
with ONE native `fread` after its small text header. Lookup is O(1). It reuses the
existing snowmask roof clipper, at128-unit cells for these maps; it is an artist
approximation, not an acoustic/occlusion simulation. Props, displacements and
moving/turned roof brushes retain that clipper's known limitations.

One static IQM carries the liquid triangles; a per-face UV bit distinguishes warm
lava cracks without another draw. One actual sky/SKY2D portal mesh carries both
the white pulse and a sparse original fork texture, so the bolt needs no extra
entity/draw. A short0.12-game-second pulse and slow shader-time cardinal phase
avoid procedural pixel noise/atan work. Flash strength is capped and can be0.
The ordinary schedule is35..80game seconds after the first30..70second wait;
thunder delay0.9..3.2game seconds. These are source bounds, NOT measured latency
or frame-time results. The fixed pre-authored fork is an approximation, not
simulated/unique physical lightning each time.

Models use `models/gibs/winterweather/`: the current native default
`sv_prop_hull_exclude` already excludes the cosmetic gibs prefix from convex
collision decomposition. Native gl_model.c default and com_mesh.c prefix check
were inspected. No live cvar/worker registration or native binary change. A
user-customised empty exclusion list can change that loading-time behaviour.

The existing loading-time `glsl/warmseed.txt` adds the base/fog ice and mist
variants and the sky variant. This requests compilation before play; no actual
cold-driver no-hitch pass is claimed. Enable weather BEFORE loading the map;
turning it on mid-run necessarily performs its one-time asset setup.

## Actual source/data checks

- Exact approved c24ede65 compiler; final supported `src/build.ps1 -Jobs 8
  -NoDeploy`: all three VMs ZERO warnings. First enum error and subsequent two
  uninitialised-allowed warnings were fixed, not suppressed; old logs retained.
- Three small offline tests: surface priority/exclusions, an acting two-height
  exposure fixture and malformed/oversized roof rejection. Not native execution.
- Actual Frost:570sky triangles,234ice triangles,65536roof cells.
- Actual Christmas:1103ice triangles,65536roof cells. Its6306-triangle sky is
  HELD by the4096 sizing cap; other features continue. The cap is conservative
  source sizing, NOT a measured FPS budget. Ice cap8192triangles.
- Bluewinter: no eligible world sky/liquid; skipped, without pretending a
  fallback outdoor classifier acted. Existing props/mist there are independent.
- All actual IQM headers/counts/index bounds/float arrays and roof sizes/finite
  data audited. Four original mono16-bit22050Hz PCM samples have nonzero bounded
  signals. Texture positive/border control:671/8192nonzero alpha pixels (8.19%).
  Original0.5blur failed the preregistered10% sparsity bound (12.13%); reducing
  the baked antialias blur to0.35 passed it. The control was NOT weakened.

## Generate / ship

Run `python tools/winter_weather.py --gamedir <OWNED-STAGING-GAMEDIR>` with the
existing local Momentum maps (or explicit `--mapdir`). Default provisional input
list is Christmas/Frost/Bluewinter. Generated map-specific IQMs/roof files stay
separate from source; no BSP, player file or public replay is modified. Original
procedural PCM/PNG assets and shaders are source-controlled.

**Do not ship the producer's gfx/snowmask scaffolding.** Those coarse128-unit
PNGs are only intermediates for the CPU audio LUT. Keep the installed fine32-unit
falling-snow masks untouched. Delivery allowlists only the five generated
`gfx/weather/*.roof` / `models/gibs/winterweather/*.iqm` files plus original
weather assets/shaders/warm list. No new online replay download is implied.

## Small native check / pending

Enable `r_weather 1` before loading Frost (not during a timed line). Check the
water's frost/shine and original hazard behaviour; cross a roof edge and listen
for a smooth sheltered/outside change. `r_weather_test 1` consumes one local
preview trigger: sky-only flash/fork, then thunder. `r_weather_flash 0` disables
both flashing and the fork; thunder is independent. `r_weather_audio 0` mutes
only the new layer. `r_weather 0` restores the no-weather control immediately.
Report clipping/sorting, volume, ugly frost or a hitch; do not infer native
success from the source/data checks above. Lava's visual colour/sorting still
needs a real lava-map check (the provisional bakes contain water).

Native renderer/audio/cold/moving-view MAX-FPS acceptance remains PENDING;
the last4096MiB/quiet render-launch guard refused on2523MiB free. Do not weaken
that guard, kill owner processes, or repeat an unchanged wait. Owner manual
acceptance is welcome for what they actually observe, not a numerical claim.
Full-world snow accumulation is the independently reserved P1287 workstream,
NOT implemented or replaced here. Event gift dates remain a separate decision.

## Actual delivery / current limit

- Product/source is committed and pushed: QC `5458009d57ed13c99733a0794dd561cfb9496d59`,
  engine journal `abb3073070142aefc72b2b0687c013e1edc5d89f`. The published P1308
  controller source and human confirmations were preserved during integration;
  combined SV/CL/MENU compile with zero warnings using the exact c24 compiler.
  P1308's native pin/tag is retained; this task did NOT rebuild/change native.
- BOTH Windows installs updated **2026-11-05 00:24:06Z**: 98 destination records
  (3VMs+3LNOs+28source-media+15generated-data per install), all hash-read back.
  Twenty actual native/config hashes unchanged. Original fine falling-snow masks
  untouched. Both caches seeded as `47f0508b.dat` with the committed non-deleting
  helper; actual cache/program hashes rechecked, no native process launched.
- Exact final CS identity admitted while retaining every old catalog byte;
  no backend restart/generation swap. This is code admission, not ranking proof.
- **Pi P1309 delivered, all12 current actors verified by 01:20:11Z5Nov.** The
  first bounded preparation correctly refused an occupied fleet before mutation.
  At a real quiet boundary, all8 current recorder payloads (2,821,850bytes) were
  archived/rehashed ONBOX+OFFBOX before ANY canonical stage/restart, with the
  strict13 declared-actor FD scope. This is NOT a general file-writer audit or
  recovery of any historical missing payload.
- 42 runtime-only media files installed/read back **01:01:28Z**; client-local
  warmseed explicitly excluded. Published P1311's expanded warm seed was already
  exact on BOTH Windows installs; preserved, not replaced by the older snapshot.
- Paired QQ-only activation **01:08:01Z** restarted11 and correctly skipped one
  newly occupied lobby. Its strict skip failure is RETAINED, not relabelled PASS:
  all46,392 pre-existing protected paths, native/config/backend unchanged.
- Scoped completion **01:20:11Z** restarted ONLY remaining lobby8 after it emptied;
  other lobbies did not need to disconnect. The SAME archive still matched ALL
  current parts; fresh13actor/FD proofs checked at the short execution boundary.
  All12 final actor epochs verified; zero repeated healthy restarts/swaps/force or
  data restoration. All46,398 paths existing at that boundary unchanged;6new
  paths retained, not deleted. Native/config/backend preserved, sweep lock gone.
  Original failure plus separate one-lobby completion receipts remain private.
- Reconnect/reload the map to select the new CSQC. Native appearance/audio/FPS
  still needs the small owner check below; status/hash readiness is not that pass.
- The actual pair includes published P1308's controller with qualified c24 and
  zero warnings. Do not replace it with an older controller-only correction and
  lose weather. This does NOT recover P1308's historical resume-metadata loss,
  regrade that failed guard or claim the separate P1310 native promotion done.

Native appearance/audio/cold/moving-view acceptance is still PENDING; defaultOFF.
The separately owned P1287 full-world snow cover remains reserved; Santa earning
activation still needs the actual event dates. This is not an all-features-done
or numerical performance claim.
