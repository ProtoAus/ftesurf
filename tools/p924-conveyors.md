# P924 — static Source conveyor carry

This is the unpublished P921 conveyor work, renumbered forward after P922/P923
shipped. P921-labelled local test artifacts retain their original identities;
they are not an additional product patch or a claim about fleet deployment.
The existing published Build decision is preserved; this feature does not make
another Build decision.

## Contract and implementation

- `func_conveyor` remains a brush, not an additional collision or draw entity.
  Authored angles determine movedir; an absent/zero speed uses Source's 100.
  VISUAL and NOTSOLID flags do not supply a physical carrier.
- Before the existing start-cap and basevelocity handoff, SSQC arms the static
  ground carrier. Only a genuinely armed push combines; an unarmed leftover is
  replaced. The existing cash-out, Z expenditure, `ride pay`/`ride arm` and
  `run_pushed` paths are unchanged. There is no separate unrecorded velocity write.
- Use the native ground identity, not proximity to a brush bbox. Placement can
  retain ONGROUND without its ground edict; only that missing-world-edict case
  reacquires real standable contact with the live native probe parameters and
  quadrant rule. It does not change flags or the native ground edict.
- Native prediction probes the starting body's contact before carrier consume.
  An optional `CSQC_PredictGroundVelocity` callback identifies the authored static
  model/origin and supplies its velocity. Older natives do not acquire this API
  by receiving new CSQC; matching native/client delivery matters.
- Match the server's Source command pieces, including carried sub-tick time.
  Restore sequence-minus-one's carrier only for the input's first piece. Increasing
  offsets continue a logical command rather than starting another replay chain.
  EveryTick setspeed still acts on later parts; enter-only and same-part duplicate
  suppression remain distinct. A fallback preview has the next input's sequence,
  so its speculative carrier cannot overwrite the completed input's history.
- The additional string stat atomically tags a native closing phase with player
  owner and the full split command sequence. Cache it at packet receipt and seed
  only an exact owner/sequence match. Bounds and numeric parsing reject malformed,
  nonfinite, overflowing or out-of-range values. The float partition count is
  validated before integer conversion and admits at most 32 pieces; outliers use
  the existing bounded mover path. No server time-budget check is relaxed.
- This patch adds no mover version, evidence grammar or ranking-policy change.
  Published P923 changes are a separate dependency during integration.

Dynamic conveyor inputs and material animation are not implemented by this work.
Negative/default speed and flag branches are source-reviewed, not all runtime
fixture-tested. Do not extrapolate the measured paths to arbitrary moving brushes.

## Predictions, corrections and acting controls

The original old-client/server control is solid ground without authored carry.
On parc_colore `*48`, the subject supplies +Y567. On classics' stage-4 `*3`, it
supplies -Y2500. The standing body must move at the belt while its intrinsic
horizontal velocity is zero. After leaving, the existing one-time horizontal
cash-out is `held * (1 + tick/2)`; the measured parc velocity is about +Y571.3.

The first post-move-arm design failed with 8.51-unit errors. Merely fixing a
carrier ring reset was not acceptance. Later diagnostics found and corrected:
first-piece-only carrier restore, the completed-key preview overwrite, missing
native phase seeding, and the one missing ground-contact tick after placement.

Use normal extrapolation, a real dedicated socket, explicit client FPS/net FPS
and a .25-unit error threshold. Ignore only the expected correction caused by
an intentional placement, not arbitrary later errors. In the acting control,
only conveyor prediction was disabled; other triggers and partition topology
remained enabled. The server still carried the body. It caused seven additional
8.51–34.02-unit corrections. Three subject actors and the restored actor had none
beyond their intentional placement correction. The temporary control is removed
from product code, as are the temporary phase/part/pay/server diagnostic prints.

Heavy diagnostics changed the test's timing. Existing `sv_showpredloss` explicitly
reported ignored input milliseconds during a noisy failing actor; ACKed commands
were absent from the server's executed sequence log. Command kind identifies
origin, not whether time was allocated. Do not fix that producer/consumer artifact
by weakening server checks or by treating a quiet subset of the noisy run as a pass.

## Completed evidence and limits

