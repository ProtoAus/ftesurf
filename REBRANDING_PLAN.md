# FTESurf -> World of Surf: rename and migration plan

Status: **P705/P710 design approved; game presentation deployed to both Windows
installs and the twelve-lobby development fleet on 2026-10-14 UTC. Public canonical
path/release cutover is not complete.** The owner has approved the World of Surf
identity, existing design and `https://proto.bar/worldofsurf/` as the canonical
website. The source-preparation checkpoints below preserve their original limits;
the superseding deployment checkpoint and `tools/rebrand-deployment.md` distinguish
what is now live. No signed identity, player-data migration or Build/version bump.

## Implementation checkpoint — 2026-10-14 (P705)

- **Done in source:** outlined full-name dark/light/one-color wordmarks; WOS
  compact art, favicon, 180/192/512 PNGs, 16–256 ICO and 1200×630 social card;
  reproducible exporter and offline gallery at `src/brand/index.html`.
- **Done in source:** landing/Anti-Cheat titles, nav, metadata and copy;
  leaderboard titles, WOS labels/tooltips; account sign-in/return/error copy.
  This is Phase 1 plus the web-only presentation subset of Phase 4, not a claim
  that intervening routing/compatibility gates are complete.
- **Verified locally:** 7 new regression checks; existing web (268), accounts
  (400) and board (351) checks; raster regeneration; original-page negative
  controls; account AST and board-JS display-only comparison; desktop/mobile
  screenshots, all five board titles and an acting WOS → `ranked` filter under
  both site prefixes. These do not prove live nginx or Steam path cutover.
- **Not done:** new live routes/canonical URLs, account-path migration, web/fleet
  deployment, native/QC identity or icons, renamed entry points/packages,
  updater migration/bridge release, player-data migration, Build/version bump.
- **Direction used for the candidate:** retain the existing dark/cyan, type-led
  presentation. Art acceptance is still a human gate; no new wave/tagline.

Next: accept the art; prepare compatible game/engine presentation changes;
then prove routing/accounts and signed-release compatibility before public
cutover. Old `/ftesurf/` OG URLs remain intentional until the new route is real.

### Stage 2 progress — P707 parallel-path preparation (2026-10-14)

**Source preparation verified; not installed or a canonical-path cutover.**
`src/release/ftesurf.nginx` now defines `/worldofsurf/` beside `/ftesurf/`, using
one existing site directory and `/board/` backend. No legacy path is redirected
away, no release/feed/client defaults change, and `SURFD_BOARD_URL` stays legacy.
Both starts intentionally advertise the legacy callback. Account application,
association database, signed formats, host cookies and service hosts are unchanged.
Installer backs up the prior snippet and probes both paths for the site marker,
JSON MIME and real board maps envelope, not a misleading filebrowser `200`.

Real local nginx + isolated surfd: five integration groups pass (both prefixes,
asset/feed bytes/MIME/cache, 404s, slash query preservation, exact upstream queries,
method boundaries, overwritten IP headers, account callbacks/cookie attributes).
Legacy-only acting control fails on missing new routes and query loss. Full mock
regressions pass: 268 web, 400 legacy-base accounts, 400 future-base accounts, 350
board and seven brand tests. Details, commands and limits: `tools/p707sitepaths.md`.
These are local Windows/Linux nginx + mock checks, not live HTTP, real Steam/browser
acceptance, a signed updater round-trip, human art acceptance or a release.

**Next gate:** accept P705 art; approve the privileged parallel-routing deployment
window, then run Linux `nginx -t` and external old/new HTTP/download/account
checks. Keep the old base authoritative until a separately approved account
transition drains old starts (600s configured start window, plus worker/config
provenance) or explicitly tests old signed callbacks. Do not blindly redirect them.
Canonical social links/defaults, native branding and updater bridge remain later
work. Game/package presentation source preparation is recorded in P710 below;
its visual/runtime acceptance is still outstanding. No QC Build, engine
binary/pin/tag, player data or live install changed.

### Stage 2 and partial Stage 3 source candidate — P710, 2026-10-14 UTC

Prepared, not deployed: manifest formal NAME, menu title/update/consent/help and
console copy, HUD map title, WOS board/profile/native-score badges, local/server
fallback hostnames and all 12 configured lobby hostnames. Lobby display accepts
both old and new name prefixes; no directory, network or ranking identity changed.
The exact old CSQC boot diagnostic is retained for active harness controls.
Current README/service headings, generated release/install/legal headings and
Linux wrapper errors use World of Surf while preserving truthful legacy commands,
archive roots, paths, community references and FTEQW attribution.

All three VMs compile with zero warnings; actual compiled string tables contain
the new title/badges and legacy technical formats. Six frozen product-source audit
tests and five package-source audit tests pass with acting old-source failures;
seven web brand checks, 12 signed-updater synthetic-key tests and physical release
deny checks remain green. These are source/compile/offline controls, NOT game/menu
execution, art/layout acceptance, native icon/title rebuild, actual package or
fresh-install/upgrade/live behavior. Clean-tree shipguard setup remains blocked
on absent ignored generated content; it is not counted as a pass. Commands,
inspected references and limits: `tools/p710presentation.md`; human checklist:
`lextest.md`. Neither stage is marked complete by this preparation.

