# P732 — explicit Monolith B4 KSF compatibility

## Scope and cause

Momentum's `surf_monolith` converts B4's opposed-ramp launch into a one-shot
`trigger_setspeed` (*108, horizontal1662, vertical398.301). Real dedicated
controls settle at1643.1304, not the supplied KSF clips'1668→1663 transient.
The original CSS BSP supplied by the operator has identical collision/geometry
lumps, but its corresponding `trigger_multiple` scripts entry X=-1760/Z=0 and
exit X=-1638 while preserving Z. Raw CSS-script emulation settles at1638 and
**does not recover the effective KSF server behavior**. Neither generic VScript
nor an inferred implementation of `StrictMode` is claimed here.

This patch deliberately chooses a reference-tuned compatibility policy for that
known converted pad:1662/Z0 on grounded opposed-face entry;1784/Z0 on its next
actual moving contact;1662/currentZ on downstream exit. The native ramp supplies
the lift. It is not a global multiplier, an edit to the BSP/zone library, or a
claim that the author wrote those effective phases. The original failed/probing
arms and source provenance remain in `p728mapfix.md`.

The profile checks map/class/model, both speed modes/values, angle, StrictMode
and absence of EveryTick/OnThink. Airborne/jump/side/reverse/noclip entries and
other pads keep the existing handler. Native `run_movetick` is reused, not a new
input clock; its unchanged declaration moves before the timer. Same-command and
zero-tick touches cannot advance the phase. Exit finalization runs before the
next command in a batch AND at packet end before `SV_RecState`, not just once per
network packet. Side exit, timeout, invalid pad, warp, hold and spawn retire
pending state. Existing `SV_RecWarp("speed")` records authoritative changes.

## Eligibility and evidence

The known ramp's next moving command may inherit the force's causal lift through
existing `run_pushed`/`run_pushlift`. Zero-tick commands do not spend it. Once the
mover advances, later commands cannot inherit it. Jump input cancels a pending
contact without replacing its real vertical rise: preserving the latch alone is
not enough because JumpWatch first needs a velocity edge. There is no blanket
start-rule disable and no older hopped/dirty clear. Actual placements reset the
profile; ghost swept-zone/padding restamps do not move the body and preserve it.
`PlayerPostThink` now retires pushed/jumpcmd on normal, timer-early-return and
held packet exits, in addition to the existing jump-watch clear.

There is no recorder grammar, signed protocol, receipt, backend, native engine,
engine commit/tag or QC Build-number change. A normal timer classification is
not proof of a community submission being accepted. No terms/account consent
or ranked submission was performed for these controls.

## Verification

Owned root: `C:/FTESurf-worktrees/mapfix-01a13ff6/`. Initial lab artifact names
retain `p730` (the original reservation). Before committing, both trees were
fast-forwarded over the published P731 UI change to QC53a50f3/engine826f0e988;
that published change is preserved. The old730 reservation was retired and
ONLY732 claimed after refetching (published max731). No peer working-tree source
or index was used. QC-only: retain native P729 pin/tag and qcbuild89.

- Acting pre-change dedicated control:1643.1304 at normal66 and batched20pps.
- Product-path normal/batched launches:1668.8672,1665.9363,1663.0054 transient,
  then1662.0000; normal/recording1, hopped0, dirty0. First two dx/dz steps match
  all four supplied clips within0.001 units. No probe writes body velocities.
- Real earlier held-hop control establishes hopped1; the later acting booster
  still reaches1662 but remains practice/hopped1. This is not taint forgiveness.
- Prosurf B4 regression:2275, normal/recording1, hopped0, dirty0.
- Actual-source QC fixture:50 predicates covering exact/negative guards,
  independent players, duplicate/zero-tick contacts, physical-progress expiry,
  the actual JumpWatch outer velocity gate and fresh taint, generated-rise clean
  control, older taints, warp/hold/side/timeout/invalid cleanup, real ghost frame/
  exit, re-entry and command-before-physics exit finalization. A one-line exit
  mutant gives43pass/1fail against the initial44 checks. Independent review then
  found two missing cases: the strengthened50-check fixture gives45pass/5fail
  against the exact pre-fix source and50pass/0fail after correction. These are
  actual-QC VM calls, not a translated Python model or only an inner predicate.
