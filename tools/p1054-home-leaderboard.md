# P1054: Home, personal leaderboard seek, completion sources

## Implemented

- First post-onboarding page is a horizontal Home dashboard: independently
  scrollable public lobby grid above WOS statistics and completion/progress;
  Friends above the existing public lobby/friend-DM chat transport on the right.
- Shared top tabs: Lobbies, Maps, Story Mode, Event Mode, Settings, Music. Maps
  uses the freed lobby height and opens without the Friends sidebar. The former
  lobby strip remains an explicit, non-archived `ui_maps_lobbies 1` compatibility
  option, off by default. Terms/Steam/name onboarding remains outside the tabs.
- Settings links the existing visual/music/privacy panels and offers explicit
  sensitivity/effects-volume adjustments. No owner settings change at startup.
- A Steam-link call to action appears only after the existing Friends service
  explicitly says the account is unlinked; transport failure is not treated as
  unlinked. A successful signed/relayed Friends snapshot removes it. Friend
  clicks on mutual friends select a DM; pending/non-mutual rows retain the
  existing public-profile overlay on Home. The chat panel can return to Public
  lobby. Conversation
  switches do not race an outstanding signed chat transaction. Home Friends
  polls every 10 s, leaving headroom alongside chat in their shared budget.
- Home shows native WOS figures, separate WOS/Everything completion, every
  difficulty tier plus unrated, and official own-player Story/Event progress.
  Unavailable services/progress are not presented as measured zero. Older
  backends hide the unsupported WOS completion selection rather than invent it.
- Both leaderboard interfaces have Jump to me. The server resolves the public
  player handle/mark, keeps map/build/track/leg/source/style/name restrictions,
  and seeks with SQL rather than downloading every preceding page. The game
  retains the absolute offset for subsequent paging. No match preserves the
  held list and says so. The merged source prefers a WOS record, otherwise the
  player's fastest imported record. Cache entries never store a seek as page 1.
- First pages and prefetches request 40 rather than 100 rows, bounding first
  reply/QC decoding work; scrolling still requests following pages. This is a
  work/bytes reduction, NOT a measured FPS or millisecond claim.
- In-game profile tier completion and website profiles offer WOS/Everything.
  Everything is WOS + Momentum + KSF. WOS counts ranked main-track finishes only.
  Bars, surf/bhop splits and tier map lists use the SAME known enabled map pool.
  Existing requests default to Everything; summaries add `completion_wos`, and
  tier lists accept `completion_source=wos|all`. Profile result rows are not
  silently hidden by a completion-only filter. Website selection is deep-linkable
  with `cs=wos`; asynchronous list caches are keyed by mode AND source.

## Verification and limits (2026-10-26 UTC)

Pre-registered controls/falsifiers and exact local command logs are retained in
owned task root `C:\FTESurf-worktrees\menu-20261026T1632Z`.

- Standard `src/build.ps1 -Jobs 8 -NoDeploy`, pwsh 7, compiler discovered using
  the existing canonical compiler directory on PATH. Server/menu: 0 warnings.
  CSQC: the SAME two baseline F333 setproperty/227 warnings in untouched
  cl_viewmodel.qc; zero new warnings. Compiler output, not wrapper exit alone,
  was inspected.
- `surfd/test_home_completion.py`: synthetic native/import/both/stage/unfinished
  controls; equal game/web completion; source-specific map lists; identical
  denominator; bhop split; invalid source; public 12-hex and linked 8-hex seek;
  own record at rank1206; wrong name/source/style/leg excludes it; filtered
  position differs from unfiltered displayed rank; ordinary absolute paging
  continues after the seek. Passed.
- `surfd/test_completion_pool.py`: 46 checks, 0 failures.
- Existing `surfd/test_board.py`: all checks passed.
- Existing `surfd/test_web.py`: 0 failed, including the static DOM-ID contract.
  An initial dynamic-ID approach failed that existing contract and was replaced
  with a retained element reference; the check was not weakened.
- `node --check surfd/web/board.js`, Python syntax and `git diff --check` pass.
  QC has no applicable LSP; fteqcc is the compiler evidence.
- Live read-only network baseline on surf_beginner returned the first100 imported
  rows in approximately 0.08-0.13 s on this connection, not a general UI/frame
  measurement. No actual-client performance speedup is claimed.