**Next safe work:** accept P705 art and P710 game/menu/HUD copy at narrow sizes,
then separately prepare native title/icon/wrapper packaging with the complete
ship set. Before deployment, review whether saved player/server hostnames should
remain owned (recommended: do not overwrite them). New browser-base/defaults,
Steam callback transition and signed old-client update bridge still need their
separate gates; keep the old endpoint/feed/technical game identity authoritative.

### Approved design and development deployment — 2026-10-14 UTC

The operator approved the P705/P710 design and deployment. Exact clean game
commit `80618e52e50bff713ad6b645511308c00d4c0ccd` compiled all three VMs without
warnings. At 17:20Z the qw/cs pair and hostname-only lobby configs were deployed
to all 12 empty active lobbies; at 17:23Z all three VMs and the formal manifest
were hash-verified in both Windows installs. No native binary/plugin was replaced,
no saved player hostname/preference was reset, and later peer commits were not
silently included. Rollback copies remain. A concurrent P712 rollout restored
older client labels under the prior withholding policy; approved composition
`0303a98` preserves its exact trainer/watch feature plus the new presentation.
Its zero-warning build, actual installed-SSQC/menu synthetic trainer control and
subject pass. At 18:10Z only that combined client was deployed to both Windows
installs and twelve empty/restarted lobbies; the new live download matches
`af01a4eb...`. Server/menu/configs and native binaries stayed unchanged.

Actual old/new menu pixels show FTESURF versus WORLD OF SURF; flat/milk station,
consent and UI-scale images were reviewed at 1280x720. The real 800x600 screenshot
confirms BACKLOG's pre-existing no-scroll consent overflow, not narrow-consent
acceptance. A fresh unseeded client downloaded the exact deployed CSQC from the
live fleet, drew the Local board and new HUD title, and reached its acting marker
with no QC errors. An Online-shell control shows WOS and correctly blocks data
without online consent; it does not prove native table rows or account linking.

The existing `/ftesurf/` landing page and its board/account presentation are now
World of Surf: four hash-verified backend presentation files, an acted graceful
worker reload, and a separately tested/reviewed no-release static transaction
(`90d2566`). All 20 static files have exact-byte/MIME witnesses; original release
history and signed feed/version/receipt bytes stayed unchanged. No functional
backend/schema/identity/environment, signing, archive or version was replaced.

External old/new path controls still show `/worldofsurf/` is the unrelated
filebrowser fallback. Authenticated nginx installation/test/reload remains needed;
HTTP 200 is not route acceptance. The guarded operator candidate/script are staged
outside served roots. Keep the legacy site/feed/callback base unchanged meanwhile.
Exact source, hashes, commands, retained failures, rollback and remaining
web/native/package gates: `tools/rebrand-deployment.md`.

## 1. Agreed identity and remaining decisions

Use one consistent public identity rather than three interchangeable titles:

| Context | Agreed spelling |
| --- | --- |
| Official game title, website, documentation | **World of Surf** |
| Short UI labels, leaderboard source badge, community shorthand | **WOS** |
| Compact account/handle spelling | **WorldofSurf** |
| New repository/package/URL slug | **worldofsurf** |
| Canonical website | **https://proto.bar/worldofsurf/** |
| Engine acknowledgement | **Built on FTEQW**; identify the modified fork where appropriate |

The objective is to separate the game's identity from its engine, NOT remove FTE's
credits, licence, source provenance, upstream names, or development tools.

**Recommended approach:** a complete public rebrand first, with compatible old
technical identifiers underneath; a separately approved technical migration if
having the new names on disk is also important. Keeping a legacy file-format name
is not an incomplete public rebrand. Changing every occurrence in one pass is unsafe.

### Confirmed decisions and remaining owner approvals

- [x] Use World of Surf, with WOS / WorldofSurf in the contexts above.
- [x] Keep `proto.bar`; make `https://proto.bar/worldofsurf/` the permanent canonical
      website, not an interim address. No new domain purchase or DNS migration.
- [ ] Choose whether launch includes only the public rebrand (recommended) or also
      the higher-risk on-disk migration in section 8.
- [x] Approve the P705/P710 design: existing dark/cyan identity, World of Surf
      wordmark and compatible game/web presentation (operator, 2026-10-14).
      This does not waive native/package/runtime compatibility gates.
- [ ] Decide whether to rename the public game GitHub repository at launch or later.
      The engine fork and shared launcher repository do not need renaming.
- [ ] Choose a launch window and a legacy endpoint support policy. Recommend at
      least 12 months for old web links, and longer for clients/downloads still in
      use. Do not retire a dependency solely because a calendar deadline passed.

## 2. Audit baseline and limits

Source audit: 2026-10-14 UTC. Both game and engine origins were fetched; neither
checkout was switched, reset, merged, or built.

| Source | Inspected reference |
| --- | --- |
| Game working checkout HEAD | `8cd6ec5481f40d774a33ce56c310d43595fa73a1` |
| Game fetched `origin/main` | `03ff7e56cedc904afc5a4aa411796d1fd76e15c2` |
| Engine working checkout HEAD | `f05d2941987502ba94437a134f915516b5c9d35e` |
| Engine fetched `origin/main` | `61466a48f3d76139318fbbeab77e503334746f1f` |

The game checkout was 77 commits behind its fetched main and both canonical source
trees contain existing work. This plan combines working-tree inspection with
explicit reads of newer launcher/update/release code at the fetched game reference
and newer updater code at the fetched engine reference. Implementation must start
from freshly inspected, coordinated references, not assume the local checkout is
current or include another session's uncommitted work.

