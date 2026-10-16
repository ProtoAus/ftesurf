# P731 — main-menu status and roomier Play picker

Claimed after fetching both repositories and checking headings/untracked pNNN
claims across their worktrees (maximum 730, 2026-10-16). QC/UI only; engine
commit/tag pin and QC build 89 stay unchanged.

## Interface for the continuing Friends workstream

This does NOT replace P722's Steam linking, friendship graph, backend schema,
privacy, private chat, polling or lobby validation. `cl_menu_friends.qc` is a
separate install-local display adapter. Existing `friend_begin` / `friend_row`
/ `friend_end` / `friend_clear` messages are unchanged. Hooks publish only the
completed `fr_buf` snapshot; partial updates leave the previous snapshot intact.

Ephemeral, non-archived cvars: `ui_friend_0..127` contain six tokenizer fields:
`who relation online "escaped-name" "escaped-server" "escaped-map"`.
The last three fields use `uri_escape`, including quotes around empty fields.
`ui_friends_count=-1` means unavailable (NOT offline). A completed publication
sets count then advances `ui_friends_epoch`. Clear/init/shutdown wipe the rows
and advance epoch. The menu gates on an active connection, requires a fresh
epoch within 16 seconds and drops a pending row press when the epoch changes.
No local friendship/presence file, address or account capability is introduced.

Join calls `friends_menu_join <8-hex-who>`. The CSQC adapter checks its current
accepted/online row, then calls existing `Friends_Action("join", who)`, including
its short-lived `friend_join` response arm. The authenticated lobby resolves
presence and authorizes the eventual response. Pending/offline rows have no
Join action. The menu cannot authenticate/query presence while disconnected;
that future capability belongs to the Friends workstream, not this UI patch.

## UI

Top-right passive version/update status replaces the station-stack update
button. F2 opens the existing updater; Escape returns. The standard/empty F2
binding is migrated, but a custom player binding is preserved. Automatic
consented update installation no longer forces the update screen open; first
permission disclosure stays intact. No new updater authority or release occurs.

Development menus identify the compiled VERSION with `(dev)`; release staging
appends non-archived `ui_release_version` metadata to its own default.cfg, using
the FINAL release version, including pre-bump builds. Linux copies that same
staged game tree. Version labels are informational, not integrity decisions.

Play keeps existing map/download/build/leaderboard controls. Filters default
collapsed, retain all selection state, and show a selected tier on the header.
Thumbs switch between 78x44/48-unit rows and 128x72/80-unit rows (large default).
Friends is optional: a separate sidebar at >=1180 virtual width, modal drawer
below that. The narrow drawer removes underlying map action targets.

## Verification

Work/evidence root: `C:/FTESurf-worktrees/menu-20261016T015008Z/`.
- Isolated origin/main base: QC `3b963fbc9b81be680825f8b189df0436d493d457`;
  engine documentation `9ad66320b6865b53d8ee64af7d96096cb3dc8e44`.
- `src/build.ps1 -Jobs 8 -NoDeploy`: all three VMs, zero warnings (build-fifth).
- `tools/test_menu_refresh.py`: native socket rig, 1280x720 and 800x600;
  24 PNGs inspected in relevant panels; final run `artifacts/test-third/
  ui-gallery-pasb73p1`, verdict PASS. F2 handler/bind, filter retention, row
  sizing, wheel scroll, 128 completed friends, partial snapshot, stale/clear,
  one real UI-to-CSQC join request and pending/offline negative controls.
- 1280x720: collapsed large=5 full map rows vs expanded=3; compact=8.
  800x600: collapsed large=3 vs expanded=1; compact=6. Tier 3 keeps 420 rows
  on collapse; map wheel advances 576 units. Synthetic IDs/names only.
- Visuals: top-right status no longer occupies a station slot; large previews,
  compact layout, wide Friends and narrow/stale drawer inspected from PNGs.
- PowerShell AST parse: build.ps1 and release.ps1 pass. QC has no clangd parser;
  LSP diagnostics are not treated as QC validation.
- Initial failed native run executed menu_restart before video startup and hit
  the builtin menu; retained as failed evidence. Driver now waits first, and
  runtime state plus changed pixels guard against silently testing no menu.
  An intermediate diagnostic exceeded sprintf's argument budget; fixed before
  the final zero-warning build.

Additional native controls passed: a pre-change build at the inspected base
still draws the old station-stack update button; the subject does not. The
isolated release-version fixture draws `Your version: 9.8.7` while its compiled
source VERSION remains 0.1.25, proving staged release metadata wins. Evidence:
`artifacts/control/ui-gallery-okrds6cg` and
`artifacts/release-version/ui-gallery-7he40j5z`; PNGs inspected. No release ran.

Remaining before delivery: inspected commits, clean-commit build provenance and
dual-install delivery. Live Steam/backend
acceptance is owned by the other Friends workstream; synthetic UI checks do not
claim that service is deployed or that a real cross-lobby join was measured.
