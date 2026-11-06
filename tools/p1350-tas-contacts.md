# P1350: native contact observations for full-line TAS sections

Unpublished prototype1344/1347 is renumbered forward after the exact published
P1347 KSF conflict, preserving published P1345-P1348 code and receipts. Historical
helper/test IDs retain their1344/1347 source labels; this is one product patch,
not a second contact protocol or input authority.

## What this adds

The local Surf line editor's **Sections** tab has two explicit views:

- **Manual markers**: your named endpoints and overrides, unchanged.
- **Observed contacts**: derived spans from the Source mover that actually ran.
  Inputs selects that span in the existing timeline. Go to start/end uses the
  existing full-line seek; it does not import a pose or shorten the original.

A complete observation map is bound to the exact retained full input revision,
base and head. The visible body may be earlier than the head. A metadata-only
marker save can keep that map only after the strict writer validates unchanged
inputs/settings and retains/readbacks the new immutable revision. A changed-input
preview is not a current observation map: Keep/Discard remains explicit, and
Discard can restore the original complete map and source. Missing observations
can be rebuilt with the explicitly labelled **Replay unchanged to retained
head** action; this visibly moves the body and existing Play cancels it.
Literal raw-input edits also invalidate the map when there is no authored intent
metadata. A transient raw-change flag is maintained at actual mutation/harvest
boundaries and cleared only with a new retained parent snapshot; pages do not
synchronously scan an entire long line. A fresh reply is allowed to say there is
no bound map: freshness alone is not an observation-validity bit.
Both cached reuse and fresh binding require the exact SHA's successful canonical
immutable readback. Observed ordinary/template/share syntax or expected-hash
failures invalidate that exact source; unrelated range/eligibility refusals do not.
A failed canonical open in binding or share preflight also revokes its exact proof.
Restored/openable bytes alone cannot recover it; a readable but nonportable base
project's share refusal does not revoke otherwise good proof. Ordinary load reuses its first
strict read. Unknown proof queues one read-only Think invocation, separate from
the load's VM budget; page requests never perform that second whole-file read.
The UI shows an empty pending state and retries finitely without manual Refresh.
The task checks canonical file identity only: it cannot admit native inputs,
restore a body, change the original, or confer time/evidence credit. Native live
command-context and restore checks remain mandatory and unchanged.
Newly obtained, rejected or recovered proof invalidates that actor's cache through a
complete empty reserved-tag0 contacts reply. Seek/edit/history/template actions
also clear the cache before dispatch: a failed Go cannot become current merely
because an unchanged Timeline page returns. Template/share reads add no positive
proof. A real legacy source reproduces reader/UI cache defects with47 acting
checks. The latest canonical-open corrections compile cleanly; candidate cache
runtime remains pending the unchanged4GiB/60s-quiet resource gate.

These are proposals, **not a section solver result**. A constrained next-ramp
solver and broader optimization remain work in progress in
[the human-first plan](plan-tas-human-workflow.md).

## Native and cache contract

Three optional output-only QC vectors expose schema/kind/plane distance, normal
and actual hull sweep endpoint. This endpoint is not a surface position or a
portable pose. The observer records the chosen StepMove path, not a rejected
speculative branch. Recovery keeps the existing movement-normal substitution,
but reports unsupported geometry rather than pairing a potentially synthetic
normal with the new trace's unrelated distance/entity. It does not change
movement calculations, input credit,
recorder/evidence grammar, portable state or submission authority.

Kinds are deliberately limited:

- World ramp face: a committed qualifying world-plane collision.
- No observed ramp: **not** an inferred airborne/grounded state.
- Nonworld or gap/unsupported: no ramp/free-flight guess is supplied.

Native classification uses `abs(normal.z) >= .1` with an inclusive configured
standable ceiling. The decoder accepts signed native normals, checks finite
unit geometry and the fixed lower bound, and does not invent a positive-only
`.7` ceiling that is absent from this packet. Wall/zero normals still refuse.

Live samples and separately retained full-line spans have bounded allocation and
4096-row capacity. Capacity/allocation or missing native support refuses a
complete-map claim; it never silently evicts the beginning. Equal adjacent plane
observations can coalesce; distinct planes remain explicit. A physical ramp may
therefore contain several observed face rows. This is not universal ramp-ID or
ramp-extent extraction. Regions bound observed trace endpoints only; stored
velocities are first/last observed post-step velocities, not pre-impact values.

