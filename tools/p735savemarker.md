# P735 — save-lock map progress markers

## Problem and scope

`surf_monolith` B4 and `bhop_futile` use `AddOutput targetname` on the player
and `filter_activator_name` on reset teleports. Saves restored the body/timer
but left today's marker behind; a cold load had no marker at all.

Capture the player's exact internal `targetname` in the existing additive
state-file contract. Restore an explicitly empty marker too. Ordinary saves,
retry/multi-session state readers, demotion rewrites, and recorded/position-only
warm rewind saves retain it. Rewind owns a bounded string buffer indexed by its
numeric ring; replacing a sample replaces its name, and reset/disconnect drops
the buffer. A captured-empty sentinel distinguishes empty from unavailable.
Unsampled replay positions cannot supply historical progress and do not borrow
the current player's name.

Restoration finishes the loading player's abandoned trigger exits BEFORE
assigning the saved marker. This retains non-name cleanup such as gravity
resets, while the final assignment replaces any abandoned progress rename.
OnEndTouchAll fires only when no peer occupancy remains. Trigger-once
consumption, shared cooldowns, peer state and map filters are not erased.
Genuine new touches continue to update map progress normally.

Legacy files without this key remain readable and keep their prior behavior;
the missing historical marker cannot be reconstructed reliably. Re-create old
saves on affected maps. This is NOT a full map-world/I/O snapshot: delayed map
outputs, counters, movers and arbitrary scripts are not rewound by this patch.
No recorder grammar, native engine pin/tag, QC Build number or release change.

## Verification

Owned root: `C:/FTESurf-worktrees/savemarker-01a14325/`.
Inspected baseline QC `bdab71288b4823f5c56ce6510422f86a774741e6`, engine
history `4dded7ad5a0fcaa79e4eff66072729d33aed3d6c` (changelog only).

From the owned game checkout, use the normal `src/build.ps1 -Jobs 8 -NoDeploy`.
The dedicated fixture uses production QC plus test-only dispatcher/spawn hooks:

```text
python tools/test_savemarker.py --baseline --out <owned-root>/control --run --progs <NoDeploy-output>
python tools/test_savemarker.py --out <owned-root>/subject --run --progs <NoDeploy-output>
```

- Actual dedicated socket, real connected actor, walking out of the start,
  running recorder and warm ring are required before assertions can execute.
- Before the callback-iteration correction, baseline: 22 expected failures in
  46 checks; corrected exit subject: 46 checks, zero failures. Controls cover real save/load/hold/release dispatch, quoted and empty
  markers, both map filter predicates with acting wrong-marker resets,
  retry/resume reader modes, original-marker preservation during demotion,
  legacy absence, sampled/unsampled rewind, physical ring wrap/overwrite,
  stale exits in both trigger modes, mixed name+gravity cleanup, exactly-once
  last-occupant outputs, peer occupancy and intact once/cooldowns.
- The unshipped first candidate `9e0a129` silently dropped all exits; review found
  that this also loses non-name cleanup. `--regression-control` reproduces four
  expected failures in 46 checks on that candidate; the corrected subject passes.
  All control graders require the EXACT expected failure multiset, rejecting
  failed actor/wrong-marker/invariant controls, not merely four required labels.
- Final callback lifetime control: `--iteration-control` reproduces the cached-
  successor bug on unshipped `a1792ff` (one failure in 49 checks). The final
  subject passes all 49 and the real cold retry. A's exit killing adjacent B
  must not fire B's retained outputs; a self-removing source must still advance
  to a live successor. Advance with nextent AFTER callbacks, which skips frees.
  Final review confirms the production lifetime fix. It notes that the explicit
  later EndThink weakens the self-removal assertion as a traversal falsifier;
  this non-blocking coverage debt is in BACKLOG.md, not a gameplay pass claim.
  The earlier 46-check control evidence remains valid for unchanged arms; no
  full authored-map gameplay traversal or full reconnect transaction is claimed.
- Real `rec_retry` queues a map restart; a spawn hook observes the actual restored
  player before legitimate new map touches can change the marker. The baseline
  loses it; the subject restores it. Both must prove sent=1 and restarted=1.
- Reader suite: 306 checks, zero failures. Paired read-only corpus: 295 recordings
  and 106 views, 190 faulted files / 193 existing faults in BOTH arms, zero
  unreadable, identical reader bytes. This is no increase, not a clean corpus.
  No owner recordings were edited.
