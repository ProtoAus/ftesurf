# P1335 — Christmas master and close, optional ramp wear

## Requested result / controls

Owner requests seasonal effects behind a Christmas cvar, ramp marks/dirt off by
default, and dirt closer to the ramp without visible detachment/z-fighting.

- `r_christmas 0` is the fresh master default. It blocks weather load/frame,
  automatic Colin theme, forced snow, props and mist. Disabling active weather
  frees its entities and stops loops/pending thunder; individual preferences are
  retained. `r_christmas 1` permits existing map-specific/per-effect selections.
- `r_rampwear 0` and `r_rampwear_dirt 0` are fresh defaults. Display Info has
  master, marks and dirt rows; the existing reset walk includes them. An existing
  explicitly saved preference still runs after default.cfg; never edit player
  ftesurf.cfg. A full client restart applies fresh non-archived defaults.
- Enabled marks use a0.03125unit default normal lift, bounded0..0.125 even for
  older saved lift2. Supported `polygonoffset 1` provides raster separation.
  Lift changes reload the cached ramp mesh once; disabled marks skip setup/draw.
  Existing masks/shaders/specular, cosmetic geometry/collision and physics stay
  unchanged. New material keys avoid an already-cached old depth state.

## Diagnosis / falsifiers

FTE gl_shader.c has no depthpush keyword. The earlier apparent depth-bias setting
was ignored, leaving the large2unit world-space lift as its workaround. Actual
Shader_PolygonOffset sets unit=-25*m, factor=-0.05 and the polygon-offset flag.
Do not assume a keyword from another Quake renderer is supported.

Source-bound truth table must include ACTED ON cases, not pass by hiding all
weather:8master/map/manual combinations, masterOFF blocks manual weather1 and
forced snow2/Colin auto; masterON allows manual or authored-map positives.
BOTH Weather_Load and Frame must agree, Winter/Snow must gate before submission,
weather off/free must stop all3sound handles and clear pending flash/thunder.

`tools/test_seasonal_defaults.py` checks these source expressions/guards, fresh
config/UI defaults, old-lift bounds and disabled/live-reload ordering. It compiles
and EXECUTES the actual native PolygonOffset function with minimal type/parser
stubs: negative units/factor and the native flag must ACT. This is NOT native
rendering/audio shutdown, edge-on stability, occluder bleed or FPS acceptance.

## Verified / preserved limitations

-8source-bound truth cases pass including nonempty ON cases. Native function
  control returns unit=-25/factor=-0.05 with flag set. Native function hash
  b15ad215cb87495534889740b9b6834f98f2c056e986f2b900a733c0b9402610.
- First tiny C fixture lacked native flags fields; retained compile failure,
  corrected fixture declarations then same function passed, no product waiver.
- Existing ramp bake/blend controls4pass after updating its exact cache-key
  contract to the newly changed close keys. Original mismatch retained; its
  old v2/legacy expectation also predates the prior lift2 key. No shader bytes
  changed and no ABI/blend check weakened.
- Existing actual native sampler/colour/3xfaster-flash controls pass unchanged.
  Current-main THREE-VM working build0warnings. Clean exact-commit qualification
  and guarded delivery are recorded below after execution.
- Source baseline inspected current5ec8a9d5899eb255cfc7baa8e5e172d928b14616:
  live P1329CS1ca3a29c/QW5e8cd6d1 and P1330 native APIs. Never deploy the prior
  9b2-qualified tree, which would remove newer published peer features.
- Default.cfg is a shared ruleset with peer uncommitted edits in the primary
  install. Client component publisher excludes that file; apply ONLY the exact
  new3client-default hunk with current-byte preimages and postimage checks.
  Preserve every unrelated byte; no whole old config copy. Player config untouched.

## Deployment / owner check

Pending guarded client-only qualification and deployment. No native pins/tag,
QW/menu/backend, media, movement, recording/evidence, QC Build or public release
change. Pi must use a safe current empty/closed-writer window; occupancy blocks
that step, not independent Windows/source work. No old-cohort archive reuse.

Small owner check after delivery: Christmas0 must stop seasonal snow/sky/audio/
props even if r_weather1/r_snow2/preview2 were set;1 should restore selected
extras. On one familiar ramp enable marks1/dirt1: is the dirt flush enough, with
no grazing shimmer or bleed through a nearby occluder? Try changing lift live,
then restore marks/dirt0. Actual feedback belongs in lextest.md. No native visual
pass is inferred from source controls or owner's general positive P1332 response.
