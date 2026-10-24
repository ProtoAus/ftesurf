# P967 — installed Legacy Original/default-T texture

## Problem and prediction

The installed CSS and Legacy games use the same knife_t diffuse filename with
incompatible layouts. Low-priority Legacy mounting must not change CSS globally.
Predict: a fixed private Legacy-only alias reads Legacy's bytes while the ordinary
name keeps reading CSS; Original/default-T render without incompatible stripes.
An unmounted alias must refuse, not silently find CSS. No blanket UV flip or
licensed asset redistribution.

## Implementation

Native `FS_FLocateFile` recognizes one exact read-only texture name, only inside
the existing fixed Legacy session mount family. It bypasses the ordinary highest-
priority cache for this lookup, preserves security/pure restrictions, matches the
resolved family at the beginning/path boundary, and has no generic fallback.
Readonly/no-save readiness resets with FS lifetime and is set only when the fixed
helper locates the texture. There are no caller paths, arguments or new mounts.

Opted-in Original/default-T wait for readiness and use that diffuse for Original
under a lit preview shader and for Fade/Web/Marble. Unrelated roots keep their
material names. The small readiness bit participates in the material cache key.
Older native clients warn instead of claiming to support the fix. This does not
reproduce all Source phong parameters or turn template paint into inventory skins.
Server protocol, movement, holds, evidence and account settings are unchanged.

## Acting controls

Existing Jobs8/NoDeploy entrypoint builds three VMs with zero warnings. Native
subject adds zero warning classes against the current clean-source baseline's
74 existing compiler warnings. clangd retains two pre-existing fs.c diagnostics;
QuakeC is checked by fteqcc/runtime, not clangd.

Actual dedicated socket/client on surf_666, isolated saved state and no run
submission: with viewmodels disabled, readiness is 0; console attempts cannot set
it; helper extra arguments refuse; flocate alias reports Not found. After the
fixed helper, readiness is 1 and native fs_hash reads:

- Legacy alias, 1,398,360 bytes:
  `3c7eeb1a4d36e710e4279830f0d3bf958eacb249f7fa157def33776dd748ef11`.
- Normal filename, CSS 87,528 bytes, before AND after:
  `dc4c6cef8c350cb1d1f97cbff773ea9643f677180cc21521e66cf1775e01bea8`.

Original/default-T inspect, CSS, Talon and Original Fade/Web/Marble controls act;
images show coherent Original texture and lit skin/cloth under normal/red light.
No QC/shader errors. Owned actors stopped. An initial 242-byte bridge command was
refused by the documented 240-byte stdin limit before execution; it was shortened,
not counted as renderer failure or pass. Final unchanged-root material names are
preserved; final clean/pinned-artifact smoke remains a separate gate.

## Delivery and limits

Native source pin/tag changes for this engine feature, while the overall patch
counter retains concurrent P968. Final clean artifact/dual-Windows promotion is
not implied by implementation/control success. Pi remains blocked by the current
serving admission gate; no backend cutover or old transaction was bypassed.
Owner appearance acceptance remains pending in lextest.md. Account persistence
and spectator setup/fire/inspect mirroring remain requested follow-up work.
No Build bump or public release.
