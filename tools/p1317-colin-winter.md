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

All destination/source/cache/catalog/fleet claims require actual producer
receipts, not this document. Full parts AND resume preimages must be captured
before the FINAL combined Pi restart; no healthy double rollout of1315 then1317,
old-data restore, skipped-unit blanket pause, or original-failure regrading.