- fteqcc is authoritative for QC; LSP has no QC parser.

Failed preparation is not evidence of a product pass: a local named like an
entity field crashed this old compiler and was renamed. Missing startup cfgs
prevented the rig loading VBSP; the runner now copies only tracked non-test
cfgs and the matching installed plugin. A negative command argument and an
unwarped random map spawn prevented initial actors. The cold probe initially
used the wrong dispatcher command, then observed after a legitimate map
OnStartTouch rename; the final probe uses the actual command and observes at
the restore boundary. Earlier logs remain local, not public test evidence.

## Delivery

Product commit `3f031b2ad1877f357e3a61f399dc74c5de1e543b` and QC-only
engine changelog descendant `a86a12701` are published to their origin/main.
The two independent reviews and focused callback-lifetime closure are complete;
no production blocker remains. The final review's optional fixture-coverage
note is recorded in BACKLOG.md. No fixture progs were deployed.

At **2026-10-16T06:22:51Z**, the clean production SSQC was copied to BOTH
`C:/FTESurf/ftesurf/qwprogs.dat` and `C:/FTEQuake/ftesurf/qwprogs.dat`, with
matching destination hashes and each immediate predecessor retained as `.prev`.
The owner game/processes were not stopped; reload the map/reconnect to load SSQC.

```text
SSQC 2015a356cdaf2706f3efd346b85b8a395abb39fb75122a1192477ed832aea6c5
CSQC 8384005ca399a546d284c4116a282a2b46e9e74273428a4176903b778961a412
menu ae77a2c2183e18299db126110ecf656aca8dcd654be520f43b8c80b5e850cbfa
prev b5ed555d980b37e13137ed0bd70acc50b5740f8d4e18e2d7047777de59c8602b
```

CSQC and menu already matched the clean build in both installs and were not
needlessly replaced. Final `build.ps1 -Jobs 8 -Pi` also compiled all three VMs
with zero warnings but **refused fleet deployment before uploading anything**:
all12 units were active, but the public directory lacked their live rows. A
read-only diagnostic saw incomplete/flapping membership (0, then9, then0), not
positive empty-population evidence. No force flag, lobby restart, remote config
change or weakened occupancy guard was used. Pi hashes remained the predecessor
SSQC and unchanged CSQC above; no `.new` swap files were left. At that checkpoint,
fleet deployment was blocked specifically by that directory/heartbeat prerequisite.

### NanoPi continuation — completed 2026-10-16T11:05:14Z

On the owner's explicit request to update the lobbies, fresh directory membership
was complete (all12 configured ports) with one Monolith player. The owner was
notified that the development rollout would interrupt that session; the existing
`build.ps1 -Jobs 8 -Pi -PiForce` entrypoint was used. This was a known populated
lobby override, not the earlier unknown-membership case.

Built in a clean isolated tree at published
`6e6c3575fe94a597d5e5fa0d6d9cb8a47f6d3bc0`; all QC, build and smoke code is
identical to verified product `3f031b2`. All three VMs compiled with zero warnings.
The SSQC and CSQC hashes above reproduced exactly, were checked after upload and
swap, and the immediate predecessors were retained as `.prev`.

Independent host readback at **11:05:14Z** proved all12 services active/running
with new PIDs and later start epochs. Program hashes match the clean build,
`.prev` matches the captured predecessor pair, no `.new` files remain, and the
native engine, hl2 plugin and aggregate cfg-tree hashes are unchanged. No native,
config, backend or player-data migration was shipped.

The existing `tools/pi_lobby_smoke.py` joined lobby2 (`192.168.1.102:27520`)
from an isolated client with NO local CSQC. It downloaded exactly the deployed
CSQC, drew the local board (8columns/type14), reported no QC error, captured a
screenshot inspected by the agent, and exited normally. Post-smoke directory
membership was all12. This is one live client/served-CSQC acceptance check, not
a full B4/futile gameplay traversal; the small owner route check below remains.

Fleet deployment is now **complete**. Receipts and smoke evidence are retained
under `C:/FTESurf-worktrees/savemarker-01a14325/`.

Actual B4/futile route acceptance is **pending** in lextest.md. The small owner
check is a NEW save from a normal run, load it, and touch the formerly resetting
ramp. Old missing-marker saves are not repaired. No complete authored-route
playthrough or multi-session reconnect acceptance is claimed.

Compact receipts/reviews/logs remain under the owned root documented above;
canonical source branches, peer edits and player data were not changed.
