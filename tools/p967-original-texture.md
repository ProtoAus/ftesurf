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
preserved. Final clean/pinned artifact and installed smoke below also pass.

## Delivery and limits

Native source pin/tag bd7aa1760/patch-967 changes for this engine feature;
main's overall counter retains concurrent P968. The build metadata now honors
lightweight AND annotated tags: default describe wrongly labelled this clean
source as P962+20; --tags and a Full rebuild correctly embed patch-967. The
published tag was preserved. Clean compatible role9b2db0c1 keeps the exact
seven-field Friends source; three VMs/zero warnings. Native74 existing/zero new
warnings; seven clean PEs and all five embedded plugin ZIPs validate.

Final actual socket control uses current installed QW/MENU in an owned fixture:
Original/default-T inspect/styles, alias hash and tag967 act, no QC/shader errors.
Actual seven-field producer publishes1/MENU draws1; acting empty yields0/0.
This is not linked-account/backend acceptance. Final image inspected; actors stopped.

BOTH Windows installs received the clean native set (both existing client aliases,
dedicated executables/all five plugins) and CSQC/LNO/cache24Oct2026, all21swaps
applied by13:07:11Z. Independent post-audit verifies every installed/hash/history/
prior-prev and current.prev. Current QW/MENU match the separate before-swap fixture.
An actual INSTALLED client/new dedicated pair also acts with tag967, Original
ready1/private-texture readiness1 and no QC/shader errors; own actors stopped.

- CSQC/cache1bcf7636:
  c10b50a6be24441f3415ee57c0ef2de6386ed5e6c016ca20e8b8db1fb3b24231.
- LNO:53bb58c772e9a7cc253f7accc54e8044a19265f735a1b5c5369b56d07716a30e.
- Client PE:9dabc1da825d1e3d709ea6254cf62ffbf8c1bbd1d52224e27d911c3908edefdf.
- Dedicated PE:e93338b8a84d106d1ce7f4c17addab8dcd1c37c9e01a51a1c8192fb81aa69d8a.
- HL2:f33612104f2d525662d26a75dd93da751314ef0f1101ff47b371cd8156800369.

IMPORTANT LIMIT: the tool's120s execution timeout interrupted the final broad
14,247-file preservation rehash AFTER all21swaps. The full protected before-map
was in memory and unavailable after termination. That guard is INTERRUPTED, not
a hash-comparison pass, and the transaction was NOT repeated or relabelled complete.
Source writes only declared managed artifacts/stages/prev, never config/player
data; the independent audit proves managed predecessors and QW/MENU, not the lost
full-data comparison. The promotion seam now persists its before-map before any
future mutation; it does not invent/backfill this transaction's evidence.

Pi remains blocked by the current serving admission gate; no backend cutover or
old transaction was bypassed. Owner appearance acceptance remains pending in
lextest.md. Account persistence and spectator setup/fire/inspect mirroring continue.
No Build bump or public release.
