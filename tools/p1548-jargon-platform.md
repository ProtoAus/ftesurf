# P1548 — JARGON platform area and event-aligned initial steering

## Problem and method

JARGON is a native-rollout model-predictive search. Its curve search uses a
cross-entropy method (CEM), initialized with a small fixed steering grid. A guide
point is not itself a landing surface, and a halfway division of nonuniform
ride knots can force late-ramp and air corrections into the same steering band.
This patch improves those search inputs, not the physics or controller gains.

For an eligible endsafe goal, QC binds one endpoint-local rectangular BHOP
permission region to one nearby course-owned end portal. Permission alone is
insufficient: five full-hull downward probes must find the same flat static
world support. The footprint is inset for the supported feet-origin hull.
Steering uses its nearest point; native grounded arrival after flight has its
own score band. A real end hit remains a separate outcome, and may finish in air.
Initial ambiguity retains the legacy objective. A changed zone-table generation,
goal or portal cancels the active search before tape advancement rather than
changing the fitness domain underneath stored candidates.

A supported final-platform landing is progress, not a failed ramp merely because
passive drift misses a door. The finish handoff rechecks actual static support,
then guides forward toward the captured eligible portal in four-tick steps,
recomputing yaw each step. Actual game finish is still required. Two game seconds of requested native steps at the latched run clock
without four units of closer progress pauses navigation on the platform, without
backtracking; it does not impose the old six-second passive-coast deadline on
active walking. This is straight ground guidance, not obstacle routing or a new
persistent checkpoint/save format. Unsupported or airborne cases keep the
existing coast flow.

The initial two-band grid uses the available launch window, or catch window when
launch is absent. If neither option is active, it uses the ride-knot boundary
already supplied by the guide. Production knot timestamps choose the partition.
Empty-side and ineligible cases retain the exact old midpoint, including odd
knot counts. No extra user knob, trial, generation, RNG draw or controller
constraint is added. This is **event-aligned CEM seeding**, not a learned policy,
a gradient method, a new global route planner or a claim of optimal control.

## Verification status

- Two scoped independent source reviews: no high/medium findings. The handoff
  review's timing note was corrected: the watchdog uses the latched `run_t_tick`,
  not a hard-coded15ms conversion.
- Existing standalone CEM suite:4381checks, including launch/catch/ride boundaries,
  odd counts, empty-side fallback and non-native modes. Synthetic timing is not
  physical proof.
- Direct standalone execution of extracted rectangle/cache/landed predicates:
  17checks. Synthetic table/entities only, no native trace/owner/physics claim.
- Recording reader:949checks,0failed. No recording grammar or hash serialization
  changed. The existing local corpus contains old faults; it is not called clean.
- On the exact accepted P1543 native trio, the matched midpoint control finished
  13.110seconds and the event-aligned arm12.285, both four backtracks. Both
  complete REC14exports have six board events and zero strict reader faults.
  The earlier old-native snapshot is retained separately, not current evidence.
  These measurements precede the active ground-handoff addition.
- The controlled midpoint log also proves the handoff defect: actual grounded
  platform reach, passive-coast rejection, then a ramp backtrack. Owner confirms
  the platform is enclosed except the entry and has a central door portal; that
  is geometry/design input, not acceptance of the new controller.
- Active handoff: three VMs compile with zero warnings; follow-up source review
  is clear. Acting current-native runtime remains pending; the first launch was
  refused by an occupied shared-rig lease before any game actor, not a controller
  result. The rate-note correction still needs the final clean build.
- Clean source build and dual Windows QC promotion pending. No Pi/backend/
  release/Build or new native-image claim.

## Limits and owner check

Five probes are a conservative heuristic, not proof that the whole rectangle has
no holes. Ambiguous/nonrectangular permission areas, moving support and
incompatible hulls fall back rather than invent a surface. Other maps, seeds,
first-contact loss, optimal dip/launch energy and perceived path quality are not
established by one successful timer finish. The small visual check is in
`lextest.md`; prior owner detection feedback is not new-route acceptance.

Native commit/tag and qcbuild89 remain pinned. This patch changes QC only.