- Three real-client packet cases seed all latches and wait for `run_pkn` to
  advance: normal, no-zone early return and native held command all act/clean.
- Existing prefix serializer's nonlive control returns0; a naturally started
  live run writes212 lines. The new active-run prefix passes the reader. Native
  `pm_recsim` reproduces32 initial-candidate and13 final-fix input packets at the
  sample-printing floor, with zero state-bit/physent-signature/digest mismatches.
  It is a prefix, NOT a
  completed/accepted record and not proof of every prestart or rewind path.
- Reader suite:306 checks,0 failures. Fresh stable read-only run corpus295 recs
  plus96 views:190 faults in BOTH control and subject. Reader bytes match the
  inspected pre-change source. Of294 save prefixes,293 are readable with16
  existing faults; one historical kept fixture denies reads. No ACL, lock,
  fixture or player data was altered. Raw inventory/details stay private.
- Real CSQC prediction hook acts with `cl_prederror 1`. Baseline and subject both
  retain the StrictMode warning and bounded entry/step seams (about1–2 units),
  plus an occasional roughly-one-tick seam (baseline24.7/subject25.0 units).
  Test warps themselves produce large corrections and are not booster errors.
  This is no claim of a new client mirror or loss/high-latency acceptance.

Failed arms remain failures: initial product guard read `Direction` instead of
`HorizontalSpeedAngle`; it did not act and was corrected. An initial Prosurf
regression could not spawn because mixed CSS/Momentum map mounts disagreed;
restart with the owned loose Momentum BSP established the actual passing arm.
The per-packet-only exit candidate was strengthened before delivery; its first
first-two-tick/endpoint checks alone did not prove command-scoped exit timing.

`p732monolith.qc` preserves the isolated test fixture. It is NEVER listed by the
production manifest. In an owned rig, compile a copy of `sv_progs.src` with a
separate output plus this fixture appended; add `p732_unit` and
`p732_packet_probe` entities to a disposable external ENT. Fresh native socket
startup prints the50 predicates. Server `p732_case 1/2/3` exercises packet exits;
4 writes `data/p732-evidence/run.rec` using the existing prefix serializer (create
that owned output directory first). Do not use this on a live lobby/player tree.

## Independent review and correction

Three independent source lenses reviewed the clean candidate without author
conclusions. Physics found no blocking regression. Eligibility found that a
pending zero-Z write could erase a real jump before JumpWatch's OUTER velocity
gate; the old test checked only a surviving latch/inner predicate and also had
older taints already set. Evidence found that ghost bookkeeping called the
placement reset without placing the body. Both were corrected BEFORE pushing
or deployment. The fixture now invokes actual JumpWatch on separate clean arms,
actual ghost TimerFrame and GhostSet(false), with an acted rejecting old-source
control. Actual placements still clear state. Private review reports remain
private; technical scope is recorded here rather than exporting raw reports.

Native key probes reached later active phases; an exact phase1 key timing was
not captured at the tested command granularity. It is NOT claimed as the real-
input phase1 falsifier: the actual-QC detector/control above supplies that case.

Product build: `pwsh -NoProfile -Command "./build.ps1 -Jobs 8 -NoDeploy"`
from the owned `qc/src` compiles all three production manifests with0 warnings.
Initial output `qc/rig/build-nodeploy-c6a974719efa46808d6e6903df4a3c42/`;
corrected final output `qc/rig/build-nodeploy-4c92e81be77d4d16827bf4524baab528/`.
Final SSQC SHA256 `eaabe85275f3eed09cccd9125ddb3d256961b6ac10a52e18ab0bece6ce4d5862`;
CSQC/menu stay the published P731 bytes. No test symbols in product VMs.
Both canonical installs' inspected VM/native/plugin hashes are unchanged by
isolated builds. LSP does not parse QuakeC; the compiler is the code gate.
A missing relative include in a copied baseline and an escaped-newline observer
compile failed during fixture preparation; neither was a product/runtime pass.

## Delivery

Product build, independent review, source publication, dual Windows delivery
and guarded Pi delivery are separate gates. Deployment receipts are appended
only after their actual hashes/restarts/live checks. Human route/feel and other
approaches remain in `lextest.md`; no release/archive was requested or produced.
