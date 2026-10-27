# P1057: bigger lobbies/images, compact stats, taller Friends

## Request / implementation

Owner: "Epic, looks good" for P1056; then requested more lobby area, bigger
thumbnails, smaller stats, more Friends height than chat, and asked why launch
was now5-10s. P1056 visual acceptance is recorded in lextest.md, not promoted to
performance/account/data acceptance.

- Stats reserve210..252px rather than expanding into most of the left column.
  All four summary cards,9 standard-tier/Unrated rows and both mode cards remain.
- The12-lobby layout uses3 columns and fills the remainder. Adaptive16:9 image
  slots replace fixed64x36; map/title/player rows stay separate. At the64-cell
  stress cap narrow cells remain numbered targets instead of vanishing.
- Friends gets58% of right-panel height. Embedded short chat uses compact room,
  list/input/note/privacy coordinates; standalone send/proof paths are unchanged.
- `ui_menu_probe boot` prints only MENU initialization, post-init wait, first
  active draw and catalogue elapsed times/count. These are NOT whole executable
  startup, native-before-MENU or GPU-presentation measurements. No speculative
  native startup optimization was shipped.

## UI verification

Owned task root: `C:\FTESurf-worktrees\menu-20261026T1632Z` (original owner/session,
not a fresh copy). Predictions: PLAN-home-balance.md. Existing runtime runner:
`python <root>/home-fit-smoke.py subject balance` reuses
`tools/test_ui_maps_runtime.py`'s overlay/process/console contracts. Initial gate
was blocked by foreign guarded tests; it later cleared normally. No foreign
process was stopped and the process gate was not relaxed.

Standard pwsh7 `src/build.ps1 -Jobs 8 -NoDeploy`: server/menu0 warnings; same two
untouched cl_viewmodel setproperty227 CSQC warnings, zero new. Runtime subject:
`artifacts/home-balance/subject-05f1d2999a`.

| Actual PNG/window | Lobby height | Stats height | Image slot | Friends/chat height |
|---|---:|---:|---|---|
|1280x720|418|210|129x73|364/264|
|1920x1111|660|248|183x103|526/382|
|800x600|298|210|69x39|294/214|

All12 cells and the last target acted; all9 WOS and Everything rows populated;
Story2/4 and Event1/3; source clicks and bottom bounds passed.64/64 numbered cells
fit at800x600. Legacy API and offline retain labels/unknowns. Screenshots inspected
at each size, including chat input/footer separation. Directory/map/profile data
is synthetic; thumbnail slot sizes do not claim the fake fixture maps have real
images. Actual atlas drawing uses the unchanged ui_thumb/subpic contract.
Owner P1057 look/feel and real linked stats acceptance remain pending.

## Launch diagnosis (isolated comparison; canonical inputs unchanged during test)

The empty navigation overlay initially reported0 maps/35ms catalogue. It cannot
explain the owner's real launch and is not counted as populated startup evidence.
Inspection found `C:\FTESurf\ftesurf\fs_addons.txt` has an extra active
`steam:Counter-Strike Global Offensive/csgo` entry; saved fs_lazyaddons is1 and
fs_automount is1. Do not infer full mounting/cost just from the template comment
or that cvar's name. The other Windows install has no active addons file.

A bounded fresh-process comparison used the SAME installed engine, HL2 plugin,
new menu, public catalogue data and explicit video/FS cvars, with that single
entry present/absent in OWNED copies. Actual native `fs_steamlibs` resolution
proved ON/OFF, both loaded2326 catalogue rows, and all canonical input hashes
stayed unchanged. Retained runner: startup-mount-smoke.py. Evidence:
`artifacts/startup-mount/result.json` and `confirmation.json`.

- ON:9.469s to first successful populated MENU timing probe.
- OFF:4.437s to the same criterion.
- ON again after OFF:9.406s, falsifying the simple first-run-only/warm-cache story.
- Qualified MENU init273..278ms; first draw77..114ms; catalogue322..339ms.

