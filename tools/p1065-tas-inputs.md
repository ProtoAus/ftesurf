# P1065: bounded TAS input edits and affected-tail recalculation

This adds a console input editor to P1055 pause/step and P1061 exact tick rewind.
It is **assisted practice**, not a human/segmented run or a public TAS board.

## Use

On the matching native/server/client, use `cl_threadedphysics 0`, walk out of a
start so the timer is running, then `tas pause`. Hold an input and grant ticks
with `tas step` / `tas step N`. These must be newly captured exact checkpoints.

- `tas inputs` lists the last8 effective inputs; `tas inputs N` lists1..16.
  The printed numbers are **run ticks**, not relative offsets. Bits are
  jump1/duck2/walk4; aim is printed in degrees.
- `tas replay FIRST` restores the exact warm prefix at FIRST-1 and recalculates
  every stored command from FIRST through the previous head, unchanged.
- `tas edit FIRST FIELD VALUE` changes one command, then recalculates that tail.
- `tas edit FIRST LAST FIELD VALUE` changes the inclusive selected range, then
  recalculates the entire affected tail, including the unmodified later inputs.

Fields: `forward`, `side`, `up` (integer -32768..32767); `pitch` (-89..89),
`yaw` (-360..360); `jump`, `duck`, `walk` (0 or1). Numeric arguments are plain
decimals, not expressions/exponents. Duck changes only the duck button, not
vertical movement. Untouched aim preserves its original command words; edited
aim is deliberately quantized to the normal command-angle resolution.

Example: if the list shows retained ticks101..108, `tas edit 103 104 yaw 30`
changes those two commands and recalculates103..108 from the exact tick102
checkpoint. It reports **queued**, then **completed** only after actual native
movement and the expected recorder/timer head have settled. Completion stays
paused. Inspect the new `tas inputs` and use normal `tas back`/`tas step`.

`tas play` or `tas off` cancels replay immediately. Step/back/new edits conflict
with an active replay and refuse. Off restores normal control, **not** clean
ancestry. Unsupported clocks/context, lost ownership or execution faults clear
the tape terminally; returning to supported settings cannot resume old work.

## Deliberate limits

- At most128 affected tail ticks, and every row plus the prefix needs an exact,
  current-attempt warm checkpoint/input. Missing/gapped/old/unsupported history
  refuses before a destructive restore; no nearby pose or demoted-load fallback.
- Movement/jump/duck/walk and aim only. Attack/use/weapon/impulse/VR input is not
  editable. Passive cursor coordinates are not movement inputs and are omitted;
  replay clears live cursor/VR/weapon extras instead of substituting them.
- Current rules and shared world, not a world snapshot. Other players, moving
  objects, audio and world time do not rewind. No all-map/water/ladder/dynamic
  world or bit-identical full-state claim.
- Edits replace the recalculated branch. There is no project save/load, undo,
  branch browser, optimization, timeline GUI or signature/TAS board yet.
- Old natives refuse the new commands; existing pause/step/back remain separate.
  Matching Windows installation and live-lobby rollout are separate provenance.

## Verification

The actual production C admission/input/queue headers pass100236 checks, covering
signed angle words/movement masks, numeric bounds, headroom, complete staging,
identity, ordered successful consumption and terminal old-handle rejection.
Real dedicated-socket controls use distinct forward/side/jump/duck commands:
unchanged replay matches printed pose/velocity/carry/hull/eye despite opposing
live input; edited side/jump/duck slices match directly simulated identical input
controls. Yaw90 matches a directly simulated world-wish-equivalent control; first
retained aim and a one-row45-degree replay agree with entity view. Unselected
rows/fields stay unchanged. These are printed-precision movement controls, not a
bit-identical proof. Render/net30/20 and240/144 retain the exact affected count.
Malformed input, missing prefix and duplicate tickets do not move the player;
active step conflicts refuse. Play/off cancellation and an **actually applied**
unsupported clock cannot revive old tape. An edited attempt finishes as TAS;
the produced REC is reader-clean. This operation alone need not create a VIEW
sidecar; existing corpus pairs are checked, not fabricated.

Reader suite930 checks0failed. The current corpus is identity-identical to the
previous inspected control:497REC,167pairedVIEW,10unpairedVIEW,306existing findings
in305faulted reports, no increase. Standard builds retain only existing warnings.
Source includes the already published P1064 audio and P1062 menu/API work; this
feature does not change volume/mute, menu preferences, backend services, schemas,
Build89 or release0.1.32. Human camera/input feel is still pending in lextest.md.
