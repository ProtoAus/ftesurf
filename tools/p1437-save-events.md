# P1437 -- save-event and lead-in consistency

## Implemented

The save endpoint string now carries the event sequence, packed operation, saved
ticks and correlation tag together, including the saved row's origin for a save.
A client cache validates the entire capsule
at input/render callback boundaries before publishing it; getters do not tokenize.
Load consumers use that event's endpoint rather than a mutable selection cursor.
The versioned load prefix remains sequence/id-bound.

A pending capsule is not a refused rewind go or an ordinary new-run transition.
While pending, preserve retained trail/angle prefixes, defer destructive fallbacks
and do not overwrite the native load angle with the previous hold latch. The short
initial missing-HOLD allowance is bounded; after HOLD was observed, losing it ends
that allowance. This preserves the existing hold/release and authoritative load.

No native executable/pin/tag, evidence file format, detector/ranking/taint policy,
historical-data rewrite or QC Build change. The old mixed-version endpoint format
is not a fallback for the new cache: deploy the matching server/client progs pair.

## Verified

- Real isolated dedicated server/client; original controls and deliberately
  unfenced test-only variants must act, not merely stay silent.
- Split HOLD state: original camera jumped about 199 units; corrected camera had
  no large jump and release remained near the configured one-second lead-in.
- Stale operation: the original did not bind the acknowledged load; corrected
  consumption did. These are state-boundary emulations, **not packet capture**.
- Traditional nonpredicted hold, 150 ms command delay and 120 ms capsule delay:
  unfenced native angle error exceeded 82 degrees; corrected error was below
  0.004 degrees. The default prediction path alone was a nonacting discriminator
  because it had already populated the target latch; those earlier results were
  not upgraded into a pass.
- A pending successful rewind go: old fences falsely refused it/deleted a retained
  failed-attempt prefix; corrected code accepted it and transferred that prefix.
- Trail-only negative control cleared 82 pending raw rows and wrote a zero-row
  resumed picture. Corrected code preserved all 41 expected source rows exactly
  through the selected tick.
- Selection-cursor displacement control: mutable-origin comparison lost the
  retained angle prefix. Corrected event-origin association transfers it once.
  The same falsifier also exposed a separate wrong sequence destination; loaded
  sequence/zero restoration and trail stitching now use the event endpoint.
  Both saved and loaded destinations are bound: a displaced saved cursor also
  fails the old saved-column check; the corrected E8 saved-origin capsule and L14
  loaded endpoint pass both location checks. The final corrected arm passes all
  existing p817 checks, retains all 41 selected trail rows exactly, and transfers
  the retained 124-line angle prefix once.
  Cursor displacement is an emulation, not an actual server-delete claim.
- Existing off-profile load and retry checks pass. `--prof2` is **not** a
  client/VM-restart cold-load test and earns no such credit.
- `python tools/test_reccheck.py`: 949 checks, zero failed. Read-only current runs:
  561 REC +179 VIEW, 740 identical same-buffer baseline/subject reports; 346 REC
  +5 VIEW pre-existing faults, zero increase.

The existing 300 ms post-release trail-growth check is intermittent in both the
untouched control and candidate. A final arm passing it does not resolve that
baseline follow-up. No universal frame-time, PVS, hardware or owner-feel claim.

Three-VM NoDeploy compilation completes with zero warnings in each VM; final
source-matched probe compilation also completes without warnings. QuakeC is
validated by fteqcc/runtime, not by an empty LSP diagnostic list.

## Deployment

Not deployed yet. Source verification, clean commit build, destination hashes and
live behavior are separate gates. No release or Build bump is part of this task.

## Remaining owner checks

`lextest.md` contains the small tap/hold/step check. Persistent missing func brushes
until reload/reconnect remain unproven and are tracked in `BACKLOG.md`: distinguish
visibility/PVS from missing draw submission, do not hide culling globally or credit
this camera fix as a demonstrated brush-visibility fix.