At the fetched game reference, case-insensitive Git text search found `FTESurf` in
**1,039 tracked text files**. This includes historical tests, comments, and file
contracts; it is NOT a count of files that should be renamed. Binary/untracked
assets and infrastructure outside Git require a separate census.

Existing work to reuse: `tools/p694launcher.md`, `tools/p695wave.md`, and
`tools/p696logo.md` describe the World of Surf launcher presentation. P696 supersedes
the earlier illustrative scenes: logo and progress only. These records explicitly
say they are not a full game rename or proof of a shipped release. The separate
`ProtoAus/Quakers-Launcher` source checkout and its current deployment were not
located/independently audited here; obtain the configured clean launcher source
before implementation. Do not assume a preview binary is the production launcher.

No live NanoPi inspection, registrar check, DNS verification, Cloudflare dashboard
inspection, external connectivity test, or public release inspection was done.
Hosting descriptions below are source/configuration findings, not live-state claims.
Private security designs and credentials are outside this public planning document.

## 3. Classify names before editing

Every match goes into one of these categories. Completion is a reviewed inventory,
not a repository-wide zero-result search.

| Class | Examples | Treatment |
| --- | --- | --- |
| Player-facing brand | Website titles, game UI, lobby names, leaderboard labels | Rename for launch |
| Public address | Website, lobby API, account links, download/update URLs | Move website/account paths; keep service hostnames and legacy compatibility routes |
| Player-facing package identity | Archive names, launch shortcuts, application icons | Rename with packaging/upgrade tests and old entry-point compatibility |
| Runtime compatibility identity | Manifest installation key, gamedir, config filename, updater paths | Preserve initially; change only through section 8 |
| Data/wire contract | Recording/PB/cache headers, account signing tags, source/filter tokens | Preserve by default; no cosmetic format migration |
| Engine identity and third-party credit | FTEQW, fteqcc, plugin filenames, upstream copyright | Preserve truthful attribution and technical compatibility |
| Historical record | Old patch entries, test evidence, published archive metadata | Preserve history; annotate current instructions where necessary |

Never blanket-replace `FTE`, `FS_`, `ftesurf`, or `proto.bar`. The engine and other
projects share some of these identifiers and infrastructure.

### Confirmed dependencies that make this more than a text rename

1. `default.fmf` has separate `GAME`, `NAME`, `PROTOCOLNAME`, `BASEGAME`, and
   `MAINCONFIG` fields. The engine manifest parser maps `GAME` to the installation
   identifier and `NAME` to the formal display name. At the inspected engine main,
   `engine/common/qkupdate.c` selects the Surf update profile by comparing the
   installation identifier to `FTESurf`. **Do not change `GAME` with the title.**
2. `tools/updatefeed.py` at game main and the native updater validate a signed
   `game: ftesurf` identity, required executable names, gamedir paths, and managed
   file allowlists. The launcher has its own side of that contract. Changing just
   the archive or executable is not a complete migration.
3. `src/menu/m_lobby.qc` already migrates saved `lobby_dir` defaults using a
   generation counter. Keep its service hostname/URL unchanged for this rebrand;
   changing a shipped default later requires a saved-setting migration, not only
   editing the new default.
4. `src/menu/m_main.qc` restricts allowed game hosts. Keep `play.proto.bar` and
   current game advertising intact: a website path rename does not require new
   game hostnames or expanded host trust.
5. `src/client/cl_account.qc` contains a fixed public Steam-link address.
   `surfd/accounts.py` derives the OpenID realm/return URL from `SURFD_BOARD_URL`
   and uses browser state cookies. Moving `/ftesurf/board` to `/worldofsurf/board`
   on the same host still requires testing the realm, return path and old callbacks.
6. `surfd/maps.nginx` supports both connected-client and menu map URL layouts,
   including a legacy gamedir component. Both must remain functional.

## 4. Work inventory: game, engine, launcher, and assets

### A. Game presentation and visible text

Primary source: `default.fmf`, `src/menu/m_main.qc`, `src/menu/m_lobby.qc`,
`src/menu/m_board.qc`, `src/client/cl_main.qc`, `cl_scores.qc`,
`cl_scores_native.qc`, `cl_account.qc`, and `src/server/sv_lobby.qc`.

- Change the formal display name and any title/menu/about/loading/console headings
  shown to players. Verify native window titles separately from the menu.
- Change source tabs and badges from FTESurf/FTE to World of Surf/WOS while keeping
  Momentum Mod and KSF correctly attributed. Keep existing backend tier names
  such as `ranked` unless a separately justified schema change is necessary.
- Update account-link prompts, connection/help/error messages, example commands,
  tooltips, standings, online/offline explanations, and recording/privacy copy.
- Update default local server names and all lobby hostnames in
  `ftesurf/cfg/lobby/lobby.cfg` and `lobby1.cfg` through `lobby12.cfg` as applicable.
  Check code that strips the old hostname prefix before drawing lobby labels.
  Discover the actual active fleet when deploying; do not hardcode a count.
- Check text fitting at narrow resolutions, UI scaling, native UI, long error
  messages, and all source-filter states. The longer title must not clip.
- Change branding through authored source; rebuild generated QC programs rather
  than editing `.dat`, `.lno`, generated definitions, or player-saved configs.

### B. Visual and audio assets

Deliver a small reusable source kit, with export recipes and licences:

