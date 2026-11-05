# P1317 — surf_colin_blaster_69000 Christmas pass

User explicitly selected the map5Nov. This is a map-specific pre-baked cosmetic
pass, not a BSP edit or a takeover of the reserved P1287 world shader.

## Actual authored data

Inspected Strata v25 BSP:18,664,473bytes, SHA256
ce40b496c672789f3e93bf998ae45f9376e15a24d0eae58fd0f2f729caee915f.

- All103actual ALEX_GRASS_01 faces become opaque snowy terrain overlays:
  376triangles. Original materials/BSP remain intact; collision unchanged.
- 1760exposed-cap polygons/3986triangles,356roofed rejections. Fine32 roof mask
  clips cap fragments; sky, liquids, glass and steep ridden faces are excluded.
  Two static terrain draws, not per-frame traces/allocations or a new world pass.
- 16distributed snowmen/decorated/snowy trees/gifts on roomy grass edges. Spawn
  exclusion160units, spacing>=256, below runtime16prop cap. Runtime still checks
  each floor once and rejects steep/solid placements; native placement pending.
- Falling snow uses NEW map's4096x2048fine32 mask. No coarse replacement of any
  existing map's fine masks. Snow/roof lookup stays point-filtered/no mip/picmip.
- Portal sky1542triangles, cosmetic ice270triangles. The bounded256x128 audio
  field uses512-unit MAX reductions of the real fine32 heights, preserving thin
  roofs instead of missing them with coarse centre sampling. Audio is conservative
  near roof edges; it is not an exact continuous roof solver. Visual clipping
  remains fine32. Uses existing bounded sky/mist/original winter audio.

`r_colin_winter 1` defaults the automatic theme ON ONLY on this map. Display Info
has its checkbox. `r_colin_winter 0` removes automatic extras without writing
saved global weather/snow/prop settings; separately enabled options still act.
Missing profile/fine media never opts an older client into unclipped automatic
snow. Existing renderer-restart callback reloads cold Winter/Weather setup so
terrain/sky/ice force-shader handles cannot point at freed/reused materials.
No automatic holiday entitlement/date/earning changes. Existing event date gate
stays off until the owner supplies actual dates.

## Reader correction and controls

First existing roof bake timed out because legacy records were used on widened
Strata node48/leaf56v2/leafbrushI32/brushside16v1 records. Fixed the SAME snowmask
reader against engine mod_vbsp.c layouts; index, stride and cycle guards make
unknown/malformed input fail closed instead of an unbounded walk. No owned bake
process survived timeout. The changed-source existing weather entrypoint then
processed the actual map successfully before the rest of the proof campaign.

Legacy/Strata concrete-only no-sky negative fixtures correctly generate no mask;
actual map supplies positive roof/sky domain; cycle fixture refuses. Thin-roof
reduction positive/old-centre-miss control and scoped no-global-cvar-write checks
pass. Existing4rendering+3weather checks pass. Fixture failures remain retained;
no fake PNG pass and no expanding substitute map generator. All3QC compile with
zero warnings. Source/math/geometry is NOT native appearance, sound, placement
or a numerical FPS acceptance pass; those remain human/native pending.

## Delivery contract

Main keeps the published feature ancestry. Actual deployment is ONLY1315+1317
visual deltas on the inspected fleet-qualified P1313 base, not the separately
pending P1314 TAS/native candidate. Native pins/tags/build unchanged. Generated
manifest binds the actual winter_theme.py source and all7runtime files (5map
model/roof +2fine32mask) by full hashes. Source media contains the authored prop
manifest, original snow grain and snow shader. Existing dual-Windows publisher
accepts only those typed fine32 exceptions and protects all old fine-mask hashes.

## Actual delivery — 5 Nov2026

- Qualified/source-published commit `a79d2ec91fc66a3d7750c0eb7f6319d29ea0a494`
  (`winter-visuals-1317-qualified`) contains ONLY the P1315/P1317 visual deltas
  on the fleet-qualified base. Functional patch identity matches main feature
  `08d49bb9`; main merge `df0179dd` and journal merge `ee92a6794` were pushed.
- Both Windows installs: actual publisher UTC `2026-11-05T08:05:22.6798973Z`,
  all92destination hashes exact;20native/config+12old fine-mask files unchanged.
  Both client download-cache seeds `fb96bebd.dat` match frozen CSQC SHA256
  `93ada3708121bb55e03ea908cbcb5c110933ece064beba7184171f1b3233d9e8`.
- Pi: final single progs-only activation `2026-11-05T08:59:22.680947+00:00`,
  ALL12restarted/0skipped,53explicit runtime media/data files read back, backend/
  native/plugin/config unchanged. QW bytes were already identical.46638old
  protected paths unchanged,3new files, no protected change/loss. `.prev` progs
  and previous media remain. No menu/default.cfg/client-local warmseed shipment.
- Before ANY canonical stage/restart,8parts/2821850bytes AND complete180resume
  payload/ms/state files/226269873bytes plus stat metadata/cleanup source were
  archived and every member rehashed ON/OFFBOX. The locked action boundary
  consumed this full proof with12actual native actors+1backend actor; no open
  parts/resume FD. Synthetic positive/new-deleted-resume-FD, change and alias
  controls acted; no general-filewriter-audit or exact-expiry claim. No old-data
  restore, old failure regrading, blanket exclusions or extra healthy restart.
- Existing client-code catalog56->57, prior bytes retained, no backend restart.
  Independent direct health HTTP200: `ok=true,lobbies=12`. Original failed
  anonymous checksum observations remain failures: status1024-byte late-key
  truncation and empty getinfo body; no served-checksum/native-frame pass inferred
  from them and no deployment repeated. Actual producer/hash/process/data/health
  proof is separate. Native appearance, sound, placement, save2 and numerical FPS
  remain pending in lextest.md; no "looks right" or MAX-FPS measurement invented.

All destination/source/cache/catalog/fleet claims above come from actual producer
receipts; raw data and preimages remain private. Full parts AND resume preimages must be captured
before the FINAL combined Pi restart; no healthy double rollout of1315 then1317,
old-data restore, skipped-unit blanket pause, or original-failure regrading.
