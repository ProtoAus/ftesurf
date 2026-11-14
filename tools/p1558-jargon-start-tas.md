# P1558 — JARGON ramp-first openings and purple TAS runs

## Request and scope

Prefer an ordinary opening jump toward ramp 1 rather than returning to the start
platform for another hop. Preserve guide-authored bhop-area openings, including
surf_prosurf bonus 4. Show the full **Tool Assisted Speedrun** tag and purple TAS
completions for JARGON and per-player slow-motion assistance. Ordinary completions
are green; clean segments are blue.

QC-only. No native engine implementation, physics change, REC grammar/version,
ranked-admission relaxation, release, native pin/tag or qcbuild89 change. The
historical unshipped P1553 claim/test labels are retained; after P1557 published,
fetched max+1 became the single active feature number P1558.

## Implementation

- Ordinary known-first-ramp openings reject an extra takeoff, return to the start
  floor or too-late copied opening jump before handover. Native first-board search
  releases its ordinary forced jump and guide jump buttons, and skips ordinary
  pre-board floor-hop waypoints. Existing Rule4096 opt-out remains.
- Failed openings wait for pending/tape work and use existing legal placement for
  a fresh attempt. Failed legal placement refuses; it does not fabricate a body
  origin/velocity. No-known-ramp guides retain the exact old bounded jump-count
  fallback.
- Authored, permitted opening floor hops remain available, including pre-clock
  guide rows and a preceding floor-hop waypoint at a plan join. Permission is
  bounded by the selected course's start-entry row, not an earlier stage's hops.
  This is a routing preference, not a new per-simulation legality fence.
- Display ancestry includes retained slow assistance as well as native TAS. The
  run remains cheat/practice/unranked. Native controls and native-used ancestry
  stay separate: a slow-only run, including a save restored while slow, must not
  acquire native controls simply because its display class is TAS.
- Cold/warm writers and both identity readers preserve that separation. An
  incomplete observation is conservative. Native-TAS snapshots keep their native
  ancestry. Old recordings are not retrospectively guessed to be slow-only.
- Full TAS status, clock/finish/banner/chat/results use purple. Stopped clocks
  remain grey. Ordinary finishes are green, clean segments blue; pace/delta
  meaning is unchanged. Returning speed to1 does not remove assistance already
  used in the same attempt.

## Predictions and falsifiers

An ordinary actual opening must release extra jump and reach a physical first
ramp; a quiet optimizer proposal is not arrival. A genuinely authored B4 opening
must still select and execute its permitted hop route. An earlier stage's hop
must not grant permission to a selected later stage. No-known-ramp behavior must
stay source-equivalent to the prior bounded jump-count fallback.

A live slow-only attempt must show TAS while native-used/control mode stay0,
including speed restoration, clean-slot load while slow, assisted cold-slot and
warm-slot load. Actual saved ancestry must agree with live readers/application.
A real finish must produce full TAS text and purple UI. Ordinary unassisted
control must not say TAS. Reader faults and protected player/config bytes must
not regress. These checks do not claim course completion or optimal energy.

## Verification completed

- Independent scoped source reviews closed the concrete opening-course,
  no-known-ramp compatibility, reader/application and native-ancestry findings.
  Selected-course negative scope and legacy fallback equivalence are source
  checks; they are not advertised as additional gameplay arms.
- An ordinary tensor2 stage2 native subject released the opening jump and
  physically reached ramp1. The bounded184second run ended at4of5, not course
  completion; no overall speedup or optimal boarding claim follows.
- Actual Prosurf B4 playback selected the authored-hop branch and played34native
  ticks with1landing and bit-equal playback. It reached0of9 within63seconds.
  This proves the exception acted, **not** that B4's route was solved. The earlier
  failed pre-clock-exception arm remains failed; the route limitation is in
  BACKLOG.md.
- The B4 observer's outer450second limit expired after gameplay/cleanup during
  protected-data observation. Original partial evidence remains unchanged.
  Read-only recovery found both actors absent, the rig lease released, and all
  18611player-data files plus input/canonical hashes unchanged, with no new file.
  Original process exit codes were not retained; none are invented. The test arm
  was not replayed merely to obtain a new receipt.
- Published intervening work was fast-forwarded into the owned tree. All8owned
  source-file hashes were identical across that integration; no canonical peer
  uncommitted source was included. Three VMs then compiled with **0warnings**
  using the same previously qualified compiler SHA256
  `1f2efd0616f60e2c3d29372cb7c32f8cad1f15cb0831d8e2490e5468048550bc`.
  A missing compiler PATH on the first final invocation produced no build; the
  existing PATH seam was corrected and the failed log retained.
- Final integrated real-dedicated-socket smoke passed **12of12** checks: ordinary
  notTAS; slow TAS/native0; clean load while slow/native0; cold and warm assisted
  ancestry0; speed1 retains TAS/native0; both assisted loads/native0; full actual
  TAS finish text. Both actors exited0; protected bytes unchanged; lease gone.
  This uses the stock Spec **zero-gravity UI fixture**, not surf movement proof.