- Editable vector wordmark for **World of Surf** and compact **WOS** mark.
- Light/dark and transparent variants, plus a readable small monochrome mark.
- Windows multi-resolution `.ico`; application/shortcut icons; PNG sizes for Linux
  desktop integration if supplied; website favicon/SVG, touch icon, and social avatar.
- New 1200x630 social preview replacing `src/release/site/og.png`, which visibly
  contains FTESURF today. Add/cache-version new exports so link previews refresh.
- Website header/download art, any game title/loading art, and community/banner
  exports. Reuse the accepted launcher logo unless the owner chooses otherwise.
- Review screenshots/video for burned-in old branding. The inspected
  `shot-rise.webp` and `shot-monolith.webp` are gameplay imagery without an obvious
  old title overlay; they do not need replacing simply because the name changed.
  Update their captions and alt text. Inspect other distributed media separately.
- Audit the ignored/generated asset tree and authoring tools, not just tracked
  filenames. Retain reproducible sources for any new raster/icon exports.
- Existing `sound/ftesurf/`, particle names, and `models/ftesurf_portal.obj` are
  runtime resource paths, not necessarily visible branding. Keep them compatible
  initially. Re-record audio only if actual spoken FTESurf branding is found.

### C. Engine application identity without claiming ownership of FTE

Inspect `engine/client/winquake.rc`, resource/icon inputs,
`engine/common/bothdefs.h`, the existing branding include hooks, platform window
creation, and build output/deploy naming.

- Use a game-specific branding configuration for the icon/application display
  identity and appropriate product metadata; do not globally rename the engine.
- Review Explorer FileDescription/ProductName, taskbar/Alt-Tab identity, Linux
  desktop name/icon, crash/support messages, and game window title.
- Keep upstream copyright, FTEQW version/provenance, engine source links, protocol
  interoperability, and plugin ABI/output names intact unless explicitly required.
- Verify the shared second install still runs correctly. A game-specific setting
  must not silently rebrand the other product built by the shared engine tree.
- Maintain the required engine/plugin rebuild and dual-deployment contracts;
  header/branding build-flag changes require the documented full rebuild as needed.

### D. Launcher and entry points

Primary contracts: the separate Rust launcher source, `ftesurf.bat`, `ftesurf.sh`,
`ftesurf_debug.bat`, `src/menu/m_update.qc`, `src/release/bootstrap.ps1`,
`linux-bootstrap.sh`, `tools/updatefeed.py`, and native `qkupdate.c`.

- Reuse current World of Surf presentation. Audit all remaining consent, failure,
  progress, offline, help, restart, download-source, and recovery text.
- Add clearly named `WorldofSurf.bat` / `WorldofSurf.sh` entry points and a branded
  shortcut if desired, while preserving the old scripts for existing users.
  Prefer thin wrappers over a second copy of launch/update logic. New managed
  wrapper paths must be explicitly admitted by every applicable updater allowlist.
- A renamed bootstrap executable must be built/packaged with matching restart and
  wrapper logic; do not rename a binary and leave hardcoded consumers unchanged.
- Preserve offline start, arguments/map shortcuts, working directory, executable
  bits, player opt-in, update locks/recovery, and failure behavior.
- The ordinary signed feed does not self-update the bootstrap in the inspected
  release contract. Plan an explicit bootstrap replacement/manual download path;
  do not assume an older launcher will acquire new launcher behavior automatically.

## 5. Work inventory: website and public services

### Website sources

- `src/release/page.template.html`: title, heading, split `FTE`/`SURF` wordmark,
  description, Open Graph/Twitter fields, download instructions, captions,
  source links, licence/source-offer wording, and all literal old URLs.
- `src/release/site/anticheat.html`: same brand/navigation/metadata updates;
  preserve the page's public disclosure limits and existing factual guarantees.
  No private detection details belong in the rebrand.
- `src/release/site/site.css` and `site.js`: wordmark sizing, font-family aliases
  if useful, responsive header layout, download/copy interactions, relative assets.
- `src/release/site/og.png`: regenerate; HTML edits cannot remove text in pixels.
- `surfd/web/board.html`, `board.js`, `board.css`: visible title, JS-generated page
  titles, source badges/tabs/tooltips, player/map/run views, navigation/footers,
  source links, and narrow-screen layout. JS currently rewrites several titles.
- `surfd/accounts.py` and `surfd/web/link.css`: dynamically rendered Steam-link
  pages, return/error/unlink pages, document titles, instructions and privacy copy.
  There is no separate tracked `link.html` template to edit.
- `surfd/templates/`: operator/admin labels and navigation. Brand changes must not
  accidentally publish admin routes under the new public path.
- Add canonical metadata and, if used, sitemap/robots/social metadata appropriate
  to `https://proto.bar/worldofsurf/`. The origin stays `https://proto.bar`; this is
  a base-path change. These are deliverables to verify, not assumed existing files.

### Public address map

The canonical site is **`https://proto.bar/worldofsurf/`**. Keep the existing
service hostnames; no new subdomains or DNS records are needed for this plan.

