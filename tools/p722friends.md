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

## Committed-source verification and delivery — 2026-10-15

Published feature commit `ada325286aae3081fdb9651f10c8a7418ae2e8c5` and
engine-notes-only commit `dbf6bd40fae7a8d87fc56e51aa8bca903e59e48c`.
The finite KSF migration assertions were then aligned to schema20 in
`c69b845e057f46c5c3f63ff907bbfb8c55fd3bfa`; this changes tests only.

- A clean committed-source `src/build.ps1 -Jobs 8 -Pi` produces zero warnings.
  Every QC output is byte-identical to the native-tested `build-final2` output.
  The exact-commit offline deployment suite passes all19 again.
- Full Linux deployment-shell suite, **staged tests only**, from `c69b845`:
  all22 suites pass including accounts/social/KSF migration/profile/top-up.
  MOM `.mtv` conversion is skipped because no external fixture is on that host.
  Original failed stage is retained: old KSF assertions expected19, and the
  manual stage omitted nginx. Correcting those premises required a complete
  rerun. The unsupported `-TestOnly` attempt made no remote change; instead the
  actual parsed deployment-suite shell ran against `git archive` bytes in an
  owned non-web scratch root. No live modules, DB, backup, reload or migration.
- Pi progs swap: all12 fresh lobby rows showed0 players. Both `.new` files
  hash-verified, swapped with `.prev` preserved, all12 lobbies restarted.
  `pi-progs.log` is the private receipt. At 03:48:49Z, all12 are live and the
  destination hashes below match. No `menu.dat` is shipped to the Pi.
- Dual Windows copy completed 03:35:12Z, with games idle; both installs' three
  QC hashes match the clean build, previous changed progs kept as `.prev`, and
  compiled CSQC cache `844e6e86.dat` seeded. Protected owner/lobby cfg hashes
  remained unchanged. `windows-progs-receipt.json` records before/after/UTC.
- `pi-native`: a fresh isolated client connects to the updated live lobby,
  loads the new Players tab (one real row) and labels module, then exits with
  no command/VM errors. No other body is present, so this is NOT a new label-
  visibility or performance measurement. Friends correctly remains not-ready
  without its backend. Debug text obscures the screenshots; the earlier local
  three-client screenshots establish layout, not these diagnostic captures.

Installed hashes (both Windows installs and the two Pi progs):

```
qwprogs.dat a06afa8f208d04d3010c8846615aea6ed5ccbbb621b2f4303236d0a97985e62d
csprogs.dat b2f50b192ec571b2c6a1caf2cf03f47718ef21ccb70c7d3d5aebd4c9438f1b19
menu.dat   44f12fd918278bd160db66f6cfb45b176d56eeb6290e3d28e6365e81e3bbcbd9
```

**This is partial delivery, NOT a live friends backend.** At 03:48:49Z live
schema is still18, social.py is absent, and all five measured live backend source
hashes remain unchanged from startup. Read-only P717 launch inventory was
requested but no approval has been received; no exclusion, worker retirement,
backend source installation or schema transition was attempted. Human acceptance
can exercise roster/profile/labels now; fleet Friends/Join/PM awaits that gate.

Scratch disposition: the two owned Linux test stages at
`/srv/nvme/agent-work/friends-01a13cdc-stage-20261015T0328Z` and
`...-20261015T0345Z` retain OWNER/shell/suite logs/per-suite outputs/provenance;
source/tar/TMPDIR copies are retired. The Windows task root retains source and
private test evidence for the blocked backend continuation. Historical NoDeploy
outputs are hash-verified into `historical-nodeploy-builds.zip`; only the final
native-tested build remains unpacked. No owner/peer process was stopped.

## Remaining acceptance

See `lextest.md` for human wording/layout, real cross-install account use and
busy-lobby surfing/contrast/performance. The final real-client rig exercises Join,
Spectate and mute button clicks. 64-player roster layout/scroll and the Players
search-result/Back runtime path remain unmeasured acceptance; transport capacity
and reviewed source integration are not substitutes for those UX observations. No native/package release,
external Steam/R2 picture fetch or generic Steam-game presence is claimed.
