# P722 — Steam friends, Players tab and overhead labels

## Contract

Friends belong to the linked Steam account across installations. A mutually
accepted friendship is required for fleet presence, Join and private Message.
Add/Accept is available from the account profile and the new full-width Players
scoreboard tab. The old sidebar is removed. ESC closes another player's entire
profile even when its search field owns focus. Players retains Spectate, profile,
chat mute and voice mute as separate targets.

This is fleet-server presence while connected to an account-enabled lobby, not
arbitrary games/Steam presence or a disconnected-main-menu reader. Pending
requests expose no location. Join resolves the current directory again rather
than trusting an old client address. Messages appear only in the recipient's
chat; they are short-lived, bounded, operator-readable and NOT E2EE. Sessions
expire after 24h and renew through the ordinary verified account proof. Social
capabilities are hashed at rest, bound to their lobby node, and never sent to
CSQC. The backend rechecks the linked key and ban status on every use.

Overhead pictures/names reuse existing body poses and the Steam picture cache.
Visibility uses view/range admission followed by PVS and a solid trace, at most
one scan per half-second per eligible body. Wall hiding may lag by 0.5s. Names
fade to zero at 1024 units; the picture centers as the name disappears. Default
picture range is 3000 units (`hud_playerlabels_far`, capped at 6000).
`hud_playerlabels 0` disables them. Opaque board/profile panels hide labels.
There is no extra pose traffic, native engine rebuild or QC Build-number bump.

## Verification and retained evidence

Owned task root: `C:/FTESurf-worktrees/friends-01a13cdc`. No real Steam IDs,
credentials, keys, private database rows or raw runtime logs belong in this file.
The fixture accounts Alice/Bob/Third are synthetic, with genuine client proofs.

Original feature verification, retained in that root:

- `build-v9.log`: server/client/menu QC compile, zero warnings.
- `test_social.py`: 21 tests, including proof authority, cross-install account
  graph, migration/concurrency, pending privacy, fresh Join, message delivery/ACK,
  string IDs, revocation, expiry, quotas and unavailable-peer removal.
- Account and board suites passed. Existing admin-log/metric boundary failures
  were unrelated and were not repaired or used to waive any feature assertion.
- `live-v5`: three real dedicated-socket clients and real local surfd. Profile
  Add, private draft and literal punctuation-safe PM to Bob but not present Third;
  spectator proof, pictures uploaded and persisted, session-expiry refresh followed
  by a new delivered list, full-width roster and focused-search one-ESC close.
  The photo cache is in the client's `data/cache/steampic`, not gamedir/cache.
- `labels-fixture`: real body/PVS, near typography, far fade/center, real world
  wall trace and behind-camera admission. `labels-mutant` removes LOS and pins
  alpha1; the wall/fade grader fails as expected. The fixture is TEST ONLY and
  absent from `cl_progs.src` / the ship build. Initial failed/racy arms remain
  failed evidence, not passes.
- Existing recorder checks: 306 checks, zero failures. Run corpus baseline stays
  289 run files, 148 completed/63 native, 48 known faults; no evidence semantics
  were changed.

Resume after merging published main through `c646a0f`:

- `pwsh -NoProfile -File ./build.ps1 -Jobs 8 -NoDeploy` from `src/`:
  all three QC outputs, zero warnings (`build-resume.log`).
- Account, social (21 tests) and board suites pass (`test_*-resume.log`).
- `python -B tools/test_surfd_deploy.py --out <owned-root>/deploy-regression`:
  19 tests pass. The actual staged shell runs a social sentinel, and its forced
  failure propagates nonzero. Selective app/account/social and KSF selections
  close both dependency groups against committed paths; a missing committed
  account module is refused even if it exists in the worktree.

Review/fix closure (after merging published P721 source/docs):

- `build-final2.log`: all three QC outputs, zero warnings.
- `transport-renewal-v2/verdict.json`: five checks pass. The real dedicated QC
  encoder sends all 41/42/64 populated rows repeatedly across >16s, five polls
  per arm, zero malformed payloads. The 64-row arm preserves decimal ACK
  `16777217`. Actual Account Think/nonce code, with only terminal nonce delivery
  replaced in a TEST COPY, proves live prompt/request deferral, stale-state
  retirement, renewal at exhausted client hello budget and bounded retries.
- `transport-final-mutant`: the original whole-array `uri_escape` preserves41
  but truncates42/64. Its grader fails as expected (8192-byte builtin limit).
- `live-final3/verdict.json`: all23 pass. Actual three-client proofs and HTTP
  transport establish PM privacy while Third is present; a forced first renewal
  HTTP503 acts, then a new proof and delivered list recover BEFORE Join. It also
  proves literal draft delivery, picture persistence, one-ESC close, Friends
  wheel scrolling and release-after-pointer-movement, cancellation when a held
  row is reordered, roster chat/voice mute toggles, Spectate and Join reconnect.
- Failed new harness arms remain retained and FAILED: malformed synthetic wire
  order, a nonexistent hover ID, a stale synthetic-list restoration and a CSQC
  status command issued too soon after reconnect were corrected, not waived.
- Independent backend/client reviews identified the transport, renewal, input,
  async row identity and Players-search integration fixes. Final backend and
  client closure verdicts are both OK. No broader full-tree audit is
  implied. The production ship manifests contain no fixture hooks.

New source adds `test_social` to the Linux deployment suite. Exact committed-
source build/tests and deployment receipts are recorded below when accepted,
never inferred from this preparation.

## Deployment boundary / rollback

At 2026-10-15T02:29–03:25Z the NanoPi is reachable but its live database remains
schema18 and `social.py` is absent. P717's schema19 old-importer transition is NOT
completed by this feature. Do not run a current `surfd-deploy.ps1` over that live
state merely because it can copy files: use the documented P717 old-writer
inventory, pre-import exclusion, whole-worker retirement and recovery protocol
first. Inventory/transition approval is separate; no jobs have been stopped and
no backend files or live schema have been changed by this continuation.

Schema20 adds only the private social tables after schema19. A rollback to
schema19 code must reset only `PRAGMA user_version` under the same deployment
exclusion; additive tables may remain. Never restore an old complete SQLite file
over newer ranked history. Do not attempt to roll P717 schema19 back through a
simple version reset; its own transition/recovery contract remains authoritative.
The existing progs deploy keeps `.prev` and refuses occupied/unproved lobbies.

## Remaining acceptance

See `lextest.md` for human wording/layout, real cross-install account use and
busy-lobby surfing/contrast/performance. The final real-client rig exercises Join,
Spectate and mute button clicks. 64-player roster layout/scroll and the Players
search-result/Back runtime path remain unmeasured acceptance; transport capacity
and reviewed source integration are not substitutes for those UX observations. No native/package release,
external Steam/R2 picture fetch or generic Steam-game presence is claimed.