| Existing public contract | Planned public destination | Transition behavior |
| --- | --- | --- |
| `https://proto.bar/ftesurf/` | `https://proto.bar/worldofsurf/` | Page/deep-link redirects after validation |
| `https://proto.bar/ftesurf/board/` | `https://proto.bar/worldofsurf/board/` | Preserve paths, queries and browser hash navigation |
| `https://proto.bar/ftesurf/board/link` | `https://proto.bar/worldofsurf/board/link` | Redirect start requests safely; handle in-flight old callbacks separately |
| `https://play.proto.bar` API/map routes | Unchanged | Keep lobby discovery, map/zone/replay downloads and their existing routes |
| Advertised game host `play.proto.bar` | Unchanged | Keep existing DNS-only/direct game routing and ports |
| `https://dl.proto.bar/ftesurf/...` | Keep existing objects; new branded releases may use `https://dl.proto.bar/worldofsurf/...` | Same download hostname/R2 storage; validate new prefixes against all readers before adopting them |
| `https://proto.bar/ftesurf/update.json` | `https://proto.bar/worldofsurf/update.json` for updated defaults | Old URL must still serve compatible signed JSON directly, not a generic page redirect |

The new website may continue linking to existing `dl.proto.bar/ftesurf/` objects
while new-prefix support is verified. Renaming a website path does not require
moving old archives, changing the download hostname, or renaming internal storage.
Both update URLs must expose the appropriate verified signed feed without resetting
version progression or changing its legacy game identity.

### Account, consent, and compatibility requirements

- Set the public board base to `https://proto.bar/worldofsurf/board` through
  `SURFD_BOARD_URL`, and update OpenID return behavior, public link text, the
  client account-link address, account documentation, and proxy paths together.
  The current realm is origin-only (`https://proto.bar`) and does not change for
  this same-host path move (`accounts.py:register`, `steam.py:precheck`).
  Do not change Steam domain registration merely for a path rename unless the
  actual integration requires it.
- The HTTPS scheme and hostname stay the same. Existing secure host cookies use
  `Path=/` in the inspected implementation, so a domain-change sign-in reset is
  not expected or required. Verify cookie behavior and any alternate path-scoped
  cookies instead of promising that every in-flight sign-in will survive.
- Existing Steam/account/key associations remain in the same backing database.
  Do not relink or regenerate them to achieve a cosmetic rename.
- `SURFD_BOARD_URL` is a single configured public board base in the inspected code.
  A same-host move changes the signed return path, not the origin-only realm.
  Drain old in-flight sign-ins and send new starts to the canonical path, or
  implement/test explicit old-path callback handling. Do not blindly redirect a
  signed OpenID callback to a different return path and assume it remains valid.
- Update online/privacy text to name the real service hosts. Decide whether the
  existing consent-version policy requires renewed acceptance; do not reset
  permissions or broaden collection simply as part of a rename.
- Saved endpoint migration must distinguish shipped defaults from user choices:
  migrate known old defaults once, retain custom/private servers, preserve a
  deliberate disabled state, and document how to opt out or change endpoints.
- Keep approved game hosts and directory advertising unchanged. Test old clients
  against rebranded servers and new clients against existing service routes;
  no new-host trust migration is part of the selected website-path scope.

## 6. Hosting and website-path work: who does what

**No new domain, DNS migration, certificate purchase, hosting provider, NanoPi,
map library, or leaderboard database is needed for this path rename.** Keep
`proto.bar`, `play.proto.bar`, `dl.proto.bar`, existing DNS/proxy settings and
Cloudflare R2 storage. HTTPS certificates cover hostnames, not individual paths;
the existing `proto.bar` certificate also covers `/worldofsurf/`.

Add scoped locations to the existing `proto.bar` nginx configuration, not a new
vhost. The new public path can use the existing internal site directory and backend.

| Work | Owner action/approval | Implementation deliverable |
| --- | --- | --- |
| Canonical website | Confirmed: `https://proto.bar/worldofsurf/` | Website, board and account paths under that base |
| Domain/DNS/TLS | No new setup or purchase; retain normal existing renewals | Existing hosts/certificates continue working unchanged |
| nginx routing | Approve deployment window and any required privileged reload | Scoped new locations, legacy compatibility routes, `nginx -t` and content checks |
| R2/CDN | Approve any new object prefix for branded releases, not a new hostname | Existing downloads retained; new keys/feed paths validated against readers |
| Steam/public integrations | Approve account-path cutover timing | Tested same-host sign-in start/return/unlink and updated links |
| GitHub/community | Approve repo/handle/display-name changes if desired | Updated remotes, badges, links and announcements |
| Cutover | Approve timing and compatibility/retention period | Measured rollout, rollback resources and provenance |

### Detailed hosting checklist

1. Inventory the actual live nginx locations, site assets, CDN cache rules,
   proxy/rate limits, active lobby ports, scheduled jobs, updater defaults, and
   deployment targets. Compare them with source before writing final commands.
   Read only the settings needed; never dump secret-bearing environments.
2. Keep DNS, nameservers, TTLs, certificates, current proxy modes, firewall/port
   forwards and any dynamic-DNS automation unchanged. Verify existing service
   health, but do not turn this path rename into a network migration.
3. Add `/worldofsurf` -> `/worldofsurf/` and scoped `/worldofsurf/` static locations
   in the existing nginx snippet/vhost. Retain the alias into the current site
   directory initially; the internal directory need not match the public name.
   Preserve prefix precedence so a missing game asset returns 404 rather than
   falling through to the unrelated root filebrowser application.
4. Add `/worldofsurf/board/` routing to the same backend `/board/`, with its
   existing route allowlists, rate limits and client-IP handling. Handle the
   slashless board URL explicitly. Do not expose administrative/write endpoints.