- The final actual screenshot was inspected: large finish time, banner accent
  and TAS result badge are purple. This is automated fixture evidence, not owner
  visual/feel acceptance. The final4owned recordings have **0strict faults**;
  the original5recording UI epoch also has0.
- A later native-binding readback correctly found that the canonical client had
  advanced beyond the old frozen test client. It was not treated as a same-byte
  pass and no native alias was overwritten. A small snapshot of the **actual
  installed primary client / FTEQuake control client, FTEQuake server, plugin and
  primary menu/progs** then passed the same12checks, both actor exits0 and all
  4recordings strict0. Canonical legacy native aliases remain asymmetric and
  untouched; they are not silently normalized by this QC change.
- `python tools/test_reccheck.py`: **949checks,0failed**.
  `python tools/test_hidcheck.py`: **1627checks,0failed**.
- Required canonical `data/runs` sweep: **571recordings**, unchanged historical
  353faulty recordings +6faulty views /360diagnostics. Every original recording
  SHA/fault list and view SHA/fault list is identical; no new corpus file/fault.
  The optional full-default saved-prefix sweep encounters a protected directory
  named `run.rec`; it is not an ACL diagnosis and was not changed/deleted.
- LSP recorded no QC diagnostics; actual fteqcc, not LSP, is the compile proof.

Qualified integrated DAT hashes:

| Role | SHA256 |
|---|---|
| SSQC | `cee5787005c98862edf321fc8429ab6e564bd6a6a2482034579d81d9faedc959` |
| CSQC | `423321f5bbbac70ba8a7883163a553b82e6a7e828c75bdf9420f2e27753536a5` |
| Menu build (not a required HUD change) | `5b709a6d7fe594a25805da990234b98373dafcb47f32adcbae10196e196d8972` |

## Delivery state

Engine documentation commit `a40db77d412c594f699ae9fbb230906ebe2788c4` is published;
it adds the single P1558 entry without changing the native implementation/pin.
Final engine delivery provenance is
`1de23dfe51e12631490d312666a98fea53355718`.

**Source published:** product commit
`b51f98cf316eaf1b92553cc48b2a66dc900229cf`. The clean-commit three-VM build has
0warnings and all6DAT/LNO files are byte-identical to the acting integrated
build. Only the3temporary SRC-list output-directory directives differ; they
normalize exactly. Final provenance-only documentation does not require a rebuild.

**Both Windows installs deployed:** 14 Nov 2026 **12:09:59UTC**. The existing
build's inspected Deploy function promoted QW+CS DAT/LNO to `C:\FTESurf` and
`C:\FTEQuake`:8destinations and their ordinary `.prev` hashes match exactly.
Menus, native binaries/aliases, config and player data were preservation targets,
not delivery inputs. Actual current-native real-socket UI/lifecycle12of12 and
4strict recordings pass as described above. Final audit **12:38:22UTC**:
20188protected hashes unchanged, no added player file, all actual tested native/
menu/progs sources still bound,8target/rollback pairs correct, rig lease absent.
The earlier frozen-native mismatch observation remains retained, not relabelled.

**All12Pi lobbies deployed:** transaction completed **12:33:44UTC**, followed by
independent postflight **12:34:38UTC**. The complete existing45-statement Pi body
executed once in order for the qualified current epoch: ordinary chat warnings,
10second countdown, noForce, exact QW+CS hashes,12fresh native births and live
status responses. No native, menu, config or backend generation was shipped.
The same strict current85-source backend dependency and full payload/metadata/FD
checks passed before upload **and after the countdown before rename**. Both
previous live programs remain as `.prev`.

The first Pi transaction stopped34of45 before rename/restart when one backend
child recycled after its first healthy boundary. Its failed receipt, earlier
healthy boundary and immutable source/captures remain intact. Fresh diagnosis
proved all payloads/config/program history unchanged and closed; only the exact
2owned staged files were withdrawn into private evidence. A genuinely new actor
epoch then requalified with the same unchanged guards/profile, not a relaxed
check or re-dated failure. All217payload rows, full metadata and program member
lists matched; all3archive hashes exactly matched independently verified old
archive bytes, permitting immutable archive reuse rather than another copy.

Postflight confirms **217payloads /354315834bytes**, identity and measured full
metadata unchanged; backend dependencies/actors and native/config unchanged;
all12lobbies restarted and both destination/rollback hashes correct. Metadata
coverage excludes atime/ACL/xattr and is not a general writer-audit claim. Live
status checks are not a Linux UI/physical surf playthrough. Final Windows/native
and Pi checks have no owned process, maintenance gate or canonical stage left.
No release or Build decision was made; qcbuild89 is unchanged. After all owned
actors exited,36disposable copied fixture DAT/LNO files were retired only after
matching retained immutable products. Unique source/history, qualified images,
logs/records/reviews/native snapshots and rollback/capture archives remain
intentionally retained under the owned `jargon-sol-1113a` task roots; no player
data, link, canonical asset or peer workspace was cleaned.

Human checks remain explicitly pending in `lextest.md`: one formerly bad opening,
the permitted B4 opening if convenient, and the purple/full TAS presentation.
No project/config/player-data reset is requested.
