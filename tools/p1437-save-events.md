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

Source `68679ee9` and engine journal `2af03bfe` are published. The clean source
built all three VMs with zero warnings. The production-entry rebuild reproduced
all six DAT/LNO artifacts byte-for-byte; QC Build 89 and native pins did not move.

- Both Windows installs received matching QW/CS + LNO at
  `2026-11-08T21:19:06Z`, retaining immediate `.prev` and prior predecessor history.
  All 1,481 checked native/menu/config non-targets were unchanged.
- The existing `build.ps1 -Pi` deployed that same QW/CS pair and restarted all
  twelve lobbies, using the normal ten-second warning and no `-PiForce`.
  Fresh status replies and hashed loopback `serverinfo` reads proved all twelve
  actors live and advertising `fs_savelead=3` by `2026-11-08T22:00:41Z`.
- QW SHA256: `ac44d5871ad69289aa847e74665b6f23b2c5d43ac59f04a4d56dd77af5dd7226`.
  CS SHA256: `e7e4c69d6ab18ca4662decef49df152150f7b1fc0e569529052e435e1b3a5c79`.
  Immediate Pi `.prev` files match the inspected predecessors. All 553 checked
  native/menu/config/helper non-targets and the backend descriptor/actor stayed
  unchanged; no backend activation or native deployment is implied.
- Before any Pi canonical stage/restart, all 213 current recorder/resume/generated
  predecessor archive members were individually rehashed on-box and off-box.
  A fresh read-only post observation retained all 53,983 old data-file prefixes,
  with zero observed appends, missing paths or changed prefixes. The thirteen
  declared current actors had zero open preserved-domain FDs at that observation.
  This is bounded operational preservation, not a general file-writer audit.

The immediate post-restart status observer timed out. That failure is retained;
subsequent fresh observations are separate evidence, not a regraded pass. No
healthy lobby was restarted again and no player data was restored.

The fresh-client download/render smoke was **not launched**: available Windows
RAM was 2.368 GiB, below the existing 4 GiB guard. Served-cache download and actual
owner feel remain pending. No release or Build bump is part of this task.

## Remaining owner checks

`lextest.md` contains the small tap/hold/step check. Persistent missing func brushes
until reload/reconnect remain unproven and are tracked in `BACKLOG.md`: distinguish
visibility/PVS from missing draw submission, do not hide culling globally or credit
this camera fix as a demonstrated brush-visibility fix.