5. Review every more-specific route: signed `update.json`, the wordmark font and
   its MIME type, static assets, CSS/JS, social images and account routes. Ensure
   assets and links are rooted at `/worldofsurf/`, not accidentally `/` or the old
   base path. Preserve path-specific cache headers and installed-site markers.
6. Update the authored `src/release/ftesurf.nginx`, `install.sh`, `publish.sh` and
   `release.ps1` URL defaults, install/hash checks, probes and path guards together.
   Keep their internal site storage paths unless a separate migration is approved.
   The source filename can remain legacy; renaming it also requires all consumers.
7. Keep `play.proto.bar` API/map endpoints, advertised game hosts and lobby ports
   unchanged. Normal Cloudflare web proxying does not carry game UDP; retain the
   existing direct/DNS-only game routing and verify an outside-LAN connection.
8. Keep `dl.proto.bar` and its current R2 binding. New branded archive names may use
   new `worldofsurf/` object keys only after launcher/updater path restrictions are
   tested. Keep the existing prefix if a bridge is needed. Never overwrite old
   immutable releases or delete their keys for appearance.
9. Make `/worldofsurf/update.json` serve the verified signed feed and keep
   `/ftesurf/update.json` serving compatible signed JSON directly for older clients.
   Exclude it from broad redirects. Update no-cache/revalidation rules and client
   defaults only with tested publication/version/compatibility behavior.
10. Add narrowly scoped human-page redirects from `/ftesurf/` to `/worldofsurf/`,
    preserving deep paths, query strings and browser hash navigation. Keep native
    reader endpoints and signed account callbacks out of generic redirect rules.
    Do not redirect the `proto.bar` root or unrelated applications.
11. Stage new locations alongside the legacy routes, validate `nginx -t`, then
    reload rather than unnecessarily restart. Prove actual page bytes and routes,
    not merely status 200. Use temporary human-page redirects during testing and
    permanent 301/308 redirects once stable. Update canonical/social metadata and
    sitemap links if supplied; no domain address-change procedure is required.
12. Monitor the new and old paths plus existing service hosts: page content,
    account flow, a known board query, download bytes, signed feed, discovery,
    certificate renewal and a real external join. Retire specific old routes only
    when compatibility evidence allows it; `proto.bar` itself is not being retired.

## 7. Packaging, documentation, repositories, and tooling

Primary sources: `src/release/release.ps1`, `bootstrap.ps1`, `linux-bootstrap.sh`,
`linux-pack.sh`, `publish.sh`, `install.sh`, `ftesurf.nginx`,
`tools/updatefeed.py`, `src/build.ps1`, and `tools/release_tree.py`.

- Update release page/archive naming, extracted top-level directory, release
  metadata, checksums and checksum instructions, generated INSTALL/SOURCE/THIRD-PARTY
  text, source offers, and Windows/Linux startup instructions together.
  Proposed new public archive prefix: `worldofsurf-<version>...`.
- Separate URL base, bucket prefix, game identity, display title, and install path.
  Set the public site base to `https://proto.bar/worldofsurf`; keep the download
  base `https://dl.proto.bar` and existing internal site root. A new `worldofsurf`
  object prefix is separate from the website-path move and must pass reader and
  guard checks before use. Existing release parameters are not universal rebrand
  switches: several hardcoded names and guards still need coordinated review.
- Preserve the allowlisted ship set. Add new icons/wrappers deliberately; do not
  solve packaging by archiving the live install or copying its map/player library.
- Generate signed feeds from verified stages only. Publish and round-trip verify
  referenced immutable objects before making a new feed/page visible. Keep the
  signing trust and version progression intact; a rebrand is not key rotation.
- Review `README.md`, `INSTALL.txt`, `SOURCE.txt`, `ENGINE.txt`, `CONTRIBUTING.md`,
  `surfd/README.md`, current roadmap/backlog/test instructions, licence notices,
  and public download/source links. Preserve the legal licence texts themselves.
- If the game repo is renamed, prefer the slug `worldofsurf`. Audit GitHub settings,
  workflows if any, badges, webhooks, external integrations, clone URLs, remotes,
  source-offer links, and local automation. Verify old GitHub links still work;
  do not recreate a conflicting repository at the old name.
- Keep the engine fork's existing repository identity unless independently useful
  to change. Keep the shared Quakers launcher entry point/product unaffected.
- Audit test drivers, fixtures, smoke logs, tools with default executable paths,
  screenshot scripts, shell/PowerShell defaults, environment variables and their
  documentation. Add new environment variable aliases only with a stated legacy
  precedence policy; do not gratuitously break existing `FTESURF_*` setup.
- Do not rename `C:\FTESurf`, `C:\FTEQuake`, the engine checkout, private tree,
  other sessions' workspaces, or the agent workspace base as launch housekeeping.
  A later developer-folder migration must separately inventory IDE/clangd/project
  settings, shortcuts, task scheduler jobs, shell profiles and absolute-path tools.
- Update external community/server listings, profile names, invite landing pages,
  social assets, pinned posts, videos/descriptions and store listings IF they exist.
  This audit does not assert that Steam/itch/Discord/etc. accounts already exist.

## 8. Optional full technical rename: a separate migration project

If the requirement includes eliminating the legacy folder/binary names, budget a
coordinated migration, not another string-replacement phase. A consistent eventual
scheme could use `worldofsurf/`, `worldofsurf.cfg`, `worldofsurf64[.exe]`, and
`worldofsurf-launcher[.exe]`; finalize exact names before writing migration code.

### Changes that must move together

