# P1162 — scoped noclip candidate (not installed)

Two owner reports: noclip judder below host_timescale1 and the walk-key/wheel
speed adjustment working privately but not in lobbies. The high-speed flicker
was confirmed noclip-only; do not widen the fix to normal movement.

The code uses the existing slow-practice presentation path with finite fast-flight
bounds, preserves Source noclip velocity outside the walking cap, and sends an
individual bounded native cl_noclipspeed userinfo preference instead of changing
the lobby's global pm_noclipspeed. Unsupported servers retain the fallback;
nonzero local seats do not mutate the primary local preference. Real placements
reach both native consumers and the default streamed CSQC body/spectator serial.

## Delivery baseline is actual installed source, not main

- Native base: P1158/tag793ee161a9baa8ba976f1f426e19bfd10c5d877a.
- VM base: P1160 backport84a8ff1a925f3ebda8f681c76387279ac6670472.
- Native candidate:520ba3ca9902f0759fc0c9e5f691bf13ba55fd9e.
- Same owned pair on deliver-noclip-1162; full-main integrations kept separately.
- Both Windows three-program hashes were actually read and match the P1160
  record in profile-inventory-p1160.md. Inventory source is retained; its backend
  remains separately blocked and is not activated here.
- No pending P1154/P1161 VM or P1161 decoder activation. No physical mover,
  native API epoch, recorder format, practice/ranking policy or qcbuild bump.

All nine native runtime files equal the reviewed candidate. Native pm_source.c
and sv_tas_rewind.inc remain the installed P1158 baseline. Nine QC runtime files
backport cleanly; one test-only conflict takes the reviewed full sourcepractice
fixture, retaining controls for already-installed roof-camera behavior.

The held-source native preference/presentation controls and eleven-scenario
native-QC-VM stream regression pass. The old stream source fails29 assertions
with continuous/walking/same-origin/reseed controls acting. Transport, roles and
arrival/render clocks are controlled; this is not real CSQC network dispatch,
GPU, owner feel or canonical world movement. Original harness/global/plugin and
compile-order failures remain in the owned task. The actual code closures must
be bound to the scoped final images before delivery is claimed.

Header-full seven-image build is required by client.h helper declarations even
without a public ABI bump. Final source/tag, both-platform/native/legacy/role
acceptance, protected data/config/parts preservation, exact installation/cold and
human feel are distinct pending gates. See lextest.md; do not ask for an owner
retest before installed files really exist. Nothing in this document is a live
Windows, Pi, backend, public release or human-acceptance claim.