- The quiet-window gate initially refused owner/peer processes; none were
  interrupted. Once they exited, an isolated offline control showed the old
  Home -> Maps action, and the subject showed Home -> Maps -> Settings -> Home.
  Screenshot readback is1920x1111 (the requested1280x720 launch flags were
  superseded during startup); it is NOT a second-resolution pass. Screenshots
  show the new dashboard, top tabs, full map list area without lobby/friends
  strips, and Settings. Empty/offline state only: real populated lobbies/stats,
  native panels, Steam link, friend DM, completion UI and loading feel remain
  pending in lextest.md. The runtime falsifier caught Maps calling only the
  preparation helper, which does not switch screens and also reveals Friends;
  fixed by selecting SCREEN_CREATE first, preparing, then hiding Friends.
  Home Enter-to-send and Settings Escape were wired to their existing handlers.
  An optional isolated headless Edge smoke yielded exit0 with no
  DOM, screenshot or server request; it is retained as infrastructure failure,
  NOT a website pass. No further browser harness campaign was started.

## Delivery state

Source is isolated from the shared dirty checkouts. Engine binary/API is
unchanged; engine commit/tag pins and qcbuild are unchanged. This is not a
release.

**Local menu installed, 2026-10-27T02:19:20Z:** the previously runtime-tested
`menu.dat` from inspected clean source `e0e9b62ab08d8ecf099c391fb18f853841306528`
is now in BOTH `C:\FTESurf\ftesurf` and `C:\FTEQuake\ftesurf`, destination SHA256
`8ca79ea6e247945d8b6205ffb0c8370fcb65c34fc40831cee3649218bf912a00`.
Each predecessor was preserved as `menu.dat.pre-p1054-home-20261027T021920Z`
beside its destination; expected predecessor hashes were checked again at the
swap boundary. All16 checked engine/plugin/CSQC/SSQC/config hashes remained
unchanged. No player data was modified and no running game was interrupted.
This menu-only scope is independent of the guarded backend. The initial full-set
promotion blocker must NOT prevent the owner testing the already-qualified menu.

Launch the game normally from either install. If already open, use console
`menu_restart`, then `menu_main`. Check the new Home, Maps, Story/Event and
Settings tabs. Populated/linked acceptance remains pending in lextest.md.

The API, website and CSQC/SSQC changes are NOT deployed by this menu-only swap.
The live backend remains owned by another guarded deployment cohort: coordinate
its promotion without bypassing ownership/consent/provenance checks. WOS-only
Home figures and jump-to-me can report unavailable until that API is promoted;
the in-game TAB/profile completion selector and website update are still pending.
Existing linked Friends/chat and Story/Event services are reused by the menu.

## Answers: existing content/time automation

- NanoPi mapwatch is scheduled six-hourly to find/download missing supported
  Momentum and KSF builds, not to overwrite a differing existing build. Maps
  reach the download mirror through its own verified publication pipeline.
- The live R2 gzip job is scheduled at minutes17/47. `tools/r2gzip.py` considers
  verified MAP BSP objects only and keeps a gzip companion when it saves at
  least10%. Existing raw objects remain; clients negotiate the compressed body.
  Internally LZMA-packed Momentum BSPs often do not benefit and are skipped.
  This is not blanket compression of screenshots or all game files; JPEG/PNG
  images are already compressed image formats.
- Screenshot harvest, JPEG derivatives/backdrops, explicit JPEG-only download
  publication, and append-only 128x72 atlas generation EXIST, but are not one
  automatic new-map-to-published-atlas transaction. `mapmedia.md` describes the
  explicit harvest/publish/atlas steps. A newly fetched BSP alone does not prove
  a new screenshot was fetched, published or added to the bundled atlas.
- Momentum `momwatch.py` is scheduled every7 minutes, prioritizing live lobbies,
  website interest and shallow boards; the normal stale target is24h, subject
  to request budgets. KSF `ksfimport.py --watch --go --demos` is scheduled every5
  minutes, revisiting page1 and slowly extending/rewalking older pages. Better
  times replace slower stored bests when that board/player is refreshed. Demo
  downloads are separate. These are eventual polling, not push notifications or
  a guarantee that every upstream PB appears immediately. A changed upstream
  record outside the currently visited pages can lag; upstream deletions are
  not automatically purged. Recent cron log mtimes show invocation, not proof
  of healthy import completion; current guarded-cohort health was not certified.