PreThink observes the previous complete native metadata/clock pair, PostThink
catches the final command, and finish observes before recorder teardown. The
per-move observer does not tokenize the command dispatcher's argv. Held/zero-step
callbacks neither erase nor duplicate samples. Missing/multistep coverage is not
backfilled with guessed events. Navigation can retain an already bound complete
original map while freezing a backwards live collector.

The contact page uses the existing editor's exact local body/request binding and
its own bounded reply tag. The receiver consumes the whole packet and checks
source, range, counts, finite geometry and current preview state. Neither a
client page nor a manual marker grants native work or authorizes another source.
Old engines report **native contact metadata unavailable**, not an empty air map.

## Qualification to date

Implemented and verified in an isolated real dedicated-socket Windows actor;
final tagged-source/review/deployment provenance is a separate delivery boundary.

- Supported `build.ps1 -Engine -Full -NoDeploy`: successful native build, all
  three QCC VMs zero warnings; no compiler warnings in modified native files.
- Current clean native code2f5c35c6b passes ARM1608/0 numeric checks, including30
  observer cases: the historical20 plus ten actual stuck-search/witness controls.
  The corresponding Windows FULL/three-VM build adds no own warning sites. These
  numeric checks do not replace real-client acceptance of the later QC cache fixes.
- Existing `pm_selftest` and all 20 production observer helper cases act/pass
  after the supported post-review native/QC build.
  Disabled/no-contact, world index zero, nonworld, invalid indices, distinct
  planes, invalid normal/distance, output clearing and observer closure are
  exercised through the actual helper. Recovery has an old normal-only
  qualifying control, production abstention, and unchanged movement-trace bytes.
- Real static BSP surf ramp: positive physical/logical clocks, finite native
  normal/plane/endpoint and held-step dedup. Whole-source rows exactly partition
  the saved input range; cached final geometry agrees with the native sample.
- Actual earlier start/end navigation retains future inputs and map extent.
  A manual marker while earlier retains the complete map under its new actual
  immutable revision, with original immutable bytes unchanged (29 post-review
  checks).
- An actually changed raw yaw replays natively and diverges; client current
  observations and server binding refuse that preview. Discard restores the
  full original contact map and exact source identity/bytes (24 checks).
- A separate completely literal line (no authored intent) reproduces the old
  changed-yaw cached-map bug (29 control checks). The fixed path retains complete
  maps on unchanged cold and warm replay, but a genuinely changed working raw
  yaw gets a fresh empty UNBOUND view and server binding refusal (29 checks).
  Original immutable bytes remain exact. This is not just a preview-flag test.
- Test-only server variants reproduce signed/boundary-normal rejection and an
  actual strict retained-file readback failure followed by erroneous fresh
  binding (32 control checks). The corrected decoder/cache passes35 checks:
  signed, inclusive and configured-band normals accepted; wall/zero refused;
  failed immutable revision stays unbound on server and client, original bytes
  unchanged. Synthetic packets are decoder contracts, not collision witnesses.
  Both temporary injection hooks are removed from production source.
- Uninstrumented corrected production checks pass metadata28/literal29/preview25
  plus22 checks including a48000-row load and intact oversized-edit refusal.
  These are pre-integration checks; merged/tagged-source and live delivery remain
  separate gates, not inferred from test counts.
- Acting old-native control moves/records normally but explicitly reports the
  observation capability unavailable. Earlier original-line marker and widget
  positive controls remain supporting evidence, not owner feel acceptance.

Preserved failures are not regraded: the initial formatter exceeded QCC's eight
TOTAL sprintf parameters; fixed before qualification. A metadata actor once
acted before the already-scheduled seek refresh completed; it now waits and
checks the real current binding without bypassing it. A diagnostic reader once
read the header before the last reliable row arrived; the existing following
status response now marks completion on the same ordered stream. A lower-FPS
attempt did **not** produce a multistep arm because the client normalizes command
cadence. That attempt is not live unsupported-scene acceptance. The literal arm
also initially lacked an exact normal-play warm prefix; its existing cold loader
now establishes one. A plain project load can close stale UI, so Sections reopens
it. A later test initially confused fresh-reply `current` with bound-map validity;
the actual reply already had flags2/no rows. The corrected assertion checks the
bound bit and empty map, and separately proves server refusal. Failed attempts
remain failed receipts, not regraded passes.

No claim yet of live moving-world/ladder coverage, whole-map ramp extraction,
owner comfort, real-device control feel, globally optimal solving or public TAS
submission acceptance. The next small human check is in [lextest.md](../lextest.md).
