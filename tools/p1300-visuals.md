# P1300 ramp wear, inspect sounds and default-sky follow-up

## Delivery state

Implemented in an isolated source tree and QC-compiled; offline bake controls
pass. **NOT fully runtime-qualified, NOT deployed.** The original rendered control
ran after waiting 544 seconds at the existing 60-second quiet / 4 GiB free-memory
gate. Subject remained blocked at that same gate and its verified owned waiter
was stopped without child processes or an owned gate left behind. The negative
producer is confirmed; subject qualification remains paused, not passed.
Do not equate the build with a visual, audio, frame-time or lobby acceptance pass.
User-facing human checks are in lextest.md; remaining Christmas content is in
ROADMAP.md. No release, QC Build decision, native pin/tag or gameplay change.

Source published: product commit `7dd89457`, asset/provenance docs `ea72a344`;
engine journal `5157ca209`. Final isolated clean-commit progs (7dd89457):
qwprogs SHA256 `9fc3dd89e0db56509aef5d5fe634f4f0b0afbed4d2bb813469e06fddc46a1309`,
csprogs `56c9bd62753a8bca63684c4144cf6eb423798752b8fa47f7bce751d29ed27b57`,
menu `e69b5f249e0fb09f777c3fc8f8a3e72c846d8b27200923f4795d93219ae3af04`.
These hashes identify staging, NOT either install or lobby deployment.

## Changes / predictions

- The original scratch rows fade when their projected footprint exceeds a pixel;
  this is distinct from the overlay's old 6000-unit overall cull. Fine grooves
  now transition into eight-times-broader scuffs. Default range 12000, clamped
  1024..24000, fade over the last quarter. Scratch strength defaults to 1.5.
- The atlas does not use a mip chain that mixes unrelated charts. Bake chart
  origins snap to a shared world texel lattice; uncontacted neighbouring faces
  can still receive a crossing boarding streak. Atlas height is power-of-two;
  oversized charts increase the offline texel spacing rather than overflowing.
- Replace slope-dependent polygonoffset (-25 units / -0.05 factor) with
  renderer-aware depthpush -2 and unchanged geometry. This is intended to reduce
  near flicker and distant grazing-angle float/overlap; screenshots are still
  required. It does not weld BSP geometry or promise every noncoplanar join.
- Single-pass double modulation retains the base ramp lighting and permits a
  small view-dependent polish term (r_rampwear_shine default .15, zero off).
  It is NOT a reflection capture, physically based specular or dynamic lighting.
  Fine/coarse scratch scales both evaluate only in their transition band; still
  one mask lookup and one pass. More distant submitted faces can still cost more:
  no speedup/no-stutter claim without a moving-view comparison.
- Sound aliases parse line-by-line instead of repeatedly constructing/scanning
  the whole script string. FTE may still load the file at first access; this is
  not streaming-I/O or zero cold-load-cost proof. Preserve package selection,
  sound-script semantics and fallbacks. Cache 64 aliases, clear when the model
  changes, and request at most one inspect event's sound precache per frame after
  equip. Warming never calls the playback function. Inspect timing/events remain
  authored by the mounted model; an immediate inspect can still beat warming.
- On world load/renderer reset, an off/unsupported Milk sky releases only the
  stale r_skybox=milk override, leaving unrelated user skies alone. The engine
  can then resolve no-skyname maps through r_skybox_default. The reported Colin
  failure is not fully reproduced yet; this addresses a specific reachable stale
  state, not every filesystem/async/default-sky failure.

## Verification already completed

- Existing build.ps1 -Jobs 8 -NoDeploy -FteRoot <paired owned engine> entrypoint.
  SV/MENU zero warnings; CL only the same two F333 VF-field-227 diagnostics as
  the original control. Warning payload multiplicities compared, not suppressed.
  Intermediate unused-local and conservative output-parameter warnings were
  fixed; their logs are retained, not relabelled passes.
- `python tools/test_rampwear.py`: 3 tests pass. The exact old paint/pack functions
  fail the seam-lattice and atlas-size controls (2 failures / 0 errors); the
  boarding-strength control passes. Shared synthetic coplanar samples agree to
  1e-6 and the crossing streak is nonzero on both faces.
- Read-only replay bakes to the owned artifacts directory:
  surf_colin_blaster_69000: 77/77 demos read, 648966 ticks, 37 ridden charts,
  780 boarding events, 1376 triangles, 2048x2048 RGBA atlas.
  surf_classics3: 70/70 demos read, 381388 ticks, 31 ridden charts,
  609 boarding events, 1831 triangles, 2048x2048 RGBA atlas.
  These use the existing corpus, NOT new demo downloads. surf_demise's local
  inputs yielded zero contact charts; it refused a bake and no replacement is
  shipped. Do not treat that as a successful empty map.
- Actual dedicated socket / rendered original client on Colin: three checks pass.
  The client was spawned; r_skybox=milk was explicitly set with milk_sky=0;
  reconnect retained milk. This proves the stale override producer acts, not that
  every aspect of the original owner's loading failure is reproduced. Only the
  owned peers were stopped and the owned fixture's junctions removed.
- LSP reports no recorded diagnostics for the edited files; clangd does not
  validate QC, so compiler output above is authoritative for that language.

## Remaining before delivery

Use the existing owned fixture/Peer entrypoints, a real dedicated socket and the
actual final subject progs/shader. Control must prove the stale Milk state exists;
subject must release it and show the loaded default, while preserving a real user
sky. Debug mask/off/on must prove actual ramp submissions; inspect near, distant
and oblique seams. Knife warming must report events>0/done=1 followed by actual
model callbacks and sound emissions; listen for correctness and compare cold/warm
frame tails. Then commit-qualified artifacts to both installs and the lobbies
with destination hashes/rollback and a cold served-CSQC client check. No live
configs/player data or third-party models/sounds have been changed.

The linked smoke project's README was inspected. Its Valve SDK terms restrict
use to modified Valve games on Half-Life; no code/assets were imported. Proposed
FTE smoke is an independent, capped impostor/slice approximation, not a promise
of full volumetric simulation at negligible cost.
