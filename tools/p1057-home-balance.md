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

Menu-only promotion is from the inspected clean-source build, with actual UTC,
both Windows destination hashes, predecessor identity/hash checks, unique adjacent
rollback copies and unchanged protected binary/plugin/progs/config hashes in the
task's receipt. Installation status is recorded after that boundary. Server/API,
CSQC/SSQC, native pins/binaries, qcbuild, website, saved configs and player data
are not part of this menu swap. The explicit authorized addons preference above
has its own separate receipt and rollback. Retain source/staging/runtime/failed controls and
startup evidence; retire only verified disposable generated outputs/owned links.
