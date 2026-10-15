# AGENT_NOTES.md

## P722 schema20 guard compatibility and acceptance bounds (2026-10-15)

Offline transition tooling now accepts immutable integer target_schema19 or20;
legacy manifests without that field still mean19. Schema20 pins the original six
KSF paths plus accounts.py/social.py and requires a strict schema20 external
receipt. Guard/candidate/dispatcher synthetic Linux suites pass (dispatcher22
checks). No live migration, generation rebind, lock reset or measured acceptance
is supplied. Never change an existing manifest or open a second guard to bypass
an old CLOSED fence. Eight hashes are a coordinated deployment group, not full
runtime/import closure: proof verifier, Steam, top-up, effective config and fresh
serving-worker origins remain external acceptance obligations. A social poll is
mutating (expiry, presence replacement, ACK), not a safe read-only health probe.
Version metadata reset alone is not rollback/recovery. See tools/p722friends.md
and tools/surfd-transition-guard.md; no unchanged client suite was rerun.

## P722 — Steam friends, roster and overhead names — 2026-10-15

Final continuation: real dedicated QC transport now proves 41/42/64 complete
roster rows across >16s; whole-array uri_escape truncates at 42 populated rows
(8192-byte builtin output limit), so encode each bounded row before concatenating
encoded array delimiters. The old encoder mutant preserves41 but rejects42/64.
Automatic capability renewal needs pending state + bounded 15..300s backoff,
not one Account_Hello call. Server-owned renewal must survive the finite client
hello budget and defer only LIVE link state: stale tags and expired PINs can
persist even with no active poll. The VM fixture tests actual Think/nonce logic
with only its terminal nonce stuffcmd replaced, then the real three-client rig
forces the first renewal HTTP reply503 and proves a fresh proof/list recovers.

Both new lists need explicit hover-gated wheel ownership, including release
AFTER the pointer moves away. Use av_pg0, not nonexistent av_tab0, in the rig.
friend_row wire order is who relation online encoded-name encoded-server
encoded-map. Synthetic snapshots must restore the genuine Bob row before PM
controls; missing hover targets otherwise leave the cursor over a fake Remove
and make the subsequent click test the wrong action. Never count that as a
product privacy failure or waive it as success. Keep failed arms. Use stable
account IDs AND cancel a retained fr_list press on snapshot replacement; native
hold/reorder control proves cancellation, not just a source argument about IDs.
`live-final3/verdict.json` passes all23 controls, including PM isolation while
Third is present, real roster chat/voice mute, Spectate and Join reconnect.
A later native TEST-ONLY Players fixture (`tools/players_smoke.py` and
`tools/fixtures/players_roster.qc`) proves 64 synthetic rows reach visible index63,
search-result selection renders Profile_DrawOn, and Back restores the bottom
scroll at1280×720 and800×600. The fixture intercepts roster-key reads only in its
owned source overlay; its manifest/instrumentation never enter shipped QC. Search
replies are loopback synthetic data, not account authority; query entry uses the
existing scores-find twin and gestures use production SUI input. Each size has
an inert one-real-row control, unacted dropdown, fresh roster-draw generation,
pinned/Players-tab checks and screenshot pixel differences; visual review is
still required. Final rig passes30 checks and11 non-native lifecycle/grader
controls. Never put subprocess.run(timeout=...) around a cleanup-owning runner:
it kills the wrapper before its finally can reap native handles/remove junctions.
Retain a timed-out wrapper and mark OWNER BLOCKED/cleanup-unverified; a successful
exit also needs explicit native/compiler-idle and no-junction observations.
Synthetic delayed-setup/cleanup-failure controls prove the lifecycle behavior. This is NOT64 genuine clients,
physical input, nonempty profile-times rows or busy-lobby performance. Initial
BuildNumber setup failure stays failed evidence: build.ps1 has no such parameter.
The last measured live schema was18; P717 transition is a concrete backend
deployment gate, not permission to install schema20 or reset user_version.

Friends are a private Steam-account graph, NOT a local file or unproven GUID
lookup. Only the existing verified connect/confirm signature/code path mints
lobby-only capabilities; `social.py` stores hashes, binds node and rechecks
keylinks/bans every use. Sessions expire24h, full-node snapshots run every5s,
presence expires16s and Join resolves the directory again at click time.
Multiple connections may prove even the SAME copied key: `(pub,node)` must NOT
be unique. Refresh retires only its explicitly supplied previous capability.
SSQC refreshes invalid sessions through Account_Hello; disconnected/recycled
slots cannot receive an old reply. Pending requests disclose no presence.
Messages require mutual acceptance/live presence, expire120s, max160 chars /
320 UTF8 bytes, 32/recipient, 2048 total, 20 actions/minute/Steam account across
installs. IDs/ACKs pass through QC as decimal strings, NEVER float32. Deliver
max2/poll and ACK after reliable private enqueue. No public reader or proxy
allowlist addition. Messages are operator-readable, NOT E2EE. Banned/deleted
peers remain removable as unavailable rows so they cannot trap the quota.
Eight-hex online marks and exact12-hex profile handles resolve unambiguously.

Pace lists four rows/100ms into separate client staging storage; swap only at
friend_end. Do not dump128 rows into a reliable packet. A currently proven
Steam player needs NO run history/profile response for Add from their profile.
Own legacy GUID-board stats still use *phash; photos/friends use server-owned
*ahash. Players_Panel and the native overlap rectangle are gone: Players is a
full-width SUI list-view tab. Other-profile ESC must run BEFORE
Profile_FieldEvent, or focused search consumes it. Message transfers keyboard
ownership to the existing chat draft, with a private target instead of say.

Labels reuse poses. PVS alone does NOT prove wall visibility: use the solid
trace. Near admission is forward dot>8, not project() depth sign. At most one
visibility scan/0.5s/body; name reaches0 at1024 units and picture centers. Detect
teleports from CONSECUTIVE FRAME deltas, not cumulative travel since the scan
(which blinks while surfing fast). Hide under opaque profile/board to preserve
photo budget. Steam photos use64 slots; SPIC_MAX intentionally does NOT reuse
spawnpoints' SP_MAX macro.

Rigs use real clients/proofs and synthetic Steam accounts, NOT live Steam/R2:
Add via profile, private draft/recipient-vs-third-party isolation, spectator
account, upload+disk cache, full-width roster and focused-search one-ESC close.
Two real bodies exercise labels. tools/p722labels_fixture.qc is TEST ONLY,
never in cl_progs.src/ship build: real body/PVS, temporary overhead point, real
world wall trace. Far mode forces admission only to isolate fade geometry.
Near/far/wall/behind controls pass; removing LOS and pinning alpha1 produces
expected failures. First arms raced acceptance / left players overlapping at
spawn; retained FAILED, not passes. Reader mistakes: QC files are under
**data/cache**, and final disconnect correctly zeros seen. Renewal proof is a
fresh issue timestamp PLUS delivered friend_end after refresh, not final seen.
See tools/friends_smoke.py and tools/playerlabels_smoke.py.

## P715/716 — Steam persistence, KSF profile positions and measured coverage

- The picture origin already caches JPEGs AND32x32 RGBA text. R2's optional
  allowlist must match actual40-hex filenames, not17-digit SteamIDs. Give an
  independent picture publisher `manifests/avatars.json`; never replace the
  map publisher's `manifests/public.json` with a picture-only inventory.
  Authenticated readback is storage evidence, not a CDN cutover. R2 origin
  delivery has deliberately NOT been switched by these patches.
- `cl_steampic.qc` persists validated bodies in256 direct-mapped disk buckets
  under the engine's client data sandbox. Full SHA256(origin + newline + mark)
  plus UTC-day headers guard prefix collisions, stale data and other origins.
  Cache hits must still rebuild renderer textures. p715pics proves cold-write,
  warm fresh-VM and vid_restart zero-HTTP DRAW, and corrupt/expired/collision/
  origin/non-hex misses with actual quadrant screenshots. Strictly validate
  hex/newline bytes: stof of damaged hex may otherwise silently draw black.
- KSF's `bestrecords/<n>` n is a START POSITION, not a requested record count.
  Its own UI uses1,6,11,...; real replies say limit5, offset(n-1), total:null.
  Critically, real valid records have `record_id:null`! Identify completions
  by main map/style, preserve null identity, and never manufacture demo/board
  authority. Existing PB writer rules remain responsible for ties/replays.
  Manual seed heads now ask position1 and use a new head-cache filename.
- Schema18 adds only `ksfprofiles`. Resolved game/site profile views enqueue
  32 active players at most, coalesce pending work, and refresh completed walks
  after24h. Queue writes wait50ms max; an importer lock cannot hang browsing.
  ksfimport's existing shared lock, total request budget, pacing and host-wide
  refusal park govern up to3 profile pages/tick, round-robin selected players.
  Persist source first (fsync writable handle; Windows rejects fsync on rb),
  file PBs FULL/idempotently, then checkpoint cursor. A repeated correctly
  offset short/empty page ends that STYLE; all4 are needed for complete.
  Wrong shape/offset, refusal, local failure or safety limit never says done.
- Profile counts can grow while the crawl runs. Game/site show queued/partial
  status and excluded-unavailable counts, not an instantaneous full-archive
  promise. Reads never call KSF synchronously. The1000-row board cap and200-row
  profile total cap were CLIENT limits, distinct from a200-row HTTP-page cap:
  both client stores are now bounded10000 with the original small requests.
  p716paging real CSQC held1050 board rows and1005 profile rows and observed
  actual offset1000 requests. Its first too-fast fixed scroll loop stalled
  at750; wait for append then scroll the NEW end instead of treating elapsed
  sleeps as evidence. Final paging and P715 regression passed; screenshots read.
- Coverage audit:759 approved Momentum maps on the Pi all have timing.197
  installed Beta/extra maps do not. Windows missed37 approved timings, but36
  have different BSP hashes; old matching BSPs on the Pi have no archived JSON.
  Only bhop_perspective matched exactly and was restored missing-only to BOTH
  Windows installs, preserving all existing local edits. Missing old-build
  zones are not safely supplied by renaming the latest official JSON.
- Deployment/rollback: ship app+ksfprofile+ksfimport together (planner enforces
  this), and include test_ksfprofile in the Linux suite. Schema18 is additive;
  rollback to schema17 code requires resetting user_version to17 under normal
  deployment exclusion (the new table may remain), not restoring an old DB
  over newer player/run history. Engine pin/tag and QC Build are unchanged.
- First staged Linux suite correctly refused to deploy: test_board still
  pinned schema17, the account DDL race fixture counted11 instead of12 CREATE
  boundaries, and the stage omitted src/release/ftesurf.nginx required by the
  existing public-proxy test. Update the test's explicit head to18 and race
  EVERY boundary including ksfprofiles; include the exact committed nginx
  fixture in StageFiles, NEVER in deployed Files/Destinations. Keep the failed
  suite evidence, rerun the whole suite rather than waive a failure. Matching
  Windows board/account tests and the new stage-only allowlist control pass.
- Restored bhop_perspective was driven in an isolated one-BSP fixture: SSQC
  read10 zones from maps/zones/local, zone_goto reached the start, walking out
  made cmd timer report running and recording1. A sparse content rig did not
  mount that map's online alias; its first load timed out. Copy just the exact
  BSP plus JSON into the owned fixture, not a whole install or canonical map.
  Reader regex must match the actual `(maps/zones/local)` origin, not `(local)`.
- DEPLOYED / VERIFIED by 2026-10-14 20:40:21Z: progs from clean QC 2d2aa6b,
  all three in both Windows installs; seed checksum 8b0e6df8 in both. Pi qw/cs
  hashes 39c5c945457003fd... / ad2bd7e5bb055b21...; build.ps1 -Pi proved all
  twelve empty, kept .prev and restarted all; later all twelve answered UDP.
  Backend matched seven-file caabd99 ship-set, full staged Linux suite passed
  (MOMGRAB real sample absent/known skip), mode600 SQLite backup, same-master
  graceful reload/health. First failed suite retained until successor accepted,
  never waived. Live schema18 view queued; real shared-pacer tick filed five
  source rows and advanced 1->6; normal cron reached21/four pages. Public HTTPS
  JSON says partial and public JS hash matches. Do NOT call it a full archive.
- R2 publisher runtime is intentionally retained at
  `/srv/nvme/agent-work/pictures-coverage-d25cd9e/`: private config/state plus
  publish-pictures.sh, publisher.lock/log, OWNER.md. A unique user-cron entry
  every10min holds flock around250 JPEG then250 RGBA copies; transport upload
  and full-body readback verify before publication. Existing cron lines were
  preserved/checked. Continuous bootstrap process was stopped only after PID,
  start-tick, PGID and cwd checks. This root is required by the scheduled job,
  NOT abandoned scratch; migrate the service/cron before ever retiring it.
  Seeding remains incomplete. Public CDN delivery was not switched or proved.
- A failed search is not absence: actually retrieved public candidate indexes
  from dPexxIAM/Momentum-surf-zones (201 legacy KV zones) and
  InSelfControll/bhop-zones (mapzones SQL,873 names). They name15/14 surf/bhop
  Beta gaps and5 old-build approved gaps; source names alone do NOT prove fit.
  Keep conversion/build/trigger controls open in BACKLOG, never execute the
  SQL or promote it by name. Live Beta missing count was196 by the later audit.


## Patch 693 — profile seeks, editor wheel and entity-pose rendering

- A profile-time handoff now includes rank/handle/milliseconds after its five
  scope tokens. Eight-character board marks and twelve-character profile handles
  both work; match SHA256(player)'s same-length prefix AND milliseconds, not a
  display name. The board's first offset is rank-6 (bounded at zero); every next
  page/reply check includes that base. Scope/tab changes reset it. Keep earlier
  and top navigation available after a distant seek.
- The editor wheel only acts with the pointer inside its panel, and advances two
  list rows per step. `zone_edit mouse` is a TOGGLE, not `mouse window` as a setter.
  Test Mouse2 both ways and look-mode placement back. Jump-bound wheel and space
  must not switch cursor ownership. `zone_edit status` exposes first list row.
- A failed P693 control acknowledged `zone_edit pointer`, but separately sent
  wheel down/up both returned took0 and the row stayed0. That did NOT prove why
  it declined: neither effective pointer nor intervening native events were
  logged. `tools/test_p693_ui.py` now batches pointer/down/up/status on one
  physical stdin line, refreshing the prerequisite for BOTH directions. Require
  exact ordered paired receipts, inside took1 and row0->2->0, outside took0 and
  unchanged row/cursor, and one fresh clean status. Keep placement-back in its
  existing look-mode chain, with no injected pointer and no save writes. Offline
  dispatch/transport mutants and actual Cbuf extraction prove only their stated
  host boundaries; actual acceptance needs authorized control-before-subject.
  That gate closed on2026-10-14 as recorded below.
- Native Windows plugin stdin has a256-byte buffer with room reserved for NUL.
  Count the terminating newline: require `len((packet + '\n').encode('ascii'))
  <256`, NOT merely a bare packet <256. An accepted255-byte bare packet can
  fill the buffer without its newline and stall dispatch. The actual Python
  sender boundary tests accept254 bare bytes and refuse255 before any write;
  the old guard is an acted negative mutant under both normal/-O. Current wheel
  packets are short; the ACK occupies a separate physical line.
- A positive ent_view face census was NOT evidence of visible faces. The current
  compressed tensor2 *36 model has local bounds [-48,-24,-64]..[48,24,64], while
  its entity origin is far from zero. Original hull emission used model vertices
  without the entity transform. P693 publishes precomputed poses and applies
  translation/rotation only to entity brushes, never world clip brushes. Do not
  guess the pose from old map coordinates; compare the native census origin to
  the current QC pose record and inspect pixels. Source additive portal material
  can make the red fill look pink; an interior red-tint crop, excluding boxes and
  labels, distinguishes the subject from the original (554 vs 0 in the acted rig).
- Exact profile-time focus must preserve integer milliseconds across JSON,
  full/compact row storage and the CSQC/MenuQC decimal mailbox. Float32 conflates
  16777217ms with16777216ms, including same-identity changed times. Keep exact
  ints separate from existing display floats. QC sprintf `%d` expects a FLOAT
  slot (F324 for int), so `itos` plus `%s` preserves the raw integer. Menu integer
  conversions are name-only in pr_menu.c: use `#0:stoi`/`#0:itos`, NOT CSQC fixed
  slots259/260. Trim leading zeros for the lexical decimal bound check BEFORE
  conversion. Pinned native4148e7292's PF_stoi (pr_bgcmd.c:4886) uses decimal
  libc atoi, NOT octal autodetection; pr_menu.c:2713 resolves to that function.
  A compiled-helper trim mutant proves canonical output, not an octal failure.
  Boundary runtime gate: p693ui.md. Fresh2026-10-14 acted PREINTEGER control
  selects1500 for16777217/16777216; integer subject passes all5 groups and6 exact
  typed full/compact changed/equal witnesses around2^24/INT_MAX. All12 PNGs
  inspected; independent audit OK with notes/no issues. Four owned PIDs/eight
  junctions gone;136 protected pins/36 install hashes+metadata unchanged. Exact
  repo-status postflight remains NONMATCH only for peer untracked694 launcher
  claim, not a native/progs/ref/index drift. Runtime scope is fixture/fallback/
  synthetic input/current poses; no real backend/native-provider/clipboard/live
  nonzero-mover claim. Commit/build/push/destination/live verification remain
  separate; retained source acceptance receipt at the owned root's artifacts/
  runtime-live/precision-acceptance-20261014T044940Z.json.
- A baseline exit0 only retains failures. `--precision-control` additionally
  requires the known float32 collision's fresh JSON/status witness and passing
  predecessor profile/editor/faces regressions. The subject needs all five groups;
  images remain a separate inspection. Exact integer prints must be from the
  current case's log interval. Parse selected ranks numerically: a substring
  check for#1 also accepts#10. Subject receipts require all6 typed raw-ms/rank
  witnesses and input hashes for all5 sibling plugins as well as executables.
  Reject output/OWNER/report aliases before creation; exclusively reserve the
  first report. Driver verdicts BLOCKED/failed/evidence/control/subject are
  distinct; process-free driver tests are NOT product acceptance. Standalone
  qclib/fteqcc helper tests likewise do not verify menu builtin name linkage or
  UI/socket/GPU behavior. FTE LOADP_F/STORE_F can copy raw integer bits: see the
  shared int cases in qclib/execloop.h, rather than guessing from opcode names.
- A delivery helper using assert can lose every safety check under python -O;
  exists()-guarded lstat misses dangling .prev/stage links. Pin both destination
  and .prev before staging, exclusively stage before visible swaps, and retain
  an atomic first-predecessor receipt across interruption. The retained P693
  helper refuses ANY existing transaction rather than automatically retrying.
  Seventeen fake-install tests pass under normal/-O, not real delivery acceptance.
  Native/plugin hashes must match the accepted build AND control/subject inputs;
  an image with an absent file/null hash is NOT an inspected screenshot.
  A confirmation JSON/process scan cannot prevent an unrelated launcher: an
  owner/peer-coordinated exclusion must cover the whole real multi-file interval.
- `tools/test_p693_ui.py` extends the isolated navigation rig with current consent
  version/addon mounts, actual full/compact profile time picks, pointer-targeted
  editor keys and viewer screenshots/censuses. Older base fixture consent4 and
  missing addon mounts were setup failures, not product failures. It never saves
  editor drafts through content junctions. `tools/test_entview_pose.py` compiles
  actual native pose/emitter/AngleVectors under fast-math and rejects four acted
  mutants; its fixed winding is NOT a BSP/GPU test. Source and deployment receipts
  are separate. Historical fixture/artifact p692 labels predate a peer's published
  P692; this task's one published patch claim is P693. See tools/p693ui.md.

## Patch 684 — viewer controls and shared SUI ownership (13 Oct 2026)

- A later front panel can draw valid hit boxes yet have dead buttons: an earlier
  replay `sui_end` cleared its release queue. Suppress the background playback
  bracket while another modal owns the cursor; do not stop the camera/HUD/clock.
  The native board's front-input gate must also ignore the background watch claim.
  Actual line/replay clicks, not console twins, are the acting control.
- A mouse motion that wakes SUI returns before rebuilding hover. Replay must
  re-test the current hit list on mouse-down, just as the board does. The new
  clock Play/Pause click exposed this: down/up were taken but had no held/released
  ID until that refresh. Keep an actual first-click arm, not just a paused cvar.
- Spectator pose saves use the existing untimed view-snapshot path. The pose
  helper belongs in cl_spectate (body-stream declarations are later than rewind);
  cl_rewind calls a prototype, not those later globals. Test a real second client
  whose watched position differs from the parked body, plus load and exclusive-pin
  readback. Preserve missing-pose refusal and the native server-history gate.
- `tools/viewer_ui_smoke.py` owns only thin source/runtime overlays beneath an
  OWNER.md root; its synthetic key lives only in the isolated server cfg. Real
  lobby saves otherwise refuse at the identity prerequisite. `waitmap`, post-spawn
  menu_restart/ui_close and a delay after the final server probe are prerequisites,
  not optional timing polish. Its two clients are stopped only by owned handles.


## P683 visual continuation — 12 Oct 2026

- Demise's apparent horizontal background seam was the HUD strafe bar, not
  mist/sky geometry. Pre-boot invisible mist, black-fade and colour sentinel
  controls left it; `hud_strafe 0` removed it, cold native `1` restored it.
  y336 at1280x800 agrees with `hud_strafe_y 0.42`. Disable HUD tracks before
  classifying a world seam; do not diagnose one from a screenshot alone.
- Mist-hidden native-mountain fog A/B/A: crop MAD21.684/255, repeatMAD0. Authored
  black world fog45000/200 becomes skyroom11250/50 at scale4. This identifies
  fog contribution, not Source-settings parity or a reason to ship fog off.
  Scrolling mist phase cannot be an exact reference-frame gate. Compare static
  regions with fog/sRGB/HDR pinned before changing the known fog approximation.
- Water-in-view old/current P683 product pairs pass on `bhop_monster_jam` at
  body256/13664/8128, angles89/0/0. Water crop500,160..850,480: modes1/3 identical,
  mode2 one channel off by1 in one pixel; adjacent opaque crop identical in all
  modes. A separate3/0/3 water actor changes all123200 wet pixels (MAD53.746),
  repeats exactly. The BSP center camera512/13824/8128 sees a narrow walkway:
  choose wet crops explicitly. Near-normal mode1/2 equality does not prove
  oblique depth accuracy or underwater fog/physics; control VMs predate P683.
- `conbridge send` rejects lines longer than240 bytes. A redirected error plus
  shell `;` let a280-byte preparation fail while later screenshots still ran.
  Treat that arm as failed; split commands, inspect preparation outputs before
  capture, and verify acted shader/cvar readbacks. Cheats reset on restart;
  a remap is denied until the owned server enables them again. No empty remap
  reset/VFS chain needed: cold boot and retirement restore native materials.
- Physical Kitsune secret-button acceptance is excluded at Lex's direction,
  not upgraded to a pass. Normal Alpha0/rainbow-hidden evidence remains valid.
  Details/retained failed arms: `tools/p683mapvisual.md` continuation section.

## Patch 680 — inert reset preparation and measured harness pitfalls, 12 Oct 2026

- `setorigin` only relinks; `SV_TimerWarped` does not clear ground. Canonical
  reset preserves the immediate groundentity/FL_ONGROUND and completed duck;
  the next move categorizes it. Save-load has different ground-clearing policy.
  Never derive a reset policy from save-load just because both teleport.
- Read-only canonical destination/save selection still updates trace_* scratch.
  Live wrappers alone retain missing-target diagnostics/cache and save scans.
- A copied client/server exe needs its matching sibling native plugins. Without
  hl2, mounted Source BSPs report unrecognised VBSP; without mounts, dune is absent.
  Neither failure is an acting movement control. Freeze plugin hashes too.
- This fteqcc crashes (3221225477) on `d->angles_x` through a struct pointer.
  Isolated one-factor compiler controls: whole-vector comparison and typed or
  untyped null arguments compile 0 warnings; direct component access crashes.
- A short solid box lets the downward trace escape to its floor. The initial
  solid-fallback fixture failed 1/64. A tall 4096-u box acts across the complete
  drop; real startsolid plus actual live fallback parity passes. Do not bless
  an unacted fallback branch just because its final origin looks reasonable.
- A start-save can pass selection and fail post-snap occupancy. Zone fallback
  must discard its saved pitch too: an acted 2/71 mismatch became 71/0 with
  explicit fallback pitch zero. First high-slab fixture had no eligible row
  (1/71 actor failed), so its green fallback assertions were NOT evidence.
  Build the slab around actual point/hull occupancy; those rules are map-latched.
- See tools/p680zoneprep.md for 71/0 reset controls, 66/0 load/release regression,
  acting negative controls and explicit non-activation limits. Source-only slice;
  no new install/fleet/native/Build or recorded-evidence deployment claim.

## Patch 674 — UI/maps deployment checkpoint, 12 Oct 2026

- Product `79c3599`, deployed tree `61d291d` (merges published P673 docs only),
  engine documentation `7b0972d57`. Clean proof build at the inspected commit:
  all three QC programs zero warnings; source/preservation guards pass and the
  output hashes equal the tested subject. No engine source/pin, server QC,
  evidence/ranking/schema/default or Build-number change.
- Backend 05:51 UTC: `surfd-deploy.ps1 -Ref 61d291d -Only
  @("surfd/surfd.py","surfd/test_web.py")`; all 17 staged suites pass on the
  NanoPi (momgrab's unavailable MTV conversion fixture explicitly skipped).
  Both installed files hash-match. surfd.py sha256 `b9101630701f1ce2`, worker
  reloaded, `/health` healthy with 12 lobbies. Database rollback retained as
  `data/surfd.db.bak-61d291d-20261012-164812` (mode 600); file predecessors
  `*.pre61d291d-20261012-164812`. No backup pruning. Live HTTP positive known-name
  filter preserves the account/rank and echoes the query; negative nonmatch
  has zero rows/counts. Last 100 app-log lines: zero ERROR/WARNING/Traceback.
- Windows 05:55:21–05:55:25 UTC: file-only deployment from the clean proof to
  BOTH installs, hashes read back independently. csprogs `444f921987a6b317`,
  menu `d111ec13ee2827f4`, each previous pair retained as `.prev`; unchanged
  qwprogs `7598b0da1cd90ebd`. No executable/plugin, process, config, fixture or
  default touched. The already-running owner's client is not restarted and
  does not prove the new local UI ran; restart for the new menu/local client.
  Eleven staged variant-zone donations rechecked FIT against each install's
  preferred BSP and copied with exclusive missing-only creation. Primary's
  existing 609 local files (including edited bhop_eazy) hash-identical; secondary
  previously had no local JSONs. Both now have the eleven additions.
- Fleet DEPLOYED 06:03 UTC: the initial one-player gate cleared; all 12 rows
  present and zero-player. `build.ps1 -Jobs 8 -Pi` from CLEAN proof/src at
  `61d291d`, zero warnings, no force. Uploaded .new hashes checked before swap;
  live qwprogs `7598b0da1cd90ebd`, csprogs `444f921987a6b317`, .prev retained
  (csprogs predecessor `825c2b46d41aa8a2`). All 12 units restarted successfully.
  Independent remote hash readback matches, every unit active, 12 fresh
  zero-player heartbeats (age0–5s), and all 12 actual UDP status sockets answer.
  No new engine/config/default or zone files shipped to the lobbies.
- Runtime limits: fallback whole-board filter/count/rank/clear, missing/stale
  echo rejection, held-TAB refusal and LINE/WATCH arms passed. Owner/map/wheel
  assertions needed harness corrections and the complete rerun is blocked by
  the foreign client; native actions, paste and final tier pixels remain open
  in lextest. Never treat their source guards as runtime acceptance.
- Harness lessons: wait for CSQC spawn before finding the HWND; acknowledge
  each console dispatch, especially after screenshots (the engine blocks on
  their writes). Fixture account marks use FS_GuidId's eight characters, not
  twelve; stop WATCH with `replay stop`, not an invented `replay close`. Search
  roster requests use `/api/board?players=`, not only `/api/players`.
- Retained owned task root: `C:/FTESurf-worktrees/ui-maps-20261012T0335Z/`;
  `proof/` is the inspected deployed tree. OWNER.md/CHECKPOINT.md and artifacts
  hold build/runtime/hash/preservation evidence. No task processes remain.
  Retained for incomplete UI acceptance and unique parent evidence; inspect
  ignored paths and shared-content junctions before retiring disposable copies.

Detailed working notes, moved out of pi.dev's always-loaded AGENTS.md. The short
AGENTS.md is the startup contract; read relevant sections here BEFORE changing
that subsystem. Older references to AGENTS.md's detailed sections refer here.
Keep new operational findings here, not in the startup brief. No historical
findings were removed in the split.

## Patch 670 — shared booster gates and reset prediction, 12 Oct 2026

- surf_deoa's nine 400-u/s boosters have DUPLICATE OnEndTouch keys: !self
  Disable at zero delay and !self Enable after one second. A lossy entity dict
  shows only Enable and suggests an unsafe no-op fix. Use bsplib.read_pairs.
  The old client demoted all nine; the 6-unit train is 400 * 0.015, not a map
  tolerance issue. P670 receives authoritative continuous-push gate state on
  the CSQC entity stream, including other players' gate changes. Unknown state
  stays server-only. Once/speed/name/movement-write demotion stays conservative.
- Acting dedicated controls at (6180,-1444,-668): OFF had 49 repeated ~6-unit
  errors, ON one entry seam and no sustained train; the ON result survived
  100 ms added packet delay. Peer gate on/off/on, independent avatar samples,
  reconnect and the older server's all-unknown fail-closed arm acted. Actual
  loss/reordering and shared re-entry under delay are NOT verified; BACKLOG.
- surf_hourglass's tested map teleport landed at (104,0,969); noclip+jump
  bypassed it and releasing jump predicted it without a correction. !r used
  (104,0,800) and still corrected. That distinguishes a server-command reset
  from a map teleport; it does NOT establish what caused the operator's exact
  historical seq 630. Camera anticipation in save/rewind is not body prediction.
  The requested acknowledged reset/load/rewind operation is unbuilt (ROADMAP).
- `build.ps1 -NoDeploy -Pi` is refused BEFORE compilation. For an isolated Pi
  deployment, use the inspected clean worktree's normal output paths and `-Pi`
  without `-NoDeploy`; verify those paths/hashes against the tested artifacts.
  Never point it at uncommitted peer source. P670's pair was byte-identical.
- DEPLOYED to the twelve empty Pi lobbies, completed by 02:08:08Z: qwprogs
  `915dfa31bf20917c`, csprogs `e2f8a9c144201116`, `.prev` kept, all restarted,
  remote hashes read back. A fresh isolated client on 27510 loaded CSQC on
  surf_kitsune, received push *64 ready/on and ran the prediction hook. HUD
  screenshot inspected (missing imported materials in the overlay are not a
  renderer acceptance). No terms accepted or ranked run submitted by the smoke.
- WINDOWS NOT DEPLOYED: the quiet-before-lock check found other sessions'
  live engines and refused before touching either install. Do not stop those
  processes. Source is pushed as 25746cb; pair and guarded deployment script
  retained under C:\FTESurf-worktrees\prediction-20261012-0125 pending quiet.


Working notes for coding-agent sessions in this repo. Read CONTRIBUTING.md too
(git identity, `git clean -x`, line endings, `.src` ordering).
pi.dev subagent setup and its read-only smoke workflow are documented in
`.pi/README.md`. Native roles inherit the parent session's selected model via
`.pi/settings.json`. Runtime state under `.pi/` is ignored, not material to
commit or publish.
Keep code comments concise; long-form reasoning belongs in ENGINE_PATCHES.md
essays, not in source files. See CLAUDE.md for the comment-style rules.
Beta phase, not release: building, deploying and restarting the Pi lobbies are
routine — do not hesitate when a change needs it.

## Patch 672 — native pre-input seam, not command prediction (12 Oct 2026)

- Optional `CSQC_PredictPlayerPreMove` is before carrier cash-out and movement;
  existing `CSQC_PredictPlayerMove` remains the post-trigger hook. Staged
  `predinput_apply` defaults to zero every replay invocation. BODY/MODE/DUCK/
  HOLD/CLEARCARRIER validate selected fields atomically. Normal QC exports no
  callback yet. Contract/reproduction: `tools/p672predinput.md`.
- **usercmd.msec is float.** 51 ms splits into 25.5 ms pieces, not 25+26.
  Native offsets must be float throughout recursion and the QC bridge. The
  first candidate's integer offset failed an acting budget control; fixed.
  A zero-offset transition is once per logical REPLAY, never once per render
  lifetime. Existing >500 ms clamp is unchanged.
- **Skipping held touches must not skip carrier state commit.** The first
  candidate saved the ring only through the post-hook, allowing stale armed/Z
  state or no state at the next command. `CSQC_PredictSaveBaseVel` is now shared
  by post-hook and held pieces; held-only and mixed-split controls act.
- HOLD is zero native command duration, NOT universally frozen physics,
  zero velocity, PM_NONE, carrier clearing, full Source restore, server timer
  freeze or save-style MOVETYPE_NONE. The helper preserves unselected fields;
  later real mover housekeeping is still allowed. Runtime reads entry values
  BEFORE fixture writes to prove next-piece origin/mode, not requested output.
- The host test compiles extracted production functions with real headers and
  explicit VM/linear-mover doubles. It is not collision or network acceptance.
  Direct invalid arms compare entire mover/carrier bytes; replay comparison
  covers the fields actually written by CL prediction, not uninitialized or
  unrelated members of `player_state_t`. Restricted discovery is source-reviewed.
- Dedicated runtime BODY/HOLD/no-op controls act; disabled silence is paired
  with a native prediction-trace heartbeat and re-enabled callback. The fixture
  on an older engine is ignored while legacy triggers act. Test-only CSQC must
  never be appended to the production `.src` or deployed. Initial early
  `ui_close` failed before menu init and is retained, not accepted; this fixture
  makes no HUD/menu claim and omits that command.
- Requests/descriptors, generation scoping, SSQC admission/application and
  operation-bearing body-baseline coverage remain NEXT. `STAT_FS_SLACK` is
  still only processed-command count. Do not claim instant hold release or
  retire an operation from that ACK. No evidence, ranked or Build change.

## Native SSQC command context (P675, 2026-10-12)

- `SV_SetSSQCInputs` ALREADY populated float `input_sequence` before native
  PreThink; absence of a safe exact operation interface was not absence of any
  bridge. P675 exposes exact low/high 16-bit words on server and P672 client.
  Do not recombine into float32, treat sequence 0 as an unavailable sentinel,
  or equate identity with admission, an epoch, an ACK or body-baseline coverage.
- The six optional typed `input_cmd_*` globals are scoped ONLY to native SSQC
  PreThink and cleared afterward. Kind 1 decoded QW/redundancy is distinct from
  kind 2 FTE timestamp-derived duration; repeats/legacy paths and budget-mutated
  commands are unavailable. Incomplete/wrong-type exports never partly opt in.
- P672 fractional-half splitting is CLIENT behavior. SERVER retains integer
  truncation/half/remainder splitting (51 -> 25+26; 50.5 -> 25+25). Native
  server offsets describe actual execution, not universal client/server piece
  equivalence. This prerequisite does not change movement/evidence semantics.
- An SSQC wrapper fixture must rename hooks AFTER fixed system defs: insert
  `cmdcontext_begin.qc` before `sv_player.qc`, append `cmdcontext.qc`. Global
  `-DPlayerPreThink`/`-DStartFrame` renaming failed compiler system-def check
  Q208, zero warnings notwithstanding. Separate output, never a product include.
- `runlines_smoke.py --server/--ssqc/--csqc` selects exact engines and COPIES
  fixture progs into an owned overlay; no install or staging swap required.
  Follow the reread acting P672 config and use `--mount`; initial candidate
  setups exited before completion (including retained P672 client control).
  No causal renderer/network repair or silent/failed pass is claimed.
- Actual-source units plus dedicated QW, FTE and old-server controls ACT; missing
  callback/frame-clear and injected stale metadata fail the grader. High words/
  wrap and recovery routing are unit/source coverage, not a forced loss/order
  runtime matrix. Complete descriptors, admission and baseline reconciliation
  remain next; normal CSQC still exports no P672 consumer. `p675cmdcontext.md`.

## Inert movement preparation (P678, 2026-10-12)

- `server/sv_moveprep.qc` is a server-only policy builder with NO normal caller
  or client export. READY is an immediate preparation result, not permission,
  native snapshot, connection/content epoch, cached freshness or baseline ACK.
  Caller owns Alloc/Free output and zoned identity strings; tokenize scratch is
  shared, so a future command caller must retokenize before resuming argv use.
- Save load requires id+seq in a fresh scoped block AND reread origin, velocity,
  pitch, yaw, duck, ticks and sequence matching the row. A matching sequence
  alone is not content identity. Strict numeric/required/duplicate-key checks
  and bounded input abstain conservatively. Rewound rows resolve rwvel;
  demoted rows remain movement-only, not recorder permission.
- Release resolves current holdrow (both block bounds), not selected cursor or
  disk. It preserves current aim and all native Source fields. Load's completed
  duck clears ducking/ducktime, replaces ducked, preserves remaining history;
  ground/carrier clear but gravity/jump history do not reset. The contract test
  enumerates all 12 pmsourcestate_t fields from the actual header.
- `cl_sendguid 1` is required for this fixture's attributed-player controls.
  `forceinfokey(..., "guid", ...)` does NOT alter engine infokey("guid"); an
  initial owner/block fixture failed 3/52 before reaching the intended guards.
  Final subject: 66/0; weak READY override: 23/66 fail as expected. Ordinary
  Load/Hold/Release parity acts; no native collision/baseline/network claim.
- FTEQCC pointer locals: separate `local T *a; local T *b;` declarations.
  `local T *a, *b;` made b a double pointer in this measured fixture. Windows
  absolute include filenames in .src stopped at drive colon; use relative
  includes (absolute output filename is supported). Retain failed logs.
- Normal VMs/fixtures compile at zero warnings. Reader 306/0; inspected reader
  unchanged, corpus 270 recs/91 views/170 existing faults. No engine source,
  pin/tag, save/evidence format, Build, owner/peer install or fleet swap. Next:
  generation lifecycle + reset/rewind builders, exact P675 bounded admission,
  PEXT2_REPLACEMENTDELTAS operation-bearing body-baseline reconciliation.
  Do not activate instant movement beforehand. Contract: p678moveprep.md.

## pi.dev startup contract

Start pi.dev from `C:\FTESurf` (or `pwsh -NoProfile -File
C:\FTESurf\tools\pi-start.ps1`) so this brief and `.pi/settings.json` load.
pi.dev has NO built-in `/add-dir`: its tools can use absolute paths outside cwd;
that access does NOT auto-load sibling instructions and is NOT a sandbox.

This work spans three directories:

- `C:\msys64\home\Lex\fteqw` — engine C/C++, ENGINE_PATCHES.md.
- `C:\FTESurf-private` — private anti-cheat plan, samples and reports.
- `C:\FTESurf` — QC, tools, deployment and the prebuilt engine.

The engine is required for anti-cheat, movement or renderer work. Before edits,
inspect Git status in every affected checkout and read any sibling instructions
that exist. For anti-cheat also read the private plan named below, on demand;
never copy it, exploit recipes, credentials or raw private tool output into a
public commit, agent artifact or shared/exported session. `C:\FTEQuake` is the
second install for client-vs-server tests; use its absolute path when needed.

Use LSP for engine symbol navigation and post-edit diagnostics; see `.pi/README.md`
for clangd's compilation database and smoke checks. clangd does NOT understand
QuakeC: QC must be checked with fteqcc and the project's runtime falsifiers.
A clean LSP report is not a build or physics/security verification.

Native roles inherit the selected model. Never silently fall back to external
CLIs or another provider after a child failure.

Context-fold defaults are intentional. A folded/compacted claim is not source
truth: reread the cited code or private document before acting on it. At a long
workstream boundary keep an explicit checkpoint (commit/ref, owned paths,
commands/results, control vs subject, unresolved questions and next step);
private anti-cheat checkpoints stay in the private tree. Do not turn unknowns
into findings or completed tests into claims about an unverified deployed build.

## Agent workspace lifecycle

Mandatory for NEW agent-created scratch copies on Windows and the NanoPi.
Before creating one, reread `C:\FTESurf\AGENTS.md`: a detached worktree can
carry an older instruction snapshot. Read any sibling instructions as usual.
Do not move existing installs, peer work or retained archives to enforce this
layout retroactively.

| Scratch work | One task root |
|---|---|
| Non-private Windows | `C:\FTESurf-worktrees\<task>-<unique>\` |
| Private/security Windows | `C:\FTESurf-private\worktrees\<task>-<unique>\` |
| NanoPi | `/srv/nvme/agent-work/<task>-<unique>/` |

Keep the task name short and the suffix unique. Verify ancestors are ordinary
owned directories, not links/mount redirections into protected paths. On the
NanoPi verify this root is OUTSIDE service/static-file/map/data/database paths;
restrict private task directories to the owner (`0700`). If the approved root
cannot be used, ask; do not silently scatter copies elsewhere.

- **One root per task/session, not one top-level folder per attempt.** Keep
  `qc/`, `engine/`, `control/`, `subject/`, `artifacts/` and `tmp/` below it as
  needed. Use inspected Git SHAs and `git worktree add` for source isolation.
  A clone is an exception with a recorded reason, not the default. Reuse only
  YOUR compatible scratch trees; never reuse a peer's root. Do not duplicate
  full installs, map/Steam libraries or package caches for every arm. Use
  verified read-only inputs where supported, not hardlinks to writable player
  data or unrecorded junctions into a live install.
- **Ownership first.** Before populating the root, write untracked `OWNER.md`
  there with task/session owner, UTC creation/update, repository/base SHAs,
  exact owned paths and process handles, arm purposes, status (`active`,
  `retained`, `blocked` or `done`) and retention/cleanup plan. Keep private
  details private; no secrets, credentials, player GUIDs or raw process args in
  public notes. Checkpoint the root in the session handoff. A filename, old
  timestamp, clean Git status or missing owner note is NOT abandonment proof.
- **Contain copies, not the product.** Canonical in-place engine/QC builds,
  documented `dist/`/release stages, compiler-internal temp files and required
  runtime gamedir fixtures keep their existing contracts. Do not change CWD
  or relocate QC `fopen` fixtures blindly: those readers require the gamedir.
  Give any necessary shared fixture exact ownership, bounded paths and verified
  park/restore steps. Tool-managed temporary directories are acceptable only
  with bounded lifetime/cleanup; retained project copies belong in the task
  root, not `%TEMP%` or a loose `/tmp`/NVMe folder.
- **Isolation must be checked, not inferred.** Inspect the build script from
  the exact commit for supported flags and all write/deploy targets. In
  `src/build.ps1`, `-FteRoot` selects the ENGINE checkout; the QC/product root
  comes from the script location, and `-QuakeDir` selects the second native
  destination.
  Do not assume `-NoDeploy` suppresses every native copy, or that an unsupported
  flag protects anything. Keep control builds away from live destinations;
  intentional deployment still follows the dual-install/Pi operations rules.
- **Retire what you own before ending the task.** Stop only your processes;
  verify no peer, lock or registered descendant still needs the tree. Inspect
  staged, unstaged, untracked AND ignored content. Preserve unique source,
  exact staging, detached/unpushed history and needed evidence in a verified
  recovery archive/checkpoint BEFORE deletion. A patch alone can omit staged
  blobs, untracked files or history; a commit alone omits ignored artifacts.
  Do not force-remove, blanket-clean, follow links or discard player data;
  ask before any data destruction or uncertain ownership/retention decision.
  Use ordinary `git worktree remove` only when safe; remove plain disposable
  copies only from an explicit owned manifest. Keep useful logs/receipts without
  retaining another whole build by default. If blocked, retain the root, update
  `OWNER.md`, and report its exact path, reason and next cleanup step. Mark
  completion only after checking path absence and worktree registrations.

## Repository layout

- `ftesurf64.exe` — prebuilt FTE engine binary (Windows x64). Engine C code is
  NOT here: separate checkout at `C:/msys64/home/Lex/fteqw` (`engine/…`), which
  also holds `ENGINE_PATCHES.md`.
- `ftesurf/` — the gamedir: `cfg/` (incl. `cfg/test/`, `cfg/lobby/`,
  `cfg/maps/`), `data/` (saves, runs), `logs/`, `screenshots/`, `glsl/`,
  compiled progs (`csprogs.dat`, `qwprogs.dat`, `menu.dat`).
- `src/` — all QuakeC and the build script (`build.ps1`, `fteqcc64.exe`).
- `surfd/` — Python (Flask/gunicorn) directory + join broker; runs on the Pi.
- `src/release/` — packaging (`release.ps1`, `publish.sh`, `install.sh`, nginx +
  page template); the ROOT `release/` is only its untracked staging output
  (`stage-0.1.N/`). `ENGINE.txt` — pin of the engine commit/patch this tree
  expects.
- `.gitignore` IS AN ALLOWLIST: `/*` ignores everything at the root, then
  `!/name` un-ignores. A new ROOT file is invisible to git until you add it
  there — that is how AGENTS.md and CLAUDE.md first went untracked (both are
  allowlisted now, `.gitignore:125-126`). Check a surprise with
  `git check-ignore -v <path>`. `dist/` and the root `release/` must stay
  ignored.

## QuakeC sources → artifacts

- `src/server/*.qc` + `sv_progs.src` → `qwprogs.dat` (server progs).
- `src/client/*.qc` + `cl_progs.src` → `csprogs.dat` (CSQC: HUD, boards,
  replays, saveloc client half).
- `src/menu/*.qc` + `m_progs.src` → `menu.dat` (menu VM: picker, join flow).
  Menu is client-local: never deployed to servers.
- `src/shared/`, `src/defs/` — defs is GENERATED, do not hand-edit.
- `.src` file order is load-bearing (compile order = declaration order; QC has
  no forward references — add a prototype `void() Foo;` or reorder).

## Build

**Native isolation pitfall (measured P541).** `build.ps1 -Engine -NoDeploy`
only suppresses QC deployment: the BuildEngine branch still copies native
outputs to its product root AND QuakeDir. For an isolated engine build, the
product root must be an isolated worktree and pass `-QuakeDir <private path>`
explicitly (a nonexistent path skips the second native deployment). Do not
assume NoDeploy protects C:\FTEQuake. A guarded `.prev` restoration is required
if those files were accidentally copied; preserve any peer replacement. The
script itself remains a follow-up in BACKLOG.


**A fresh engine worktree is not a build tree (measured P609).** It has no
`engine/libs-x86_64-w64-mingw32` (an ignored `makelibs` product), so `make sv-rel`
there links `zlib1.dll` and the exe ends in 0.1 s with 0xC0000135 when started
from anything but an msys shell: five arms "ran" that way and measured nothing.
Pass `ARCHLIBS=C:/msys64/home/Lex/fteqw/engine/libs-x86_64-w64-mingw32` and
compare `objdump -p <exe>`'s DLL names with the installed binary's. It also
stamps nothing (`.git` is a file there): supply `SVN_VERSION` and `SVNREVISION`,
and make the patch tag ANNOTATED or `git describe --long` skips it.

From `src/`, with pwsh 7 (NOT `powershell`):

    pwsh -NoProfile -Command "./build.ps1 -Jobs 8"

- Default: compiles all three progs + plugin, deploys to `C:\FTESurf` AND
  `C:\FTEQuake` (dual deploy is mandatory).
- `-Engine`: also rebuilds the engine from the fteqw checkout; add `-Full`
  after any engine header change. Plugin rebuild is automatic. It builds the
  engine WORKING TREE, and `release.ps1` ships whatever it built. 0.1.8 went out
  with another session's uncommitted Patch 362, so commit engine edits before
  anyone cuts a release. The same holds for the progs: `release.ps1` packs the
  install's .dat, and its dirty gate cannot see uncommitted QC source -- build
  HEAD's progs in a clean worktree and copy them in. fteqcc output varies with
  the checkout path, so compare .dat hashes only between builds from one path.
- `-Pi`: ships qwprogs+csprogs to the Pi lobbies and restarts them.
- `src/release/release.ps1`: ALWAYS `-Bump patch -DryRun`. A bare `-DryRun`
  targets the PUBLISHED version and rewrites its stage, archive, receipt and
  page. A run that fails after its upload cannot be re-run (each pack stamps a
  new `built` time, so the md5 no longer matches R2): scp `dist\site-<v>\*` to
  the Pi's `ftesurf-site/.incoming/<v>/` and run `publish.sh <v>`, or bump.
  - A RELEASE THAT KEEPS THE LAST ENGINE (0.1.21): `git worktree add --detach`
    the engine at ENGINE.txt's `tag` (the engine that shipped), copy
    `release\stage-<prev>\ftesurf64.exe` and the plugin into its
    `engine\release\` (as `fteqw64.exe`), copy the same pair into the install
    after backing up the dev pair, run with `-FteRoot` = the worktree, then put
    the dev pair back. Byte-identical binaries, no rebuild. The receipt's patch is
    the worktree's highest ENGINE_PATCHES.md heading, and gate 3 only compares the
    two copies of the same exe -- so a worktree at the PIN (481 since 4 Oct) would
    stamp 481 on the 467 binary and pass. The tag is what makes it true.
    SINCE PATCH 623 GATE 3 WANTS THE ui_imgui PLUGIN'S BUILT COPY THERE TOO and
    stops, naming it, when the exe and hl2 plugin are there without it. A stage
    older than 0.1.24 has none to copy, and an exe that old refuses the plugin
    anyway: such a release takes it out of `$ShipRootFiles`, it does not pass
    `-AllowEngineSkew`.
  - THE QC BUILD NUMBER: `-BuildNumber <n>`. The script derives it from a
    `Build NN:` commit subject and HARD-FAILS when the last one is more than 200
    commits back (Build 89 was 228). It now takes the number explicitly, because
    the authority is the operator, not the log -- AGENTS.md's "only on the user's
    Build NN commit" is about WHO decides, and `-BuildNumber` is that person
    typing it. It still has to agree with ENGINE.txt's `qcbuild` (a Warn, not a
    Fail, as before). Build 89 = Patches 434-438.
    THE SWITCH IS NOT NAMED `-QcBuild`, and that cost an hour: PowerShell variable
    names are case-insensitive, so `$qcBuild = $null` and a `$QcBuild` parameter
    are ONE variable -- the switch bound 89, that line reset it to 0, and the run
    died 45 lines later on "You cannot call a method on a null-valued expression"
    with no mention of the switch. `grep -in` both spellings before adding a
    parameter.
  - **GATE L2 IS A `-Linux` GATE, NOT A GENERAL ONE** (`if ($Linux) { … }`, and
    its hard failures are BUILDINFO/soname checks). So a QC-only batch needs no
    engine work at all: omit `-Linux` and the receipt carries `linux: null`.
    Earlier note here claimed L2 blocked a QC-only release; that was reading the
    gate's comment rather than its scope.
  - WHAT REMAINS TRUE about the engine identity, and it is a receipt question not
    a gate: without `-Linux` nothing records which engine commit the shipped exe
    came from. ENGINE.txt's `commit` line is NOT that (it pins `45174b9d4` =
    Patch 427 while the 0.1.12 exe carries stamp
    `git-6891-patch-266-102-ga72183e6b` = Patch 419), so do not "reconcile" a
    release by rebuilding `-Engine` from the pin: it yields a DIFFERENT exe
    (measured `279841f7…` against 0.1.12's `1950288f…`) and nothing would record
    the swap. Read the stamp out of the binary if you need the commit.
  - `menu.dat`'s hash is path-dependent (fteqcc), so it will differ from an older
    receipt with `src/menu/` untouched -- measured `46ab6af4` against 0.1.12's
    `d8fe56aa`. That is not dirt: gate 1 compares the ship set against GIT, and
    it passes clean. Reproduce it from a clean `git worktree` anyway if you want
    the archive to match a from-scratch clone.
  - `-NoDeploy` on a worktree build leaves the .dat in the WORKTREE's `ftesurf/`,
    never in `C:\FTESurf` -- copy them in, and copy the shipped pair back after.
    That is also how a control build is made when this tree's source already holds
    the patch (`cfg/test/p439smoke.cfg`'s RESULT block records the recipe and the
    hash that proved which build ran).
- CSPROGS SITS AT FTEQCC'S GLOBAL LIMIT (131,072). Patch 474's ten 1,000-float
  arrays took it to 131,418 and the build died with `Too many globals`, reported
  as `Error in client/cl_main.qc on line 0`. Big tables go in `memalloc`'d memory
  (`cl_lines.qc`, `cl_online.qc` `Online_Alloc`), not in global arrays.
  WHAT IS COUNTED IS DEFINITIONS (`numglobaldefs`, the 6th int of the .dat's
  header; `qccmain.c:2425` against `MAX_GLOBALS = 1<<17`), one per array
  element and one per LOCAL, not globals memory (184,579 words, no limit near).
  Patch 637's csprogs held 131,039: 33 to spare, and a 61-definition patch
  died. Patches 640 and 641 moved six float tables out (1,024 and 510); it
  is 129,663 after both and 642. `-max_globals` on the command line would lift it and
  the engine has no such table, but about nineteen `tools/*.py` compile
  `cl_progs.src` themselves and would not have the flag: keep moving tables.
  `float *a, *b;` declares b a `float**`: one declarator a line.
- QC-only change → default build is enough. Treat "0 warnings" as the bar, but
  check whether a warning is yours: this tree usually carries other people's
  uncommitted work (`cl_hud.qc:2007`, a 9-arg sprintf, is a standing example).

- ON A MACHINE WITH ONLY MSYS2 MINGW64 (the holiday laptop, 2026-09-29):
  `C:\msys64\ucrt64\bin` can exist and be EMPTY, and then every `make` step
  dies on "command not found". Put `C:\msys64\mingw64\bin;C:\msys64\usr\bin` on
  PATH and set `C_INCLUDE_PATH=C:\msys64\mingw64\include\opus` (the Makefile's
  `-I/usr/include/opus` misses the mingw64 package). The plugin link needs
  `pacman -S zip`; TTF fonts need `mingw-w64-x86_64-freetype` BEFORE the build
  (without it the Makefile silently adds `-DNO_FREETYPE`, and a later install
  needs a clean rebuild). `build.ps1 -Engine` then dies at plugins-rel on box3d's
  missing library -- build `NATIVE_PLUGINS="hl2 cod"` by hand and copy the exe and
  the hl2 DLL. That build links its libraries dynamically: copy libjpeg, libpng,
  libopus, libspeex(dsp), libvorbis(file), libogg, zlib1 and the freetype chain
  beside `ftesurf64.exe` (all git-ignored), and put mingw64\bin on PATH for
  `fteqcc64.exe` as well.

### World of Surf art/web candidate (P705)

Brand sources/gallery: `src/brand/`; exporter: `tools/brand_assets.py`.
Use the pinned development-only fontTools/Pillow/Playwright recipe in its README,
with an installed Chromium path. No runtime font/network dependency in the
outlined SVGs. Edge can hang capturing a 16px viewport: render at >=256px then
clip the native-size icon. A no-browser check covers SVG only, not PNG/ICO.
The browser falsifier checks document AND nav scroll widths; the former alone
missed cropped header text at 320px. Its board data/images are labelled samples.
Do not import `surfd/test_accounts.py` as a fixture: it executes its suite on
import, and a caller already exposing `tools/` in sys.path can confound its
missing-verifier control. Run it standalone; the web preview uses `test_web`.
For hash-route browser checks, `networkidle` is not a render-completion signal;
await exact titles and the acting HTTP response/pressed control, not a stale DOM.
P705 changes web presentation only: old OG/service paths, launch filenames,
signed formats, player data and native/QC binaries remain intentional. Do not
mistake local dual-prefix fixtures for live nginx/Steam transition proof.
Source controls and failures: `tools/p705rebrand.md`.

### World of Surf parallel website paths (P707)

`tools/test_site_routes.py` runs the authored nginx snippet against isolated real
surfd, with scoped addresses/temp paths and a distinct filebrowser fallback.
Use a real nginx distribution plus Flask; --mime-types overrides its type table.
Default POSIX daemonization detaches the serving master from Popen: retain it
with `daemon off`, check pidfile == retained PID, reap it and check closed socket
before removing the fixture. --lifecycle-control setup/shutdown are intentionally
failing cleanup controls. No unproved/global cleanup; preserve blocked fixtures.
Run test_accounts standalone with ACCOUNTS_TEST_BOARD_URL to exercise either
configured public base. Dual HTTP routes do not mean dual signed callback bases:
SURFD_BOARD_URL stays legacy in this prep, and Steam realm is origin-only while
return_to is path-sensitive. No public/canonical switch follows from local mocks.
Commands, both-platform controls, findings and remaining gates: tools/p707sitepaths.md.

## Run and test

- Normal launch: `./ftesurf64.exe` (or `ftesurf.bat`).
- Headless: `./ftesurf64.exe -WindowStyle Minimized +exec <name>` with cfgs in
  `ftesurf/cfg/test/`; output in `ftesurf/logs/<log_name>.log` and
  `ftesurf/screenshots/`. Verify by reading logs and screenshots.
  CWD MUST BE `C:\FTESurf` — the basedir is the cwd and Start-Process inherits the
  caller's, so a shell left in `ftesurf/` produces NO log at all and the run just
  sits there: two 200 s timeouts read as a hang before the cwd was the answer.
  Pass `-WorkingDirectory "C:\FTESurf"` rather than trusting the shell's.
- EXPLORING WITHOUT A CFG PER QUESTION: `python tools/conbridge.py start --map <m>`
  keeps one client and one dedicated server up and takes a console line at a
  time: `send`, `wait <regex>`, `log`, `info` (cmd viewpos + cmd timer), `shot`,
  `stop`; `--help` has the rest. It feeds stdin under `-plugin` and tails the two
  logs. NOT AN ARM -- nothing in it repeats, so freeze what it finds into a cfg
  with a control. It runs in the real install as the owner's profile, on a
  manifest of its own so every cfg_save lands in a private copy of ftesurf.cfg;
  `stop` lists what changed under `data/` and at the top level
  (`tools/test_conbridge.py` checks the guards with no engine).
  Measured building it (2026-10-10), and any
  hand-rolled driver meets the same: a line the CLIENT reads while still starting
  is dropped silently; the SERVER logs a typed line with no newline
  (sv_main.c:5369), gluing the reply's first line to it; between `client X
  connected` and the spawn `cmd viewpos` IS answered, with `setpos` all zeros, so
  an answer is not a spawn; a minimized client wrote 1280x720 of black and still
  logged `Wrote` (one shot); and the client takes the foreground on every mode
  set (gl_vidnt.c:1727) whatever STARTUPINFO asked for.
  THREE MORE, each usable by an arm: the engine reads `<basedir>/<argv0>.fmf`
  before default.fmf (fs.c:7495) and argv[0] is whatever the command line says,
  so `Popen([name, ...], executable=exe)` gives one run its own MAINCONFIG with
  no rig -- `fs_showmanifest` reads it back. A `+set run_resume 0` given BEFORE
  the map survived the server QC's registercvar, on a dedicated server (across a
  second map load) and on a listen server; it reads back `"0" (default)`, and
  PF_registercvar returns early on a cvar that exists (pr_bgcmd.c:2036). The
  reset the `cl_trigdebug` bullet records is CSQC's and was not re-measured. And
  a client's quit rewrites `<gamedir>/conhistory.txt` from the copy it read at
  start (same bytes, new mtime) unless `con_savehistory 0`.
- WHERE A DEDICATED SERVER'S CRASH RECORD IS DEPENDS ON ITS BUILD. From Patch 609
  it appends module+offset frames to `crashaddr.txt` in the basedir it is running
  (here, beside the client's records; each record names its exe). EVERY SERVER
  BUILT BEFORE THAT wrote to the hard-coded `C:\FTEQuake\quakers\crashaddr.txt`,
  so this tree's file staying old did not mean nothing faulted: 609's own fault
  sat there through four runs written up as "not written". Whoever built an exe
  has its unstripped twin beside it as `fteqwsv64.exe.db`; `nm -n` on that names
  every frame. Same patch: a server that reaches Sys_Error no longer restarts
  itself unless started with `-autoreset` (before, unless `-noreset`: on a
  mistyped `+map`, an orphan copy every 13 s), and a release server cannot be
  made to fault on request -- `crashme` is `_DEBUG` only and `sv-dbg` does not
  link (BACKLOG) -- so `tools/p609sverr.py` starts a thread at address 5 in it.
- AN ARM NEEDS A CONTROL BUILD AND A DETECTOR PROVEN TO HAVE FIRED. "Not flagged"
  is also what a subject that never fired prints, so an arm with no pre-change
  build beside it measures nothing — p411push printed a textbook flip on a pad
  that never armed. AND THE CONTROL IS NOT `git checkout -- <file>` ONCE THE TREE
  HOLDS A BATCH: that reverts one patch and leaves the others in, so the
  "control" still contains the fix. Build it from a `git worktree` at the
  pre-batch commit with `-NoDeploy`, copy its .dat in, and prove which build ran
  by hash (recipe and the hash that proved it: `cfg/test/p439smoke.cfg`'s RESULT
  block). Prove the subject ACTED before believing any verdict: its own
  dprint, or a latch carrying its authored number (p412speed used `tkspd 2060`,
  the pad's own horizontalspeed). Expect the pre-registered detector to be the
  wrong one and say so when it is. Control recipe — NOT `git stash`, which would
  take the other session's files: copy the file aside, `git checkout -- <file>`,
  build, run, copy back, rebuild, and diff the diffstat against the saved one.
  WHEN A CONCURRENT SESSION'S UNCOMMITTED FILE DOES NOT COMPILE, do not touch it and
  do not stash it: build the control anyway by `touch`ing that file's already-valid
  `.o` in `engine/release/<target>/` forward, so make skips it. The two binaries then
  differ ONLY in the files under test, which is a *better* control than a full
  rebuild, and the peer's work is never at risk. Verify the `.o` you are advancing is
  from a build that succeeded, and say in the entry which file was skipped and why.
- AN ARM WHOSE PREMISE IS AN ABSOLUTE ROW INDEX BREAKS ON AN UNRELATED FIX, and it
  reads as a failure of the thing you changed. `p477rewind` R5C loaded its at-rest
  save as `sl_goto 4` and R8 asserted `saves: 5/5`; Patch 499 stopped a resume row
  being dropped across a run boundary, one row earlier in the list then survived,
  and both arms failed on a build that was correct -- R5C loaded somebody else's
  row and R7/R8 failed behind it. Address a row by a PROPERTY (`sl_goto 9999`
  clamps to the count, i.e. the newest row) with the property CHECKED (the save's
  own row number beside the count), and keep an absolute count out of an arm whose
  subject is not the count.
- Test-cfg recipe: `cfg_save_auto 0` FIRST -- the engine writes ftesurf.cfg on
  every disconnect and map change (`CL_ClearState`), not only at quit, and a
  harness's `cl_maxfps 100` then lands in the owner's config (measured: an
  unguarded jit01 wrote `cl_maxfps "0"` over `"1000"`). `python tools/cfgguard.py`
  lists any test cfg without it, and exits 1. Then `cl_idlefps 0` AND
  `cl_maxfps 100` (uncapped fps starves async loads); `menu_restart` before any menu-VM command in a `+exec` run
  (menu.dat loads lazily); `set <cvar> <v>` for cvars not registered yet.
- The engine's BUILTIN menu is open from boot and `togglemenu` only OPENS;
  `ui_close` is the way back. Until it closes `notmenu=0` skips the whole HUD
  stack, so every screenshot harness needs `menu_restart` + `ui_close`.
- This machine's archived `ftesurf/ftesurf.cfg` overrides `default.cfg` (it
  archives `hud_energy_ref` and `hud_timer_size` among others, and the values
  drift — read the file rather than trusting a number quoted here). A headless
  test must `set` every cvar its measurement depends on, not assume a default.
  An install that ran 0.1.9 or earlier saved Momentum Mod's binds and some
  settings into its ftesurf.cfg (fixed by Patch 377, not undone): a player with
  odd binds, no chat on ENTER or a dead restart key should delete that file.
- DRIVING A RUN: the clock starts when you LEAVE THE START BOX. `+jump` hops in
  place (~80 u in 4 s on a bhop map) and never starts it; `+forward` walks at
  `sv_maxspeed` (260 in `default.cfg` — the move values are 450 precisely so
  they cap nothing) and clears the box in about a second — BUT NOT ALWAYS, AND A
  JUMP IS THE WRONG GESTURE: on surf_4am a straight `+forward` from `zone_goto`
  STOPS 32 u inside the region (y 96 against a boundary at 64) so no run ever
  starts and there is no sidecar; the start rule refuses a chain ("hopped start --
  one jump out of the start, or walk out"); and `+right` alone only TURNS.
  SINCE PATCH 445 THAT TAG IS STICKY AND ONLY `!r` TAKES IT BACK — which is the
  thing to know when an arm reads `hopped 1` three sections after the jump that
  earned it. `run_rearmhop` (build 21's extra forgiveness: stand
  `run_prestrafe_time` grounded and the tag lifts) **now defaults to 0**, and an
  ARM no longer forgives either, so nothing a harness does incidentally will clear
  it. The clears are the `!r`/`!m`/`!s`/`!b`/**`zone_goto`** gesture (all reach
  `SV_ZoneMoveAt`, and `zone_goto` is the warp this file tells harnesses to use, so
  a harness DOES clear it incidentally — round 6's correction), the ground dwell at
  `run_rearmhop 1`, and a respawn. All three zero the velocity, which is why they are
  safe. A `retry` does NOT clear it: `hopped` is in the save format, restored
  raise-only. **Patch 448 added a fourth: crossing a ZONE_END** — the tag dies with
  the run it described, so the next attempt starts clean. That one does NOT zero the
  velocity (players coast past the line) and carries its own argument at the call
  site; round 8 found it had to live at the ZONE_END site rather than inside
  `SV_TimerFinish`, because that function's other caller is a stage boundary that
  hands the next stage over at speed. **Patch 477 added a fifth and a raise**
  (`SV_SaveLoadTag`): a load that leaves the body at rest outside a run, with no
  trigger or delayed output still owed to it, forgives; an IDLE load faster than
  a walk or a jump (horizontal over sv_maxspeed, vertical over pm_jumpvelocity)
  raises it, and an armed, finished or running one only when it is that fast
  AND its file says hopped -- on bhop-mode maps a box entered from anything but
  IDLE never runs the rest test that forgives a load's tag after the arm. That
  rest-test forgiveness (`run_t_finfgv`) belongs only to a tag the load itself
  raised: a hop chain's stays `!r`'s, and `!r` or a raise-only restore drops a
  pending one. **The tag still survives a cancel zone, a map
  teleport and a stage-boundary finish**, so an arm can read `hopped 1` many sections
  after the jump that earned it; there is a chat reminder on each later fluffed start
  but nothing on the HUD. Walk out, then
  prove the run with `cmd timer` reading
  `running / recording 1` before anything depends on it, and read the body with
  `cmd viewpos` — since Patch 435 it also prints `velocity … horizontal N`, the
  ONLY server-side speed read there is (the hold publishes the SAVE's, the
  recorder's samples exist only after a close, the client's is a prediction).
  `timer` prints the client latches, `cmd timer` the server's.
- MEASURING A DRAW: with no console dump, take two screenshots with exactly one
  variable changed between them and diff the numbers — a frozen column beside a
  live readout that moved is a measurement, one picture is not.
  A minimized harness draws slowly: wait ~500 ms after a change before
  `screenshot` (100 ms captured the previous state in p390mouse).
- WORLD CATCH-UP (P681): `sv_perfdump` counts world ticks, NOT player-mover
  substeps. On a spawned local bhop player at 20 FPS, native default limit 3
  measured 603/202 ticks/frames, ruleset default 8 measured 1012/203; the 100 FPS
  old-default control was 1009/1008. Surf's unchanged local world defaults are
  `sv_mintic 0`, `sv_maxtic 0.1` (one world tick/frame at 20 FPS), while its
  player mover still has `pm_ticrate 0.015`. Do not infer a 66.667 Hz world loop
  from that player cvar. Keep a real spawned local player: SV_Physics forces
  0.1-second idle steps when nobody plays. `tools/p681ticks.py` uses isolated
  configs/data and the actual default assignment; it is not an input or ranked
  movement accuracy test.
- MOUSE: `spectate look <dx> <dy>` pushes one IE_MOUSEDELTA through the input
  chain; `mousepad` counts the deltas it saw. Real ones can reach a starting
  harness window, so a mouse arm checks that count before it counts.
  **IT DOES NOT AIM, and this line used to read as though it did.** Measured
  2026-09-27: `spectate look 800 0` twice, 500 ms apart, gave `took 0` and
  `aim 0 0 0` both times — CSQC declines the event and the engine applies no
  synthetic delta to the view. It delivers an EVENT, which is all a mouse arm
  needs; it does not turn the player. **To turn a headless player, use the
  keyboard:** `+left`/`+right` aim at exactly `cl_yawspeed` (measured:
  `+left` 700 ms at 210 gave `aim 0 148.05 0`). Someone read this bullet as
  "a mouse delta through the chain, therefore it aims" and built on it.
- Client-vs-server (prediction) tests need a REAL socket, not a listen server:
  run `C:\FTEQuake\fteqwsv64.exe +set sv_port <p> +exec cfg/test/<sv>` from
  `C:\FTESurf` (`ftesurf64.exe -dedicated` crashes after prop lighting), with
  `sv_public 0` or it heartbeats to public masters.
  It writes nothing to stdout: pass `+set log_enable 1 +set log_dir logs +set
  log_name <n>`, run it via `Start-Process -WindowStyle Minimized -PassThru` +
  `WaitForExit`, then read `ftesurf/logs/<n>.log`. A cfg's own `log_name`
  line overrides the `+set`.
  - After EVERY csprogs rebuild run `python tools/seed_csprogs.py`, then RESTART
    the dedicated server. A stale `downloads/csprogsvers/<hash>.dat` silently
    runs the OLD code (no download line, no error); a server left running holds
    the old progs in memory and the client then logs "no client game" with every
    QC command reading "Unknown command" (panels absent, screenshots empty).
    The advertised hash is the folded MD4 of csprogs.dat (`CalcHashInt(hash_md4)`,
    digest bytes XORed by `i%4`); seeding by hand, STRIP LEADING ZEROS — the
    engine spells the filename `%x`.
  - A client whose csprogs.dat differs from the server's downloads the server's
    copy to `downloads/csprogsvers/` (clients before 0.1.8 use
    `<gamedir>_downloads/`). That only works against an engine at Patch 362 or
    later; a rollback below it leaves every uncached client with no HUD after a
    progs deploy. To test a join with no cache, delete that file first
    (`cfg/test/p362csqc.cfg`). With no CSQC, nothing sends `rechid`/`inprof`,
    so a community run flagged 2560 (TF_NOJOURNAL|TF_NOPROFILE) means the HUD
    never loaded, not something the player did.
  - Warp with `cmd zone_goto`, NOT `setpos`: setpos forces MOVETYPE_NOCLIP
    server-side and desyncs the two simulations. It also taints the run
    (`cheated`), which is fine once no measurement depends on the clock. And it
    writes NO `warp` record — the only placement in the mod that records nothing
    (`sv_player.qc`: setorigin + SV_ClearCarrier + SV_TimerWarped) — so a replay
    cannot follow it and pm_verify HOLDs `no finish` on any run a harness drove
    with it. On maps
    with no zone data, setpos + `cmd noclip` TWICE lands in WALK — prove it with
    a viewpos z-drop; ONE toggle leaves you in NOCLIP (level flight). Each
    `noclip` is processed twice — engine `SV_Noclip_f` flips to WALK, then the
    mod's QC handler flips back and prints "noclip ON" — so the printed state
    lies; trust the z-drop, not the console.
  - CSQC-registered cvars (`cl_trigdebug`, `cl_triggers`) must be set AFTER
    `connect`: registercvar resets a pre-connect `set` to default.
- No QC unit tests. surfd's tests are plain scripts, run on the Pi (Flask is
  not on Windows): `SURFD_HOME=$(mktemp -d) python3 surfd/test_x.py`.
  `test_recplot.py` is stdlib only and runs anywhere.
- TEST AN ENGINE CHANGE WITHOUT DEPLOYING IT: with `C:\msys64\ucrt64\bin;
  C:\msys64\usr\bin` on PATH, `make -j8 -C <fteqw>/engine sv-rel m-rel
  FTE_TARGET=win64`, then run `engine\release\fteqwsv64.exe` or `fteqw64.exe`
  with cwd `C:\FTESurf` (the basedir is the cwd). The installs keep their binary
  and a control run on `C:\FTEQuake\fteqwsv64.exe` stays one command away.
- AND THE FLIP SIDE: AN ARM THAT PASSES SAYS NOTHING ABOUT WHAT THE OWNER IS
  RUNNING. The bullet above is why — every arm drives `engine\release\`, so the
  install can lag the engine tree indefinitely and every verdict stays green.
  Measured 2026-10-05: `C:\FTESurf\ftesurf64.exe` was SIX engine patches behind
  (485, 487, 488, 489, 490, 491 — four of them client-security fixes that protect
  the owner's own client) while all four of Patch 491's arms passed beside it.
  Nothing in the tree checked. `cfg/test/deploy491smoke.cfg` is that check: boot,
  load a map, ask the server QC two questions, run one local operator command,
  quit, and grade by presence/absence of strings only one cause can produce.
  PROVENANCE IS AN MD5, NOT AN ARM: compare the install against
  `engine/release/fteqw64.exe` and `C:\FTEQuake`'s copy — all three identical is
  what "deployed" means. Reading a gate's literal out of the binary
  (`grep -a -o "Blocking insecure renderer" | wc -l`) dates it when the stamp
  does not, which is how the six-patch gap was found.
- A synthetic key (`in_journal_synth`) never reaches the binds in a minimized
  headless client, so a key's effect cannot be driven. Probe the input chain's
  verdict instead: `vote key <scan> <0|1>` runs CSQC_InputEvent and prints
  `took`, which is what decides whether keys.c runs the stored `-command`.
- A cross-session heads-up can sit unapproved and expire undelivered: park and
  restore shared fixtures regardless, and never wait on a reply.
- Another session may run game copies from `%TEMP%` on its own ports. Between
  harness arms kill only processes whose ExecutablePath is under `C:\FTESurf`,
  `C:\FTEQuake` or `engine\release`. Agent PowerShell cannot `Remove-Item`
  under `C:\FTESurf`, and logs append: give each run a fresh `log_name`.
- A HARNESS HANDLE IS A REGISTERED CVAR, NOT A QC GLOBAL. `+set foo 1` creates a
  CVAR; a bare `float foo;` in QC is invisible to it, reads 0, and nothing says
  so — the arm then exercises the unhandled path and passes by never happening.
  `registercvar` it and read it with `cvar()`, and set it AFTER the map, because
  registercvar resets a value set earlier (the `cl_trigdebug` trap). Related, and
  why Patch 438 needed a new command: the server STUFFS `set cl_saveroot
  "data/saves/<map>"` on every `sl_` command, so a client-side save root cannot be
  overridden at all — `sl_replay <slot>` fires the load event with no save behind
  it (no placement, no clock, no row) for exactly that reason.
- A HARNESS SCRATCH PATH MUST BE INSIDE THE GAMEDIR. `FS_LoadFile` locates with
  `FS_GAME`, so `%TEMP%` or the install root opens nothing and `fopen(FILE_READ)`
  returns -1 with NO "Access denied" line — which reads as a reader bug and is a
  path bug. Cost a whole arm.
- **A TRIGGER ALIAS'S EXECUTION IS DEFERRED, AND THE CLIENT'S `quit` RE-FIRES IT — so
  neither a marker's POSITION nor a COUNT attributes a phase** (measured driving Patch
  487's arm). A multi-command alias body (one containing `;`) goes to
  `Cbuf_AddText`, and text queued at a changelevel drained ~94 s later, during the
  client's own quit. Separately, quiting reloads the menu and the map and those
  reloads fire `f_newmap` AGAIN — two extra payload runs after the client had printed
  its own "done" — so the control counted the planted payload 4x and the subject 3x,
  a difference that is NOT the fix. GRADE SUCH AN ARM BY THE PRESENCE/ABSENCE OF A
  STRING ONLY ONE CAUSE CAN PRODUCE: three different gated `fs_*` commands gave three
  disjoint success strings and three disjoint blocking strings, and every line in the
  log then named its own cause. Same family: `cmd viewpos`'s reply is ASYNCHRONOUS and
  a shader reload (~150 lines) landed between request and answer, so a fixed byte
  window read it as "not connected" — a false verdict on the one prediction that says
  every other verdict came from a live connection. Bound that window by the client's
  own done marker. And `stuffcmd` REFUSES A `;` ("You're not allowed to stuffcmd
  that", `sv_ccmds.c`), so a server admin cannot stuff a multi-command alias body;
  the filter is in the console command, not in the wire path.
- **A SERVER-SET CVAR'S READBACK PRINTS THREE LINES AND THE FIRST ONE LIES.**
  `stuffcmd * set foo 1` makes the client `Cvar_LockFromServer` the cvar, so a later
  readback prints `"foo" is "0"` / `Effective value is "1"` / `Default: "0"` -- the
  LATCHED pre-override string first and the value `.ival` actually holds second. This is
  the same split AGENTS.md already records for string mirrors, appearing in the ENGINE'S
  OWN cvar readback. It cost a precondition control: an arm matching the first line
  reported a precondition that HAD held as one that had not, and the leg it was
  guarding had in fact fired (`Operating in databaseless mode` was in the log). Match
  `Effective value is`, not `is`, and derive the pattern against the real bytes with
  `repr()` rather than guessing at adjacency -- every log line carries a
  `YYYY-MM-DD HH:MM:SS ` prefix, so a pattern expecting two lines to touch can never
  match. A NOT-REACHED grade is what stopped that from being read as a passing verdict.
- **AN ARM WHOSE OBSERVABLE IS PRODUCED DOWNSTREAM OF THE THING IT MEASURES CANNOT
  DISTINGUISH A FIX FROM NO FIX.** `p482c` graded `allskins` by the skin-loader line,
  and `qwskin_t::name[64]` truncates that name to 63 characters -- so a bounded copy
  and an unbounded one print the SAME line, and the arm passed both. Its own RESULT
  block said the right thing ("the overrun itself was NOT measured") but the arm still
  looked like coverage. When the only visible effect is downstream of a narrowing
  step, MEASURE AT THE WRITE: Patch 489's canary build put a known word at the buffer's
  end and printed it before and after the copy, which is what an AddressSanitizer build
  would report and what this toolchain does not have (`mingw64` absent, `ucrt64` gcc
  builds without it). Generate BOTH variants from one pristine file with a script that
  ASSERTS they differ in exactly one line, or the instrumentation itself becomes the
  variable. And keep the detector separate from the regression arm: the canary pair
  proves the bound, the REAL pair proves skin forcing still works, and grading the
  canary build for behaviour would conflate the two. Note also that a canary changes
  the layout it instruments -- the crash it produced belongs to the instrumented build,
  so quote the write, not the crash.
- **A COMMAND'S LOCAL FORM AND ITS STUFFED FORM CAN PARSE DIFFERENTLY, and the
  difference is silent** (measured driving Patch 488's arm). `setrenderer gl <path>`
  UNQUOTED hands the handler `argv(1) == "gl"` ALONE -- the path is `argv(2)` and is
  never read -- so no subrenderer token is parsed, nothing loads, nothing complains
  and the log holds no evidence either way. `stuffcmd * setrenderer "gl <path>"`
  delivers the whole quoted string as ONE argument, which the handler's own
  `COM_Parse` then splits into name and token, so THAT form exercises the code path.
  A regression control written in the local unquoted form therefore measures a
  different path from the subject's: it would have read as "the fix broke local
  renderer selection" on the subject while passing vacuously on the control. When an
  arm compares a local invocation with a stuffed one, quote both identically and
  check the control produced its own evidence line before believing either verdict.
- `alias <name>` WITH NO VALUE DELETES THE ALIAS. `Cmd_Alias_f`'s argc==2 path
  builds an empty value and reaches `if (!*cmd && !dpcompat_console.ival)` —
  "someone wants to wipe it. let them" — and unlinks it. So it is NOT a query, and
  using it as one destroys the subject: two arms reported a planted alias as
  "missing", the second written specifically to explain the first, and the item
  they were disproving turned out to be real. The only safe read is the full
  `alias` listing (argc==1).
- A `+exec` CFG RUNS BELOW `rcon_level` (20), and bare `rcon_level` prints
  `Unknown command` — with no refusal message, because the dispatcher's
  `cmd '%s' was restricted.` is a `Con_TPrintf` that does not reach the log at these
  settings. Stufftext runs at `RESTRICT_SERVERSEAT(0)` = 31.
  **CORRECTION (Patch 487, measured): the claim this bullet used to carry — "an
  `alias` defined in a cfg creates nothing" — IS FALSE.** `cfg/test/p487probe.cfg`
  creates `alias f_probe "echo LOCALALIAS-RAN"` in a `+exec` cfg: the full `alias`
  listing shows it, typing it prints `Execing alias f_probe` + `LOCALALIAS-RAN`, and
  it also fires as an `f_newmap` trigger. WHAT A CFG CANNOT DO IS CREATE A
  SERVER-LEVEL ALIAS, which is the distinction the old wording was reaching for:
  `Cmd_Alias_f` stamps `execlevel = RESTRICT_SERVER` only when `Cmd_FromGamecode()`
  (level >= 31) is true, otherwise `execlevel = 0` = "run at users exec level". A cfg
  is RESTRICT_LOCAL, so its aliases are USER-level — which is exactly what makes one a
  valid regression control and not a second subject. An arm that needs a SERVER alias
  must stuff it. Related and general: **SILENT REFUSALS ARE
  EVERYWHERE IN THE COMMAND LAYER** (`condump`'s `if (Cmd_IsInsecure()) return;`
  prints nothing either), so grepping a log for a payload's own output cannot
  distinguish "refused" from "never ran". Every arm needs a control that must
  print.
- `stuffcmd *` WITH NO `map` HAS NO CLIENT TO ADDRESS and the text vanishes with no
  message anywhere — the same shape as the stringcmd-before-spawn trap below, one
  level earlier. The server's userinfo dump is `user`, not `info`; `InfoBuf_Print`
  renders a blob key as `<N BYTES>` and never dumps its content.
- bash SPLITS `+set <cvar> "value with spaces"` INTO SEPARATE ARGUMENTS, so the cvar
  reads back empty and the arm measures nothing while looking like a negative. Use
  a path with no spaces (an 8.3 short name via `GetShortPathNameW`) rather than
  trusting the quoting — and print the cvar back before believing the result.
- STRINGCMDS SENT BEFORE THE SERVER HAS SPAWNED THE CLIENT VANISH from both logs
  with no error anywhere. A map with downloads (bhop_arcane: ~7 s of models)
  needs a wait for `spawn`, not a fixed guess, and the failure looks exactly like
  "the command did nothing". `sl_hold` is the same shape one level down: it needs
  `sl_goto <n>` first (the cursor is the LAST row after a rescan, and with no row
  under it the hold returns without a word) and must share a frame with its
  `sl_load`.
- `sprintf` DROPS ITS NINTH ARGUMENT and only warns, so a nine-specifier debug
  print reports the EIGHTH value under the NINTH label. A print that lies is worse
  than no print: this one sent a hunt after a value that was correct. Same cost,
  different shape — a line inserted between a braceless `if (x)` and its body
  REBINDS the body, so the gate looks dead while the print runs unconditionally.
  Instrument by copying the file aside and restoring it; never clean debug lines
  with a line-filter script (one such edit left an `if` with no body behind).
- A smoothness gate needs the subject's own motion measured first. Patch 383's
  owner walking circles varies its speed 4.3% by itself, so `speed CV < 2%` was
  falsified by the owner, not the renderer. Compare the render with the sampled
  motion (frames drawn exactly on a sample tick), not with a constant.

## Generated / never edit

`ftesurf/*.dat`, `*.lno`, `src/defs/*.qc`, `ftesurf/ftesurf.cfg` (auto-saved
archive), `ftesurf/data/**` (player data), `installed.lst`, `crashaddr.txt`.

## Conventions

- OPEN BUGS AND FOLLOW-UPS LIVE IN `BACKLOG.md`. Add what you find and do not
  fix (with a file:function and a falsifier); delete it in the fixing commit.
- QC style: `type() Name =\n{ … };`, `local` declarations first, tabs,
  ALL_CAPS defines, module-prefixed globals (`ui_`, `lb_`, `lj_`, `rec_sl_`).
- THIS TREE USUALLY CARRIES MORE THAN ONE WORKSTREAM UNCOMMITTED. Before
  claiming a build number, `grep -rn "BUILD 8[0-9]" src/` — comments claim
  numbers before the commit does. A `build.ps1` failure in a prog you did not
  touch is probably not yours: check `git status` first.
- Every change is "Patch NNN": append to `ENGINE_PATCHES.md` (engine repo) and
  bump the `patch` pin in `ENGINE.txt`. Mod-side-only patches still take a
  number and say so; the engine `commit`/`tag` pins only move for engine work.
  NEW ENTRIES ARE CONCISE: Problem / Change / Verified, a few lines each, no
  prose padding. Entries up to patch 334 are a long-form archive: never rewrite
  them and do not imitate their style. `qcbuild` bumps only on the user's
  "Build NN" commit.
  - PATCH NUMBERS COLLIDE BETWEEN CONCURRENT SESSIONS (343, 351 and 354 all did
    on 2026-09-18). Right before committing, `git fetch` both repos and take
    max+1 over the ENGINE_PATCHES.md headings AND untracked `cfg/test/pNNN*`
    files, where a claim shows up first. Tell any other live session the
    number, and claim one number at a time: an open range ("392 and up")
    leaves the other session no free max+1. Fix a collision forward by
    renumbering yours; `patch` never moves down.
- COMMIT AFTER EVERY FEATURE, AND PUSH. Do not wait to be asked and do not batch
  a session's work into one lump — this is the development phase, and the cost of
  not committing is what the build-86 catch-up had to clean up: 75 unpushed
  commits, the agent brief untracked, and four client sources that `cl_progs.src`
  references missing from the repo entirely, so a fresh clone could not compile.
  - The order is: build to 0 new warnings, run the falsifier, THEN commit.
    Never commit something you have not verified.
  - ONE COMMIT PER FEATURE. `git add -A` fuses unrelated workstreams into an
    unbisectable lump — this tree usually holds more than one. Stage the paths
    your change actually touched, and check `git status` for what you left.
    A shared file (AGENTS.md, ENGINE.txt, ENGINE_PATCHES.md) can hold another
    session's uncommitted hunks. Stage only yours: `git apply --cached` a
    trimmed diff. `git add -p` is interactive, which agents cannot use.
    Other sessions also STAGE files in this shared index. `git commit --
    <paths>` commits those paths' WORKING-TREE content: right for files wholly
    yours, wrong for one holding another session's hunks. There, `git apply
    --cached` yours, check `git diff --cached` is exactly your set, then a bare
    `git commit`.
  - A working-tree build proves nothing about a commit whose tree also holds
    other sessions' QC. Prove it alone: `git diff --cached > p`, `git worktree
    add <tmp> HEAD`, `git -C <tmp> apply p`, copy the untracked
    `src/fteqcc64.exe` in, compile the three `.src` there, remove the worktree.
  - Format is CONTRIBUTING.md's: `Build NN — …` or a plain subject ≤ 72 chars,
    body Root cause / Fix / Verified. Say what you could NOT verify.
  - `git push origin HEAD:main`. Never force-push and never rewrite pushed
    history; unpushed local commits are yours to reshape freely.
    **THE CHECKED-OUT BRANCH IS NOT `main` AND THE LOCAL `main` REF IS STALE.**
    This tree sits on a session branch (`build57` as of 2026-10-05) that is 563
    commits AHEAD of the local `main` ref, which still points at `4a87aef`
    (Patch 343). So `git rev-list --count main..feat-maps-demos` and any other
    comparison against `main` answers a question about a months-old tree, and
    `feat-maps-demos` reads as "500 unmerged commits" when it is simply old.
    Compare against `origin/main`, which is what HEAD:main publishes to, and
    verify a push with `git merge-base --is-ancestor <sha> origin/main` rather
    than by reading branch names.
  - `qcbuild` in ENGINE.txt still moves only on the user's own "Build NN" commit;
    the `patch` pin moves with your ENGINE_PATCHES.md entry.
- Compare two dynamic strings with `strcmp`; `==` only against literals.
- One `URI_Get_Callback` per VM — branch on the request id.
- Inspect existing implementations before adding systems: cvar mirrors in
  cl_hud.qc, `HUD_Size` fallbacks, the `Seq_*` anchor chain in cl_board.qc, the
  `sl_*` command table in cl_saveloc.qc/sv_saveloc.qc, surfd routes. Reuse
  commands/cvars/paths instead of inventing parallel ones.
- A display switch that can be turned off wants three things, not one: the
  `registercvar`, a row in `cl_hudedit.qc`'s `HE_OptDef` (rows must stay
  contiguous — the first `""` ends the pane, and `HE_ResetAll` walks them, so an
  omitted row is a cvar the reset button cannot recover), and a `set` line in
  `default.cfg`.  A chip in hud_edit's FIXED block instead -- a setting that
  belongs to no element, like Patch 440's `hud_font_outline` -- wants a
  `HE_FIXEDROWS` bump and a `HE_ResetCvar` line in `HE_ResetAll`, or the panel's
  height and its reset button both miss it.

## Boundaries and interfaces

- Server QC is authoritative (saveloc lists, timer/zones, heartbeat, board
  submits). Client QC renders/predicts. Menu QC is offline UI + directory.
- **PlayerPreThink is per USERCMD; PlayerPostThink is per PACKET.** The engine
  brackets the usercmd loop in SV_PreRunCmd/SV_PostRunCmd (`sv_user.c:9331`), so
  `SV_TimerFrame` and the whole timer run ONCE PER PACKET while touches and the
  mover run per command. Anything that must act on every command belongs in
  PreThink. Corollary: `FL_ONGROUND` read in PostThink is post-move AND
  post-touch — a jump or any upward `trigger_push` has already cleared it, so a
  ground test there is not the ground state the player had. Patch 403's first cut
  put a per-command clamp on the PostThink path and a client's own packet rate
  chose how often it fired.
- **A speed check must say whether it means `.velocity` or velocity + carrier.**
  `trigger_push` does not write `.velocity`; it arms `.run_basevel`, which the
  engine rides as `pmove.basevelocity` and which becomes velocity only on the
  first command nothing re-armed it (`SV_BaseVelocityFrame`). A body can be doing
  1800 u/s with `.velocity` EXACTLY ZERO — measured, and the recording's `seed`
  says `0 0 0` because that is honest. Effective horizontal speed is
  `.velocity + (1 + run_bv_tick * 0.5) * .run_basevel`. `run_stagecap` read the
  wrong one until P407/P411 (`launch 0 ... cap 290` at 1809 u/s); it is 0 since
  2026-09-21 (Lex: boosters count, speed does not matter).
- Client→server: `cmd sl_*`-style registered command strings.
  Server→client: `stuffcmd` (e.g. `set cl_saveroot`), stats, sprint, csqc
  entity fields. MIRRORS SPLIT BY TYPE: floats ride a stuffed `set` read with
  `cvar()`; STRINGS must ride `forceinfokey(p, "*key", …)` read with
  `getplayerkeyvalue(player_localnum, "*key")` (`*wrank`, `*phash`) — a stuffed
  `set` is Cvar_LockFromServer, and `cvar_string` then returns the LATCHED
  pre-override string while `cvar()` still reads the effective value.
  Customization channels: userinfo `lobbycolor`/`lobbyfx`/`lobbytrail` in;
  `tc` (the engine's own chat-name colour key), `lc`, `lrgb` and `*phash`
  (FS_GuidId) out.
- Engine↔QC: traps (`registercommand`, `infokey`, `serverkey`,
  `Mod_ForName`/`BIH_EnumBrushes`), per-frame cvar mirrors in QC, renderer cvars
  (`r_voidview`, fog) live in the engine repo.
- EVERY PUBLIC LOBBY SETS `lobby_nopb 1`. SV_PBGet then returns 0 and every PB
  figure is zero there — `TF_HAVEPB`, `STAT_FS_TIMERPB`, and the split and
  checkpoint deltas (`TIMERDELTA`, `TIMERCPD`). Anything PB-dependent is silent
  on the servers people actually play on; test it offline or on a listen server.
- CLIENT-SIDE TRIGGER PREDICTION (patches 335–338; full story in
  ENGINE_PATCHES.md). `cl_triggers.qc` mirrors the stateless Source triggers
  (teleport/push/setspeed) inside `CSQC_PredictPlayerMove`. It is a MIRROR of
  `sv_entities.qc` — read the server counterpart before touching either half.
  Load-bearing invariants:
  - Push is NOT a one-command carrier: 337 mirrors the full Patch 249 state
    machine. PUSH HAS THREE LEGS that must stay in lockstep: ride, CASH OUT held
    into real velocity when `!armed`, spend held Z. Per predicted command the
    engine runs `SV_BaseVelocityFrame`'s exact shape (restore, cash out, hand the
    window to `pmove.basevelocity`, spend held Z) and QC reports fires via
    `predmove_basevel` / `predmove_bvfired`. The engine keeps a sequence-keyed
    ring of (held, armed) and it MUST survive chain restarts — the chain restarts
    from the ack every rendered frame, so chain-scoped carrier state
    systematically loses the first replayed command's push.
  - THE SERVER STAYS AUTHORITATIVE for anything needing runtime state:
    StartDisabled / IO-toggled triggers, and filters whose verdict depends on the
    player's runtime targetname (`filter_activator_name` — outputs rename the
    player). Missing or unimplemented filters FAIL OPEN exactly as the server
    does, so those triggers ARE predicted (336). `.rec`/`.hid` evidence is
    untouched by any of this, and LISTEN SERVERS GATE THE HOOK OFF — a listen
    server never exercises prediction at all.
  - Patch 338 mirrors only the Enable/Disable half of entity I/O, ZERO DELAY
    ONLY: touch edges of predicted slots, event-only trigger_multiples, and
    `logic_auto`'s OnMapSpawn. A demotion fixpoint keeps everything else
    server-side — relays, buttons, timers, OnTrigger/OnJump/OnLand,
    Toggle/Kill/AddOutput/ModifySpeed, the All-variants, delayed outputs — and
    StartDisabled slots are predicted only when their enabler is mirrored too.
    Gate state = persistent array + sequence-keyed ring committed at chain start;
    edge seeding uses persistent last-overlap stamps (continuous stay vs
    warp-in). `trig_io` dumps the graph, `cl_trigdebug 2` traces edge seeding.
    If a map ever mis-gates, suspect a speculatively-committed event or a
    suppressed setspeed enter-edge first (both bounded, both Patch-328 class).
  - Exact client brush clipping = tracebox `MOVE_TRIGGERS|MOVE_OTHERONLY`
    against an edict with `setmodel("*N")` AND `solid = SOLID_BSPTRIGGER`,
    tested ZERO-LENGTH at the command's END position (the server's
    `World_TouchAllLinks` dispatch shape). Sweeping fires on grazes the server
    never sees. (A submodel with `solid = SOLID_NOT` silently clips its BOUNDING
    BOX instead — `World_ClipMoveToEntity` resolves the model only for
    SOLID_BSP/BSPTRIGGER/PORTAL — and huge trigger bboxes then fire from
    everywhere under them.)
  - `cl_prederror` prints one line per acked command whose server origin
    differs. KNOWN RESIDUE, do not re-chase: 4–8 u transients at discrete
    boundaries (pad entry, step-off lip) are Patch-328 class and self-heal in a
    correction or two. A CONSTANT quantized cascade or a GROWING error is a real
    bug — that is how 337 was found.
  - Changes here need a REAL playtest on `bhop_mom_training_beta` (24 pushes,
    20 setspeeds, training-scale blocks); synthetic walkers never once crossed a
    live pad, and both push bugs only printed under a human riding them.
    Harnesses: `p335k5` (walk-mode pad drop, z-drop WALK proof), `p338c`
    (Enable/Disable lifecycle) / `p338e` (the mapspawn-enabled teleport) against
    the `p335sv2` dedicated server.
- Patch 339 was a CENSUS, not code (`tools/ioscan.py`): across 82 roster maps
  there are ZERO zero-delay relay or timer gates on movement triggers — every
  relay OnTrigger gate is delayed 0.05–200 s (song/hint/ending sequences; the
  only MOVE-class rows are surf_lt_unicorn's ending viewholder swap) and timers
  gate no triggers at all — so a relay or timer mirror has an EMPTY actionable
  set — re-run the census before building one. The next real coverage step is a
  delayed-output scheduler (absolute-clock pending queue), the prerequisite for
  movers and song-timed work alike.
- Movers: the server has NO real movers — func_door/func_button are Tier-2
  state only ("NOTHING MOVES", sv_entities.qc:553 and :6221), func_rotating is a
  MOVETYPE_PUSH stub, and competitive maps force doors open anyway. Client
  mover prediction is moot until server movers exist.
- Pi deploy of csprogs requiring engine 335+ is version-skew safe: csqc globals
  bind BY NAME and missing ones point at junk (CSQC_FindGlobals), and
  CSQC_PredictPlayerMove is simply never called on an old engine — prediction
  degrades to server-authoritative, both directions.
- surfd broker: `/lobbies.json` (directory), `/api/join` (files a claim and
  returns a lobby NOT already running the map — the menu waits for the directory
  row to flip, patch 334), `/api/heartbeat` (carries assignments back to
  lobbies; children of mapcluster never heartbeat).
- The web leaderboard (Patch 359) is surfd's `/board/`, served from `surfd/web/`
  and proxied at proto.bar/ftesurf/board/ by `src/release/ftesurf.nginx`. Owner
  review is `/admin/runs` on play.proto.bar. The page must use relative URLs,
  because the browser path and Flask's path differ.
  The admin panel is PUBLIC at play.proto.bar/admin; proto.bar/admin/ is an
  unrelated FileBrowser. The panel's fleet comes from `cfg/lobby/lobby<N>.cfg`.
  nginx changes go in `src/release/ftesurf.nginx` or `surfd/surfd.nginx`, and
  installing them needs Lex's sudo (`install.sh`). A proxied surfd route must
  set `X-Real-IP`, or every client shares one rate bucket.
- LOBBY BODIES ARE A CSQC STREAM (Patch 383): the avatar's SendEntity
  (`sv_pose.qc`) feeds CSQC_Ent_Update (`cl_body.qc`). Each sample carries the
  owner's `run_movetick`, and the client interpolates on that clock, never by
  arrival; `Body_Pose(slot, ...)` is the API. `lobby_av_stream 0` is the old
  engine avatar byte for byte (the control), `lobby_av_rate 0` every moved tick,
  `lobby_av_budget` the cap for a full lobby. qwprogs and csprogs ship TOGETHER:
  a client whose csprogs lacks CSQC_Ent_Update is kicked. CSQC_Ent_Remove is
  global, so a second networked CSQC entity dispatches on the reserved type bit
  0x80. Measure with `body_trace`/`body_stats` and `tools/bodytrace.py`.
- `shared/sh_interp.qc` is the one interpolation speller (the replay viewer and
  the body stream). The replay viewer is measured per frame with `replay trace
  <n> <dt>` / `replay trace frames <n>` and `tools/watchtrace.py` (`--model`
  re-derives its tables, `--compare` replays the frames through a Python model).

## Anti-cheat and run evidence

- **Verifier observations need stable source bytes (Patch 599).** Fresh SHA-256
  before runner admission must match a known-current filing digest. Fresh reads
  after runner/row/stage checks must match the admitted bytes; evidence requires
  both the lobby copy the engine reads and KEEP copy the row checks read. Read
  failure/replacement becomes retryable ERROR, with unknown ticks and no counts
  snapshot, not a cheating judgement or a new Verified badge. Hash reads compare
  handle/path metadata and never use the filing cache. Hashing runs outside a
  writer transaction; existing ERROR budgets/refile/recheck scheduling remain.
  Unknown/stale filing digests retain compatibility without backfill. Run
  `surfd/test_verifier_sources.py` alongside sweep/counts/board/replays controls.
  This is a before/after fence, NOT immutable engine input or detection of a
  hostile host's intermediate change-and-restore. ERROR does not revoke existing
  PASS/owner approvals; no historical reread, schema, detector or review-policy
  change. Sweeper-only deployment needs no web reload or game/progs swap. Exact
  controls, full boundary and installed-source/hash gates: `tools/p599sources.md`.

- **Journal diagnostics are frame measurements, not new detector policy**
  (Patches 512–514). `identity_mouse_frames` counts nonzero counts only on a
  judged axis; its denominator is the yaw/pitch judged union, counting a frame
  once. `identity_no_mouse_longest` and `identity_unresolved_longest` follow
  original v-record order; an unjudged/nonmatching frame breaks continuity,
  interspersed event lines do not. These are not elapsed seconds, raw-report
  coverage or hardware attestation. Explicit `identity_blind` reasons explain
  existing abstentions. Fault and unresolved precedence, equations, thresholds
  and ranking remain unchanged. Receipt journal details retain the measurements
  before identity prose; a fault summary is limited to 96 characters so the
  sweep's existing 300-character bound cannot discard all numeric diagnostics.
  The original fault note remains unchanged. `test_journal_diagnostics.py` has
  active/sparse/excluded controls; `test_sweep.py` proves five genuinely signed
  SQLite rows including FAULT plus unresolved continuity. Independent reviews
  caught the bounded-FAULT omission; pre-fix controls fail and retained re-review
  closes it. Four paired readers from exact `ebf8462` deployed to the Pi and BOTH
  Windows installs, hashes and installed-module paths/controls proven at
  2026-10-06 21:21:56 UTC. Thirteen staged Pi suites pass. Real receipt pass read
  0/faulted 0; generated installed-source controls ACTED, not field calibration.
  Original gunicorn master and health/12 lobbies unchanged; no progs, engine,
  config, schema or historical reread. Primary build57 branch/index preserved;
  its two clean-but-stale reader paths now have owned commit-derived deployment
  overlays. Build/release from the clean inspected worktree, not that dirty tree.

- **A reproduced trajectory must also describe the ranked duration** (Patch 602).
  New finished-run PASS observations compare the engine's confirmed finish ticks
  with `replays.ticks`; the submit-time filename stamp is not that independent
  check. A different duration is HOLD, preserving measured ticks/counts. Missing,
  ambiguous or out-of-range `ticks N rows N` output is retryable ERROR, with unknown
  ticks and no counts snapshot, not a player finding. Evidence/abandon promotion,
  header/stage/source fences and explicit review precedence keep their contracts.
  No historical reread, schema, detector, engine/progs/config or Build change.
  `surfd/test_verifier_finish.py`: real POST/file/SQLite/public-board controls with
  an acting verifier stub; nine tests, five baseline failures, final zero. Both
  arrival orders, grouped companions, malformed output, approvals and abandon
  controls are explicit. Full Linux70 pass; Windows70 retain only the two existing
  admin UDP/amplification assertions. Native Pi pm_verify positively PASSes one
  existing recording with parseable matching ticks on an owned verifier port;
  that is compatibility, not detector calibration. Immutable run/sidecar corpus:
  baseline/subject269 rec,91 view,170 faulted files/173 faults, unchanged.
  Deployed exact a4a75be at2026-10-08T20:27:40Z to the Pi: only sweep and two
  controls, destination hashes exact; actual installed finish9/counts7/sources15
  pass. Canonical lock, mode600 completed DB/source rollback retained;137
  protected files/history/scalar board counts/master+worker/health12 unchanged.
  No reload or Windows game swap. Provenance/limits: `tools/p602finish.md`.

- **A finished receipt also describes the selected recording's duration**
  (Patch 603). `join_rec` compares positive signed ticks with the readable closed
  recording's exact integral finish, from the SAME captured bytes as nonce/angles.
  Mismatch is content FAULT with signature1 and independent angle result intact.
  -1 unkept and0 abandon are not recording durations. Missing/malformed/nonintegral
  closes remain unavailable, not invented clocks; VALID signature alone is not a
  measured association. New full/rec-only/view-only joins check; journal-only does
  not rejudge old recordings. Cache one parse per capture and reset on recapture.
  Computed `Report.finish_ticks` is not header `info`: review caught header-key
  spoofing and binary64 near-integer rounding. Raw bounded Decimal extraction
  closes both; legacy float grammar/info and fault classifications stay unchanged.
  `tools/test_receipt_ticks.py`:18 acting crypto/file/SQLite controls, including
  both sentinels, old grammar, exact-counter/header edges and snapshot replacement.
  Initial12 has8 baseline failures; final independent review closes both findings.
  Full Linux71 pass; Windows71 only the same two admin UDP assertions. rcpt74 and
  recorder306 pass; immutable269 rec/91 view baseline/subject170 faulted files/173
  faults, unchanged. No schema/format, detector, history, rank/review, engine/QC/
  progs/config/pin/tag or Build change. Extra parsing without a view is intentional,
  not measured fleet-scale cost. Exact7e24d9d installed2026-10-09: secondary04:09:08Z,
  primary04:10:06Z, Pi04:13:28Z; actual installed18 controls at each, three hashes exact.
  Primary's peer edit cleared before the guarded copy; never overwritten while dirty.
  Canonical Pi lock/completed mode600 rollback,137 protected files/history/scalar counts/
  master+worker/health12 unchanged; Windows protected6/195 and index unchanged.
  Initial primary/Pi path-context failures restored predecessors; private harness-only
  correction, no product repair/reload/progs/game/config swap. `tools/p603receiptclock.md`.

- **Angle explanations are observations, not strings to reconstruct later**
  (Patch 511). `receipts.angles_reason` stores up to 1,000 characters from the
  same captured pair as `angles`; diagnostic notes include why an existing
  rule abstained. Late view/recording updates move verdict and detail together,
  never overwriting an earlier angle FAULT. Partial reads/recovery keep the
  historical detail whenever they keep its verdict; journal-only retries leave
  both alone. A completed explicit full reread may replace both. The additive
  migration leaves old details empty, even if sources still exist. Authenticated
  admin renders literal text and says historical detail unavailable; an empty
  angle verdict says not checked, not that the recording is necessarily absent.
  This changes no thresholds, detector verdicts, signing history, ranked policy
  or automatic reread scheduling. `test_receipt_angle_reasons.py` exercises real
  signed pairs, migration and executed DOM rendering; it explicitly skips only
  DOM controls when Node is absent (83 Python checks vs 99 with Node).
  Scheduling suites compare complete rows including the detail.
  Deployed from exact `be530ead` to the Pi, final hashes 2026-10-06 20:34:30 UTC:
  18 staged suites pass, admin258; installed-source/reader83 controls pass. All
  old fields of22 historical observations match the owner-only SQLite backup;
  new details remain unknown. Live admin field/fallback and anonymous refusal,
  unchanged real receipt pass (0 reads/faults), original master/one fresh worker
  and health12 are proven. No lobbies/progs/binaries/configs/Windows install swap.
  For a selected `surfd-deploy.ps1 -Only` stage, include its unchanged import
  supports (recplot/simcheck/rcon; accounts/steam since Patch 612) or staging
  fails before copy. Live tools default
  to the game's `tools/`, not surfd's directory. Fixture writers may prepend their
  own tools path: preload actual installed readers and assert module paths in
  installed controls; byte-identical staged code is not installed-path proof.
  The shared build57 branch diverged from main and was preserved; published source
  is on main and the isolated p511-angle-reasons worktree.

THE DESIGN IS NOT IN THIS REPO. It lives in
`C:/FTESurf-private/anticheat-plan.md` — layers 0–3, threat classes T0–T5,
phases 0–5, experiments E1–E5. Read it before touching anything below; none of
this restates it. Half the commit log since build 72 is this workstream.

IT IS OUTSIDE THIS REPO ON PURPOSE AND MUST STAY THERE. This repo is GPL and
published to dl.proto.bar; the plan names live bypasses, the Layer 3 detection
thresholds and the T5 ceiling. Quote a conclusion here when you need one, never
the document. (It was in `C:/Users/Lex/.claude/plans/` until 2026-09-18 under a
generated slug — tool-managed, unbacked, and the only copy. That one is now
bannered as superseded.)

**A SECOND PRIVATE DOCUMENT SITS BESIDE THE PLAN: `ENGINE_SECURITY.md`**, the
audit of what a server can make a CLIENT do — the engine's stufftext surface,
which is the other half of the anti-cheat argument (a client that can be made to
run things cannot be trusted to report honestly). **EVERY DRIVEN ITEM IN IT IS NOW
FIXED** (481's `fs_*` set, then items 4/7/8 by Patch 483, 5/6/9 by 485, item 1 by
487, item 2 by 488, item 3 by 489 and item 10 by 491). What is left is the audit's
LOWER-VALUE list -- a census of read-only `fs_*` commands, never armed, and Patch
485's sweep is the reason not to assume that list is harmless: `fs_indexmaps` looked
read-only and was writing and mounting. THE TWO HEADLINE ITEMS WERE THE ONES THAT DEFEATED ALL THE OTHERS: one
stuffed `alias f_newmap "<anything>"` ran its body at `RESTRICT_LOCAL`, so every
`Cmd_IsInsecure()` gate read 29 for it and 481 was a delivery-path fix rather than
a boundary (Patch 487 closed it by running a trigger alias at the alias's OWN
execlevel); and a stuffed `setrenderer "gl <path>"` named the DLL the renderer
loads, which is native code in the client process -- driven with a canary whose
DllMain wrote a marker line (Patch 488 closed it by refusing an explicit
subrenderer token from an insecure caller, WHOLE rather than screened for slashes,
because a bare name also reaches LoadLibrary through the search order); and `allskins`
was a bare `strcpy` of a server-supplied argument into `char allskins[128]`, which a
canary build measured writing 172 bytes past it (Patch 489 fixed it with the BOUND and
not a gate, because forcing skins is a legitimate server feature that must stay
server-reachable); and item 10 let a remote server DROP a connected client and
re-purpose its process into a cluster master, because `mapcluster` had no restriction
level and a client registers those commands too -- the audit's own note that the route
"needs a local/listen server first" was wrong, and arming it is what showed that
(Patch 491). What is safe to say here is in BACKLOG.md's
"Engine client-security audit" section — code site, impact class, falsifier, no
recipe. The arms are in `poc/p482/cfg/`, `poc/p483/`, `poc/p485/`, `poc/p487/`
`poc/p488/`, `poc/p489/` and `poc/p491/` there and stay there: they are working
exploits for holes that are still open, and the convention is that an arm ships
publicly WITH its fix, not before it.

- **A CLEAR IS ONLY SAFE IF THE ILLEGITIMATE SPEED CANNOT SURVIVE IT — AND "I HAVE
  ENUMERATED EVERY PLACE THE SPEED COULD BE" IS NOT A WAY TO ESTABLISH THAT.** Most
  clears in the taint design satisfy the rule by ZEROING the velocity, which is
  checkable. The one that cannot — the finish, because players coast past the line —
  went through Patch 454 and six rounds of 455 trying to satisfy it by listing the
  places speed can hide: the push carrier, the carrier's vertical component, a pending
  trigger output. **Three consecutive review rounds found a defect in the previous
  round's fix, every one of them a term missing from the list**, because completeness
  is not a checkable property and "as far as I can trace" is the only honest answer
  anyone can give about it.
  What replaced it is a LATENCY BOUND — **but it does NOT dominate the enumeration, and
  the first draft of this entry said it did.** Measured after the fact: `vbsp_io_delay`
  is a bare `stof` with no clamp (`sv_entities.qc`, the only writer), and the shipped
  corpus carries 249 delayed outputs on 39 maps that reach a player through an input
  this QC implements — including a **0.5 s** `AddOutput basevelocity` on
  `surf_aquaflow`, which has an online zone file and is therefore a timed map. That is
  twice the dwell, in the wrong direction. What protects that map is the enumeration's
  `vbsp_iodelay` clause, so the two are COMPLEMENTARY: the bound covers the short and
  the unenumerated, the enumeration covers the long. Do not delete either on the
  strength of the other.
  The bound itself is that the clear waits until the body has read clear for an unbroken
  interval, on the argument that whatever was committed would have ARRIVED by then.
  **AND AN UNBROKEN INTERVAL HAS TO BE INTERLOCKED, NOT ANDed.** Requiring
  `elapsed >= D` AND `reads >= N` is bankable: send N-1 clear packets at a low
  `cl_netfps` (a client cvar the server cannot refuse), stop, and the streak sits one
  read short with both bounds pre-paid for as long as you like — then commit the pending
  write inside the Nth packet's usercmds, which run before the gate, and the required
  latency is 0. The streak must break when too long passes between OBSERVATIONS, which
  is what makes the interval an observation window rather than a span. It is stronger than waiting,
  because the carrier cash-out runs in `PlayerPreThink` — inside `SV_RunCmd`, before
  `PlayerPostThink` where the gate lives — so a pending carrier does not merely arrive,
  it becomes `.velocity`, which the gate already measures. Sized from the longest
  latency the tree has measured: an `OnEndTouch` at 0.06–0.09 s (four to six packets),
  a carrier at one command. **It needs BOTH an elapsed-time and an observed-read bound**
  — a read count alone is bought by bursting packets, and elapsed time alone credits a
  gap in which nothing was observed, which is the completeness argument again one level
  down. If you add a term to a gate like this, ask first whether the gate should stop
  depending on the list being finished.
- Three recordings of one run, joined by filename through `FS_RunPath`: `.rec`
  (server, `sv_timer.qc`), `.view` (CSQC per-frame angles, `cl_replay.qc`),
  `.hid` (engine raw-input journal, `in_generic.c`). A forgery has to be
  consistent across all three. Taint bits demote and never accuse:
  `TF_CHEAT/NOJOURNAL/NORULESET/NOPROFILE/NOMAP/NOCLOCK` in `sh_defs.qc`,
  consumed by surfd's `certifiable()`.
- **THE MOVE TRIPLE IS THE ONE COLUMN WITH NO RANGE TEST ANYWHERE** (Patch 493,
  mod-side): the engine copies a usercmd's `forwardmove/sidemove/upmove` into
  `.movement` with a bare assignment, and the only bound is the client's wire bound
  at ±32767.  `SV_MoveBoundFrame` compares each command's largest |axis| against
  `run_movebound` (2000, 0 = off, latched per map beside `run_startcap`), counts the
  ones over it, keeps the largest value the attempt sent AT ALL, and sets
  **TF_MOVEOOR (262144) -- a marker, never a demotion**, because THREE HONEST ROUTES
  PASS ANY CONSTANT: the move cvars are plain archived cvars (`cl_movespeedkey`'s
  engine default is 2.0 where `default.cfg` ships 1, so +speed sends 900),
  mouse-strafe adds `m_side * mouse_x` per command, and **A GAMEPAD WITH +speed HELD
  IS UNBOUNDED** (`in_generic.c`'s IN_MoveJoystick scales jstrafe by
  `360 * cl_movespeedkey` then multiplies by `cl_forwardspeed` without
  re-normalising).  The 2000 is a judgement over a corpus, not over a rule: 450 is
  the maximum of 1,342,728 axis values in 63 fleet runs.  The file states its bound
  as a `movebnd` header key from the SAME latch the check reads, so reccheck can
  fault the bit against the file's own `in` rows in both directions -- and no key
  means abstention on the `proprule` precedent, which is what keeps this tree's own
  Patch 358 fixtures (`side=2325 / fwd=-1067`, no bit) honest.
  **THE HEADER FLAGS WORD IS ONLY REWRITTEN AT A REAL CLOSE.**  `SV_RecFlagLine`
  reserves a fixed width at open and only `SV_RecClose` / `SV_RecKeepEvidence` seek
  back to it, so a Multi-Session park and a save-state prefix are closed files
  reading `flags 0` no matter what the run did.  That is why every header-bit
  cross-check in reccheck sits behind `end`, and it is not a guess: Patch 493's own
  first harness graded a park, got `flags 0` beside 284 rows over the bound, and the
  ungated check accused a file the writer never finished.
  Arm: `tools/p493move.py` (26 checks) with `cfg/test/p493{move,off}.cfg`.
- A FORGIVENESS HUNG ON ANYTHING `SV_TimerArm` TOUCHES IS A FORGIVENESS THE MAP
  HANDS OUT. `SV_TimerArm` is reachable from ordinary map DATA, not only from a
  gesture: 21 shipped maps have two abutting start regions whose seam re-arms on
  every crossing, and 66 have a velocity-keeping `trigger_teleport` landing inside
  a START region (both measured over the 1316-bsp corpus). Three attempts at the
  hopped-start rule died on this before Patch 445, which is why the rule now hangs
  its clear on a short, named list of callers instead of on a state change.
- AND THE TEST THAT SETTLED IT IS "DOES THE CLEAR KEEP YOUR SPEED". A taint on a
  pre-start attempt is only worth laundering if the prespeed the chain built
  survives the laundering, so a clear paired with `velocity = '0 0 0'` cannot be an
  exploit however reachable it is, and a clear that leaves the speed on is one
  however narrow. That is checkable, where "is this reachable from map data" needs
  a corpus census every time. Patch 445's three callers each zero or abandon the
  velocity; `SV_TimerArm` does not, and that was the whole bug.
- ON A DEDICATED SERVER MAP ENTITY I/O CANNOT BECOME A CLIENT COMMAND, and that is
  what makes `!r` usable as a rule. `SV_IOCommand` runs a map's `Command` through
  `localcmd()`, i.e. the SERVER console, and `ClientCommand` is the only path to
  `SV_ZoneChatCommand`. **THE DEDICATED QUALIFIER IS LOAD-BEARING AND WAS MISSING
  HERE UNTIL PATCH 445's ROUND 6:** the server's own `say` is registered only
  `if (isDedicated)` (engine `server/sv_ccmds.c`), so on a LISTEN server
  `localcmd("say !r\n")` runs the client's `CL_Say_f`, forwards as that player's chat,
  and does reach the gesture. It buys nothing (the forced `!r` zeroes velocity and
  voids the run, and a listen server cannot submit to the board) but the absolute
  form of the claim is false.
- THE `say`/`echo`/`print` ALLOW-LIST WAS NOT ITSELF A BARRIER, and Patch 446 is what
  made it one. `SV_IOCommand` checked the first token and passed the WHOLE string to
  `localcmd`, and `Cbuf` splits on an unquoted `;` — so `echo x;set run_starthop 0`
  passed the gate and ran both, at a restriction level that admits anything registered
  without an explicit one. `run_starthop` is read live every packet, so one poisoned map
  switched the whole hopped-start rule off; `run_evidence_days` would have made the next
  sweep delete recordings. 446 refuses `;`, CR, LF, `"` and `$` for an allow-listed verb
  (measured free: 0 of 1438 shipped Command rows carry any of them).
  THE LESSON OUTLIVES THE FIX: do not hang a new rule on "the map can only say things".
  Hang it on where the command ENTERS — client stringcmd versus console — which is a
  property of two code paths rather than a list of permitted words.
- THE SAVE FILE IS AN UNTRUSTED INPUT TO THE RUN, and `state.txt` is plain text in
  the player's own `data/saves` tree. Every taint bit the format carries — or fails
  to carry — is a laundering channel: `run_t_hopped` was missing until Patch 445, so
  one `retry` forgave a marked chain for free. The grammar is additive (a key-match
  loop with defaults), so adding a field costs one line at each end and no version
  bump. STILL MISSING and in BACKLOG: any check on the BSP behind the map NAME
  (`map` is written and no reader matches it, while `infokey(world, "*mapcrc")`
  already exists with a correct third verdict), the mover state, and the five
  movevars the `SL_RowGrounded` probe judges a row with.
- THE `.rec` GRAMMAR BLOCK over `SV_RecOpen` (sv_timer.qc) IS AUTHORITATIVE,
  currently FTESURF-REC 10 when the file holds a `pause` (retry, cold load,
  Multi-Session) and 9 otherwise. pm_recsim and pm_verify replay a v10
  Multi-Session file session by session (Patch 367) and REFUSE a retry/load
  pause or anything above 10. `tools/reccheck.py` is written from that block and
  never from the writer, so a writer that drifts from its own documentation gets
  caught. Same rule for `hidcheck.py` and `.hid`.
- **A `.rec` CARRIES ONE WITNESS FOR THE PLAYER'S INPUT, NOT TWO, so any detector
  that cross-checks one input column against another is vacuous in every file in
  this tree.** `keys` is DERIVED from the move columns: `SV_RecKeys` sets
  FSI_LEFT/RIGHT from the SIGN of `movement_y` and FSI_FWD/BACK from
  `movement_x`, and `momreimport.py` applies "the same rule as SV_RecKeys" -- so
  LEFT and RIGHT are mutually exclusive by construction and an overlap statistic
  reads a perfect score for everybody. Same for jump: `fl` bit 4 and `keys`
  FSI_JUMP are both `e.button2`, and measured they agree on every row of all 5571
  `.rec` files in `data/`. This is why `tools/reccheck.py`'s key-mask check is
  self-referential (BACKLOG), and the general rule is Finding E's: **a check
  built on a field the same writer derived from the field it is checked against
  measures nothing, however clean it reads.** Cross-check the client's `.view`
  against the server's `.rec` instead -- those are two machines.
  Measured by `tools/census/assist.py census`, which prints the agreement count
  beside it so a future reader sees the 0 disagreements rather than trusting this.
- THE `.hid`'S TWO "FRAMES" COUNTERS ARE TWO DEFINITIONS, and confusing them reads
  as a defect: `end <dt> <abs> <events> <frames> ...` counts DRAINS, i.e. `f`
  rows, while `in_jrn484_frames` counts VIEW SAMPLES the identity governed. The
  relation is exact and worth remembering: `#v == in_jrn484_frames +
  in_jrn484_skipped + 1`, the +1 being the first view, which
  `IN_Journal_CheckIdentity` returns on before `vcount++` (`!in_jrn_vhavelast`).
  Verified both ways on `p484_B.hid` (678 `f`, trailer 678) and `p486_B.hid` (182
  `v`, log reads 181, skipped 0). And `f` appears **iff a device event was
  drained** -- `IN_Journal_Frame()` has one call site, inside IN_Commands'
  non-empty-drain branch -- so a journal with no `f` rows is a journal of nothing
  happening, not a journal with a missing record.
- HID DIAGNOSTIC DENOMINATORS (Patches 515–517): union relevant-mouse coverage
  can conceal a silent axis. Use `identity_yaw_*` / `identity_pitch_*` coverage
  from actual judged sets, not governed-candidate totals. Each axis's exclusion
  dictionary plus its judged count accounts for emitted `v` records; earlier
  global gates omit unexecuted coverage rather than inventing a measured zero.
  Seed records are not comparisons. Counts-join windows partition into initial
  exemption, checked and absolute-input unjoinable; transforms overlay the latter
  two groups and exclude the same initial window. Spans/windows describe source
  records, not elapsed time or render frames. These additive measurements are
  available in verbose HID reports, NOT durable per-receipt metric snapshots:
  the stored 300-character reason remains bounded prose. No-window/invalid
  profile paths cannot be reconstructed as present-day measured zeroes.
- Version bump rule: new header keys and new record types are additive and need
  no bump (readers skip what they do not know). Bump when `end` grows a field or
  an existing line CHANGES MEANING. Then update, in reccheck.py: `COLUMNS`, the
  `HEAD_Vn` ladder, the allowed-header ladder, the trailer-width ladder, and the
  `r.info` print tuple — that tuple has silently swallowed a new field four
  builds running, because nothing automatic reads it.
  - "Additive" is safe for reccheck, NOT for the verifier: pm_recsim skips
    unknown records. A record that changes physics or the run's continuity
    (resume, pause, session) must be taught to pm_recsim/pm_verify in the same
    patch, either consumed or REFUSEd. pm_verify REFUSEs any version above the
    one it reads (Patch 356).
- A new recorder COUNTER or change-latch goes in four places, or a resumed file
  lies: `SV_RecOpen`'s reset, `SV_RecRecount` (every rewind recounts from the
  body), `SV_RecTrailer`, and sv_resume.qc's ms.txt (`SV_MsWriteMeta` /
  `SV_MsReadMeta` / `SV_MsRecAttach`).
- After ANY change here: `python tools/test_reccheck.py` (0 failed) AND a corpus
  sweep over `ftesurf/data/runs` — the fault count must not move. A false note
  about a correct file is the one thing these tools may not produce.
- A MAP ENTITY THAT WRITES A PLAYER'S VELOCITY MUST MARK ITSELF. The hop rule's
  only view of a jump is velocity_z crossing PM_NONJUMP_VEL, so any direct write is
  read as a jump unless the site sets `run_pushed` — keep its writer list in
  sv_entities.qc current. `trigger_setspeed` was missing for three patches and
  falsely accused players on 16 pads across 9 maps (Patch 412). Two rules, each
  paid for with a withdrawn patch:
  - ONE PACKET WIDE. `run_pushed` is cleared every packet, so it cannot cover a
    consequence that lands later, and a horizontal write clipped upward off a
    STANDABLE slope on the next move still is not covered (Patch 412's NOT DONE
    note). The carrier path survives only because it re-arms every command; a site
    that writes once has nothing to re-arm.
  - SIGN DISCIPLINE. A flag that WITHHOLDS an accusation must not be reused to
    GRANT credit. Reversed, `run_jumpcmd` turns "press on with the accusation"
    into "holding +jump buys the mover's rise" (withdrawn 411b, sv_timer.qc).
  Both directions are defects: a false accusation taints an honest run, a false
  acquittal ranks a driven one. Say which one a change trades for the other.
- EVIDENCE BOUNDARY, exactly: `warp` = a direct write of origin or velocity
  OUTSIDE the mover by a map entity, or by two client commands: `zone` (`!r`,
  zone_goto) and the zero a replay/rewind pin imposes on a body with speed or a
  carrier (`warp ... pin`, Patch 477; the hold's per-packet zero and the
  release's are not written). `ride` = the basevelocity carrier handed to
  the mover (a span: `arm` persists until changed, `pay` is the cash-out). A
  PORTAL crossing (`linked_portal_door`) is committed INSIDE the mover by the
  engine (`PM_PlayerTracePortals`), so no QC site sees it; the engine publishes
  it (Patch 346) and v9 writes the `portal` record. None has been captured live
  yet.
- THE VERIFIER: `pm_verify <file>` (engine, headless server on the file's map)
  replays a finished v9 or v10 file exactly and runs the timer's own zone scan, printing
  `VERIFY <file> PASS|HOLD|REFUSE <reason>` (never FAIL). It is exact only on the
  same binary and pin. It REFUSES on a zone-table mismatch before replaying a
  single tick, so a file recorded under a `cfg/test/*.zones.json` fixture only
  verifies with that same fixture installed at `maps/zones/local/<map>.json`. It replays with the file's own trace cvars
  (`pm_trisoup_bevels`, `pm_rotatedboxhulls`, `pm_portalcsg_scanall`; Patch 358),
  warns when they differ from the server's, and restores the server's values
  after. `surfd/sweep.py` runs it from proto's cron into the `verdicts` table.
  A board row reads Verified when its replay's latest current non-ERROR
  verdict is PASS or the owner approved it (`VER_SQL`, surfd.py). "Current"
  means newer than the file (`at >= replays.submitted`). Reasons never leave
  `/admin`.
  It follows a stage restart through the progs' `SV_VerifyRestart` (Patch 369),
  and a warp or restart written after its packet's sample (`!r`) acts after
  that packet's zone scan. At each Multi-Session pause it checks the clock (the trace's ticks at the
  pause's closing horizon = the pause's = the session's) and the resume (the
  seed within 0.0001 of the replayed state: the save writes %.4f) -- HOLD
  otherwise. A ghost window (Patch 373) runs no zone scan; it HOLDs on input
  once the window's rows went empty or 1 s in. Run verify harnesses whose
  subjects must PASS on the Pi: this Windows box builds one physent fewer at
  surf_derpis's finish than the Pi and the live server (Patch 373).
  Harnesses: `p349verify`, `p352slots`, `p356newer`, `p358trace`,
  `p367verify`, `p373verify`.
- A LOBBY STREAMS. A `retry` reads it back into a buffer first (Patch 368,
  SV_RecDestream). A save copies the stream's prefix to its slot a 512 KB
  chunk per packet (Patch 375); a load of the same lineage truncates the
  stream in place (`fsize(fh, n)`), any other rebuilds it from the slot.
  Anything that closes, renames or truncates the part file calls
  SV_RecCopyFlush first. The first load after a posted stage is always cold
  (Patch 360 keeps the stream as evidence). `p375sv/p375cl`, `p375bsv/bcl`.
- MOUSE COUNTS (Patch 376): a 376 client sends its input-ring and read sums
  in the prydon cursor floats when serverinfo says `fs_counts 1`; the progs
  write `mc` records and pm_verify HOLDs on ring != read. `p376sv/p376cl`.
  `sl_prev`/`sl_next` LOAD the save they step to -- a harness that follows
  them with `sl_load` loads twice.
- THE SPECTATE HOLD (Patches 380/382) keeps a run RANKED. `cmd rec_spec <n>`
  (entnum; 0 starts the countdown) sets `.run_pmhold`, and the engine then runs
  ZERO mover ticks for that player and links it without touching triggers
  (`*pmhold` "1" says the engine can; the progs refuse a ranked hold without it).
  A MOVETYPE_NONE pin is NOT a hold: the duck timer and stamina decay under it.
  The window is `spec 1|0` edges plus TF_SPEC (32768, a marker, not a class);
  the trace stays continuous, so a replay needs nothing from them, and pm_verify
  checks each edge where it sits among its row's warps. Anything new that moves
  a player, idles or rewinds a run, or parks it must call `SV_SpecRelease` FIRST
  (the funnels: disconnect, SV_Shutdown, retry, load, SV_ZoneMove, setpos,
  respawn), and nothing may write to the recorder while `run_pmhold` is set.
  Entry is refused while a trigger is touching the body or has not seen it leave.
  STAT_FS_SPEC 103: 0 off, n = watching entnum n, -3..-1 the countdown.
  Harnesses: `p380verify` (derived files), `p382a/c/d` (+`p382t/e`), `p382verify`.
- SPECTATING (Patch 385, `client/cl_spectate.qc`) drives that hold. The camera
  integrates IE_MOUSEDELTA itself and NEVER writes VF_CL_VIEWANGLES, so the
  body's aim cannot move (the .hid shows no 'v' record inside a window).
  `Spec_Active()` (cl_keys.qc) is the one "spectate owns the input" test --
  asking, leaving, watching, counting down, or the stat says so; anything new
  that opens over the game must refuse under it, as the ghost and replay do.
  Under it a key press runs only a bind on SPEC_CMDS, looked up with
  `Keys_BindNow` (the bind for the modifiers held -- plain `getkeybind` misses
  `bind shift+q`; an unbound right Alt runs left Alt's), and a key with a turn in
  ANY modifier slot is swallowed (`Keys_TurnAny`); a new menu key that must work
  while watching goes on that list or into a handler ahead of it in
  CL_InputChain. Two routes stay open, outside CSQC: a console `+left` and an
  F-key under the engine menu; the per-frame release cuts a held turn
  from either, not a force_centerview.
  The usercmd and its time are zeroed for the whole window, so after the release
  about one round trip of anti-hover moves land as no-input rows (one on a local
  host, p385rec).
  Handles: `spectate look <dx> <dy>` (a mouse delta through the chain),
  `scores pick <name>` (a row click minus the hit test), `spectate status`,
  `spec_trace` for `tools/spectrace.py`. Harnesses `p385view` (+`sv/own/two`),
  `p385hid` (+`t`), `p385rec` + `p385verify` (a recorded run, surf_666 fixture).
  A three-client harness needs `set sv_playerslots 4` (default.cfg allows 2;
  the third client just retries "full").
- At a frame rate near the 66 Hz stream a raw-sample control jitters between
  0, 1 and 2 samples a frame instead of stalling: grade the rate band, not the
  no-step fraction alone (p385view P4c).
- To put MORE THAN ONE COMMAND IN A PACKET use `cl_c2spps`, not `cl_netfps`.
  Lowering cl_netfps makes one LONGER command ("cl_netfps 20 -> one usercmd per
  50 ms"), and CSQC re-pins it to `pm_ticrate` at every map load
  (`Net_MatchTicrate`), so it only sticks if you set it AFTER the map. `cl_c2spps`
  drops outgoing packets (`cl_input.c:3570`, at most 2 in a row) and QW's backup
  moves then travel together — 3 `in` rows per packet. This is the only way to
  reach the multi-command paths a LAN never exercises.
- Experiment convention: numbered (E1…), one cfg per arm in `cfg/test/`.
  PRE-REGISTER the predictions and the falsifier in the cfg header before
  running; keep a CONTROL that must still fail (a harness that merely got looser
  improves both); write the result back into the header afterwards, INCLUDING
  the predictions that failed — build 85's did, and the failure was the finding.
  Each prediction must name an observable the change can actually move, and
  every changed call site needs a subject that only it affects. p358 first
  "verified" a restore through a cvar string the patch never writes.
  When you DERIVE an arm from another cfg (`sed` on log_name and a path is the
  usual way), rewrite the header — a RESULT block inherited from the source
  states another run's numbers for this one, and a stale RESULT is worse than
  none. Two of Patch 403's arms shipped that way and the review caught it.
- Capture pattern for a live recording: a run only closes at the finish, which a
  scripted walk never reaches. So the harness holds the run open at the end and
  an outside poller copies `data/parts/0.rec` during that window (an abandoned
  stream is removed on quit -- unless the run passed `run_resume_min`, see
  below). `b85ride.cfg` is the current worked example.
  On a lobby, copy `data/parts/p<port>-<slot>.rec` from the Pi over ssh during the hold
  (`p352live.cfg`). A copy taken mid-write ends in half a row.
- THE RUN NONCE (Patch 416). The server draws 128 bits at `SV_RecOpen`, writes
  `nonce <hex32>` in the `.rec` header, stuffs it to the running client, and sets
  **TF_NONCE (131072)** when that client echoes it (`cmd rec_nack`). A resume
  draws a fresh one into the body as `nonce <mt> <hex32>`; a retry or save-load
  re-publishes the one in force (`SV_RecNoncePublish`), and a COLD load adopts the
  nonce the rebuilt file's header states. MARKER ONLY -- not a class, not in
  TF_UNCERT, nothing demoted for its absence, and it must stay that way while
  pre-416 clients exist: the attacker picks which silence they present.
  reccheck FAULTS a v9+ file whose flags claim the bit with no nonce anywhere;
  the converse is never a finding.
- THE RUN RECEIPT (Patch 417). At the run-end edge the client signs five lines --
  server, nonce, ticks, sha256 of its `.hid`, sha256 of its `.view` -- with an
  Ed25519 key kept in `fskey` beside `qkey`, and the server writes
  `data/evidence/<map>/<runid>.rcpt`. Check one with `python tools/rcptcheck.py
  <file|dir>` (`--hid`/`--view` to hash the files, `--tamper` for the negative
  control, `--server` to check the address binding). THREE RULES THAT COST
  SOMETHING TO LEARN: a server may not ask a client to sign (`rec_sign` refuses
  `Cmd_FromGamecode()`, or a relay attaches a victim's key to your run); the
  statement names the server the CLIENT's netchan is talking to, which is what
  makes a signature non-portable; and the server refuses a receipt while the run
  is still recording, or the commitment is not made at the finish.
- EVIDENCE UPLOAD (Patch 418). `run_evidence_ul 1` takes the client's `.view`,
  `2` also takes the `.hid`; the client's own switch is `rec_upload`. The client
  stages to `data/staged/<nonce>.<ext>` and ARMS it; the server asks after the
  receipt lands (`sv_recupload <entnum> <nonce> <path> [path2]`) and the files
  arrive as `data/evidence/<map>/<runid>.<ext>`, swept by `run_evidence_days`
  with the recordings. THE REQUEST CARRIES NO PATH THE CLIENT READS -- it names
  the RUN and the KIND (`rec_ul_send <nonce> view|hid`, stuffed) and the client
  answers from the slot it armed for that run, or not at all. That asymmetry is
  the security argument; the nonce is what stops a LATE answer being the NEXT
  run's file, which is not a corner case (see the race arm). The client holds
  four arm slots -- two runs -- and `data/staged/` keeps two runs' files,
  because a run's second file is asked for only when its first has arrived.
  One chunk per request -- enforced by the packet sequence, not just by a flag
  -- written to `<name>.part` and renamed at 100%; a completion carrying no
  bytes is discarded, and a teardown deletes the part. A CLIENT THAT CANNOT
  ANSWER SAYS SO: `rec_ul_send` with nothing armed, or a file over the client's
  4 MiB cap, sends the `snap` stringcmd, which is QuakeWorld's existing "I
  decline" and reaches the same teardown. An armed destination nobody has
  answered expires in 15 s (a round trip), one with bytes arriving in 120 s of
  silence -- two clocks, because holding the first for two minutes also blocked
  the next runs' evidence behind it. A loopback client is never asked: on a
  listen server the recording is already here.
  `rcptcheck` now COUNTS the receipts that commit to evidence which is not on
  the host ("N of them commit to evidence that is not on this host"). That is
  not a fault -- an upload can legitimately not arrive -- but before it, a
  client that signed digests and handed nothing over looked exactly like a
  server with uploads switched off. Sizes decide the default: a `.view` is 2.93 KB per second of run
  (20 KB for 7 s), a `.hid` is 110 KB (8.38 MB for 76 s), 38x more.
  ONE UPLOAD AT A TIME PER CLIENT. A sidecar is one <=768-byte chunk per round
  trip -- 459 of them for a two-minute run, 25 s at 30 ms RTT and 80 s at 150 --
  so on a lobby the NEXT run finishes while the last one is still arriving. That
  request is refused and logged (`sv_recupload: <n> is still sending <path> --
  not asking again`), so **a run may legitimately have a receipt and no
  sidecar**; rcptcheck calls an absent sibling absent, not a fault. A request the
  client never answers expires after 120 s of silence, and every teardown (drop,
  cap, `snap`, expiry) DELETES the partial file -- a truncated `.view` beside a
  recording reads as a digest mismatch, which is the shape of an accusation.
  `run_evidence_ul 2` IS A LAN AND SHORT-RUN SWITCH: at 110 KB/s the client's
  4 MiB cap refuses any journal past ~38 s of run, and one that fits is 17,000
  round trips. Collecting journals from a public lobby needs a transport that is
  not the netchan.
- THE SIDECAR IS CHECKED AGAINST THE RECORDING, not just hashed. `reccheck`
  joins the `.view`'s frames to the `.rec`'s `in` rows by run tick and compares
  angles; `rcptcheck` reaches it by RUNID, so one command covers signature,
  digest and content. THREE RULES, and `reccheck.py --tamper-view <f.rec>`
  re-measures the sensitivity of all three on any pair -- the only honest way
  to quote one:
  - ONE-FRAME (v9 only, `ANG_SOLO` 0.05 deg): a tick that held exactly ONE
    rendered frame must agree to the `%.2f` print plus the wire quantum,
    because the usercmd was built from that frame. The tight rule, and the
    only one that discriminates on a camera that never turned.
  - SWEEP (`ANG_CUT` 3x the tick's own sweep, on over `ANG_HOLD` 5% of moves).
  - RUN LENGTH (`ANG_RUN` 250 consecutive), which is what sees a splice.
  Cut from 339 pre-v9 pairs plus 21 honest v9 ones. The real findings are
  `surf_garden/main/cheat` and `surf_demise/main/cheat`, which do pair a
  recording with another run's sidecar.
- THE JOIN HAS AN OFFSET AND IT IS NOT OPTIONAL. The `.view`'s tick column is
  `STAT_FS_TIMERTICKS`, a server stat read out of the client's last snapshot,
  so on a connection it lags `in.mt` by the round trip. AT 30 ms AN HONEST PAIR
  FAILED BOTH SWEEP RULES -- and every lobby client is remote while every file
  that calibrated the cuts is same-machine. The offset is READ OFF THE FILES
  (frames indexed by their printed angles, moves vote on the tick difference),
  never searched inside a window: a window has an edge and the edge convicts.
  Reported as `angle_lag`.
- IT ABSTAINS MORE THAN IT JUDGES, AND EVERY ABSTENTION IS LOAD-BEARING --
  each of these was a false fault on an honest run before it existed:
  - a GHOST window is a legitimate disagreement between exactly these two files
    and `cl_replay.qc:1730` says so. Exempt from the `.rec`'s windows, NEVER
    the `.view`'s, or a forger declares one ghost over his whole run.
  - a resume/retry/pause/session moves the tick epoch: no angle rule judges
    that file, including the two that convict.
  - the tight rule is gated on the ANGLE SOURCE (`in rows`), not the file
    version: `check_rec` falls back to `.v_angle` samples for any file with no
    `in` rows, at any version, and 0.05 deg against that stream faults 11
    honest pre-v9 pairs.
  - under `ANG_SOLO_COVER` 75% cover it reads `PARTIAL COVER` and surfd stores
    `BLIND`, never `OK`. Coverage is a line count in the attacker's own file,
    so it gates the CLEAN verdict and not the fault: hiding ticks costs a
    forger his `OK`, which is all it buys and is worth saying as such.
  - a non-finite column is its own fault, and a sidecar too broken to join at
    all makes the RECEIPT read FAULT rather than leaving the verdict empty.
  STILL OPEN AND DEMONSTRATED: a save-lock hold moves the same epoch and writes
  NO record of it (`SV_RecPause` is only reached on a cold rewind), so an
  honest held run is still convicted -- 33-41% of one-frame ticks past cut,
  cover reading 100%. The run is kept (`SV_TimerFreeze` marks it practice,
  which is `RT_LAST`, not `RT_NONE`), so it reaches the board. DO NOT TREAT AN
  ANGLE FAULT ON A RUN THAT MAY HAVE BEEN HELD AS A FINDING.
- CROSS-RUN SIMILARITY IS COLLECTED AND NOT ENFORCED (surfd schema 10,
  `surfd/simcheck.py`).  A run submitted twice -- a PLAYBACK of a recording rather
  than a performance -- produces two clean board rows and nothing else in this tree
  sees it, because `pm_verify` is an exactness check and PASSes a faithful playback
  by design.  `tools/census/recsim.py` chose the statistic and the fleet corpus
  calibrated it (positive min 1.0000 against negative max 0.5866, a clean 1.70x
  separation over 20 independent pairs), so **the sample and not the metric is why
  this stores and does not gate**: only 8 of those 20 pairs are cross-identity, and
  a similarity gate's hardest honest case is one player replaying one map.  A
  threshold picked from 20 pairs would be a guess in a measurement's clothes, so the
  sweep accumulates pairs from live submissions instead.  THREE RULES, each of which
  a review or a test caught:
  - **STORE-ONLY, EXACTLY AS SCHEMA 7's `receipts` TABLE WAS.**  Nothing in
    `VER_SQL` reads `sims`, no badge moves, no run is demoted and no public route
    exposes it.  `test_simcheck.py` arm 4 asserts that by grepping the three files
    that could have wired it in, which is the arm that would catch this becoming a
    gate by accident -- the one defect here that would hurt a player.
  - **A SKIP IS STORED AS A SKIP.**  `verdict` carries `skip` plus a reason beside
    `compared`, because a pair that could not be judged is not a pair that
    disagreed.  Two 9-move stubs agree over all 9 rows and read 1.0000, which is
    arithmetically true and means nothing; arm 5 pins that the floor turns it into a
    skip AND that the same pair with the floor lifted does read 1.0000, so the skip
    cannot pass by never having compared anything.
  - **THE IDENTITY IS THE GUID DIGEST, NEVER THE NAME.**  `same_who` is stored per
    pair and every figure is reported split on it, because a single max is the number
    that misleads.  `recsim.who_of` matches the trailing 8 hex WITHOUT requiring a
    dash in front, deliberately: `FS_PlayerSeg` files a name that slugs to "" under
    the bare id (`0001000_26c95e00_run.rec`), which a dash-anchored pattern reads as
    no identity.  (`1proto-` vs `proto-26c95e00`, the case first given for it, reads
    the same under both.)  The cost is that a netname ending in 8 hex characters
    reads as an identity -- a census imprecision in the safe direction, since it can
    merge two identities and so UNDER-report cross-identity pairs, never invent them.
  The comparison is NOT re-implemented: `reccheck` owns the `.rec` grammar and
  `recsim` owns the move stream, and `simcheck` calls `recsim.compare_paths`, which
  is the rule `rcptcheck` follows when it delegates to `reccheck`.  A host without
  `recsim.py` keeps migrating and keeps sweeping; the step stores nothing and
  `similarity skipped: no recsim.py found (tried: <TOOLS>/census/recsim.py)` rides
  on EVERY tick's sweep line (each tick is a new process, so the "once" this file
  used to promise never held).  Only the caller's TOOLS, else SURFD_TOOLS, is
  searched.  `sweep.py --sims 0` disables the step, note and import included;
  `--dry-run` prints the pending count and the identity split.  The comparisons
  run with no transaction open (test_simcheck arm 10): inserting between them
  held the write lock (peers-1) x ~88 ms, and /api/run 500'd behind it.
  **A RUN WITH NO COMPARABLE PEER IS NOT PENDING EITHER.**  `compare_run` stores
  nothing for it, so a `pending` selecting on "has no sims row" alone re-picked it
  on every tick and crowded out newer runs once the limit was reached.  Imported
  tiers are excluded for the same reason a lone run is: another community's run under
  another game's physics cannot be a playback of ours.
  **P524-526: VALID ZERO IS NOT UNAVAILABLE.** Required malformed move columns
  abstain for the whole source; parse to locals before parallel appends. Strict
  shared comparisons and CLI diagnostics distinguish I/O from successfully read
  no-input files. Tolerant standalone parsing remains available, but its None
  is not proof of absence. A zero-agreement pair retains a positive comparison
  denominator; a true zero-opportunity result abstains. `test_recsim_*.py` and
  `test_recsim_observations.py` prove positive, unavailable and measured-zero
  arms through the actual reader/storage/history boundary. This is not general
  grammar validation, pair-completeness, calibration or historical backfill.
  When checking corpus faults, retain sidecars: a REC-only private copy does
  not reproduce the complete REC/view reader result.
- EVERY v9 `.rec`/`.view` PAIR IN data/ HAS A NAILED-DOWN CAMERA (every 416-419
  fixture drives its route with `setpos` and `noclip`) and so does nearly every
  lobby run, which is why the one-frame rule is the one that works there and
  the sweep rule honestly reports `BLIND`. To make a swept pair: `cl_yawspeed`
  + `+left`/`+right` INSIDE the run, then a `setpos` to restore the heading
  (`p420live.cfg`); `tools/p421corp.py` drives a batch of them.
  AND DO NOT SET A THRESHOLD FROM ONE FRAMERATE. This file claimed for a day
  that the v9 cuts were ~400x looser than needed, from a single run at
  `cl_maxfps 100` -- at or below the mover rate the client builds one usercmd
  per rendered frame, so the two files carry the SAME NUMBER by construction.
  Across 30-500 fps the worst honest move is 1.49 against a cut of 3, so the
  cut stays. `cl_netfps` is not an axis either: `Net_MatchTicrate`
  (`cl_main.qc:108`) pins it to `1/pm_ticrate` on every map load.
  Every measurement behind the above is in the anti-cheat plan, not here.
- AN ABANDONED RUN KEEPS NO `.rec` UNLESS IT POSTED A STAGE.
  `SV_RecKeepEvidence` returns early on `rec_rec_posts <= 0`, so a main-leg run
  that is walked away from leaves a `.rcpt` and a `.view` and nothing to join
  them to. 37 of this tree's 38 receipts are that shape; "no recording to check
  against" is normal, not a fault.
  Since Patch 426 a KEPT abandon (one that posted a stage) takes its receipt:
  the server holds the run that ended (`rec_end_*`) until a receipt signing its
  ticks arrives. Its receipt asks no upload and names no `.view` (RT_NONE).
- EVIDENCE RETENTION REACHES EVERY MAP, NOT THE LOADED ONE (Patch 418, after
  review). `SV_EvidenceSweep` globs the current map's directory at every map
  init and, where `run_evidence_sweepall 1` is set, the whole `data/evidence/`
  tree once a day, stamped in `localinfo fs_evswept`. SET THAT ON EXACTLY ONE
  PROCESS: the tree is shared by twelve lobbies, so a whole-tree sweep imposes
  that process's `run_evidence_days` on all of them. Before that, `run_evidence_days` only ever applied to maps that
  were in rotation. It is 0 (keep everything) since 2026-09-21, so both sweeps
  are no-ops until it is raised; Patch 423 warns when the drive fills. The stamp is localinfo because an SSQC global is reset by
  the map load and a cvar the gamecode creates is purged with the progs -- both
  were tried and both silently swept at every init (`cfg/test/p418sweep.cfg`).
- A SERVERINFO KEY IS PUBLISHED AT MAP INIT, so a cvar it is derived from must be
  set BEFORE the map loads: `+set run_evidence_ul 2` on the command line, not
  `set` inside the `+exec` cfg. Cost a harness run.
- `surfd/test_admin.py` FAILS TWO ARMS AT HEAD on this box (the rcon
  amplification-guard message and "three snapshots cost no more packets than
  one") -- real UDP sockets, reproducible, and nothing to do with your change.
  Baseline before chasing: restore the file from HEAD and run it.
- TWO-PROCESS HARNESS TRAPS, one run each: a RUNNING dedicated server holds
  `C:\FTEQuake\fteqwsv64.exe`, so `build.ps1`'s deploy fails with "being used by
  another process" and the next arm measures the PREVIOUS binary -- kill it
  first and read the deploy line. And a second server started on a port another
  one already holds logs "Server spawned" and then sees no clients: the connect
  goes to the incumbent, so the run lands in the OTHER log file.
- `Con_DPrintf` NEVER REACHES THE LOG FILE unless `log_developer 1` (console.c:
  `developer` echoes to the console, `log_developer` writes). A falsifier that
  greps a server log for a DPrint measures nothing.
- **AND A SERVER QC `print()` NEVER REACHES A CLIENT'S LOG, WHICH IS THE SAME
  SILENCE WITH A DIFFERENT CAUSE.** `print` is builtin 339, "unconditionally
  print on the local system's console, even in ssqc" -- the local system being
  the SERVER. It is Con_Printf, and Con_Printf reaches a connected client only
  where the qc sends it there itself (`sprint`/`bprint`). So a client-driven arm
  that asks the server for something answered with `print()` sees NOTHING: no
  error, no "unknown command", no timeout -- the stringcmd went, was handled, and
  printed somewhere the arm is not reading. Measured three ways on 2026-10-06:
  `cmd viewpos` and `cmd timer` DO appear in the client's log because
  SV_SaveLocStatus/SV_TimerReport answer with `sprint(self, PRINT_HIGH, ...)`,
  while `cmd timefmt` and `cmd ent_census` -- `print(...)` -- did not, on a lobby
  whose qwprogs.dat was sha256-verified to be the local build and which answered
  both correctly in its OWN log. **USE `print`, NOT `dprint`, for a server-side
  harness handle** (dprint would be invisible on a lobby too, for the
  log_developer reason above, and a lobby has `log_enable 0`, `log_developer 0`,
  `developer 1` -- measured over rcon), and then READ IT FROM THE SERVER:
  `cfg/test/deploy496smoke.cfg`'s header has the rcon recipe (`log_name`,
  `log_dir`, `log_enable 1`, one cvar per `execute()` call, put back to 0 and
  delete the file afterwards). A command answered by `print` is still the right
  shape for a client arm IF the arm reads the server's log -- which is the only
  honest way to grade what the fleet is running.
- EDITING ENGINE FILES FROM A SCRIPT: the tree is stored LF and checked out CRLF
  (`core.autocrlf`), and earlier patch blocks were written back as LF -- so ONE
  FILE HOLDS BOTH. A multi-line match must try `\r\n` and then `\n`, or it
  silently finds nothing. Git normalises on commit, so the mix costs nothing but
  failed edits.
- Multi-Session (Patch 365): a run of at least `run_resume_min` s is PARKED on
  every disconnect, map change and quit (QC `SV_Shutdown`; not `retry`) into
  `data/resume/<map>/@<guid|local>/save000/`. A fixture that reloads or quits
  mid-run leaves a slot there that the next run on that map is offered: clean it
  with the rest of the test data, or `set run_resume 0`.

### Patch 502 — rewind/save pictures and continuation

- Patch 502 supersedes placement-only running rewind. The server ring keeps
  bounded timer/recorder snapshots beside physics; a same-lineage timed go
  restores the prefix as **segmented**, preserves valid pre-cut snapshots,
  and synchronously removes the abandoned tail. Ended runs without available
  evidence still produce practice placements. Cold restores do not invent
  historical scalar snapshots: the drawn prefix can predate the authoritative
  ring. A cold/demoted load clears the old implicit-row pointer, not its saved
  files; a later go on the same live lineage replaces its implicit resume row.
- The client picture is `trail.txt` beside a save's existing `.view`. It is
  visual data, never run evidence. Raw samples and rendered events are rebuilt
  together on a splice. An ordinary missing picture clears the live history;
  it must not copy another run's trail into that save. Ended/replay saves
  capture their cutoff at request time. Replay poses remain practice-only,
  regardless of the source recording's timer.
- Pictures need their own terminal result, not the latest save/load operation
  or an approximate command count. A raw list can overtake a queued save, and
  a later load can replace its event. The client consumes the correlated saved
  slot/cutoff before rebasing a loaded line and retains correlation through
  display reset. Native saves serialize captured pictures; following state
  changes wait behind them. Drain a ready load and hold **in one command-buffer
  pass**: the server's same-time/row/sequence/position checks are intentional
  and unchanged. Release stays immediate; deferred holds recheck ownership.
- `tools/p502segments.py --dedicated [--stream]` isolates fixtures and uses a
  real socket. It checks frozen timed clocks, held body/recording, release,
  deep warm rewind, cold row retention, viewer overlap/load, vote and board
  edges. Its display-off arm positively seeds a stale private picture after
  the server write, at one client FPS, before the answer is consumed.
  `tools/test_p502segments.py --rig <retained rig>` falsifies stale-report,
  recorder, clock, board, load-event and loaded-body false greens.
- 2026-10-13 installed-program check: save A -> load A -> save B -> timed
  rewind/go -> save C retains every raw visual-prefix field through each
  predecessor. Returning to A/B restores their own prefix; a fresh server and
  client loading C and saving again retains C's entire accepted prefix. Timed
  recording stays segmented, held countdown clock/history stay fixed, and a
  matched trail-on/off view positively shows the restored line. This is not
  arbitrary placement/replay-save promotion or a current fleet check.
- Keep the distinct short-load seam defect visible: loading a stationary save
  about 62 units away appended two pre-load-position samples after its intact
  prefix, before the new body arrived. `Trail_Take`'s 128-unit settle guard does
  not reject that displacement. The strict no-borrowed-tail check remains red;
  prefix preservation is not a claim of seamless continuation (BACKLOG).
- The inherited P502 cfg did not ACT its timed prerequisites against the current
  installed surf_dune zones: the first save was ARMED and later forward legs
  fell/reset. That failed rig is retained, not a suite pass. The focused checks
  used an overlay-only smaller start region on the existing safe spawn platform
  and proved a walked, running recorder before saving. Never modify shared zone
  content or weaken the actor gate to make the historical cfg appear green.

### Similarity collector operational limits (P546–548, P551–553)

- `simcheck.summary` distinguishes missing/error (counters unavailable), empty
  (measured zero), and available. Its read-only log line explicitly states no
  sample or unavailable; it never repairs/migrates a missing table.
- Each sweep reports unresolved-primary and row-failure counts, even when zero
  pairs land. These are availability, not player findings or coverage measures.
- `--sims` remains the source-row cap. `--sims-pairs` independently caps new pair
  admissions across a pass (default 200; zero disables quietly). Existing pairs
  consume none; unresolved peers and raised comparisons do consume an attempt.
  Limit exhaustion creates no fake skip for unattempted pairs. Comparisons still
  run outside write transactions; only completed rows flush short transactions.
- Collector comparisons explicitly bound each source to 16 MiB / 200,000 moves.
  Actual capture reads at most cap+1 bytes, including ignored records and growth;
  over-budget sources abstain whole, never a measured surviving prefix. The
  reader's standalone defaults remain unchanged. Old support without the bounded
  capability is unavailable, not silently unbounded.
- New skips capture allowlisted `skip_code` categories independently of prose.
  Additive ensure leaves old codes empty; read-only old/new-schema summary/admin
  classify them as legacy unknown without backfill. Unknown codes/details are
  withheld. Fixed categories are availability/abstention, not player findings.
- `--sims-seconds` adds a default ten-second monotonic cooperative admission
  window. Loader/schema/query time counts; in-flight work and normal writes finish.
  Zero disables before support import; invalid CLI values reject before main's
  connection, NOT before the existing import-time database initialization.
- NOT a hard timeout, overall RSS/DB scan bound, complete/fair pair scheduler or
  calibration. Existing pending and first-200-peer semantics remain. Run
  `test_simcheck_collection.py`, `test_simcheck_budget_cli.py`,
  `test_simcheck_ingestion.py`, `test_simcheck_codes.py`, `test_simcheck_time.py`
  and `test_recsim_observations.py` in addition to the regular deployment suite,
  which does not auto-discover new suites. Typed observations now project fixed
  malformed/unreadable labels; empty historical codes retain legacy withholding.
- Fresh parallel pi.dev reviewers in a NEW shared worktree can race automatic npm
  dependency installation (`ENOTEMPTY`, errno -4051). Capture state/diff and exact
  failed run first; once dependencies are present, retry that lane with the same
  native protocol. This setup failure is not a code review or external fallback
  permission. Private logs retain failed controls and successful replacements.

### Historical similarity byte provenance (P567-569)

- Capture the existing bounded binary buffer, not a second path read or normalized
  text/moves. Compared buffers carry version1 A/B SHA-256 and byte length; skips
  and unbounded standalone comparisons do not. The collector stores validated
  capture in the same short INSERT transaction as metrics. Old observations stay
  empty, never reread/backfilled or silently rebound to current files.
- Authenticated review retains stored A/B orientation and valid metrics when
  capture is missing/invalid. Bound raw SQL projection as BLOB bytes: SQLite TEXT
  slicing stops at embedded NUL and can hide malformed trailing data. Reject
  oversize/invalid UTF-8/JSON; coalesce SQLite's empty-BLOB substring NULL so the
  legacy-empty state remains explicit. Use text-only sinks and historical/not-
  current/not-authenticity labels; there is no public badge or policy consumer.
- Reload alone does not initialize an existing collector table. After a backed-up
  rollout, run installed ensure_schema under the canonical sweep lock, checking
  original columns/rows against the pre-deploy snapshot. This adds capture only,
  not a comparison pass. Keep legacy captures empty and prove a measured legacy
  projection ACTED. Explicit new reader/collector/admin *_sources.py suites are
  required; the standard shipper does not discover them. Node-free Pi DOM cases
  skip; Windows runs the actual renderer with an HTML-sink trap.
- Verified deployment source a976089 on 2026-10-08 at03:36UTC: all34selected Linux
  programs passed, installed22cases (five inherited, three DOM skips) passed, all
  four destination hashes match and old rows/values across six live tables are
  unchanged. Reader/SQLite/file backups retained, gunicorn reload/health/401 pass.
  Broad Windows admin suite's two UDP/RCON failures reproduce exactly in untouched
  e2d621b control; Linux passes. No engine/QC/progs/Build/release change. These
  hashes prove consumed bytes, not authenticity, current files, atomic A/B capture,
  calibrated thresholds, complete coverage, hard elapsed/RSS/DB budgets or browser
  visual acceptance. Shared uncommitted work was never deployed.

## The run line (Patches 432, 449-453)

- Patch 628: THE OFF-RAMP MARK AT THE RAMP'S OWN EDGE, from the loaded map.
  The ramp bit says the mover clipped a ramp DURING a tick; its sample is
  where that tick ended, and on 176 of 290 native leaves the hull is already
  off the ramp there. `Line_Edge` (`cl_lines.qc`) asks the map. `Line_OnRamp`
  traces the player's hull from a quarter unit off the recorded plane to half
  a unit into it and wants a face of the ramp band. The last sample whose
  hull is still against the ramp is the last contact sample (how 1), else the
  one before it (how 2), else a sample in the hold's 0.08 s that the bit
  missed (how 3); the tick from there to the NEXT sample is halved six times
  along the straight line between them, and the mark is the last point found
  against the ramp: time, place and velocity read off that line, the ordinal
  the first sample's.
  THE PROBE HAS THREE ANSWERS, and the third is not "no": 1 against a ramp
  face, 0 clear, -1 the hull starts inside something and the map cannot say.
  A leave is placed only on definite answers -- the near sample 1, the far
  sample 0 (asked, when it is the sample the leave was seen on), every
  halving 1 or 0 -- and otherwise stays on the last contact sample, Patch
  608's rule. That is also what `hud_lines_edge 0` gives, what a file with
  no plane gets (an import, a format before the column: `Line_EdgeOff`, and
  then no record is kept and a sample costs nothing), and what the live line
  always does: only a recording's two scanners hand in the plane.
  WHAT THE TRACE IS MADE AS, twice wrong before it was right. As `world` it
  passes through player clip, and a map whose ramps are clip brushes read as
  having no ramps (0 of 382 contact ticks on surf_axiom, 1 of 1,130 on
  surf_boreas): it is made as an entity whose `hitcontentsmaski` is
  `CONTENTBITS_BOXSOLID`. And as an ordinary move it also hits what is not
  the map: the glare pass's walk-through copies of brush entities, linked
  SOLID_BSP (`cl_sprites.qc`), and the server's brush entities of the
  moment. Something of that kind stood between the probe and the ramp on
  surf_medley (71% of its contact ticks answered) and surf_tensor2 (61%);
  which of the two was not separated. It is world-only now (`LN_XMOVE`, the
  engine's MOVE_WORLDONLY): 99.0 and 98.9. The review named the mechanism;
  the 17-map run showed it was the cause. A ramp that is a brush entity or a
  prop is not seen, and abstains.
  Measured over one native recording on each of 17 maps (2026-10-11, `replay
  rampprobe` and `replay marks` in the game): the hull is against a ramp
  face on 21,892 of 22,461 contact ticks; 16 maps at 98% or more and
  surf_boreas at 65 (388 of its ticks find no ramp face in reach and 5 start
  in solid; not explained). Of 290 ramp leaves 283 are placed -- 68 with the
  lip in the tick after the last contact, 176 in the last contact tick
  itself, 39 after a sample the bit missed -- and 7 stay as stamped. On the
  arm's two maps the placed marks moved a median 11.6 u (surf_kitsune, most
  39.7) and 15.3 u (surf_voyager, most 157.4: a ride whose contact outlived
  its bit by four ticks).
  Arm `runlines_edge.cfg` + `test_runlines_edge.py`: on; off (the model, mark
  for mark); a board line; the wrong map (nothing is against anything and no
  mark moves); the clip map. The client prints each placed leave (`lnx`,
  under `hud_lines_edgedebug`). Eight one-edit mutants are each caught in the
  game by the check that names them: the tick halved the wrong way, the
  sample before the last contact never tried, the hold's gap never asked of
  the map, the trace made as the world, the mark keeping its first sample's
  clock, or its velocity, the switch ignored, a board line not handed the
  plane.
  THE REVIEW'S THREE CASES ARE NOT ON THOSE MAPS and were shown offline, by
  its own scenarios on the build before and the build after (the built
  csprogs in an interpreter, a small brush tracer standing in for the map):
  a cleared record's plane was still read, so one file marked differently in
  a slot that had been used; a pillar 0.03 u beside the path made "inside
  something" read as "off the ramp" and put the mark BEFORE the last contact
  sample; a body that never left the face was placed 63/64 into its last
  tick. All three abstain now. Its parity check (the table bit-identical to
  the build before with no plane, with the switch off, with every trace
  missing, with every trace solid) and its ordering fuzz (110 streams, 5,826
  leaves, 0 violations) pass on the shipped build. None of that is the
  engine.
  The open's budget (Patch 626's note): 2 events a sample on a file with no
  plane, and 79.0% on the longest import against main's 76.2 with all three
  patches in. The first cut cost 8 a sample on files it could never place.
  The live line: `runlines_livelag` passes on this build and its one leave is
  counted as stamped (`lnmx 10 1 1 0 0 0`).
  `tools/runlines_smoke.py --mount` gives an overlay the default list of other
  games: without it a map that lives in one of them does not load, and the
  cfg waits its whole `waitmap` and carries on with no map.
  The older arms that compare a native line with tools/p449mark.py now say
  `set hud_lines_edge 0`: the model cannot trace a map, and the rule it holds
  is the fallback that still ships.
  NOT RUN, or not looked for in what ran: a ducked body on a ramp; a ramp
  that is a brush entity or a prop (abstains, by reading).
- Patch 627: THE TOPS AND BOTTOMS. A line now marks the top of each arc and
  the bottom of each ride (speed, energy, time), and they are on by default:
  `hud_lines_nums 2` in `default.cfg` and `registercvar` (until Patch 637:
  labels are off by default since, the owner's layout). Until now a turn
  was looked for only between two AIR samples and only once |vz| had reached
  40 -- so no bottom on a ramp was ever marked, which is where a surf run's
  bottoms are. `Line_Peak` (`cl_lines.qc`): a turn is where vz crossed zero
  between the sample before and this one, STAMPED AT THE CROSSING (time,
  height and sideways speed read off the straight line vz draws between the
  two; exact in the air, where gravity is two half steps) and not on the
  sample after it. It is MARKED when it stands `LN_EVDZ` (8 u) of height clear
  on both sides: of the turn before it or of where the count began, and of
  where the body goes next. So a mark appears once the body has moved on and
  is stamped back -- `Line_EvAt` now keeps the table in time order, which
  `Line_EvFind` searches by -- tops and bottoms alternate, and a wobble
  smaller than 8 u marks nothing however fast vz flips. In the air, on a ramp
  and across the change between them; the count starts again on a slot's
  first sample, after a break or a loaded save, and on or beside ground (a
  takeoff is not a bottom). A turn on a sample that carries its own contact
  mark, OR ON THE ONE AFTER IT, counts for the alternation and is not drawn
  twice: a landing on an upslope is the bottom, and in real files half of
  them turn vz up a tick after the landing's own sample (the review counted
  13 of 24 native and 119 of 244 imported), which the first cut drew as a
  second mark 17 u along. A LANDING ON GROUND IS A FAR SIDE TOO: a top that
  only the landing puts 8 u behind is marked (a hop onto a ledge 8 to 12 u
  under its top was marked or not by where the last air sample fell: 35 tops
  in 68 bhop imports). `Line_Seed` takes the seed's origin so a turn in a
  board line's first interval is stamped between its two samples.
  tools/p449mark.py mirrors all of it. On the longest import's open it costs
  3 budget events a sample: 78.6% of the call's budget, from 77.9% (Patch
  626's note has what that budget is).
  A BOARD LINE AND THE REPLAY OF ONE FILE CAN DIFFER BY THE RUN'S FIRST TOP
  (the review): a whole-run board line's count starts at its one seed sample,
  the replay's at the file's first sample, so a top just after the clock
  starts that is 8 u above the takeoff and not above the seed is on the
  replay only. 14 of 75 native whole-run files and 53 of 700 imports, by the
  mark model (8 and 30 under the rule before this patch). Not fixed: the fix
  is a board line that reads its approach as the replay does (BACKLOG). The
  fixture's apex 1 is built to be that case, so a change to it is seen.
  THE FIRST CUT WAS A GATE AND IT WAS WORSE: |vz| reached 40, or 8 u moved,
  since the last mark. It marked the same bottom twice where a ride wobbles
  (surf_voyager at 18.67 and 18.71 s) -- 52 pairs under 0.1 s apart in 400
  imports and 29 in 186 native runs, against 0 and 4 for the rule shipped
  (artifacts' peaks_sim2.py; the mark model itself gives 0 and 0).
  By the mark model over 400 imports (326 minutes): 8,627 tops and bottoms
  where the old rule marks 5,157, a median 13 a run against 7; 3,413 are
  bottoms and 3,452 have ramp contact on a sample either side.
  Arm `runlines_peaks.cfg` + `test_runlines_peaks.py`: the fixture is BUILT by
  the test, tick by tick, so every expected mark is known by construction and
  not from the classifier -- one motion as a native file and as an import
  (`runlines_peaks.rec`, `runlines_peaks_mom.rec`; `--write` regenerates
  them and a test pins them). Its docstring lists the cases; the review
  showed which the first fixture did not pin (LN_EVDZ anywhere from 3 to 10.5
  passed, and the x and y of a turn were not looked at), and it has them now.
  The control is the build before. Fourteen one-edit mutants are each caught: a
  turn that need not stand clear of the one before it, one marked at once,
  one on a landing drawn as well, ground not left out, a break not starting
  the count again, a turn stamped on the sample after it, the table not kept
  in time order, the first of two bottoms kept, and the review's six -- a
  bottom a tick after a landing drawn, a ground landing not a far side,
  LN_EVDZ 7.3 and 8.7, a board line's count from height 0, a turn at the
  later sample's x and y. They are BUILT and graded OFFLINE (artifacts'
  mutate_627v.py: the built csprogs in the review's interpreter against this
  test's own expectations, no game); nine of them were also caught in the
  game on an earlier cut of the fixture. The label default's mutant needs
  the engine and was caught there on that cut.
  The older ramp-leave grader took "the mark before a leave" as the ride's
  landing; a bottom sits between the two now (6 of 32 rides on p492voy.rec),
  and it looks for the landing.
  NOT RUN: a top or a bottom on the player's own LIVE line. `runlines_livelag`
  passes on this build and its land and leave are where they were, but its
  one ride has no turn in it, and three tries at a scripted jump inside a
  running run did not get one (surf_kitsune's start leaves 68 u of platform
  past its zone). A mark there appears about 8 u after its turn, by the rule.
  Not pinned by anything: a stitch that is not also a break.
- Patch 626: RAMP CONTACT INFERRED ON AN IMPORTED RUN. A .mtv records none, so
  an import's line had no ramp marks, its Segments column no ramp rows, and the
  strafe bar graded its rides against the flat-air target. `cl_infer.qc`
  infers it in the viewer from the samples; no file is rewritten and
  `WT_F_RAMPI` exists in memory only. Between two samples one mover tick
  apart, neither on ground and not a teleport, contact is a push up -- (change
  in vz) + step > 0.045 -- less a hard push (over 2.5 steps) with no sideways
  change at all, which is a floor touched for a tick. THE STEP IS READ OFF THE
  FILE (the commonest fall, to 0.01), never 800 * tick: one imported map runs
  gravity 750. Two readers through one `Infer_Step`: the replay
  (`Watch_InferScan`, a bit per buffer line, which the line, the Segments
  build and the playhead read through `Watch_Flags`) and the board-line job,
  which reads an import's file twice (a first pass for the step). UNAVAILABLE
  is a third answer: an import with no `momdemo` (21 of 5,281 -- velocity
  differenced from positions and NO ground flag, so a floor would read as a
  ramp; their fall is sharp enough, shares 0.27 to 0.50, that only the header
  tells), under 30 judgeable pairs, no fall common enough, or a run over
  200,000 samples (`INF_SCANMAX`: the budget, below). It is SAID: a
  ramp edge's label starts with `~`, `replay status` and `hud_watch_info` say
  `inferred`, the bar says `ramp: no plane` and gives no target, and
  `Line_Grade` gives no answer on an inferred tick. THE PLANE IS NOT INFERRED.
  tools/rampinfer.py is the rule in Python, written from the measurement and
  not from the QC; its `--score` and `--twin` are how the rule is known.
  Against native bit 16, one file a run (2026-10-10): 16 tick-counted
  recordings on 8 maps -- all 14,640 contact ticks and all 155 rides, 152
  starting and 155 ending on the recording's own tick, 1 extra ride (a noclip
  hover in a cheat file); 145 frame-sampled ones on 29 maps, re-clocked --
  52,386 of 52,433 ticks, 810 of 816 rides, 791 starts and 797 ends exact, 115
  extra rides of which 108 are in cheat, practice and save files and 7 in
  clean runs holding 351. AND ONE REAL DEMO: cfg/test/p492voy.rec is the
  owner's surf_voyager Momentum run flown again by this engine (bodies a
  median 0.3 u apart over the timed run), so its bit 16 is the contact the
  import lacks: 33 of 38 rides found, 31 starts and 32 ends on the exact tick;
  the 5 missed are one to eleven ticks on a face pointing DOWN; 1 extra ride
  is a lift. Over all 5,281 imports: 5,257 inferred, 24 unavailable (21 with
  no `momdemo`, 2 with too little air, 1 too long).
  What the measuring taught:
  A JITTERY CLOCK IS NOT A JITTERY MOVER. The first cut divided by the clock
  step and read half of free flight as a push: a format under 5 samples by
  frame (steps of 0.0088 and 0.0152 on a 0.01 tick) while vz still moves by
  whole steps.
  LEAVING OUT "vz DID NOT MOVE" WAS WRONG. Noclip and a ladder do that, and so
  does a body wedged still on a ramp, which is how a surf run waits at its
  start: native files set the bit there (2,770 ticks).
  REQUIRING A RAMP'S OWN SIDEWAYS PUSH WAS WRONG TOO. A body landing in the
  crease between two facets of a curved ramp is pushed up while the sideways
  parts cancel: that test refused the first tick of 10 rides in 33 on the demo.
  A REPLAY OPENS IN ONE QC CALL, AND THE CALL HAS A BUDGET. The engine ends a
  call at 100,000,000 branches, calls and returns (`execloop.h` RUNAWAYCHECK:
  the session ends with "runaway loop error"), and every pass of the open is
  paid per sample -- about 320 a sample before this patch, so some 312,000
  samples was already the ceiling. No arm sees it. The review counted it by
  running the BUILT csprogs in an offline QuakeC interpreter: the longest
  import (238,434 samples, an hour of surf_666) opened at 76.2% of the budget
  on main, 94.7% with this patch's first cut, and 97.4% with the two patches
  stacked on it. Shipped instead: the scan tokenizes a line once (48 a
  sample, was 82), and over 200,000 samples (`INF_SCANMAX`) neither reader
  infers and the line says `unavailable: too long a run`. That file opens at
  77.9% now; the longest that is still inferred (197,512 samples) at 73.1%.
  BEFORE ADDING ANYTHING PER SAMPLE TO THE OPEN, COUNT IT ON THAT FILE.
  BIT 32 IS A READER'S OWN: the three places that read a file's flags column
  for a line clear it first (`Watch_Flags`), so a file cannot set it.
  Arm `runlines_infer.cfg` + `test_runlines_infer.py` on surf_voyager: ten
  checks against the reference and tools/p449mark.py. The control is main, and
  six one-edit mutants are each caught by the check that names them (run on
  the build before the review's fixes). tools/test_rampinfer.py: 25 cases.
  MY OWN 19 MUTANTS OF THE RULE WERE ALL CAUGHT AND SAID LITTLE: of the
  review's 46, the 17 cases I had caught 17 -- no threshold, bound, tie or
  rounding was pinned. The 25 catch 42 (the four left: the hold's length in
  the scoring helper, twice, and two details of the mark model's seed). A
  mutant list written by the author of the tests measures the author.
  WHAT THE ARM CANNOT SHOW: its one recording never lands on the rule's edges
  (breaking the teleport refusal, the one-tick window, the three thresholds,
  the tie or the rounding in the reference changes none of its 4,516 bits).
  The client is held to the reference there only offline: 96,000 generated
  samples aimed at every threshold, through the built `Infer_*`, 0
  differences (the review's script, rerun on the shipped build). The same
  interpreter ran what the arm does not: a board line whose window opens in
  contact (two legs of a staged import), six real imports at both tick
  rates, reopening and dropped jobs. None of it is the engine.
- Patch 616: the LIVE Segments column at a teleport. `Board_LiveMoved`
  (`cl_board.qc`), called from the HUD just before the live `Board_Frame`,
  calls Patch 613's `Board_LineBroke` on a frame the body was moved. A map
  teleporter the client PREDICTED: `tg_teleseq` is the command it fired on and
  `tg_lastseq` the command the hook last ran on, which is the upper of the two
  states the drawn body lies between; while they are equal, and one frame
  past, and on the frame a teleport is first predicted. Anything else: the
  replay's kinematic rule between two rendered frames (64 u more than the two
  velocities explain) and no looser. A LISTEN SERVER HAS ONLY THE
  SECOND: the engine does not run the prediction hook there. A SAVE-LOCK LOAD
  IS NOT TOLD: from its event (`Board_ResetContact`'s 2 s clock, or the event
  still unread this frame, or `ui_rs_armed`) or its hold (`STAT_FS_HOLD`,
  `STAT_FS_PIN`) until the next step is seen, because a restore puts the open
  row back with the reference its save holds. `Board_Frame`'s break block now
  moves `seg_laste` too, and that line runs in the replay pass as well. An air
  row opened with no ground sample is not named Jump or Bhop live either.
  `replay seq live` prints the column and the teleports told (predicted,
  kinematic); `cl_trigdebug 1` prints each break and each load step kept
  quiet. Arm `runlines_seglive.cfg` + `test_runlines_seglive.py`, in
  surf_kitsune's spawn room (no zone there, so the run timer never clears the
  column; its door lifts a walking body 300 u, the real case). Three controls,
  each one edit compiled out; the grader's docstring names them.
  What the measuring and the one review taught:
  WHICH TWO COMMANDS THE BODY LIES BETWEEN MOVES WITH THE FRAME RATE. The
  first cut keyed the predicted window on the command counter (n - 1); the
  replay stops at the first command sent within one net interval, so it is
  n - 2 as often as not. The door hid it: 300 u is not blended and the
  kinematic rule took the same frame, and the grader summed the two counters.
  LETTING A HOLD GO IS A STEP WITH NO EVENT: behind 250 ms a 400 u/s save moved
  the body 129 u on release and the first cut told it as a teleport.
  A REVIEW FIX IS A CHANGE AND ONE OF THESE WAS WRONG. To keep a corrected,
  unpredicted booster from reading as a teleport the threshold was given the
  speed change times the unacknowledged time. That finding was arithmetic and
  so was the cure; the arm then lost a real move to it (157 u onto the floor
  at 30 fps behind 120 ms). Run five times each, that variant fails 4 of 5
  with the allowance and 0 of 5 without, so the one green run it had given
  on the pass before was the fifth. It is out again and the booster is
  BACKLOG. One green run of a case near a threshold is not coverage: run it
  several times and against the build without the change.
  Deployed 2026-10-10 from `adc724d`, csprogs `ebc342f0` only (qwprogs and
  menu.dat were already these bytes in all three places): both Windows
  installs 16:15Z, the Pi 16:15Z to 16:16Z with nobody on, all 12 lobby
  processes started after the swap (read from the host), and
  `pi_lobby_smoke.py` on lobby 1 was served this csprogs and drew the board.
  That smoke does not walk through a teleporter: the rule itself was measured
  in rigs on this file, not on the fleet. `.prev` is Patch 617's csprogs
  (`4355bdf0`); on the Pi the `.prev` pair is the whole 617 build.
  A SERVER COMMAND'S ANSWER IS PRINTED A ROUND TRIP LATER, after the next
  stage's `echo`: the grader reads the three `cmd viewpos` answers in order,
  not per stage (read per stage, every run said "cannot measure").
  THE FIRST JUMP AFTER THE MENU CLOSES can leave before the column has seen the
  floor (5 u low and no hop name on two of three dedicated runs): the arm
  waits 500 ms first. And a stage in a zone is cleared by the run timer.
  `cl_maxfps` IS A CAP: the arm prints what was drawn (`cl_predtrace -200`).
- Patch 613: a replay's SEGMENTS rows at a teleport. The run line knows where
  a recording moved the body (a break: `Watch_ScanPair`); the segment machine
  (`Board_Frame`, fed by `Watch_BuildSeq`) only noticed a step over 512 u
  (`SEG_JUMPDIST`). The scan now lists the file lines it broke on and the
  build pass calls `Board_LineBroke` there: the held ramp ride ends at once
  (as `Line_Point`'s does), the launch point is forgotten, the energy step
  across the break is charged to no row, the rows either side are not merged,
  and a fall that begins with a teleport is not named Jump or Bhop. The live
  board was not told until Patch 616. On eight recordings (1,894 rows) 86 rows change, none is
  added or dropped and no mark moves: surf_rookie's 0.54 s "Bhop" at +23807
  and 99.96% reads 124, six more rows between 1770 and 3247 in size read
  under 140, and the save010 file passes p449mark's containment (its ramp row
  ended 0.02 s past a 154 u teleport, where the hold ran out and nothing is
  marked). `runlines_segbreak.cfg` replays an authored body with three such
  teleports against rows written by hand; `test_runlines_segbreak.py` needs
  `--control-log` and refuses a build before the patch.
  Also: the apex or trough that arrives at a full mark table went in after the
  other peaks were cut; it goes with them now (`Line_EvAt`; checked with a
  private `LN_EVCAP 20` build, one kind-4 row beside `cut 1` before, none after).
  What the measuring taught: CUTTING THE HOLD ALONE MADE ONE ROW WORSE. With
  the ride ended at the teleport, surf_4am's next row opened "off the ground"
  and took the ground left behind as its launch point (+4935); the old build
  was only spared by a phantom held ramp. The step taken out is the WHOLE
  energy step, not its height: bhop_monster_jam's fail teleports put the body
  back 58 u up with its speed zeroed, and a height-only cut charged that speed
  to the hop (-76 where the flight gained 99). The fixture's third teleport
  rewrites speed so the two rules read differently (-2.6 against -52.7).
  `p449mark.py` now takes a break mark as the mark a row may end on; on the
  build before, the save010 row still fails it, so that is not what passes it.
  Patches 611 and 613 were deployed together on 2026-10-10 from `f141ee4`
  (its QC is `63eea9c`'s): csprogs only to both Windows installs (10:28Z) and,
  with a byte-identical qwprogs, to the Pi (10:28Z, 12 lobbies restarted with
  nobody on; `pi_lobby_smoke.py` on lobby 1 was served this csprogs). `.prev`
  is Patch 608's in all three places.
- Patch 611: the LIVE line (`cl_trail.qc`) pairs each sample with the command
  frame the server's stats describe. The ramp bit and the run clock are stats;
  the position is predicted. `Trail_Keep` keeps 64 command frames of predicted
  state and `Trail_Pair` takes frame `servercommandframe + 2`: the engine draws
  one net interval behind real time (`cl_pred.c` CL_GetPredictionRealtime), so
  that IS the current frame on a local dedicated server and an older one
  behind a ping. When two commands are acknowledged at once the frame between
  them is sampled too (clock between its neighbours', ramp bit only if both
  have it), so the line keeps a sample a command. Measured against the
  server's own recording of a scripted ride (surf_kitsune, exit at 890 u/s,
  `sv_minping 120`): the ramp-exit mark 79 and 100 u from the recorded contact
  sample on the build before, 3 u after; 44 u before at `sv_minping 60`; every
  sample of the run a median 69 u from its recorded one before, 2.5 u (at most
  9) after, with the recorded sample's ramp bit on all 113. At 250 ms: 4 u. At
  100 tick: 0 u (101 before). Seventeen marks of a hopping run: a median 0.6 u
  (at most 1.6), 15.6 u (at most 28) before.
  `runlines_livelag.cfg` through `runlines_smoke.py --dedicated --map
  surf_kitsune --server-arg "+set sv_minping 120"`, graded by
  `test_runlines_livelag.py <rig>/ftesurf --control <older build's rig>/ftesurf`.
  EXIT STATUS 2 IS "CANNOT MEASURE" (no latency in the run, a save that missed
  the ride): not a pass, run it again.
  TELEPORTS. One the client PREDICTED (a map trigger, `cl_triggers 1`;
  `tg_teleseq` in `cl_triggers.qc` is the command it fired on) needs nothing:
  the frames kept before it are where the server had the body, and the line
  now runs to within a tick of the teleporter. One the server made alone
  (`cmd setpos`, a zone's cancel region, a load, a hold) makes the kept frames
  wrong for a round trip, so `tr_kfrom` refuses them; the line still draws ONE
  sample of the old path, because the engine applies a snapshot's state a
  frame after its stats (two such samples on the build before, with no ping).
  UNDER THE TICK RATE the line is as right as it is with no latency at that
  frame rate, not better: a command then spans a tick or two. Measured with no
  latency on the build before: at 60 fps one sample in ten is a frame off (17 u
  at the 90th centile), at 30 fps a median 12 u. Pairing by TIME instead of by
  frame count (a tick after frame A + 1 was drawn) read 2 u at 30 fps offline:
  BACKLOG.
  Traps, each met while measuring:
  `sv_minping` is what makes latency on loopback (the server holds the
  client's packets back). ON A LISTEN SERVER THE STATS LEAD THE DRAWN BODY by
  under a tick (the acknowledged frame is 1 behind, not 2): untouched, 12 to
  19 u at 890 u/s. `servercommandframe` DOES advance in today's client on both
  server kinds; the `cl_hud.qc` essay that says otherwise is about an older
  build. The engine sends ONE command a rendered frame at most, so under 67
  fps `clientcommandframe` counts frames, not ticks. `+set pm_ticrate 0.01` on
  a surf map changes the cvar and not the mover (the recording's
  `movetickrate` stays 0.015): a `bhop_` map NAME loads the 100 Hz mode, so
  the 100 tick run used a private copy of the map and its zone file under such
  a name. The ride's saves must land in the 0.3 s between the exit and the
  reset, which is why the arm issues twelve; that reset is the zone's, not the
  map's carpet trigger, so the client does not predict it. An acknowledgement
  BURST of seven frames sat exactly on a `cmd setpos`: sampling every frame of
  it drew six samples of the old path, which is why only one frame between
  snapshots is filled. A perfect auto-bhop's one-tick contact is not in the
  predicted ground flag at the tick's end: four of six hops drew a trough and
  no land or jump mark, before and after.
  The review (one round) found the first cut dropping the last round trip of
  path before a predicted teleporter, losing a hop contact in a skipped frame,
  blanking under 12 fps with ping and breaking the line on a 0.25 s stall; all
  four are what the paragraphs above replaced, and the rework was not reviewed
  again.
  The same day's coverage of RECORDED lines, nothing changed: 298 ramp leaves
  in eight recordings of six maps at both tick rates, each on a sample of its
  file, 128 of them on rides whose contact normal turned more than 5 degrees.
- Patch 608: a ramp LEAVE mark is stamped at the ride's last real contact (the
  last sample carrying the ramp bit), not on the sample the 0.08 s hold ran out
  on. The classifier, its edges, the hold and the Segments rows are unchanged, so
  a bridged gap still marks nothing; each mark also keeps its edge's clock
  (`ln_ec`, the LAST column of `replay marks`), which containment is graded on.
  The contact colour follows the marks, so it ends with the ride too. On a
  surf_kitsune recording all 38 ramp leaves moved back 0.090 s, a median 211 u
  (84..315). The stamp is the first sample at or past the exit (on the two
  authored exits measured the bit stayed set through the tick the hull left
  in), so it can be a tick late, and where the bit alternates it can end a gap
  early. A ride with no contact of its own since the slot began or the last
  break or stitch takes its first such sample: that is what keeps the table in
  clock order, and the review's one code finding was a stitch on a repeated
  clock (no break, so the hold survives) putting the leave BEHIND the stitch.
  `runlines_rampleave.cfg` through `runlines_smoke.py --recording`, graded by
  `test_runlines_rampleave.py` (give it `--control-log`: a build before the patch
  must be refused), `p449mark.py` and `p452col.py`, which now colours from the
  file's marks. THAT RECORDING'S 38 RIDES ARE ONE SHAPE (the test prints the
  census), so the arm also replays the authored `runlines_rampshapes.rec`
  against a table written by hand. p449mark's stamp is NOT independent of the
  client, and its model had lacked Patch 530's hold reset at a break: three of
  its eight fixtures failed on the unmodified build, and one still failed
  containment until Patch 613. No fixture reaches LN_EVCAP; the compaction was
  checked with a private LN_EVCAP 20 build. Not covered then: the LIVE line's
  stat lag, turning ramps and the rate sweeps (see Patch 611 above).
  Deployed from `26e350e` on 2026-10-10: csprogs only to both Windows installs
  (08:07Z) and, with a byte-identical qwprogs, to the Pi (08:09Z, 12 lobbies
  restarted empty; `pi_lobby_smoke.py` on lobby 1 was served this csprogs).
  `.prev` is Patch 607's in all three places.
  Two traps: `runlines_smoke.py` copies only TRACKED cfg files, so a new
  fixture is "cannot read" until `git add`, and the run still says completed.
  And DO NOT RESTORE ONE LINE OF AN UNCOMMITTED FILE WITH `git checkout --
  <file>`: that took this whole patch out of `cl_lines.qc` after a throwaway
  build. It came back from the diff, proven by the rebuilt csprogs matching the
  tested one byte for byte. Commit first, or undo the line.
- Patch 527: `hud_edit lines` has seven rows, not 29. Player (`hud_trail`),
  demo (`hud_watch_path`) and selected board (`hud_lines_board`) lines are
  independent and on by default. Turning off board drawing retains selections.
  `lines help` lists advanced label/style cvars; their existing names still work.
  `tools/runlines_smoke.py ftesurf/cfg/test/runlines_ui.cfg` checks this in a
  private content overlay, retaining logs/screenshots and unlinking its content
  junctions. Never run the fixture in the owner's save/config tree.
- Patch 529: reset/start-save loads retain the failed line and its pre-reset
  rewind head; a new attempt begins its one-second fade. The practice extension
  stops in a start/stage boundary after placement settles. Live discontinuities
  beyond a speed-scaled tolerance are visual dashed breaks, never .rec warps.
  `runlines_reset.cfg` through `runlines_smoke.py --dedicated`, graded by
  `test_runlines_reset.py <private log>`, covers map and explicitly requested
  stage-1 attempts. P502's full dedicated prefix/save/rewind suite also passes.
  Stage 2 on surf_dune in the first rig teleported outside its start and launched
  immediately; that is not a valid standing-at-start control. Immediate restart
  while TS_RUNNING (and clock reset) still needs separate lifecycle handling.
- Patch 533 supersedes P532's visible steps: live births come from Line_Add,
  not Line_End, and alpha is a constant-rate ramp. The small unbuilt tail draws
  with stride 1 and no stale sphere culling, including first two samples; breaks
  still terminate joins. Full spheres/LOD/gain builds remain batched. Only live
  tail colours refresh, not board caches; contact/energy classifiers still walk
  the active slot rather than guessing a kind. Demo publication is one uniform
  fade, not a restarted stagger every 32 points. Static interleaved-gradient
  noise replaces the body's 16 Bayer levels: 33 actual distinct monotonic coverage
  images over 32 substeps, normal survivor colours, no animated noise seed.
  Extended private overlay: 37 alpha checks, 51 rendered screenshots including
  pending-tail/break controls; both constant half-fades are 0.4993 brightness.
  The separate dedicated reset regression still passes all five acted checks.
  No all-backend or worst-case contact-mode FPS claim; owner motion feel remains
  a human check. No authoritative evidence or movement state changes.
- Patch 532: `hud_lines_reveal 0.18` reveals newly published live/demo chunks
  from oldest to newest; 0 restores instant drawing. Heap birth stamps belong
  only to demo slot 0 and the two live/previous slots. Rebuilding never restarts
  old births; Clear/reuse and cap compaction preserve the publication contract.
  Mature demo publication composes with playhead reveal, not the run clock.
  `cl_playerfade 1` is viewer-local opaque Bayer discard on streamed Body_Predraw,
  hidden within 32 units and opaque beyond 128 (`cl_playerfade_near/far`). Existing
  body alpha stays 1; no server rule, ghost or owner avatar change. The material
  is embedded in CSQC so joining clients need no separately installed GLSL file.
  `hud_edit lines` now has 11 rows including these four controls. The private
  overlay `tools/visual_fades_smoke.py` proves 33 publication/playhead/compaction
  assertions plus 16 actual line/body screenshots. Its test-only world-free
  hooks are never deployed. A forward call to Line_StatsReset (declared later)
  crashed fteqcc without stdout in the initial extension; removing the unnecessary
  call fixed the harness. QC definition order applies to test seams too.
  Frozen product `4fdfbdf` deployed 2026-10-07, verified at 04:03:53 UTC:
  both Windows CSQC hashes/backups and Pi live/previous pair match. Clean-build
  bytes equal the tested production build; no test hooks. SSQC source is unchanged
  from P530, Windows SSQC/menu/native untouched; Pi SSQC hash stays identical.
  default.cfg matches on all three destinations and also catches up the earlier
  approved P527/P529/P530 viewer defaults (their progs shipped without that cfg).
  No movement/server-rule changes. All 12 lobbies restarted empty, remained healthy
  and were empty after controls. Fresh-cache clients on both installed engines
  downloaded matching CSQC, drew the 11-row pane/defaults and received live peer
  body streams. The actual lobby map was surf_kitsune; its existing single missing
  material is not a fade/shader or map-download fix. Owner configs/data unchanged.
- Patch 530: `hud_lines_declutter 0` (default) keeps visible labels and lays them
  into up to 16 nearby vertical lanes instead of silently suppressing overlaps;
  `1` restores the sparse grid. The existing 128-label/frame cap, view/distance
  culling and explicit mark switches still apply. Impossible density can still
  overprint. `hud_lines_telealpha 0.3` fades both dashed joins and endpoint squares.
  Ramp holds/turn grades cannot span a break. Private `runlines_labels.cfg` on a
  supplied surf_kitsune .rec plus `test_runlines_labels.py` tests 8 complete vs 6
  sparse labels, all numeric fields, record-derived marks and both off switches.
  Screenshots prove the text actually draws. Native contact bits are retained;
  adjacent ramp-plane changes and imported missing planes are NOT solved here.
  The full dedicated P502 main/edge suite and 306 reccheck checks pass.
- QC compiler pitfall found here: `fov` is LOCAL to `Line_ViewFrame`. Referring to
  `fov_y` from a new helper caused the installed fteqcc to access-violate
  (3221225477, no diagnostics). A clean same-commit build acted; storing the
  screen size explicitly for the helper restores a zero-warning build. Do not
  diagnose a silent compiler crash as an unexplained success or rely on LSP.
- P527/P529/P530 deployed from clean inspected `5ff0b3b` on 2026-10-07 UTC.
  Both Windows installs received only CSQC with immediate `.prev` hash controls;
  native/plugin, SSQC, menu, owner configs/data were unchanged. This preserves
  already-deployed water code, not a new water deployment. Pi got the coherent
  SSQC/CSQC build pair through the no-player/hash/backup/restart procedure; SSQC
  source/shared contracts are unchanged from its deployed water baseline.
  All 12 active units and live/previous hashes verified. Actual fresh-cache
  downloads with both installed native clients match this CSQC; spawned editor
  screenshots and independent help/defaults act. Heartbeats empty afterward.
  Local map content was supplied read-only to the private overlays; this is not
  a map-download/material-availability fix or completed Momentum/contact/compare
  acceptance. Existing archived fade settings are not forcibly overwritten.

- **What it draws.** `cl_lines.qc` renders a recording's path as a screen-space
  strip, slot 0 the open replay and 1-8 the board's ticked lines. On it:
  `V` where the run touched ground or a ramp, a chevron where it left one, a
  DOUBLE chevron where the jump button was down, and two grey bars where a
  SEGMENTED run loaded a save (`resume`/`retry`, not `restart` -- a stage
  restart is not a save state coming back). Numbers at those marks and at the
  peaks where vz turns over. Four colourings beyond speed: gain, contact,
  energy, air control.
- **THE MARKS ARE THE EDGES OF `Board_KindOf`**, the same three-state contact
  function the Segments column is built from (`cl_board.qc`), with none of that
  column's row-level debounce. So every segment row boundary is a mark, and a
  contact too short to become a row is a mark with no row -- both directions are
  graded by `tools/p449mark.py`, and the second count is registered per fixture
  rather than asserted to be zero. Do not write a second detector; extend
  `Board_KindOf` and both follow.
- **Marks carry their own position, never a point index**, which is what makes
  them survive the two decimations (the build-time stride and the past-the-cap
  halving) with no fixup. A mark is identified by its SAMPLE ORDINAL and never
  by its time: both bhop fixtures repeat a timestamp, because a file records one
  sample per packet and a held clock repeats it, so keying on `t` mis-assigns.
- **MEASURED AND NOT ENGINEERED AROUND:** samples are one per packet (43-65/s
  against a 66.67 Hz tick) and a bhop's ground contact is one tick, so a perfect
  hop's contact can fall between two packets and be absent from the file. The
  line misses those hops -- and so does the Segments column, from the same
  samples, identically. Do not interpolate hops the file does not contain.
- **Cvars.** `hud_lines_marks|land|leave|jump|stitch|size|gap`,
  `hud_lines_nums|speed|energy|ref|delta|vz|time|numsize`, and
  `hud_lines_win|winf` (seconds of run time behind and ahead of the playhead; 0
  = the whole line). The colouring, the visible distance, the width and the
  through-walls mode stay on the EXISTING `hud_watch_path_*` names -- nothing was
  renamed, so archived configs keep working. All of it is one `hud_edit` pane
  ("Run lines", 25 rows, tooltips), plus `set` lines in both shipped configs.
- **Your own run, live (Patch 475, `cl_trail.qc`)** fills slots 9 and 10 from
  `pmove_org`, one sample per command frame, while the run is on the clock. A
  finished or cancelled run keeps its line; the next run's start swaps the two
  slots and the old one fades over `hud_trail_fade`. A picture only -- nothing
  in it is sent or is evidence. `trail` prints both slots and the build cost.
  Graded by `tools/p475trail.py`, pixels included.
- **Reading it back.** `replay marks [slot]` dumps the mark table as the draw
  pass reads it (`lnmb`/`lnm`/`lnmz`), `replay seq` the Segments rows for the
  containment check, `replay colours <slot> <stride>` dumps `ln_col` itself plus
  the movement settings a grade was measured against, and `replay marktrace <n>`
  prints what the next n frames actually DREW -- counts, window, ia/ib, and each
  glyph's screen position and label text. Graded by `tools/p449mark.py`,
  `p449win.py`, `p451num.py`, `p452col.py`, `p453q.py` against the `.rec` itself.
  `scores lineat <slot> <path>` is the harness handle for a board line: a
  headless client has no board rows behind it, and every `scores line N` answers
  "no recording behind that row".
- **A COUNTER OF INTENT IS NOT EVIDENCE OF INK.** Text drawn from inside
  `Line_Draw` does not appear at all -- the pass is a stream of `R_BeginPolygon`
  batches the engine defers until a later 2D call flushes them, and a
  `drawstring` between two of them draws nothing. The labels are queued and
  drawn from `cl_main.qc` beside `Ev_Labels`, which has the same shape for the
  same reason. While this was broken every counter, the trace and the graded
  label text were green; only a screenshot disagreed.
- **The air-control grade is the strafe bar's own**, regime for regime
  (`cl_hud.qc`'s `HUD_DrawStrafe`), so the line and the bar cannot grade one
  moment two ways -- including its several NO ANSWER cases, drawn grey rather
  than red. It reads the movement settings from THIS server, as the bar does for
  a replay: a recording made elsewhere is graded against local settings, and the
  v9 header's `pmpin` block is where a future patch would get the file's own.
  EXCEPT THE TICK: since Patch 470 the line (every slot, `ln_tick`) and the bar
  (`rec_wt_tickrate`) grade a replay at the file's own `tickrate`. A board slot
  gets it in `Watch_LineJobWindow`, after the header -- the job's start is too
  early. `replay status` prints the bar's `bar tick/ideal/speed/regime`. The
  Segments column too since Patch 473: `Board_Tick()` (cl_board.qc) is
  `board_ov_tick` inside Watch_BuildSeq's pass, the server's live. To change a
  listen server's tick in a harness, `sv_cheats 1` first -- the movement lock
  reverts a typed `pm_ticrate`.

- **Multi-patch reach actors (native, not exit acceptance).**
`tools/offramp_trimulti{,_smoke}.py`: eleven actors on a rectangular-patch
ramp and one V trough. The supplied patch set is the BUILT native BIH's
triangle leaves, dumped by value with their node indexes and required to equal
the table; no neighbourhood is discovered. A reach boundary comes in two kinds
and the record tells them apart: a HORIZON CUT (exists at one probe distance)
and a FOOTPRINT EDGE (five of six here unmoved at larger horizons; the sixth
vanished, a lowered neighbour being already under the footprint). Gap WIDTH and
neighbour DROP each lose reach alone: a 16-unit gap whose neighbour is 2 lower
loses it at the footprint edge, the neighbour 0.052 beyond the probe, and has
it back within a command at a horizon cut; the one
COPLANAR 50-unit gap here never regains it, because the unsupported body sinks
0.18, 0.36, 0.54 a command and takes the far patch's SIDE as a wall (blocked
2, graded; one hit). On the two exits observed the native ramp flag stayed set
for the rest of that command and read clear in the next. Native down-2 equals
exact horizon-2 reach at 352 of 352 tick ends, including ones 0.0006 and
0.0013 either side of the cut and 0.0003 and 0.0002 either side of a footprint
edge: a TRIANGLE leaf's clip decides on the TRUE entry fraction and the 1/32
bias only moves the reported one (a brush under Source clip decides on the
adjusted one; one tick end here tells the two apart). In a trough, at
`pm_fixrampbugs` 2, the mover takes its two-plane crease branch in every
command once it is there (16 of 32; verified; three planes and every stopping
outcome refuse), and ANY move, once
5.5e-5 of a command, clears its plane list first. The crease's float32
normalisation bleeds 6e-5 u/s a clip at 400: a flat velocity tolerance was
1.9e-5 from refusing an honest capture. Ties are real, between coplanar
triangles, between a face and a bevel that IS the face plane (turned either
way by rounding), and in a crease between two DIFFERENT planes: never gate on
which tied plane or leaf won. A CONSISTENT LIE NEEDS ITS OWN TEST: a
single-field fault trips some other gate as well, so deleting the gate changes
no verdict. When a check lists row prefixes by name, read what the layer
prints: the shape layer's is GEOM. A report label is a claim: derive it from
the counts, or "verified" gets written over a rule no hit took.
Harness lessons, each paid for here: a `Mock` patched in as a pass-through
cache keeps every call it receives (2.1 GB in the slow tests; patch in a plain
function). A MUTANT SWEEP IS A TEST TOO AND MUST READ A FROZEN COPY: one run
"killed" all 54 mutants in test setup on a path bug, another 58 in under a
second each on a source digest, after the worktree it imported from was edited
under it. Pass the unmutated copy through the harness before the first mutant
and AGAIN after the last, and count setup kills apart from test kills. SEAT A
MUTANT AT THE CALL AS WELL AS IN THE FUNCTION: a unit pins what a function
does with an argument, not which argument its caller hands it, and the clip
rule's entry velocity lived through a sweep and a review that way. A falsifier
not yet run against its mutant has shown nothing. A script named `warnings.py`
shadows the standard module for every Python started beside it.
See `tools/OFFRAMP_CONTACT.md`; private diagnostic builds NEVER ship.
- **Front reach on the captured path (offline, not exit acceptance).**
`tools/offramp_trireach.py` runs the exact front algebra on the committed
segments below instead of endpoint chords. `hypothetical_down` (0<=d<=2)
CONTAINS `in_place`; on these actors live in-place reach is empty, the hull
riding 1/32 off whichever plane it hit (0.0521 above the front with the bevel,
0.1012 without). Parameterize a command by time-left BEFORE x committed
fraction, pinned against captured velocity; still not an exit clock. Record
whether a reach boundary is the horizon cut or the footprint edge: both
entries here are the cut, both exits the edge, and bevel-OFF's "interior
reach, unreachable endpoints" holds at horizon 2 only. The chord was resolvably
wrong in 1 of 96 commands; a kink under one float32 step is not a finding.
No actor loses and regains reach: recontact is NOT ACTED. A gate that compares
empty with empty has not run -- carry the non-empty count (12 of 114 here).
See `tools/OFFRAMP_CONTACT.md`.
- **Bounded actual intra-command path diagnostic (not exit acceptance).**
`tools/offramp_tripath{,_smoke}.py` adds fixed-capacity native TryPlayerMove
value copies to the unchanged three bevel-PM actors. Capture ALL attempts,
including misses and native endpoint validations, time-left/clip/commit/return;
do not substitute accepted requests or command-endpoint interpolation for the
actual collision-clipped body path. Fixture-only vs OFF/ON/repeat must preserve
prior body/query gates. Only ordinary identity standing-AABB paths are graded;
cached/recovery/portal/ground/sliding/posture generalization refuses or remains
NOT_TESTED. Native zero biased fraction with positive truefraction can still
clip and take a residual sweep. Native time-left is NOT an elapsed exit clock:
a clear pass breaks before decrementing it. Raw-loss first move is now captured
and remains native/ideal clear, NOT support-exit proof. Independent field/row
falsifiers must ACT even with prior gates and mirrored repeat parity unchanged.
See `tools/OFFRAMP_CONTACT.md`; private diagnostic builds NEVER ship.
- **Off-ramp stage diagnostic (not a patch or fix).** The first `surf_dune`
  route rides a slope but reaches ground before a surf-to-air leave: native
  contact alone does not prove the intended off-ramp arm acted. On Voyager,
  the start's real launch pad is reached walking BACK relative to its spawn
  view; forward merely explores the floor. `tools/OFFRAMP_CONTACT.md` describes
  isolated per-native-tick/packet/sample/event/actual-render traces and strict
  counterfactual gates. Live positions are predicted while flags/run clocks
  arrive in server stats. The hold can expire on a point well after native
  contact loss; the mark and actual render retain THAT point, so render retiming
  is not established as the cause. A jump between sampled run clocks is not a
  changed hold constant. Repeated timestamps retain command/input ordinals.
  First rewind press confirms a running-run splice; the second opens. Missing
  packet anchors (including a capture terminated between two prints) are RED;
  preserve them before a labeled rerun. Structural PASS explicitly does not
  close classification, jump/trough semantics, hull/brush geometry, LOD/pixel
  acceptance, or P560's requested/native clock mismatch. Raw traces stay private.
- **Buffered off-ramp replay (tooling only).** The live per-tick `Con_Printf`
  seam perturbs sampling; use a separate clean native worktree for the buffered
  exact-input control in `tools/OFFRAMP_CONTACT.md`. Build/retain the clean server
  before instrumenting. Capture OFF/ON/repeated ON must match the clean mover
  summaries and reproduce the file's own body text; this is not bit-exact clean
  state proof. Fixed buffers dump only after capture stops; overflow rejects.
  A bare `sv-rel` server/rig cannot load VBSP: copy the installed HL2 loader into
  the PRIVATE executable directory, copy isolated default configs, and load HL2
  before `map`. Hash that external loader rather than asserting a clean build.
  Offline brush candidates must use model 0's reachable leaf brushes, not the
  entire global brush lump (inline models are in there too). Python raw LZMA
  decoding can return padding beyond Source's declared `actual` output size;
  the plugin caps at `actual`, so the geometry reader must too, not invent a
  trailing leaf or weaken alignment checks. Candidate hull/plane halfspaces do
  not authenticate the winning brush. Short raw losses can lack a nonface
  boundary crossing; no-match/unsupported geometry abstains. This still does
  not decide the early label, live render/tick-rate cadence, or P560 clock.
- **Winning trace provenance (tooling only).** A later validation/ground trace
  can overwrite BIH probe globals. `offramp_origin_smoke.py` keeps the witness
  local to each BIH trace, stamps the exact output address and carries only
  the winning nested-model/physent result into the accepted ramp buffer row.
  Fraction decrease alone is insufficient: legacy brush clips replace an
  equal-fraction winner while Source clips retain the first; actual accepted
  leaf updates must drive the witness. Cached firsttrace needs its own copy;
  recovery's synthesized normal is not the underlying collider's plane.
  Runtime leaf ordinals are not VBSP brush-lump IDs. Missing/nonparticipating
  traces, portals and solids abstain; triangles stay unresolved, not guessed
  displacement identities. Sixteen setup-only native collider controls and
  four-arm repeat/parity validate provenance, NOT winning halfspaces, edge/
  jump/seam motion, cached/recovery/portal movement paths or classification.
  Use a fresh clean engine worktree and retain private raw output. No product
  patch/ABI/recorder/hold/mark/Build/deployment changes belong to this tool.
- **Copied brush geometry (tooling only).** Offline BSP plane lumps omit loaded
  bevels; a known winning runtime leaf is not a lump brush index. The optional
  `offramp_shape_smoke.py` seam copies all loaded side planes/bounds AT THE WIN,
  with a fixed 64-side whole-shape cap/ABSTAIN and instance/capsule/direct-BIH
  metadata. Never reopen source geometry at dump. Repeating every plane for
  every contact can exhaust the harness timeout: deduplicate only immutable
  captured payloads AFTER capture, not live geometry. Payload IDs are not
  collider identities. Exact accepted-plane membership and unchanged numeric
  tick/contact+origin captures validate copied static data, not a physical exit.
  Extended/hybrid callbacks, pose/scale/capsules, embedded/entity geometry,
  recovery/portals and over-cap shapes abstain. Halfspace gaps at a loss use the
  PREVIOUS contact hull; the new tick's posture/hull is not recorded here.
  Bounds are retained, but side-gap math is not the full collision/support
  oracle. Keep authored edge/jump/seam and same-input mark/render gates open.
- **Actual contact/tick hulls (tooling only).** `offramp_hull_smoke.py` composes
  a fourth private layer in a NEW clean native worktree. Copy actual mins/maxs,
  capsule/movement type and posture state separately at accepted contacts and
  tick ends; raw stand/duck cvars are not observed hull heights. A transition
  flag alone does not imply the small hull. Seven real `PMSrc_ApplyHull` setup
  controls restore all touched state, but are NOT crouch/motion trajectories.
  `offramp_hull.py` uses EACH POINT's actual hull for copied halfspace gaps;
  capsule/non-normal samples abstain. Quiet/parity/repeat and the initial
  standing-only replay prove capture, not physical exits or posture coverage.
  Added dump rows exceeded the prior 120-second limit on the same segment;
  180 seconds completed. Retain timeout rigs; no performance claim. No extra
  capture-path queries/I/O/allocations, player ABI or mark/hold/recorder change.
  Full support-oracle, authored edge/jump/seam/unsupported movement and all
  same-input render/rate/classifier/mark acceptance gates remain open.
- **Authored native static trajectories (tooling only).** `offramp_motion_smoke`
  adds a PRIVATE command driving REAL PM_PlayerMove/PMSrc ticks on models from
  the existing BIH_Build API, not mirrored private node layouts. Fixture-only
  versus capture servers, plus a no-oracle arm, prove body/query/binding parity.
  Six32-tick cases ACT: interior ride, partial/full straight and convex side
  exits, input-driven interior short loss/reacquisition, real ground jump and
  overlapping-brush handoff. Query actual hulls AFTER ticks: stationary, down2,
  projected +/-2 against union and each brush; validate JOINT convex/box
  feasibility, not independent expanded-plane maxima. A unit wedge falsifies
  the latter. Side support disappears at an end sample BEFORE raw contact's
  falling edge; an interior raw loss retains support and previous-brush loss
  at a seam need not mean union loss. These are observations, NOT mark rules.
  No map/progs/plugin/asynchronous spawn or owner content/process needed.
  Embedded template/base stamps are provenance, not authenticity. No new
  production traces/ABI/marks/hold/clock/evidence semantics. Only these static
  fixture actors are closed: exact physical exit time, broader support/world,
  real posture/capsule/transform/entity/triangle/displacement and explicit
  cached/recovery/portal motion, plus P560 clock/live/rate/render gates stay open.
- **Independent authored triangle/slab SAT (tooling only).**
  `offramp_triangle.py` compares the retained triangle/removal standing-AABB
  queries to a complete geometric prism/box SAT sweep interval. Include all
  prism-face/box-face/edge-cross-axis projections and the four-unit BACK slab;
  face/axial tests alone ACT a false positive at an oblique back corner. The
  solver uses authored vertices, not native fractions/planes. Native collision
  bias is 1/32 along the independently derived entry normal, not a universal
  fraction tolerance. Native misses have entnum -1, zero plane/contents; guessing
  0 broke the first controls. Triangle hit ticks are 0..13, not another fixture's
  0..22. Inactive removed geometry may overlap while native removal still misses;
  that is explicitly hypothetical, not an actual embedded body. Mirroring a
  wrong fraction into all arms preserves parity but the SAT check refuses it.
  Query agreement does NOT prove native axial/broadphase semantics equal the
  ideal full slab everywhere, copied accepted geometry, physical exits or marks.
  `world-triangle-unresolved` and support ABSTAIN remain unchanged; no new native
  build/runtime actor or product/deployment claim belongs to this reader work.
- **Winning triangle fixed-copy seam (tooling only).** `offramp_tricopy_smoke.py`
  adds a separate private value payload to the origin, not trace/model/plugin
  ABI: actual three indexes/xyz at the winning leaf, native winning plane tag,
  applied bevel flag and source-guarded four-unit back slab. No pointer survives
  into the buffer. Probe/source mutation, same-kind competition, nested/physent
  ownership and brush/unknown clearing ACT in native setup. Triangle equal
  fractions REPLACE (`enterfrac <= truefraction`), not first-wins; the first test
  got this wrong and its failed rig remains. Preserve invalid-source zeros, not
  partial geometry; copied native dereferences are NOT pointer/index bounds
  validation because the native leaf supplies no vertex-array length. The
  existing motion reader still ignores/abstains on triangle geometry; mirrored
  bad copied vertices keep old parity but fail the new binding check. All fourteen
  direct standing-world contacts independently agree with copied-prism SAT and
  max(0, geometric entry - 1/32/closing speed); clamp matters, tolerance is spatial.
  Native axial/broadphase/back/corner/bevel semantics are NOT globally equivalent
  to ideal SAT. General support stays ABSTAIN, original twenty cases/winners exact.
  Setup point/capsule/translated/hybrid/portal examples prove copy metadata and
  refusal/clearing, NOT unsupported mover trajectories. Installer failure must
  be atomic; sentinels/owned dirty fixture restore byte-exact. Build diagnostics
  compare absolute-root-normalized messages, not guessed old checkout names or
  warning totals alone. A logging-heavy five-arm batch outgrew 180s outer timeout:
  retain partial rig/unknown exit, use fresh rigs and adequate timeout; do not
  fabricate completion/exit metadata from a completed-looking log.
- **Full native triangle back slab is NOT the ideal prism (tooling only).**
  `offramp_trislab` ACTS full BIH queries on one horizontal identity triangle
  with a small AABB and explicit removal/solid/front controls. Native shaped
  axial planes use original triangle xyz extents, not extruded slab bounds:
  back sweep enters FOUR units later than ideal SAT, and short-back/stationary
  slab queries miss despite ideal intersection. Stationary alone cannot separate
  broadphase from axial exclusion. Front agreement and copied winning xyz do
  not generalize this away. Never reinterpret native miss as ideal-prism clear
  or hypothetical removed geometry as actual support. Setup-only queries restore
  before the unchanged twenty-case mover; old motion/copy results remain exact.
  Nine tests (three actual-native) and10,440 ACTED refusals bind inputs/results;
  mirrored new fraction faults preserve old parity then refuse. General support
  stays ABSTAIN; no engine collision/marker fix or deployment. Corpus subset
  drivers must retain/report non-file glob matches (including directories named
  run.rec), never delete player fixtures or call skipped candidates full coverage.
- **Bounded copied front-edge/bevel queries (tooling only).** `offramp_tribev`
  restores a separate setup-only full BIH fixture before the unchanged mover.
  One oblique identity triangle/small AABB ACTS a tag5 bevel winner: independent
  SAT over COPIED winning xyz gives entry1/2 and 1/32 normal-distance bias.
  Bevel-OFF instead wins in-plane tag2 at1/4 and reports a stationary false solid
  where complete SAT and independent joint feasibility prove separation. Face,
  occupied, outside, removed and repeated controls ACT; solid/miss copies remain
  empty. Original axial bounds admit these front contacts; this bounded agreement
  does NOT undo the measured back-slab NON-equivalence. Thirty queries/setup,
  ten tests (four actual-native) and24,360 ACTED numeric refusals bind full queries
  and return-bound copies. Mirrored new fraction/xyz faults preserve old mover/
  copy/slab parity then refuse. This is NOT a new bevel-winning PM trajectory,
  authenticated support, physical exit, marker/classifier fix or deployment.
  General corner/tie/transform/capsule/entity/topology/recovery/portal remains open.

## Rewind (Patch 477)

### Practice labels and save-owned noclip reason — P718

Ordinary save loads replace the abandoned attempt's noclip/settings latch with
`cheat` from the saved state plus the CURRENT `SV_CheatLevel`; apply it to run
and stage. Do not OR the old live latch back into clean saved flags. Running
loads still add segmentation/shadow and retain recorder restoration/failure
rules. Retry, hopped-start forgiveness and active-mode watching are unchanged.
The historical RC_CHEAT/TF_CHEAT/SF_CHEAT and `cheat` filename remain evidence/
compatibility reasons, not a separate player-facing Cheated category: shared
names, timer/stage marks, banners/chat and the local Practice chip say Practice.
When aliasing colours, audit comparison callers too: `Bn_ChatCol`'s old red
TC_CHEAT comparison caught amber Practice until removed. Filter controls must
contain classified rows, not just test that the selected chip changed. P718's
six header-only browser fixtures include bare practice and an unflagged legacy
reason; they are NOT verifier/playback evidence. See tools/p718_runtags.md.


P682's warm-go preparation is inert. See `tools/p682rewindprep.md` for supported
current-recording/same-generation pin and all explicit unavailable branches.
Shared `SV_RewindSelectRead` is bounded and effect-free; `SV_RewindFind` still
publishes globals. This selector uses a +/- half-second SPATIAL window, then
tick-distance/newest ties, or latest-past without near. It never clamps to the
ring head. The predecessor handoff audit's Peek/Alloc/count names were not in
source; reread the real function before planning a test from that audit.

Four-decimal row write/read normalization is movement policy even on a warm
rewind prefix. Rewind pitch is not the start-save reset clamp. Successful go
ends held (NONE, zero live velocity) with normalized sample release velocity;
READY describes only that body policy, not file/copy/attachment success, a
reserved save ID/sequence, a future epoch or prediction permission. Pure-save,
cold/ended/forked attachment, full-list and prior-go replacement abstain. No
production consumer, native admission, baseline reconciliation or Build bump.

The dedicated cfg must run the real go fixture DURING the walked recording.
A three-second walk plus waits on surf_dune fell back into the start and rearmed;
that failed prerequisite was not a movement result. Invoke at about 1.1 seconds
without an extra post-walk wait. A copied player edict used as test snapshot
must have a non-player classname: otherwise `SV_RewindAlone` correctly sees the
snapshot as a second connected player and withholds the replaceable go ID.
P682 retains both failed rigs and grades only a complete real recorder/pin/
write/read/load/hold/release actor. Independent review found a missed rate
boundary despite initial 91/0: sl_saveat go pays the general sl_* charge AND
a second go charge in the same dispatcher call. Pre-dispatch preparation must
require TWO tokens without spending either, not one. One-token and just-below-
two actors leave the real pin/body/list unchanged; exactly-two goes through
real write/read/load/hold. Corrected subject 98/0; old one-token gate mutant
4/98, spatial 7/98 and held-velocity 2/98 named expected assertion failures.
QC pointer declarations need separate statements (`local float *a; local float
*b;`), not `local float *a, *b;`: fteqcc treats the latter second declarator as a
pointer-to-pointer. `lobby_enable` is a cvar, not a QC global; test with cvar_set.
P682 publication/deployment: `tools/p682deployment.md`. A concurrent published
release-tooling commit was integrated in a separate clean source tree; unchanged
QC/fixture inputs and byte-identical3 VMs proved review provenance. The standard
empty12-lobby guard and program-only swap/restarts ACTED; dual Windows and fleet
destination/.prev hashes, unchanged native/config/data guards and two fresh-cache
served-CSQC board smokes ACTED. SSH lacks journal visibility: do not grade that
probe as a clean journal. Screenshots show the board but known missing-map
material behind it; not map completeness or native/prediction acceptance.


- **Request/native captions (P560).** Fractional display, sampled wire request
  and acknowledged native clock are separate. `Rewind_ResumeInfo` states the
  sampled request while browsing, waiting while pending, and native/request/
  signed delta while counting. Native caption requires correlated SLTRAILTAG
  plus valid SAVETICKS/rate; untimed practice and missing/foreign metadata never
  invent a clock. State clears/gets gated across reset/open/close. Context goes
  below key legend (.84), not on the speed/e-line (.735 initially overlapped in
  inspected pixels). Countdown caption .46; actual held main HUD is untouched.
  `stitched_rewind_smoke.py --presentation --selection-audit --visual` records
  forwarded ACTUAL draw text and timer-panel output in private overlays; nine
  compiled metadata/presentation units and five REAL SV_RewindFind repeated-
  position/window/tie cases restore the player's private test ring. Four six-cut
  warm/fresh-cold arms at caps 30/100/300 and both clients pass independent native/
  body/hold/release/ack/prefix/camera/UI gates with explicit 120ms delay; unchanged
  requested-clock test stays RED on three/four cuts. Presentation is not general
  alignment. Twenty-five UI counterfactuals, prior HUD21/12, navigation/focus/
  opposition and reader 306/0 pass. Production screenshot/status/timer control
  passes; PNG IHDR verifies 1920x1111 (video request is not size proof).
  QC pointer locals must be separate declarations: combined `*old, *m` produced
  a double-pointer cast warning/error in the private test. Initial seam/compile
  failures did not ACT. With delay/screenshots, 500ms initial save wait left go
  legitimately blocked; allow 1600ms and prove pending/hold. Inserting screenshots
  inside fixed six-cut hold/log windows misplaced late cmd-timer replies at
  high caps; run images separately, never remove body/frozen/clock assertions.
  Countdown number changes during hold; compare fixed NATIVE caption, not the
  whole draw string. Low-resolution/custom HUD and actual-device/untimed camera
  feel remain human gates. No evidence, selection, camera or engine/Build change.
  Frozen 8994b59 rebuilt clean/zero warnings and deployed to both Windows installs
  and empty-gated twelve-lobby fleet, P554 retained .prev. SSQC/menu/config/engine
  and owner source/index/personal cfg unchanged. Non-instrumented request/pending/
  native/delta/main-timer/close controls pass on both clients and live lobby 1;
  production screenshots inspected. Destination/previous hashes and twelve active
  services verified; final health OK/twelve empty rows 2026-10-08 01:46:48 UTC.
  Original game push raced a peer ROADMAP-only plan: inspect/rebase unpublished
  commit, no force; source/progs remained identical. First post-probe health
  assertion did not pass and its response was not retained; later explicit saved
  readbacks passed. Do not invent a cause from that missing first snapshot.

- **Focus cancels activity, not ownership (Patch 554).** `rw_kactive` is separate
  from down/taken identity. Chat/menu/modal cursor and effective console cursor
  cancel browsing holds; IE_FOCUS cancels only keyboard=0, not unchanged -1 or
  mouse-only loss. Return/repeats and releasing an opposing cancelled owner do
  not restart; a released fresh press ACTS. Taken repeats/up remain owned after
  close/rebind. `notmenu` excludes menu/cwindows but NOT the main console;
  existing checked `getcursormode(TRUE)` supplies its effective cursor. No new
  engine hook. Pending-go/countdown and native save/resume/body/evidence gates
  are unchanged. Extended `rewind_navigation_smoke.py` passes at 30/100/300
  and both installed clients, unchanged baseline ACTS/fails chat cancellation,
  47 grader controls pass. Existing HUD 21/12 controls and reader 306/0 pass;
  screenshot inspected. These are synthetic chain events, not real OS/device
  delivery or human feel. Private regression launch initially lacked an output
  directory; create it and rerun, do not call an unlaunched arm a pass. Grader
  mutation initially expected echoed cfg text in a timestamped log; target the
  final event instead. Compiler/VM logs, probes and failures remain private.
  Production source `e1c556e`, rebuilt clean/zero warnings, deployed to both
  Windows installs and empty-gated twelve-lobby fleet; `.prev` retains P550.
  Non-instrumented whole-chain focus/cancel/return/fresh/pin/body/clock controls
  pass with both installed clients and live lobby 1. SSQC/menu, default cfg,
  engine and owner source/index/personal cfg unchanged. Final destination hashes,
  all twelve active services, twelve empty heartbeat rows and health OK verified
  2026-10-07 23:49:14 UTC. Actual-device acceptance remains in lextest.md.

- **Opposing live-rewind holds cancel (Patch 550).** Direction is presence of
  owned right minus presence of owned left, not the newest held key. Refresh on
  press/release and every browsing frame; reset acceleration only on an effective
  direction change. Preserve physical ownership through repeats/rebinds and
  pre-open presses. Native cursor/save/resume and pinned movement are unchanged.
  `rewind_navigation_smoke.py` drives full-chain controls over a real dedicated
  socket at 30/100/300 FPS and with both installed clients. The unchanged source
  ACTS and fails cancellation; 28 grader controls reject missing/duplicate/NaN,
  unacted, stuck-release, body/clock/native-selection and pending-HUD mutations.
  Start its cursor at 2 s: the live line has fewer indices at 30 FPS, so the
  original 1 s acceleration control reached its lower bound, invalidating that
  arm. Native probe agreement is with the existing lower selected sample, NOT
  proof of low-FPS requested/native snapshot alignment. Delivered releases behind
  chat/console/menu pass; opening chat/menu without release still scrolls on the
  P550 baseline; P554 closes that focus-cancellation defect. Synthetic
  chain events are not actual-device/OS-focus or camera-feel acceptance.
  Production from exact `41410d8` built with zero warnings; both Windows installs
  and all 12 empty-gated Pi lobbies carry CSQC SHA-256
  `676ca48a7b5d5bf26f76fe0620d50e80c30c248310758b368283841666615f2a`.
  SSQC remains `76f4a7bf...`; menu/configs/engine are unchanged, `.prev` kept.
  Both local production clients and live lobby 1 pass non-instrumented
  cancel/release/pin/body/clock controls; fleet hashes/default cfg and all active
  services rechecked 2026-10-07 22:09:02 UTC. No instrumented program deployed.

- 2026-10-07 repeated-cut control `tools/stitched_rewind_smoke.py`: private
  dump seam plus real dedicated recorder, fresh second client, no fixture or
  install saves touched. Three warm cuts pass after counted 5–6 second waits:
  cut head replaces future, raw hold counts/rows stay equal, release grows the
  retained prefix. Cold persisted picture equals save001. Cold cuts at
  2.0/1.5/1.0 (all after the load) remain RED on two/three: later server sample,
  then refusal. Do not loosen the oracle or call warm success an idle-tail fix.
  State files show cold snapshots lack `recrid`; SV_RecGenOK refuses warm,
  SV_RecRewindStream makes another serial, SV_RewindRebase drops old snapshots.
  BACKLOG carries the boundary; never fix it by passing client geometry as
  authority or merely trimming to its requested clock. Initial test also
  requested pre-load times and must not be cited as newly recorded history;
  corrected after reading the bounded state-ring contract. Harness first used
  two unregistered bare cvars before spawn: repaired to `set`, full rerun had
  zero command/VM errors and zero compiler warnings. Strict retained grader
  exposes the two cold failures, not an all-green claim. Run with private
  `--output-dir`; test-only programs must NEVER ship.
  P539 repairs this specific cold attachment boundary without adopting a saved
  run ID/nonce: fresh local `recbranch` at open/cold/session attach; both save
  writers emit it; warm cuts compare it plus serial/run ID/generation floors.
  Legacy saves retain the nonempty run-ID gate. Streamed and buffered six-cut
  controls now pass, including native body/ticks at the selected snapshot,
  counted failed waits, hold/release and 17 compiled refusal/reset controls.
  Grader counterfactuals: 19 streamed / 18 buffered pass. P502 main/edges and
  its nine grader controls pass in both recorder modes. Reader 306/0; read-only
  corpus remains 269 recordings / 164 recording faults and 91 views / 6 view
  faults, with byte-identical before/after reports. The first candidate omitted the
  separate SV_RewindWriteState writer and correctly remained red. A diagnostic
  seam initially used nonexistent fields (fteqcc crashed without output); fix
  the probe, not product code. `p502segments --content` is needed in source-only
  worktrees: a missing map proves no gameplay. Broader visual acceptance remains
  open; these probes do not judge rendered labels or camera feel. Independent
  review caught a vacuous `zip` native-body oracle: empty/truncated vectors
  could pass. Enforce complete unique finite native fields and keep eight
  malformed-field counterfactuals. Old parser accepts the acted empty-body
  negative; corrected parser rejects it and all other malformed arms. Initial
  draft corpus counts were incorrect; inspect the complete report, not line
  counts or a recalled summary, before publishing a count.
  P539 production progs from inspected `8f87209` reached both Windows installs
  and all 12 Pi lobbies on 2026-10-07 (completed controls 07:49:48 UTC). Pi
  occupancy gate found a current row for every unit, all zero; no force. Hashes
  agree and ordinary `.prev` pairs remain. Engine/plugins/menu, owner configs
  and the second install's Quakers mod were not changed. Independent source
  reviews and the bounded oracle recheck found no residual code blocker.
  Two fresh private clients cold-downloaded matching CSQC, received real peer
  streams and reached the settings/imported/native UI without command/VM/shader
  errors. Native screenshot inspection shows the terms-unaccepted gate and a
  missing-map-material warning: no board-row fetch, complete map appearance or
  rendered camera/path acceptance is claimed. Isolated native cut controls,
  not these compatibility screenshots, establish the recorder fix.
- **Current requested/native selection audit (2026-10-08, tooling only).** Do
  not group historical ticks 49/103 as two still-broken boundaries: P542 closes
  tick49's raw serialization loss; tick103's forward selection was separate.
  Fresh P554-source six-cut controls pass at caps 30/100/300, streamed/buffered
  at 30 and with the second installed client. All thirty local selections match
  independently enumerated native rings, correlated acknowledgements and exact
  acknowledged raw prefixes; measured requested/native offsets are -15..+30ms,
  not universal clock equivalence. Second-client 0.735/request/native/raw agrees.
  An explicitly configured/read-back 30ms packet-delay arm retains strict red
  requested-clock results on three warm cuts (+60/+60/+45ms), while all six
  native/body/hold/release/counting/prefix and camera/discontinuity gates pass.
  Nearest-clock-only candidates have worse position matches; do not force time
  selection or retime evidence to satisfy the display oracle. Alignment/UX and
  human feel remain open. The original .031s clock check is unchanged.
  `stitched_rewind_smoke.py --client` selects both warm/fresh cold executables.
  Requested-clock failure no longer skips per-cut native/body checks or camera
  diagnostics, remains a nonzero result and is not mislabeled as only cold.
  An acted pre-fix combined clock/body negative hid native corruption behind the
  clock failure; the strengthened grader independently rejects it. Grader
  controls: native-selection19, streamed cuts21, buffered cuts20, visual16;
  selection/visual counterfactuals also pass on the strict-red latency captures.
  Compiler zero warnings; reader306/0; no product/format/clock/engine/Build bump,
  new numbered patch or deployment. Private logs/captures stay private. Initial
  second-client launch used an unsupported flag and did not ACT; the added
  explicit pass-through then ACTED. Final logs append warm+cold cvar readbacks:
  expect one in the warm snapshot and two in the combined log, not one overall.
- P542: `Trail_RawSample` serializes clocks at six decimals. Native tick 49
  at 0.015 produces cutoff 0.734999955, but decoding its 0.735 row produces
  0.735000014. An exact unrounded comparison dropped a whole rendered sample
  (45 ms at 30 FPS), despite the request/native/ack clocks agreeing. The old
  retained native probes establish tick 49 for the 0.735 -> 0.690 failure;
  the other 1.500 -> 1.545 failure held native tick 103 and is separate.
  `Trail_RawClock` puts trim/save/load cutoffs through the SAME six-decimal
  formatter/parser once per operation. No new sample, FPS epsilon, native
  selection, evidence/save-state clock or format change. It also preserves
  negative/untimed cutoff behavior. New `--selection-audit` captures the entire
  native ring, wire request, sampled cursor and correlated go acknowledgement;
  independent distance/tick ordering and full raw-prefix comparisons ACT on
  all six cuts. All strict existing checks plus six compiled clock controls
  pass buffered at 30/100/300 and streamed at 30; 19 audit counterfactuals reject
  wrong/missing/nonfinite selection, request, ack and raw rows. Visual 30-FPS
  scans pass 5,646 buffered / 5,574 streamed samples and all nine compiled
  presentation controls. Baseline 30-FPS still loses a 2.025 boundary to 1.980
  and fails compiled clock normalization; do not weaken either grader.
  Production P502 main/edges pass both modes, native negatives 18/19 and visual
  negatives 16 pass; reader 306/0. Captured 269-file recording corpus: unchanged
  baseline/candidate findings, 164 files with faults. No evidence-reader change.
  An initial edit used an undeclared `endt` in `Trail_Trim`, causing fteqcc to
  exit without diagnostics; fixed the variable, not the compiler or peer code.
  New diagnostics are PRIVATE programs: never deploy probe commands/raw output.
  General requested/native clock UX, real teleport/contact truth and human
  moving-camera feel remain unverified. Engine commit/tag and qcbuild unchanged.
  Frozen published source `72e7884` production pair installed to both Windows
  trees at 2026-10-07 11:28:21 UTC, keeping ordinary `.prev`. CSQC SHA256
  `ac19e6df987d33393b6c1e526f0ab3d7256d9754fa27e49f47c6741efc36e22b`;
  SSQC remains `e56b81df...`. No private diagnostic markers in production.
  Installed dedicated P502 main/edges ACT/pass using FTESurf's client and
  FTEQuake's actual `fteqw64.exe`; finish verified 11:34:44 UTC. The initial
  FTEQuake arm used absent `ftesurf64.exe` (WinError 2 before client action):
  recheck destination hashes and finish only with the actual executable, do
  not recopy the progs. Protected native/plugin/menu/personal/default config
  and Quakers hashes stayed unchanged.
  Pi deployment is PENDING: normal `-Pi` occupancy gate found one player in
  lobby 1 and refused before copies/restarts; no force. Independent read at
  11:32:04 UTC found predecessor `e7e519c3...` CSQC and all 12 units active.
  A later directory read still had 12 current rows and the same occupied port.
  Retry the frozen production build normally when empty, then verify remote
  hashes, every unit and fresh-cache live behavior. Do not claim fleet delivery
  or drop the connected player to finish this deployment.
  Fleet retry completed 2026-10-07 at 12:10:46 UTC, from the SAME clean frozen
  `72e7884` source. Normal occupancy guard found all 12 current rows empty;
  no force. Zero-warning production rebuild matches the Windows pair. All
  12 exact units independently active; remote CSQC is `ac19e6df...`, previous
  CSQC is P540 `e7e519c3...`, SSQC remains `e56b81df...`. Default cfg unchanged;
  ordinary `.prev` retained. Two fresh-cache installed clients downloaded exact
  matching CSQC, received acted peer streams and reached the settings/imported/
  native UI without command/VM/shader errors. Inspected native screenshot still
  shows unaccepted terms and the known missing-map material: compatibility, not
  board-row fetch, map completeness or moving-camera acceptance. No second
  restart during finish controls. Windows production/protected native/plugin/
  menu/personal/default cfg and Quakers hashes stayed unchanged. Directory had
  all 12 rows and zero players afterward. P542 fleet delivery is now complete.
- Native event/stop controls (tooling after P542):
  `python tools/native_trail_events.py --output-dir <private dir> --fps 30`
  (also 100/300) walks out of start on a real dedicated socket, then engine
  touches private AABB volumes using the ordinary `trigger_teleport_touch`.
  Keep/zero velocity and view-snap modes ACT, with exact native before/after
  destination, body, velocity and unchanged tick checks. Land on the map's
  actual floor: an unnetworked synthetic slab does NOT provide matching client
  prediction collision. A six-second running stop advances counted ticks and
  raw time without body/velocity drift; a fixed cursor over 1.5 wall seconds
  preserves clock, body, velocity and raw rows while the native pin freezes.
  Complete quarter-point scans at 30/100/300, nine compiled controls and distinct
  first-person/chase view-state probes pass. The initial screenshots aliased:
  PNG encoding consumed the waitms interval without drawing the changed camera.
  Follow-up uses frame barriers and captures VF_ORIGIN/VF_ANGLES immediately
  before renderscene, not from a console command outside CSQC_UpdateView.
  First/chase/return at 30/100/300 changes 40.2% of a world-only image patch,
  then restores it (0.0% changed). Screenshots were inspected. This is bounded
  renderer/synthetic-volume/native-handler coverage, NOT authored BSP teleport
  or human camera-feel acceptance.
  `python tools/test_native_trail_events.py --rig <private rig> --output-dir
  <private dir>` rejects 43 malformed/missing/unacted/wrong-state/body/clock/
  mode/raw-break/camera cases, including aliased images, wrong return pixels and
  missing/wrong return camera probes; positive first. Existing visual grader's 16
  controls still pass. Its angular oracle now accounts for the SAME independently
  derived six-decimal time bound as velocity: `abs(short_arc)*2e-6/dt`, not a
  tolerance chosen from a failing difference. One native trace exposed a
  90-degree turn over serialized 9.960000..9.974999 seconds: midpoint -135 was
  correct but a fixed .003-degree oracle rejected its .0030002 text-rounding
  difference. Discontinuities retain the strict bound; wrong-view falsifiers
  still reject. No product/evidence format change or new product patch.
  Native instant poses and sampled visual endpoints are different contracts:
  keep-velocity native-to-first-raw-break offsets vary across runs/FPS. Bracket
  each acted touch with raw pre/post dumps, retain exact native tests and report
  the offset; don't silently retime history or claim instant-pose equivalence.
- P540: raw trail break/stitch columns (8/9), not only legacy flag
  `0x4000000`, gate `Trail_VisualState` interpolation. `Rewind_Camera` bounds
  its +/-3-point tangent to the cursor's continuous span. Compiled positives
  for continuous/short-yaw/sampled-save/raw-break/raw-stitch/legacy-break/
  position-break and both sides of a chase break: baseline fails four, subject
  passes all nine. `stitched_rewind_smoke --visual` adds private quarter-point
  first-person/chase traces, restored after scanning; never ship the probe
  programs. Six-cut native body/clock/prefix/refusal controls pass streamed and
  buffered at 100 FPS and streamed at 300 FPS (12,006 / 12,110 / 12,142 traced
  cursor samples respectively). Genuine 5-second running stops stay counted.
  Visual-only 30-FPS buffered traces pass (5,626 samples), but the full oracle
  stays red: 0.735 requested -> 0.690 retained, 1.500 -> 1.545. Both failures
  reproduce exactly with `--baseline` (HEAD client code, before this commit).
  Do not call the low-FPS full matrix green or silently broaden its tolerances.
  All 17 lineage guards, 19/18 native grader counterfactuals, 16 visual grader
  controls and P502 main/edges pass; reader 306/0. No evidence writer/reader,
  server selection, save clock, engine pin/tag or qcbuild change.
  Probe compile failures were a vector component on a call result and a missing
  forward declaration, not product defects. Initial hold probe preceded load
  acknowledgement: allow 1.2 s before hold1, still inside the 3 s hold. At
  30 FPS use .9/.7/.5 warm cuts to retain the existing >10-sample coverage floor;
  changing that floor would conceal the first low-FPS fixture failure. Printed
  six-decimal time needs a velocity tolerance derived from dt/velocity slope,
  not arbitrary smoothing. Empty/truncated/nonfinite/missing-quarter and pose/
  view/camera/index mutations all reject; raw angles are independently derived.
  Numeric geometry is not screenshots, camera feel or full contact/teleport
  truth. Those human/broader cases and low-FPS alignment remain open.
  P540 frozen production `996462b` deployed to both Windows installs and all
  12 Pi lobbies; compatibility gates finished 2026-10-07 08:44:27 UTC. CSQC
  SHA256 `e7e519c38707aca332ff8eff8ad7ff44282187a7404c320f43b13a56aecac32f`;
  SSQC stays `e56b81df...`, predecessor CSQC `8b3811fb...` retained as `.prev`.
  Clean frozen builds match the production P502 subject byte-for-byte and
  contain no probe commands. Pi occupancy gate: all 12 current rows empty,
  no force; independent hash/status read: all active. Windows native/plugin/
  menu/personal/default cfg and Quakers hashes unchanged. Two fresh-cache
  installed clients downloaded matching bytes and received acted peer streams;
  no command/VM/shader errors. Inspected settings/native screenshots still
  show the unaccepted-terms gate and known missing-map material: compatibility,
  not row-fetch, map appearance or camera-feel acceptance. No extra restart
  during finish-only controls. Peer source/index edits remain untouched.
- P533/P535/P536/P537 final frozen product `2b7cced` deployment verified
  2026-10-07 at 06:07:21 UTC. Both Windows installs and Pi have CSQC SHA256
  `541accec08be6396d4e711947c8092a641183c97c0242a7661913fd74851e66a`;
  immediate `.prev` is P536 `9120d5ac...`. Clean product has no test hooks.
  Windows SSQC/menu/native and owner configs/data unchanged; Pi coherent pair
  preserves SSQC `951acd41...`. Default.cfg `8fd357ac...` changes only the reveal
  comment relative to P532, with original config backups retained. No engine
  pin/tag, qcbuild or server-rule changes. All 12 were empty for deployment;
  verification finished separately without another swap/restart. Fresh-cache
  clients on both installed engines downloaded those bytes, received peer body
  streams, and drew the eleven-row settings plus separate imported/native tabs
  without Compare. Terms deliberately unaccepted: UI/scope and stream controls,
  not remote row-fetch/permission or all-backend acceptance. Actual map was
  surf_kitsune with its known unresolved material; not repaired by this batch.
  The final 21-unit/12-dedicated-phase P537 layout regression and inspected
  screenshot remain the cursor/input proof, not these idle live clients.
- Patch 537: final production screenshot caught the old REWIND heading
  overlapping P535's timer caption. Hide that heading while the main cursor
  snapshot is active; footer carries explicit mode. Controls at 0.80 and implicit
  resume context at 0.76 avoid default speed/chat rows. Pending-go/countdown
  heading/guards stay unchanged. Full 21/12 controls rerun, new screenshot
  inspected; this is default-layout evidence, not every custom HUD layout.
- Patch 535: ui_rw_* is a presentation-only snapshot, published after camera
  setup and consumed by the existing main timer/speed/energy panels. Fractional
  rw_visualt/p and tr_vis_* never serialize a save: tr_cur_t/p, raw selected
  velocity/angles and prefix bound remain at the same floor sample as before.
  Duplicate clocks keep the last sample; position/velocity do not blend through
  breaks. The timer says display-only; `e line` is relative to the first line
  sample's total energy (not the current live/manual/jump anchor). Missing raw
  velocity displays unavailable, not a fabricated zero. Live physics/board
  derivatives and unsupported ramp/trainer panels stay out of the cursor path.
  Entry/exit force the readout latch; pending-go/countdown use normal live HUD.
- Bound bare +moveleft/+moveright commands now scrub live rewind, not assumed
  A/D. Up to 16 simultaneously held physical bind identities track separately;
  released slots recycle. Held-before-open keys are not adopted; repeats do not
  step again; release/rebind/focus identity and overlapping-direction fallback
  retain ownership. Movement during pending-go/countdown follows the preexisting
  release-gate policy, not queued navigation. Compound binds and demo parity are
  not claimed. This is not the full P477 27-round matrix or a stitched-idle fix.
- `tools/rewind_hud_smoke.py` uses private test-only seams and a real dedicated
  socket: 21 sample-vs-visual/unknown/ownership assertions and 12 acted HUD/input
  phases, including native viewpos proving a stationary pinned body. Actual main
  HUD/camera and post-resume screenshots inspected. Initial seam needed a later
  Rewind_Reset prototype; the first grader expected `origin:` rather than the
  actual viewpos `setpos` output. Both repaired and controls rerun. First product
  compile caught a nonexistent tr_track and wrong Interp_Arc arity, corrected
  using the existing stat and Interp_View before any product publication.
- P533 tail-batch correction: TR_BUILD is 16, so a live tail can have 15 pending
  points, not three. The implementation already handles it; extended pixel/emit
  controls now prove the full 15-point tail. 37 alpha assertions, 52 screenshots.
  Long-sweep opaque body had five one-channel 1/255 differences; the endpoint
  now uses the same <=1 RGB tolerance as survivor checks, retaining exact coverage
  masks. Original images regraded explicitly, not silently relabeled/relaunched.
  306 recorder-reader checks pass; unchanged checker/corpus hashes retain the
  existing 269 REC observation (164 REC faults plus six of 91 paired VIEW faults).

- P544 demo navigation: `Watch_Track` runs before every input handler/release
  gate. Up/repeat identity is physical, not a re-read bind; pre-open/chat-owned
  repeats cannot acquire the viewer. Bounded 16-key table; bare +moveleft/right
  only (primary mouse buttons remain chrome's). Tap seeks one recording tick;
  held rate is 0.45..9 run seconds/wall second over 2 seconds, opposing directions
  cancel, same-direction keys remain independent. `Watch_Seek` retains all cache
  invalidation/window clamps. Close/open/Space cancel active scrub, but taken
  repeats/up remain swallowed through close/rebind. Menu/chat cursor focus and
  IE_FOCUS loss cancel active scrub; console releases are observed ahead of its
  draft/other handlers. Compound/modifier binds and actual OS/device focus are
  not covered by the synthetic input arm; P550 later adds live opposing-key
  cancellation and P554 adds live focus cancellation.
  `tools/watch_navigation_smoke.py --output-dir <private dir>
  [--baseline <pre-patch ref>]`
  creates an isolated test-only overlay and real dedicated socket. 35 cursor
  probes/55 CSQC_InputEvent events pass at 30/100/300, replay position/velocity
  match the synthetic straight-line cursor and native pinned body stays exact.
  Unchanged baseline ACTS but fails held-scroll oracle. The grader's 31 controls
  reject unacted/missing/wrong ownership/time/pose/body/focus probes. Initial
  harness used absent menu_main; togglemenu repaired both arms. Coordinate
  oracle allows .03u for float32 interpolation at <=14500u world coordinates,
  independent of ownership/time stop equality. 306 recorder-reader tests pass;
  unchanged checker over 269 real REC files retains 170 existing paired faults.
  This is navigation assurance, not evidence retiming, imported-camera or human
  smoothness acceptance. Engine pin/tag/qcbuild stay unchanged.

- P549 fractional demo clock: `Watch_ClockTicks` is presentation-only. The
  main timer and full-demo chrome use visual seconds / recorded tickrate,
  bounded to zero/recorded finish; sampled `rec_wt_ticks` still own events,
  splits and state. Live rewind and stage-cut chrome remain unchanged.
  `tools/watch_clock_smoke.py --output-dir <private dir> [--baseline <ref>]`
  probes actual formatted draw text and panel arguments through a private
  dedicated overlay: 33 acted native/foreign/legacy positions, paused holds,
  forward/backward/sub-tick seeks, stationary spans and lead-in/finish bounds.
  Native server body stays exact. Unchanged baseline ACTS but fails the
  fractional-input oracle. Retained screenshots show matching panel/chrome.
  `--rig <retained rig>` runs the strict grader and 20 counterfactual rejections.
  Foreign/legacy fixtures are reader controls, not import-codec/unknown-velocity
  acceptance; broader HUD/camera continuity, long demos and human feel remain
  separate. All three progs compile at zero warnings; 306 reader checks pass.
  Unchanged checker/corpus retains 269 REC / 91 VIEW and 170 existing faults.
  Clean published product `11e32ba` deployed 2026-10-07 UTC: fleet restarts
  completed 20:18:51, both Windows installs hash-match with .prev retained and
  personal cfg preserved (including absence). Independent 20:25:57 host read:
  both progs match, all twelve lobbies active, directory back to zero players.
  Production client on lobby 1 ACTS on synthetic replay: inspected panel/chrome
  agree at 1.001s, stationary 3.205s and exact 6.000s finish. No diagnostic progs,
  server/config/engine changes or PiForce. This is clock rendering, not world
  camera/import acceptance. `runlines_smoke.py --recording` always copies to
  cfg/test/runlines_sample.rec; a generic no-error completion with 'nothing
  loaded' is NOT an acted control. Preserve failed logs and repair the cfg only.

- **The rewind rides the replay's pin, marked as its own: `rec_watch 1 rw`.** A
  pinned RUNNING run is frozen and practice, and EVERY way out of a rewind ends
  that run rather than thawing it -- a thaw past an unrecorded freeze convicts its
  angles (the held-run fault, under Anti-cheat). ENTER and ESC resume through
  `sl_saveat <ticks> x y z go` (an IDLE row). A refused resume, `rec_watch 0`
  (plain or `void`), a warp the server serves (SV_RewindWarped: AFTER the warp,
  and only if it moved the body), `retry`, a Multi-Session park and a lobby flip
  void it (SV_WatchLetGo). A replay's pin (no `rw`) keeps its run through warps
  and thaws on release, as before 477; it shares the rest -- speed and carrier
  held at zero (a `warp ... pin` on a running run), the taint only on a running
  clock.
- **The state is the server's, never the client's.** SV_RewindSample keeps 4000
  samples a slot, one every 2 run ticks, only while running and unheld; the
  client's x y z only picks among samples within 0.5 s of its tick. A run start
  wipes the ring; a warp under the rewind marks it over, so the next start does.
- **STAT_FS_PIN (111) is the rewind's open serial while its pin is held,
  `-serial` once that open's pin is refused or let go (until the next pin), 0
  before any** (`rec_watch 1 rw <serial> <state at the open>`). The client closes
  the mode on a release it did not ask for, and latches only its own serial, so
  an earlier open's pin or release in flight is never mistaken for it. The pin
  also carries the state and the run ticks the client saw at the open, and the
  server refuses to pin a run that is not that one (not RUNNING then, or fewer
  ticks now); the ask is tied to the trail line, so a new run is asked afresh.
- **A replay opened while browsing takes the pin over in the same frame**
  (Watch_Open calls Rewind_HandOver before its own `rec_watch 1`).
- **A frozen run's kept-abandon `inend` is the mover tick at the freeze**
  (`run_t_frzmt`), because the `in` rows stop there; pm_verify flies a last row
  to `inend`.
- **THE PIN OWNS THE MOVETYPE (Patch 499).** `SV_WatchHoldMove` re-imposes
  MOVETYPE_NONE from BOTH thinks -- PlayerPreThink per usercmd and ahead of the
  mover, PlayerPostThink ahead of `SV_NoclipWatch` -- because `SV_WatchHold`
  wrote it once at the press and nothing held it, so one `cmd noclip` left a
  pinned, recording run reading `class: cheated`. The pin does NOT re-place the
  body (a teleport under it is the rewind's own business); that is what the
  save-lock hold does instead, and why only the hold was immune. A resume row's
  "the next resume replaces it" pointer (`rw_goid`) now dies with its run:
  `SV_RewindReset` clears it, so a `retry` no longer lets the next ENTER's `go`
  DELETE a save from the run before it. The row stays, as an ordinary save.
- Harness: `tools/p477rewind.py` (parks data/saves/surf_dune; its last section
  changes map to surf_embrace). `vote key <scan> <0|1>` runs a key through the
  whole input chain (CSQC_InputEvent: Rewind_Track, the chat draft, the rest);
  `rewind key <scan> [up] [other]` feeds Rewind_Track and this mode's handler
  only (`other`: a press another handler took); `rewind
  status|seek|step|go|save` drive the rest.

## Map/leg tier metadata (P723/P724)

- `maps/tiers.txt` is public generated metadata, not player data. Rebuild with
  `tools/maptiers.py`; ship the asset to both installs and the Pi separately from
  `build.ps1 -Pi`'s progs. Whole-map MOM/KSF numeric ratings and the owner's
  community KSF bonus-letter sheet are distinct. Unit/Strafe letters are NOT a
  numeric conversion. Do not donate main-map tiers to a stage or strip suffixes.
- Public Momentum caches currently have bonus ratings but no non-null stage
  tiers. Synthetic stage controls prove support, not real upstream stage data.
  Skip private testing/disabled maps when generating a public asset.
- A real dedicated/headless client control found initial serverinfo omitted a
  whole-payload rating key. FTE marks values >=64 bytes OR containing semicolons
  as large info blobs (`InfoBuf_IsLarge` / `InfoBuf_NeedsEncoding`). P723 uses
  short comma-only per-leg keys and `mapratings=v1:<map>`, clears old-map keys,
  and rejects different-map markers. Do not revert to one semicolon-rich key
  merely because `forceinfokey` and server-side `serverinfo` show its bytes.
- A headless renderer does not run the ordinary view's deferred zone loading.
  `zone_reload` before `scores open` proves the real client sidebar leg table;
  merely querying a direct tier formatter with track/leg numbers does not.
  `-plugin` is needed on the Windows dedicated test process too if commands are
  sent through its owned stdin pipe. Without it, a map-change echo never acts.
- Actual CSS-only `surf_unrequited` join plus `flocate` proved the default
  `steam:Counter-Strike Source/cstrike` mount supplies `cstrike/maps` before a
  download. Exact filenames/build compatibility still apply. `fs_addons.txt`
  overrides defaults; do not overwrite an owner's mounts. Full controls/limits:
  `tools/p723tiers.md`.
- P724 visual falsifier: a `22 * rec_sb_cw` sidebar still clipped the Strafe
  half of a bonus label at1280x720. The row's mono face had shrunk to8px while
  the UI label had a12px floor. Measure every actual title/rating string in its
  drawn face/size during the existing sizing loop; use the same formatter to
  measure and draw. `scores status` now witnesses label+insets fitting sidew.
  Quiet-gated1280x720/800x600 screenshots and real UI-chain row clicks passed;
  an800x600 HUD-editor control also registered the entire extra bonus row inside
  the window. A first graphical rig's server cfg used client-only commands
  without `set` and correctly failed its unknown-command grade; corrected in
  the fixture, not hidden as a product pass.

## Imported runs: Momentum Mod and KSF

- (Patch 635 has since taken the Imported tab out: the Online list asks for
  the combined tier unless its filter is on. "The TAB board: every game by
  default".)
  Patch 536 removes the misleading imported-board Compare chip and its
  rec_sb_mixboth state. Scores_TierOf returns imported for the imported tab,
  ranked for native; no silent interleaving. Combined read API/database rules
  remain intact and this is not a live/frame comparator. Private
  tools/compare_chip_smoke.py proves both board frames actually drew, getter
  tiers differ, Compare has zero calls and imported/refresh widgets retain
  positive calls. Screenshots inspected; terms are unaccepted, so the arm proves
  UI/scope, NOT remote row fetch or new permission. The first test initialized
  its sentinel as an implicit QC constant; explicit var repaired it and rerun
  passed with zero warnings. Test-only draw counters are never shipped.
- **THE TIER IS THE MECHANISM, and it is not decoration.** A foreign run lands
  in its own `tier` (`momentum`, `ksf`), never in `ranked`. `tier` is in the
  runs primary key, so one player holds a time in each without either
  overwriting the other; and every board query filters on `tier`, so imported
  rows are invisible to the ranked board BY CONSTRUCTION rather than by each
  future query remembering to exclude them. Patch 425 already used unreadable
  tier strings as the hiding mechanism -- this is the same trick named.
  `surfd/test_momindex.py` is the arm: 130 ranked boards' rows and counts
  identical across importing 2,782 runs, against a COPY OF THE LIVE DATABASE.
- **READABLE, NOT CLAIMABLE.** `/api/board` validates against `TIERS_READ`;
  `submit_run` still validates against `TIERS`. A keyed lobby -- trusted enough
  to write `ranked` -- gets HTTP 400 for `momentum`, `ksf`, `imported` or
  `combined`. Only a local importer beside the files writes those. Keep it that
  way: the wire must never be able to name a foreign tier.
- **`imported` and `combined` are PSEUDO-TIERS: they name a query, not a class
  of run.** Nothing is stored under either. `TIERS_IMPORTED` is the one tuple
  the predicates read and `TIER_EXPAND` maps the pseudo names to it, so a third
  source is one tuple entry, not four edits. Rows on those boards carry `tr`,
  their real tier; single-tier boards do NOT send it, and the client falls back
  to the board's own tier (`Online_WhyString`, two levels, in that order).
- **The pipeline.** `.mtv` (Momentum's container) is never parsed here: its body
  is a Source entity-delta netstream with no public spec, and the wrlines
  reference does not decode it either -- it fits a chain of float32 triples with
  a dynamic program. Read its OUTPUT instead:
  `wrlines/tests/reference/wrpath_extract.py --all --jobs N --skip-existing`
  writes `.wrpath`, then `tools/momimport.py` turns those into `.rec` under
  `data/momentum/<map>/<legdir>/`, then `surfd/momindex.py` indexes them.
  **Extraction stays on Windows**: that extractor's float arithmetic is
  bit-pinned to CPython 3.13.9 (`math.dist`, a Neumaier `sum()`), and a
  last-digit disagreement does not nudge a coordinate, it SELECTS A DIFFERENT
  CHAIN through the demo. The Pi runs 3.11. `momimport` does no such arithmetic.
  Extraction is memory-hungry: 8 workers peaked ~2.2 GB and got a background job
  reaped on a 16 GB box. 3 jobs is the polite figure.
- **WHAT A .wrpath DOES NOT CONTAIN** (the "proven negatives" here came from
  grepping wrlines, which never decodes the netstream): view angles, buttons,
  ground contact. The .mtv has all three -- tools/momreplay.py decodes them, and
  since 4 Oct tools/momreimport.py writes every import from its demo (5260 of
  5281): eye angles, fl ground/duck/jump/attack, the move from the recorded
  wishVel. Still never recorded: ramp contact (bit 16, the plane). The viewer
  infers the contact since Patch 626 and says so (the run line's notes); the
  plane it does not (BACKLOG).
  **Never write a `.view` sidecar for an import**: that file is the client's
  per-frame evidence, and nothing here was recorded per frame.
- **NO `warp` RECORDS ARE SYNTHESISED**, and the grammar forbids it in terms:
  "A record synthesised by watching for a discontinuity would see the jump and
  still not know what caused it, which is the entire question." 37 % of these
  paths teleport; the reader's own kinematic test finds them and reports them as
  `kin` rather than `rec`, which is the truth about where the knowledge came
  from. `momline.cfg` A3 grades exactly that: `snaps 0 rec 22 kin`.
- **The integrity keys are OMITTED, not filled.** `mapcrc`, `zonecrc`,
  `zonerule`, `nonce`, `pmpin`, `seed` state what the machine that ran the
  physics loaded, and that machine was Source. `cl_lobbytime.qc:652-681` already
  makes this argument for a client-written `.rec`. reccheck then reports the
  file as `zones not stated` / `nonce not stated` / `ruleset unknown` in its own
  words, and `pm_verify` cannot pass one of these and should not.
- **THE DEMO NAMES THE BUILD IT WAS RECORDED ON, and it is checkable exactly.**
  A `.mtv`'s 40-hex `mapHash` is a plain SHA1 of the `.bsp` -- verified on five
  maps, and the `.wrpath` carries 39 of it at 0x74. So `momimport --maps <dir>`
  hashes the map once and compares. **877 of 7,040 extracted paths (12.5 %)
  name a build this install does not have**, concentrated in maps re-released
  under one name (`surf_simple_v1` alone has 183). Those are SKIPPED by default:
  the time is real, but a line built from their samples is placed against
  geometry the player never touched, which is wrong and looks right.
  `--other-build` imports them anyway and the header records the verdict as
  `mapbuild <sha> ok|other|nomap`.
  This is the exact form of the wider hazard: 322 of 1,062 map names shared
  between the Momentum and CS:S installs are DIFFERENT BUILDS under one name,
  and all 322 are plain-named -- the `_ksf` suffix marks the cases somebody
  disambiguated, not the cases that collide. A size comparison is a proxy; the
  SHA1 is the answer.
- **Velocity is a central difference of positions and it SPIKES AT COVERAGE
  GAPS.** 7.6 % of files exceed the demo's own `maxHorizontalSpeed` by >5 %, 44
  by over 2x; 81 % of those carry no `LOW_CONFIDENCE` flag, because that flag
  measures coverage, not velocity. The ceiling ships inside every demo, so the
  check is free: the ratio goes in the header as `momquality`. `Line_Range`'s
  mean ± 2 sd clamp keeps an outlier out of the colour ramp, so the visible cost
  is confined to the live speedometer at that instant.
- **The KSF board importer remains times-only; local playback is separate.**
  Patch 702 adds `tools/ksfconvert.py` for public CSS/66t v2/v3 binaries (not a
  Source `.dem` parser), explicit external map/course/style bindings and the
  existing imported `.rec` player. `replay_id` is still 0 on imported board rows;
  automatic board Watch/download association is not implemented.
  `surfd/ksfimport.py --from-maps` pages every board of a map -- main, stages,
  bonuses -- off KSF's JSON API (its docstring has the routes and the two traps:
  a linear map's `cp_count` counts checkpoints, and the search is a typeahead).
  `--seed`/`--from-boards` is the older player-seeded path, main track only.
  Politeness is the wrlines reference's: one at a time, 400 ms apart, capped,
  honest User-Agent, never automatic, a non-2xx reported as a refusal and
  nothing retried. Answers are cached, so a re-run costs nothing.
  `surfd/test_ksfimport.py` is the arm (no network; six mutants caught).
- **KSF playback contracts (Patch 702).** `tools/ksfplayback.md` has the exact
  console aliases/conversion commands. First frame integer is Source BUTTONS,
  not entity flags; native FSI direction keys derive from movement. Preserve raw
  masks separately. v2 `moves buttons 1` is a labelled unit-direction proxy,
  not measured analog magnitude; opposing inputs cancel, no SOCD order guessed.
  v2 ground is unavailable. v3 ground bit0 is shared by both public-viewer paths;
  bit1 conflicts (ducked/teleport), so no native ducked/warp evidence is emitted.
  `demodata` extends the old `momdemo` inference capability without certifying
  an import. Bookmark clock and official row time are separate (up to one CSS
  tick here). Main/bonus boundaries are required; no full-file/stage fallback.
  The visible title states KSF style/build unknown, info import/not verified,
  and imported hashes are never formatted as native dates. No native data filing.
  Dedicated full source-frame traces matched all twelve public clips on three
  installed maps; `p702ksf_smoke.py` also makes real-frame advancement act.
  Synchronous multi-thousand-line traces consume an enqueued `waitms` deadline;
  use `wait 60` and `replay trace frames 60` AFTER the synthetic trace instead.
  All-map harness needs a 600-second outer timeout, or invoke one map at a time.
- **A KSF time is a THIRD measurement.** CS:S physics, KSF's own zones, and
  their `mapName` is the PLAIN name (`surf_whiteout`, not `surf_whiteout_ksf`),
  so a matching name does not mean the same build, start or end.
- **THE TWO IMPORTED TIERS DO NOT CARRY THE SAME CLAIM, and that asymmetry must
  not be averaged away.** A Momentum row is build-verified exactly (the demo
  publishes the map's SHA1). Nothing on the CS:S side publishes a per-map
  digest, and the 322 divergent names are all plain-named -- which is where KSF
  records live. So `momentum` means "same build, checked" and `ksf` means
  "build unknown and unknowable". Anything that presents them as one class of
  row is overstating the second.
- **`board_fetch` asks for the map the client is ON.** `Online_Fetch` reads the
  level name; it is not a parameter. An arm that fetches a board for a different
  map without changing map first grades the wrong board and looks correct.

### In-game demo requests and graphs (Patch 545)

Momentum board rows now carry `get = rowid/demo-SHA1` from the indexed upstream
hash, not a caller-provided address. `momboards.py --all --go` backfills this
metadata after schema 11 installation; equal-time updates attach only the same
PB, never a slower cached row's hash. `POST /api/momentum/N/SHA1` validates the
current Momentum/clean row and queues it; GET only polls. At most 64 active
jobs, 10 POSTs/min/IP, TTL one day, terminal history pruned. No CDN request on
the HTTP path. The existing locked momgrab cron prioritizes these jobs inside
its six-demo budget and existing hash, size, duration, disk, map, time and retry
checks. Explicit candidates also bind the demo's player. The converter/filing
path and `/api/replay/N` remain the existing foreign-replay contract.

Client requests selected line handles before round-robin polling; closing a
board cancels watch intent, not a durable job. New picks replace old watch
intent; a cached replay must not wait behind a queued unavailable old choice.
A lost POST is retried idempotently rather than silently converted to a GET.
The nginx snippet must be installed separately from the Python deploy: the new
public GET/POST prefix is allowlisted, body-limited and rate-limited, with no
heartbeat/run-write exposure.

`cl_linegraph.qc` follows the same retained samples as displayed replay/board
lines (slots 0..8, not live trail slots 9..10). A bounded min/max envelope builds
2048 points/frame; mouse readings binary-search actual retained samples. It
aligns run/stage starts, includes vz in E, and uses recorded pmpin gravity or an
explicitly labelled g=800 assumption. E is relative to the first shown run
sample. No endpoint clamping or interpolation over teleport/stitch/large gaps.
`linegraph` takes cursor claim 64; the board's graphs button hands off after
sui_end. Legend ticks hide graph curves, not the world-line loads. Escape releases
only that cursor claim; watched-replay chrome retains its own claim. `hud_linegraph`
and `hud_linegraph_labels` control passive graphs and world-path names.

Patch 610 redrew both without touching the above. The envelope is binned over
the panel's VIEW (wheel zoom, drag pan; a closed panel is always the whole run)
into a second buffer that swaps in when complete, and what is drawn is a
simplified cache of those bins. The passive graph is the hud_edit element
`graph` (`hud_linegraph_x/_y/_plots/_size`), small, under the map info; it
gives way to the finish card and to a held TAB board. Pitfalls: "The trainer,
the run graphs and the list thumb (Patch 610)".

Falsifiers: `tools/p545graph.py --prepare`, its cfg and `--check <fresh log>`;
`tools/p545mom.py` has a localhost-only HTTP stub and its own game arm. The latter
must use a cold disposable synthetic replay id to prove body delivery; a cached
run is not that control. `surfd/test_momrequest.py` exercises the real filing,
linking and serving path with an explicitly doubled converter. Neither double
claims independent codec coverage. Synthetic UI inputs and screenshots do not
prove actual-device feel or eight long-demo performance; those remain in lextest.

Measured deployment controls: Linux `/tmp` had 5.1 GB free and NVMe had 80 GB.
The downloader's unchanged 20 GB floor stopped both queue-worker test arms in
`/tmp`; all eleven suites passed with TMPDIR and fixtures on NVMe. The deployer
now stages on the target data volume, and `-Only` restricts installation, not the
complete app/dependency archive used by tests. Do not lower the production floor
to make fixtures pass. Private game cfgs use `waitms` for startup, not a long
frame wait before any map exists. `menu_restart` reloads consent: synthetic HTTP
controls set their test-only cvar *after* it, never in a player's install.
The inspected public build.ps1's QC loop only writes this checkout's generated
progs; a successful worktree build did not update C:\FTESurf, and C:\FTEQuake's
csprogs hash remained different too. Explicitly copy the clean build's three
progs to both installs, retaining .prev/first rollback bytes, and compare hashes.
The Pi swap/restart gate did match both progs and all 12 zero-player lobbies.
Backend queue/real conversion/serving works; installing the prepared nginx prefix
needs Lex's sudo. Do not call the public HTTPS path verified before that step.

### The map roster (which BUILD, not just which name)

- **A MAP NAME DOES NOT IDENTIFY A MAP HERE.** Of the 1062 names present in both
  the Momentum and CS:S installs, **322 (30.3%) are a different file** -- and a
  run recorded against the wrong one is demoted `TF_NOMAP` silently. `surf_kitsune`
  is the worked example (`mapsync.py:47-63`). Anything reasoning about maps by
  name alone is wrong about a third of the library.
- `tools/maproster.py` is the answer to "which build": `hash` fills
  `data/maphash.txt`, `build` writes `data/maproster.txt`, `check <map>` explains
  one, `fetch` refreshes the KSF sources. 1748 surf/bhop maps, 1280 of them on a
  local mount (`have` != `-`); that is NOT the same number as what the Pi serves.
- **IT HASHES ONLY THE BUILD THE ENGINE WOULD LOAD**, resolved by reading
  `fs_addons.txt`'s mount order rather than assuming it -- 43.7 GB instead of the
  90 GB both installs hold. First run is at disk speed; after that the cache is
  keyed on (size, mtime) and a re-run is free, because **a stale cache is silent**.
- **`ftesurf/maps/` WINS THE MOUNT, ahead of Momentum and cstrike, and two of its
  four loose BSPs shadow a different upstream build.** `surf_dune` and
  `surf_fantasy` there are byte-identical to the CS:S cuts and override Momentum's,
  so every run on either is against geometry no leaderboard knows -- 45 and 5
  attestations respectively say so. This is the one gotcha a census of the two
  Steam installs cannot see, and it is why `mount_dirs()` puts the gamedir first.
- **THE PIN HAS THREE VERDICTS AND `unknown` IS PERMANENT.** `ok` matches the
  most-attested build, `alt` matches an attested build that is not that one,
  `other` means builds are attested and ours is none of them, `unknown` means
  NOTHING attests. `unknown` is 1279 of 1748 and it is not a backlog: no CS:S- or
  KSF-sourced map has a published digest anywhere. Collapsing it into `other`
  accuses most of the library on the strength of nobody having said anything.
- **WHERE ATTESTATIONS COME FROM, and the two sources disagree in LENGTH.** A
  `.mtv` demo carries the map's SHA1 as 40 UPPERCASE hex at FIXED offset 80
  (verified on 2888 demos, no exceptions). An imported `.rec`'s `mapbuild` line
  carries **39**, because a `.wrpath` stores the hash in a 40-BYTE field including
  its terminator and the last digit is lost; `momimport.py` copies that through.
  So matching is prefix-aware and a 39 is folded into the 40 it prefixes --
  without the fold every map carrying both sources reads as contested. The `.rec`
  corpus is the WIDE source (472 maps) and the demos the exact one (40).
- **`builds` IS A FLOOR AND `ev` SAYS WHY.** A count of attested builds is what
  these sources SAW, not what exists -- a wider corpus finds `surf_4am` on three
  where these find two. `ev` carries the number of attestations so a later corpus
  raising the count reads as new evidence rather than as the tool having lied.
  This is not theoretical: `surf_slobs` was reported here as a build nobody plays
  on the strength of ONE demo, and against 19 it is the most-played one.
- **THE KSF DRIVE IS PUBLIC -- no API key, no OAuth, no credential, and there
  should never be one.** `tools/ksffetch.py` mirrors what is missing. 929 maps on
  the roster sheet, 929 archives, 894 already on disk. **Enumerate with
  `embeddedfolderview?id=<id>`, NEVER `/drive/folders/<id>`**: the latter embeds
  only the first 50 entries and paginates the rest by XHR, so a scraper on it sees
  50 of 466 and looks like it worked.
- The BSP lands in the **Momentum install's `maps/`** because `mapsync.py` mirrors
  FROM there to the Pi; anywhere else is a map you can play and cannot host.
  Archives are RAR5 (7-Zip, not stdlib), hold one bare `.bsp`, and reach 335 MB
  unpacked -- stream them to disk, do not `.read()` them. Google's large-file
  interstitial returns HTML, so the magic bytes are checked before the file is
  believed.
- The roster and the KSF sheet **disagree on five names** and four of those five
  are on disk under the DRIVE's spelling (`surf_junglepics_ksf` vs
  `surf_junglespic_ksf`, `surf_not_so_zen` vs `surf_nsz_fix`, ...). Trusting
  either alone reports maps missing that are already here: that is
  `unreconciled`, and it never folds into `missing`.

### Map downloads (the button, and where the bytes actually go)

- **HTTP IS THE TRANSPORT AND THE GAME NETCHAN IS THE FALLBACK, and the engine
  already does that swap on its own.** With `sv_dlURL` set the client rewrites a
  missing map to `<url>/<gamedir>/maps/<map>.bsp` (`cl_parse.c:1002`); if that
  fetch fails it re-enqueues the same file over the netchan by itself
  (`cl_parse.c:719-724`). A broken mirror therefore costs speed, never the
  download -- do not write fallback logic, it is there.
- **THE MENU'S OWN DOWNLOADS USE A DIFFERENT URL SHAPE.** `cl_download_mapsrc`
  takes the BARE name -- `<url>/<map>.bsp`, the "maps/" prefix is stripped
  (`cl_parse.c:1020`) -- and is only consulted when `sv_dlURL` is empty, which is
  exactly the disconnected case. Both layouts must resolve or the button works
  in a lobby and not in the menu; `surfd/maps.nginx` answers both with one regex.
- **`localcmd("download …")` CANNOT DO THIS AND MUST NOT BE MADE TO.**
  `PF_localcmd` buffers at `RESTRICT_INSECURE` for every VM, so menuqc is
  indistinguishable from a server's stuffcmd and the console command takes its
  server-initiated branch: `cl_download_redirection` defaults to `2`, which
  allows only `demos/*.mvd` and `package/*.pak` and refuses a bare map. Relaxing
  that cvar is the tempting fix and the wrong one -- its own description says it
  lets a server send nearly arbitrary download commands, so it buys one button by
  weakening the client against every server it joins. Patch 465's `downloadmap`
  builtin exists for this, takes a bare name, and whitelists `[A-Za-z0-9_-]`.
- **THE PROGRESS BAR AND THE KB/s NEEDED NO ENGINE WORK.**
  `serverkey("dlstate")` returns `files-remaining total-size unknown-flag
  localname remotename percent rate received total`, and
  `PF_cl_serverkey_internal` reads `cls.download` directly rather than through a
  VM, so menuqc can ask (`pr_clcmd.c:1433-1447`).
- **THE RATE CAP IS IN NGINX, NOT IN THE GAME, and `limit_rate` CAPS ONE
  CONNECTION.** That multiplier is the trap already written into
  `nettest-dl.conf` from the day a tester pulled 6.20 GB through the Pi with
  nothing capping it. `sv_maxdrate` caps only the netchan fallback; it defaults
  to `500000`, so "is it uncapped?" has always been no -- it was half the figure
  anyone would have asked for, on the slow path only. Both are 1 MB/s now.
- **THE LIST COULD NOT SHOW A MAP YOU DO NOT HAVE**, and that, not the transport,
  is why this feature did not exist. `ui_load_maps` builds every row from
  `search_begin`, so "listed" and "installed" were one fact. `ui_dl_load` reads
  `data/mapdl.txt` and appends the rest with `ms_have "0"`. It MUST run before
  `ui_meta_load`, which builds its byname hash from `ms_name` -- the other order
  leaves every downloadable map untiered, and an untiered map and a tier-1 map
  look identical in the list.
- **`data/mapdl.txt` IS THE INTERSECTION OF THE CATALOGUE AND THE PI, not the
  catalogue.** 1748 maps are catalogued and the Pi serves 1743; offering the
  other 5 draws a button that 404s. `tools/mapscan.py` takes that intersection
  and reports the remainder as a sync backlog rather than hiding it.
- **`NEW` MEANS "A SWEEP SAW THIS NAME APPEAR", not "recently released" and not
  "we only just noticed".** The first run has nothing to compare against, so
  every name is written `bootstrap` and none of them badge; only a name that
  turns up in a LATER sweep is `scan`. Without that split the first run badges
  the entire library on the day it ships.
- **THE FINISH TEST ASKS THE FILESYSTEM.** `dlstate` goes empty both when a
  download completed and when it failed, and a 404 on the mirror is not even a
  failure -- the engine re-queues over the netchan and `dlstate` stays busy. Only
  "is the bsp on disk now" settles it. `Dl_Tick` is polled OUTSIDE `m_draw`'s
  `menu_active` gate for the same family of reason as `ui_join_tick`: the
  download survives an ESC and nothing else notices it finished.
- **AN HTTP DOWNLOAD LANDS IN A `.tmp` AND IS RENAMED ONLY WHEN WHOLE** (Patch
  465). It did not before: `httpclient.c:639-642` opens its localname directly
  with `"w+b"` and never renames, and `DL_Abort`'s rename arm is gated on
  `DLLF_BEGUN`, which a web download never sets. So an interrupted transfer left
  a SHORT .bsp under the real name -- which reads as installed, stops the button
  offering it, and mismatches mapcrc, i.e. a silent `TF_NOMAP` on every run
  played on it. The rename lives in `CL_WebDownloadFinished` and not in
  `DL_Abort` because that arm also does `FS_Remove(dl->dclname)`, and
  `dclname`/`prefixbytes` are set only on the netchan path.
- **NAMES IN `data/mapdl.txt` ARE THE PI'S SPELLING, NOT THE CATALOGUE'S.** The
  catalogues lowercase and the Pi does not; six maps differ by case alone. The
  name in that file IS the download path, and nginx's `alias` uses the captured
  name verbatim on a case-sensitive filesystem, so the catalogue's spelling
  would 404 forever. `mapscan.py` folds case to MATCH and emits what the Pi has.
- **HAVING THE FILE AND HAVING THE RIGHT BUILD ARE DIFFERENT FACTS** (Patch
  466). Patch 465 asked `COM_FCheckExists`, a question about a NAME, so the one
  case the Download button could not help with was a WRONG build -- which is
  exactly what a server kicks you for (mapcrc mismatch, `cl_parse.c:7669`).
  `ui_dl_load` now compares `mapfilekb(name)` against `data/mapdl.txt`'s kb and
  marks the row `ms_have "2"`, which draws "Wrong build" and re-gets with
  `downloadmap(name, 1)`.
- **THE RE-GET CANNOT TOUCH A STEAM INSTALL, and that was traced rather than
  assumed.** `DLLF_OVERWRITE` means "ignore any local files" (client.h:609), not
  "clobber", and this path leaves `fsroot` at `HTTP_CL_Get`'s default
  `FS_GAMEONLY` -- only `DLLF_NONGAME` forces `FS_ROOT` (`cl_parse.c:810`). So
  the file lands in `ftesurf/maps/` and SHADOWS the lower mount. Worth the trace:
  if it had been `FS_ROOT`, the `FS_Remove` beside the rename would have deleted
  content out of the user's Momentum install.
- **`mapfilekb` AND NOT `search_getfilesize`.** The first resolves through the
  MOUNT ORDER (`FS_FLocateFile`); the second answers for whichever duplicate the
  search listed first, and NAMESORT is an explicitly unstable qsort
  (`pr_bgcmd.c:3592-3598`), so with the same map in two mounts it can describe
  the copy the engine will NOT load -- precisely the configuration the check is
  for. Measured: with a truncated shadow planted, `mapfilekb` reads 483 KB, the
  shadow, not the 965 KB copy beneath it.
- **KILOBYTES, NOT BYTES, ACROSS THE QC BOUNDARY.** A QC float is 32-bit and
  exact only to 2^24; maps here pass 200 MB and surf_666 alone is 21,644,745
  bytes. KB also matches `data/mapdl.txt`'s own column so the two compare as
  authored. (And the integer divide has to come first: `(double)(n+1023)/1024`
  is a ratio, not a ceiling.)
- **A SIZE DIFFERENCE IS PROOF OF A DIFFERENT BUILD; EQUAL SIZES ARE PROOF OF
  NOTHING.** The check under-reports by construction and never accuses a correct
  install, which is the right way round when the action is to spend a player's
  bandwidth. Two builds of identical size are missed, and that is the documented
  limit rather than a bug to fix with a tighter threshold.
- **THE WRONG-BUILD BASELINE ON THIS BOX IS 2, NOT 0.** `surf_dune` and
  `surf_fantasy` -- the maps lextest 2i asks about -- and `tools/p466reget.py`
  computes the baseline rather than assuming zero, because a control that
  expected 0 would have failed for the right reason and been "fixed" the wrong
  way. That the size check finds exactly the pair the hash-attestation check
  found is two independent methods agreeing, and is the strongest evidence 2i
  has.
- **`ui_load_maps` IS LAZY, so a reading taken at startup is not a reading.** A
  bare `ui_dlmap` before the browser has opened reports `list 0`, and a
  `wrongbuild` of 0 from an empty list says nothing about the install. The first
  cut of p466reget graded exactly that and the control passed while measuring
  nothing. Any arm that inspects the map list must call `ui_maplist` first, and
  its grader must discard rows whose `list` is 0.
- **A FEATURE IS NOT SHIPPED UNTIL ITS DATA FILE IS IN `$ShipGameFiles`.** 0.1.15
  had to be cut because 0.1.14 carried the map-download code and no
  `data/mapdl.txt` for it to read -- `ftesurf/data/*` is gitignored and the ship
  set is a NAMED list, so the file existed on the build box and nowhere else.
  `ui_dl_load` then reads nothing, every row comes from `search_begin` and is
  already installed, and NO ROW DRAWS A BUTTON. It reads exactly like the
  feature being broken. When a feature's input is generated rather than
  authored, adding it to that list is part of the feature, not packaging.
  The release was also six hours older than the commits -- pushed source is not
  a shipped build, and "is it pushed" is a different question from "what did
  the user download".
- **`tools/mapgrab.py` FETCHES WHAT mapsync CANNOT.** mapsync copies from the
  local Steam install, so it is silent about maps this workstation does not have
  either -- 468 of 1748, and 443 of those bhop, which was 131 of 574. Momentum's
  own `_cache/*.dat` carries every map's `downloadURL` and `bspHash`, so the Pi
  curls them directly (2.7 MB/s there, against a 40 Mbit uplink here) and checks
  each against the publisher's digest. 463 of 464 landed; bhop is 574 of 574.
  `tools/grabtest.py` is the falsifier and must keep passing: good hash installs,
  BAD HASH INSTALLS NOTHING, dead url installs nothing, an existing file is left
  byte-identical, and no `.part` survives any case.
- **`mapsync --only` NAMES WHAT IT DROPPED, and the reason is the bug it hid.**
  It intersects against `--momentum`, so three maps living on the cstrike and
  ftesurf mounts vanished from the selection and the run printed "nothing to do
  -- the Pi already has everything selected". An EMPTY selection wearing a
  satisfied one's words, on a tool whose whole job is copying files.
- **`build.ps1` PRINTS THROUGH THE HOST STREAM, so `2>&1 | Select-String` COUNTS
  NOTHING.** A warning count taken that way returned 0 against a build that
  prints `Done. 0 warnings` three times -- the filter saw an empty pipeline and
  would have said 0 with fifty warnings present. Capture with `*>&1`, then count.
  This is the CLAUDE.md filter rule with a new mechanism: not a spelling that
  does not match, but a STREAM that never arrives.
- **`cl_download_mapsrc` IS DEAD CONFIGURATION while `sv_dlURL` is set**, because
  `cl_parse.c:1005` makes it an `else if` on dlURL being empty and `sv_dlURL` is
  the same cvar (`fs_dlURL`) on a client. Measured, not assumed:
  `tools/p465dl.py` serves both url shapes and every request arrived at the
  `sv_dlURL` one. It is kept as the documented fallback, not as the live path.
- `tools/p465dl.py` is the falsifier for the whole thing, and `ui_dlmap` is the
  Download button's headless twin the way `ui_join` is the start button's --
  no cfg in this tree drives a cursor. **Run `--control` too**: it answers 404
  from the same port with the same config and must reach `failed` with nothing
  on disk. A subject arm alone can pass on a stale file from the last run.
- **A STATE SHOWN FOR A FIXED TIME NEEDS A SAMPLE INTERVAL SHORTER THAN THE
  WINDOW.** `DL_HOLD` is 6 s; an arm polling every 8 s reported `active -> idle`
  with the map on disk, which reads exactly like a download that never finished.
  It had finished -- the probe was stepping over the banner.
- **THE TEST LOG ACCUMULATES.** FTE appends, so a driver that does not delete its
  log before the run grades the PREVIOUS arm's lines too. The control's first
  pass showed 12 state samples for 6 calls, opening with the subject's `ok`.
- The sweep is a Windows scheduled task (`FTESurf map scan`, PT6H,
  `tools/mapscan_6h.ps1`) and NOT a Pi cron, because `maproster.py` hashes the
  build this install would load out of the two Steam installs and those are here.
  The cost is stated in that file: a sweep missed while the PC is off is missed,
  not queued. Since Patch 644 it fetches nothing the Pi can fetch itself: it
  reads the Pi's catalogue back and sends the Beta list ("The library keeps
  itself level").

### The map browser's parallel buffers (build 89, and a build-58 defect)

- **`bufstr_add` APPENDS AT THE BUFFER'S PHYSICAL `used`, WHICH IS NOT
  `ms_count`.** `PF_bufstr_add_internal` (`pr_bgcmd.c`) does `index =
  strbuflist[bufno].used` for the append-on-end form. `ui_load_maps`' second
  pass compacts the list by moving the rows it keeps DOWN and then only moving
  the count -- its own comment says "just move the count", and the dropped rows
  stay physically in the buffer past `ms_count` (81 of them on this box; the
  "maps not listed" line is their count). So from build 58 to 87 every row
  `ui_dl_load` appended was written 81 slots past the index the hash beside it
  recorded, and the hash was right. Name, source, list mask, size and NEW badge
  all landed on a different map's row.
  It survived four builds because the columns it corrupted are UNIFORM over the
  search-derived rows -- `ms_have` is a column of "1", `ms_new` of "0",
  `ms_dlkb` of "0" -- so a displaced write looked exactly like a correct one.
  Build 89's tier column was the first with an independent count to disagree
  with: the engine said 550 KSF tiers where the data files allow 469, and
  550 - 469 = 81 exactly.
  **Write the index (`bufstr_set(buf, ms_count, ...)`) rather than trusting a
  length.** And never size a new parallel buffer from `ms_count` when the ones
  beside it were created before the compaction -- their lengths do not agree
  and nothing warns.
- **TWO NUMBERS FOR ONE QUESTION IS WHAT FOUND IT.** `tools/b89browse.py`
  derives all five of build 89's figures from `data/mapmeta.txt`,
  `data/mapdl.txt` and `data/mapwr.txt` and compares them to what the engine
  printed. The first cut of the PYTHON side was wrong too -- it tested "mapmeta
  has no row" where the engine tests "no tier is shown", missing 7 rows -- so
  the first disagreement was 88, not 81. A condition stated slightly wrong
  reads exactly like a bug in the subject; the way through was to make the
  engine NAME the rows rather than count them.
- **A SECOND TIER SOURCE EXISTS AND WAS BEING THROWN AWAY.** `mapmeta.txt` is
  Momentum's cache. `maproster.py:413` falls back to KSF's roster where Momentum
  has no record (`mtier if mtier != "-" else ktier`) and `mapdl.txt` inherits
  that, so 462 maps had a real tier in a file the menu already opens and drew
  "--". `ui_meta_load` now consults `ms_dltier` where `ms_tierv` is 0 and marks
  the row `ksf`, which draws `T3k`. 469 rows on this box; 128 maps have no tier
  from anywhere and still draw "--", which is the honest answer for them.
- **MEASURE A PROPORTIONAL FONT, DO NOT COUNT CHARACTERS.** The download button
  was a flat `DL_W 92` and "re-get 149.0 MB" was being cut off. The UI face is
  Roboto (`sh_font.qc`); `ui_dl_gutter` asks `stringwidth` for the widest label
  and the widest re-get line and returns 127 px. The arm FAILS if the old 92
  would have been enough -- a fix whose premise is not measured is aimed at a
  guess.
- **A WRAPPED FILTER STRIP NEEDS MORE PITCH THAN ITS OWN HEIGHT.** The wrap was
  `y + 46`, which is exactly heading (20) + `CHIP_H` (26) -- so the next heading
  started on the pixel the chips above it ended. Invisible while a wrap only
  happened in a narrow window; build 89's third strip made it the normal case
  and "library" sat on the tier chips. `STRIP_PITCH` is 52.
- **`buf_sort` IS NOT THE TOOL FOR ORDERING `ms_view`.** Its key is a string
  prefix, and `ms_view` holds indices as text, where "1000" sorts before "2".
  More importantly nothing specifies that it is STABLE, and within a tier the
  order has to stay the name order -- the engine's own NAMESORT next door is an
  explicitly unstable qsort. `ui_refilter` uses a counting sort over 44 buckets
  (ROADMAP 10's data class, then the 11 tier ranks), which is stable by
  construction rather than by assumption.
  A CONSEQUENCE WORTH KNOWING: because appended (downloadable) rows are added
  to `ms_name` last and the sort is stable, they land at the END of their tier.
  Installed maps come first within each tier. That is not a bug, but it means a
  Download button is never on the first screen of a tier.
- **`data/mapwr.txt` IS A SNAPSHOT, and `tools/mapwr.py` has to be re-run before
  a release.** It holds the best known main-track time per map, read straight
  out of surfd's `runs` on the Pi with `MIN(millis)` -- the same row
  `BOARD_ORDER` ("millis ASC, submitted ASC, player ASC", `surfd.py:2056`) puts
  first. MILLIS AND NOT TICKS: tickrate is per-run and 66.6667, 100 and 125 all
  appear in that table, so a tick count is not comparable between rows. 736
  maps have one; 586 of those are Momentum's imported archive and 150 KSF's, so
  on nearly every row this is another community's world record rather than
  anything set here. `ui_wr_load` is deliberately SILENT about a missing file --
  the column is optional, and a warning would send people looking for a tool
  they do not need to run.

- **A SAVED CVAR SHADOWS A SHIPPED ONE, SILENTLY, AND ftesurf.cfg IS READ AFTER
  default.cfg.** `sv_dlURL` was EMPTY at runtime although `cfg/default.cfg` sets
  it, because `ftesurf/ftesurf.cfg` -- what the engine writes on quit -- held
  `sv_dlURL ""`. With no url, `CL_CheckOrEnqueDownloadFile` never reaches
  `CL_EnqueDownload` and returns "nothing to wait for", which `ui_dl_start` can
  only read as a failure. NO MESSAGE AT ANY LAYER: the download button simply
  does nothing. `ui_dl_migrate_url` repairs an empty value and stamps a
  generation, which is `Lob_MigrateDir`'s rule -- and the reason `lobby_dir` was
  fine in the same file while `sv_dlURL` was not is precisely that one had a
  migration and the other did not.
  WHICH CVARS THIS CAN HAPPEN TO: ftesurf.cfg carries ARCHIVE-flagged ENGINE
  cvars (measured by ftesurf-e0: six `set` cvars from default.cfg are absent
  from it, and every line in it is engine-declared with the engine's own
  description). A QC `registercvar` cvar is not written -- unless someone types
  `seta` at it, which makes it archived from then on. `seta lobby_dir_gen "1"`
  is in there, which is also what makes the generation stamp a real one-shot.
- **TWO WRONG ANSWERS BEFORE THE RIGHT ONE, AND BOTH READ AS RESULTS.** Chasing
  that empty cvar: (1) "it is `cl_download_mapsrc`" -- three variants differed in
  the cvar AND in the map, and the map that succeeded under one setting later
  FAILED under the same one. A confounded arm reads exactly like a finding.
  (2) "it is elapsed time" -- +2 s, +18 s and +38 s, three different maps
  (a failed download is cached per file, so retrying one answers the cache and
  not the question); all three failed. What settled it was printing the cvar
  rather than reasoning about the branch that reads it.
- **ms_lst IS "WHICH LIBRARY", ms_src IS "WHERE THE FILE IS", AND THE SWITCH
  WANTS THE FIRST.** Lex, on a laptop: the CS:S list showed about 30 surf maps
  where `data/mapdl.txt` offers 925 that are KSF-listed (and every one of those
  925 is surf; 0 are bhop). `ms_lst` was being taken from the MOUNT alone, so on
  a machine with no cstrike mount every map Momentum also ships read as
  Momentum-only -- 463 of the offerable maps are in both catalogues. `ui_dl_load`
  now ORs the catalogue letters (`k`, `m`, `km`) into `ms_lst` for INSTALLED rows
  as well as appended ones. OR and not replace: a map in the Momentum mount
  really is available from Momentum, and KSF listing it too is an addition.
  Measured cs:s 1027 -> 1080 on a box that HAS CS:S, which is small by
  construction -- the machine without the mount is the one this is for.
- **A MAP ON DISK WAS BEING OFFERED AS A DOWNLOAD.** `ui_load_maps` drops every
  map whose only mount is neither Momentum nor CS:S, and THE GAMEDIR IS ONE OF
  THOSE -- so a map fetched by the Download button landed in `ftesurf/maps/`, was
  dropped from the search list on the next load, fell through to `ui_dl_load`'s
  append branch and was offered again with a size beside it. The one thing a
  Download button must never do is come back after it worked.
  `surf_raqbonus3ramp` reads `src 1 lst 1` here, which is what that looks like.
  The append branch now asks the filesystem (`mapfilekb`, or `ui_file_exists` on
  a pre-466 engine) and writes the same three `ms_have` states the installed
  branch does, so such a row draws Play or Wrong build instead. `ms_dlcount`
  counts what the row will DRAW rather than lines read, or "offers 464" would
  still say 464 after you had downloaded all of them.
- **THE ACTION COLUMN IS ALWAYS RESERVED, and that is why it holds Play.** The
  download gutter used to appear only when `data/mapdl.txt` offered something,
  because a download button was the only thing that ever went in it -- so on a
  complete install it was 127 px of nothing down every row. Lex: "replace the
  Download button box with a green play button box so it doesn't look so empty".
  `ms_have` is one value, so the three states are mutually exclusive by
  construction: "1" plays, "2" replaces, "0" fetches. Play goes through
  `ui_launch` and NOT `ui_launch_local`, so the consent gate and the name gate
  stay in front of it -- a direct call there is exactly the refactor `ui_launch`'s
  own essay warns about.
- **THE TWO HARNESSES FOR THIS BROWSER.** `tools/b89browse.py` derives all five
  of the build-89 figures from the data files and compares them with what the
  engine printed -- two numbers for one question, which is what caught the
  build-58 defect. `tools/b89join.py` drives the pre-join fetch against the REAL
  mirror (a stub would prove the state machine and not the feature) and grades
  its two NEGATIVE arms as hard as the positive one: a join-check that holds a
  join it should not have held is a player who cannot join anything, which is a
  worse bug than the kick it fixes. It also removes the map it downloaded and
  CHECKS the removal, rather than swallowing the error.
- **`tokenize` CLOBBERS A CONSOLE COMMAND'S OWN `argv`.** A diagnostic that read
  `argv(1)`, called `ui_load_maps()` and then used `argv(1)` again ran all three
  of its cases against `surf_zor` -- a word out of mapmeta.txt -- and reported
  the feature doing nothing. `ui_load_maps` tokenizes every line of three data
  files. strzone the arguments BEFORE any call that can tokenize. The server's
  too: Patch 477's `sl_saveat ... go` lost its `go` to SV_SaveReadLight, which
  tokenizes the state file it reads back -- read every argv() first.
### `status` CANNOT SEE MOST OF SERVERINFO -- do not read its silence as absence

`SVC_Status` builds serverinfo into a `char infostr[1024]` and `InfoBuf_ToString`
drops low-priority keys once that fills (`sv_main.c:1253-1256`, which carries its
own `FIXME` about the limit and a `prioritykeys` list "to make sure we include
these before we start overflowing"). A `status` probe of a lobby comes back at
almost exactly 1029 bytes and ENDS ON A CLEAN KEY BOUNDARY, so a truncated reply
is indistinguishable by eye from a complete one.

This session read `sv_dlURL` as unset from such a probe and started debugging a
config that was correct. Use rcon for a specific cvar when the question is "did
this setting take" -- and read the password from `cfg/lobby_local.cfg` inside the
script rather than passing it as an argument, where `ps` would show it.

### Preparing the boards (the sweep, and keeping it fresh)

- **Times and demos are separate jobs and the difference is three orders of
  magnitude.** Every surf/bhop board's top 25 is 3,693 requests, about an hour.
  The DEMOS behind those rows would be ~92,000 files, ~35 GB and a day of
  sustained traffic. So `tools/momfetch.py` fetches times for everything and
  demos stay bounded and on demand. Do not casually widen that.
- **The map catalogue is the one input that cannot be fetched** -- FALSE for
  approved maps, measured 11 Oct (Patch 644, "The library keeps itself
  level"): `/v1/maps` lists them anonymously, ids and boards included. Still
  how `momtracks.tsv` is made: `tools/msml.py`
  reads the game's `momentum/_cache/*.dat` (`MSML`, two u32s, a zlib JSON
  array) for map ids and each map's track list.
  Export it with `--out` and ship the TSV to any box without the game --
  `momfetch --tracks` reads that instead of `--cache`.
- **Ask in the map's OWN gamemode.** The catalogue claims a board in nearly
  every gamemode for nearly every map and almost all are empty (44,676 claimed
  against 3,693 real). `gm_of()` decides by the name prefix.
- **1.0 s between requests, not the reference's 400 ms.** That figure was for a
  person pressing a button; a sweep should cost more, not less. One at a time,
  capped per invocation, honest User-Agent, and a non-2xx STOPS and is never
  retried. Every answer is cached, so a re-run is free and an interruption
  resumes -- which is the property that makes re-running it polite rather than
  rude.
- **MOMENTUM'S API DOES RATE-LIMIT, AND 1.0 s EVENTUALLY TRIPS IT.** Measured
  2026-09-28: HTTP 429 after 2,164 consecutive requests in one 61-minute run,
  ~2,700 across the session. This CONTRADICTS the wrlines reference, which says
  "No 429 was ever observed and none is mentioned in any file -- the constraint
  is stated as courtesy and cost-to-the-operator, not as an enforced limit the
  author ran into." That was true of a tool that never swept; it is not true of
  one that does. The limit is real and it is theirs to set.
  THE ANSWER IS TO COME BACK LATER, NOT TO RETRY. momfetch stops on it, caches
  everything already fetched, and resumes exactly where it left off, so a full
  sweep is two or three sittings rather than one. Do not lower the delay to
  "get it done"; do not add a retry. A 429 is the host asking for less, and the
  only correct reply is less.
- **`surfd/momwatch.py` needs no hook in the game.** surfd already records what
  every lobby is on, so it reads the `lobbies` table, refreshes the boards of
  currently-played maps that are missing or stale, and does nothing otherwise.
  Staleness is per BOARD, so one new stage record does not re-fetch a map's
  other fifteen boards. Cron it; on an idle fleet it makes zero requests.
- **A KSF 500 is an ANSWER, not a refusal.** It is how that host says "not a
  player of mine" -- measured at a third of SteamIDs taken off Momentum's
  boards. Collapsing it into a refusal ends a sweep at its first non-KSF
  player. The reading is INFERRED, so `SKIP_STREAK` (25 consecutive) is the
  breaker on being wrong about it: a host that is really refusing answers 500 to
  everything and trips it in seconds.
- **The two imported tiers differ in watchability, by nature.** Momentum rows
  can carry a replay; KSF rows never can. After a full times sweep most
  `momentum` rows will also be times-only -- the demo corpus is ~5,000 runs
  against ~90,000 board rows -- so "imported" will mostly mean "a time", with a
  minority watchable. `momboards --link` is what joins a fetched time to a demo
  we already hold for the same run.

## Pi operations (public lobbies)

**Fleet catch-up — 2026-10-12.**

- Clean product `1f60e35` and pinned native `263d17686`/P679 are now live on all
  twelve lobbies, including the previously pending P677 CSQC. New native/plugin
  pair built in an owned ARM root, not shared p349build; both map dettests match
  Windows on all 19 normalized lines, two verifier compatibility controls PASS.
  All12 fresh `/proc/PID/exe` hashes, mapped plugins, UDP sockets, version and
  `sv_limittics 8` readbacks proved at10:58:29Z. Fresh unseeded client downloaded
  exact CSQC and drew8cols/type14; screenshot inspected, no QC errors. Player
  files/protected configs unchanged. P678/P680 prep remains inert; backend was
  already current. Full hashes, rollback and limits: `tools/lobby-catchup-20261012.md`.
- Linux dedicated harnesses must pass the actual owned `default.fmf` path to
  `-manifest`, not bare `ftesurf`: a same-name directory can reach
  `FS_Manifest_ReadSystem` and abort with an invalid enormous allocation before
  logging starts. Windows happened to reject that directory at open. Explicit
  file path passed the same ARM build's acting controls. This is a harness
  correction, not a product fix; the unchecked path is recorded in BACKLOG.
- A clean isolated native engine cannot read Source BSPs until its **matching
  hl2 plugin** is built beside it. Successful sv-rel alone is not a Source-map
  gate. `plugins-rel` also needs zip for embedded metadata; the catch-up extracted
  the package under its owned root, without altering system packages. Preserve
  failed build evidence and actually rerun the complete target/gate.
- `-NoDeploy -Pi` is intentionally rejected. Use the clean worktree's documented
  `build.ps1 -Pi` path, inspect actual destination behavior, then verify both
  Windows installs explicitly instead of assuming the isolated root is the
  canonical install. All three clean-built VMs now hash-match in both installs.

- **THIS FLEET IS A DEVELOPMENT FLEET AND THE OWNER WANTS CHANGES DEPLOYED.**
  Standing instruction from the operator, 2026-09-27, in their words: *"we are in
  development and I WANT changes to be deployed or else I can't test it. You will
  not be affecting any players because I don't have any."* So `build.ps1 -Pi` is
  the normal end of a piece of work, not an escalation to ask about: build to 0 new
  warnings, run the falsifier, commit, deploy, then verify on the host. Do not sit
  on a tested patch waiting for permission — an undeployed patch cannot be tested
  by the person who asked for it, which is the whole point of the fleet.
  The things that still warrant a word first are the ones that are NOT "deploy a
  tested build": destroying data (the evidence tree, the board database, a save
  root), anything that cannot be rolled back, and shipping ANOTHER SESSION'S
  uncommitted work — `-Pi` pushes both progs, so it carries whatever is in the tree.
  `qwprogs.dat.prev` and `csprogs.dat.prev` are kept by the deploy, so an ordinary
  progs deploy is one copy away from reversible; say so rather than hedging.
- **Credentials are the operator's to rotate and they have asked for it to be done
  when needed.** `rcon_password` and `lobby_master_key` live in
  `game/ftesurf/cfg/lobby_local.cfg` (NOT in this repo) and are SHARED with surfd's
  `surfd.env` as `SURFD_RCON_PASSWORD` and `SURFD_KEY` — prove that by hash before
  touching either, and rotate both sides in one pass or the board starts refusing
  heartbeats with `bad key`. Back up with the tree's `.bak-prerotate-<stamp>`
  convention, chmod 600, and never print a value into a log, a commit or a chat
  line. `SURFD_ADMIN_SECRET` is surfd-only. `sv_guidkey` is a different kind of
  thing: rotating it RE-DERIVES EVERY CLIENT GUID and orphans the identity binding
  on existing runs, so it is a data decision and wants asking.
- **surfd is NOT a systemd unit** — the unit file next to it says so in its own
  header. It is gunicorn started by `/srv/nvme/surfd/run.sh` as `proto`, so it
  needs no sudo. `stop.sh` only works if `surfd.pid` exists, and on 2026-09-27 it
  did not: `run.sh` then started a second gunicorn that could not bind 8084, wrote
  a pidfile anyway and exited, leaving the OLD process serving. Kill the real
  master by pid (`ps -eo pid,ppid,lstart,cmd | grep surfd:app`, the one with
  ppid 1), wait for the port to free, then `run.sh` — and confirm ONE master and
  one worker afterwards rather than trusting the "started" line.
- 12 lobbies, systemd `ftesurf@1..12`, basedir `/srv/nvme/ftesurf-server/game`;
  lobby cfgs sourced from this repo's `ftesurf/cfg/lobby/` — edit here, scp there.
- Server CONTENT is hand-copied beside the engine: `game/{momentum (maps only),
  cstrike, hl2}` hold VPKs from a Windows Steam install, mounted by the Pi's
  `fs_addons.txt`, and a lobby mounts new content only on restart. There is no
  Steam and no `data/mapdeps.txt`, so fs_automount mounts nothing: props from the
  CS:GO/TF2/Portal/Momentum-`mount` packs are NOT solid on the server. `hl2` was
  empty until 2026-09-20 (bhop_monster_jam collided 2142 of 6048 prop faces);
  with the 31 `hl2_*.vpk` copied in, the Pi's pm_dettest equals Windows. Prove
  any content change the same way (`cfg/test/p386det.cfg`, a spare port).
- **TWELVE SSH CONNECTIONS IN A ROW LOOKS LIKE A FLOOD TO sshd, AND A DEPLOY CAN
  END WITH THE FILES LIVE AND SOME LOBBIES STILL ON THE OLD PROGS.** Measured
  2026-09-27: `ftesurf@7`, `@10`, `@11`, `@12` all returned
  `Connection closed by port 22` during one `-Pi`. `build.ps1` reported it and
  threw, which is correct — but by then the swap had already happened, so the
  fleet was split: eight lobbies on the new build, four on the old. **Read the
  host after every deploy rather than trusting the "all 12 restarted" line**, and
  restart the stragglers one at a time. If this recurs, space the restarts or reuse
  one ssh connection (`-o ControlMaster`) instead of twelve.
- **THE GIT INDEX IS SHARED BETWEEN CONCURRENT SESSIONS, AND `git commit` COMMITS
  THE INDEX — NOT YOUR PATHSPEC.** This bit both sessions on 2026-09-27 in both
  directions: a `git add -A` swept the other session's uncommitted client work into
  two of my commits, and later my staged server work landed inside *their* commit,
  so my own commit message described changes that were not in it. Staging explicit
  paths does NOT fix it, because the hazard is the window between your `add` and
  your `commit`. **Use `git commit -- <paths>`**, which commits only those paths
  whatever else is staged, and read `git diff --cached --name-only` immediately
  before committing. The code survives either way; what breaks is the record, and a
  commit message describing work that is not in the commit is worse than no message.
- Restart: sudoers is per-unit only — loop `sudo -n systemctl restart ftesurf@$i`
  for i in 1..12. After copying a cfg, restart and READ THE VALUE BACK rather
  than trusting the file: from `/srv/nvme/surfd`, `rcon.Rcon("127.0.0.1", port,
  pw).execute([cvar])` with `pw` read from `surfd.env` inside the script and
  never printed (loopback only, 8 packets per 30 s per port).
- Deploy server progs with `./build.ps1 -Pi` (refuses while players are
  connected, scp's both .new files, hash-verifies on the Pi, swaps in ONE ssh
  command keeping `.prev`, restarts every active lobby); menu.dat stays local.
  `-PiForce` overrides the refusal — beta phase, and the connected player is
  usually the reporter; say so when you use it.
  `-Pi` SHIPS THE WORKING TREE. When the tree carries other sessions'
  uncommitted QC, build from a clean `git worktree add <tmp> HEAD` instead, and
  remove the worktree afterwards. A clean HEAD still carries other sessions'
  COMMITTED patches: check `git log <last deployed>..HEAD` and ask; if one is not
  approved to ship, `git -C <tmp> revert --no-commit <sha>` in the worktree only.
- The lobbies run a NATIVE aarch64 engine, `game/fteqw-svarm64`, built on the Pi
  in `/srv/nvme/p349build` -- as of 2026-09-20 the 375 deploy, Patch 380's three
  server files and Patch 396's `sv_send.c`, NOT 386-388's fs.c/fs_stdio.c; since
  then 418, 419 and 427 (`sv_user.c`), per the `fteqw-svarm64.preNNN-*` swap
  backups in game/. `git hash-object` a file before assuming it is current. That tree is NOT a git checkout: send changed files
  with `git -c core.autocrlf=false archive <sha> <paths> | ssh … tar -x` (plain
  `git archive` here ships CRLF), check them with `git hash-object`, then
  `make -C engine sv-rel FTE_TARGET=linux CC=gcc BITS=arm64 -j3`. Gate:
  `pm_dettest` on bhop_eazy prints the same hashes as the Windows build. For a
  one-off run: `+set sv_port <p> +map bhop_eazy +exec cfg/<x>.cfg`. A dedicated
  server with no `+map` dies with "Couldn't load a map", and the Pi has no
  `cfg/test/`: copy the cfg in, then delete it. Also `pm_verify` a known PASS
  file, because the sweeper uses the new binary at once. SINCE PATCH 492 A PIN-1
  FILE AND bhop_eazy CANNOT SEE THE SOURCE CLIP: `tools/pigate.sh <bin> <port>
  <dir>` (scp it, `cfg/test/p492voy.rec` and the install's
  `maps/zones/local/surf_voyager.json` into <dir>) prints pm_dettest on bhop_eazy
  and surf_ace -- every line, `srctrace` included, must equal Windows -- and
  verifies a pin-1 file and p492voy.rec (pmsrcver 2) through an overlay. The old
  binary REFUSEs p492voy.rec, which is the control. NEVER ROLL THE SWEEPER BACK
  PAST 492: an old verifier reads only the header's pmsrcver, so a Multi-Session
  run parked before a 492 deploy and resumed after it (pin 1 in the header, 2 in
  a later `pm` record) HOLDs there. An ssh that starts a
  background server does not return, so run it in the background. Run
  hand tests on a port other than 27698, which is the sweeper's. Swap by
  `cp` to `.new` then `mv -f`, keeping `fteqw-svarm64.preNNN-<stamp>`. Running
  lobbies keep the old binary until restarted; the sweeper picks up the new one
  immediately.
- **AN OVERLAY BASEDIR IS LINKS INTO THE LIVE GAME, AND A GUI DELETE FOLLOWS
  THEM.** 2026-10-05: an old overlay, /srv/nvme/p323base (126 links, 24 MB real,
  57 GB to anything that follows links), was deleted with a file manager and
  emptied game/ftesurf/{models,glsl,particles,scripts} and all of
  game/momentum/maps while 12 lobbies ran. Restored the same day from the 0.1.23
  stage and the Windows Steam Momentum install (1347 BSPs, a superset of the
  library), rotation maps first. Remove an overlay with `rm -r <dir>` in the
  session that made it; never leave one behind.
- To pm_verify a fixture-zoned file on the Pi (surf_666 with p360sf) without
  touching live zones: an overlay basedir -- link every entry of game/ except
  ftesurf/, and every entry of game/ftesurf except data, logs and maps; put the
  fixture at <overlay>/ftesurf/maps/zones/local/<map>.json and the files under
  <overlay>/ftesurf/data; run game/fteqw-svarm64 -basedir <overlay> with the
  sweeper's arguments (port != 27698). Remove it after (rm -r keeps link targets).
- Configs reach the Pi BY HAND: `-Pi` ships only the progs. A dedicated server
  execs `cfg/default.cfg` when there is no `server.cfg` or `quake.rc`
  (`sv_main.c:6714`).
  DIFF BEFORE COPYING, and list the server-relevant cvars that would change.
  Until 2026-09-18 the Pi's copy carried a hand-written `set pm_slide 0`
  block, which gated func_slide (Patch 280) off from the build 66 deploy. Lex
  turned slides on, and the Pi now runs the repo's file. Mover cvars must be
  set IN default.cfg: `cvar_lockdefaults` makes a later cfg or rcon unable to
  change them. A lobby's real physics values are in its recordings' `pmpin`
  header.
  A RULE CHANGE IN `default.cfg` NEEDS THE COPY TOO, and `-Pi`'s output never
  mentions it: Patch 445's `run_rearmhop 0` was "deployed" 2026-09-27 and the
  fleet ran `1` until 2026-10-03. Compare the two files' sha256 after a deploy.
- `rcon.Rcon(...).execute(argv)` runs ONE command, so `execute(["a", "b"])` SETS
  `a` to "b" -- on 2026-10-03 a two-cvar "read" did exactly that to two lobbies.
  One cvar name per call.
- Post-deploy verification is a CLIENT CONNECT, not the journal: `ftesurf@N`
  journals need sudo (sudoers is restart-only) and lobby cfgs write no file
  logs. Use the `cfg/test/p339pi.cfg` pattern — headless client into a live
  lobby, check the `trig:` census, hook-alive line and prederr count; every
  rotation map exists locally in the Steam Momentum library.
  **"NO FILE LOGS" IS ABOUT THE CFGs, NOT ABOUT THE ENGINE, and the difference
  matters: a lobby's file log can be TURNED ON BY RCON for the length of one
  measurement** -- `log_name <n>`, `log_dir logs`, `log_enable 1` (one cvar per
  `execute()` call), read `<basedir>/ftesurf/logs/<n>.log`, then `log_enable 0`
  and delete the file. That is the only way to see server-side `print()` output
  from the fleet, and it is what `cfg/test/deploy496smoke.cfg` needs because a
  server QC `print()` does not reach the client's log at all (see the pitfall).
  It is also a temporary change to a public lobby: do it on one unit, say so in
  the entry, and put it back.
- **`tools/pi_lobby_smoke.py` IS THE CLIENT CONNECT FROM AN ISOLATED RIG**
  (added 2026-10-10). It gives a fresh client NO csprogs, joins a lobby, and
  grades the file the engine downloaded against the build's hash, then that the
  board drew (`scores status`). That is the one check that says what a lobby
  SERVES rather than what sits on its disk. THE RIG MUST CARRY THE REAL
  `default.fmf`: a lobby answers a client whose `PROTOCOLNAME` differs with
  "Game mismatch: This is a FTE-Quake server but you are using FTE" ten times
  and the cfg then runs to its end marker against no server at all, screenshot
  included. Map content comes from `fs_addons.default.txt`'s Steam mounts; the
  hl2 plugin must sit beside the exe.
  `build.ps1 -Pi` ALSO REWRITES qwprogs EVERY TIME even when no server QC
  changed: fteqcc stamps the compile date into the file (two bytes at 0x72), so
  "the hash moved" is not evidence that server code did. Diff the bytes.
- **A LOBBY PORT IS 27510 or 27520..27620 (cfg/lobby/lobby<N>.cfg), NOT 27698.**
  27698 is the sweep server's, which AGENTS.md already says to avoid for hand
  tests, and connecting to it from a smoke cfg produces `Can't "cmd", not
  connected` four times -- which reads exactly like dead progs and was a dead
  port. `build.ps1 -Pi` discovers the fleet's own ports over ssh rather than
  keeping a list, so nothing else in the tree repeats this mistake by accident.
- **`build.ps1 -Pi` MIS-BINDS ITS OWN PARAMETERS WHEN ITS OUTPUT IS REDIRECTED
  TO A FILE, AND THE GUARD IS WHAT MAKES THAT SAFE.** Measured 2026-10-06, pwsh
  7.6.6, same command line both times: `pwsh -NoProfile -Command
  "./build.ps1 -Jobs 8 -Pi" *>&1 > /tmp/x.txt` reaches the Pi step with
  `$PiGame = 'cl_progs.src'` -- a value that appears nowhere else in the script
  except as the middle element of its own compile list -- and throws
  `-PiGame 'build.ps1:cl_progs.src' is not a plain absolute path`. The identical
  invocation piped (`2>&1 | grep ...`), or run bare, or run through `-File`,
  binds correctly and deploys. Probes pin it: `$PiGame` is still correct at
  script start, at `Step "QuakeC"`, after `Push-Location` and inside the compile
  loop, and is wrong by `if ($Pi)`. Nothing in the script assigns it. A minimal
  faithful reproduction does NOT reproduce it, so this is a pwsh host/binding
  fault rather than a script one -- which is why the fix is not in the script's
  logic. TWO RULES FOLLOW: never grade or capture a `-Pi` run with `*>&1 > file`
  (use a pipe, or `-File`), and never remove that `$PiGame` regex guard, whose
  only job is to stop a corrupt path reaching twelve `scp` and `ssh` calls.
- surfd is `surfd.service` (gunicorn :8084 behind nginx), and its app log is
  `/srv/nvme/surfd/logs/surfd.log`. To deploy:
  1. Take the files FROM THE COMMIT, not the tree:
     `git -c core.autocrlf=false archive HEAD surfd/... | ssh … tar -x` into a
     /tmp stage.
  2. Run the suite there, with `TMPDIR` set to a private dir; the tests leave
     their temp dirs behind. Stage `tools/` and `src/shared/` beside `surfd/`
     (test_sweep and the TF_* pins read them). `test_momindex.py` is an import
     arm, not a suite member: it needs `--db <copy> --momentum <tree>`.
  3. Back up `data/surfd.db` with sqlite's backup API. (The `database is
     locked` heartbeats that seemed to follow it on 4 Oct were momwatch's: they
     land on every `*/7` tick, all day, backup or not -- see BACKLOG.)
  4. Copy the files in under `flock /tmp/surfd-sweep.lock`.
  5. Reload the gunicorn master, then read the log for `surfd ready`. SINCE
     27 SEP THAT IS NOT THE UNIT: `surfd.service` is dead and surfd runs from
     `run.sh` with `--pid /srv/nvme/surfd/surfd.pid`, so `systemctl show surfd
     -p MainPID` reads 0 and `kill -HUP 0` signals your own process group (it
     killed a deploy script on 4 Oct, mid-reload). Check the pidfile names a
     live `surfd:app` gunicorn, then `kill -HUP $(cat …/surfd.pid)`.

  **`tools/surfd-deploy.ps1` IS THAT PROCEDURE AS A SCRIPT** (added 2026-10-05):
  stages from a COMMIT with `git archive`, runs the suite in the stage on the Pi,
  backs up the db, copies under the flock, reloads, and then -- the step that
  matters -- **hashes every deployed file on the Pi against `git rev-parse
  <sha>:<path>`** and fails if any differ. Use it instead of hand-running the
  above; `-SkipTests` and `-NoReload` exist and should be said out loud if used.
  IT ALSO KEEPS THE CREDENTIAL STORE OWNER-ONLY: the backup it makes is chmodded
  600 and the deploy FAILS if that did not take, and its step 7 tightens any loose
  `surfd.db*` file and reports what the backups cost (`OURS=` / `HANDMADE=` /
  `TIGHTENED=` / `STILL_LOOSE=`). `-KeepDbBackups N` prunes the script's own,
  oldest first, only after the deploy has verified; the default REPORTS AND
  DELETES NOTHING, because a deploy that made the backup is not a deploy that may
  decide to destroy older ones.
  FIVE TRAPS IT PAID FOR, all of them the shape "the tool reported success while
  doing nothing":
  - **A COPY THAT PRINTS A COUNT IS NOT A COPY THAT COPIED.** Its first run
    reported `COPIED=49` having installed zero files: a variable that did not
    expand made every destination an empty string, `install` failed 49 times,
    `set -e` did not fire inside the loop, and the counter counted iterations.
    Nothing on the live host changed, /health answered, and the reload "succeeded"
    by reloading the old code. **Verify by hashing the destination, not by
    counting the loop.**
  - **`set -e` WITHOUT `set -u` TURNS A TYPO INTO AN EMPTY STRING.** A
    `$backupTag` that failed to interpolate inside a here-string did not error;
    it silently made the backup name and the destination empty. `-u` makes an
    undefined variable fatal, which is the only thing that converts this class of
    bug from silent to loud.
  - **`git ls-tree` PATHS ARE REPO-RELATIVE AND THE PI'S LAYOUT IS NOT.** The
    files it names are `surfd/recplot.py`; the Pi has `recplot.py` directly in
    `/srv/nvme/surfd`. Installing under the repo-relative name wrote 49 files into
    a NESTED `surfd/` that is not a package and is not on the import path -- live
    files untouched, deploy "successful". (The stage must keep the repo-relative
    names, because `tools/` has to land beside `surfd/` for the suite.)
  - **POWERSHELL `-match` IS CASE-INSENSITIVE**, so grading a remote script on an
    uppercase `FAILED` sentinel matched every suite's own `0 failed` success line
    and seven passing suites read as a failure. Use `-cmatch`/`-cnotmatch` for
    sentinels. And `$LASTEXITCODE` READ AFTER A POWERSHELL FUNCTION RETURNED IS
    STALE -- a function call does not set it, so the check graded an unrelated
    earlier command; capture it immediately after the native call and pass it out.
  Also: a function named `Ssh` and the `ssh` executable are ONE name in
  PowerShell, so `& ssh` inside it recursed until "call depth overflow" -- the
  release-script `-QcBuild`/`$qcBuild` trap above, in a function name.
  - **THE REMOTE BODIES RUN UNDER `sh`, AND POWERSHELL'S `-replace` IS A
    CASE-INSENSIVE REGEX.** `Invoke-PiScript` pipes the body to `sh '$stage/<name>.sh'`,
    so bash-only spelling (`read ... < <(...)`) is a syntax error on the Pi's dash --
    `sh -n` the body over ssh before believing it. And a `KEEP` placeholder in a
    body replaced with `-replace 'KEEP', $n` also matched the English word
    "keeping" in the printf two lines below it, putting a number in the middle of a
    sentence. Placeholders are `__NAME__` applied with the literal, case-sensitive
    `.Replace()`; the same reasoning as the `-cmatch` sentinel rule above.
  - **LONG SSH COMMAND-ARGUMENT SCRIPTS CAN TRUNCATE AND STILL EXIT ZERO.**
    Patch 507's checked 10.6k-character body copied source and ran its first
    installed controls, then the remote shell warned that a here-document ended
    at EOF. The remaining race probe, real receipt pass, reload and final health
    checks had never run; the caller still printed its success line. Local syntax
    checks prove the original body, not what transport delivered. Stream long
    bodies through SSH stdin to an explicitly selected `bash -s` (or `sh -s` for
    POSIX bodies), and require every final control/health/UTC sentinel plus exit
    zero and no heredoc warning. Finish only the missing gates after verifying
    installed/paired hashes; never recopy or reinterpret a partial deployment as
    complete. P507's finish-only streamed arm proved the remaining controls and
    reload at 2026-10-06 15:28:23 UTC; source and owner-only backups were retained.

  DEPLOYED (the Pi keeps no receipt of its own, so this line is the record; UTC):
  `2007afc` to /srv/nvme/surfd at 2026-10-04 18:00 -- all 49 files hash-matched
  the commit, master 2479950 unchanged since 27 Sep, worker re-forked to 425928,
  `surfd ready` 18:00:26, /health `{"ok":true,"lobbies":12}`, seven suites green
  in the stage. Backups: `*.pre2007afc-20261005-045845` (34 files it replaced) and
  `data/surfd.db.bak-2007afc-20261005-045845`. Verified live afterwards: run 749
  serves `momdemo e9a68559…` and no integrity key.

  **2026-10-05 10:09-10:14 UTC, the 0.1.23 batch (game `44e9bd8`, engine
  `f2630d9ad`, binaries tag `patch-494` = `6b7b70143`).** Pi engine: 38 files sent
  to p349build from 6b7b70143 (all hash-checked), `make sv-rel` -> md5 07323ee4;
  `tools/pigate.sh` equal to Windows on bhop_eazy and surf_ace (srctrace
  de0ed342 / f89ef15d), boreas 0003107 PASS, p492voy.rec PASS, the old binary
  REFUSE; swapped keeping `fteqw-svarm64.pre492-20261005-100948`. Cfgs:
  default.cfg (pm_fixrampbugs 2, run_movebound 2000) and
  maps/map_surf_voyager.cfg, backups `*.pre492-20261005-100948`. Progs:
  `build.ps1 -Pi` from the clean worktree, 0 players, all 12 restarted -- read
  back: every lobby's process is md5 07323ee4, lobby 1 `pm_fixrampbugs` 2.
  surfd: `surfd-deploy.ps1 -Ref 44e9bd8`, `surfd ready` 10:13:01, /health ok,
  backup `data/surfd.db.bak-44e9bd8-20261005-211108`. Release 0.1.23 published
  10:14 (Windows sha256 AD3085A7..., Linux 1E10FEC0...).

  `490f73d` then `e11084c` to /srv/nvme/surfd at 2026-10-05 03:48 and 04:03 --
  schema 10 (`sims`, the store-only cross-run similarity sample), eight suites
  green in the stage including the new `test_simcheck` (40 checks), all 53 files
  hash-matched the commit, master 2479950 unchanged, `surfd ready` 04:03:22,
  `/health {"ok":true,"lobbies":12}`, live `user_version` 10 with 0 `sims` rows.
  Backups `*.pre490f73d-20261005-144643` and `*.pre-e11084c-…`, plus
  `data/surfd.db.bak-490f73d-20261005-144643`.

  **[HISTORICAL: superseded by the 2026-10-06 runtime read below] THE SIMILARITY
  STEP STORED NOTHING ON THE PI THEN, AND THAT WAS EXPECTED RATHER THAN BROKEN.**
  At that observation `tools/census/` was not deployed beside the game, so
  `_recsim()` found no comparison and the step degraded to storing nothing and
  printing its reason on every sweep line -- the behaviour the receipt step's
  lazy imports exist for. The then-live `simcheck._recsim(sweep.TOOLS)` reported `no
  recsim.py found (tried: /srv/nvme/ftesurf-server/game/tools/census/recsim.py,
  /srv/nvme/tools/census/recsim.py)`.  The first path is the RIGHT one and is
  where reccheck.py and rcptcheck.py live; installing `recsim.py` there could
  activate the step with no code change and no reload. The 2026-10-06 read below
  found it already installed; this old observation is not current provenance.
  **AND NOTE THE SECOND PATH IT TRIED, BECAUSE IT IS A TRAP.** `/srv/nvme/tools`
  EXISTS and is a steamcmd directory (linux32, linux64, steamcmd.sh) with nothing
  to do with this tree.  It is `<surfd>/../tools`: simcheck's own-neighbourhood
  fallback, which `e11084c` kept, so a `census/recsim.py` there would have been
  imported and RUN by the sweep.  It is gone (branch surfdfix); the module
  searches only the caller's resolved directory (else SURFD_TOOLS), because a
  default is policy and two spellings of one policy drift.
  The measurement this feature was for was made on a COPY of the live database and
  reproduced `recsim.py`'s census exactly through a different code path: 24 pending
  runs, 22 pairs, 20 compared, 2 unjudgeable, 0 notable, same-identity max 0.5866
  (n=12) against cross-identity max 0.2146 (n=8).  Two independent derivations
  agreeing is the strongest evidence it has.

  `d42165e` to /srv/nvme/surfd at 2026-10-05 04:46 UTC -- momboards' link_demos
  fix (a symmetric LINK_SLACK_MS bound: a superseded slower demo can never again
  become a faster row's watch link) AND the cf6cd12 momgrab/momwatch/momindex/
  ksfimport batch that had sat undeployed since e11084c (momwatch's change is
  itself a logging fix -- a handler on surfd's logger so the per-tick import
  stops reading as a restart).  Nine suites green in the stage including the new
  `test_momboards` (9 checks), all 54 files hash-matched the commit, master
  2479950 unchanged (SIGHUP to the pid, never the unit), `surfd ready` 04:46:46,
  `/health {"ok":true,"lobbies":12}`, 2 processes.  Backups
  `*.pred42165e-20261005-154500` and `data/surfd.db.bak-d42165e-20261005-154500`.

  `df00b61` to /srv/nvme/surfd at 2026-10-05 04:59 UTC -- the player pages
  (561bb1e) and the test isolation they needed.  561bb1e itself stopped in the
  stage, nothing installed: `test_join` counted the Pi's 66 real local zones,
  because SURFD_ZONES_LOCAL defaults beside the live run tree.  56 of the
  commit's 58 surfd files hash-match (README.md and ftesurf@.service differ as
  before), master 2479950 SIGHUP'd, `surfd ready` 04:59:40, `/health` ok.
  `data/people.json` (0600, 10 MB) was then built by one local request (8.6 s
  on 127.0.0.1:8084) so no visitor paid the first build behind nginx's 5 s;
  deploys keep it, only `people_reset()` or a fresh install removes it.
  Through nginx: profiles 1.77 / 0.56 / 0.47 s, directory 0.04 s.  Backups
  `*.predf00b61-20261005-155751`, `data/surfd.db.bak-df00b61-20261005-155751`.

  `baadc73` to /srv/nvme/surfd at 2026-10-05 05:58 UTC -- the review fixes to
  561bb1e (per-writer snapshot temp names, a single-flight cold start, no older
  directory over a newer one, a stamp ahead of the clock counted stale, the
  thread-start guard, "Show more" by prefix via `limit`, and the maps cache's
  empty answer for 300 s after a boot).  Live hashes matched df00b61 at 05:56.
  After: a profile 2.66 s on the new worker's first request (snapshot load),
  `limit=200` 0.62 s, people.json rewritten by the background rebuild at
  05:59:13 (0600, no temp left).  Backups `*.prebaadc73-20261005-165654`,
  `data/surfd.db.bak-baadc73-20261005-165654`.

  `8cd56ee` to /srv/nvme/surfd at 2026-10-05 06:34 UTC -- three submit-path
  fixes out of the b818e8a review: adopt only a `kind='run'` replay's tier (a
  trusted post naming a momindex leaf can no longer file a board row under
  `momentum` nor unlink the imported row's demo), the hidden `tier@runid` slot
  now checks the stage cap (a rejected run cannot park stages past it), and the
  leg-0 cap scan runs BEFORE the write lock instead of holding it 0.37 s on every
  first finish (the scan is still 0.37 s -- BACKLOG keeps the index/count latency
  follow-up, with the teeth each has).  Nine suites green in the stage including
  the new falsifiers test_replays s15 and test_board s23/s24, all 54 files
  hash-matched the commit, master 2479950 SIGHUP'd, `surfd ready` 06:34:18,
  `/health {"ok":true,"lobbies":12}`, 2 processes.  Backups
  `*.pre8cd56ee-20261005-173227` and `data/surfd.db.bak-8cd56ee-20261005-173227`.

  `a254da2` to /srv/nvme/surfd at 2026-10-05 07:30 UTC -- the board database and
  its backups are the owner's alone (`runs.player` is a guid, and a guid is what a
  keyed lobby authenticates a submit by; sqlite creates the db 0644 & ~umask and
  the Pi's umask was 022).  Nine suites green in the stage including
  `test_surfd` section 10, all 54 files hash-matched the commit, master 2479950
  SIGHUP'd, worker re-forked to 1226126, `surfd ready` 07:30:49,
  `/health {"ok":true,"lobbies":12}`, `/board/api/map` 200.  Backups
  `*.prea254da2-20261005-182858` and `data/surfd.db.bak-a254da2-20261005-182858`
  (the first one this script wrote at mode 600 -- it chmods and then FAILS if the
  backup is not 600).  Step 7 of the deploy now reports the backups and tightens
  any loose `surfd.db*`: `OURS=12 files, 8236 MiB`, `HANDMADE=24 files, 1814 MiB
  (never pruned here)`, `TIGHTENED=36` on the run that fixed the existing copies
  (0 on the deploy, which found none left), `STILL_LOOSE=0`.  Pruning needs
  `-KeepDbBackups N` and is OFF by default -- 9.3 GB of copies on a volume at 88%
  is Lex's decision, in BACKLOG.
  PROVEN LIVE THREE WAYS, because a mode read once is not a mode kept: the
  WORKER's `/proc/<pid>/status` reads `Umask: 0077` while the MASTER's still reads
  `0022` (a SIGHUP re-forks the worker and the app is imported there, so the
  master keeps the umask run.sh started it with until a full restart -- it writes
  nothing sensitive); the db and its newest backup both `stat` 600; and a db
  `chmod 644`'d BY HAND was back to 600 after ONE request that connects, which is
  `_harden_db_files()` in production rather than in a test.  Still open and in
  BACKLOG with its measurement: the GAME's data tree, 10,938 of 10,938 files 0644
  under `game/ftesurf/data` with the guid IN THE `.rec` FILENAME, so a directory
  listing alone leaks it and file modes cannot fix it (the lobby unit says
  `UMask=0022`).

  `migrate()` runs on EVERY `import surfd`, including sweep.py's cron import,
  so each schema step must be idempotent and safe to race. admin.py must not
  import surfd; surfd injects what it needs.

  `sweep.py`'s receipt step (schema 7/8: `receipts`, `pubkeys`, `sweepmeta`) imports
  `rcptcheck`/`reccheck`/`ed25519` from `<SURFD_GAME>/tools` (`SURFD_TOOLS`),
  and the import is INSIDE the function on purpose: a host without them must
  keep running the verification it has run since Patch 349. Deploy those three
  beside the game, not beside surfd. Both new tables are store-only -- nothing
  in `VER_SQL` reads them and no badge moves.

  DEPLOY surfd/ AND tools/ IN THE SAME PASS, and check the sweep log after. On
  2026-09-21 the surfd half went up alone and the receipt step failed on every
  cron tick for three hours with `AttributeError("'Receipt' object has no
  attribute 'angles'")` -- a new `sweep.py` calling a `rcptcheck.py` that
  predated the function. The try/except held (the Patch 349 verdict sweep ran
  on the same line, every time) and `receipts` simply stayed at 0 rows, which
  is exactly why it is easy to miss: nothing is down, nothing is loud. Read
  `/srv/nvme/surfd/logs/sweep.log` for `receipt step failed`, and
  `sweep.py --dry-run` for the unread count.
  A tools-only deploy needs NO `kill -HUP`: surfd does not import them, so the
  PID and the lobbies are untouched. Copy under `flock /tmp/surfd-sweep.lock`
  with `install` + `mv` so no cron import can see a half-written file.
  READERS BEFORE CLIENTS. Engine Patch 468 journals carry a 12-field `end`,
  five-field `p` records and a `touchpad` device type. A `hidcheck.py` older
  than efc4627 reads every one of them as "never closed"; efc4627 passes a
  journal whose pad never fired and faults every `p` line of one that did;
  fde8420 is the floor (the length sets are strict on purpose). Deploy
  tools/ to every host that reads journals before any 468 client exists.

  **DEPLOYED 2026-10-05 02:43 UTC (game repo `24b50bf`).** The rule above had
  not been followed: `hidcheck.py` was ABSENT from the Pi and `reccheck.py` /
  `rcptcheck.py` were at their 2026-09-21 and 2026-10-03 blobs, i.e. before Patch
  484. All four are now at HEAD's blobs, verified by `git hash-object` ON THE PI
  (`493097d8`, `85fcfc68`, `fbb8c624`, `bb522ba4`) and not by size or mtime.
  Backups: `*.pre490-20261005-024331`. Installed under `flock
  /tmp/surfd-sweep.lock` with `install` + `mv`, `__pycache__` cleared, no surfd
  reload (the sweep re-imports per invocation, so a tools-only deploy needs no
  `kill -HUP`).
  WHAT THE ABSENCE COST: less than the rule implies, and it is worth knowing why
  rather than assuming the worst. `sweep.py` imports only `rcptcheck`, which
  imports `reccheck` and `hidcheck` LAZILY and inside a try, so a missing
  `hidcheck` degraded `r.journal` to "" plus a note instead of taking the receipt
  step down — and the fleet holds `0 hid` in `data/evidence/`, so nothing was
  actually going unchecked. The stale `reccheck` was the live one: Patch 477's
  `pin` warp kind is missing from its `WARP_KINDS_V9`, so a pinned run's warp
  reads as an unknown kind. Verified after: `sweep.py --dry-run` exit 0 with no
  receipt-step failure, all four import, and `rcptcheck.py data/evidence` checks
  19 receipts of which **2 fault** — both on surf_4am, both the KNOWN save-lock
  hold fault documented below at 33-41% of one-frame ticks (one reads 45.8% of
  155), not a regression from this deploy. 18 of the 19 commit to evidence that is
  not on the host, which `rcptcheck` calls absent rather than a fault.
  **A NOTE ON VERIFYING A DEPLOY: two ssh calls made back to back can read the
  directory in different states, and the one that ran second is not the one that
  is right.** The install and an independent check were issued together; the check
  reported `hidcheck.py ABSENT` and the pre-deploy hashes while the install
  reported success. A third, single-call read settled it — all four present at
  HEAD's hashes. Settle a contradiction with one authoritative read rather than
  believing either of the two that disagree.

  Schema 8 (Patch 422, first key wins) is admin-only too. Three things an
  operator must know:
  - `receipts_v8()` runs on EVERY migrate() -- a repair, not a step. It marks
    rows a pre-8 sweep wrote (`signed_at = 0`) stale = 1 (signature unknown,
    not judged) and voids the watermark. `--reread-receipts` marks stale = 2:
    the signature is known and is still judged until the re-read replaces it.
  - "unsigned" is judged only below `sweepmeta.receipts_through` (the last
    complete receipt pass) less 300 s, so a stalled receipt step pauses it
    instead of flagging every signer. The admin runs page says so in red after
    an hour: that note, not the flag count, is how a broken step shows now.
  - Patch 501: initial receipt/sibling-digest I/O alone defers the read, like
    a PENDING reread, rather than storing a permanent evidence FAULT. A separate
    measured signature/recording/digest fault survives sibling I/O; a pending
    join's recovery cannot clear it. Partial stale rereads preserve old content
    joins and the stale retry flag; their automatic completion also retains
    the measured primary fault (`receipt_partial:` metadata). Unknown first-stat
    paths still get a queue identity; disappearance cannot restore coverage.
    Failed reads consume the pass budget, with
    a durable per-path queue: arrivals/attempts go to the tail. An array cursor
    is NOT stable under compaction and arrivals; it still starved a stale row.
    Coverage uses ALL unread fresh receipts, independently of attempt order,
    or stays unchanged when an age is unknown. Enumerate both
    directory levels explicitly: glob silently hides unreadable map directories.
    `test_sweep.py` exercises failure/recovery, persistent-failure progress and
    source removal between a measured fault and an unmeasured join's recovery.
    Repeating `--reread-receipts` does not supersede an in-flight partial read;
    complete it before requesting a new reinterpretation. Permanent lost
    unobserved receipts pause unsigned coverage until operator reconciliation.
  - P501 deployed from clean reviewed/published `4f16963` on 2026-10-06 at
    07:52:56 UTC: 262 sweep checks, 306 reader checks, nine app suites pass on
    the Pi. Installed ONLY sweep/test_sweep and the matching four reader files
    under the sweep lock, with DB/file backups and all six blob hashes verified.
    The old live reader API lacked fields the sweeper expected (50 exceptions
    in its last 100 log lines). New live read ACTED: 1 receipt / 0 faults, rows
    19 -> 20, coverage 1791203401 -> 1791272575; health stayed ok / 12 lobbies.
    No progs/lobby swap or web reload. The 19 earlier receipt rows were not
    automatically reread; paired deployment is NOT historical recalibration.
  - Patch 503: receipt hash and content checks share captured `.view`/`.hid`
    bytes, including captured absence/read errors; `.rec` runid/nonces/angles
    share the selected handle's decoded observation. Parsers accept keyword-only
    `data=` without reopening the path and retain text-mode UTF-8 replacement
    and universal-newline behavior. Never hash a path and then reopen it to
    claim its content was signed. `tools/test_rcptcheck.py` swaps files AFTER
    the first read closes, with controls proving replacement and later digest
    rejection. This is one observation, not filesystem atomicity, persisted
    receipt identity, late-arrival scheduling or hardware attestation. Deploy
    rcptcheck/reccheck/hidcheck together from a clean inspected commit; no
    automatic historical reread or detector/policy change belongs in this slice.
    Selected `.rec` tail I/O must defer (not become ordinary absence); unknown
    final-session nonce cannot be inferred from its readable header. Known
    sibling presence can prove a missing-digest contradiction even when reading
    bytes fails; unknown presence cannot. Final reviewed `4303a0e` deployed on
    2026-10-06 09:52:46 UTC: 74 snapshot controls, 262 sweep, 306 reader and
    263 HID checks all pass; nine app suites plus all three reader suites pass
    on the Pi. Four reader/crypto files match the commit on the Pi and both
    Windows installs. Installed caller ACTED on generated signed HID (OK) and
    changed-digest control (FAULT), without storing test evidence; real receipt
    step read 0. This is integration verification, not new fleet calibration.
  - Patch 510: missing-source readiness is a captured observation, not a later
    filesystem inference. A successful full read can establish a missing-rec
    wait; a late-view completion may RETAIN that wait but cannot create it.
    Initial candidate: checked rec -> prune rec -> late view -> new rec wait ->
    returned/replaced rec automatically judged. Review exposed that excluded
    completed-source rearm despite 212 passing checks. Four new scope checks
    fail on the candidate; corrected suite has 227 passes. Both completed and
    historical-unknown cases must prove the direct reader's contradiction and
    an explicit full reread ACT, not just assert scheduler silence.
    `surfd/sweep.py:receipt_step` now keeps rec/view/HID turns separate; persisted
    co-ready order is rec/view/rec/HID, with bounded attempts and row fairness.
    Discovery headers are hints only; selected bytes and original receipt binding
    authorize joins. A checked view is hashed again to bind a newly possible rec
    pair, never to schedule completed-source replacements. Unknown readiness and
    initial partial observations still need a completed explicit full read.
    Frozen published b1be008 shipped only sweep/new recording suite on the Pi
    at 2026-10-06 16:23:30 UTC after both re-review lenses and 18 Linux suites.
    Installed temporary/in-memory controls ACTED; real pass 0 reads/faults and
    two bound rows unchanged, reload/health proved. No engine/progs/schema/reader
    or detector-policy change. Header discovery cost at fleet scale is unmeasured.
  - test_admin runs `node --check` on the admin pages' scripts (f19d477 shipped
    one that never ran). The Pi has no node and prints a skip, so run it on
    Windows after editing a template. On Windows its `amplification guard` and
    `three snapshots` rcon checks fail (UDP to a closed port resets instead of
    timing out); they pass on the Pi.

  BUMPING `SCHEMA_VERSION` BREAKS ANY SUITE THAT PINS THE LITERAL. 6 -> 7 broke
  test_join and test_replays, which know nothing about receipts; they compare
  the upgrade path to where a fresh database lands now. Do the same in a new
  one. test_board went unbumped for a day; it has one `HEAD_SCHEMA` now.

  Patches 424/425 (no schema bump; `replays_bound()` runs on every migrate):
  - `replays.bound` is 1 when the replay was filed against its file (header
    matches runid, map, track, leg, flags, tickrate). -1 means "not assessed"
    and is resolved from the disk by the next migrate, i.e. the next cron sweep;
    a row whose file cannot be read stays -1 until it can. After a deploy, check
    that the live rows came out 1: `SELECT kind, bound, COUNT(*) FROM replays
    GROUP BY 1, 2`.
    A reject hides the stage times of every bound replay's run.
  - `replays.sha` is the file's sha256 at filing and `sha_at` the `submitted`
    it belongs to. A re-post is new evidence only if player, ticks, bytes or a
    known, current sha differ; an unknown sha ('') falls back to "the header
    names another run". `_file_sha` hashes only the file whose header was just
    read, and caches by (path, inode, size, mtime_ns).
  - Tiers ending `@<runid>` are a rejected run's hidden stage times, and
    `^<its own runid>` (`^r<id>` recorded, `^-<submitted>` no runid) a time
    waiting behind a better one; neither reaches a public board. Reviews move
    them. Do not delete them by hand: a clear gives them back.
  - Patch 426's arms: `cfg/test/p426{cl,bcl,ccl,dcl}.cfg` against `p426sv.cfg`
    and the stub `b65stub.py cert 8131`. p426dcl needs `+set sv_mintic 0.1`
    on the server to make its same-physics-step race frequent (1 in 21 at the
    default step).
  - Before 425, test_board wrote `.rec` files into the DEFAULT `SURFD_RUNS`, the
    live run tree. It sets its own temp dir now. Point every suite at one.

  And the live database is `<SURFD_HOME>/data/surfd.db`, NOT
  `<SURFD_HOME>/surfd.db` -- a stray empty file at the second path has existed
  since 2026-09-21 and is not it.

### Observer deployment gates: resolve the live tool and bound verification

Measured 2026-10-06, frozen game `bf5153d` (P521/P522 and the tooling-only
`4c519b9` runtime installer). The old missing-similarity-tool note above was stale:
the installed recsim.py matched published `34c2984` exactly, with two native rows
and one stored pair. Its diff to the current canonical source was comments only.
Use the explicit resolved tool path and inspected predecessor hash; do not
blindly overwrite an unexpected file. `tools/simcheck_runtime.py` packages only
clean exact-commit bytes and installs one fixed path, dry-run by default, with
paired-reader hashes, predecessor guards and rollback. Installed long/short
controls passed on the Pi and both Windows installs; this is not new activation,
complete pair coverage, hardware provenance or calibration.

Two private post-swap gates failed while the destination hashes were already
correct. First, `_recsim()` returns `(module, loaded_path)` on success, not an
empty reason: check the path, do not reject a loaded module for its path string.
Second, a verification snapshot attempted `SELECT * FROM runs` into Python: the
live board had over three million rows and the probe was killed. Kernel evidence
did not establish the kill's cause; do not claim a confirmed OOM. Health stayed
at 12 lobbies. A replacement gate denied protected-table DML with SQLite's
authorizer (a denied no-op proves the guard acted), compared bounded metadata and
scalar board counts, and reported 0.093 s for the collector/post-history interval
with no new stored pairs. Never materialize the board to prove an observer did
not modify it.

Finish only missing controls after rechecking frozen destinations and rollback
copies; do not recopy source or overwrite the first backup. All 26 Linux suites
passed, installed API/storage/path controls acted, then master-preserving worker
replacement/ready log and health completed at 2026-10-06T23:42:33Z. Linux Node is
absent: actual DOM controls passed on Windows, not in a live browser. No automatic
historical metrics reconstruction, engine/progs/config/threshold/badge change.

### Comparison-reader deployment: P524-526

Frozen game `4f5c47f` deployed tools-only on 2026-10-07 at 00:27:07 UTC.
Only the fixed `tools/census/recsim.py` runtime changed on the Pi and both
Windows installs. Use the Git-pinned installer, paired-reader and predecessor
hash guards, and retain its `recsim.py.pre-<sha12>` rollback copies. Destination
hashes match the commit; nine Linux stage suites and installed long/short,
malformed/unreadable/no-input/measured-zero controls pass. The actual Pi caller
resolves the installed reader and a real pair is measured read-only. Protected
table counts and binary/progs/config/app/process state remain unchanged;
health stays OK with 12 lobbies. No reload or lobby restart is needed.

A private post-swap probe called a nonexistent locator after the tool was
already installed. Recheck hashes and the original backup, repair the probe to
use the actual shared locator with an isolated app HOME/DB, and finish missing
gates only: never recopy a correct destination or overwrite the first backup.
Isolated secretless app logs are not live heartbeat failures. Historical rows
are not reclassified; this does not establish pair coverage or calibration.


### Cleanup copies without crossing into live content

Measured Windows/NanoPi cleanup pitfalls (2026-10-08), not a product patch:

- **Windows `DirEntry.stat()` is not canonical identity.** Its cached results
  can have zero `st_dev`, `st_ino` and `st_nlink` while `Path.lstat()` returns
  the real values. Use no-follow `lstat` for reparse-point, hardlink and
  before/after identity checks. A real junction control must prove rejection
  and that unlinking only the junction leaves a target sentinel intact.
- **POSIX unlink changes surviving hardlink aliases' ctime.** A strict guard
  can stop after deleting one alias even though the other name's bytes have
  not changed. Do not broadly ignore ctime: accept only an inode this exact
  transaction already unlinked, with identical device/inode, mode, size and
  mtime, plus a fresh hash matching the preserved archive. After a partial
  stop, rehash/replan the remaining entries; never blindly retry or force.
- Archive and verify every ignored artifact before removing a published-clean
  worktree. Preserve dirty/untracked files, unique history, player data and
  owner configs. Check locks, descendants and process executable/args/cwd.
  Use normal `git worktree remove`; retain branch/history recovery.
- For test overlays, archive links as inert metadata and delete via anchored
  directory descriptors with `O_NOFOLLOW`. Reject linked roots and every
  mount boundary. Acted controls need a directory link, a regular hardlink
  pair and a target sentinel; the sentinel must survive the actual removal.
- Compare live map/static-file metadata, config/progs/binary hashes, existing
  backup names and lobby PIDs before/after. Separate new live data from loss:
  directory timestamps can change when new files arrive while every existing
  file remains unchanged. Keep raw inventories, process args and recovery
  archives private; never publish them as verification output.


## Chat and `say` — the contract, and it changed in 342

Getting this wrong kills the restart keys silently, so it gets its own section.

- `say` does NOT arrive via `registercommand` (engine commands beat
  CSQC_ConsoleCommand). The engine offers it to the `CSQC_ChatSay(args, team)`
  globalfunction before sending (patch 341, `zqtp.c`).
- BARE `say` opens the draft; `say <text>` is DECLINED so CL_Say sends it
  (patch 342). `say_team` is declined outright (no teams here), and `/me`
  (`CL_Say`'s `extra`) never reaches the hook at all. Taking text back breaks
  `bind r "say !r"` / `!m` in `default.cfg` (and `defaultuser.cfg`) —
  i.e. the restart keys — and the `cfg/test` fixtures that drive runs with it
  (seven today: b26a, b48d, b57eclipse, b57stage, b58ab, b86a, b86b).
- THE MESSAGE MUST REACH THE SERVER AS ONE ARGUMENT: SV_ParseClientCommand reads
  the whole thing from `argv(1)` and splits on the first space itself. CL_Say
  wraps it in the one quote pair SV_Say strips (exactly one, `sv_user.c:4385`),
  so plain `say !s 2` keeps its number; `cmd say !s 2` arrives as two arguments
  and the number is LOST (stage 0, silently). Cfgs, fixtures and the menu
  self-test use plain `say`. Corollary: a `%S`-quoted `say` line ships a second
  quote pair and leaves visible quotes in everybody's chat.
- The DRAFT's own submit is the exception and must stay `cmd say`: `set
  cl_safetmp %S` then `cmd say $cl_safetmp` — the buffer's `;` split is
  quote-aware, expansion runs after the split, and `cmd` bypasses CL_Say so the
  hook cannot re-enter itself. The cost is that the draft cannot send `!s N`
  (the tail splits); `!r`/`!m` are unaffected.
- Key presses reach CSQC_InputEvent BEFORE their bind runs, so chat keys are
  intercepted by stealing the key whose `getkeybind()` is `messagemode`,
  `messagemode2` or `chat_say` (cl_chat.qc:533) — not by claiming the command.
  `toggleconsole` is the one key a live draft gives back (it abandons the draft).
- Hooking any engine command intercepts YOUR OWN callers. Audit cfgs, fixtures
  and internal submitters before hooking one.
- Harness handles (Patch 370): `chat_say <text>` opens the draft prefilled
  (bare `chat_say` is unchanged); `chat_rows` prints the last draw's wrapped
  rows, widths and drawn y (`^` doubled so the log keeps codes). The chatbox
  wraps with the engine's markup units (`Chat_CodeLen`), so a new markup form
  in COM_ParseFunString needs a line there too.
- SYSTEM CHAT LINES (Patch 371) are PRINT_CHAT spelled `^C word:^7 text\n`
  (`server:`, `finish:`, `board:`, `lobby:`, `vote:`): a `^` right after the
  colon means the engine can never read one as a player's `name: ` chat
  (zqtp.c:2288). Send to the others with `Lobby_SayOthers`, name players with
  `Lobby_ChatName`, pass player text through `Lobby_Clean`. The server log's
  copy reads `said> ...` (dprint, log_developer) -- on a listen server it shares
  the client's log, so grep chat lines by what follows the timestamp.
- A JOIN IS PER CONNECTION: the `*ann` userinfo star key survives changelevel
  and map_restart (ClientConnect runs again on both; parms would not survive
  map_restart). Your own finish line is client-side (cl_banner.qc Bn_ChatSay,
  `banner chat`), so a harness client needs `menu_restart` + `ui_close` or
  notmenu skips Banner_Frame and no line is ever said.

## Map clock and votes (Patch 372)

- The rotation's deadline, its state, the next map and any running vote go
  out as serverinfo (grammar: sh_defs.qc, VOTE_*), written only by sv_vote.qc
  Vote_Publish. A change a vote decides is always EXECUTED BY Lobby_Cycle
  (lobby_vt_force / lobby_vt_next): a changelevel issued from a client command
  runs before StartFrame clears lobby_cyc_moving, and the runs it interrupts
  would park as `server` instead of `rotate`.
- Harness handles: `vote fake clock|next|open|label|votec|off` overrides
  serverinfo on the client only (HUD_SK); `vote key <scan> <0|1>` runs the
  whole CSQC_InputEvent chain, so it proves handler ORDER; `vote status`
  (client) and `cmd vote` (server) print both sides.
- A test that lowers lobby_cycle must raise it again before a map change: on
  the next map a short period opens the end-of-map vote on its first frame.

## Linux build, test rig and release (Patches 386-389, 0.1.11)

- **BEFORE CUTTING ANYTHING: does the feature you are shipping READ A GENERATED
  FILE?** If so it has to be named in `$ShipGameFiles` (`release.ps1:192`), which
  is an allowlist and not a glob. `ftesurf/data/*` is gitignored, so such a file
  exists on the build box and nowhere else, and the feature ships compiled-in,
  working and invisible. 0.1.15 exists because 0.1.14 did exactly that with
  `data/mapdl.txt`. Full account under the map-download section above.
- BUILD: `pwsh -NoProfile -File tools\linux\build-linux.ps1 -Commit <engine sha>
  -ExpectSonames -OutName linux-build-<x>` builds in a Debian bullseye chroot
  inside WSL `Ubuntu-22.04` (made once by `tools/linux/chroot-setup.sh`), from a
  fresh clone, offline, from `tarballs.sha256`. `-Commit` defaults to ENGINE.txt's
  pin, which is the right answer for a release. Output `dist\<OutName>\` with
  BUILDINFO.txt; `gates.sh` G1-G10 must all PASS (libc/libm only, glibc <= 2.31,
  zstd in the plugin -- Momentum's VTF 7.6 -- versioned sonames, clean stamp).
  `makelibs` runs at -j1: its two-target rules race under -j. Takes ~90 s when the
  chroot and its clone are warm.
- A WINDOWS EXE'S STAMP IS BAKED INTO OBJECTS, AND THEY DO NOT REBUILD WHEN
  `SVN_VERSION` CHANGES. 0.1.12 shipped an exe carrying TWO stamps
  (`ga72183e6b` from a .rc object, `g2b685797b-dirty` from a later sv_user.c), so
  nothing could say which commit it was and gate L2 refused to publish a Linux
  drop beside it. To re-stamp: find the objects that still hold the old string
  (`grep -rl` over `engine/release/**/*.o`), delete them, `touch client/sys_win.c
  common/common.c server/sv_user.c`, and rebuild with
  `SVN_VERSION=git-<count>-<describe> SVN_DATE=2026-09-23` passed ON MAKE'S
  COMMAND LINE (build.ps1's `$env:` does not reach it). Then read the stamps back
  out of the binary -- do not trust the build having run.
- TWO MSYS2 BUILD TRAPS, both environment rather than code: `make` inherits
  `TMP=/tmp`, and Windows gcc then dies with `Cannot create temporary file in
  C:\WINDOWS\: Permission denied` -- pass `TMP="C:\msys64\tmp"
  TEMP="C:\msys64\tmp"`. And an agent bash's `/tmp` is
  `C:\Users\Lex\AppData\Local\Temp`, NOT `/c/msys64/tmp`, so a scratch file
  written by one is invisible to the other.
- Call `wsl.exe -d <distro> --exec ...` from PowerShell. Git Bash rewrites
  /mnt/c paths, and without `--exec` the login shell expands `$vars`.
- A Windows exe built from a `git worktree` carries NO revision stamp (the
  Makefile tests `-d .git`, a file in a worktree): set `$env:SVN_VERSION =
  git-<rev-list --count + 29>-<describe --long --always>` and `$env:SVN_DATE`
  before `build.ps1 -Engine -Full -FteRoot <worktree>`.
  SET THEM FOR THE MAIN CHECKOUT TOO WHEN CUTTING A RELEASE. The Makefile stamps
  with `git describe --dirty` run under msys2, which sees the CRLF working copy
  as modified and writes `-dirty` even when Windows `git status` is clean --
  release gate L2 then refuses the drop ("names no clean commit"). `$env:SVN_DATE`
  MUST HAVE NO SPACES (`%cs`, i.e. `2026-09-21`): it reaches CFLAGS unquoted, and
  `Sep 21 2026` makes the compiler treat `21` and `2026` as linker inputs.
- RELEASE: `release.ps1 -Bump patch -BuildNumber <n> -Linux dist\<drop>`.
  `-BuildNumber` is REQUIRED unless a `Build NN:` commit is inside the last 200
  (the script derives the number from a subject and hard-fails without it; the
  last one, `QC build 89` f4b5051, is 224 back as of Patch 441 -- re-measure with
  `git rev-list --count HEAD ^f4b5051` rather than trusting a number here, and
  note it was 219 when this line was written, not the 228 it claimed). The Linux drop and ftesurf64.exe must come from the same
  engine commit (gate L2); build.ps1 recompiles the progs from `src`, so copy the
  lobby-deployed .dat back in before releasing. `ENGINE.txt`'s pin block is a gate
  too -- bump `commit`, `patch` and `qcbuild` with the engine or the run stops
  there.
  - STEP 18 USED TO FAIL ON WINDOWS. The fix in 6aaeebb did NOT work and was
    never run: it passed `-LiteralPath` to scp, which is a PowerShell parameter
    name, and a native exe answers `scp: unknown option -- L` and exits 1 -- the
    same failure at the same point, after the same unre-runnable uploads. Fixed
    for real in Patch 441 (a bare path argument, the shape the loop above it
    already used), and that shape was run against the Pi rather than reasoned
    about. The original defect: `scp -r "$pageDir\*"`
    passes the literal `*`, so the page never went up and the run threw AFTER both
    archives were uploaded -- the documented unre-runnable state, hit again on
    0.1.13, whose page was therefore deployed by hand: `scp dist\site-<v>\<each
    file>` to the Pi's `ftesurf-site/.incoming/<v>/`, the three site scripts
    beside them, then `sh publish.sh <v>` there. Check
    https://proto.bar/ftesurf/version.json afterwards, and download both archives
    back and compare bytes/md5/sha256 against the receipt -- the script's own
    "origin: size and md5 match" is the uploader's word, not the reader's.
- ONLY THE LOBBY PORTS ARE FORWARDED. A one-off server on a spare port is
  reachable from the LAN address (192.168.1.102), not from 180.150.62.57.
- TEST RIG: WSL `Debian` is a runtime-only player machine (user `surf`;
  `tools/linux/rig-setup.sh`), driven by `rig-install.sh` / `rig-run.sh` /
  `rig-steam.sh` / `rig-sv.sh`. Case tests need ext4 (`/home/surf/fakesteam`,
  `rig-fakesteam.sh`): /mnt/c is case-insensitive, and so slow that a lobby join
  over it timed out. A cfg's own `log_name` wins and logs APPEND: read the tail.
- Linux engine facts: loose files fold case ONLY through the name hash
  (fs_cache); a stale hash or an FSLF_IGNOREPURE lookup (`exec`) is exact-case.
  Linux runs are UNRANKED during the beta (Patch 389: SV_ProfileBroken demotes a
  profile without IPH_RAW; delete those three lines to lift it). Patch 387's
  entry lists what Linux input evidence cannot see.

## Source live-water depth (Patch 541)

`$refractiondepth` must set both HASREFRACT and HASREFRACTDEPTH; a sampler
read returning zero did not prove the pass acted. The fixed-camera raw-depth
control distinguished an absent attachment from real scene depth. Depth
capture avoids the colour-only oblique projection: reconstruct from the actual
m_projection, not near/far assumptions. In mode 1 leave sampler slot 1 null so
adding depth at slot 2 does not accidentally request a planar reflection.

For cloned BSP material controls, copy the map's actual `dep <map> <addon>`
rows, not invented CSV rows. Missing dependencies made sky/brush controls
invalid. One launch per map gave stable hundreds-of-draws readback; chained
map loads took almost 30 seconds and could screenshot a loading frame despite
waitmap/waitms. Prove contents at the camera: a point under a wet-looking slab
can be solid. Neutral-normal, fog-range and no-fog controls must visibly act.
Source water is still an approximation; modes 0/3/4 remain distinct choices.

## Source water and material menu (Patch 523)

- `hl2_water` defaults to 3. Mode 4 is an opt-in capture-free approximation:
  animated normals, alpha blending, fog colour and baked-cubemap reflection.
  It has no depth sampler, live reflection or depth-correct above-water fog.
  Modes 1/2 still capture refraction; 2 also captures reflection. Do not call
  mode 1 capture-free, or claim GPU/portable FPS from local wall-frame timings.
- P543: shader reload must compare old/new sort after successful parsed VMT
  and shader-file paths too, not only generator fallback. Early `continue`
  skipped resort: cold flat water worked while a live Full -> Flat switch
  drew before the floor. Sampler-free flat colour avoids GLSLONLY's missing
  compatibility progless path. Water Bayer cells floor gl_FragCoord (pixel
  centres are .5); glass intentionally keeps its older path. Coverage knobs
  now have narrow renderer-owned shader policies, not a wider plugin flag mask.
  `r_refractreflect_scale` is cached into material portalfboscale: change plus
  `flushshaders` and prove actual capture dimensions before timing. A no-flush
  scale arm is inert and proves nothing about CPU versus GPU cost.
- Plugin_GetCvar masks CVAR_SHADERSYSTEM. P523 opted water alone into the
  renderer's shader-rebuild policy; P543 also opts in the two coverage knobs. Cvar_Get2 does not retrofit that flag onto an
  existing variable. Preserve default/early user value/archive flags and test
  both initialization orders rather than widening every plugin flag at once.
- Patch 528 gates the live 0..4 row on LOCAL extension
  `FTE_CSQC_HL2_WATER_BUDGET`: native live policy, programmable OpenGL and a
  loaded plugin with embedded budget source are required. Cvar existence/value
  cannot substitute. Older engines, missing/older plugins and unverified
  backends retain 0..3 with `*`. Unsupported archived 4 becomes 3 and queues
  `flushshaders`, because pre-CSQC BSP generation may already have cached 4.
  Refresh at initialization/menu command/renderer restart; preserve milk's
  target invalidation. Availability does not promise GPU compilation success.
  Native P523 without the new extension conservatively uses the legacy row.
- Compatibility gates use actual old/new EXEs and both mixed plugin pairs,
  not a fake "force old" cvar. Legacy cycles need the advertised rebuild;
  capable cycles do not. Test the saved result as well as the readback. A
  matching menu fixture does not replace full downloadable-product CSQC tests.
- Graphics material rows carry `*` when their generated shader does not update
  automatically. Glass 0 is Translucent, not Opaque. `retry` can reuse cached
  BSP data: it is not a promise that every map-time setting gets reread. Keep
  that distinction in status and footer; readback alone is not rendered action.
- Water gates must show actual camera/draw/index submission and loaded programs
  plus full/cheap live-capture positive controls. Production builds contain no
  diagnostic hooks. Test menu cycling through 4, an explicit isolated archive
  save and fresh-process restore, and early startup override. Use fresh log
  names and waitms, not frame-count waits. Test the full product CSQC too, not
  only a standalone menu fixture; the latter intentionally omits gameplay.
- Fresh engine worktrees lack ignored SDK headers/libraries. Copy the existing
  dependency bundle into the owned worktree before building. Compare warnings
  against an identically configured baseline; existing warnings are not new.
  Build the shader generator from a relative source path so its generated
  banner does not embed a private worktree path in public source. The generated
  `mat_vmt_progs.h` must agree with the GLSL included by plugins/hl2/Makefile.
- `tools/test_water_menu.py --engine <checkout>` checks source contracts, not
  rendering. `test/p523water.cfg` is an optional isolated runtime menu smoke.
  Depth fog/capture sharing, other menu rows, glass and particle coverage retain
  their own acting-control gates in BACKLOG; this water patch does not close them.

## Source base content without a separate HL2 install — 2026-10-12

- `momentum/gameinfo.txt` mounts `mount/hl2_dir.vpk` shipped with Momentum;
  its external CS:GO mount is appid **4465480**, CS:GO Legacy (Source 1).
  CS2's `game/csgo` Source 2 content is not that pack. The standalone legacy
  install on this machine is `steamapps/common/csgo legacy/csgo`; the older
  `Counter-Strike Global Offensive/csgo` copy also remains; this is also the
  CS2 `csgo_legacy` beta layout. Before P679 FTESurf named only that older
  folder in `tools/mapdeps.py:ADDONS`.
- Before P679, `fs_addons.default.txt` mounted standalone HL2, not Momentum's
  shared pack. The dependency scanner assumed HL2 in `MOUNTED` and could not
  diagnose a player's absent base pack. With only Momentum/momentum and CS:S mounted,
  surf_666 reported **31 unresolved materials** and checkerboard walls/ceiling.
  Adding Momentum/mount at boot resolved brickfloor001a.vmt and
  concretefloor014a.vtf from hl2_dir.vpk; screenshots restored those surfaces,
  without any Half-Life 2 path. A separate HL2 arm restored them too.
- Existing-install workaround: `fs_load "steam:Momentum Mod Playtest/mount"`,
  then **quit and restart FTESurf**. Verified that fs_load saved the mount and
  a fresh process resolved the same files. A map reload alone kept the old
  missing-material warning and some checker shaders: locating a file after
  mounting does not prove previously generated shaders were replaced.
- This removes the separate HL2 requirement only when Momentum is installed.
  It does not make CS:GO a substitute for all CS:S assets: the offline scan
  with Momentum's HL2 pack and legacy CS:GO still missed CS:S paths. Three
  texture references remained unresolved even with CS:S plus standalone HL2;
  the restored screenshots still contained some checkerboards. Do not promise
  that mounting fixes every surface. P679 now mounts only hl2_dir.vpk
  automatically after configured addons, including for existing mount lists;
  old Momentum/mount dependency specs also select only that pack. No owner
  fs_addons.txt rewrite or generated mapdeps refresh is required. Other-game
  placeholder VPKs are excluded. The scanner treats this as base content.
- P679 resolves both CS:GO Source 1 folder aliases by checking pak01_dir.vpk,
  not merely whether CS2's install directory exists. Explicit Steam-root
  overrides precede registry/VDF installs across both aliases; requested layout
  wins when both exist. Hermetic tests compile the actual resolver function.
  The Windows primary-library file probe must return the absolute game
  directory, not its relative probe filename (the old empty-filename probes
  concealed this bug). Modern-only CS2 is not claimed as supported.
- Harness action traps: boot mounting can precede log_enable, so do not demand
  its startup dprint as the positive control; prove file consumption and the
  live searchpath instead. Set fs_hidesyspaths explicitly: 0 changes screenshot
  messages from $basedir to absolute paths. Match the artifact suffix and
  verify the PNG itself. Failed first arms are retained, not relabelled passes.
- P679 Windows deployment UTC **2026-10-12T08:07:50Z**: engine
  `263d176862ccfd55fc3a82d5b65e20159d64a011` / annotated `patch-679`, paired QC
  source `c82f843643612a25ab76a1288e0251038af9cd82`. Committed clean full build
  stamped `git-7270-patch-679-0-g263d17686`; client SHA256
  `f193852bad80bc2ef86a63237abf8e2d24dce55a03952d981996671978b24cbd`.
  Both Windows installs received the client and all five native plugins;
  C:/FTEQuake also received the paired dedicated server. All 13 destination
  hashes verified, predecessors in .prev. Actual installed EXEs were then
  launched against owned no-HL2 fixtures using copies of installed progs;
  both consumed Momentum's pack and restored the tested surfaces (logs/PNGs
  inspected). Owner configs, mount lists, progs and mapdeps stayed byte-identical.
  No NanoPi/Linux deploy, release archive or QC Build bump. A tester using an
  older download still needs an updated client. Compact evidence and the
  original control-native set are retained at
  `C:/FTESurf-worktrees/sourceauto-761b9b44`; no owner/peer process was killed. Disposable-copy retirement status is in
  that root's OWNER.md.

## Source material cache/opacity controls (Patch 683)

- One VTF can be both a 2D emissive image and a frame-array animation in the
  same map. Include concrete target type in texture cache identity. Preserve
  request-side ANY as a wildcard after upload resolves its concrete type;
  pending ANY cannot satisfy a concrete target. Resource-status callers that
  ask about any texture view must explicitly use ANY.
- A program variant name proves requested defines, not successful sampling.
  Demise's mask-only shader rendered the scaled glyph; sampling its smoke
  image removed it. `r_imagelist smokeanimated` then proved the wrong shared
  2D_ARRAY object. With type-separated caching, native 2D and 331-layer views
  both load and the builtin glyph appears. Keep a unique sentinel plus mask
  probe before interpreting a black/inactive sampler as authored colour.
- Frame-zero VTF retention still has to traverse every stored frame per mip.
  Test both environment-map layouts and all-frame arrays. Additive ONE/ONE
  opacity must mask RGB; changing only output alpha is inert. Absent WVT
  texture2 does not justify inverse alpha: Source's hasBaseTexture2 gate leaves
  direct vertex opacity. Preserve entity and authored vertex opacity in new
  reflection programs as well as material ALPHA.
- New GLSL files need the hand-maintained hl2 Makefile list plus regenerated
  builtin header. Compile generatebuiltinsl.c from a relative path to avoid
  embedding an owned task path in the public generated banner.
- Cold process restoration is safer than an empty r_remapshader target. Chained
  live VFS/remap diagnostics crashed; separate old/new fs_restart controls did
  not. Cause remains in BACKLOG. Long bridge command lines are rejected at
  240 bytes; split them and inspect ACTED probe output, not only command exit.

## OpenGL blend collector and visual harness (Patch 685)

### P721 cache-gate readback refusal and build guards — 2026-10-15

- The new exact-P721 Q1 product/twin attempt stopped BEFORE its first PNG:
  `hud_timers` was unknown; raw replies also reject `hud_pb`, `hud_spectators`,
  `hud_statusbar`, `hud_lobby` and `hud_surfinfo`. Copying old setting strings
  into a mandatory readback contract does not establish that those names exist.
  Keep required renderer/registered HUD controls strict; audit actual registration
  and pin the loaded progs separately from any source checkout. An unknown name
  is neither an effective zero nor evidence that every overlay is disabled.
  This was one product boot/zero shots/no diagnostic boot, NOT a renderer/cache
  failure or functional pass. Once-only rc0 closure restored eight subject
  binaries; independent audit matched both installs/protected membership and
  proved all three originally absent fixture files removed.
  Preserve the frozen failure; a corrected contract needs separate review,
  refreeze and fresh authority, never a silent retry or a generic Unknown bypass.
- The diagnostic build helper's first review caught a warning filter that ignored
  Makefile lines and required lowercase `warning:`. Match the word case-
  insensitively, including non-colon forms, and compare payload MULTIPLICITIES;
  an extra occurrence of an inherited warning must fail. Attribute compiler/Make
  categories without discarding either. Normalize only registered source roots.
  Acting controls reject new Makefile/mixed-case/non-colon and duplicate payloads.
  Reread both source and product HEADs in the final closure, not just status/index
  and tracked bytes. Corrected exact-P721 diagnostic compile: zero NEW counts,
  unchanged tracked sources/dependency cache/HEADs/index; no native acceptance.

### Legacy list readiness/rescan seam (2026-10-14 source probe)

`tools/test_p690legacyorder.py` compiles complete production batch-generation,
rebucket and reload functions with controlled stubs, actual sort enum and acting
mutants. Eleven cases/six mutants pass C-O0/O2 and Python normal/-O. Registration
is WG_MAIN (`R_LoadShader` asserts it), not a worker shader-table race proved by
`-noworkers`. Loader timing can alter queued GL callback/publication readiness.
Initial batch head insertion and later global head-insertion rebucket can produce
opposite final same-band lists. ANY used shader sort change triggers the global
rebucket; `Mod_ResortShaders` checks MLS_LOADED only (no model-type guard), reverses
unchanged lists, skips loading models and clears scene cache. Controlled built-
before/after/not-published schedules are source counterexamples, not production
histories. P688/merged registration source is identical after Git newline handling.

The exact merged production's .db was retired. Earlier candidate COFF names lack
type debug information and candidate model-root addresses are0x1000 different.
Offline complete-function normalized matches independently recover actual model
root RVAs; do not borrow diagnostic/candidate addresses or infer arbitrary type
fields. `tools/p690legacyorder.md` documents machine-code scope and remaining
fail-closed decoder/late-snapshot controls. No live observer acceptance yet.
A late loaded-memory graph cannot reconstruct registration history or prove GPU
submission order; `worker_status pending0` does not attest in-flight completion.
Never use body-reading `mod_batchlist`, `mod_texturelist`, `r_showshader`,
`shader_here` or `r_showshaders` as a lifecycle-neutral observer. No default2,
product fix, native causality, deployment or performance claim from this probe.


- A cached VBO batch deliberately has no CPU meshes; that is a coarse whole-
  batch record, not an empty draw. Preserve original descriptor/cache pointers
  and ranges when submitting individual mesh records. Scenetris require their
  mesh vertex bounds: the world-wide batch bounds make different-depth polygons
  tie. Stable sequence only resolves genuinely equal depths.
- Fast-math can invalidate ordinary finite comparisons. The production blend
  key guard uses bitwise IEEE exponent checks; the portable test runs normal/
  HEXEN2 both with and without fast-math and requires three acted failing mutants.
- Always pass absolute conbridge executable paths. A relative name resolved from
  canonical cwd selected the old install rather than the newly staged subject;
  identical basedir/plugin paths do not prove the client ACTED. Verify process
  image hash and runtime version stamp, then compare the new bundle.
- World-disabled polygon fixtures can render into an alpha target and be
  normalized at compositing; RGB is not necessarily the simple background-over
  result. Keep world rendering explicitly enabled, capture a fixture-off
  background separately per mode, disable both native and HUD crosshairs, and
  grade a registered crop. An unregistered fixture cvar needs explicit `set`
  before it can safely be invoked as a command.
- PowerShell unquoted drive-valued arguments and an inherited
  MSYS2_ARG_CONV_EXCL can each produce an unacted build. Quote drive paths and
  clear argument exclusion inside pwsh before it launches make/GCC. A worktree
  `.git` is a file: the engine Makefile's directory probe emits an empty revision.
  Pass an inspected SVN_VERSION/SVN_DATE in the owned build adapter and verify
  runtime `version`; do not infer provenance from file time.
- Cold ODE dependency compilation added upstream warnings to one full build.
  The exact final build and accepted baseline both emitted the same74 compiler
  diagnostics with no new payloads. Keep cold failures/warnings separately;
  compare actual compiler diagnostics, not Make's repeated pattern warnings.
- P685 ships default1 and opt-in2 only. Source cache1 remains selectable but does
  NOT activate temporal generation at delivered a8e705787: VBSP_LoadModel sets
  fg_new, while Surf_DrawWorld admits only quake/halflife/quake3. Static brush
  VBOs are not temporal caches. r_waterinfo's “in use” prints .ival, not branch
  activity, and that command is unsafe on Source. See tools/p690blendplanes.md
  for the postdraw-counter actor/positive controls; do not credit a readback or
  matching Source screenshot as cache/performance/capture acceptance.

## Conservative blend-plane refinement and controls (Patch 690)

- Fixed unsupported slots are not pairwise barriers: moving admitted faces
  across a dynamic slot can invert their order against the dynamic geometry.
  Reject the whole proposed permutation before writing when admitted-rank
  distance differs from absolute-slot distance. Three admitted world faces
  can still regress an unproven intersecting pair: retain baseline edges for
  unknown overlapping pairs; disjoint projected pairs remain unconstrained.
  Real painter cycles, budget exits and barrier exits must be atomic. Both
  regressions ACTED in pre-fix actual-C collector and native authored controls.
- Eligible blend-sort-bucket faces are not necessarily conventional alpha.
  Non-programmable static geometry, actual finite planar vertices, standard
  perspective and identity-world gates are the implemented scope. Per-face
  caps exclude a record; admitted-face/total-vertex/pair-work caps abort the
  stage. The pair-work counter does not bound the full admission scan.
- Lock sensitivity/m_yaw/m_pitch/in_windowed_mouse for exact screenshots and
  verify server body, aim and zero velocity. An earlier identical-settings
  run moved the camera and is excluded. Cross-binary Source-water deltas were
  1,501 Air-HUD pixels, explicitly PNG-triaged and post-masked; they were not
  silently ignored. Native water is cache0 Full/Dither/Full-return; cache1
  evidence is separately attributed v2 Q1, not a VBSP worker-cache claim.
- Source cache reachability continuation: diagnostic-only post-BE_DrawWorld
  main-view counters and actual rendered eye/angles prove cold/selected Source1
  uses ordinary draws; staged Q1 cache1 ACTS and cache0/return restore ordinary
  draws. Counters do not change decisions or production binaries. Exact retained
  P688/merged production Kitsune cache0/1/return0 repeats/default parity pass;
  mode2 changes12065 pixels per selected cache setting. This is ordinary Source
  submission, not a VBSP cache gate. New diagnostic Q1 proof does not relabel old
  v2 production-cache evidence. Artifacts: source-cache-20261013/grade_cache.py.
- Supported-Q1 continuation now binds96 exact P688/delivered integrated/probe/
  P688-return frames on two asset-free BSP29 maps. Both modes/cache0/1/return0
  preserve every opaque pixel and coarse cached-alpha P688 output. Diagnostic
  settled intervals prove cached-only470..476 draws versus ordinary-only469..480,
  with exact production pixel/input parity. Ordinary mode2 acts20604 pixels and
  both initial/return authored order witnesses; default/repeat comparisons exact.
  Offline p690cache.py plus test_p690cache.py reject33 acted bad-evidence controls
  under normal and -O. Two synthetic maps/one camera/GPU, not broader promotion.
- Ordinary stationary-cost continuation was REJECTED, not a performance green.
  tools/p690ordinary.md separates128-swap WGL-return cadence (r_speeds0) from
  100-frame refresh service buckets (r_speeds2, subtract table overhead only).
  r_speeds3 injects GPU finishes; REAL refresh+server still is not the whole host
  frame. vid_wait queries print canonical vid_vsync; renderer must be explicit.
  A0.4second bridge read captured partial dumps in34/38 replies even though full
  records exist in raw logs: require a unique ticket and footer before grading.
  Six/eight Kitsune fullframe repeats changed1016..3900 pixels; no new mask was
  allowed. Timer/mapinfo/mouse-pad stayed visible behind guessed HUD names; inspect
  actual registered names, but scene deltas do not prove HUD causation. Archived
  excluded timing diagnostics also show P688 mode1 return cost+37.57%, above the
  frozen20% drift guard. Timing slowdown ACTS5x cadence/59x refresh; that does not
  rescue unstable controls. Serialize native timing against detector/corpus/hash
  work and prove quiet A/B/A returns. No product bug/fix/default2 acceptance.
- Quiet ordinary follow-up passes ONLY the fixed Kitsune cache0 GL station.
  src/client/cl_mouse.qc:MPad_Draw's lower-right square is hud_mouse, not a
  minimap; hud_timer/hud_mapinfo are registered panel controls. Disable/read
  these plus explicit input/prediction/HDR state, and prove the actual on/off/on
  channel. Short probe changes16215 HUD pixels, exact return and both fullframe
  repeats across r_speeds0/2/0, counters advance314/315 ordinary draws.
  New schema2 reader requires current unique BEGIN/END-or-footer primary records
  and hash-bound successful completion waits with exact timestamped-primary
  completion binding and unique witness paths, never fixed-short-read recovery.
  BLOCKING serialized capture, no concurrent parent/child detector/hash/corpus
  work:78 complete samples/17 exact PNGs; mode2 acts12065, default/diagnostic/
  return parity exact. Six medians P688/merged/return: mode1 753.410/730.220/
  692.195us, mode2 785.760/762.495/677.520us adjusted refresh. Both-controls1.20
  and return[.80,1.20] unchanged; -8.13%/-13.78% return drift is within guard,
  NOT identical load or a speedup. All cadence medians9.9995..10.0015ms; slowdown
  acts5x/65.34x; WGL-return is not GPU/display, refresh is not whole-host time.
  All owned stopsrc0/native8/fixtures/install hashes restored. New controls74
  offline rejections/6 synthetic positives under normal/-O. Old failures stay
  excluded. Artifacts ordinary-quiet-20261013/, tools/p690ordinary.md. No broader
  map/moving-camera/frame-tail/promotion/default2 claim; several setup changes
  together do not establish what caused the previous scene drift.
- Additional-map stationary eligibility is NOT a performance matrix. Existing
  Tensor2/Demise fullframes still change with the actual quiet HUD/input settings,
  fixed rendered eye/aim, cache0 and314/315 advancing ordinary draws. Tensor2 mode1/
  mode2 repeats change286088/283347 pixels in lower water-area bounds; Demise's
  valid retry changes24701/21166 in upper sky-area bounds. No masks/time freezing
  or causal shader-defect claim. Known-stable Kitsune positive repeats exactly,
  HUD16215 pixels/exact return. Both extra stations are INELIGIBLE for the exact
  stationary gate, so no production A/B/A timing there. New p690stationprobe.py
  separates INVALID evidence from valid-but-INELIGIBLE; normal/-O controls cover
  ticket/wait/camera/state/closure and one-pixel drift. tools/p690stationprobe.md.
  Demise first cmd setpos printed the target but settled about1.1 units off it:
  exclude, don't widen tolerance. A separately frozen retry split noclip activation
  from placement, placed again after settling and checked body BEFORE PNG/cost;
  same target passed. Root cause of initial placement drift remains unknown.
  Timer may be running on a stationary renderer station; correct world, ZERO
  velocity and protected fixture restoration matter, not assumed idle/armed.
- Bounded sprite/world preservation now has native production P688/merged/P688-
  return coverage: one generated SPR32 billboard via prop_dynamic,24 fullframe
  PNGs. env_sprite is removed by this QC, not a sprite fixture. Set gl_blendsprites1
  BEFORE map load; verify actual defaultsprite blend shader and rendered green
  footprint9216pixels. Sprite-on repeats/returns and both production modes are
  exact; sprite-off mode2 correction acts20604pixels. Merged mode2's on/off delta
  includes world reorder, so it is NOT pure sprite area. Preservation does not
  prove inherited ordering correct; no diagnostic admission/eye counter, animated/
  arbitrary sprite/model/weapon/portal/performance/default2 claim. Generator writes
  only fresh owned artifacts; native fixture/native8/config/data/install closure
  is separate. tools/p690spritefixture.md; artifacts/sprite-overlap-20261013/.
- P690 rotated func_wall continuation (tools/p690brushfixture.md) generated two
  BSP29 maps identical except actor angles0/45. One local model*1 green pane at
  origin272,0,64 acts: green footprint9216pixels/96x96 versus6532/68x104. Loaded
  *1:<map>/one-green-surface batch, ordinary-alpha shader and on/off/on readbacks
  bind the production actor; no fixture QC/build/diagnostic admission claim.
  The complete48PNG frozen native matrix is REJECTED. Mode1 yaw45 initial P688
  differs20604pixels from both merged and P688-return, including entity-OFF;
  P688 mode1 world-only frames also differ across the yaw-map boots. Every
  within-boot repeat/entity-return is exact; mode2 ON subset matches, and OFF
  merged correction acts20604. A baseline that does not return cannot certify
  default parity or attribute the difference to the candidate. Keep the original
  normal/-O rejection, all raw/PNGs and a separately labelled postcapture report;
  do not mask/widen/relabel. Next protocol must prove stable legacy world return
  (prefer same-loaded-world observed angle action) before native acceptance.
- Same-loaded-world brush follow-up uses existing engine poke_ssqc numeric
  entity.field/vector assignment, not a new QC command. Discover targetname,
  verify classname/model/origin/angles/avelocity BEFORE writing only actor angles;
  bind complete fresh ticketed raw replies and visible0/45/0 footprints. All18
  P688 initial/return fullframes now exact, angle ON/OFF3150/0 in all modes/arms,
  but all10 mode1 P688-vs-merged PNGs differ20604. Full gate remains REJECTED;
  do not claim a candidate defect/root cause. Mod_ResortShaders prepends/reverses
  lists when called, Shader_DoReload calls only after a live sort change; these
  runs did not count-bind that lifecycle. mod_batchlist is not inert: it calls
  Shader_GetShaderBody, which can reparse shaders. Observe after pixel states or
  prove observer-OFF/ON/OFF parity before using an order diagnostic.
- A subclass of a retained capture helper must explicitly pin ITS OWN __file__;
  inherited __init__ resolves globals in the helper module. First54PNG attempt
  restored but frozen checker rejected before pixels: driver_sha256=helper hash.
  Retain failed source/manifest/protocol unchanged. Separately versioned V2 pins
  subclass/helper independently; real constructor with mock helper-init and a
  wrong-driver negative control prove metadata BEFORE launch. Never fix captured
  manifests. The V2 native onepixel mode1 control was hidden by an already failing
  comparison: record UNPROVED, not a passed control. Synthetic rejection does not
  make it native. Frozen pane-only ON/OFF was also a protocol error: removing an
  unsupported barrier enables world correction outside actor area. Keep original
  rejection; explicitly diagnose this known control interaction, not product bug.
  tools/p690brushfixture.md; artifacts/brush-sameworld[-v2]-20261013/.
- Later passive lifecycle continuation (55PNGs/five boots) binds raw batches and
  real reload/resort events at exact P688/merged sources, without shader-body/
  parser/rebuild calls. Identical65-line additive observers; samples1..8, zero
  overflow. Both observerOFF/ON/OFF sets and all11 production P688 returns exact.
  Diagnostic P688 activation reload changes red/blue/green sort5->11; one actual
  resort reverses blue/red/black into opaque black plus red/blue; mode1 center
  (64,0,127). Diagnostic merged has no sort changes/resorts, blue/red order,
  center(127,0,64). Observed diagnostic records, NOT production causality: each
  diagnostic's nine mode1 PNGs differs20604pixels from its production boot,
  so18 frozen transfer failures remain; mode2 exact. Within-boot observer parity
  and identical source do NOT prove boot-time nonperturbation. Normal/-O reports
  retain all18 failures plus NEW SPECIFIC native observer1bit/source/overflow/
  footer/material controls. Earlier rejected protocols/manifests/gates unchanged.
  tools/p690brushfixture.md; artifacts/brush-order-20261013/.
- Minimal m-rel builds:37 inherited compiler warnings/0new plus222 Make grouped-
  target warnings each, retained separately. First checker mixed the categories
  and failed; source/log/failure retained. Shared ARCHLIBS hashes unchanged. Five
  pairs quitrc0/native8/protected1223/install2/fixture absence restore; recorder
  306/0 and corpus/reader/count/fault parity unchanged. Parent review only.
  A separately frozen -noworkers follow-up now PASSES all55 exact production/
  diagnostic/P688-return fullframes, mode1 preservation, observer parity and
  yaw0/45/0 return. Both processes zeroed BEFORE worker initialization; default
  positive has4 live/0pending on cl+sv and210 measured receipts showcount0/live0/
  pending0. Bind actual MATCH cl/sv waits, unique tickets/raw paths and phase
  intervals against observer/state/PNG, not just labels; boot receipt reuse is
  not evidence of later or server state. Both diagnostics now show activation
  sort5->11/resort1/red-blue,21 events/eight unchanged passive samples; mode2 OFF
  correction still acts20604. Normal/-O frozen grades and4 pixel/36-total native
  replay controls pass. Six owned pairs quitrc0/native8/protected1223/install2/
  fixture absence restore; recorder306/0 and corpus hashes/counts/faults unchanged.
  Exact retained binaries/no rebuild/default/deployment change. The previous
  rejected gates stay immutable. This bounds a synchronous-loader fixture, NOT
  ordinary-worker transfer or workers-only causality: ticket cadence/warmup also
  differ. A second matched cadence/warmup six-boot worker-enabled capture now
  ACTS212 replies4live/0pending, valid55PNG/16samples/closure, but gate REJECTS18:
  nine merged production/diagnostic transfers and nine mode1 crossbinary images,
  each20604. Normal/-O validJSON preserves all18;4 new-specific pixel/44-total
  replay controls ACT despite preexisting failures. Both diagnostics still have
  resort1/red-blue; never assign those events to mismatching merged production.
  Other46 images crossbatch exact; both mode2 transfers/all11 P688 returns and
  observer parity hold, not a subset acceptance. Six pairs/protected/native/
  fixture/corpus closure pass. Worker setting implicated, NOT sole cause proved
  (zero-then-enabled, no uninstrumented production lifecycle). Next isolate real
  worker-enabled registration/rescan without diagnostic perturbation; cadence/
  warmup match is now tested, not a remaining prerequisite.
  Stable rebucketing remains separate unproved product work. No forced resort/
  reparse/flush/retry selection, mask/widening/subset rescue or arbitrary model/
  default2/performance acceptance. tools/p690brushfixture.md;
  artifacts/brush-workers-20261014/, brush-workers-enabled-20261014/.
- Before native launch, actually exercise extra argv through conbridge argparse
  with dispatch stubbed. --server-args=-noworkers works; separate flag/value
  tokens reject as expected-one-argument and can strand staged binaries if the
  harness marks active too early. Only a PROVED predispatch parser failure plus
  independent absent processes/registry can clear active for restoration; never
  swallow an ambiguous launch/stop failure. Port guard needs rc0/explicit success
  enumeration; suppressed errors/empty stdout are NOT an unoccupied port. Normal/
  -O safety mutants caught these before the zero-worker fixture froze/launched.
  Reviewer timed out with useful partial findings, parent corrected/tested;
  no completed independent correction/result clearance or fallback claimed.
- Stale r_waterinfo MarkLeaves age is NOT cache-action proof. Q1BSP_MarkLeaves
  common/q1bsp.c:2227 returns same-cluster cvis BEFORE marktime at2275. Actual
  stationary cache0 reported wanted0/inuse0 plus stale14.1s/false causal cache
  explanation; a proposed actor failed and was retained. Use postdraw counters
  with actual-world/rendered-camera/production-image binding instead. Existing
  historical stale-age-only positive evidence must not be relabelled draw proof.
- Uncollidable authored BSP tests need explicit noclip after EACH map load.
  Body0 alone fell thousands of units before the first PNG. An opaque blue quad
  fully occluded the first fixture's red lost-geometry sentinel: exact frames
  alone were insufficient. Reject zero authored red pixels; expose the red edge,
  keep the failed96-frame matrix/generator and rerun. FTESurf actual rendered eye
  at body0 is0.062,0.062,64.062 here, not assumed vanilla Quake22. Compare numeric
  diagnostics, require exact stable production repeats and do not add a mask.
- Before labeling a map-switch arm, prove model/map identity, not just body/zero
  velocity: missing Q1 map404 left the prior Source world running at origin0.
  Retain/exclude it. Re-read the exact station recipe: unrelated water-station
  camera6235.4... is NOT sorter station -14986.3 -14484.8 772.3/19.3 125.6 0;
  its animated pixels failed repeat parity. Corrected final station reproduces
  12065 exactly. No mask or product correction was used to hide those failures.
- The same baseline executable produced two legacy mode1 interbatch orders
  (20,402 A/A-return pixels) after restart/flush. Do not blame a candidate for
  that without A/B/A. Original Kitsune six-yaw mode1 is exact baseline/subject.
  Mode2 changed-pixel counts prove action; frozen geometry supplies the order
  oracle. Timerefresh/explicit-finish timing is not normal frame-time evidence.
- Windows and MSYS Git have different autocrlf config; prepending the MSYS
  toolchain PATH made a clean Windows worktree appear673 files dirty. Owned
  build adapters use explicit Git-for-Windows for provenance checks. Compiler
  PATH and artifact-directory prerequisites must precede parallel test arms.
- Exact P688/P690 cold client/server/all-five-plugin builds both emit74 compiler
  warnings/45 distinct message payloads plus349 Make grouped-target warnings,
  no new compiler payloads. Three QC programs have zero warnings. P690 fresh
  exact-stamp station reproduces all retained six-yaw counts/default parity.
  See tools/p690blendplanes.md for SHA-bound source/bundle and delivery status.
- Integrated a8e705787 P689+P690 was clean-built and delivered native-only to
  both Windows installs at2026-10-13 11:10 UTC:13 native targets with .prev and
  immutable rollback, actual installed exe/DLL-path/map smokes,9310 protected
  files unchanged by path/size/hash/mtime. Defaults stay1; no own progs/config/
  Build/Pi/release change. Fresh merged48-shot station reproduces six-yaw parity
  and ACT counts; eight signed cold recovery controls pass. Existing water/
  cache/program/timing arms retain their original build attribution.
- Preserve ODE tar mtimes when seeding a build. Fresh cp made the archive newer
  than the shared library and triggered a dependency-cache rebuild (NOT a
  read-only input):1041 extra ODE warnings/13 payloads, native74/45 unchanged,
  full compiler1115. Never restore/delete a potentially shared cache to hide
  this. Parallel plugin warning lines interleave; attribute file/payload rather
  than subtracting a contiguous log range. Plugins have no embedded SHA stamp.
- Box3D and ODE are exclusive active physics plugins. Test loaded native paths
  in separate plug_close/plug_load phases, not simultaneous availability.
  ui_imgui requires client interfaces and should refuse a dedicated server.
  Retain mistaken smoke arms; corrected expectations are not product fixes.
  Signed recovery controls require their exact fixture/feed hash, not merely
  an arbitrary retained update.json: wrong fixtures can block in a modal error.
- Number claim raced a native-recovery session during long builds: sorter
  b59026cc2 initially used P689, while peer c325d045/tag patch-689 was created.
  Tag-create failed but a wrongly chained push still exported the pre-existing
  peer tag. Reported immediately; no tag/history rewrite. Forward metadata-only
  7598b4c4d assigns sorter P690/patch-690 and unchanged C is rebuilt/station-tested
  with exact git-690 stamp. Do not infer the sorter source from patch-689. Tag
  creation and peeled-SHA checks must succeed BEFORE any explicit tag push.
- No default2, arbitrary model/sprite/weapon native, tessellation/external-matrix
  runtime, Source envmap/model-lighting, QC Build or release claim.

## Missing-asset art (Patch 534) -- 2026-10-07

- `R2D_Init` requests the diffuse fallback as `no_texture`, with replacement
  allowed. The standard high-res search finds `textures/no_texture.png`:
  no engine rebuild is needed. `gfx/env/missingtexture.png` is the author's
  source image; the alias must remain byte-identical. `gl_load24bit 1` loads
  it at 64x64; 0 plus vid_restart restores the engine's 16x16 fallback.
  Normal/gloss placeholders stay 4x4, not magenta checker maps.
- `models/missing_error.md3` is a standalone extruded Impact ERROR asset,
  not an installed automatic failed-model replacement. Its opaque faces are
  fullbright red, sides darker; four small additive outline rings work with
  bloom off. No font binary/Source model is redistributed. Regeneration uses
  `tools/make_error_model.py` with a locally licensed Impact font; only the
  generator needs fonttools/shapely/mapbox-earcut/numpy. Runtime needs the MD3,
  `scripts/missing_assets.shader` and `gfx/env/missing_error_palette.png`.
- A pass-level `rgbgen const` with `program default2d` rendered this GPU alias
  mesh WHITE even though the script parsed. Use baked palette UVs instead;
  do not grade shader parsing as red pixels. The red front/angle/off controls
  distinguish actual rendering; 0 off pixels vs 58653/53639 red pixels, bloom0.
  The final quantized mesh has no degenerate triangles; tiny ones removed by
  MD3's 1/64 coordinate quantization do not change the frontal pixels.
- This replaces ENGINE CHECKERS, not every missing Source texture path.
  A valid Source UnlitGeneric whose explicit pass map is absent can remain
  black: `T_GEN_SINGLEMAP` does not use the `T_GEN_DIFFUSE` fallback. A missing
  VMT and a found VMT with a missing base texture are different controls.
  Failed-model fallback must retain failed-load diagnostics and must NOT
  change Source collision. Both integration tasks remain in BACKLOG.
- `tools/test_missing_assets.py` checks MD3 bounds/offsets/triangles/materials,
  PNG CRC/resolution/palette/alias and explicit release entries. The release
  globs for models/scripts are nonrecursive, so the MD3 sits at their top level.
  Do not silently put it into a subdirectory and call a local render a ship pass.

## Source fire sheets: loading is not animation -- 2026-10-07

- Particle VTFs can have ONE image frame and still contain an animated sprite
  sheet. The resource tag is binary 0x10, not SHT: fire_particle_4 is 2048x128
  with five 16-frame sequences; fire_particle_2 has an 18-frame sequence plus
  single-frame aliases. Use authored UV rectangles and durations, not a guessed
  uniform square grid. Inspect the VTF version/header bounds before walking a
  resource directory: 7.1 has no 7.3 directory. Preserve/report sequence flags
  rather than guessing their byte layout from a third-party parser.
- `p_script.c` tcoords/atlas randomize a static UV cell at spawn. They do not
  step it as the particle ages. Patch 531 adds separate native texframe/texanim
  tables, but does not change those legacy commands or integrate the fire baker.
  The PCF translator currently emits neither a
  sheet table nor animation, so registering a SpriteCard material or successfully
  baking a PCF is not evidence that its flames animate. A fit-to-life prototype
  needs a frozen pose with two different UV frames, repeated effects-off pixels
  to bound background drift, and a real-time animation control.
- Source c_fire_smoke.cpp:Start selects env_fire_tiny/small/medium/large with
  optional _smoke. These effects can live in shared game PCFs, even when a map
  embeds no PCF at all. Dune combines env_fire with custom/shared PCF systems;
  Anubis combines env_fire with hundreds of warm ParticleSphere smoke stacks.
  Material/class identity matters: do not replace every yellow orb with fire.
- Bright SpriteCard addself/overbrightfactor is not the same as $additive or
  full-screen bloom. One UV-stepped additive pass can approximate a bright
  flame without a capture/blur/light pass, but does not reproduce Source's
  depth blend, frame cross-fade or children. Keep those limits explicit.
- Polygon quads can batch by material and avoid one model entity per sprite;
  that does not make them free. Bound nearby/visible sites and sprite count,
  use smaller/fewer distant quads and measure overdraw. Equal-count polygon
  glow vs flame timings do not compare against the installed native emitter.
  A Dune camera with missing/checker materials is a UV diagnostic only, NOT a
  valid full-map performance or visual acceptance baseline.

### Native stepping prerequisite (Patch 531)

- `texframe duration s1 t1 s2 t2` appends a finite normalized rectangle, up to
  256 rows, with positive durations. `texanim static/lifetime/loop/clamp [rate]`
  steps the existing native normal-sprite UV fields in the same material batch.
  Lifetime mode uses the actual randomized particle lifespan. No cross-fade,
  secondary channel, per-particle allocation, extra sample/capture/light pass.
  `FTE_PART_TEXANIM` means compiled scripted-backend syntax; callers must still
  select that backend. Real old/new clients render and return extension 0/1.
- The isolated colored atlas acts for point and trail particles, lifetime
  expiry, loop/clamp, legacy static UVs, source-reset surviving retint, set unload
  and renderer restarts. All 256 rows survive actual QC query/export/re-exec;
  257th/NaN/negative/bad-type/no-frame controls visibly reject. The QC query and
  export buffers are enlarged to 64 KiB; their old 8 KiB cuts long tables.
- Native particles are drawn/simulated from the world walk in r_surf.c.
  `VF_DRAWWORLD 0` produces black native-particle tests with a nonempty pool:
  that is not an animation failure or a passing off control. Keep world draw
  enabled and inspect actual colored pixels and active/free pool counts.
- Let particle precache mappings refresh after exec/redefinition/restart before
  emitting via cached CSQC handles; same-command-stream emission can miss.
  Existing particle export omits trail step spacing; a replayed trail can emit
  nothing. This prerequisite leaves that unrelated omission alone. Restore the
  authored step for an acting trail control instead of interpreting silence.
- Shared env_fire definitions were located in the explicitly mounted HL2 VPK's
  particles/fire_01.pcf. The installed shared fire_burning_character VTF is 7.6,
  2048x2048: primary sequences3..5, secondary0..2, authored timing/flags. Do not
  substitute Dune's flame for Anubis or confuse its separate smoke stacks with
  flame. Inventory resolution is not yet a production shared-library resolver.
- Native Dune/Anubis flame-only rigs act with repeated-off images identical,
  an explicitly capped pool128, nearby sites<=8/range512 and <=72 emissions/sec.
  They approximate size/forces/alpha/material and omit graph children. Dune's
  diagnostic camera still has missing/checker materials. Uncapped alternating
  local wall-frame observations are NOT GPU/whole-map/installed-path acceptance.
  No product emitter, generated assets, owner install or fleet changed. Keep
  BACKLOG's integration/budget/compatibility/ship-set gates open.

### env_fire in the game (Patch 643) -- 2026-10-11

- `cl_emit.qc` draws `env_fire` as Source's `env_fire_tiny/_small/_medium/_large`
  (`floor(firesize / 36)`, `c_fire_smoke.cpp:167`): the system, its `_b` child
  and its embers, numbers out of `particles/fire_01.pcf`. EVERYTHING IS TEXT IN
  CSPROGS: the r_part blocks go through `localcmd`, the shader is an inline
  `glslprogram` in `shaderforname`, the frame table is the generated
  `cl_flamesheet.qc`. A lobby hands a player csprogs.dat, never `particles/` or
  `glsl/`. `emit_list` says which rule chose the look (`Emit_FlameWhy`).
- THE ATLAS IS NEVER SHIPPED. It is drawn from the mounted game: Counter-Strike:
  Source's and Half-Life 2's copies are one file (VTF 7.3, 5,601,084 bytes),
  Momentum's is another (7.6, 1,160,144), and all three carry the same sheet --
  `tools/flamesheet.py` refuses to write the table otherwise. `fs_addons.txt`'s
  `steam:Momentum Mod Playtest/momentum` does not reach Momentum's `mount/`
  vpks, so the game draws CS:S's.
- `whichpack` ANSWERS "" FOR A FILE INSIDE A MOUNTED GAME'S .vpk, found or not.
  The first probe said "no mounted game carries the atlas" while `flocate`
  found it in `cstrike_pak_dir.vpk`. `search_begin` + `search_getsize` (as
  `cl_banner.qc` probes a sound) answers both ways: measured present with the
  mounts, absent with the CS:S and HL2 lines taken out of `fs_addons.txt`.
- SOURCE BLENDS SPRITECARD IN LINEAR LIGHT; THIS FRAMEBUFFER BLENDS IN GAMMA
  SPACE. Premultiplying in gamma space drew a fire that was mostly not there:
  a quarter-covered layer adds a quarter where linear light adds half. The
  shader writes the linear sum's own encoding and a destination factor that is
  exact on black and on a 0.6 grey (`Emit_FlameShader`). Other Source
  translucents that look thin here may be the same thing.
- A BURST OF SCREENSHOTS STARVES THE EMITTER. Each shot stalls the client,
  `Emit_Frame` will not catch a stall up, and a flame lives 1.2-1.75 s: six
  shots 150 ms apart showed one full fire and five thin ones, and read as a bug
  in the emission. 2.5 s apart every shot is full.
- A COUNTER OF INTENT, AGAIN: with `texanim clamp` written as `texanim static`
  every line of the arm still passes (the effects exist and answer the engine's
  query) and the brazier's pictures hold a sixteenth of the flame
  (`tools/p643fire.py`: mean 214 flame-bright pixels against 3,349). A
  sequence's FIRST frame is a small flame, so the tiny and large fires only
  halve: each group of shots has its own bar, set between the two builds.
- THE COMMAND BUFFER HOLDS 64 KB AND DROPS WHAT DOES NOT FIT, whole, with one
  console line (`Cbuf_AddText: overflow`, `cmd_maxbuffersize`). A size class
  of fire is 14-16 KB of r_part text; the two maps with all four classes
  (`surf_classics2`, `surf_road_to_hell`) are 61 KB. That fitted when sent in
  one go (measured, with 4 KB to spare), and is sent a class a frame
  (`Emit_FlameStep`) so the next thing added to it does not find the edge.
- `!!ver 100-450` IS NOT A RANGE. The engine reads two numbers with `strtol`
  (`gl_shader.c`, the `!!ver` branch), the second comes out as -450, and the
  program is built at the minimum: `#version 110`. A range is `!!ver 100 450`.
  The embedded shaders say `!!ver 110`, which is what was tested.
- A SPRITE'S SIZE IS ITS TEXTURE'S. Source's embers are radius 1-3 of
  `particle_glow_05`, down to half brightness at 0.12 of the sprite;
  `ftesurf_dot` is at 0.37. At equal radius they drew the old orbs back.
- A WORKTREE IS NOT A RIG UNTIL IT HAS WHAT GIT DOES NOT: `ftesurf/particles/*`
  and `data/mapparticles.txt` (untracked, see BACKLOG), `fs_addons.txt`, the exe
  and plugins, the built .dat. Without the first the log says `couldn't exec
  particles/ftesurf.cfg` every second and nothing else is wrong.
- A DRIVER STARTS THE GAME `SW_SHOWMINNOACTIVE` (`STARTUPINFO.wShowWindow = 7`).
  `-WindowStyle Minimized` handed to the exe, as older drivers do, is ignored:
  the window opens in front of the owner and the run prints focus lines.
- DEPLOYED 11 Oct from `74e4d44`: csprogs `dcbf42b6`, the file the arm passed
  on, to the Pi at 12:54Z with 12 lobby rows and 0 players, and to both
  installs at 12:54:38Z with no game running, under the rig lock. Twelve
  lobbies restarted, hashes read back from the host. `tools/pi_lobby_smoke.py`
  on 27510 at 12:55Z: the client was served a csprogs hashing `dcbf42b6`, drew
  the board, no QC error. `.prev` is Patch 646's `e9371ed5`; qwprogs, menu.dat
  and the exe did not change. The smoke grades the board, not a flame: no
  client has looked at a fire on a lobby.
- A DEPLOY GUARD THAT READS MAIN REFUSES THE WRONG THING. The first attempt
  stopped on "main holds later QC" (Patch 645, pushed and not yet deployed) and
  touched nothing. Later QC on main is somebody's next deploy; what must not
  happen is rolling a DEPLOYED build back, and that is read off the installs'
  and the Pi's hashes, not off git.

### func_precipitation: rain and snowfall (Patch 668) -- 2026-10-12

- WHERE: `src/client/cl_emit.qc`, the section "func_precipitation the way
  Source draws it": `Emit_PrecipAdd` at map load, `Emit_PrecipDefine` (two
  shaders, 24 rain blocks `ftesurf_prain_t<k>`, 32 snow blocks
  `ftesurf_psnow_t<k>`), `Emit_PrecipFrame` every frame, `Emit_RainDrop`,
  `Emit_SnowFlake`. Volumes are not emitters: their own arrays (`pr_*`), kind
  `EK_PRECIP` for the report only. `emit_list` has a line for the volumes,
  two for rain and one for snow; `developer 1` prints each volume's box at
  load. `vbsp_emit_precip 0` is off, read every frame.
- SOURCE'S RAIN IS NOT A PARTICLE SYSTEM'S RAIN. `func_precipitation` type 0
  is 0.35 wide, a tenth of a second long at 425 a second (45 units), 880 a
  second in a 1,500 square that follows the player; surf_tensor2's
  `info_particle_system` rain (Patch 659) is 1 wide, 80 long, 1,000 to 3,000
  a second, in fixed boxes. Both are `particle/rain`.
- THE LIBRARY HAS NO TYPE 1. Its "snow" is type 3, SNOWFALL, a different
  thing in `c_effects.cpp`: one manager for the map (`CSnowFallManager`),
  500 flakes alive at most, spawned round the player. An earlier count in
  this file called the 201 "snow".
- THE SKY IS IN A SIDE'S NAME, AND I HAD CONCLUDED IT WAS NOWHERE. A VBSP
  trace's `trace_surfaceflags` is 0 on a sky side, and from TWO hits whose
  sides I had not identified (one was a metal ceiling) I wrote "a trace names
  no surface" and built a second trace instead: from what was hit, up and out
  of the world; something over it a roof, nothing the sky. The arm passed, on
  a map with no sky over its volume. The review modelled the brushes of 36
  rain maps: a fifth of sky ceilings have a brush over them and a tenth of
  roofs have none. `trace_surfacename` exists for a progs that DECLARES it
  (`pr_csqc.c`; it is not in `cl_defs.qc`), and the plugin names a sky side
  `sky/...` (the name is cut at 15 characters). On surf_misc the old test
  read 355 starts "under the sky" under `metal/train_met`; this reads 0.
- A BLOCK WITH NO `alphadelta` LINE FADES TO NOTHING OVER ITS LIFE
  (`p_script.c:2452`, "use old behavior"): `alpha 0.4` alone is a ramp from
  0.4 to 0. With lives that end on the ground that halved the rain, and
  Patch 659's drop blocks had the same hole. `alphadelta 0` holds it.
- SOURCE'S TRACE OUT OF A BRUSH RUNS ON. The point where a drop passes the
  player's height is often inside something (a wall, a hill); refusing those
  drops left no rain over anything taller than the player. Only a trace that
  is solid all the way is a no.
- `setmodel`'s BOX IS A UNIT LARGER EACH WAY THAN THE BRUSH (6778 for the
  lump's 6777): a volume drawn up to a ceiling starts every drop inside it.
- `renderamt` IS A BYTE in Source (`SetRenderColorA(atoi)`): six rain volumes
  say 300, 400 or 550 and mean 44, 144 and 38.
- A MAP WITH NOTHING BUT PRECIPITATION HAS NO EMITTER: `Emit_Frame` returned
  at `if (!em_n)` before anything ran. It tests `pr_n` too.
- GLOBALS USED BY `Emit_LoadForMap` MUST BE ABOVE IT. The section first sat in
  front of `Emit_Frame`; fteqcc said "Unknown value" (it did not crash this
  time: these were reads in expressions, not a pointer assignment).
- A REPAIR'S CAP IS ON REPAIRS IN A ROW. "Three times a map" (Patch 659's
  `Emit_PsysRepair`, copied here) left an effect off after the third
  `vid_restart` on one map; the count now starts again when the handle
  answers.
- THE RELEASE'S ENGINE, AFTER THE FACT. Patches 656, 657 and 659 went to the
  lobbies without a run on the engine the 0.1.24 download ships (patch-625,
  `183faf44`, kept by 0f in `hud3-20261011T0836Z/artifacts/eng625`); the
  note about that is in this file and I missed it. Run afterwards with the
  lobby's csprogs `e04ccb61`: `p659rain.py` 18 of 18, `p657bright.py` and
  `p656fire.py` pass, `p648motes.py` all but "the looks answer again", read
  10 s after a `vid_restart` that takes 12 on that engine (four seconds
  later the motes were back; the arm now reads it then). 668 was run there
  before it went.
- DEPLOYED 12 Oct (UTC 11 Oct) from `1eca438`, main's tip: csprogs `ddf40c04`,
  the file the arm passed on, to the Pi with 12 lobby rows and 0 players
  (read back 23:10:14Z) and to both installs at 23:10:15Z with no game
  running, under the rig lock. Twelve lobbies restarted;
  `tools/pi_lobby_smoke.py` on 27510 was served that csprogs, drew the board,
  no QC error. `.prev` is 669's `cbc72b32` in all three. Then `tools/pcf.py
  --map surf_tensor2` and `--map surf_boreas` over `C:\FTESurf\ftesurf`:
  `particles/surf_tensor2.cfg` is `1b8d2e83` (was `e42ae639`), byte-equal to
  the file the arm ran on; `surf_boreas.cfg` `bb277920` and
  `data/mapparticles.txt` `6c1f06ec` came out as they were. The three from
  before are in the task root, `tmp/bake-installed-before`. The Pi's qwprogs
  was swapped for the same bytes (`35fda5eb`); the installs' qwprogs,
  menu.dat, default.cfg and the exes were not touched. The smoke grades the
  board: no client has looked at rain or snow on a lobby.

### Rain: a sprite trail placed drop by drop (Patch 659) -- 2026-10-12

- WHERE: `tools/pcf.py` writes, for a trail whose material is in
  `TRAIL_BLENDED`, twenty more blocks a system (`<map>_<name>_t<k>`, lives
  0.04 * 1.25^k) and a `trail` line in `data/mapparticles.txt`;
  `src/client/cl_emit.qc` reads it (`Emit_TrailNote`), makes the streak's
  shader (`Emit_TrailShader`, `ftesurf_trail/<material>`) and places each
  drop (`Emit_TrailDrop`). `emit_list` has two lines: `sprite trails:` and
  `drops:`. The system's own block and psys line are untouched, so an old
  client with new files, or a new client with old files, draws the old rain.
- THE ENGINE TRACES EVERY CLIPPED PARTICLE EVERY FRAME. `clipbounce` in a
  block means a traceline a particle a frame (`r_particle_tracelimit` is
  0x7fffffff), about 4 microseconds each on the desktop: Source's 800 drops a
  second, 1,550 alive, took 650 frames a second to 133. `r_partinfo` marks
  such a type `(+traceline)`. The old rain's 130 drops, with the map's other
  systems, read 565 where the map without any read 787.
- A DROP THAT MEETS NOTHING LIVES ITS WHOLE `die`. The engine's trace did not
  stop a drop at the sky's floor, so most of the old rain's drops were under
  the map for ten seconds, traced.
- THE FIX IS ONE TRACE A DROP: QC picks the point and the speed, traces along
  the fall, and uses the block whose life is the largest not over the fall
  time; the time left over the drop has "already fallen" (a lower start, and
  faster). Nothing to trace afterwards.
- WHEN THE COUNT WENT DOWN, THE SUBJECT'S OWN COUNTERS SAID WHY. The second
  cut held 256 particles where the first held 1,500 and the arm failed its
  count. `drops: made / born inside something / mean life` showed lives of
  0.42 s and a fifth of the box inside something: the first cut's 1,500 were
  mostly under the map. The threshold was the wrong thing, not the rain.
- A REPAIR THAT ASKS A HANDLE NOBODY TOOK REPAIRS FOR EVER. The first repair
  after a renderer restart probed the first trail system in the INDEX, which
  on surf_tensor2 no entity names: its handles were never taken, the slot
  read 0, the query read "", and the map's config was sent again every
  second, each time freeing every live particle of its 280 blocks. The arm
  passed (a drop lives 0.4 s). The review read it; `Emit_PsysRepair` asks the
  first system that EMITS, three times a map at most, and the arm grades
  `reloads`. (It also brings a baked map's blocks back after `vid_restart`,
  which nothing did before.)
- A TEXTURE'S EDGE IS EMPTY. A streak under a pixel wide puts most pixels'
  middles outside it; clamping the lookup there read `rain.vtf`'s outer
  columns, alpha 0, and the streak drew as dots: 8 to 15% of the rain's
  pixels in blobs under 8, against 1.5% with the texture's mean (its 1x1
  mip, `texture2D(..., 8.0)`) standing in under two pixels.
- A SPARK'S `scale` IS ITS FULL WIDTH (`R_AddTSparkParticle`), where a
  sprite's is 4*sqrt(2) times its half-width: `pcf.py` had one number for
  both and rain was 5.66 wide. `stretchfactor -n` is a fixed half-length and
  only the batched draw reads it; a shader that sorts `blend` (any .vmt
  material) gets `GL_DrawTexturedSparkParticle`, which draws from the
  particle to 0.05 s of its travel ahead.
- THE ENGINE DRAWS A PARTICLE ONCE MORE IN THE FRAME IT DIES (killed on
  `die < particletime`, then moved and drawn, time advanced after), and a
  spark's quad is centred on it: a drop given exactly its fall time shows a
  frame of travel and half a streak past the surface.
- `rain.vtf` IS A 32x32 GREY BLOB (0.506, alpha to 0.84), not a line: the
  streak's shape is the quad's.
- `alpha` AND `alpharand` ARE A FLOOR AND A RANGE (`alpha + alpharand *
  frandom()`). `pcf.py` wrote the middle and half the range since it was
  written: every baked system drew the upper half of Source's alpha.
- A PNG SCREENSHOT STALLS EMISSION: frames longer than 0.25 s are clamped,
  so the drops made between two `emit_list`s that bracket two shots read 455
  a second, not 608. The arm's tie divides by what was made, not the rate.
- THE BAKED FILES ARE THE TOOL'S: `python tools/pcf.py --map <map>` writes
  `particles/<map>.cfg` and `data/mapparticles.txt` in `C:\FTESurf\ftesurf`.
  Neither is in git or sent by a lobby; `C:\FTEQuake` has neither.
- DEPLOYED 12 Oct (UTC 11 Oct) from `a68e411`, main's tip: csprogs `e04ccb61`,
  the file the arm passed on, to the Pi at 21:13:22Z with 12 lobby rows and 0
  players, and to both installs at 21:13:23Z with no game running, under the
  rig lock. Twelve lobbies restarted, hashes read back from the host;
  `tools/pi_lobby_smoke.py` on 27510 at 21:13Z was served that csprogs, drew
  the board, no QC error. `.prev` is 657's `c7596c74`. Then `tools/pcf.py
  --map surf_tensor2` and `--map surf_boreas` over `C:\FTESurf\ftesurf`:
  `particles/surf_tensor2.cfg` `e42ae639`, `surf_boreas.cfg` `bb277920`,
  `data/mapparticles.txt` `6c1f06ec`, each byte-equal to the file the arm ran
  on (they were `0ffb08be`, `ebc0f495`, `17cb909e`; those three are kept in
  the task root, `tmp/bake-installed-before`). `C:\FTEQuake` has no particle
  files and was given none. The Pi's qwprogs was swapped for the same bytes
  (`35fda5eb`); menu.dat, default.cfg and the exes did not change. The smoke
  grades the board: no client has looked at rain on a lobby.

### How bright a mote is (Patch 657) -- 2026-10-12

- WHERE: `src/client/cl_emit.qc`, `Emit_Exposure` / `Emit_MapHDR` in front of
  `Emit_MoteShader`; one shader an exposure (`ftesurf_mote<exposure * 100>`).
  `emit_list` says `motes are lit at exposure N: <why>`;
  `vbsp_emit_exposure` (-1 the map's, 1 Source without HDR) is read at load.
- QC's `fread`, `fseek` AND `fsize` EACH LOAD THE WHOLE FILE on first use
  (`pr_bgcmd.c`, FRIK_FILE_READ_DELAY; a failed allocation is a Sys_Error).
  The first cut guarded a 495 MiB map with `fsize`, which read all of it to
  answer; the review read the builtin. `search_begin` and
  `search_getfilesize` ask the file system. 872 bytes of a map's header still
  cost its 24 MB (median), so the read is skipped unless the answer turns on
  it, and the arm counts the `qcfopen("maps/<map>.bsp"` lines.
- A WALL OF ONE KNOWN COLOUR: from the void over a map, looking straight up,
  nothing is drawn, and `r_clear 1` with `r_clearcolour` paints what is. A
  Frozen mote holds its alpha for 11 s, so one row is photographed over
  black, a grey and white (`cfg/test/p657bright.cfg`). The HUD's "Air:" line
  and the crosshair are in that frame: the blob finder's box stays clear of
  the first and its 40-pixel floor drops the second.
- A CHECK THAT A THING IS NOT THERE NEEDS SOMETHING THAT IS. "A white mote on
  white is not there" passed on a frame with no motes at all; the blue row
  beside it is now part of the same check.
- A MAP'S EXPOSURE CEILING IS A logic_auto OUTPUT, not a key of the
  env_tonemap_controller: `"OnMapSpawn" "tonemap,SetAutoExposureMax,1.2,0,-1"`,
  the commas 0x1b in newer maps (surf_dune) and commas in older (surf_tensor2).
  surf_dune's is 1.2; this file's earlier "max default 2" read its Min.
- UnlitGeneric's PIXEL SHADER IS `vertexlit_and_unlit_generic_ps20b.fxc`
  (`unlitgeneric_dx9.cpp:198`), whose :481 ends in a fog term and
  TONEMAP_SCALE_LINEAR. `unlitgeneric_ps20b.fxc` says TONEMAP_SCALE_NONE and
  is debugnormalmap's.
- 71% OF THE LIBRARY'S MOTE VOLUMES ARE COLOURED (3,737 of 5,297), and a blend
  with one alpha has one slope for three channels. The first cut took the
  slope from the mote's luminance and drew `0 128 255`'s red at 0.140 on
  white for 0.422, worse than the 0.236 it replaced, with the old arm's
  colour check retired in the same commit. Judge a coloured row per channel.
- DEPLOYED 12 Oct (UTC 11 Oct) from `35510e0`, main's tip: csprogs `c7596c74`,
  the file the arm passed on, to the Pi at 19:40:26Z with 12 lobby rows and 0
  players, and to both installs at 19:40:27Z with no game running, under the
  rig lock. Twelve lobbies restarted, hashes read back from the host.
  `tools/pi_lobby_smoke.py` on 27510 at 19:40Z: the client was served a
  csprogs hashing `c7596c74`, drew the board, no QC error. `.prev` is 663's
  follow-up `9fc0940b`. The Pi's qwprogs was swapped for the same bytes
  (`35fda5eb`); the installs' qwprogs, menu.dat, default.cfg and the exes did
  not change. The smoke grades the board: no client has looked at a mote on
  a lobby.

### env_fire's smoke, floor and reach (Patch 656) -- 2026-10-12

- WHERE: `src/client/cl_emit.qc`, `Emit_SmokeSpec` / `Emit_SmokeBlock` /
  `Emit_SmokeShader` (slots 13-16 of a size class) and `Emit_DropFires`; the
  two sheets' frames are `cl_smokesheet.qc`, written by `tools/smokesheet.py
  <game>_dir.vpk ...`. `vbsp_emit_firesmoke 0` is the fire without it.
  `emit_list` has five env_fire lines: sheet, smoke, reach, light, floor.
- A SMOKE EFFECT WHOSE SHADER DID NOT COMPILE STILL ANSWERS, and draws a red
  square. `%g` writes `1` for 1.0 and GLSL 1.10 will not multiply an int by a
  float: three of five smoke shaders failed while `emit_list` said "10 of 10
  smoke effects answering". The constants go in as `float(%g)`, and the arm
  counts "compilation error" lines.
- SPRITECARD IS NOT FOGGED: `spritecard_ps20b.fxc:184` ends in
  `PIXEL_FOG_TYPE_NONE`. The first cut fogged flame and smoke "as Source
  would"; the review read the shader. (An inline GLSL program CAN take the
  frame's fog, `!!permu FOG` and `#include "sys/fog.h"`, and UnlitGeneric,
  the motes' shader, is fogged.)
- fteqcc DIES WITHOUT A WORD ON A GLOBAL USED ABOVE ITS DECLARATION when the
  use is a pointer assignment: exit 0xC0000005, no error line, and `build.ps1`
  prints only "fteqcc failed on cl_progs.src". It was `em_drop =
  memalloc(...)` in Emit_Alloc, 350 lines over `float *em_drop;`. Bisect by
  change block against the last commit that built.
- THE DROP MUST MEET SOURCE'S SOLIDS, NOT cl_sprites.qc'S OCCLUDERS. Those are
  SOLID_BSP copies made for the glare test: absent at `vbsp_glare_brush 0`,
  and at its default they include func_illusionary. `Emit_DropFires` stands
  them down, stands up tier 1 of `Sprite_OccluderTier` with func_brush's
  Solidity, traces, and puts everything back. `.solid` alone is not seen until
  `setorigin` links the entity again. Without the brush entities surf_lost2
  reads "107 lit (mean 778), 71 with nothing"; with them "178 lit (mean 24)".
- TWO SHADERS IN ONE SORT BUCKET ARE DRAWN IN THE ENGINE'S RUN-LIST ORDER,
  which is whichever particle type last went from empty to not. The smoke
  shader is `sort banner`, a bucket before the flame's `additive`.
- A VTF'S IMAGE COMES AFTER ITS SHEET. The largest mip is the LAST thing in the
  file; "header, thumbnail, then mips" read vistasmokev1's colour as 0.55 where
  it is 0.33 (`tools/sparkleshape.py`'s `top_mip` is right only for a .vtf with
  no sheet, which sparkles is).
- `tcoords s1 t1 s2 t2 1 <n> <stride>` picks one of n frames across the sheet
  for each particle (`p_script.c`, the tcoords branch). smoke1's six stills are
  one block that way.
- SMOKE IS SEEN AS DARKENING, AND ONLY OVER A STILL BACKGROUND. The arm takes
  the same shots with and without and compares a box over the flame with one
  beside it (dust off: the side box is equal to the hundredth). Over
  surf_road_to_hell's lava every pixel differs between any two frames, AND
  LAVA IS FLAME-COLOURED: a far-fire check that counted flame-bright pixels
  looking down on that map read 3,600 with no fire in it. The reach stage
  compares fire on with fire off instead: 32 pixels at 6,000 units, 0 before.
- `traceline` AT MAP LOAD HITS THE WORLD and its static props: 233 of
  surf_classics2's 233 fires found a floor (mean 15 units down, most 565).
- A CAMERA IN THE VOID SEES IN. `setpos` far above a map with `noclip` looks
  through the backs of its ceilings: how the reach stage sees a fire from
  6,000 units with nothing to walk on.
- DEPLOYED 12 Oct (UTC 11 Oct) from `87c63c8`, main's tip: csprogs `bc2b938e`,
  the file the arm passed on, to the Pi at 18:14:05Z with 12 lobby rows and 0
  players, and to both installs in the same second with no game running,
  under the rig lock. Twelve lobbies restarted, hashes read back from the
  host. `tools/pi_lobby_smoke.py` on 27510 at 18:14Z: the client was served a
  csprogs hashing `bc2b938e`, drew the board, no QC error. `.prev` is 661's
  `6cb9b6c2`. The Pi's qwprogs was swapped for the same bytes (`35fda5eb`);
  the installs' qwprogs, menu.dat and the exes did not change. The smoke
  grades the board: no client has looked at a fire on a lobby.

### Blended particles are drawn once (engine Patch 658) -- 2026-10-12

- WHAT WAS WRONG. `GLBE_SubmitMeshes(batches, start, stop)` INCLUDES `stop`
  (the D3D and Vulkan loops stop before theirs). `GLBE_DrawWorld` submitted
  PORTAL..SEETHROUGH+1, drew the lights, then SEETHROUGH+1..NEAREST: the bucket
  after SEETHROUGH, UNLITDECAL, went through both. Only the script particle
  system's default shaders sort there (`p_script.c`, the templates for blend,
  blendcolour, invmoda, invmodc, subtract).
- WHAT 658 DOES. The first submit stops at SEETHROUGH. The templates ask for
  `program defaultsprite#TWICE` (alpha becomes a * (2 - a)) or `#TWICEC`
  (colour, c * (2 - c)), which is exactly what two blends left; clamped to 1
  first. Beams and fans were drawn once all along (the render queue) and keep
  the plain program under `<texture>_blend1`.
- `#NAME` AFTER A PROGRAM NAME IS A `#define`, with no `!!` line needed
  (`gl_shader.c`, the program-name parser). The built-in programs live twice:
  `engine/shaders/glsl/*.glsl` and as string literals in `engine/gl/r_bishaders.h`.
  Edit both; the header is what is compiled, and no rule regenerates it.
- THE ARM, `tools/p658once.py`: six still dots over a wall photographed bare.
  The one that counts draws is P, a shader with the OLD template text: 0.549 of
  the wall left on 658 (one draw of a sprite 0.914 opaque: 0.543), 0.306 on the
  645 engine (two: 0.295). P is graded against the sprite file's own alpha:
  the first cut compared it with the default shader's dot, and "T is P squared"
  is true for ANY number of draws.
- IT DOES NOT SEE beams, fans, subtract, invmoda, blendcolour, fog, another
  renderer. `tools/test_p645lines.py` is the check that a backend change left
  the engine-drawn run lines alone; it needs surf_voyager and a recording that
  are not in `C:\FTESurf` (ask the run-line session, or read its header).
- THE BUILD, in a worktree of ftequakers main: the recipe under Patch 645
  above. Client only (no server file, plugin or header moved). Stamp
  `git-7229-patch-658-0-g7501a6cce`, sha256 `4faa7ff4`; the DLL list from
  `objdump -p` is the installed binary's.
- DEPLOYED 11 Oct 16:58Z (12 Oct here): that client as `C:\FTESurf\ftesurf64.exe`
  and `C:\FTEQuake\fteqw64.exe`, no game running, under the rig lock; `.prev`
  is the patch-645 client `03989f66` in both. The arm had passed on those very
  bytes, and the run-line session's `tools/test_p645lines.py` read 28 of 28 on
  them. `fteqwsv64.exe`, the plugins, the progs and the Pi were not touched;
  the Linux client is not built.

### func_dustmotes in the game (Patch 648) -- 2026-10-12

- WHERE IT IS: `src/client/cl_emit.qc`, the Patch 648 section. One r_part block
  per LOOK on the map (`ftesurf_dm<N>`, written at load), one shader
  (`ftesurf_mote`) that draws the sprite itself. `emit_list` says
  `func_dustmotes: Source's motes, N looks asked, M answering` or
  `orbs, because <reason>`; `vbsp_emit_motes 0` is the old look.
- WHAT RIDES WHERE. `rgbf` reaches the shader as floats, not bytes: red is the
  size, green the life, blue the entity's colour as one integer (r + 256 g +
  65536 b, exact in a float), alpha the age. `tcoords` carries DistMax and
  Alpha in its whole parts. They are unpacked in the VERTEX shader: an integer
  that size does not survive being interpolated.
- THE DEFAULT BLEND BUCKET IS DRAWN TWICE A FRAME (BACKLOG, "Blended particles
  are drawn twice"). The first cut's shader was `sort unlitdecal`, like the
  engine's own, and every mote measured `1 - (1 - a)^2`: 0.975 for 0.85. The
  exponent of the fit was 0.906 where 0.4545 was expected, twice it, which is
  what gave it away. `sort additive` is drawn once; `sort blend` goes through
  the per-particle sorted path instead of a batch.
- A LOOK DEFINED THIS FRAME DOES NOT EXIST THIS FRAME. The block is `localcmd`
  text; a `pointparticles` at it before the engine has read it is dropped
  without a word. A volume loses a frame. `emit_mote` says "look N is new; say
  it again", and the arm says each row twice.
- THE KEYS ARRIVE NARROWER THAN THE MAP WRITES THEM. `func_dust.cpp:87-93`
  sends the lifetimes in 4 bits, SpawnRate and SpeedMax in 12, DistMax in 16:
  a LifetimeMax of 20 is 4 on the client (122 volumes on 39 maps wrap).
- SOURCE KEEPS 2,048 OLD-STYLE PARTICLES IN THE WORLD
  (`particle_iterators.h:20`, refused at `particlemgr.cpp:1150`). 173 maps
  hold volumes that together ask for more; `Emit_Frame` scales every mote
  volume in range alike (`dm_thr`), and `emit_list` prints the scale.
- A RULER FOR SOMETHING TWO PIXELS WIDE: `emit_mote` stands rows of BLACK motes
  at depths it is told, over a wall photographed bare. A black mote only
  darkens, so `1 - (shot / bare)^2.2` is its coverage per pixel whatever the
  wall is. The wall must be bright: over the dark doorway the grader refuses
  ("too dark to read"), which is why the rows sit at rises 0.17, 0.10, 0.04.
- A PIXEL IS `size / 10000 * height / 1.5` at fov 90 (the fov is the 4:3
  frame's, as in Source), whatever the depth.
- AN r_part PARTICLE STARTS AT A RANDOM ANGLE (`p_script.c:1118`) unless the
  block says `rotation`. A shader that reads the quad's own frame draws its
  square tilted at random; the review saw it in a screenshot's 6% contours, no
  check did. At `rotation 0` the quad is a diamond (`:7166-7169`).
- `die min max` IS NOT A RANDOM LIFE. The engine starts such a particle already
  aged by the difference, alpha and colour alike (`:5233-5282`), so no channel
  tells age from birth. The block says `die LifetimeMax` and the shader ends a
  mote at its own life: `r_partinfo` counts LifetimeMax, not the mean.
- A FIXED-FUNCTION BLEND IS A STRAIGHT LINE OVER THE WALL'S BRIGHTNESS and
  linear light is a curve, so it is exact at two walls and only there. Which
  two is a choice: black and white drew a white mote at alpha 0.087 0.108 too
  bright on a 0.37 wall (measured, the arm's second control); a 0.25 grey and
  white is 0.023 over there and 0.10 under on 0.04. A black mote is exact
  everywhere, so a ruler of black motes cannot see this: row W (white, Alpha
  26) is what does.
- `tools/p648motes.py` IS THE FALSIFIER, with two controls kept in its header:
  the depth term and the pool's scale out (SIZE at 330 reads 18.5 px for 88,
  the engine holds 9,009 for 2,560), and `rotation 0` out with the blend on its
  first anchors (UPRIGHT reads 1.23 px towards the sides for 0.00, row W as
  above). `tools/sparkleshape.py <game>_dir.vpk` is where 0.25 and 1.17 come
  from: the computed shape against Valve's texel by texel (mean difference
  0.028, HL2 and CS:S alike).
- `vid_restart` TAKES 8 s ON THE RIG, so an arm that reads 10 s after it has
  seen 2 s of motes: read twice and grade the rise (315, then 981).
- DEPLOYED 12 Oct (UTC 11 Oct) from `7e37d30`, main's tip, so with Patch 649
  under it: csprogs `88986a28`, the file the arm passed on, to the Pi at
  14:53Z with 12 lobby rows and 0 players, and to both installs at 14:53:36Z
  with no game running, under the rig lock. Twelve lobbies restarted, hashes
  read back from the host. `tools/pi_lobby_smoke.py` on 27510 at 14:54Z: the
  client was served a csprogs hashing `88986a28`, drew the board, no QC error.
  `.prev` is 649's `95f30046`. The Pi's qwprogs was swapped for itself
  (`35fda5eb`, the same source compiled a day after `76e00522`); the installs'
  qwprogs, menu.dat and the exes did not change. The smoke grades the board:
  no client has looked at a mote on a lobby.

### Release shipguard lifecycle controls — 2026-10-12

Six literal misses were not release baselines: `maps/%s.bsp` is mounted or
runtime-downloaded content (`Emit_MapHDR`); `data/mapdl.net.txt/.tmp` are the
menu's validated network cache/parsing scratch (`Mdl_Reply`); `data/mapbuild.txt`
is player build preference state (`ui_pick_set`); `maps/settings/local/` is the
editor's own overrides/transaction files (`MapSet_Path`, `ZoneEdit_SettingsSave`,
native `SV_LoadEditorRuleset`). Four exact exclusions and one trailing-slash
prefix express those lifecycles. Do not exempt all maps/data or read-mode opens:
shipped `data/mapdl.txt` is the cache's fallback, and local zone JSON is a release
baseline distinct from local editor settings. Runtime cache/preferences and both
VFS/physical local-settings spellings are also archive/stage-denied.

A mutation could say CAUGHT merely because an unrelated literal already missed.
`shipguard.py --mutate` now requires SHIPPED -> MISS for the same literal after
hiding the chosen glob; invalid/negative indices refuse. `test_shipguard.py`
requires actual thumbnail/local-zone omission flips, all five menu snapshots,
neighboring path/read-mode boundaries, and a pre-existing MISS which cannot
satisfy a cfg-glob mutation. Use an owned fresh `--work-root`.

The first all-gates preview then correctly refused three `.ttf.prev` copies
seeded from the install by `release_tree.py`. The font glob now denies `*.prev`;
all three original faces and both OFL notices remain shipped, and disk backups
are untouched. Do not weaken the global backup tripwire or hide this failure by
cleaning the install. `test_release_deny.ps1 -WorkRoot <owned-fresh-root>` extracts
the production policy/function, allows a real baseline stage/archive, and
individually refuses seven runtime/backup/case-variant paths in physical fixtures.
Measured Windows: 12 shipguard controls, real deny fixtures, and an isolated
network-mocked full pack passed. Mocked R2 calls are not service access proof;
no Linux compile/runtime, production publication or deployment is claimed by
this tooling fix. Literal coverage still excludes computed/engine-convention
assets; zero MISS is not proof of a complete product archive.

## The milk visualizer (Patch 467)

**P688/P691 thumbnail lifecycle (2026-10-13):** atlas decoding can be asynchronous,
but `data/mapmeta.txt` is a locally generated table, not a menu download. Caching
the map key is not proof that its row was found: P688 never noticed later table
publication/replacement on the same map. P691 retries misses after 5s and valid
coordinates after 30s, reading at most 64 rows per active sky view. Keep old valid
coordinates only during a same-map refresh; map changes clear them. Close streams
on world load, renderer reset and sky disable. Strict digit tokens prevent `stof`
turning bad page text into zero. `milk_skyinfo [refresh]` reports rows/maxbatch.

`tools/test_soundsky_metadata.py --output-dir <owned-root>/artifacts/<arm>` changes
only its private runlines overlay's metadata after live phase markers. Late row,
1,025-row replacement, removal/malformed row, restart, off/on and automatic valid
refresh all acted; compiled no-retry control failed late recovery. Screenshots
show neutral/tan/olive/neutral. A cfg `wait 1` can allow two sky views before its
next diagnostic (observed rows128), so it is NOT proof of one frame's file budget:
measure actual per-call maxbatch (64) instead. Existing cached atlas bytes at the
same filename are not force-refreshed by a metadata scan.

Blank-line EOF pitfall measured by the P691 live fixture: `if (!ln)` still stops
at a blank line (rows0), because QCC logical-not emits OP_NOT_S, which checks both
null handle and empty content. The builtin contract's **`if not(string)`** means
that QC syntax, not C-style `!string`. Use `if not (ln)` for the raw null-handle
branch (default ifstring flag off); corrected late/restored fixtures read rows2
and resolve the valid row. Both the failed run and corrected run are retained.
A failed metadata fopen must also clear coordinates/palette: preserving them is
valid only while a successfully opened same-map scan remains in flight.

- `src/milk_sys.qc` (both VMs, like sui_sys.qc) is a MilkDrop-style feedback
  renderer on render targets: scene -> warp -> sprites -> bloom -> composite, one
  tick at a FIXED 60 Hz. `src/menu/m_milk.qc` owns the menu's raymarched space
  (four stations; changing screen flies the camera) and the VISUALS / MUSIC
  screens; `src/client/cl_milk.qc` the sky (`r_skybox milk`). Shaders are
  `ftesurf/glsl/milk_*.glsl`; `milk_common.h` is the `w_user[]` slot table and
  must stay in step with `Milk_Pack`. GL only -- `Milk_Supported()` turns it off on
  any other renderer (Vulkan's 2D render-target switch is an empty function).
- Harness: `+set milk_bootcheck 1 +exec test/p467milk.cfg` photographs all four
  stations and quits; `3` shoots one station twice (diff them: identical = frozen
  sim); `4` with `test/p467perf.cfg` prints frame rate with the space on, then off.
  `test/p467sky.cfg` (surf_rookie, setpos-aimed) for the sky, with the map's own
  sky as the control. Screenshots are JPEG: a 2256x1380 PNG blocks the main thread
  ~2 s, and the harness steps are timed.
- Render-target rules that cost time here: configure a target with the 4-arg
  `setproperty(VF_RT_DESTCOLOUR, ...)` before the first `drawpic` whose material
  names it; `[shader] name ... prog 0` in the log means the program is on the PASS,
  not missing; a 2D polygon with a GLSL material falls back to something ugly off GL
  (MM_Shade drew a black half-screen on Vulkan).
- THE WORLDS AND THE IN-WORLD PANELS (2026-09-30). `milk_world` picks the menu's
  space: `lattice` (`glsl/milk_scene.glsl`), `monolith` (`milk_monolith.glsl`, a
  brutalist void), `vessel` (`milk_vessel.glsl`, one `#S0..#S3` variant per
  station, swapped halfway through a flight), `fractal` (`milk_fractal.glsl`,
  likewise: two pseudo-Kleinian cathedrals, a Mandelbulb, a Menger tunnel) or
  `shuffle`. `milk_panels 1` draws
  MAIN / VISUALS / MUSIC into render targets `mm_ui0/1` that the world raymarches
  as a slab's face; `milk_present.glsl #PANELS` redraws them crisply over it,
  gated by the scene target's alpha (+1 slab A, -1 B), and `MM_MouseToUI` traces
  the cursor back through the camera `milk_ud` holds. At rest a panel is laid out
  face-on at one texel per pixel (`MM_PanelPlace`), so its text is the font's
  raster; the camera orbits the panel only while the cursor is off it. The slabs
  are intersected (`panTrace`), never marched: in the SDF they cost the lattice
  4 ms a frame on the N100.
- `milk_scenediv 2`: every world raymarches every other tick while the feedback
  runs every tick -- except `milk_quality 4` ("ultra", high's resolution) and the
  lattice at high, which raymarch every tick. The camera and panel slots in
  `w_user` are only repacked on a raymarch tick, because the present and the
  cursor trace must match the image that is on screen.
- Resolutions: the targets are `180 + 180 * quality` high (360 / 540 / 720, by
  aspect; `MM_Frame`), the scene target a per-world 50-100% of that
  (`milk_scenescale`), bloom at 1/2 and 1/4, and the present stretches `out` to
  the screen bilinearly (or FSR 1's output, below). The present is a quad
  `MM_CROP` bigger than the screen, hanging off every edge (`mm_quad`), rather than
  a crop inside the shader -- which had scaled even a screen-sized image by
  1/0.97 -- so an image the quad's own size (native, FSR's) lands texel for
  pixel; the panel maths (`MM_PanelPlace`, `MM_MouseToUI`) take its per-axis crop
  (`mm_cropx/y`). Only the panels are drawn at screen resolution (the `#PANELS`
  overlay). The raymarch is the cost. N100, monolith MAIN, a tick a
  frame: ~19 ms a raymarch at medium (511x313), ~50 at high (942x576), against
  ~3 ms a frame for everything else the milk does -- `+set milk_bcdiv 1` against
  `999` (a harness knob pinning the raymarch to every Nth tick), 2026-09-30.
- THE FRACTAL WORLD (2026-09-30). Each station turns about its resting camera
  (the bulb about itself), so the camera can rest for the panels while the
  fractal moves: MAIN and PLAY are Knighty's pseudo-Kleinian with two fold
  boxes, the camera at a box corner (19 and 15 m from any surface, from a
  Python port of the DE -- the corners were the roomiest spots in all seven
  boxes scanned), VIS a
  power-8 Mandelbulb lit from just behind its rim, MUSIC a Menger slab drifting
  down its tunnel with the hole edges on the spectrum. The hit tolerance is the
  pixel's footprint (`PIXA`, from `dFdy(tc)`); 100-131 fps at medium on the
  N100, in-world panels. Its poses in `MM_PoseW` are the shader's `ORG`s; each
  anchor is the camera plus 400 m along that station's `LIGHT`, so the trails
  and the shafts come from the light. It plays `ftesurf_void` on "auto".
- KICK STREAKS (`milk_streaks`: 0 off, 1 menu, 2 the sky too; VISUALS -> look).
  `Milk_WaveSpawn` throws a wave on each rise of `milk_hit` (a kick an arc,
  sometimes the waveform line; a snare a comet), `Milk_WavesDraw` draws each as
  ribbons INTO the fresh feedback frame after the owner's sprites, and
  `glsl/milk_wave.glsl` bends each line by `milk_spec`'s waveform row, levelled
  to the mix's RMS. Lattice 1, vessel 0.8, fractal 0.7, monolith none. They fly
  at `milk_wavedepth` (the menu: the anchor's distance x1.05 + 2.5 m) and are not
  drawn where a model is nearer: the scene's alpha is now 2 + the distance for a
  hit the world calls a model (`milk_alpha` in `milk_common.h`; the lattice's
  cubes, towers and orbs, the vessel's cells, plankton and eye, the fractal
  everywhere but the Menger tunnel), a panel's mask as before, else 0 -- read it
  through `milk_panelmask()`. The test is at draw time, so the echoes already in
  the trails stay where they were drawn. Harness: `milk_bcwaves <s>` throws one
  every s seconds whatever plays (both VMs), `milk_bcwavekind` pins the kind, and
  `milk_bootcheck 9` shoots six frames.
- LIGHT SHAFTS: `glsl/milk_shafts.glsl` blurs the scene's brightest light toward
  `M_FOCUS.xy` into `<p>_b3` at 1/4 size, only while `milk_shafts > 0` (the
  fractal); the comp adds it at `M_FOCUS.z`, which is the menu's shaft strength
  and the sky's landing ring.
- THE SPEED PAGE (VISUALS -> speed): `milk_res 1` renders at the present's quad
  (`MM_Overscan`: the screen plus an even margin), scene scale 1; `milk_fsr 1` runs FSR 1 (`glsl/milk_fsr.glsl`, EASU then RCAS)
  once a tick into `<p>_up`/`_up2`, sized past the present's crop so the present
  still takes one tap; `milk_checker 1` raymarches a half-width target
  (`#CHECKER`, parity in `M_EVENT.z`) that `glsl/milk_resolve.glsl` fills out
  from its neighbours and the last frame (`<p>_scp`); `milk_cone 1` runs the
  world's `#CONE` variant at 1/4 size (`glsl/milk_cone.h`) and the scene pass
  (`#CONED`) starts each ray where that says nothing can be. All menu-only and
  all off by default; the page prints what it renders and the frame rate.
  N100, medium, a raymarch every tick (`milk_bcdiv 1`), MAIN: monolith 35-38 fps
  -> checkerboard 57, coarse pass 36-38 (noise); fractal 58 -> 99, 69, both 110.
  Lattice at normal settings: 123 fps, FSR 38, native 21, native+checkerboard 29.
- `show_fps` over the milk menu is the menu's own (`MM_DrawFps`, drawn last in
  `m_draw`): the engine draws its counter first, under the menu's full-screen
  backdrop. Over a live game the engine's still shows.
- More harness: `milk_bootcheck 10` runs `milk_bcseq`'s '|'-separated commands
  at the station `milk_bcstation` names, bare, a shot after each -- a sweep for
  tuning a look. A command with ';' in it goes in an alias in a cfg exec'd
  first (a ';' on the command line splits the `+set`). `milk_bcvispage 1` opens
  VISUALS on the speed page in the tour. `p467milk.cfg` and `p467perf.cfg` pin
  the streaks and the speed page too -- a new setting is the owner's own in every
  harness run until it is pinned (a tour shot showed their "menu + sky").
- THE BEAT GATES (2026-09-30). `milk_beat` pulses on every engine onset, hats
  included (7/s on `ftesurf_drive`). The visuals answer `milk_kick` (a bass onset
  gated by the bass ratio above 1.3) and `milk_hit` (a kick, or a treble onset
  with the mids above 1.2): `M_AUDIOATT.w` is `milk_hit`, `M_EVENT.w` `milk_kick`,
  and the flash is `milk_hit`. `Milk_ReactCurve` maps the cvar (0/1/2) to
  0 / 0.6 / 1.0 -- "wild" is the old "normal". `python tools/p468react.py LOG`
  replays a `cfg/test/p468react.cfg` trace through the same gates (keep the two in
  step); the menu tour (`milk_bootcheck 1`) prints `big hits N in T s` from the
  live QC to check it against.
- `milk_grade` (VISUALS "Colour grade", `M_TIME.y`): `milk_grade()` in
  `milk_common.h`, after `aces()` -- the image cooled and a little desaturated,
  colours near a pure red, green or blue kept and pushed.
- The vessel's x-ray films: `gfx/env/xray1.jpg` / `xray2.jpg`, grayscale JPEGs
  (q90, from the red channel the shader reads), tracked and in the ship set; the
  source PNGs beside them stay git-ignored. PLAY hangs one behind the plankton, VISUALS
  mirrors the other in the cornea; without them the maps are `$blackimage`. The
  harness start line prints `films` (bit 1, bit 2) and the art tour
  (`milk_bootcheck 7`) ends with `r_imagelist`, which says whether they loaded.
- Sound: `python tools/mkmusic.py` writes every generated track to
  `ftesurf/music/` (dream -- still `mkmenumusic.py`, byte-identical -- plus
  monolith, vessel, canopy, void, drive) and the menu's effects to
  `ftesurf/sound/milk/`. All git-ignored and deterministic; menu music "auto"
  plays the world's own track. The menu plays effects only if `click.wav` exists.
- More harness modes (`MM_BootTick`): `4` measures the station `milk_bcstation`
  names; `5` the panels (a fake cursor via `milk_fakemouse`: pick at rest, orbit,
  pick again); `7` every station bare -- run with `+set milk_panels 0` AFTER the
  exec, or the cfg's pin wins; `8` a dive into `milk_bcworld`. The harness cfgs
  now pin `milk_panels 1`, `milk_sfx 1` and `s_inactive 1`.
- The engine half: `snd_getvis` / `snd_visimage` analyse the software mix, and
  `snd_fx_lowpass` is the menu's "muffle the game". OpenAL output bypasses the
  mixer entirely, so there is nothing to analyse there.

### Windows-output/spatial sky verification (Patch 688)

- `MilkSky_WorldLoaded` has valid world bounds but `serverkey("map")` was empty
  in the acted dedicated Source-map fixture. An initial-only metadata lookup
  silently leaves page/cell -1 forever. Cache a zoned name and resolve changed
  live keys; reset it on world load. Final live atlas5/thumbnail RT pixels acted.
- Keep `program milk_sky` INSIDE its pass, before both `$rt:` maps.
  `Shaderpass_DefineMap` bundles successive maps only when `pass->prog` exists;
  moving the program to shader scope overwrote the first map and left the second
  sampler blank. A solid fragment probe acted, yet map colours were black.
  Direct RT preview proved the thumbnail was valid: this was sampler binding,
  not an image/renderer failure. Restore probes and verify the source diff.
- The native shader diagnostic's `prog` counts shader->prog, NOT pass->prog.
  `prog 0 passes 2` alone is not failed GLSL compilation. Inspect actual pixels.
  WGL production-fragment controls certify geometry/tones, not in-game RT state.
- `milk_bootcheck 1` needs a disconnected client to tick/fly its menu world. A
  dedicated-map fixture timed out in the level; disconnecting before menu_restart
  and togglemenu made the same screenshot control act. Keep its first failure.
- Upload `snd_visimage` on unavailable data too: native supplies zero spectrum /
  neutral waveform, whereas skipping the upload freezes a previously live image.
- Windows output includes ANY ongoing default-device playback. A later quiet
  rerun had nonzero external sound after the owned tone stopped, so it was not a
  silence pass/failure. Do not mute/kill the owner's apps; retain the earlier
  controlled quiet arm separately. Local source0 close/reset still acted.
- Cold native control/subject at the inspected P687 base both had 35 compiler
  warning occurrences / 26 distinct payloads, none new. Make peer-target warnings
  are separate. PATH must include UCRT DLLs for clangd's GCC query; the first CLI
  check failed system-header extraction. Correct PATH and `--tweaks=` gave zero
  errors. Editor diagnostics without this task's compile database were fallback.

## Renderer alpha admission — P701, 2026-10-14

A shader-level alpha test is not enough: test real multi-mesh material batches.
P700's default plane-admission loop rejected an entire batch if any mesh was
rear/near-span, hiding otherwise provable Kitsune foreground planes. The initial
one-face-per-batch fixture missed it. P701 preserves material/world/state guards
but admits geometry per face through the existing bounded sorter. Real rear4029
plus three panes,72 yaw/order/first-or-last rear cases, exact mode0 replay and
intervening-slot fallback now pass; original/restored P700 veto ACT and fail.
Full client compile has zero new warnings and no cache-file changes. Fresh GPU,
startup and performance remain open; unsupported intervening commands still
abstain. See tools/p700alphafix.md; no decoder/trace prerequisite or worker change.

## Pitfalls discovered the hard way

### Native recovery journal publication boundary — P692, 2026-10-13

A failed journal OPEN does not exercise publication. Native replay used to close
journal.tmp, remove journal.json, then rename. Windows held-source sharing refusal
and Linux exact rename failure/interruption made the current client refuse but
its next launch start mixed because replay reads only journal.json. P692 publishes
with replace-existing rename without first unlinking that authority; both live
writers and cold pending-only publication share the helper. Failed commit retains
the old superset and all staged objects, allowing reclassification on replay.

Windows failure fixture: precreate only owned journal.tmp; hold it readable with
FILE_SHARE_READ|FILE_SHARE_WRITE but NOT FILE_SHARE_DELETE. Independently prove
truncate/write works and MoveFileExW of that actual source fails error32. A folder
write denial tests OPEN instead; a destination share denial can also prevent the
old unlink, hiding the missing-authority control. Linux companion interposer
matches the exact sibling rename, logs its native PID and forces EACCES/exit86
before commit or only after successful real commit. No key/pin override required.

Both row orders need an earlier installed content actor and preserved edited
zone, old version/no offline completion certificate while content is pending.
Every native launch has its own marker/log/error/exit and pre-cleanup job/group
census; inherited markers cannot grade the next phase. New live Windows controls
prove initial failure installs nothing then same-game retry, and a held ordinary
destination proves deferred pending-only publication then cold completion.

A reaped leader is NOT an empty POSIX group: terminate/confirm the recorded owned
group even when process.poll already returns. Early timeout/modal/census failures
must still export that launch's native log before any fixture deletion. Keep an
unconfirmed-phase guard if containment/evidence fails; a failed retirement must
write FAIL rather than preserving a prior PASS grade. Seven client-free negative
tests exercise these branches on Linux, including a real owned surviving Python
group member; Windows runs three applicable tests/four explicit POSIX skips.

Process interruption is NOT power loss. After-commit interruption can leave old
resolved staged objects behind because the newly committed journal no longer
names them; do not claim complete cleanup. A separate corrupt retry after that
arm consumes attempt3, so direct repaired retry and corrupt-next-launch evidence
must be separate fixtures if both are wanted. Native Windows cold replacement
interruption now has an acted test-only continuation below. Initial/deferred live
interruption remains separate coverage; the second-live-writer sharing failure
is acted in its test-only continuation. Retained
signed production and signed-loopback fixtures are different contracts: the old
Windows recovery driver requires the synthetic updater_fixture row and a full
union object closure, while new cold publication controls use ordinary crosshairs.
See tools/p692native_journal.md for tests, failed setup attempts and source-only
acceptance. Never equate this source pin with any installed/released binary.

### Windows deferred live journal fault debugger — P692 continuation, 2026-10-13

A lock before the initial live writer is not a deferred-commit fault. The new
native driver compares exact executable/companion PE text, finds the optimized
writer and two direct callers, and checks both observed caller RVAs/thread/ordinal.
It snapshots complete initial authority at the second writer, holds only that
writer's source sibling with writes allowed/no delete sharing, then lets native
OPEN/write/close/rename run. Exact pending-only temp, live error/state, one landed
content row/partial ledger, byte-exact full authority and staged objects prove
ACTED publication failure. Old control loses journal and starts mixed; current
corrupt retry refuses at attempt2, repaired retry completes at attempt3. This is
transient INT3 memory instrumentation, not a disk product patch or simulated API
return. Independent rename probe32 is not a sampled product-thread TEB error.

NEVER close CREATE_THREAD_DEBUG_EVENT.hThread early: ContinueDebugEvent at thread
exit closes debugger-owned handles automatically. A reused handle number then
let that automatic close destroy our journal source lock, producing native exit0
but helper exit90/CloseHandle error6. Leave debug-event process/thread handles to
their debugger lifecycle; separately acquired OpenThread/PROCESS_INFORMATION and
image/DLL file handles have distinct ownership. Failed subject06 remains FAIL.
Debug EXIT_PROCESS can precede final kernel/job exit accounting; a bounded natural
zero census after raw exit is valid, killing a success arm to force zero is not.

Cold failure cleanup must terminate and confirm the owned job empty BEFORE closing
its kill-on-close handle or clearing the unconfirmed-phase guard. A dead leader
alone is insufficient on Windows too. Failure exports must include journal.tmp,
not just *.json: a preceding live snapshot does not preserve a later failed cold
rewrite. Client-free negative controls exercise persistent cold job rejection,
exact failed-temp export/FAIL retirement and early live export failure guard.
Validate helper as a regular file and hash BEFORE creating runtime/evidence roots.
The native wrong-prologue control refuses before startup and verifies owned job0.

Signed-manifest order, not test destination order, defines the initial journal.
Legacy direct repair can leave the failed temp orphan when it does not rewrite;
export/grade that orphan rather than silently crediting complete native cleanup.
Both corrected matrices and a fresh repeat use immutable accepted external before/
subject clients, with settings/recording/local-zone/unmanaged-asset sentinels;
no mounted-content, Windows interruption, power-loss, default-HTTPS or deployment
claim. See tools/p692native_journal_deferred.md for reproduction and limits.

### Windows cold journal commit process interruption — P692, 2026-10-13

`tools/p692native_journal_interrupt.md` closes cold pending-only Windows
replacement process-interruption coverage, not power loss or initial/deferred
live interruption. External test-only debugger binds immutable client/companion
PE text, unique native call and exact return PC. P692's shared helper additionally
requires inspected stack/tail shape and the cold caller. Restore original bytes
and RIP, never simulate rename/register results. Observe real nonzero return,
thread/RVA/path checks, owned exit86 and observed job0 before/after cleanup.
Before-rename old client already unlinked full authority and next corrupt launch
starts mixed; P692 retains byte-exact full journal/refuses. After-rename authority
is pending-only attempt2 while all staged inputs still exist. Separate fresh
repaired arm completes attempt3; corrupt arm publishes attempt3 and repaired next
launch must refuse exhaustion without budget reset. Pending-only authority cannot
name resolved objects: repaired after-commit fixture explicitly retains these
orphans; no garbage-collection certificate. Settings/recording/edited local zone/
unmanaged sentinels and partial ledger/completion envelopes are independently
graded in both row orders.

First helper rejected because only native path separators were normalized; also
normalize expected argv paths. Preserve failed history/temp/log evidence. Native
wrong-byte rejection remains FAIL (helper90/job0), though its rejection assertion
passes. Timeout/export/containment negatives must retain retirement guards when
unknown. Frozen native repeat/review and retained paths are in the task checkpoint
under `C:/FTESurf-worktrees/wjcut-20261013T172400Z/artifacts/`.

### Windows initial live journal publication controls — P692, 2026-10-13

The first QKU_Apply journal has no prior authority. Before its rename, interruption
leaves a complete attempt1 temp but ALL selected destinations and ledger old;
acted next startup staying all-old is expected, not mixed-startup regression.
Both old27c58e and subject195dc58e have that initial-boundary safety. Do not copy
the old cold/deferred authority-loss expectation or fabricate prior authority.

Use tools/native_journal_initial.c + test_update_native_journal_initial.py:
match complete PE/companion text; source-bind first live caller, exact writer,
real native call/return and same thread; validate native paths and flags/root.
Subject frame/stack-probe target, tail wrappers, commit caller and direct/import
instruction targets are checked before mutation. Restore original bytes/RIP; no
native return spoof. The full attempt1 temp is copied at native pre, before any
initial content installation. Source-lock AFTER writer completion permits
writable OPEN but independently fails source rename32, then observes actual
product return0; this is not a TEB-error sample or failed writer-OPEN gate.
Preserve initial-error/stateerror/full temp/old ledger+destinations before
releasing retry acceptance; the lock itself is released after actual rename
failure. Same-game retry has separate markers/plans and exact HTTP counts.

Owned pre/post interrupts use child86; helper0, exact raw event order, first
writer/caller and observed job0 before AND after cleanup are mandatory. Before
cold startup leaves the complete temp/all-old state unchanged. After commit,
full attempt1 authority/temp consumed/all-old destinations seed separate fresh
direct-completion and corrupt-refusal/attempt2-pending/repair cases. Never spend
the same cold retry budget twice and label it a fresh fixture. Every arm exports
metadata INCLUDING .tmp, staged identities, logs and full runtime-file hashes
before retirement. Wrong-entry-byte native negative exits helper90 before startup;
its phase remains FAIL with exact sentinel export/job0, even when the negative
assertion passes. Equal/nested/existing resolved runtime/evidence roots refuse
before creation. Trusted synthetic roots only, not hostile path-swap/hardlink
protection. See tools/p692native_journal_initial.md. Deferred live interruption,
power-loss/flush ordering, staged orphan GC and canonical/fleet delivery remain
separate; test-only tooling does not bump ENGINE.txt or product tags.

### Native journal shared export/retirement guards — 2026-10-13

Legacy cold/live/deferred callers can grade AFTER managed content has landed.
Metadata/stage-only fallback is not preservation of those actual destination
bytes. Shared snapshot now exports raw metadata INCLUDING .tmp/logs, staged
identities and SHA256 of ALL regular runtime files (not only ftesurf), under an
independent export/receipt guard. A failed target refuses reuse before writing,
so an implicit finally retry cannot overwrite its FAIL/release its guard. A
complete separately named fallback cannot erase the earlier failed guard.
Checked scandir traversal propagates root/subtree listing errors and checks
links/reparse points before descent; Python3.10 rglob silently suppresses some
PermissionErrors and otherwise certified incomplete/empty inventories. Both
omission and same-target-release controls ACT on frozen04 and refuse on fixed05. Process guards separately require containment, full
export and receipt write; natural Windows success observes job0 BEFORE and AFTER
cleanup without termination. Unknown containment/export/receipt retains runtime
and FAIL. Fresh resolved runtime/evidence roots must be disjoint before creation.

An active client exclusively byte-locks `.ftesurf-updater/install.lock` in
QKU_FSLock. Three native attempts to full-read an active runtime failed and
correctly retained fixtures with job0; releasing a journal source lock did NOT
release the install lock. Active initial-refusal capture explicitly excludes
ONLY that exact control file and emits active_export true/full_export FALSE.
Unreadable metadata/content/stage still fails. Full post-containment export is
separate/mandatory; no broad PermissionError swallow or inferred lock hash.

Fresh frozen old/subject reruns:10 native matrices,94 PASS phase receipts with
both observed job0 censuses,130 full inventories,528 raw byte-hash checks, two
explicit non-full active captures;69 Windows client-free tests (including actual
duplicate callsite one-shot failures/listing denial). Separate legacy harness
has3Windows passes/4POSIX-only skips; no new Linux execution claim. Acting mock
baseline/current post-mutation grader refuses both: old fallback loses content
identities, hardened runner preserves them. This is test-only, trusted synthetic
roots, not a hostile path-swap/hardlink or power-loss certificate. Do not rewrite
older receipt strengths. Commands/limits: tools/native_journal_evidence.md.

### Deferred live journal before/after process interruption — P692, 2026-10-14

The second live writer is not the cold writer or initial full publication.
Extend the external initial debugger only with an explicit second-caller and
prior-authority snapshot pair. Restore/execute the first entry instruction by
single-step, preserve its other flags, rearm entry, validate inspected initial
then deferred callers on the same thread. At second entry require full attempt1
native authority/first temp consumed; at pre-native rename save the complete
pending-only attempt1 temp and validate real paths/root/flags/commit caller.
Before interruption restores the original instruction/RIP; after requires the
actual positive native result. Never force API results or infer ACT from timing.

Hold either first or last selected signed row, prove the other row installed,
exact partial old-version ledger/no certificate, both staged inputs and protected
sentinels. Use fresh fixtures for direct repair, corrupt-then-repair and corrupt
attempts2/3 then repaired exhaustion; do not consume/reset one shared budget.
Old pre-rename loses authority and ACTS mixed-content startup; save/export that
failure before explicit control-only initial-authority restoration. P692 keeps
full authority/refuses corrupt retry. Post-rename both retain pending-only
attempt1 authority and temp is gone. A reduced authority cannot retire the
already installed live row's staged copy: observed orphan, not safe GC.

Review found that live-boundary HTTP counts alone miss unexpected cold requests.
Keep that receipt AND compare/store the unchanged exact counter after ALL cold
branches, before PASS; repeated manifest/object and unknown cold GET negatives
must discriminate. Accepted frozen02:20new native scenarios/56phases, plus both
initial-regression matrices; combined74natural job0/full-export phases,
106full inventories/482raw byte-hash checks,81client-free Windows passes.
Wrong native byte exits90/job0 and retains FAIL/full sentinels; separate negative
assertion passes. No engine/product edit, new Linux/defaultHTTPS, hostile-root,
power-loss or deployment claim. Contract/commands/limits:
`tools/p692native_journal_deferred_interrupt.md`.

### Windows authority-bounded staged retirement controls — 2026-10-14

`tools/test_update_native_staging_windows.py` adds retained-signed-closure cold
controls for the existing `QKU_ReplayJournal`/`QKU_FSPurgeObject` contract. Each
three-row case runs pending-first/last: valid resolved objects ACT removal only
after successful reduction; a hash shared with a held pending destination must
survive reduction then disappear on repaired completion; real source-rename32
retains full authority and ALL objects. Exact ledgers/tuples/budgets/certificates,
protected bytes and stage maps are graded after natural pre/post-cleanup job0.
A separately seeded reduced-authority control retains a resolved orphan through
completion. It is not a new crash actor or permission to garbage-collect it.

A wrong-size corrupt object only tests size checking: omitting the native hash
comparison would still preserve it. Use a one-byte mutation of the signed bytes,
assert equal size/unequal digest, and retain the wrong-size case separately.
Unreferenced objects cannot independently falsify purge validation because the
native purge helper never visits them. Valid resolved removal is the ACT arm.

ThreadingHTTPServer defaults to daemon request workers; joining serve_forever's
thread does NOT join those workers. A final counter sampled before shutdown can
miss an already-accepted GET held before its increment. This driver makes
workers non-daemon with block_on_close, bounds socket reads, and samples only
AFTER context exit joins every accepted worker. An event-controlled real late
handler falsifies early census. Zero GETs is signed-mirror scope, not all-network
silence. Matrix01 predates these two review fixes and is not strengthened.
Accepted frozen02:11scenarios/22natural job0/full-export phases,22inventories/
81raw-byte hash checks;13client-free tests. Tooling only, no new engine patch,
orphan deletion, file/directory flush, hostile-root or deployment acceptance.
Contract/commands/provenance: `tools/native_staging_windows.md`.

### Bounded restart-safe retirement proposal and process-cut model — 2026-10-14

A reduced pending journal cannot recover resolved candidates after interruption;
completion also unlinks authority before purge, and the void purge helper does
not preserve removal outcomes. Closing only reduced publication is incomplete.
The reviewed proposal retains the complete bounded signed transaction row set in
one journal, recomputes resolution, retires only after publication/completion,
then checks journal removal LAST. Failed/held/corrupt/unreadable stage candidates
retain authority, not silent deletion or a broad storage scan. This can block
future in-game updates indefinitely; do not overwrite retained generations.

Cleanup-only retries of genuinely completed content must be nonfatal and not
spend/reset content attempts. Exhausted UNRESOLVED content still refuses BEFORE
mutation; moving the budget gate below installation is not a fix. An admitted
content pass that completes but leaves cleanup outstanding must publish the
bumped count. Legacy reduced/no-journal inputs cannot retroactively adopt orphans.

`tools/update_retirement_protocol.py` is an in-memory executable proposal, not
native code or a filesystem cleanup tool. Trusted signed tuples/protection
classifications and real byte digests support independent survivor/shared-hash
oracles. Tests enumerate168 process cuts (44 ordinary/shared +92 blocked/missing
+32 admitted-completion),
require acted valid removal and retained pending/corrupt controls, and reject
source-shaped legacy reduction/unlink actors. Full completion must reject every
unreadable signed destination, including preserved/outside-reduced-journal paths:
cached bytes are not proof of current readability. Compute expected shared pending
hashes independently from fixture bytes/policy, never by calling the implementation's
pending predicate; an always-empty mutation must still fail the oracle.
They do NOT verify signatures,
install content, prove disk durability, launcher behavior or native outcomes.
Source seams/availability decision/native falsifiers:
`tools/native_retirement_protocol.md`. The engine orphan follow-up remains open;
no patch/pin/version bump, release or deployment is authorized by model acceptance.

### Native full-superset retirement candidate and cold gates — 2026-10-14

The protocol now has an isolated **unpublished** qkupdate.c candidate, not just a
model. Three same-toolchain native client builds bind clean before caeb0b951,
first candidate87326b33 and read-corrected7321da29 source; exact bindings stay in
`C:/FTESurf-worktrees/wjnative-20261014T062856Z/artifacts/`. Each optimized build
has37 compiler-warning occurrences, zero new; no canonical install/Pi/release,
engine pin/tag, QC Build or product patch was changed by this tooling work.

The NEW cold gate `tools/test_update_native_retirement_windows.py` independently
checks20 scenarios/35 phases each for before and corrected subject: original
superset rows, shared pending hashes, same/wrong-size corrupt retention, actual
stage-delete and final-journal sharing denial32/release, completed-attempt3 versus
unresolved exhaustion, persisted admitted-completion count, outside/reduced/no-
journal boundaries and tuple/exec/duplicate/signature refusals. Fifteen unit
falsifiers reject byte/policy/budget/survivor mutations. Historical graders are
unchanged. Native exports require natural pre/post-cleanup job0 and separate
semantic receipts; signed-mirror census occurs only after accepted workers join.

`tools/test_update_native_retirement_interrupt.py` adds real FS_Remove pre/post
process interruption for both row orders, exact zero/one removed object, retained
survivor authority and repaired attempt3 completion. The external helper observes
real return1 plus OS absence before terminating only its owned child86; it restores
instructions/context, never supplies a file/API result. Sixteen units include
ledger/version/hash, consent, whole signed closure and exact stage-map negatives.
Review found the initial extension omitted intermediate ledger/closure checks;
fixed source gets a fresh before03/subject02 pair, earlier evidence stays historical.
`tools/native_retirement_{windows,interrupt}.md` describe scope and commands.

Readability requires more than VFS_READ==0: Windows maps ReadFile failure to zero.
Review found the first candidate could call unreadable protected bytes preserved;
the corrected FTESurf hash helper requires counted bytes == opened-file length
and successful VFS_CLOSE. This source correction/core rerun is NOT the requested
native partial-read falsifier. That worker failed provider-side after a defective-
client attempt; its FAIL/guard/runtime are retained, not passed, rerun or published.
Native partial-read, live/deferred publication-interruption, retained-generation
new-apply refusal and launcher supersession remain shipping blockers. Linux,
hardlink/hostile-path swaps and power-loss/flush durability remain excluded.

### Default HTTPS native/menu drivers and real return census — P689, 2026-10-13

`tools/test_update_default_https.py` uses the exact archived real bootstrap and
public signed feed without URL/pin/insecure overrides. The receipt contains six
critical hashes, not all 821 archive paths: bind the archive SHA/count/raw bytes,
bootstrap/notices and complete signed Windows closure. External P689 initiator
and archived returning P687 game are different provenance, not a P689 release.

Windows parse captured argv with CommandLineToArgvW; require the entire fixed
launcher/return vector, not substrings. Rust canonical executable argv has the
Win32 extended drive prefix: normalize paths only, never allow added flags.
Persist ALL captured exits/pre-cleanup census before grading, including initial
nonzero exits. Product processes must exit0 and job be empty before closure;
exact System32 conhost109 is separately retained as an OS broken-pipe teardown,
not a product exit0 or permission to ignore other nonzero exits.

Early independent `in` commands can show a title screen instead of Updates.
After menu initialization, run a sequential cfg with draw waits, then demand
screen7/client1 and individually named PNGs. Physical input can overwrite a
synthetic SUI hover between frames: batch hover/down/up callbacks in one console
command, without changing product input or blocking the owner's mouse. Offline
negative graders reject title0, extra argv, bad exits and incomplete failure
census. Attempts remain FAIL even when partial subjects acted; final full default
HTTPS matrices pass. Limits/failure history: `tools/p689native_https.md`.

### Linux default HTTPS/menu and complete task trees — 2026-10-13

`tools/test_update_default_https_posix.py` closes Linux consent/current/content/
engine-menu restart with the unchanged production archive/feed and real Rust/
returning game. External P692 initiator and returning P687 archive are different
provenance: acceptance is not a deployment, release or new product patch. Use
private PID/mount namespaces, tmpfs POSIX modes, private /tmp/Xvfb/HOME; no shared
WSL GUI sockets or original player install. Five final PNGs require pixel review.

Do not replace Windows jobs with process polling on Linux. strace follows fast
fork/exec/orphan actors. Parse successful clone/fork IDs (including resumed
records), require every referenced task trace/terminal outcome, exactly one
initial root, full reachability and actual launcher ancestry for the return.
An omitted thread-only trace otherwise false-passes even when executable count
and final namespace are correct. Save raw exits and namespace/group observations
BEFORE grading; every task/tracer exits0, no exception. Early failures need the
same pre-containment snapshot. Terminate only owned tracees while keeping strace
alive to record their terminal outcomes, then reap; an exited tracer/group leader
alone does not prove its group is empty. Controls ACT these failures without clients.

POSIX console logs echo typed commands before output. A marker substring can
complete a wait before its probe executes: require a standalone timestamped echo
line, not `echo HTTPS_MARKER...` in the input echo. Draw waits and screen7/client1
still apply to the actual returning game; no injected restart argv or adapter.
Bash-to-wsl.exe combined `> log 2>&1` capture overlaid unit-report prefixes in this
lane even with unbuffered Python. Separate stdout/stderr files retained every test
name and both acted FAIL JSONs. Preserve complete reports; do not infer a missing
control from a truncated/overlaid combined transcript.

Evidence allowlists need no-link checks on the scan root AND each ancestor/leaf
before rglob/read/copy, not only descendants returned by rglob. A static linked
export root otherwise copies its referent before retirement rejects it. Failed
exports/retirement must retain FAIL and an independently verified persistent
non-secret recovery bundle BEFORE tmpfs teardown. If recovery verification also
fails, retain the explicitly owned namespace for recovery, not a dead tmpfs path;
a marker alone cannot authorize discard. No identity.pfx/mounted-content export.
Fifteen client-free controls, reviewed fixes and full final-byte native matrix:
`tools/update_native_https_linux.md`. Recovery-blocked wrapper retention is
source-reviewed only; successful recovery/export/retirement failure controls ACT.

### Windows native bounded retirement completion — P703, 2026-10-14

The historical provider-failed partial-read lane above remains FAIL/read-only.
The operator explicitly authorized a fresh same-provider lane. New exact-source
>5MiB valid protected JSON/whitespace, shared-open + ReadFile33 and full838-file/
directory oracle discriminate blocked87326b from corrected7321da at attempts3;
release ACTS journal/three-name retirement preserving the edit. Eleven portable
mutations and a fresh independent raw-receipt review pass. Source and readlock
reviews find no issues; `tools/native_retirement_readlock.md` is the bounded gate.

P703 engine source/tag/pin and clean client binaries are now published/delivered
to both Windows installs; `tools/p703native_retirement.md` records exact hashes,
199 units, final build/PE-text binding, installed-path acceptance and limits.
A peer claimed P702 during completion: the rejected push changed no remote ref;
only our unpublished entry was renamed/rebased onto the peer's docs-only engine
commits. Fetch again before pushing; never force the race away.

Native build-directory fixtures have no adjacent plugin DLLs, canonical clients
have five. Existing PM_PreparePackageList/PM_EnumeratedPlugin inventory those into
synthetic installed.lst BEFORE recovery; a missing catalogue is therefore not a
valid no-mutation baseline for an installed-path gate. The first delivery fixture
FAIL/guard is retained. Fresh delivery-only fixtures independently author the
exact deterministic five-plugin catalogue BEFORE launch and require its exact
bytes in the unchanged full-namespace grader. No log/file exclusion, monkeypatch,
canonical installed.lst edit or failed-run relabelling. Bind installed binary
hash/PE text directly to the original clean build; output paths alone differ.

Windows allows renaming a running client to a unique predecessor while its mapped
image continues. Preserve that name and immutable backups plus .prev; never kill
the owner's game to deploy. Disk/new-launch acceptance is NOT an assertion that
the owner's current process has upgraded. This task changed only two client
executables, not plugins/server/progs/defaults/player data, Pi/Linux or release.

### Windows native unreadability actors and loopback ownership — P689 continuation, 2026-10-13

`tools/test_update_native_windows_unreadable.py` reuses an existing signed feed
and verified object closure without a key/pin override. Repeat --objects when a
retained synthetic feed added an object outside its production closure. Run a
real client in a suspended owned job, not a dedicated server; explicit headless
renderer and trusted -plugin stdin drive planning without claiming menu pixels.
Both zones and mounts need existing readable-edit and genuinely missing controls.
Consent is disk-seeded, not a writable cvar. Force checking avoids the version
fast path; a single ordinary content delta proves planner/apply action. Refusal
requires exact protected-path error, one feed request, zero object requests,
unchanged metadata/managed bytes and a refused apply; echoes alone never pass.

Windows share mode zero proves read error32; a leaf Everyone read-data DENY ACL
proves error5. Both must first prove existence, then restore access after native
exit. SetFileSecurity can clear SE_DACL_AUTO_INHERITED while preserving every
ACE: compare actual DACL bytes/defaulted/protection, not whole descriptor bytes.
The pre-fix engine replaces an ACL-denied file, discarding its deny ACE, so that
control must require signed replacement and restored read access, NOT continuing
read denial. Sharing locks also block replacement: old recovery changes ordinary
content then refuses with Unfinished content update, not successful startup.
Subject early refusal preserves either journal order and every staged object.
Export each failed phase before retirement; never count its partial PASS arms as
a completed acceptance run.

Python HTTPServer defaults can enable SO_REUSEADDR. On Windows that can duplicate
an occupied bind and interfere with a peer listener. Use SO_EXCLUSIVEADDRUSE,
disable reuse, and require an owned ephemeral busy-port rejection BEFORE clients.
The signed mirror port is not permission to steal a port or modify an envelope.
Final paired native matrices: 16 expected-before + 16 subject; both bound to the
same driver hash, no source patch/build/pin/deployment implied. Windows ancestor
denial, actual default HTTPS/menu/restart and the journal rename crash gap remain
separate gates; provenance and failure history: `tools/p689native_windows.md`.

### Unreadable native protected files and partial-recovery retirement — P689, 2026-10-13

`QKU_FSPreserveFile` must distinguish missing from failed hashing. A native
unprivileged client overwrote existing mode000 local zones/mounts with signed
bytes; an inaccessible zone ancestor caused late refusal after earlier content
installed. Only OS-confirmed absence permits failed-hash replacement. Shared
install/preserve/unreadable decisions now precede planner candidate compaction
and whole-journal mutation; readable edits and genuinely missing files retain
P687's policy. Classify before freeing/moving candidate paths, not midway through
compaction where an early error can double-free the original array.

Mixed-pending recovery may retire resolved objects only AFTER a successful
unresolved-only journal rewrite, and only if no outstanding destination needs the
same staged hash. Hash/size/no-link checks still govern removal: corrupt resolved
objects and unrelated staged sentinels survive. A failed journal write refuses
without retiring objects; the preexisting remove-then-rename crash gap is a
separate BACKLOG gate. Never claim this as atomic journal replacement.

`tools/test_update_native_recovery_posix.py` uses an actual retained signed
Linux object closure and external client, no signing key/pin override. Run its
driver AND client unprivileged on tmpfs/ext4, not DrvFS or root: prove mode000
open and ancestor-search refusal before testing. Private mount/network namespaces
avoid production HTTP and shared fixtures; +quit needs no graphics server.
Sixteen before/subject arms prove overwritten/late-refusal/leaked-object actors,
missing positives, shared hash retention, corrupt/unreferenced preservation,
honest partial state/version, repaired retries, failed journal-open and exhaustion.
Retain each partial/completed phase separately; reusing a phase directory erases
the strongest staging evidence. Retry increments BEFORE the limit check, so a
journal at attempts=3 refuses next launch rather than writing attempts=4.

Failure evidence must use copyfile, not copytree/copystat onto DrvFS under an
unprivileged uid: data copying can succeed while metadata setters raise EPERM.
Record failure and actual runtime retirement in nested finally blocks, including
when evidence export fails. The first expanded harness had both mistakes; those
failed attempts remain failures, not passes. Windows native regression eight
passes; clean control/subject Windows warnings match (259 occurrences); Linux
subject no compiler warnings. Standalone clangd needs the configured UCRT DLL
PATH, Windows TMP/TEMP and --tweaks=; completed zero-error check is separate from
stale cached diagnostics. Commands/hashes/review: `tools/p689native_recovery.md`.
Source acceptance is not a release or deployment; 0.1.25 remains P687.

### Complete updater source and staged-file controls — P687, 2026-10-13

The whole native/menu/wrapper/bootstrap/feed source is one product change, not
separate helper patches. Earlier paragraphs below record source-preparation
phases, not current deployment. Source commits and native pins do not mean a
production release, generated feed, updated bootstrap archive or installed game.
No QC Build/public version bump or fleet/canonical deployment belongs to P687's
source acceptance. Preserve P686's board sounds in the release allowlist.

Four acted blockers were fixed: `.part` links/linked ancestors followed before
or during object transport; native `state.json.enginetmp` links; replay overwrote
zones edited after journaling; executable downloads widened 0600/0640 to 0755.
Whole-batch FTESurf preflight and guarded no-follow regular-file opens precede
transport/mutation. Only prepare_install adds execute bits, preserving read/write.
Native replay shares the planner's protection decision for all rows before any
replacement. Protected-only recovery commits the verified version with zero
replacement records, never certifying the edited bytes. Ordinary Quakers policy
is unchanged. Final-component no-follow/immediate ancestor checks do not claim
hostile concurrent ancestor-swap or hardlink protection; see BACKLOG for remaining
native coverage and unreadable-protected-file behavior.

Measured controls: eight actual Windows native before arms reproduce overwrite
and linked-temp external writes; eight subject arms pass, with player settings
and recordings unchanged. tools/test_update_native_recovery.py accepts an existing
signed fixture/object closure and invokes an external owned client engine; it
needs no signing key. **Use a client, not -dedicated:** QKU_FSLock intentionally
skips dedicated installs. Own its Windows job before resuming the suspended PID;
read/dismiss only its fatal modal. Error windows can exist before static text:
wait for nonempty expected rejection text, not an empty dialog or timeout.

Locked-offline Rust passes 37 Windows/38 unique Linux tests, no warnings. Four
pre-fix regressions fail; fresh/partial/local-complete positives ACT with real
loopback counters. Linux umask077 is isolated in a repeated test-runner child
(not another unique test): 0600/0640 stage modes become 0700/0750 on install.
All agent tests use an explicit owned fixture root; ordinary cargo test supports
bounded RAII temps, never skips absent environment settings.

Build traps measured here: Makefile ARCHLIBS := overrides environment alone;
pass ARCHLIBS explicitly as a make assignment (or MAKEFLAGS assignment). Stock
plugins-rel may still fetch the ODE tarball even with cached libode.a; a dependency
cache reference is not offline/read-only proof. Full removes objects, not every
PCH: fresh task output avoids stale header/stamp mixtures. Windows-created .git
worktree pointers contain C:/ paths and fail Linux discovery; use the inspected
owned worktree gitdir explicitly, without changing shared Git config. Do not use
production Linux build.sh for isolation: it targets shared /build source/cache.
Private mount namespaces can bind source/root/cache read-only with task-only
outputs, but dirty stamps/clock-skew warnings are not clean release BUILDINFO.
Pin the startup Git executable before augmenting PATH: MSYS Git can miss Windows
core.autocrlf=true and report every unchanged CRLF source file as modified.
Instrumentation here saw the same 670 statuses before AND after compilation;
Windows Git was clean, and all native input/static archive bytes+mtime matched.
Do not reset/convert source to satisfy the wrong Git provider. Fresh clean P687
Windows client/server/HL2/imgui and native bootstrap builds now pass; the actual
client/server expose git-7281-patch-687-0-g3688683ff. Plugins are hash/compile-flag
bound, not required to export that string. Their source/archive hashes and the
real bootstrap --help/wrapper actors were verified, with no new compiler payloads.
Clean pinned Linux BUILDINFO/gates and release-preview/archive acceptance remain.

### First production-signed BOTH-platform release — 0.1.25, 2026-10-13

Published `0.1.25+b89.p687`; receipt build UTC 2026-10-13T08:45:33Z:
QC source `efe3b2ecac206a63c398f7cc71a00c3803da83c4`, native source
`3688683ff245431ac515a37bd63997c5fd7e56d8`, separate bootstrap source
`5c60f697c635a8b82affdcd46f51a50aedd3d280`. Build remains owner Build 89;
no new product patch, engine pin move, key rotation or P688 shipment. Linux
remains beta/unranked and the combined measured glibc floor is 2.30.

The real `release.ps1 -Bump patch -DryRun -BuildNumber 89 -Linux <clean drop>
-FirstUpdateFeed -LauncherRoot <clean bootstrap> -FteRoot <clean engine>` passed
without gate overrides, followed by the same production invocation with
`-VerifyFull` and without `-DryRun`. The existing private seed matches the
unchanged pinned public key; no secret bytes were logged. Both platforms are
present in the signed feed: 1,637 entries, 755 unique objects. All referenced
objects were uploaded and downloaded/hash-verified before the locked first-feed
check and atomic site swap. Both complete archives round-trip SHA256 matched;
public page/feed bytes and feed Cache-Control no-cache matched. Already-installed
nginx was byte-identical; no sudo, reload, lobby restart or player-install change.

- Windows: `https://dl.proto.bar/ftesurf/ftesurf-0.1.25.7z`, 42,381,944 bytes,
  SHA256 `8597d4b330662115dceab13ff042f72185cfb74784ac88384bc7b71825333d60`.
- Linux: `https://dl.proto.bar/ftesurf/ftesurf-0.1.25-linux-x86_64.tar.xz`,
  42,225,560 bytes, SHA256
  `039e9bce31b6563305e7ae7f8e8c9edd8b16faa69b57d9bd959d8c9e8baa6aef`.
- Feed: `https://proto.bar/ftesurf/update.json`, SHA256
  `1568a34c99ffca799db6ddb70dee9fde941d38038f7bdff32afbedd99386bb9f`.

Exact production archives/stages have 821 Windows and 818 Linux files, including
separate bootstrap/notices. Acted controls prove offline/opt-out argv forwarding,
protected settings/mounts/zones/recording sentinels, zero unwanted HTTP, normal
engine exits and no remaining owned descendants. The actual Windows archive also
installs one changed signed loopback content object, preserving its bootstrap.
The tested signed preview differs from final staging ONLY in VERSION.txt's
UTC metadata; complete file/byte comparison binds the other final contents.
Linux archive mode/owner checks and private tmpfs/Xvfb/loopback namespace avoid
repairing the extracted product or changing shared WSL sockets. Do not credit
these loopback controls as default-HTTPS native-menu handoff acceptance.

Retained evidence: `C:/FTESurf-worktrees/update-20261012T074529Z/artifacts/`
`coherent-publication-{dryrun-verdict-03,live-verdict-04,final-binding-04}.json`
and production logs, with exact-archive results under that root's rig. Initial
fixture-key rejection remains retained, not relabelled a pass. The deployed
publish.sh's pre-existing retention sort unexpectedly pruned unsigned 0.1.24's
page instead of the oldest page; immutable archives and signed-feed history
remain. A read-only GNU-sort falsifier reproduced it; the source fix and isolated
controls are recorded below. Do not blanket-clean those live pages.

### Release-page retention ordering — 2026-10-13

GNU sort's explicit per-key `n` prevents a global `-r` from reversing those keys.
`publish.sh` now uses `nr` on EACH major/minor/patch key. Current-page and signed-
feed-history exclusions are unchanged; signed history can exceed the five-page
limit. This tooling fix changes no product patch, engine pin, Build or version.

`python3 -B tools/test_release_retention.py --work-root <fresh owned root>
--control-publish <preserved old publish.sh>` runs the actual shell publisher with
public RFC8032 fixtures, no network/production key. Twelve retention cases check
exact survivor names/bytes, gate/swap/prune actors, each numeric component at the
cutoff, current/signed history and non-semver sentinels; ten existing shell
publication controls still pass. A seven-page old-source control removes 0.1.24;
fixed source removes 0.1.0/0.1.1. With SIX pages, old code prunes nothing because
only current 0.1.25 reaches the prune loop: the first harness expectation was
wrong and retained as a failure. Oldest-first/no-pruning and three lexical-key
mutants all fail the detector after publication acts. Synthetic runtime sites
are retired. DrvFS tests do not prove independent Unix permissions or live
HTTPS/storage. Source fix only: no live pruning, 0.1.24 page restoration, release,
helper deployment, player-install change or lobby restart was performed.
Evidence: `C:/FTESurf-worktrees/pageret-20261013T090939Z/` artifacts and rig.

### Signed updater release/publication contract — 2026-10-13

The wrapper lane is reviewed separately; `release.ps1` prepares signed feeds
from its archive-verified stages, not from an installed player tree. These are
the source/publication rules; the production acceptance above is separate
measured evidence, not implied by preparing a feed.

- Every release (including `-DryRun`) chooses `-FirstUpdateFeed` OR an explicit
  `-PreviousUpdateFeed <saved signed update.json>`. First feed needs `-Linux`
  and BOTH supported stages. Later Windows-only releases preserve Linux files
  and executable metadata; pass `-PreviousUpdateObjects <old output/objects>`
  for distinct retained Linux objects. That cache is read-only, byte/hash checked;
  missing/corrupt retained bytes refuse BEFORE a feed is written. Do not infer
  a prior feed from a URL or silently drop a platform. Explicit empty bytes are
  NOT absent input: verify every supplied predecessor, require an object payload,
  and validate even a signed empty object before preparing new feed bytes.
- Feed versions advance strictly. `-Force` is not an updater rollback or
  same-version replacement override. The site validates the exact prior feed's
  SHA256 under a publication lock; stale/racing prior input and first-feed-on-
  existing-feed refuse without moving static. Existing release directories are
  immutable too. A post-swap HTTP/route failure is a FAILED public-verification
  gate: repair/verify the route and exact feed, do not blindly re-run same-version
  publication or call the partially acted operation a success.
- Signing uses `-UpdateSeedFile`, `FTESURF_UPDATE_SEED_FILE`, or the private default
  seed PATH. Key bytes never appear in arguments, reports, archives or page files.
  `tools/updatefeed.py` CLI keeps the production public key pinned. Synthetic
  tests substitute only a helper copy's pin with the public RFC8032 test vector;
  those logs are not real signing-key/HTTPS/storage acceptance.
- After Windows and optional Linux stage/archive checks, a fresh
  `dist/update-<version>-<unique>/` gets the feed, the FULL referenced object
  closure, and `objects.txt`. Bootstrap remains excluded. The full closure is
  important: the pre-fix helper preserved Linux descriptors but omitted the
  Linux engine object, so a Windows-only upload was not enough. DryRun records
  only LOCAL verification; no remote receipt or site advertisement is produced.
  Fresh feed directories allow preview then actual release without reusing an
  output object set; retain previous feed/cache for the next release.
- `src/release/updatefeed.ps1` validates/regenerates inventory from signed bytes,
  uses rclone `--immutable --checksum`, downloads JUST all referenced objects
  into a fresh owned verification directory, and checks BLAKE2b-256 AND size for
  every platform. `-SkipUpload` skips PUT only, never the complete round-trip
  gate when publishing a page. Missing/corrupt/colliding objects refuse before
  `update.json` is copied into the candidate page. Failed downloads are retained
  for evidence; successful disposable downloads are removed after proof binding.
- Pi receives the public-key-only publisher/Ed25519 helpers and page candidate.
  `publish.sh` checks candidate signature/version, full-set verification receipt
  bound to exact feed SHA256, and live prior hash BEFORE permission/move/swap.
  Atomic `static` symlink replacement exposes page/feed together LAST. Ordinary
  page pruning preserves signed-feed release directories; object/history GC
  needs an explicit owner decision. The archive receipt includes feed/prior SHA256,
  but is NOT the remote-object verification receipt. Public HTTP verification
  requires byte-identical `update.json` and `Cache-Control: no-cache`.
- Gates: `test_updatefeed.py --work-root <fresh owned root>` checks retained
  bytes/rollback/descriptor policy; `test_update_publication.py --work-root
  <fresh owned root> --control-tool <preserved pre-wiring updatefeed.py>
  --prior-control-tool <preserved pre-prior-fix updatefeed.py>` executes
  production PowerShell AST seams against byte-copying R2 mocks and actual
  `publish.sh` in ephemeral WSL sites BELOW the owned fixture/evidence root,
  with OWNER written before runtime population. DrvFS is not independent Unix
  permission/mode proof. Positive arms assert exact object/feed/
  static actors; negative arms assert no advertisement/static change. AST seam
  tests do NOT run full clean BUILDINFO/archive/receipt production provenance,
  real R2/HTTPS/SSH, native updater restart, or fleet/storage cutover.

### Launcher resize / continuous-screen controls — P708 (2026-10-14)

- A default Windows Terminal host can ignore SetConsoleWindowInfo while returning
  success; SetConsoleScreenBufferSize then fails87 and the actual viewport stays
  120x30. Do not grade the requested size. Use a uniquely owned ConPTY with actual
  ResizePseudoConsole and independently read back its viewport/cells.
- A redirected harness can pass its valid standard API-pipe handles into a ConPTY
  child even without handle inheritance. Temporarily clear only the helper's std
  handles for CreateProcess, then restore all three in finally. Adding a separate
  CREATE_NEW_CONSOLE is NOT the same ConPTY and can create a visible fixture.
  CreateProcess failure must close the owned ConPTY/drain thread; no CLI fallback.
- Open CONOUT$ again after alternate-screen activation; a handle opened before
  the TUI can still name the old buffer. Raw mode alone does not mean a question
  is rendered: wait for exact prompt text before injecting Enter/arrow controls.
- Count concurrent requests frozen BEFORE bodies. A server callback can linger
  after delivering its final byte while the client legally begins its next job;
  callback overlap is not an extra download worker. Preserve failed counters.
- Whole-workflow styling: require one actual VT1049 enter/leave pair, continuous
  raw input, live black-cell/header resize checks and restored mode on exit.
  The current P704 launcher is already detached; use the retained pre-P704
  preview for a wait-defect control. ConPTY/actors are not physical-terminal or
  native GUI/game acceptance. Controls/failure history: tools/p708launcher.md.

### Automatic update finalization preparation — 2026-10-13 (not yet shipped)

- Preserve the full owned source before replay onto newer published bases. The
  finalization-source-01 manifest binds 36 source files, refs/index/status and
  mtimes; original task trees remain unchanged. Whole-file AGENT_NOTES hashes
  legitimately differ after upstream notes: compare the exact owned +/- delta,
  not a source overwrite. The isolated final-* worktrees integrate P683.
- Normal wrappers select the bootstrap; only an absent bootstrap selects the
  engine. An invoked-bootstrap failure NEVER retries the engine. Linux refuses
  linked/non-executable bootstrap paths, including dangling links (`-e` alone
  misses those). Preserve map/quoted-arg/cwd/stderr/status behavior with actors.
- First non-terminal launch with absent consent needs explicit bootstrap
  `--offline`, not auto-consent or an engine fallback. Leave permission unset;
  in-game opt-in enables later checks. Terminal first launch keeps the prompt.
  Windows probes Console.IsInputRedirected with built-in Windows PowerShell
  only while consent is absent; failed probe conservatively skips the check.
- Stored opt-out tests missed the fresh-desktop regression. Pre-fix real Rust
  refused absent consent with non-terminal stdin; a separate dangling-bootstrap
  control incorrectly ran the engine. Fixed controls add real fresh desktop and
  POSIX pty consent, a Windows fresh-console routing actor, and link refusals.
  Tiny engine actors prove wrapper/Rust spawn contracts, NOT native GUI,
  production HTTPS, release archives, process census or timeout cleanup.
- `--offline` skips only the bootstrap check. The native game's independent
  auto-check follows saved permission; direct startup is not whole-client
  offline. Generated INSTALL/page/launcher README must say so consistently.
- Whole feature remains uncommitted/unshipped here. At the wrapper-only
  checkpoint signed-feed publication was unwired; the subsequent source/mocked
  publication lane is documented above, not production acceptance. The prior
  reviewed Linux archive is a bounded dirty/test-stamped fixture, not production
  BUILDINFO or clean integrated native-build evidence.

### Automatic update controls — 2026-10-12 (not yet shipped)

- Updater permission is `.ftesurf-updater/consent`, not player-consent data or
  `installed.lst`. Drive the real Updates buttons through `ui_hover @mu_*` and
  `ui_mouse down/up`; `ui_mouse` can report `took 0` even when the button ACTED.
  Require the native state, permission bytes and HTTP/object counts as actors.
  Reopen `ui_updates` and wait for drawing before EVERY click: one control
  reached screen 0 after the wait, so its absent restart button never acted.
- Enable/disable/re-enable in one process exposed the native auto-check latch:
  re-enabling had remained idle without a second request. Opt-in resets that
  latch. Successful retries also clear the native console's old error string.
- Existing permission and install-lock guards did not cover `consent.tmp` or
  the launcher executable itself. Real owned file-symlink controls showed the
  old engine writing an outside permission target and spawning a linked exe;
  the fixed paths refuse before either operation, keeping the current game.
- Recovery uses the same signed policy and version floor as fresh updates.
  A stale native signed journal actually rolled the fixture and ledger back;
  both runtimes now refuse it. Rust recovery validates every pending path,
  needed staged object, link/metadata path and readable ledger BEFORE live
  replacement, and reuses planning to keep edited zones/custom mounts local.
  A later forged path had previously changed an earlier valid live file.
- Restart queues `quit` behind existing Cbuf text: a cfg-tail echo can print
  before normal exit. It is not proof that restart failed. Use process exit,
  exact fixed-local argv, a real Rust update actor and a fresh returning-engine
  actor. Test-only adapters may add loopback flags; do not call that a shipped
  bootstrap/default-public-feed test. A separate native-lock control proves
  real `--wait-for-game` makes no request/permission write while blocked.
- A missing bootstrap used to print only to the console, leaving the Updates
  pane's generic restart text unchanged. Restart failures now publish through
  read-only `update_error` while keeping the pending state/plan and retry button.
  Inspect the actual pane PNG: a stored error alone does not prove it rendered.
  Both content-restart and binary-handoff refusal controls draw download/place/
  retry guidance; adding the test-only bootstrap in the SAME game and clicking
  again clears the error and completes the real Rust/returning-engine chain.
- Bind owned Windows clients to kill-on-close Job Objects before they can
  create descendants. The adapter/launcher/returning-game chain must all exit
  normally on success; failure cleanup closes only those jobs, never kills by
  process name or an unverified descendant PID. The final control recorded
  fourteen jobs and zero active descendants, followed by zero task-root exes.


### POSIX bootstrap permissions — 2026-10-12 (not yet shipped)

- Byte hashes do not prove an executable can run. Real Linux controls reproduced
  archive adoption falsely printing ready for an engine at 0644; actual launch
  failed Permission denied. Cold recovery after rename also cleared pending
  before enabling execute. Verify the complete signed set, then repair modes
  before committing metadata/clearing pending, even when no object is missing.
- Permission repair retains read/write bits, adding execute for the owner and
  existing readers (0640 -> 0750, not unconditional 0755). Signed exec flags
  do not authorize chmod of protected edited zones/custom mounts. An unsigned
  explicit-offline archive is not a permission-repair authority. Dry-run must
  neither commit cold pending recovery nor chmod during signed-cache outage.
- `tools/test_update_posix.py` has an acted fresh-download/argv control and a
  `--expect-before` defect control. Subject: 17 acted arms, none skipped, including
  real fixture launch after zero-download adoption/recovery and cached transport
  outage, plus real unprivileged chmod failure retaining pending/no ready ledger.
  Corrupt/link refusals retain pending and earlier modes; protected modes stay.
  Initial pending rejection tests omitted loopback allowance and falsely passed
  at mirror-policy decoding. Corrected tests require the intended error; separate
  cache-outage corrupt/link controls actually reach preparation's contents guard.
  The initial unprivileged fixture also failed at reading 0600 content; all signed
  payloads must be readable to that child to prove chmod itself refused.
  `test_update_launcher.py` also runs on Linux with real flock/symlinks; both
  platforms' full shared suite and 24 Rust unit tests pass. The launcher builds
  without warnings on Windows MSVC and WSL Ubuntu with locked dependencies.
- Permission fixtures must be on a filesystem with real POSIX chmod semantics,
  not unconfigured WSL drvfs. Runtime-only TemporaryDirectory contexts on ext4
  retire fixtures after copying small evidence to the owned task root; cargo
  output remains beneath that root. No native Linux engine/fork/exec handoff,
  archived Linux release, glibc-floor or default-public-feed claim follows from
  these synthetic fixture actors. Larger updater remains uncommitted/unshipped.

### Bootstrap archive controls — 2026-10-12 (not yet shipped)

- Build the separately delivered Rust bootstrap from an explicit inspected
  `-LauncherRoot`, with locked dependencies and an explicit Windows/WSL host
  target. Record source fingerprint (including untracked source), commit,
  dirty status, compiler/target and binary hash; never select a stale executable
  from the player's install. Real missing-source and file-link controls refuse;
  same-commit source changes alter both fingerprint and dirty status.
- The ordinary signed feed deliberately omits `ftesurf-launcher(.exe)`.
  Archive upgrades of the bootstrap require exiting game AND launcher first;
  there is no bootstrap self-update. License/dependency notices are required
  archive entries too. Cargo metadata must be filtered by shipped target AND
  traversed from its resolve root: its package list still includes unreachable
  other-target crates. The first all-package notice attempt correctly failed
  on an unused UEFI crate with no bundled license text; do not silently skip
  missing notices for an actually selected dependency.
- The real CLI has `--offline`, `--enable-updates`, and `--wait-for-game`,
  NOT `--disable-updates` or `--wait`. It already waits for the engine's exit.
  An initial archive driver invented those flags and failed at clap before
  any engine actor; that was a harness failure, not a passing opt-out control.
  Persistent opt-out is in the menu. `--offline` skips the launcher check
  without changing stored permission; the native game's own auto-check still
  reads that permission, so isolate the actors/counts before claiming no network.
- Delivery fixture archive: inspect exact extracted hashes; physically remove
  bootstrap/notices in separate negative archives and run the same production
  required-entry helper. Launch the unmodified archived bootstrap, not an adapter,
  from another cwd with install/cfg/argv containing spaces. Require real engine
  actors, preserved argv/player sentinels and normal exits. Suspend the launcher,
  assign its kill-on-close job, THEN resume, so even fast children are contained.
  Four direct launch/update arms passed with zero remaining job descendants.
- The full `-Bump patch -DryRun` (network-mocked) is STILL BLOCKED by current
  shipguard's six existing QC asset-reference misses; see BACKLOG.md. The real
  bootstrap fixture archive and direct signed loopback update are NOT a passed
  production release, default-HTTPS native restart, Linux runtime, or publish.

### Native POSIX updater/restart controls (2026-10-12, not yet shipped)

- Run native Linux fixtures on ext4: DrvFS does not prove Unix execute-bit
  behavior. Use bounded runtime-only gamedirs, not source/install copies;
  capture allowlisted logs/PNGs to the owned task root and explicitly retire
  fixtures after all owned process groups and orphan descendants are reaped.
  Ubuntu/WSLg execution is NOT a bullseye/glibc-floor or Linux release proof.
- POSIX `Sys_Error` execs xmessage when stderr is not a tty. A harness-owned
  stderr PTY captures cold errors and permits exit without creating a modal.
  Require the expected fatal text, nonzero exit and no gamedir log/mount actor;
  never turn a timeout or missing display into a passing cold refusal.
- `QKU_Restart_f`'s exec-error pipe must retry EINTR and accept ONLY EOF as
  success. The prior `read(...) > 0` test incorrectly accepted negative reads.
  A harness-only LD_PRELOAD interposer fired on the real restart pipe: the
  pre-fix missing-interpreter click cleared its error instead of publishing
  failure. Fixed EINTR/EIO controls retain restart state/error and complete a
  same-game real Rust/returning-engine retry. A VALID-launcher EINTR control
  separately proves actual retry/EOF success, not simply rejecting all errors.
  Check FD_CLOEXEC preparation before fork and consume the child's write result.
- Native/Rust flock parity needs more than one early snapshot. Keep the native
  actor locked until an explicit harness release; repeatedly prove contention,
  no HTTP requests, unchanged updater metadata and unchanged managed target.
  The distinguishing loop observes two seconds, then requests native quit.
- Failed-click probes can repeat stale stored errors. Require a fresh native
  `update:` failure line within EACH bounded click segment, including missing
  and non-executable cases that deliberately share the same error text. Gate
  EACH click until Python installs and checks that exact fixture; bound the
  diagnostic between its current armed/observed actors, not a prior actor.
  A deliberately delayed driver (3 seconds, longer than the old fixed wait)
  proves the non-executable click cannot advance while the fixture is missing.
- Save the verdict AFTER process census, cleanup and retirement acceptance.
  A live helper must not leave a PASS JSON followed by an assertion failure.
  Continue cleanup across recorded owned groups, with bounded TERM/KILL and
  orphan reaping; two actual TERM-ignoring helpers distinguish this behavior.
  Keep FAIL evidence and the exact runtime path if safe retirement is blocked.
- Keep permission fixtures in `tools/test_update_posix.py` and the actual
  engine harness in `tools/test_update_native_posix.py`; they are distinct
  contracts. A file-name collision in this continuation was corrected by
  restoring the permission driver to its exact recorded SHA256 from the prior
  whole-file slice, moving native code under a distinct name, and rerunning
  all 17 permission controls plus the native lane.
- Source-reviewed limitations remain: EOF assumes exec closed the pipe; child
  death or failure to report exec error can also close it. Fcntl failure and
  child-write interruption/error were source-reviewed, not fault-injected.
  Stub Linux HL2 plugin/UI fixtures prove updater/menu behavior, not gameplay.

### Linux bootstrap/archive controls (2026-10-13, not yet shipped)

- Host compatibility is not the release floor. The prior bootstrap gate accepted
  GLIBC_2.34 on Ubuntu/glibc 2.35 although the engine baseline is 2.31. Combine
  engine/plugin and bootstrap requirements under a HARD 2.31 ceiling; measure
  the ELF symbols, not only the host's libc. `test_bootstrap_linux.ps1` executes
  the real release AST block, including engine-2.34/bootstrap-2.31 refusal and
  the default `libgcc_s.so.1` allowance (Rust's compiler runtime).
- `linux-bootstrap.sh` builds locked/offline with the host Rust compiler in
  the existing Bullseye chroot. Private mount namespace, read-only shared
  chroot/source/toolchain/registry, task-owned output/tmp/Cargo locks; no shared
  /build rewrite or dependency-cache copy. Refuse existing builder submounts.
  `--exec wslpath` preserves Windows backslashes; invoke login bash for rustup's
  PATH and pass source/output paths as positional args, not shell interpolation.
  Record the compiler actually used and execute the built bootstrap's --help on
  libc 2.31. An inherited active mount and a root-chroot selection both refused
  before Cargo in acted controls; namespace mounts vanished after exit.
- Real delivery fixture: 816 regular files, exact archived/extracted bytes,
  0755 directories/three executables and 0644 other entries, tar owner 0:0,
  bootstrap/notices required independently of stage equality. The actual
  production pack/verify and PowerShell policy refused physical missing-file,
  wrong-mode and changed-notice tar mutants. Bind policy logs to both current
  archive and verification-log SHA256: saved VERIFIED text alone previously
  passed even if the physical archive was removed/replaced. Both falsifiers
  now refuse BEFORE any policy PASS; parked original restored hash-identically.
- Supply the observed loopback URL to EVERY Rust arm, not only the enabled
  positive arm. Engine cfg update_manifest_url does not configure Rust. Prove
  enabled consent stays 1 across --offline; resetting it to 0 before the arm
  merely repeats stored opt-out. Disable the ENGINE's independent autocheck
  explicitly to measure Rust's one-launch override; this is not evidence that
  --offline suppresses native engine checks too. Missing --offline in the final
  enabled-consent control fired the real-bootstrap HTTP-count falsifier.
- Run unchanged extracted Rust/engine from unrelated cwd and installation/cfg/
  argument paths containing spaces. WSLg GUI actors exited normally, preserved
  bootstrap/engine and protected synthetic player sentinels, and applied exactly
  one signed content object. Separately the same archived Rust -> real dedicated
  engine ran under glibc 2.31 with private network namespace and unchanged
  executable hashes. This is not GUI-on-2.31, gameplay, full release.ps1/receipt,
  clean-source provenance, production HTTPS/publication or live deployment proof.
- Notice checks compare reachable package inventory for the locked Linux build
  and notice target (203 packages), not dependency edges/features or every license
  body's text. Notices used actual Windows MSVC plus Linux GNU targets; the
  unrelated Windows GNU target refused for a cached crate missing license text.
  Use stdin=DEVNULL for unattended launch errors; terminal stdin prompts for Enter.

### Updater startup and JSON string lengths (2026-10-12, isolated controls)

- `COM_InitFilesystem` can return before the startup `FS_ChangeGame` selects its
  manifest. `QKU_Init` may therefore register cvars BEFORE the recovery hook.
  Profile/consent configuration must work in either order. Within `FS_ChangeGame`,
  `fs_manifest` and `com_gamepath` are final before mounting, but
  `FS_GetGamedir(true)` is not: it is assigned by the later path mount. Checking
  that public gamedir at the recovery hook misclassified an FTESurf install and
  incorrectly inherited Quakers' enabled permission. Real opt-out and positive
  HTTP controls, not a zero-request observation alone, exposed this.
- Menu builtin `clientstate()` returns **1** when disconnected, **2** when
  connected, and **0** for a dedicated process; see `PF_clientstate`. Testing for
  0 prevents the normal disconnected menu from acting.
- `JSON_ReadBody` returns the RAW escaped body length, even when it writes a
  decoded string; it is an allocation upper bound, not decoded byte count.
  Comparing that return value to `strlen` rejected every normal signed envelope
  containing escaped quotes. Reject decoded NULs explicitly and verify the exact
  decoded bytes; do not change the shared JSON API to accommodate one reader.
- `CVARFD`'s `enginevalue` starts as a static literal. The existing
  `Cvar_SetEngineDefault` frees a non-null old enginevalue; do not call it on that
  literal. The attempted use failed before runtime logging. Profile defaults in
  the updater use static replacements, update defaultstr only if it still aliases
  the old enginevalue, and preserve a non-default user value.
- FTE's `in` timer stores its trailing `Cmd_Args` verbatim: use
  `in 3 exec cfg/test/steps.cfg`, not `in 3 "exec cfg/test/steps.cfg"`.
  The latter attempts a command whose name includes the quotes. Runtime fixtures
  also need a frozen OLD stage; copying the changing publisher stage into later
  subject installs can turn a download control into an already-current install.


### Zone-editor hover controls (Patch 676) — 2026-10-12

- Use the shared SUI tooltip path, not a second renderer/timer. Clear only `ze_`
  tips when this panel is off or its cursor is released; unconditional reset in
  the inactive panel would erase the HUD editor's later-frame hover timer.
- A delay control must first move the pointer away and let the old candidate
  clear. The real initial cursor had already hovered Box for 0.35 seconds before
  the synthetic first hover, so an early visible tip did not disprove the delay.
- `hud_edit ui hover` moves SUI's pointer but not zone_edit's cached pointer;
  use `zone_edit pointer` before a held-mouse acting control. Its routed result
  is logged as `sui_event`, not `sui_key`. Keep the required malformed settings
  overlay for the older P671 regression or its invalid-file arm cannot act.
- P676 fixtures retain pre-claim P675 echo/screenshot names after a concurrent
  native claim. New product sources preserve published P674 and P675 work;
  this help-only change does not build/deploy a different native engine.
- Product `90790c5`, clean committed build zero warnings and identical tested
  bytes. File-only dual Windows csprogs swap at 06:19:01 UTC; each P674 predecessor
  retained as `.prev`, identical qwprogs/menu hash-skipped. Protected native,
  owner/default/config files' hashes and mtimes unchanged. No owner game stopped.
  Fleet `build.ps1 -Pi` passed the fresh twelve-row zero-player gate, hash-checked
  and swapped the pair, then restarted all twelve by 06:20:42 UTC. Remote hashes
  match, health/heartbeats twelve with zero players at 06:28 UTC. New csprogs
  `7d3954d9eb25152d6`; unchanged qwprogs `7598b0da1cd90ebd`, menu `d111ec13ee2827f4`.
- Fresh live connections using both installed client/program pairs show Surface
  and Map properties help and close dismissal without runtime errors. Live probe
  must set `ui_tooltip_delay` after CSQC registers it, and explicitly synthesize
  focus with `in_focusgrab 0` to avoid the secondary window's real foreground
  correction. This is synthetic focus/hover acceptance, not OS device delivery.
  First failed probes and final acted controls are retained, not relabelled pass.
- Source proof, staging and raw control/runtime evidence deliberately retained at
  `C:/FTESurf-worktrees/zetips-01a12ea0/` for wording/acceptance comparison; OWNER.md
  and CHECKPOINT.md give ownership, exact commands and retirement criteria.
  No owned game/server process remains. This root has no native build outputs.

### Zone editor organization and presets (Patch 673) — 2026-10-12

- The old `surf` button was SURFACE tracing, not a gamemode. Renamed Surface;
  Surf/Bhop is a separate properties selector. It stages AA150/1000 and mode
  1/2, leaving selected speed/gravity; native hosted mode selection uses the
  WHOLE validated file before the existing mode pipeline. Three visible keys
  plus gamemode are complete new files; old complete six-key files remain
  readable. Removed ground fields are not removed from map-authored config.
- A mode toast/cvar write is not proof: acting reload controls must read
  `movement` source and pm_ticrate + sv_mintic + sv_maxtic + run_starthop.
  Measured Bhop .01/1000 and Surf .015/150, including Surf overriding forced
  Bhop, chosen cap6000 kept, and next unedited map restoring defaults. Dedicated
  tests use runlines_smoke's explicit `--server` to avoid the older installed
  native server masquerading as the subject.
- Reset removes destination name/coordinates. A NONE spawn falls back to the
  native bounds centre, which can be OUTSIDE a concave ring: keep an explicit
  safe interior floor point in that case. Tests prove setter acted first,
  ordinary save/reload preserves reset, concave point is not in the cut-out,
  and an empty selection does not invent a zone. CRC excludes destinations;
  inspect full td status and serialized teleDestPos, not CRC alone.
- Placement chrome uses `_sui_round_draw` in its existing raw draw coordinates,
  shared tooltip colors/rounding, three text lines and screen-bounded width.
  Do not open a second SUI input bracket. List/selection/construction/file
  groups retain the original probe IDs and title drag/window clamp contract.
- Harness false starts: a cfg launched before renderer/map/menu warm-up can
  lose map/UI commands. Use the existing 1500 ms startup + waitmap60 + spawn
  wait, menu_restart then ui_close; logging is log_dir/log_name, NOT log_file.
  Explicit quit/completion is required. Screenshots taken in the same command
  frame as a synthetic press can show the OLD button selection/value: wait
  after save before capturing. Native loader manifest `exit=0` is a provenance
  gate in the old reader, not an inferred cvar pass; preserve it at generation.
- Pre-claim candidate counts: new 27/27, P67129/29, P6698/8. Fifteen native
  loader arms freshly acted, including command-looking mode/canary, duplicates,
  fractional/partial mode and legacy controls. Final source incorporates the
  separately published P672 header seam and gets a full native rebuild; no
  fixture/consumer is activated in production. Final full tagged native
  `57bfa6bd3` controls also pass new27/27 + P67129/29 + P6698/8, with all 15
  loader arms freshly rerun and exact subject dedicated binary. Published
  P672 seam's ten production-slice unit groups pass. Native warning comparison
  must normalize line/column numbers: pr_csqc.c's existing array-address warning
  moved with P672, it was not newly introduced. Compiler warning set unchanged;
  only pre-existing Make peer-target diagnostics remain. Physical input is not
  proved. The 82 tracked per-map cfgs set none of sv_accelerate/maxspeed/friction;
  that census is not a claim about every community map.
- DEPLOYED P673 QC `3d17ade4` / native tag-source `57bfa6bd3`: all 12 idle Pi
  lobbies restarted 05:20:12..21 UTC with csprogs `825c2b46`, qwprogs `7598b0da`
  (qw bytes unchanged), old pair kept; Pi native unchanged. Windows gate held
  for the owner's game, then passed naturally: 19 native/progs/plugin destinations
  verified at 05:23:09 UTC (client `e9bbd6f3`, dedicated `c6e4cede`). Installed
  hosted checks new27/27 with fresh identical-byte loader controls, installed
  dedicated guards pass; fresh lobby client downloaded exact `825c2b46` and
  drew board cols8/type14. Owner/default config hashes/mtimes unchanged. No game
  was killed, no role/upload/time mutation, no Build or release increment.

### Zone editor extensions (Patch 671) — 2026-10-12

- A QC `cvar_set` plus a success toast DOES NOT implement map settings: the
  engine's movement lock restores its canonical value before movement. The
  rejected first experiment saved 6000 but surf_voyager still reported effective
  10000/150. The real loader is `SV_LoadEditorRuleset`, in sv_phys.c's existing
  pre-lock map-ruleset window. It reads only six numeric allowlisted values from
  `data/maps/settings/local/<map>.cfg`, validates the entire bounded file, and
  replaces existing canonical entries (the lookup uses the FIRST matching
  entry). It never runs a cfg, and dedicated/public lobbies never read it.
  Existing clear/load/lock machinery restores each next map's own defaults.
- `frename` does not replace an existing file on Windows. Settings read back
  the candidate, move the predecessor to `.prev`, then put the candidate in
  place; failed replacement attempts restore the predecessor. The control
  must save TWO distinct values and inspect `.prev`, not only create a file.
- `vote key <scan> <down> [char]` now accepts an optional character code. Scan
  127 with char 0 does NOT test text backspace; the sui editor takes char 8.
  All probes keep `cl_input_real` false. Synthetic pointer/release/button
  branches must not authorize writing on somebody else's server.
- Press ownership survives mode changes, editor close, map changes and bind
  changes. Owned key-ups are routed before other panels, even with the editor
  off; releases of game presses before opening pass through. Numeric text is
  re-zoned after sui edits so a later free never targets a temporary string.
- Polygon authoring reuses the existing Momentum XY ring + Z band. Simple
  concave outlines work, no holes/sloping caps. Crossed/touching nonadjacent
  edges and collapsed grids are refused before replacing a selected zone.
  A concave zone's default spawn must be INSIDE its ring, not its box/mean.
  Corner snapping takes priority over a nearer edge projection; Z proximity
  rejects snapping to a zone on a different floor. BSP edges are not exposed.
- The fixture protocol retains `P670` labels, but files/reader are `p671*`:
  another session published P670 during testing. Rebased on inspected QC
  feab052 and engine bd6cf6d91; no peer dirty files are included. Never reuse a
  guessed NoDeploy directory: parse/verify the actual compiler output and make
  staging failure fatal before launching a rig.
- Physical mouse/keyboard delivery is NOT verified by handler probes. Human
  acceptance stays in lextest.md; Steam identity/role and NanoPi publication
  policy stay in ROADMAP.md. No name-derived privilege or upload was added.
- DEPLOYED from published QC `2c540555` after the context handoff: all 12 Pi
  lobbies restarted at 2026-10-12 03:39:01..11 UTC, zero players, remote progs
  hashes verified (`7598b0da` qwprogs, `6080b34d` csprogs), old pair in `.prev`.
  Pi engine unchanged. Both Windows installs verified at 03:40:54 UTC with
  native source/tag `dbcaa17a7` / `patch-671`: client `8fe38e11`, dedicated
  `d29b8242`, all five plugins and all three progs; menu `a87b88ca`.
  Installed hosted/dedicated P671 controls: 29/29, including the nine retained
  loader arms on identical native bytes (not newly rerun); P669 hosted: 8/8.
  A fresh lobby-1 client downloaded `6080b34d` and drew an 8-column/type-14
  board. Owner/default config hashes and mtimes unchanged; no peer game killed.
- The inherited staging manifest still held pre-paste `8339e1e` outputs;
  rebuild the exact final source, do not merely relabel that manifest. The
  normal build and NoDeploy build of final QC produced identical progs here.
  `build.ps1:Deploy` updates only hl2/ui_imgui in the primary install even when
  cod/box3d/ode already exist. Finish those three from the same native build;
  hash-skip already correct destinations so retries preserve original `.prev`.
  The canonical build-script follow-up is in BACKLOG.md.

### The zone editor, part one (Patch 669) — 2026-10-12

- THE OWNER'S ASK: Momentum's zone editor in the game, for admins, because the
  CS:S maps need zones (about 870 KSF-only maps have none, and a few `_css`
  builds are offset from their Momentum twin). PART ONE is the editor and a
  saved file. PART TWO, an admin publishing to the lobbies, is NOT built: it
  waits on two decisions of his (who is an admin; maps that already have
  times).
- IT IS ONE CLIENT FILE, `src/client/cl_zoneedit.qc`, AND NO SERVER CHANGE.
  It edits this client's own zone table (sh_zones.qc's arrays, the ones
  cl_zones.qc draws) and `save` writes `maps/zones/local/<map>.json`. QC's
  fopen puts a write under `ftesurf/data/` and reads data/ first, so that is
  `ftesurf\data\maps\zones\local\`, and both VMs already read
  `maps/zones/local` before anything else: a hosted game times with it at the
  next map load with no code of its own. qwprogs is byte-identical.
- WHY THAT CANNOT REACH THE BOARD: a lobby's zones are its own files on the
  Pi, and a hosted game posts no times (sv_lobby.qc, "Ranked = official
  servers only"). On somebody else's server a saved file changes only what
  that player is SHOWN.
- THE TABLE IS KEPT IN THE FILE'S SHAPE AFTER EVERY CHANGE (`ZoneEdit_Touch`):
  a region's type is its POSITION in the file, so stages are renumbered 1..n,
  the end is one past the last, checkpoint ordinals run 1.. along the track,
  and the rows are sorted into file order, because `Zone_Hash` walks the table
  and an unsorted course would hash one way on screen and another once saved.
  A table that came from a file does not move.
- `Zone_Hash` DOES NOT COVER A ZONE'S DESTINATION, so "same crc" does not show
  a save kept `teleDestTargetname`: the arm compares `zone_edit status`'s
  zone lines, which print it.
- A NEW START OR STAGE GETS `teleDestPos`: the middle of its floor, facing the
  way you looked; `spawn here` sets it to where you stand. A KSF map has no
  `info_teleport_destination` to name.
- `&&` EVALUATES BOTH SIDES, AND `zone_type[-1]` ENDS THE SESSION. The first
  run died opening the panel ("Progs boundcheck failed", Host_EndGame) on
  `a && zone_type[ze_sel] == ...` with nothing selected. Nested ifs.
- WHO MAY WRITE A FILE (`ZoneEdit_MayWrite`). Every `zone_edit` word is a
  console command, and a server can type one for a player (Patch 617). So a
  file is written or removed only when this client IS the server
  (`serverkey("ip")` holds `QLoopBack`; unreadable is NOT ours, the reverse of
  cl_replay.qc's default) or a device has just let go of MOUSE1 over the
  panel (`cl_input_real`). On a dedicated server five ways of asking by
  command are each refused in words and nothing is written (`p669remote.cfg`).
  Zones made by command are still drawn until the map changes: a server can
  already draw what it likes on its own players' screens.
- SAVE WRITES BESIDE THE NAME, READS THAT BACK, AND ONLY THEN REPLACES: the
  same count and the same crc as the screen, or the old file stays. An
  unchanged table is not written (`save force` does), and `drop my file`
  (`zone_edit forget`) removes this machine's copy and reads the map's zones
  again: a save is a `zones/local` file and would otherwise win there for good.
- THE FLOOR GOES DOWN TO THE GRID, NEVER UP, and a new start's spawn stands on
  the floor as it was HIT. Rounded to nearest, a bottom could sit half a grid
  over the floor, and the server arms a start on a point test of the feet
  (`run_zone_hull 1`): a start nobody could arm.
- THE ONE REVIEW found those three and: every checkpoint after the first stage
  falling into stage 1 once a track had two (an in-place renumber reading its
  own marks; now worked out from the old numbers into `ze_tmp`); a height
  written to three decimals moving a top by 0.001; a re-place removing the
  wrong row after a reload; the wheel taken everywhere (`x = a && b` again:
  cl_entview.qc:1801 has the same line and is NOT fixed here); no yield to
  the leaderboard or the layout editor; a second sui bracket for the hint.
  The arm's course had one stage; it has two now, and the reviewed build
  fails five of its eight checks.
- THE PANEL holds the mouse through the cursor register (`UIC_ZONEEDIT` 256);
  PLACING gives it back and takes MOUSE1, MOUSE2 and the wheel only, each
  release going where its press went. The aim is traced and a click answered
  in the draw pass (`ZoneEdit_Draw3D`, after `Zone_Draw`), the frame it is
  drawn in.
- THE ARM (`cfg/test/p669zoneedit.cfg`, `tools/test_p669zoneedit.py`) has no
  mouse: `zone_edit click` / `back` are MOUSE1's and MOUSE2's code,
  `zone_edit press <id>` makes the panel's branch for one element run, and
  `zone_edit add ...` builds by command. Eight checks on a hosted game: the
  map's own zones saved and read back line for line; the panel's buttons; a
  zone placed with the aim; an empty table refused; a two-stage course in
  file order; a stage deleted; the hosted game's own server and client
  stating the saved crc after the map loads again; the way back. 8 of 8 on
  csprogs `cbc72b32`, on the patch-658 client and on the 625 exe; one more on
  a dedicated server (above).
- FOR PART TWO, what the other sessions said: zones are files by map name,
  `zones/local` on the Pi is the one place the watcher never writes and the
  server reads first, and the site's zones folder is what clients fetch
  ("Zone files: what ships, what is fetched" above). Who is an admin has to
  be surfd's decision about an account, never a lobby's or a client's word,
  and an upload must not go live by arriving; the accounts session's
  conditions are in this task's private notes, not here.
- DEPLOYED 11 Oct UTC (the 12th here) from `79425a5`: csprogs `cbc72b32`
  (119,995 definitions) to the Pi at 22:45:13Z, nobody on, twelve lobbies
  restarted and read back, and to both installs at 22:47:44Z with no game
  running; `.prev` is 659's `e04ccb61` in all three. qwprogs, menu.dat,
  default.cfg and the exes untouched. A client on the 625 exe joined a lobby,
  was served it and drew the board. The arm had run on that exe first.

### What is written on the run lines (Patch 661) — 2026-10-12

- THE OWNER'S FOUR ASKS, after trying twenty-odd lines: a name on every line
  in the line's colour, labels that do not "display too far away", energy in
  "the other E measurement the HUD speedo uses", and switches for what a
  label carries. "Too far away" was read two ways and both were done: far
  from their MARK (the lanes moved a label up to eight rows off) and far from
  the EYE (a number showed as far as its line, 12000 u).
- ONE QUEUE, PLACED AT THE END OF THE FRAME. `Line_Marks` queues the numbers
  while the lines draw, `LineGraph_WorldLabels` then queues the names (it runs
  BEFORE `Line_FrameEnd` now, cl_main.qc), and `Line_LabelsPlace` gives out the
  room: nearest the eye first (a name at half its distance, one already
  showing at 0.85 of its own so a pair does not trade places), a grid of cells
  stamped with the frame's number, and an alpha a label that eases 0.15 s in
  and 0.10 s out (`ln_lfa`, `ln_lff`, indexed by mark, then `LN_LB_NAME +
  slot` for a name). A label without room is still queued: that is what lets
  it fade back in. One under `LN_LB_FAINT` is drawn and takes no room.
- `hud_lines_declutter` 0 IS THE NEW PLACING; the lanes it used to mean are 2,
  the sparse grid still 1. The four older arms that meant the lanes say 2 now.
- THE QUEUE HOLDS 512 AND THE LAST 67 ARE THE NAMES': numbers are queued
  first, and a crowd of them must not leave a line without its name.
- THE LABEL TEXT ARRAY STAYS A REAL GLOBAL ARRAY (`ln_lab_t`): its strings
  are temp strings and allocated memory is not where the collector looks. The
  rest of the queue is allocated (the definition count).
- A NAME SITS AT THE NEAREST READABLE POINT OF ITS LINE, found among 256
  samples; past eight names they share 2048 and the two closer looks are 128
  tries each, so a whole 65536-sample line is searched coarsely then. Its
  colour is the line's own at that sample (`ln_col`), or its place by time.
  `lg_lab_*` and `lg_name_*` are `LN_SLOTS` now; the graph is still eleven.
- ENERGY ON A LABEL: `hud_lines_units` 1 energy (default), 0 the speed it is
  worth, -1 the split list's `hud_seq_units`, which a label followed before
  and which is u/s in the owner's layout. `hud_lines_ref` 0 is the default
  now: the speedometer's zero in every state it has (`HUD_EnergyRef`, a
  rewind's `ui_rw_ref`), and the run's own start where the speedometer has no
  answer. Same formula as `Strafe_Energy`, so a label reads what the
  speedometer would have read there. `hud_labels_rev` moves a saved 1 once.
- THE EDITOR'S "Line labels" PANE is the 24th row of 28 (`HE_MAX` and
  `HUDE_MAX` moved together). `hud_lines_nums` came from "Run lines" and
  `hud_linegraph_labels` from "Run graph"; `hud_lines_marked`, `_ref`,
  `_units`, `_label_far`, `_declutter` and the five element switches had no
  row before.
- THE ARM (`cfg/test/p661labels.cfg`, `tools/test_p661labels.py`) uses one
  run in every line, so it shows ONE name and ONE number where twenty want the
  place: that is the placing working, and it is also why no arm shows a real
  crowd. `lines native` prints "last labels N with room, M without";
  `linegraph status` lists every name, its colour and how far it has faded in.
- THE ONE REVIEW FOUND, AND THESE WERE FIXED: names had been given the
  numbers' range (a replay's own name vanished at 3000 u), a full queue
  dropped every name, the closer looks cost thousands of tries a line with
  whole lines ticked, the label's zero was not the speedometer's in a rewind
  or with no start zone, one far label put every near one in a single
  distance bucket, a nearly faded label kept an opaque one out, and the
  frame counter was a float that stops at 2^24. Of those only the names'
  range and the saved zero have a check in the arm.
- PAST EIGHT NAMES A LINE LOOKS FOR ITS PLACE ONE FRAME IN (names / 16) and
  keeps the point between looks, projected again. Without that, sixty-four
  names cost 0.8 ms a frame; with it 0.3.
- MEASURED (QC a frame, 1600x900, this PC, a paused replay, one run in every
  line, 2.13 ms with none): eight lines 2.96, sixteen 3.13, thirty-two 3.48,
  sixty-four 4.26 with their names (3.95 without; 4.02 before this patch,
  when only eight had one). Numbers on the first eight add 0.1 where they
  added 1.4, because they stop at 3000 u. Numbers on all sixty-four: 6.29.
- `lg_gen` IS THE GRAPH'S, AND fteqcc TAKES A SECOND DECLARATION OF A GLOBAL
  WITHOUT A WORD. The names' frame counter was first called that: it bumped
  the graph's "curves changed" count every frame, the graph simplified every
  curve again each frame, and eight lines cost 6.1 ms where they cost 2.9.
  Every arm passed. The cost table showed it and `profile_csqc` said where
  (LineGraph_Simplify and LineGraph_Swing, half the frame; the new code was
  1.6%). Grep a new global's name before declaring it; it is `lg_lab_frame`.
- THIS PC IS THE DESKTOP (i9-9900K, RTX 2080 SUPER). 645's and 649's notes
  said "this laptop" in two lextest items; the owner corrected it.
- DEPLOYED 11 Oct UTC from `497527d`: csprogs `6cb9b6c2` (118,136
  definitions) to the Pi at 17:15:58Z, nobody on, twelve lobbies restarted
  and read back; csprogs and `cfg/default.cfg` (+10 -5, the one before kept as
  `default.cfg.pre661-*`) to both installs at 17:18:20Z with no game running;
  `.prev` is 653's `84eaeec6` in all three. A fresh client on a lobby was
  served it and drew the board. It had been run on the 625 exe first, at
  twenty lines asked (eight given there), which is the check 649 skipped.
  The installed engine that day was the patch-658 client.

### An engine before 645 keeps eight run lines (Patch 654) — 2026-10-12

- `Scores_LineMax()` (`cl_scores.qc`) is `SB_LNMAX` where
  `checkbuiltin(lines_draw)`, and `SB_LNOLD` (8) where not. The three ways a
  line is ticked ask it: a row's box, the LINE heading, `scores lineat`. The
  refusal says a newer game draws sixty-four.
- WHY: without the builtins `Line_Emit`'s own loop draws, six vertices a
  segment (ten for a wide line) into ONE polygon batch, and an engine before
  Patch 645 dies when a batch reaches 32768 (`PF_R_PolygonEnd`, ENGINE_PATCHES
  645). Eight windowed lines are about 5,500. Patch 649 raised the limit for
  every engine and was live on the lobbies that way from 14:37Z on 11 Oct
  until this patch's deploy.
- MEASURED on a copy of the 625 exe (`183faf44`, what 0.1.24 ships), the 649
  arm's cfg: with 649's csprogs `95f30046` eight lines draw and the client
  dies as the fortieth is added; with 654's the fifty-six asks past the
  eighth are refused in words, eight lines are drawn (920 segments, as
  before) and the client reaches the end.
- THE ARM is 649's: `tools/test_p649lines.py` reads `native builtins 0` in
  the log and grades those three things instead (run it with `--client <an
  exe before 645>`). On the 645 engine the same build is 11 of 11.
- THE LESSON IS IN 649'S NOTES: a limit that is raised is re-run on every
  engine that is out, not on the newest.
- DEPLOYED 11 Oct UTC from `884d171`: csprogs `827dece4` (649, 648 and this;
  117,452 definitions) to the Pi at 15:13:07Z, nobody on, twelve lobbies
  restarted and read back, and to both installs at 15:13:51Z with no game
  running; `.prev` is 648's `88986a28` in all three. A fresh client on a lobby
  was served it and drew the board. So a 625-engine client on a lobby could
  be closed by a long list from 14:37:27Z to 15:13:07Z, 35 min 40 s; nobody
  was on a lobby at either deploy, and nothing here says whether anyone
  joined between.

### Sixty-four run lines (Patch 649) — 2026-10-12

- SLOTS 0..10 ARE WHERE THEY WERE (0 the replay, 1..8 board lines, 9 and 10 the
  live run), each with its 65536-sample store; slots 11..66 are fifty-six more
  board lines of 8192 samples. `LN_B(s)` is a slot's first sample in the shared
  arenas, `LN_C(s)` its capacity, `LN_TRAIL(s)` "9 or 10", `LN_BOARDSLOT(i)`
  the scoreboard's line i (0..63). `s * LN_CAP` is still right for a slot under
  11, which is why `cl_trail.qc`, `cl_rewind.qc` and `cl_linegraph.qc` did not
  change; generic code must use `LN_B`. The run graph and the name labels are
  `LG_SLOTS` 11: places 1..8 only.
- THE PER-SLOT TABLES ARE ALLOCATED (`Line_AllocSlots`, first thing in
  `Line_RegisterCvars`; `sb_ln_*` in `Scores_RegisterCvars`): seventy-five
  arrays of 67 would not fit fteqcc's global definitions. One pointer a
  declaration line (`float *a, *b;` makes b a pointer to a pointer).
- ONE memalloc IS 16 MiB AT MOST (`pr_bgcmd.c PF_memalloc`), and `ln_pos` and
  `ln_col` are 13.5 MiB each: that, not memory, is what stops at fifty-six
  more slots of 8192. The tables are 68.9 MiB in all (36.7 before), made at
  the first `Line_Begin` of a map.
- ONLY THE FIRST EIGHT DRAWN CARRY MARKS (`hud_lines_marked`, by place among
  the drawn lines, `ln_mkrank`, not by slot: untick the first eight of twenty
  and the next eight have them). With marks on all sixty-four they were half
  the cost, 2.2 of 4.2 ms.
- THREE THINGS THAT WERE PER LINE OR PER PAIR AND DID NOT SHOW AT EIGHT:
  `Line_Rank` paired every line with every other each frame (now on a change
  of who is ranked or on what time); every `Line_End` bumped one count, so the
  live run's build, four times a second, repainted every ticked line from its
  first sample (now a count a slot, `ln_sgen`); and the follow search looked
  at each whole line every 0.25 s (now every 0.25 s x lines/8, each slot at
  its own sixteenth of the interval whenever it last looked, and at once, four
  lines a frame, when the viewer is moved away from a cursor: `ln_fo_jump`).
  Up to eight lines the search is as it was.
- MEASURED on the 645 engine (QC time a frame, 1600x900, a paused replay,
  2.11 ms with no board line): eight lines 2.93, sixteen 3.03, thirty-two
  3.33, sixty-four 4.02; sixty-four whole lines 6.64; with marks on all
  sixty-four and the search unthinned it was 6.57 against 2.35.
- THE SERVER LIMITS RECORDINGS TO TWENTY A MINUTE AN ADDRESS (surfd
  `REPLAY_RATE_MAX`; nginx `surfdreplay` 20r/m burst 5, read off the Pi) and
  says 429. The line downloads spend tokens (`sb_ln_tok`: three, one more
  every four seconds) and a 429 puts the line back, four times. Sixty-four
  uncached online lines take about four minutes.
- THE ARM (`cfg/test/p649lines.cfg`, `tools/test_p649lines.py`): eight then
  sixty-four of one run (exactly eight times the segments, the same marks);
  the viewer moved 25 s along the run and all sixty-four cursors with it half
  a second on; the replay playing; a line alone in slot 5, 42 and 66 the same
  picture; a 65th refused; and on surf_dune a walk that builds the live line
  without repainting the eight. 11 of 11 on csprogs `95f30046`; with the
  one-count repaint put back the last check fails, 48 repaints in five builds
  of the live line against 0. `lines native` prints the repaint count and what
  the tables took to make (17 and 23 ms in those two runs).
- A PRIVATE CHECK, not in the arm (it needs a recording over two minutes): an
  18,252-sample run is 18,252 points in slot 5 and 4,563 in a new slot, with
  the same 823 marks; its 113 teleports draw as 90 there, two that fall
  inside one kept step becoming one.
- NOT A FAULT, AND IT COST AN HOUR: "the Linux client's VM is 32 MiB". Three
  readers took it from `initlib.c PR_Configure`; the caller hands it
  `PR_ReadBytesString`, which makes -1 into 2 GiB on 64-bit Linux too
  (`pr_bgcmd.c:132`). The 0.1.24 Linux client then drew a line in the rig.
  Read the caller before the callee's default.
- THE REPLAY BAR'S CLOSE BUTTON LIGHTS UNDER THE REAL MOUSE: a 20x20 box that
  differs between two shots of one view when the owner's mouse is over the
  rig's window (382 pixels). The arms' "holds still" control then says not
  measured, which is the right answer and not a failure.
- csprogs: 117,320 definitions.
- DEPLOYED 11 Oct UTC (the 12th here) from `512870b`: csprogs `95f30046` to
  both installs at 14:36Z with no game running (`.prev` is 645's `f40d4069`),
  and with qwprogs to the Pi at 14:37Z, nobody on, twelve lobbies restarted
  and read back; a fresh client on a lobby was served it and drew the board.
  No engine, menu.dat or cfg. The Pi's qwprogs became `35fda5eb`: the same
  source as the installs' `76e00522` built after midnight, one header byte
  (fteqcc's compile date, offset 115), which is also all that differs in
  menu.dat. A hash that matches nothing may be that; diff the bytes.
- SHIPPED WITH A FAULT, FOUND AT 14:49Z: an engine before patch-645 (the
  0.1.24 download) draws these by the QC loop, six to ten vertices a segment
  into one batch, and dies when a batch reaches 32768 (the fault 645 fixed).
  The arm on a copy of the 625 exe: eight lines draw, the client dies as the
  fortieth is added. Every check before the deploy ran on the 645 engine; the
  old one had been run with eight lines only. A limit that is raised is a
  limit to re-run on every engine that is out. Patch 654 keeps eight there.

### Run lines drawn by the engine (Patch 645) — 2026-10-11

- WHERE EIGHT LINES' TIME WENT (`set r_speeds 2`, `r_speeds_dump`, bucket
  `QC UpdateView`; `pr_enable_profiling` + `profile_csqc`): the per-segment QC,
  `Line_Feed` -> `Line_Q` -> `Line_Emit`, 250 instructions and 14 builtin
  calls, and the HUD graph's `Plot_Q` through the same emitter. The ImGui
  plugin is not in that path: only the OPEN graph panel goes through it, the
  HUD's small one is always QC (`LineGraph_Hud`).
- THE ENGINE HAS THE SAME CODE IN C (`engine/client/pr_csqc_lines.inc`):
  `lines_draw` is `Line_Draw`'s loop, `lines_segment`/`lines_width` are
  `Line_Emit`, `lines_strip2d` a plot's curve; `lines_arrays` and `lines_lod`
  register the sample and LOD arrays once (`Line_Alloc`). QC KEEPS ITS LOOP,
  for an engine without the builtins (`checkbuiltin(lines_draw)`) and as the
  reference: A CHANGE TO ONE IS A CHANGE TO THE OTHER, and `LP_*` in
  `cl_lines.qc` is the enum in the .inc. `hud_lines_native 0` draws the QC way.
  `lines native` prints builtins, in use, passes, refused, and the last
  drawer's points, segments, wild, clipped and screen box.
- MEASURED, one process and view (1600x900, the same run in eight slots, QC
  time a frame, no board line 2.49 ms): a window with marks and graph 5.84 ms
  the QC way, 3.41 the engine's; without the graph 4.61 and 2.92; whole lines
  with the graph 10.16 and 4.98; whole with labels (`hud_lines_nums 2`) 13.47
  and 8.78. What is left is QC that is not per segment: labels most of all.
- THE ARM (`cfg/test/p645lines.cfg`, `tools/test_p645lines.py`, run with
  `runlines_smoke.py --client <engine>`): each view the QC way, the engine's,
  the QC way again. 28 of 28; seven paused views exact in every pixel and
  count. It fails on an engine with one alpha term dropped (123 pixels in the
  window view).
- QC's `=` BINDS TIGHTER THAN `&&`. `ln_nat = ln_nath && cvar(...)` stored
  `ln_nath`: the switch was dead, both shots were the engine's, and the first
  run read 0 pixels different. Only the check that each mode says who drew
  caught it. Bracket the right-hand side; keep that check in any A/B arm.
- A REFUSED PASS LOOKS LIKE A PASS: `lines_draw` returning 0 makes QC draw the
  reference picture. It is counted (`refused`) and the arm wants 0.
- EIGHT COPIES OF ONE RUN HIDE EACH OTHER: board lines draw at 0.85 over the
  replay's own, so only the top ones are measured, and a wrong slot base that
  lands in another loaded slot reads the same data. The arm has the replay's
  line alone and one board slot alone for that (the review).
- surf_voyager under a paused replay is EXACTLY still (0 of 255 between
  frames). surf_dune is not, even with `vbsp_emit 0`: thousands of pixels move
  by 1 and a few by more, so the live view is compared on the line's own
  pixels. After `say !m`, 2.5 s of `+forward` walks off the start, the fall
  ends the run and the player is put back at the start looking along the line.
- THE 32768 CRASH IS UPSTREAM'S. `PF_R_PolygonEnd` flushes the batch itself
  at 32768 vertices or a flags change, `CSQC_PolyFlush` clears
  `csqc_poly_shader`, and the next `R_BeginPolygon` flushed the carried
  polygon with a NULL shader (`GLBE_DrawMesh_List` + 0x16). Eight whole lines
  at `hud_watch_path_px 3` reach it; the installed 625 client died there. A
  rig client that crashes appends to `C:\FTESurf\crashaddr.txt`, its working
  directory: resolve an rva with `nm -n` on `engine\release\fteqw64.exe.db`
  (the .exe is stripped, and statics are missing from the table).
- THE ENGINE BUILD THAT WORKED, in a worktree of the engine at its main: from
  pwsh with `C:\msys64\ucrt64\bin;C:\msys64\usr\bin` first on PATH and TMP/TEMP
  `C:\msys64\tmp`, `make -j6 -C <wt>\engine m-rel FTE_TARGET=win64
  ARCHLIBS=C:/msys64/home/Lex/fteqw/engine/libs-x86_64-w64-mingw32
  SVN_VERSION=git-<rev-list count + 29>-<describe --long> SVN_DATE=<%cs>`,
  then `sv-rel` the same. 93 s and 43 s clean. An .inc is not a dependency:
  touch the .c that includes it. For the final build delete
  `release\m_mgw64\*.o` and `sv_mingw64\*.o` first and read the stamp back out
  of the binary. No header moved, so the plugins were not rebuilt.
- csprogs: 129,741 definitions (118,347 once Patch 643 was under it).
- DEPLOYED 11 Oct: the client `03989f66` and server `25071c74`, both stamped
  `git-7216-patch-645-0-g65bf6f464`, into both installs at 12:57Z; csprogs
  `f40d4069` (with 643's) to both installs 12:58Z and the Pi 12:58:48Z, nobody
  on, twelve lobbies restarted and read back; a fresh client with the new
  engine was served it and drew the board. Engine main had moved under the
  stamped commit, so it went in by a merge (`aa153267a`), not a rebase. The
  0.1.24 release, cut in the same hour from `580a640`, carries the 625 engine:
  the release session and this one agreed "whichever is ready first", and the
  release was. The tree whose `engine\release` matches the installs is this
  task's `eng` worktree (the installed hl2 and ui_imgui plugins copied in).

### The board's lists take the mouse wheel (Patch 646) — 2026-10-11

- SUI RE-TESTS THE HOVER ONLY ON MOTION. A list scrolled under a resting
  cursor keeps the old hover, so a click went to the row that HAD been there.
  `_sui_mouse_move(_cursor_position, FALSE)` before the test re-reads it
  (`Scores_InputEvent`, at a notch and at a MOUSE1 press).
- A SECOND SUI BRACKET EMPTIES THE INPUT BUFFER. With a replay under the board
  the replay's `sui_end` runs first, so an event queued for sui never reaches
  the board's lists. The notch moves the list's offset itself. Read by the
  review, never run with a replay.
- BOTH NOTCHES ARE BOUND TO `+jump`: the wheel is taken only pinned and over
  a list. `tools/p646wheel.py` drives it with `hud_edit ui hover <id>` and
  `vote key 516|515`, and grades `took`, `scores status`'s `scroll N` and the
  dprint `scores: click row N`; four one-edit builds fail it.
- DEPLOYED 11 Oct from `088bb6a`: csprogs `e9371ed5` to both installs at
  11:40Z with no game running (under the rig lock, after a peer's run), and
  to the Pi at 11:41Z with nobody on. Twelve lobbies restarted; hashes read
  back from the host, twelve heartbeats after. No client was connected to a
  lobby to see it served. `.prev` is Patch 640's `b01acd53`; qwprogs and
  menu.dat did not change.

### Rounded corners from masks made at their own size (Patch 642) — 2026-10-11

- THE BLUR WAS ONE 8-TEXEL CORNER STRETCHED. `gfx/ui/roundmask.png` is 32x32
  with radius 8, and `_sui_round_draw` (`src/shared/sh_ui.qc`, both VMs) drew
  it at every radius. Along the corner's edge the mean difference from the
  exact shape was 0.025 at 6 px, 0.18 at 20, 0.34 at 96 and 0.37 at 176, with
  3.6 to 33 times the exact count of half-lit pixels. Now a disc of the wanted
  pixel radius is rasterised in QC and uploaded: 0.000 on the ladder's radii.
- THE LADDER: by 1 to 32 px, by 2 to 64, by 8 to 128, by 16 to 256, rounded
  UP. The radius itself is not rounded; a corner between two steps is the
  next mask shrunk by under a pixel (0.030 at 45 px, 0.040 at 100).
- AN UPLOADED PICTURE NEEDS ITS OWN SHADER. drawsubpic's default one wants a
  premultiplied picture and does not find an upload under that name (the
  missing-texture checker: ftesurf-5b's tip). `shaderforname` with a body that
  names the texture; `rgbgen vertex` and `alphagen vertex` in it.
- NEVER ASK ABOUT A MASK NAME THAT MAY NOT EXIST. A draw or a
  `drawgetimagesize` on a name with no shader defines it as a file picture,
  and `R_LoadShader` then returns that for good: the mask could never be made
  under it. The first cut polled a name to see whether a video restart had
  taken the masks and could poison names doing it (the review). Now each VM
  forgets its masks in the hook the engine calls before the next draw
  (`CSQC_RendererRestarted` in `cl_milk.qc`, `Menu_RendererRestarted` in
  `m_main.qc`; engine `renderer.c`, after a restart) and makes them under the
  next number. The VMs do not share names (`sui_rndc...`, `sui_rndm...`). A
  name that will not make is tried once more under the next number, then the
  .png draws for the rest of that VM's life.
- A ROUNDED BOX IS SNAPPED TO WHOLE PIXELS, a tie going the way the rasteriser
  takes it: `ceil(v * ratio - 0.5)`. `_sui_pixel_align` is `floor(v + 0.5)`,
  which at an edge of exactly k + 0.5 (anything centred over an odd width)
  lands one pixel past a `drawfill` of the same rectangle.
- THE MEASURE IS ALONG THE EDGE. The first grader took the mean over the whole
  corner square, which thins as the radius grows: the review's model showed a
  mask with no antialiasing passing from 32 px up. `tools/test_p642corners.py`
  takes the pixels within 1.5 px of the exact edge and the count of half-lit
  ones; modelled, every fault tried reads 0.05 or more where an honest corner
  reads 0.000 (`cfg/test/p642corners.cfg`, 9 radii drawn both ways and a video
  restart: 6 of 6, and the old way fails from 20 px up).
- TO LOOK: `hud_edit ui round <px>` keeps one white box on black, `round png`
  and `round mask` pick the way, `round 0` ends it; `hud_edit ui` prints
  `sui_masks made N off O last L gen G`, and the menu's own is
  `ui_strip_test masks`.
- csprogs: 130,609 of fteqcc's 131,072 global definitions. The per-radius
  tables are memalloc'd for that reason.
- DEPLOYED 11 Oct from `6713cd3`: csprogs `30f816bb` and menu.dat `6db94852`
  to both installs at 10:08Z with no game running (the copy took the rig lock
  and waited out a peer's run), csprogs to the Pi at 10:09Z with nobody on.
  Twelve lobbies restarted and read back; a fresh client on a lobby was
  served it and drew the board. `.prev` is Patch 641's pair.

### A config on the HUD's old defaults is moved, once (Patch 641) — 2026-10-11

- THE OLD DEFAULT IS PINNED THREE WAYS, not one. The engine saves every
  archived name only the game code registers (16 of Patch 637's 42); the
  editor's "reset" and "reset all" wrote the others with `seta`; and an older
  release's default.cfg sets them, or lacks them so that a save pins them
  (0.1.13 has no line for `hud_lines_nums` and the trainer's place, 0.1.7 for
  six more: the review's reading of those releases' files). The first cut moved
  the 16 and would have left such players a mix, so `HE_MigrateDefaults`
  (`cl_hudedit.qc`) covers all 42: once a config (`hud_layout_rev` 637,
  archived), a setting still EXACTLY its old default becomes the new one, a
  place only when both its axes are.
- IT CANNOT TELL "PUT BACK ON THE OLD DEFAULT" FROM "NEVER TOUCHED" and moves
  both. Once the mark is written, a value typed back is left alone.
- CALLED AFTER EVERY HUD REGISTRATION (`CSQC_Init`, after
  `MPad_RegisterCvars`): reading a name before its `registercvar` creates it
  empty and the default never lands.
- IT SAYS WHAT IT DID: one console line with the count, nothing on a fresh
  install. The arm grades that number as well as the values.
- csprogs WAS 12 DEFINITIONS FROM FTEQCC'S LIMIT (131,060 of 131,072 with the
  first cut; the count is the sixth int of the .dat's header). `ui_ehist_e` and
  `ui_ehist_t`, two 256-float rings in `cl_hud.qc`, are memalloc'd in
  `HUD_RegisterCvars` now: 130,556.
- THE ARM (`cfg/test/p641migrate.cfg`, graded by `tools/test_p641migrate.py`
  against `tools/p637_tables.py`): `seta` lines before the map stand for the
  old config, and `map` again restarts the game code, so one process holds
  three starts. 9 of 9; the build before fails 7 of them. It also reads the
  config the game then saves. A fresh overlay on this build says nothing and
  passes Patch 637's arm (11 of 11).
- DEPLOYED 2026-10-11 from `475d313`: csprogs `05b3a6ff` (qwprogs `76e00522`
  and menu.dat were already these bytes in all three places; no cfg). Both
  Windows installs 09:04:45Z with nothing running; the Pi 09:05:30Z with
  nobody on, all 12 lobby processes started 09:05:32Z to 09:05:40Z (read from
  the host), and `pi_lobby_smoke.py`'s fresh client was served this csprogs,
  drew the board and printed no move line. `.prev` is Patch 637's csprogs
  (`154fe49e`) in all three places.

### The HUD's defaults are the owner's layout (Patch 637) — 2026-10-11

- 42 SETTINGS MOVED, ALL THE EDITOR'S. From the owner's saved config, the names
  `hud_edit` owns and no other line of it (`cl_hudedit.qc`: `HE_Add`, `HE_Text`,
  `HE_OptDef`, the fixed five). A default lives in up to four places that must
  agree: the `registercvar`, the `set` in `cfg/default.cfg` and in
  `cfg/defaultuser.cfg` where there is one, and for a position the literal in
  `HE_Default`. `tools/test_p637defaults.py` reads them from the tree.
- A NAME ONLY THE GAME CODE REGISTERS IS SAVED BY EVERY CONFIG, AT ITS DEFAULT
  TOO. The engine writes each archived name on save (the review's count in a
  fresh rig's own saved file: 39 of 40 such names it never touched are there,
  and 0 of the 3 `default.cfg` names looked for). So 16 of the 42 (the positions `default.cfg` does
  not list, `hud_lines_order`, `hud_linegraph_plots`) reach a new install only:
  an install that has saved once keeps the old value, and reads it as the
  default. The other 26 move with `default.cfg`. Patch 641 moves a config
  that is still on the old ones (the section above).
- THREE SIZES MOVED IN THE DRAWER, NOT IN THE CVAR, which is `cl_timer.qc`'s
  build 66 argument: the speed's own size is 32 units (was 24), its energy's 24
  (16), the trainer's 10 (8), so they are his 64, 48 and 20 px at hud_scale 2,
  still follow hud_scale, and reach a config that saved 0. The first cut made
  the cvars 64, 48 and 20 and the review turned that down. `HE_Text`'s base and
  the trainer's stand-in box in `HE_Add` moved with them. With timer, segments,
  banner and run graph that is seven sizes he holds as pixels and the game
  leaves automatic.
- "RESET ALL" WRITES TWO MORE LITERALS (`hud_lines_order 4`,
  `hud_linegraph_plots 3`), as Patch 632 did for its colour rows: for a name a
  saved config created, `cvar_defstring` is the saved value.
- BOARD AND BOARDING ARE PLACED, NOT STACKED. Their default was the -1/-1
  sentinel (under the strafe bar, under Board); it is a coordinate now and the
  editor's "reset" writes that. -1/-1 still attaches them, from the console.
  Board's top edge is the screen's centre: its first row, the segment line,
  ships off, and switched on it is drawn through the crosshair.
- OFF THAT WERE ON: Boarding, run-line labels (`hud_lines_nums 0`; Patch 451
  had turned them on at his asking), the Segments column's absolute, percent
  and unit columns, three Board rows, three strafe-bar rows. His layout, as
  asked; lextest lists them for him.
- AN ARM WRITTEN BEFORE THIS THAT READS A HUD DEFAULT WITHOUT SETTING IT reads
  another value now. `runlines_peaks.cfg` graded "labels are 2 with nothing
  set" and sets it itself now; this list's three arms set what they read; the
  1,121 cfgs under `cfg/test` were not swept. Set what you depend on.
- THE ARM (`cfg/test/p637defaults.cfg`, a fresh overlay): it boots on the 42
  values and on the other 99 unchanged; setting his whole saved layout by hand
  (80 names) moves none of the editor's 20 rectangles; the 42 put back on
  their old defaults move them; "reset all" brings all 141 and the rectangles
  back. 11 of 11; the build before fails the four that rest on the defaults.
  It cannot see a saved config, nor a panel's real size where the editor
  draws a stand-in box (every panel that is not up at spawn). Two boxes are
  left out of its on-screen check and named: results (listed from its corner,
  drawn from its centre) and the trainer, whose box at his place runs 7 px
  past a 900-line screen where the drawer lifts the panel.
- A FRESH GAME'S SCREENSHOT IS NOT THE SAME TWICE: the sky moves, so 626,860
  of 1,440,000 pixels differed between two builds whose HUD was identical.
  The speed and its energy were compared below the sky (rows 552 to 900: no
  pixel differs between the first cut's absolute 64 and 48 and the drawer's
  32 and 24 units at hud_scale 2).
- DEPLOYED 2026-10-11 from `423c081`: csprogs `154fe49e` and
  `cfg/default.cfg` `c09e0b3e` (qwprogs `76e00522` and menu.dat were already
  these bytes in all three places). Both Windows installs 05:44:43Z with
  nothing running (the default.cfg before kept as
  `default.cfg.pre637-20261011T054443Z`); the Pi 05:45:58Z with nobody on, all
  12 lobby processes started 05:46:00Z to 05:46:09Z (read from the host), and
  `pi_lobby_smoke.py` was served this csprogs and drew the board. `.prev` is
  Patch 635's csprogs (`b2b6de57`) in all three places. The owner's saved
  config was rewritten at 05:11Z, after the patch was made from it: none of
  the editor's 141 settings in it had changed.
- `hud_edit off` SAVES THE LAYOUT: in a rig, to the overlay's own ftesurf.cfg.
  The owner's file was read through a script that takes the editor's names
  only, and its modification time was the same after the runs.

### The TAB board: every game by default, a filter switch and slider, the LINE heading (Patch 635) — 2026-10-11

- THE ONLINE LIST IS EVERY GAME'S UNLESS FILTERED (the owner, 11 Oct: "show all
  combined, and then the filter on the right, to be like a slider, with a
  filter toggle switch"). `cl_scores.qc:Scores_ImpState` is the one mapping and
  `Scores_TierOf` the wire word: 1 the merged list (`combined`, surfd's own
  merge, each row's tier in `tr`), the default; 0, 2 and 3 one game (`ranked`,
  `momentum`, `ksf`: no `tr`, so `Online_RowSrc` falls back to the board's
  tier); 4 both imports without ours (`imported`). Segmented is always ours: an
  imported run is clean. The Imported tab is gone.
- SAVED AS `sb_filter` (the switch) AND `sb_filter_src` (the stop: 0 FTESurf, 1
  Momentum, 2 KSF), archived, written with `cvar_set` in the frame of the
  click. Off, the slider waits dim on its stop; a press on a stop turns the
  filter on there. Console: `scores source all|ftesurf|momentum|ksf`. State 4
  is `scores tab imported`, a session global on no control (`rec_sb_imponly`)
  that every tab change clears (`Scores_TabSet`); p474page, p545mom and
  p603http type it.
- AN ARM THAT OPENS THE BOARD NOW GETS THE MERGED LIST. Twenty older cfgs and
  tools were given `set sb_filter 1` / `set sb_filter_src 0` (ours alone, the
  board they were written against): read, not rerun. A new arm that wants the
  ranked board pins the same two.
- THE ROOM LIST ASKS FOR ITS OWN BOARD (`cl_players.qc:Players_Ask`,
  `Players_BoardReply`). It read the Online tab's store when that held (main,
  ranked, clean), which is now the exception; it still does when it can. One
  request a map and board generation, `OB_RETRY_SECS` after a failure.
- "MY ROW" IS OUR ROW. One account can hold a ranked time and an imported one:
  `Online_FindMine` prefers the ranked row, and the finish seek goes only to
  it. When a merged list does not hold it (past the page of 100) the row
  pinned under the list says `<name>   FTESurf #<rank>` and draws no rank
  cell: the `#` column there counts every game. Measured through a
  server-side seam in a scratch tree (a listen server's client has no
  account): the first cut took row 1 of 71, the same account's KSF time, this
  takes row 65.
- A HELD BOARD TAKES NO CLICK. `Scores_InputEvent` still swallows mouse1 but
  hands it to the controls only while pinned: held, it re-fired whichever
  control the cursor last rested on.
- THE LINE HEADING (`sb_lnall`, `scores lineall`, `Scores_LineAll`): with any
  row of the list on screen ticked it unticks those; with none it ticks from
  the top the rows with a recording here or on surfd, until the eight slots
  are full. One sentence says what it did, on the console and in the footer
  for four seconds (`Scores_Note`). A Momentum row that still says "Get demo"
  is left to its own box: eight of those from one click is eight jobs on a
  queue that fetches six demos a run.
- NAMES AND THE FOOTER ARE CUT TO THEIR ROOM (`Chat_Fit`): a tagged name ran
  into the time and changed how it read, and the count ran under the key
  hints. The slider's stops are spaced from `stringwidth` of the labels, which
  stop at 12 px while `rec_sb_cw` shrinks with the rows; on the 8 px board the
  slider takes its own height (`Scores_FilterDraw`), or the knob sits on the
  word. That one was found in a frame at 1024x576, hud_scale 1, not by a check.
- THE ARM RUNS THE REAL surfd. `tools/p635board.py --output-dir <owned dir>`
  starts this checkout's surfd in a thread (port 27634, a scratch database:
  main two ranked, three Momentum, four KSF, so a total read from the wrong
  count is a different number; bonus 1 ranked only; bonus 2 130 rows), puts
  ten Local recordings in the overlay and grades 52 checks from `scores
  status`, which prints the footer's sentence and the first rows' names AS
  DRAWN. A build with seven faults planted fails the ten checks for them and
  no other. `runlines_smoke.py --put` takes plain paths under `data/` only: the
  first cut's could reach the install through the overlay's junctions.
- A CHECK THAT LOOKS FOR A REQUEST AMONG "THE FIRST THREE" COUNTS THE NEXT
  STEP'S. The room list's request was graded that way and passed the build
  that never made it: the FTESurf stop's click asks for the same board. It is
  graded by the room list's own count (`room list: N best time(s)`).
- IN A CFG, THE MARKER GOES BEFORE THE CLICK, and before any `scores <word>`
  whose shared tail prints the status: a click prints on the next frame, and a
  grader that takes "the last board print of the section" took a later
  command's three times here (`scores open` after the held board was the
  third).
- DEPLOYED 2026-10-11 from `8286948`: csprogs `b2b6de57` (qwprogs `e9c95065`
  and menu.dat were already these bytes in all three places; no cfg change).
  Both Windows installs 04:41:35Z with nothing running; the Pi 04:42:53Z with
  nobody on, all 12 lobby processes started 04:42:55Z to 04:43:04Z (read from
  the host), and `pi_lobby_smoke.py` was served this csprogs and drew the
  board (its Local tab: the smoke does not open Online). The live surfd
  answered `tier=combined` for three maps in 25 to 63 ms, one request each
  over the LAN, where `imported` took 37 to 57. `.prev` is Patch 632's
  csprogs (`6dc6e7b3`) in all three places.

### Run lines: a colour for your line, one for the others, a fourth Labels state (Patch 632) — 2026-10-11

- TWO GROUPS, ONE SETTING EACH. `hud_lines_color_own` colours the live trail's
  two slots, `hud_lines_color_others` slot 0 (the open demo) and the board's
  1..8. 0..4 are the five readings `hud_watch_path_color` had; 5
  (`LN_CM_PLAIN`, both defaults) is the group's plain colour: `LN_OWNCOL` blue,
  or the line's place by time. `cl_lines.qc:Line_Mode` maps a slot to its group.
- BY TIME IS OVER THE LINES SHOWN, LEG BY LEG (`Line_Rank`, every frame, nine
  slots). A slot's time is its window's end less the clock the window counts
  from (`ln_start`), so a stage line ranks by the stage's time, and only
  against lines of its own track and leg: a ticked line outlives the leg the
  board showed, and a stage beside a whole run placed first whatever the runs
  were. Equal times share a place (a run both watched and ticked is one run in
  two slots, and came out red over green). Not ranked: a hidden group
  (`hud_lines_board 0`, `hud_watch_path 0` or path mode 0, where no drawer
  draws the demo) and a line with nothing in its window. One line alone is green.
- `hud_watch_path_color` IS NO LONGER REGISTERED OR READ. The editor writes
  `seta` on every click and a saved value pins a setting against a new default,
  so the new look went under new names. A config that had chosen gain, contact,
  energy or air control (1..4) keeps it for both groups, once: the old name is
  then set to 0, or the next start would undo a later choice of plain. Nine
  test cfgs and `tools/visual_fades_smoke.py` set both new names where they
  set the old one. The five readings are what they were: 574 points of
  `p492voy.rec` in each, the old name on the build before against the new
  names on this one, 0 differ.
- YOUR OWN LINE HAD NO SPEED RANGE, before this patch too. Only `Line_Range`
  set `ln_lo/ln_hi` and nothing calls it for the trail, so "speed" over your
  line alone was one flat red (58 of 58 points, the review; the old default
  did the same). `Line_End` now takes the trail's range (`Line_SpeedRange`),
  and the shared ramp is over the lines that are in the speed colouring, not
  every line that is on. A new attempt is not on until its first `Line_End`
  (16 samples).
- AN IMPORTED LINE'S BLUE TINT (`hud_watch_path_foreign`) is over a reading
  only: a plain colour pulled toward blue would say neither. `replay colours`
  prints `lncr <ramp lo> <hi> <slot lo> <hi> <on>` and ends `lnce <mode>
  <ranked> <place> <tint> <of> <age>`: the tint is what the slot was last DRAWN
  with (`ln_tintd`; `ln_col` is before the blend), `of` the lines of its leg,
  `age` the seconds since a drawer reached it, -1 never.
- `hud_lines_nums 3` is the tops and bottoms alone: a contact keeps its chevron
  and gives up its number, unless it IS one. Patch 627 folds a turn within a
  sample of a contact mark into that mark (1 of 11 bottoms of `p492voy.rec`, 2
  of 5 of `runlines_peaks.rec`); `ln_efd` flags the mark, `Line_LabelOn` is the
  one gate, and `replay marks` prints it per mark (`lng`) with the flagged ones
  (`lnf`). The chip's order is off, contacts, peaks, both (0 1 3 2).
- A NAME BESIDE A LINE wears the line's plain colour (`cl_linegraph.qc`); the
  graph's own curves and legend keep the graph's palette (lextest).
- THE NEARBY-PLAYER ROWS left the pane (`cl_playerfade`, `_near`, `_far`:
  console only, and `lines` says so with `seta`). `HE_ResetAll` resets them and
  the two colour rows with LITERALS: on an install whose default.cfg predates a
  setting, the saved `seta` line creates it first, its "default" is then the
  saved value (`registercvar` leaves an existing name alone), and
  `HE_ResetCvar` writes back what it found (the review, on release 0.1.23's
  default.cfg). Every row that only `registercvar` creates has this; BACKLOG.
- fteqcc DIES WITH NO OUTPUT (exit 0xC0000005) ON A NAME DECLARED TWICE. Here
  `vector ln_pc[LN_SLOTS]` beside an older `vector ln_pp, ln_pc;`; in Patch 631
  a function in `cl_board.qc` naming a global that `cl_hud.qc`, a later file,
  declares. `build.ps1` shows nothing: run `fteqcc64.exe -srcfile cl_progs.src`
  in `src/` with its output to a file, and add the new declarations back one
  at a time.
- THE ARM. `tools/runlines_smoke.py ftesurf/cfg/test/p632lines.cfg --mount
  --output-dir <owned dir>`, then `tools/test_p632lines.py <log>`: 38 checks
  (a saved colouring carried over, reset all, the pane's rows and clicks, your
  line under three colourings, lines by time on one leg, on two, tied, watched
  and ticked, hidden; the import's tint; labels). A place's colour is worked
  out in the grader from the place. A build with the review's six fixes taken
  out fails the 8 checks for them and cannot be measured on 1. The first cut's
  "a reading when asked" passed on one flat colour: it sampled the line along
  the start platform, where every sample is 260 u/s, so it could not tell a
  line with no range from a constant speed. It samples after the ramp now.
- DEPLOYED 2026-10-11 from `6f936bc`: csprogs `6dc6e7b3` and
  `cfg/default.cfg` `b9480a1e` (qwprogs `e9c95065` and menu.dat were already
  these bytes in all three places). Both Windows installs 03:51:37Z with
  nothing running (the default.cfg before kept as
  `default.cfg.pre632-20261011T035137Z`); the Pi 03:52:17Z with nobody on, all
  12 lobby processes started 03:52:19Z to 03:52:28Z (read from the host), and
  `pi_lobby_smoke.py` was served this csprogs and drew the board. `.prev` is
  Patch 631's csprogs (`1a27aa8f`) in all three places.

### Run/demo label ink and autohop marks (Patch 677) — 2026-10-12

- `Line_LabelText` uses inline yellow (`^xFF3`) speed and green (`^x4F6`)
  energy fields; queue the numeric label on white and measure `stringwidth`
  with colour parsing ON. Keep `Line_Label` and `lndm` plain for existing
  readers. One queued string retains one HUD_Text/shadow pass, not one per
  field. Energy stays green when its units are speed-equivalent.
- Peaks remain height turns, not a new energy/speed detector. Standalone tops
  are closed pink up-triangles and bottoms closed purple down-triangles;
  existing nums switches and contact-folding still govern visibility.
- `Line_LandIsHop` suppresses INK ONLY: ground landing, immediate next event a
  jump from ground, sample-index gap <=1, jump ink on. No table deletion: mark
  and numeric dumps, energy deltas, Segments and recorded data keep both events.
  Several samples on ground, ramp contact, walking off, and jump-off settings
  retain the contact symbol.
- Acting pair: `tools/test_p677labels.py --write <owned fixtures>` generates
  native/imported authored hop files; run `p677labels.cfg` via
  `tools/runlines_smoke.py` with `--csqc`, `--ssqc`, `--output-dir` (must exist)
  and `--also p677hop.rec=... --also p677hop_mom.rec=...`. Grade with `--log`
  and `--control-log`: 7/7 including board ink, table preservation, switches,
  colour pixels and triangle direction. The three change checks fail on control.
- First harness cut set measured QC cvars BEFORE map spawn: shipped config/init
  replaced them, `lng` was zero, and an open replay alone did NOT prove label
  ink acted. Set controls AFTER map/menu init. Log rows have timestamp prefixes;
  normalize them before anchoring regexes. Map stars were yellow and defeated a
  whole-screen colour count: sample the clear label above the first ramp-leave
  projection instead, and require speed-only/energy-only negative colour arms.
- `build.ps1 -NoDeploy` currently prints its actual `rig/build-nodeploy-*`
  output directory: read that path; do not take unchanged install progs as the
  build output. Source/build ownership and runtime evidence are separate.
- WINDOWS DEPLOYED 2026-10-12 06:45:15Z from clean committed `b5a704f`, subject
  bytes identical: both csprogs `d6b4d81e8c64261d`, P676 predecessors in `.prev`.
  Unchanged SSQC/menu skipped; 23 protected native/config hashes/mtimes stable.
  Each installed engine/program pair passes the isolated 7/7. No owner process
  stopped. FLEET PENDING: `build.ps1 -Pi` refused one active player among 12
  rows, before upload/swap/restart. At 06:48:53Z still one player and remote
  csprogs still P676 `7d3954d9eb25152d`; never bypass the gate. Safe next step:
  once every active lobby is verifiably empty, build/deploy inspected product
  `b5a704f` from a clean tree and check remote hashes/live behavior.
  Retained evidence/staging: `C:/FTESurf-worktrees/labels-677-20261012T0623/`.

### Perfect-board presentation (Patch 686) — 2026-10-13

- `Board_PerfectFeedback` belongs at the new **live graded ramp** counter edge,
  not in `Board_Compute`: the latter also processes replay scans/restores.
  Ground/bhops and `Board_ResetRun` preserve the streak; only a non-perfect
  graded board clears it, or `Board_Clear` for a new map/VM. Sound Off/Mute still
  tracks it. Controls and original WAV generator: `tools/p686_board_feedback.md`.
- New loose sound directories must be present **before** a lobby's filesystem
  scan/restart. P686's first progs-only restart could not serve subsequently
  copied WAVs; a guarded restart after copying made fresh unseeded clients fetch
  all three exact cues. HTTP-mirror 404 is not the server-download result: prove
  the fallback files/hashes too, and do not claim an HTTP deployment from that.
- Splitting a mono grade into per-glyph drawstrings and summing their measured
  advances moved its percentage suffix **one pixel** versus the original whole
  string. Keep the suffix in its original centered whole-string draw, replacing
  the seven Perfect glyphs with mono spaces. P686's isolated-backdrop screenshot
  controls prove zero changed suffix pixels. Native software sound speed is
  quantized to 1/64, so PCM pitch tests use the emitted quantized frequencies,
  not exact equal-temperament frequencies inferred from the builtin arguments.

### The Boarding window's levels (Patch 631) — 2026-10-11

- THE WINDOW'S ENERGIES ARE LEVELS WITH THEIR OWN ZERO. `board_ein` is what you
  arrived with (the value the air segment closes at, so the Jump/Air row's
  `Energy now` is the same number), `leave_e` the energy on the frame the ride
  ends (the Ramp row's); `board_eref` and `leave_eref` are `HUD_EnergyRef()`
  taken then, and `board_eok`/`leave_eok` say that zero had an answer
  (`HUD_ZeroKnown`; `--` is drawn when it had none). `boarding` prints both, what
  each is made of, how long ago, the zero and the speedometer's e now, and the
  Segments column's last six rows.
- LIVE, THE FRAME A BOARD IS NOTICED ON IS NOT THE CLIPPED FRAME. The counter and
  its latched pair are the newest packet's; the drawn body can be a net frame
  behind (`cl_predict_extrapolate 0`). `Board_ClipSeen` is the part of the
  into-plane speed `vel` has already lost, f: the arrival is `e + stepe*f*(2-f)`
  and the ramp opens at `e - stepe*(1-f)^2`, so the Board row is the cost exactly
  whatever f is. One fall held at 42.3e in flight, cost 96.7, twelve rides with
  this rule: f 0.000 on a listen server (once 0.249), 0.495 dedicated, 0.990
  behind `sv_minping 120`; the enter read 42.1 to 43.2. Build 39's column and
  the first cut of this patch assumed 1, and on the listen server read the Air
  row 139.0 for 42.3, the Board row 42.3 for -54.4, and the Ramp row's change
  -96.3 for about 0.
- TWO CORRECTIONS INSIDE IT, EACH FROM A FAILING RUN. (1) vin is latched after
  StartGravity, half a tick of gravity past the tick the drawn state ended on:
  against bare `vin*n` a listen-server run read 45.9. (2) A drawn body earlier
  in its fall is short of the arrival's into-plane speed by a tick of gravity per
  tick it trails, and is not part way through the clip: 0.5 and 1.7 ticks behind
  read 44.1 and 48.6. Within two ticks' worth (f under 0.039 on that ramp) it is
  the arrival: the shipped build's listen ride printed `raw 0.033` and read 42.3.
  `boarding` prints f and the value before that allowance (`raw`).
- A REPLAY NEVER RUNS `Board_Frame` AT THE CURSOR. `Watch_BoardApply` calls
  `Board_Compute` on the newest board record at or before the clock, so anything
  `Board_Frame` stamps beside that call is the BUILD PASS's last board: the first
  cut drew one stale level (-22751e) at every seek. The level comes from
  `rec_wt_bde`, filled by the build pass on the sample after each `board` record
  (f is 1 there: a sample is the board's own tick), and is read against the
  viewer's zero NOW (`BD_Zero`). A stamp taken when the board was applied
  depended on where the seek came from. A replay still has no leave row.
- A RESET ADOPTS THE COUNTER. A listen server keeps `STAT_FS_BOARDCOUNT` across
  maps (4, the old plane still latched, 0.43 s into the next), and the first cut
  drew that as a board; closing a replay did the same with the replay's last.
  `Board_ResetRun` sets `board_resync` (live only) and `Watch_SeqRestore` calls
  `Board_ResetContact()`.
- THE ARM, ON THREE SERVERS. `tools/runlines_smoke.py
  ftesurf/cfg/test/p631boarding.cfg --mount --output-dir <owned dir>`; again with
  `--dedicated --map surf_kitsune --server-arg "+set run_startjitter 0"`; again
  with `--server-arg "+set sv_minping 120"` added; then
  `tools/test_p631boarding.py <log> <log> <log>`. The enter is graded against
  the speedometer's e printed in flight BEFORE the board. The first cut's checks
  compared the window with the Segments column, which made the same mistake,
  and passed at 139. A build with f fixed at 1, no resync and a stamped replay
  zero fails 5 of 11 on a listen server.
- DEPLOYED 2026-10-11 from `d43a0c2`: csprogs `1a27aa8f` only (qwprogs
  `e9c95065` and menu.dat were already these bytes in all three places). Both
  Windows installs 02:35:57Z; the Pi 02:37:08Z with nobody on, all 12 lobby
  processes started 02:37:11Z to 02:37:19Z (read from the host), and
  `pi_lobby_smoke.py` was served this csprogs and drew the board. `.prev` is
  Patch 630's csprogs (`9ab0442f`) in all three places.

### hud_edit: second sizes, what the speedometer shows, the keys' size (Patch 630) — 2026-10-11

- `HE_OptDef` HAS TWO MORE KINDS. `s` is a second text size drawn like an
  element's own size row (values = up to four pixel sizes, 0 = auto, the lit box
  clicked again clears it); `b` is a plain row of boxes (values, names). Their
  chips are `he_o_<cvar><value>`, one per box, where a toggle or a cycle has one
  `he_o_<cvar>`. An `s` label says `<Label> auto` or `<Label> 20`, not the size
  in force: "Subtext 16 auto" ended 4 px short of the first box.
- `hud_edit status` PRINTS `not drawn` FOR EVERY ROW WHILE THE EDITOR IS CLOSED:
  the drawers publish their boxes only while it is open (`0 rect(s) live`). An
  arm that grades a drawn box opens the editor first; `tools/test_p630hud.py`
  reported five checks as NOT MEASURED until its cfg did.
- THE SPEEDOMETER DRAWS WHAT `hud_speed_show` SAYS (0 speed, 1 both, 2 the energy
  alone). `hud_energy 0`, the old "off", is no longer offered by the editor. A
  config SAVED that way is moved at load (`HUD_RegisterCvars`: `hud_energy 1`,
  and `hud_speed_show 0` if it was 1), because left alone the pane read `Shows:
  both` and `Energy as: 0` over a speed with no energy, and clicking `Shows`
  went energy, speed, speed (the review ran it). Set in a session it still
  means no energy line under the speed, so cfgs that set it look as they did;
  at `hud_speed_show 2` the energy is drawn in units regardless. A watched
  player has no energy of yours to show, so spectating draws the speed in every
  mode.
- `hud_keys_size` (1, 1.25, 1.5, 2) SCALES THE KEY BLOCK, AND THE MOUSE PAD IS CUT
  FROM THE BLOCK'S HEIGHT. At auto placement (`hud_keys_x 0`) the block keeps the
  size-1 floor gap and the same gap on the right, so it grows up and to the
  left; where size 1 has no floor gap (hud_scale 3 in a 900-line window: it
  already ends at 912) a larger block stands on the bottom edge. A dragged
  block, or a detached pad, grows right and down from its anchor and is not
  kept on screen (BACKLOG). The duck/jump row's unit is snapped to the font
  ladder ONCE, at size 1, and multiplied: snapped per size, XL at hud_scale 3
  was 384x280 with a 64 px row under 96 px keys, not twice 192x156. At size 1
  the geometry is the old one (both builds print 128x104 at 1432,756 and the
  pad 166x104 at 1262,756 in a 1600x900 window).
- `waitms` COUNTS FROM THE FRAME'S START (the review, `cmd.c:278`), so a
  screenshot or a long dump earlier in the same batch eats it: the first run's
  "Mouse pane at S" shot was the Run graph pane, one frame rendered between the
  two dumps, and I had not looked at that one. `wait 4` after the wait fixes it.
- THE ARM: `python tools/runlines_smoke.py ftesurf/cfg/test/p630hud.cfg
  --output-dir <owned dir>`, then `python tools/test_p630hud.py <rig>/ftesurf/
  logs/runlines_smoke.log`. Clicks are `hud_edit ui hover <id>` and
  `hud_edit ui down|up mouse1`; each write is read back with the engine's own
  cvar print. 41 checks. The build before the patch failed 21 of the 34 the
  first cut of the cfg reached; the commit before the review's fixes fails the
  four they are for (the saved-off config's two reads, XL at hud_scale 3 twice
  S and on the bottom edge). A rig window is 640x480 unless the cfg sets
  `vid_width`/`vid_height` before its first wait; the panel halves its scale
  when it would not fit, so the cfg asks for 1600x900.
- DEPLOYED 2026-10-11 from `2570367`: csprogs `9ab0442f` only (qwprogs
  `e9c95065` and menu.dat were already these bytes in all three places). Both
  Windows installs 01:43:06Z, with `cfg/default.cfg` `922605a3` (the one before
  kept as `default.cfg.pre630-20261011T014306Z`); the Pi 01:43:53Z with nobody
  on, all 12 lobby processes started 01:43:55Z to 01:44:03Z (read from the
  host), and `pi_lobby_smoke.py` on lobby 1 was served this csprogs and drew
  the board. `.prev` is Patch 629's csprogs (`6ddb3e37`) in all three places.
  surfd's "account proofs must name game code" line still named the pair before
  at 01:45:30Z: `accounts.py`'s `game_code` re-reads the two files at each proof
  and logs when the pair changes, and no proof had arrived (the smoke's client
  has no key).

### SUI theme, the board and the gallery (Patches 606, 607) — 2026-10-10

- LOOK AT THE PANELS WITH `tools/ui_gallery.py`. One isolated rig, one arm per
  window size (`--sizes 1920x1080 800x600 ...`), a loopback stub for lobbies and
  both boards, up to sixteen screenshots an arm; `--against <rig or arm>` writes
  side-by-side pairs. It grades only that every shot exists and the log has no
  QC error. `tools/test_ui_theme.py` is the look gate built on it: every panel
  pixel-identical to a control build (or to an earlier gallery arm), a csprogs
  it mutates itself (one theme colour) caught where that colour is drawn and
  nowhere else, and a menu tooltip read back. Its regions are 1920x1080 at
  hud_scale 2.
- THERE IS ONE STYLE SINCE PATCH 607. The palette is `SUI_THEME_*` in
  `sh_ui.qc`; a panel's own names (`SBC_`, `HEC_`, `PLC_`, `COL_`) are aliases
  of those tokens. While two styles existed, each alias was
  `(style ? token : '<old literal>')`, and TWO LITERALS THAT LOOK ALIKE WERE NOT
  ONE MACRO: the first cut folded the room list's `'0.35 0.85 1'` and
  `'0.5 0.8 1'` into a macro whose classic arm was `'0.35 0.75 1'`, and the
  pixel gate could not see it (one player in the room, nobody spectated, no
  voice icon hovered). A reviewer diffing removed literals against their
  replacements found it; do that diff, a gate only covers the states its
  gallery reaches.
- "0 PIXELS DIFFER" BETWEEN TWO BUILDS IS ALSO WHAT TWO PANELS THAT NEVER OPENED
  LOOK LIKE. While two styles existed, "modern differs from classic" proved each
  panel drew; with one style that witness was gone and a reviewer noticed.
  `test_ui_theme.py` P0 now makes every shot differ from a named other shot of
  the SAME run (the plain HUD, or the state before it). And A MENU PANEL'S
  ROUNDED CORNERS SHOW THE ANIMATED BACKDROP: a region two pixels inside a
  12 px-radius panel read 16-18 "changed" pixels, all in its corners; six clears
  them.
- A RIG WINDOW THAT TAKES THE FOREGROUND LOSES ITS PARKED HOVERS. The final
  Patch 606 theme run failed three menu comparisons that way (a hovered lobby
  cell and a hovered close button missing), with `[focus] window is foreground`
  in that rig's log and the parked cursor reading back as the real pointer's
  321,1137. `ui_gallery.py` now reports such a rig as INTERFERED and the gate
  exits 2, not 1: it is not the build's fault and not a pass either.
- A HELPER NAMED FOR ONE PANEL CAN BE ANOTHER'S ONLY DRAWER. Deleting the
  renderer menu's classic `Gfx_Row` broke the vote box, which is its other
  caller. fteqcc said so in its FIRST error and then printed hundreds of
  cascaded warnings and crashed: read the first error, not the tail.
- `m_draw` CALLS `Font_Reset()` BEFORE `sui_end()`, so anything `sui_end` draws
  (tooltips, the bind overlay) starts in the 8 px bitmap face unless it selects a
  font itself. The first menu tooltip was drawn in it.
- THE KEYBOARD CURSOR IS A HOVER. sui parks it on a control the moment a menu
  opens, so a tooltip keyed on `sui_is_hovered` alone pops up unasked. Tips test
  `_cursor_is_mouse_active`. `ui_click` ends in keyboard mode, so a cfg holds a
  tip up with `ui_hover <x> <y>` (menu VM) and reads it back with a bare
  `ui_hover` at least one frame later: `tip 1 [<sui id>]`.
- THE BOARD ALWAYS DRAWS, AND SAYS WHICH FORM IT TOOK. `Scores_Draw` sizes
  itself in steps (type, columns, room list) and past the last one shrinks its
  type toward 8 px. `scores status` prints `cols` (5-9) and `type` (px) for the
  last drawn frame: that is how a cfg tells the steps apart without a pixel.
- THE p603 SUITES COMPILE THEIR OWN CSPROGS FROM THE WORKING TREE (`src/` plus
  `tools/fixtures/`); `--qc-artifacts` supplies menu.dat, and qwprogs.dat outside
  `--dense`/`--http`. The tree is the board source under test, whatever build
  directory is passed, so do not edit `src/` while one runs.
- THE p603 SUITES SPLICE THE CFG AT EXACT SEQUENCES: the three startup lines
  (`set ui_native_scores_font 13` / `scores tab local` / `+showscores`), the
  final `-showscores` / `replay off` / `waitms 500` / `p603 probe closed1`, and
  `echo P603 FINISHED` / `quit`. A line inserted inside one makes a suite raise
  before any arm runs; the source-switch clicks sit outside them.
- THE BOARD'S sui IDS ARE THE HARNESS'S HANDLES (`sb_run<i>`, `sb_ln<i>`,
  `sb_t0..3`, `sb_leg<i>`, `sb_fa/fc/fs/fx`, `sb_tref`, `sb_graph`): they
  survived the redesign unchanged, which is why the p603 suites still grade its
  clicks, and `p603 move sb_t1` (any id spelt `sb_...`) clicks the source
  switch. Both row drawers read `sb_colx/sb_colr/sb_colon`; a new column wants
  an `SBK_` id and a slot in `Scores_Cols`.
- THE p603 RIGS HAVE NO `gfx/ui/roundmask.png`, so they draw the board
  square-cornered (the missing-mask fallback). Their screenshots are evidence
  of what acted, not of the look.
- `p603perf.py` PROVES THE NATIVE ROUTE FROM A SCREENSHOT: it counts the themed
  provider's own background. It used to count ImGui's default blue, which the
  theme removed; a provider colour change moves that witness before anything
  else.
- A FIXED PIXEL, CROP OR CVAR VALUE IN A GATE IS A LAYOUT ASSUMPTION. Three of
  the p603 tools carried the classic board's geometry and each failed
  differently when it went: `p603perf.py`'s crop sat below the new rows (893
  bright pixels against a bound of 1000 at the default 6 rows, fine at 20);
  `test_p603dense_unit.py`'s one-pixel control poked (568,279), outside the new
  rank crop, so a control meant to be caught was not (68/69); `p603life.py`
  docked the room list with `hud_scale 5`, which the new board answers by
  shrinking its type. Derive positions from what the subject prints (`P603
  RECT`), and when a layout changes, run each tool at its DEFAULT arguments
  once, not only the ones the gate script passes.
- TaskStop DOES NOT END A GATE SCRIPT'S LOOP ON THIS MACHINE. A stopped batch
  ran its remaining steps for 24 more minutes beside the batch that replaced
  it, two games at once. Listing only game and python processes afterwards did
  not show the surviving `bash.exe`. The owned gate scripts check a stop file
  between steps and wait while another game is running.
- `p498keys.py` IN A BARE WORKTREE NEEDS `ftesurf/data/consent.txt` (`version 1`)
  AND A CHOSEN NAME (`+set name X` on the command line; an autoexec.cfg is not
  run), or it grades the terms screen: 6 of 16 failed, then 1, then 0, with no
  product change between them. Run the exe by hand and `--grade-only`. The run
  leaves `installed.lst` BESIDE the gamedir as well as files in it; a cleanup
  that lists only `ftesurf/` misses it.
- A HARNESS WINDOW THAT TAKES THE FOREGROUND MID-RUN FAILS UNRELATED CHECKS.
  `test_ui_modern.py` lost four (tooltip, dirty save) in the one run whose log
  holds `[focus] window is foreground` between its stages; the next run, on the
  same files, passed. Grep for that line before believing a UI arm's failure.
  (`window is NOT foreground ... correcting` at startup is the normal line.)
- AN `-Engine` BUILD CHANGES THE ENGINE'S HASH EVEN WHEN ONLY THE PLUGIN'S
  SOURCES CHANGED: both `fteqw64.exe` and `fteqwsv64.exe` came out different from
  the previous build of the same engine source. Identical bytes are not available
  as evidence that engine source did not move; use the commit.

### The trainer, the run graphs and the list thumb (Patch 610) — 2026-10-10

- LOOK AT THEM, AND GRADE THEM, WITH `tools/p610ui.py` (ui_gallery's rig). The
  trainer: a driven jump in zero gravity, `+right`/`+left` at an authored
  cl_yawspeed, graded on its own `trainer:` lines (developer 1 and
  log_developer 1 around the drive only). The graphs: three synthetic 46-53 s
  runs through `scores lineat`, one of them replayed; graded on `linegraph
  status` (view, drawn window, value range, `hud`, vertices, playhead) and on
  `hud_linegraph` after a real click on each of the three switches. The thumb:
  `ui_cursor`'s rectangle for `cs_listvbar` before, during and after a drag.
  `--legacy` sends a pre-610 csprogs only what it knows; `--perf` prints QC
  time per frame from profile_csqc windows.
- `drawline` IGNORES ITS WIDTH (pr_menu.c:1089): one aliased hardware line and
  one draw call a call. The old graph issued two per filled bin per run per
  plot. A curve is cl_plot.qc's `Plot_Strip`/`Plot_Q`, which is cl_lines.qc's
  `Line_Emit` with a mitre. `Scores_Tick` still asks for a width it does not get.
- ORDER IN A PANEL THAT DRAWS CURVES: fills and text, every polygon, a fill,
  then text. A drawstring between two polygon batches does not appear (the
  note over `ln_lab_p`). `drawresetcliparea` flushes the batch while it is
  still clipped, so the clip goes round the curves and nothing else.
- A CURVE IS SIMPLIFIED ONCE, NOT REDRAWN FROM ITS BINS. `LineGraph_Simplify`
  cuts a slot's bins to the fewest vertices within a physical pixel of what
  the bins hold (a cone of slopes from the last vertex keeps half a pixel from
  each point it is fed, and a bin's low and high are fed when they stand that
  far off its ends; a break, a gap or a bin holding either ends the strip) and
  `LineGraph_Curves` draws that until the drawn buffer, the value range or the
  plot's height changes. That bound is by construction: no arm measures the
  deviation. The tolerance is in value units, so a taller plot keeps more:
  three 50 s runs are 104 vertices on the HUD's speed plot and 197 on the
  panel's (542 on its energy plot), from about 2300 points. `linegraph status`
  prints the counts. The first cut's cone was three times as wide while its
  notes said half a pixel; that was found in review, not by an arm.
- THE GRAPH HAS A VIEW. Bins are built for [lg_v0, lg_v1] into the buffer that
  is not drawn and swap in when complete; until then the old buffer is drawn at
  the new view. `linegraph zoom <from> <to>` sets it from a cfg and bare `zoom`
  fits. `lg_buildslot` still reads 9 when a build is done (`p545graph.py`).
- THE COMPARISON PANEL DOES NOT SHRINK WITH hud_scale, only its type does: its
  width is the larger of 68 row heights and 56% of the screen. The first cut
  tied it to the type alone, and p545's rig (a small scale) drew a 540 px panel
  with the energy caption under the gravity warning. Where both do not fit, the
  warning stays.
- `hud_edit ui hover|down|up` DRIVES WHICHEVER PANEL HOLDS THE CURSOR since 610
  (the board's `sb_*`, the graph panel's `lg_*`), not only the editor: the last
  sui bracket of a frame owns `_action_elements`. With no cursor panel it says
  `sui_probe: no cursor panel` (it said `editor closed`).
- THE MENU HAS A DRAG: `ui_hover @<id> [dx dy]` parks the mouse on the middle of
  a control as last drawn, `ui_mouse down|up` is the button alone. `ui_click`
  is both at once and cannot hold anything.
- A REPLAY WHOSE `map` HEADER IS NOT THE SERVER'S NAME FOR THE MAP CLOSES ON ITS
  NEXT FRAME (`rec_wt_map != serverkey("map")`). The replay arm first wrote
  `map uigallery` on a server that says `uigallery.map`: the log read "opened"
  then "stopped", and the playhead the arm existed to show read -1.
- A SCROLL THUMB HAS A FLOOR (`sui_scrollbar`): four gutter widths, never over
  half the list, and its travel shortens to match. A list whose proportional
  thumb is already longer takes the old arithmetic untouched, which is why the
  look gate matches the menu leaderboard's thumb to the pixel but for its grip.
  At 640x480 the map picker's list has no height (-16 px): the tool prints NOT
  GRADED rather than a pass.
- `test_ui_theme.py --moved SHOT:X0,Y0,X1,Y1` leaves a rectangle a patch
  changes on purpose out of P1, and a P1 failure prints the box its differing
  pixels fall in. Find a rectangle by blanking candidates until 0 remain
  (`differing(..., moved=[...], box=True)`), not by reading the layout code.
- `profile_csqc` PRINTS OPS AND SECONDS, NOT CALLS. `Rewind_Waiting` and
  `Online_ReplayState` are one op each, once a frame: their ops are the
  window's frames, and the tool refuses a window where the two disagree. The
  seconds are the profiler's, well above the unprofiled cost: compare builds
  with them, do not quote them as a budget.
- A GATE STEP THAT RUNS SEVERAL RIGS WAITS FOR ANOTHER SESSION'S GAME ONLY
  BETWEEN STEPS. A peer's 30 s install run overlapped one gallery of the look
  gate. That run was not flagged INTERFERED and its pixels matched; read the
  focus lines before trusting one that was.
- A HOVER CAN DIFFER BETWEEN TWO RUNS OF ONE BUILD. One look-gate run failed on
  two menu shots that differed only in which lobby card was lit, with no focus
  line in either log; the same builds matched to the pixel on the next run. The
  real mouse cursor resting over the rig's window would do that, and nothing
  records where it was: likely, not demonstrated.
- **DEPLOYED 2026-10-10 14:12 to 14:14 UTC (FTESurf `eafb117`).** Both installs:
  csprogs.dat `fe286a637a2d1ebb`, menu.dat `a8ef786dad01bb12`, their `.lno` with
  them; qwprogs.dat was already this build's (`199ffdd83dec9651`) and was not
  written. `.prev` there is Patch 615's csprogs (`a28719be71d38908`) and the 10
  Oct menu.dat (`d38891771c3ae376`). The Pi: `build.ps1 -Pi` from a clean
  worktree at `eafb117`, 0 players, all 12 lobbies restarted 14:14:04 to
  14:14:13 UTC; read back csprogs `fe286a63`, qwprogs unchanged, `.prev` the
  Patch 615 pair. `tools/pi_lobby_smoke.py`: lobby 1 served `fe286a63` and the
  board drew.
  TWO THINGS THE COPY NEEDED. fteqcc's compile date (`Compiled [YYYY/MM/DD]` at
  offset 96 of a .dat) made the installed menu.dat, built the day before,
  differ from a build of the same source by one byte, so "is the installed
  file main's build" is asked with that date masked. And a fresh `git worktree`
  has no `src/fteqcc64.exe` (ignored): `-Pi` stops at the compile, before
  anything is sent. Copy the compiler in from the checkout that gated.

### Run graphs on ImPlot (Patch 614) — 2026-10-10

- **DEPLOYED 2026-10-10 15:03 to 15:07 UTC (FTESurf `56d8582`, engine
  `a67cebe1e`, tag `patch-614`).** Both installs: the client `7c97e69b27cad2b2`,
  C:\FTEQuake's server `1c338f6407b15489`, the five plugins (ui_imgui
  `69929fe57fa06826`, hl2 `4406ae6a98515b7e`), csprogs.dat `ce6397a5a3de525e`,
  menu.dat `19874c5a21619d1b`; qwprogs.dat not written (`199ffdd83dec9651`).
  `.prev` beside each is what it replaced. The Pi: `build.ps1 -Pi` from a clean
  worktree, 0 players, 12 lobbies restarted 15:06:34 to 15:06:42 UTC; read back
  csprogs `ce6397a5`, qwprogs unchanged, `.prev` Patch 610's pair. Lobby 2
  served `ce6397a5` to a fresh client running a copy of the installed exe.
- THE PLUGIN IS NOT LOADED BY A NORMAL BOOT, AND NO ARM COULD HAVE SAID SO: each
  one types `plug_load ui_imgui`. Found after the deploy, by asking what the
  owner would see. In a rig with the real default.cfg and both DLLs beside the
  exe, `plug_loaddefault` reads 3, `plug_list` says `fteplug_ui_imgui_x64.dll:
  not loaded`, and `ui_imgui_status` is an unknown command until the plug_load.
  The patch's notes said "where the plugin is installed"; they say "loaded" now.
  When a feature rides on something optional, boot a plain rig and look.
- PATCH 618 NAMES IT IN default.cfg: `if $dedicated == 0 plug_load ui_imgui`.
  Three plain boots on that file (`runtime/plugprobe`, the stamped Patch 614
  binaries): a client with the DLL lists it loaded and answers
  `ui_imgui_status`; a client without it boots and draws the QC panels; a
  dedicated server with the DLL beside it does not touch it. With the guard
  taken out, that server loads the DLL, the plugin refuses, and the log says
  `Couldn't load plugin ui_imgui`: the guard is what the server arm shows.
  `$dedicated` is the engine's own macro (cmd.c), "1" or "0".
  **DEPLOYED 2026-10-10 15:30 to 15:31 UTC (FTESurf `9239f6f`):** default.cfg
  `e971b8cb0ced3e67` in both installs, the predecessor (`8fd357ac59147c8a`)
  beside each as `default.cfg.pre618-20261010T153048Z`; and on the Pi for
  parity (`default.cfg.pre618-20261010-153115`), with no lobby restarted,
  since a server skips the line. C:\FTESurf is also the canonical checkout,
  so `git status` there shows default.cfg modified until it reaches 9239f6f.
- THREE LAYERS, ONE AUTHORITY. QC (`cl_linegraph.qc`, the `lgn_*` block) owns the
  rows, the energy sum (`lgn_e`, 8192 rows a frame), the chips, the card and
  every number. The engine (`cl_plugin_ui_plot.inc`) copies rows out of QC memory
  and validates them. The plugin (`plots.inc`, owner 206) draws and reports the
  view and the cursor's time back as scalar actions 1-5. Nothing the plugin
  reports is used as data: the card reads `LineGraph_At` at the reported time.
- `ui_native_plot_rows` TAKES QC POINTERS, the first native UI builtin that
  does. The host resolves each with `PR_PointerToNative_MoInvalidate` at OFFSET
  0 (its regular-pointer branch tests `offset` but returns `stringtable + ptr`,
  so a non-zero offset would be bounds-checked in one place and read in
  another), and reads through memcpy: a QC pointer need not be aligned.
- A PLOTTED NUMBER IS BOUNDED, NOT JUST FINITE: `PLUGUI_PLOT_MAX_VALUE`, 1e9.
  The first cut took any finite float, and at 1e30 a flat view could not be
  padded and a hover failed the frame. x is judged LESS ITS OFFSET, so a run
  that starts late on a long clock still passes.
- A VM DRAWS ONE NATIVE OWNER A FRAME, AND THE BOARD'S CHIP OPENS THE PANEL
  MID-FRAME (`Scores_Finish`), after the board's native table has drawn. The
  panel's first draw is then refused. The first cut read that as the plugin
  failing and kept the QC plots for the whole open; `lgn_nodraw` lets one go
  and gives up on three running.
- THE HOST DROPS AN OWNER OVER AN ACTION PAST 1e6. A zoom request outside the
  run came back as such a report; the panel saw no actions, kept `drew 1`, and
  opened a new owner every frame (context, font atlas, revision).
  `linegraph status` read healthy throughout: only the plugin's `opens` counter
  moved. When a native panel looks right and costs too much, read
  `ui_imgui_status` twice.
- ImPlot ZOOMS ONE STEP FOR A FRAME'S WHEEL WHATEVER ITS SIZE (`implot.cpp:2026`),
  a notch in and a notch out are not inverses (x0.8333 and x1.25 at ZoomRate
  0.25, x1.0417 the pair), and ImGui takes a wheel queued after a move a frame
  later. So the panel sends one event a frame, a notch at a time, and a harness
  cannot predict a span after mixed notches: it counts what was sent.
- IMGUI'S ASSERTS ARE LIVE IN THE PLUGIN BUILD. Owner 206 switches the
  recoverable ones to a callback that fails the frame (`PlotsError`); a plain
  `IM_ASSERT` anywhere, and every other owner, still ends the process.
- A POINT ON SCREEN COSTS ABOUT A MICROSECOND through the mesh path (the backend
  expands indices to vertices, the host clips every triangle on the CPU). Two
  points a pixel column was 11,752 points and 9-16 ms a frame. The plugin now
  cuts each curve to within 0.25 px of its rows and keeps the strips until the
  view changes; `linegraph status` prints `points`, `rebuilt` (0 while the view
  is only read) and `cut`, its running sum. If `cut` climbs while nothing is
  touched, something in the key moves every frame: the y axis is fitted to ROWS
  in view for that reason, not to the surviving vertices.
- THE FIRST COST RUN THAT LOOKED BAD WAS MINE. A second run read native at 3.9 ms
  and QC at 5.4 ms in one window: an image diff and a rebase were running beside
  it. `p614plots.py --arms cost` alternates the two routes inside one run for
  that reason; read the QC windows against each other before the difference.
- A MUTANT THAT DOES NOT BUILD IS NOT A CATCH. Two of the host sweep's catches
  were an unused variable and an unused function under -Werror: the fixture
  never ran, and "21 of 22" had been 19. `p614mutants.py` has a NO RUN verdict
  now, and both mutants were rewritten to compile (and are caught).
- THE HARNESS'S OWN FOUR. Found by review, each fixed: the native arm printed
  NOT GRADED and passed when the plugin did not draw; the fallback arms graded a
  status line that reads the same on every route and no pixels; one check
  compared a variable with its copy; five grammar cases were refused by a
  neighbouring rule. `linegraph refuse` and `lose N` exist so an arm can force
  the two ways out, and the `routes` line counts which route drew each frame.
- `linegraph probe` SENDS ONE HOSTILE TRANSACTION A FRAME, not all at once: the
  host allows two `begin`s a frame, and a refusal for the budget is not the
  refusal under test. Each case prints what every call returned.
- AN OLDER FIXTURE FILED THE NEW TABLE AS THE DRAWING SERVICE.
  `p598imgui_host.cpp`'s ExportInterface copied any name it did not know over
  its `service` table, so the plugin's fourth export made `Close` a wild pointer
  and the suite segfaulted. It read like a plugin crash; the control was the
  same fixture against the pre-patch tree (110 checks, 0 failed). Unknown names
  are refused now, as an older host does.
- THE UNIT TOOLS EXTRACT THE ABI FROM plugin.h BY A MARKER LINE
  (`test_p590bridge_unit.py::host_controls`). A new table after the last marker
  is not in `ui_abi.h` and every host fixture stops compiling: add the marker.
- `[focus]` LINES: `window is foreground` is the gallery's INTERFERED. The
  other one (`NOT foreground but the focus messages said active -- correcting`)
  drops a parked SUI hover just the same; it cost one run its emphasis shot.
  `p614plots.py` fails an arm on either between the panel opening and the arm's
  own `vid_restart`, which always prints two.
- THE REAL MOUSE CAN REACH A RIG, AND NO FOCUS LINE SAYS SO. A GL or Vulkan rig
  prints `NOT foreground ... correcting` as it starts and took no real input
  in any run. A D3D11 rig prints no focus line at all, and both D3D11 runs of
  the native arm took real mouse positions: 77 before the harness's first move
  in one, 106 inside an idle second in the other. Most likely its window is
  the real foreground one; that was not checked. `linegraph status` prints
  `events`, what the panel forwarded to the plugin, and the arm calls a count
  that moves while its own cursor is parked INTERFERED.
- THE PLUGIN'S CLOCK IS REAL FOR OWNER 206 ONLY (a double click and the splitter
  delay are measured in ImGui time; every other owner still advances 10 ms a
  Draw). A fixture that draws frames back to back gets the 0.5 ms floor.
- msys `make` FROM GIT BASH LOSES TEMP: gcc then tries `C:\WINDOWS\` and every
  compile fails with "Cannot create temporary file". Exporting TEMP in bash does
  not reach it. Run the engine build from pwsh, as `build.ps1` does. And a new
  engine worktree has no `engine/libs-x86_64-w64-mingw32` (ignored, 72 MB):
  copy it from one that built.

### Board lines in run order (Patch 624) — 2026-10-10

- THE WINDOW WAS ALREADY THERE. `Line_Window(ta, tb)` narrows a draw's local
  ia/ib, fades both ends and touches no storage; the replay used it round its
  playhead and the board loop switched it off, because a board line had no
  playhead. This patch gives it one: the sample nearest the eye, in run order
  (`Line_Follow`), and `Line_FollowWindow` sets the window from it before each
  board slot's `Line_Draw`. It is ONE global window: off again after the loop.
- NEAREST IS NOT ENOUGH, WHICH IS THE WHOLE BUG. A route that passes the same
  place twice has two nearest points. The cursor is FOLLOWED (48 samples either
  side a frame, the last of equals; a line's own teleport is two neighbouring
  samples, so it crosses with the viewer), and four times a second the whole
  line is looked over as well. Every stretch within 1.5 times the nearest
  distance (or 128 u) is a candidate: the one being followed stays if it is
  one, else the one nearest in time to it wins; with no cursor believed (a new
  line, or a restart: the clock stepped back or the timer armed) the earliest.
- THE FIRST CUT LOOKED ONLY WHEN THE EYE WAS 768 u FROM THE FOLLOWED STRETCH,
  AND THE REVIEW BROKE IT FOUR WAYS, by porting the follow to Python and flying
  real recordings through it. (1) A stop in the recording longer than 48
  samples held the cursor at its first sample: `<` takes the first of equals,
  and a 9 s stop left nothing drawn ahead of the viewer. (2) Another part of
  the route within 768 u was never taken: dropping from one pass to another
  470 u away, 6.9 s beside a line that was not drawn. (3) The look compared its
  512 samples and nothing between them: on a run of a few minutes they are
  hundreds of units apart against a tolerance of 128 u, and it took the later
  pass a quarter of the time at 2000 u/s. Now any of the 512 that could have a
  nearer sample beside it (a sample between two is at most their spacing nearer
  than either) is looked at sample by sample, and a run of them is ONE stretch
  with one nearest sample, so a near pass cannot crowd a farther one out of the
  24 kept. (4) A restart's forget lasted one frame, and the stats lead the
  view: spent where the viewer still was, it took that place's stretch and kept
  it. It lasts `LN_FO_FRESH` (0.5 s) now.
- `lines order` prints the cursor, the looks made and those that moved it;
  `replay marktrace 1` prints, from inside the draw, the window a slot was given
  (`lnd`) and the samples it drew (`lnd2`). `tools/p624order.py` grades both,
  and counts the later pass's pixels: 0 with the order on, 1094 with
  `hud_lines_order 0`. It has a step for each of the review's four on a second
  authored run at a real pace (2000 u/s, 162 s, the 512 samples 660 u apart,
  and the fixture checks that a look at the 512 alone takes the wrong pass),
  and THE REVIEWED BUILD FAILS EVERY ONE: after a restart from far down the
  later pass it reads 27.165 s where 5.000 belongs.
  Thirteen one-line mutants each fail at the step that is theirs: always the
  earliest; a restart forgets nothing, or for one frame; the window never set,
  or as long behind as ahead; never follows; nearest only; the first of
  equals; the 512 alone; never looks again; keeps whatever it follows; the
  name on the whole line; a stale window read as one.
- THE NAME ON A LINE MUST SEARCH WHAT WAS DRAWN. `LineGraph_WorldLabels` looked
  over the slot's whole shown range; with a window that puts a name on a part
  of the line that is not there. It reads the window the board loop gave the
  slot THIS frame (`ln_fo_wt` is that frame's cltime), less a twelfth of the
  span at each end: the window fades over a sixth. THE FIRST CUT READ
  `tb >= ta` AS "A WINDOW WAS GIVEN", which the arrays' initial 0 and 0 also
  are, and the board loop returns before it writes anything when no line is
  ticked: the open replay's name sat on its first sample, or nowhere, until a
  line had been ticked once. Every rig that opened a replay ticked lines
  first. The arm stands ON one pass with the cursor on
  the other: the name is on the cursor's pass, 100 u aside, and with the clamp
  taken out it is on the pass under the eye. ITS FIRST CUT STOOD BETWEEN THE
  PASSES AND PASSED WITH THE CLAMP TAKEN OUT: the search takes the nearest of
  256 coarse samples the text fits at, and 2 u of drift decided which pass
  that was, the right one both times.
- `cfg/test/p449win.cfg` W5 reads `winon 0` for a board line to show that the
  REPLAY's window never reaches it. It sets `hud_lines_order 0` now.

### The live run on the run graphs (Patch 622) — 2026-10-10

- THE LIVE SLOT IS A GRAPH SLOT NOW, NOT A SPECIAL CASE BESIDE THEM. `LG_SLOTS`
  is `LN_SLOTS` (11), so every `ln_*[s]` in cl_linegraph.qc still indexes the
  line it means; what differs for the live one goes through three accessors
  (`LG_Start`, `LG_Ia`, `LG_Ib`): its zero is the graph's and its last sample
  is `ln_n - 1`, not the trail's shown range. `LineGraph_Available(9|10)` is
  `s == lv_slot`.
- ITS BINS ARE ADDED TO, NOT REBUILT. A slot's bins were rebuilt whole when its
  sample count changed; the live one's changes every tick. `LineGraph_LiveFold`
  puts new samples straight into the drawn buffer and bumps `lv_head`, on which
  only that slot's curve is cut again. A full rebuild is for a new run
  (`tr_gen`), a new zero, the halving past LN_CAP (`ln_step`), a line begun
  again in place (`ln_graphgen`: a trim, a load) and the head passing the span.
- A STAGE RUN'S ZERO IS WHERE ITS CLOCK STARTED, NOT THE BOUNDARY. A ticked
  stage window is `[T - dur, T]` from `stagepost`, and `dur` is counted from
  `run_st_tick`, which `SV_StageStart` moves to the walk out of the stage's
  box. So the live zero is `STAT_FS_STAGEBASE` as it stands, not as it stood
  when the segment changed: the first cut captured it at the change and was a
  box-wait early. The arm's `base` column is that stat, and start == base is
  graded.
- THE TIMER'S STATS ARE THE SERVER'S PRESENT, AND THE LINE IS ITS PAST. A
  teleport into a stage's box moves the stats a frame or more before the
  trail's sample there ends the line (`Trail_Take`, `Trail_InBoundary`). The
  first cut re-read the alignment every frame, so the line that was about to
  end was given the next stage and its zero, and kept like that: one dot at
  x = 0, energy 52.6 where 0.0 belonged. It was in the arm's own passing log;
  the arm graded only `seg` and `base` at that mark, and the review read the
  line beside them. A changed answer now waits `LV_SETTLE` (0.25 s) of the
  line's OWN growth past the frame it was first seen in. The arm ticks a
  stage 1 run as well and reads the line in the box of stage 2: same line,
  same zero, every sample it had, not growing; the first cut fails it.
- A REBUILD ONLY THE LIVE RUN ASKED FOR KEEPS THE DRAWN BUFFER UP (`lv_wait`:
  not folded into meanwhile). It blanked the whole graph to "building..." at
  every run start and stretch. THE RIG COULD NOT SHOW THAT: its two 401-sample
  runs rebuild inside one frame (2048 samples a frame), so a blank frame never
  happens whichever way the code is written. The arm's `many` phase ticks
  eight: blank frames 0, then 7 as they are ticked, and still 7 after three
  rebuilds for the live run alone (the mutant: 3 more).
- AN AXIS NOBODY READS IS NOT A REASON TO CUT EVERY CURVE AGAIN. The fold bumps
  the curves' generation when a sample leaves either cached range; the range
  of a plot the HUD does not draw is never refreshed, so once the energy left
  it every frame cut all eleven slots again: 108 times in 1.7 s against 3
  (the mutant, and the arm's `up` step: `setpos` 400 u higher, no status in
  between, because the status reads both ranges and a range just read is not
  stale). A range is compared only while `lg_rgen` says it is current.
- THE PLUGIN'S WHOLE VIEW ENDS WHERE ITS ROWS DO, not at `lg_tmax`, which is
  rounded on past a live head: the `fit` chip stayed up past the longest ticked
  run. `lgn_ext`, and the rows before it, since the view comes back a frame
  after new rows.
- `ln_leg` / `ln_track` (cl_lines.qc) say what a ticked slot's window shows; the
  two loaders set them after `Line_Range` (`Line_Leg`). Without them the graph
  could not tell a stage window from a whole run.
- `tools/p622live.py`: the timer really runs in the gallery rig (its start box,
  a strafe out of it, then coasting at one speed with no floor and no gravity).
  Linear arm, `--staged`, and `--plugins` for the panel on ImPlot. The `timer`
  line of `linegraph status` is the server's stats, the `live` line what the
  graph made of them, `liveops` its own counters; the white ink in the plot is
  counted and ends at the head's column. Ten one-line mutants, each caught at
  its own step. `tools/p545graph.py` read `build 9` for a finished cache: it is
  `LG_SLOTS`, 11 now.

### The release ships the ui_imgui plugin, and a dry run with no network (Patch 623) — 2026-10-10

- `release.ps1 -DryRun` IS NOT OFFLINE. It writes and deletes a probe object in
  the production R2 bucket and reads the published archive's hash. To try a
  change to the ship set without that, and without touching the tree releases
  are cut from: `git worktree add` a scratch tree, build its QC, copy the three
  binaries in from engine\release, `tools/release_tree.py <tree>` (copies the
  ship set's untracked files from the install, read only), then
  `tools/release_dryrun.ps1 -Tree .. -FteRoot .. -OutDir .. -BuildNumber <qcbuild>`.
  It defines functions named rclone, ssh, scp and curl before calling the
  script, which PowerShell resolves ahead of the executables, and lists what
  they swallowed (three rclone calls). Every gate, the stage, the tripwire, the
  pack and the archive check run for real.
- GATE 3 PINS THREE BINARIES NOW: the exe, the hl2 plugin and
  `fteplug_ui_imgui_x64.dll` must each hash to engine\release's.
  `build.ps1 -Engine` deploys all three, so its advice still holds. No built
  copy at all is "cannot check", as it was. ONE MISSING BESIDE THE OTHERS IS
  SKEW: the first cut asked for all three or nothing, which switched the gate
  off for a tree holding only the exe and the hl2 plugin (the review ran the
  two versions of those lines side by side). And the three are hashed again in
  the stage: gate 3 reads them minutes before they are copied, on a machine
  where another session deploys.
- THIRD-PARTY.txt IS GENERATED INTO THE STAGE, like VERSION.txt, and is about
  that one DLL. READ, each stopping the release if absent or not the text
  expected: Dear ImGui's LICENSE, the notice at the head of `implot.h` (ImPlot's
  LICENSE file names one holder and 2020; the compiled sources name two), stb's
  statement at the foot of `imstb_truetype.h`, Roboto's OFL beside the plugin's
  font, all from `plugins/ui_imgui/` in the engine tree; and winpthreads'
  COPYING from `src/release/notices/` (a copy of the compiler's own file).
  ProggyClean's MIT text is typed in.
- WINPTHREADS IS IN THAT DLL AND IN NEITHER OTHER BINARY. plugins/Makefile links
  it `-static-libstdc++ -static`, and libstdc++ brings the thread library with
  it: `grep -a -o 'pthread_[a-z_]*'` finds 134 names in the plugin, none in the
  exe or the hl2 plugin. Its licence (MIT and a BSD part) asks for its notice
  in binary copies. A C++ plugin linked that way owes it; the C ones do not.
- SOURCE.txt NAMED THE BRANCH `engine-patches`, which stops at Patch 500 on the
  remote and has no `plugins/ui_imgui`. The pinned commit is on `main` only
  (`git branch -r --contains`). It says `main`.
- THE `qcbuild` PIN WAS NEVER READ: the drift check took ENGINE.txt's first 40
  lines and `qcbuild` is at 179, under the patch notes. `-BuildNumber` leans on
  that warning. It reads the whole file.
- THE STAGE COUNTS ITS GENERATED FILES BY A LITERAL (`$staged += 4`). Add one
  and forget it, and "staged N files" is one short while the archive check
  still passes: it compares the archive with the stage, not with that number.
- Controls run in the scratch tree, each stopping the script with its own
  message: the plugin absent ("ship set names a file that does not exist"),
  one byte appended to it (gate 3 names it), its built copy absent beside the
  other two (gate 3 names it), `implot.h` moved aside, a byte appended to the
  staged DLL while the rest was still being copied. `-BuildNumber 88` draws the
  drift warning with `qcbuild 89` in it, and a relative `-FteRoot` completes.

### Demo trainer inputs (Patch 712)

- REMOVING THE REPLAY HIDE IS NOT A FIX. The live sampler is downstream of the
  replay/ghost input returns, so it would show the viewer's last jump. The shared
  Trn_Sample consumes each file sample on its recorded clock, not Watch's
  interpolated angles, viewer commands, playback multiplier or rendered dt.
- DO NOT ADD ANOTHER WHOLE-FILE PASS TO WATCH_OPEN. Its existing inference/board
  passes already approach the VM instruction budget on long files. The trainer
  walks at most 512 records per frame; backwards seek rebuilds with an explicit
  Reading demo inputs placeholder, never partially reconstructed grades.
- IMPORTED INPUT IS NOT A PHYSICS PIN. Momentum and KSF movements can measure
  key/flick timing without authentic air-rate parameters. Do not borrow server
  cvars to award them a letter grade. KSF v2's buttons-1 proxy lacks ground:
  keep its continuous input span and label contact unknown, not fake jumps.
- THE OLD LIVE PIXEL ARM HAS A CONTROL FAILURE HERE. At 1280x720 Vulkan,
  tools/p621trn.py finds 365 pixels in the retired strip rectangle in BOTH the
  unmodified control and subject. Its numeric jump/history/timing assertions
  pass. Do not repair unrelated HUD pixels or call this a full suite pass.
- P710 IS AN EXPLICITLY WITHHELD PRESENTATION CANDIDATE. A clean origin/main
  build can still include changes whose author forbids deployment. P712's
  delivery snapshot uses the inspected pre-P710 runtime plus only this feature.
  Public source retains both; do not silently ship the candidate from a rebase.

### The trainer's jumps and their history (Patch 621) — 2026-10-10

- A JUMP IS FREE AIR. It was take-off to landing by the ground flag alone, and
  on a surf map that is the whole flight: over the 106 recordings in the
  desktop's data/runs (`fl` bits 1 and 16; a few are arm fixtures) one a run at
  the median, the longest 163 s, 56 of them past the ring's 16 strafes. By the
  rule that shipped it is five a run, median 0.90 s and three strafes, none
  past 14: 1530 jumps kept, 198 stretches under 0.15 s and 84 with no strafe
  not kept. `hud_trainer_split 0` is the old rule.
- THE RAMP FLAG DROPS OUT IN THE MIDDLE OF A RIDE: 185 gaps of one to four ticks
  against 529 of twenty or more. `TRN_MINAIR` (0.15 s) is the whole answer: a
  jump shorter than that is not kept, and the open one is not put on the panel
  until it is older. No lookahead, no bridging; `trainer status` counts what was
  dropped (`short`, `empty`). The census that sized this first used a four-tick
  hold that did not ship; the review caught the numbers quoted from it.
- A STRAFE'S SYNC IS TIMED FROM THE KEY, NOT FROM WHERE THE STRAFE OPENED. The
  ground and the ramp close every strafe, so a key already down at take-off
  opens one there, and the first cut paired that with whatever flick was near:
  the review's emulation gave a number to 123 of the 408 first strafes after a
  ride. `trn_kt` is the clock the key last changed at, read on the ground and
  the ramp too. Held longer than the pairing window: no number. Pressed inside
  it: timed from the press. In the air nothing changes (the two are the same
  tick).
- BLOCK 0 IS THE OPEN JUMP. Every strafe and trace array is nine blocks; the
  sampler indexes block 0 as it always did and a kept jump in slot k is block
  k + 1, so the panel draws any of them through one range (`trv_*`).
- A LANDED JUMP IS DRAWN FROM ITS COPY. Before, its timeline's span was
  `trn_clock - t0` and went on growing on the ground, and `trn_j_v1` followed
  the ground speed, so "+N u/s" bled away as you slowed down to read it.
- THE ARROWS ARE READ BY SCAN ELSEWHERE (replay seek, rewind browse, board tabs,
  the menus), and those panels take the key before a bind runs. That is why
  `bind LEFTARROW "trainer older"` is safe in default.cfg.
- `tools/p621trn.py`. The gallery rig's map has no floor, so its real flags say
  air for ever; `trainer feed 1|2|3` authors ground, ramp and air, and `+right`
  authors each strafe's rate, so every kept jump is known without the subject.
  `--real` feeds nothing: surf_kitsune, a hop from the spawn and a drop onto a
  ramp, and the jumps come back ended by 1 (ground) and 2 (ramp).
- A SOURCE MAP IN THE GALLERY RIG needs hl2's loader beside BOTH exes and the
  server without `-noplugins` (`ui_gallery.EXTRA_PLUGINS`, `SERVER_CFG`). The
  Windows server prints nothing to a pipe: log to a file to see why it left.
- THE ARM'S FED CASES: a key held 400 ms into a jump reads no sync and the swap
  after it -15 ms; a key pressed with its flick 45 ms before the jump reads 0.
  The cut the review read gave the held key -15 and the pressed one +45.
- MUTANTS, once, seven one-line defects (`tmp/mut621.py` in the task root, not
  kept in tools/): all seven fail the fed arm. The first sweep read six, because
  the seventh crashed the GRADER (a KeyError where a jump was missing); a
  mutant that does not run is not a catch, so the grader was fixed and it was
  run again.

### Names: fallback faces, whole owners, a label that slides (Patch 620) — 2026-10-10

- A FONT SLOT IS A LIST OF FACES. `loadfont`'s face argument is split on commas
  (`Font_LoadFont`, gl_font.c) and a glyph comes from the first face that has
  it. A file is looked for in the game and then in the OS font directory
  (CSIDL_FONTS on Windows, /usr/share/fonts on Linux), so the system's fonts
  serve as fallbacks at no size. Before this a missing glyph was the engine's
  hex box, or for Cyrillic a KOI8 transliteration ("PRIWET"), which is what
  "glitched names" was. `FONT_FB_WIN` / `FONT_FB_LINUX` in sh_font.qc.
- AN ENTRY THAT FAILS TO LOAD AND DOES NOT END .ttf OR .otf IS RETRIED AS AN
  IMAGE FONT. So the Linux list is .ttf names only. The two .ttc on the Windows
  list ship with Windows 10 and 11 as far as I know; seen on one machine.
- THE CONSOLE'S FACE IS A CVAR AND AN ARCHIVED ONE (`con_textfont`): a saved
  copy of the old default wins over default.cfg. `Font_Init` moves that exact
  value (and the other platform's list) to this platform's list. Anything else
  is a face the player chose: the first cut moved every value that BEGAN with
  GoogleMed.ttf, which a player's own list does.
- QC STRINGS ARE BYTES HERE (`utf8_enable` 0), so `substring(name, 0, 18)` left
  half a character behind, which drew as a stray red letter. `UI_CharBytes`
  is where the first n characters end; a fourth continuation byte in a row
  counts as a character, so a damaged file cannot outrun four bytes each.
  `UI_NameShow` cuts there and doubles a `^`: six of 845 real names have one.
- THREE READERS TOOK `argv(1)` FOR A RECORDING'S OWNER, its first word; the
  recorder writes the whole netname, and 560 of the 6077 recordings on the
  desktop have a space in it. `UI_OwnerLine` takes the rest of the line and
  trims the tail, because tokenize was what used to drop a CR.
  `cl_online.qc`'s reader (the upload) already took the line and is untouched.
- A QUOTED OWNER STILL READS AS WHAT IS INSIDE THE QUOTES. The grammar says
  "read to end of line", but `ui_gallery.py`, `p603scores.py` and `p603http.py`
  write `owner "Two Words"` and grade the unquoted name, and the first cut of
  this patch drew their quotes on the board: the look gate caught it (11235
  pixels of the Local tab's player column). Three imported runs here have a
  player whose name really is quoted; they lose the quotes as they always did.
- THE NAME ON A LINE WAS THE NEAREST OF 256 SAMPLES, in whatever face was
  current. `LineGraph_WorldLabels` sets the UI face, walks from that sample to
  the nearest POINT of the line, and puts the name there if text can be read
  there: in front of the eye and inside 2..98% by 6..86% of the screen, less
  the text's width. Where it cannot, it bisects back along the line to where
  the line comes onto the screen. `linegraph status` prints `eye`, and for each
  label its point on the line, its screen position and its text.
- THE NEAREST POINT OF A LINE YOU RIDE ALONG IS UNDER THE CAMERA. The first cut
  had no on-screen rule and its arm looked only ACROSS lines, so it passed with
  every label of the usual view off screen; the review modelled it and the arm
  then measured it, at (957, 3681) on a 1920x1080 screen. An arm for a thing
  drawn in the world needs the view the thing is used from.
- `hud_watch_path_far 0` is "never fade"; the label loop read it as "nothing in
  range" and drew no name at all. Fixed here.
- `tools/p620names.py`: four authored runs with one made-up name of each kind.
  Four eyes looking across them, between samples: 16 labels, all on the true
  closest point (0.001 u); with the refinement compiled out they sit up to
  26.2 u off. Three eyes on run 1's line looking along it: all four labels on
  screen, the ridden line's at the middle of the 86% line (960, 928.8), each
  the same distance ahead of the eye at all three (spread 0.02 u). What a glyph
  LOOKS like is not graded: the four shots are for eyes, and the build before
  the patch gives the boxes to compare with.
- REAL NAMES STAY OUT OF FIXTURES AND NOTES. The census that sized this (74 of
  845 on five boards) read the public board API and kept counts by Unicode
  block, not the names.

### Native fixture APIs and falsifiers must actually act — 2026-10-09

- `com_bih.c`'s `struct bihproberec_s` and `BIH_ProbeSave/Restore` are local
  implementation details, NOT `com_bih.h` APIs. Calling them from an included
  `pm_source.c` fixture fails with an unknown storage size/implicit declarations.
  The private bevel PM fixture uses identical translation-unit-local adapters
  in fixture-only and capture builds; no product ABI or mover patch is implied.
- Native retained logs can preserve CRLF. A missing-row fault constructed with
  `text.replace(splitlines_row + '\n', '', 1)` can silently remove NOTHING.
  Verify changed text and the exact decremented row count before calling the
  rejecting reader. Never count a no-op mutation as an ACTED refusal.
- Setup-only native triangle bevel queries are not a PM trajectory. The separate
  `offramp_bevpm` command ACTS steep tag5 copied-winning contacts through actual
  `PM_PlayerMove`, matched removal and bevel-OFF earlier side-plane ghosts,
  independent complete SAT/bias and joint feasibility controls; old twenty-case
  reports stay exact. This bounded evidence does not resolve arbitrary native
  back-slab/triangle support or physical exit/classifier/render/hold acceptance.

- **Native-score density continuation** (published as Patch 605; historical p603 harness IDs):
  never enlarge the exact-size /1 struct in place. The additive /2 snapshot is
  256 widgets (28684 bytes vs /1's7180); the two VM stage/current pairs occupy
  114736 bytes. The scoreboard itself caps24 nine-cell rows + at most6 metadata
  widgets (222), not an entire store. An optional capacity builtin negotiates
  256; old engines/providers stay64 and six-row pages. Keep QC numeric/label
  cache halves non-overlapping (1024 floats / 256 labels) and token/key halves
  at24 each; changing only the native bound corrupts the old mirrors.
  Equal-sized page replacement after vertical scrolling does NOT clamp back to
  its start: the retained before control fails12 checks per index width. Reset
  vertical scroll on first-row identity/count replacement, not every same-row
  checkbox/font/geometry revision. The clipper's final seek stretches RowPosY2
  over omitted rows; never use RowPosY2-RowPosY1 as a single-row mouse metric.
  A tall13px viewport can fit all24; use a genuinely overflowing viewport or
  larger physical font to prove wheel/scrollbar ACT. At different virtual scales
  the inherited shell has different physical extents: compare glyph ink in a
  fixed common region, not raw background or variable crop sizes. Legacy peek
  is already clickable; test its acting cover separately from native passive
  inertness and close that watch before pinning. Following own index31 lands
  /1 on page30; it needs FIVE real Previous clicks to return to0, not the one
  needed by /2 page24. The32-row HTTP case uses the real callback/parser/FindMine
  (authoritative synthetic *phash, never ob_mine), and proves identical/reordered/
  shrunk authority plus cold/warm replay identity. Final GL six-arm gate and69
  read-only reader controls pass; 597 /2 bridge and2872 dense +3750 original
  scoreboard checks per index width pass, native warnings fatal. One-factor
  six-row source freeze leaves all3750 originals acting and fails exactly the
  24-row acceptance. Evidence: C:/FTESurf-worktrees/imgui-dense-20261009T150334Z.
  Backend, cost, endurance and publication gates closed in Patch 605
  (`tools/p603scores.md`, top section); human font/DPI/device acceptance is
  lextest.md's, and the default stays legacy.

- **Native scoreboard, what the finish cost** (Patch 604/605, 2026-10-10):
  - `.gitignore` drops `*.c`/`*.cpp`. Four host fixtures under `tools/fixtures/`
    were on disk, built and green, and absent from the staged commit. After
    adding a fixture, `git status --ignored -- tools/fixtures` and `git add -f`.
  - A host fixture that calls `ImGui::CreateContext()` writes `imgui.ini` into
    the cwd unless `GetIO().IniFilename = nullptr`. The plugin already does this;
    two fixtures did not, and a stray `C:/FTESurf/imgui.ini` was theirs.
  - A D3D11 `screenshot` taken before Patch 604 is upside down. Any older D3D11
    capture, and any reader threshold tuned on one, is flipped. D3D9/D3D8 have
    the same loop (BACKLOG).
  - The Vulkan start crash was `Win32VK_EnumerateDevices` calling through an
    uninitialised local when `vulkan-1.dll` was already loaded: 10 of 40 cold
    starts on the unfixed client, 0 of 40 fixed (`tools/vkenum_coldstart.py`).
    The renderer option list is the cvar `_vid_renderer_opts`.
  - `PlugUI_LabelValid` refuses a control byte or malformed UTF-8 and one refused
    label costs the whole table, so every label goes through
    `Scores_NativePlain`. It has three modes because the QC string builtins do:
    bytes (`utf8_enable 0`, the product default), code points, and code points
    that `chr2str` writes back as raw bytes (`utf8_enable 1` with
    `com_parseutf8 <= 0`). `tools/p603names.py` runs all of them.
  - Hit-test a click against SUI's `_cursor_position`, never a private copy fed
    only while the table paints: motion made while it is not painting is lost
    and the next press acts on the old row (`dense_cursor` in `p603dense.py`;
    the pre-fix source clicks row 8 instead of row 0).
  - A product-source control for a NEW harness step needs the new fixtures on
    the OLD product source: a detached worktree at the pre-fix commit with only
    `tools/p603dense.py` and the two `p603*_runtime.qc` fixtures copied in.
  - PRIVATE BYTES ARE NOT FLAT, SO A FITTED SLOPE READS THE COLLECTOR. QC temp
    strings (one per `bufstr_get`/`sprintf`/`strcat`) are freed by a threshold
    collector whose threshold only grows, so the client saw-tooths by tens to
    hundreds of MiB with a board open. The first soak's "under 4 MiB" bounds
    failed every arm, legacy included, and its leak control sat inside the
    subject's noise: it measured nothing about leaks. Grade the FLOOR (min of
    the last third minus min of the first) against a legacy arm, with enough
    fast cycles that a per-cycle leak outgrows the teeth, and keep a leak arm
    that must separate (`tools/p603soak.py`).
  - What that soak did find: rebuilding ~220 labels every frame made 5.4 MiB/s
    of garbage against legacy's 1.05. `Scores_NativeDraw` now rebuilds only when
    its `scn_sig*` numbers change, an action was polled, or 0.1 s has passed.
    Anything new that must show on the very next frame belongs in the signature.
  - THE COLLECTOR IS IN THE CPU NUMBER TOO. The same held-open table, identical
    pixels and plugin counters, read 822 us of QC UpdateView with the collector
    off (`pr_gc_threaded 2`, diagnostic) and 1159 us with it cycling. Fresh
    sessions with little garbage read low, long-churned ones high, legacy always
    high. Say which regime an arm was in before comparing two medians; a "cost
    regression" of a third of a millisecond with unchanged draw counts is this.
  - Cost runs also just drift on this laptop: closed-phase QC UpdateView stepped
    between cycles inside one arm in two of the first three runs (native +24%,
    legacy -8%). Run the arms in both orders (`p603perf.py --arms absent legacy
    native`) and read the per-cycle samples before believing a median.
  - The harness reaps BACKGROUND shells when the laptop runs short of memory
    (twice in this work: a `-Full -Jobs 8` engine build, then a soak's leak
    arm, whose samples lived in the driver and were lost). A driver that holds
    its measurements in memory until the last arm should write them per sample.

- **Synthetic mouse controls need a single motion writer:** the P603 continuation
  (2026-10-09) intermittently consumed both native button edges without acting a
  watch/missing-replay control. Win32 `INS_Accumulate` feeds real absolute cursor
  coordinates on inactive-mouse frames, racing the fixture's direct CSQC motion.
  The test-only entrypoint wrapper now rejects hardware IE_MOUSEABS while its
  synthetic motion calls the unchanged production input body. Corrected combined
  local/HTTP/lifecycle matrix is zero-fault at both virtual scales. This is a
  synthetic-event proof, explicitly NOT manual device/focus acceptance.
- **Probe the completed draw, not the previous frame:** an HTTP callback can
  publish OBS_READY immediately before a console probe while native painting still
  describes the prior frame. P603 HTTP probes are queued and sampled after the
  actual production CSQC_UpdateView, with a frame barrier before the next action.
  Pending probe labels use strcmp against empty, not string-handle truthiness.
  Keep completion, exact fields, duplicate checks and acting controls mandatory.
- **A later control can mask an earlier wrong identity:** combining P603 lifecycle
  failure-cover watches with the base suite let a later correct Row0 replay satisfy
  the base watch's whole-log identity search. The wrong-identity reader mutant
  caught it. Bind the identity search to that control's own action/probe interval;
  the combined 25 base / 29 HTTP / 26 lifecycle reader controls now pass.
- **Identical board bytes do not retain native click authority:** the actual
  loopback HTTP scoreboard acting control (2026-10-09) replaced rows and advanced
  `ob_epoch`, but a byte-equal model skipped commit and accepted a held old watch
  on release. Track the online replacement epoch separately from display/context
  keys: commit a fresh revision even for identical labels/IDs, without resetting
  the selected page. Corrected two-scale native + legacy/no-plugin HTTP matrix
  is zero-fault; genuine parser FindMine, cold replay/line/watch and queued/failed
  demo POST controls act before held-refresh subjects. See `tools/p603scores.md`
  and `tools/p603http.py`. These historical p603 harness names no longer reserve
  product Patch 603. Loopback/synthetic identity is not public service, external
  downloader, real-device or deployment acceptance.
- **Map-clock state is not online-board readiness:** P603's finite parsed-board
  acting gate stayed on legacy because native drawing tested `ui_mc_state != 2`.
  `MapClock_Read` / `HUD_MapClockText` define that as the map-change clock (2 is
  changing map), not consent/fetch readiness. Use the current board's valid leg
  and `Online_Shows` before native allocation, like the legacy online table.
  Wrong-body leg/style retain legacy explanations without native churn. The
  corrected five-arm local/finish matrix `p603-scores-7sbn9_kl` is zero-fault;
  its synthetic own-index seam is NOT Online_FindMine/HTTP/download acceptance.
  A one-shot finish seek must be consumed only after native publish/draw succeeds,
  or same-frame legacy fallback loses its reveal. See `tools/p603scores.md`.
- **Native table children do not inherit passive input safety from their parent:**
  P603's acting ImGui host found a watch action under a parent NoInputs window:
  the table's scrolling child still processed widgets. Disable the passive
  widget scope as well. Corrected 16/32-bit hosts pass 474 scoreboard assertions
  each, including an acting pinned watch/line before cancellation subjects.
  This is a local-table WIP finding, not roadmap C/device acceptance; checkpoint
  `tools/p603scores.md`. Transient online readiness must precede native allocation,
  or an unready board can open/upload/close a context every frame.
- **Struct-vector member typos can silently crash git-6681 qcc:**
  `_action_elements[i].size_y` returns 0xc0000005 with no compiler output;
  `.size.y` is correct for the vector inside a struct. Single-factor P603
  probes retain the crash while a float-index/dotted-member control compiles.
  Do not blame untouched QC or infer that the index type caused this crash.
  Runtime fixtures must prove watch/line ACTED before stale-click subjects;
  `replay off`, not nonexistent `replay close`, releases the replay input owner.

- **Native .inc scope is load-bearing:** ui_imgui/input.inc is included INSIDE
  FteImGui. Third-party and standard headers must stay at global scope in the
  parent .cpp; otherwise it declares nested FteImGui::ImGui/std and breaks the
  real compiler. P600's first local frozen gate caught a late include cleanup;
  new-location LSP errors were real, not the earlier missing-database cache.
  Restore global includes and repeat host/frozen/runtime gates BEFORE publication.
- **P601 native models are immutable revisioned snapshots, not array offsets:**
  Stage 0..count-1 inside the frontend draw bracket and commit before Draw.
  Malformed/incomplete/duplicate rows poison the transaction; only a complete
  counted copy publishes. Stable widget/row IDs and current revision govern
  actions, not label hashes or list indices. Replacement resets BOTH queued/held
  input and unpolled actions and revokes successful-draw authority until redraw.
  Literal ##/### labels must render as plain text rather than alter ImGui IDs.
  Checkbox updates are QC-owned new revisions, not mutations of copied values.
  Owner generation alone does not prove snapshot freshness. Keep implementation
  includes free of third-party headers inside namespaces (P600 scope failure).
  Synthetic diagnostic events are not real-device/panel acceptance. Contract and
  acting reorder/delete/held/queued/unpolled controls: tools/p601model.md.
- **P600 native input queues must be bounded across frames, not just per Draw:**
  ImGui trickles alternating edges across NewFrame. Resetting a per-frame event
  counter does not bound the residual queue. Limit BOTH host accepted events
  (128 per host frame, reopening cannot bypass) and actual ImGui queued events
  (128 across frames); reset must still act at the limit, clear queued/held
  keys/mouse/text and abandon active widgets/actions. The acting backlog control
  proves residual edges, repeated refill refusal and reset reclamation. Host
  failure closes once; polling is draw-bracket/success/VM/generation gated and
  capped at 16. No native command/bind/scancode interception. Compact keys and
  Unicode scalars are separate; build ALL upstream/adapter units with
  IMGUI_USE_WCHAR32 so supplementary text survives as exact UTF-8. Default atlas
  glyph coverage is NOT non-Latin font acceptance. Static interactive gallery
  owners 103/204 are not a dynamic model protocol: owner generation cannot stand
  in for snapshot/row generations. Synthetic QC events do not establish physical
  device routing, cursor ownership or movement-minus/modifier/real-panel safety.
  Exact scope, controls and remaining gates: tools/p600input.md. Probe namespace
  p599/P599 is retained solely for preregistered rig continuity; concurrent
  verifier P599 remains intact. No production panel/progs/Pi/Build/default change.

- **Native atlas release can happen after recording but before submitting a
  Vulkan frame (2026-10-09 staging):** action polling follows NativeMesh draw;
  replay watch can synchronously close the UI owner. Immediate Vulkan image/view/
  sampler destruction then loses the device although the mesh API copied all CPU
  arrays. Use the existing copied-handle VK_AtFrameEnd fence helper, as upload
  replacement already does; do not retain QC/ImGui pointers or merely wait for
  previously submitted GPU work. Native watch + renderer/plugin/VM/preference
  teardown act with fenced destruction; legacy acts too. An unrelated pre-plugin
  Vulkan cold-start 0xC0000005 remains in BACKLOG.md. See tools/p603scores.md.
- **Native scoreboard physical fonts (2026-10-09 staging):** actual13/16/20/24
  ProggyClean bakes share one bounded immutable atlas; optional sixth metadata
  selects a bake without changing NativeUIModel/1. Default five-widget schema
  stays compatible; the prior scoreboard provider rejects larger metadata and
  gets gesture-latched usable legacy cover. Rebuild style from an immutable base,
  not cumulative ScaleAllSizes; scale table/footer budgets, reserve wrapped text,
  and reset held authority when a selected bake changes. Font/DPI/Unicode quality
  and automatic physical-DPI selection remain separate, unaccepted gates.
  FTE parses literal nan/inf cvar spellings as +/-0, so prove raw strings plus
  observed numeric results rather than claiming QC received IEEE NaN/Inf.
  ImGui preserves scroll on font changes: a drag control aimed at the old left
  edge clicks the track, not the moved thumb. Reset with actual horizontal wheel
  input before a thumb-drag control (no production scroll reset); require the
  scrolled line action to ACT. Source-only variants must copy EVERY pinned vendor
  manifest entry, including LICENSE.txt; an incomplete copy cannot be a negative
  mechanism witness. Font source-only selector freeze fails actual-bake checks
  while metadata/input controls stay green at both index widths. Font reader
  probes/statuses/watch identities are interval-bound; PNG ink and virtual-scale
  equality are measured separately from metadata. See tools/p603scores.md and
  C:/FTESurf-worktrees/imgui-font-20261009T131505Z/CHECKPOINT.md.
- **Cost/row-density controls must compare real displayed work:** NativeUIModel/1
  has 64 widgets; six 9-cell rows plus header/standing/paging fit, ~20 rows do not.
  A 24-row store showing native six vs legacy twenty is not a speed comparison.
  Use six total rows, uninstrumented QC, spaced 100-frame CPU dumps, open/closed
  native counters and table-pixel witnesses; reject missing/stale dumps instead
  of lending a later sample. r_speeds total refresh includes its overlay and
  pacing/present; process private bytes include screenshot/allocator transients.
- **NoDeploy compiler success and wrapper success remain separate (2026-10-09):**
  engine/client/server/plugins and all three QC programs can build, then the final
  build.ps1 summary Get-Item still reads absent installed qwprogs.dat in a staging
  tree and errors. Keep that wrapper failure, compiler output and artifact hashes;
  do not deploy or claim exit zero. From Bash, a literal Windows .ps1 wrapper
  avoids -Command path conversion; if the outer launch excludes MSYS conversion,
  clear that exclusion inside pwsh before make passes POSIX paths to native GCC.
- **P598 minimal ImGui is a diagnostic prerequisite, not migrated UI:** optional
  pinned 1.91.9b plugin exports only NativeUI/1 service + shutdown/status; separate
  MQC/CSQC contexts/atlases, no implicit ini/log files, no Tick/Menu/Sbar drawing.
  Actual ImGui text/rounded control/1000-row clipped table/tooltip and overlap
  markers pass 23 screenshots at two virtual scales, physically identical.
  Real-source adapter/host controls pass 107 assertions per 16/32-bit arm including
  >64K rollover, whole-data rejection and bounded splitting. Fixed scratch buffers
  expand triangles; this is NOT cost acceptance. Submit failure returns false but
  cannot undo previous successful batches; fallback must redraw covering content.
  No input/widget/model transport, actual-panel/default/Build/release change.
  Pinned vendor needs `vendor/* -text` to preserve SHA256 bytes in autocrlf clones;
  unmodified vendor uses -O1 for GCC 16 range diagnostics, adapter -O2, both -Werror.
  C++/pthread runtime DLL imports are eliminated by static plugin linkage. Exact
  evidence and final frozen/delivery gates: tools/p598imgui.md. Provisional native
  P595 collided with concurrent surfd P595-597; preserve those entries and the
  already-published historical patch-595 tag. Canonical native source/tag is P598;
  test command/cvar/log prefixes remain p595 for retained-rig continuity.
  Canonical frozen d5e828f03 / patch-598 embeds git-7125-patch-598-0-gd5e828f03;
  74 compiler warning occurrences / 49 distinct fingerprints match P594, zero
  new, QC zero warnings. Guarded dual native-only delivery and repeated actual
  installed-path galleries (46 shots) pass at 2026-10-08T14:20:11Z; four target
  hashes/rollback and all 38 protected progs/config/data/server/DLL groups match.
  First whole-data gate was HOLD because the scheduled public-map sweep ACTED
  at 14:07 UTC; task/writer witness retained. Re-register a fresh whole-data
  baseline and repeat; do NOT stop the owner's task, restore data or exclude
  changed files to pretend the original gate passed. No progs/Pi/server swap.
- **`build.ps1 -NoDeploy` previously did not exist:** PowerShell silently accepted
  the unknown switch in `$args`; QC wrote into the integration install and native
  deployment still copied to the second install. P598 now declares the switch,
  adds CmdletBinding unknown-argument refusal and rejects NoDeploy+Pi/Run. It
  compiles through owned same-src-directory manifests (only output line changed)
  into fresh rig directories, removes its temporary manifests and blocks native
  deployment. This fteqcc's -o switches to new-style parsing; absolute input paths
  in old-style manifests also failed. Both are retained failed controls, not a
  workaround to ship dirty source. The real -Engine -NoDeploy control proves 65
  install/rollback/progs/cfg byte/path witnesses unchanged and three zero-warning
  QC builds. Earlier ignored-switch native copies were hash-guard restored from
  retained rollback files; new optional DLLs were parked before proceeding.
  Frozen worktree versioning also needs actual SVN_VERSION/SVNREVISION make
  inputs (+29 count offset): automatic .git-directory checks miss .git files,
  and FTEBUILDNO/FTEBUILDVERSION are not consumed. Verify embedded binary bytes,
  not just a wrapper's printed stamp. The unstamped provisional build was held.

- **P594 inherited native clipping: validate AFTER physical conversion.** Final
  P593 review found inherited clipping was intersected after P589's validation.
  NaN/Inf and finite virtual-to-physical overflow must fail before callback/flush,
  release the opened owner once and return explicit QC fallback. New acting host
  controls fail 12 assertions on P593; corrected actual-core controls pass 170
  assertions plus 24 grader controls. They use FTE-equivalent NaN/Inf bit semantics,
  not libc finite assumptions. This is host robustness, not malformed-driver
  injection or a native-module sandbox. `tools/p594clip.md` records the falsifier;
  published P593 tag remains immutable. Published source/tag `bed572f50` /
  `patch-594`; frozen game source/test `9e820a7`, integration `8206480` only adds
  peer off-ramp tooling/docs (not shipped). Clean full build stamped
  `git-7118-patch-594-0-gbed572f50`: same 74 baseline warning fingerprints, zero new;
  QC zero warnings. Frozen galleries `p590-bridge-u16xorn0` / `p589-mesh-n418owc1`
  pass. Actual installed Windows executable paths ACT in `p590-bridge-qksc2vm_` /
  `-ek419z65`, zero failed, after guarded native-only swaps retaining P593 rollback;
  destination hashes and progs/config/data/server/DLL preservation verified
  2026-10-08T11:34:11Z. No second Pi swap; existing P593 payloads are byte-identical.
  The no-flush assertions concern the rejected Draw path; resource cleanup may
  independently flush for P589 texture lifetime. No fixture DLL, QC/progs, panel,
  input/model ABI, preference, release or Build-number change in this fix.

- **P593 native bridge prerequisite: explicit QC draw sites, not plugin overlay
  hooks.** `NativeUI/1` copies an exact service table; optional named MQC/CSQC
  status/open/draw/close builtins provide one owner per VM, non-reused float-exact
  handles, per-host-frame dispatch, physical/virtual dimensions and inherited
  physical clip. QC-before/native/QC-after flushing restores caller colour, flags
  and backend scissor. Explicit close, failed open/draw, VM teardown, plugin unload
  and renderer shutdown release owners; renderer cleanup precedes P589 textures.
  Draw outside the frontend callback, stale/fractional/foreign/duplicate handles,
  exhausted handle space and render targets fail closed to caller QC fallback.
  Open/Close allocate/release only; trusted callbacks may not retain frame pointers
  or reenter engine services. This is not a hostile native-module sandbox.
  `src/shared/sh_nativeui.qc` supplies nested optional-builtin guards in both progs;
  no real panel, input chain, preference, default or Build-number change.
  Final candidate `p590-bridge-z7lgogbi` passes five acting arms and 52 screenshots:
  P589 legacy baseline, absent service, two MQC/simple-CSQC virtual scales and full
  CSQC UpdateView. Actual-core host controls: 149 assertions; grader controls: 24.
  P589 regression `p589-mesh-4jpv7z06` passes; its 33 grader controls also pass.
  Isolated predecessor/subject full builds have identical 74 compiler warning
  message/count fingerprints, zero new; QC compiles are zero-warning. Initial
  path/SDK/API/fixture failures remain recorded in `tools/p590bridge.md`; after a
  renderer reset, reacquire the SAME owner before testing alternate-owner rejection
  or the fixture itself creates another valid owner. P590 fixture names are kept
  after forward-renumbering to the one product patch 593 (peers published 590-592).
  Published engine implementation/tag: `25ad9d56e` / `patch-593`; main's
  `452c8814a` merge adds only the peer P590-592 delivery record. Game feature
  `d3b7174` is published. Clean frozen engine/tag and game feature rebuild stamped
  `git-7115-patch-593-0-g25ad9d56e`, with the same 74 baseline warning fingerprints;
  frozen `p590-bridge-3nyqfybl` and `p589-mesh-hei0vtp6` pass. Guarded dual Windows
  native+CSQC+MQC delivery kept rollback; unchanged SSQC was not replaced. Actual
  installed executable paths ACT in `p590-bridge-hmrva9oz` / `-gvq91c1r`, zero failed,
  at 2026-10-08T11:00:43Z; configs/data/server/DLL digests remain unchanged. Pi progs
  swap from exact game feature kept `.prev`, zero players, 12 fresh lobbies; all
  12 advertise the exact new cached CSQC CRC/size, protected engine/config and
  rollback hashes match, health 12, verified 2026-10-08T10:54:38Z. No Pi engine,
  Windows server/DLL, config, reader, evidence, release or Build change. Two private
  finish-only Pi probes failed on quoting and decimal-vs-hex size parsing; source
  confirms *csprogssize is hex. No recopy/restart was used to finish those gates.
  Next: minimal ImGui command-list service; widget/model/input transport, real
  panels, non-GL/device-input acceptance and CPU/GPU budgets remain separate gates.

- **P589 native indexed-2D prerequisite (2026-10-08):** separate exact-size
  `2DMesh/1`, immutable raw RGBA8 and non-repeating 64-bit plugin-owned tokens.
  Cleanup on release/plugin close and BEFORE renderer shader/image teardown.
  Whole-batch validation precedes real bounded mesh submission; CPU physical
  triangle clipping interpolates UV/color without touching backend-dependent
  `BE_Scissor`, caller color or blend flags. Linear/clamped straight-alpha atlas,
  both windings. Never treat this as a hostile-pointer/thread sandbox: trusted
  main-thread plugins call Submit only in a 2D drawing callback, not Tick.
  Per-Submit limits are 16,384 vertices, 65,535 consumed indices, 128 commands;
  32 textures/32 MiB per plugin and 256/128 MiB globally. No per-frame heap copy.
  Engine `69b2c1bdb`, tag `patch-589`, clean full stamp
  `git-7109-patch-589-0-g69b2c1bdb`; client SHA256 starts `7d125dedb98d`.
  C/header tree equals initially verified `516a6a1f5`; only patch notes/peer
  documentation changed before the final published tagged full rebuild.
  Full client/server/four-plugin build has the same 74 compiler warning messages
  and counts as P581, zero new. Engine plugin/renderer TUs have only baseline
  tidy warnings; standalone fixture/header diagnostics lack engine context.
  `tools/p589mesh.py`/`.md`: `p589-mesh-xro1c2lq` passes acting P581/subject1/
  subject2/disabled/no-renderer arms, offsets/alpha/winding/clips/chunks/order,
  invalid-second-command no-partial draw, 25 invalid/seven lifetime/61 count
  budget assertions, foreign destroy+submit rejection, automatic 32-texture
  cleanup, restart and main-plugin reload stale rejection. Physical screenshots
  inspected; scale1/2/repeat/restart/reload galleries are exactly identical.
  33 grader tests pass. Older atlas, font scales1/2 (exact P581 pixel equality)
  and 28 dedicated/editor controls pass. Initial snprintf macro/link failure,
  triangle-edge and bilinear-transition grader sample mistakes retained; corrected
  positions rather than relaxing tolerance. Disabled console animation is not a
  mesh regression; require absent sentinel/gallery pixels, not whole-screen
  equality. Forward-renumbered after peers published P586 then P587/588;
  preserve their full text and history; no published tag was moved.
  No QC/ImGui/service/input bridge yet. Next: VM-local explicit MQC/CSQC draw-site
  dispatch, with actual QC-before/native/QC-after and inherited-clip controls.
  Native MenuEvent here is only a fixture surface, not a substitute UI bridge.
  Non-GL parity, byte/global-budget stress, device and CPU/GPU cost remain open.
  Clean game-ref proof: `C:/FTESurf-mesh-proof` at game
  `2cad73344ccab9e4addeb0e638f1c98bf620afce`, engine/tag as above. Frozen
  native artifact plus clean QC compile (zero warnings), five-arm mesh gallery
  (`p589-mesh-bcynr8m7`) and 33 grader tests pass; proof source remains clean.
  Guarded native-only dual swap verified 2026-10-08T09:09:48Z: client plus
  matching hl2/cod/box3d/ode DLLs in both Windows installs, no server-binary swap.
  All ten destination hashes match the frozen candidate; `.prev` and
  `rig/deploy-p589-20261008T090946Z` retain predecessor/older-prev bytes.
  BOTH installed-client COPIES repeat all mesh arms (`p589-mesh-_9isse8e`,
  `p589-mesh-20f_971_`), zero failed; post-test hashes and protected cfg/progs/
  reader/server bytes still match. No owner process stopped, settings edited,
  peer dirty source deployed, progs/config/reader/asset/server/Pi/release swap or
  Build bump. This is not a claim that the owner/fleet rendered an ImGui panel.
  Next workstream starts from the published refs: implement the explicit
  VM-owned QC dispatch/service bridge, preregister mixed QC/native clipping and
  fallback/action controls, then build the minimal ImGui command-list service.
  Budget measurement and real-panel migration remain gated after that gallery.

- **P570 physical font contract:** `Font_LoadFont` converts virtual ladder
  heights to pixels; P566's QC physical conversion alone did NOT establish a
  native bake. Engine `loadfont ... "<ladder> pixels=1"` opts into physical
  rungs and reload preserves them. `Font_NativeSlot` is lazy/separate: retain
  `Font_Set`/`ui_font_cur` as the legacy face for `Font_Px`, use the physical
  mirror only during draw, then restore `drawfont`. Do not shrink the legacy
  virtual ladders (their larger scaled menu/HUD bakes are still required).
  Engine selection uses actual physical bake heights, each axis uses its own
  ratio, and near-integer/unit float round-trips are repaired. Gallery at
  1280x720 and console scales 1/1.5/2 is pixel-identical; pre-patch 1 versus 2
  changes 30,764 pixels. Same-process/menu/renderer repeats must agree and the
  unbaked +0.75px arm must visibly act on every crop. `tools/font_quality.md`
  documents hashes/commands/limits. This does not rank Apple-like aesthetics,
  measure recurring CPU/GPU cost or implement ImGui.
  Fleet verification 2026-10-08T04:19:39Z and delivery checkpoint: source
  `ae80bca` (published through
  merge `efcfe0d` with peer tooling/docs only), engine `60dfdc102`/`patch-570`.
  Clean proof `C:/FTESurf-font-proof` builds all QC with zero warnings; native
  client stamp is `git-7076-patch-570-0-g60dfdc102`. Pi qwprogs is unchanged,
  new csprogs SHA starts `80f2a137`; remote hashes match and all 12 units are
  active. A live Pi client reaches connection/editor actions; its whole-panel
  A/A pixel floor fails on the live scene (classic 11902, modern 1528), while
  the isolated static-map arms pass. Do not relax that reader or report a live
  pixel-noise pass. Windows deployment stopped BEFORE any swap because the
  owner's running `C:/FTESurf/ftesurf64.exe` is locked; do not terminate it.
  Dual Windows deployment completed at 2026-10-08T05:28:54Z after the owner
  closed the game; no process was stopped. Guarded script
  `C:/FTESurf-font-proof/rig/deploy-p570.ps1` verified both installs against the
  clean proof's five artifact hashes and supplied matching font/mask assets.
  `.prev` plus `rig/deploy-p570-20261008T052851Z` retain rollback copies and
  per-file provenance. Both installed-client copies pass the gallery/reload/
  unbaked controls (primary scale 1, second scale 2); matched images differ by
  zero pixels. Each actual dedicated/editor arm passes all 28 checks in its
  disposable rig (`font-quality-ho5psde5`, `font-quality-36f16w1n`,
  `ui-modern-20261008-162943`, `ui-modern-20261008-163011`). The second
  executable is `C:/FTEQuake/fteqw64.exe`, not ftesurf64.exe. The deployment
  JSON's `rows.name` is the logical source artifact name; map its secondary
  `ftesurf64.exe` row to `fteqw64.exe` for a later destination recheck. All 18
  artifact/asset hashes still match after testing. No primary peer
  sources/configs were changed. Next: Stage B's minimal ImGui bridge, with
  cost/aesthetic/device acceptance still separate.
- **P581 atlas prerequisite (2026-10-08):** native engine `710087cb7` /
  `patch-581` repairs the returned memory-image handle, guards encoded input
  before decoding and validates positive/in-range/live shader IDs. Old IDs
  are reference-counted shader-table slots, NOT generation-safe capabilities;
  reacquire after UpdateVideo and balance every successful reference. Initial
  number 577 collided with concurrently published reader P577-580; corrected
  forward without rewriting published `51dfe46ef`/`patch-577` history. Primary
  `tools/p581atlas_claim.md` advertised only 581 until publication completed.
  Harness names/markers retain P577 for their pre-registered reproduction.
  `tools/p577atlas.py --engine <subject> --control <old-client>` compiles an
  owned C fixture with `-Werror`; control's data handle is 0 while memory/disk
  lookup pixels ACT, subject's returned handle matches those crops exactly.
  Replacement, renderer restart, temporary release/reload (visible pixels),
  seven invalid inputs and four invalid-ID query/draw/quad/unload arms pass;
  disabled-plugin arm rejects commands/no sentinel. Startup root autoload
  proves no-renderer rejection before graphics; engine logging is not ready,
  so the fixture flushes begin/end markers to the per-child absolute
  `P577_NONE_MARKER` file. It subsequently opens GL and exits normally.
  Initial `-dedicated` client reached rejection then faulted during untouched
  shutdown; retained, NOT accepted or repaired. Do not weaken exit checks.
  `test_p577atlas_unit.py`: 30 mutation controls. Client/server compiler arms
  retain exactly 2/5 baseline warnings, zero new. Standalone fixture/header
  clangd lacks its engine context; engine plugin TU has only baseline tidy
  warnings. Actual GCC build is the gate, not that standalone diagnostic.
  Build with MSYS2 ucrt64/usr bins explicitly on PATH: otherwise cc detection
  can silently choose empty ARCHLIBS/NO_FREETYPE. Compute native SVN_VERSION
  with the clean Windows-Git checkout BEFORE prepending MSYS paths (different
  autocrlf context can give a false dirty stamp), and use an annotated tag.
  Final clean full build is `git-7096-patch-581-0-g710087cb7`; `clangdb.py`
  regenerated the database. Atlas, fonts at scales 1/2, exact approved-P570
  font pixel equality and 28 dedicated/editor controls pass. Clean proof
  `C:/FTESurf-atlas-proof` at game `e172392` repeats zero-warning QC, atlas and
  all 28 editor checks; frozen native SHA256 starts `f0fe4319ac3b`. Guarded
  native-only dual swap verified at 2026-10-08T07:51:06Z, keeping `.prev` plus
  `rig/deploy-p581-20261008T075105Z`. Both installed-client COPIES repeat all
  atlas arms (`p577-atlas-bcioqy63`, `p577-atlas-ifyudd87`); post-test hashes and
  protected cfg/progs/reader bytes match. No owner process stop, progs/config/
  reader/asset/server/Pi/release swap. Indexed-2D/QC/ImGui work is NEXT, not
  accepted by this delivery.
- **Stage B existing-ABI preflight (2026-10-08):** no ImGui implementation
  yet. Disposable native fixture against engine `3abccb525` (docs-only delta
  from deployed `60dfdc102`) accepts exact 2D/Input/Cmd sizes, rejects shortened
  2D, draws a magenta MenuEvent sentinel and disk 2x2 RGBA control, including
  half-alpha blue/white, before/after `vid_restart`. Disabled-plugin arm
  rejects commands/no sentinel; subject reaches 100 then 310 rendered frames.
  Valid memory TGA returns 0 and draws nothing because
  `cl_plugin.inc:Plug_Draw_LoadImage` explicitly sets NULL for type 3; this
  historical defect is now repaired by P581 above. Same-name `LoadImage` after `LoadImageData` retrieves the
  uploaded texture, exactly matching the disk crop before/after restart.
  This proves upload acted, not the one-call returned-handle contract. Do not
  call the prerequisite probe a passed native atlas/ImGui gallery.
  Evidence `C:/FTESurf-font-proof/rig/ui-plugin-preflight`: `preflight.c`,
  `run.py`, `PREDICTIONS.md`, final `same-name-memory-control/results.json`.
  `python .../run.py` compiles with GCC `-Wall -Wextra -Werror` and asserts the
  acting controls plus this known failure; it uses one-shot output dirs.
  Initial startup `-width/-height` did not set capture dimensions, and
  `vid_width/vid_height` alone still maximized to 1920x1111. The corrected arm
  also sets `vid_winmaximize 0` early and asserts 640x480 physical/virtual
  dimensions. Do not sample virtual coordinates as physical. A shader-name
  lookup workaround produced no memory texture; not accepted. Existing 2D
  exposes quads only; header handle persistence is not established, and the
  backend `srect_t` units differ (merged.h Patch 208). Next is the atlas path,
  then a separate versioned indexed-2D ABI plus explicit QC submission and
  clipped mixed-native/QC controls, not a pretend wrapper over Sbar callbacks.
- **P566 SUI/font tests:** the HUD editor was the first panel in this style
  (opt-in behind `ui_style 1` until Patch 607 removed the switch);
  `shared/sh_ui.qc` is ordered after fonts/SUI in both VMs. Native font means
  the final PHYSICAL height is a baked size: convert first, snap with the
  selected face's ladder, then convert back on both axes. Pixel-align origins.
  Layout/scale screenshots passing is not font-quality acceptance. The new
  tooltip must measure with its cached drawfont/glyph size; a console probe's
  default font is not the font that drew it. Wrap only on changed text/face/
  size/width, not every frame, and do not reset a valid hover merely because
  a screenshot/slow frame took >250ms. IE_FOCUS mouse and keyboard arguments
  are independent, with -1 meaning unchanged; retain both and reset tooltips
  before any handler can consume focus. `getkeydest` exists in MQC, not this
  CSQC defs/table: trying it in shared CSQC made git-6681 qcc crash silently;
  a reduced compile isolated that reference. DP registercvar archive is 32,
  not 1; MENU does not define the CSQC `CVAR_ARCHIVE` convenience macro.
  Fresh menu rigs also need the offline-consent/chosen-name prerequisites
  and the p498 fixture's fixed geometry, not the owner's archived state.
  `HUD_EditClose` explicitly saves when dirty: automatic-save guards alone
  are insufficient. The UI driver creates a marked disposable basedir, uses
  `map ui_modern.map` (omitting the extension searches for a .bsp), seeds its
  exact csprogs and terminates only its own handles. On published `21cfeea`,
  build.ps1 has no NoDeploy option and QC-only builds stay in the worktree;
  inspect the actual script before relying on a different shared version.


### Source water and visual controls (Patch 538)

- `CVAR_NOSET` does not defeat an early command-line `+set`: cvar registration
  preserves an already created value. The server's `pm_sourceversion` therefore
  derives from `PMSRC_VERSION` and is force-set immediately after registration.
  A startup override to 2 must still advertise and record 3; later console writes
  must be refused. Do not let prediction follow a different mover from the pin.
- Reject non-finite ramp pins before version-3 dispatch. `IS_NAN` is an exponent
  bit test (also rejects infinity); floating-point unordered tests can be folded
  under fast-math. Both the header and a valid two-integer `pm` restatement need
  a native REFUSE control. A malformed restatement which the parser ignores is
  not that control.
- `CL_Fog_f` blends for one second. Wait at least 1.5 seconds after fog changes
  before comparing settled screenshots. A 750ms restore screenshot is not an
  identity test. Underwater material fog must act with `r_waterwarp 0`; the warp
  flag is not an immersion test. `fg_new` includes CoD/Doom: use `MDLF_SOURCEBSP`
  when disabling Quake's orange plain-water blend for VBSP only.
- Swimming is mover version 3; v1/v2 pins and old-server prediction retain their
  original water drift. A dry recording repinned to 3 is only a dry regression
  control. A fresh real-recorder wet+jump run reproduced 136/136 arrivals and
  native PASS (144 rows /154 ticks) on Windows and aarch64; the old native engine
  REFUSEd that version. Cross-architecture dry gates also matched all seven
  `pm_dettest` rows on bhop_eazy and surf_ace.
- Automatic visual knobs do not exec sticky map overrides: hue -999 and fog
  distance/density -1 choose map defaults; explicit settings remain the user's.
  Source hue runs after LUTs, scene-only. Neutral/no-LUT maps bypass the pass.
  `surf_sidistic` selects 150 degrees, distance 2, max-opacity multiplier .5.
  There is no scripted water-lip jump and no submerged portal/stair/carrier
  collision runtime claim. Portal maps reuse the prior portal-aware slider.


- **An isolated renderer rig must also isolate the executable's plugin directory.**
  `-basedir <rig>` plus an original-install executable can still load that
  executable's old HL2 DLL. For a plugin-only falsifier, copy the unchanged exe
  and the subject DLL into the rig, launch that exe explicitly, record hashes,
  and prove the new behavior/cvar acted. When adapting an old harness, assert
  every source replacement matched: a silently missed exe-path replacement
  produced a clean run of the OLD floor in the 508 investigation. That failed
  arm was discarded, not counted as verification. Do not overwrite owner
  installs merely to make an isolated test load the intended plugin.

- **`volume 0` DOES NOT MUTE MUSIC.** Music plays at `musicvolume * mastervolume`
  (`snd_dma.c:3512`) and `volume` only scales the rest, so a harness that
  "mutes" with `volume 0` plays its music out loud -- Patch 467's did, with the
  laptop's owner in the room. And every volume cvar is applied BEFORE the
  snd_vis tap, so muting music also blinds the analysis. Use a whisper instead:
  `set musicvolume 0.02` (the analysis is level-normalised), and test WAVs at
  -40 dBFS (`tools/p467visprobe.py`).
- **`+lookup` DOES NOTHING IN A MINIMIZED HARNESS.** To aim the camera, use the
  mod's `cmd setpos <x> <y> <z> <pitch> <yaw> <roll>` (taints the run -- fine for
  pixels) with coordinates from `cmd viewpos`; `cfg/test/p467pos.cfg` prints a
  map's spawn that way.
- **LAUNCHING `ftesurf64.exe` DIRECTLY SKIPS `ftesurf.bat`'S fs_addons SEEDING.**
  On a fresh clone that means no Steam mounts at all -- "FTESurf: 0 maps" -- and
  a harness that loads a map finds nothing. Copy `fs_addons.default.txt` to
  `fs_addons.txt` once, as the .bat does.
- **A PLAYER'S RUNNING GAME LOCKS `ftesurf64.exe`.** A deploy fails with "being
  used by another process" while the owner has the game open. Never kill it:
  wait on that PID (`Wait-Process -Id <pid>`) and copy after it exits.
- **A 2256x1380 PNG SCREENSHOT BLOCKS THE MAIN THREAD ~2 s.** A timed harness then
  shoots frames drawn before its own last step took effect -- Patch 467's first
  tour looked like a frozen sim for exactly that reason. `scr_sshot_type jpg`
  writes in milliseconds.
- **FTEQCC'S PRECEDENCE IS NOT C'S FOR `||` AGAINST ARITHMETIC.**
  `scene = div <= 1 || t - floor(t / div) * div == 0;` was never true, so the
  monolith drew nothing and measured 142 fps. Parenthesise, or spell it out with
  an `if`, and never trust a frame rate you have not looked at a frame of.
  MEASURED 2026-10-03 (`fteqcc64 -Fwasm` on a probe): it is the ASSIGNMENT --
  `r = a || b;` compiles to `STORE_F a, r; OR_F a, b` (`(r = a) || b`), and
  `r = (a || b);` is one `OR_F`. Conditions parse as in C: `a == b || c != d`,
  `a && b - c < d`. And neither operator short-circuits (both sides evaluated).
  Patch 477's `busy = !rw_on || rw_ack || rw_cd;` was this; a reviewer found it.
- **ON THE N100, SHADER SIZE COSTS AS MUCH AS SHADER WORK.** The monolith with
  its object groups skipped by a runtime switch ran 40 fps; a build with those
  groups (and its material code) compiled out ran 72 -- most likely register
  pressure on every pixel. So measure a feature by compiling it out, not by
  branching round it; loop from a `ZERO` the compiler cannot see so map() is
  inlined once per loop (unrolled, the first compile took 12 s); and keep one
  call site for march and shade (the water reflection is a second pass of the
  same loop, not a second call).
- **A CELL-BOUNDARY CLAMP OF `edge + 0.1` MAKES RAYS CRAWL.** Domain-repeated
  objects clamp the step at the cell edge because a neighbour may be nearer -- but
  with a tiny margin, every ray grazing a cell boundary takes 0.1 m steps. Use
  the real clearance (object to cell edge) as the margin: the monolith's far
  walls were at the 90-step cap in a step-count heat map and well under it after,
  and the lattice's PLAY station went from 29 to 41 fps.
- **THE SCENE TARGET'S ALPHA IS NOT ONLY THE PANEL MASK.** Since the streaks
  hide behind models it is 2 + a distance on a model's hit; `abs(a)` read as a
  mask is 1 over every one of them. Every reader goes through `milk_panelmask()`
  (present, comp, shafts); a world that writes plain `mask * (1 - fog)` (the
  monolith) still reads right, it just hides no streaks.
- **A 2D POLYGON IS BACK-FACE CULLED.** `R_BeginPolygon(..., TRUE)` with a
  script material culls by winding, and a ribbon built along its direction of
  travel winds either way: every waveform line and half the comets were simply
  not drawn. `cull none` on the material (`milk_wave` in `scripts/milk.shader`).
- **A HEADER SHARED BY BOTH STAGES CANNOT USE `dFdx` OR `gl_FragCoord` BARE.**
  `milk_common.h` is compiled into the vertex shader too; the speed options'
  helpers sit under `#ifdef FRAGMENT_SHADER`, or every world's variant fails with
  "'dFdx' : function is not known" in a VERTEX shader.
- **DO NOT WRAP `build.ps1` IN COREUTILS `timeout`.** Under `timeout 280 pwsh
  ...` fteqcc failed on `sv_progs.src` with no output at all, three times; the
  same build bare passed.
- **`clampmap` DOES NOT OPEN A TEXTURE UNIT IN A PROGRAM PASS.** Only `map`
  goes through `Shaderpass_DefineMap`, which starts the next merged pass; a
  `clampmap` line overwrites the current one. The vessel's films as `clampmap`s
  replaced `mm_ui1` at unit 3 and left units 4-5 empty (black) -- with no warning,
  and the log still said `passes 6`. Use `map $clamp:<path>`.
- **NEVER PUT AUDIO IN A RATE THAT MULTIPLIES TIME.** The leaf cells' phase was
  `T * speed` with the mids in `speed`, so a 0.5 swing in the mids a minute in
  moved every chloroplast ~12 radians in one tick -- the "freakout". Audio may
  scale an amplitude or a brightness; a rate needs a phase accumulated in QC.
- **A MARCH THAT RUNS OUT OF STEPS IS NOT SKY.** The monolith's corridor drew
  its step-exhausted rays in the void's haze colour: a grey wedge at the far end
  of a tunnel bored through rock. `march()` now returns minus the distance
  reached, and a miss inside the corridor ends in its own dark.
- **QC `&&` DOES NOT SHORT-CIRCUIT, AND A MISSING `#0:` BUILTIN ABORTS THE WHOLE
  VM.** Patch 467's `if (milk_hasvis && snd_getvis(...))` called `snd_getvis` on an
  engine that lacked it: "Builtin 0:snd_getvis not implemented", menu.dat shut
  down, and the engine dropped to the stock Quake menu. Gate an optional builtin
  with `checkbuiltin` and NESTED ifs (`if (a) if (b(...))`), never `&&`.
- **`git add <paths> && git commit` COMMITS THE WHOLE INDEX, including what the
  peer staged before you started.** Staging your files does not unstage theirs.
  On 2026-09-28 commit 7a3d194, titled as a zone-mirror change, carried the
  peer's AGENTS.md, BACKLOG.md, lextest.md, m_main.qc and a two-file rename --
  6 of its 8 files were theirs. `git commit -- <paths>` is mandatory in this
  tree, and read `--stat` on the result before pushing. (The separate, harder
  case is a peer's edit INSIDE a file you are also editing, which a pathspec
  cannot catch; that one needs `git diff --cached`.)
- **`./src/build.ps1` from the Bash tool silently does nothing** -- no output,
  exit 0, no build. A measurement taken between two runs used a build that had
  never happened, reported the previous number, and read as "the change had no
  effect". Build through the PowerShell tool, and check `menu.dat`'s mtime if
  the result surprises you.
- **`build.ps1` writes its warnings with `Write-Host`, so `2>&1` into a
  variable does not capture them.** A filter counting lines matching /warning/
  over the captured output returned 0 while the build printed 2 real Q302s.
  This is CLAUDE.md's filter trap in a new costume: the tool's own
  `Done. N warnings` line is the count to trust, and it was correct both times.
- **The staleness gate is doing double duty as a cross-session guard.**
  `release.ps1` gate 1 scopes its dirty check to the SHIP SET, and `.qc` files
  are not in it -- only the `.dat` they build. So a peer's uncommitted
  `m_main.qc` does not trip gate 1; what stops you shipping it is gate 2
  noticing the source is newer than the progs. Do not rely on gate 1 to tell
  you whose work you are about to publish; read `git status` yourself.
- A DEPLOY'S PROVENANCE CHECK GOES STALE THE MOMENT YOU FINISH IT, because the
  other session commits into the same working tree and `-Pi` ships the TREE.
  On 2026-09-28 I ran `git log <deployed>..HEAD`, cleared all four commits, built
  and deployed -- and the peer landed a commit in the two minutes in between, so
  the progs that went to twelve public lobbies were built from a HEAD I had never
  inspected. It was harmless (BACKLOG.md, a test cfg and a .py -- no QC), and that
  was luck, not method. Re-read `git log` and `git status` AFTER the build and
  BEFORE the swap, or build from a `git worktree add <tmp> <sha>` at the exact
  commit you checked so the artifact cannot move under you. The deploy prints the
  progs hashes: they are only meaningful against a commit you can name.
  **AND IT IS NOT ONLY THE DEPLOY -- THE SAME RACE RUNS THROUGH `git push`,**
  which is how this bullet got written too narrowly and then bit again the same
  day. Later on 2026-09-28 the peer asked me to push a commit of theirs, I read
  `git show --stat` on it to confirm it held no client code, and then pushed a
  chain that by then also contained their phase C client commit -- landed at
  15:43:25, inside the same command as my own `git commit`. Seven files of QC and
  cfg went public without either of us choosing the moment. Verifying a payload
  and then acting on a LATER HEAD is one mistake with two exits; `git push
  <sha>:main` publishes exactly what you inspected, and a bare `HEAD` publishes
  whatever arrived while you were reading. On a PUBLIC repo that is not
  rollbackable by any means you are allowed to use -- never force-push -- so the
  inspect-then-act gap has to close before the push, not after.
- A CLIENT NEVER SEES AN AUTOBUNNY HOP TOUCH DOWN, so anything keyed on an
  `onground` EDGE silently does not fire during a bhop chain.
  `PMSrc_CheckJumpButton` clears onground on the jump tick itself
  (`pm_source.c`, see the comment at :2991), and the client only ever observes
  end-of-tick state, so a clean `pm_autobunny` chain has no frame with onground
  set at all. `hud_seq_hopbreak` was written to split the segment column per hop
  on exactly that edge and had never once done so; the column merged whole chains
  and the energy percentage read over 100% because the ceiling counted one jump
  for N. Two ticks on the ground is enough to make it visible, which is why an
  imperfect hop behaves and a good one does not. If you need "a hop happened",
  take it from the impulse (an upward step in `vel_z`, which gravity and
  AirAccelerate cannot produce) or from the energy, not from the flag.
- TO FIND ENERGY A PLAYER CANNOT HAVE EARNED, WALK A `.rec` TICK BY TICK against
  `cap^2/2g`. `E = z + |v|^2/2g` is EXACTLY conserved by the engine's half-step
  gravity (`PMSrc_StartGravity`/`FinishGravity`: dE = 0 per tick, algebraically),
  and AirMove flattens wishdir so AirAccelerate adds nothing vertical -- so in
  free air the ONLY thing that can move the energy is strafing, bounded by
  `pm_maxairspeed^2 / 2g` per tick. Any tick over that is a booster, a push, a
  teleport or a jump, and the recorder's flag word says which. 300 files gave
  17021 such ticks in 4419 air runs and separated three causes in one pass;
  `tools/p452col.py`'s `samples()` is the parser and `p449mark` has the flag
  bits. Far cheaper than reproducing any of it in the game.
- `pwsh`, never `powershell`.
- AN ENTITY BOX FROM THE MODELS LUMP IS WHERE A BRUSH CAN BE, NOT WHERE IT IS —
  wrong by a wide margin three times; `tools/census/README.md` has the cases. Grade
  the claim before quoting it: `gap == 0` counts a zero-width plane contact as an
  overlap and is nearly meaningless, positive overlap VOLUME is better, and
  CONTAINMENT (the pad's whole box inside the zone) is the only figure that
  survives — and even that does not prove you can touch the brush. A `cmd viewpos`
  read back after a `setpos`, or a `.rec` row from a real player, beats all three.
- **A COMPACTED SUMMARY OF A DOCUMENT IS NOT THE DOCUMENT, AND THE CLAIM MOST
  LIABLE TO BE WRONG IS "THIS SOURCE IS WRONG".** A session resumed from compaction
  asserted that two of `ENGINE_SECURITY.md`'s citations were bad (`cl_main.c:3725`,
  `cl_parse.c:4791`) and built a conclusion on it -- that a traced-only list with
  drifted line numbers is a list nobody can check. The file cites `sv_ccmds.c:3256`
  and `sv_ccmds.c:3891`, and BOTH ARE EXACT; the invented numbers were the summary's,
  not the file's. It reached a pushed public commit before anyone opened the file.
  Two rules follow: never assert a defect in a source you have not just read, and
  treat a citation carried through compaction as unverified until it is checked.
  Related and cheaper to remember: the same entry claimed a finding the file had
  ALREADY stated, so the honest claim was the measurement, not the discovery -- say
  which of the two you are making.
- A `file:line` CITATION DIES WHEN ANYTHING ABOVE IT GROWS, in its own file and in
  every file that cites it: one added comment block invalidated ~10 numbers here,
  two of them in sv_timer.qc. Cite QC by FUNCTION NAME; keep line numbers for
  `pm_source.c` and other engine files this repo never edits. Cite a measurement to
  a committed script (`tools/census/`), never to a scratch path that will not exist
  for the next reader. AND AN ENGINE LINE NUMBER IS NOT SAFE EITHER JUST BECAUSE WE
  DO NOT EDIT THAT FILE: Patch 455 cited `pm_source.c:4696` for the prestrafe
  ceiling and that line is a single `{` — the essay is at `4679-4698` and the
  binding statement at `5001`. Open the line before you cite it.
- WHICH DIAGNOSTIC PRINTS ROUND, because a rounded readout bounds the claim you may
  make from it and this tree has several. Audited 2026-09-27: 53 `%.0f` sites in
  `src/`, of which these print a speed-like value where the precision can mislead —
  `cl_hud.qc` `Strafe_EquivSpeed`'s `%.0fu/s`, `cl_scores.qc`'s `speed %.0f..%.0f`
  band, `cl_watch.qc`'s `replay colours` speed range, and `sv_entities.qc`'s
  `basevel: OnJump ... vz %.0f`. The one that cost something was a speed printed at
  `%.0f` beside the cap it was being compared against: "260 u/s is at or below the
  cap 260" reads as a boundary equality and means only `[259.5, 260.0]`. The real
  margin was 6.6 u/s, and the crossing speed varied 243.9 to ~260 between runs — so
  a fixed boundary was inferred from a rounded number twice. A dprint costs nothing
  at `%.3f`; use it wherever the number is about to be compared to a limit.
- Deleting save dirs behind a running server does NOT clear its in-memory list;
  it rescans on map change/lobby flip/restart. Delete-all is `sl_delall`.
- SAVE-LOCKS SINCE PATCH 428 (sv_saveloc.qc): 999 a player a map, in memalloc'd
  columns (qwprogs sits at ~40k of 65535 globals -- do not grow them back into
  arrays). A lobby block is fresh only for the guid it was scanned for
  (SL_Fresh); only the newest 24 lobby saves keep their run -- older ones are
  DEMOTED to a position at rest; `sl_delall` sweeps 2 rows a server frame;
  20 `sl_` commands a second. A hold needs a load of that save in the same
  frame at its spot, a zone move releases it, and SV_TimerFrame runs no zone
  tests under it. Each rule closed a clean-run path in review: `cfg/test/
  p428hold.cfg` is the arm, and the open older holes are under Patch 428's Known.
- Two clients writing the same `log_name` interleave confusingly.
- TIME QC WITH DEVELOPER LOGGING OFF. `developer 1` + `log_developer 1` writes a
  `qcfopen(...)` line per QC fopen: 999 small reads measured 4.8 s against
  0.24 s without. `+set pr_enable_profiling 1` on the server, then
  `profile_ssqc` (over rcon from the harness client) gives per-function times.
- `cmd viewpos` is answered BEFORE spawn (`setpos 0 0 0`), so it proves nothing
  about a join; the server log's `said> server: <name> joined` does.
- A leftover test process (`ftesurf64*.exe`, `fteqwsv64.exe`) holds
  `fteplug_hl2_x64.dll`, so build.ps1's deploy aborts part-way and `C:\FTEQuake`
  keeps a stale server. Check `Get-Process ftesurf*,fteqw*` before `-Engine`.
  A server still in its closing `waitms` also keeps the port, and the next run's
  client joins IT and is dropped when it quits: kill leftovers between runs.
- Sessions share test fixtures (surf_666 + `p360sf.zones.json`, `data/runs`,
  `data/saves`, `data/resume`). Tell the other live session before a run that
  moves them, park rather than delete, restore and `diff -r` afterwards. The
  same goes for `build.ps1`: it redeploys the progs a running harness loads.
- Two-process harnesses drift: over a five-minute run the clients' `waitms`
  timeline ran 5-9 s ahead of the server's. Leave windows of 5 s or more
  between a server `set` and the client action that depends on it, and read the
  logs' timestamps rather than the cfg's arithmetic.
- A lobby process sees files another process wrote only after its own next map
  load (the name hash; `SV_MsAdopt` renames onto itself to force it). A
  cross-lobby test starts the second server after the first one's write.
- Agent shells: a Bash heredoc collapses `\\` to `\`, so an inline edit script
  that must match QC's literal `\n` fails or writes a real newline. Write such
  scripts with the file tool, or build the backslash with `chr(92)`. AND CHECK THE
  RESULT: `chr(92)+'n'` inside a `python -c "…"` string lands in the file as the
  literal text `' + NL + '`, which fteqcc rejects ("newline inside quote") or --
  worse -- compiles into a print that never fires. It cost four builds in one
  session. The reliable shape is a `python - <<'PYEOF'` heredoc that writes the
  file with `chr(92)` only where a real backslash-n is wanted, then `grep -n` the
  line back before building.
- Engine cvar `timeout` (default 65 s) is the dead-client drop; lobbies set 30.
- Unregistered cvar set by bare name in a cfg is "Unknown command" — `set` it.
- Engine `sv.active` is never assigned anywhere — every `if (sv.active)` is dead
  code; the live server test is `sv.state != ss_dead`.
- Engine `va()` is a small rotating buffer. Its pointer dies at the next `va()`
  anywhere, including inside FS calls: FS_Remove restarts the loader threads,
  whose names come from `va()`, and a download was saved as "loadworker_3". Copy
  with `Q_snprintfz` before holding it across a call. Also:
  `CL_CheckOrEnqueDownloadFile` returns FALSE when it STARTS a download.
- The QuakeWorld join is `SV_New_f`; `SVNQ_New_f` (NQPROT) is NetQuake's, and
  an edit there does nothing for FTESurf clients.
- THE PI TALKS UTC AND `git log` TALKS LOCAL (+10). Comparing a Pi file's mtime
  against a commit date silently misreads which build is live — it cost a fleet
  record that understated the fleet by nine patches. Pin a deploy with
  `TZ=UTC git log --date=iso-local`, and remember the Pi keeps no receipt: the
  DEPLOYED notes in ENGINE_PATCHES.md and the `.prev`/`.preNNN` files are the
  only record, so write one after every `-Pi`.
- Off the home LAN, 192.168.1.102 is dead but `proto@180.150.62.57` answers, and
  `build.ps1 -Pi -PiHost proto@180.150.62.57` deploys fine (its lobbies.json
  probe reaches :8084 too). Only the 12 lobby ports are forwarded, so a
  hand-started test server on another port is unreachable from outside — run
  that arm locally and say so in the entry.
- A player's guid is the `qkey` in the install ROOT, so two clients from one
  install are ONE player to the server. For a second player run the same exe
  with `-homedir <dir>` holding its own random `qkey` (FS_ROOT reads it there;
  its logs land in `<dir>/ftesurf/logs`) -- `p428slota/b`. Read both guids out
  of the server log as the control before believing the result.
- fteqcc: `arr[i]_x` does not compile ("Cannot cast from vector to float") —
  copy to a local vector first; sprintf takes ≤ 8 args (warns above, and DROPS
  the ninth silently); a lone `;` branch warns Q205 — use a comment-only block;
  big fixed arrays blow the globals/strings budget (4096 rows forced a 32-bit
  target — size them to the library). qwprogs is the 16-bit target and was at
  64547 of 65535 globals before Patch 428 moved the save columns into
  `memalloc` (`float *p = memalloc(n * sizeof(float))`, indexed as an array;
  the heap resets with the globals at every map load) -- check numglobals in
  the .dat header before adding an array.
- **GATING ONE LEG OF A COMMAND THAT RE-QUEUES TWO IS NOT GATING THE COMMAND.**
  `SV_MapFrom_f` ends in two `Cbuf_AddText(..., Cmd_ExecLevel)` calls, so both inherit
  the caller's restriction level: Patch 481's `fs_useaddons` gate refused the first,
  and the `map "@<argv(1)>/<argv(2)>"` beside it still ran. Measured on the unfixed
  build, a stuffed `mapfrom ftesurf bhop_eazy` printed `Blocking insecure command:
  fs_useaddons "ftesurf"` and then **`SpawnServer: bhop_eazy`** -- a remote server
  made the client HOST a map. It stayed open four patches because the refusal line in
  the log read as the command having been stopped. WHEN A HANDLER ENDS IN
  `Cbuf_AddText` OR `localcmd`, GATE THE HANDLER, not the things it queues: the
  queued commands inherit the level and each one is a separate decision somebody else
  made. Patch 485 gates `SV_MapFrom_f` itself. The corollary for an arm: a refusal
  line for command X is not evidence about command Y that X was about to run.
- **`Cmd_IsInsecure() && !Cmd_FromGamecode()` MEANS THE OPPOSITE OF WHAT IT READS.**
  Both are thresholds over ONE ordered value (`engine/common/cmd.h`): `RESTRICT_LOCAL`
  29 < `RESTRICT_INSECURE` 30 < `RESTRICT_SERVER` 31, `Cmd_IsInsecure()` is `>=30`,
  `Cmd_FromGamecode()` is `>=31`. The conjunction is therefore *exactly* level 30 --
  it blocks csprogs/menuqc and ADMITS a server's stufftext, which arrives at
  `RESTRICT_SERVER`. So the pair cannot separate "a remote server" from "ssqc", and
  the tree's policy is to refuse both (Patch 481's comment says so; its `fs_*` gates
  and `FS_RefuseInsecure` are plain `Cmd_IsInsecure()`). Cost an arm: a stuffed
  `fs_changegame 1` under that condition switched games and crashed the client with
  no `Blocking` line, while a strict gate beside it in the same run refused correctly.
  A local console/cfg caller is `RESTRICT_LOCAL` and is never insecure, so a strict
  gate costs the USER nothing -- it only costs QC. `grep` the QC before assuming that
  matters: `fs_changegame` has no caller in `src/`, and the engine's own mod menu
  uses `RESTRICT_LOCAL`.
- fteqcc parses `x = a && b` as `(x = a) && b`: assignment binds tighter than
  `&&` and `||` (measured: `t = !first && FALSE` gave 1). Wrap the whole
  right-hand side, `x = (a && b);`, as the tree mostly does. Still unwrapped in
  committed code, left for a decision because fixing them changes behaviour:
  `snapang` in trigger_teleport_touch (sv_entities.qc) and its mirror in
  TG_FireTeleport (cl_triggers.qc) -- the keep-angles flag is ignored on both
  sides; `probe`/`hit` in TG_ChainStart and Trig_ConsoleCommand (cl_triggers.qc);
  `lpd_active` in Portal_LoadForMap; `onpanel` in Ev_InputEvent; `vote_on` in
  Vote_Frame; `vbsp_retrigger` in SV_UpdateMovementServerInfo.
- **A QC INTEGER LITERAL IS A FLOAT UNLESS IT CARRIES AN `i` SUFFIX, AND AN `int`
  LOCAL ABSORBS ONE WITH NO WARNING.** Measured in both VMs (Patch 496): with
  `local int x`, `x = 2144999 * 1000 + 952` stores **2144999936** and
  `x = 2144999 * 1000i + 952i` stores **2144999952** -- the first promotes the
  product to float32, quantises it, and the assignment truncates back. So any
  integer arithmetic written with plain literals silently becomes float32
  arithmetic above 2^24, which is exactly the range an int was chosen for.
  Suffix every literal in an `int` expression (`1000i`, `0i`, `1i`), as
  `m_board.qc`'s ms split always did. THE ONLY THING THAT SAID ANYTHING was
  fteqcc's own **F324, `sprintf: %i requires int at arg N (got float)`** -- so
  `%i` in a sprintf is a type assertion worth making on purpose, and a QC file
  with int arithmetic should compile with 0 warnings rather than be read.
  Related and older: fteqcc takes NO exponent in a literal (`1e15` is `1` then
  the identifier `e15`, "bad suffix on number"), and `int` is a type while
  `double` is not ("`double` is not a type"), so an exact product has to be a
  compensated float32 pair rather than a wider scalar.
- Every QC GLOBAL is zeroed on every map load, `map_restart` (so `retry`)
  included. Anything that must identify state across one lives in a cvar or a
  file: a per-map rewind serial let a pre-retry save rewind "warm" across the
  counter restart (Patch 364 moved it to the `rec_serial` cvar).
- QC HAS NO FILE SCOPE, and fteqcc merges two same-named same-typed globals into
  ONE with no warning. That is the mechanism forward declarations rely on, and it
  is also a live hazard: build 48 added a `ui_rs_armed` in cl_results.qc that
  already existed in cl_board.qc, silently aliasing build 26's teleport guard,
  and BOTH features broke in opposite directions for several builds (see the
  essay at the declaration in cl_results.qc). `grep -rn "float  <name>" src/`
  before naming a new global.
- PARALLEL-ARRAY COLUMNS ARE A STANDING TRAP. cl_board.qc's `seq_*` column is
  TEN arrays (`kind gain de emax dur launch pct eend sub eref`) and the count in
  the file's own warning says SEVEN places move together: the SEQ_MAX scroll
  inside Seq_Push (cl_board.qc:2024) and Seq_Push's own row write (`Seq_Push` is
  at 1976), Seq_Mark, Seq_Unmark, Seq_Load, and the seq.txt pair
  Seq_Write/Seq_Read — PLUS the FOUR sites in cl_watch.qc that seven does not
  count: `Watch_SeqRow` (the replay CAPTURE into rec_wt_sq*), `Watch_SeqSave`,
  `Watch_SeqRestore` (the park pair, rec_wt_sv*) and `Watch_SeqApply`. That is
  exactly where `seq_eend` (build 65) and `seq_sub` (66) stayed stale for two
  builds — the park pair was fixed in 342 and the capture in 343. A new column
  needs BOTH rec_wt_ sets or a replay silently draws the run's last row on every
  line. `seq_mk_*` is a full ten-array MIRROR of the column (cl_board.qc:883-892)
  and moves with it.
  Miss one and the column draws happily with a single field a row out of step,
  which reads as a physics bug.
- Entity I/O's authoritative semantics live in `src/server/sv_entities.qc`
  (~7800 lines, heavily essayed): ED_ParseUnknownEpair (case-sensitive "On"
  prefix), SV_EntityIOBuild (five-field rows, ESC-or-comma), SV_FireOutput /
  SV_IODeliver (exact-then-case-insensitive lookup), SV_ApplyInput, SV_IOEnable,
  SV_TriggerIOTouch / SV_TriggerEndThink (edge tracking, 0.05 s end grace,
  once-retirement).
- Unimplemented server classes leave DORMANT wiring: `trigger_userinput` has no
  spawn function, so its 14 OnKeyPressed outputs on mom_training fire nowhere
  and its StartDisabled targets are dead server-side too. Before blaming client
  prediction for a "broken" map mechanism, grep sv_entities.qc for the class.
- Defining CSQC_Parse_Print routes EVERY svc_print into csprogs and the engine
  prints nothing: re-`print()` each level you do not handle or it vanishes from
  console and logs. Chat arrives pre-formatted by CL_PrintChat with console
  escapes (`\1`, `^[`, `^]`, `\player\N^`) — parse it into (slot, text), never
  blit it; the name comes back from the slot via getplayerkeyvalue.
- sui has ONE hit-test list and ONE input buffer per frame: sui_begin empties
  the list, sui_end clears the buffer, so a SECOND sui bracket in the same frame
  draws dead buttons. Clickable panels either share a bracket (Players_Panel
  draws inside Scores_Draw's) or refuse to coexist.
- sui_slidercontrol's THIRD component is a DIVISION COUNT, not a step size
  (`src/sui_sys.qc:1167` quantises by `rint(r*steps)/steps`): `[0, 255, 1]` is one
  division = the whole range, so every drag snaps to an endpoint.
  steps = stops − 1 (bytes: 255, off/trail/long: 2, binaries: 1).
- A second clearscene/renderscene during the 2D phase with VF_VIEWPORT +
  VF_DRAWWORLD 0 is a working subview (cl_avatar.qc's preview): park the stage
  outside every game frustum and emit its particles after the main renderscene,
  or the world view inherits them.
- Chain guards gate handlers: CL_InputChain offers Scores_InputEvent under
  `rec_sb_open || sc_held` — a handler written for a new state is dead code
  until the guard admits that state. Read the guard, not just the handler, when
  a key "does nothing".
- A PANEL WITH TWO WAYS IN NEEDS BOTH WAYS OUT TESTED. The board is held by
  `+showscores` and pinned by MOUSE2 — which is also `+jump`, so jumping while
  peeking pinned it by accident and the release did not clear the pin. When a
  state machine grows a second entry, walk every exit.
- WORK SPREAD PER PACKET IS NOT SPREAD. SV_ReadPackets drains the socket in one
  loop, so a batch in PlayerPostThink that costs about a packet interval runs
  back to back until done -- Patch 428's first delete-all sweep stalled the
  server as long as the one-call version, with no `took over a second` line.
  Spread server work from StartFrame, and measure it by a command answered
  mid-way, not by that warning.
- lobby.cfg sets `rcon_password ""`: a test server that execs it and needs rcon
  sets the password AFTER the exec (a `+set` loses; the log says `Bad rcon`).
- Build and verify (headless run + logs/screenshots, or Pi journal) before
  declaring any task complete.
- THE ENGINE'S FONT OUTLINE IS A BAKE, NOT A DRAW FLAG.  `outline=N` in loadfont's
  sizes string and `r_font_postprocess_outline` are read at slot definition for
  EVERY slot in the process -- they re-bake the console and menu fonts too -- so
  neither can be a HUD switch.  Patch 440 draws its ring instead (eight copies of
  the string one pixel out in each direction, under the body, in HUD_TextDraw,
  gated on `ui_font_cur == ui_font_mono`).  And ftefont is PREMULTIPLIED
  (`blendfunc gl_one gl_one_minus_src_alpha`, rgbgen vertex): the requested rgb
  reaches the framebuffer UNSCALED by the requested alpha, so an outline or
  shadow colour must be DARK -- a light grey at half alpha is a bright smear, not
  a shadow.  A second baked slot for one face doubles its cells in the four-plane
  glyph atlas every font in the process shares; a draw-side ring allocates none.
- A `.cfg` HAS NO BLOCK COMMENTS. The config parser knows `//` and nothing else,
  so every line inside a `/* ... */` goes to the command interpreter. Patch 462
  wrote its arm that way and the log filled with `Unknown command "AIR"`,
  `"because"`, `"pms_lockedmovevars"` — the first token of each prose line. That
  is noise until a line happens to BEGIN with a real cvar, at which point the
  comment silently sets it: two lines in that file opened `map,` and
  `hud_trainer_x/y` and were saved only by the punctuation making the token
  unmatchable. 1013 of the 1016 files in `cfg/test/` use `//` already; the three
  that did not are `b86b.cfg`, `tint02.cfg` (checked 2026-09-28 — 7 and 13 prose
  lines apiece, none of which can execute) and p462trn.cfg, now converted. Grade
  an arm's log for `Unknown command` as well as for its own verdict.
- A MOVER CVAR CANNOT BE SET FROM AN ARM WITHOUT `sv_cheats 1`, AND THE FAILURE
  IS SILENT. `sv_gravity`, `sv_airaccelerate`, `sv_maxspeed`, `pm_ticrate`,
  `sv_friction` and the rest are in `pms_lockedmovevars` under
  `pm_lockmovement 1`, and the lock cuts BOTH ways (`sv_phys.c:136` says so in
  the cvar's own help): every one is restored to the game's default AT MAP LOAD,
  and refused thereafter unless cheats are on. So a `set` above the `map` line is
  undone by the load, and a bare assignment below it is reverted inside
  `Cvar_Set` before any tick sees it. The only window is `map` -> `sv_cheats 1`
  -> the cvar. Read it back with a bare `cvar` line afterwards and treat a
  `(default)` suffix in the readback as a FAILED SET, not as cosmetic — that
  suffix is the whole diagnostic and it does not look like an error. Patch 462
  spent two arm cycles reading `"sv_gravity" is "800" (default)` as noise while
  every cut measured a body in free fall at `horizontal 0`.
  The two arms carrying `set sv_gravity 0` (`p440font.cfg:111`, `p457av.cfg:69`,
  both commented "a still camera") are NOT invalidated by this and were not
  corrected: neither sends any movement before its shots, and a grounded body
  with no input is equally still at 800 — their stillness never came from the
  line. Only an arm that needs gravity to actually CHANGE is affected.
- PIXEL-DIFF HARNESS RECIPE (`cfg/test/p440font.cfg`, `tools/p440font.py`): still
  the camera by sending no movement — the `sv_gravity 0` in that file is inert
  (see the bullet above) and a grounded body needs no help staying put; pick a
  map whose textures
  actually mount -- surf_kitsune's skyroom does not and a missing sky FLASHES
  between frames (the floor read 239133 changed pixels; surf_rookie's is exactly
  0); `con_notifytime 0`, because notify lines move AND, with notify on screen
  plus extra drawstring passes plus a busy HUD, unrelated glyphs tint to the
  console's ^7 white (BACKLOG, engine-side); park control regions off the sky
  (clouds move); a control region must not contain the feature's own widget (its
  chip has to change -- grade the panel's element rows, not the panel); and take
  the floor from a pair of shots at the SAME cvar ~0.7 s apart, grading regions
  against it, never the whole frame (the fps counter always moves).

### Similarity atomic peer flush and contention (P574-576, 2026-10-08)

Peer admission and observations share one short atomic flush after comparison;
source admission remains a separate pre-work checkpoint, not completion/reservation.
A real abort after the first insert must restore the old peer cursor AND discard
all new observations across reopen. All-failed admitted pairs still checkpoint,
without fake skips/zeros. File comparison must allow an independent writer to ACT.

Sweep explicitly owns the busy-handler slot for collection: --sims-lock-ms1000
(default) is per SQLite lock operation;0 is immediate/no wait, not disabled. Restore
previous numeric timeout before ordinary verification, including failure/interrupt.
Standalone unopted/dry-run waits remain unchanged. Python cannot retrieve/restore
an arbitrary native handler. This is not a total pass deadline or RSS/write cap.

Classify contention by actual SQLite BUSY/LOCKED primary result codes only. Stop
further source admission, preserve prior committed observations, and report fixed
coverage-not-measured availability; summary busy state has ALL counters unknown.
Python3.10 lacks these error-code attributes and retains generic failures;3.11/3.13
code-required controls ACT. Never infer result codes from exception prose.

The new Windows3.13 atomic test exposed that SQLite context managers COMMIT but
DO NOT CLOSE. Explicitly close owned reopened/concurrent writer fixture connections
before temp cleanup. The older untouched source fixture shows the same cleanup
failure on published baseline; do not repair unrelated tests to mask it. Windows
admin UDP/RCON failures still match baseline; Linux full tests pass after one
recorded unmodified rerun of the existing dynamic-board timestamp equality case.

Publication74dcca0 shipped ONLY simcheck.py/sweep.py via canonical -Only -NoReload;
installed Python3.11 passes15 unique new controls without skips. Additional WAL
writer/wrapper control proves short abstention, restoration/recovery and later
synthetic verification with prior wait. Explicit live mode=ro/DML-denial controls
leave cursor/sample history unchanged; original sims/receipts/verdicts/reviews rows
match the pre-copy backup via bounded SQL with ACTED changed/deleted-row fixtures.
Do not turn this into mutable board/replay preservation or live-contention proof.
Both destination hashes and health/auth checks pass; rollback files/mode600 DB
backup retained. No game/QC/engine/config/Windows artifact or owner-process restart.

### Bounded log, association and plot acquisition (P590-592, 2026-10-08)

Log tails size the opened handle, read only their byte window, and discard a
partial initial line from that buffer. Newline-free and rotated/growing files
must ACT in controls; output line limiting after an unsized read is not a bound.
Historical associations acquire cap+1 per direction (26), display 25 and expose
independent more flags. Their selected cumulative SQL allowance is opt-in only
on the request-owned connection. Exhaustion withholds both lists but preserves
the receipt; partial badges say 25+, never a manufactured exact total.
Plot max_bytes is an exact nonnegative integer. Every normal/drain read uses
remaining bytes, including zero/one/non-aligned boundaries. A budget-cut line
cannot become a sample. Exact-cap files conservatively show truncated without
an extra EOF probe; complete plots with allowance remaining retain semantics.

Three new real-file/DB/DOM suites pass six tests each. Combined selected controls
pass 25 with the following command from surfd/:

```sh
python -W error -m unittest test_admin_log_bounds test_admin_association_bounds test_recplot_budget test_admin_metric_bounds test_admin_similarity_budget
```

Node controls run locally with no skips; Linux lacks Node and skips two renderer
arms, not an independent DOM pass.
Existing receipt-fragment harnesses must include the actual association helper;
compare board evidence without its generated response timestamp t. These are
selected read/result/SQL-work bounds, not whole-request RSS/time/snapshot proof.

Clean baseline/final offline script comparison has zero new failures; the same
two legacy UDP admin failures remain. Reccheck: 306 checks, zero failures. Frozen
corpus: 269 recordings / 101 view files, still 170 faulting recordings, unchanged
manifest.
Independent native review inspected source/artifacts, did not rerun tests.
Frozen 2ea4035 shipped only eight selected surfd source/test files, after stage
gates, mode 600 DB backup and copy under sweep lock. All destination hashes match;
replacement worker acts on authenticated log/association/plot reads and health
reports 12 lobbies at 2026-10-08T10:16:14Z. Rollback copies retained. No game/QC,
engine/pin/tag/Build, verifier-tool, Windows artifact or owner-game restart.
Browser/readability acceptance remains in lextest.md; no live evidence collection.

### Authenticated observer fetch/work limits and dry schema (P586-588, 2026-10-08)

Stored journal/counts fields use cap+1 BLOB-prefix SQL projections, not TEXT substr:
NUL and multibyte payloads must retain a byte oversize sentinel. Strict UTF-8 and
existing typed/versioned validation preserve measured zero and legacy unavailable;
invalid snapshots do not trigger historical rereads/backfill. These are selected
result-field limits, not bounds on the entire review response, SQL scan or RSS.

The historical similarity panel owns only its fresh request connection's callback
slot. Existing ReadBudget supplies one million selected VM instructions over PRAGMA
and history reads. **P597 (2026-10-08)** also charges the initial sqlite_master probe
within that allowance; its former unbudgeted exception is now closed. An interrupted
probe says read_limit, not confirmed missing. Real initial-probe interruption and
handler teardown ACT in `surfd/test_admin_similarity_probe.py`.
ReadLimit withholds the entire optional panel (state read_limit), not partial pairs
or false empty history, while useful run review remains. Missing stays distinct;
other storage errors still error. Borrowed similarity_for calls default to no budget
and retain caller callbacks. Owner opt-in cannot restore an unknown foreign handler.
Actual related-pair sorting must ACT: unrelated rows can use indexes and prove no
exhaustion. Default recovery must retain a positive 80-opportunity control.

Only the similarity dry-run subsection is non-initializing: existence-aware scalar
counts/summary never create/ALTER sims or sim_cursor. Main/import general schema
setup still mutates. A real authorizer distinguishes absent, legacy and current
schemas; the actual normal collector must still initialize and store a comparison.
Python3.10 authorizer teardown uses an explicit allow callback in the new fixture.

Frozen b4f4d31: 60/60 explicit Linux programs; Windows59/60 with the same two UDP
assertions in byte-identical test_admin source reproduced on baseline56/57. Argument-
required momindex is excluded, not a pass. New3/4/4 tests are warning-clean; recorder
306/0, captured269REC/91VIEW hashes and full fault lists match (170 existing faulted
reports). Source/evidence review found no concrete blocker but did not rerun tests.
Windows actual Node DOM passes; Linux Node/conversion capability skips remain.

Canonical exact-commit -Only (repo-relative paths) shipped ONLY admin.py,
templates/admin_run.html and sweep.py, with NORMAL shipper tests, no skip/reload
flags. First preflight used wrong allowlist names and changed nothing; corrected
invocation used the shipper's actual NVMe staging. Master2479950 retained, new
worker/ready09:05:04UTC; all destination AND predecessor rollback blobs match.
Mode600 DB backup retained. Installed modules are bound to actual paths in isolated
HOME/DB:11cases, ten pass/one absent-Node skip; live authenticated detail200/anonymous
401 and read-only diagnostics ACT. Bounded SQLite EXCEPT proves original
sims/receipts/verdicts/reviews rows match backup, with exact/changed/deleted oracle
controls. Initial finish probes expected wrong summary state and streamed CRLF;
finish-only corrections completed, no recopy/reload. Final host09:11:25UTC healthOK,
12lobbies active. No live collection/reread, reader/engine/progs/Windows/config swap;
no mutable board/replay/cursor preservation, hard time/RSS, calibration or live-
browser acceptance claim. Shared peer trees are untouched.

### Similarity ownership and scalar diagnostics (P582-585, 2026-10-08)

Exact integer source/peer/pair limits reject negatives (SQLite LIMIT would mean
unlimited), booleans, fractional/string inputs and signed-64 overflow before
optional loading or queries. Zero does no loading/query work. CLI rejects before
main connects, not before surfd's existing import-time initialization.

Enabled collection/direct comparison require idle connections before schema/file
work or sweep handler-slot changes. Never commit/rollback unrelated caller DML to
make collection run. Source admission/schema writers reject active transactions;
read-only pending/summary and disabled calls preserve ownership. Real two-connection
controls prove pending DML stays invisible/rollbackable; an idle independent writer
ACTS during an 80-opportunity comparison. This is an embedded API fix, not a proved
cron-path leak. SQLite connection context managers commit/rollback but do NOT close;
main now explicitly closes its fresh connection on normal/dry/error/interrupt exits,
even when the caller retains the traceback. Borrowed step APIs remain usable.

Dry-run counts a capped eligible-ID subquery as one scalar, never replay payloads.
Share the pending predicate; rotating collection selection remains unchanged. Keep
one-million cap, print at least on equality, and retain whole-query unavailable plus
independent summary allowance. Wide-payload and real VM-interruption controls ACT;
cap-label branch is synthetic, not million-row performance or native RSS/scan/time
proof. No detector math, threshold, history, receipt, ranking or badge-gate change.

Frozen published705ce1b passed57/57 explicit Linux programs; Windows56/57 with the
same two UDP-admin failures reproduced on baseline. The argument-required momindex
integration rig is not a standalone pass. Initial Linux disk-floor failures came
from fixtures on the 4.8GB root filesystem; full unmodified rerun on NVMe passed.
Existing test_sweep fixture ResourceWarnings reproduce20/40/12lines in baseline;
new focused cases are warning-clean, not the entire suite. Recorder306/0;269REC and
91pairedVIEW full reports equal on captured bytes,170faulted reports unchanged.
Source/artifact reviewer did not re-execute or hash-attest Git; parent did. Waiting
for final artifacts exhausted its30min budget; clean/ref proof and same-native resume
completed review without fallback. Owned scratch was retained after failed rmdir.

Only installed simcheck.py/sweep.py shipped by canonical exact-commit -Only/-NoReload,
normal stage tests, rollback files and mode600 DB backup; no reader/progs/engine/
Windows/config swap or live collection. Installed synthetic HOME binds actual module
paths and reader, stores80opportunities, exercises all four seams. Protected bounded
SQL with exact/changed/deleted controls proves original sims/receipts/verdicts/reviews
rows match backup. Final UTC2026-10-08T08:06:26 health/auth gates pass. Mutable board/
replay/cursor preservation, complete scheduling and hard resource bounds unclaimed.
The shipper infers repo from PSScriptRoot; it has no -Repo parameter. Read its actual
parameters. Existing primary-Windows reader peer-ownership blocker remains untouched.

### Truthful historical observation follow-ups (P595-597, 2026-10-08)

Verdict history acquires201/displays200 with owner-only limit/more metadata;
partial summaries never call omitted history all-stale. Journal/counts typed
JSON projections reject duplicate decoded keys at every nesting level. Initial
similarity table existence now shares the owned cumulative SQL allowance with
PRAGMA/history; exhaustion is unknown/read_limit, not confirmed missing.
Actual predecessor behavior reds and source/fetch/DOM/SQLite greens are in
`tools/p595observers.md`; source review was read-only, not a deploy attestation.

Frozen38eb243 passes59Linux programs (includingrecorder); Windows57/58 with
only the same two admin UDP assertions reproduced on untouched4f066479.
New focused tests are warning-clean; full legacy fixtures are not. Node runs on
Windows, not the Pi. Installed-source complete isolated harness22tests/fourDOM
skips, authentic-worker API/anonymous401, worker replacement/health12, selected
history/public board and protected support/progs/config/reader bytes ACT.
Only admin.py/template shipped; no partially installed test-helper chain.

A live online backup can restart forever under heartbeat churn. The first
private attempt timed out BEFORE swaps and its partial file was retained/marked
incomplete; exact owned process only was stopped. Stable source read transaction
plus explicit90second progress deadline completes. `BEGIN` alone is deferred:
P599's first attempt still timed out before swaps; actually read sqlite_master
(or another safe table) before backup to establish the source snapshot. Its
corrected completed backup preceded the selected source copy. RELEASE it before fresh
preservation checks or the snapshot could conceal later writes. Keep mode600
completed backups and .prev files. This Pi kernel lacks task/<pid>/children;
portable parentage must prove worker replacement. Wrong probe-cookie name and
that unsupported interface were private procedure failures, not product bugs.
The interface failure restored exact predecessor files. An untouched legacy
counts test compared transient board t across a second: advancing-clock baseline
red/stable-clock green proves flake; freeze only isolated fixture clock, never
repair production to satisfy it. BACKLOG retains the site/falsifier. Final
verified UTC2026-10-08T13:59:52Z; human browser/calibration and hard whole-request
bounds remain unverified. Read actual surfd-deploy parameters, not guessed names.

### Similarity reliability batch (P577-580, 2026-10-08)

Optional reader budgets are configuration: invalid integer/type/read-size limits
reject before I/O, not as evidence skips. None and valid zero/exact bounds retain
behavior. Collector flush counts use insertion-local rowcount, not buffered results
or total_changes; same-key overlapping winners and trigger writes cannot fabricate
new additions. Admission still is not completion/reservation/exactly-once.

The canonical capsule requires integer version1 bounded-input/capture capabilities
and ACTED disposable80-row exact-capture and whole byte/move-limit abstention
controls before destination mutation. This is trusted-code smoke testing, not
sandbox/authenticity/hard resource proof. A collection pass uses one initially
resolved module; direct calls and later passes re-resolve their explicit tools path.
No process-global cache or atomic recording-content snapshot is implied.

Frozen952d586 reviewed without blockers and published. All52explicit Linux programs
pass across51first-run passes plus one retained unmodified dynamic-board timestamp
rerun; established skips remain. Windows51/52, unchanged admin's same2UDP assertions
reproduced on the byte-identical baseline. Recorder306/0;269REC with pairedVIEW,
combined170faulted reports: exact source manifests and reports equal baseline.

Pi reader installed07:00:37UTC and ONLY simcheck.py via canonical -Only -NoReload
-SkipTests (52program stage already completed). Hashes/rollback/mode600DB backup
verified;25installed cases including5inherited and isolated installed sweep wrapper
ACT. Read-only live DML-denial/read-budget controls and bounded exact/changed/deleted
SQL gates preserve original sims/receipts/verdicts/reviews rows vs pre-copy backup;
no mutable board/replay preservation or live collection claim. Final gates
07:02:31UTC, health/auth OK. Secondary Windows reader installed07:01:07UTC; exact
hash, rollback and3installed source controls pass. PRIMARY Windows deployment is
BLOCKED by tracked modified reader in the shared checkout: preserved unchanged,
not overwritten. No engine/QC/progs/config/release/Build or owner-process restart.

### Selected similarity SQL read budgets (P571-573, 2026-10-08)

Sweep opts into a pass-wide 1,000,000 SQLite VM instruction allowance through
`--sims-sql-steps`; zero disables collection. Source cursor/pending and peer cursor/
candidate/late-recheck queries share it. Dry-run summary has an independent fresh
allowance. Whole-query interruption means unknown/unavailable, never partial
selection, prefix aggregates, zero agreement or full coverage. A late recheck
must flush prior successful observations and checkpoint only admitted work.

`ReadBudget` is explicit CONNECTION-OWNER authority: Python SQLite cannot retrieve
and restore an unknown existing progress callback. Use only on the owner's otherwise
unused slot; no-budget APIs preserve caller callbacks. Guard execution AND fetching,
close cursors and clear callbacks before file comparison/checkpoints/writes, including
ordinary SQL errors. Reserve a final callback quantum per statement to cover residual
instructions conservatively; small queries may abstain before the actual cap. This
is selected VM work, not lock waits, schema/writes, native/UDF cost, wall time, RSS,
fairness, concurrent reservations or completion. Actual expensive SQL plus positive
80-opportunity controls are required; mocked budget depletion alone is insufficient.

The exact publication passed 43 explicit Linux programs and 15 installed SQL cases
plus an actual installed sweep-wrapper comparison. Windows admin has the same two
UDP/RCON failures on the untouched baseline; do not repair unrelated code. Operator
import audits needing external input arguments are not standalone test programs.
Keep TMPDIR on NVMe for unchanged worker free-space floors; dynamic board `t` can
make the existing full-dict equality test flaky (see prior notes and BACKLOG).

Live board rows are mutable independently of deployment and outside the sweep lock.
An early all-table preservation gate saw board drift already in the pre-copy backup;
evidence/verifier/review/replay tables stayed exact. Do not assert a frozen board or
reinterpret that failure as six-table preservation. Never mirror a fleet-sized board
into two Python dictionaries for diffing: use bounded SQL/projections or explicitly
leave mutable-board preservation unverified. Bound lock waits and read work, retain
failed gates, and stop only the specifically proven owned diagnostic if necessary.

### Similarity retry admission controls (P563-565, 2026-10-08)

`sim_cursor` is additive INTERNAL admission state: one source position and an
independent peer position per source. Select greater eligible IDs first, then
wrap ascending. Only admitted work advances; reads never initialize or advance
state. Historical direct `compare_run` callers may have only `sims`, so create
cursor schema at the first actual checkpoint, not a read/disabled call.

Source checkpoints commit before file work; peer checkpoints commit once per
source call, including pair exceptions. Comparison/result-building faults leave
that pair unobserved and keep successful neighbors eligible for normal atomic
flush. A measured zero needs a positive comparison denominator; no fake skip or
zero is created for thrown pairs. Selection/checkpoint/storage failures are still
row failures; an ACTED mid-insert trigger proves observation rollback. Cursor
progress originally was not atomic with observations. P574 now commits peer progress
and observations together; source admission still precedes work. Neither reserves
work across competing collectors. Crashes/races can leave source admission ahead;
that is NOT completion, byte binding, exactly-once or full fleet-fairness proof.

Installed-module checks ran 55 cases including inherited fixtures, not 55 unique
coverage claims. Mock fault controls use denominator 1; separate installed bounded
reader checks ACT on real 80-opportunity fixtures: unavailable source rotation
survives connection restarts, a faulting first peer yields to later peers then
wraps, and a middle fault preserves successful neighbors. Additive live schema
init preserves sample/verdict rows; protected mode=ro checks preserve cursor state
as well. No live collection needed for temporary-fixture proof.

Windows RCON polling assertions in unchanged `test_admin.py` failed identically
in clean published-baseline and subject trees; source equality was captured, no
unrelated repair or Windows-pass claim. Frozen Linux admin and all 31 programs
pass. The already-recorded dynamic-board timestamp test failed once in an earlier
stage and passed one recorded rerun; the exact publication stage passes unmodified.
Both source reviews are read-only. Scoped `watchdog_diff` rejects an absolute
external worktree; pause/record the exact failure and bounded clean/ref/diff proof,
then explicitly distinguish parent attestation from reviewer independent source
inspection. No silent alternate runner or broader tooling fallback.

### Similarity eligibility and summary controls (P557-559, 2026-10-08)

`simcheck.pending()` means an eligible native pair remains unobserved, not that
its source has no stored observation. Stored pairs in either orientation must be
excluded BEFORE the peer LIMIT. Four sources with row/pair budgets one should
ACT six times, then go idle; a primary with 200 observed older peers must still
reach newer peers. This is eligibility, not fair retry or full-coverage proof.
The summary returns <=13 fixed aggregate rows in Python. Unbudgeted standalone
SQLite reads and working memory/cooperative elapsed completion remain unbounded;
P571-573 add optional owner-only selected-read VM budgeting, not a total RSS cap.

Frozen Linux suites passed at the inspected deployment commit; 23 focused
controls also passed with `sys.modules['simcheck']` bound to the INSTALLED file.
Real installed-reader controls completed six 80-opportunity pairs across budgeted
passes, then five new peers beyond a mixed-orientation 200-observation window.
Live metadata checks used mode=ro while holding the sweep lock; no real collection
or verdict/sample mutation was needed to prove the temporary fixtures ACTED.

An unchanged `test_admin_metrics` run failed its full public-board dict comparison.
That response includes dynamic `t` and can cross a wall-clock second; the failure
artifact did not retain the earlier timestamp separately. Same source bytes
had passed in the previous frozen stages and passed one recorded rerun. Keep the
failed artifact, source proof and rerun; do not repair unrelated product code or
claim that changing authentication/metrics changed the board. A deterministic
clock-boundary falsifier is recorded in BACKLOG.md.

### The public web surface (`/board/`) -- what may leave the process

- **A PUBLISHED `runs.player` WOULD BE A PUBLISHED IDENTITY.** That column is
  the client's guid, 32 hex derived from its qkey, and a client writes its own
  qkey -- so anyone holding a guid could file times as that player from a keyed
  server. `web_map`'s `del row["player"]` is load-bearing, not tidiness. The
  public id is `web_handle()` = sha256(guid)[:12]; 128 bits of guid does not
  come back out of 48 bits of digest. Never add a route that returns `player`.
- **The one exception is gated in one function.** `web_ext()` publishes an
  imported row's steamid64 -- which Momentum's own board publishes -- and
  returns None for every other tier whatever the value looks like. One
  predicate, one place, and test_web.py pins that a ranked row never carries it.
- **The run viewer's header is an ALLOWLIST (`WEB_HEAD_KEYS`).** A `.rec`
  carries `mapcrc`, `zonecrc`, `zonerule`, `nonce` and `pmpin`; those are the
  integrity surface and a blocklist ships whatever key is added next. The
  fixture .rec in test_web.py contains all of them on purpose, so the arm can
  fail. `evidence` rows, `community` runs and rejected runs are 404 there too.
  **IT IS THE SECOND OF TWO LISTS, and the first one filters silently.**
  `recplot.HEAD_KEYS` decides which header keys `parse()` returns at all, and an
  unlisted key yields no note and no counter (the `unknown records` note counts
  BODY records), so a key added to `WEB_HEAD_KEYS` alone publishes nothing and the
  symptom is a missing field rather than an error. `momdemo` needed both. Move them
  together.
- **`tier` on `/board/api/map` falls back, it does not 400.** The route shipped
  ignoring that parameter, so links carrying `tier=community` exist and
  test_web.py pins that they open ranked. A 400 there is a 400 on a bookmark.
- **`/board/shot/<name>` gets its safety from `clean_map`, not an allowlist.**
  Every other `/board/` file route has a fixed filename map; this one cannot
  (630 maps and growing), so the name goes through the SAME validator that
  decides what a map may be called on submit -- `..` refused, `_MAPNAME_OK`,
  `MAX_MAP_LEN` -- and the result is joined to one directory. Images are named
  for the MAP, not Momentum's uuid, so surfd needs no `mapmeta.txt`; the join
  happens once in `tools/mapshots_web.py`. A miss is a 404 with no placeholder
  and `board.js` loads through a detached `Image()` before showing the element,
  so the 110 maps without one lay out as though the hero was never there.
  test_web.py section 6c drives eight traversal shapes against a real file one
  directory up, WITH a control proving that file exists and is readable.
- **The nav tab is a function of the hash, not of the markup.** `aria-current`
  was written into board.html once and never moved, so Leaderboard stayed lit
  on top of a profile and Players never lit at all. `route()` owns it now; a
  new view must call `navTab()` or it inherits the previous view's highlight.
- **Two rules are spelled twice and must be changed twice**: the Quake colour
  strip (`board.js plain()` / `surfd.py web_plain()`), and the no-markup rule
  that test_board.py's private-word guard enforces by bare substring -- so a
  COMMENT containing `innerHTML` or `reason` fails the build. Both happened.
- **A missing map-difficulty catalogue reads as UNKNOWN, never as zero.**
  `map_tiers()` returns None when `momtracks.tsv` is absent and the page says
  tiers are unavailable. "0 of 64 tier-1 maps" for a box with no catalogue is a
  lie about a player, not a low score.
- **Ranking a profile is not ranking a board.** Two obvious orderings both put
  nonsense on top of a real profile: by placing it led with #1 of 1 (that
  profile has 35 such boards and 0 contested firsts), by board size it led with
  #501 of 501. It orders by `of - rk`, people beaten. Likewise `wr` counts
  first places and `wrc` counts the contested ones; the page leads with `wrc`.

### Steam accounts (Patches 612, 615, 617, 619 and 625, surfd schema 15) -- stored, and ranking on nothing

- **STORE-ONLY.** `accounts`, `linkkeys`, `linkcodes` and `linknonces` are read
  by nothing that ranks, verifies or publishes, and sv_account.qc kicks and
  refuses nobody. ROADMAP 14.3 is where that changes.
- **AN INSTALL IS ITS KEY, NOT ITS GUID (Patch 615).** Patch 612's `links` was
  keyed on the guid, and a guid is handed to any server that sends this fleet's
  `sv_guidkey` (sv_main.c:137): whoever harvested one could move the link, or
  squat it before its owner linked. `linkkeys` is keyed on the `fskey` public
  key, and every lobby call carries a signature by it: a connect's over a nonce
  THE LOBBY chose (a client-chosen one could be replayed off the wire), a
  link's over digests of the code. The guid goes along for the log and decides
  nothing; test_accounts.py has the harvested-guid arm.
- **THE STATEMENT IS rec_sign's, AND TWO LANGUAGES BUILD IT.** `rec_sign <nonce>
  <kind> - 0` signs `FTESURF-RCPT 1 / server / nonce / ticks <kind> / hid - 0 0
  / view -` in C (cl_receipt.c); `accounts.STATEMENT` rebuilds it in Python. The
  suite pins the Python bytes; ONLY `tools/p615link.py` shows the engine's
  signature verifying under them, because it runs the installed client. Run it
  after touching either side.
- **THE KIND IS THE TICK COUNT: -2 A CONNECT, -3 ASKING, -4 CONFIRMING.** A run
  signs its stamp, -1, or 0 for a kept abandon, and `SV_RecRcpt` refuses below
  -1, so no proof can be filed as a run's and no run's taken for a proof. THE
  FIRST CUT SIGNED 0 and took a receipt "only while a proof was owed": the
  review filed a stray proof as a kept abandon's receipt and had a proof eat a
  real one.
- **A LINK IS MADE BY THE KEYBOARD AND BY NOTHING ELSE (Patch 617).** Patch 615
  took the code as `link <code>` and the consent as `link <number>`, a number
  the lobby printed, on the argument that text a server left in a client
  cannot read it. A probe build whose server stuffed both commands back at the
  client linked it: the engine runs a stuffed game-code command, and game
  code's `localcmd` is above the level `rec_sign` refuses. So now `link` only
  opens a box (cl_account.qc); the code is typed into it and Enter answers
  "link this game to X?"; and NO console command carries a code or makes
  either signature. The number is still the lobby's and still signed, to bind
  the answer to the question; nobody types it.
- **`CSQC_InputEvent` IS THE ENGINE'S ENTRY AND NOTHING IN QC MAY CALL IT.** It
  sets `cl_input_real` round `CL_InputEvent`, and the box acts only while that
  is set. `vote key` feeds `CL_InputEvent` and `hud_edit ui` feeds
  `CL_InputChain`, from the console, which a server can type: both find the
  box deaf. The arm greps every .qc for a call, presses the same Enter both
  ways, and FAILS on a build with the guard removed (built and run: the
  console's Enter moved the link).
- **`rec_sign` IS A CONSOLE COMMAND, SO EVERY `localcmd` IS A ROAD TO IT.** The
  box makes its signatures only under keys, and the review still found two
  other ways to the same signature. The run's receipt (cl_replay.qc) signed
  `rec_sign <nonce> <ticks>` with BOTH taken from the server, and -3 and -4
  are tick counts: it signs nothing below -1 now. And `zone_goto` and `ghost
  speed` pasted a typed argument into a `localcmd`, where `"1;rec_sign ..."`
  is two commands at game code's level; both take a number now, and the arm's
  M echoes a marker through the old build. About fifty more `localcmd` calls
  carry text and have not been read for it. ROADMAP 14.3 opens with the real
  fix (signing as a builtin). Until then "only the keyboard" is true of the
  box, not of the client.
- **THE BOX TAKES PRESSES AND NEVER RELEASES.** The first cut copied the chat
  draft and swallowed the release of a key it took. With the box closing under
  a held key that left the game its repeats but not its release: a held `2`
  loaded a saveloc and held it, a held digit cast a vote. Now a release always
  goes on (a press the box took ran no bind, so there is nothing to undo), and
  the REPEATS of a press it took are kept from the game until the key is up.
  It keeps its own table of keys down: `chat_rep` can be set from the console.
- **ESC AFTER THE CONFIRM SAID "CANCELLED" OVER A LINK THAT WENT THROUGH.** The
  confirm is with surfd before a hand can reach Esc. The box now says
  "Linking..." and waits; an answer that outlives its patience is still shown.
- **A SECOND ESC IS THE GAME'S.** The arm dismissed an ending with Esc after an
  Esc that had already closed it; the engine opened its menu, the menu took
  the keyboard, and every later key in the run went nowhere. It dismisses with
  Backspace. A player doing the same just sees the menu.
- **FOUR TEST OVERLAYS CALL `CSQC_InputEvent` ON PURPOSE** (tools/fixtures/
  p603*_runtime.qc, rewind_navigation_smoke.py, watch_navigation_smoke.py):
  in THOSE builds a console-driven key counts as real. The arm's grep reads
  src/ only, which is what ships.
- **THE ENGINE HAS A COMMAND THAT INJECTS REAL KEYS.** `in_journal_synth` puts
  SPACE and mouse moves through `IN_KeyEvent`, the device path, with no level
  check. So consent is Enter, Y, N or Esc, never SPACE and never "any key";
  the arm runs it at the question. A new engine test command that injects
  other keys is a way round every CSQC prompt: give it `rec_sign`'s check.
- **A HELD KEY REPEATS INTO WHATEVER OPENS UNDER IT.** The Enter that sends the
  code is still down when the question arrives, and Windows repeats it. The
  box takes a repeat (`chat_rep`, cl_chat.qc) as nothing, and ignores every
  key for 0.6 s after the question appears. The arm holds Enter across it.
- **THE BOX WAS RIGHT IN THE LOG AND WRONG ON THE SCREEN, TWICE.** Screenshots
  of each state: the "would move" line sat on the footer, and with the console
  open nothing was drawn at all (`notmenu` is false under this engine's
  console window, and the HUD block is skipped), so `link` appeared to do
  nothing until the console closed. It is drawn in both branches now.
- **AN ARM THAT WAITS FOR A LINE MUST WAIT FOR A NEW ONE.** `Log.wait` matches
  after the last match, and an earlier box's "link box open" was still ahead
  of it: the arm typed into a box that was not up yet and the first key went
  to the game. It read as the box dropping a character, in one arm only.
  Count the line before sending and wait for the count to rise.
- **A RIG CLIENT HAS ITS MENU UP FROM BOOT**, and game code is offered keys only
  when nothing else has the keyboard. The arm sends `closemenu`, finds the
  window by its class (`FTEGLQuake`) and posts WM_KEYDOWN with the scan code
  in lParam: the engine maps the key from that, not from wParam.
- **THE ENGINE SIGNS ACCOUNT PROOFS, THROUGH BUILTINS, AND SAYS WHETHER A KEY WAS
  PRESSED (Patch 625).** `acct_sign(nonce, kind)` signs `FTESURF-ACCT 1` with a
  `key` line; kinds -3, -4 and -5 are refused unless the engine is inside its
  own delivery of a DEVICE's key-down to game code (`in_generic.c` marks every
  event made by `in_journal_synth` or a plugin; `pr_csqc.c` holds the flag
  round CSQC_InputEvent). `rec_sign` on the console still signs a run's
  receipt and nothing below -1. surfd refuses the old statement, so an engine
  before 625 cannot link and `cl_account.qc` says "needs an update".
  MEASURED WITH A PROBE csprogs (not in the tree: it asks for a confirm's
  signature from a console command and on any SPACE): console 0 characters,
  `in_journal_synth`'s SPACE 0 with QC's own `cl_input_real` reading 1, a
  SPACE posted to the window 213. So the engine now refuses what 617 could
  only route around by answering four keys.
- **625'S OWN REVIEWS, AND WHAT THEY CHANGED.** Engine lens: a QC error inside
  the key handler longjmps out of Host_Frame past the line that takes the
  "device's key" flags down, so the next csprogs to load signed without a key
  (the flags come down at the landing now, at every IN_Commands and with the
  VM, and the builtins want both); one press could loop the browser and all
  three link kinds (one signature and one browser a press; a held key's
  repeats are not presses); demo and QTV playback is "connected" with a
  netchan address that is whoever sent the last packet (refused). Protocol
  lens: nothing in the new start, and two older things it would not let
  ranking sit on, both fixed here: a typed code's bare digest (twelve
  characters and a salt now), and the page's number crossing in the clear
  (a digest with the client's opener now). It also asked what a rollback does
  to "links were dropped": `linkkeys.via`, and the drop at every start.
- **625'S SECOND ROUND, AND REPRODUCING A TRACED FINDING BEFORE FIXING IT.**
  Both reviewers had only READ their findings, so each went into the probe
  first, against the build they had read. The engine's: the statement named
  whatever the netchan pointed at, and one handshake packet re-points it
  under loaded game code (reproduced: a key press then signed for an address
  that game code never came from). The address is now noted when the VM is
  made and compared when it asks. And an injected key-up cleared the repeat
  latch (reproduced), so the latch moved into in_generic.c and is driven by
  device events alone. The protocol's: THE CLIENT PICKS ITS CSPROGS FROM A
  DOWNLOAD CACHE BY A 32-BIT CHECKSUM (`CSQC_FindMainProgs`), so "a key press
  is consent" was consent to whatever was in that cache. Every account proof
  now carries the SHA-256 of the csprogs that asked (statement line `code`,
  form field `game`) and surfd takes only what it can read off the lobbies'
  disk (`SURFD_GAME_CODE`). `p615link.py --foreign-code` is that arm: the
  lobby serves one file, surfd is told another, and the real engine's proof
  is refused in words the box prints. A link also lives in `keylinks` now:
  the first cut stamped rows of `linkkeys`, and older code's upsert left the
  stamp on a row it re-linked.
- **RANKED MEANS LINKED IS A SETTING (Patch 629), AND THE SUITES SAY WHICH SIDE
  THEY TEST.** `SURFD_RANKED_LINKED` is read at import; anything but `0` is
  on. The ten suites that post runs to test the board's own mechanics carry
  `os.environ.setdefault("SURFD_RANKED_LINKED", "0")` under their imports and
  post runs under any `player` they like; `test_ranked.py` has it on. A NEW
  SUITE THAT POSTS RUNS MUST PICK: with neither, its runs all land on the
  community board and its ranked assertions fail in a way that reads like a
  board bug. The mutant tool runs `test_ranked.py` after `test_accounts.py`.
  In the rig (`p615link.py`) the lobby's own probe run, fired by
  `rcon lobby_run_probe 1`, shows what the lobby SENDS (`RUNS`), and a
  scripted body in surfd's place (`SCRIPT`) shows what it SAYS to each `why`;
  a clean stored finish is not driven there (the probe is cheated on purpose:
  a clean one would be a forgery tool), so the row itself is `test_ranked`'s.
  THE Pi RUNS WITH `SURFD_RANKED_LINKED=0` UNTIL THE OWNER SAYS: check
  surfd's start line `ranked rows need a linked Steam account: ...`.
  THE LINE GOES INTO `surfd.env` BEFORE THE CODE DOES. The default is on, and
  every cron tool imports surfd and so runs its start: the first tick after
  the new file lands would move the ranked board with the line still absent.
- **629'S FIRST REVIEW, THREE LENSES, ALL THREE FOUND THE SAME ROOT AND EACH A
  DIFFERENT EDGE OF IT.** Identity was read per post, so one run could be
  split between a guid and an account (pinned per run now: `runpins`, and the
  lobby's `run_pub`). The guid is whatever a client sends, and it shared a
  column with SteamIDs (never nameable alike now, both modes). "Is a
  SteamID" was a prefix that half the range does not have (who is in
  `accounts` now). The move ran at every import under the write lock (once a
  switch-on now). What made this findable: the older suites all ran with the
  switch off, so nothing exercised a stage, a reject or a recording under an
  account until the reviewers did. `test_ranked.py` has those cases now.
  MEASURED IN THE RIG: a run that got its id on the connection is posted with
  that id and its key; with the latch line compiled out of `sv_timer.qc` the
  same check fails with the id and NO key.
  A PAUSED RUN'S KEY IS DRIVEN BY THE ARM (its P checks, main mode): leaving
  parks the run with its key; with the slot's `key` line rewritten to another
  key the same connection is refused `!resume` and `!discard` and the slot
  stays; with the line put back it prints "run resumed ... session 2". The rig's
  server is not a lobby, so the slot is `@local` and only client 1's: the arm
  waits out the zombie slot before it reconnects (it came back as client 2 the
  first time, and "no paused run" looked like a refusal to a loose needle).
  NOT DRIVEN: the gate before surfd has been heard on a map (traced).
- **629'S SECOND ROUND.** The pin gave an account to any later post on the
  same guid, key or no key (it keeps the key now, and a post without it is not
  stored). The one-time move could be raced by two starts into DELETING what
  it moved, and its "done" marker could be flipped by a cron tool before the
  service restarted (every start now, lock first, off an index). A run begun
  before the proof landed could never rank (the lobby adopts the key for a
  run it minted itself).
- **fteqcc DIES WITH A SEGMENTATION FAULT, AND NO OUTPUT, ON A FUNCTION CALLED
  BEFORE ANY DECLARATION OF IT.** `build.ps1` says only "fteqcc failed on
  sv_progs.src". Lobby_GuidOk was defined 500 lines below its first call; a
  prototype above fixed it. Bisect by what was added last, not by the three
  expressions that look exotic (which is where the first twenty minutes went).
- **THE RIG ARM FAILS WHEN THE OWNER IS PLAYING.** Two of eight main-mode runs
  on 11 Oct failed in the link steps with keys dropped or thirty seconds
  late: `Get-Process ftesurf64` showed the owner's own game up on a live
  lobby since five minutes before the first. Three of three passed once it
  was closed. Look for his game before a run, and before believing a failure.
  The arm now puts the desktop's clipboard back if one of its sign-in
  addresses is what it left there.
- **BANS ARE A TIER, NOT A FILTER (Patch 633).** A banned account's rows
  stand on `banned:<tier>` in `runs` and `replays`. Before adding a reader,
  name its tiers (every one does); a reader of "all tiers that are not
  imported" would list banned rows. `test_ranked.py` section 8 grades the
  public routes by their own words: with no file on disk a PUBLIC recording
  answers "no recording on this node" and a banned one "no such run", so a
  404 alone tells nothing. `test_admin.py` fails two rcon packet-count checks
  on main as well (259 ok either way): not this patch's.
  ITS REVIEW (two lenses) found that the first cut's "review goes on working
  inside the family" was true of re-standing and FALSE of stage parking
  (`restage` named `ranked`/`community`), so a reject made while banned came
  back public at the unban and a clear made while banned stayed hidden; that
  the recording behind stage rows (kind `evidence`, tier '') was still
  served; that a ban committed while a run was being filed left that run
  live (7 of 40 under a stress built to hit it); and that the page's list
  re-sorted under a second click. Section 8's first fixture had NO FILE ON
  DISK, so its replay was unbound, `_run_rejected` was false and the stage
  path never ran: 8b writes a real recording.
  THE FINAL CHECK of those fixes found three low corners, all in the new
  path for a run filed across a ban, each needing a second coincidence and
  none produced unforced: the late pass acted on a ban it had read before it
  held the lock (an unban committing meanwhile was followed by a full
  set-aside; it reads again under the lock now); if the pass never ran, or
  timed out on the lock, the row stayed live (every start repairs it now,
  `bans_now`); and a tie re-filed over the same recording across the ban
  loses the row's link to its recording (BACKLOG, not fixed). Its fuzz, 200
  sequences of ban, unban, review and sweep against a no-ban control, found
  no difference; with the family rule forced back to the old code 49 of 200
  differ.
  `tools/mapwr.py`'s check runs only where `tools/` is beside `surfd/` and
  prints `skip ... NOT MEASURED` in a copy of `surfd/` alone (a mutant's);
  with its tier filter removed by hand it fails with `banned:ranked` as the
  map's best.
- **629'S LAST CHECK.** A file an earlier cut had started on had `runpins`
  without its key column and answered 500 to every run with an id (the start
  adds it and drops those pins). A post surfd holds back answers `why: held`
  and the lobby says "not submitted" (it had said "unranked: no Steam account
  linked" to somebody who had one).
- **SCHEMA 16 BUILDS AN INDEX ON `runs`** (`runs_live`): one scan of three
  million rows under the write lock, once, at the first start of the new
  code. Deploy with nobody on a lobby; a run posted in those seconds waits.
- **625'S THIRD ROUND FOUND NO WAY TO A WRONG LINK, AND STILL CHANGED THINGS.**
  Engine: the address a VM may sign for is noted when its SERVERDATA arrives,
  with whether that was a live connection, so a VM made in demo playback or
  with no connection never signs; the press latch is cleared by
  `Key_ClearStates` (X11 and D3D11 release keys on a focus change without the
  input queue, and Enter's release goes to the browser the same press
  opened); "one file of code" is the VM's own `numprogs`, not a guess from
  file names. surfd: the old link table is EMPTIED at each start, not dropped
  (the live code, rolled back onto a 15 file without it, answered 500), and
  `keylinks` is made at every start (a file an earlier cut stamped 15 had
  none); a start's kept signature is asked "is that game code ours" again
  when a sign-in opens it; a game code file is hashed through one handle with
  its size and time taken before and after; one unreadable file makes an
  unmatched proof "cannot check", not "foreign".
- **AFTER A PROGS DEPLOY, READ surfd's LOG FOR THE GAME CODE IT EXPECTS.** It
  logs `account proofs must name game code: <file> <16 hex>; ...` whenever
  that changes, each file with its hash or `is absent` or `CANNOT BE READ`. If the lobbies serve a csprogs surfd cannot read (another path, a
  permission), every link and every connect answers `later` or `game`. The
  default path is `<SURFD_GAME>/ftesurf/csprogs.dat` and `.prev`.
- **`acct_browse(opener)` OPENS ONE PAGE.** The address is the engine's constant
  with the opener after it; game code cannot name another, and it works only
  under a device's key press. `-nobrowse` on the command line prints the
  address instead: every harness passes it (p615link.py does), because the
  desktop it runs on is the owner's. A switch and not a cvar: a server sets
  cvars. Linux is `xdg-open` by fork and exec, COMPILED BY NOBODY YET.
- **THE ARM NEEDS THE ENGINE UNDER TEST:** `p615link.py --client <exe> --server
  <exe>`; plugins are the ones beside the client. Its H used to claim a code
  from the console and is now the engine refusing to.
- **A START IS ONE KEY PRESS AND NAMES ITSELF.** The code is a digest of the
  opener (`Account_CodeOf`, surfd's `start_code_of`), so the lobby sends the
  client nothing before the question: `acct_start` and `acct_go` are gone,
  and with them the code a rewritten connection could swap. The first start to
  bring a code holds it; a watcher who registers it first gets a start their
  key never sealed, which the real opener does not open.
- **THE LINK STARTS IN THE GAME (Patch 619), AND A NUMBER TIES THE BROWSER TO
  IT.** The start's code is in an address and on the wire: public, and it links
  nothing. The page the player signs in on shows four digits
  (`linkcodes.shown`); the box asks for them under the account's name; surfd
  compares, one try, and a wrong one spends the start. THE FIRST CUT TIED THE
  TWO BY ADDRESS (a browser at the address the game started from, nothing
  typed), then by address plus "the account's first install". The review
  walked a victim's account onto somebody else's install with one sign-in:
  an address is a household, a campus or a carrier's NAT, and at rollout every
  account is one with no install. Do not bring the address back as a shortcut.
- **A START'S SIGNATURE IS CHECKED WHEN THE BROWSER ARRIVES, NOT WHEN THE START
  DOES.** The page's number is typed into the game and goes to the lobby in the
  clear. That is harmless only if a player can never be signed in for
  somebody else's start, and game code cannot tell its own start from another:
  it does not know its own key, and every line from the lobby can be rewritten
  on the way. So the client makes a secret (the opener, `&k=` in the address),
  and its key signs the lobby's nonce WITH it. surfd keeps that signature
  (`linkcodes.seal`) and verifies it with the opener a sign-in brings. THE
  FIRST ANSWER WAS A DIGEST OF THE OPENER SENT WITH THE START, and it does not
  work: whoever sees the digest can register it under their own key. What
  cannot be copied is a signature over something its watcher never saw. The
  cost: `/api/link/start` stores a claim it has not verified, so "one start a
  key" is enforced at sign-in, and a wrong signature is found there too.
- **THE OPENER IS THE ENGINE'S RANDOM BYTES HASHED WITH A POOL OF THE VM'S OWN**
  since Patch 625 (`acct_random`). The pool, which was all of it in 619:
- **THE POOL IS FRAME TIMING, HASHED** (`Account_Stir`: every frame's `cltime`,
  `frametime` and `random()`, and every key event, into a SHA-256 chain).
  Measured on this machine, 11 Oct: `frametime` differs frame to frame in its
  sixth and seventh digits (0.00998342875, 0.0100200288, 0.0100286286 ...),
  so a few seconds of frames is far more than the 96 bits taken; the mouse's
  moves are folded in as well. THE START'S SIGNATURE IS AN OFFLINE TEST FOR A
  GUESSED OPENER (key, nonce and signature all cross the wire), so everything
  rests on that pool: game code has no random source of the engine's, and if
  it gets one, use it. Opening a start at sign-in has a signature allowance of
  its own (`verify-open`), so a flood of link steps cannot strand a player who
  has just spent a Steam assertion.
- **THE BOX TAKES NO KEY A PLAYER NEEDS TO REACH A BROWSER.** The first cut took
  Tab for "I have a code": Alt+Tab is how the player gets to the browser, and
  default.cfg binds Tab and Enter (`+showscores`, `say`). The prompt that comes
  up by itself and the wait for the browser take Enter and Esc and nothing
  else (`Account_Light`); the question for a start takes digits, Backspace,
  Enter and Esc, and NOT Y or N.
- **A START IN FLIGHT IS FORGOTTEN ON CANCEL** (`Account_Unwait`). Esc between
  the Enter and surfd's reply used to leave the request out; its reply then
  armed ten minutes of waits for a box that had closed. The client also sends
  `cmd link cancel` when its own 20 s runs out on anything but a confirm.
- **THE LOBBY'S NUMBER FOR A START LIVES AS LONG AS THE START** (`acct_pin_t` is
  a deadline now). It is issued while the player is still in the browser; with
  617's 90 s it was dead before they got back.
- **THE SIGN-IN ADDRESS IS THE CLIENT'S OWN CONSTANT.** `acct_go` carries a code
  and nothing else; what is copied is `ACCT_LINK_URL` with it. A server that
  could put an address on the clipboard under "paste this into your browser"
  would be choosing the sign-in page. The server's `lobby_link_url` cvar is gone.
- **THE PROMPT IS ONCE A GAME, NOT ONCE A MAP**: `_acct_prompted` is a cvar
  because CSQC globals die with the map. A map change during the browser step
  closes the box for the same reason; `link` starts again.
- **`p615link.py`: A KEY THE GAME OWNS HAS TO PRINT.** "The prompt leaves the
  game its keys" is graded on `bind w "echo gamekey-w"` and a count of that
  line: once with the prompt up, twice once the wait is.
- **`accounts_mutants.py` PINS A MUTANT TO A FUNCTION** (fifth element) where
  two share a line. Thirteen older mutants went BAD the day `/api/link/start`
  repeated `/api/link`'s limits; the shared lines became `link_call` and the
  rest are pinned. `expiry-pre` and `spent-pre` no longer survive alone:
  `/api/link/wait` reads through `live_code` and nothing else.
- **`test_admin.py` FAILS TWO CHECKS ON AN UNTOUCHED main** on this machine
  (11 Oct, `fec0820`: the amplification-guard message, and "three snapshots
  cost no more packets than one: got 8, want 4"). Not from the accounts work;
  nobody has looked.
- **A TYPED CODE NEVER REACHES THE LOBBY.** The client sends `code_tag(code)` and
  signs `ask_nonce(code)`: three tagged SHA-256s, so the wire's is not the
  signed one. The first key to ask with a code holds it (`linkcodes.claim`);
  only that key can confirm. A code is 50 bits (ten characters since Patch
  617) and the tag unsalted, so the tag is NOT a secret-keeper: the claim is.
- **A GAME-CODE COMMAND'S NAME IS FREE ONLY UNTIL A SERVER TAKES IT.** "Grepped
  the engine and plugins" checks a namespace that servers add to at run time: a
  cvar named `link` makes `registercommand` fail silently and the typed line a
  cvar set. cl_account.qc reads `cvar_type` BEFORE registering and says so; and
  since Patch 617 a typed `link` has no code after it to lose.
- **A CONNECTING CLIENT'S COMMANDS REACH QC BEFORE ITS EDICT IS CLEARED.** The
  engine reuses the slot as it is, clears it at the newcomer's `spawn`, and
  runs ClientConnect at `begin`; `SV_ParseClientCommand` is live from
  `cs_connected`. So per-client state is reset in ClientDisconnect (which also
  frees its zoned strings: the engine's clear zeroes them unfreed), and the
  account commands wait for `acct_here`, set by ClientConnect. `vote_here` and
  `run_inserver` are the same guard.
- **THE GAME CLOCK JUMPS AT CONNECT; TIME A CLIENT-SIDE WAIT WITH `cltime`.**
  CSQC's `time` read 33.7 on the first frame and 116.5 on the next, so the
  connect ask's 3-7 s wait fired at once and its 8 s retry could fire with it.
  Two asks minted two nonces, the first signature was posted under the second,
  and surfd refused it: 1 reconnect in 9, silently. Found only because one arm
  run failed and the next did not; forced by the arm's L (one console line, two
  asks), which the unfixed build fails with two `issued` lines and `proof`.
  The server now keeps ONE nonce in force while a proof is owed.
- **THE SIGNED ADDRESS MUST BE OURS, AND A PRIVATE ADDRESS IS NOBODY'S.** The
  statement names the server the CLIENT is talking to; surfd accepts what
  `SURFD_PUBLIC_HOST` resolves to, on the asking lobby's port, plus
  `SURFD_LINK_HOSTS`. Measured on the Pi's 23 receipts (2026-10-10): 22 signed
  the public address, 1 the LAN's, and the port equalled the lobby's in all 23.
  DO NOT LIST THE LAN ADDRESS IN PRODUCTION: 192.168.1.102 is also a machine on
  every other LAN that numbers one so, and a player who joins a server there
  signs exactly the string this fleet's LAN players would. A name that has
  never resolved answers `later`, not `server`: a third verdict.
- **A PROOF ARRIVES AS `rec_rcpt`, AHEAD OF SV_RecRcpt** (sv_player.qc's
  dispatch). `Account_Proof` takes every receipt whose ticks is -2, -3 or -4,
  owed or not, and nothing else: a run-shaped receipt goes to the run's handler
  even while a link is owed (the arm's J), and a build that takes every receipt
  leaves a finished run with none (`p615link.py --receipt` fails on it: the
  mutant was built and run against the first cut's dispatch).
- **A REPLY WITH CODE 0 AND NO BODY IS NOT AN ANSWER.** A request that never
  connected reaches `URI_Get_Callback` as 0 too. surfd puts `acct` in every
  lobby reply and sv_account.qc treats its absence as silence, never as "not
  linked". `ClientDisconnect` clears the request id: the engine does not clear
  an edict until its next player spawns, and an answer still out would find them.
- **NOTHING A SERVER STUFFS MAY REACH `localcmd` UNCHECKED** (cl_account.qc). A
  stuffed command runs BELOW the game code's own level, so pasting its argument
  into a command line hands the server ours. The nonce is 32 lowercase hex or
  dropped; a typed code is its eight characters or never sent.
- **THE CONNECT ASK IS NOT IN THE HUD BLOCK.** `Account_Frame` first sat beside
  `Banner_Frame`, which an open menu skips (`notmenu`), and a headless client's
  builtin menu is open from boot: the arm's connect proof never happened while
  every `link` worked. It is called beside `Rec_ViewFrame` now.
- **A RIG RUNS THE PROGS YOU HAND IT.** The arm's first full failure was a
  build made before the last edit to sv_account.qc. `build.ps1 -NoDeploy`
  writes a NEW `rig/build-nodeploy-<guid>` each time; the driver prints each
  .dat's hash, so read them, and delete the old build dirs.
- **A STEP THAT DROPS A TABLE RACES ITSELF, AND THE STEP THAT MADE IT.** Schema
  13 dropped the empty `links`; test_board.py's two-threads-migrating arm caught
  the second thread finding it gone (`no such table`), and the step now
  tolerates exactly that. THE SECOND HALF SHIPPED: a process still in step 12's
  script reached `CREATE INDEX ... ON links` after another had finished 13.
  The same arm met it ONCE, in the deploy stage on the Pi, having passed every
  run on the desktop, and `surfd-deploy.ps1` refused to install. Step 12 no
  longer makes the table. A thread arm finds a race by luck: test_accounts.py
  now lets a second connection finish both steps at each of their six
  statements in turn (sqlite's trace hook), and fails on the old script at the
  third. gunicorn and a cron tool do start together on a deploy.
- **THE CODE GOES BROWSER -> GAME, AND IT IS A BEARER TOKEN.** The other
  direction lets a link sent to a victim bind THEIR Steam account to the
  sender's install. This direction still links whoever types the code first,
  so: every link names the account and waits for the number, a move says where
  from, and A BAN MUST NEVER PIN AN
  INSTALL TO ITS ACCOUNT. The first cut refused to move a banned account's
  install, and the review turned that into a weapon: link a victim's install
  to a throwaway account, get it banned, and the victim is locked out.
- **A STRAY ASSERTION IS BURNED, BEST EFFORT.** A valid Steam reply that lands
  in a browser without the state cookie is recorded in `linknonces` and
  refused. Without that, a victim who signed in through a link they were sent
  could hand the resulting address back to the sender, who holds the cookie.
  ROUND 2 SHOWED WHAT IT DOES NOT COVER: a reply refused BEFORE that line (a
  rate limit, nginx's, a lock) is not recorded and stays usable for
  `steam.NONCE_SKEW` (120 s). No allowance keyed on the victim closes that; it
  is in BACKLOG, the sequence is in the private tree's
  `checkpoints/steam-accounts-20261010.md`, and ROADMAP 14.2's install list is
  the real answer. Made-up strays stop
  being recorded at half the table so they cannot close sign-in, and a row
  lives `NONCE_KEEP` (5 min): the first fix kept them an hour and one burst
  shut sign-in for that hour. A link scanner that fetches the address first
  burns an honest player's reply; they start again.
- **EVERY LOBBY POSTS FROM ONE ADDRESS**, so a per-source limit on a lobby
  route is one bucket for the fleet. (It is the Pi's LAN address,
  192.168.1.102, not loopback: surfd's access log, 10 Oct. This line said
  127.0.0.1 from the rig.) The per-player limits come first and are keyed on the
  client ADDRESS the lobby reports (`ip`), not the guid: a guid is whatever the
  client says, and one player could spend another's. 12 connects and 8 link
  steps a minute an address, which is also every signature it can have checked.
- **A MUTANT THAT SURVIVES IS A MISSING TEST OR A CHECK NOBODY NEEDS.** The v2
  sweep left eight. Five wanted tests (a seven-digit number, a re-link to the
  same account, a move's date, the buckets, the write lock); one wanted a pair;
  and two checks changed no answer and were deleted: a tag's shape (it is only
  ever compared) and a per-address signature budget the two limits above
  already bound. The lock's test bans the account from a second connection
  inside the step, through sqlite's trace hook, and must be refused the lock.
- **EXACT SETS, AND `fullmatch`.** The reply must hold exactly Steam's ten
  fields and its signed list exactly Steam's seven. Everything received goes
  back to Steam to be checked, and whether Steam's parser folds
  `openid.claimed.id` onto `claimed_id` is NOT known; nothing unlisted is sent.
  `re.match(r"^...$")` accepts a trailing newline: a nonce with one was a second
  replay key until every pattern here became `fullmatch`.
- **`SURFD_BOARD_URL` IS THE BROWSER'S ADDRESS** (`https://proto.bar/ftesurf/board`),
  not surfd's `/board`. Realm and return_to come from it. The cookie is
  `__Host-ftl` with Path=/ because the board shares its origin with other
  applications; a Flask test client never
  returns it, so test_accounts.py sends the header itself with
  `use_cookies=False`, or its jar replaces it.
- **nginx allows GET (and so HEAD) only under `/ftesurf/board/`**, so the
  sign-in is three GETs and no form, and the handlers refuse HEAD themselves:
  Flask answers HEAD on a GET route, and one would spend a sign-in unseen.
- **THREE VERDICTS.** `steam.Refused` (400) and `steam.Unavailable` (503) are
  different pages. `SURFD_STEAM_KEY` travels in a URL: `steam.http` raises with
  a status or an exception's type name, never its text, and `http.client`'s
  own exceptions are not `OSError` (a cut-short reply was a 500 until caught).
- **A CAP CHECKED BEFORE ITS PRUNE NEVER EMPTIES.** `linknonces` is pruned
  before it is counted; the first cut pruned inside the insert the cap had
  already refused, which is a permanent lockout once full. The suite found it.
- **WHAT THE LOGS HOLD NOW.** surfd.log names SteamIDs and installs' 8-hex
  public ids. gunicorn's and nginx's access logs hold each sign-in's return
  address: SteamID beside client address. `run.sh` sets umask 077 for the first;
  the Pi's existing `logs/gunicorn.log` was 644 and is chmodded at deploy.
- **`accounts.py` and `steam.py` hold no module state** (the suites pop `surfd`
  from sys.modules per case and these two stay loaded), and surfd.py imports
  both at module top: a `surfd-deploy.ps1 -Only` that ships surfd.py must ship
  them too, or the worker cannot boot. Loud on purpose; a guarded import would
  deploy "successfully" without the feature.
- **NOT COVERED BY AN ARM:** the browser's side of the cookies, more than one
  client on a lobby (every arm has one), and a real player's `link` on a real
  lobby (lextest.md).
- **MEASURED AGAINST REAL STEAM (2026-10-10):** a refusal's exact bytes
  (`ns:...\nis_valid:false\n`, 0.3 s from the desktop and from the Pi), that a
  302 is not followed, a bad key's 403, and one profile through the real key.
  A POSITIVE ASSERTION: Lex signed in at 10:41 UTC the same day and the page
  showed his code; the row carries his persona and avatar. So Steam's real
  reply is exactly the ten fields and seven signed names the exact-set check
  demands.
- **DEPLOYED 2026-10-10 10:20 UTC (FTESurf `76cfd63`), surfd only.**
  `surfd-deploy.ps1 -Ref 76cfd63 -Only` the seven files the patch owns
  (accounts.py, steam.py, surfd.py, run.sh, test_accounts.py, test_board.py,
  web/board.css): the Pi's other differences from main are 38 test files and
  an old `surfd.nginx` copy from earlier `-Only` deploys, left as found. All
  twelve staged suites pass on the Pi (Python 3.11, Flask 2.2), the seven files
  hash-match, master 2479950 SIGHUP'd, `schema migrated 11 -> 12` and `surfd
  ready` at 10:20:14, /health 12 lobbies. `surfd.env` gained `SURFD_STEAM_KEY`
  and `SURFD_BOARD_URL=https://proto.bar/ftesurf/board` (backups
  `surfd.env.bak-pre612-*`, mode 600) and `logs/gunicorn.log` went 644 -> 600;
  run.sh's umask only acts at the next start. Read back live: the four tables
  exist and are empty, `/ftesurf/board/link` is 200 under the board's CSP, the
  redirect lands on Steam's own sign-in form with realm `https://proto.bar`, the
  cookie is `__Host-ftl` (Secure, HttpOnly, Lax, Path=/, 600 s), a return with
  no assertion is 400 and a HEAD 405, `/api/account` and `/api/link` are 404
  through both vhosts and answer on loopback with the key. No lobby, progs,
  binary or config changed. ROLLBACK: put back the four
  `*.pre76cfd63-20261010-211806` files and SIGHUP; the old code runs on the
  schema-12 file (review C measured it) and never looks at the new tables. The
  database backup is `data/surfd.db.bak-76cfd63-20261010-211806` (its stamp is
  local time).
- **DEPLOYED 2026-10-10 13:45 to 13:49 UTC (FTESurf `3adb6f8`, Patch 615):
  surfd, the Pi's twelve lobbies, both Windows installs.**
  THE FIRST ATTEMPT WAS REFUSED, 13:31Z: `surfd-deploy.ps1 -Ref 6fc1695`
  stopped at its suite stage on test_board's two-thread arm and installed
  nothing (the migration race above; `3adb6f8` is the fix).
  surfd, 13:45Z: `-Ref 3adb6f8 -Only` accounts.py, surfd.py, test_accounts.py,
  test_board.py, web/board.css. Twelve staged suites pass on the Pi, the five
  files hash-match, master 2479950 SIGHUP'd, `schema migrated 12 -> 13` and
  `surfd ready` at 13:45:47, /health 12 lobbies. Read back: schema 13, `links`
  gone, `linkkeys` empty, `linkcodes.claim` there, the one account row intact,
  `SURFD_LINK_HOSTS` unset, `SURFD_PUBLIC_HOST` (play.proto.bar) resolving on
  the Pi to 180.150.62.57; the page 200 and an unlink with no token 400 through
  proto.bar; keyless POSTs to both `/api` routes 403 on the host.
  Lobbies, 13:47Z: `build.ps1 -Jobs 8 -Pi` from the clean worktree. 12 rows, 0
  players. `qwprogs.dat` `199ffdd8` (1018110 bytes) and `csprogs.dat`
  `a28719be` (5007410), hash-verified on the Pi; the previous pair kept as
  `.prev` (`5e7fd33b`, `7dca72dc`: Patch 613's); all 12 restarted.
  LIVE, ONCE: `tools/pi_lobby_smoke.py --addr play.proto.bar:27510`, a rig
  client with a new key and no csprogs, was served `a28719be`, drew the board,
  logged no QC error, and 18 s after connecting was told "this install is not
  linked to a Steam account". surfd's access log has that lobby's `POST
  /api/account`, 200, 21 bytes, at 13:47:55: the engine's signature naming
  180.150.62.57:27510 verified on the Pi and the address check passed.
  Windows, 13:49Z: qwprogs.dat/.lno and csprogs.dat/.lno into
  `C:\FTESurf\ftesurf` and `C:\FTEQuake\ftesurf`. Their `.prev` is now the
  Patch 613 pair; the Patch 608 csprogs (`69515b32`) is no longer kept.
  menu.dat (`d3889177`) and the binaries untouched. No game was running.
  NOT DONE LIVE: a link. Nobody has typed `link` on a real lobby (lextest 00).
  ROLLBACK: lobbies, the `.prev` pair and a restart. surfd, the five
  `*.pre3adb6f8-20261011-004334` files (stamp local) and SIGHUP, NOT MEASURED
  on a schema-13 file: 612's two `/api` routes read `links`, which is gone,
  though no Patch 613 lobby calls them. The database backup
  `data/surfd.db.bak-3adb6f8-20261011-004334` is schema 12, taken 13:43Z.
- **DEPLOYED 2026-10-10 15:49 to 15:52 UTC (FTESurf `7c1161c`, built at
  `2dd135a`, Patch 617): the Pi's twelve lobbies, both Windows installs, surfd.**
  It waited eleven minutes on the owner, who was on a lobby: `-Pi` refuses
  with a player on, and no file goes into an install under a running game.
  Lobbies, 15:49Z: `build.ps1 -Jobs 8 -Pi` from the clean worktree. 12 rows, 0
  players. `qwprogs.dat` `092f9880` (1017194 bytes) and `csprogs.dat`
  `4355bdf0` (5098190), hash-verified on the Pi; the previous pair kept as
  `.prev` (`199ffdd8`, Patch 615's, and `ce6397a5`, Patch 614's); all 12
  restarted.
  Windows, 15:49Z: the same two progs and their `.lno` into both installs;
  `.prev` is the pair above; menu.dat (`19874c5a`), binaries, plugins and
  default.cfg untouched. The only games running were another session's rig
  copies.
  surfd, 15:51Z: `-Ref 2dd135a -Only` accounts.py and test_accounts.py (codes
  are ten characters, the page's instructions). Twelve staged suites pass on
  the Pi, both files hash-match, master 2479950 SIGHUP'd, `surfd ready`
  15:51:49, /health 12 lobbies. No schema change.
  LIVE, TWICE: `pi_lobby_smoke.py --addr play.proto.bar:27510` was served
  `4355bdf0`, drew the board and was told how to link in the new words. Then a
  rig client with a new key opened the BOX on that lobby, typed a made-up code
  with real key presses and was told "That code is not valid or has expired":
  surfd's log has the lobby's `POST /api/link`, 200, 30 bytes, at 15:52:37.
  `linkkeys` still holds its one row.
  NOT DONE LIVE: a link made in the box. Only the owner has a Steam account to
  do it with (lextest 00).
  ROLLBACK: lobbies and installs, the `.prev` pair (Patch 615's qwprogs with
  Patch 614's csprogs is a pair that ran from 15:06Z to 15:49Z). surfd, the two
  `*.pre2dd135a-20261011-024936` files and SIGHUP. Database backups: this
  deploy's `surfd.db.bak-2dd135a-20261011-024936`; the Patch 615 one was
  removed after it, the owner having asked for the redundant ones to go.
- **DEPLOYED 12 Oct 2026, 02:28 to 02:29 UTC (FTESurf `3fdd401`, Patch 667;
  engine `17b11bc13`, tag `patch-667`): THE CLIENT EXE, menu.dat AND csprogs.**
  The engine commit was stamped before ftequakers main moved (Patch 670's log
  entry), so it is MERGED there (`91465d783`), not rebased: the binary names
  `g17b11bc13`. Stamp `git-7249-patch-667-0-g17b11bc13`, sha256 `72feb6d5`,
  built clean in this session's `eng` worktree by the recipe under Patch 645.
  Lobbies, 02:28Z: `build.ps1 -Pi` from the pushed tree, nobody on, csprogs
  `a7810a87` hash-verified on the Pi and all 12 restarted. THAT csprogs IS
  PATCH 670's CLIENT CODE WITH 667 ON IT (670 was pushed and put on the Pi by
  its own session at 02:08Z, `e2f8a9c1`, which is now `.prev`); qwprogs
  `915dfa31` went up as the same bytes 670 had put there.
  Windows, 02:29:26Z, no game running, under the rig lock: both installs'
  csprogs `a7810a87` (`.prev` `ce9e7607`) and menu.dat `a87b88ca` (`.prev`
  `10cba3c1`), and the client as `C:\FTESurf\ftesurf64.exe` and
  `C:\FTEQuake\fteqw64.exe` (`.prev` the patch-658 client `4faa7ff4`).
  `fteqwsv64.exe`, the plugins and default.cfg untouched.
  FOR PATCH 670's SESSION: its Windows half was "pending quiet" with a guarded
  script. The installs now hold 670's client code inside `a7810a87`, so that
  script's csprogs guard will refuse, rightly. THE INSTALLS' qwprogs IS STILL
  `76e00522`, NOT 670's `915dfa31`: a game hosted from this PC predicts its
  boosters the old way (670's own note: an older server is all-unknown and
  fails closed). That file is 670's to place.
  ON THE STAMPED BYTES, before the installs: p667paste 16 of 16, p655text 17
  of 17, p663profile 38 of 38, p653box 14 of 14, p647boot 8 of 8; on release
  0.1.24's client p663profile 38 of 38 and p667paste's control. After: the
  lobby smoke on 27510 was served `a7810a87` and drew the board on 0.1.24's
  client and on the new one, and `test_p645lines.py` read 28 of 28 on the
  installed files (give `runlines_smoke.py` an ABSOLUTE --output-dir: a
  relative one timed out with no log, the client having been given a basedir
  that was not there).
  TWO ARMS' POINTER CLICKS FAILED TWICE ON THESE BYTES AND IT WAS THE OWNER'S
  MOUSE: he had just closed his game. `GetLastInputInfo` (scratch
  `tmp/idle.ps1` in this session's task root) said the desktop had been in use
  until the minute the second run ended; with it idle both passed. Posted
  messages and SetCursorPos do not count as input there, so the figure is the
  owner's alone: read it before and after any arm that moves the pointer.
  The same hour the keyboard-only arms passed throughout.
  NOT SEEN: the owner pasting; a release (0.1.24's players have no paste).
  ROLLBACK: the three `.prev` files in each install (exe, menu.dat, csprogs),
  as a set: the old menu.dat on the new exe is fine, the new menu.dat on the
  old exe pastes nothing. Lobbies: `csprogs.dat.prev` is 670's own build.
- **PASTE (Patch 667): THE ENGINE ASKS, AND A CONSOLE LINE'S LEVEL IS NOT A
  WALL.** QC never reads the clipboard. A field calls `sui_paste_ask` (the
  game's `clipboard_get`) or the menu's `clipboard_paste` under a V or an
  Insert going down; the engine judges the chord (its own key state and
  `IN_RealKeyDown`), reads the clipboard itself, and with a server connected
  or a demo playing puts ONE PROMPT for both VMs (`pr_clcmd.c`): yes is a
  device's Y after 0.35 s of drawn frames, anything else a no. A yes comes
  as `IE_PASTE` (8) events: `CSQC_InputEvent` hands each character to the
  link box, a chat draft, the profile's field or the name, in that order;
  `Menu_InputEvent` to `sui_paste_char`, and the field that draws with the
  keyboard takes it. With nobody about the menu is answered at once.
  A NEW BOX GETS PASTE BY (1) asking under `scanx == 'v' || scanx == K_INS`
  and returning if the ask says chord, and (2) a branch in `CSQC_InputEvent`'s
  IE_PASTE block. Do not read a control code 22 yourself: the engine is the
  only judge.
  THE FIRST DESIGN WAS WRONG, AND ITS REVIEW SAID SO: "keep servers off the
  menu's console commands, then the menu may paste" (655's note). The
  refusal is there (`MP_ConsoleCommand`, for registered commands and for the
  unknown words cmd.c offers it), but an alias could carry a server's text
  to the player's level (closed in `cmd.c`), and nobody has shown the other
  roads shut. So that gate is called hardening wherever it is described, and
  the clipboard has the prompt. The private checkpoint has the conditions.
  ON AN ENGINE BEFORE 667 (release 0.1.24's) both builtins are missing:
  `checkbuiltin` says so, nothing asks, and the V is a letter. The arms tell
  which exe they were given by `clipboard_paste` in its bytes.
  RIG FACTS. A posted Ctrl+V is a chord to the ENGINE (it reads its own key
  state) though the character with it is a plain v. On a listen server the
  console's `stuffcmd <name> <text>` IS stuffed text at the server's level
  (its "safe list" refuses only `;` and newlines). `aliaslevel` clamps to 29
  from the console, so an alias cannot stand in for a server. The menu over
  a game wants `togglemenu` before `ui_name screen`. RUN THE ENGINE BUILD
  AND AN ARM IN SEPARATE SHELLS: the build puts msys first on PATH and
  `python` becomes msys's.
  A rig that types `ui_*` on stdin, in a config or on the command line is
  the player's level and is unaffected; one that had a server or game code
  run a menu word would be refused (none did: src, cfg and tools searched).
- **DEPLOYED 12 Oct 2026, 00:15 to 00:23 UTC (FTESurf `4519bdb` and `0464e0f`,
  Patches 665 and 666): surfd, then csprogs.** surfd: `surfd-deploy.ps1 -Ref
  4519bdb -Only` surfd.py and test_web.py, the whole suite green on the Pi,
  backup `data/surfd.db.bak-4519bdb-20261012-111517`, both files hash-matched,
  `surfd ready` 00:18:04Z; asked once on the host: the maps list (1,370 rows,
  6.0 s cold), a search, a breakdown, `ct=1` (65 maps), `ct=u`, `on=` (four
  legs), the site's maps list; no error line. THE UNRATED COUNT MOVED UNDER
  THE CHECK: 845 at 00:18Z and 953 five minutes later, as the map index took
  in what Patch 664's watcher had fetched that hour; two players asked
  together agree.
  csprogs, 00:20Z: `build.ps1 -Pi` from the pushed tree, nobody on any of the
  12 lobbies, `ce9e7607` hash-verified on the Pi (qwprogs `35fda5eb` swapped
  for itself), all restarted; both Windows installs 00:20:12Z under the rig
  lock, guard on Patch 668's `ddf40c04`, which is `.prev`. menu.dat
  (`10cba3c1`), default.cfg and the exes untouched.
  LIVE, on the engine 0.1.24 shipped (`183faf44`): `pi_lobby_smoke.py --addr
  play.proto.bar:27510` was served `ce9e7607` and drew the board; then a test
  player on that lobby (scratch `tmp/p666_live.py` in this session's task
  root) opened the most-timed player's tier 2 (105 of 117 finished, a hundred
  held), the unrated (71 of 952) and their seven times on surf_kitsune in the
  board. NOT SEEN: a person doing any of it by hand.
  ROLLBACK: lobbies and installs, the `.prev` csprogs (668's), which asks
  neither new form; surfd, the two `*.pre4519bdb-20261012-111517` files and
  SIGHUP.
- **THE PROFILE'S TIER LISTS AND THE BOARD'S PLAYER VIEW (Patch 666).**
  cl_profile.qc holds two more asks beside the breakdown's: `Profile_Tier*`
  (`pf_ct`, one tier's maps for whoever `pf_who` is, a hundred a page, a
  thousand held) and `Profile_On*` (`pf_on_who` on `pf_on_map`, 96 rows). A
  TIER STAYS ON SHOW for the next player and is asked for when their
  breakdown lands: surfd has their rows ranked by then, and asked beside it
  the Pi would rank them twice. The card opens on the results.
  The board draws `Profile_DrawOn` in its table's place while `pf_on_who` is
  set, and gives the table back when the leg or the source moves BY ANY ROAD
  (`sb_on_leg`, `sb_on_tab`, compared at draw: the arrows, `scores leg` and
  the finish's follow moved them under the view in the first cut).
  A PICK IS ITS FRAME'S ONLY HAND-OFF (`Scores_SearchPick` returns TRUE). The
  first cut returned FALSE and the table's own row pick ran under the
  search's list: the native table takes a press anywhere in its rect.
  THE ARM READS THE MAP'S LEGS (`scores leg <i>`, then `scores status`). It
  assumed bhop_eazy's four stages and a bonus on the day Patch 664 replaced
  that build with one segment; on a map with the main track only it prints
  CANNOT MEASURE for which leg a time's row opens.
  `hud_player status` says `tier "<t>" <answer> maps <held>/<of> done <n>
  bar x,y wxh` AT ITS END (663's checks read the line up to there), `scores
  status` a `showing "<who>" on this map` line with the chip's and the first
  row's rectangles; `hud_player tier <n|u|off>` and `scores on [who]` are the
  console's twins, the first only with the card up.
  THE THREE FIXES FROM ITS REVIEW EACH FAIL ON THE BUILD BEFORE THEM (csprogs
  `7ca649ad`: 35 of 38), which is how their checks were shown to measure.
- **`tools/accounts_mutants.py` LIED FROM PATCH 662 UNTIL 665, AND ITS OWN
  LINES SAID SO.** 662 gave every suite `PYTHONPATH=tools` (test_web.py
  imports from there). test_accounts.py's "a host with no ed25519.py" check
  makes its host by taking `tools/` off `sys.path`; with the path in the
  environment as well the module still imported, the check failed on
  UNMUTATED code, and the sweep called every mutant killed: 173 of them by
  that check alone, the eleven expected survivors among them. Seen in 665
  because eleven "unexpected" names had all died of one check; measured on
  the unmutated suite (0 failures without the variable, that one with it).
  The path is test_web.py's alone now (and this file's own directory: built
  from the argument, `python tools/accounts_mutants.py surfd` pointed it at
  nothing, test_web.py died on its import, and a crash counted as a kill:
  665's review, then measured). EVERY SUITE NOW RUNS ONCE UNMUTATED FIRST, in
  the sweep's own environment, and the sweep stops if one fails there. A
  whole sweep reads 428 mutants, 417 killed, 11 survive alone as expected.
  READ WHICH CHECK KILLED, NOT ONLY THAT ONE DID: one name across many
  mutants is the environment. It takes about 27 minutes with six workers now
  that a mutant the first suite lets through runs the second;
  `ACCOUNTS_MUTANTS_ONLY=gp-` sweeps the mutants of one prefix (two minutes).
- **THE GAME'S TIER LIST AND PLAYER-ON-A-MAP (Patch 665)** are two more forms
  of `/api/board?player=`: `&ct=` and `&on=` (surfd/README.md has the
  replies). Both read `_profile_rows`, so they cost what the breakdown costs
  and little more while it is held. `_tier_maps` is the site's
  `/board/api/player/<h>/maps` as well: change one and the other moves.
- **DEPLOYED 11 Oct 2026, 19:02 UTC (FTESurf `de74859`, Patch 663): csprogs
  and default.cfg; AND WHAT THE FIRST LIVE LOOK FOUND.** `build.ps1 -Pi`
  from the pushed tree, nobody on any of the 12 lobbies: csprogs
  `221cbebf62381187` (qwprogs `35fda5eb` swapped for itself), all 12
  restarted, `.prev` is 655's `a9c73455`. Both installs at 19:02:50Z, no
  game running, under the rig lock, read back twice: csprogs `221cbebf`,
  and `cfg\default.cfg` `1029ff976654671c` (661's `28801b17` kept beside it
  as `default.cfg.pre663-20261011T190250Z`). menu.dat is not this patch's:
  `sui_text_event` is compiled for the game VM alone so that it stays
  `10cba3c1`. `pi_lobby_smoke.py` at 19:04Z on the engine release 0.1.24
  shipped: served `221cbebf`, the board drew, no QC error.
  A RIG CLIENT ON LOBBY 27510 AT 19:05Z, READING THE REAL DIRECTORY through
  play.proto.bar (a consent file and the real `lobby_dir`; read-only asks,
  as any player's): the owner's own breakdown by his mark, 50 rows of 2,051
  and 100 after a scroll, his real picture at the card's head, ten tier
  bars; a search for `lex`, twelve names, the exact one first.
  IT ALSO FOUND WHAT THE ARM COULD NOT, because the arm dismissed it first:
  the Link Steam offer that comes up by itself for an unlinked player drew
  OVER the card and took Enter from the search (a link started under a
  pick). Fixed in the commit after the patch's: while the card is up the
  offer is not drawn, and while the card is up or a search field has the
  keyboard it takes no key. The arm now opens the card with the offer
  pending (check O); the build that was live fails it.
  THAT FIX DEPLOYED 19:21 UTC (FTESurf `fa50eb5`): csprogs
  `9fc0940b9ba83594` on the Pi (12 lobbies restarted, nobody on; `.prev`
  `221cbebf`) and in both installs at 19:21:20Z, read back twice; menu.dat
  and default.cfg as they were. `pi_lobby_smoke.py` at 19:25Z on release
  0.1.24's engine: served `9fc0940b`, the board drew, no QC error.
  NOT SEEN: the card opened by a linked player on a real lobby (the rig's
  linked one was on its own surfd), and P pressed by a hand.
- **THE PROFILE (Patch 663): ITS PIECES, AND TWO TRAPS IT WAS BUILT ROUND.**
  `cl_profile.qc` holds the two asks (`player=`, `players=`), their answers
  and three pieces a panel draws INSIDE ITS OWN BRACKET: `Profile_Field`,
  `Profile_Drop` (last in the bracket: of the elements under the cursor sui
  answers for the last one registered, which is how a list lies over other
  controls) and `Profile_DrawStats`. `hud_player` and the leaderboard both
  use them; a picked player is `Profile_TakePick()`.
  A FIELD IN A GAME PANEL TAKES ITS KEYS AS THEY COME (`sui_text_event`),
  not through sui's buffer: every `sui_end` in a frame empties that, and a
  replay's chrome drawn first ate them. Do not also hand that key to
  `sui_input_event`. AND IT SWALLOWS ONLY THE RELEASES OF KEYS IT TOOK THE
  PRESS OF (`Profile_Took`): the engine returns before a bind's release when
  game code takes a key-up (keys.c:3860), so a strafe key held as the box
  took the keyboard stayed down for good.
  A RIG CLIENT THAT IS TO ASK A BOARD NEEDS `+set lobby_dir <its own surfd>`
  AND A CONSENT FILE AT VERSION 4: without the first its asks go to the real
  Pi, without the second none is made (Patch 653's own rig has neither, so
  its picture step measured nothing). `tools/p663profile.py` seeds its
  surfd's database directly, plants a four-colour picture, wraps surfd's
  `game_player` to count asks and to lie, and drives the panel by its
  console twins (`hud_player stats|view|find|scroll|status`, `scores
  find|me`); `hud_player status` is the line it grades. A CONSOLE TWIN GIVES
  NO FIELD THE KEYBOARD: only a press does (class Mouse, which moves the
  desktop's pointer). TWO TRAPS IN THAT ARM'S FIRST CUT: a picture must be
  planted BEFORE the game first asks for its mark (a miss is remembered
  fifteen minutes), and an alias run under `developer 1` is three log lines,
  not one.
  csprogs: 118,807 global definitions with this patch (448 more), of
  fteqcc's 131,072.
- **DEPLOYED 11 Oct 2026, 18:20-18:21 UTC (FTESurf `498a1bc`, Patch 655):
  csprogs and menu.dat.** `build.ps1 -Pi` from the pushed tree, nobody on
  any of the 12 lobbies: csprogs `a9c734555bf1b558` (qwprogs `35fda5eb`
  swapped for itself), all 12 restarted, `.prev` is 656's `bc2b938e`. Both
  installs at 18:21Z, no game running, under the rig lock, each read back
  twice: csprogs `a9c73455` (`.prev` `bc2b938e`) and menu.dat
  `10cba3c146bab74f` (`.prev` 652's `b4b46b6e`). The deploy build is byte
  for byte what the arms ran on.
  `pi_lobby_smoke.py` at 18:22Z on the engine release 0.1.24 shipped
  (`183faf44`), lobby 27510: served `a9c73455`, the board drew, no QC
  error.
  NOT SEEN ON A LIVE LOBBY: a text field (the game has none with a
  selection until Patch 663; the menu's were looked at in the rig, at 1:1).
- **TEXT FIELDS (Patch 655): HOW TO HAVE ONE, AND WHY NONE PASTES.**
  A field calls `sui_text_metrics(<text's x in the box>, <its size>)` just
  before `sui_text_input`, draws `sui_text_selection` between its box and
  its text, and asks `sui_text_has_focus(id)` for its ring and caret. Without
  metrics it is what it was (a click goes to the end, nothing is selected).
  A panel calls `sui_keys_forget()` when it opens and closes.
  A CHORD IS ITS CONTROL CODE (1, 3, 24; Windows makes it from the real
  keyboard state): an arm feeds `ui_key c down 3`; a POSTED Ctrl plus a
  posted letter is typed, by design (a Ctrl whose release was missed looks
  like that). `tools/p655text.py`'s class Chord shows a real one to the
  engine, for one press.
  NO FIELD READS THE CLIPBOARD, AND `clipboard_get` IS IN NEITHER .dat (that
  arm checks the bytes). Do not add it back from QC: the menu's `ui_*`
  commands run from a server (read from the engine; the private checkpoint
  `steam-accounts-20261010.md` has the reasoning and the three failed
  gates), so "a key the engine delivered" proves a key and not who arranged
  what it lands on. BACKLOG has the engine change that would allow it.
  `ui_mouse` now stamps `ui_synth_t` as `ui_key` and `ui_click` do.
- **DEPLOYED 11 Oct 2026, 17:35-17:38 UTC (FTESurf `2999820`, Patch 662):
  surfd.** `surfd.py` alone by `surfd-deploy.ps1` (the live file was main's
  before it, `f833ec74`, checked first), the suite green on the Pi, backup
  `data/surfd.db.bak-2999820-20261012-043548`, reload 17:38:35Z, the maps
  list (5.8 s cold) and a player page (1.8 s) asked once.
  MEASURED ON THE PI, 17:39Z, on 127.0.0.1:8084: `players=` with no text
  0.006 s, `lex` 0.013 s, `a` 0.012 s, a name nobody has 0.012 s (twelve rows
  or none; 67,000 entries walked in the last three). `player=` for the
  widest profile (2,626 rows) 1.52 s the first time and 0.026 s the second,
  0.027 s by its 8-hex mark, 0.029 s for 200 rows (24,653 bytes); the
  owner's by his mark 0.019 s (the site's page had asked for it); a handle
  nobody has 404, a malformed one 400. THROUGH `play.proto.bar`: a search
  0.17 s, that profile 0.10 s. 0 error or warning lines in the service's 89
  since the reload.
  NOT SEEN: the game asking (Patch 663 is not deployed), and the two
  together under real use.
- **THE GAME'S PLAYER LOOKUPS (Patch 662) ARE THE SITE'S, AND COST WHAT THE
  SITE'S COST.** `/api/board?players=` walks the in-memory directory once a
  request (about 20 ms for 67,000 entries on this desktop in its review, 12 ms
  on the Pi itself; under the GIL, so four threads do not make four searches
  faster), and
  `?player=` is `_profile_rows`: the first answer for a wide profile is
  seconds on the Pi, kept for two minutes. The proxy gives 5 s; the game asks
  once more by itself after an answer that never came (Patch 663).
  A PLAYER IS FOUND BY A 12-HEX HANDLE OR BY THE GAME'S 8-HEX MARK, which is
  the handle's first eight (`accounts.who_of(x) == web_handle(x)[:8]`, held by
  a check). By mark only while the board is by account, and only where ONE
  directory player has it: two who share a mark are found by handle (the
  search gives it) and never by mark.
  `tools/accounts_mutants.py` now runs `test_web.py` for its `gp-` mutants,
  with `tools/` on the path (that suite imports from it).
- **DEPLOYED 11 Oct 2026, 16:22-16:25 UTC (FTESurf `1142049`, Patch 660):
  surfd.** `surfd.py` and `steamsync.py` by `surfd-deploy.ps1`, the whole
  suite green on the Pi first (`test_ranked` with its Pillow), backup
  `data/surfd.db.bak-1142049-20261012-032236`, reload 16:25:23Z, the maps
  list (6.3 s cold) and a player page asked once, table `boardpics` there.
  THE FIRST PASSES, BY HAND UNDER THE CRON'S OWN LOCK. Dry: 67,259 players,
  8.0 s, 49 MB. Real, 16:26Z: all of them read in, and Steam went quiet on
  the FOURTH batch of fifty: `steam.py` gives a profile 1.5 s, which is a
  sign-in's patience, and the pass ended at 150 asked, 149 pictures kept,
  50 s. The next, 16:28Z: 5,000 asked, 4,786 distinct pictures named, 200
  fetched (its budget that once), 125 s. So the pass has its own ten seconds
  now (`PEOPLE_TIMEOUT`, the commit after this patch's, steamsync.py alone,
  no reload).
  SEEN LIVE, 16:32Z: surf_beginner's Momentum board, first 50 rows, 1 with
  `av` in the game's answer and on the site's (351 pictures were on disk of
  67,259 players), about 70 s after the pass that fetched it: the stamp, the
  thread, the next 60-second table. That row's picture is served, 1,828
  bytes. 0 error or warning lines in the service's 1,001 since the reload.
  NOT SEEN: a picture on an imported row IN THE GAME (the game's answer
  carries `av`; no client has drawn one), and the fill finishing: at 5,000
  players and 1,500 pictures a half hour it is a day's worth.
- **PICTURES FOR THE IMPORTED ROWS' PLAYERS (Patch 660): WHAT RUNS, AND WHAT
  THE NUMBERS WERE.** `steamsync.py` (cron, :07 and :37) has two more
  defaults, `--people 5000` and `--pictures 1500`: Steam is asked about that
  many board players a run (none twice in a day) and that many pictures are
  asked for. 67,259 SteamIDs on the boards, so the first fill is about a day
  of runs. Its state: table `boardpics`, and two stamps in `data/avatars`:
  `people.at` (the last read of the boards) and `board.at`, which surfd
  watches: IT REBUILDS ITS TABLE OF THEM WHEN THAT FILE'S TIME MOVES AND NOT
  OTHERWISE, on a thread. A table changed by hand is not seen until
  `steamsync.changed()` or a restart.
  THE BOARDS' READ IS `SELECT DISTINCT +player`: without the `+` sqlite
  walks `runs_player` with a lookup a row, 35.1 s on the Pi against 11.4 s
  (measured read-only on the live file). It is the shape the Patch 636 note
  on that index warns of; `tools/plan_audit.py` before the next one.
  NOTHING IS PRUNED WHILE A BOARD PLAYER HAS NEVER BEEN ASKED ABOUT, so a
  directory outlives a restored database for the day its refill takes.
- **DEPLOYED 11 Oct 2026, 15:42 UTC (FTESurf `8a6a117`, Patch 653): csprogs,
  the Pi's twelve lobbies and both Windows installs.** FIRST ON THE ENGINE
  THE 0.1.24 DOWNLOAD HAS (a copy of the 625 exe, `--client`): `p653box.py`
  14 of 14 there too, the check Patch 649 went out without. Then, under the
  rig lock with no game running, `build.ps1 -Pi` at 12 rows and 0 players:
  `csprogs.dat` `84eaeec6`, the bytes the arms ran on (`.prev` `827dece4`,
  Patch 654's), `qwprogs.dat` `35fda5eb` swapped for itself, twelve lobbies
  restarted. Windows, 15:42:50Z: `csprogs.dat` and its line table into
  `C:\FTESurf` and `C:\FTEQuake`, the old pair kept as `.prev`, read back
  with a second tool. LIVE, 15:46Z: `pi_lobby_smoke.py` on
  `play.proto.bar:27510` was served `84eaeec6`, drew the board, no QC error.
  The first try, queued behind the owner's game, REFUSED ITSELF: main had
  moved under it twice in ten minutes (two notes-only commits), and the
  deploy script wants the tree to be origin/main. Fetch and fast-forward
  right before, not when the deploy is queued.
  NOT SEEN LIVE: the box itself on a lobby (the owner is linked: `link` in
  the console raises it), and a picture in the room list at its new size.
- **THE LINK BOX'S MOUSE (Patch 653), AND HOW A RIG CLICKS.**
  `tools/p653box.py --progs <build> --output-dir <owned dir>`: p615link's
  rig, about 100 s, screenshots of every state to look at.
  THE BOX HAS THE CURSOR ONLY IN A LINK THE PLAYER STARTED (`acct_ui_cur`,
  set by that Enter; `UIC_ACCOUNT` 128): the wait, the page's number, the
  confirm. Its first cut claimed it for every state that owned the keyboard,
  and the review pointed at `link` plus one letter: a console line and a
  movement key away, with no timeout once a letter is in. The click is
  hit-tested in `Account_InputEvent`, not at draw: `acct_browse` answers only
  while a device's press is being delivered, and a mouse button is one
  (measured: the engine printed its second `acct_browse:` for the click).
  FOUR THINGS A RIG NEEDS TO CLICK. The engine does not read a posted
  WM_MOUSEMOVE: with a free cursor it reads the desktop's pointer
  (`in_win.c`, GetCursorPos), so the arm moves the real pointer and puts it
  back. It reads it only in the front window unless `in_focusgrab 0`. A
  posted WM_LBUTTONDOWN is a press. And a Python process is told a SCALED
  client size (1536 for 1920) until `SetProcessDPIAware()`: the first aimed
  click landed 143 px high and was graded as "beside the box", which an
  earlier check then passed on.
  A client's developer prints are not in its log without `log_developer 1`.
  The box draws in the HUD stack, outside any sui bracket: `_sui_round_draw`
  at absolute coordinates and its own `sui_style_hud`, not `sui_style_box`
  (which adds the last bracket's frame). fteqcc WARNS on a ninth argument to
  sprintf and drops it.
- **RELEASED 11 Oct 2026, 12:24-12:28 UTC: 0.1.24** (QC build 89, game
  `580a640`, Windows and Linux; the owner asked for one "so players can
  test"). The engine is Patch 625's, the one both installs run: stamp
  `git-7182-patch-625-0-gc543d688a`, exe `183faf44`, plugins `66042d85` and
  `ab7b0512`; the Linux drop is a build of that commit, gates all PASS.
  Progs: qwprogs `76e00522`, csprogs `e9371ed5` (Patch 646's), menu.dat
  `9dc45991` (Patch 647's), each equal by hash to a clean build of the
  release commit. `ftesurf-0.1.24.7z` 40,942,415 bytes, sha256 `fb696694`;
  `ftesurf-0.1.24-linux-x86_64.tar.xz` 40,601,152 bytes, sha256 `2a58e573`.
  CHECKED AFTER: both downloaded back from dl.proto.bar and equal to the
  receipt and to proto.bar's version.json; the Windows one unpacked: 805
  files, those six hashes, `mapdl.txt` 1283 lines (705 before: a
  `mapscan.py --go` ran first, the Pi serving 1349 maps), and no consent
  file, key, config, recording or `.prev` in it.
  NOT IN IT: Patches 643, 644, 645, 648 and 649, none on FTESurf main when it
  was cut. "engine patch 647" in the receipt is the patch LOG's number, not
  the binary's: `-FteRoot` was a tree at ftequakers `4e1ba6988`, the last
  commit before 645 changed engine source, because the script reads that
  number from the tree's ENGINE_PATCHES.md and gate 3 from its
  `engine\release`.
  A FIRST BOOT OF THE UNPACKED DOWNLOAD, 12:51Z (it waited for the owner's
  game to close): the archive's own exe from its own directory, nothing
  answered. LOOKED AT: "Before you play" comes up by itself, both cards, the
  fonts and the three buttons drawn; by its own print the panel is 1240 x 781
  at 16 px in a 1920 x 1111 window. No consent file was written; the boot
  wrote its log, the screenshots and `installed.lst`. NOT PRESSED THERE:
  either answer, so the Steam offer was not seen from the download.
  THE LINUX ARCHIVE WAS PUBLISHED UNBOOTED. Its checks were the build's gates
  (sonames, glibc, stamp, code = pin) and the archive's (owner, modes, sha256
  = stage, ldd resolves); nothing started it, and no Linux client is known to
  have started a run since 0.1.14. A release with a Linux half BOOTS IT, and
  starts a run, before it publishes.
  A FAULT WAS READ INTO IT THE SAME HOUR AND WAS NOT THERE. A reviewer, then
  ftesurf-0f, then this session read `qclib/initlib.c:601-606` (the game VM
  gets 32 MiB outside Windows) against run-line tables of 36.7 MiB, and this
  session wrote here that the Linux client would stop at its first line. All
  three read the callee. The caller, `pr_csqc.c:8408`, passes
  `PR_ReadBytesString(pr_csqc_memsize)`, and `common/pr_bgcmd.c:132-145`
  turns the default -1 into 2 GiB on 64-bit Linux as on Windows, so that
  branch is never reached there (ftesurf-0f found it while checking how the
  cure's "256m" would parse).
  THEN MEASURED, BY ftesurf-0f (its log read here), 14:02Z: this release's
  Linux stage copied whole into the Debian rig and started as `rig-run.sh`
  starts it, offline. Stamp `git-7182-patch-625-0-gc543d688a`,
  `pr_csqc_memsize` "-1", `map bhop_eazy` loads, a 4,418-point board line is
  queued and drawn ("1 drawn, 15 segments last frame"), exit 0, and no
  addressable-memory line. That is ONE boot under WSLg, one map, one line:
  not a lobby, not a player's run, not a real Linux desktop.
  AND THE 625 ENGINE ON THE LOBBIES' CSPROGS (`f40d4069`, Patches 643 and
  645, live half an hour after the release), 13:46Z, also ftesurf-0f's: no
  engine line builtins, eight lines drawn the QC way, no error line; its
  picture differs from the 645 engine's QC-way picture only in the replay
  bar's close button, which lights under the real mouse. NOT RUN: a 0.1.24
  client joining a live lobby since that deploy (this session's smoke was
  queued behind the owner's game and stopped for low memory).
  AND A FAULT THAT REACHED IT, 14:37:27Z TO 15:13:07Z THAT DAY: Patch 649's
  csprogs on the lobbies let any client tick sixty-four run lines, and this
  release's 625 engine dies when one polygon batch passes 32768 vertices,
  which the fortieth line did (ftesurf-0f measured both on a copy of the
  exe). Patch 654 (csprogs `827dece4`) keeps the limit of eight on an engine
  without the line builtins. Nobody was on a lobby at either deploy; whether
  anyone joined between is not known.
  WHAT COST A RUN: `ftesurf\gfx\fonts\*.ttf.prev` trips the deny list (moved
  aside, put back after); the main checkout has to BE the release commit (it
  was 101 behind, its five stray files byte-equal to main's); and a shell
  left sitting in `release\stage-0.1.24` after reading the dry run stopped
  the real run at [5], AFTER it had written VERSION, so the rerun goes
  without `-Bump`. None of the release's steps opens a game or writes the
  install: they do not take the rig lock, and waiting on it with the owner's
  game up only blocks the other sessions.
- **DEPLOYED 11 Oct 2026, 12:01-12:05 UTC (FTESurf `5d3d98f`, Patch 647):
  menu.dat on both Windows installs, one file of surfd.** Under the rig lock,
  no game running, 12:01:42Z: `menu.dat` `9dc45991`, the bytes the arm ran on,
  and its line table into `C:\FTESurf` and `C:\FTEQuake`, the old pair kept
  as `.prev` (`6db94852`), read back with a second tool; csprogs `e9371ed5`
  (Patch 646's) and qwprogs untouched, and nothing to the Pi's progs: a
  dedicated server has no menu. surfd: `accounts.py` `d2d6508` by
  `surfd-deploy.ps1` (the Pi's was main's `5ddfeba`), its suite green there,
  reload 12:04:37Z, backup `data/surfd.db.bak-5d3d98f-20261011-230200`; the
  maps list (6.8 s cold) and a player page asked for once; 0 error or warning
  lines in the 74 since the reload. READ BACK through proto.bar: the sign-in
  page says the Steam name and avatar are shown with the times, in the game
  too. NOT SEEN ON A REAL FIRST BOOT: both installs hold a consent file, so
  the new screens were seen only in rigs; a fresh install of the next
  release is the first.
- **THE FIRST-BOOT SCREENS (Patch 647): HOW THEY ARE LOOKED AT AND DRIVEN.**
  `ui_strip_test screen terms` and `screen steam` put either screen up, and
  `screen fit` prints the terms panel against the window. NO WORD ANSWERS A
  SCREEN, and nothing typed may: a console line can be a server's stufftext,
  and the terms' answer is a consent. That held for the new words and NOT
  for two old ones: `ui_key` and `ui_click` are console commands that feed
  the menu real-looking events (the harnesses' hands), and through them a
  line could press the online answer. Since this patch the two answers and
  the offer's sign-in do nothing for 1.5 s after either (`ui_synth`); every
  other button still takes them. `tools/p647boot.py` answers as a player
  does, with real keys on the client's own window (p615link's `Keys`): Enter
  on a fresh terms screen is the DEFAULT button, offline; D (`+moveright`,
  the menu cursor's "right") then Enter is online. Its three modes on
  menu.dat `9dc45991`: sign-in 8 of 8 (tier 4 on disk, the offer, the map
  list loaded before the join, the join of the rig's lobby under the factory
  name, the game's own box asking for Enter), `--later` 6 of 6 (ESC: no
  join, `_acct_prompted` 1), `--offline` 4 of 4 (tier 1, no offer, the
  directory asked nothing).
  THE MENU LAYS OUT IN THE 2D RESOLUTION, NOT THE WINDOW'S: `vid_width` and
  `vid_restart` did not move the rig's window (three "sizes", one 1920 x 1111
  frame each), `vid_conautoscale 0; vid_conwidth W; vid_conheight H` gives
  the layout that size at once. Measured so: 1920 x 1080, panel 1240 x 781
  at 16 px; 1280 x 720, 1240 x 641 at 12 px; 1024 x 768, 992 x 656 at 12 px.
  The first cut was 15 px text in a 1040 px panel, 790 px tall: it did not
  fit 720p, and I had looked at it at one size only. 15 px is not on the UI
  face's baked ladder either (`sh_font.qc`: 8 12 16 20 24 28 32).
  THE MAP LIST IS `ui_create_open`'S TO LOAD, and a first boot has not
  opened PLAY: `ui_connect`'s map check (`ui_prejoin`) reads an empty list
  as "nothing to fetch". A join from anywhere else loads it first. In a rig
  the list is empty anyway (its maps are in no mounted game), so the arm
  grades the loader's own line falling between the offer and the join.
  A RIG'S SECOND LAUNCH RIGHT AFTER ITS FIRST DREW NOTHING once (flat black
  screenshots while its log said the commands ran): a script that looks at
  screenshots counts their colours and launches again. THE BACKDROP'S
  IN-WORLD PANEL KEEPS ITS LAST DRAWING on a screen that does not draw it
  (PLAY / VISUALS behind the offer, reached by the test word from the main
  menu; empty on a real first boot, which has never drawn it).
- **DEPLOYED 11 Oct 2026, 10:31-10:32 UTC (FTESurf `c3dde39`, Patch 640):
  csprogs, the Pi's twelve lobbies and both Windows installs.** Under the rig
  lock. `build.ps1 -Pi` at 12 rows and 0 players: `csprogs.dat` `b01acd53`,
  the bytes the arm ran on (`.prev` `30f816bb`), `qwprogs.dat` `76e00522`
  swapped for itself; twelve units active. Windows, 10:32:22Z, no game
  running: `csprogs.dat` and its line table into `C:\FTESurf` and
  `C:\FTEQuake`, the old pair kept as `.prev`, read back with a second tool.
  LOOKED AT, LIVE, 10:37Z: a private rig of the installed files (a key of
  its own, not linked) joined `play.proto.bar:27520` on surf_beginner and
  opened the Online list on FTESurf rows: the owner's row with HIS Steam
  picture before the name, the cache "asked 1 got 1", no error in the log;
  so the game-facing vhost passes `?avatar=` to surfd for a real mark too.
  NOT SEEN: a picture in the room list or beside a run line (each needs a
  linked player on the lobby: lextest asks the owner to look).
  THE PI'S DATABASE BACKUPS, the same day, on the owner's word ("if they are
  redundant, yes"): eight superseded deploy snapshots removed at 09:29Z
  (8.0 GiB), after `quick_check ok` on the two kept, `bak-b8c2c5d` (the
  newest) and `bak-pre629on` (the last before his rows changed owner). Left:
  `prewipe492` (the only copy of the 173 baseline rows wiped on 5 Oct) and
  `bak-ac-safe-observers` (another session's). A read-only open of a WAL
  database still writes `-shm` and `-wal` beside it: open copies with
  `immutable=1`, or a listing leaves two files a backup.
- **A TEXTURE FROM `r_uploadimage` IS NOT WHAT `drawpic(name)` DRAWS (Patch
  640).** drawpic's default shader is `program default2d#PREMUL` and loads its
  picture with `IF_PREMULTIPLYALPHA` (`gl_shader.c:8270`, Shader_Default2D);
  the upload makes its texture without (`RT_IMAGEFLAGS`), and
  `Image_FindTexture` matches on that bit. So drawpic made a SECOND texture
  of the same name, failed to load it from disk and drew the engine's
  missing-texture checker, dull red and black, 2 x 2: beside a fixture that
  was itself four quadrants, which is why the cut looked nearly right by
  eye and only the colours gave it away. Register a shader of your own after
  the upload (`cl_steampic.qc`: `program default2d`, `clampmap <name>`,
  `blendfunc blend`). Pixels are ints in memory order r, g, b, a; read hex
  four digits at a time (`stoh` of eight would not fit a signed int).
  INSIDE A SUI FRAME USE `sui_pic`: a list row's position is its frame's, and
  the first cut's drawpic put the picture nowhere a screenshot could find.
  THREE CUTS, ONE COUNTER: the cache's own line said "asked 1 got 1, state 3"
  for all three (csprogs `99da5072` nothing on screen, `fafda76b` the
  checker, `cde8f65a` the picture); only `tools/p640pics.py`'s reading of
  the screenshot told them apart (0, 0 and 117 quadrant matches).
  `set lobby_dir http://...` from a console line is cut at `//`: quote it.
  A MINIMISED CLIENT (p615link's `wShowWindow = 7`) DREW NOTHING in two runs
  of five; a second game window up beside it did the same to a shown one.
  AND IT IS ALL GONE AFTER `vid_restart` OR F11 (`fullscreen_toggle`):
  `R_ShutdownRenderer` runs `Shader_Shutdown` and `Image_Shutdown`, the VM
  lives on, and `CSQC_RendererRestarted` (cl_milk.qc) is the one place to drop
  what was held. A name drawn BEFORE its re-upload gets drawpic's default
  shader and keeps it: `R_LoadShader` returns the shader a name already has
  and ignores the script it is handed (`gl_shader.c:8609`). The review traced
  it; `p640pics.py`'s V step reproduced it on the build before the fix (cache
  "1 of 1", 0 quadrant matches after the restart) and passes after (2 of 2,
  127 matches).
- **THE ENGINE'S HTTP CLIENT HAS FOUR THREADS AND NO TIMEOUT** (`httpclient.c`,
  `MAXDOWNLOADTHREADS 4`; only a 0.1 s select). Every `uri_get` from any VM
  takes one, and a request to a host that never answers holds it for the
  session: the fourth such stops the board, replay fetches, zone downloads
  and the menu's lobby list together. So an unanswered request is not
  given up on and replaced (`cl_steampic.qc` asks nothing while one is out,
  takes a late answer, and holds off across maps after a slow one), and a
  429 pauses the asker instead of moving on to the next thing to ask.
  MEASURED IN THE RIG with surfd made slow and busy (`p640pics.py --slow 25`,
  `--busy 1`): one request and the picture drawn 25 s on; a 429, the mark
  still wanted, the second request 60 s later, drawn. The reviewer's offline
  VM, same build before the last touches: a directory that never answers, 1
  request in ten minutes (it was 6 in 100 s); 429s with 24 marks on screen,
  3 requests in three minutes and no mark written off (it was all 24 in
  36 s, each for 15 minutes).
  REQUEST IDS RESTART AT 1 IN EVERY VM (`Online_NextReq`), and the engine's
  stale-reply test compares a spawncount nothing in CSQC changes
  (`pr_bgcmd.c:6139`): a reply slower than a map load arrives in the next VM
  under an id that is live again. `Players_BoardReply` checks the reply's
  map for this; a reply with nothing to check needs ids of its own.
- **DEPLOYED 11 Oct 2026, 08:49-08:52 UTC (FTESurf `b8c2c5d`, Patch 639):
  surfd only.** Six files by `surfd-deploy.ps1` (`surfd.py` `ed55301`,
  `accounts.py` `5ddfeba`, `admin.py` `2a1a3bc`, `steamsync.py` `78c9f0a`,
  `web/board.js` `c777b6e`, `web/board.css` `6467544`; the Pi's six equalled
  origin/main's before, and the commit's after), its suite green on the Pi,
  reload 08:51:57Z, backup `data/surfd.db.bak-b8c2c5d-20261011-194917`. One
  hand pass of `steamsync.py --go` under cron's lock, 08:52:43Z: 1 picture
  fetched, 1 game copy made (`data/avatars`, mode 700). READ BACK:
  `/board/avatar/<handle>` 200 `image/jpeg` 3,540 bytes through proto.bar,
  with `nosniff` and the CSP; `/api/board?avatar=<mark>` 200, 8,247 bytes, a
  header and 32 rows of 256; the player page says `av: 1`; play.proto.bar
  forwards the parameter (an unknown mark is surfd's own 404); 0 error or
  warning lines among the 187 since the reload; the live player page in a
  headless browser shows the picture. The first player page and the first
  maps list after the reload took 7.3 s and 7.1 s on the Pi (asked for once
  here, then 0.05 s): past nginx's 5 s, so ask for both after every reload.
  No lobby restart, no client files. The Pi holds 9 of the deploy script's
  database backups (9.1 GiB) and 26 hand-made (2.7 GiB), 108 GiB free: not
  pruned, the owner's call.
- **STEAM PICTURES, THE SERVICE HALF (Patch 639): WHAT WAS LOOKED AT FIRST.**
  On the Pi: Pillow 12.3 and ImageMagick's `convert` are there; Steam's
  picture host answers `https://avatars.steamstatic.com/<hash>.jpg` (32 px,
  1.6 KB), `_medium.jpg` (64 px, 3.5 KB) and `_full.jpg` (184 px, 13.7 KB)
  for the hash `accounts.avatar` already held. THE GAME-FACING ADDRESS
  FORWARDS A FIXED LIST OF PATHS (`/etc/nginx/snippets/surfd.conf`:
  `/api/board`, `/api/replay/`, `/api/momentum/`, `/api/join`,
  `/lobbies.json`, `/health`; everything else is the vhost's own 404, asked
  and answered), and `proto` may `sudo` nothing but the lobby units, so a new
  path for the game cannot be opened from here: the game's copy is
  `/api/board?avatar=<mark>`. In the engine (the survey of 11 Oct): JPEG and
  PNG decode, but a URL as a pic name is broken by this fork's own `//`
  collapse in `COM_CleanUpPath`, and `uri_get` hands QuakeC a string, so a
  binary body stops at its first NUL: hence RGBA as hex text, which QuakeC
  can parse and `r_uploadimage` takes.
  LOOKED AT: the fixture site with two drawn pictures, in a headless
  browser, the board and a player page.
  ONE REVIEW, ELEVEN FINDINGS, NONE A WAY OUT OF THE DIRECTORY. The two worth
  keeping: `steam.Unavailable` is BOTH "the host is down" and "status 404 for
  this one object", and a pass that broke on either stopped at the same
  refused hash every half hour, in sorted order, for good (`_refused` splits
  them; a 429 is the host). And a body cut short on the way has a JPEG's
  first bytes and `resp.read()` returns it without a word: keep nothing
  Pillow has not opened.
- **DEPLOYED 11 Oct 2026, 05:31-05:33 UTC (FTESurf `36bd989`, Patch 638):
  surfd, the Pi's twelve lobbies, both Windows installs' qwprogs.** surfd
  first (`accounts.py`, `surfd.py`, the new `steamsync.py`, two tests; the
  staged suites pass on the Pi; backup `surfd.db.bak-36bd989-20261011-162839`;
  `surfd ready` 05:31:17Z; the commit's blobs read back, no error since the
  reload). A crontab line for `steamsync.py --go` at minutes 7 and 37 (the
  old crontab kept as `crontab.pre638-*` beside surfd); its dry run and then
  a real pass asked Steam for the one account and renamed nothing: THE
  OWNER'S ROWS WERE ALREADY UNDER HIS STEAM NAME, which is the name his game
  had. Lobbies, `build.ps1 -Pi` at `36bd989`, 12 rows and 0 players:
  `qwprogs.dat` `76e00522` (the bytes the arm ran on), `csprogs.dat`
  `b2b6de57`, byte for byte Patch 635's, so the swap replaced it with itself
  and `csprogs.dat.prev` is `b2b6de57` too now; twelve units active since
  05:32:48Z to 05:32:57Z. Windows, 05:33:20Z: `qwprogs.dat` and its line
  table into both installs, no game running, the previous `e9c95065` kept as
  `.prev`, read back with a second tool. Live check 05:33:47Z: the installed
  client in a private rig (a key of its own, no key pressed) joined
  `play.proto.bar:27510` and had its proof answered, not linked, the prompt
  up, no error. NOT MEASURED ON THE FLEET: a name being forced, which needs
  a linked game; the owner's next connect is the first (lextest has the
  check). ALSO READ THAT HOUR, 05:09:39Z: the owner's stage time on surf_666
  stored `tier=ranked` under his account, the first live run through Patch
  629's path. THE FIRST MAPS-LIST BUILD AFTER THIS RELOAD TOOK 6.48 s.
  Roll back: `qwprogs.dat.prev` over the file and a lobby restart; the
  `.pre36bd989-*` copies over surfd's files and a reload; remove the cron
  line (nothing else reads `named`, and an old lobby ignores it).
- **THE STEAM NAME IS THE NAME (Patch 638): WHAT THE ENGINE DOES WITH A FORCED
  NAME.** Read in the engine before a line was written (`pr_cmds.c`
  PF_ForceInfoKey, `sv_main.c` SV_ExtractFromUserinfo, `sv_user.c`
  SV_SetInfo_f): `forceinfokey(e, "name", x)` sets userinfo and `netname`
  without the "changed their name" line and without touching the client's
  cvar; the engine may alter x (a "(1)" before a duplicate, "unnamed" for a
  name with "console" in it, a cut at 31 bytes), so the lobby latches what
  the engine MADE and forces again only when `netname` has moved off it; a
  client `setinfo name` overwrites a forced name, and the QC hook the engine
  has for that (`UserInfo_Changed`) runs after the fact, so the lobby drops
  the command in `SV_ParseClientCommand` instead. `Account_Is` drops the
  latch each time surfd says who the connection is: without that a link moved
  to another account kept the last account's name (found by the arm's own
  first run, not by reading).
  MEASURED IN THE RIG (`p615link.py`, the N check): the lobby's own line names
  each account in turn, a client `name Imposter` is answered and never
  reaches the server's log. CONTROL: a build with the drop compiled out
  (qwprogs `b5bc58e1` against `38b7f0d6`) fails that one check, 41 of 42,
  with "Imposter" in the log.
  A fresh worktree has no `src/fteqcc64.exe` (it is not tracked): copy it in
  before a control build, or `build.ps1` says only "fteqcc not found".
  ITS REVIEW (one reviewer: evidence, abuse, breakage) found nothing that
  loses a recording, fails a check, misattributes a run or moves a rank: a
  recording's leaf is built once at close, `owner` is unbound, and nothing
  compares a name with one stored earlier. What it found was about the name:
  THE DROP TESTED ONE SPELLING OF A RENAME AND THE ENGINE TAKES THREE
  (`setinfo name`, its own `name` command, and a `setinfo` behind a comment
  that the engine's tokenizer skips and `tokenize()` takes for the command
  word): the test is `Account_IsRename` on `tokenize_console` now, before
  the function's own tokenize. `steamsync` renamed rows only on a change it
  saw itself, so every row filed before the patch, and a name a sign-in
  wrote first, stayed stale for good: the rows follow the account now, each
  pass. surfd's reserved-word test was "is console" and the engine's is
  "contains console, read as leet, spaces dropped" ("Falcon Soleil"): ported
  byte for byte, and the lobby puts back the player's own name and lets go
  if the engine still answers "unnamed". A "(1)" before a name somebody had
  first is retried every fifteen seconds. A reply with no picture kept
  blanking the stored one; a reply that cannot be read stopped every pass at
  the same fifty accounts.
  THE FULL SWEEP ON THIS PATCH CAUGHT A MUTANT ORPHANED BY THE LAST ONE:
  `rank-ext` survived because Patch 636 publishes a linked account's Steam
  id by a second rule; 636 changed `surfd.py` and ran `test_web.py` and the
  lint, not the sweep. A patch that touches a file the sweep mutates runs
  the sweep.
  A FAILING CHECK THAT PRINTS A NAME OUTSIDE THE CONSOLE'S CODE PAGE RAISED
  IN `print()`: the sweep called it "killed by a crash", which is a kill for
  the wrong reason. `test_ranked.py`'s `check()` escapes what it prints.
- **DEPLOYED 11 Oct 2026, 04:16:58 UTC (FTESurf `32c3b3b`, Patch 636), surfd
  and its website**: `accounts.py`, `momboards.py`, `surfd.py`, the three
  `web/` files and two tests through `surfd-deploy.ps1` (staged suites pass
  on the Pi, backup `surfd.db.bak-32c3b3b-20261011-151414`, reload, 0
  players), and `tools/momfetch.py` copied by hand to the Pi's flat
  `/srv/nvme/surfd/momfetch.py`, where `momwatch` loads it from (the deploy
  script stages `tools/` for the suite only); refused unless the copy there
  was the previous blob, the old one kept as `.pre32c3b3b-*`. The start
  built `runs_player` itself. Read back on the host: the commit's blobs, no
  ERROR or Traceback since the reload by position, and THE TWO PLANS THAT
  MOVED ARE WHERE THEY WERE: the directory build `SCAN runs; USE TEMP B-TREE
  FOR GROUP BY` (11.2 s on that read; 8.0 s an hour before), the admin's
  account counts off `runs_live` in 0.00 s. The owner's player page 1.61 s
  the first time and 0.03 s the second; its maps list 0.02 s and the same
  ten tiers as its bars (58 of 65 in tier 1 ... 0 of 1 in tier 10, 454
  unrated); surf_beginner 7,859 rows on All games, 1 / 7,652 / 206 by game;
  the public `board.js` is the new one. `momusers` is empty until `momwatch`
  refetches a board. THE FIRST MAPS-LIST BUILD AFTER THIS RELOAD TOOK 4.95 s,
  against nginx's 5: ask for `/board/api/maps` once after every surfd reload.
- **THE SITE, PATCH 636: WHAT WAS MEASURED, AND ONE THING THAT DID NOT WORK.**
  A player page for an account with 2,029 rows, timed on the Pi part by
  part: the read of `runs` by player 0.6 s warm and 4.66 s cold (no index:
  `runs_player` is the fix), the rows ahead 0.54 s, the board sizes 0.71 s,
  2,029 empty statements 0.005 s. I REWROTE THE RANK AS TWO INDEX RANGES IN
  ONE STATEMENT AND IT BOUGHT NOTHING: 1.29 s against 1.27 s on the live
  file, the same answer on every row, so `rank_of` is as it was and the page
  holds a player's ranked rows for two minutes instead. The widest profile
  has 2,626 rows. Cached board sizes would take the 0.71 s (BACKLOG).
  MOMENTUM'S PROFILE ADDRESS is `/profile/<their user number>`: read in
  their website's source (`pages/profile/routes.ts`, `Number(params.get
  ('id'))`), not guessed; the board files kept only the SteamID, so the
  number arrives as `momwatch` refreshes each board.
  AND THE INDEX, BUILT ON THE LIVE FILE BEFORE ITS REVIEW, MADE TWO OTHER
  STATEMENTS SLOWER FOR 27 MINUTES (03:34 to 04:01 UTC, 11 Oct). I took "an
  index only adds a faster path" for true. With `runs_player` there and no
  `sqlite_stat1`, sqlite answered the two statements that GROUP BY player by
  walking it in order with a table lookup a row: the site's directory build
  34.2 s for 8.0 s, the admin's account counts 14.4 s for 0.00 s, both
  measured on the Pi when the reviewer's report said to look. Dropped at
  once; both statements say `GROUP BY +player` now and `test_web.py` holds
  their plans. `tools/plan_audit.py "<CREATE INDEX ...>"` is the check that
  would have caught it: it traces every statement the suites run on the
  table and prints the ones whose plan moves (34 here, 5 of them walks of
  the new index, 2 of those the service's own). Run it BEFORE an index goes
  near the live file.
  THE REVIEW (one lens set: leak, wrong, break, script) ALSO FOUND the held
  page dropped by `submit_run` alone, so a banned account's times stayed on
  its page for the two minutes and a run landing while the ranks were
  counted could be overwritten by the list from before it: an entry now
  carries a mark of the player's own rows (count, summed times, newest,
  summed recording ids), read off the index on every hit. Nothing under
  script injection: no `innerHTML`, every outbound address percent-encoded.
  THE PAGES WERE LOOKED AT: a fixture served on localhost and three
  screenshots from a headless browser (the board, one game's filter, a
  profile with a tier open through `&ct=2`). `test_web.py` gained hand
  mutants in the task root, not a tool: 17 of 17 killed on the final code,
  after two checks the first run showed were missing (a stage time is not a
  finished map; a negative Momentum number is not kept).
- **"COULD NOT LOAD THE BOARD (HTTP 504)" WAS ONE QUERY (Patch 634).** The
  owner saw it on the site's front page on 11 Oct. Timed on the Pi, route by
  route: `/board/api/maps` 12.06 s, every other route under 0.2 s except a
  player page at 2.0 s. nginx gives surfd 5 s, and the list is cached 60 s, so
  it was the FIRST visitor after each minute who got it, and a reload worked.
  Query by query: the imported count took 7.9 s of the 12, `SCAN runs USING
  INDEX runs_run`, a walk in map order with a table lookup for each of 3.2
  million rows, because `replay_id` beside the count is in no index. NOT
  TODAY'S: the schema-15 backup from before Patch 629 gives the same plan (and
  28 s cold). As two queries it is 0.67 s off `runs_board` (covering) and
  0.026 s off `runs_replay`, the same answer on the live file (849 maps,
  12,611 recordings); the recordings query needs `GROUP BY +map`, without
  which sqlite picks the map-ordered walk again (6.3 s).
  LEFT: the list is still built inside a request, about 2 s once a minute
  (BACKLOG); a player page reads `runs` by `player` with no index, 0.6 s of a
  full scan before its ranks.
  DEPLOYED 11 Oct 2026, 02:46:48 UTC (FTESurf `234a488`), surfd only:
  `surfd.py` and `test_web.py`, the staged suites pass on the Pi, backup
  `surfd.db.bak-234a488-20261011-134417`, reload, 0 players. Read back: blob
  `3ebe67a`, `ranked rows need a linked Steam account: yes`, and the route
  timed on the host: 5.94 s for the FIRST build after the reload (cold: one
  visitor after each surfd restart can still see a 504, so ask for the route
  once after a deploy), 0.005 s from the cache, 1.95 s for the rebuild after
  the cache lapsed, the body the same 73,898 bytes as before; 0.08 s through
  the public address. THE PLAYER PAGE WAS 3.95 s IN THE SAME READ (2.0 s an
  hour earlier): it asks `rank_of` for EVERY row a player has, two counts
  each, before it shows a hundred of them, and the owner's account has 2,029.
  No review round: a read-only route, six lines, its answer compared with the
  old query's on the live file.
- **DEPLOYED 11 Oct 2026, 03:16:10 UTC (FTESurf `04a6ea0`, Patch 633), surfd
  only**: `accounts.py`, `admin.py`, `surfd.py`, the four admin templates and
  two tests; the staged suites pass on the Pi (`test_ranked` 95 checks);
  backup `surfd.db.bak-04a6ea0-20261011-141333`; reload with 0 players. Read
  back: the commit's blobs (`f8b4cb8` / `10905ce` / `891c627`), no ERROR or
  Traceback after the reload by position in the log, `ranked rows need a
  linked Steam account: yes`, `/admin/accounts` 302 to the login and the
  three new API routes 401 without a session, the boards as they were (21
  ranked rows, nobody banned, the first maps build 2.05 s). NOT DONE ON THE
  FLEET: a ban. It needs the owner's panel password and an account to ban;
  lextest has the try (his own account, note "test", then unban).
- **RANKED-MEANS-LINKED SWITCHED ON, 11 Oct 2026, 02:14:18 UTC** (the owner:
  "yes"). No code moved: the Pi's `surfd.env` line `SURFD_RANKED_LINKED` went
  from 0 to 1 and surfd was reloaded. BEFORE THE LINE, in this order and with
  0 players: a backup (`data/surfd.db.bak-pre629on-20261011T021343Z`, mode
  600, `quick_check` ok); then, as he had asked, his own rows moved by hand
  from his install's old id to his account in one IMMEDIATE transaction (21
  board rows, all `ranked`; 7 recording rows; one `installs` row), refused
  unless there was exactly one link and the only owner of non-imported rows
  was that link's install. Done the other way round the first start would
  have moved them to community. Read back: the log line `ranked rows need a
  linked Steam account: yes`, 21 ranked rows of one account, nothing moved by
  the start, `/health` ok, no ERROR or Traceback after the reload BY POSITION
  IN THE LOG (a filter on the timestamp column also passed five old undated
  Traceback lines, which is how I came to count by line number).
  WHAT IT SHOWED AT ONCE: his account also holds 2,008 imported Momentum rows
  under the same SteamID, and after the player directory's five-minute cache
  his page lists both under one handle (`by_tier` ranked 21, momentum 2008).
  NOT MEASURED AT THE SWITCH: a finished run stored under an account on the
  live fleet; the owner's next finish is the first.
  To switch off: the line to 0 and a reload. Rows stay where they are.
  `pubkeys.player` still names his install's old id, so the admin's key
  flags read his older recordings as another player's key (ROADMAP 14.3 b).
- **DEPLOYED 11 Oct 2026, 01:31-01:38 UTC (FTESurf `061fa8d`, Patch 629),
  SWITCHED OFF: surfd, the Pi's twelve lobbies, both Windows installs' progs.**
  No engine change. In this order:
  01:31:52Z `SURFD_RANKED_LINKED=0` appended to the Pi's `surfd.env` (copy
  kept as `surfd.env.pre629-20261011T013152Z`, mode 600), BEFORE any 629 code
  was on the host: the code's default is on and every cron tool imports
  surfd. The service's process has no `SURFD_*` in its environment, so it and
  the cron tools both read that file.
  surfd, `-Ref 061fa8d -Only` its fourteen changed python files: the staged
  suites pass on the Pi, `test_ranked` among them (added to the script's
  list); backup `surfd.db.bak-061fa8d-20261011-123213`; reload, `surfd ready`
  01:34:53Z. Read back: blobs `da2d40b` / `d2dfdd9` (the commit's), schema
  16, `runs_live` present, `runpins` with its `pub` column, the log line
  `ranked rows need a linked Steam account: NO (SURFD_RANKED_LINKED=0)`, and
  the board as it was: 21 ranked rows of one install, 1 link, 0 pins, 0
  installs, also after the 01:35 cron sweep had imported the new module.
  THE INDEX BUILD TOOK SEVEN SECONDS (01:34:46 to 01:34:53) AND COST ONE
  HEARTBEAT: the outgoing worker logged `heartbeat db error ... database is
  locked` once. 0 players at the time.
  Lobbies, `build.ps1 -Pi` from the worktree at `061fa8d`, 12 rows and 0
  players: `qwprogs.dat` `e9c95065`, `csprogs.dat` `6ddb3e37` (the bytes the
  rig arm ran on), previous pair kept as `.prev` (`bc25c080` / `848c654e`),
  twelve units active since 01:36:22Z to 01:36:30Z. `menu.dat` unchanged
  (`e5604321`).
  Live check, 01:37:23Z: the installed client in a private rig (its own key,
  no key pressed) joined `play.proto.bar:27510`, its connect proof was
  answered (not linked, the prompt came up), and surfd's game-code line now
  reads `6ddb3e37` with `848c654e` before it. THAT CHECK POSTS NO RUN: with
  the switch off the run path is the old one by construction (`if
  RANKED_LINKED:` in `submit_run`), and the owner's next finish is its first
  live use.
  Windows, 01:38:33Z: both installs' `qwprogs.dat` and `csprogs.dat` and
  their line tables, by a copy that refuses unless the installed file is the
  previous main's build and no installed game is running (it waited out a
  peer's rig client); each previous file kept as `.prev`; read back with a
  second tool.
  Roll back: `.prev` over each progs file and restart the lobbies; the
  `.pre061fa8d-20261011-123213` copies over surfd's files and a reload
  (schema 16 is two tables and an index the Patch 625 code never reads).
  (Switched on forty minutes later, on the owner's word: the entry above.)
- **DEPLOYED 10 Oct 2026, 22:07-22:10 UTC (FTESurf `e31cce8`, engine
  `c543d688a` = tag `patch-625`, Patch 625): surfd, the Pi's twelve lobbies,
  both Windows installs, progs AND engine.** Over Patch 622's pair
  (`2e41110e` / `47444c35`) and surfd's 619 files, all read back first.
  surfd FIRST, `surfd ready` 22:07:19Z: `-Ref e31cce8 -Only` accounts.py,
  surfd.py and their two tests; the staged suites pass on the Pi; database
  backup `surfd.db.bak-e31cce8-20261011-090453`. Read back: schema 15,
  `keylinks` made and empty, `linkkeys` kept and emptied (its log line:
  `dropped 1 link(s)`, the owner's test link), `accounts` still its one row,
  13 ranked rows untouched. It logged the game code it expects from the
  default path, the lobbies' `csprogs.dat` and `.prev`.
  Lobbies, 22:08:34Z: `build.ps1 -Pi` from the clean worktree, 12 rows and 0
  players; `qwprogs.dat` `bc25c080` (1020466 bytes) and `csprogs.dat`
  `f1126df3` (5386290), hash-verified on the Pi (a peer's independent build
  of `e31cce8` gave the same pair); the 622 pair kept as `.prev`; all 12
  active from 22:08:37. surfd noticed the new csprogs at its next check
  (22:10:57Z) with no restart.
  Windows, 22:09:52Z, no installed game running: the same two progs and
  their `.lno` into both installs (`menu.dat` `e5604321` unchanged), and the
  patch-625 engine build, one stamp `git-7182-patch-625-0-gc543d688a`:
  `C:\FTESurf\ftesurf64.exe` and `C:\FTEQuake\fteqw64.exe` `183faf44`,
  `fteqwsv64.exe` `e9cfd598`, plugins hl2 `66042d85`, ui_imgui `ab7b0512`
  (both installs), cod `a6c00b64`, box3d `f19f9814`, ode `59508a3d`
  (`C:\FTEQuake`). Every replaced file has a `.prev` (exe `7c97e69b`, server
  `1c338f64`, hl2 `4406ae6a`, ui_imgui `69929fe5`). The Pi's own server
  binary is untouched: 625 changes no server C.
  READ BACK LIVE, as far as it goes without a person: the installed client in
  a private rig (its own key) joined lobby `play.proto.bar:27540`; its
  connect proof was answered "not linked" and the prompt came up, so the
  address, the game code's hash and the signature all passed on the live
  service. It pressed nothing: Enter copies over the owner's clipboard and
  leaves a start in the live database, and the arm shows Enter on these same
  bytes. NOT CHECKED: a real person linking end to end (lextest).
  A JOIN BY THE Pi's LAN ADDRESS STILL CANNOT LINK (`why: server`, as before):
  use the lobby list or `play.proto.bar`.
- **DEPLOYED 10 Oct 2026, 18:40-18:45 UTC (FTESurf `66a4225`, Patch 619): surfd,
  the Pi's twelve lobbies, both Windows installs.** Over Patch 621's pair
  (`092f9880` / `87bd5e43`), read back on all three before anything was copied.
  surfd FIRST, 18:40Z: `-Ref 66a4225 -Only` accounts.py, surfd.py and
  web/link.css (new). Twelve staged suites pass on the Pi, the three files
  hash-match, master 2479950 SIGHUP'd, `surfd ready` 18:42:47, /health 12
  lobbies. Read back: schema 14, `linkcodes` has `shown` and `seal`,
  `linkkeys` still its one row. `/board/link`, `/board/link.css` and a start's
  address answer 200 through proto.bar; `/api/link/start` and `/wait` are 404
  from outside.
  Lobbies, 18:43Z: `build.ps1 -Jobs 8 -Pi` from the clean worktree. 12 rows, 0
  players. `qwprogs.dat` `2e41110e` (1019982 bytes) and `csprogs.dat`
  `8a5ccca3` (5367186), hash-verified on the Pi; the 621 pair kept as `.prev`;
  all 12 active, started 18:44:00 to 18:44:09.
  Windows, 18:44:36Z: the same two progs and their `.lno` into both installs;
  `.prev` is the 621 pair; menu.dat (`e5604321`), binaries, plugins and
  default.cfg (`591c3236`) untouched. No game was running.
  LIVE, ONCE, 18:45:16-18:45:23Z: a rig client with a new key joined lobby 1 by
  `play.proto.bar`, was served `8a5ccca3`, told it is not linked, and got the
  prompt unasked. A real Enter started a link: surfd logged `POST
  /api/link/start` 200 and "started a link on p27510", the row has no account,
  `shown` `?` and a 181-character seal; the box showed the address and the
  live page for it hands code and opener to its button; the lobby's `POST
  /api/link/wait` came at 18:45:21 and :23 and stopped at Esc.
  NOT DONE LIVE: the sign-in, the number and the link. Only the owner has a
  Steam account to do it with (lextest 00).
  ROLLBACK: lobbies and installs, the `.prev` pair. surfd, the two
  `*.pre66a4225-20261011-054030` files, remove web/link.css, SIGHUP. ROLL THE
  LOBBIES BACK FIRST AND WAIT TEN MINUTES: the old `step` knows nothing of a
  start's number and would confirm a signed-in start without it. Schema 14
  stays (two additive columns the old code ignores). Database backups: this
  deploy's `surfd.db.bak-66a4225-20261011-054030` and the Patch 617 one, both
  kept.
- **`p615link.py` WRITES THE REAL CLIPBOARD.** The rig client calls
  `clipboard_set` like any other, so every run on a desktop leaves a test
  sign-in address where the owner's last copy was. Say so if they are at the
  machine.
- **A .dat CARRIES ITS COMPILE DATE.** fteqcc writes `Compiled [YYYY/MM/DD]`
  into the header (one byte differed, offset 115, across midnight), so "is the
  installed csprogs a build of main?" cannot be answered by hash on another
  day. Diff the bytes.

### The ship set is an allowlist, and three things it never named -- 2026-09-28

**IF THE GAME NAMES A FILE, SOMETHING IN `$ShipGlobs` OR `$ShipGameFiles` HAS
TO NAME IT TOO, AND NOTHING CHECKS THAT.** Three separate "it's broken"
reports in one session were one cause: content referenced by a string literal
in QC that no ship-set line carried, so the code was correct and the archive
was empty.

| Referenced from | Missing for | Presented as |
|---|---|---|
| `Zone_LoadForMap`, `maps/zones/local/<map>.json` | every release to 0.1.17 | "this map has no zone file, so it has no legs and no times" on all 589 zoned maps |
| `cl_players.qc:403`, `gfx/thumbnails/speaking_off` | every release ever | an error texture beside EVERY player's name, permanently |
| `ui_bgprobe`, `gfx/mapshots/<uuid>-<size>.jpg` | every release ever (1.1 GB, never shippable) | a full-screen error texture behind the create panel |

**WHY IT IS INVISIBLE HERE AND FATAL THERE:** the build box has all of it, so
no amount of local testing reproduces any of the three. The only honest check
is against the ARCHIVE -- download the published file and list it, which is
also how each of these was confirmed fixed. `release.ps1` verifies the archive
matches the STAGE, and the stage matches the allowlist; nothing verifies the
allowlist matches what the code asks for.

A gate exists now: `python tools/shipguard.py` (2026-10-05) sweeps the QC for
literal asset paths and asserts each resolves in the ship set, exit 1 on an
unexplained miss. It PARSES `$ShipRootFiles`/`$ShipGameFiles`/`$ShipGlobs` out of
release.ps1 rather than copying them, because a copy drifts and then the gate grades
a ship set nobody ships. `--mutate N` hides the Nth glob and asserts a MISS appears
-- run it, because a gate nobody has watched fire is not a gate. TWO THINGS IT
TAUGHT, both of which read as a clean pass and both now in its docstring: a PREFIX
deny key swallows its own subtree (`maps/` excused `maps/zones/local/`, the largest
of the three faults above), and **`fopen` IS A LOAD WHEN THE MODE IS `FILE_READ`,
NOT A PROBE** -- classing it as a probe hid `data/mapdl.txt` entirely, i.e. the
0.1.15 fault passed clean. A read whose failure is silent is the worst thing to call
optional. It reaches 9 of the 13 globs (a 14th since, #13 `gfx/env` `xray*.jpg`, is
reached by m_milk.qc's bind literal); the other four (`cfg`, `glsl`, `scripts`,
`gfx/env`) are ENGINE-CONVENTION -- `r_skybox milk` builds `gfx/env/milk.png`, a
shader's `prog milk_scene` builds the glsl filename -- so no literal sweep of
anything we author can see them, and a clean run means "no literal path in src/ is
missing", not "the archive is complete". **WIRED 2026-10-05: `release.ps1` gate 4**, in the Gates
step -- before staging and packing, so ONE call site covers the Windows and the Linux drop, which
share `$ShipGlobs`. It has no override (gates 1-3 each have one), it hard-Fails if the tool or
`python` is missing because a gate that cannot run must not read as a pass, and it echoes the tool's
own stdout into the release log so a run records what it saw and not only that it passed. Its
falsifier was run rather than reasoned about: deleting `'ftesurf/data/mapdl.txt'` from
`$ShipGameFiles` -- 0.1.14's actual fault -- made `-Bump patch -BuildNumber 89 -DryRun` stop at
`MISS data/mapdl.txt src/menu/m_main.qc:2117` / `FAILED: 1 literal asset path(s)` with no `[5] Stage`
step at all; restored, the same command ran all eleven steps to exit 0 with zero warnings. (That run
needed `-AllowDirty -AllowStale` to get past gates 1 and 2, because a concurrent session had
`ftesurf/cfg/default.cfg` modified and its QC newer than the installed .dat -- gate 4 has neither.)

**AND A MISS IS NOT A NO-OP.** `drawpic` substitutes
`R2D_SafeCachePic("no_texture")` and draws it (`pr_menu.c:622-632`), so a
missing pic is a visible error texture rather than nothing. `drawsubpic`
(`:688-712`) does not, and `precache_pic` (`:820-861`) never draws at all --
with flag 512 it returns `""` when an image will not load, which is an
existence test that does not go through `fopen`. Three builtins, three
behaviours; a comment that claimed `drawpic` no-ops on a miss is what kept the
blind fallback in `ui_map_backdrop` alive for as long as it lived.

### Zone files: what ships, what is fetched, and what the server must never read

- **The library ships now** (`release.ps1` `$ShipGlobs`, 609 files, 2.5 MB). It
  had never shipped before 2026-09-28, so every archive up to 0.1.17 gave a
  player no zones for any map. `local\` and not `online\`, which looks backwards
  and is not: `online\` resolves into the Momentum install, so on a machine
  without Momentum it is not a directory at all. The Pi is the mirror image --
  its `game/ftesurf/maps/zones/local` holds only 66 overrides because its
  Momentum mount supplies the other 537, which is why the nginx alias points at
  `ftesurf-site/zones` (the shipped set) and NOT at the server's own copy.
- **`cl_zonedl.qc` fetches what a release could not know about.** Client only.
  `sv_zones.qc` does not read `maps/zones/dl/` and must not: the server's table
  is what the clock is a function of, and it is not going to come from an HTTP
  fetch made by the box being timed. What the fetch buys is the DISPLAY.
- **The URL is a client cvar (`cl_download_zonesrc`), never `sv_dlURL`.** That
  one arrives in serverinfo and is whatever host you connected to; a zone file
  from there would be a stranger deciding where this client thinks the start
  zone is. A server cannot set a client cvar. Empty switches it off.
- **`dl/` is tried LAST of the three file sources, and that is the safety
  property rather than a preference.** A fetched file can never beat a shipped
  one or your own edit, so a bad mirror stops mattering at the next release.
- **It lands in `ftesurf/data/maps/zones/dl/`, not `ftesurf/maps/zones/dl/`.**
  QC fopen READS the whole VFS but WRITES into the `data/` sandbox, so the same
  relative path means two places depending on the verb. Both halves work
  because the read goes through the VFS the write landed in; what it costs is
  that a human clearing these by hand must go to `data/`. Measured, after the
  first version of this note named the wrong directory.
- **Proven end to end, once** (`cfg/test/b89zdl.cfg`, 2026-09-28): with BOTH
  local copies parked -- ours and Momentum's `online/` -- the log reads
  `zones: none for surf_rookie`, then `zones: 19 on surf_rookie
  (maps/zones/dl) crc d1eaee84`. The crc is the same one Momentum's own copy
  produces, and the fetched bytes hash equal to the mirror and to the shipped
  file. The first run of that arm measured nothing (no `waitms` before `map`,
  no `waitmap`, so the map never loaded and `zone_reload` came back
  `Unknown command` because CSQC does not exist without a map); the second
  named `maps/zones/online` because only OUR copy had been parked, which is
  the fixture's own stated falsification criterion firing.
- **`ZSRC_DL` is appended, not inserted**, so the three values the `.rec` header
  has always carried keep their numbers. The server never emits it.

### The boards are 2.8% of what exists, and one literal was why -- 2026-09-29

- **`momfetch.py` built every URL with `&skip=0`, so `--take 25` was a CEILING and
  not a default.** Measured against the cache it produced: **81,290 times held of
  2,927,709** that exist, with 2,914 of 3,726 boards stopped at exactly 25 places.
  The API pages fine -- `skip=100` returns ranks 101-200, contiguous, probed by
  hand. Nothing had ever asked it to. `--depth` now exists (`-1` = whole board),
  the unit of work is a PAGE, and `len(rows)` of the cached file is the cursor, so
  a sweep resumes with no bookkeeping.
- **The unit matters because one board can be 262 pages.** surf_kitsune stage 1 is
  26,112 times -- more than a whole sitting's budget for one board out of 3,726.
  Pages sort by depth, so every board reaches page 2 before any reaches page 3 and
  an interrupted deep sweep leaves the corpus EVEN.
- **What the depth targets cost**, all reconciled against an independent count
  before anything was fetched:

  | target | times | % | pages | at 1.5 s |
  |---|---|---|---|---|
  | held before | 81,290 | 2.8 | -- | -- |
  | top-100 | 262,942 | 9.0 | 3,671 | 1.5 h |
  | top-200 | 450,743 | 15.4 | 4,866 | 2.0 h |
  | everything | 2,927,709 | 100 | 30,058 | 12.5 h |

  `surfd.py`'s `BOARD_LIMIT_MAX = 200` is the deepest rank anything we serve can
  render, so top-200 is ~100% of what is visible today and full depth is for a
  rank-lookup feature that does not exist yet. Lex chose full depth anyway, on
  purpose, via `--backfill`.
- **THREE MERGE TRAPS, none of which reading found.** (1) `--refresh` at skip=0
  must MERGE and not replace, because momwatch passes it every 7 minutes and
  replacing truncates a deep board to one page per tick. (2) A short later page
  must clamp `total` to what is held, or an off-by-a-few `totalCount` is an
  INFINITE ASK that a backfill loops on forever. (3) Rows merge by `replayHash`
  ordered by time, because a board gaining a record mid-paging shifts every rank
  below it; the API's `rank` is kept but ADVISORY, which is checked rather than
  assumed -- `momboards.py` never reads it and surfd derives rank from
  `BOARD_ORDER` at query time.
- **The cost of merging is that nothing purges a run deleted upstream.** A union
  never shrinks. Deleting the board's json is the only way and it costs the whole
  depth. Deliberate trade; stated in the docstring.

### Three things now drive the top-up, and one of them is the website -- 2026-09-29

- **`momwatch.py` knew whether a board was FRESH and had no idea whether it was
  DEEP**, so a board holding 25 of 322 stayed at 25 forever however many people
  played the map. It takes `--depth` now, and a board that is fresh but SHORT is
  work.
- **`--refresh` made a tight tick pointless, and this is the one line to
  remember.** Its skip=0 pages sort ahead of every depth page, so with `--max 2`
  against two thin boards both requests re-read ranks 1-25 already held and the
  tick gained **0 rows** -- while the backfill beside it gained 50 from the same
  budget. `--refresh` is now passed only when a board is genuinely STALE.
- **`--want N` reads surfd's `mapwant` table (schema 9), written by
  `/board/api/map`.** A QUEUE AND NOT A FETCH: a public unauthenticated GET must
  never become an outbound request to somebody else's API while the visitor waits.
  Recorded only AFTER the route's own 404, so a sweep of invented names fills
  nothing, and one row per map means it cannot outgrow the library. `note_want`
  never raises -- a board page that 500s over a counter would be the worse bug.
- **`--backfill N` has its own cap on purpose**, so a busy fleet cannot starve the
  crawl and a long crawl cannot delay a map somebody is standing on. It needs no
  state: momfetch already sorts pages by depth, so a backfill is that tool with a
  small `--max` and no `--map`. **Live on the Pi's crontab** at `--depth -1 --want
  25 --backfill 15`, which is ~3,000 requests/day and ~10 days to full depth, at
  roughly a twelfth of the rate that tripped a 429.
- **`--take` now defaults to 100** in both tools. 25 was the old ceiling and is
  otherwise four times the requests for the same rows.
- **momboards had to become incremental first, and that was a prerequisite rather
  than a tidy-up.** It re-read all 3,726 files and re-upserted every row every 7
  minutes: 2.0 s and 66 MB at 84k rows, which extrapolates to ~70 s and ~2.3 GB at
  full depth against a Pi with **1.0 GB available**. Now it reads only files newer
  than `<boards>/.indexed`, flushes in chunks, and advances the watermark to the
  highest mtime PROCESSED rather than to `now`.
- **A WATERMARK MUST BE `st_mtime_ns`.** No decimal spelling of `st_mtime`
  round-trips: truncated to whole seconds, every file touched in that last second
  stays dirty; written as `%.6f` it rounds DOWN below the true value and the single
  newest file stays dirty. Both were measured, each left exactly one file re-read
  forever, and both would have looked like "incremental works" to any check that
  did not demand **zero**.
- **Bumping `SCHEMA_VERSION` still breaks `test_board.py`'s `HEAD_SCHEMA`.** 8 ->
  9 caught it on three arms that know nothing about a want-queue. The warning
  further down this file is accurate; heed it.

### Keeping the imported boards fresh -- KSF and the demo grab are cronned since 5 Oct

- **`momwatch.py` is on the Pi's crontab, every 7 minutes**, `--stale 24
  --max 40 --delay 1.5 --index`, under `flock`. It reads the `lobbies` table,
  refreshes only boards that are missing or stale for maps the fleet is on, and
  on a fresh fleet makes ZERO outbound requests -- verified on the first tick:
  "live maps 12, boards already fresh 44, boards to refresh 0". 1.5 s rather
  than the 1.0 s measured tripping Momentum's 429 after 2,164 consecutive
  requests, because this one runs unattended.
- **KSF IS CRONNED SINCE 2026-10-05, BY LEX'S EXPLICIT DECISION** ("slowly
  fill up my record list over time"); until then the rule here was "never
  automatic", and the docstring changed first, as that rule asked.
  `ksfimport.py --watch --go` every 5 minutes under `flock -n
  /tmp/surfd-ksfwatch.lock`: 10 requests 3 s apart, the next unseen page of
  every board in all four styles, maps in `mapwant` first; a refusal parks it
  6 h doubling to 48 h (`data/ksf/.refused`). Its own lock (`data/ksf/.lock`)
  also keeps a by-hand `--from-maps` from running beside it. `data/ksf/owed/`
  holds boards fetched and not yet filed; a non-empty one after a quiet hour is
  a failing write, not a backlog. Log: `logs/ksfwatch.log`.
- **`momgrab.py` fetches the Momentum demos the Pi does not hold** (cron, every
  5 minutes, `flock -n /tmp/surfd-momgrab.lock`): 6 demos a tick from
  cdn.momentum-mod.org, the top 10 of every board, converted with
  `tools/momreimport.py`'s rules. It imports momreplay/momimport/momreimport
  from the game's `tools/` (sweep.py's TOOLS), which `surfd-deploy.ps1` does
  NOT ship: copy them like the sweep's tools (`install` + `mv` under the sweep
  flock, `git hash-object` on the Pi). zstd demos (3%) need the `zstandard`
  module in the cron user's Python. State: `data/momgrab/`; demos kept in
  `data/momdemos/`. Log: `logs/momgrab.log`.
- **KSF's per-map boards ARE a paged JSON API; this file said the opposite for a
  morning.** On 2026-09-29 the board looked server-embedded in `/maps/<map>` and
  "there is no API route to find" was written up as structure. The leaderboard is
  fetched by the browser on `/maps/<map>/records`, a page neither search opened.
  Routes and traps: `ksfimport.py`'s docstring.
- **Two claims in `ksfimport.py`'s docstring were false and are corrected.** It
  said "no demo URL in any endpoint found" -- `/api/players/{id}/replays/{map}`
  returns per-zone `file` names like `replay_css_6201_0_712551_1790101734.rec` (a
  shavit .rec, no download path located, so "reachable" is still unproven). And it
  said a KSF row's build "CANNOT BE CHECKED, EVER" -- `/api/files/<map>.zip`
  answers `{"exists":true}`, and a published archive is a hashable one. Both
  conclusions stand; their reasons did not. A wrong reason under a right
  conclusion is the kind of thing this file exists to catch.
- The map roster stays a Windows scheduled task (`FTESurf map scan`, PT6H) for
  the reason already recorded: it hashes builds that live on this workstation.
  Since Patch 644 the Pi lists upstream and fetches for itself (next section).
- **`--watch`'S ORDER, since Patch 644** (`ksfimport.py`, the constants'
  comment). On 11 Oct 372 of 448 Forward main boards held ONE 20-row page
  while surf_rookie's stage boards held 2,300 rows each: a viewed map's every
  board, four styles of every stage and bonus, went to its end before any
  other map's second page. Now a viewed map's main board to 1,000, then its
  other boards to 100 and every map's main board to 200 in one class by
  depth, then the rest. The request rate is unchanged (10 per 5 minutes).

### Zones whose hash is not theirs, and bhop_eazy follows Momentum (Patch 664) -- 2026-10-12

Lex, of the 92 maps `--updates` could not follow and of bhop_eazy: "do both".

- **A REPLY THAT DOES NOT HASH IS TAKEN ONLY AS THE ZONE FILE HELD, SAVED
  AGAIN** (`surfd/mapwatch.py`, the module docstring; `zone_ask`): the same
  `tracks`, key for key. Measured on all 92 on 11 Oct, 22:10Z: 64 are that,
  each with new `globalRegions.allowBhop` and none with a changed cancel
  region; 8 changed inside the tracks (a `bhopEnabled` flag on 6, real edits
  on surf_anzchamps, surf_santorini and surf_summit); 20 have no zone file
  here. The 3-map sample the note below rested on was right about 64 of them.
- **THE OTHER 28 ARE `data/mapwatch/approved.json`**: `{"z:<map>:<first 12 of
  zoneHash>": "<sha1 of the bytes to be written>"}`. A person writes it, the
  watcher only reads it, and a key is good for those bytes alone. The value
  is the SHA1 of `json.dumps(zones, separators=(",", ":"),
  ensure_ascii=False)`. A key already struck three times (`zonetiming`) also
  needs its `later` entry taken out of state.json, under
  `/tmp/surfd-mapwatch.lock`. A file that does not parse (a BOM) approves
  nothing and says nothing.
- **WHAT IS WRITTEN IS A RE-DUMP, READ THE WAY THE GAME READS IT**
  (`zone_regions`). The engine's `json_get_float` runs `atof` over a string,
  so `"9000_0e-9"` is 9000 to the game and 0.00009 to `float()`; its
  `json_find_object_child` takes the FIRST of two keys where Python keeps the
  last. So a number must be a JSON number, a region three points,
  `teleDestPos` three numbers inside the world. Every one of the 985 zone
  files held and the 92 replies passes; 105 regions held use a position. A
  cancel region whose box is over the start is NOT a fault: 21 held files
  have one.
- **A REPLACED ZONE FILE IS KEPT** in `zones/online/.old/<stem>.<sha12>.json`,
  before its build is swapped; where `.old` is not a folder nothing held is
  asked for. The 14 replaced on 11 Oct (651) were not kept.
- **A re-save moves `zone_crc`** (it covers every region, allowBhop
  included): a run parked on one of those maps no longer resumes.
- **bhop_eazy IS MOMENTUM'S BUILD, AND NOT THE SAME MAP TO AN ARM.**
  4ddeea8cc0fa against 07320480e924: every collision and geometry lump byte
  for byte the same; 188 `func_door` platforms are 188 `func_bhop`; the
  published zones make its three STAGES three checkpoints of one segment
  (the same boxes, start and end) and add a cancel region. `pm_dettest` on
  both builds, on the Pi and on Windows: all seven lines equal but `mapcrc`
  (676de275, now 7f53da5d). The gate's Windows side is
  `C:\FTEQuake\fteqwsv64.exe`; `C:\FTESurf\fteqwsv64.exe` is from 28 Sep
  and prints no `srctrace`. 91 of the 246 arms and tools that name bhop_eazy
  mention stages and 24 use `pm_verify`: none was rerun. The old pair is
  kept, on this PC as `ftesurf\maps\.old\bhop_eazy.07320480e924.bsp` and
  `ftesurf\maps\zones\local\.old\bhop_eazy.0d413404a764.json`, on the Pi
  in `maps/.old/` and `zones/online/.old/`. For an arm that needs it, copy
  both over `maps\bhop_eazy.bsp` and `maps\zones\local\bhop_eazy.json`,
  and put Momentum's back after.
- DEPLOYED 11 Oct (UTC): `b15ab86` to `/srv/nvme/surfd` at 23:24Z
  (mapwatch.py alone, no reload; the suite 0 failed on the Pi), with
  `data/mapwatch/approved.json` (28 keys) and `state.json.pre664` beside the
  state. One run by hand, 23:27 to 23:35Z: 17 builds replaced, 69 zone files
  replaced and 6 written. Read back against the replies saved at 22:10Z: of
  the 92, every build is the published one and every zone file the bytes
  read then; no strike is left (92 before); 91 of the site's copies follow
  (one is the shipped set's own file); 76 zone files and 48 builds are kept
  aside. A throwaway server loads what was counted: `zones(sv)` 24 on
  surf_ace (12 before), 23 on surf_arcade, 35 on surf_santorini, 46 on
  surf_zeitgeist, 64 on surf_fortress. The same run took 14 more `_css`
  builds: 1,871 maps held, 1,016 with a zone file, 34 second builds timed by
  their map's. bhop_eazy waited for lobby 27540 to leave it and went in on
  a second run at 23:41Z; this PC's copy and its `zones\local` file at
  23:42Z, the Pi's two files by hash. `pm_dettest` after, on the Pi's live
  library and with `C:\FTEQuake\fteqwsv64.exe` on the installed files: the
  seven lines equal (mapcrc 7f53da5d, trace f7958b04dbcd1008, tick
  93e8615d81c26325, srctrace de0ed3421db7e9d1).

### One row per map with a Momentum / CS:S switch; the menu fetches its list (Patch 652) -- 2026-10-12

The menu half of Patch 651 (below). ROADMAP 8 asked for builds under one
name; this is two names on one row, which needed no engine or server change.

- **THE FOLD** (`ui_dl_load`, m_main.qc). A list row with a tenth column is a
  second build of the map named there, and goes onto that map's row:
  `ms_var` (plain row -> the build's row), `ms_varof` (the reverse;
  `ui_refilter` leaves that row out), `ms_pick` ("1" = CS:S chosen, kept in
  `data/mapbuild.txt`). `ui_eff(row)` is the row whose FILE an action is
  about: Play, Download, start, the leaderboard panel, the player's own time
  and the headcount read through it; the name, tier, picture and best known
  time stay the plain map's. A build whose map is not listed keeps its row.
- **A REPLY FROM `lobby_dir` IS A STRANGER'S TEXT** (`Mdl_Reply`, m_lobby.qc).
  Every row is rebuilt from fields that each passed their own test, and a
  name is `[A-Za-z0-9_-]{1,64}`: it goes on to a download path, a join query
  and `map`. A list with no row that passes saves nothing (saved, it would
  hide the shipped one: `ui_dl_load` reads `data/mapdl.net.txt` first).
- **`strstrofs` AND `substring` ARE A strlen OF THE WHOLE STRING EACH** in
  the engine (pr_bgcmd.c). The first cut walked the reply with them: by the
  review's arithmetic two megabytes of short lines was 340 s inside one
  callback. The reply is written to a file once and read back with `fgets`.
- **A VARARGS CALL CARRIES EIGHT PARAMETERS**: fteqcc warns ("More than 8
  parameters on varargs function") and the row is built in two sprintfs.
- **TO DRIVE IT**: `ui_build <map> [mom|css]` (the switch's twin, and its
  controls' names for `ui_hover @<id>` + `ui_mouse`), `ui_mapnet [ask|sel]`
  (the fetch; what start would launch), `ui_find <text>` (the search).
  `tools/p652builds.py` is the arm, on p615link's rig with surfd in process.
  A rig has no mapmeta, so no row has a tier to the list's mind: set
  `ui_maps_showall 1` or it draws "no matches".
- **A RIG WAITER TAKES THE LOCK LAST.** Mine took `rig.lock` and then waited
  for a quiet machine, and sat on it while the owner played (11 Oct 15:25Z).
  Quiet first, then the lock, then one more look.
- DEPLOYED 11 Oct from `123c70e`: menu.dat `b4b46b6e` to both installs at
  16:33:40Z with no game running, under the rig lock (`.prev` is 647's
  `9dc45991`); nothing to the Pi, a server has no menu. THEN RUN ONCE ON THE
  OWNER'S OWN INSTALL (16:40Z, `cfg_save_auto 0`, nothing picked or played):
  `maplist: saved 1787 map(s) from the directory, 0 row(s) not kept`; 20
  rows folded; `ui_build surf_ace` knew `surf_ace_css` (not installed, 18,088
  KB); the libraries count 1,189 both, 1,172 Momentum, 996 CS:S; with
  "rookie" typed by real keys the one row drew the switch. Looked at: that
  screenshot, MOM lit beside "KSF 2". `ftesurf.cfg` was not written;
  `data/mapdl.net.txt` is the menu's own and stays.

### Two builds of one map: zones, boards, and the list the game fetches (Patch 651) -- 2026-10-11

Lex's reply to 644's report: follow Momentum's updates; copy Momentum's zones
"if the map has a momentum mod version"; both games' times on both builds;
the game fetches its own map list. The menu half is Patch 652.

- **A SECOND BUILD TAKES THE PLAIN MAP'S ZONES ONLY THROUGH `surfd/zonefit.py`**
  (`mapwatch.py`, "ZONES GIVEN TO A SECOND BUILD"). The target is a `<name>_css`
  that is KSF's archive (`made`) or a port by suffix (`PORTS`; `_v2`, `_new`
  and `_redux` are maps, and a `_css` that is not KSF's archive is nobody's
  port). Not Momentum's own name under any row, not a Beta map, not one with
  zones in `zones/online` or `zones/local`, not one with Momentum's timer
  triggers in its BSP. Measured read-only on the Pi's files before deploy: 24
  FIT, 3 SHIFTED (surf_aquaflow_css, surf_ravine_csgo, surf_sequoia_fix), 41
  with zones already.
- **THE FIT RULE IS `tools/census/zonefit.py`'s, COPIED** (tools/ is not on the
  Pi): world mins within 64 units, every start/end/stage region inside the
  target's world, every `teleDestTargetname` present. `test_zonefit.py` runs
  both on the same pairs. What it does NOT see, from the review: a world
  rearranged inside the same box; a name carried by an entity that is no
  destination; a file naming no destination at all (22 of 549) rests on the
  mins. The review's count on Momentum's own install: 61 FIT port pairs, 59
  sharing a frame by named-entity offsets, 2 unmeasurable, 0 moved; of pairs
  of unrelated maps that share mins, 4 of 1,143 passed.
- **`given` IS WHAT MAKES A RE-RUN SAFE**: the zone bytes' hash and the
  target build's. A file edited since is somebody's. A target whose build
  changed is measured again and, no longer fitting, its file is moved to
  `zones/online/.old/` (with `--updates`, no lobby on it), else left and
  counted. A given file deleted by hand comes back next run: write a
  `zones/local` file to keep a map untimed.
- **A NUMBER NO FLOAT HOLDS ENDED EVERY RUN** in the first cut: `float()` of a
  400-digit integer in a zone file is an OverflowError, not a ValueError.
- **THE LIST** is `<state>/mapdl.txt`, `data/mapdl.txt`'s grammar with a tenth
  column on a second build (the map it is a build OF); `tools/mapscan.py`
  writes the column too. surfd serves it at `/api/board?maps=1`, on that path
  for `game_avatar`'s reason: nginx forwards a fixed list. The first run
  records every name `bootstrap`, so New means "arrived after the list began".
- **BOARDS**: `variant_base()` reads the catalogue's `of` rows (only a file
  compared with KSF's archive is one). A second build's board is its own
  native rows and the plain name's imported ones, in one ORDER BY; an
  ordinary map's SQL text is unchanged (25 of 25 bodies identical, the
  review). On the Pi's database: the same index (`runs_board`), 0.048 s
  against 0.017 s for a 100-row page. `/board/api/map` (the site) is not
  changed.
- **TWO FILES OF ITS OWN IN ANOTHER SHAPE** (`seen` in state.json, a
  catalogue row) used to end the run or add a row to the list; each now
  costs that row what it said.
- **MOMENTUM'S zoneHash DOES NOT MATCH ITS OWN ZONES FOR 92 MAPS** (11 Oct).
  No serialisation of the reply hashes to it. Three compared with the files
  held (surf_ace, surf_crush, surf_grassland) differ in `dataTimestamp` (now
  January 2026) and a new `globalRegions.allowBhop` and in nothing else: a
  re-save on their side that left the hash behind. So for those maps
  `--updates` could not have the zones (75 zone files and 17 builds) until
  Patch 664, above, which measured all 92. The donor of a second build
  is therefore the file the plain map is TIMED BY here, at the published
  build, hashed or not (4ceeca5): that gave surf_ace_css, surf_beginner_css,
  surf_lovetunnel_css, surf_rookie_css and surf_whiteout_css their clocks.
- **bhop_eazy WAS NOT UPDATED until Patch 664** (above): the engine gate
  compares `pm_dettest` on it between the Pi and Windows, and both held
  07320480e924 where Momentum publishes 4ddeea8cc0fa.
- DEPLOYED 11 Oct: `610c1b0` to `/srv/nvme/surfd` (surfd.py, mapwatch.py,
  zonefit.py; SIGHUP, "surfd ready" 15:19:13Z), then `4ceeca5` (mapwatch.py,
  no reload, 15:34Z). Two runs by hand with `--updates` (15:20Z, 15:35Z): 31
  builds replaced, the old ones linked in `maps/.old/`; 14 zone files
  replaced; 23 second builds given zones (18 of the 21 `_css`; 3 SHIFTED and
  surf_vestige_fix has its own timer triggers); 985 of the 1,857 maps have a
  zone file (937 before). Seen on the host: `zones(sv): 12 on surf_ace_css
  (maps/zones/online)` and `6 on bhop_24` from a throwaway server;
  `play.proto.bar/api/board?maps=1` 200, 89,063 bytes, 1,787 rows, 20 naming
  the map they are a build of, the bytes of the watcher's file;
  `/api/board?map=surf_ace_css&tier=combined` counts 7,672 Momentum and 645
  KSF rows. The crontab line has `--updates` since 15:39Z (the line before:
  `data/mapwatch/crontab.pre651`).

### The library keeps itself level: `surfd/mapwatch.py` (Patch 644) -- 2026-10-11

- **LOOK AT THE HOST.** This file said the Pi served 1,743 of 1,748 catalogued
  maps. It served 767 of 1,753 (465 of KSF's 929, 379 of Momentum's 1,164): the
  5 Oct restore stopped at `surf_k`, and what `mapgrab.py` had fetched from
  Momentum's CDN was never fetched again. `data/mapscan.log` had printed
  "catalogued but not on the Pi: 1052" every six hours, to nobody.
  `mapsync.py` put back the 586 this PC holds (1,349 after); the rest is the
  watcher's.
- **MOMENTUM'S CATALOGUE CAN BE FETCHED**, which this file and `mapgrab.py`
  both denied. `/v1/maps?gamemode=1|2&expand=currentVersion,leaderboards`
  answers anonymously for APPROVED maps (ranked and unranked boards: 758
  surf_/bhop_ names) with bspHash, downloadURL, zoneHash and the tier.
  `/v1/maps/submissions` answers 401, so the Beta list (319) still comes from
  the game's cache on a PC: `mapscan.py` writes it to the Pi as
  `data/mapwatch/extra.tsv`. Zones are anonymous too:
  `/v1/maps/<id>?expand=currentVersionWithZones`, and the `zones` object as
  sent is byte for byte the game's file and hashes to zoneHash.
- **KSF'S SITE IS AHEAD OF ITS DRIVE.** `ksf.surf/maps` embeds its whole list
  in the page (952; the sheet stops at 929, 17 April) with `/files/<map>.zip`,
  one bare `.bsp`. OuiSURF/Surf_Maps on GitHub is a README naming the same two
  Drive folders and sheet `maproster.py` already reads.
- **A CS:S INSTALL'S COPY IS NOT KSF'S BUILD.** Of six maps this PC's
  `cstrike/maps` matched KSF's own archive on three; surf_kitsune,
  surf_beginner and surf_ace are a THIRD build, neither KSF's nor Momentum's.
  So the second build of a name both list is KSF's archive, kept as
  `<name>_css` where its bytes differ (`--variants`; ROADMAP 8). It gets no
  zones from the watcher. `state.json`'s `made` is the record that a `_css`
  file IS that archive; one without a record (somebody's own, or the state
  lost) is compared again, never written over, and is not catalogued until
  it matches.
- **`import surfd` SETS umask 077.** A cron tool that imports it and writes a
  file nginx serves must chmod it; the first cut wrote every map 0600, a 404
  to every player. The suite's mode check measures on Linux only and says
  "skipped" on Windows: run it on the Pi (it fails there with the chmod out).
- **ZONES ARE WRITTEN NARROWLY**: only Momentum's, only on the hash, only for
  a map held at the build that row publishes (49 held builds differ; zones are
  world coordinates), never under `zones/local`, and never while a lobby is on
  the map or the lobbies cannot be heard (a run in progress is in `data/parts`,
  which nothing here reads). A NAME with a native run, save, parked run or
  kept evidence gets its FIRST zone file only with `--updates`: the file
  changes its zone crc and what a parked run resumes to. That includes a map
  installed the same run -- the review's catch: a BSP lost on 5 Oct and
  fetched again still has its runs, and the log names each one ("installed
  under a name that already has runs").
- **`--updates` IS OFF, and bhop_eazy is why to think before turning it on**:
  it is one of the 49, and `pm_dettest` on it is the engine gate. A replaced
  build orphans every run set on the old one; nothing reads `.old/` back.
- **A REFUSAL IS ABOUT THE HOST, A BAD FILE ABOUT THE FILE.** A 403, 429, 503
  or silence ends that host for the run and sends that file to the back of
  the next; a bad hash, bad archive, 404 or the file's own 5xx is struck
  (3, then 30 days), keyed with the build's hash. A 200 that does not start
  as a BSP or an archive is the host's (a block page), refused at its first
  bytes. The first cut had one 500 blocking a host for ever, and a 403 for
  everything shelving every file.
- **WHAT A REPLY CAN COST IN MEMORY IS NOT ITS SIZE.** `zipfile` inflates a
  bzip2 or LZMA member all at once whatever the directory claims (a 313-byte
  archive: 449 MB), so only stored and deflated members are read. The regex
  for the page's escaped strings took ~280 MB per megabyte of one chunk; the
  scan that replaced it takes 1. A list reply at the 6 MB cap parses to
  ~200 MB, and a list page holding more maps than were asked for is refused
  (every name is kept). `be_small()` caps the process at 1.5 GB and marks it
  first for the OOM killer.
- **NO READ CLOCK COVERS A REPLY'S HEADERS.** The body clocks start at the
  first body byte and the socket timeout restarts at every byte, so a host
  dripping headers held the lock for ever (the review ran it: 12 s against a
  3 s limit). `opened()` gives that wait its own SIGALRM deadline
  (`OPEN_SECONDS`), ended as a refusal by that host; a `faulthandler` watchdog
  exits a run that outlives every clock. Linux only: the suite's case for it
  says "skipped" on Windows and fails on the Pi with the alarm out.
- **HISTORY IS READ AT THE WRITE, NOT AT THE START.** Round 3's fix read
  `played()` once before the downloads, and the next review wrote a zone file
  under a run set meanwhile. It is read again (0.6 s on the Pi, 5 s cold)
  between the zone request and the write, with a look at the lobbies on BOTH
  sides of that read: one that came during the request is seen before it can
  slip a run past it. A history folder that is listed and will not open, or a
  game data folder that is not there, is "cannot tell", not "no runs".
- **FIVE REVIEW ROUNDS, AND WHY IT STOPPED.** Rounds 1 to 4 each found a way
  to put a zone file under a run or to hurt the box (round 4's was a
  regression from round 3's fix). The fifth, on the zone-write path alone,
  found a window one `played()` wide and the missing-folder reading; both are
  closed above and have a failing mutant. Nothing after that was reviewed.
- **Cron**: `23 */6 * * *`, `flock -n /tmp/surfd-mapwatch.lock`, `--variants 20
  --site-zones /srv/nvme/ftesurf-site/zones --go`; state `data/mapwatch/`
  (`catalogue.json` is what `mapscan.py` reads back); log
  `logs/mapwatch.log`. About 10 list requests a run when nothing is new.
- **THE SCAN ON THIS PC RUNS `C:\FTESurf\tools\mapscan.py`**, and that
  checkout is not kept at origin/main: the task runs whatever is there. It
  was 101 commits behind until the 0.1.24 release moved it on 11 Oct, and was
  fast-forwarded to `ed14d91` after the fill.
- DEPLOYED 11 Oct from `ed14d91`: `mapwatch.py` and `ksfimport.py` to
  `/srv/nvme/surfd` at 12:38Z by `surfd-deploy.ps1 -Only ... -NoBackup
  -NoReload` (the whole suite ran in the stage first). The first live run
  installed three maps: mode 0644, zones with them, `play.proto.bar/maps/
  bhop_25.bsp` 206, the client's zone URL the same bytes, and a throwaway
  headless server printed `zones(sv): 4 on bhop_25 (maps/zones/online)`.
- THE FILL, 12:40Z to 13:36Z (`--max 600 --max-gb 40 --zones 500 --variants
  20`): 340 requests, 505 downloads, 485 maps and 20 `_css` builds, 11.5 GB,
  54 MB of memory, no refusal. After it: 1,857 BSPs, every file 0644, no
  leftover; held 758 of 758 approved, 319 of 319 Beta, 951 of KSF's 952 (one
  has no archive); a dry run says `new: 0`. 382 names are still to compare
  for a `_css` build, 20 a run. The crontab line went in at 12:40Z (the one
  before it is `data/mapwatch/crontab.pre644`).
- A MAP HELD IS NOT A MAP TIMED. 937 of the 1,857 have a zone file (871 in
  `zones/online`, 66 local): 713 of the 758 approved, 121 of the 319 Beta, 67
  of the 549 KSF lists alone. Six approved maps' zones did not hash to
  `zoneHash` and were not written (surf_bewatermyfriend, surf_colum_up,
  surf_fortress, surf_het, surf_meridional, surf_reytx); 84 held zone files
  differ from the published one and were left.
- THE CRAWL ORDER, SEEN: of the boards fetched in the two hours before the
  deploy 7 of 149 were Forward main boards; in the first tick after it, 8 of
  10. 367 of 450 main boards held one page at 12:43Z (372 of 448 that
  morning): at 8 new pages a tick, about a day and a half to 200 rows each.
- **TWO TOOLS, ONE HOST (Patch 650).** The KSF crawl parked itself at
  13:31Z on 11 Oct ("read operation timed out": six hours, doubling each
  time) while 644's fill was downloading archives from ksf.surf, 13:28Z to
  13:36Z. It had also timed out the day before with no watcher running, so
  the cause is not shown; the overlap is, and at 20 archives every six hours
  it would have recurred. `mapwatch.py` now holds the crawl's own lock for
  each request to ksf.surf (`/tmp/surfd-ksfwatch.lock`, the one the crawl's
  cron line takes with `flock -n`, so a tick starting meanwhile is skipped),
  waits `KSF_WAIT` for a tick in progress, and asks KSF nothing while
  `data/ksf/.refused` says the crawl is parked. The lock cases need flock:
  "skipped" on Windows, graded on the Pi, where six mutants fail. DEPLOYED
  11 Oct 13:48Z from `0aa7e64` (`-Only surfd/mapwatch.py -NoBackup
  -NoReload`); a dry run on the Pi then printed `ksf: NOT READ (it refused
  its crawl ...: nothing asked until 2026-10-11 19:31 UTC)`.
- `mapscan.py --go` from `C:\FTESurf` at 13:40Z: the Pi's catalogue 1,647
  names, 37 the roster did not have; 319 Beta names sent; `mapdl.txt` 1,787
  rows (1,279 in the 0.1.24 archive, 705 lines before that).

### P698 — map manifest, real port links and held beta zone donors

- The admin manifest is **https://play.proto.bar/admin/maps**, NOT
  proto.bar/ftesurf/admin/maps. Its board links use SURFD_BOARD_URL (the
  existing public proto.bar/ftesurf/board route), not play's nonexistent /board.
- A disabled mounted build must stay in `?maps=1` with `of zoned enabled`
  columns. Omission is not policy: the menu discovers local BSPs independently.
  Pool state is per build in SQLite `map_pool`, absent entries enabled. The
  updated menu refreshes at most once/minute with online consent; offline uses
  the saved feed. /api/join enforces policy for older clients too. Explicit
  console maps and configured rotations are not rewritten by these controls.
- A beta/extra donor can be valid even without an API zoneHash: match the held
  BSP to extra.tsv, require well-shaped zones fitting that donor, then still
  apply destination geometry/restart checks. `donor_of` must admit `extra` as
  well as approved `mom`; adding donors alone does nothing if the loop retains
  its approved-only gate (the acted extra integration test caught that).
- Real KSF known-port suffixes can link to held MOM extra roots too. `names`
  alone is the API set and may omit extras: pass `names | set(extra)` to the linker.
  Namesake _css files stay independent unless archive-compared, and _v2/_new
  are never stripped. Imported boards share a group in both APIs; native rows
  stay on the exact build. SQL uses MULTI-INDEX OR / covering runs_board lookups
  for the live aircontrol alias, not a whole-table scan.
- `surf_aircontrol_ksf` already had an authoritative LOCAL zone on the fleet;
  absence in online/ is not absence of zones. Preserve it. P698's copy pass
  installed 28 other compatible zones; 29 refused transfers were left alone.
  The live manifest at 07:25Z on 14 Oct had 2,033 BSPs, 875 missing-zone maps;
  no maps were disabled by default. The live disable/re-enable control restored
  its original policy row exactly (zero fixture rows afterward).
- `mappool_smoke.py` uses synthetic offline consent only in an owned overlay.
  A cvar alone does not set menu `ms_consent`: seed data/consent.txt there to
  inspect Create Server instead of accidentally screenshotting terms. Keep
  the initial renderer delay before `map`, then menu_restart. `ui_find` is a
  substring query: `surf_ace` also finds surf_acerbus; use a unique disabled
  fixture for the zero-row arm. `ui_browse` restores the prior show-all setting,
  so set/open Create Server before claiming its post-browse visibility.
- Source/deploy provenance: `tools/p698maps.md`. All 19 staged Pi suites passed;
  Windows admin's two rcon/cache timing failures reproduced on the unchanged
  e008c3b control. Node syntax checks are explicitly skipped if Node is absent
  on the Pi; the actual page's JS was exercised in Chrome on Windows.

### P699 — zone coverage, explicit KSF top-up and binary replay format

- Census at 07:53Z 14 Oct: all 759 approved Momentum BSPs held on the Pi had
  zone files. Of 320 held beta/extra maps, 199 had no indexed zone file;
  online-only inspection found 198, three with embedded start+stop triggers.
  Beta download membership is not a promise of public API zones. Look in LOCAL
  as well as online/. Never copy a namesake zone across an unmeasured build.
  Later LOCAL census is different: 759 approved held in Momentum Playtest,
  39 missing JSON (including bhop); 38 BSP SHA256s differ from the Pi's builds.
  Only bhop_perspective matched and passed zone_on_build; its public zone was
  seeded to both Windows installs without overwriting anything. Do NOT turn
  the fleet's complete approved coverage into a claim of local coverage.
  Version reconciliation/archived zones for those 38 remain BACKLOG.
- surfd's map index now recognizes bounded, valid BSP brush start/stop pairs;
  zonefit caches by path+mtime_ns+ctime_ns+size so replacements invalidate it.
  The menu says 'zones not listed' rather than asserting no timer exists when
  its available catalogue cannot prove one. No personal zone files are fetched.
- Schema 17 adds ksftopup. POST /api/board?ksfmore=1 or /board/api/map queues a
  known KSF leg/style; GET remains read-only for this action. Canonicalize links
  with variant_base. Active requests coalesce, 64 active keys globally, +100
  source rows/request up to 10k/board. --watch consumes three keys/five pages
  each under its existing request/delay/refusal park. Only finish_topups AFTER
  write_rows; durable cached rows/owed markers recover a cut before filing.
  Source exhaustion is not 'there are no more rows on our current UI page'.
- FW is KSF mode0 / clean, SW=1, HSW=2, BW=3. Style is a separate board key,
  not a verification class. The game's selectors force KSF for non-forward;
  returning to another source resets clean. Website empty KSF-style tabs can
  still ask for their first batch on a known leg. Bonus4 is zone34, not stage4.
- FTE uri_get callback code for HTTP 202 is 202, NOT 0 (only 200 is normalized).
  An acted POST had durably queued while the first UI callback falsely said
  failed; positive runtime witnesses now pin both VMs' 202 acknowledgement.
- The operator's KSF /replays/<map>/<file>.rec links are HTML viewers. CSS raw
  bytes are /api/replays/<file>?game=66t. The public gokz/js/replayviewer.js
  describes versions2/3: 4 int32 header cells; v3 adds frame/extension sizes;
  524-byte bookmarks, then fixed-stride pose/angle/buttons/velocity frames.
  All twelve supplied files decoded (3 v3, 9 v2). tools/ksfreplay_info.py is a
  bounded OFFLINE inspector only. Frames include lead-in/out; header tick
  count alone is not the advertised timed duration. Playback/conversion is
  BACKLOG, not evidence that no usable public replay exists.
- Tests/provenance/limits: tools/p699ksf.md. Chrome smoke uses real-time CDP
  (Node's built-in WebSocket), an owned headless profile and explicit GUI state
  waits. A hash changing is not proof that its next board has rendered yet.

### P706 — original KSF files and automatic sparse demo imports

- Public cached board rows already carry `file` when a demo exists. Consume
  that field, not guessed filename numbers or a request per player. The existing
  board crawler discovers it; equal-time/newer metadata must refresh too, since
  an unchanged PB can gain or lose its file. Only CSS/66t main/bonus courses are
  supported. Stage cuts, CSS100/other clocks and BSP build identity stay explicit
  limits. Original files contain no trustworthy map/player/style binding.
- `replay ksf <binary> <map> <bonus> <style>` normalizes original v2/v3 bytes into
  Watch's imported buffer without Python or writing player data. Bounds precede
  fopen/fsize/fread because those builtins materialize the file. 16 MiB and
  40,000 frames bound the synchronous VM. Preserve bookmark clock, raw buttons,
  six-decimal normalized analog direction, source velocity/ground where present;
  never infer duck state, map hash or native evidence. Imported .rec/board/API
  playback still uses the existing viewer and integer `rep` protocol.
- `ksfimport --watch --go --demos` reserves up to two requests WITHIN --max,
  holding its shared lock through demo discovery/download/index. First download
  sleeps too, after the board request. Fixed-origin no redirects; shared host
  cooldown covers socket/header/body failure and ALL non-2xx, not just 429.
  Normalize transport errors before local conversion/archive OSError handling:
  ConnectionResetError and IncompleteRead are not per-file disk failures.
- Exact binding includes upstream record/date, raw double seconds and advertised
  file hash, not rounded millis alone. Seed records MUST retain raw seconds and
  cannot revoke an unchanged known binding without board file metadata. A faster
  PB clears its old rep. Original/provenance writes precede transactional exact
  recheck/link; failed indexing retains intent. Warm missing files retry. Retire
  obsolete jobs and three-strike local failures so a bounded queue can progress.
  Exclude readable exact warm links BEFORE admission as well as pending retention;
  otherwise 256 current warm jobs can starve one cold row forever. Persist
  local-only removals/empty ticks, not just attempted downloads. Missing or
  unreadable warm files remain recovery candidates.
- Imported times on a catalogued variant retain their time rows but KSF `rep`
  is suppressed when its stored map differs from the requested build. Do not
  remove Watch's exact map guard to advertise an unplayable action.
- Compiler finding: this fteqcc crashes silently when the new console condition
  calls undeclared `argc()`. Baseline and loader-only arms compile; console-only
  reproduces exit139. QuakeC uses the return of tokenize(cmd), not argc(). The
  original one-argument Watch_Open wrapper remains compatible with all callers.
  Pass float booleans to sprintf %g (or explicitly cast for %i), including codec
  capability metadata; the QC varargs declaration is not a type-conversion gate.
- Commands, limits and provenance: tools/p706ksf.md. No native reader/evidence
  semantics, engine pin/tag or QC Build change. Fleet delivery is a separate gate.

### KSF backend codec shipping (source-only continuation, 2026-10-14)

- Staging codecs for the backend suite does NOT install them. The pre-continuation
  surfd-deploy allowlist only shipped surfd/, although ksfgrab requires both
  tools/ksfconvert.py and tools/ksfreplay_info.py in the flattened backend layout.
  Default shipping now includes those two allowlisted tools. A selective importer
  or codec selection expands to the matched app/importer/codec five-file set;
  an app-only selection remains narrow. Unknown paths and absent committed
  dependencies refuse. PlanOnly resolves a full immutable SHA with no SSH or
  scratch creation; archives and verification hashes use the same SHA.
- Backend suite now invokes test_ksfgrab with its required owned --out, plus the
  codec tests. Export TMPDIR BEFORE $(mktemp -d): TMPDIR=x command $(mktemp -d)
  assigns x too late to control the substitution. Exclusive local/NVMe stage
  roots are owned before population; no startup blanket cleanup or service-dir
  scratch. Failed stages/logs are retained and reported; success keeps a local
  ownership/plan receipt. Live backup retention remains a separate decision.
- Offline falsifiers: tools/test_surfd_deploy.py, seven groups; the real flattened
  collector/index/Flask test-client suite passes 17 tests. Either missing codec
  acts as an import failure. Actual suite shell controls propagate collector and
  converter failure, and test homes stay under the owned stage. Existing codec,
  import/top-up, board and replay suites also pass. Commands/evidence/limits:
  tools/ksf-deployment.md. No game/GPU tests, remote installation, reload, cron
  enablement, native source, product patch, engine pin/tag or QC Build change.

### P711 — recover retained KSF originals without rebinding a stale PB

- Interrupted indexing already retained bytes but the next tick fetched them
  again; a missing normalized replay did the same. New installs publish bounded
  `job-<exact-binding-sha256>.json` provenance beside digest-named originals.
  Lookup includes map/course/style/player/runid/millis/date/advertised file;
  verify metadata and complete original SHA256 before conversion, never scan
  the archive or trust a path from JSON. Reuse remains subject to exact-current
  checks before and inside the link transaction. Old unkeyed archives are a
  cache miss, not an implicit migration/scan or identity authority.
- Read/convert at most two retained originals per tick, including corrupt or
  missing-byte attempts. A known third retained job waits rather than falling
  through to a redundant download. Local repair runs with zero request allowance
  and host cooldown; existing job retry times still apply. Persist admission
  rotation even for missing bytes: two leading misses must not consume both
  slots forever while a later intact original waits through a cooldown.
  Missing bytes can use the normal remaining request allowance;
  malformed/mismatched/deeply nested provenance, links or corrupt originals
  defer locally without parking the host.
- Equal raw seconds are NOT equal upstream record identity. Seed metadata lacks
  the advertised file, but supplies record ID/date: unchanged/unknown identity
  cannot revoke a valid known board binding; a different known current ID/date
  clears it. Older/slower/rounded-only rows retain existing non-authority gates.
  Regression splits formerly incorrect preservation of a replacement from the
  genuinely unchanged-record control, and requires board metadata to restore it.
- Source/offline checks, controls and limits: tools/p711ksfrecovery.md. No new
  stage/CSS100 support, codec clock/map guard/native evidence semantics, game/GPU,
  remote install, cron enablement, engine pin/tag or QC Build change.

### P713 — close KSF cache/CLI/publication and backend delivery gaps

- **A cached board is not a newly fetched authority.** After a seed replaces a
  known equal-raw-time/same-date record ID, an older owed board must not change
  it back and make its old original linkable again. `board_rows`/`map_rows`
  label cache-only rows; only exact row identities fetched THIS tick get board
  authority, including mixed owed/fresh boards and `--from-maps`. No record-ID
  monotonicity is inferred. Older/slower/rounded-only and unchanged/unknown seed
  protections remain; fresh exact board/file metadata may restore the binding.
- **Opted-in demo recovery is independent of its network reservation.** Real
  `--watch --go --demos --max 0/1/2` still calls the collector with zero demo
  requests, under the shared lock. Cold downloads remain bounded by the reserved
  allowance. Publish exact-job provenance BEFORE original/normalized bytes so
  a normalized-file write failure cannot strand a newly retained original.
  Intent without completed original bytes uses the existing missing-byte path.
- Cap the common advertised ASCII leaf at255 before integer conversion, queue
  admission or request construction. A sub-cap board can otherwise carry a
  5,000-digit player/date filename and abort the whole tick. Malformed rows must
  not request/park the host or prevent the following valid row from linking.
- **Delivery verification must act on the claimed state.** Ref-query failure is
  not publication; use raw `git hash-object --no-filters --` at the destination.
  Reload snapshots the inspected master's direct workers and waits bounded60s
  for all old workers gone, exactly one new child, that PID's fresh ready line,
  healthy response and successful remote exit. Track log rotation and a monotonic
  deadline; cap health and sleep to remaining budget, not30 sleeps plus HTTP time.
  Old health/global process counts/
  historical boot lines cannot verify a replacement. Do not print app log tails.
- Original-source red controls reproduce all six reviewer findings plus the
  filename boundary. Repaired offline collector28, codec9 and delivery10 groups
  pass; full backend regressions and exact final-commit checks are recorded in
  tools/p713ksffinal.md. No upstream/game/GPU, installation/reload/cron, native
  evidence, engine pin/tag or QC Build change. Live fleet acceptance is deferred.

### KSF top-up fresh authority and saturated cold admission — P714, 2026-10-14

- **Cache filing is not an answer from upstream.** Explicit top-ups used to
  discard actual pages and append the entire cache to `fetched`, including
  completed boards requiring zero requests. This revived same-time/same-date
  superseded seed bindings despite the P713 owed/from-maps guards. Keep actual
  pages and whole-cache filing separate; both initial owed states must match
  fresh authority by exact valid player/runid. No-page and unrelated-fresh-page
  arms preserve B; genuinely fresh A proves the positive path can still act.
  Mark intent before filing/acknowledgement, even for cache-only completion.
- **Queue cap must not silently disable local recovery.** A full pristine-cold
  queue stranded retained repair257 at zero allowance. Bounded priority admits
  at most two provenance-present candidates by replacing only cold intents
  with no retry/strike metadata. Presence is scheduling only; bounded exact
  provenance, digest and PB/transaction checks still authorize bytes. Retained
  and deferred intents are protected, not forcibly evicted. P717 later closes
  fully protected admission with a bounded local overflow lane; a genuinely
  full active deferral ledger still conditionally refuses unknown work. Queue256
  and two original reads/request caps are unchanged.
- Original-source controls fail at the intended stale-binding and cold256
  guards; cold255 and real fresh A are positive witnesses. Repaired collector31
  and top-up8 pass; final source/read-only review and exact-commit evidence live
  in tools/p714ksfaccept.md. No fleet/game/GPU/native acceptance is inferred.
- **Exact-commit means modes too.** Read each selected blob's mode from the same
  Git tree, install/verify644 or755 alongside raw bytes, and record executable
  bits for every documented direct entrypoint. Historical commits keep their
  own modes; a .sh suffix is not permission authority. Windows/DrvFS mode shims
  validate only forwarding/predicates; actual POSIX execution stays a Linux gate.
- **A copy-only flock cannot protect a deployment receipt.** Hold a persistent
  cooperating-deployer lock through backup, install, hashes, fresh worker/reload
  acceptance and a final invocation/full-commit-specific ACK. Fresh bounded
  per-phase ACKs reject a disconnected holder; the final remote under-lock ACK
  is acceptance, not a guarantee against later/noncooperating writes. EOF closes
  only the owned helper; never unlink the lock or signal an owner process.
- **Unique stages are not unique backups.** Both DB/file tags need the invocation
  nonce and exclusive name reservation; same-second same-ref collisions must
  preserve the older rollback. Retention matches both historical/new owned
  shapes, not hand-made backups. Do not delete stage/logs before final acceptance:
  a reviewer caught cleanup-before-ACK evidence loss. Pre-ACK failure retains;
  post-ACK cleanup failure warns and records accepted/cleanup-unconfirmed with
  the exact inspection path. Transport failure may follow successful removal;
  never claim retained logs without confirming they still exist.

### P717 — retained repair through protected queues and rotating board windows

- Cold-only admission is insufficient when all256 intents already hold protected
  retry/strike/provenance. A <=2 transient local-only overflow lane shares the
  original read/conversion cap2 with queued work; missing bytes never fetch.
- One global row cursor across SCAN32 windows repeats the first misses in each
  half of a64-board cache. Persist one board+exact-key resume position, resume
  inside that board, and move on when its window has no eligible candidates.
  The acted64-board gate repairs both later healthy originals across8 fresh
  Python process restarts without sleep/fetch or loss of256 protected intents.
- Preserve expired retry strikes, but reconcile <=2048 nonterminal histories
  against scoped exact-current PBs and linked-file readability. Obsolete/ready
  histories must retire or they permanently saturate capacity. At a truly full
  active ledger, decline new overflow; queued terminal intents hold their slot
  until seven-day expiry rather than lose history or attempt a fourth time.
- Legacy writers can append failures after truncation and save2050..2304 entries.
  After normal expiry, an oversized active set parks LOCALLY before DB/work/save,
  preserving historical bytes and refusing no host. Accepted processing/new
  writes are capped2048; preserved historical files are not physically normalized.
- P716 null-ID profile PB .0599 can replace identified .0601 at rounded60ms,
  then stale filing/legacy repair rebinds the old record after raw clock is lost.
  Schema19 ksf_unbound retains precise seconds/millis/submitted per exact scope
  in the same transaction as PB writes. Cache cannot bind; slower fresh records
  refuse, matching fresh identity clears metadata. Current/install/legacy paths
  all refuse matching markers. No record ID or native evidence is fabricated.
- Original18 empty-runid KSF rows are ambiguous. Mark unknown precision without
  rewriting runs/guessing clocks; native/identified rows stay unchanged. Fresh
  identified authority is needed, and an unknown same-ms clock cannot reject a
  subtly slower fresh record until precision is regained. Provably pre18 legacy
  remains compatible; malformed matching markers require explicit repair.
- Forward integer reading is NOT old-reader/old-writer rollback: old ticks erase
  new dictionaries; old18 writers do not honor markers. surfd migrates on import,
  BEFORE the importer's inner lock. Deployment/sweep flocks alone are insufficient.
  Approved live transition must exclude/drain old cron/manual writers BEFORE any
  install/import and retain fail-closed exclusion through coherent six-file
  install, migration, accepting-generation verification and receipt, even on
  failure/disconnect. Preserve source+DB+demos.json; do not overwrite later native/
  player data or delete/reset metadata to downgrade. No live transition executed.
- Independent review closed3 queue/state P1s plus1 incoming null-ID authority P1.
  Frozen Windows collector45/profile16/importer106/top-up8/codec9 and explicit
 13-boundary account/board19 migration controls pass. Synthetic10000-row local
  WSL19 migration is indexed/idempotent and preserves runs (~0.010s), not live
  sizing/availability proof. Final exact current native18/flattened45/backend21
  receipts remain required before publication. Limits/commands are recorded in
  tools/p717ksfprotected.md and owned CHECKPOINT. Native Node/corpus/Pillow/MTV,
  fleet/crawl/cron/game/GPU and crash/power-loss acceptance are not inferred.

### P717 continuation — process-death controls and native optional runtimes

- `tools/test_ksf_interrupt.py --out <owned-root>/artifacts/cuts` creates fresh
  synthetic homes only. Five deliberately spawned worker cuts ACT inside/after
  PB/precision-marker transactions and cursor acknowledgement. Fresh readers
  distinguish rolled-back from committed pairs; restarted owed pages must use
  durable bytes with HTTP forbidden. An uninterrupted positive and an explicitly
  TEST-ONLY split-transaction defect prove both oracle directions. Unrelated
  identified/community fixture rows and SQLite integrity remain unchanged.
  The fourth group proves inherited config/game-code sentinels are not opened:
  scrub SURFD_* and set ACTUAL ENV/GAME_CODE/KSF_RUNS keys before import. An
  independent review caught the earlier wrong-key leak; acted audit red/green
  and final review close it. Windows/native four-group proofs are retained.
  Optimization (`-O`) refuses because worker assertions are load-bearing.
  This closes subprocess-death coverage, NOT storage/power loss or live drain.
- Exact P717 native source additionally exercised ten optional-runtime scripts
  with root-local official Node24.14.0 and Pillow12.1.1. Seven JS/template inputs
  parse and invalid JS refuses; ranked/Steam picture JPEG/PNG branches act.
  No owner corpus was read. Real MTV conversion remains explicitly skipped:
  a default fixture path existing is not proof of public sample provenance.
- Live18->19 remains blocked on persistent PRE-IMPORT launch exclusion and
  natural drain. The ordinary deployer REQUIRES a live gunicorn master; its
  per-file installation permits worker-recycle imports, even with -NoReload.
  Do not use it as a stopped-app transition protocol. A reviewed quiescent-start
  driver/procedure and coherent source+SQLite+KSF-cache recovery bundle are still
  required; failure/disconnect must stay fenced. Never overwrite later native/
  player writes, clear metadata or source-downgrade to fake rollback.
- Additional commands, acted controls, prior fixture-premise failures and limits:
  tools/p717ksfprotected.md and the owned ksfcont-20261015T000538Z artifacts.
  Tooling/tests only: no product patch, engine pin/tag, QC Build or live action.

### P717 continuation — cooperative launch-fence preparation

- `tools/surfd_transition_guard.py` is a stdlib POSIX pre-application-import
  admission helper, NOT an end-to-end schema transition. Close fsyncs persistent
  CLOSED before a bounded exclusive drain; launched foreground processes retain
  a shared flock across same-PID exec. Missing/malformed state refuses. Reopen
  requires a closure/generation/raw-six-hash-bound external receipt but does not
  attest its truth. Candidate start and generation rebinding remain BLOCKED.
- `tools/test_surfd_transition_guard.py --out <NEW-owned-path>` exercises real
  module-import/writer/shared-lock activity, controller death/EOF, direct bypass
  as an oracle-negative control, and eight simulated installation-phase cuts.
  Source FIFO/directory/symlink inputs refuse through nonblocking regular-file
  handles; canonical paths reject `..`. The test-only mutating controller must
  match an authored fixture identity/token/home/guard before any close or write.
  Initial review found the blocking FIFO read and unchecked test-controller
  path; focused controls now cover both. See tools/surfd-transition-guard.md.
- LOCAL WSL exact-source bundle rehearsal creates18 from fda98ed and migrates19
  with65250ec; it exercises interrupted partial installation, matched online
  SQLite/source/cache restore before later writes, then retention of later
  synthetic SQL/cache rows after process death. It does NOT prove authenticated
  native submits or enforced exclusion. Initial imports missed GAME/GAME_CODE
  overrides; audited rerun sets fixture paths, observes actual fixture-code reads
  and denies default-host opens before the OS. Earlier isolation claim rejected.
- A backend outage is NOT no-loss: sv_lobby.qc posts finishes/stages once and
  does not retain a durable retry body; local recordings are not board acceptance
  (the existing Ranking integrity BACKLOG records this). No live quiescence until
  native-submit admission/in-flight drain is independently agreed and verified.
- Source-backed findings, exact commands, initial failures and bounded evidence:
  C:/FTESurf-worktrees/ksfguard-20261015T002724Z/artifacts/CHECKPOINT.md. No real
  gunicorn/scheduler/FD-coverage inventory, owner migration or live action claimed.

### P717 continuation — foreground gunicorn lifetime and inventory boundaries

- `tools/test_surfd_guard_gunicorn.py` adds real LOCAL Linux gunicorn20.1.0 and
  23.0.0 upstream-pin controls: synthetic Unix-socket WSGI/gthread2, actual HUP
  and max-requests recycling, admission-lock dev/inode inheritance and independent
  exclusive contention, held-request graceful drain and exact-identity cleanup.
- CLOSED blocks new guard admissions, NOT an admitted master's recycled worker
  imports. Both real recycle arms import/serve while CLOSED and keep drain blocked.
  Installation must wait for successful drain, not merely durable CLOSED.
- The test-only FD-drop launcher still serves while close reports DRAINED; the
  same lifetime oracle fails. Foreground success does not certify detached/service
  routes or same-UID cooperation. Upstream pins are not distro-host equivalence.
- The approved read-only host inventory advanced launch-path knowledge, not
  enforced coverage. Raw metadata stays private; sanitized findings/remaining
  unknowns and the separately approved transition gates are recorded in
  C:/FTESurf-worktrees/ksfworkers-20261015T011756Z/artifacts/CHECKPOINT.md.
  No DB/schema inspection, owner migration or live mutation was performed.
- Test interface, dependency pins, source-derived launch families and limitations:
  tools/surfd-transition-guard.md. Candidate/generation handover, coordinated
  recovery and live native-submit no-loss acceptance remain separate blockers.

### P717 continuation — authorized candidate and legacy import gates

- The explicit Linux `candidate` route now admits one externally authorized
  fixed `server` while general admission remains CLOSED. Its independent
  candidate-lifetime flock survives exec/fork: promotion can hold admission EX
  without asking the candidate to exit; a full close drains BOTH lifetimes.
  Grant and receipt bind the current closure/generation. Reopen additionally
  checks the real candidate PID/start/cwd and held lifetime lock; only the
  separately measured external receipt asserts application/schema acceptance.
- `tools/surfd_import_dispatch.py` renders exact hash-pinned legacy wrappers.
  O_RDONLY shared flock works under a read-only service source sandbox; the
  real immutable module executes in its original namespace with genuine origin.
  Stale preloaded dependencies refuse. This gates APPLICATION imports/effects,
  not interpreter creation/startup hooks, and is not a same-UID sandbox. Pin the
  entire runtime/resources and drain every already-loaded old process first.
- `test_surfd_guard_gunicorn.py` now uses a live authorized synthetic candidate.
  Explicit `--host-distro` tests the actual installed Debian package sources and
  records dpkg/source provenance, separately from upstream20/23 pins. Native
  candidate and legacy-direct-import gthread2 tests passed with the installed
  distro bytes. These results are not production gthread4 or schema acceptance.
- `test_surfd_dispatch_gunicorn.py` proves original module identity/origins,
  worker O_RDONLY lifetime, held-request completion, and CLOSED HUP/recycle/fresh
  direct-worker refusal. The legacy master itself need not hold admission;
  workers must. A deliberate worker FD-drop still serves while drain succeeds,
  so the same independent oracle rejects it. Exact Popen/start identities alone
  are used for cleanup; no discovered-PID/group escalation is justified.
- A setgid scratch ancestor can produce mode2700 even with mkdir(mode0700).
  The exact owner-only guard correctly refuses it. Explicitly chmod only the
  NEW owned task root before fixtures; do not weaken private-state checks or
  chmod shared ancestors. Also, `python -I test.py` omits its sibling imports:
  isolate the trusted test HOME/env instead; reserve -I for standalone guard/
  launcher paths that do not require implicit source imports.
- Commands, exact hashes, acted controls, failed fixture/staging attempts and
  separate live-transition state: tools/surfd-transition-guard.md and
  C:/FTESurf-worktrees/ksfdeploy-20261015T014929Z/artifacts/CHECKPOINT.md.
  Tooling/tests only; no engine/product patch, pin/tag or QC Build claim.

### P721 continuation — Git observer identity and native deploy rollback

- A UCRT/MSYS host-test PATH changed `git` from Git-for-Windows to MSYS Git.
  Different system `core.autocrlf` made unchanged CRLF checkouts appear dirty in
  every engine worktree. The original failed guard is retained; explicit original
  `C:/Program Files/Git/mingw64/bin/git.exe` status/rawdiff and SHA256 inventories
  prove source/index closure without checkout/reset/config repair or host retry.
  Pin the observer executable as well as compiler PATH before comparing status.
- Native installation rollback must archive BOTH current and pre-existing `.prev`
  before mutation. A preflight process query is stale after hashing/compression;
  query at mutation boundaries, never kill a newly observed owner process.
  Hash-before-write alone is not ownership across forward writes and rollback.
- The bounded Windows ten-file helper uses nofollow lstat/fstat checks, refuses
  reparse/symlink (including dangling) and hardlinked writable aliases, and holds
  `CreateFileW` shareMode0/OPEN_REPARSE_POINT identity-bound handles through
  archive verification, writes, fsynced success receipt and independent recovery.
  Absent `.prev` uses CREATE_NEW; its rollback removes by owned-handle disposition,
  not arbitrary path unlink. Restore each recorded current/previous mutation
  independently even when another restore fails. Final archive hashing/receipt
  I/O must remain INSIDE the rollback exception boundary; receipt persistence is
  the commit point, not an unguarded afterthought.
- Twelve actual Windows scratch controls pass normal/-O without skips: late busy
  and inventory failure, linked aliases, blocked peer replacement/in-place writes,
  peer-created absent `.prev`, partial current write plus failed current restore,
  final receipt/archive-hash failure, exact ordinary rollback and lease retention
  at receipt persistence. Source-only initial review found five real blockers;
  all fixed and independently re-reviewed BEFORE the first deployment.
- Standard build.ps1 native destination contract is three CFTESurf files and
  seven CFTEQuake files, not a full install/config/QC-progs copy. P721 first actual
  transaction2026-10-15T02:40:50Z passes all10destination/current.prev hashes,
  archived old.prev CRC/SHA and unchanged config/progs/player-data aggregates.
  No global process exclusion or crash/power-loss atomicity is claimed. Separate
  installed-image2boot/4frame gate now PASSES204.5s/rc0/firstattempt: both actual
  installed client images and installed dedicated image have raw OS PID/path/hash
  proof; default1 original104.2 equality, mode0 preservation+42052pixel actor,
  4ordinary workers and complete1279held/protected/prev/owned-process closure.
  One unrelated native process at admission was untouched; NONEXCLUSIVE is not
  quiet timing. Plugin display `$system` is not independent OS DLL provenance.
  Quiet timing and broader renderer fixtures remain distinct open gates, not
  inferred from installed smoke, byte deployment or historical staged captures.
  Evidence: owned mapvisual task continuation-01a13d4e; product scope/pins and
  accepted native reference controls: tools/p721alphacull.md.

### P717 live backend transition: measured operational gates — 2026-10-15

- The reviewed backend generation reached schema19 and OPEN with all twelve
  lobbies recovered. The migration preserved the native/community row digest
  and made exactly 398705 legacy empty-ID markers at the cut. Schema19 does NOT
  invent IDs or delete those legacy rows; later imports can change the live
  counts. P722/schema20 compatibility and deployment are separate from this
  completed generation; do not equate origin/main with the live backend.
- Probe actual procfs capabilities before admission/outage. This kernel omits
  `/proc/PID/task/TID/children`, including for the observer itself. A bounded
  TGID/PPID census, repeated around FD observation with exact target-identity
  checks, supplies the relevant child predicate without that optional interface.
  Permission, malformed-record and bound failures must not mean an empty census.
- Start-of-frame counters alone do not prove deferred command timers ran. After
  producer suppression, empty HTTP contexts and the acted held-request oracle,
  require an acted zero-delay command-timer fence, then recheck map/process epoch,
  contexts, tasks, sockets and admission. RCON can execute before the ordinary
  command/timer phase. A test where frames advance but timers do not must block.
- Protected same-UID cwd/exe reads also need preflight. Do not blanket-skip them.
  Any narrow non-application-role exception needs fresh root-managed service or
  current-controller ancestry bindings and exact observed PID/start/PPID/argv.
  Keep an explicit unobserved-cwd sentinel and retain the record in descendant
  and candidate-family accounting; otherwise refuse. Systemd's cached ExecStart
  pid can be zero while its independently authenticated MainPID remains live.
- Restart lobbies behind persistent admission keys. Restore captured effective
  backend endpoints, rates and worker settings with auto-save still disabled;
  prove all fresh engine identities and heartbeats before releasing admission.
  Restore original auto-save last. Archive and identity/content-check only the
  generated maintenance/recovery configs before removing them.
- An immutable backend copy must include the assets its code actually opens.
  The board uses `WEB_DIR` beside `surfd.py`, not Flask's templates/static tree.
  Mirror the five published board assets, hash and seal them with the runtime,
  and test the real public board and each allowlisted asset, not only health or
  mocked web fixtures. Retain owner backup files without serving/copying them.
- Current cutoff evidence includes all23 backend suites, native guard/Gunicorn
  controls, controller/observer/adapter controls and independent targeted reviews.
  An additional live readback proves schema19, twelve fresh heartbeats, exact
  runtime/config recovery, no generated maintenance configs, guarded legacy
  entrypoints and HTTP200 for health, lobbies and the public board. Detailed
  recovery/process evidence remains private. No engine/QC patch or Build claim.
