# P1332 — native snow binding and faster lightning

## Owner acceptance and predicted correction

Owner reports Colin snowy grass is black and asks whether snow relief should
exist. Owner says flashes LOOK GOOD but individual flashes are too slow. Record
that as human flash-appearance confirmation only, not FPS/timing/snow acceptance.

Existing Colin snow caps are shallow2..5unit uneven meshes with boundary rims,
not large terrain displacements or collision changes. Keep that geometry intact;
repair its material bindings before inventing new snowbank coverage.

Prediction: native clampmap then map leaves snow sampler1 unbound. Two ordinary
map entries must produce distinct roof0/snow1 bindings. Native #usemods must
permit GenerateColourMods before vertex attribute binding; exactvertex/vertex
alpha must use the existing IQM colour VBO directly, not a second relight or CPU
colour expansion. A distinct runtime material key avoids a cached old material.
Pulse/gap/fade must scale together by1/3 to preserve existing peak/shape while
keeping3..6strokes and thunder delay after the final stroke unchanged.

## Root cause and implementation

FTE Shaderpass_ClampMap does not call Shaderpass_DefineMap. A program begins
with numMergedPasses0; the subsequent map increments it to1 and overwrites the
first texture. The P1327 isolated WGL helper injected BOTH textures and gl_Color
directly, so its passing pixels never exercised this native material assembly.
That earlier arithmetic result remains valid, not a native appearance pass.

Winter_Surface now uses `map $clamp:$nosrgb:$nearest:...` then the mounted snow
albedo map. #usemods enables colour generation/binding; exactvertex and vertex
alpha select the native direct-VBO fast path. New snow_v4 runtime material keys.
No shader file, texture, model, terrain, physics, dynamic light, audio recording,
backend, evidence, native binary/pin/tag or QC Build change. Client program ONLY.

Lightning duration50..150ms becomes16.7..50ms; dark gap60..340ms becomes20..113ms;
fade denominator120ms becomes40ms. These are source schedule ranges, NOT measured
native frame timing. Flash exposure shape,3..6count, eight-second repeat preview,
ordinary interval and post-final thunder0.8..3.1s remain unchanged.

## Verified

- `tools/test_winter_binding.py --engine <checkout> --gcc <ucrt64/gcc.exe> --out <owned-artifacts>`:
  compiled/executed the THREE ACTUAL native map/clampmap/DefineMap functions,
  stubbing texture I/O/tokenization only. Old control ACTS:1slot, overwritten
  roof0, snow1 unbound. Corrected subject ACTS:2slots, roof0/snow1 distinct.
  Native snippets hash efbf710640f154c341ec350b728cf2b7b46ff76ba6fd0cdb51fe019f7c1242b7.
- Source-bound native colour gate/direct-VBO checks pass. Pulse/gap endpoints
  and interior samples exactly1/3; matching fade/count/thunder guards pass.
- Existing updated winter-lighting suite passes: actual shader light/dark,
  roof/cull negatives, stored normalized nonzero IQM light, cap skirts, mounted
  material/footstep references and all3finite Vorbis PCM controls. No asset changed.
- Qualified THREE-VM NoDeploy build0warnings, inspected compilerc24ede65af01.
  Actual candidate CSP f6ead0e677f1bac29fe005c172989254d03e032561e7530389c82e13a69c6659.
  QW/menu outputs are build controls ONLY, not deployment inputs.
- Initial edits based on stale broad excerpts refused without changing source;
  reread actual small source regions before the corrected edits. No failed
  parser/GPU/native arm regraded. Gameplay appearance/listening/FPS still separate.

## Delivery and next small owner check

Delivered5Nov2026: feature `d231e515f979493ea1864e7d8004785ab2d41d2c`,
qualified `9b2ba43a4470e7e3ca9880847dd2739df7a4b722` on the released native/API
base. BOTH Windows19:05:06UTC: client DAT/LNO only,4targets exact,41protected
native/server/menu/config/fine-mask paths unchanged at publication; both caches
seeded as b11ea2a0.dat. No runtime media delta.

ALL12lobbies19:13:56UTC: original client-only transaction exit0,12new epochs,
zero skipped. Independent readback19:14:35UTC verified exact current epochs,
client/predecessor and held native/server/menu/backend; previous8media remain
exact. All47,452pre-existing protected runtime entries unchanged; direct
health200/ok/lobbies12 and maintenance-lock release verified. Fresh source/stat-
bound current preimages were verified ON/OFFBOX before canonical staging.
No second activation/recovery restart, native/server/menu/backend/media/config/
physics/evidence/Build change. Ordinary beta delivery, NOT a published release.

After delivery/reconnect: is the SAME Colin grass patch visibly snowy rather than
black, is a nearby cap rim visible, and are flashes now quick enough? Existing
`r_weather 1; r_weather_test 2` previews; test0 stops preview. See lextest.md.
