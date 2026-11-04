# P1307 — ramp shader asset ABI and provisional bake delivery

## Problem / change

The ignored compiled progs and tracked source assets can advance independently
in a development install. P1295's qualified85254ea5 CSP expects a full multiplier
and filter blend; P1300's shader outputs half the multiplier for double modulation.
One filename/material identity is unsafe across those cohorts. Actual pre-copy
Windows assets had already advanced to the half-output source while the installed
progs were still P1295. That preimage is retained; it is NOT the legacy authority.

Keep `glsl/ftesurf_rampwear.glsl` EXACTLY the qualified852 source, and put the
unchanged A84 modern shader in `glsl/ftesurf_rampwear_v2.glsl`. At map load the new
CSP probes v2 readability and selects its matching program+double blend, otherwise
legacy program+filter. Separate `ftesurf_rampwear_v2/<map>` and `_legacy/<map>`
material keys do not accidentally reuse an earlier cached stage. Old CSP still
uses the legacy filename. No new per-frame file access, draw pass, texture sample,
trace or light. This is an asset/output/blend contract, not a new evidence format.

## Checks and limits

-Exact legacy852 SHA256:7b350f403958e031fe0b7d780671de1a293c2e4146602945b611b0abe9daaee4.
-Unchanged modern A84 v2 SHA256:7c61c929b87764a1b656831d390a62b6b8182d47c37266ea9153b0c1729a8668.
-Existing3 seam/atlas/strength controls pass; the added source-contract control
  verifies those frozen bytes, selector/cache-key/blend source and the four
  old/new client/asset pairing equations, including an acting mismatched-brightness
  negative. This is SOURCE/MATH evidence, not native renderer execution.
-Actual c24ede65 compiler builds all3 programs with zero warnings.
-Native shader appearance, inspect sound, Milk sky and moving-view frame time
  remain pending. The prior runtime quiet/4096MiB guard refusals remain failures;
  no numerical MAX-FPS, no-hitch or all-map visual pass is inferred.

The existing cache seeder no longer deletes arbitrary `.tmp`/`.dcl` downloads.
The actual old helper seeded a synthetic cache but removed both owned pending
sentinels; the changed helper seeds the same content hash and preserves both.
Real two-install seeding preserves other hashes and pending work. This is a small
required publication safety seam, not permission to clean another client's cache.

## More replay-driven bakes

Actual existing local Momentum inputs, all readable/judgeable, no new online
downloads and no player-data writes:

| Map | Replay instances | Boardings | Overlay triangles |
| --- | ---: | ---: | ---: |
| surf_colin_blaster_69000 |77|780|652|
| surf_classics3 |70|366|1831|
| surf_frost |2|48|62|
| surf_simple_v1 |125|258|361|
| surf_garden |41|205|2298|

Total315 replay instances, NOT unique players. All have nonzero scratch masks
and chart contacts. Current output is generated with the existing `tools/rampwear.py
--map <name> --gamedir <owned staging>` entrypoint; raw demos are not copied or
modified. Colin's two installed BSP hashes differ, but the actual complete
eligible normals/vertices/triangles compare equal; no map was overwritten.

Christmas10 demos/561 boardings also bake successfully:8024 triangles, or5840 with
one neighbour ring. Both stay STAGED, not default-shipped while moving-view sizing
is unmeasured. Bluewinter has0 local inputs; no empty successful bake is claimed.
The hypothesis that zero-mask neighbours are identity draws was rejected from
actual shader source BEFORE code: zero ride wear is fully dirty. No fake no-op
pruning or shader-cost claim was implemented.

## Separate delivery states

P1304 backend02a56b32f0d0414a0a42cb421cee30d488704951 is live since4Nov21:03:22Z:
core26/event component1, old schema/count/identity preservation accepted, eventOFF
and zero early gifts. Existing Linux producer acceptance and `/health` are the
sources of truth; system surfd and USER momrequests are healthy. A consistent
private historical DB snapshot and same-DB rollback cohort are retained. Never
restore the old DB to roll back code. No private output/identifiers are published.

Both Windows installs previously received A84/c24ede65 candidate progs+assets,
with exact hashes, rollback copies and unchanged native/config. P1307 and its
bake destination hashes/provenance are recorded only after actual publication;
source publication, compilation, installation and visual acceptance are separate.
No native pin/tag, QC Build decision, movement or recorder change.
