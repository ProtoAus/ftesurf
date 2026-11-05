# P1319: visible snow, snowy-grass footsteps and real ramp clearance

## Owner failure and falsifiers

Owner5Nov: Colin props are present, snow is purple/from underneath rather than
snowy grass; wants snowy walking sounds; Frost already has native snow; ramp dirt
still fights while surfing. Preserve these as real failures of prior corrections.

Predictions: real stored IQM faces must be clockwise against their outward normals;
reversing them must cull the visible snow. Production snow GLSL must render white
on exposed grass/caps, discard a roofed cap and leave covered grass visible.
An absent/disabled replacement must NOT suppress native snow; rain is untouched.
Footstep substitution must stay local to Colin's authored snowy-grass material and
have four distinct, finite, nonclipping short samples. Ramp positions and culling
radii must use the same actual normal lift, not just a GPU slope offset.

## Changes

- IQM material precache ran before the snow definition, using the same name.
  FTE's `R_RegisterShader`/`R_RegisterSkin` share `R_LoadShader`'s cached-name
  lookup. Register a distinct versioned runtime material **before** precache.
  Do not let a missing IQM material select the purple fallback for this handle.
- Correct winding against actual float32 stored positions/normals, not an assumed
  OBJ/BSP fan order. Drop collapsed/degenerate triangles. Keep grass opaque and
  caps roof-clipped, with no collision/world-material edit or new draw call.
- Reuse material-resolved contact and local footstep emission for four original
  procedural snow crunches on this map's snowy grass, including quiet walking.
  Other floors/maps retain general-Foley opt-in and walk silence. The map-only
  theme opt-out disables these automatic sounds. No movement/input writes.
- Submit optional falling snow before native precipitation. Only an installed,
  submitted replacement stops new type3 map snowfall; old short-lived native
  flakes expire. Turning it off restores native emission. Rain/other effects stay.
- Real ramp-normal clearance defaults2units (was0.75); `r_rampwear_lift` is clamped
  to0..8 and takes effect at map reload/reconnect. The matching bounds expand too.
  Keep `depthpush -2`: native Patch1251 defines constant depth steps, NOT a slope
  term. Distinct material names avoid reusing the previous runtime material cache.

## Actual evidence and limits

- Smallest existing three-VM NoDeploy build: initial owned undeclared-local error
  retained; after fixing it, SSQC/CSQC/menu each0warnings, native exit0.
- `test_winter_repair_pixels.py`: actual hidden Windows GL context compiles/links
  production vertex+fragment programs. Exposed grass378white/blue-snow pixels;
  open cap378; roofed cap0; deliberately reversed winding0. This is shader-pixel
  proof, NOT a game screenshot, native placement, surfing or FPS acceptance.
- Original shader caps AND grass compile on this driver. Initial `packed`
  reserved-keyword suspicion is **falsified here**, not asserted as the root cause.
- Real corrected grass344CW / caps3768CW, all nondegenerate. Retained originals
  contain344wrong grass fronts and3476wrong cap fronts plus collapsed faces.
- Four distinct mono16-bit22050Hz PCM files, each0.1..0.5s; RMS/peak bounded.
- Inspected Frost BSP contains10type3 `func_precipitation` volumes. Suppression
  is based on actual replacement submission, not merely `r_weather` or map name.

`r_weather 1` on Frost controls storm sky/clouds, reversible cooler map light,
wind and intermittent flash/thunder. `r_weather_test 1` triggers the acting flash
without waiting. It is NOT the falling-snow switch (`r_snow`). `weather_info` and
`winter_info` report loaded components. Native manual check stays in lextest.md;
no numerical FPS or owner appearance/sound/ride pass is claimed.

## Actual delivery5Nov2026

Public feature `2468a105`, journal `8af388411`; isolated qualified source
`dacf00d8b870f838ca5f5ea07ef24555321ca48f` published on the existing qualified
branch. Its functional files match the feature exactly; metadata retains the
qualified native/API base rather than importing unrelated newer native work.
All3VM clean build0warnings using the inspected c24ede65 compiler.

Both Windows installs published at10:47UTC:102explicit destinations verified,
32native/config/old-fine paths unchanged. Both exact client caches are seeded
under advertised folded-MD4 `3dbd1053`. Later P1320 advanced only four server
program/symbol destinations together; the98remaining destinations, including
our corrected client/media and both caches, still match. Do NOT recopy old server
programs over that newer work.

Client SHA256:
`06585861c9afaf6ae6db1ee05151814d35f9532691cf8dca2eb23ccbdd4b6b12`.

The Pi's58explicit media files published with strict parts/backend preservation.
Exact client admission appended57->58, preserving every prior catalog byte;
no backend restart. Before ANY canonical stage/restart, all8current parts
(2,821,850bytes) and180complete resume payload/sidecar files (226,269,873bytes)
were captured and individually rehashed ON/OFFBOX with source/stat context.
No guessed expiry, restoration, ignored namespace or failure regrading.

Original paired-program transaction swapped the exact pair and verified5empty
lobby restarts, then FAILED on a later status timeout. Retain that failure.
The existing remaining-only completion seam refused a transient unclassified
nonactor FD denial; no remaining restart was requested. A later strict preflight
then detected concurrent P1320 server advancement and stopped, again without a
restart request. Do NOT rerun the original rollout, restore an old server or
repeat healthy restarts to make this receipt pass.

Independent read-only end-state check at11:14:14UTC: all12actual lobby epochs
are newer than preparation, exact corrected client current, all58media hashes
match, native/config/backend unchanged, direct health HTTP200/ok/lobbies12.
ALL46,766original protected entries remain byte-identical, with8new paths.
Both Windows installs and The Pi now use peer P1320 server hash `121eabc12b53…`
while retaining our exact client. This is current end-state evidence, NOT a
relabeled pass of our failed original transaction or a claim we restarted all12.

Native look/sound/ride/FPS is still owner-pending. No native engine binary,
pin/tag, QC Build, player config/data or evidence format change by this feature.
Private raw histories/preimages remain private; owned source/evidence roots are
retained for the small manual follow-up, not left as unexplained build copies.
