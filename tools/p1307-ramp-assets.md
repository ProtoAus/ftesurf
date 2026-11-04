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
with exact hashes, rollback copies and unchanged native/config. Final P1307 C95 candidate installed BOTH Windows at22:05:23.7571741Z,4Nov2026:
70exact copies (6program/LNO+19source assets+10baked files per install), both old
and prior.prev retained,20actual native/config hashes unchanged. Safe helper seeds
both `e1e7ee6a.dat` caches with exact new CSQC bytes, preserves pending downloads.
Peer independently upgraded nativeP1306; this operation did not overwrite it.

Pi source/baked29assets read back, then exact QQ2 promoted22:42:09.227204Z:
all12empty lobbies restarted,0skipped, NO FORCE. Eight actual recorder parts,
2,821,850bytes, were individually rehashed ONBOX+OFFBOX BEFORE canonical staging;
strict13actor/FD/exact-part checks repeat at the real locked boundary. All46300
protected old paths unchanged,0new, config/native/backend preserved, lock released.
Current/.prev and actual process/native/plugin readiness pass existing producer;
known `/health` returns200 afterwards. No optional observer failure is regraded.

Actual clean/current c24 builds all3VMs with zero warnings; fresh final C95 output
matches frozen code. Full program identities:
- QW eb0135778b73ec7d9c60caf60f90ba3f2448f6aa246114e77966cc2adc0ae5d9
- CS fae924336e042c4578eb8571851690f8eca9c7d068ce975fa7bf72578930e840
- Menu464c0a9bb3076f9caff7e105ddf45724a1ca107a2f065b25665c4a9698691596

Exact CS identity added to existing catalog52->53 preserving every prior byte.
This is code admission, NOT an actual ranked run or native visual/FPS acceptance.
Original sources/receipts/predecessors retained in owned task roots; raw recorder
archives and actor details stay private. Source publication, compilation, install
and visual acceptance remain separate. No release, native change by this task,
QC Build decision, movement or recorder change.