- Isolated Full native/plugin build and subsequent native/QC builds: zero new
  warnings; all three QC progs report zero warnings.
- Hook-free real-socket parc and classics belt/step-off smokes: normal extrapolation
  and .25 threshold, only intentional placement corrections. Server `viewpos`
  confirms actual moving body, including retained parc +Y571.3 velocity in air.
- Real save/load on the parc belt: actual saved placement restored, then carried
  away; the load's intentional placement correction is not a movement failure.
- Independent review used physical/prediction and evidence/network-safety lenses.
  Its two P1s were fixed: EveryTick's later-part suppression and unbounded native
  partition work. Targeted re-review: OK with notes, no remaining concrete defect.
- Compiled QC unit invoked the real setspeed handler in one unused metadata slot:
  EveryTick at offsets 0/15/duplicate15 returned 1/1/0, applying Z125 then preserving
  duplicate Z-9. Enter-only control returned 1/0 and preserved later Z-7. The helper,
  dispatcher and slot are not present in product source.
- Actual extracted partition guard, including the engine's finite test, compiled
  with GCC `-O2 -ffast-math -fno-strict-aliasing`: normal200ms ->13, carry.006/148ms
  ->10,32/33 boundaries, nonfinite/overflow and100000 float-bit work-bound cases pass.
  This is guard-level coverage, not whole-engine hostile-server acceptance.
- Pre-integration recorder-reader suite: 864 checks, zero failed.
- Jump input and a separate natural legacy push-pad placement did not ACT in the
  rig. They are not passes, numerical momentum evidence or proof of a regression.
  Once-pad physical acceptance remains untested. Keep the small human checks in
  `lextest.md`; do not spend another large harness campaign claiming to replace them.

## Final integration verification — 22 October 2026 UTC

At QC `78bb485ac1ad6a07d186c4fde80855140ec983be` and native
`a0ebb9d06afd0e9fe552bb86030be34c809d97c8`, the standard isolated
`build.ps1 -Jobs 8 -Engine -Full -NoDeploy` completed: all three VMs have zero
warnings and native/plugins have zero NEW compiler warnings against the retained
Full-build baseline. The rebuilt native stamp is
`git-7710-patch-923-1-ga0ebb9d06`; the inspected source/tag is P924, not P923's
previous binary. The existing build uses annotated-tag description for its stamp.

The matching final binaries/progs passed dedicated parc and classics smoke with
normal extrapolation and .25-unit correction reporting. Both arms positively
moved across their belts; each had exactly the intentional zone-placement
correction and no subsequent above-threshold error. Native `pm_selftest` reports
all checks passed. Earlier disabled-conveyor and phase controls remain the
negative evidence; this smoke is integration confirmation, not a replacement
for those controls or owner jump/feel acceptance.

The reader suite passes864/0. The current corpus has419REC and126VIEW, including
279 faulting REC and4 faulting VIEW files /284 diagnostics, with no read errors.
This is a newer corpus than P923's captured405/120. The P923 baseline reader and
P924 reader are byte-identical (SHA256
`b22487bdc5625ed0928f393a9851a0dd32aed65a09d08c9c6ed5420228f9104f`), and
the current corpus therefore has identical baseline/subject diagnostics; none
is introduced by this feature. No player bytes were modified.

A targeted independent integration review found no issues: held checks remain
first in both callbacks, native context boundaries are intact, phase-string
cleanup does not add held effects, and closed-world coverage is unchanged.

## Delivery state

Committed/pushed and installed in both Windows copies on22October2026 UTC;
the later published P932 CSQC update was preserved and the current installed
combination acting-verified. Exact source/hash/provenance: [delivery](p931-delivery.md).

Mainline Pi promotion remains subject to its independent producer/native gate.
The separately qualified P922-based compatible variant2ec17923 retains the old
writer/native generation and is now deployed on all12lobbies after the normal
zero-player guard passed. Postflight17:59UTC confirms exact progs/.prev,12new
processes, unchanged native/plugins/configs and preserved pre-existing data
metadata. A cold-cache live client downloaded the exact CSQC and fired a real
Glock shot. No force or qualification relaxation. Owner acceptance is pending.
