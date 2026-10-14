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

- Inspected/pushed product commit: `37cc4b1d267d4255a4187fb5b29ec7a971e8f807`.
  Engine documentation entry: `394fecbd0633b7030e736393cabe4751eaafd55b`.
- All 19 backend suites passed in an owned NanoPi stage, including test_admin;
  declared skips were the absent Momentum conversion fixture and Node syntax
  check (the actual admin JavaScript passed Windows Chrome controls).
- 2026-10-14 07:19:19Z: exact-file backend deployment under sweep/mapwatch locks,
  owner-only SQLite backup, source hashes verified, graceful gunicorn reload;
  health 200 / 12 lobbies. Installed eight public runtime/new-test files only.
  Three already-different live docs/tests were preserved, not overwritten.
- Live watcher command: `mapwatch.py --updates --max 0 --zones 0 --variants 0
  --site-zones /srv/nvme/ftesurf-site/zones --go` under its lock: no map/archive
  downloads, 28 checked zone transfers plus site copies, 29 incompatible
  transfers left refused; 72 explicit real-port links now in the catalogue.
  surf_aircontrol_ksf already had an authoritative local zone, preserved.
- 07:24:04Z: file-only menu.dat/menu.lno deployment to BOTH Windows installs,
  .prev retained. menu.dat SHA256:
  `f1eac14c22a35a56d387ad6c78a786793bdc06b338f832aa981161735073bc0d`.
  No client/server VM, native binary, engine pin or release/feed swap.
- The 28 public checked zone files were exported with their target BSP and zone
  hashes. Each Windows install received 27 missing local zone files for these
  server-offered builds (preseeded for future map downloads); one existing local
  file in each install was preserved. No existing zones were overwritten.
- 07:25Z live authenticated HTTP controls: CSRF refusal, disable, join 403,
  explicit disabled feed row, reenable; original policy restored exactly. Live
  manifest: 2,033 builds, all enabled, 875 missing-zone builds. Public play feed
  is 200/no-store. Admin maps redirects correctly to secure login at
  https://play.proto.bar/admin/maps; public board is on proto.bar/ftesurf/board.
- Live aircontrol web boards both expose 2,210 Momentum and 1,003 KSF records;
  base has one native ranked row, _ksf has none (native separation preserved).
  Related-build links name both held files. Live alias plan uses MULTI-INDEX OR
  covering runs_board lookups, not a table scan. Last 400 app/gunicorn log lines
  had zero ERROR/Traceback/CRITICAL after deployment.

Human course/alignment and display acceptance is in lextest.md. No blanket
claim of a played start-to-finish test on all 28 newly zoned builds.
