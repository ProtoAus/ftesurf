# P933 compatible Friends deployment source

Parent: published 2ec1792344e9fc63eebebdf67530590a9713c083, the P931 REC13
fleet variant. Read-only live SHA256 checks match its qualified e7c8a664... /
11701c87... pair exactly. Mainline's independent producer hold is NOT bypassed.

The initial ae3eb28f candidate applied ONLY P933 mainline f5826963's hunks in:
- src/server/sv_social.qc
- src/client/cl_friends.qc
- src/client/cl_menu_friends.qc

These files are identical to P933's corresponding source. In initial ae3eb28f,
every other source file, including recorder/timer/producer, was unchanged from
the then-inspected live baseline. ENGINE.txt only marks the compatible P933 scope; native pin remains
P924's required CLIENT API and existing lobby native/producer is retained.
There is no schema, recording policy, run-class, native interface or evidence
format change.

## Forward preservation of the concurrent P932 rollout

The first standard P933 -Pi swap succeeded at an empty12-lobby boundary, but
postflight found csprogs.prev48beec2e rather than the earlier11701c87 snapshot.
It exactly matches the peer's committed P932 compatible artifact240440a4: their
CSQC advanced during preparation. The Friends-only candidate temporarily
omitted that newly-live client feature. Do NOT claim that as complete delivery.

This forward combined candidate additionally applies only the SIX client-source
hunks from already-published P9323a8d2427. Those six files/include order are
identical to the peer's qualified240440a4 source. P933's three Friends files stay
identical to publishedf5826963. All other source, especially every SSQC
recorder/timer/producer file, stays unchanged. Combined three-VM NoDeploy build
has0/0/0 warnings; SSQC remains byte-identical to the initial P933 candidate.
Existing acted P932 policy/cache/playback controls and P933 social controls apply
to unchanged functional files; a new full runtime matrix is not invented.

Use the combined candidate for the next ordinary empty-fleet promotion and
verify the actual immediately preceding pair again. Preserve both features;
never restore an older full variant just to obtain one desired client module.

Standard build.ps1 -NoDeploy -Jobs8 compiles all three VMs at zero warnings.
P933's existing 44 social API/privacy/expiry/rollback controls cover the exact
activity/transport implementation. Existing P931 compatible native/prediction
qualification remains applicable to its unchanged source; this is not invented
new movement or producer qualification. Real-account stage/bonus UI acceptance
remains pending in mainline lextest.md.

The seven-field CSQC adapter and server refresh capability are backward-compatible
with the independently delivered Windows menu; the legacy menu built here must
NOT replace either Windows install. For fleet deployment use standard -Pi with
-QuakeDir pointing at an owned shallow artifact sink, not C:/FTEQuake. Leave all
real Windows binaries/progs/config/player data at their mainline versions.

No deployment is claimed by this source report. Before promotion recheck the
exact live baseline pair, empty fleet, source status and native hashes, preserve
.prev with the ordinary builder, then verify destination hashes/live readiness
and record UTC. Backend activity also requires the separately guarded compatible
social.py successor; code publication alone does not provide live stage status.
No maintenance gate or collection activation is used during preparation.
