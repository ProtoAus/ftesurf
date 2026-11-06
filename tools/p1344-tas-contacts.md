# P1344: native contact observations for full-line TAS sections

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

These are proposals, **not a section solver result**. A constrained next-ramp
solver and broader optimization remain work in progress in
[the human-first plan](plan-tas-human-workflow.md).

## Native and cache contract

Three optional output-only QC vectors expose schema/kind/plane distance, normal
and actual hull sweep endpoint. This endpoint is not a surface position or a
portable pose. The observer records the chosen StepMove path, not a rejected
speculative branch. It does not change movement calculations, input credit,
recorder/evidence grammar, portable state or submission authority.

Kinds are deliberately limited:

- World ramp face: a committed qualifying world-plane collision.
- No observed ramp: **not** an inferred airborne/grounded state.
- Nonworld or gap/unsupported: no ramp/free-flight guess is supplied.

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
- Existing `pm_selftest` and all 17 production observer helper cases act/pass.
  Disabled/no-contact, world index zero, nonworld, invalid indices, distinct
  planes, invalid normal/distance, output clearing and observer closure are
  exercised through the actual helper.
- Real static BSP surf ramp: positive physical/logical clocks, finite native
  normal/plane/endpoint and held-step dedup. Whole-source rows exactly partition
  the saved input range; cached final geometry agrees with the native sample.
- Actual earlier start/end navigation retains future inputs and map extent.
  A manual marker while earlier retains the complete map under its new actual
  immutable revision, with original immutable bytes unchanged (28 checks).
- An actually changed raw yaw replays natively and diverges; client current
  observations and server binding refuse that preview. Discard restores the
  full original contact map and exact source identity/bytes (24 checks).
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
cadence. That attempt is not live unsupported-scene acceptance.

No claim yet of live moving-world/ladder coverage, whole-map ramp extraction,
owner comfort, real-device control feel, globally optimal solving or public TAS
submission acceptance. The next small human check is in [lextest.md](../lextest.md).
