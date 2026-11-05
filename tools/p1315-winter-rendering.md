# P1315 winter rendering corrections

Owner feedback5Nov: holiday props appeared inside-out; light mist was weak and
popped away nearby; `r_weather 1` on Frost showed no sky/lighting change; ridden
ramp dirt fought the surface, particularly save2. Colin's complete Christmas
conversion is the following map-specific work, not silently dropped.

## Corrections

- Six selected CC0 holiday IQMs now reverse OBJ triangle indices, preserving
  outward normals/UVs. Actual source snowman has890nondegenerate CCW/outward
  triangles. Front-face orientation, not a two-sided rendering workaround.
- Mist no longer rejects an entire field at192 units or when its coverage score
  crosses the cap. Up to4fields receive continuous projected-size shares, shrinking
  smoothly as approached rather than disappearing or filling the screen. Twice
  the old noise opacity. Budget math is not a numerical GPU-time guarantee.
- Both legacy/full and v2/half ramp-wear paths get an actual0.75-unit normalized
  face-normal lift once on load, plus conservative culling radius. Driver depth
  push alone wasn't sufficient. No map/collision/player position change.
- Weather retries the late native/server identity at0.25s until the world key
  matches. Missing roof/profile now reports a reason. Storm clouds draw on the
  bounded actual sky portals continuously, not just during a0.12s flash. Cool
  base-style lighting is captured/applied once and restored on OFF, never over
  another map's style. No dynamic light/shadow/capture or per-frame lightmap call.
- `weather_info` reports map/pending/ready/sky/ice/audio/tint. `r_weather_test 1`
  requests the next flash and delayed thunder immediately; `r_weather 0` is the
  restoration control. Existing defaults stayOFF. No owner config edited.

## Qualification and deployment separation

Four source/math controls in test_winter_rendering.py and existing three weather
roof/geometry controls pass. Actual all3VM c24/git7809 zero-warning compile;
first varargs warning retained and diagnostic split. Six rebuilt IQMs keep their
size/counts and normal/UV bytes; only imported winding changes.

Public main includes a separately pending P1314 TAS/native lane. Do NOT silently
ship that work with this visual update. Main keeps published ancestry; visual-only
deployment is separately inspected on fleet-qualified P1313 parent02a217cd plus
ONLY this delta, using the same compiler and existing dual-Windows Deploy helper.
Actual qualified source/artifact hashes and receipts must be recorded after the
acting publisher. No product-native/tag/qcbuild change or release requested.

Native/save2/close-motion/sky/lighting/audio/MAX-FPS acceptance is PENDING. Source,
compiled bytecode and projected-size arithmetic are not that pass. Restart client
when convenient to discard previously cached same-name models/mist shaders, then
check Frost outside a timed run, close to a light, and save2's ramp. New v2 sky
material avoids the old sky program cache. Turn weather off to compare lighting.
