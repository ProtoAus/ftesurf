# P1169 — larger native Maps filters and unzoned-map roster

## Implemented

Only the main-menu Maps filter strip changes. Labels use16 requested units and
headings20, through existing `sui_native_text` physical font mirrors rather than
legacy12/15 shadowed text. Keep `ui_font_cur` on the legacy face for bake lookup,
measure with the same snapped physical mirror as drawing, then restore the
legacy UI font. Buttons are32 high with40 row pitch; mode-switch width derives
from the two measured labels. Groups wrap without overlapping search/list/footer.

Tier, Surf/Bhop, Library, Extra and Sort IDs/actions remain the same. No global
font/HUD restyle, changed filters or sort policy, engine ABI/pin/tag, SSQC/CSQC,
physics, account, zone/tier, backend, Build or release change.

## Verified

- Untouched public baseline and changed-source official three-program NoDeploy
  builds: zero NEW warnings. Menu/server0; same two existing client F333 warnings.
  Both SSQC and CSQC artifacts are byte-identical; menu changes.
- Same native-image fixture control/subject. Actual1280x720,1920x1080 and900x600
  captures were read: enlarged sharp filter labels/headings, wrapped groups,
  search/list/footer reachable. Native requested sizes use the existing baked
  ladder and physical-pixel alignment; this is not a new renderer/font contract.
- Existing `ui_bootcheck 2` ACTED tier3 and Bhop stages: fixture views1052 ->291
  tier3 and506 Bhop, matching the unchanged control. Offline synthetic fixture
  version1 is NOT owner consent/acceptance and is never copied to an install.
- First control drew only terms; original images retained, then the SAME owned
  fixture was explicitly made offline-only. Two attempted queued-command input
  arms reached the builtin menu before custom-menu initialization; original
  logs/images remain failed coverage, NOT actual click passes. Stopped that
  approach and used the existing known-working bootstrap driver. Library/sort
  callbacks/IDs are source-inspected, not claimed as actual hit-test acceptance.
- Owner appearance/size and click acceptance remain pending in `lextest.md`.

## Adoption scope

Client-local `menu.dat` and matching `menu.lno` ONLY, in BOTH Windows installs.
No menu.dat is ever a lobby ship item. The inspected prior menu/LNO in both
installs initially matched the public P1168 fba5b68f delivery AND the untouched
control build. At the actual mutation boundary BOTH had changed to an unbound
menu6f8760a5/LNOa70ad3cb; the guard refused BEFORE any install copy. The separate
P1168 reader owner also preserved that same concurrent menu. One bounded clean
public-canonical1d0 control build did NOT match it; checked active-producer
artifacts did not match either. This is NOT source binding or a successful rollout.
All8 actual current/.prev MENU files have a read-only rollback archive with each
member rehashed. Installation remains BLOCKED on the actual menu writer's
source/build handoff, or an explicit owner decision to supersede just those4
MENU/LNO files with the qualified candidate while preserving that rollback.
Never silently weaken the original guard or infer owner approval from testing.
Preserve `.prev`; verify destination hashes and protect actual newer
SSQC/CSQC/native/configs when adoption becomes authorized.
Use the existing build's Deploy helper narrowly; never default-deploy all progs
or restart lobbies for this change. ONLY AFTER adoption, reload with `menu_restart`.

Qualified source is public `e2a03eee6bcf81295a6be98a5adc92f28d3fac7f`;
subsequent peer adoption/status changes are docs-only, not a changed menu input.
Frozen candidate (not installed):

| File | SHA-256 |
|---|---|
| menu.dat | `b63095a727f41642cbd6797a8b81e4a67fa86620d324ef8b5b3574fd10f7cd48` |
| menu.lno | `cca6bc18f13280563ca4b3657a4e10bb7567a7458e43168c86aea2b0cdc6ff9f` |

## Dated unzoned-map list

The requested1Nov2026 snapshot is supplied as
`C:/FTESurf/unzoned-maps-2026-11-01.csv` (Excel-friendly UTF8/BOM) and the matching
Markdown list. It is a dated report, not a zone/tier edit or a live feed.

All2179 live catalog names exactly reconcile to all2179 held Surf/Bhop BSP
names.1601 zoned maps are excluded;578 unzoned are included,515Surf/63Bhop.
461 are explicitly KSF;117 have unattributed library metadata and UNKNOWN tiers
(54Surf/63Bhop). Current and independent KSF/Momentum ratings remain separate;
zero/missing ratings are UNKNOWN, never invented. Exact `_css`/other build names
stay separate; maps outside the active pool remain in the list. An optional
blank review-tier column is supplied for the tiering review.

Unzoned means the live server's explicit zoned0, NOT absence of a tier, thumbnail
or imported board. Server-recognized embedded timers count as zoned. Positive
control `surf_eclipse` is present, zoned and excluded. Every CSV row/UNKNOWN and
all grouped counts round-trip to the frozen map-list snapshot. This covers the
held FTESurf library, not every uninstalled upstream KSF/Momentum map. Snapshot
UTC/hash and definition are included in the readable report. No map files,
zones, tiers, active pool, backend/config/player data were changed by the report.
