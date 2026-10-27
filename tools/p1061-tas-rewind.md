# P1061: exact retained-tick TAS rewind

This extends P1055's movement-only pause/advance, not the later input editor.
Matching native, server and client programs are required. Installation/provenance
is recorded separately; source implementation is not a fleet-deployment claim.

## Controls

With the normal Source15ms driver and `cl_threadedphysics 0`, walk out of a start
so a real attempt is running, then:

```
tas pause
tas step           // one actual movement tick using current movement/buttons
tas step 7
tas back           // restore the previous retained tick; remain paused
tas back 7         // restore seven retained movement ticks earlier
tas step 7         // simulate forward again from the restored state
tas status         // completion/request/native counters plus timeline tick/hull/eye
tas play
tas off
```

Counts are integers1..128. Back requires pause, a running attempt, no queued steps
and the exact retained checkpoint. A missing checkpoint refuses without choosing
a nearby position. Reliable request tickets remain monotone; back does not undo
native movement/completion counters or grant extra forward ticks.

Open the existing rewind UI while paused in supported TAS mode. Left/right and
movement navigation taps select one movement tick; holding repeats tick selection.
ENTER restores that exact tick and stays paused, with no normal rewind countdown.
The wheel moves ten ticks. Normal non-TAS rewind retains its existing line-sample,
spatial/coarse-history and countdown policies. Unavailable ticks are not silently
approximated. Drawn geometry remains an interpolated preview, not imported state.

## What is actually retained

Each completed granted step and the pause head has an in-memory native Source
movement checkpoint alongside the existing timer/recorder-prefix state. This
includes jump/duck/carry and hull/eye state, not just position and velocity.
The native store is bounded to4000 dense slots per player, roughly one minute of
15ms steps. Rewinding trims the abandoned future; stepping forward simulates it
again from current inputs. There is no redo branch or editable input movie yet.

Native handles are tied to the current map/VM/connection and slot generation,
not accepted as a saved-file or client state import. Save files retain existing
assistance/prefix semantics, but do not serialize this native checkpoint store.
Changing map/reconnecting does not turn those files into persistent projects.

## Limits

- Each granted single-step is retained. Ordinary live playback can execute several
  physics ticks in a packet without intermediate QC/recorder prefixes; those
  missing ticks refuse. History from before native TAS capture is not invented.
- Moving-carrier captures, non-Source/changed clocks, timestamp inputs and native
  counters outside single-tick QC precision are unsupported. No fallback to a
  visually nearby point is presented as exact rewind.
- Only your movement is restored. Shared movers, other players, delayed IO,
  props, global clocks and rules remain current. Flat/jump/duck checks are not
  all-map, water, ladder or dynamic-world parity evidence.
- Changing current input after back produces a new future, but there is no input
  timeline editor, arbitrary downstream cache/recalculation, movie export,
  optimizer, signed collaboration or TAS leaderboard admission.
- Off returns to normal speed, not human eligibility. A completed assisted run
  retains TAS ancestry. No human/segmented admission policy is broadened.

## Verification

Actual-C gate suite182 checks and reader suite930 checks pass. A real dedicated
socket control walks out of the start and proves the attempt is running before
pause. Direct back1/back7 restores exact logical ticks while movement/completion
counters stay monotone; repeated flat and airborne endpoints match at the
existing printed precision. Invalid counts and old-native support refusal act.

The UI/transition arm passes31 checks: exact head, one-tick cursor, wall wait
without logical/native drift, paused go without countdown/free tick, first grant
advances both clocks, actual duck eye/hull change and duck/unduck next-state
parity. Render/net30/20 and240/144 arms restore the predecessor and reproduce the
next endpoint. Actual finish after play/off retains TAS ancestry; the resulting
REC/VIEW has zero reader faults. Existing497 RECs,167 paired and10 unpaired
VIEWs retain306 findings (305 faulted reports), not an invented clean corpus.

Initial UI checks exposed replay-viewing time and first-thaw-tick omission;
those attempts were failures, not passes. The corrected exact owned-TAS pin
excludes replay-clock accounting while keeping unrelated viewer/hold/impulse
behavior. Human aim/rewind/latency acceptance remains pending in `lextest.md`.

The remaining staged feature plan is [plan-tas.md](plan-tas.md).
