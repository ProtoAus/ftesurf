# Patch 698: map links / zones / admin manifest

Claimed after fetching both repositories: published headings through 696,
untracked p697 claim; no engine source or binary work. QC base e008c3b,
engine documentation base caeb0b951. Native pin/tag and QC Build unchanged.

## Controls and verification

- `pwsh -NoProfile -Command './build.ps1 -Jobs 8 -NoDeploy'` from `src/`:
  all three VMs compile, zero warnings, isolated outputs in `rig/build-nodeploy-*`.
- `python surfd/test_mappool.py`: default-enabled manifest; per-build zoning;
  anonymous/session/CSRF/cross-origin/invalid-input arms; reversible persisted
  disable; join allocator refusal; files/history retained; linked game+web
  imported boards in both directions; native records stay on their builds;
  `_v2` and Momentum-owned suffix names do not collapse; checked beta donors.
- `python surfd/test_mapwatch.py`: beta/extra integration copies held zones to
  a fitting KSF port but refuses a shifted one, alongside its existing local,
  edited, own-timer, restart-target and previous-copy controls. Full suite passes
  on Windows except its declared POSIX-only skips.
- `test_variants`, `test_web`, `test_board`, `test_join`, `test_surfd`,
  `test_accounts`, `test_zonefit`: pass on Windows. `test_admin` has the same
  two rcon/cache timing failures on subject and unchanged e008c3b control;
  no unrelated fixes made to it.
- `python tools/mappool_smoke.py --qc-artifacts <NoDeploy output>
  --output-dir <owned task root>/menu`: acts through the real menu VM, flags,
  disabled-side fallback/refusal, folded links and positive/negative filter
  controls. A synthetic offline-only consent record exists only in the owned
  overlay. Missing metadata/thumbs in this thin rig are not a product claim.
- A local headless Chrome fixture exercises the actual admin page JavaScript:
  search, mode, zones, tier, related-build filters, sorting, red rows, disable,
  unhighlight, disabled filtering, and reenable. Browser and menu screenshots
  inspected. Test data/credentials are synthetic, no owner/browser session used.

## Semantics and limits

Known port suffixes against held MOM roots create **related-build** links, not
proof of identical courses. `_css` links keep their archive-hash provenance;
version suffixes and a suffix map MOM lists itself remain separate. Imported
rows are readable across a linked family; native FTE rows are build-specific.
Zones still need independent geometry/restart compatibility. Existing/local
zones are not overwritten; incompatible copies remain missing and marked red.

Admin Maps is `/admin/maps`. Enable/disable is per build and persists in
SQLite. Menu refresh is at most once per minute with online consent; offline
menus use their saved policy. Disabled mounted builds must remain in the feed
with explicit flags, otherwise they silently become available again. Pool
controls do not delete files/history, evict current lobbies, rewrite explicit
rotations, or prohibit console `map` commands. The join allocator enforces
policy even when an older client ignores the menu extension.

## Deployment checkpoint

Staging and live provenance are recorded after the inspected-commit gate;
source verification is not itself a deployment claim.