Thus this optional primary-install entry accounts for roughly5s in the controlled
launch path, rather than the new layout's MENU work. These are not cold-cache,
first-pixel or owner's exact-config benchmarks;4.437s is not a launch-time promise.
The first helper/manifest and automatic-index-file assumptions were tooling
failures, retained in logs; they were not passed arms. The corrected existing
Runtime/manifest and real mount-resolution control completed the A/B/A comparison.
No new wrapper chain, owner/peer termination or canonical config edit was used
for those comparisons.

## Authorized on-demand verification and configuration

Owner then approved "yes if it works correctly". The same runner's ondemand arm
copied the real public mapdeps.txt and loaded installed surf_cavediver (a declared
CS:GO-only dependency) in an owned loopback listen fixture. Full CS:GO paths were
ABSENT before map selection. Native state4->1, spec CS:GO, newly PRESENT full pack
searchpaths and actual map status proved automount ACTED. Inspected
`csgo-off-48979abe26/ftesurf/screenshots/ondemand-cavediver.png`: textured in-game
world, not a placeholder/menu screen. Optional normal/luma lookup warnings are
not a claim that every optional channel or custom map was tested. No start zone
was seeded: this is asset-loading evidence, not run/prediction acceptance.
Proof: `artifacts/startup-mount/ondemand.json`; canonical inputs stayed unchanged.

Only AFTER that test, at **2026-10-27T04:32:03Z**, removed exactly the one active
CS:GO line from `C:\FTESurf\ftesurf\fs_addons.txt`, retaining all other bytes.
`fs_automount1` was already enabled; ftesurf.cfg was never edited. Unique adjacent
rollback: `fs_addons.txt.pre-p1057-ondemand-20261027T043203Z`.
Receipt: `artifacts/ondemand-install/20261027T043203Z/receipt.json`. All16 protected
binary/plugin/progs/saved-config hashes unchanged; secondary addons file remained
absent. No assets uninstalled/deleted; map-load cost is deferred to maps that
need it. This verifies one real declared-dependency case, not undeclared/all
custom maps. Owner's actual normal-launch time remains manual acceptance.

## Installation / retention

Installed BOTH Windows `ftesurf/menu.dat` files at **2026-10-27T04:35:51Z**, from
inspected/pushed QC `16f5cca3c0a1e4a81a8281b3e71a1539ea85d516`; engine patch
record pushed as `b1e3b1affc3919e1ff7a53163f0c3c5d21338e58`. The clean inspected
rebuild was BYTE-IDENTICAL to all tested menu payloads; no repeated runtime was
needed after a documentation/index-only commit. Both destination SHA256:
`4536c2e52bca1f690985c7bc167c80066a126cdc328f5491965697e694e899dc`.
Predecessor identity/hash checks acted at swap; unique adjacent rollback files:
`menu.dat.pre-p1057-balance-20261027T043551Z`. All17 protected hashes stayed
unchanged (the prior16 plus the now-authorized addons result). Secondary addons
absence preserved. No owner/foreign process existed at the boundary or was
stopped; the short canonical claim was released after verification.
UTC receipt: `artifacts/menu-local-install/20261027T043551Z/receipt.json`;
immutable manifest: `artifacts/p1057-manifest.json`. Server/API,
CSQC/SSQC, native pins/binaries, qcbuild, website, saved configs and player data
are not part of this menu swap. The explicit authorized addons preference above
has its own separate receipt and rollback. Source/staging/runtime/failed controls
and startup evidence are intentionally retained. Two generated build directories
were archived and hash-verified before retirement; all current runtime junctions
and owned processes are absent. Clean engine-doc worktree retired normally.
`artifacts/p1057-retirement.json` records this cleanup; the clean QC source stays
for owner acceptance and original coordinated backend work, not an active fixture.

Restart the game normally for the launch setting to apply. `menu_restart` then
`menu_main` can reload only the new layout; it is not a fresh-launch measurement.
