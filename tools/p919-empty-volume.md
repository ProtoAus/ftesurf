# P919 — bhop_goldsrc2 empty illusionary collision parity

Engine 0265ae46068d633e9779182f48a140f1c9bf2517 / annotated patch-919.
Owner control: save 2 / slot002 at 15:47.230 gave large vertical corrections,
repeatedly 8/16 units. This is real reported behaviour, not an invented test pass.

## Cause / prediction before editing

Read the mounted map: *93 func_illusionary is a thin sheet at 3638 -6200 10047,
local bounds -136 -2 -18 .. 136 2 18; it explicitly authors skin=-1. Such skins
are legacy contents overrides. Server snapshot encoding deliberately sends
negative-skin volumes as BSP. AddEntityToPmove already maps Q1CONTENTS_EMPTY to
nonsolid, but client CL_SetSolidEntities omitted EMPTY and kept a solid physent.
The client therefore tried colliding with a sheet the server correctly ignores.
The CSQC glare occluder copies were inspected but are not in this native body
physent list; do not change visual occlusion or make decorative brushes solid.

Minimal fix: add that one client case. Predict equal EMPTY classification,
unchanged ordinary/ladder/fluid cases, no body/eye collision for the empty sheet.

## Verified / limits

- A compiled probe wraps the ACTUAL old client, new client and server switches,
  using actual bspfile contents constants. Old EMPTY mismatch acts; nine cases
  pass with unchanged other mappings. Initial harness macro extraction missed
  an inline comment in a constant name; fixed the extractor, not engine code.
- Five native real hull-trace controls at the authored sheet geometry: old solid
  classification demonstrably starts stuck, nonsolid is clear, full fraction,
  no false roof duck, body origin unchanged. All prior native selftests pass.
- Native build and clean stamped rebuild client/server/plugins pass; no new
  warnings versus inspected P918 source. No new server physics, mover version,
  evidence/recorder eligibility or global error smoothing.
- This does not claim a measured real-socket zero-correction run. The owner's
  small save2 walk/jump check is explicitly pending in lextest.md.

Client deployment/readback recorded after the clean artifact swap. The same
existing v11 server protocol is compatible; no Pi restart is needed.
