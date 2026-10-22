# P933 compatible Friends deployment source

Parent: published 2ec1792344e9fc63eebebdf67530590a9713c083, the P931 REC13
fleet variant. Read-only live SHA256 checks match its qualified e7c8a664... /
11701c87... pair exactly. Mainline's independent producer hold is NOT bypassed.

This variant applies ONLY P933 mainline f5826963's hunks in:
- src/server/sv_social.qc
- src/client/cl_friends.qc
- src/client/cl_menu_friends.qc

These files are identical to P933's corresponding source. Every other source
file, including the recorder/timer/producer, is unchanged from the exact live
baseline. ENGINE.txt only marks the compatible P933 scope; native pin remains
P924's required CLIENT API and existing lobby native/producer is retained.
There is no schema, recording policy, run-class, native interface or evidence
format change. P932 cross-source playback is NOT included by this variant.

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
