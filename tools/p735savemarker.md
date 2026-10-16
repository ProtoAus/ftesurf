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
- Final baseline: 22 expected failures in 46 checks; subject: 46 checks, zero
  failures. Controls cover real save/load/hold/release dispatch, quoted and empty
  markers, both map filter predicates with acting wrong-marker resets,
  retry/resume reader modes, original-marker preservation during demotion,
  legacy absence, sampled/unsampled rewind, physical ring wrap/overwrite,
  stale exits in both trigger modes, mixed name+gravity cleanup, exactly-once
  last-occupant outputs, peer occupancy and intact once/cooldowns.
- The unshipped first candidate `9e0a129` silently dropped all exits; review found
  that this also loses non-name cleanup. `--regression-control` reproduces four
  expected failures in 46 checks on that candidate; the corrected subject passes.
  Both control graders require the EXACT expected failure multiset, rejecting
  failed actor/wrong-marker/invariant controls, not merely four required labels.
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

Pending final review, publication and destination/live verification. No fixture
progs may be deployed. Ship only a clean production build of the inspected commit.
