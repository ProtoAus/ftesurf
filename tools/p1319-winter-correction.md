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

Deployment/provenance will be recorded after actual publication. No native
engine binary, pin/tag, QC Build, player config/data or evidence format change.