- Manifest installation/profile detection, `BASEGAME`, `MAINCONFIG`, and any
  protocol/game discovery identifiers; preserve old identities as compatibility
  aliases before attempting a switch.
- Build outputs, launch/debug wrappers, launcher restart/handoff, native updater,
  release allowlists, signed feed producer/readers, required paths and exec fields.
- Updater consent/state/locks/journals and crash/interruption recovery. Old and new
  names must not allow two independent update processes to modify one install.
- File mount/search/write locations, addon mount lists, downloaded maps/zones,
  caches, config defaults, backups, test harnesses, server launch/deploy paths,
  services/sudoers only if their internal names are also being changed.
- Map download URL layouts with both legacy and new gamedir components.
- Existing player-owned configs, binds, sensitivity, local PBs/runs, demos,
  screenshots, edited zones, installed/downloaded content, preferences and install
  identity. Preserve them; do not ship or expose them through a release.

### Choose one supported upgrade path

**Lower-risk default:** a separately downloaded World of Surf package plus an
explicit, owner-approved, non-destructive import/migration tool. Keep the old
installation intact. The tool must enumerate its approved data set, preview
conflicts, preserve user edits and identity, avoid following arbitrary links, and
refuse ambiguous cases. It must not copy an entire install/map library blindly.
Test rollback and ensure the old and new installations cannot run concurrently
against shared writable state. Do not reset identity to sidestep a migration issue.

**Higher-effort alternative:** an automatic in-place bridge release. First ship
readers/launchers that understand both identities and the migration journal, then
publish compatible bridge metadata to the old feed, then switch paths only after
safe recovery is proven. Older bootstrap binaries do not update themselves via the
ordinary feed; this constraint must be solved explicitly. A new feed with a changed
`game` field cannot simply be handed to an old reader.

For either path, build an idempotent transaction with backups, conflict detection,
interrupted-run recovery, explicit player consent where appropriate, and a tested
way back. A half-moved install must not be allowed to start as if complete.

**Do not rename historical recording/PB/cache/account-signing format tags for
appearance.** They may remain indefinitely. A future actual format change requires
versioning, backward readers, corpus tests, and the recorder/verifier/private design
review required by project policy. No evidence-semantics change is proposed here.

## 9. Execution order and gates

Each step is a bounded change set. P705 is the first verified presentation
candidate, not the full launch. Allocate further patches only for actual work;
do not bump the owner's QC Build number without the owner's decision.

| Phase | Work | Gate before proceeding |
| --- | --- | --- |
| 0. Approvals and freeze | Record approved name/site path; confirm scope/art; obtain current launcher source; freeze source/served hashes and inventory | Known baselines and ownership; no peer work silently included |
| 1. Brand kit | Wordmarks, small icon, OG image and representative game/web mockups | Owner accepts the art, compact label and longer-title layout |
| 2. Compatibility preparation | Dual website paths, preserved service URLs, legacy endpoints, account-path transition and updater bridge policy | Old/new matrix passes before any public endpoint is retired |
| 3. Parallel routing | Add `/worldofsurf/` nginx routes on `proto.bar`; same hosts/backend/storage | External HTTP/download/account tests; existing services unaffected |
| 4. Product rebrand | Menu/HUD/account/site/board/lobby labels, engine metadata, launcher copy and packaging | Clean builds, screenshots, regression tests and fresh-install checks |
| 5. Verified candidate | Isolated inspected commits; Windows + Linux archives; development deployment | Hash/source provenance and real-client acceptance on both installs/fleet |
| 6. Public cutover | Approved release, canonical website, new client defaults and announcement | Old clients still play/update; Steam links and records preserved |
| 7. Compatibility period | Monitor both website paths and unchanged service hosts; retain existing certificate renewals; fix route gaps | Evidence-based decision to keep or retire each dependency |
| 8. Optional technical migration | Section 8 only if approved and separately verified | Data/recovery/upgrade proof; not a blocker for public brand launch |

Suggested practical release strategy: first prepare a compatibility release while
old endpoints are still authoritative, then cut the public rebrand after the new
website path and art are accepted. If those can safely ship in one release, that must be proven
by old-client controls, not assumed. Do not change the game rules or erase records.

### Project execution constraints

Before implementation, read the relevant current AGENT_NOTES sections and create
an owned task root/OWNER.md before any isolated worktree or test overlay. Use clean
inspected commits for standalone verification and release/deploy. Pre-register
expected results and negative controls; zero new compiler warnings is required.
Product changes receive individual patch ledger entries under the normal max+1
allocation procedure; engine pins change only for engine work and QC Build numbers
only on the owner's Build decision. Commit/push verified features independently,
with an inspected index and exact inspected SHA; never sweep shared edits into them.

Normal development deployment still applies after verification. Windows engine and
plugins require the documented paired-install deployment; public lobby progs and
configs need their own explicit ship steps. `menu.dat` is client-local. Read the
full current Pi operations rules, respect occupied lobbies, retain `.prev` progs,
verify destination hashes/live behavior, and record UTC provenance. Public release
is separate: start with the documented `-Bump patch -DryRun` procedure plus the
current release script's required feed/bootstrap inputs, and verify final archives.

## 10. Verification and rollback

Write the final executable test matrix against the chosen scope before editing.
At minimum, prove these predictions with explicit controls:

| Area | Required proof / falsifier |
| --- | --- |
| Fresh Windows/Linux install | Extract actual archive into an isolated owned path; launch from another CWD; title/icon correct; menu, maps, mounting and offline play work |
| Existing installation | Custom binds/sensitivity/endpoints/PBs/account/edited zones unchanged; known shipped defaults migrate once and stay migrated after restart |
| Mixed versions | Old client/new service, new client/legacy routes, and new client/new service actually discover and join a dedicated lobby |
| Hosting | Known page bytes and correct MIME types; missing resources genuinely 404; old/new deep links, queries and board hash navigation work |
| UDP | A real outside-LAN client joins the advertised direct host; a working web page is not accepted as a game-network test |
| Downloads | Acted menu download and connected-client download, both map URL layouts, zones and replay; hashes/size match; missing file/fallback behavior preserved |
| Steam linking | Start/return/link/restart/unlink under `proto.bar/worldofsurf/board`; same-host cookies verified; old bookmarks start safely; expired/in-flight old state fails helpfully or completes through a tested transition |
| Rankings | Same accounts, player associations, records, source tiers, filters, replay and run-line behavior; display labels change but storage identities do not |
| Updater | Old bootstrap and new bootstrap/native reader each fetch supported signed metadata and perform a controlled real update; custom/offline/declined-consent cases stay so |
| Update failures | Invalid signatures, disallowed destinations/paths, interrupted apply and locked files still refuse or recover; rename does not bypass existing gates |
| Presentation | Screenshots at multiple resolutions/UI scales; mobile site/board; Windows file/taskbar identity; Linux desktop entry if supplied; social preview pixels |
| Isolation | Shared FTEQuake/Quakers product still correctly identified and runnable; unrelated web applications unaffected |
| Asset/content shipping | Allowlist-only archive; new asset paths present; no private data/maps/keys accidentally added; old legacy assets retained only intentionally |

Relevant existing suites to select/run in isolated fixtures include
`surfd/test_web.py`, `surfd/test_accounts.py` (including Steam behavior),
`surfd/test_board.py`, `surfd/test_join.py`, `surfd/test_replays.py`, and newer
main-branch `tools/test_updatefeed.py`, `tools/test_update_launcher.py`,
`tools/test_update_wrappers.py`, `tools/test_update_publication.py`,
`tools/test_release_retention.py`, `tools/test_ingame_update.py`,
and applicable native recovery/handoff tests. Do not assume every script is a pure
unit test; inspect its fixtures, network actions, deployment targets and cleanup
contract before executing. Update tests that intentionally assert visible copy,
not tests that pin legacy on-disk contracts. Add explicit dual-name/dual-path tests.

If evidence readers or semantics change at all, the project's mandatory
`python tools/test_reccheck.py` and run-corpus fault-count gate also apply, with
private design/contracts read first. Keeping evidence formats untouched is preferred.

### Rollback is different for pages, clients, and signed updates

- Keep reviewed nginx route configurations and prior static web assets. Restore
  routing/page assets without dropping legacy paths or unrelated sites. DNS/TLS
  and service hostnames are unchanged by the planned cutover.
- Preserve player/account data in place. A normal brand rollback should not require
  restoring an old database over newly submitted runs or new account links.
- Keep prior development progs/binaries/config backups under the normal deployment
  procedure; restore only known compatible sets, after coordinating live players.
- Signed update publication is forward-only in the inspected pipeline. Do NOT
  roll back by overwriting an immutable archive, replacing an existing version,
  or moving the signed feed to an older version. If shipped client code is bad,
  publish the corrected/reverted content under a NEW version and valid signature.
  Separate static page rollback from signed feed progression when planning tools.
- For any technical migration, prove interrupted recovery and restore before
  allowing real player data through it. Never delete the old install as cleanup.

## 11. Definition of done and owner handoff

The public rename is complete when:

- [ ] World of Surf is consistently the player-facing game/site/download identity;
      WOS is the intentional compact badge, not a mixture of old/new labels.
- [ ] New art, icon and social preview are accepted and actually shipped/served.
- [ ] `https://proto.bar/worldofsurf/`, its board/account paths, existing TLS and
      download hosting work externally; unrelated services remain unaffected.
- [ ] Fresh and upgraded Windows/Linux clients launch, play, join, link accounts,
      read boards/replays, download maps/zones and update correctly.
- [ ] Existing accounts, records, settings, local content and identity remain intact.
- [ ] Old URLs/launch paths/update endpoints have a tested compatibility policy.
- [ ] FTEQW/third-party credit, licence/source offers and engine provenance remain
      accurate; no claim is made that the FTE engine was authored by this project.
- [ ] Remaining FTESurf occurrences are inventoried as intentional compatibility,
      attribution/history, or explicitly approved follow-up work.
- [ ] Delivery records distinguish source committed/pushed, binaries built, development
      deployed, public released, and live verified, with their exact hashes and UTC.

Owner handoff should include: approved brand kit; final same-host path/redirect map;
nginx/publication checklist; changed-source inventory; release and verification
receipts; rollback/forward-fix runbook; and the specific legacy endpoints/identifiers
being retained, with retirement criteria. No domain purchase or DNS transfer is part
of this handoff.

**Immediate next step:** review `src/brand/index.html` and the P705 mobile/desktop
screenshots; confirm the art and public-only versus full-technical scope. The user
has now authorized staged implementation; live routing, signed-release cutover and
player-data moves are not implied by this source-only presentation candidate.
Keep the remaining phases bounded and compatibility-tested.
