# P1346 — interrupted similarity-source recovery

## Scope

A durable recovery marker in existing similarity cursor storage recovers an
admitted source after interruption. Rotation and admission commit atomically;
comparisons remain outside owned write transactions; handled completion clears
only its own marker. This does not change the schema, recording/receipt formats,
comparison thresholds, historical observations, ranking or enforcement. Native,
VM, engine commit/tag pins, Build and release version are unchanged.

## Verification

Two independent fresh-context source reviews found no issues in the exact held
product diff. Windows and Linux each passed all 28 simcheck test programs,
including 11 new reservation cases. Baseline and admission-removed controls each
had seven intended failures, with actual comparison/interruption/reopen and
transaction ownership acting rather than silence being interpreted as a pass.
Reader checks passed 949 tests; primary RUNS corpus faults did not increase.

An additional Windows cap/keyset/wrap/budget combination recovered the source,
interrupted the actual wrap query without mutation, and stored two genuine
80-opportunity comparisons. Baseline SQL selected rows but failed recovery order.
A manually seeded reservation bypasses admission and therefore does not detect
an admission-only mutant; that extra coverage is NOT claimed.

Existing saves unreadability and unrelated baseline warning/import limitations
are retained in private evidence. This is not a fairness, exactly-once, elapsed
runtime or RSS guarantee. Historical observations and captures are not rewritten.

## Delivery

Source verified; backend generation promotion pending. This file is not an
activation receipt. No lobby/native/VM swap is required for this backend change.
The current-data rollback must preserve observations and the coupled existing
reader; never restore a historical database as a source-only rollback.
