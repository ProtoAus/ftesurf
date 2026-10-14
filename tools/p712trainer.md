# P712 — demo strafe trainer

## Behavior

`hud_trainer 1` now displays the trainer while watching the game's native,
Momentum and KSF recordings through `replay`/board Watch. The recorded resolved
side movement and yaw feed the same sampler as live commands. Every input
sample is consumed once on the file clock: pause, playback speed, rendered FPS
and viewer movement do not age the runner's keys. Backwards seeks and split
changes restart a bounded 512-record/frame reconstruction; a small placeholder
hides partial results until caught up. Off/on and replay close clear stale data.
Ground/contact histories retain the existing older/newer jump navigation.

Signed SYNC is key time minus flick time: positive late, negative early. A key
held without a nearby flick is not assigned a fictitious swap time. Direction is
resolved movement, not independent proof of physical keyboard or SOCD order.
Timing cannot be more accurate than the original sample spacing. This is HUD
analysis, not verification of imported movement or an anti-cheat verdict.

Air-rate letter grades require the file's positive airaccelerate/maxspeed/
maxairspeed pin and contact coverage. Imported files typically lack that pin:
they still show L/R bands, flick marks, durations, gains and swap timing, but
say Keys only: physics unknown rather than borrow the current lobby's settings.
KSF v2's button-direction proxy lacks contact: it shows a continuous keys-only
span, not fabricated jumps. Missing movement capability explicitly abstains.
Recorded discontinuities/gaps discard an open span, retaining completed history.
Ordinary engine `.dem` files are not an additional input reconstruction path.

## Sources and controls

Task root: `C:/FTESurf-worktrees/demo-trainer-20261128-88a1/` (OWNER.md).
Initial inspected public runtime QC base: `2c2cb20ce9bfc2480b4940d5aba521ae1d4c501e`.
The complete SHA is recorded authoritatively in the task checkpoint; the source
worktree was subsequently fast-forwarded to published P710/P711 before integration.
Engine ledger base initially `30d39532016015a5e895e72869563ee5bbbc9f62`;
likewise see the checkpoint for exact resolved SHAs. No engine C was changed.

Predictions were registered in OWNER.md before edits: acting hidden control,
independent authored late/early swaps, identical replay clocks under transport
controls, capability abstention, live reset, bounded reconstruction.

From the owned QC source tree, compile in pwsh 7:

```text
cd src
pwsh -NoProfile -Command "./build.ps1 -Jobs 8 -NoDeploy"
```

Pass the exact printed NoDeploy output directory (not src/ and not a stale
ftesurf/ artifact) to the test. Both artifacts below are explicit clean builds:

```text
python tools/p712trainer.py --control --qc-artifacts <unmodified-artifacts> --out <owned-root>/control
python tools/p712trainer.py --qc-artifacts <subject-artifacts> --out <owned-root>/subject
python tools/p621trn.py --engine C:/FTESurf/ftesurf64.exe --server C:/FTEQuake/fteqwsv64.exe --qc-artifacts <artifacts> --out <owned-root>/live --sizes 1280x720 --renderer vk --timeout 180
python tools/test_reccheck.py
```

`p712trainer.py` uses a real dedicated socket and fully synthetic native,
Momentum, original KSF v2/v3 and movementless fixtures. It asserts reader action,
+15/-15 ms authored key swaps, identical native duration/timing/rate grades at
pause (including outgoing viewer commands), .25x/4x, backwards seek and off/on;
no invented air-rate grade for imports; missing inputs abstention; multi-frame
catchup for 2,100 samples; and clean replay close. Logs and screenshots expose
the panel rectangle, sampler clock/capabilities and each strafe's measurements.

## Results and limits

- All three VMs compile with zero warnings on the initial runtime base.
- Acting unmodified control: loaded all four formats, trainer rectangle zero.
- Subject: all demo assertions pass; screenshots inspected for native/Momentum,
  KSF and missing-input states. No runtime/unknown-command/reader error allowed.
- Live P621 numeric/history checks pass: 3 of first 5 jumps kept, one short and
  one empty excluded, 13 keeps total, held key unpaired and recent press timed
  from the press. BOTH control and subject fail the same 365-pixel no-strip
  rectangle check at 1280x720 Vulkan. No complete pixel-suite pass claimed.
- Evidence checker regressions pass. Exact baseline/subject fault lists match
  across 289 installed recordings: 184 pre-existing faults, no new faults.
  Only aggregate counts/digests are retained; no private run names or IDs here.
- First test KSF-v3 fixture incorrectly declared extension count zero while
  writing three cells; the real reader refused it. Corrected fixture to three,
  reran control/subject, and added a whole-log reader-refusal assertion.
- A vector-state implementation hit the compiler's exit-with-no-output failure;
  the allocated cursor and existing recorded break table build cleanly. No
  unsupported diagnosis of the exact internal compiler failure is claimed.
- The normal source branch now contains explicitly withheld P710 presentation.
  Deployment MUST use the separate clean P712-only runtime snapshot, not a
  blanket origin/main build. SSQC/menu and configs must not accidentally ship
  P710. Source committed, built, pushed, installed and live verified are distinct.

Real fleet clips, physical-key provenance/sub-sample timing and preferred HUD
placement remain human acceptance in lextest.md. Delivery SHA/hashes/UTC and
actual fleet state are recorded separately in the task checkpoint/receipt.
