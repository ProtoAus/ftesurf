# P926 — rotated trigger prediction matches server geometry

## Cause and acting control

The owner's surf_me save9 was read without modifying it. Only its numeric body
origin, zero velocity and view angles were used for a fresh isolated actor;
no identity, saved run or clock was copied. A no-destination zone reproduces
that origin through normal zone_goto (bottom+2), with no movement/look input.

surf_me has ordinary trigger_teleport entities, not linked_portal_door. Its *32
brush targets tele4 and has authored yaw-180. The client parser read `angles`
but never assigned them to its probe entity. It also culled against unrotated
local mins/maxs. The server retains the authored rotation and links world bounds.

With native source/tag P924, real dedicated socket,100fps, normal extrapolation,
cl_prederror.25 and predicted triggers ON, the original mirror ACTS: it fires
tele4 around.8seconds before the server, with four4205..4257-unit corrections.
It resets pitch/yaw to0 at that false hit, then misses the real crossing and
gets a5352-unit correction there. With prediction OFF, the early turn disappears
but the expected late unpredicted crossing remains. This distinguishes the
reported view discontinuity from the map's legitimate final destination angle.
An initial.48second probe ended before crossing and is NOT the acting evidence;
the longer original logs are retained. Mouse sensitivity/pitch/yaw were zeroed
for the final positive/subject comparison so a background physical device cannot
change the no-input premise.

At the measured early body point the old trigger probe returns startsolid1.
The subject returns startsolid0/allsolid0/fraction1 at that same point. The
subject later fires one real teleport and native angle debugging reports the
same command sequence for its predicted snap and server acknowledgement. No
false-teleport or unpredicted-real-crossing correction remains. The expected
zone-placement correction and an unrelated sub-2-unit slope correction remain
explicit; this patch does not claim all movement prediction is error-free.

## Change and scope

Set the parsed angle on the probe before setorigin, then use its engine-linked
world absmin/absmax for the broad phase. This reuses the same brush/link behavior
as the server rather than inventing rotated-corner math or suppressing view
snaps. Existing server-authored destination angles, masks, filters and gates
are unchanged. Named zone-tool boxes retain their existing shaping path.

Client QC only: no physical server, evidence writer/reader, held qualification,
coverage, ranking policy, native source/tag pin or qcbuild change. Three product
VMs compile with zero warnings. QuakeC's LSP result is not used as compile proof.
P924's reader864/0 and byte-identical-reader corpus evidence remain valid because
this change does not touch those dependencies. The committed clean build at
`0d3f0e672e59529ed88e901388ee3ce101e6895f` compiles0/0/0 warnings and its CSQC is byte-identical to the acting
subject. A fresh, fully spawned classics socket also carries37.5 units in the
first.25seconds with no post-placement above-.25 correction. The earlier chained
map-load auxiliary probe had no acting carry and is retained as invalid, not a
regression pass; use the fresh-start proof instead.

## Delivery and acceptance

Installed in both Windows copies on22October2026 UTC after the earlier guarded
attempt refused the owner's running game. The later published P932 CSQC update
was preserved and the installed combination checked; [delivery](p931-delivery.md)
records exact source, hashes and acting proof. Owner acceptance is still pending.

The P922-based compatible variant2ec17923 is now deployed on all12Pi lobbies:
normal12row/zero-player guard, exact hashes/.prev, unchanged native/plugins and
positive cold-cache live-client smoke. Mainline's producer gate stays separate;
no force or partial promotion was used. P924 native/API is required on the client
for the combined conveyor feature, not for this old angle/link API.

Small owner check after matching delivery: load surf_me save9, touch no controls,
and confirm there is no early view reset during the fall; the actual map
teleport may still turn you to its authored destination. Pending in lextest.md.
