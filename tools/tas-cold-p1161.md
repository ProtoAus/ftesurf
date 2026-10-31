# P1161 — fresh-session TAS project loading

## Change

Read-only input validation still requires the current native TAS actor, but no
longer requires an already-created rewind/input pool. It does not allocate one
or authorize playback. CHECK/BEGIN/PUT/ARM and failed-admission cancellation keep
their execution gates.

Legal-start placement now uses CHECK after initializing its recording serial,
then checks the existing explicit live-plan allocator when a pool is needed.
Project loading applies the common living/unheld walk-body preflight before
reading or placing either project kind. Noclip and save/watch holds are not
released or converted into playback eligibility by a load request.

No physical movement, recorded format or human-run eligibility change is claimed.
Published P1158 native and P1160 inventory work is preserved. No qcbuild or
release-number bump was performed.

## Frozen build inputs

- Native code/tag: `844619bcfdac4bdb52fc8fa81093128e76308617`, `patch-1161`.
- QC producer: `cd12d6073f1b21efe427bed453ee5b98ab28d5d7`.
- Native version: `git-8077-patch-1161-0-g844619bcf`.

Published delivery prose advanced during compilation. Both histories were merged
without changing any native/QC compilation inputs. The original tag and already
qualified images stayed frozen; they were not rebuilt or relabelled for prose.

## Implemented and verified

Two independent source re-reviews accepted the corrected native/caller boundaries.
The initial legal-pool and early body-admission findings were fixed, not waived.

Windows official Full NoDeploy build:

- No new warnings; server/menu are clean and the client retains its two known
  baseline warnings. The complete native warning multiset matches the baseline.
- Both host executables and five plugins have the expected final version. Plugin
  metadata was decompressed, CRC-checked and its adjusted central/local ZIP
  offsets checked. This is not package-manager grammar acceptance.
- Actual final-image native self-test: **1448 checks, 0 failed**.
- Actual dedicated-socket cold base load/replay from the same immutable nonempty
  game-written project, with no preparatory airborne/history/planner priming.
  Placement changes the body, and completion/movement advance by exactly its input
  row count; replay finishes paused, with no pending work or native fault.
- Actual cold legal-start replay reaches a nonzero pre-start head; the next actual
  step verifies the saved target. The old-VM/new-native counterfactual refuses
  that replay, proving the caller correction acts.
- Malformed canonical input and an actual unsupported current 20ms native clock
  refuse before placement. The malformed fractional row is an earlier canonical
  refusal, not a claimed native-decoder negative.
- Actual noclip and typed save-hold requests refuse without changing the observed
  body, hold, timer, recorder or project state. Ordinary nonwalk no-op movement
  clocks continue advancing. A no-request control proves that advancement; an
  explicitly paused owned world then isolates unchanged movement/request/carry/
  completion fields around the actual refusal. Pose/velocity observations are
  printed precision only.

ARM scratch build and controls, same frozen native source/version:

- AArch64 server and HL2 plugin build and metadata checks pass; no live files or
  units were changed.
- Actual native self-test: **1448 checks, 0 failed**.
- Production admission/input/queue C headers: **100262 checks, 0 failed** on both
  Windows and ARM.
- Complete production tape dispatcher/context/cancel/stop/publication functions
  plus the production input header: **17 checks, 0 failed** on both platforms,
  using controlled engine actor/pool/VM-field adapters. A real staged production
  tape is cancelled on unsupported admission; restoring admission cannot arm its
  old token, while a fresh BEGIN/PUT/ARM positive really grants pending input.
  The broken-admission control compiles and fails the exact refusal requirement.
  These adapter tests are not full protocol/identity or actual-player proof.

## Evidence and limits

Initial harness/header/spawn/cache/reader expectation failures are retained, not
reported as product passes. Native numeric tests completed successfully before a
colour-code reader error. An initial common-bootstrap loop unnecessarily repeated
that healthy test for two other arms; those failed wrapper records remain. The
original first completed log was correctly read, and only the missing client
arms were resumed, without another numeric run. No source, geometry, zone or
player data was changed to make a subject pass. All invoked owned peers stopped.

The ARM controls do not claim an ARM actual-client cold replay, canonical map
finish, full-world cross-platform equality, approved TAS profile, public-board
credit or human-run authority. Those remain separate TAS qualification work.

**Deployment is not claimed.** Protected-file preservation/adoption and the
current backend publisher-provenance handoff remain separate rollout gates.
No Windows install, lobby, backend generation or player data was written by this
qualification. Keep source publication, built artifacts and deployed versions
as distinct states.
