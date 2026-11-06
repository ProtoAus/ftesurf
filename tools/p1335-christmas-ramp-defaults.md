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
  Current-main THREE-VM working build0warnings. Clean exact-commit C4 and D911
  qualifications each0warnings; dependency/promotion details below.
- Source baseline inspected current5ec8a9d5899eb255cfc7baa8e5e172d928b14616:
  live P1329CS1ca3a29c/QW5e8cd6d1 and P1330 native APIs. Never deploy the prior
  9b2-qualified tree, which would remove newer published peer features.
- Default.cfg is a shared ruleset with peer uncommitted edits in the primary
  install. Client component publisher excludes that file; apply ONLY the exact
  new3client-default hunk with current-byte preimages and postimage checks.
  Preserve every unrelated byte; no whole old config copy. Player config untouched.

## Deployment / owner check

## Installed Windows and all lobbies (6 November UTC)

Feature `c4cfebabe7df2eaef1aebdb2663cd4b8393d487f` is published on
winter-defaults-1335-qualified. Main `d911930d4524022e937a7fa216c0a32829b8222c`
merges it with concurrently published P1336; both features/notes retained and
patch maximum1336 preserved. Initial non-fast-forward refusal and old-base/
PowerShell-quote failures retained, never claimed as candidate qualification.

During preparation another session advanced BOTH Windows to QW66a6dcd1 /
CSb639d68f (P1336), while lobbies still run QW5e8cd6d1 /CS1ca3a29c (P1329).
The predecessor guard refused the original C4/b7d67c22 Windows candidate BEFORE
staging. Do not simply rebaseline that candidate and downgrade the newly live
pair. Instead clean-build D911: QW66a6dcd1 EXACTLY matches the new live server;
our five seasonal/ramp modules EXACTLY match C4. Other VMs are controls only.

BOTH Windows installed6Nov02:50:08UTC: ONLY client DAT/LNO,4targets exact,
41protected paths unchanged. CSP117d627ace2dff49c1400a9d4c426b940ba18d7959827f56b5a8c72adcec11cf;
both caches e760cdcc.dat seeded. Known-source client catalog64->65 preserves
all previous rows for this installed Windows body, without a backend restart.
Source D911 contains committed P1336 code
because that pair was already installed, not an unapproved peer-work release.
Two exact4line cosmetic-default insertions separately verified ALL other bytes
unchanged against current shared-config preimages. Initial CRLF expectation
refused without rollback; actual original and resulting files were both LF,
and exact-byte comparison with the LF hunk passed. Archived player cfg untouched.

Pi delivery completed6Nov03:37:10UTC: original Pi-compatible C4/CSPb7d67c223057;
QW/native/config/backend unchanged,12new actors,0skips. User's6Nov policy makes
warning/countdown/restart default even when occupied. A bounded runtime-only
join hold allowed normal disconnect AFTER10seconds, final save/closed-writer
capture, all-member ON/OFF-box verification, then guarded promotion. All12join
capacities restored; no maintenance gate. Pre-warning captures and original
occupied-window refusals retained. Local180second SSH wait expired but on-Pi
activation completed; read-only observation verified receipt and actors, with
NO repeated swap/restart or relabelled timeout. Protected47680files unchanged.
Fresh no-local-CS lobby client downloaded exact b7d67 hash, board drew, no QC
error, screenshot inspected. This is not human Christmas/dirt acceptance.
DO NOT cross-pair this Pi QW with newer Windows CSP; current-pair guard remains.

No native pins/tag, QW/menu/backend, media, movement, recording/evidence,
QC Build or public release changed by this task. Fleet delivery is complete;
native visual acceptance remains manual.

Small owner check after delivery: Christmas0 must stop seasonal snow/sky/audio/
props even if r_weather1/r_snow2/preview2 were set;1 should restore selected
extras. On one familiar ramp enable marks1/dirt1: is the dirt flush enough, with
no grazing shimmer or bleed through a nearby occluder? Try changing lift live,
then restore marks/dirt0. Actual feedback belongs in lextest.md. No native visual
pass is inferred from source controls or owner's general positive P1332 response.
